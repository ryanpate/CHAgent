import { Preferences } from '@capacitor/preferences';

const API_BASE = 'https://aria.church';

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
