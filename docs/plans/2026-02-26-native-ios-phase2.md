# Native iOS Phase 2: App Badge Count + Pull-to-Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add iOS app icon badge count for unread notifications and pull-to-refresh gesture for all pages.

**Architecture:** Badge count is tracked per-device via a new field on `NativePushToken`. When sending native push, FCM payload includes `apns.payload.aps.badge` with the current count. A lightweight API endpoint resets the count when the app opens. Pull-to-refresh is a pure JS touch handler in `base.html` that reloads the page.

**Tech Stack:** Django, Firebase Cloud Messaging (firebase-admin), Capacitor PushNotifications plugin, vanilla JS touch events

---

### Task 1: Add `unread_badge_count` field to NativePushToken

**Files:**
- Modify: `core/models.py` (NativePushToken class, ~line 3173)
- Test: `tests/test_native_push.py`

**Step 1: Write the failing test**

Add to `tests/test_native_push.py` at the end of `TestNativePushTokenModel`:

```python
def test_badge_count_default_zero(self, user_alpha_owner, org_alpha):
    token = NativePushToken.objects.create(
        user=user_alpha_owner,
        organization=org_alpha,
        token='badge-test-token',
        platform='ios',
    )
    assert token.unread_badge_count == 0

def test_badge_count_increment(self, user_alpha_owner, org_alpha):
    token = NativePushToken.objects.create(
        user=user_alpha_owner,
        organization=org_alpha,
        token='badge-inc-token',
        platform='ios',
    )
    token.unread_badge_count += 1
    token.save()
    token.refresh_from_db()
    assert token.unread_badge_count == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_native_push.py::TestNativePushTokenModel::test_badge_count_default_zero tests/test_native_push.py::TestNativePushTokenModel::test_badge_count_increment -v`
Expected: FAIL with `AttributeError: 'NativePushToken' object has no attribute 'unread_badge_count'`

**Step 3: Add the field and create migration**

In `core/models.py`, add after `updated_at` in `NativePushToken` (~line 3175):

```python
unread_badge_count = models.PositiveIntegerField(default=0)
```

Then run:
```bash
cd /Users/ryanpate/chagent && python manage.py makemigrations core -n add_badge_count_to_native_push_token
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_native_push.py::TestNativePushTokenModel -v`
Expected: All pass

**Step 5: Commit**

```bash
cd /Users/ryanpate/chagent && git add core/models.py core/migrations/ tests/test_native_push.py
git commit -m "feat: add unread_badge_count field to NativePushToken"
```

---

### Task 2: Include badge count in FCM push payload

**Files:**
- Modify: `core/notifications.py` (`send_native_push` ~line 313 and `_send_fcm` ~line 333)
- Test: `tests/test_native_push.py`

**Step 1: Write the failing test**

Add a new test class to `tests/test_native_push.py`:

```python
@pytest.mark.django_db
class TestBadgeCountInPush:
    def test_send_native_push_increments_badge(self, user_alpha_owner, org_alpha):
        token = NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='badge-push-token',
            platform='ios',
        )
        assert token.unread_badge_count == 0

        with patch('core.notifications._send_fcm', return_value=True) as mock_fcm:
            from core.notifications import send_native_push
            send_native_push(token, 'Test Title', 'Test Body', '/')

        token.refresh_from_db()
        assert token.unread_badge_count == 1

    def test_send_native_push_passes_badge_to_fcm(self, user_alpha_owner, org_alpha):
        token = NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='badge-payload-token',
            platform='ios',
        )

        with patch('core.notifications._send_fcm', return_value=True) as mock_fcm:
            from core.notifications import send_native_push
            send_native_push(token, 'Test', 'Body', '/')

        mock_fcm.assert_called_once()
        call_payload = mock_fcm.call_args[0][1]
        assert call_payload['badge'] == 1

    def test_badge_count_increments_across_sends(self, user_alpha_owner, org_alpha):
        token = NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='badge-multi-token',
            platform='ios',
        )

        with patch('core.notifications._send_fcm', return_value=True):
            from core.notifications import send_native_push
            send_native_push(token, 'First', 'Body', '/')
            send_native_push(token, 'Second', 'Body', '/')
            send_native_push(token, 'Third', 'Body', '/')

        token.refresh_from_db()
        assert token.unread_badge_count == 3
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_native_push.py::TestBadgeCountInPush -v`
Expected: FAIL (badge count not incremented)

