# ARIA Mobile App - Capacitor Design

**Date:** 2026-02-23
**Status:** Approved
**Approach:** Ionic Capacitor (hybrid native shell + WebView)

## Goals

1. **App Store presence** - List ARIA on Apple App Store and Google Play Store
2. **Reliable push notifications** - Native APNs (iOS) and FCM (Android), solving iOS PWA push limitations
3. **Meet user expectations** - Downloadable "real app" experience instead of confusing PWA install flow

## Non-Goals

- Deep native device features (HealthKit, Siri, etc.)
- Rebuilding the UI in native components
- Offline-first functionality (app loads from live server)

## Architecture

```
+-------------------------------------+
|         Native App Shell            |
|  +-------------------------------+  |
|  |   Native Tab Bar (Capacitor)  |  |
|  |  Chat | Volunteers | Follow-  |  |
|  |        ups | Comms | More     |  |
|  +-------------------------------+  |
|  +-------------------------------+  |
|  |     WKWebView / WebView       |  |
|  |                                |  |
|  |   Existing Django app          |  |
|  |   (HTMX + Tailwind + Alpine)  |  |
|  |   loaded from aria.church      |  |
|  +-------------------------------+  |
|  +-------------------------------+  |
|  |    Native Plugins              |  |
|  |  Push (APNs/FCM), Splash,     |  |
|  |  Status Bar, Haptics, Keyboard |  |
|  +-------------------------------+  |
+-------------------------------------+
         |
         | HTTPS
         v
+-------------------------------------+
|     Django Backend (aria.church)    |
|                                      |
|  Existing: All views, HTMX, AI      |
|  New: /api/auth/token/ (JWT)         |
|  New: /api/push/register/ (tokens)   |
|  Modified: base.html (app mode)      |
+-------------------------------------+
```

The app loads pages from the live server (`aria.church`). This means UI updates deploy instantly without app store review cycles. The native shell provides tab bar navigation, push notifications, and platform integration.

## Django Backend Changes

### New API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/token/` | POST | Login with email/password, returns JWT + sets session cookie |
| `/api/auth/token/refresh/` | POST | Refresh an expiring JWT token |
| `/api/push/register/` | POST | Register native APNs/FCM push token |

Implementation: `djangorestframework-simplejwt` (~50 lines of code, 3 files).

### New Model

```python
class NativePushToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='native_push_tokens')
    token = models.TextField()
    platform = models.CharField(max_length=10, choices=[('ios', 'iOS'), ('android', 'Android')])
    device_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'token']
```

### Template Conditional (base.html)

When running inside Capacitor (detected via `?app=1` cookie or query param):
- Hide web sidebar
- Hide mobile header/hamburger menu
- Add padding for native status bar (top) and tab bar (bottom)
- Hide PWA install prompts
- Route external links to system browser

Web users see zero changes.

### Push Notification Extension

Extend `send_notification_to_user()` in `core/notifications.py`:
- Check for `NativePushToken` records alongside `PushSubscription`
- Send via `firebase-admin` (FCM/Android) and `apns2` (APNs/iOS) Python libraries
- Native tokens take priority over web push tokens
- All existing notification types (announcements, DMs, care alerts, follow-ups, tasks) work through the same dispatch

## Capacitor App Structure

```
mobile/
+-- package.json              # Capacitor + plugin dependencies
+-- capacitor.config.ts       # Server URL, plugins, app ID
+-- src/
|   +-- index.html            # Entry point (login screen shell)
|   +-- app.js                # Tab bar setup, WebView routing, navigation
|   +-- auth.js               # Login flow, token storage, session management
|   +-- push.js               # Native push permission + token registration
|   +-- styles.css            # Login screen + native UI styles
+-- ios/                      # Generated Xcode project
|   +-- App/
+-- android/                  # Generated Android Studio project
|   +-- app/
+-- resources/
    +-- icon.png              # 1024x1024 app icon
    +-- splash.png            # Splash screen (dark theme)
    +-- adaptive-icon.png     # Android adaptive icon
```

### Tab Bar Navigation

| Tab | Icon | Loads URL |
|-----|------|-----------|
| Chat | Message bubble | `/chat/` |
| Volunteers | People | `/volunteers/` |
| Follow-ups | Checklist | `/followups/` |
| Comms | Megaphone | `/comms/` |
| More | Ellipsis | Native menu (Analytics, Care, Documents, Settings) |

