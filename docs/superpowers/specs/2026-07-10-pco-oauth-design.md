# Planning Center OAuth + Per-Org Credential Plumbing — Design

**Date:** 2026-07-10
**Status:** Approved
**Goal:** Let churches connect Planning Center with a "Connect with Planning
Center" button (OAuth) instead of manually creating and pasting a developer
Personal Access Token. Conversion-plan item #3 — the biggest remaining
onboarding-funnel leak (Aria is useless until PCO connects, and the current
manual-token step is developer-tool friction for a non-technical audience).

## Load-bearing finding (why this is two pieces)

`core/planning_center.py::PlanningCenterAPI.__init__` reads credentials from
GLOBAL settings (`PLANNING_CENTER_APP_ID/SECRET`), and all ~18 construction
sites call it with no arguments. The per-org fields
`Organization.planning_center_app_id/secret` (written by the onboarding
connect-pco view) are NEVER read by the client. Today every org's Aria queries
hit the single Planning Center account in the Railway env. This is a latent
multi-tenant isolation gap (unexposed only because there are no real customers
with their own PCO data yet). OAuth is meaningless without fixing it, so this
project does BOTH: (1) thread per-org credentials into the client, (2) make
those credentials OAuth tokens.

## Decisions (made with Ryan)

1. Build the per-org plumbing AND OAuth together (one project).
2. Keep the manual App ID/Secret form as a collapsible fallback; OAuth is the
   primary path. PATs still work per PCO docs.
