# Native iOS Phase 2: App Badge Count + Pull-to-Refresh

**Date:** 2026-02-26
**Goal:** Add app icon badge count for unread notifications and pull-to-refresh gesture to further demonstrate native API usage for App Store approval.

## App Badge Count (Unread Notifications)

### How It Works

1. When Django sends a native push notification via FCM, the payload includes the user's current unread count in the `apns.payload.aps.badge` field.
2. iOS automatically updates the app icon badge number.
3. When the user opens the app, a script in `base.html` clears the badge to 0 via `Capacitor.Plugins.PushNotifications.removeAllDeliveredNotifications()` and calls a lightweight API endpoint to reset the server-side counter.

### Backend Changes

- Add `unread_badge_count` integer field to `NativePushToken` model (per-device counter).
- In `send_native_push()`, increment `unread_badge_count` and include it in the FCM payload's `apns.payload.aps.badge` field.
- Add `POST /api/push/badge-clear/` endpoint — resets `unread_badge_count` to 0 for the authenticated user's tokens.

### Frontend Changes (templates/base.html)

- On page load in native app: call `PushNotifications.removeAllDeliveredNotifications()` to clear the notification center.
- Fire a `fetch()` to `/api/push/badge-clear/` to reset the server-side counter.

### Key Behavior

- Badge count increments with each push notification sent.
- Badge clears when the user opens any page in the app.
- Each device token tracks its own count (user may have multiple devices).
- No new models — just a field on `NativePushToken`.

## Pull-to-Refresh

### How It Works

Pure client-side touch gesture handler in `base.html`. When the user pulls down from the top of the page past a threshold, shows a spinner and reloads the page.

### Implementation

- Detect `touchstart`, `touchmove`, `touchend` events on `document`.
- Only activate when at scroll position 0 (top of page) and `Capacitor.Plugins` is detected.
- Show the existing `.ptr-indicator` spinner element when pull distance exceeds 60px.
- On release past threshold: trigger `window.location.reload()`.
- On release before threshold: animate indicator back and cancel.

### Key Behavior

- Only active in the native app (guarded by `Capacitor.Plugins` check).
- Only triggers when scrolled to the top of the page.
- Visual feedback: a spinner/arrow indicator appears during the pull gesture.
- No Capacitor plugin needed — pure JS touch events.

## Files Changed

| File | Change |
|------|--------|
| `core/models.py` | Add `unread_badge_count` field to `NativePushToken` |
| `core/notifications.py` | Include badge count in FCM `apns` payload |
| `core/api_views.py` | Add `badge_clear` endpoint |
| `core/api_urls.py` | Route for `/api/push/badge-clear/` |
| `templates/base.html` | Badge clear on load + pull-to-refresh gesture handler |
| Migration | `NativePushToken.unread_badge_count` field |
