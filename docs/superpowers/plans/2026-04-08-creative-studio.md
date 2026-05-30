# Creative Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Creative Studio feature — a dedicated space for worship arts teams to share original creative work, collaborate through "build on this" chains, and have leaders spotlight standout work.

**Architecture:** New models appended to `core/models.py`, new views in a dedicated `core/studio_views.py` file (to avoid further bloating the 6789-line `views.py`), new templates in `templates/core/studio/`, URLs in `core/urls.py`. Follows existing multi-tenant patterns with org-scoped queries, HTMX partials, and push notifications.

**Tech Stack:** Django 5.x, HTMX, Tailwind CSS, OpenAI text-embedding-3-small (for related posts), existing push notification system.

**Spec:** `docs/superpowers/specs/2026-04-08-creative-studio-design.md`

---

### Task 1: Models — CreativeTag, CreativeCollection, CreativePost

**Files:**
- Modify: `core/models.py` (append after line 4494)
- Create: `tests/test_creative_studio.py`

- [ ] **Step 1: Write failing tests for CreativeTag model**

```python
# tests/test_creative_studio.py
import pytest
from core.models import CreativeTag


class TestCreativeTagModel:
    def test_create_tag(self, db, org_alpha):
        tag = CreativeTag.objects.create(
            name='worship',
            organization=org_alpha,
        )
        assert tag.name == 'worship'
        assert tag.slug == 'worship'
        assert str(tag) == 'worship'

    def test_tag_slug_auto_generated(self, db, org_alpha):
        tag = CreativeTag.objects.create(
            name='Stage Design',
            organization=org_alpha,
        )
        assert tag.slug == 'stage-design'

    def test_tag_unique_per_org(self, db, org_alpha, org_beta):
        CreativeTag.objects.create(name='easter', organization=org_alpha)
        CreativeTag.objects.create(name='easter', organization=org_beta)
        with pytest.raises(Exception):
            CreativeTag.objects.create(name='easter', organization=org_alpha)

    def test_tag_tenant_isolation(self, db, org_alpha, org_beta):
        CreativeTag.objects.create(name='worship', organization=org_alpha)
        CreativeTag.objects.create(name='tech', organization=org_beta)
        alpha_tags = CreativeTag.objects.filter(organization=org_alpha)
        assert alpha_tags.count() == 1
        assert alpha_tags.first().name == 'worship'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_creative_studio.py::TestCreativeTagModel -v`
Expected: FAIL with `ImportError: cannot import name 'CreativeTag'`

- [ ] **Step 3: Write failing tests for CreativeCollection model**

```python
# tests/test_creative_studio.py (append)
from core.models import CreativeCollection


class TestCreativeCollectionModel:
    def test_create_collection(self, db, org_alpha, user_alpha_owner):
        collection = CreativeCollection.objects.create(
            name='Easter 2026',
            description='Ideas for Easter service',
            organization=org_alpha,
            created_by=user_alpha_owner,
        )
        assert collection.name == 'Easter 2026'
        assert collection.is_archived is False
        assert str(collection) == 'Easter 2026'

    def test_collection_tenant_isolation(self, db, org_alpha, org_beta, user_alpha_owner, user_beta_owner):
        CreativeCollection.objects.create(name='Easter', organization=org_alpha, created_by=user_alpha_owner)
        CreativeCollection.objects.create(name='Easter', organization=org_beta, created_by=user_beta_owner)
        assert CreativeCollection.objects.filter(organization=org_alpha).count() == 1
```

- [ ] **Step 4: Write failing tests for CreativePost model**

```python
# tests/test_creative_studio.py (append)
from core.models import CreativePost


class TestCreativePostModel:
    def test_create_post(self, db, org_alpha, user_alpha_owner):
        post = CreativePost.objects.create(
            author=user_alpha_owner,
            organization=org_alpha,
            post_type='lyrics',
            title='Still Waters',
            content='In the quiet of the morning light...',
            status='published',
        )
        assert post.title == 'Still Waters'
        assert post.post_type == 'lyrics'
        assert post.is_collaborative is False
        assert post.is_spotlighted is False
        assert post.parent_post is None
        assert str(post) == 'Still Waters'

    def test_post_draft_vs_published(self, db, org_alpha, user_alpha_owner):
        draft = CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='Draft Idea', status='draft',
        )
        published = CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='Published Idea', status='published',
        )
        assert CreativePost.objects.filter(organization=org_alpha, status='published').count() == 1

    def test_build_on_chain(self, db, org_alpha, user_alpha_owner, user_alpha_member):
        parent = CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='lyrics', title='Original Song', status='published',
        )
        child = CreativePost.objects.create(
            author=user_alpha_member, organization=org_alpha,
            post_type='audio', title='Re: Original Song',
            status='published', parent_post=parent,
        )
        assert child.parent_post == parent
        assert parent.builds.count() == 1
        assert parent.builds.first() == child

    def test_post_with_collection_and_tags(self, db, org_alpha, user_alpha_owner):
        collection = CreativeCollection.objects.create(
            name='Easter 2026', organization=org_alpha, created_by=user_alpha_owner,
        )
        tag1 = CreativeTag.objects.create(name='worship', organization=org_alpha)
        tag2 = CreativeTag.objects.create(name='easter', organization=org_alpha)
        post = CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='lyrics', title='Easter Song', status='published',
            collection=collection,
        )
        post.tags.add(tag1, tag2)
        assert post.collection == collection
        assert post.tags.count() == 2

    def test_post_tenant_isolation(self, db, org_alpha, org_beta, user_alpha_owner, user_beta_owner):
        CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='Alpha Idea', status='published',
        )
        CreativePost.objects.create(
            author=user_beta_owner, organization=org_beta,
            post_type='idea', title='Beta Idea', status='published',
        )
        assert CreativePost.objects.filter(organization=org_alpha).count() == 1

    def test_spotlight(self, db, org_alpha, user_alpha_owner, user_alpha_member):
        post = CreativePost.objects.create(
            author=user_alpha_member, organization=org_alpha,
            post_type='poem', title='A Poem', status='published',
        )
        post.is_spotlighted = True
        post.spotlighted_by = user_alpha_owner
        post.spotlight_note = 'Beautiful imagery!'
        post.save()
        post.refresh_from_db()
        assert post.is_spotlighted is True
        assert post.spotlighted_by == user_alpha_owner
        assert post.spotlight_note == 'Beautiful imagery!'
```

- [ ] **Step 5: Implement all three models**

Append to `core/models.py` after line 4494:

```python
# =============================================================================
# Creative Studio Models
# =============================================================================


class CreativeTag(models.Model):
    """Lightweight tag for categorizing creative posts."""
    name = models.CharField(max_length=50)
    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, related_name='creative_tags'
    )
    slug = models.SlugField(max_length=60)

    class Meta:
        unique_together = [['name', 'organization']]
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class CreativeCollection(models.Model):
    """Themed grouping for creative posts (e.g., 'Easter 2026', 'Songwriting Circle')."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, related_name='creative_collections'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='created_collections'
    )
    cover_image = models.FileField(upload_to='studio/collections/', blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class CreativePost(models.Model):
    """A creative work shared in the studio — lyrics, artwork, audio, ideas, etc."""
    POST_TYPE_CHOICES = [
        ('lyrics', 'Lyrics'),
        ('poem', 'Poem'),
        ('artwork', 'Artwork'),
        ('audio', 'Audio'),
        ('video_concept', 'Video Concept'),
        ('stage_design', 'Stage Design'),
        ('idea', 'Idea'),
        ('devotional', 'Devotional'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('audio', 'Audio'),
        ('document', 'Document'),
        ('none', 'None'),
    ]

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='creative_posts'
    )
    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, related_name='creative_posts'
    )
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True, default='')
    media_file = models.FileField(upload_to='studio/posts/%Y/%m/', blank=True)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='none')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    is_collaborative = models.BooleanField(default=False)
    is_spotlighted = models.BooleanField(default=False)
    spotlighted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='spotlighted_posts'
    )
    spotlight_note = models.CharField(max_length=200, blank=True, default='')
    parent_post = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='builds'
    )
    tags = models.ManyToManyField('CreativeTag', blank=True, related_name='posts')
    collection = models.ForeignKey(
        'CreativeCollection', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='posts'
    )
    embedding_json = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status', '-created_at']),
            models.Index(fields=['organization', 'post_type']),
        ]

    def __str__(self):
        return self.title
```

- [ ] **Step 6: Run makemigrations and migrate**

Run: `python manage.py makemigrations core`
Expected: Creates migration with CreateModel for CreativeTag, CreativeCollection, CreativePost

Run: `python manage.py migrate`
Expected: Applied migration successfully

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_creative_studio.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add core/models.py core/migrations/ tests/test_creative_studio.py
git commit -m "feat(studio): add CreativeTag, CreativeCollection, CreativePost models"
```

---

### Task 2: Models — CreativeComment and CreativeReaction

**Files:**
- Modify: `core/models.py` (append after CreativePost)
- Modify: `tests/test_creative_studio.py`

- [ ] **Step 1: Write failing tests for CreativeComment**

```python
# tests/test_creative_studio.py (append)
from core.models import CreativeComment


class TestCreativeCommentModel:
    @pytest.fixture
    def published_post(self, db, org_alpha, user_alpha_owner):
        return CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='lyrics', title='Test Song', status='published',
        )

    def test_create_comment(self, published_post, user_alpha_member):
        comment = CreativeComment.objects.create(
            post=published_post, author=user_alpha_member,
            content='Love this!',
        )
        assert comment.content == 'Love this!'
        assert comment.parent is None
        assert published_post.comments.count() == 1

    def test_threaded_reply(self, published_post, user_alpha_owner, user_alpha_member):
        parent_comment = CreativeComment.objects.create(
            post=published_post, author=user_alpha_owner,
            content='Great work!',
        )
        reply = CreativeComment.objects.create(
            post=published_post, author=user_alpha_member,
            content='Thank you!', parent=parent_comment,
        )
        assert reply.parent == parent_comment

    def test_comment_with_mentions(self, published_post, user_alpha_owner, user_alpha_member):
        comment = CreativeComment.objects.create(
            post=published_post, author=user_alpha_owner,
            content='@alpha_member check this out',
        )
        comment.mentioned_users.add(user_alpha_member)
        assert comment.mentioned_users.count() == 1
```

- [ ] **Step 2: Write failing tests for CreativeReaction**

```python
# tests/test_creative_studio.py (append)
from django.db import IntegrityError
from core.models import CreativeReaction


