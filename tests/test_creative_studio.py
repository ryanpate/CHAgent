"""
Tests for Creative Studio models: CreativeTag, CreativeCollection, CreativePost.
"""
import pytest
from django.db import IntegrityError
from core.models import CreativeTag, CreativeCollection, CreativePost, CreativeComment, CreativeReaction


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


from core.models import NotificationPreference
from unittest.mock import patch


class TestStudioNotificationPreferences:
    def test_default_studio_preferences(self, db, user_alpha_owner):
        prefs = NotificationPreference.objects.create(user=user_alpha_owner)
        assert prefs.studio_new_posts is True
        assert prefs.studio_comments is True
        assert prefs.studio_builds is True
        assert prefs.studio_spotlights is True


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
    def test_notify_studio_spotlight(self, mock_send, published_post, user_alpha_member):
        from core.notifications import notify_studio_spotlight
        published_post.is_spotlighted = True
        published_post.spotlighted_by = user_alpha_member
        published_post.save()
        notify_studio_spotlight(published_post)
        mock_send.assert_called_once()
