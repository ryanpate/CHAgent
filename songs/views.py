import logging
from django.db.models import Count, Avg, Q
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone

from core.models import Organization
from core.middleware import require_organization
from core.views import get_org
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

        # Send push notification to team (defer to Task 6)
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


@login_required
@require_organization
def song_dashboard(request):
    """Team dashboard for reviewing song submissions."""
    org = request.organization
    submissions = SongSubmission.objects.filter(organization=org)

    # Stats
    total_count = submissions.count()
    pending_count = submissions.filter(status='pending').count()
    approved_count = submissions.filter(status='approved').count()
    rejected_count = submissions.filter(status='rejected').count()
    reviewed_count = submissions.filter(status='reviewed').count()
    avg_rating = submissions.filter(vote_count__gt=0).aggregate(avg=Avg('average_rating'))['avg'] or 0.0

    # Insights
    top_rated_pending = submissions.filter(status='pending', vote_count__gt=0).order_by('-average_rating').first()
    most_submitted_artist = submissions.values('artist').annotate(count=Count('id')).order_by('-count').first()

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
    else:
        submissions = submissions.order_by('-created_at')

    # User votes for inline display
    user_votes = {}
    if request.user.is_authenticated:
        votes = SongVote.objects.filter(submission__organization=org, user=request.user).values_list('submission_id', 'rating')
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


@login_required
@require_organization
def song_detail(request, pk):
    """Detail page for a song submission."""
    org = get_org(request)
    submission = SongSubmission.objects.filter(organization=org, pk=pk).first()
    if not submission:
        raise Http404

    user_vote = SongVote.objects.filter(submission=submission, user=request.user).first()
    user_rating = user_vote.rating if user_vote else 0

    team_votes = submission.votes.select_related('user').order_by('-rating')

    similar = SongSubmission.objects.filter(
        organization=org, title__iexact=submission.title,
    ).exclude(pk=submission.pk)

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
        submission=submission, user=request.user,
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


def song_submit_thanks(request, org_slug):
    """Confirmation page after submission. Redirects to submit form."""
    org = Organization.objects.filter(slug=org_slug, is_active=True).first()
    if not org:
        raise Http404
    return redirect('song_submit', org_slug=org_slug)