class TestCreativeReactionModel:
    @pytest.fixture
    def published_post(self, db, org_alpha, user_alpha_owner):
        return CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='Great Idea', status='published',
        )

    def test_create_reaction(self, published_post, user_alpha_member):
        reaction = CreativeReaction.objects.create(
            post=published_post, user=user_alpha_member,
            reaction_type='heart',
        )
        assert reaction.reaction_type == 'heart'
        assert published_post.reactions.count() == 1

    def test_multiple_reaction_types_per_user(self, published_post, user_alpha_member):
        CreativeReaction.objects.create(post=published_post, user=user_alpha_member, reaction_type='heart')
        CreativeReaction.objects.create(post=published_post, user=user_alpha_member, reaction_type='fire')
        assert published_post.reactions.count() == 2

    def test_unique_reaction_type_per_user(self, published_post, user_alpha_member):
        CreativeReaction.objects.create(post=published_post, user=user_alpha_member, reaction_type='heart')
        with pytest.raises(IntegrityError):
            CreativeReaction.objects.create(post=published_post, user=user_alpha_member, reaction_type='heart')
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_creative_studio.py::TestCreativeCommentModel tests/test_creative_studio.py::TestCreativeReactionModel -v`
Expected: FAIL with `ImportError`

- [ ] **Step 4: Implement CreativeComment and CreativeReaction models**

Append to `core/models.py` after CreativePost:

```python
class CreativeComment(models.Model):
    """Comment/feedback on a creative post."""
    post = models.ForeignKey(
        'CreativePost', on_delete=models.CASCADE, related_name='comments'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='creative_comments'
    )
    content = models.TextField()
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='replies'
    )
    mentioned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name='creative_comment_mentions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author} on {self.post.title}"


class CreativeReaction(models.Model):
    """Emoji reaction on a creative post."""
    REACTION_CHOICES = [
        ('heart', '❤️'),
        ('fire', '🔥'),
        ('pray', '🙏'),
        ('clap', '👏'),
        ('lightbulb', '💡'),
        ('star', '⭐'),
    ]

    post = models.ForeignKey(
        'CreativePost', on_delete=models.CASCADE, related_name='reactions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='creative_reactions'
    )
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['post', 'user', 'reaction_type']]

    def __str__(self):
        return f"{self.user} reacted {self.reaction_type} on {self.post.title}"
```

- [ ] **Step 5: Run makemigrations and migrate**

Run: `python manage.py makemigrations core && python manage.py migrate`
Expected: Migration applied successfully

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_creative_studio.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add core/models.py core/migrations/ tests/test_creative_studio.py
git commit -m "feat(studio): add CreativeComment and CreativeReaction models"
```

---

### Task 3: NotificationPreference fields and notification helpers

**Files:**
- Modify: `core/models.py:3621` (add fields after `song_submissions`)
- Modify: `core/notifications.py` (add preference check + notify helpers)
- Modify: `tests/test_creative_studio.py`

- [ ] **Step 1: Write failing tests for notification preferences**

```python
# tests/test_creative_studio.py (append)
from core.models import NotificationPreference


class TestStudioNotificationPreferences:
    def test_default_studio_preferences(self, db, user_alpha_owner):
        prefs = NotificationPreference.objects.create(user=user_alpha_owner)
        assert prefs.studio_new_posts is True
        assert prefs.studio_comments is True
        assert prefs.studio_builds is True
        assert prefs.studio_spotlights is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_creative_studio.py::TestStudioNotificationPreferences -v`
Expected: FAIL with `AttributeError: ... has no field named 'studio_new_posts'`

- [ ] **Step 3: Add NotificationPreference fields**

In `core/models.py`, find line 3621 (`song_submissions = models.BooleanField(...)`) and add after it:

```python
    # Creative Studio notifications
    studio_new_posts = models.BooleanField(default=True, help_text="New creative studio posts")
    studio_comments = models.BooleanField(default=True, help_text="Comments on my studio posts")
    studio_builds = models.BooleanField(default=True, help_text="When someone builds on my post")
    studio_spotlights = models.BooleanField(default=True, help_text="When my post is spotlighted")
```

- [ ] **Step 4: Run makemigrations and migrate**

Run: `python manage.py makemigrations core && python manage.py migrate`
Expected: Migration adding 4 fields to NotificationPreference

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_creative_studio.py::TestStudioNotificationPreferences -v`
Expected: PASS

- [ ] **Step 6: Write failing tests for notification helpers**

```python
# tests/test_creative_studio.py (append)
from unittest.mock import patch


class TestStudioNotifications:
    @pytest.fixture
    def published_post(self, db, org_alpha, user_alpha_owner):
        return CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='lyrics', title='Test Song', status='published',
        )

    @patch('core.notifications.send_notification_to_users')
    def test_notify_new_studio_post(self, mock_send, published_post, org_alpha):
        from core.notifications import notify_new_studio_post
        notify_new_studio_post(published_post)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs[1]['notification_type'] == 'studio'
        assert 'Test Song' in call_kwargs[1]['title']

    @patch('core.notifications.send_notification_to_user')
    def test_notify_studio_comment(self, mock_send, published_post, user_alpha_member):
        from core.notifications import notify_studio_comment
        comment = CreativeComment.objects.create(
            post=published_post, author=user_alpha_member, content='Great!',
        )
        notify_studio_comment(comment)
        mock_send.assert_called_once()
        assert mock_send.call_args[1]['notification_type'] == 'studio'

    @patch('core.notifications.send_notification_to_user')
    def test_notify_studio_build(self, mock_send, published_post, user_alpha_member, org_alpha):
        from core.notifications import notify_studio_build
        child = CreativePost.objects.create(
            author=user_alpha_member, organization=org_alpha,
            post_type='audio', title='Re: Test Song',
            status='published', parent_post=published_post,
        )
        notify_studio_build(child)
        mock_send.assert_called_once()

    @patch('core.notifications.send_notification_to_user')
    def test_notify_studio_spotlight(self, mock_send, published_post, user_alpha_owner):
        from core.notifications import notify_studio_spotlight
        published_post.is_spotlighted = True
        published_post.spotlighted_by = user_alpha_owner
        published_post.save()
        notify_studio_spotlight(published_post)
        mock_send.assert_called_once()
```

- [ ] **Step 7: Add preference check in send_notification_to_user**

In `core/notifications.py`, find line 206-208 (the `song_submission` preference check) and add after it:

```python
            elif notification_type == 'studio':
                if not prefs.studio_new_posts:
                    return 0
```

- [ ] **Step 8: Add notification helper functions**

Append to `core/notifications.py`:

```python
def notify_new_studio_post(post):
    """Send notifications when a new creative studio post is published."""
    from core.models import OrganizationMembership

    memberships = OrganizationMembership.objects.filter(
        organization=post.organization,
        is_active=True,
    ).select_related('user')

    users = [m.user for m in memberships if m.user.is_active and m.user.pk != post.author_id]

    author_name = post.author.display_name or post.author.username
    title = f'🎨 New in Studio: {post.title}'
    body = f'{author_name} shared a new {post.get_post_type_display().lower()}'

    sent = send_notification_to_users(
        users=users,
        notification_type='studio',
        title=title,
        body=body,
        url=f'/studio/post/{post.pk}/',
        data={'post_id': post.pk},
    )
    logger.info(f"Studio new post notifications sent: {sent}")
    return sent


def notify_studio_comment(comment):
    """Send notification when someone comments on a studio post."""
    post = comment.post
    if comment.author_id == post.author_id:
        return 0

    commenter_name = comment.author.display_name or comment.author.username
    return send_notification_to_user(
        user=post.author,
        notification_type='studio',
        title=f'💬 Comment on {post.title}',
        body=f'{commenter_name}: {comment.content[:100]}',
        url=f'/studio/post/{post.pk}/',
        data={'post_id': post.pk, 'comment_id': comment.pk},
    )


def notify_studio_build(child_post):
    """Send notification when someone builds on a studio post."""
    parent = child_post.parent_post
    if not parent or child_post.author_id == parent.author_id:
        return 0

    builder_name = child_post.author.display_name or child_post.author.username
    return send_notification_to_user(
        user=parent.author,
        notification_type='studio',
        title=f'🔨 Build on {parent.title}',
        body=f'{builder_name} built on your post: {child_post.title}',
        url=f'/studio/post/{child_post.pk}/',
        data={'post_id': child_post.pk, 'parent_id': parent.pk},
    )


def notify_studio_spotlight(post):
    """Send notification when a post is spotlighted."""
    if not post.spotlighted_by or post.spotlighted_by_id == post.author_id:
        return 0

    spotter_name = post.spotlighted_by.display_name or post.spotlighted_by.username
    body = f'{spotter_name} spotlighted your post'
    if post.spotlight_note:
        body += f': "{post.spotlight_note}"'

    return send_notification_to_user(
        user=post.author,
        notification_type='studio',
        title=f'⭐ {post.title} was spotlighted!',
        body=body,
        url=f'/studio/post/{post.pk}/',
        data={'post_id': post.pk},
    )
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `python -m pytest tests/test_creative_studio.py::TestStudioNotifications tests/test_creative_studio.py::TestStudioNotificationPreferences -v`
Expected: All PASS

- [ ] **Step 10: Commit**

```bash
git add core/models.py core/migrations/ core/notifications.py tests/test_creative_studio.py
git commit -m "feat(studio): add notification preferences and helpers for creative studio"
```

---

### Task 4: Studio views — feed, create, detail

**Files:**
- Create: `core/studio_views.py`
- Modify: `core/urls.py`
- Modify: `tests/test_creative_studio.py`

- [ ] **Step 1: Write failing tests for studio feed view**

```python
# tests/test_creative_studio.py (append)
from django.test import Client


class TestStudioFeedView:
    @pytest.fixture
    def client_alpha(self, db, user_alpha_owner, org_alpha):
        client = Client()
        client.force_login(user_alpha_owner)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    def test_feed_renders(self, client_alpha):
        response = client_alpha.get('/studio/')
        assert response.status_code == 200
        assert 'Creative Studio' in response.content.decode()

    def test_feed_shows_published_only(self, client_alpha, org_alpha, user_alpha_owner):
        CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='Published Idea', status='published',
        )
        CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='Draft Idea', status='draft',
        )
        response = client_alpha.get('/studio/')
        content = response.content.decode()
        assert 'Published Idea' in content
        assert 'Draft Idea' not in content

    def test_feed_filter_by_type(self, client_alpha, org_alpha, user_alpha_owner):
        CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='lyrics', title='A Song', status='published',
        )
        CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='artwork', title='A Painting', status='published',
        )
        response = client_alpha.get('/studio/?type=lyrics')
        content = response.content.decode()
        assert 'A Song' in content
        assert 'A Painting' not in content

    def test_feed_tenant_isolation(self, client_alpha, org_alpha, org_beta, user_alpha_owner, user_beta_owner):
        CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='Alpha Post', status='published',
        )
        CreativePost.objects.create(
            author=user_beta_owner, organization=org_beta,
            post_type='idea', title='Beta Post', status='published',
        )
        response = client_alpha.get('/studio/')
        content = response.content.decode()
        assert 'Alpha Post' in content
        assert 'Beta Post' not in content

    def test_feed_shows_own_drafts(self, client_alpha, org_alpha, user_alpha_owner):
        CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='My Draft', status='draft',
        )
        response = client_alpha.get('/studio/my-work/')
        content = response.content.decode()
        assert 'My Draft' in content
```

