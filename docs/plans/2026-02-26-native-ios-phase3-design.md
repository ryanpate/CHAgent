# Native iOS Phase 3: App Store Approval Enhancement

**Date:** 2026-02-26
**Goal:** Add 5 native iOS features that both improve UX and strengthen the App Store approval case by demonstrating meaningful native API usage beyond a WebView wrapper.

**Context:** ARIA already uses 7 native iOS APIs (push notifications, biometric auth, haptics, badge management, pull-to-refresh, splash screen, status bar). This phase adds 5 more, bringing the total to 12 distinct iOS API integrations.

**Timeline:** ~1 week

---

## Feature 1: Offline Fallback Page

When the device loses connectivity, show a branded offline page instead of a blank WebView error.

### How It Works

- `@capacitor/network` plugin monitors connectivity state via iOS `NWPathMonitor`
- When a WebView navigation fails due to no network, intercept the error and display a locally-bundled `offline.html`
- The offline page shows the ARIA logo, "You're offline" message, and a "Try Again" button
- Stores the last-attempted URL so the retry button loads the correct page
- When connectivity returns, automatically retries loading

### iOS API

`NWPathMonitor` (Network framework) via `@capacitor/network`

### Files

| File | Change |
|------|--------|
| `mobile/package.json` | Add `@capacitor/network` |
| `mobile/src/offline.html` | Branded offline page (bundled locally) |
| `mobile/src/app.js` | Network listener, WebView error interception, auto-retry |

---

## Feature 2: Native Share Sheet

Let users share content from ARIA using the iOS share sheet (`UIActivityViewController`).

### Shareable Content

| Content | Format |
|---------|--------|
| Follow-up items | Text summary ("Prayer request for Sarah: ...") |
| Chat responses | Aria's response text |
| Volunteer contact info | Name, email, phone |

### How It Works

- Share button (icon) added to follow-up detail, chat messages, and volunteer detail pages
- Only visible in native app mode (guarded by Capacitor check)
- Tapping calls `Share.share({ title, text, url })` from `@capacitor/share`
- iOS presents native share sheet (Messages, Mail, Notes, Copy, etc.)

### iOS API

`UIActivityViewController` via `@capacitor/share`

### Files

| File | Change |
|------|--------|
| `mobile/package.json` | Add `@capacitor/share` |
| `templates/base.html` | Share button injection script (app mode only) |
| `templates/core/followup_detail.html` | Share button markup |
| `templates/core/chat_message.html` | Share button on AI responses |
| `templates/core/volunteer_detail.html` | Share button for contact info |

---

## Feature 3: Deep Linking / Universal Links

When a user taps an `aria.church` link anywhere on iOS, it opens directly in the ARIA app.

### Supported Paths

- `/chat/` — Aria chat
- `/followups/*` — Follow-up detail
- `/volunteers/*` — Volunteer detail
- `/comms/*` — Communication hub
- `/documents/*` — Knowledge base document

### How It Works

- Serve an Apple App Site Association (AASA) file at `https://aria.church/.well-known/apple-app-site-association`
- AASA references Apple Team ID and bundle ID (`church.aria.app`)
- Add Associated Domains entitlement (`applinks:aria.church`) to iOS project
- Capacitor's `appUrlOpen` listener receives the URL and navigates the WebView

### Backend Changes

- Django view serving AASA JSON at `/.well-known/apple-app-site-association`
- Content-Type: `application/json`

### iOS API

Associated Domains / Universal Links (via `NSUserActivity`)

### Files

| File | Change |
|------|--------|
| `core/views.py` | AASA endpoint |
| `config/urls.py` | Route for `/.well-known/apple-app-site-association` |
| `mobile/src/app.js` | `App.addListener('appUrlOpen', ...)` handler |
| `mobile/ios/App/App.entitlements` | Add Associated Domains |

---

## Feature 4: Local Notifications for Follow-up Reminders

Schedule on-device reminders for follow-ups that fire even without server connectivity.

### How It Works

- When a user views a follow-up with a `follow_up_date`, the app schedules a local notification
- Uses `@capacitor/local-notifications` plugin
- Notifications fire at the scheduled time with the follow-up title
- Tap action deep-links to the follow-up detail page
- Follow-up completion or date change cancels/reschedules the notification
- Each notification uses the follow-up ID as its unique identifier
- On follow-up list page, syncs all pending follow-up reminders

### iOS API

`UNUserNotificationCenter.add(UNNotificationRequest)` via `@capacitor/local-notifications`

### Files

| File | Change |
|------|--------|
| `mobile/package.json` | Add `@capacitor/local-notifications` |
| `templates/base.html` | Local notification scheduling script (app mode) |
| `templates/core/followup_detail.html` | Data attributes for follow-up date/title/id |
| `templates/core/followup_list.html` | Bulk sync of pending reminders |

---

## Feature 5: App Shortcut Actions (Quick Actions)

Long-press on the ARIA app icon shows quick actions for common tasks.

### Quick Actions

| Action | Icon (SF Symbol) | Opens |
|--------|-------------------|-------|
| Chat with Aria | `bubble.left.and.bubble.right` | `/chat/` |
| My Follow-ups | `checklist` | `/followups/` |
| Log Interaction | `square.and.pencil` | `/interactions/create/` |

### How It Works

- Static shortcut items defined in `Info.plist` under `UIApplicationShortcutItems`
- Each item has an SF Symbol icon, title, and type identifier
- `AppDelegate.application(_:performActionFor:completionHandler:)` handles the tap
- Stores the target URL and navigates the WebView after it loads (same pattern as cold-start notification handling)

### iOS APIs

`UIApplicationShortcutItem`, SF Symbols. No Capacitor plugin needed — pure native Swift.

### Files

| File | Change |
|------|--------|
| `mobile/ios/App/App/Info.plist` | Add `UIApplicationShortcutItems` array |
| `mobile/ios/App/App/AppDelegate.swift` | Handle shortcut action, navigate WebView |

---

## Native API Summary (After Phase 3)

| # | Feature | iOS API | Phase |
|---|---------|---------|-------|
| 1 | Push notifications | APNs / FCM | 1 |
| 2 | Biometric auth | LocalAuthentication (Face ID/Touch ID) | 1 |
| 3 | Haptic feedback | UIFeedbackGenerator | 1 |
| 4 | Badge count | applicationIconBadgeNumber | 2 |
| 5 | Pull-to-refresh | Touch events (custom) | 2 |
| 6 | Splash screen | LaunchScreen storyboard | Initial |
| 7 | Status bar | UIStatusBarStyle | Initial |
| 8 | Offline detection | NWPathMonitor (Network framework) | 3 |
| 9 | Share sheet | UIActivityViewController | 3 |
| 10 | Universal links | Associated Domains / NSUserActivity | 3 |
| 11 | Local notifications | UNUserNotificationCenter (scheduled) | 3 |
| 12 | Quick actions | UIApplicationShortcutItem | 3 |

This gives Apple reviewers 12 distinct native iOS API integrations demonstrating that the app provides genuine native functionality beyond what Safari offers.
