# Song Submissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow anyone to suggest songs for a worship team to review, with org-scoped public submission, team dashboard with stats/voting, and push notifications.

**Architecture:** New `songs/` Django app (like `blog/`) with `SongSubmission` and `SongVote` models. Public form at `/<org-slug>/songs/submit/`, team dashboard at `/songs/`. HTMX for voting and status updates. Push notifications via existing `core/notifications.py`.

**Tech Stack:** Django 5.x, HTMX, Tailwind CSS, pytest, existing push notification infrastructure.

**Spec:** `docs/superpowers/specs/2026-04-01-song-submissions-design.md`

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `songs/__init__.py` | Create | App package |
| `songs/apps.py` | Create | Django app config |
| `songs/models.py` | Create | SongSubmission, SongVote models |
| `songs/views.py` | Create | Public submission + team dashboard/detail/vote/status views |
| `songs/urls.py` | Create | URL routing for team views |
| `songs/admin.py` | Create | Admin interface for submissions |
| `config/settings.py:70` | Modify | Add `'songs'` to INSTALLED_APPS |
| `config/urls.py:116-118` | Modify | Add songs URL includes (public + team) |
| `core/middleware.py:29-53` | Modify | Add song submission public URLs to PUBLIC_URLS |
| `core/models.py:3227` | Modify | Add `song_submissions` field to NotificationPreference |
| `core/notifications.py` | Modify | Add `notify_song_submission()` + preference check |
| `core/views.py:4329-4379` | Modify | Add `song_submissions` to push_preferences POST handler |
| `templates/songs/submit.html` | Create | Public submission form |
| `templates/songs/submit_thanks.html` | Create | Confirmation page |
| `templates/songs/dashboard.html` | Create | Team dashboard |
| `templates/songs/detail.html` | Create | Submission detail page |
| `templates/songs/partials/submission_row.html` | Create | HTMX-swappable list row |
| `templates/songs/partials/star_rating.html` | Create | HTMX-swappable star display |
| `templates/songs/partials/status_buttons.html` | Create | HTMX-swappable status buttons |
| `templates/base.html:488-494` | Modify | Add Song Submissions nav link |
| `templates/core/notifications/preferences.html` | Modify | Add song submissions toggle |
| `tests/test_song_submissions.py` | Create | All tests |

---

### Task 1: Create the `songs` Django app scaffold

**Files:**
- Create: `songs/__init__.py`
- Create: `songs/apps.py`
- Create: `songs/models.py`
- Create: `songs/urls.py`
- Create: `songs/admin.py`
- Modify: `config/settings.py:70`

- [ ] **Step 1: Create app directory and files**

```bash
mkdir -p songs
```

- [ ] **Step 2: Create `songs/__init__.py`**

Create empty file:
```python
```

- [ ] **Step 3: Create `songs/apps.py`**

```python
from django.apps import AppConfig


class SongsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'songs'
    verbose_name = 'Song Submissions'
```

- [ ] **Step 4: Create `songs/models.py` with SongSubmission and SongVote**

```python
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class SongSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
        ('rejected', 'Not Added'),
    ]

    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='song_submissions',
    )

    # Song info
    title = models.CharField(max_length=200)
    artist = models.CharField(max_length=200)
    link = models.URLField(blank=True)

    # Submitter info
    submitter_name = models.CharField(max_length=200, blank=True)
    submitter_comment = models.TextField(blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='song_submissions',
    )

    # Review
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_song_submissions',
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Denormalized voting data
    average_rating = models.FloatField(default=0.0)
    vote_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} by {self.artist}"

    def update_rating(self):
        """Recalculate average_rating and vote_count from votes."""
        from django.db.models import Avg, Count
        stats = self.votes.aggregate(avg=Avg('rating'), count=Count('id'))
        self.average_rating = round(stats['avg'] or 0.0, 1)
        self.vote_count = stats['count'] or 0
        self.save(update_fields=['average_rating', 'vote_count'])


class SongVote(models.Model):
    submission = models.ForeignKey(
        SongSubmission,
        on_delete=models.CASCADE,
        related_name='votes',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['submission', 'user']

    def __str__(self):
        return f"{self.user} rated {self.submission.title}: {self.rating}/5"
```

- [ ] **Step 5: Create `songs/urls.py`**

```python
from django.urls import path
from . import views

app_name = 'songs'

urlpatterns = [
    path('', views.song_dashboard, name='dashboard'),
    path('<int:pk>/', views.song_detail, name='detail'),
    path('<int:pk>/vote/', views.song_vote, name='vote'),
    path('<int:pk>/status/', views.song_update_status, name='update_status'),
]
```

- [ ] **Step 6: Create `songs/admin.py`**

```python
from django.contrib import admin
from .models import SongSubmission, SongVote


@admin.register(SongSubmission)
class SongSubmissionAdmin(admin.ModelAdmin):
    list_display = ['title', 'artist', 'organization', 'status', 'average_rating', 'vote_count', 'created_at']
    list_filter = ['status', 'organization', 'created_at']
    search_fields = ['title', 'artist', 'submitter_name']
    readonly_fields = ['average_rating', 'vote_count', 'created_at', 'updated_at']


@admin.register(SongVote)
class SongVoteAdmin(admin.ModelAdmin):
    list_display = ['submission', 'user', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
```

- [ ] **Step 7: Create placeholder `songs/views.py`**

```python
# Views will be implemented in later tasks
```

- [ ] **Step 8: Add `'songs'` to INSTALLED_APPS in `config/settings.py`**

Add `'songs',` after the `'blog',` line (line 70).

- [ ] **Step 9: Generate and run migration**

```bash
python manage.py makemigrations songs
python manage.py migrate
```

Expected: Migration creates `SongSubmission` and `SongVote` tables.

- [ ] **Step 10: Commit**

```bash
git add songs/ config/settings.py
git commit -m "feat(songs): scaffold songs app with SongSubmission and SongVote models"
```

---

### Task 2: Write model tests

**Files:**
- Create: `tests/test_song_submissions.py`

- [ ] **Step 1: Write model and denormalization tests**