- [ ] **Step 2: Write failing tests for post create view**

```python
# tests/test_creative_studio.py (append)
class TestStudioPostCreateView:
    @pytest.fixture
    def client_alpha(self, db, user_alpha_owner, org_alpha):
        client = Client()
        client.force_login(user_alpha_owner)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    def test_create_form_renders(self, client_alpha):
        response = client_alpha.get('/studio/post/create/')
        assert response.status_code == 200

    def test_create_post_published(self, client_alpha, org_alpha):
        response = client_alpha.post('/studio/post/create/', {
            'title': 'New Song',
            'post_type': 'lyrics',
            'content': 'Verse 1 lyrics here...',
            'status': 'published',
        })
        assert response.status_code == 302
        post = CreativePost.objects.get(title='New Song')
        assert post.status == 'published'
        assert post.organization == org_alpha

    def test_create_post_draft(self, client_alpha, org_alpha):
        response = client_alpha.post('/studio/post/create/', {
            'title': 'WIP Song',
            'post_type': 'lyrics',
            'content': 'Work in progress...',
            'status': 'draft',
        })
        assert response.status_code == 302
        assert CreativePost.objects.filter(title='WIP Song', status='draft').exists()

    def test_create_build_on(self, client_alpha, org_alpha, user_alpha_owner):
        parent = CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='lyrics', title='Original', status='published',
        )
        response = client_alpha.get(f'/studio/post/{parent.pk}/build-on/')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Re: Original' in content
```

- [ ] **Step 3: Write failing tests for post detail view**

```python
# tests/test_creative_studio.py (append)
class TestStudioPostDetailView:
    @pytest.fixture
    def client_alpha(self, db, user_alpha_owner, org_alpha):
        client = Client()
        client.force_login(user_alpha_owner)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    @pytest.fixture
    def published_post(self, db, org_alpha, user_alpha_owner):
        return CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='lyrics', title='Detail Test', status='published',
            content='Some lyrics here...',
        )

    def test_detail_renders(self, client_alpha, published_post):
        response = client_alpha.get(f'/studio/post/{published_post.pk}/')
        assert response.status_code == 200
        assert 'Detail Test' in response.content.decode()

    def test_detail_shows_comments(self, client_alpha, published_post, user_alpha_member):
        CreativeComment.objects.create(
            post=published_post, author=user_alpha_member, content='Love this!',
        )
        response = client_alpha.get(f'/studio/post/{published_post.pk}/')
        assert 'Love this!' in response.content.decode()

    def test_detail_shows_build_chain(self, client_alpha, published_post, user_alpha_member, org_alpha):
        child = CreativePost.objects.create(
            author=user_alpha_member, organization=org_alpha,
            post_type='audio', title='Re: Detail Test',
            status='published', parent_post=published_post,
        )
        response = client_alpha.get(f'/studio/post/{published_post.pk}/')
        assert 'Re: Detail Test' in response.content.decode()

    def test_draft_not_visible_to_others(self, db, org_alpha, user_alpha_owner, user_alpha_member):
        draft = CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='Secret Draft', status='draft',
        )
        client = Client()
        client.force_login(user_alpha_member)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        response = client.get(f'/studio/post/{draft.pk}/')
        assert response.status_code == 404
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_creative_studio.py::TestStudioFeedView tests/test_creative_studio.py::TestStudioPostCreateView tests/test_creative_studio.py::TestStudioPostDetailView -v`
Expected: FAIL (404 — no URL patterns yet)

- [ ] **Step 5: Create `core/studio_views.py` with feed, create, detail, my-work, build-on views**

```python
# core/studio_views.py
"""Views for the Creative Studio feature."""
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from .models import (
    CreativeCollection, CreativeComment, CreativePost, CreativeReaction, CreativeTag,
    OrganizationMembership,
)

logger = logging.getLogger(__name__)


def get_org(request):
    """Get organization from request (set by TenantMiddleware)."""
    return getattr(request, 'organization', None)


def get_membership(request):
    """Get membership from request (set by TenantMiddleware)."""
    return getattr(request, 'membership', None)


def is_leader_or_above(membership):
    """Check if membership role is leader, admin, or owner."""
    if not membership:
        return False
    return membership.role in ('leader', 'admin', 'owner')


@login_required
def studio_feed(request):
    """Main creative studio feed with sidebar filters."""
    org = get_org(request)
    if not org:
        return redirect('dashboard')

    posts = CreativePost.objects.filter(
        organization=org, status='published',
    ).select_related(
        'author', 'collection', 'parent_post',
    ).prefetch_related('tags', 'reactions', 'comments').annotate(
        comment_count=Count('comments'),
        build_count=Count('builds', filter=Q(builds__status='published')),
    )

    # Apply filters
    post_type = request.GET.get('type')
    if post_type:
        posts = posts.filter(post_type=post_type)

    tag_slug = request.GET.get('tag')
    if tag_slug:
        posts = posts.filter(tags__slug=tag_slug)

    if request.GET.get('collaborative') == 'true':
        posts = posts.filter(is_collaborative=True)

    if request.GET.get('spotlighted') == 'true':
        posts = posts.filter(is_spotlighted=True)

    collections = CreativeCollection.objects.filter(
        organization=org, is_archived=False,
    )
    tags = CreativeTag.objects.filter(organization=org).order_by('name')

    context = {
        'posts': posts[:50],
        'collections': collections,
        'tags': tags,
        'post_type_choices': CreativePost.POST_TYPE_CHOICES,
        'current_type': post_type,
        'current_tag': tag_slug,
        'page_title': 'Creative Studio',
    }
    return render(request, 'core/studio/studio_feed.html', context)


@login_required
def studio_my_work(request):
    """Show current user's posts (including drafts)."""
    org = get_org(request)
    if not org:
        return redirect('dashboard')

    posts = CreativePost.objects.filter(
        organization=org, author=request.user,
    ).exclude(status='archived').select_related(
        'collection', 'parent_post',
    ).prefetch_related('tags', 'reactions', 'comments').annotate(
        comment_count=Count('comments'),
        build_count=Count('builds', filter=Q(builds__status='published')),
    )

    context = {
        'posts': posts,
        'page_title': 'My Work',
        'collections': CreativeCollection.objects.filter(organization=org, is_archived=False),
        'tags': CreativeTag.objects.filter(organization=org).order_by('name'),
        'post_type_choices': CreativePost.POST_TYPE_CHOICES,
    }
    return render(request, 'core/studio/studio_feed.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def studio_post_create(request):
    """Create a new creative post."""
    org = get_org(request)
    if not org:
        return redirect('dashboard')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        post_type = request.POST.get('post_type', 'other')
        content = request.POST.get('content', '')
        status = request.POST.get('status', 'draft')
        collection_id = request.POST.get('collection')
        is_collaborative = request.POST.get('is_collaborative') == 'on'
        parent_id = request.POST.get('parent_post')

        if not title:
            return render(request, 'core/studio/post_create.html', {
                'error': 'Title is required.',
                'collections': CreativeCollection.objects.filter(organization=org, is_archived=False),
                'post_type_choices': CreativePost.POST_TYPE_CHOICES,
            })

        post = CreativePost.objects.create(
            author=request.user,
            organization=org,
            post_type=post_type,
            title=title,
            content=content,
            status=status,
            is_collaborative=is_collaborative,
            collection_id=collection_id if collection_id else None,
            parent_post_id=parent_id if parent_id else None,
        )

        # Handle media upload
        media = request.FILES.get('media_file')
        if media:
            ext = media.name.rsplit('.', 1)[-1].lower() if '.' in media.name else ''
            if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
                post.media_type = 'image'
            elif ext in ('mp3', 'm4a', 'wav'):
                post.media_type = 'audio'
            elif ext in ('pdf', 'doc', 'docx', 'txt'):
                post.media_type = 'document'
            else:
                post.media_type = 'none'
            post.media_file = media
            post.save()

        # Handle tags
        tag_names = request.POST.get('tags', '')
        if tag_names:
            for tag_name in [t.strip() for t in tag_names.split(',') if t.strip()]:
                from django.utils.text import slugify
                tag, _ = CreativeTag.objects.get_or_create(
                    name=tag_name, organization=org,
                    defaults={'slug': slugify(tag_name)},
                )
                post.tags.add(tag)

        # Notify on publish
        if status == 'published':
            from .notifications import notify_new_studio_post, notify_studio_build
            notify_new_studio_post(post)
            if post.parent_post:
                notify_studio_build(post)

        return redirect('studio_post_detail', pk=post.pk)

    # GET — render form
    parent_post = None
    initial_title = ''
    initial_collection = None
    parent_id = request.GET.get('parent')
    if parent_id:
        parent_post = get_object_or_404(
            CreativePost, pk=parent_id, organization=org, status='published',
        )
        initial_title = f'Re: {parent_post.title}'
        initial_collection = parent_post.collection_id

    context = {
        'collections': CreativeCollection.objects.filter(organization=org, is_archived=False),
        'post_type_choices': CreativePost.POST_TYPE_CHOICES,
        'parent_post': parent_post,
        'initial_title': initial_title,
        'initial_collection': initial_collection,
    }
    return render(request, 'core/studio/post_create.html', context)


@login_required
def studio_post_build_on(request, pk):
    """Redirect to create form with parent pre-filled."""
    org = get_org(request)
    parent = get_object_or_404(CreativePost, pk=pk, organization=org, status='published')
    return redirect(f'/studio/post/create/?parent={parent.pk}')


@login_required
def studio_post_detail(request, pk):
    """View a single creative post with comments, reactions, and build chain."""
    org = get_org(request)
    if not org:
        return redirect('dashboard')

    post = CreativePost.objects.filter(
        pk=pk, organization=org,
    ).select_related(
        'author', 'collection', 'parent_post', 'spotlighted_by',
    ).prefetch_related('tags', 'reactions', 'comments__author').first()

    if not post:
        raise Http404

    # Draft visibility: only author can see drafts
    if post.status == 'draft' and post.author != request.user:
        raise Http404

    comments = post.comments.filter(parent__isnull=True).select_related('author').prefetch_related(
        'replies__author', 'mentioned_users',
    )

    builds = CreativePost.objects.filter(
        parent_post=post, status='published',
    ).select_related('author')

    # Build reaction summary
    reaction_summary = {}
    for reaction in post.reactions.all():
        rt = reaction.reaction_type
        if rt not in reaction_summary:
            reaction_summary[rt] = {'count': 0, 'user_reacted': False, 'emoji': dict(CreativeReaction.REACTION_CHOICES).get(rt, rt)}
        reaction_summary[rt]['count'] += 1
        if reaction.user_id == request.user.id:
            reaction_summary[rt]['user_reacted'] = True

    membership = get_membership(request)

    context = {
        'post': post,
        'comments': comments,
        'builds': builds,
        'reaction_summary': reaction_summary,
        'reaction_choices': CreativeReaction.REACTION_CHOICES,
        'can_spotlight': is_leader_or_above(membership),
        'can_edit': post.author == request.user,
        'can_delete': post.author == request.user or (membership and membership.role in ('admin', 'owner')),
    }
    return render(request, 'core/studio/post_detail.html', context)
```