### Capacitor Plugins

| Plugin | Purpose |
|--------|---------|
| `@capacitor/push-notifications` | APNs + FCM registration and handling |
| `@capacitor/splash-screen` | Branded splash on launch |
| `@capacitor/status-bar` | Dark theme status bar |
| `@capacitor/haptics` | Tactile feedback on key actions |
| `@capacitor/keyboard` | WebView keyboard behavior |
| `@capacitor/browser` | Open external links in system browser |
| `@capacitor/preferences` | Secure token storage |

### Login Flow

1. App opens -> branded splash screen (ARIA logo on dark background)
2. Check for stored auth token in Capacitor Preferences
3. If token exists and valid -> set session cookie in WebView -> load dashboard
4. If no token -> show native login screen
5. User enters credentials -> POST `/api/auth/token/`
6. Store JWT in Preferences, set session cookie in WebView
7. If 2FA enabled -> WebView loads `/login/2fa/` (handled by existing web flow)
8. Load dashboard with tab bar navigation

### Link Handling

External links that open in system browser (not WebView):
- Stripe billing portal
- Planning Center OAuth
- External documentation
- mailto: and tel: links

Small JS snippet intercepts `<a>` clicks and routes external domains to `@capacitor/browser`.

## App Branding

| Element | Value |
|---------|-------|
| App Name | ARIA |
| Subtitle | AI Worship Team Management |
| Bundle ID | `church.aria.app` |
| Theme | Dark (#0f0f0f) + gold (#c9a227) |
| Status Bar | Light text on dark background |
| Splash Screen | ARIA logo centered on #0f0f0f |

## App Store Publishing

### Apple App Store
- Apple Developer account ($99/year)
- Xcode project generated by Capacitor
- WebView apps accepted when providing value beyond simple wrapper (native tab bar, push, login qualify)
- Submit via Xcode/Transporter

### Google Play Store
- Google Play Developer account ($25 one-time)
- Signed AAB built via Android Studio or CLI
- Submit via Google Play Console

### Required Assets
- App icon (1024x1024 PNG, no transparency)
- Screenshots (6.7" iPhone, 5.5" iPhone, various Android sizes)
- App description, keywords, subtitle
- Privacy policy URL (aria.church/privacy/)
- Support URL

## Push Notification Architecture

### iOS (APNs)
- Capacitor push plugin requests permission on first launch
- Receives APNs device token
- POSTs token to `/api/push/register/` with `platform=ios`
- Django sends via `apns2` Python library

### Android (FCM)
- Same flow with Firebase Cloud Messaging token
- Django sends via `firebase-admin` Python library

### Rich Notification Features (unlocked by native)
- Grouped notifications by type
- Action buttons (Mark Complete, Reply)
- Badge count on app icon
- Silent/background push for data sync
- Reliable delivery (no iOS PWA limitations)

## What Does NOT Change

- All 130+ view functions
- All 104+ templates (content area)
- All HTMX interactions
- All AI/Aria chat functionality
- All Planning Center integration
- All analytics, comms, projects, tasks
- Database schema (only 1 new model added)
- Web app experience for browser users

## Testing Strategy

| Layer | Tests |
|-------|-------|
| Django API | Token auth endpoints, push token registration, app detection |
| WebView rendering | All pages render correctly without sidebar in app mode |
| Push notifications | Delivery on both iOS and Android platforms |
| Navigation | Tab bar loads correct pages, back button behavior |
| Auth flow | Login, 2FA, session persistence, token refresh |
| Deep linking | Push notification tap opens correct page |
| External links | Stripe, PCO, mailto/tel open in system browser |

## Estimated Effort

| Phase | Duration |
|-------|----------|
| Django API endpoints + NativePushToken model | 1-2 days |
| Template conditionals (app mode) | 1 day |
| Capacitor project setup + config | 1 day |
| Tab bar + WebView navigation | 2-3 days |
| Native login screen | 1-2 days |
| Push notification integration | 2-3 days |
| Testing on devices | 2-3 days |
| App Store assets + submission | 2-3 days |
| **Total** | **~2-3 weeks** |