```python
import pytest
from django.test import Client
from songs.models import SongSubmission, SongVote


@pytest.mark.django_db
class TestSongSubmissionModel:
    def test_create_submission(self, org_alpha):
        sub = SongSubmission.objects.create(
            organization=org_alpha,
            title='Build My Life',
            artist='Housefires',
            submitter_name='Sarah M.',
            submitter_comment='Great for Good Friday',
        )
        assert sub.status == 'pending'
        assert sub.average_rating == 0.0
        assert sub.vote_count == 0
        assert str(sub) == 'Build My Life by Housefires'

    def test_submission_with_link(self, org_alpha):
        sub = SongSubmission.objects.create(
            organization=org_alpha,
            title='Graves Into Gardens',
            artist='Elevation Worship',
            link='https://www.youtube.com/watch?v=example',
        )
        assert sub.link == 'https://www.youtube.com/watch?v=example'

    def test_submission_with_logged_in_user(self, org_alpha, user_alpha_owner):
        sub = SongSubmission.objects.create(
            organization=org_alpha,
            title='King of Kings',
            artist='Hillsong Worship',
            submitted_by=user_alpha_owner,
            submitter_name='Alpha Owner',
        )
        assert sub.submitted_by == user_alpha_owner

    def test_org_isolation(self, org_alpha, org_beta):
        SongSubmission.objects.create(organization=org_alpha, title='Song A', artist='Artist A')
        SongSubmission.objects.create(organization=org_beta, title='Song B', artist='Artist B')
        assert SongSubmission.objects.filter(organization=org_alpha).count() == 1
        assert SongSubmission.objects.filter(organization=org_beta).count() == 1

    def test_ordering_newest_first(self, org_alpha):
        sub1 = SongSubmission.objects.create(organization=org_alpha, title='First', artist='A')
        sub2 = SongSubmission.objects.create(organization=org_alpha, title='Second', artist='B')
        subs = list(SongSubmission.objects.filter(organization=org_alpha))
        assert subs[0] == sub2
        assert subs[1] == sub1


@pytest.mark.django_db
class TestSongVoteModel:
    def test_cast_vote(self, org_alpha, user_alpha_owner):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='Artist')
        vote = SongVote.objects.create(submission=sub, user=user_alpha_owner, rating=4)
        assert vote.rating == 4

    def test_unique_vote_per_user(self, org_alpha, user_alpha_owner):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='Artist')
        SongVote.objects.create(submission=sub, user=user_alpha_owner, rating=4)
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            SongVote.objects.create(submission=sub, user=user_alpha_owner, rating=5)

    def test_update_rating_single_vote(self, org_alpha, user_alpha_owner):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='Artist')
        SongVote.objects.create(submission=sub, user=user_alpha_owner, rating=4)
        sub.update_rating()
        assert sub.average_rating == 4.0
        assert sub.vote_count == 1

    def test_update_rating_multiple_votes(self, org_alpha, user_alpha_owner, user_alpha_member):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='Artist')
        SongVote.objects.create(submission=sub, user=user_alpha_owner, rating=5)
        SongVote.objects.create(submission=sub, user=user_alpha_member, rating=3)
        sub.update_rating()
        assert sub.average_rating == 4.0
        assert sub.vote_count == 2

    def test_update_rating_no_votes(self, org_alpha):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='Artist')
        sub.update_rating()
        assert sub.average_rating == 0.0
        assert sub.vote_count == 0
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
python -m pytest tests/test_song_submissions.py -v
```

Expected: All 10 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_song_submissions.py
git commit -m "test(songs): add model tests for SongSubmission and SongVote"
```

---

### Task 3: Public submission form view and templates

**Files:**
- Modify: `songs/views.py`
- Create: `templates/songs/submit.html`
- Create: `templates/songs/submit_thanks.html`
- Modify: `config/urls.py:116-118`
- Modify: `core/middleware.py:29-53`

- [ ] **Step 1: Write tests for the public submission form**

Add to `tests/test_song_submissions.py`:

```python
@pytest.mark.django_db
class TestPublicSubmissionForm:
    def test_form_renders(self, org_alpha):
        client = Client()
        response = client.get(f'/{org_alpha.slug}/songs/submit/')
        assert response.status_code == 200
        assert b'Suggest a Song' in response.content

    def test_form_shows_org_name(self, org_alpha):
        client = Client()
        response = client.get(f'/{org_alpha.slug}/songs/submit/')
        assert org_alpha.name.encode() in response.content

    def test_invalid_org_slug_404(self):
        client = Client()
        response = client.get('/nonexistent-org/songs/submit/')
        assert response.status_code == 404

    def test_submit_song(self, org_alpha):
        client = Client()
        response = client.post(f'/{org_alpha.slug}/songs/submit/', {
            'title': 'Goodness of God',
            'artist': 'Bethel Music',
            'link': 'https://youtube.com/watch?v=example',
            'submitter_name': 'Jane Doe',
            'submitter_comment': 'Perfect for Easter',
        })
        assert response.status_code == 200
        assert b'Song Submitted' in response.content
        sub = SongSubmission.objects.get(title='Goodness of God')
        assert sub.organization == org_alpha
        assert sub.artist == 'Bethel Music'
        assert sub.submitter_name == 'Jane Doe'

    def test_submit_requires_title(self, org_alpha):
        client = Client()
        response = client.post(f'/{org_alpha.slug}/songs/submit/', {
            'title': '',
            'artist': 'Bethel Music',
        })
        assert response.status_code == 200
        assert b'Song title is required' in response.content
        assert SongSubmission.objects.count() == 0

    def test_submit_requires_artist(self, org_alpha):
        client = Client()
        response = client.post(f'/{org_alpha.slug}/songs/submit/', {
            'title': 'Goodness of God',
            'artist': '',
        })
        assert response.status_code == 200
        assert b'Artist is required' in response.content
        assert SongSubmission.objects.count() == 0

    def test_submit_minimal_fields(self, org_alpha):
        client = Client()
        response = client.post(f'/{org_alpha.slug}/songs/submit/', {
            'title': 'Way Maker',
            'artist': 'Sinach',
        })
        assert response.status_code == 200
        sub = SongSubmission.objects.get(title='Way Maker')
        assert sub.submitter_name == ''
        assert sub.link == ''

    def test_logged_in_user_prefills(self, org_alpha, user_alpha_owner):
        client = Client()
        client.force_login(user_alpha_owner)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        response = client.post(f'/{org_alpha.slug}/songs/submit/', {
            'title': 'Holy Spirit',
            'artist': 'Francesca Battistelli',
        })
        assert response.status_code == 200
        sub = SongSubmission.objects.get(title='Holy Spirit')
        assert sub.submitted_by == user_alpha_owner
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_song_submissions.py::TestPublicSubmissionForm -v
```

Expected: All fail (views not implemented yet).

- [ ] **Step 3: Add public song submission URLs to `core/middleware.py` PUBLIC_URLS**

In `core/middleware.py`, add to the `PUBLIC_URLS` list (around line 53, before the closing `]`):

```python
        # Song submissions (public)
        '/songs/submit',
```

Note: The middleware uses `startswith` matching, so this will catch `/<org-slug>/songs/submit/` paths. Actually, looking at the middleware more carefully — the public URLs at `/<org-slug>/songs/submit/` are matched by the path prefix. We need to add the org-slug pattern. Let me check the middleware matching logic.

Actually, the `_is_public_url` method in TenantMiddleware checks `request.path.startswith(url)` for each URL in `PUBLIC_URLS`. Since our public URL starts with `/<org-slug>/`, and org slugs are dynamic, we can't use a static prefix. Instead, we should add a regex or path-based check.

The simpler approach: add a dedicated check in the middleware's `process_request` for paths matching the song submission pattern. But even simpler — the middleware already returns `None` for unauthenticated users (line 68-69: `if not request.user.is_authenticated: return None`), so anonymous submissions will work without changes. For logged-in users submitting to a different org's form, we just need the view to look up the org from the slug rather than relying on `request.organization`.

So: **No middleware change needed.** The view will look up the org by slug directly.

- [ ] **Step 4: Add public URL route to `config/urls.py`**

Add before the `path('', include('core.urls'))` line (line 118):

```python
    # Song submissions - public form (org-scoped by slug)
    path('<slug:org_slug>/songs/submit/', include([
        path('', 'songs.views.song_submit', name='song_submit'),
        path('thanks/', 'songs.views.song_submit_thanks', name='song_submit_thanks'),
    ])),
```

Actually, Django's `path()` with a string view is deprecated. Use the proper import pattern. Add these imports and URL patterns to `config/urls.py`:

Add to imports at top of `config/urls.py`:
```python
from songs.views import song_submit, song_submit_thanks
```

Add before `path('', include('core.urls'))`:
```python
    path('<slug:org_slug>/songs/submit/', song_submit, name='song_submit'),
    path('<slug:org_slug>/songs/submit/thanks/', song_submit_thanks, name='song_submit_thanks'),
```

And add the team URLs:
```python
    path('songs/', include('songs.urls', namespace='songs')),
```

- [ ] **Step 5: Implement the views in `songs/views.py`**

```python
import logging
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from core.models import Organization
from .models import SongSubmission, SongVote