- [ ] **Step 6: Add URL patterns in `core/urls.py`**

Insert before the closing `]` at line 203:

```python
    # Creative Studio
    path('studio/', studio_views.studio_feed, name='studio_feed'),
    path('studio/my-work/', studio_views.studio_my_work, name='studio_my_work'),
    path('studio/post/create/', studio_views.studio_post_create, name='studio_post_create'),
    path('studio/post/<int:pk>/', studio_views.studio_post_detail, name='studio_post_detail'),
    path('studio/post/<int:pk>/build-on/', studio_views.studio_post_build_on, name='studio_post_build_on'),
```

Also add the import at the top of `core/urls.py`:

```python
from . import studio_views
```

- [ ] **Step 7: Create minimal templates to make views render**

Create `templates/core/studio/studio_feed.html`:

```html
{% extends 'base.html' %}
{% block title %}{{ page_title }}{% endblock %}
{% block content %}
<div class="max-w-7xl mx-auto px-4 py-6">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">Creative Studio</h1>
    <a href="{% url 'studio_post_create' %}" class="bg-ch-gold text-ch-darker px-4 py-2 rounded-lg font-semibold hover:bg-ch-gold/90 transition">+ New Post</a>
  </div>
  <div class="flex gap-6">
    <!-- Sidebar filters -->
    <div class="w-64 flex-shrink-0 space-y-4">
      <div class="bg-ch-dark rounded-lg p-4">
        <h3 class="text-ch-gold text-xs uppercase font-semibold mb-3">Filter by Type</h3>
        <div class="space-y-1">
          <a href="{% url 'studio_feed' %}" class="block text-sm {% if not current_type %}text-white font-semibold{% else %}text-gray-400 hover:text-white{% endif %}">All Posts</a>
          {% for value, label in post_type_choices %}
          <a href="{% url 'studio_feed' %}?type={{ value }}" class="block text-sm {% if current_type == value %}text-white font-semibold{% else %}text-gray-400 hover:text-white{% endif %}">{{ label }}</a>
          {% endfor %}
        </div>
      </div>
      <div class="bg-ch-dark rounded-lg p-4">
        <h3 class="text-ch-gold text-xs uppercase font-semibold mb-3">Collections</h3>
        <div class="space-y-1">
          {% for collection in collections %}
          <a href="{% url 'studio_collection_detail' collection.pk %}" class="block text-sm text-gray-400 hover:text-white">{{ collection.name }}</a>
          {% empty %}
          <p class="text-gray-500 text-sm">No collections yet</p>
          {% endfor %}
        </div>
      </div>
      <div class="bg-ch-dark rounded-lg p-4">
        <h3 class="text-ch-gold text-xs uppercase font-semibold mb-3">Quick Filters</h3>
        <div class="space-y-1">
          <a href="{% url 'studio_my_work' %}" class="block text-sm text-gray-400 hover:text-white">My Work</a>
          <a href="{% url 'studio_feed' %}?spotlighted=true" class="block text-sm text-gray-400 hover:text-white">⭐ Spotlights</a>
          <a href="{% url 'studio_feed' %}?collaborative=true" class="block text-sm text-gray-400 hover:text-white">🤝 Looking for Collaborators</a>
        </div>
      </div>
      {% if tags %}
      <div class="bg-ch-dark rounded-lg p-4">
        <h3 class="text-ch-gold text-xs uppercase font-semibold mb-3">Tags</h3>
        <div class="flex flex-wrap gap-2">
          {% for tag in tags %}
          <a href="{% url 'studio_feed' %}?tag={{ tag.slug }}" class="text-xs px-2 py-1 rounded-full {% if current_tag == tag.slug %}bg-ch-gold text-ch-darker{% else %}bg-gray-700 text-gray-300 hover:bg-gray-600{% endif %}">{{ tag.name }}</a>
          {% endfor %}
        </div>
      </div>
      {% endif %}
    </div>
    <!-- Feed -->
    <div class="flex-1 space-y-4">
      {% for post in posts %}
      {% include 'core/studio/partials/post_card.html' %}
      {% empty %}
      <div class="text-center py-16">
        <p class="text-gray-400 text-lg mb-2">No posts yet</p>
        <p class="text-gray-500 text-sm mb-4">Be the first to share something creative!</p>
        <a href="{% url 'studio_post_create' %}" class="text-ch-gold hover:underline">+ Create a Post</a>
      </div>
      {% endfor %}
    </div>
  </div>
</div>
{% endblock %}
```

Create `templates/core/studio/partials/post_card.html`:

```html
<a href="{% url 'studio_post_detail' post.pk %}" class="block bg-ch-dark rounded-lg p-5 border {% if post.is_spotlighted %}border-ch-gold{% else %}border-gray-800{% endif %} hover:border-gray-600 transition">
  {% if post.is_spotlighted %}
  <div class="text-ch-gold text-xs mb-2">⭐ SPOTLIGHTED</div>
  {% endif %}
  <div class="flex items-center gap-2 mb-2">
    <span class="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">{{ post.get_post_type_display }}</span>
    {% if post.is_collaborative %}
    <span class="text-xs px-2 py-0.5 rounded bg-green-900/50 text-green-400">🤝 Looking for collaborators</span>
    {% endif %}
    {% if post.status == 'draft' %}
    <span class="text-xs px-2 py-0.5 rounded bg-yellow-900/50 text-yellow-400">Draft</span>
    {% endif %}
  </div>
  <div class="flex items-center gap-2 mb-2">
    <div class="w-7 h-7 bg-ch-gold rounded-full flex items-center justify-center text-xs text-ch-darker font-bold">{{ post.author.display_name|default:post.author.username|truncatechars:2|upper }}</div>
    <span class="text-white text-sm font-semibold">{{ post.author.display_name|default:post.author.username }}</span>
    <span class="text-gray-500 text-xs">· {{ post.created_at|timesince }} ago</span>
  </div>
  <h3 class="text-white text-base font-semibold mb-1">{{ post.title }}</h3>
  {% if post.content %}
  <p class="text-gray-400 text-sm line-clamp-3 mb-3 {% if post.post_type == 'lyrics' or post.post_type == 'poem' %}italic{% endif %}">{{ post.content|truncatechars:200 }}</p>
  {% endif %}
  {% if post.media_file and post.media_type == 'image' %}
  <div class="mb-3 rounded-lg overflow-hidden max-h-48">
    <img src="{{ post.media_file.url }}" alt="{{ post.title }}" class="w-full object-cover">
  </div>
  {% endif %}
  {% if post.tags.all %}
  <div class="flex flex-wrap gap-1 mb-3">
    {% for tag in post.tags.all %}
    <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-400">{{ tag.name }}</span>
    {% endfor %}
  </div>
  {% endif %}
  <div class="flex items-center gap-3 text-gray-500 text-xs">
    {% for reaction in post.reactions.all|dictsort:"reaction_type" %}{% if forloop.first or forloop.revcounter %}{% endif %}{% endfor %}
    <span>{{ post.reactions.count }} reactions</span>
    <span>{{ post.comment_count }} comments</span>
    {% if post.build_count %}<span>{{ post.build_count }} builds</span>{% endif %}
  </div>
</a>
```

Create `templates/core/studio/post_create.html`:

