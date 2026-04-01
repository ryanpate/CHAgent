# Song Submissions Feature — Design Spec

**Date:** 2026-04-01
**Status:** Approved
**Branch:** TBD (from `feat/subtasks`)

## Overview

Allow anyone — logged-in members or anonymous visitors — to suggest songs for the worship team to review. Submissions are scoped to an organization via the org slug in the URL. The team gets a dashboard with stats, insights, filterable list, inline 1-5 star voting, and push notifications on new submissions.

## Architecture

New Django app `songs/` (following the `blog/` app pattern) with its own models, views, URLs, and templates. Keeps the feature self-contained and avoids further bloating `core/`.

## Data Models

### SongSubmission

| Field | Type | Notes |
|-------|------|-------|
| `organization` | FK → Organization | CASCADE, `related_name='song_submissions'` |
| `title` | CharField(200) | Required |
| `artist` | CharField(200) | Required |
| `link` | URLField | Optional. YouTube, Spotify, Apple Music, etc. |
| `submitter_name` | CharField(200) | Optional. Anonymous if blank. |
| `submitter_comment` | TextField | Optional. Why they're suggesting it. |
| `submitted_by` | FK → User | Nullable. Set if submitter is logged in. |
| `status` | CharField(20) | Choices: `pending` (Pending Review), `reviewed` (Reviewed), `approved` (Approved), `rejected` (Not Added). Default: `pending`. |
| `reviewed_by` | FK → User | Nullable. Who changed the status. |
| `review_note` | TextField | Optional. Internal team note. |
| `reviewed_at` | DateTimeField | Nullable. When status was changed. |
| `average_rating` | FloatField | Default 0.0. Denormalized from votes. |
| `vote_count` | IntegerField | Default 0. Denormalized from votes. |
| `created_at` | DateTimeField | auto_now_add |
| `updated_at` | DateTimeField | auto_now |

### SongVote

| Field | Type | Notes |
|-------|------|-------|
| `submission` | FK → SongSubmission | CASCADE, `related_name='votes'` |
| `user` | FK → User | CASCADE |
| `rating` | PositiveSmallIntegerField | 1-5, validated with MinValue/MaxValue |
| `created_at` | DateTimeField | auto_now_add |
| `updated_at` | DateTimeField | auto_now |

**Constraints:** `unique_together = ['submission', 'user']` — one vote per user per song, updatable.

**Denormalization:** When a vote is cast or updated, recalculate `average_rating` and `vote_count` on the parent `SongSubmission` to avoid aggregation queries on every dashboard load.

## URL Structure

### Public (no auth required)

| URL | Method | View | Purpose |
|-----|--------|------|---------|
| `/<org-slug>/songs/submit/` | GET | `song_submit` | Render submission form |
| `/<org-slug>/songs/submit/` | POST | `song_submit` | Create submission |
| `/<org-slug>/songs/submit/thanks/` | GET | `song_submit_thanks` | Confirmation page |

### Team (auth required, org-scoped)

| URL | Method | View | Purpose |
|-----|--------|------|---------|
| `/songs/` | GET | `song_dashboard` | Dashboard with stats + list |
| `/songs/<int:pk>/` | GET | `song_detail` | Submission detail page |
| `/songs/<int:pk>/vote/` | POST | `song_vote` | Cast/update vote (HTMX) |
| `/songs/<int:pk>/status/` | POST | `song_update_status` | Update status (HTMX) |

## Views

### Public Submission Form (`song_submit`)

- **GET:** Render form with org context (org name below ARIA logo). If user is authenticated and belongs to the org, pre-fill `submitter_name` from their User record.
- **POST:** Validate required fields (title, artist). Check org slug resolves to an active organization (404 if not). Create `SongSubmission` with `submitted_by` set if authenticated. Trigger push notification. Redirect to confirmation page.
- **Template:** Standalone public template (like `base_public.html`), dark theme, ARIA branding with org name.

### Confirmation Page (`song_submit_thanks`)

- Shows submitted song title, artist, and "Pending Review" status.
- "Submit Another Song" link back to the form.

### Dashboard (`song_dashboard`)

- **Stats bar:** Total submissions, pending count, approved count, rejected count, average rating across all submissions.
- **Insight cards:** Top-rated pending song (highest `average_rating` where `status='pending'`), most submitted artist (aggregate `COUNT` grouped by `artist`).
- **Filterable list:** Filter by status, sort by newest/oldest/highest rated/most votes. Each row shows title, artist, submitter, date, comment (if any), listen link (if any), inline star rating with vote count.
- **Copy Submission Link button:** Copies `https://aria.church/<org-slug>/songs/submit/` to clipboard.
- **Pagination:** Standard Django pagination if list grows large.

