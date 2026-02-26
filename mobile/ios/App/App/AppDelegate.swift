import UIKit
import WebKit
import UserNotifications
import Capacitor
import FirebaseCore
import FirebaseMessaging

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {

    var window: UIWindow?
    /// URL from notification tap that launched the app (cold start)
    var pendingNotificationURL: String?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        print("[ARIA] Configuring Firebase...")
        FirebaseApp.configure()
        print("[ARIA] Firebase configured. Setting messaging delegate...")
        Messaging.messaging().delegate = self
        print("[ARIA] Messaging delegate set. Firebase app: \(FirebaseApp.app()?.name ?? "nil")")

        // Check if launched from a notification tap (cold start)
        if let remoteNotification = launchOptions?[.remoteNotification] as? [String: Any],
           let url = remoteNotification["url"] as? String {
            print("[ARIA] Cold start from notification, pending URL: \(url)")
            pendingNotificationURL = url
        }

        // Register for remote notifications explicitly
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
            print("[ARIA] Notification authorization: granted=\(granted), error=\(error?.localizedDescription ?? "none")")
            if granted {
                DispatchQueue.main.async {
                    application.registerForRemoteNotifications()
                    print("[ARIA] Called registerForRemoteNotifications()")
                }
            }
        }

        return true
    }

    func applicationWillResignActive(_ application: UIApplication) {
        // Sent when the application is about to move from active to inactive state. This can occur for certain types of temporary interruptions (such as an incoming phone call or SMS message) or when the user quits the application and it begins the transition to the background state.
        // Use this method to pause ongoing tasks, disable timers, and invalidate graphics rendering callbacks. Games should use this method to pause the game.
    }

    func applicationDidEnterBackground(_ application: UIApplication) {
        // Use this method to release shared resources, save user data, invalidate timers, and store enough application state information to restore your application to its current state in case it is terminated later.
        // If your application supports background execution, this method is called instead of applicationWillTerminate: when the user quits.
    }

    func applicationWillEnterForeground(_ application: UIApplication) {
        // Called as part of the transition from the background to the active state; here you can undo many of the changes made on entering the background.
    }

    func applicationDidBecomeActive(_ application: UIApplication) {
        // Clear badge count when app becomes active
        application.applicationIconBadgeNumber = 0

        // Proactively fetch FCM token as fallback in case delegate didn't fire
        fetchFCMTokenIfNeeded()

        // If launched from notification tap (cold start), navigate after WebView loads
        if let url = pendingNotificationURL {
            print("[ARIA] Injecting pending notification URL: \(url)")
            pendingNotificationURL = nil
            DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                guard let rootVC = self.window?.rootViewController else { return }
                if let webView = self.findWebView(in: rootVC.view) {
                    let js = "window.location.href = '\(url)';"
                    webView.evaluateJavaScript(js, completionHandler: nil)
                    print("[ARIA] Navigated WebView to \(url)")
                }
            }
        }
    }

    func applicationWillTerminate(_ application: UIApplication) {
        // Called when the application is about to terminate. Save data if appropriate. See also applicationDidEnterBackground:.
    }

    func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        // Called when the app was launched with a url. Feel free to add additional processing here,
        // but if you want the App API to support tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(app, open: url, options: options)
    }

    func application(_ application: UIApplication, continue userActivity: NSUserActivity, restorationHandler: @escaping ([UIUserActivityRestoring]?) -> Void) -> Bool {
        // Called when the app was launched with an activity, including Universal Links.
        // Feel free to add additional processing here, but if you want the App API to support
        // tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(application, continue: userActivity, restorationHandler: restorationHandler)
    }

    // Forward APNs token to Firebase so FCM can map it to an FCM registration token
    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        print("[ARIA] APNs device token received: \(tokenString.prefix(20))...")
        Messaging.messaging().apnsToken = deviceToken
        print("[ARIA] APNs token forwarded to Firebase")
        NotificationCenter.default.post(name: .capacitorDidRegisterForRemoteNotifications, object: deviceToken)
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("[ARIA] APNs registration FAILED: \(error.localizedDescription)")
        NotificationCenter.default.post(name: .capacitorDidFailToRegisterForRemoteNotifications, object: error)
    }

    // Handle notification tap when app is in background (not killed)
    func application(_ application: UIApplication, didReceiveRemoteNotification userInfo: [AnyHashable: Any], fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void) {
        print("[ARIA] didReceiveRemoteNotification: \(userInfo)")
        if application.applicationState == .inactive,
           let url = userInfo["url"] as? String {
            print("[ARIA] Notification tap from background, navigating to: \(url)")
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                guard let rootVC = self.window?.rootViewController else { return }
                if let webView = self.findWebView(in: rootVC.view) {
                    webView.evaluateJavaScript("window.location.href = '\(url)';", completionHandler: nil)
                }
            }
        }
        completionHandler(.newData)
    }

}

// MARK: - Firebase Messaging Delegate
extension AppDelegate: MessagingDelegate {
    func messaging(_ messaging: Messaging, didReceiveRegistrationToken fcmToken: String?) {
        guard let token = fcmToken else {
            print("[ARIA] FCM delegate fired but token is nil")
            return
        }
        print("[ARIA] FCM registration token: \(token.prefix(30))...")
        injectFCMToken(token)
    }

    func injectFCMToken(_ token: String) {
        // Inject FCM token into WebView so JS can register it with the server
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
            guard let rootVC = self.window?.rootViewController else {
                print("[ARIA] No rootViewController found for FCM injection")
                return
            }
            if let webView = self.findWebView(in: rootVC.view) {
                let js = "window.dispatchEvent(new CustomEvent('fcmToken', {detail: '\(token)'}));"
                webView.evaluateJavaScript(js) { _, error in
                    if let error = error {
                        print("[ARIA] FCM token injection error: \(error)")
                    } else {
                        print("[ARIA] FCM token injected into WebView")
                    }
                }
            } else {
                print("[ARIA] No WKWebView found for FCM injection")
            }
        }
    }

    /// Fallback: proactively fetch FCM token if delegate hasn't fired
    func fetchFCMTokenIfNeeded() {
        Messaging.messaging().token { token, error in
            if let error = error {
                print("[ARIA] FCM token fetch error: \(error.localizedDescription)")
            } else if let token = token {
                print("[ARIA] FCM token fetched proactively: \(token.prefix(30))...")
                self.injectFCMToken(token)
            } else {
                print("[ARIA] FCM token fetch returned nil")
            }
        }
    }

    private func findWebView(in view: UIView) -> WKWebView? {
        if let webView = view as? WKWebView { return webView }
        for subview in view.subviews {
            if let found = findWebView(in: subview) { return found }
        }
        return nil
    }
}
