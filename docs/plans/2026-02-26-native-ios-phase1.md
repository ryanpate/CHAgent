# Native iOS Phase 1: Biometric Auth + Haptic Feedback — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Face ID biometric authentication and haptic feedback to the ARIA Capacitor iOS app to demonstrate native API usage for App Store approval.

**Architecture:** The `@capgo/capacitor-native-biometric` plugin stores credentials in the iOS Keychain and gates access with Face ID/Touch ID. On app launch, if biometrics are available and credentials stored, the user is prompted for Face ID instead of seeing the login form. `@capacitor/haptics` (already installed) adds tactile feedback on tab switches, login, and menu interactions.

**Tech Stack:** Capacitor 8, @capgo/capacitor-native-biometric (v8.3.6+), @capacitor/haptics

---

### Task 1: Install biometric plugin

**Files:**
- Modify: `mobile/package.json`

**Step 1: Install the plugin**

Run from `mobile/` directory:
```bash
npm install @capgo/capacitor-native-biometric
```

**Step 2: Sync native project**

```bash
npx cap sync ios
```

**Step 3: Verify installation**

Check `package.json` includes `@capgo/capacitor-native-biometric` in dependencies.

**Step 4: Commit**

```bash
git add mobile/package.json mobile/package-lock.json
git commit -m "feat: install capacitor-native-biometric plugin"
```

---

### Task 2: Add biometric functions to auth.js

**Files:**
- Modify: `mobile/src/auth.js`

**Step 1: Add biometric imports and constants**

Add at top of `auth.js`, after the existing Preferences import:

```javascript
import { NativeBiometric } from '@capgo/capacitor-native-biometric';
import { Capacitor } from '@capacitor/core';

const BIOMETRIC_SERVER = 'aria.church';
```

**Step 2: Add biometric availability check**

```javascript
export async function isBiometricAvailable() {
    if (!Capacitor.isNativePlatform()) return false;
    try {
        const result = await NativeBiometric.isAvailable();
        return result.isAvailable;
    } catch {
        return false;
    }
}
```

**Step 3: Add credential store function**

Called after successful email/password login:

```javascript
export async function storeBiometricCredentials(email, password) {
    try {
        const available = await isBiometricAvailable();
        if (!available) return;
        await NativeBiometric.setCredentials({
            username: email,
            password: password,
            server: BIOMETRIC_SERVER,
        });
    } catch {
        // Biometric storage failed — non-fatal, user can still log in normally
    }
}
```

**Step 4: Add biometric login function**

Prompts Face ID, retrieves stored credentials, obtains fresh JWT:

```javascript
export async function loginWithBiometric() {
    // Verify identity with Face ID / Touch ID
    await NativeBiometric.verifyIdentity({
        reason: 'Sign in to ARIA',
        title: 'Sign In',
    });

    // Get stored credentials from Keychain
    const credentials = await NativeBiometric.getCredentials({
        server: BIOMETRIC_SERVER,
    });

    // Use credentials to get fresh JWT tokens
    return await login(credentials.username, credentials.password);
}
```

**Step 5: Add check for stored credentials**

```javascript
export async function hasBiometricCredentials() {
    try {
        const credentials = await NativeBiometric.getCredentials({
            server: BIOMETRIC_SERVER,
        });
        return !!(credentials && credentials.username);
    } catch {
        return false;
    }
}
```

**Step 6: Add credential cleanup to clearTokens**

Update the existing `clearTokens()` function to also remove biometric credentials:

```javascript
export async function clearTokens() {
    await Preferences.remove({ key: 'auth_token' });
    await Preferences.remove({ key: 'refresh_token' });
    try {
        await NativeBiometric.deleteCredentials({ server: BIOMETRIC_SERVER });
    } catch {
        // Credentials may not exist yet — ignore
    }
}
```

**Step 7: Commit**

```bash
git add mobile/src/auth.js
git commit -m "feat: add biometric auth functions (Face ID / Touch ID)"
```

---

### Task 3: Integrate biometric flow into app.js

**Files:**
- Modify: `mobile/src/app.js`

**Step 1: Add imports**

Add to the top of `app.js`, after existing imports:

```javascript
import { Haptics, ImpactStyle, NotificationType } from '@capacitor/haptics';
import { Capacitor } from '@capacitor/core';
import {
    isBiometricAvailable,
    hasBiometricCredentials,
    loginWithBiometric,
    storeBiometricCredentials,
} from './auth.js';
```

