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
        response = client_alpha.get(f'/studio/post/create/?parent={parent.pk}')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Re: Original' in content


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
        # Use alternating positive/negative values for a different direction
        different_embedding = [0.1 if i % 2 == 0 else -0.1 for i in range(1536)]
        post3 = CreativePost.objects.create(
            author=user_alpha_owner, organization=org_alpha,
            post_type='idea', title='Stage Design Idea', status='published',
            embedding_json=json.dumps(different_embedding),
        )

        from core.embeddings import search_similar_posts
        results = search_similar_posts([0.1] * 1536, organization=org_alpha, exclude_post_id=post1.pk, limit=2)
        assert len(results) <= 2
        # post2 should be more similar to post1 than post3
        if len(results) >= 1:
            assert results[0]['post_id'] == post2.pk
