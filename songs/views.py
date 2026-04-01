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


def song_dashboard(request):
    """Team song submission dashboard. Implemented in Task 4."""
    raise Http404


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
