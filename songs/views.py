import logging
from django.db.models import Count, Avg, Q
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from core.models import Organization
from core.middleware import require_organization
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


def song_detail(request, pk):
    """Song submission detail page. Implemented in Task 5."""
    raise Http404


def song_vote(request, pk):
    """Vote on a song submission. Implemented in Task 5."""
    raise Http404


def song_update_status(request, pk):
    """Update song submission status. Implemented in Task 5."""
    raise Http404


def song_submit_thanks(request, org_slug):
    """Confirmation page after submission. Redirects to submit form."""
    org = Organization.objects.filter(slug=org_slug, is_active=True).first()
    if not org:
        raise Http404
    return redirect('song_submit', org_slug=org_slug)