### Detail Page (`song_detail`)

- **Left column:**
  - Submission details: title, artist, submitter, date, comment, listen link.
  - Your rating: Large interactive stars, HTMX POST to `/songs/<pk>/vote/`.
  - Team votes: List of all votes with user initials, name, and star rating. Average at bottom.
- **Right column:**
  - Status buttons: Pending, Reviewed, Approved, Not Added. Current status highlighted. HTMX POST to `/songs/<pk>/status/`. Requires admin/owner/leader role.
  - Team note: Textarea for internal notes, saved with status update.
  - Quick stats: Average rating, total votes, days pending.
- **Duplicate detection:** If similar submissions exist (case-insensitive title match within the org), show "Similar submissions" section with links.

### Vote (`song_vote`)

- POST only, HTMX. Accepts `rating` (1-5).
- Creates or updates `SongVote` (upsert via `unique_together`).
- Recalculates `average_rating` and `vote_count` on the `SongSubmission`.
- Returns updated star display HTML fragment.

### Update Status (`song_update_status`)

- POST only, HTMX. Requires admin/owner/leader role.
- Accepts `status` and optional `review_note`.
- Sets `reviewed_by`, `reviewed_at`, `review_note`.
- Returns updated status badge HTML fragment.

## Permissions

| Action | Required Role |
|--------|---------------|
| Submit a song (public form) | None (anonymous OK) |
| View dashboard | Any authenticated org member |
| View submission detail | Any authenticated org member |
| Vote on a submission | Any authenticated org member |
| Update status (approve/reject) | Admin, Owner, or Leader |
| Save team review note | Admin, Owner, or Leader |

## Push Notifications

- **New notification type:** `song_submission`
- **NotificationPreference field:** `song_submissions = models.BooleanField(default=True)`
- **Trigger:** After `SongSubmission` is created in the public submission view.
- **Helper:** `notify_song_submission(submission)` in `core/notifications.py`
- **Recipients:** All active members of the organization.
- **Content:**
  - Title: "New Song Suggestion"
  - Body: `"{submitter_name} suggested {title} by {artist}"` (or "Someone suggested..." if anonymous)
  - URL: `/songs/<pk>/`
- **Delivery:** Both web push (PushSubscription) and native push (NativePushToken) via existing `send_notification_to_users()`.

## Sidebar Navigation

- Add "Song Submissions" link with a music note icon in the sidebar.
- Show badge count of pending submissions (`SongSubmission.objects.filter(organization=org, status='pending').count()`).
- Position near "Knowledge Base" in the content section.

## Duplicate Detection

Soft detection, not prevention. On the dashboard and detail pages:
- Query for other submissions in the same org with case-insensitive title match (`title__iexact`).
- Dashboard: "Possible duplicate" badge on rows with matches.
- Detail page: "Similar submissions" section listing matches with links.
- Submissions are never blocked — multiple submissions of the same song carry signal about congregational interest.

## Templates

| Template | Purpose |
|----------|---------|
| `songs/submit.html` | Public submission form (extends `base_public.html`) |
| `songs/submit_thanks.html` | Confirmation page (extends `base_public.html`) |
| `songs/dashboard.html` | Team dashboard (extends `base.html`) |
| `songs/detail.html` | Submission detail (extends `base.html`) |
| `songs/partials/submission_row.html` | HTMX-swappable list row |
| `songs/partials/star_rating.html` | HTMX-swappable star display |
| `songs/partials/status_badge.html` | HTMX-swappable status badge |

## Design

- Dark theme: `#0f0f0f` background, `#1a1a1a` cards, `#333` borders, `#c9a227` gold accent.
- Matches existing ARIA design system used across all authenticated pages.
- Public form shows ARIA logo + org name, minimal chrome.
- Stars use gold (`#c9a227`) for filled, `#333` for empty.
- Status badges: gold for pending, white for reviewed, green for approved, gray for rejected.

## Testing

Tests in `tests/test_song_submissions.py` covering:
- **Model tests:** SongSubmission CRUD, SongVote uniqueness constraint, denormalized rating recalculation, org isolation.
- **Public form tests:** GET renders form, POST creates submission, required field validation, invalid org slug returns 404, logged-in user auto-fills `submitted_by`.
- **Dashboard tests:** Stats accuracy, filter/sort behavior, insights calculations, auth required.
- **Detail tests:** Vote creation and update, status change permissions (leader+ only), team vote display, duplicate detection.
- **Notification tests:** Push sent on submission, respects preferences, correct content.
- **Permission tests:** Members can vote but not change status, anonymous can submit but not access dashboard.
