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


@pytest.mark.django_db
class TestSongDashboard:
    def test_dashboard_requires_auth(self):
        client = Client()
        response = client.get('/songs/')
        assert response.status_code == 302

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