**Step 3: Update `send_native_push` and `_send_fcm`**

In `core/notifications.py`, replace `send_native_push` (~line 313):

```python
def send_native_push(token_obj, title, body, url='/', data=None):
    """Send a push notification to a native iOS/Android device."""
    # Increment badge count
    token_obj.unread_badge_count += 1
    token_obj.save(update_fields=['unread_badge_count'])

    payload = {
        'title': title,
        'body': body,
        'url': url,
        'data': data or {},
        'badge': token_obj.unread_badge_count,
    }

    try:
        if token_obj.platform == 'android':
            return _send_fcm(token_obj.token, payload)
        elif token_obj.platform == 'ios':
            return _send_apns(token_obj.token, payload)
    except Exception as e:
        logger.error(f"Failed to send native push to {token_obj.platform}: {e}")
        return False
    return False
```

Replace `_send_fcm` (~line 333):

```python
def _send_fcm(token, payload):
    """Send via Firebase Cloud Messaging."""
    try:
        import json
        import os
        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            cred_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
            if cred_json:
                cred = credentials.Certificate(json.loads(cred_json))
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()

        badge_count = payload.get('badge', 0)

        message = messaging.Message(
            notification=messaging.Notification(
                title=payload['title'],
                body=payload['body'],
            ),
            data={
                'url': payload.get('url', '/'),
                **{k: str(v) for k, v in payload.get('data', {}).items()},
            },
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(badge=badge_count),
                ),
            ),
            token=token,
        )
        messaging.send(message)
        return True
    except Exception as e:
        logger.error(f"FCM send failed: {e}")
        return False
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_native_push.py::TestBadgeCountInPush -v`
Expected: All pass

**Step 5: Commit**

```bash
cd /Users/ryanpate/chagent && git add core/notifications.py tests/test_native_push.py
git commit -m "feat: include badge count in FCM push payload for iOS"
```

---

### Task 3: Add badge-clear API endpoint

**Files:**
- Modify: `core/api_views.py` (add new view)
- Modify: `core/api_urls.py` (add route)
- Test: `tests/test_native_push.py`

**Step 1: Write the failing test**

Add a new test class to `tests/test_native_push.py`:

```python
@pytest.mark.django_db
class TestBadgeClearAPI:
    def test_clear_badge_resets_count(self, client, user_alpha_owner, org_alpha):
        token = NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='clear-test-token',
            platform='ios',
            unread_badge_count=5,
        )
        client.force_login(user_alpha_owner)
        response = client.post('/api/push/badge-clear/')
        assert response.status_code == 200

        token.refresh_from_db()
        assert token.unread_badge_count == 0

    def test_clear_badge_resets_all_user_tokens(self, client, user_alpha_owner, org_alpha):
        NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='token-1',
            platform='ios',
            unread_badge_count=3,
        )
        NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='token-2',
            platform='android',
            unread_badge_count=7,
        )
        client.force_login(user_alpha_owner)
        response = client.post('/api/push/badge-clear/')
        assert response.status_code == 200

        counts = list(NativePushToken.objects.filter(user=user_alpha_owner).values_list('unread_badge_count', flat=True))
        assert counts == [0, 0]

    def test_clear_badge_requires_auth(self, client):
        response = client.post('/api/push/badge-clear/')
        assert response.status_code in [401, 403]
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_native_push.py::TestBadgeClearAPI -v`
Expected: FAIL with 404 (route doesn't exist)

**Step 3: Add the endpoint**

In `core/api_views.py`, add at the end:

```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_badge_count(request):
    from core.models import NativePushToken

    NativePushToken.objects.filter(user=request.user).update(unread_badge_count=0)
    return Response({'status': 'cleared'})
```

In `core/api_urls.py`, add the route:

```python
path('push/badge-clear/', api_views.clear_badge_count, name='api_push_badge_clear'),
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_native_push.py::TestBadgeClearAPI -v`
Expected: All pass

**Step 5: Commit**

```bash
cd /Users/ryanpate/chagent && git add core/api_views.py core/api_urls.py tests/test_native_push.py
git commit -m "feat: add badge-clear API endpoint"
```

---

### Task 4: Clear badge on app open (base.html)

**Files:**
- Modify: `templates/base.html` (add badge clear script near existing Capacitor scripts, ~line 683)

**Step 1: Add badge clear script**

In `templates/base.html`, add a new `<script>` block after the Capacitor native detection script (after the `capacitor-native` class script) and before the haptics script:

```javascript
<script>
    // Clear app badge count when page loads in native app
    (function() {
        if (!window.Capacitor || !window.Capacitor.Plugins) return;

        var PushNotifications = window.Capacitor.Plugins.PushNotifications;
        if (PushNotifications && PushNotifications.removeAllDeliveredNotifications) {
            PushNotifications.removeAllDeliveredNotifications().catch(function() {});
        }

        // Reset server-side badge counter
        var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        var token = csrfToken ? csrfToken.value : '';
        fetch('/api/push/badge-clear/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token,
            },
            credentials: 'same-origin',
        }).catch(function() {});
    })();
</script>
```

**Step 2: Test manually**

Build and run in Xcode simulator. Open Safari Web Inspector. On page load you should see:
- No errors from the badge clear script
- A POST to `/api/push/badge-clear/` in the Network tab (may return 401 if not using session auth — that's OK, the endpoint is for JWT auth from the native app; the session-based call is a best-effort bonus)

**Step 3: Commit**

```bash
cd /Users/ryanpate/chagent && git add templates/base.html
git commit -m "feat: clear app badge and notifications on page load"
```

---

### Task 5: Pull-to-refresh gesture

**Files:**
- Modify: `templates/base.html` (add pull-to-refresh JS and update existing `.ptr-indicator` CSS)

**Step 1: Update the `.ptr-indicator` CSS**

In `templates/base.html`, replace the existing `.ptr-indicator` CSS block (~line 302):

```css
/* Pull to refresh indicator */
.ptr-indicator {
    position: fixed;
    top: -50px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 9999;
    width: 36px;
    height: 36px;
    border: 3px solid rgba(201, 162, 39, 0.3);
    border-top-color: #c9a227;
    border-radius: 50%;
    transition: top 0.2s ease;
}
.ptr-indicator.pulling {
    top: 10px;
}
.ptr-indicator.refreshing {
    top: 10px;
    animation: ptr-spin 0.6s linear infinite;
}
@keyframes ptr-spin {
    to { transform: translateX(-50%) rotate(360deg); }
}
```

**Step 2: Add the ptr-indicator element and JS**

In `templates/base.html`, add the indicator element right after `<body>` tag (~line 349), before any other content:

```html
<div id="ptr-indicator" class="ptr-indicator"></div>
```

Then add a new `<script>` block after the haptics script, before `</body>`:

```javascript
<script>
    // Pull-to-refresh for native app
    (function() {
        if (!window.Capacitor || !window.Capacitor.Plugins) return;

        var startY = 0;
        var pulling = false;
        var threshold = 60;
        var indicator = document.getElementById('ptr-indicator');

        document.addEventListener('touchstart', function(e) {
            if (window.scrollY === 0) {
                startY = e.touches[0].clientY;
                pulling = true;
            }
        }, { passive: true });

        document.addEventListener('touchmove', function(e) {
            if (!pulling) return;
            var distance = e.touches[0].clientY - startY;
            if (distance > 0 && distance < 120) {
                indicator.style.top = (distance - 50) + 'px';
                if (distance > threshold) {
                    indicator.classList.add('pulling');
                } else {
                    indicator.classList.remove('pulling');
                }
            }
        }, { passive: true });

        document.addEventListener('touchend', function() {
            if (!pulling) return;
            pulling = false;
            var currentTop = parseInt(indicator.style.top) || -50;
            if (currentTop > threshold - 50) {
                indicator.classList.remove('pulling');
                indicator.classList.add('refreshing');
                window.location.reload();
            } else {
                indicator.style.top = '-50px';
                indicator.classList.remove('pulling');
            }
        });
    })();
</script>
```

**Step 2: Test manually**

Build and run in Xcode simulator:
- Pull down from top of any page — gold spinner should appear
- Release past threshold — page reloads
- Release before threshold — spinner snaps back
- Does NOT trigger when scrolled down in a page

**Step 3: Commit**

```bash
cd /Users/ryanpate/chagent && git add templates/base.html
git commit -m "feat: add pull-to-refresh gesture for native app"
```

---

### Task 6: Run full test suite and push

**Step 1: Run all tests**

```bash
cd /Users/ryanpate/chagent && python -m pytest tests/ -v --tb=short
```

Expected: All 446+ tests pass (441 existing + 5 new badge tests)

**Step 2: Push**

```bash
cd /Users/ryanpate/chagent && git push
```
