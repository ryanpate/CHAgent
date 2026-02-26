# Native iOS Phase 3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 5 native iOS features (offline fallback, share sheet, deep links, local notifications, quick actions) to strengthen App Store approval and improve UX.

**Architecture:** Each feature is independent — a Capacitor plugin or native Swift code that hooks into the existing WebView app. Backend changes are minimal (one new Django view for AASA). Most work is in `mobile/src/app.js`, `templates/base.html`, and `AppDelegate.swift`.

**Tech Stack:** Capacitor plugins (`@capacitor/network`, `@capacitor/share`, `@capacitor/local-notifications`, `@capacitor/app`), native Swift (UIApplicationShortcutItem), Django (AASA endpoint)

---

### Task 1: Offline Fallback Page

Install `@capacitor/network` and create a branded offline page that displays when the WebView can't load.

**Files:**
- Create: `mobile/src/offline.html`
- Modify: `mobile/src/app.js`
- Modify: `mobile/package.json`

**Step 1: Install the network plugin**

```bash
cd /Users/ryanpate/chagent/mobile
npm install @capacitor/network
npx cap sync ios
```

**Step 2: Create `mobile/src/offline.html`**

This file is bundled locally in the app and shown when the server is unreachable.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>ARIA - Offline</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f0f;
            color: #e5e5e5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
            padding-top: env(safe-area-inset-top, 0px);
        }
        .container {
            text-align: center;
            max-width: 320px;
        }
        .icon {
            width: 64px;
            height: 64px;
            margin: 0 auto 1.5rem;
            opacity: 0.5;
        }
        h1 {
            font-size: 1.5rem;
            color: #c9a227;
            margin-bottom: 0.5rem;
        }
        p {
            color: #888;
            font-size: 0.95rem;
            line-height: 1.5;
            margin-bottom: 1.5rem;
        }
        button {
            background: #c9a227;
            color: #0f0f0f;
            border: none;
            border-radius: 8px;
            padding: 0.875rem 2rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
        }
        button:active { opacity: 0.8; }
        .status {
            margin-top: 1rem;
            font-size: 0.8rem;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="container">
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="#c9a227" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8.288 15.038a5.25 5.25 0 017.424 0M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0M1.924 8.674c5.565-5.565 14.587-5.565 20.152 0M12.53 18.22l-.53.53-.53-.53a.75.75 0 011.06 0z" />
        </svg>
        <h1>You're Offline</h1>
        <p>ARIA needs an internet connection to load. Check your Wi-Fi or cellular connection and try again.</p>
        <button id="retry-btn" onclick="window.location.reload()">Try Again</button>
        <p class="status" id="status-text">Waiting for connection...</p>
    </div>
    <script>
        // Auto-retry when connection returns
        if ('onLine' in navigator) {
            window.addEventListener('online', function() {
                document.getElementById('status-text').textContent = 'Connection restored! Reloading...';
                setTimeout(function() { window.location.reload(); }, 500);
            });
        }
    </script>
</body>
</html>
```

**Step 3: Add network monitoring to `mobile/src/app.js`**

Add this import at the top of `app.js` (after the existing imports at line 5):

```javascript
import { Network } from '@capacitor/network';
```

Add this function before the `init()` function (around line 30):

```javascript
async function setupNetworkMonitoring() {
    // Listen for network status changes
    Network.addListener('networkStatusChange', (status) => {
        console.log('[ARIA] Network status:', status.connected);
        if (status.connected) {
            // If we're on the offline page, reload to get back to the app
            if (window.location.href.includes('offline.html')) {
                window.location.reload();
            }
        }
    });
}
```

Call `setupNetworkMonitoring()` at the start of the `init()` function (line 31, inside `async function init()`), before the authentication check:

```javascript
async function init() {
    // Monitor network connectivity
    await setupNetworkMonitoring();

    // ... rest of existing init code
```

**Step 4: Test manually**

1. Build the iOS app: `cd /Users/ryanpate/chagent/mobile && npx cap sync ios`
2. Open in Xcode: `npx cap open ios`
3. Build and run on device
4. Turn off Wi-Fi and cellular data
5. Navigate to a new page — should see the offline.html page
6. Turn Wi-Fi back on — should auto-reload

Note: The Capacitor WebView automatically shows local pages from the app bundle when the server is unreachable. The `offline.html` page is served from the `src/` directory which Capacitor copies to the app bundle. The WebView error handler in Capacitor can be configured to redirect to this page. However, since Capacitor's server config points to `https://aria.church`, the offline page needs to be loaded via a custom error handler.

To handle WebView load failures, add this to `AppDelegate.swift` after the `findWebView` function (around line 182):

```swift
// MARK: - Offline Fallback
extension AppDelegate {
    func setupOfflineHandler() {
        // Observe WebView navigation failures
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleWebViewError(_:)),
            name: NSNotification.Name("CAPWebViewLoadFail"),
            object: nil
        )
    }

    @objc func handleWebViewError(_ notification: Notification) {
        guard let rootVC = self.window?.rootViewController else { return }
        guard let webView = self.findWebView(in: rootVC.view) else { return }

        if let offlineURL = Bundle.main.url(forResource: "public/offline", withExtension: "html") {
            webView.loadFileURL(offlineURL, allowingReadAccessTo: offlineURL.deletingLastPathComponent())
        }
    }
}
```

Call `setupOfflineHandler()` at the end of `didFinishLaunchingWithOptions` in AppDelegate.

**Step 5: Commit**

```bash
cd /Users/ryanpate/chagent
git add mobile/src/offline.html mobile/src/app.js mobile/package.json mobile/package-lock.json mobile/ios/App/App/AppDelegate.swift
git commit -m "feat: add offline fallback page with network monitoring"
```

---

### Task 2: Native Share Sheet

Install `@capacitor/share` and add share buttons to follow-up detail, chat messages, and volunteer detail pages. Share buttons only appear in native app mode.

**Files:**
- Modify: `mobile/package.json`
- Modify: `templates/base.html` (add share script for app mode)
- Modify: `templates/core/followup_detail.html` (add share button)
- Modify: `templates/core/chat_message.html` (add share button on AI responses)
- Modify: `templates/core/volunteer_detail.html` (add share button)

**Step 1: Install the share plugin**

```bash
cd /Users/ryanpate/chagent/mobile
npm install @capacitor/share
npx cap sync ios
```

**Step 2: Add share utility script to `templates/base.html`**

Add this script block inside the existing Capacitor/app-mode script section of `base.html`. This should go in the `{% if is_app_mode %}` block or be guarded by a Capacitor check. Find the end of the existing Capacitor scripts in `base.html` and add before the closing `</body>`:

```html
<!-- Native Share Sheet (app mode only) -->
<script>
(function() {
    if (!window.Capacitor || !window.Capacitor.Plugins || !window.Capacitor.Plugins.Share) return;
    var Share = window.Capacitor.Plugins.Share;

    // Find all elements with data-share-title and data-share-text attributes
    document.querySelectorAll('[data-share-title]').forEach(function(btn) {
        btn.addEventListener('click', async function(e) {
            e.preventDefault();
            var title = btn.getAttribute('data-share-title') || '';
            var text = btn.getAttribute('data-share-text') || '';
            var url = btn.getAttribute('data-share-url') || '';
            try {
                await Share.share({ title: title, text: text, url: url });
            } catch(err) {
                // User cancelled share — ignore
            }
        });
    });
})();
</script>
```

**Step 3: Add share button to `templates/core/followup_detail.html`**

Find the header section (around line 8-37). After the existing header `<div class="flex items-center gap-4 mb-6">` block, inside the `<div class="flex-1">` section, add a share button next to the title. Add this right after the closing `</div>` of the flex-1 div (around line 37) and before the `{% if followup.status != 'completed' %}` check:

```html
        <!-- Native share button (app mode only) -->
        {% if is_app_mode %}
        <button data-share-title="{{ followup.title }}"
                data-share-text="Follow-up: {{ followup.title }}{% if followup.volunteer %} ({{ followup.volunteer.name }}){% endif %} — {{ followup.description|truncatewords:20 }}"
                data-share-url="https://aria.church{% url 'followup_detail' followup.id %}"
                class="text-gray-400 hover:text-ch-gold transition p-2"
                title="Share">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"></path>
            </svg>
        </button>
        {% endif %}
```

**Step 4: Add share button to `templates/core/chat_message.html`**

Find the feedback buttons section for AI responses (around line 10-51, inside the `{% if message.role == 'assistant' %}` block). Add a share button before the thumbs up/down buttons. Inside `<div id="feedback-{{ message.id }}" class="flex items-center gap-1">`, add at the start:

```html
            {% if is_app_mode %}
            <button data-share-title="Aria Response"
                    data-share-text="{{ message.content|truncatewords:50|escapejs }}"
                    class="text-gray-500 hover:text-ch-gold transition p-1"
                    title="Share response">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"></path>
                </svg>
            </button>
            {% endif %}
```

**Step 5: Add share button to `templates/core/volunteer_detail.html`**

Find the volunteer header section. Add a share button in the header row. The exact location depends on the template structure — look for the volunteer name heading and add a share button nearby:

```html
{% if is_app_mode %}
<button data-share-title="{{ volunteer.name }}"
        data-share-text="{{ volunteer.name }}{% if volunteer.email %} — {{ volunteer.email }}{% endif %}{% if volunteer.phone %} — {{ volunteer.phone }}{% endif %}"
        data-share-url="https://aria.church{% url 'volunteer_detail' volunteer.id %}"
        class="text-gray-400 hover:text-ch-gold transition p-2"
        title="Share contact">
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"></path>
    </svg>
</button>
{% endif %}
```

**Step 6: Test manually**

1. `cd /Users/ryanpate/chagent/mobile && npx cap sync ios && npx cap open ios`
2. Build and run on device
3. Navigate to a follow-up detail page — tap the share icon
4. iOS share sheet should appear with the follow-up text
5. Test on a chat message — long-press or tap share icon on Aria's response
6. Test on a volunteer detail page

**Step 7: Commit**

```bash
cd /Users/ryanpate/chagent
git add mobile/package.json mobile/package-lock.json templates/base.html templates/core/followup_detail.html templates/core/chat_message.html templates/core/volunteer_detail.html
git commit -m "feat: add native share sheet for follow-ups, chat, and volunteers"
```

---

### Task 3: Deep Linking / Universal Links

Serve an Apple App Site Association file from Django and configure iOS to handle `aria.church` links.

**Files:**
- Modify: `config/urls.py` (add AASA route)
- Modify: `mobile/ios/App/App/App.entitlements` (add Associated Domains)
- Modify: `mobile/src/app.js` (add appUrlOpen listener)
- Create: `tests/test_aasa.py`

**Step 1: Write the failing test**

Create `tests/test_aasa.py`:

```python
import pytest
import json


@pytest.mark.django_db
class TestAppleAppSiteAssociation:
    def test_aasa_returns_json(self, client):
        """AASA endpoint returns valid JSON with correct content type."""
        from django.test import Client
        c = Client()
        response = c.get('/.well-known/apple-app-site-association')
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json'

    def test_aasa_contains_applinks(self, client):
        """AASA contains applinks with correct app ID."""
        from django.test import Client
        c = Client()
        response = c.get('/.well-known/apple-app-site-association')
        data = json.loads(response.content)
        assert 'applinks' in data
        assert 'details' in data['applinks']
        details = data['applinks']['details']
        assert len(details) >= 1
        assert details[0]['appIDs'][0].endswith('.church.aria.app')

    def test_aasa_specifies_paths(self, client):
        """AASA specifies allowed paths."""
        from django.test import Client
        c = Client()
        response = c.get('/.well-known/apple-app-site-association')
        data = json.loads(response.content)
        details = data['applinks']['details'][0]
        components = details.get('components', [])
        assert len(components) > 0
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/ryanpate/chagent
python -m pytest tests/test_aasa.py -v
```

Expected: FAIL — 404 on `/.well-known/apple-app-site-association`

**Step 3: Add the AASA endpoint to `config/urls.py`**

Add this function after the existing `manifest()` function (around line 74):

```python
def apple_app_site_association(request):
    """Serve Apple App Site Association file for Universal Links."""
    import json
    data = {
        "applinks": {
            "details": [
                {
                    "appIDs": [
                        "XXXXXXXXXX.church.aria.app"  # Replace XXXXXXXXXX with Apple Team ID
                    ],
                    "components": [
                        {"/" : "/chat/*"},
                        {"/" : "/followups/*"},
                        {"/" : "/volunteers/*"},
                        {"/" : "/comms/*"},
                        {"/" : "/documents/*"},
                        {"/" : "/interactions/*"},
                        {"/" : "/analytics/*"},
                        {"/" : "/care/*"},
                    ]
                }
            ]
        }
    }
    return HttpResponse(
        json.dumps(data),
        content_type='application/json'
    )
```

Add the URL route in `urlpatterns` (before `path('admin/', ...)`, around line 83):

```python
    path('.well-known/apple-app-site-association', apple_app_site_association, name='aasa'),
```

**Important:** Replace `XXXXXXXXXX` with your actual Apple Team ID from https://developer.apple.com/account → Membership Details.

**Step 4: Run test to verify it passes**

```bash
cd /Users/ryanpate/chagent
python -m pytest tests/test_aasa.py -v
```

Expected: 3 PASSED

**Step 5: Add Associated Domains to iOS entitlements**

Edit `mobile/ios/App/App/App.entitlements` to add the Associated Domains capability:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>aps-environment</key>
	<string>development</string>
	<key>com.apple.developer.associated-domains</key>
	<array>
		<string>applinks:aria.church</string>
	</array>
</dict>
</plist>
```

**Step 6: Add appUrlOpen listener to `mobile/src/app.js`**

Add this import at the top of `app.js` (with the other imports):

```javascript
import { App } from '@capacitor/app';
```

Install the plugin:

```bash
cd /Users/ryanpate/chagent/mobile
npm install @capacitor/app
npx cap sync ios
```

Add this inside the `showApp()` function in `app.js`, after the push notification setup (around line 128):

```javascript
    // Listen for Universal Link / Deep Link opens
    App.addListener('appUrlOpen', (event) => {
        console.log('[ARIA] Deep link opened:', event.url);
        try {
            const url = new URL(event.url);
            if (url.hostname === 'aria.church' && url.pathname) {
                navigateToUrl(url.pathname);
            }
        } catch (e) {
            console.error('[ARIA] Failed to parse deep link:', e);
        }
    });
```

**Step 7: Commit**

```bash
cd /Users/ryanpate/chagent
git add config/urls.py tests/test_aasa.py mobile/ios/App/App/App.entitlements mobile/src/app.js mobile/package.json mobile/package-lock.json
git commit -m "feat: add deep linking with Universal Links and AASA endpoint"
```

---

### Task 4: Local Notifications for Follow-up Reminders

Install `@capacitor/local-notifications` and schedule on-device reminders from follow-up pages.

**Files:**
- Modify: `mobile/package.json`
- Modify: `templates/base.html` (add local notification scheduling script)
- Modify: `templates/core/followup_detail.html` (add data attributes for scheduling)
- Modify: `templates/core/followup_list.html` (add data attributes for bulk sync)

**Step 1: Install the local notifications plugin**

```bash
cd /Users/ryanpate/chagent/mobile
npm install @capacitor/local-notifications
npx cap sync ios
```

**Step 2: Add local notification scheduling script to `templates/base.html`**

Add this in the app-mode script section of `base.html`, near the other Capacitor scripts:

```html
<!-- Local Follow-up Reminders (app mode only) -->
<script>
(function() {
    if (!window.Capacitor || !window.Capacitor.Plugins) return;
    var LocalNotifications = window.Capacitor.Plugins.LocalNotifications;
    if (!LocalNotifications) return;

    // Request permission
    LocalNotifications.requestPermissions().catch(function() {});

    // Schedule reminders for follow-ups with dates
    document.querySelectorAll('[data-followup-id]').forEach(function(el) {
        var id = parseInt(el.getAttribute('data-followup-id'));
        var title = el.getAttribute('data-followup-title') || 'Follow-up Reminder';
        var dateStr = el.getAttribute('data-followup-date');
        var status = el.getAttribute('data-followup-status') || 'pending';

        if (!dateStr || !id) return;
        if (status === 'completed' || status === 'cancelled') {
            // Cancel any existing notification for completed/cancelled follow-ups
            LocalNotifications.cancel({ notifications: [{ id: id }] }).catch(function() {});
            return;
        }

        var scheduleDate = new Date(dateStr + 'T09:00:00');
        if (scheduleDate <= new Date()) return; // Don't schedule past dates

        LocalNotifications.schedule({
            notifications: [{
                id: id,
                title: 'Follow-up Reminder',
                body: title,
                schedule: { at: scheduleDate },
                extra: { url: '/followups/' + id + '/' },
            }]
        }).then(function() {
            console.log('[ARIA] Scheduled local reminder for follow-up #' + id);
        }).catch(function(e) {
            console.log('[ARIA] Failed to schedule reminder:', e);
        });
    });

    // Handle local notification taps — navigate to the follow-up
    LocalNotifications.addListener('localNotificationActionPerformed', function(action) {
        var url = action.notification.extra && action.notification.extra.url;
        if (url && url.startsWith('/')) {
            window.location.href = 'https://aria.church' + url + '?app=1';
        }
    });
})();
</script>
```

**Step 3: Add data attributes to `templates/core/followup_detail.html`**

Find the outermost `<div>` in the content block (line 6: `<div class="max-w-3xl mx-auto">`). Add data attributes to it:

Change:
```html
<div class="max-w-3xl mx-auto">
```

To:
```html
<div class="max-w-3xl mx-auto"
     data-followup-id="{{ followup.id }}"
     data-followup-title="{{ followup.title }}"
     data-followup-date="{{ followup.follow_up_date|date:'Y-m-d' }}"
     data-followup-status="{{ followup.status }}">
```

**Step 4: Add data attributes to `templates/core/followup_list.html`**

Find the follow-up list items in the template (each follow-up card in the list). Each follow-up card should get data attributes. Look for the loop that renders follow-ups and add data attributes to each card's container element. The exact location depends on the template — find where each follow-up is rendered (likely a `{% for followup in followups %}` loop) and add:

```html
data-followup-id="{{ followup.id }}"
data-followup-title="{{ followup.title }}"
data-followup-date="{{ followup.follow_up_date|date:'Y-m-d' }}"
data-followup-status="{{ followup.status }}"
```

to each follow-up card's outermost div.

**Step 5: Test manually**

1. `cd /Users/ryanpate/chagent/mobile && npx cap sync ios && npx cap open ios`
2. Build and run on device
3. Navigate to a follow-up detail page that has a future `follow_up_date`
4. Check Xcode console for "[ARIA] Scheduled local reminder for follow-up #..."
5. Set a follow-up date to 1 minute from now to test the notification fires
6. Tap the notification — should deep-link to the follow-up detail page

**Step 6: Commit**

```bash
cd /Users/ryanpate/chagent
git add mobile/package.json mobile/package-lock.json templates/base.html templates/core/followup_detail.html templates/core/followup_list.html
git commit -m "feat: add local notifications for follow-up reminders"
```

---

### Task 5: App Shortcut Quick Actions

Add static quick actions to the app icon (3D Touch / Haptic Touch) and handle them in AppDelegate.

**Files:**
- Modify: `mobile/ios/App/App/Info.plist` (add UIApplicationShortcutItems)
- Modify: `mobile/ios/App/App/AppDelegate.swift` (handle shortcut actions)

**Step 1: Add shortcut items to `mobile/ios/App/App/Info.plist`**

Add the `UIApplicationShortcutItems` array before the closing `</dict>` tag in Info.plist (before line 52):

```xml
	<key>UIApplicationShortcutItems</key>
	<array>
		<dict>
			<key>UIApplicationShortcutItemType</key>
			<string>church.aria.app.chat</string>
			<key>UIApplicationShortcutItemTitle</key>
			<string>Chat with Aria</string>
			<key>UIApplicationShortcutItemIconType</key>
			<string>UIApplicationShortcutIconTypeCompose</string>
		</dict>
		<dict>
			<key>UIApplicationShortcutItemType</key>
			<string>church.aria.app.followups</string>
			<key>UIApplicationShortcutItemTitle</key>
			<string>My Follow-ups</string>
			<key>UIApplicationShortcutItemIconType</key>
			<string>UIApplicationShortcutIconTypeTask</string>
		</dict>
		<dict>
			<key>UIApplicationShortcutItemType</key>
			<string>church.aria.app.interaction</string>
			<key>UIApplicationShortcutItemTitle</key>
			<string>Log Interaction</string>
			<key>UIApplicationShortcutItemIconType</key>
			<string>UIApplicationShortcutIconTypeAdd</string>
		</dict>
	</array>
```

**Step 2: Handle shortcut actions in `mobile/ios/App/App/AppDelegate.swift`**

Add a `pendingShortcutURL` property next to the existing `pendingNotificationURL` (around line 13):

```swift
    /// URL from quick action that launched the app
    var pendingShortcutURL: String?
```

Add the shortcut handler method inside the `AppDelegate` class (before the `MessagingDelegate` extension, around line 126):

```swift
    // MARK: - Quick Action Shortcuts
    func application(_ application: UIApplication, performActionFor shortcutItem: UIApplicationShortcutItem, completionHandler: @escaping (Bool) -> Void) {
        let url = urlForShortcut(shortcutItem.type)
        print("[ARIA] Quick action: \(shortcutItem.type) -> \(url)")

        guard let rootVC = self.window?.rootViewController else {
            completionHandler(false)
            return
        }

        if let webView = self.findWebView(in: rootVC.view) {
            webView.evaluateJavaScript("window.location.href = 'https://aria.church\(url)?app=1';", completionHandler: nil)
            completionHandler(true)
        } else {
            // App not fully loaded yet — store for later
            pendingShortcutURL = url
            completionHandler(true)
        }
    }

    private func urlForShortcut(_ type: String) -> String {
        switch type {
        case "church.aria.app.chat": return "/chat/"
        case "church.aria.app.followups": return "/followups/"
        case "church.aria.app.interaction": return "/interactions/create/"
        default: return "/chat/"
        }
    }
```

Also update `applicationDidBecomeActive` to handle `pendingShortcutURL` — add this after the existing `pendingNotificationURL` handling (around line 76):

```swift
        // Handle pending quick action shortcut (cold start)
        if let url = pendingShortcutURL {
            print("[ARIA] Injecting pending shortcut URL: \(url)")
            pendingShortcutURL = nil
            DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                guard let rootVC = self.window?.rootViewController else { return }
                if let webView = self.findWebView(in: rootVC.view) {
                    webView.evaluateJavaScript("window.location.href = 'https://aria.church\(url)?app=1';", completionHandler: nil)
                }
            }
        }
```

**Step 3: Test manually**

1. Build and run on device
2. Go to home screen
3. Long-press the ARIA app icon
4. Three quick actions should appear: "Chat with Aria", "My Follow-ups", "Log Interaction"
5. Tap "My Follow-ups" — app should open to `/followups/`
6. Go home, long-press, tap "Chat with Aria" — should open to `/chat/`
7. Force-quit the app, then long-press and tap "Log Interaction" — should handle cold start

**Step 4: Commit**

```bash
cd /Users/ryanpate/chagent
git add mobile/ios/App/App/Info.plist mobile/ios/App/App/AppDelegate.swift
git commit -m "feat: add app shortcut quick actions for chat, follow-ups, and interactions"
```

---

### Task 6: Backend Tests and Final Sync

Write Django tests for the AASA endpoint (already covered in Task 3), run the full test suite, and do a final `cap sync`.

**Files:**
- Test: `tests/test_aasa.py` (already created in Task 3)

**Step 1: Run the full test suite**

```bash
cd /Users/ryanpate/chagent
python -m pytest tests/ -v --tb=short
```

Expected: All existing tests pass + 3 new AASA tests pass

**Step 2: Final Capacitor sync**

```bash
cd /Users/ryanpate/chagent/mobile
npx cap sync ios
```

**Step 3: Build and test on device**

```bash
npx cap open ios
```

Test all 5 features end-to-end on a physical iOS device:
1. Turn off Wi-Fi — see offline page — turn back on — auto-reload
2. Go to follow-up detail — tap share icon — share sheet appears
3. Long-press app icon — 3 quick actions appear
4. Open a universal link (`aria.church/followups/...`) from Notes app — opens in ARIA
5. View follow-up with future date — check console for scheduled reminder

**Step 4: Final commit with all synced files**

```bash
cd /Users/ryanpate/chagent
git add -A mobile/ios/ mobile/android/
git commit -m "chore: sync Capacitor platforms with phase 3 plugins"
```

---

### Task 7: Deploy Backend Changes

Push to Railway so the AASA endpoint is live.

**Step 1: Push to origin**

```bash
cd /Users/ryanpate/chagent
git push
```

**Step 2: Verify AASA is accessible**

After Railway deploys, verify:

```bash
curl -s https://aria.church/.well-known/apple-app-site-association | python -m json.tool
```

Expected: JSON with `applinks` and `details` containing your app ID.

**Step 3: Verify with Apple's AASA validator**

Visit https://search.developer.apple.com/appsearch-validation-tool/ and enter `aria.church` to validate the AASA file.
