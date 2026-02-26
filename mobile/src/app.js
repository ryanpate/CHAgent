import { SplashScreen } from '@capacitor/splash-screen';
import { StatusBar } from '@capacitor/status-bar';
import { Browser } from '@capacitor/browser';
import { Capacitor } from '@capacitor/core';
import { Haptics, ImpactStyle, NotificationType } from '@capacitor/haptics';
import { Network } from '@capacitor/network';
import {
    login,
    isAuthenticated,
    clearTokens,
    isBiometricAvailable,
    hasBiometricCredentials,
    loginWithBiometric,
    storeBiometricCredentials,
} from './auth.js';
import { initPushNotifications } from './push.js';

const SERVER_URL = 'https://aria.church';

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

async function setupNetworkMonitoring() {
    Network.addListener('networkStatusChange', (status) => {
        console.log('[ARIA] Network status:', status.connected);
        if (status.connected) {
            if (window.location.href.includes('offline.html')) {
                window.location.reload();
            }
        }
    });
}

async function init() {
    await setupNetworkMonitoring();

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

function showLogin() {
    document.getElementById('login-screen').style.display = 'flex';
    document.getElementById('tab-bar').style.display = 'none';

    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const btn = document.getElementById('login-btn');
        const error = document.getElementById('login-error');

        btn.disabled = true;
        btn.textContent = 'Signing in...';
        error.style.display = 'none';

        try {
            await login(email, password);
            await storeBiometricCredentials(email, password);
            await hapticSuccess();
            await showApp();
        } catch (err) {
            error.textContent = err.message;
            error.style.display = 'block';
        } finally {
            btn.disabled = false;
            btn.textContent = 'Sign In';
        }
    });
}

async function showApp() {
    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('tab-bar').style.display = 'block';

    // Set app-mode cookie so Django hides sidebar
    document.cookie = 'aria_app=1; path=/; domain=aria.church; secure; samesite=lax';

    // Navigate to default tab
    navigateToUrl('/chat/');

    // Set up tab bar
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', async () => {
            await hapticImpact();
            const url = tab.dataset.url;

            // Handle "More" tab specially
            if (url === '/more/') {
                showMoreMenu();
                return;
            }

            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            navigateToUrl(url);
        });
    });

    // Initialize push notifications
    await initPushNotifications();

    // Listen for navigation events from push notifications
    window.addEventListener('navigate', (e) => {
        navigateToUrl(e.detail.url);
    });
}

function navigateToUrl(path) {
    // The app uses the server URL directly
    // Capacitor's server config handles loading from aria.church
    window.location.href = `${SERVER_URL}${path}?app=1`;
}

function showMoreMenu() {
    hapticImpact();

    // Simple menu for additional pages
    const items = [
        { label: 'Analytics', url: '/analytics/' },
        { label: 'Care Dashboard', url: '/care/' },
        { label: 'Knowledge Base', url: '/documents/' },
        { label: 'Settings', url: '/settings/' },
        { label: 'Sign Out', action: 'logout' },
    ];

    // Create a simple overlay menu
    let overlay = document.getElementById('more-menu');
    if (overlay) {
        overlay.remove();
        return;
    }

    overlay = document.createElement('div');
    overlay.id = 'more-menu';
    overlay.style.cssText = `
        position: fixed; bottom: 60px; left: 0; right: 0; top: 0;
        background: rgba(0,0,0,0.7); z-index: 9998;
        display: flex; align-items: flex-end; justify-content: center;
    `;

    const menu = document.createElement('div');
    menu.style.cssText = `
        background: #1a1a1a; border-radius: 12px 12px 0 0;
        width: 100%; padding: 1rem; padding-bottom: calc(1rem + env(safe-area-inset-bottom, 0px));
    `;

    items.forEach(item => {
        const btn = document.createElement('button');
        btn.textContent = item.label;
        btn.style.cssText = `
            display: block; width: 100%; padding: 1rem;
            background: none; border: none; color: #e5e5e5;
            font-size: 1rem; text-align: left; cursor: pointer;
            border-bottom: 1px solid #333;
        `;
        if (item.action === 'logout') {
            btn.style.color = '#ef4444';
            btn.addEventListener('click', async () => {
                await hapticImpact();
                await clearTokens();
                document.cookie = 'aria_app=; path=/; domain=aria.church; expires=Thu, 01 Jan 1970 00:00:00 GMT';
                window.location.reload();
            });
        } else {
            btn.addEventListener('click', async () => {
                await hapticImpact();
                overlay.remove();
                navigateToUrl(item.url);
            });
        }
        menu.appendChild(btn);
    });

    overlay.appendChild(menu);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.remove();
    });
    document.body.appendChild(overlay);
}

// Handle external links (open in system browser)
document.addEventListener('click', (e) => {
    const link = e.target.closest('a');
    if (!link) return;

    const href = link.getAttribute('href');
    if (!href) return;

    const isExternal = href.startsWith('http') && !href.includes('aria.church');
    const isSpecial = href.startsWith('mailto:') || href.startsWith('tel:');

    if (isExternal || isSpecial) {
        e.preventDefault();
        Browser.open({ url: href });
    }
});

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', init);
