"""
Views for the Cherry Hills Worship Arts Portal.
"""
import json
import uuid

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Count

from .models import Interaction, Volunteer, ChatMessage
from .agent import (
    query_agent,
    process_interaction,
    detect_interaction_intent,
    confirm_volunteer_match,
    skip_volunteer_match
)
from .volunteer_matching import VolunteerMatcher, MatchType


@login_required
def dashboard(request):
    """Dashboard view with overview statistics."""
    context = {
        'total_volunteers': Volunteer.objects.count(),
        'total_interactions': Interaction.objects.count(),
        'recent_interactions': Interaction.objects.select_related('user').prefetch_related('volunteers')[:5],
        'top_volunteers': Volunteer.objects.annotate(
            interaction_count=Count('interactions')
        ).order_by('-interaction_count')[:5],
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def chat(request):
    """Main chat interface view."""
    # Get or create session ID from cookie
    session_id = request.COOKIES.get('chat_session_id')
    if not session_id:
        session_id = str(uuid.uuid4())

    # Get chat messages for this session
    messages = ChatMessage.objects.filter(
        user=request.user,
        session_id=session_id
    ).order_by('created_at')

    response = render(request, 'core/chat.html', {
        'messages': messages,
        'session_id': session_id,
    })

    # Set session ID cookie if new
    if not request.COOKIES.get('chat_session_id'):
        response.set_cookie('chat_session_id', session_id, max_age=86400 * 7)  # 7 days

    return response


@login_required
@require_POST
def chat_send(request):
    """Handle chat message submission via HTMX."""
    message = request.POST.get('message', '').strip()
    session_id = request.COOKIES.get('chat_session_id', str(uuid.uuid4()))

    if not message:
        return HttpResponse('')

    # Detect if this is logging an interaction or asking a question
    is_interaction = detect_interaction_intent(message)

    pending_matches = []
    unmatched = []
    interaction_id = None

    if is_interaction:
        # Process as a new interaction
        result = process_interaction(message, request.user)
        interaction = result['interaction']
        volunteers = result['volunteers']
        pending_matches = result.get('pending_matches', [])
        unmatched = result.get('unmatched', [])
        interaction_id = interaction.id

        # Generate a confirmation response
        volunteer_names = ", ".join([v.name for v in volunteers]) if volunteers else None
        response_text = "I've logged your interaction.\n\n"
        if result.get('extracted', {}).get('summary'):
            response_text += f"**Summary:** {result['extracted']['summary']}\n\n"

        if volunteer_names:
            response_text += f"**Volunteers linked:** {volunteer_names}\n\n"

        # Note about pending/unmatched (will show UI below)
        if pending_matches or unmatched:
            response_text += "I found some names that need your input to match correctly."
        else:
            response_text += "Is there anything else you'd like to add or any questions about volunteers?"

        # Save to chat history
        ChatMessage.objects.create(
            user=request.user,
            session_id=session_id,
            role='user',
            content=message
        )
        ChatMessage.objects.create(
            user=request.user,
            session_id=session_id,
            role='assistant',
            content=response_text
        )
    else:
        # Process as a question using RAG
        response_text = query_agent(message, request.user, session_id)

    # Get the two most recent messages (user + assistant)
    recent_messages = ChatMessage.objects.filter(
        user=request.user,
        session_id=session_id
    ).order_by('-created_at')[:2]

    # Reverse to get chronological order
    recent_messages = list(reversed(recent_messages))

    # Prepare pending match data for template
    pending_match_data = []
    for match in pending_matches:
        match_data = {
            'name': match.name,
            'match_type': match.match_type.value,
            'score': int(match.score * 100),
            'suggested_name': match.pco_name or (match.volunteer.name if match.volunteer else match.name),
            'volunteer_id': match.volunteer.id if match.volunteer else None,
            'pco_id': match.pco_id,
            'alternatives': match.alternatives[:3] if match.alternatives else []
        }
        pending_match_data.append(match_data)

    return render(request, 'core/chat_message.html', {
        'messages': recent_messages,
        'pending_matches': pending_match_data,
        'unmatched': unmatched,
        'interaction_id': interaction_id,
    })


@login_required
@require_POST
def chat_new_session(request):
    """Start a new chat session."""
    new_session_id = str(uuid.uuid4())

    response = render(request, 'core/chat_empty.html')
    response.set_cookie('chat_session_id', new_session_id, max_age=86400 * 7)

    return response


@login_required
def interaction_list(request):
    """List all interactions with pagination."""
    interactions = Interaction.objects.select_related('user').prefetch_related('volunteers').all()

    # Simple search
    search_query = request.GET.get('q', '')
    if search_query:
        interactions = interactions.filter(content__icontains=search_query)

    context = {
        'interactions': interactions[:50],  # Limit for performance
        'search_query': search_query,
    }
    return render(request, 'core/interaction_list.html', context)


@login_required
def interaction_detail(request, pk):
    """View a single interaction."""
    interaction = get_object_or_404(
        Interaction.objects.select_related('user').prefetch_related('volunteers'),
        pk=pk
    )
    context = {
        'interaction': interaction,
    }
    return render(request, 'core/interaction_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def interaction_create(request):
    """Create a new interaction manually."""
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            result = process_interaction(content, request.user)
            return redirect('interaction_detail', pk=result['interaction'].pk)

    return render(request, 'core/interaction_create.html')


@login_required
def volunteer_list(request):
    """List all volunteers."""
    volunteers = Volunteer.objects.annotate(
        interaction_count=Count('interactions')
    ).order_by('name')

    # Simple search
    search_query = request.GET.get('q', '')
    if search_query:
        volunteers = volunteers.filter(name__icontains=search_query)

    # Filter by team
    team_filter = request.GET.get('team', '')
    if team_filter:
        volunteers = volunteers.filter(team=team_filter)

    # Get unique teams for filter dropdown
    teams = Volunteer.objects.exclude(team='').values_list('team', flat=True).distinct()

    context = {
        'volunteers': volunteers,
        'search_query': search_query,
        'team_filter': team_filter,
        'teams': teams,
    }
    return render(request, 'core/volunteer_list.html', context)


@login_required
def volunteer_detail(request, pk):
    """View a single volunteer's profile and interactions."""
    volunteer = get_object_or_404(Volunteer, pk=pk)
    interactions = volunteer.interactions.select_related('user').order_by('-created_at')

    # Aggregate extracted data from all interactions
    all_extracted_data = {}
    for interaction in interactions:
        if interaction.ai_extracted_data:
            for key, value in interaction.ai_extracted_data.items():
                if value:  # Only include non-empty values
                    if key not in all_extracted_data:
                        all_extracted_data[key] = []
                    if isinstance(value, list):
                        all_extracted_data[key].extend(value)
                    else:
                        all_extracted_data[key].append(value)

    context = {
        'volunteer': volunteer,
        'interactions': interactions[:20],
        'extracted_data': all_extracted_data,
    }
    return render(request, 'core/volunteer_detail.html', context)


@login_required
@require_POST
def volunteer_match_confirm(request):
    """
    Confirm a volunteer match for an interaction.

    HTMX endpoint that links a volunteer to an interaction based on user selection.
    """
    interaction_id = request.POST.get('interaction_id')
    original_name = request.POST.get('original_name', '')
    volunteer_id = request.POST.get('volunteer_id')
    pco_id = request.POST.get('pco_id')

    if not interaction_id:
        return HttpResponse('<span class="text-red-500">Error: Missing interaction ID</span>')

    # Confirm the match
    volunteer = confirm_volunteer_match(
        interaction_id=int(interaction_id),
        original_name=original_name,
        volunteer_id=int(volunteer_id) if volunteer_id else None,
        pco_id=pco_id if pco_id else None
    )

    if volunteer:
        return render(request, 'core/partials/match_confirmed.html', {
            'volunteer': volunteer,
            'original_name': original_name
        })
    else:
        return HttpResponse('<span class="text-red-500">Error: Could not link volunteer</span>')


@login_required
@require_POST
def volunteer_match_create(request):
    """
    Create a new volunteer for an unmatched name.

    HTMX endpoint that creates a new volunteer and links to interaction.
    """
    interaction_id = request.POST.get('interaction_id')
    original_name = request.POST.get('original_name', '').strip()
    team = request.POST.get('team', '')

    if not interaction_id or not original_name:
        return HttpResponse('<span class="text-red-500">Error: Missing required fields</span>')

    # Create new volunteer and link
    volunteer = confirm_volunteer_match(
        interaction_id=int(interaction_id),
        original_name=original_name,
        create_new=True
    )

    # Update team if provided
    if volunteer and team:
        volunteer.team = team
        volunteer.save()

    if volunteer:
        return render(request, 'core/partials/match_confirmed.html', {
            'volunteer': volunteer,
            'original_name': original_name,
            'created': True
        })
    else:
        return HttpResponse('<span class="text-red-500">Error: Could not create volunteer</span>')


@login_required
@require_POST
def volunteer_match_skip(request):
    """
    Skip matching a volunteer for an interaction.

    HTMX endpoint that dismisses a pending match without linking.
    """
    interaction_id = request.POST.get('interaction_id')
    original_name = request.POST.get('original_name', '')

    if interaction_id:
        skip_volunteer_match(int(interaction_id), original_name)

    return render(request, 'core/partials/match_skipped.html', {
        'original_name': original_name
    })