```html
{% extends 'base.html' %}
{% block title %}{% if parent_post %}Build on {{ parent_post.title }}{% else %}New Post{% endif %}{% endblock %}
{% block content %}
<div class="max-w-2xl mx-auto px-4 py-6">
  <h1 class="text-2xl font-bold text-white mb-6">{% if parent_post %}Build on "{{ parent_post.title }}"{% else %}New Post{% endif %}</h1>
  {% if parent_post %}
  <div class="bg-ch-dark rounded-lg p-4 border-l-4 border-ch-gold mb-6">
    <p class="text-sm text-gray-400">Building on <strong class="text-white">{{ parent_post.title }}</strong> by {{ parent_post.author.display_name|default:parent_post.author.username }}</p>
  </div>
  {% endif %}
  {% if error %}
  <div class="bg-red-900/50 border border-red-700 rounded-lg p-4 mb-4 text-red-300">{{ error }}</div>
  {% endif %}
  <form method="post" enctype="multipart/form-data" class="space-y-6">
    {% csrf_token %}
    {% if parent_post %}<input type="hidden" name="parent_post" value="{{ parent_post.pk }}">{% endif %}
    <div>
      <label for="title" class="block text-sm font-medium text-gray-300 mb-1">Title</label>
      <input type="text" name="title" id="title" value="{{ initial_title }}" required class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none">
    </div>
    <div>
      <label for="post_type" class="block text-sm font-medium text-gray-300 mb-1">Type</label>
      <select name="post_type" id="post_type" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none">
        {% for value, label in post_type_choices %}
        <option value="{{ value }}">{{ label }}</option>
        {% endfor %}
      </select>
    </div>
    <div>
      <label for="content" class="block text-sm font-medium text-gray-300 mb-1">Content</label>
      <textarea name="content" id="content" rows="10" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none" placeholder="Share your creative work..."></textarea>
    </div>
    <div>
      <label for="media_file" class="block text-sm font-medium text-gray-300 mb-1">Media (optional)</label>
      <input type="file" name="media_file" id="media_file" accept=".png,.jpg,.jpeg,.gif,.webp,.mp3,.m4a,.wav,.pdf,.doc,.docx,.txt" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white file:mr-4 file:bg-gray-700 file:text-gray-300 file:border-0 file:rounded file:px-3 file:py-1">
      <p class="text-xs text-gray-500 mt-1">Images, audio, or documents. Max 10MB.</p>
    </div>
    <div>
      <label for="collection" class="block text-sm font-medium text-gray-300 mb-1">Collection (optional)</label>
      <select name="collection" id="collection" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none">
        <option value="">None</option>
        {% for c in collections %}
        <option value="{{ c.pk }}" {% if initial_collection == c.pk %}selected{% endif %}>{{ c.name }}</option>
        {% endfor %}
      </select>
    </div>
    <div>
      <label for="tags" class="block text-sm font-medium text-gray-300 mb-1">Tags (comma-separated)</label>
      <input type="text" name="tags" id="tags" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none" placeholder="worship, easter, original">
    </div>
    <div class="flex items-center gap-2">
      <input type="checkbox" name="is_collaborative" id="is_collaborative" class="rounded bg-gray-800 border-gray-600 text-ch-gold focus:ring-ch-gold">
      <label for="is_collaborative" class="text-sm text-gray-300">Looking for collaborators</label>
    </div>
    <div class="flex gap-3">
      <button type="submit" name="status" value="published" class="bg-ch-gold text-ch-darker px-6 py-2 rounded-lg font-semibold hover:bg-ch-gold/90 transition">Publish</button>
      <button type="submit" name="status" value="draft" class="bg-gray-700 text-gray-300 px-6 py-2 rounded-lg font-semibold hover:bg-gray-600 transition">Save as Draft</button>
      <a href="{% url 'studio_feed' %}" class="text-gray-400 px-4 py-2 hover:text-white transition">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

Create `templates/core/studio/post_detail.html`:

```html
{% extends 'base.html' %}
{% block title %}{{ post.title }} — Creative Studio{% endblock %}
{% block content %}
<div class="max-w-3xl mx-auto px-4 py-6">
  <!-- Breadcrumb -->
  <div class="text-sm text-gray-500 mb-4">
    <a href="{% url 'studio_feed' %}" class="hover:text-white">Creative Studio</a> › {{ post.title }}
  </div>

  <!-- Post header -->
  <div class="flex items-center gap-3 mb-4">
    <div class="w-10 h-10 bg-ch-gold rounded-full flex items-center justify-center text-sm text-ch-darker font-bold">{{ post.author.display_name|default:post.author.username|truncatechars:2|upper }}</div>
    <div>
      <div class="text-white font-semibold">{{ post.author.display_name|default:post.author.username }}</div>
      <div class="text-gray-500 text-xs">{{ post.created_at|timesince }} ago{% if post.collection %} · in <a href="{% url 'studio_collection_detail' post.collection.pk %}" class="text-ch-gold hover:underline">{{ post.collection.name }}</a>{% endif %}</div>
    </div>
    <div class="ml-auto flex items-center gap-2">
      <span class="text-xs px-2 py-1 rounded bg-gray-700 text-gray-300">{{ post.get_post_type_display }}</span>
      {% if post.is_collaborative %}<span class="text-xs px-2 py-1 rounded bg-green-900/50 text-green-400">🤝 Collaborators welcome</span>{% endif %}
    </div>
  </div>

  <!-- Spotlight banner -->
  {% if post.is_spotlighted %}
  <div class="bg-gradient-to-r from-ch-gold/10 to-transparent border-l-4 border-ch-gold px-4 py-3 rounded-r mb-4">
    <span class="text-ch-gold text-sm">⭐ Spotlighted by {{ post.spotlighted_by.display_name|default:post.spotlighted_by.username }}{% if post.spotlight_note %} — "{{ post.spotlight_note }}"{% endif %}</span>
  </div>
  {% endif %}

  <!-- Title -->
  <h1 class="text-2xl font-bold text-white mb-4">{{ post.title }}</h1>

  <!-- Content -->
  {% if post.content %}
  <div class="bg-ch-dark rounded-lg p-6 mb-4 border border-gray-800">
    <div class="text-gray-300 leading-relaxed whitespace-pre-line {% if post.post_type == 'lyrics' or post.post_type == 'poem' %}font-serif italic text-lg{% endif %}">{{ post.content }}</div>
  </div>
  {% endif %}

  <!-- Media -->
  {% if post.media_file %}
  <div class="mb-4">
    {% if post.media_type == 'image' %}
    <img src="{{ post.media_file.url }}" alt="{{ post.title }}" class="rounded-lg max-w-full">
    {% elif post.media_type == 'audio' %}
    <audio controls class="w-full"><source src="{{ post.media_file.url }}">Your browser does not support audio.</audio>
    {% elif post.media_type == 'document' %}
    <a href="{{ post.media_file.url }}" target="_blank" class="inline-flex items-center gap-2 bg-ch-dark px-4 py-3 rounded-lg border border-gray-700 text-gray-300 hover:text-white transition">📄 Download {{ post.media_file.name|truncatechars:40 }}</a>
    {% endif %}
  </div>
  {% endif %}

  <!-- Tags -->
  {% if post.tags.all %}
  <div class="flex flex-wrap gap-2 mb-4">
    {% for tag in post.tags.all %}
    <a href="{% url 'studio_feed' %}?tag={{ tag.slug }}" class="text-xs px-2 py-1 rounded-full bg-gray-700 text-gray-400 hover:text-white">{{ tag.name }}</a>
    {% endfor %}
  </div>
  {% endif %}

  <!-- Reaction bar -->
  <div class="flex items-center gap-2 py-3 border-t border-b border-gray-800 mb-4">
    {% for rtype, emoji in reaction_choices %}
    <button hx-post="{% url 'studio_post_react' post.pk %}" hx-vals='{"reaction_type": "{{ rtype }}"}' hx-target="#reaction-bar" hx-swap="outerHTML" class="px-3 py-1 rounded-full text-sm {% if reaction_summary|default_if_none:'' %}{% for key, val in reaction_summary.items %}{% if key == rtype and val.user_reacted %}bg-ch-gold/20 border border-ch-gold/50{% endif %}{% endfor %}{% else %}bg-gray-800{% endif %} hover:bg-gray-700 transition">
      {{ emoji }} {% for key, val in reaction_summary.items %}{% if key == rtype %}{{ val.count }}{% endif %}{% endfor %}
    </button>
    {% endfor %}
    <div class="ml-auto flex gap-2">
      <a href="{% url 'studio_post_build_on' post.pk %}" class="bg-ch-gold text-ch-darker px-4 py-1 rounded-full text-sm font-semibold hover:bg-ch-gold/90 transition">🎨 Build on this</a>
      {% if can_edit %}<a href="{% url 'studio_post_edit' post.pk %}" class="text-gray-400 hover:text-white text-sm px-3 py-1">Edit</a>{% endif %}
      {% if can_delete %}<a href="{% url 'studio_post_delete' post.pk %}" class="text-red-400 hover:text-red-300 text-sm px-3 py-1">Delete</a>{% endif %}
      {% if can_spotlight %}
      <form method="post" action="{% url 'studio_post_spotlight' post.pk %}" class="inline">
        {% csrf_token %}
        <button type="submit" class="text-sm px-3 py-1 {% if post.is_spotlighted %}text-ch-gold{% else %}text-gray-400 hover:text-ch-gold{% endif %}">{% if post.is_spotlighted %}★ Unspotlight{% else %}☆ Spotlight{% endif %}</button>
      </form>
      {% endif %}
    </div>
  </div>

  <!-- Build-on chain -->
  {% if builds %}
  <div class="mb-6">
    <h3 class="text-ch-gold text-xs uppercase font-semibold mb-3">{{ builds|length }} Build{{ builds|length|pluralize }} on this</h3>
    <div class="border-l-2 border-ch-gold pl-4 space-y-2">
      {% for build in builds %}
      <a href="{% url 'studio_post_detail' build.pk %}" class="block bg-ch-dark rounded-lg p-3 border border-gray-800 hover:border-gray-600 transition">
        <div class="flex items-center gap-2 mb-1">
          <div class="w-6 h-6 bg-indigo-500 rounded-full flex items-center justify-center text-xs text-white font-bold">{{ build.author.display_name|default:build.author.username|truncatechars:2|upper }}</div>
          <span class="text-white text-sm font-semibold">{{ build.author.display_name|default:build.author.username }}</span>
          <span class="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-300">{{ build.get_post_type_display }}</span>
          <span class="text-gray-500 text-xs">· {{ build.created_at|timesince }} ago</span>
        </div>
        <p class="text-gray-400 text-sm">{{ build.title }}</p>
      </a>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  <!-- Comments -->
  <div>
    <h3 class="text-white font-semibold mb-4">{{ comments|length }} Comment{{ comments|length|pluralize }}</h3>
    <div id="comments-list" class="space-y-3">
      {% for comment in comments %}
      {% include 'core/studio/partials/comment.html' %}
      {% endfor %}
    </div>
    <!-- Comment form -->
    <form hx-post="{% url 'studio_post_comment' post.pk %}" hx-target="#comments-list" hx-swap="beforeend" class="mt-4 flex gap-3">
      {% csrf_token %}
      <div class="w-8 h-8 bg-ch-gold rounded-full flex items-center justify-center text-xs text-ch-darker font-bold flex-shrink-0">{{ request.user.display_name|default:request.user.username|truncatechars:2|upper }}</div>
      <div class="flex-1">
        <textarea name="content" rows="2" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none text-sm" placeholder="Add a comment..."></textarea>
        <div class="flex justify-end mt-2">
          <button type="submit" class="bg-ch-gold text-ch-darker px-4 py-1 rounded-lg text-sm font-semibold hover:bg-ch-gold/90 transition">Post</button>
        </div>
      </div>
    </form>
  </div>

  <!-- Parent post link -->
  {% if post.parent_post %}
  <div class="mt-6 pt-4 border-t border-gray-800">
    <p class="text-gray-500 text-sm">Built on: <a href="{% url 'studio_post_detail' post.parent_post.pk %}" class="text-ch-gold hover:underline">{{ post.parent_post.title }}</a> by {{ post.parent_post.author.display_name|default:post.parent_post.author.username }}</p>
  </div>
  {% endif %}
</div>
{% endblock %}
```

Create `templates/core/studio/partials/comment.html`:

```html
<div class="flex gap-3">
  <div class="w-7 h-7 bg-indigo-500 rounded-full flex items-center justify-center text-xs text-white font-bold flex-shrink-0">{{ comment.author.display_name|default:comment.author.username|truncatechars:2|upper }}</div>
  <div class="bg-ch-dark rounded-lg p-3 border border-gray-800 flex-1">
    <div class="flex items-center gap-2 mb-1">
      <span class="text-white text-sm font-semibold">{{ comment.author.display_name|default:comment.author.username }}</span>
      <span class="text-gray-500 text-xs">· {{ comment.created_at|timesince }} ago</span>
    </div>
    <p class="text-gray-300 text-sm">{{ comment.content }}</p>
  </div>
</div>
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/test_creative_studio.py -v`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add core/studio_views.py core/urls.py templates/core/studio/ tests/test_creative_studio.py
git commit -m "feat(studio): add feed, create, and detail views with templates"
```

---

### Task 5: Studio views — edit, delete, comment, react, spotlight

**Files:**
- Modify: `core/studio_views.py`
- Modify: `core/urls.py`
- Modify: `tests/test_creative_studio.py`

- [ ] **Step 1: Write failing tests for edit, delete, comment, react, spotlight**

