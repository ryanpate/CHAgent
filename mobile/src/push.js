import { PushNotifications } from '@capacitor/push-notifications';
import { Capacitor } from '@capacitor/core';
import { getStoredToken } from './auth.js';

const API_BASE = 'https://aria.church';

export async function initPushNotifications() {
    if (!Capacitor.isNativePlatform()) return;

    const permission = await PushNotifications.requestPermissions();
    if (permission.receive !== 'granted') return;

    await PushNotifications.register();

    PushNotifications.addListener('registration', async (token) => {
        await registerTokenWithServer(token.value);
    });

    PushNotifications.addListener('registrationError', (error) => {
        console.error('Push registration failed:', error);
    });

    PushNotifications.addListener('pushNotificationReceived', (notification) => {
        console.log('Push received:', notification);
    });

    PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
        const url = action.notification.data?.url;
        if (url) {
            // Navigate WebView to the notification URL
            window.dispatchEvent(new CustomEvent('navigate', { detail: { url } }));
        }
    });
}

async function registerTokenWithServer(token) {
    const authToken = await getStoredToken();
    if (!authToken) return;

    const platform = Capacitor.getPlatform(); // 'ios' or 'android'

    try {
        await fetch(`${API_BASE}/api/push/register/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`,
            },
            body: JSON.stringify({
                token,
                platform,
                device_name: `${platform} device`,
            }),
        });
    } catch (error) {
        console.error('Failed to register push token:', error);
    }
}