3. Encrypt all PCO secrets at rest (new OAuth tokens AND the existing
   `planning_center_secret`, whose help text already claims "encrypted at
   rest"). `cryptography` (Fernet) is already installed — no new dependency.

## PCO OAuth facts (from developer.planning.center)

- **One** OAuth app for the whole product (NOT one per church). Register it in
  a Planning Center account at api.planningcenteronline.com → get a client ID +
  secret, set the redirect URI.
- Authorize URL: `https://api.planningcenteronline.com/oauth/authorize`
- Token URL: `https://api.planningcenteronline.com/oauth/token`
- Scopes needed: `people services` (space-separated) — covers everything Aria
  queries (people/contacts + service plans/songs/blockouts).
- Access token lifetime: 2 hours (`expires_in` = 7200). Refresh token: 90 days,
  rolling (each refresh issues a new pair).
- Grants: `authorization_code` (initial), `refresh_token` (renewal).

## Manual prerequisite (Ryan, before deploy)

1. Sign in to Planning Center, go to api.planningcenteronline.com → your OAuth
   applications → **New Application**.
2. Name it (e.g. "Aria"), set **Redirect URI** to
   `https://aria.church/onboarding/pco/callback/`.
3. Copy the **Client ID** and **Secret** into Railway env as
   `PCO_OAUTH_CLIENT_ID` and `PCO_OAUTH_CLIENT_SECRET`.
4. Scopes `people` and `services` are requested per-authorization; no app-level
   scope config needed beyond enabling those products.
5. Set `FIELD_ENCRYPTION_KEY` in Railway env to a Fernet key (generate with
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
   Required in production; if unset, encrypted fields fall back to a key
   derived from `SECRET_KEY` (fine for dev/tests, NOT for production — a
   `SECRET_KEY` rotation would then orphan the data). Never lose this key: the
   stored OAuth tokens and manual secret become unreadable without it (users
   would re-authorize / re-enter the manual secret).

Nothing ships broken if the OAuth env vars are absent: the OAuth button renders
a "Planning Center connection isn't configured yet — enter credentials manually
below" message and the manual form still works.

## Piece 1 — per-org credential plumbing

### `core/planning_center.py`

- `PlanningCenterAPI.__init__(self, organization=None)`:
  - Resolve, in priority order:
    1. `organization` with a non-empty `pco_access_token` → OAuth mode
       (store token + refresh token + expiry + the org ref for refresh writes).
    2. `organization` with non-empty `planning_center_app_id`/`secret` →
       manual/PAT mode (Basic auth).
    3. Otherwise → global `settings.PLANNING_CENTER_APP_ID/SECRET` (unchanged
       fallback; keeps Cherry Hills and the whole test suite working with no
       call-site changes needed for the global path).
  - `is_configured` returns True if any of the three resolved.
- `_get()` auth selection:
  - OAuth mode: ensure a fresh token (see refresh below), send
    `headers={'Authorization': 'Bearer ' + access_token}` (no `auth=` tuple).
  - Manual/global mode: `auth=(app_id, secret)` exactly as today.
- **Token refresh (lazy, no cron):** a helper `_ensure_fresh_token()` called at
  the top of `_get()` in OAuth mode. If `pco_token_expires_at` is None or within
  a 5-minute skew of now, POST to the token URL with
  `grant_type=refresh_token`, `refresh_token`, `client_id`, `client_secret`;
  on success write the rotated `access_token`, `refresh_token`, and new
  `pco_token_expires_at` back to the org (`save(update_fields=[...])`) and use
  the new access token. On refresh failure (e.g. refresh token expired after 90
  idle days), log and raise/return empty so the caller degrades gracefully; the
  org's connect status can prompt re-auth. Also handle a 401 on the actual GET
  by attempting one refresh-and-retry.
- `PlanningCenterServicesAPI` inherits `__init__` unchanged (subclass), so it
  accepts `organization=` too.

### Call sites (~18)

Pass the `organization` already in local scope to the constructor:
`PlanningCenterAPI(organization=organization)` /
`PlanningCenterServicesAPI(organization=organization)`.
- `core/agent.py`: all handler functions already receive `organization=` params
  — thread it into every `PlanningCenter*API()` call (lines around 1309, 1310,
  1446, 3116, 3779, 4153, 4512, 4548, 4549, 4956, 4957, 5040, 5106; verify by
  grep at implementation time).
- `core/models.py:3336` and `core/bpm_service.py:297`: pass the org available in
  those scopes (or `None` if genuinely unavailable → global fallback, preserving
  today's behavior).
Where a call site has no org in scope, leaving it argument-less keeps the
current global-fallback behavior — acceptable, not a regression.

## Piece 2 — OAuth flow

### Encrypted field (`core/fields.py`, new)

- `EncryptedTextField(models.TextField)` — transparent Fernet encryption:
  - `get_prep_value(value)`: return `Fernet(key).encrypt(value.encode())`
    decoded to str; pass through empty/None unchanged.
  - `from_db_value(value, ...)`: attempt `Fernet(key).decrypt`; on
    `InvalidToken` (a legacy plaintext value not yet migrated) return the raw
    value unchanged, so reads never crash during the migration window.
  - Key resolution helper `_fernet()`: use `settings.FIELD_ENCRYPTION_KEY` if
    set; else derive a stable key from `SECRET_KEY`
    (`base64.urlsafe_b64encode(sha256(SECRET_KEY).digest())`) so dev/tests need
    no config.
  - Column type stays text; encrypted output is base64 (fits, no length cap) —
    hence TextField, not CharField.

### Model (`core/models.py`, new migration)

New `Organization` fields (all `null=True/blank=True`):
- `pco_access_token = EncryptedTextField()`
- `pco_refresh_token = EncryptedTextField()`
- `pco_token_expires_at = DateTimeField()`
- `pco_auth_method = CharField(max_length=10, blank=True)`  # 'oauth' | 'manual' | ''

Change existing field:
- `planning_center_secret` → `EncryptedTextField` (was CharField; help text
  already says "encrypted at rest"). `planning_center_app_id` stays plaintext
  (it is the Basic-auth identifier, not the secret).

`has_pco_credentials()` extended: True if `pco_access_token` OR
(`planning_center_app_id` and `planning_center_secret`).

### Data migration (encrypt existing secrets)

Separate migration after the schema migration: iterate
`Organization.objects.exclude(planning_center_secret='')` and
`.save(update_fields=['planning_center_secret'])`. Because `from_db_value`
tolerates plaintext (returns it raw) and `get_prep_value` always encrypts, this
transforms Cherry Hills' existing plaintext secret into ciphertext. Reverse op
is a noop. Safe on Railway (migrate runs on deploy before serving).

### Settings / env

- `PCO_OAUTH_CLIENT_ID`, `PCO_OAUTH_CLIENT_SECRET` (env, may be empty).
- `PCO_OAUTH_REDIRECT_URI` defaulting to
  `https://aria.church/onboarding/pco/callback/` (override via env for local).
- `FIELD_ENCRYPTION_KEY` (env; falls back to a SECRET_KEY-derived key when
  unset — see `core/fields.py`).
- Authorize/token URLs as module constants in a small `core/pco_oauth.py`.

### `core/pco_oauth.py` (new — keeps OAuth logic out of the 6k-line views.py)

- `build_authorize_url(state)` → authorize URL with `client_id`,
  `redirect_uri`, `response_type=code`, `scope='people services'`, `state`.
- `exchange_code(code)` → POST token URL `grant_type=authorization_code`;
  returns `{access_token, refresh_token, expires_in}` or raises.
- `refresh_token(refresh_token_value)` → POST `grant_type=refresh_token`.
- `is_configured()` → bool(client id and secret).
- No Django imports beyond settings; pure functions for easy testing (mock
  `requests.post`).

### Views (`core/views.py`, URLs in `core/urls.py`)

- `pco_oauth_start(request)` (login required; resolves org via the existing
  `_resolve_onboarding_org`): if `pco_oauth.is_configured()` is False →
  message + redirect back to connect page. Else generate a random `state`,
  store in `request.session['pco_oauth_state']`, redirect to
  `build_authorize_url(state)`.
- `pco_oauth_callback(request)`: read `code` + `state`; reject if `state` !=
  session value (clear it after). Resolve org. `exchange_code(code)`, store
  tokens on org with `pco_token_expires_at = now + expires_in`,
  `pco_auth_method='oauth'`, `planning_center_connected_at=now`. Redirect to
  `onboarding_invite_team` if in wizard else `org_settings` (mirror
  `onboarding_connect_pco`'s `in_wizard`/`next_url` logic). On exchange error →
  message + back to connect page.
- URLs: `/onboarding/pco/start/` and `/onboarding/pco/callback/` (both under
  the `/onboarding/` PUBLIC_URL prefix; they resolve org from session/user like
  the sibling onboarding views).

### Template (`templates/core/onboarding/connect_pco.html`)

- Primary gold button "Connect with Planning Center" → `pco_oauth_start`.
- Existing manual App ID/Secret form moved under a collapsible
  "Enter credentials manually" `<details>` (kept fully functional; on submit it
  sets `pco_auth_method='manual'`).
- If `pco_oauth.is_configured()` is False, hide/disable the OAuth button and
  show the manual form expanded with a short note.
- Show connected state (method + connected_at) when already connected.

## Security

- CSRF on the OAuth round trip via the `state` param (session-stored, compared,
  single-use).
- All PCO secrets (OAuth access + refresh tokens, manual
  `planning_center_secret`) encrypted at rest via `EncryptedTextField` (Fernet).
  Key from `FIELD_ENCRYPTION_KEY` env, SECRET_KEY-derived fallback for dev.
- Key management: losing `FIELD_ENCRYPTION_KEY` orphans stored secrets (re-auth
  / re-enter required). Key ROTATION (re-encrypting existing data under a new
  key) is out of scope for this change — single active key only.
- The global env `PLANNING_CENTER_SECRET` fallback stays as an env var (not DB),
  so it is not a DB-at-rest concern.

## Testing

- `PlanningCenterAPI` credential resolution: org-with-OAuth → Bearer header +
  no basic auth; org-with-manual → Basic tuple; org-with-neither / no org →
  global settings (all via a mocked `requests.get`, asserting the auth path).
- `_ensure_fresh_token`: expired `pco_token_expires_at` triggers a mocked
  refresh POST, rotated tokens persisted, request proceeds; refresh failure
  degrades gracefully.
- `pco_oauth.exchange_code` / `refresh_token`: mocked `requests.post` returns
  token JSON → parsed correctly; non-200 raises.
- `pco_oauth_callback`: state mismatch → rejected (no tokens written); happy
  path writes tokens + method + connected_at and redirects correctly (wizard vs
  settings).
- `pco_oauth_start`: not-configured → redirect with message; configured →
  redirect to authorize URL containing scope + state.
- Manual form still connects and sets `pco_auth_method='manual'`.
- A spot-check that a representative agent handler passes `organization=` into
  the API constructor (e.g. via a mock asserting the constructor arg).
- `EncryptedTextField`: a saved value is ciphertext in the DB (raw column value
  != plaintext) but reads back equal to the original; a legacy plaintext value
  reads back unchanged (InvalidToken fallback); round-trips through a model
  save/reload.
- Data migration: an org with a plaintext secret has ciphertext in the column
  afterward and still reads back the original secret.
- No live PCO network calls anywhere in tests.

## Out of scope

- Encryption KEY ROTATION (re-encrypting under a new key); single active key.
- Encrypting non-PCO secrets (Stripe keys, etc.) — separate change if wanted.
- Real-time/webhook PCO sync.
- Scopes beyond `people services`.
- Migrating Cherry Hills off its manual/global key — it keeps working via the
  fallback (its secret is now encrypted at rest by the data migration).