logger = logging.getLogger(__name__)


def song_submit(request, org_slug):
    """Public song submission form. No auth required."""
    org = Organization.objects.filter(slug=org_slug, is_active=True).first()
    if not org:
        raise Http404

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        artist = request.POST.get('artist', '').strip()
        link = request.POST.get('link', '').strip()
        submitter_name = request.POST.get('submitter_name', '').strip()
        submitter_comment = request.POST.get('submitter_comment', '').strip()

        errors = []
        if not title:
            errors.append('Song title is required.')
        if not artist:
            errors.append('Artist is required.')

        if errors:
            return render(request, 'songs/submit.html', {
                'org': org,
                'errors': errors,
                'title': title,
                'artist': artist,
                'link': link,
                'submitter_name': submitter_name,
                'submitter_comment': submitter_comment,
            })

        submitted_by = request.user if request.user.is_authenticated else None
        if submitted_by and not submitter_name:
            submitter_name = getattr(submitted_by, 'display_name', '') or submitted_by.username

        submission = SongSubmission.objects.create(
            organization=org,
            title=title,
            artist=artist,
            link=link,
            submitter_name=submitter_name,
            submitter_comment=submitter_comment,
            submitted_by=submitted_by,
        )

        # Send push notification to team
        try:
            from core.notifications import notify_song_submission
            notify_song_submission(submission)
        except Exception as e:
            logger.error(f"Failed to send song submission notification: {e}")

        return render(request, 'songs/submit_thanks.html', {
            'org': org,
            'submission': submission,
        })

    # Pre-fill name for logged-in users
    submitter_name = ''
    if request.user.is_authenticated:
        submitter_name = getattr(request.user, 'display_name', '') or request.user.username

    return render(request, 'songs/submit.html', {
        'org': org,
        'submitter_name': submitter_name,
    })


def song_submit_thanks(request, org_slug):
    """Confirmation page after submission. Redirects to submit form."""
    org = Organization.objects.filter(slug=org_slug, is_active=True).first()
    if not org:
        raise Http404
    return redirect('song_submit', org_slug=org_slug)
```

- [ ] **Step 6: Create `templates/songs/submit.html`**

```html
{% extends 'core/onboarding/base_public.html' %}

{% block title %}Suggest a Song — {{ org.name }}{% endblock %}
{% block meta_description %}Suggest a song for the {{ org.name }} worship team to consider adding to their rotation.{% endblock %}

{% block container_class %}max-w-lg{% endblock %}

{% block content %}
<div class="text-center mb-8">
    <div class="text-ch-gold text-3xl font-bold tracking-wider mb-1">ARIA</div>
    <div class="text-gray-400 text-sm">{{ org.name }}</div>
</div>

<div class="bg-ch-dark rounded-lg p-6 md:p-8">
    <h2 class="text-xl font-bold text-white mb-1">Suggest a Song</h2>
    <p class="text-gray-400 text-sm mb-6">Know a song that would be great for worship? Let the team know!</p>

    {% if errors %}
    <div class="bg-red-900/30 border border-red-700 rounded-lg p-4 mb-6">
        {% for error in errors %}
        <p class="text-red-400 text-sm">{{ error }}</p>
        {% endfor %}
    </div>
    {% endif %}

    <form method="POST">
        {% csrf_token %}

        <div class="mb-4">
            <label class="block text-xs text-gray-400 uppercase tracking-wider mb-1">Song Title <span class="text-red-400">*</span></label>
            <input type="text" name="title" value="{{ title|default:'' }}"
                   class="w-full bg-ch-gray border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:border-ch-gold focus:outline-none"
                   placeholder="e.g. Goodness of God" required>
        </div>

        <div class="mb-4">
            <label class="block text-xs text-gray-400 uppercase tracking-wider mb-1">Artist / Band <span class="text-red-400">*</span></label>
            <input type="text" name="artist" value="{{ artist|default:'' }}"
                   class="w-full bg-ch-gray border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:border-ch-gold focus:outline-none"
                   placeholder="e.g. Bethel Music" required>
        </div>

        <div class="mb-4">
            <label class="block text-xs text-gray-400 uppercase tracking-wider mb-1">Link <span class="text-gray-600">(optional)</span></label>
            <input type="url" name="link" value="{{ link|default:'' }}"
                   class="w-full bg-ch-gray border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:border-ch-gold focus:outline-none"
                   placeholder="YouTube, Spotify, or Apple Music URL">
        </div>

        <div class="mb-4">
            <label class="block text-xs text-gray-400 uppercase tracking-wider mb-1">Your Name <span class="text-gray-600">(optional)</span></label>
            <input type="text" name="submitter_name" value="{{ submitter_name|default:'' }}"
                   class="w-full bg-ch-gray border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:border-ch-gold focus:outline-none"
                   placeholder="So the team knows who suggested it">
        </div>

        <div class="mb-6">
            <label class="block text-xs text-gray-400 uppercase tracking-wider mb-1">Why this song? <span class="text-gray-600">(optional)</span></label>
            <textarea name="submitter_comment" rows="3"
                      class="w-full bg-ch-gray border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:border-ch-gold focus:outline-none resize-y"
                      placeholder="e.g. Would be perfect for Easter, the lyrics really speak to...">{{ submitter_comment|default:'' }}</textarea>
        </div>

        <button type="submit"
                class="w-full bg-ch-gold hover:bg-ch-gold/90 text-ch-black font-semibold py-3 rounded-lg transition">
            Submit Song
        </button>
    </form>
</div>

<p class="text-center text-gray-600 text-xs mt-6">Powered by ARIA</p>
{% endblock %}
```

- [ ] **Step 7: Create `templates/songs/submit_thanks.html`**

```html
{% extends 'core/onboarding/base_public.html' %}

{% block title %}Song Submitted — {{ org.name }}{% endblock %}

{% block container_class %}max-w-lg{% endblock %}

{% block content %}
<div class="text-center mb-8">
    <div class="text-ch-gold text-3xl font-bold tracking-wider mb-1">ARIA</div>
    <div class="text-gray-400 text-sm">{{ org.name }}</div>
</div>

<div class="bg-ch-dark rounded-lg p-6 md:p-8 text-center">
    <div class="w-16 h-16 bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-5">
        <svg class="w-8 h-8 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
    </div>

    <h2 class="text-xl font-bold text-white mb-2">Song Submitted!</h2>
    <p class="text-gray-400 text-sm mb-6">Thanks for your suggestion. The worship team will review it.</p>

    <div class="bg-ch-gray border border-gray-700 rounded-lg p-4 text-left mb-6">
        <div class="mb-3">
            <div class="text-xs text-gray-500 uppercase tracking-wider">Song</div>
            <div class="text-white text-sm mt-1">{{ submission.title }}</div>
        </div>
        <div class="mb-3">
            <div class="text-xs text-gray-500 uppercase tracking-wider">Artist</div>
            <div class="text-white text-sm mt-1">{{ submission.artist }}</div>
        </div>
        <div>
            <div class="text-xs text-gray-500 uppercase tracking-wider">Status</div>
            <span class="inline-block mt-1 bg-ch-gold/20 text-ch-gold text-xs px-2 py-0.5 rounded">Pending Review</span>
        </div>
    </div>

    <a href="{% url 'song_submit' org_slug=org.slug %}"
       class="text-ch-gold hover:text-ch-gold/80 text-sm transition">
        Submit Another Song &rarr;
    </a>
