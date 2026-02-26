# Native iOS Phase 1: Biometric Auth + Haptic Feedback

**Date:** 2026-02-26
**Goal:** Add native iOS features to strengthen App Store approval chances by demonstrating real native API usage.

## Biometric Authentication (Face ID / Touch ID)

### Flow

1. User logs in with email/password the first time (existing flow).
2. After successful login, store credentials in iOS Keychain via `capacitor-native-biometric`.
3. On next app launch, if tokens exist AND biometrics enrolled: prompt Face ID.
4. If Face ID succeeds, use stored credentials to obtain fresh JWT tokens.
5. If Face ID fails or user cancels, show email/password login screen.

### Plugin

`capacitor-native-biometric` — wraps iOS LocalAuthentication framework. Supports Face ID and Touch ID. Stores credentials in iOS Keychain (more secure than Preferences).

### Key Behavior

- Biometric enrollment is automatic after first successful login (no settings toggle).
- Stored credentials (email + password) in Keychain are used to call `/api/auth/token/` for fresh JWTs on biometric success.
- If refresh token expired (30 days), biometric still works because it replays stored credentials.
- If biometric fails or is cancelled, user sees the standard login form.

## Haptic Feedback

### Plugin

`@capacitor/haptics` (already installed in package.json).

### Touch Points

| Action | Haptic Type |
|--------|-------------|
| Tab bar tap | Light impact |
| Login success | Success notification |
| More menu open | Light impact |
| More menu item tap | Light impact |

## Files Changed

| File | Change |
|------|--------|
| `mobile/package.json` | Add `capacitor-native-biometric` dependency |
| `mobile/src/auth.js` | Add biometric check, store, and clear functions |
| `mobile/src/app.js` | Integrate biometric flow at launch, add haptics to tab bar, login, and More menu |

No backend changes required.