```python
# tests/test_creative_studio.py (append)
class TestStudioPostActions:
    @pytest.fixture
    def client_alpha(self, db, user_alpha_owner, org_alpha):
        client = Client()
        client.force_login(user_alpha_owner)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    @pytest.fixture
    def member_client(self, db, user_alpha_member, org_alpha):
        client = Client()
        client.force_login(user_alpha_member)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    @pytest.fixture
    def published_post(self, db, org_alpha, user_alpha_owner):
        return CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='lyrics', title='Editable Post', status='published',
            content='Original content',
        )

    def test_edit_own_post(self, client_alpha, published_post):
        response = client_alpha.post(f'/studio/post/{published_post.pk}/edit/', {
            'title': 'Updated Title',
            'post_type': 'lyrics',
            'content': 'Updated content',
            'status': 'published',
        })
        assert response.status_code == 302
        published_post.refresh_from_db()
        assert published_post.title == 'Updated Title'

    def test_cannot_edit_others_post(self, member_client, published_post):
        response = member_client.get(f'/studio/post/{published_post.pk}/edit/')
        assert response.status_code == 403

    def test_delete_own_post(self, client_alpha, published_post):
        response = client_alpha.post(f'/studio/post/{published_post.pk}/delete/')
        assert response.status_code == 302
        assert not CreativePost.objects.filter(pk=published_post.pk).exists()

    def test_add_comment(self, client_alpha, published_post):
        response = client_alpha.post(f'/studio/post/{published_post.pk}/comment/', {
            'content': 'A new comment',
        })
        assert response.status_code == 200
        assert published_post.comments.count() == 1

    def test_toggle_reaction(self, client_alpha, published_post):
        # Add reaction
        response = client_alpha.post(f'/studio/post/{published_post.pk}/react/', {
            'reaction_type': 'heart',
        })
        assert response.status_code == 200
        assert published_post.reactions.count() == 1
        # Remove reaction (toggle)
        response = client_alpha.post(f'/studio/post/{published_post.pk}/react/', {
            'reaction_type': 'heart',
        })
        assert published_post.reactions.count() == 0

    def test_spotlight_by_owner(self, client_alpha, published_post):
        response = client_alpha.post(f'/studio/post/{published_post.pk}/spotlight/')
        assert response.status_code == 302
        published_post.refresh_from_db()
        assert published_post.is_spotlighted is True

    def test_spotlight_denied_for_member(self, member_client, published_post):
        response = member_client.post(f'/studio/post/{published_post.pk}/spotlight/')
        assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_creative_studio.py::TestStudioPostActions -v`
Expected: FAIL (URLs not found)

- [ ] **Step 3: Add edit, delete, comment, react, spotlight views to `core/studio_views.py`**

```python
# Append to core/studio_views.py

@login_required
@require_http_methods(["GET", "POST"])
def studio_post_edit(request, pk):
    """Edit an existing creative post (author only)."""
    org = get_org(request)
    post = get_object_or_404(CreativePost, pk=pk, organization=org)
    if post.author != request.user:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    if request.method == 'POST':
        post.title = request.POST.get('title', post.title).strip()
        post.post_type = request.POST.get('post_type', post.post_type)
        post.content = request.POST.get('content', post.content)
        post.status = request.POST.get('status', post.status)
        post.is_collaborative = request.POST.get('is_collaborative') == 'on'
        collection_id = request.POST.get('collection')
        post.collection_id = collection_id if collection_id else None

        media = request.FILES.get('media_file')
        if media:
            ext = media.name.rsplit('.', 1)[-1].lower() if '.' in media.name else ''
            if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
                post.media_type = 'image'
            elif ext in ('mp3', 'm4a', 'wav'):
                post.media_type = 'audio'
            elif ext in ('pdf', 'doc', 'docx', 'txt'):
                post.media_type = 'document'
            post.media_file = media

        post.save()

        # Update tags
        tag_names = request.POST.get('tags', '')
        post.tags.clear()
        if tag_names:
            from django.utils.text import slugify
            for tag_name in [t.strip() for t in tag_names.split(',') if t.strip()]:
                tag, _ = CreativeTag.objects.get_or_create(
                    name=tag_name, organization=org,
                    defaults={'slug': slugify(tag_name)},
                )
                post.tags.add(tag)

        return redirect('studio_post_detail', pk=post.pk)

    context = {
        'post': post,
        'collections': CreativeCollection.objects.filter(organization=org, is_archived=False),
        'post_type_choices': CreativePost.POST_TYPE_CHOICES,
    }
    return render(request, 'core/studio/post_edit.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def studio_post_delete(request, pk):
    """Delete a creative post (author or admin/owner)."""
    org = get_org(request)
    post = get_object_or_404(CreativePost, pk=pk, organization=org)
    membership = get_membership(request)
    if post.author != request.user and (not membership or membership.role not in ('admin', 'owner')):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    if request.method == 'POST':
        post.delete()
        return redirect('studio_feed')

    return render(request, 'core/studio/post_confirm_delete.html', {'post': post})


@login_required
@require_POST
def studio_post_comment(request, pk):
    """Add a comment to a post (HTMX)."""
    org = get_org(request)
    post = get_object_or_404(CreativePost, pk=pk, organization=org, status='published')
    content = request.POST.get('content', '').strip()
    if not content:
        return render(request, 'core/studio/partials/comment.html', {'comment': None})

    comment = CreativeComment.objects.create(
        post=post, author=request.user, content=content,
    )

    # Notify post author
    from .notifications import notify_studio_comment
    notify_studio_comment(comment)

    return render(request, 'core/studio/partials/comment.html', {'comment': comment})


@login_required
@require_POST
def studio_post_react(request, pk):
    """Toggle a reaction on a post (HTMX)."""
    org = get_org(request)
    post = get_object_or_404(CreativePost, pk=pk, organization=org, status='published')
    reaction_type = request.POST.get('reaction_type')
    if reaction_type not in dict(CreativeReaction.REACTION_CHOICES):
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest()

    existing = CreativeReaction.objects.filter(
        post=post, user=request.user, reaction_type=reaction_type,
    )
    if existing.exists():
        existing.delete()
    else:
        CreativeReaction.objects.create(
            post=post, user=request.user, reaction_type=reaction_type,
        )

    # Return updated reaction bar
    reaction_summary = {}
    for reaction in post.reactions.all():
        rt = reaction.reaction_type
        if rt not in reaction_summary:
            reaction_summary[rt] = {'count': 0, 'user_reacted': False, 'emoji': dict(CreativeReaction.REACTION_CHOICES).get(rt, rt)}
        reaction_summary[rt]['count'] += 1
        if reaction.user_id == request.user.id:
            reaction_summary[rt]['user_reacted'] = True

    return render(request, 'core/studio/partials/reaction_bar.html', {
        'post': post,
        'reaction_summary': reaction_summary,
        'reaction_choices': CreativeReaction.REACTION_CHOICES,
    })


@login_required
@require_POST
def studio_post_spotlight(request, pk):
    """Toggle spotlight on a post (leader/admin/owner only)."""
    org = get_org(request)
    membership = get_membership(request)
    if not is_leader_or_above(membership):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    post = get_object_or_404(CreativePost, pk=pk, organization=org, status='published')

    if post.is_spotlighted:
        post.is_spotlighted = False
        post.spotlighted_by = None
        post.spotlight_note = ''
    else:
        post.is_spotlighted = True
        post.spotlighted_by = request.user
        post.spotlight_note = request.POST.get('spotlight_note', '')
        from .notifications import notify_studio_spotlight
        notify_studio_spotlight(post)

    post.save()
    return redirect('studio_post_detail', pk=post.pk)
```

- [ ] **Step 4: Add URL patterns**

In `core/urls.py`, add after the existing studio URLs:

```python
    path('studio/post/<int:pk>/edit/', studio_views.studio_post_edit, name='studio_post_edit'),
    path('studio/post/<int:pk>/delete/', studio_views.studio_post_delete, name='studio_post_delete'),
    path('studio/post/<int:pk>/comment/', studio_views.studio_post_comment, name='studio_post_comment'),
    path('studio/post/<int:pk>/react/', studio_views.studio_post_react, name='studio_post_react'),
    path('studio/post/<int:pk>/spotlight/', studio_views.studio_post_spotlight, name='studio_post_spotlight'),
```

- [ ] **Step 5: Create edit and delete templates**

Create `templates/core/studio/post_edit.html`:

```html
{% extends 'base.html' %}
{% block title %}Edit: {{ post.title }}{% endblock %}
{% block content %}
<div class="max-w-2xl mx-auto px-4 py-6">
  <h1 class="text-2xl font-bold text-white mb-6">Edit Post</h1>
  <form method="post" enctype="multipart/form-data" class="space-y-6">
    {% csrf_token %}
    <div>
      <label for="title" class="block text-sm font-medium text-gray-300 mb-1">Title</label>
      <input type="text" name="title" id="title" value="{{ post.title }}" required class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none">
    </div>
    <div>
      <label for="post_type" class="block text-sm font-medium text-gray-300 mb-1">Type</label>
      <select name="post_type" id="post_type" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none">
        {% for value, label in post_type_choices %}
        <option value="{{ value }}" {% if post.post_type == value %}selected{% endif %}>{{ label }}</option>
        {% endfor %}
      </select>
    </div>
    <div>
      <label for="content" class="block text-sm font-medium text-gray-300 mb-1">Content</label>
      <textarea name="content" id="content" rows="10" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none">{{ post.content }}</textarea>
    </div>
    <div>
      <label for="media_file" class="block text-sm font-medium text-gray-300 mb-1">Media{% if post.media_file %} (current: {{ post.media_file.name|truncatechars:30 }}){% endif %}</label>
      <input type="file" name="media_file" id="media_file" accept=".png,.jpg,.jpeg,.gif,.webp,.mp3,.m4a,.wav,.pdf,.doc,.docx,.txt" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white file:mr-4 file:bg-gray-700 file:text-gray-300 file:border-0 file:rounded file:px-3 file:py-1">
    </div>
    <div>
      <label for="collection" class="block text-sm font-medium text-gray-300 mb-1">Collection</label>
      <select name="collection" id="collection" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none">
        <option value="">None</option>
        {% for c in collections %}
        <option value="{{ c.pk }}" {% if post.collection_id == c.pk %}selected{% endif %}>{{ c.name }}</option>
        {% endfor %}
      </select>
    </div>
    <div>
      <label for="tags" class="block text-sm font-medium text-gray-300 mb-1">Tags (comma-separated)</label>
      <input type="text" name="tags" id="tags" value="{% for t in post.tags.all %}{{ t.name }}{% if not forloop.last %}, {% endif %}{% endfor %}" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none">
    </div>
    <div class="flex items-center gap-2">
      <input type="checkbox" name="is_collaborative" id="is_collaborative" {% if post.is_collaborative %}checked{% endif %} class="rounded bg-gray-800 border-gray-600 text-ch-gold focus:ring-ch-gold">
      <label for="is_collaborative" class="text-sm text-gray-300">Looking for collaborators</label>
    </div>
    <div class="flex gap-3">
      <button type="submit" name="status" value="{{ post.status }}" class="bg-ch-gold text-ch-darker px-6 py-2 rounded-lg font-semibold hover:bg-ch-gold/90 transition">Save</button>
      <a href="{% url 'studio_post_detail' post.pk %}" class="text-gray-400 px-4 py-2 hover:text-white transition">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

Create `templates/core/studio/post_confirm_delete.html`:

```html
{% extends 'base.html' %}
{% block title %}Delete: {{ post.title }}{% endblock %}
{% block content %}
<div class="max-w-lg mx-auto px-4 py-6">
  <h1 class="text-2xl font-bold text-white mb-4">Delete Post</h1>
  <div class="bg-red-900/20 border border-red-800 rounded-lg p-4 mb-6">
    <p class="text-red-300">Are you sure you want to delete <strong>"{{ post.title }}"</strong>? This cannot be undone.</p>
  </div>
  <form method="post">
    {% csrf_token %}
    <div class="flex gap-3">
      <button type="submit" class="bg-red-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-red-700 transition">Delete</button>
      <a href="{% url 'studio_post_detail' post.pk %}" class="text-gray-400 px-4 py-2 hover:text-white transition">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