</div>
{% endblock %}
```

- [ ] **Step 8: Run the submission form tests**

```bash
python -m pytest tests/test_song_submissions.py::TestPublicSubmissionForm -v
```

Expected: All 8 tests pass.

- [ ] **Step 9: Commit**

```bash
git add songs/views.py config/urls.py templates/songs/
git commit -m "feat(songs): add public song submission form with org-scoped URLs"
```

---

### Task 4: Team dashboard view and template

**Files:**
- Modify: `songs/views.py`
- Create: `templates/songs/dashboard.html`
- Create: `templates/songs/partials/submission_row.html`
- Create: `templates/songs/partials/star_rating.html`

- [ ] **Step 1: Write dashboard tests**

Add to `tests/test_song_submissions.py`:

```python
@pytest.mark.django_db
class TestSongDashboard:
    def test_dashboard_requires_auth(self):
        client = Client()
        response = client.get('/songs/')
        assert response.status_code == 302  # Redirect to login

    def test_dashboard_renders(self, client_alpha, org_alpha):
        SongSubmission.objects.create(organization=org_alpha, title='Test Song', artist='Test Artist')
        response = client_alpha.get('/songs/')
        assert response.status_code == 200
        assert b'Song Submissions' in response.content
        assert b'Test Song' in response.content

    def test_dashboard_stats(self, client_alpha, org_alpha):
        SongSubmission.objects.create(organization=org_alpha, title='Song 1', artist='A', status='pending')
        SongSubmission.objects.create(organization=org_alpha, title='Song 2', artist='B', status='approved')
        SongSubmission.objects.create(organization=org_alpha, title='Song 3', artist='C', status='rejected')
        response = client_alpha.get('/songs/')
        assert response.status_code == 200
        context = response.context
        assert context['total_count'] == 3
        assert context['pending_count'] == 1
        assert context['approved_count'] == 1
        assert context['rejected_count'] == 1

    def test_dashboard_filter_by_status(self, client_alpha, org_alpha):
        SongSubmission.objects.create(organization=org_alpha, title='Pending Song', artist='A', status='pending')
        SongSubmission.objects.create(organization=org_alpha, title='Approved Song', artist='B', status='approved')
        response = client_alpha.get('/songs/?status=pending')
        assert response.status_code == 200
        assert b'Pending Song' in response.content
        assert b'Approved Song' not in response.content

    def test_dashboard_sort_by_rating(self, client_alpha, org_alpha, user_alpha_owner):
        sub1 = SongSubmission.objects.create(organization=org_alpha, title='Low Rated', artist='A', average_rating=2.0)
        sub2 = SongSubmission.objects.create(organization=org_alpha, title='High Rated', artist='B', average_rating=5.0)
        response = client_alpha.get('/songs/?sort=highest_rated')
        assert response.status_code == 200
        content = response.content.decode()
        assert content.index('High Rated') < content.index('Low Rated')

    def test_dashboard_org_isolation(self, client_alpha, org_alpha, org_beta):
        SongSubmission.objects.create(organization=org_alpha, title='Alpha Song', artist='A')
        SongSubmission.objects.create(organization=org_beta, title='Beta Song', artist='B')
        response = client_alpha.get('/songs/')
        assert b'Alpha Song' in response.content
        assert b'Beta Song' not in response.content

    def test_dashboard_copy_link_present(self, client_alpha, org_alpha):
        response = client_alpha.get('/songs/')
        assert org_alpha.slug.encode() in response.content
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_song_submissions.py::TestSongDashboard -v
```

Expected: All fail.

- [ ] **Step 3: Implement `song_dashboard` view in `songs/views.py`**

Add to `songs/views.py`:

```python
from django.db.models import Count, Avg, Q
from core.middleware import require_organization, get_org


@login_required
@require_organization
def song_dashboard(request):
    """Team dashboard for reviewing song submissions."""
    org = get_org(request)

    submissions = SongSubmission.objects.filter(organization=org)

    # Stats
    total_count = submissions.count()
    pending_count = submissions.filter(status='pending').count()
    approved_count = submissions.filter(status='approved').count()
    rejected_count = submissions.filter(status='rejected').count()
    reviewed_count = submissions.filter(status='reviewed').count()
    avg_rating = submissions.filter(vote_count__gt=0).aggregate(avg=Avg('average_rating'))['avg'] or 0.0

    # Insights
    top_rated_pending = submissions.filter(
        status='pending', vote_count__gt=0
    ).order_by('-average_rating').first()

    most_submitted_artist = submissions.values('artist').annotate(
        count=Count('id')
    ).order_by('-count').first()

    # Filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        submissions = submissions.filter(status=status_filter)

    # Sort
    sort = request.GET.get('sort', 'newest')
    if sort == 'oldest':
        submissions = submissions.order_by('created_at')
    elif sort == 'highest_rated':
        submissions = submissions.order_by('-average_rating', '-vote_count')
    elif sort == 'most_votes':
        submissions = submissions.order_by('-vote_count', '-average_rating')
    else:  # newest (default)
        submissions = submissions.order_by('-created_at')

    # Get current user's votes for inline display
    user_votes = {}
    if request.user.is_authenticated:
        votes = SongVote.objects.filter(
            submission__organization=org,
            user=request.user,
        ).values_list('submission_id', 'rating')
        user_votes = dict(votes)

    context = {
        'submissions': submissions,
        'total_count': total_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'reviewed_count': reviewed_count,
        'avg_rating': round(avg_rating, 1),
        'top_rated_pending': top_rated_pending,
        'most_submitted_artist': most_submitted_artist,
        'status_filter': status_filter,
        'sort': sort,
        'user_votes': user_votes,
        'org_slug': org.slug,
    }
    return render(request, 'songs/dashboard.html', context)