Note: `Capacitor` is already imported — just add to the existing import. `login`, `isAuthenticated`, `clearTokens` are already imported.

**Step 2: Update init() with biometric flow**

Replace the `init()` function:

```javascript
async function init() {
    // Set dark status bar
    if (Capacitor.isNativePlatform()) {
        try {
            await StatusBar.setStyle({ style: 'DARK' });
            await StatusBar.setBackgroundColor({ color: '#0f0f0f' });
        } catch (e) { /* Status bar plugin not available on all platforms */ }
    }

    const authenticated = await isAuthenticated();

    if (authenticated) {
        await showApp();
    } else {
        // Try biometric login before showing login form
        const biometricReady = await isBiometricAvailable() && await hasBiometricCredentials();
        if (biometricReady) {
            try {
                await loginWithBiometric();
                await hapticSuccess();
                await showApp();
            } catch {
                // Biometric failed or cancelled — show login form
                showLogin();
            }
        } else {
            showLogin();
        }
    }

    await SplashScreen.hide();
}
```

**Step 3: Store credentials after successful email/password login**

In the `showLogin()` function, after `await login(email, password)` succeeds, add credential storage. Update the try block inside the form submit handler:

```javascript
        try {
            await login(email, password);
            await storeBiometricCredentials(email, password);
            await hapticSuccess();
            await showApp();
        } catch (err) {
```

**Step 4: Add haptic helper functions**

Add before the `init()` function:

```javascript
async function hapticImpact() {
    if (Capacitor.isNativePlatform()) {
        try { await Haptics.impact({ style: ImpactStyle.Light }); } catch {}
    }
}

async function hapticSuccess() {
    if (Capacitor.isNativePlatform()) {
        try { await Haptics.notification({ type: NotificationType.Success }); } catch {}
    }
}
```

**Step 5: Add haptics to tab bar taps**

In the `showApp()` function, inside the tab click handler, add haptic before existing logic:

```javascript
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', async () => {
            await hapticImpact();
            const url = tab.dataset.url;
            // ... rest of existing handler
```

**Step 6: Add haptics to More menu**

In `showMoreMenu()`, add haptic at the start of the function:

```javascript
function showMoreMenu() {
    hapticImpact();
    // ... rest of existing function
```

And inside each menu item click handler, add haptic:

```javascript
        if (item.action === 'logout') {
            btn.style.color = '#ef4444';
            btn.addEventListener('click', async () => {
                await hapticImpact();
                await clearTokens();
                // ... rest
            });
        } else {
            btn.addEventListener('click', async () => {
                await hapticImpact();
                overlay.remove();
                navigateToUrl(item.url);
            });
        }
```

**Step 7: Commit**

```bash
git add mobile/src/app.js
git commit -m "feat: integrate Face ID login and haptic feedback"
```

---

### Task 4: Add NSFaceIDUsageDescription to iOS project

**Files:**
- Modify: `mobile/ios/App/App/Info.plist`

**Step 1: Add Face ID usage description**

Apple requires a usage description string for Face ID. Add to Info.plist:

```xml
<key>NSFaceIDUsageDescription</key>
<string>ARIA uses Face ID for quick and secure sign-in.</string>
```

**Step 2: Commit**

```bash
git add mobile/ios/App/App/Info.plist
git commit -m "feat: add Face ID usage description to Info.plist"
```

---

### Task 5: Rebuild and test

**Step 1: Sync Capacitor**

```bash
cd mobile && npx cap sync ios
```

**Step 2: Build in Xcode**

Open `mobile/ios/App/App.xcodeproj`, build and run on simulator (Cmd+R).

**Step 3: Test login flow**

1. Launch app — should show email/password login (no biometric credentials stored yet)
2. Log in with email/password — should feel a success haptic
3. Kill and relaunch the app — should prompt Face ID
4. Authenticate with Face ID — should skip login form, go straight to app
5. Tap tabs — should feel light haptic on each tap
6. Tap More — should feel haptic, menu items too

**Step 4: Test failure cases**

1. Cancel Face ID prompt — should fall back to login form
2. Sign out from More menu — should clear stored credentials
3. Next launch after sign out — should show login form (no biometric prompt)

**Step 5: Final commit and push**

```bash
git push
```