Create `templates/core/studio/partials/reaction_bar.html`:

```html
<div id="reaction-bar" class="flex items-center gap-2 py-3 border-t border-b border-gray-800 mb-4">
  {% for rtype, emoji in reaction_choices %}
  <button hx-post="{% url 'studio_post_react' post.pk %}" hx-vals='{"reaction_type": "{{ rtype }}"}' hx-target="#reaction-bar" hx-swap="outerHTML" class="px-3 py-1 rounded-full text-sm {% if rtype in reaction_summary and reaction_summary|dictsort:"0" %}{% for key, val in reaction_summary.items %}{% if key == rtype and val.user_reacted %}bg-ch-gold/20 border border-ch-gold/50{% endif %}{% endfor %}{% else %}bg-gray-800{% endif %} hover:bg-gray-700 transition">
    {{ emoji }} {% for key, val in reaction_summary.items %}{% if key == rtype %}{{ val.count }}{% endif %}{% endfor %}
  </button>
  {% endfor %}
</div>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_creative_studio.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add core/studio_views.py core/urls.py templates/core/studio/ tests/test_creative_studio.py
git commit -m "feat(studio): add edit, delete, comment, react, and spotlight views"
```

---

### Task 6: Collection views

**Files:**
- Modify: `core/studio_views.py`
- Modify: `core/urls.py`
- Create: `templates/core/studio/collection_list.html`
- Create: `templates/core/studio/collection_detail.html`
- Create: `templates/core/studio/collection_create.html`
- Create: `templates/core/studio/collection_confirm_delete.html`
- Modify: `tests/test_creative_studio.py`

- [ ] **Step 1: Write failing tests for collection views**

```python
# tests/test_creative_studio.py (append)
class TestStudioCollectionViews:
    @pytest.fixture
    def client_alpha(self, db, user_alpha_owner, org_alpha):
        client = Client()
        client.force_login(user_alpha_owner)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    @pytest.fixture
    def member_client(self, db, user_alpha_member, org_alpha):
        client = Client()
        client.force_login(user_alpha_member)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    def test_collection_list(self, client_alpha, org_alpha, user_alpha_owner):
        CreativeCollection.objects.create(name='Easter 2026', organization=org_alpha, created_by=user_alpha_owner)
        response = client_alpha.get('/studio/collections/')
        assert response.status_code == 200
        assert 'Easter 2026' in response.content.decode()

    def test_create_collection(self, client_alpha, org_alpha):
        response = client_alpha.post('/studio/collections/create/', {
            'name': 'Songwriting Circle',
            'description': 'A place for songwriters',
        })
        assert response.status_code == 302
        assert CreativeCollection.objects.filter(name='Songwriting Circle', organization=org_alpha).exists()

    def test_create_collection_denied_for_member(self, member_client):
        response = member_client.post('/studio/collections/create/', {
            'name': 'Should Fail',
        })
        assert response.status_code == 403

    def test_collection_detail(self, client_alpha, org_alpha, user_alpha_owner):
        collection = CreativeCollection.objects.create(name='Easter 2026', organization=org_alpha, created_by=user_alpha_owner)
        CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='Easter Idea', status='published',
            collection=collection,
        )
        response = client_alpha.get(f'/studio/collections/{collection.pk}/')
        assert response.status_code == 200
        assert 'Easter Idea' in response.content.decode()

    def test_delete_collection(self, client_alpha, org_alpha, user_alpha_owner):
        collection = CreativeCollection.objects.create(name='To Delete', organization=org_alpha, created_by=user_alpha_owner)
        response = client_alpha.post(f'/studio/collections/{collection.pk}/delete/')
        assert response.status_code == 302
        assert not CreativeCollection.objects.filter(pk=collection.pk).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_creative_studio.py::TestStudioCollectionViews -v`
Expected: FAIL

- [ ] **Step 3: Add collection views to `core/studio_views.py`**

```python
# Append to core/studio_views.py

@login_required
def studio_collection_list(request):
    """Browse all collections."""
    org = get_org(request)
    if not org:
        return redirect('dashboard')
    collections = CreativeCollection.objects.filter(
        organization=org, is_archived=False,
    ).annotate(post_count=Count('posts', filter=Q(posts__status='published')))
    membership = get_membership(request)
    context = {
        'collections': collections,
        'can_manage': is_leader_or_above(membership),
    }
    return render(request, 'core/studio/collection_list.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def studio_collection_create(request):
    """Create a new collection (leader/admin/owner only)."""
    org = get_org(request)
    membership = get_membership(request)
    if not is_leader_or_above(membership):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '')
        if name:
            CreativeCollection.objects.create(
                name=name, description=description,
                organization=org, created_by=request.user,
            )
            return redirect('studio_collection_list')

    return render(request, 'core/studio/collection_create.html')


@login_required
def studio_collection_detail(request, pk):
    """View posts within a collection."""
    org = get_org(request)
    collection = get_object_or_404(CreativeCollection, pk=pk, organization=org)
    posts = CreativePost.objects.filter(
        collection=collection, status='published',
    ).select_related('author').prefetch_related('tags', 'reactions', 'comments').annotate(
        comment_count=Count('comments'),
        build_count=Count('builds', filter=Q(builds__status='published')),
    )
    membership = get_membership(request)
    context = {
        'collection': collection,
        'posts': posts,
        'can_manage': is_leader_or_above(membership),
        'post_type_choices': CreativePost.POST_TYPE_CHOICES,
    }
    return render(request, 'core/studio/collection_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def studio_collection_edit(request, pk):
    """Edit a collection (leader/admin/owner only)."""
    org = get_org(request)
    membership = get_membership(request)
    if not is_leader_or_above(membership):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    collection = get_object_or_404(CreativeCollection, pk=pk, organization=org)

    if request.method == 'POST':
        collection.name = request.POST.get('name', collection.name).strip()
        collection.description = request.POST.get('description', collection.description)
        collection.save()
        return redirect('studio_collection_detail', pk=collection.pk)

    return render(request, 'core/studio/collection_create.html', {'collection': collection})


@login_required
@require_http_methods(["GET", "POST"])
def studio_collection_delete(request, pk):
    """Delete a collection (leader/admin/owner only)."""
    org = get_org(request)
    membership = get_membership(request)
    if not is_leader_or_above(membership):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    collection = get_object_or_404(CreativeCollection, pk=pk, organization=org)

    if request.method == 'POST':
        collection.delete()
        return redirect('studio_collection_list')

    return render(request, 'core/studio/collection_confirm_delete.html', {'collection': collection})
```

- [ ] **Step 4: Add URL patterns**

In `core/urls.py`, add after existing studio URLs:

```python
    path('studio/collections/', studio_views.studio_collection_list, name='studio_collection_list'),
    path('studio/collections/create/', studio_views.studio_collection_create, name='studio_collection_create'),
    path('studio/collections/<int:pk>/', studio_views.studio_collection_detail, name='studio_collection_detail'),
    path('studio/collections/<int:pk>/edit/', studio_views.studio_collection_edit, name='studio_collection_edit'),
    path('studio/collections/<int:pk>/delete/', studio_views.studio_collection_delete, name='studio_collection_delete'),
```

- [ ] **Step 5: Create collection templates**

Create `templates/core/studio/collection_list.html`:

```html
{% extends 'base.html' %}
{% block title %}Collections — Creative Studio{% endblock %}
{% block content %}
<div class="max-w-4xl mx-auto px-4 py-6">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">Collections</h1>
    {% if can_manage %}
    <a href="{% url 'studio_collection_create' %}" class="bg-ch-gold text-ch-darker px-4 py-2 rounded-lg font-semibold hover:bg-ch-gold/90 transition">+ New Collection</a>
    {% endif %}
  </div>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {% for collection in collections %}
    <a href="{% url 'studio_collection_detail' collection.pk %}" class="bg-ch-dark rounded-lg p-5 border border-gray-800 hover:border-gray-600 transition">
      <h3 class="text-white font-semibold mb-1">{{ collection.name }}</h3>
      {% if collection.description %}<p class="text-gray-400 text-sm mb-2">{{ collection.description|truncatechars:100 }}</p>{% endif %}
      <p class="text-gray-500 text-xs">{{ collection.post_count }} post{{ collection.post_count|pluralize }}</p>
    </a>
    {% empty %}
    <p class="text-gray-400 col-span-3 text-center py-8">No collections yet</p>
    {% endfor %}
  </div>
</div>
{% endblock %}
```

Create `templates/core/studio/collection_detail.html`:

```html
{% extends 'base.html' %}
{% block title %}{{ collection.name }} — Creative Studio{% endblock %}
{% block content %}
<div class="max-w-4xl mx-auto px-4 py-6">
  <div class="text-sm text-gray-500 mb-4">
    <a href="{% url 'studio_feed' %}" class="hover:text-white">Creative Studio</a> › <a href="{% url 'studio_collection_list' %}" class="hover:text-white">Collections</a> › {{ collection.name }}
  </div>
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-2xl font-bold text-white">{{ collection.name }}</h1>
      {% if collection.description %}<p class="text-gray-400 mt-1">{{ collection.description }}</p>{% endif %}
    </div>
    {% if can_manage %}
    <div class="flex gap-2">
      <a href="{% url 'studio_collection_edit' collection.pk %}" class="text-gray-400 hover:text-white text-sm">Edit</a>
      <a href="{% url 'studio_collection_delete' collection.pk %}" class="text-red-400 hover:text-red-300 text-sm">Delete</a>
    </div>
    {% endif %}
  </div>
  <div class="space-y-4">
    {% for post in posts %}
    {% include 'core/studio/partials/post_card.html' %}
    {% empty %}
    <p class="text-gray-400 text-center py-8">No posts in this collection yet</p>
    {% endfor %}
  </div>
</div>
{% endblock %}
```

Create `templates/core/studio/collection_create.html`:

```html
{% extends 'base.html' %}
{% block title %}{% if collection %}Edit Collection{% else %}New Collection{% endif %}{% endblock %}
{% block content %}
<div class="max-w-lg mx-auto px-4 py-6">
  <h1 class="text-2xl font-bold text-white mb-6">{% if collection %}Edit Collection{% else %}New Collection{% endif %}</h1>
  <form method="post" class="space-y-6">
    {% csrf_token %}
    <div>
      <label for="name" class="block text-sm font-medium text-gray-300 mb-1">Name</label>
      <input type="text" name="name" id="name" value="{% if collection %}{{ collection.name }}{% endif %}" required class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none" placeholder="e.g., Easter 2026">
    </div>
    <div>
      <label for="description" class="block text-sm font-medium text-gray-300 mb-1">Description (optional)</label>
      <textarea name="description" id="description" rows="3" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:border-ch-gold focus:outline-none">{% if collection %}{{ collection.description }}{% endif %}</textarea>
    </div>
    <div class="flex gap-3">
      <button type="submit" class="bg-ch-gold text-ch-darker px-6 py-2 rounded-lg font-semibold hover:bg-ch-gold/90 transition">{% if collection %}Save{% else %}Create{% endif %}</button>
      <a href="{% url 'studio_collection_list' %}" class="text-gray-400 px-4 py-2 hover:text-white transition">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

Create `templates/core/studio/collection_confirm_delete.html`:

```html
{% extends 'base.html' %}
{% block title %}Delete: {{ collection.name }}{% endblock %}
{% block content %}
<div class="max-w-lg mx-auto px-4 py-6">
  <h1 class="text-2xl font-bold text-white mb-4">Delete Collection</h1>
  <div class="bg-red-900/20 border border-red-800 rounded-lg p-4 mb-6">
    <p class="text-red-300">Are you sure you want to delete <strong>"{{ collection.name }}"</strong>? Posts in this collection will not be deleted, but will become uncategorized.</p>
  </div>
  <form method="post">
    {% csrf_token %}
    <div class="flex gap-3">
      <button type="submit" class="bg-red-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-red-700 transition">Delete</button>
      <a href="{% url 'studio_collection_detail' collection.pk %}" class="text-gray-400 px-4 py-2 hover:text-white transition">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_creative_studio.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add core/studio_views.py core/urls.py templates/core/studio/ tests/test_creative_studio.py
git commit -m "feat(studio): add collection list, detail, create, edit, delete views"
```

---

### Task 7: Sidebar navigation

**Files:**
- Modify: `templates/base.html` (lines ~496 and ~603)

- [ ] **Step 1: Write failing test for sidebar nav**

```python
# tests/test_creative_studio.py (append)
class TestStudioNavigation:
    @pytest.fixture
    def client_alpha(self, db, user_alpha_owner, org_alpha):
        client = Client()
        client.force_login(user_alpha_owner)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    def test_studio_in_sidebar(self, client_alpha):
        response = client_alpha.get('/studio/')
        content = response.content.decode()
        assert 'Creative Studio' in content
        assert "studio_feed" in content or "/studio/" in content
```

- [ ] **Step 2: Add Creative Studio nav item to mobile sidebar**

In `templates/base.html`, find line 496 (the Knowledge Base `<a>` tag in mobile sidebar, right before `</nav>`). Insert before it:

```html
            <a href="{% url 'studio_feed' %}" @click="sidebarOpen = false" class="nav-link {% if 'studio' in request.resolver_match.url_name %}active{% endif %}">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"></path>
                </svg>
                Creative Studio
            </a>
```

- [ ] **Step 3: Add Creative Studio nav item to desktop sidebar**

In `templates/base.html`, find line 603 (the Knowledge Base `<a>` tag in desktop sidebar). Insert before it:

```html
            <a href="{% url 'studio_feed' %}" class="nav-link {% if 'studio' in request.resolver_match.url_name %}active{% endif %}">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"></path>
                </svg>
                Creative Studio
            </a>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_creative_studio.py::TestStudioNavigation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/base.html tests/test_creative_studio.py
git commit -m "feat(studio): add Creative Studio to sidebar navigation"
```

---

### Task 8: Embedding and related posts (Aria light integration)

**Files:**
- Modify: `core/embeddings.py`
- Modify: `core/studio_views.py`
- Modify: `tests/test_creative_studio.py`

- [ ] **Step 1: Write failing test for related posts search**

```python
# tests/test_creative_studio.py (append)
import json


class TestStudioRelatedPosts:
    def test_search_similar_posts(self, db, org_alpha, user_alpha_owner):
        post1 = CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='lyrics', title='Worship Song', status='published',
            embedding_json=json.dumps([0.1] * 1536),
        )
        post2 = CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='lyrics', title='Another Worship Song', status='published',
            embedding_json=json.dumps([0.1] * 1536),
        )
        post3 = CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='Stage Design Idea', status='published',
            embedding_json=json.dumps([0.9] * 1536),
        )

        from core.embeddings import search_similar_posts
        results = search_similar_posts([0.1] * 1536, organization=org_alpha, exclude_post_id=post1.pk, limit=2)
        assert len(results) <= 2
        # post2 should be more similar to post1 than post3
        if len(results) >= 1:
            assert results[0]['post_id'] == post2.pk
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_creative_studio.py::TestStudioRelatedPosts -v`
Expected: FAIL with `ImportError: cannot import name 'search_similar_posts'`

- [ ] **Step 3: Add `search_similar_posts` to `core/embeddings.py`**

Append to `core/embeddings.py`:

```python
def search_similar_posts(query_embedding: list[float], organization=None, exclude_post_id=None, limit: int = 3, threshold: float = 0.3):
    """
    Find creative posts most similar to query using cosine similarity.

    Returns: List of dicts with keys: 'post_id', 'title', 'post_type', 'similarity'
    """
    import json
    import math

    from core.models import CreativePost

    posts = CreativePost.objects.filter(
        status='published',
    ).exclude(embedding_json__isnull=True).exclude(embedding_json='')

    if organization:
        posts = posts.filter(organization=organization)
    if exclude_post_id:
        posts = posts.exclude(pk=exclude_post_id)

    results = []
    for post in posts:
        try:
            post_embedding = json.loads(post.embedding_json)
        except (json.JSONDecodeError, TypeError):
            continue

        # Cosine similarity
        dot_product = sum(a * b for a, b in zip(query_embedding, post_embedding))
        norm_a = math.sqrt(sum(a * a for a in query_embedding))
        norm_b = math.sqrt(sum(b * b for b in post_embedding))
        if norm_a == 0 or norm_b == 0:
            continue
        similarity = dot_product / (norm_a * norm_b)

        if similarity >= threshold:
            results.append({
                'post_id': post.pk,
                'title': post.title,
                'post_type': post.post_type,
                'similarity': similarity,
            })

    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:limit]
```

- [ ] **Step 4: Add embedding generation on publish in `studio_post_create`**

In `core/studio_views.py`, in `studio_post_create`, after the notification block inside the `if status == 'published':` branch, add:

```python
            # Generate embedding for related posts
            if post.content:
                from .embeddings import get_embedding
                import json
                embedding = get_embedding(post.content[:8000])
                if embedding:
                    post.embedding_json = json.dumps(embedding)
                    post.save(update_fields=['embedding_json'])
```

- [ ] **Step 5: Add related posts to detail view**

In `core/studio_views.py`, in `studio_post_detail`, add before the `context` dict:

```python
    # Related posts via embeddings
    related_posts = []
    if post.embedding_json:
        import json
        try:
            from .embeddings import search_similar_posts
            embedding = json.loads(post.embedding_json)
            related_posts = search_similar_posts(
                embedding, organization=org, exclude_post_id=post.pk, limit=3,
            )
        except (json.JSONDecodeError, TypeError):
            pass
```

And add `'related_posts': related_posts,` to the context dict.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_creative_studio.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add core/embeddings.py core/studio_views.py tests/test_creative_studio.py
git commit -m "feat(studio): add embedding-based related posts search"
```

---

### Task 9: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run the full existing test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All existing tests still pass (452+ existing + new studio tests), 0 failures

- [ ] **Step 2: Fix any regressions**

If any existing tests break (e.g., from URL changes or model migrations), fix them.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve any test regressions from creative studio feature"
```

---

### Task 10: Push notification preferences UI

**Files:**
- Modify: `templates/core/push_preferences.html` (or equivalent notification settings template)
- Modify: `tests/test_creative_studio.py`

- [ ] **Step 1: Find the push preferences template**

Run: `grep -r 'studio_new_posts\|notification.*studio' templates/` to check if any template already references studio prefs. If not, find the notification preferences form.

- [ ] **Step 2: Add studio notification toggles to the preferences form**

Find the existing notification preference toggles in the push preferences template and add after the song submissions toggle:

```html
<!-- Creative Studio Notifications -->
<div class="border-t border-gray-800 pt-4 mt-4">
    <h3 class="text-white font-semibold mb-3">Creative Studio</h3>
    <div class="space-y-3">
        <label class="flex items-center gap-3">
            <input type="checkbox" name="studio_new_posts" {% if prefs.studio_new_posts %}checked{% endif %} class="rounded bg-gray-800 border-gray-600 text-ch-gold focus:ring-ch-gold">
            <span class="text-gray-300 text-sm">New posts in Creative Studio</span>
        </label>
        <label class="flex items-center gap-3">
            <input type="checkbox" name="studio_comments" {% if prefs.studio_comments %}checked{% endif %} class="rounded bg-gray-800 border-gray-600 text-ch-gold focus:ring-ch-gold">
            <span class="text-gray-300 text-sm">Comments on my posts</span>
        </label>
        <label class="flex items-center gap-3">
            <input type="checkbox" name="studio_builds" {% if prefs.studio_builds %}checked{% endif %} class="rounded bg-gray-800 border-gray-600 text-ch-gold focus:ring-ch-gold">
            <span class="text-gray-300 text-sm">When someone builds on my post</span>
        </label>
        <label class="flex items-center gap-3">
            <input type="checkbox" name="studio_spotlights" {% if prefs.studio_spotlights %}checked{% endif %} class="rounded bg-gray-800 border-gray-600 text-ch-gold focus:ring-ch-gold">
            <span class="text-gray-300 text-sm">When my post is spotlighted</span>
        </label>
    </div>
</div>
```

- [ ] **Step 3: Update the push preferences view to save studio fields**

In the view that handles POST for notification preferences, add the 4 new fields to the save logic:

```python
prefs.studio_new_posts = 'studio_new_posts' in request.POST
prefs.studio_comments = 'studio_comments' in request.POST
prefs.studio_builds = 'studio_builds' in request.POST
prefs.studio_spotlights = 'studio_spotlights' in request.POST
```

- [ ] **Step 4: Run tests to verify everything still passes**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add templates/ core/views.py tests/
git commit -m "feat(studio): add studio notification preferences to settings UI"
```