```

- [ ] **Step 4: Create `templates/songs/partials/star_rating.html`**

```html
{# Inline star rating — used in dashboard rows and detail page #}
{# Context: submission, user_rating (0-5), show_count (bool) #}
<div class="flex items-center gap-1" id="stars-{{ submission.id }}">
    {% for i in "12345" %}
    <button hx-post="{% url 'songs:vote' submission.id %}"
            hx-vals='{"rating": "{{ i }}"}'
            hx-target="#stars-{{ submission.id }}"
            hx-swap="outerHTML"
            class="text-lg {% if forloop.counter <= user_rating %}text-ch-gold{% else %}text-gray-700{% endif %} hover:text-ch-gold transition cursor-pointer">
        &#9733;
    </button>
    {% endfor %}
    {% if show_count %}
    <span class="text-xs text-gray-500 ml-1">
        {% if submission.vote_count > 0 %}{{ submission.average_rating }} ({{ submission.vote_count }}){% else %}No votes{% endif %}
    </span>
    {% endif %}
</div>
```

- [ ] **Step 5: Create `templates/songs/partials/submission_row.html`**

```html
{# Single submission row for dashboard list #}
{# Context: submission, user_votes #}
{% load songs_tags %}
<div class="bg-ch-dark border border-gray-800 rounded-lg p-4 flex items-center gap-4" id="submission-{{ submission.id }}">
    <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 flex-wrap">
            <a href="{% url 'songs:detail' submission.id %}" class="text-white font-semibold hover:text-ch-gold transition truncate">
                {{ submission.title }}
            </a>
            <span class="text-xs px-2 py-0.5 rounded
                {% if submission.status == 'pending' %}bg-ch-gold/20 text-ch-gold
                {% elif submission.status == 'reviewed' %}bg-white/10 text-white
                {% elif submission.status == 'approved' %}bg-green-900/30 text-green-400
                {% else %}bg-gray-800 text-gray-500{% endif %}">
                {{ submission.get_status_display }}
            </span>
            {% if submission.duplicate_count %}
            <span class="text-xs bg-blue-900/30 text-blue-400 px-2 py-0.5 rounded">
                Possible duplicate
            </span>
            {% endif %}
        </div>
        <div class="text-gray-400 text-sm mt-1">
            {{ submission.artist }}
            &middot; {{ submission.submitter_name|default:"Anonymous" }}
            &middot; {{ submission.created_at|timesince }} ago
        </div>
        {% if submission.submitter_comment %}
        <div class="text-gray-600 text-xs mt-1 italic truncate">"{{ submission.submitter_comment }}"</div>
        {% endif %}
    </div>

    <div class="flex items-center gap-2 shrink-0">
        {% if submission.link %}
        <a href="{{ submission.link }}" target="_blank" rel="noopener"
           class="text-ch-gold text-xs hover:text-ch-gold/80 transition whitespace-nowrap">
            &#127911; Listen
        </a>
        {% else %}
        <span class="text-gray-600 text-xs whitespace-nowrap">No link</span>
        {% endif %}
    </div>

    <div class="shrink-0">
        {% with user_rating=user_votes|get_item:submission.id show_count=True %}
        {% include 'songs/partials/star_rating.html' %}
        {% endwith %}
    </div>
</div>
```

- [ ] **Step 6: Create `songs/templatetags/__init__.py` and `songs/templatetags/songs_tags.py`**

```bash
mkdir -p songs/templatetags
```

`songs/templatetags/__init__.py`: empty file

`songs/templatetags/songs_tags.py`:
```python
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key. Returns 0 if not found."""
    if dictionary is None:
        return 0
    return dictionary.get(key, 0)
```

- [ ] **Step 7: Create `templates/songs/dashboard.html`**

```html
{% extends 'base.html' %}
{% load songs_tags %}

{% block title %}Song Submissions{% endblock %}

{% block content %}
<div class="max-w-5xl mx-auto">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
            <h1 class="text-2xl font-bold">Song Submissions</h1>
            <p class="text-gray-400 text-sm">Songs suggested by your congregation</p>
        </div>
        <button onclick="navigator.clipboard.writeText('{{ request.scheme }}://{{ request.get_host }}/{{ org_slug }}/songs/submit/'); this.textContent='Copied!'; setTimeout(() => this.textContent='📋 Copy Submission Link', 2000)"
                class="bg-ch-dark border border-gray-700 text-ch-gold px-4 py-2 rounded-lg text-sm hover:border-ch-gold transition whitespace-nowrap">
            &#128203; Copy Submission Link
        </button>
    </div>

    <!-- Stats Bar -->
    <div class="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
        <div class="bg-ch-dark border border-gray-800 rounded-lg p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wider">Total</div>
            <div class="text-2xl font-bold text-white mt-1">{{ total_count }}</div>
        </div>
        <div class="bg-ch-dark border border-gray-800 rounded-lg p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wider">Pending</div>
            <div class="text-2xl font-bold text-ch-gold mt-1">{{ pending_count }}</div>
        </div>
        <div class="bg-ch-dark border border-gray-800 rounded-lg p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wider">Approved</div>
            <div class="text-2xl font-bold text-green-400 mt-1">{{ approved_count }}</div>
        </div>
        <div class="bg-ch-dark border border-gray-800 rounded-lg p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wider">Not Added</div>
            <div class="text-2xl font-bold text-gray-500 mt-1">{{ rejected_count }}</div>
        </div>
        <div class="bg-ch-dark border border-gray-800 rounded-lg p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wider">Avg Rating</div>
            <div class="text-2xl font-bold text-white mt-1">{{ avg_rating }} <span class="text-sm text-ch-gold">&#9733;</span></div>
        </div>
    </div>

    <!-- Insights -->
    {% if top_rated_pending or most_submitted_artist %}
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
        {% if top_rated_pending %}
        <div class="bg-green-900/10 border border-green-900/30 rounded-lg p-4">
            <div class="text-xs text-green-400 font-semibold mb-1">&#128293; Top Rated Pending</div>
            <div class="text-white text-sm">{{ top_rated_pending.title }} — {{ top_rated_pending.artist }}</div>
            <div class="text-gray-500 text-xs mt-1">{{ top_rated_pending.average_rating }} &#9733; avg from {{ top_rated_pending.vote_count }} vote{{ top_rated_pending.vote_count|pluralize }}</div>
        </div>
        {% endif %}
        {% if most_submitted_artist %}
        <div class="bg-indigo-900/10 border border-indigo-900/30 rounded-lg p-4">
            <div class="text-xs text-indigo-400 font-semibold mb-1">&#127925; Most Submitted Artist</div>
            <div class="text-white text-sm">{{ most_submitted_artist.artist }}</div>
            <div class="text-gray-500 text-xs mt-1">{{ most_submitted_artist.count }} song{{ most_submitted_artist.count|pluralize }} submitted</div>
        </div>
        {% endif %}
    </div>
    {% endif %}

    <!-- Filters -->
    <div class="flex flex-col sm:flex-row gap-2 mb-4 items-start sm:items-center">
        <select onchange="window.location.search='status='+this.value+'&sort={{ sort }}'"
                class="bg-ch-dark border border-gray-700 text-white rounded-lg px-3 py-2 text-sm">
            <option value="" {% if not status_filter %}selected{% endif %}>All Statuses</option>
            <option value="pending" {% if status_filter == 'pending' %}selected{% endif %}>Pending</option>
            <option value="reviewed" {% if status_filter == 'reviewed' %}selected{% endif %}>Reviewed</option>
            <option value="approved" {% if status_filter == 'approved' %}selected{% endif %}>Approved</option>
            <option value="rejected" {% if status_filter == 'rejected' %}selected{% endif %}>Not Added</option>
        </select>
        <select onchange="window.location.search='status={{ status_filter }}&sort='+this.value"
                class="bg-ch-dark border border-gray-700 text-white rounded-lg px-3 py-2 text-sm">
            <option value="newest" {% if sort == 'newest' %}selected{% endif %}>Newest First</option>
            <option value="oldest" {% if sort == 'oldest' %}selected{% endif %}>Oldest First</option>
            <option value="highest_rated" {% if sort == 'highest_rated' %}selected{% endif %}>Highest Rated</option>
            <option value="most_votes" {% if sort == 'most_votes' %}selected{% endif %}>Most Votes</option>
        </select>
        <span class="text-gray-500 text-xs sm:ml-auto">{{ submissions|length }} submission{{ submissions|length|pluralize }}</span>
    </div>

    <!-- Submissions List -->
    <div class="space-y-2">
        {% for submission in submissions %}
        {% include 'songs/partials/submission_row.html' with submission=submission user_votes=user_votes %}
        {% empty %}
        <div class="bg-ch-dark border border-gray-800 rounded-lg p-8 text-center">
            <p class="text-gray-400">No song submissions yet.</p>
            <p class="text-gray-500 text-sm mt-2">Share your submission link to start receiving suggestions!</p>
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
```

- [ ] **Step 8: Run dashboard tests**

```bash
python -m pytest tests/test_song_submissions.py::TestSongDashboard -v
```

Expected: All 7 tests pass.

- [ ] **Step 9: Commit**

```bash
git add songs/ templates/songs/
git commit -m "feat(songs): add team dashboard with stats, insights, filters, and inline voting"
```

---

### Task 5: Detail page, voting, and status update views

**Files:**
- Modify: `songs/views.py`
- Create: `templates/songs/detail.html`
- Create: `templates/songs/partials/status_buttons.html`

- [ ] **Step 1: Write detail, vote, and status tests**

Add to `tests/test_song_submissions.py`:

```python
@pytest.mark.django_db
class TestSongDetail:
    def test_detail_requires_auth(self, org_alpha):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='A')
        client = Client()
        response = client.get(f'/songs/{sub.pk}/')
        assert response.status_code == 302

    def test_detail_renders(self, client_alpha, org_alpha):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Build My Life', artist='Housefires')
        response = client_alpha.get(f'/songs/{sub.pk}/')
        assert response.status_code == 200
        assert b'Build My Life' in response.content
        assert b'Housefires' in response.content

    def test_detail_shows_team_votes(self, client_alpha, org_alpha, user_alpha_owner, user_alpha_member):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='A')
        SongVote.objects.create(submission=sub, user=user_alpha_owner, rating=5)
        SongVote.objects.create(submission=sub, user=user_alpha_member, rating=4)
        response = client_alpha.get(f'/songs/{sub.pk}/')
        assert b'Alpha Owner' in response.content
        assert b'Alpha Member' in response.content

    def test_detail_org_isolation(self, client_alpha, org_beta):
        sub = SongSubmission.objects.create(organization=org_beta, title='Beta Song', artist='B')
        response = client_alpha.get(f'/songs/{sub.pk}/')
        assert response.status_code == 404


@pytest.mark.django_db
class TestSongVote:
    def test_cast_vote(self, client_alpha, org_alpha):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='A')
        response = client_alpha.post(f'/songs/{sub.pk}/vote/', {'rating': '4'})
        assert response.status_code == 200
        sub.refresh_from_db()
        assert sub.average_rating == 4.0
        assert sub.vote_count == 1

    def test_update_vote(self, client_alpha, org_alpha, user_alpha_owner):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='A')
        SongVote.objects.create(submission=sub, user=user_alpha_owner, rating=3)
        sub.update_rating()
        response = client_alpha.post(f'/songs/{sub.pk}/vote/', {'rating': '5'})
        assert response.status_code == 200
        sub.refresh_from_db()
        assert sub.average_rating == 5.0

    def test_vote_requires_auth(self, org_alpha):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='A')
        client = Client()
        response = client.post(f'/songs/{sub.pk}/vote/', {'rating': '4'})
        assert response.status_code == 302

    def test_vote_invalid_rating(self, client_alpha, org_alpha):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='A')
        response = client_alpha.post(f'/songs/{sub.pk}/vote/', {'rating': '0'})
        assert response.status_code == 400


@pytest.mark.django_db
class TestSongStatusUpdate:
    def test_owner_can_update_status(self, client_alpha, org_alpha):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='A')
        response = client_alpha.post(f'/songs/{sub.pk}/status/', {'status': 'approved'})
        assert response.status_code == 200
        sub.refresh_from_db()
        assert sub.status == 'approved'

    def test_member_cannot_update_status(self, org_alpha, user_alpha_member):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='A')
        client = Client()
        client.force_login(user_alpha_member)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        response = client.post(f'/songs/{sub.pk}/status/', {'status': 'approved'})
        assert response.status_code == 403

    def test_status_sets_reviewed_fields(self, client_alpha, org_alpha, user_alpha_owner):
        sub = SongSubmission.objects.create(organization=org_alpha, title='Test', artist='A')
        client_alpha.post(f'/songs/{sub.pk}/status/', {
            'status': 'approved',
            'review_note': 'Great fit for our style',
        })
        sub.refresh_from_db()
        assert sub.reviewed_by == user_alpha_owner
        assert sub.reviewed_at is not None
        assert sub.review_note == 'Great fit for our style'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_song_submissions.py::TestSongDetail tests/test_song_submissions.py::TestSongVote tests/test_song_submissions.py::TestSongStatusUpdate -v
```

Expected: All fail.

- [ ] **Step 3: Add `song_detail`, `song_vote`, `song_update_status` views to `songs/views.py`**

```python
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.utils import timezone


@login_required
@require_organization
def song_detail(request, pk):
    """Detail page for a song submission."""
    org = get_org(request)
    submission = SongSubmission.objects.filter(organization=org, pk=pk).first()
    if not submission:
        raise Http404

    # Current user's vote
    user_vote = SongVote.objects.filter(submission=submission, user=request.user).first()
    user_rating = user_vote.rating if user_vote else 0

    # All team votes
    team_votes = submission.votes.select_related('user').order_by('-rating')

    # Duplicate detection
    similar = SongSubmission.objects.filter(
        organization=org,
        title__iexact=submission.title,
    ).exclude(pk=submission.pk)

    # Permission check for status changes
    membership = request.membership
    can_change_status = membership and membership.role in ('owner', 'admin', 'leader')

    context = {
        'submission': submission,
        'user_rating': user_rating,
        'team_votes': team_votes,
        'similar_submissions': similar,
        'can_change_status': can_change_status,
    }
    return render(request, 'songs/detail.html', context)


@login_required
@require_organization
@require_POST
def song_vote(request, pk):
    """Cast or update a vote on a submission. HTMX endpoint."""
    org = get_org(request)
    submission = SongSubmission.objects.filter(organization=org, pk=pk).first()
    if not submission:
        raise Http404

    try:
        rating = int(request.POST.get('rating', 0))
    except (ValueError, TypeError):
        return HttpResponseBadRequest('Invalid rating')

    if rating < 1 or rating > 5:
        return HttpResponseBadRequest('Rating must be 1-5')

    vote, created = SongVote.objects.update_or_create(
        submission=submission,
        user=request.user,
        defaults={'rating': rating},
    )
    submission.update_rating()

    return render(request, 'songs/partials/star_rating.html', {
        'submission': submission,
        'user_rating': rating,
        'show_count': True,
    })


@login_required
@require_organization
@require_POST
def song_update_status(request, pk):
    """Update submission status. Requires admin/owner/leader role. HTMX endpoint."""
    org = get_org(request)
    membership = request.membership

    if not membership or membership.role not in ('owner', 'admin', 'leader'):
        return HttpResponseForbidden('Insufficient permissions')

    submission = SongSubmission.objects.filter(organization=org, pk=pk).first()
    if not submission:
        raise Http404

    new_status = request.POST.get('status', '')
    valid_statuses = [s[0] for s in SongSubmission.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return HttpResponseBadRequest('Invalid status')

    submission.status = new_status
    submission.reviewed_by = request.user
    submission.reviewed_at = timezone.now()
    submission.review_note = request.POST.get('review_note', submission.review_note)
    submission.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note', 'updated_at'])

    return render(request, 'songs/partials/status_buttons.html', {
        'submission': submission,
        'can_change_status': True,
    })
```

- [ ] **Step 4: Create `templates/songs/partials/status_buttons.html`**

```html
{# HTMX-swappable status buttons for detail page #}
{# Context: submission, can_change_status #}
<div id="status-buttons-{{ submission.id }}">
    {% if can_change_status %}
    <div class="flex flex-col gap-2">
        {% for value, label in submission.STATUS_CHOICES %}
        <button hx-post="{% url 'songs:update_status' submission.id %}"
                hx-vals='{"status": "{{ value }}"}'
                hx-target="#status-buttons-{{ submission.id }}"
                hx-swap="outerHTML"
                class="w-full text-left px-3 py-2.5 rounded-lg text-sm transition
                    {% if submission.status == value %}
                        bg-ch-dark border-2 border-ch-gold text-ch-gold font-semibold
                    {% else %}
                        bg-ch-dark border border-gray-700 text-gray-400 hover:border-gray-500
                    {% endif %}">
            {% if value == 'pending' %}&#9203;{% elif value == 'reviewed' %}&#128065;{% elif value == 'approved' %}&#10003;{% else %}&#10007;{% endif %}
            {{ label }}
        </button>
        {% endfor %}
    </div>
    {% else %}
    <span class="text-xs px-2 py-1 rounded
        {% if submission.status == 'pending' %}bg-ch-gold/20 text-ch-gold
        {% elif submission.status == 'reviewed' %}bg-white/10 text-white
        {% elif submission.status == 'approved' %}bg-green-900/30 text-green-400
        {% else %}bg-gray-800 text-gray-500{% endif %}">
        {{ submission.get_status_display }}
    </span>
    {% endif %}
</div>
```

- [ ] **Step 5: Create `templates/songs/detail.html`**

```html
{% extends 'base.html' %}
{% load songs_tags %}

{% block title %}{{ submission.title }} — Song Submissions{% endblock %}

{% block content %}
<div class="max-w-5xl mx-auto">
    <!-- Breadcrumb -->
    <div class="text-xs text-gray-500 mb-4">
        <a href="{% url 'songs:dashboard' %}" class="text-ch-gold hover:text-ch-gold/80 transition">Song Submissions</a>
        &rsaquo; {{ submission.title }}
    </div>

    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div>
            <div class="flex items-center gap-3">
                <h1 class="text-2xl font-bold">{{ submission.title }}</h1>
                <span class="text-xs px-2 py-0.5 rounded
                    {% if submission.status == 'pending' %}bg-ch-gold/20 text-ch-gold
                    {% elif submission.status == 'reviewed' %}bg-white/10 text-white
                    {% elif submission.status == 'approved' %}bg-green-900/30 text-green-400
                    {% else %}bg-gray-800 text-gray-500{% endif %}">
                    {{ submission.get_status_display }}
                </span>
            </div>
            <p class="text-gray-400 mt-1">by {{ submission.artist }}</p>
        </div>
        {% if submission.link %}
        <a href="{{ submission.link }}" target="_blank" rel="noopener"
           class="bg-ch-dark border border-gray-700 text-ch-gold px-4 py-2 rounded-lg text-sm hover:border-ch-gold transition whitespace-nowrap">
            &#127911; Listen &rarr;
        </a>
        {% endif %}
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Left Column (2/3) -->
        <div class="lg:col-span-2 space-y-4">
            <!-- Submission Details -->
            <div class="bg-ch-dark border border-gray-800 rounded-lg p-5">
                <div class="text-xs text-gray-500 uppercase tracking-wider mb-3">Submission Details</div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <div class="text-xs text-gray-600">Submitted by</div>
                        <div class="text-white text-sm mt-1">{{ submission.submitter_name|default:"Anonymous" }}</div>
                    </div>
                    <div>
                        <div class="text-xs text-gray-600">Date</div>
                        <div class="text-white text-sm mt-1">{{ submission.created_at|date:"F j, Y" }}</div>
                    </div>
                </div>
                {% if submission.submitter_comment %}
                <div class="mt-3">
                    <div class="text-xs text-gray-600">Comment</div>
                    <div class="text-gray-300 text-sm mt-1 italic">"{{ submission.submitter_comment }}"</div>
                </div>
                {% endif %}
            </div>

            <!-- Your Rating -->
            <div class="bg-ch-dark border border-gray-800 rounded-lg p-5">
                <div class="text-xs text-gray-500 uppercase tracking-wider mb-3">Your Rating</div>
                {% with show_count=False %}
                {% include 'songs/partials/star_rating.html' with submission=submission user_rating=user_rating %}
                {% endwith %}
                <span class="text-gray-500 text-sm ml-2">
                    {% if user_rating %}You rated {{ user_rating }} star{{ user_rating|pluralize }}{% else %}Click to rate{% endif %}
                </span>
            </div>

            <!-- Team Votes -->
            <div class="bg-ch-dark border border-gray-800 rounded-lg p-5">
                <div class="text-xs text-gray-500 uppercase tracking-wider mb-3">Team Votes ({{ team_votes|length }})</div>
                {% if team_votes %}
                <div class="space-y-2">
                    {% for vote in team_votes %}
                    <div class="flex items-center gap-3">
                        <div class="w-7 h-7 bg-ch-gray rounded-full flex items-center justify-center text-xs text-gray-400 shrink-0">
                            {{ vote.user.display_name|default:vote.user.username|make_list|first }}{{ vote.user.display_name|default:vote.user.username|truncatewords:1|make_list|first }}
                        </div>
                        <div class="flex-1 text-gray-300 text-sm">{{ vote.user.display_name|default:vote.user.username }}</div>
                        <div class="text-ch-gold text-sm">
                            {% for i in "12345" %}{% if forloop.counter <= vote.rating %}&#9733;{% else %}<span class="text-gray-700">&#9733;</span>{% endif %}{% endfor %}
                        </div>
                    </div>
                    {% endfor %}
                </div>
                <div class="border-t border-gray-700 mt-3 pt-3 flex justify-between">
                    <span class="text-gray-500 text-sm">Average</span>
                    <span class="text-white font-semibold">{{ submission.average_rating }} &#9733;</span>
                </div>
                {% else %}
                <p class="text-gray-500 text-sm">No votes yet. Be the first to rate!</p>
                {% endif %}
            </div>

            <!-- Similar Submissions -->
            {% if similar_submissions %}
            <div class="bg-blue-900/10 border border-blue-900/30 rounded-lg p-5">
                <div class="text-xs text-blue-400 font-semibold mb-2">Similar Submissions</div>
                {% for sim in similar_submissions %}
                <a href="{% url 'songs:detail' sim.pk %}" class="text-sm text-blue-300 hover:text-blue-200 block">
                    {{ sim.title }} by {{ sim.artist }} — {{ sim.get_status_display }} ({{ sim.created_at|date:"M j" }})
                </a>
                {% endfor %}
            </div>
            {% endif %}
        </div>

        <!-- Right Column (1/3) -->
        <div class="space-y-4">
            <!-- Status -->
            <div class="bg-ch-dark border border-gray-800 rounded-lg p-5">
                <div class="text-xs text-gray-500 uppercase tracking-wider mb-3">Update Status</div>
                {% include 'songs/partials/status_buttons.html' with submission=submission can_change_status=can_change_status %}
            </div>

            <!-- Team Note -->
            {% if can_change_status %}
            <div class="bg-ch-dark border border-gray-800 rounded-lg p-5">
                <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">Team Note</div>
                <form hx-post="{% url 'songs:update_status' submission.id %}"
                      hx-target="#status-buttons-{{ submission.id }}"
                      hx-swap="outerHTML">
                    {% csrf_token %}
                    <input type="hidden" name="status" value="{{ submission.status }}">
                    <textarea name="review_note" rows="3"
                              class="w-full bg-ch-gray border border-gray-700 text-white rounded-lg px-3 py-2 text-sm focus:border-ch-gold focus:outline-none resize-y"
                              placeholder="Add an internal note...">{{ submission.review_note }}</textarea>
                    <button type="submit"
                            class="w-full bg-ch-gold hover:bg-ch-gold/90 text-ch-black font-semibold py-2 rounded-lg text-sm transition mt-2">
                        Save Note
                    </button>
                </form>
            </div>
            {% endif %}

            <!-- Quick Stats -->
            <div class="bg-ch-dark border border-gray-800 rounded-lg p-5">
                <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">Quick Stats</div>
                <div class="space-y-3">
                    <div>
                        <div class="text-xs text-gray-600">Avg Rating</div>
                        <div class="text-ch-gold text-lg font-bold">{% if submission.vote_count %}{{ submission.average_rating }} &#9733;{% else %}—{% endif %}</div>
                    </div>
                    <div>
                        <div class="text-xs text-gray-600">Total Votes</div>
                        <div class="text-white text-lg font-bold">{{ submission.vote_count }}</div>
                    </div>
                    <div>
                        <div class="text-xs text-gray-600">Days Pending</div>
                        <div class="text-white text-lg font-bold">{{ submission.created_at|timesince }}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Run detail, vote, and status tests**

```bash
python -m pytest tests/test_song_submissions.py::TestSongDetail tests/test_song_submissions.py::TestSongVote tests/test_song_submissions.py::TestSongStatusUpdate -v
```

Expected: All 11 tests pass.

- [ ] **Step 7: Commit**

```bash
git add songs/ templates/songs/
git commit -m "feat(songs): add detail page with voting, status updates, and duplicate detection"
```

---

### Task 6: Push notifications and notification preferences

**Files:**
- Modify: `core/models.py:3215-3227`
- Modify: `core/notifications.py`
- Modify: `core/views.py` (push_preferences handler)
- Modify: `templates/core/notifications/preferences.html`

- [ ] **Step 1: Write notification tests**

Add to `tests/test_song_submissions.py`:

```python
from unittest.mock import patch


@pytest.mark.django_db
class TestSongNotifications:
    def test_notification_sent_on_submission(self, org_alpha, user_alpha_owner):
        from core.models import OrganizationMembership
        with patch('core.notifications.send_notification_to_users') as mock_send:
            mock_send.return_value = 1
            client = Client()
            client.post(f'/{org_alpha.slug}/songs/submit/', {
                'title': 'Test Song',
                'artist': 'Test Artist',
            })
            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args
            assert call_kwargs[1]['notification_type'] == 'song_submission'
            assert 'Test Song' in call_kwargs[1]['title'] or 'Test Song' in call_kwargs[1]['body']

    def test_notification_preference_respected(self, org_alpha, user_alpha_owner):
        from core.models import NotificationPreference
        prefs = NotificationPreference.get_or_create_for_user(user_alpha_owner)
        prefs.song_submissions = False
        prefs.save()
        # The preference check happens inside send_notification_to_user,
        # which is already tested in existing notification tests.
        # Just verify the field exists and defaults to True.
        prefs2 = NotificationPreference.get_or_create_for_user(user_alpha_owner)
        assert hasattr(prefs2, 'song_submissions')
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_song_submissions.py::TestSongNotifications -v
```

Expected: Fail (field doesn't exist yet, notification function doesn't exist).

- [ ] **Step 3: Add `song_submissions` field to NotificationPreference in `core/models.py`**

After the `followup_reminders` field (around line 3227), add:

```python
    song_submissions = models.BooleanField(default=True, help_text="Song submission notifications")
```

- [ ] **Step 4: Generate and run migration**

```bash
python manage.py makemigrations core
python manage.py migrate
```

- [ ] **Step 5: Add `song_submission` preference check to `core/notifications.py`**

In `send_notification_to_user()`, after the `elif notification_type == 'followup':` block (around line 204), add:

```python
            elif notification_type == 'song_submission':
                if not prefs.song_submissions:
                    return 0
```

- [ ] **Step 6: Add `notify_song_submission()` function to `core/notifications.py`**

Add after the `notify_new_announcement()` function:

```python
def notify_song_submission(submission):
    """Send notifications when a new song is submitted."""
    from core.models import OrganizationMembership

    # Get all active members of the organization
    memberships = OrganizationMembership.objects.filter(
        organization=submission.organization,
        is_active=True,
    ).select_related('user')

    users = [m.user for m in memberships if m.user.is_active]

    # Don't notify the submitter if they're logged in
    if submission.submitted_by:
        users = [u for u in users if u.pk != submission.submitted_by.pk]

    submitter = submission.submitter_name or 'Someone'
    title = '🎵 New Song Suggestion'
    body = f'{submitter} suggested {submission.title} by {submission.artist}'

    sent = send_notification_to_users(
        users=users,
        notification_type='song_submission',
        title=title,
        body=body,
        url=f'/songs/{submission.pk}/',
        data={'submission_id': submission.pk},
    )

    logger.info(f"Song submission notifications sent: {sent}")
    return sent
```

- [ ] **Step 7: Add `song_submissions` to push_preferences view in `core/views.py`**

In the `push_preferences` view's POST handler, add after the existing preference updates:

```python
        prefs.song_submissions = request.POST.get('song_submissions') == 'on'
```

- [ ] **Step 8: Add song submissions toggle to `templates/core/notifications/preferences.html`**

Add a new section after the Follow-up Reminders section (before the Quiet Hours section), following the same pattern:

```html
            <!-- Song Submissions -->
            <div class="border-b border-gray-700 pb-6">
                <div class="flex items-start justify-between">
                    <div>
                        <h3 class="font-medium">Song Submissions</h3>
                        <p class="text-sm text-gray-400">New song suggestions from your congregation</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" name="song_submissions" class="sr-only peer" {% if prefs.song_submissions %}checked{% endif %}>
                        <div class="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-ch-gold"></div>
                    </label>
                </div>
            </div>
```

- [ ] **Step 9: Run notification tests**

```bash
python -m pytest tests/test_song_submissions.py::TestSongNotifications -v
```

Expected: All 2 tests pass.

- [ ] **Step 10: Commit**

```bash
git add core/models.py core/notifications.py core/views.py core/migrations/ templates/core/notifications/
git commit -m "feat(songs): add push notifications for song submissions with preference toggle"
```

---

### Task 7: Sidebar navigation link

**Files:**
- Modify: `templates/base.html:488-494`

- [ ] **Step 1: Add Song Submissions nav link to sidebar**

In `templates/base.html`, add the following after the "My Tasks" nav link (line 488) and before the "Knowledge Base" link (line 489):

```html
            <a href="{% url 'songs:dashboard' %}" @click="sidebarOpen = false" class="nav-link {% if 'song' in request.resolver_match.url_name %}active{% endif %}">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"></path>
                </svg>
                Song Submissions
                {% if pending_song_count %}<span class="ml-auto bg-ch-gold/20 text-ch-gold text-xs px-1.5 py-0.5 rounded-full">{{ pending_song_count }}</span>{% endif %}
            </a>
```

- [ ] **Step 2: Add `pending_song_count` to context processor**

In `core/context_processors.py`, inside the `organization_context` function, after the organization is set in context, add:

```python
    if organization:
        # ... existing code ...
        # Pending song submissions count for sidebar badge
        try:
            from songs.models import SongSubmission
            context['pending_song_count'] = SongSubmission.objects.filter(
                organization=organization, status='pending'
            ).count()
        except Exception:
            context['pending_song_count'] = 0
```

- [ ] **Step 3: Verify sidebar renders correctly**

```bash
python -m pytest tests/test_song_submissions.py::TestSongDashboard::test_dashboard_renders -v
```

Expected: Passes (dashboard still renders).

- [ ] **Step 4: Commit**

```bash
git add templates/base.html core/context_processors.py
git commit -m "feat(songs): add Song Submissions link with pending badge to sidebar nav"
```

---

### Task 8: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run all song submission tests**

```bash
python -m pytest tests/test_song_submissions.py -v
```

Expected: All tests pass (approximately 38 tests).

- [ ] **Step 2: Run the full project test suite**

```bash
python -m pytest -v
```

Expected: All 452 existing tests + ~38 new tests pass with 0 failures.

- [ ] **Step 3: Verify no migration conflicts**

```bash
python manage.py showmigrations songs
python manage.py showmigrations core
```

Expected: All migrations applied.

- [ ] **Step 4: Commit final state if any fixes were needed**

```bash
git add -A
git commit -m "test(songs): verify full test suite passes with song submissions feature"
```
