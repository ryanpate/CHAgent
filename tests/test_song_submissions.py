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
