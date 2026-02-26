import { Preferences } from '@capacitor/preferences';
import { NativeBiometric } from '@capgo/capacitor-native-biometric';
import { Capacitor } from '@capacitor/core';

const API_BASE = 'https://aria.church';
const BIOMETRIC_SERVER = 'aria.church';

export async function getStoredToken() {
    const { value } = await Preferences.get({ key: 'auth_token' });
    return value;
}

export async function getRefreshToken() {
    const { value } = await Preferences.get({ key: 'refresh_token' });
    return value;
}

export async function storeTokens(access, refresh) {
    await Preferences.set({ key: 'auth_token', value: access });
    await Preferences.set({ key: 'refresh_token', value: refresh });
}

export async function clearTokens() {
    await Preferences.remove({ key: 'auth_token' });
    await Preferences.remove({ key: 'refresh_token' });
    try {
        await NativeBiometric.deleteCredentials({ server: BIOMETRIC_SERVER });
    } catch {
        // Credentials may not exist yet — ignore
    }
}

export async function login(email, password) {
    const response = await fetch(`${API_BASE}/api/auth/token/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Invalid credentials');
    }

    const { access, refresh } = await response.json();
    await storeTokens(access, refresh);
    return access;
}

export async function refreshAccessToken() {
    const refresh = await getRefreshToken();
    if (!refresh) return null;

    try {
        const response = await fetch(`${API_BASE}/api/auth/token/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh }),
        });

        if (!response.ok) return null;

        const data = await response.json();
        await storeTokens(data.access, data.refresh || refresh);
        return data.access;
    } catch {
        return null;
    }
}

export async function isAuthenticated() {
    const token = await getStoredToken();
    if (!token) return false;
    // Simple JWT expiry check (decode payload)
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        if (payload.exp * 1000 < Date.now()) {
            // Token expired, try refresh
            const newToken = await refreshAccessToken();
            return !!newToken;
        }
        return true;
    } catch {
        return false;
    }
}

// --- Biometric Authentication ---

export async function isBiometricAvailable() {
    if (!Capacitor.isNativePlatform()) return false;
    try {
        const result = await NativeBiometric.isAvailable();
        return result.isAvailable;
    } catch {
        return false;
    }
}

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
