"""
Views for the Cherry Hills Worship Arts Portal.

All views are tenant-scoped - data is filtered by the current organization.
"""
import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone

from .models import Interaction, Volunteer, ChatMessage, ConversationContext, FollowUp, ResponseFeedback
from .middleware import require_organization
from .agent import (
    query_agent,
    process_interaction,
    detect_interaction_intent,
    confirm_volunteer_match,
    skip_volunteer_match
)
from .volunteer_matching import VolunteerMatcher, MatchType

import re


def get_org(request):
    """Helper to get organization from request, with fallback for migration period."""
    return getattr(request, 'organization', None)


def should_start_new_conversation(message: str) -> bool:
    """
    Determine if this message should start a fresh conversation.

    IMPORTANT: We now track conversation context across messages, so we should
    be LESS aggressive about starting new sessions. This allows:
    - Follow-up questions to work properly
    - Context deduplication (not repeating the same interactions)
    - Progressive conversation building

    Returns True ONLY for:
    - New interactions being logged (these are distinct events)
    - Explicit requests to start fresh
    """
    message_lower = message.lower().strip()

    # Only start new sessions for ACTUAL new interactions being logged
    # Questions and queries should continue the current conversation
    new_interaction_patterns = [
        r'^log\s+interaction',           # "Log interaction: ..."
        r'^log\s*:',                      # "Log: ..."
        r'^talked\s+(to|with)',           # "Talked to/with John..."
        r'^met\s+with',                   # "Met with Sarah..."
        r'^had\s+a\s+(conversation|chat|talk)', # "Had a conversation with..."
        r'^spoke\s+(to|with)',            # "Spoke to/with..."
        r'^chatted\s+with',               # "Chatted with..."
    ]

    for pattern in new_interaction_patterns:
        if re.search(pattern, message_lower):
            return True

    return False


def home(request):
    """
    Public landing page for unauthenticated users.
    Redirects to dashboard for authenticated users.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    from .models import SubscriptionPlan

    # Get plans for pricing section (order by actual DB field, not property)
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly_cents')

    context = {
        'plans': plans,
    }
    return render(request, 'core/landing.html', context)


def pricing(request):
    """
    Public pricing page showing all subscription plans.
    """
    from .models import SubscriptionPlan

    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly_cents')

    context = {
        'plans': plans,
    }
    return render(request, 'core/pricing.html', context)


@login_required
def dashboard(request):
    """Dashboard view with overview statistics and AI chat interface."""
    org = get_org(request)

    # Get or create session ID from cookie for chat
    session_id = request.COOKIES.get('chat_session_id')
    if not session_id:
        session_id = str(uuid.uuid4())

    # Get chat messages for this session (scoped to user and organization)
    chat_messages = ChatMessage.objects.filter(
        user=request.user,
        session_id=session_id
    )
    if org:
        chat_messages = chat_messages.filter(organization=org)
    chat_messages = chat_messages.order_by('created_at')

    # Build base querysets scoped to organization
    volunteer_qs = Volunteer.objects.all()
    interaction_qs = Interaction.objects.all()
    if org:
        volunteer_qs = volunteer_qs.filter(organization=org)
        interaction_qs = interaction_qs.filter(organization=org)

    context = {
        'total_volunteers': volunteer_qs.count(),
        'total_interactions': interaction_qs.count(),
        'recent_interactions': interaction_qs.select_related('user').prefetch_related('volunteers')[:5],
        'top_volunteers': volunteer_qs.annotate(
            interaction_count=Count('interactions')
        ).order_by('-interaction_count')[:5],
        'chat_messages': chat_messages,
        'session_id': session_id,
    }

    response = render(request, 'core/dashboard.html', context)

    # Set session ID cookie if new
    if not request.COOKIES.get('chat_session_id'):
        response.set_cookie('chat_session_id', session_id, max_age=86400 * 7)  # 7 days

    return response


@login_required
def chat(request):
    """Redirect to dashboard where chat is now integrated."""
    return redirect('dashboard')


@login_required
@require_POST
def chat_send(request):
    """Handle chat message submission via HTMX."""
    from .agent import handle_followup_response, detect_followup_opportunities
    from .models import ConversationContext

    message = request.POST.get('message', '').strip()
    session_id = request.COOKIES.get('chat_session_id', str(uuid.uuid4()))
    org = get_org(request)

    if not message:
        return HttpResponse('')

    # Check if this message should start a new conversation
    # This keeps the chat window clean and focused on one topic at a time
    start_new_session = should_start_new_conversation(message)
    if start_new_session:
        session_id = str(uuid.uuid4())

    # Check if we're in a follow-up creation flow
    followup_response = handle_followup_response(message, session_id, request.user, organization=org)
    if followup_response:
        # Save user message
        ChatMessage.objects.create(
            user=request.user,
            organization=org,
            session_id=session_id,
            role='user',
            content=message
        )
        # Save assistant response
        ChatMessage.objects.create(
            user=request.user,
            organization=org,
            session_id=session_id,
            role='assistant',
            content=followup_response
        )
        # Return the messages
        recent_messages = ChatMessage.objects.filter(
            user=request.user,
            session_id=session_id
        ).order_by('-created_at')[:2]
        recent_messages = list(reversed(recent_messages))

        return render(request, 'core/chat_message.html', {
            'chat_messages': recent_messages,
            'pending_matches': [],
            'unmatched': [],
            'interaction_id': None,
            'new_session': False,
        })

    # Detect if this is logging an interaction or asking a question
    is_interaction = detect_interaction_intent(message)

    pending_matches = []
    unmatched = []
    interaction_id = None

    if is_interaction:
        # Process as a new interaction
        result = process_interaction(message, request.user, organization=org)
        interaction = result['interaction']
        volunteers = result['volunteers']
        pending_matches = result.get('pending_matches', [])
        unmatched = result.get('unmatched', [])
        interaction_id = interaction.id

        # Generate a confirmation response
        volunteer_names_list = [v.name for v in volunteers] if volunteers else []
        volunteer_names = ", ".join(volunteer_names_list) if volunteer_names_list else None
        response_text = "I've logged your interaction.\n\n"
        if result.get('extracted', {}).get('summary'):
            response_text += f"**Summary:** {result['extracted']['summary']}\n\n"

        if volunteer_names:
            response_text += f"**Volunteers linked:** {volunteer_names}\n\n"

        # Note about pending/unmatched (will show UI below)
        if pending_matches or unmatched:
            response_text += "I found some names that need your input to match correctly.\n\n"

        # Detect follow-up opportunities
        followup_opportunity = detect_followup_opportunities(message, volunteer_names_list)
        if followup_opportunity.get('has_followup'):
            # Store pending follow-up in conversation context
            context, _ = ConversationContext.objects.get_or_create(
                session_id=session_id,
                defaults={'organization': org, 'user': request.user}
            )
            context.pending_followup = {
                'state': 'awaiting_confirmation',
                'title': followup_opportunity.get('title', 'Follow-up needed'),
                'description': followup_opportunity.get('description', ''),
                'category': followup_opportunity.get('category', 'action_item'),
                'priority': followup_opportunity.get('priority', 'medium'),
                'volunteer_name': followup_opportunity.get('volunteer_name', ''),
                'interaction_id': interaction.id
            }
            context.save()

            # Add follow-up suggestion to response
            category_display = followup_opportunity.get('category', 'action_item').replace('_', ' ').title()
            response_text += f"---\n\n**Potential Follow-up Detected**\n\n"
            response_text += f"I noticed something that might need follow-up:\n\n"
            response_text += f"**{followup_opportunity.get('title')}**\n"
            response_text += f"*{followup_opportunity.get('reason')}*\n\n"
            response_text += f"Would you like me to create a follow-up reminder for this?"
        else:
            response_text += "Is there anything else you'd like to add or any questions about volunteers?"

        # Save to chat history
        ChatMessage.objects.create(
            user=request.user,
            organization=org,
            session_id=session_id,
            role='user',
            content=message
        )
        ChatMessage.objects.create(
            user=request.user,
            organization=org,
            session_id=session_id,
            role='assistant',
            content=response_text
        )
    else:
        # Process as a question using RAG
        organization = getattr(request, 'organization', None)
        response_text = query_agent(message, request.user, session_id, organization=organization)

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

    response = render(request, 'core/chat_message.html', {
        'chat_messages': recent_messages,
        'pending_matches': pending_match_data,
        'unmatched': unmatched,
        'interaction_id': interaction_id,
        'new_session': start_new_session,
    })

    # Update session cookie and swap behavior if we started a new conversation
    if start_new_session:
        response.set_cookie('chat_session_id', session_id, max_age=86400 * 7)
        # Tell HTMX to replace content instead of appending
        response['HX-Reswap'] = 'innerHTML'

    return response


@login_required
@require_POST
def chat_new_session(request):
    """Start a new chat session and clear conversation context."""
    # Get the old session ID to clean up its context
    old_session_id = request.COOKIES.get('chat_session_id')
    if old_session_id:
        # Clear the old conversation context (optional: could delete instead)
        try:
            old_context = ConversationContext.objects.get(session_id=old_session_id)
            old_context.clear_context()
            old_context.save()
        except ConversationContext.DoesNotExist:
            pass

    new_session_id = str(uuid.uuid4())

    response = render(request, 'core/chat_empty.html')
    response.set_cookie('chat_session_id', new_session_id, max_age=86400 * 7)

    return response


@login_required
@require_POST
def chat_feedback(request):
    """
    Handle feedback submission for AI responses.

    For positive feedback: Creates record directly
    For negative feedback: Shows issue reporting form
    """
    message_id = request.POST.get('message_id')
    feedback_type = request.POST.get('feedback_type', 'positive')

    if not message_id:
        return HttpResponse('<span class="text-red-500 text-xs">Error</span>')

    try:
        chat_message = ChatMessage.objects.get(pk=int(message_id), role='assistant')
    except ChatMessage.DoesNotExist:
        return HttpResponse('<span class="text-red-500 text-xs">Error</span>')

    # For cancel, restore the feedback buttons
    if feedback_type == 'cancel':
        return render(request, 'core/partials/feedback_buttons.html', {
            'message_id': message_id,
        })

    # For negative feedback, show the issue reporting form
    if feedback_type == 'negative':
        return render(request, 'core/partials/issue_report_form.html', {
            'message_id': message_id,
            'issue_types': ResponseFeedback.ISSUE_TYPE_CHOICES,
        })

    # For positive feedback, submit directly
    existing_feedback = ResponseFeedback.objects.filter(chat_message=chat_message).first()
    if existing_feedback:
        existing_feedback.feedback_type = feedback_type
        existing_feedback.save()
    else:
        ResponseFeedback.objects.create(
            chat_message=chat_message,
            user=request.user,
            feedback_type=feedback_type
        )

    # Store the query pattern for learning
    try:
        from .models import QueryPattern
        user_message = ChatMessage.objects.filter(
            user=chat_message.user,
            session_id=chat_message.session_id,
            role='user',
            created_at__lt=chat_message.created_at
        ).order_by('-created_at').first()

        if user_message:
            normalized = QueryPattern.normalize_query(user_message.content)
            existing_pattern = QueryPattern.objects.filter(
                normalized_query=normalized
            ).first()

            if existing_pattern:
                existing_pattern.record_match(was_successful=True)
            else:
                QueryPattern.objects.create(
                    query_text=user_message.content,
                    normalized_query=normalized,
                    detected_intent='general',
                    extracted_entities={}
                )
    except Exception:
        pass

    return render(request, 'core/partials/feedback_response.html', {
        'feedback_type': feedback_type
    })


@login_required
@require_POST
def chat_feedback_submit(request):
    """
    Handle issue report form submission for negative feedback.

    Creates a ResponseFeedback record with issue details.
    """
    message_id = request.POST.get('message_id')
    issue_type = request.POST.get('issue_type', '')
    expected_result = request.POST.get('expected_result', '')
    comment = request.POST.get('comment', '')

    if not message_id:
        return HttpResponse('<span class="text-red-500 text-xs">Error</span>')

    try:
        chat_message = ChatMessage.objects.get(pk=int(message_id), role='assistant')
    except ChatMessage.DoesNotExist:
        return HttpResponse('<span class="text-red-500 text-xs">Error</span>')

    # Check if feedback already exists
    existing_feedback = ResponseFeedback.objects.filter(chat_message=chat_message).first()
    if existing_feedback:
        existing_feedback.feedback_type = 'negative'
        existing_feedback.issue_type = issue_type
        existing_feedback.expected_result = expected_result
        existing_feedback.comment = comment
        existing_feedback.save()
    else:
        ResponseFeedback.objects.create(
            chat_message=chat_message,
            user=request.user,
            feedback_type='negative',
            issue_type=issue_type,
            expected_result=expected_result,
            comment=comment
        )

    return render(request, 'core/partials/feedback_response.html', {
        'feedback_type': 'negative',
        'submitted': True
    })


@login_required
def feedback_dashboard(request):
    """
    Dashboard for admins to review feedback and reported issues.

    Shows all feedback with filtering options for issue types and resolution status.
    """
    org = get_org(request)

    # Get filter parameters
    filter_type = request.GET.get('type', 'all')  # all, positive, negative
    filter_resolved = request.GET.get('resolved', 'all')  # all, yes, no
    filter_issue = request.GET.get('issue', '')  # specific issue type

    # Base queryset (scoped to organization)
    feedbacks = ResponseFeedback.objects.select_related(
        'chat_message', 'user', 'resolved_by'
    )
    if org:
        feedbacks = feedbacks.filter(organization=org)
    feedbacks = feedbacks.order_by('-created_at')

    # Apply filters
    if filter_type == 'positive':
        feedbacks = feedbacks.filter(feedback_type='positive')
    elif filter_type == 'negative':
        feedbacks = feedbacks.filter(feedback_type='negative')

    if filter_resolved == 'yes':
        feedbacks = feedbacks.filter(resolved=True)
    elif filter_resolved == 'no':
        feedbacks = feedbacks.filter(resolved=False)

    if filter_issue:
        feedbacks = feedbacks.filter(issue_type=filter_issue)

    # Get counts for stats (scoped to organization)
    base_feedback_qs = ResponseFeedback.objects.all()
    if org:
        base_feedback_qs = base_feedback_qs.filter(organization=org)

    total_count = base_feedback_qs.count()
    positive_count = base_feedback_qs.filter(feedback_type='positive').count()
    negative_count = base_feedback_qs.filter(feedback_type='negative').count()
    unresolved_count = base_feedback_qs.filter(
        feedback_type='negative', resolved=False
    ).count()

    # Get user questions for each feedback
    feedback_with_questions = []
    for feedback in feedbacks[:100]:  # Limit for performance
        user_question = None
        if feedback.chat_message:
            user_msg = ChatMessage.objects.filter(
                user=feedback.chat_message.user,
                session_id=feedback.chat_message.session_id,
                role='user',
                created_at__lt=feedback.chat_message.created_at
            ).order_by('-created_at').first()
            if user_msg:
                user_question = user_msg.content
        feedback_with_questions.append({
            'feedback': feedback,
            'user_question': user_question,
        })

    context = {
        'feedbacks': feedback_with_questions,
        'filter_type': filter_type,
        'filter_resolved': filter_resolved,
        'filter_issue': filter_issue,
        'issue_types': ResponseFeedback.ISSUE_TYPE_CHOICES,
        'total_count': total_count,
        'positive_count': positive_count,
        'negative_count': negative_count,
        'unresolved_count': unresolved_count,
    }
    return render(request, 'core/feedback_dashboard.html', context)


@login_required
@require_POST
def feedback_resolve(request, pk):
    """Mark a feedback item as resolved."""
    from django.utils import timezone

    org = get_org(request)

    queryset = ResponseFeedback.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    feedback = get_object_or_404(queryset, pk=pk)
    feedback.resolved = True
    feedback.resolved_by = request.user
    feedback.resolved_at = timezone.now()
    feedback.resolution_notes = request.POST.get('resolution_notes', '')
    feedback.save()

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/feedback_row.html', {
            'item': {
                'feedback': feedback,
                'user_question': None,  # Will be fetched if needed
            }
        })
    return redirect('feedback_dashboard')


@login_required
def interaction_list(request):
    """List all interactions grouped by volunteer."""
    from collections import defaultdict

    org = get_org(request)

    interactions = Interaction.objects.select_related('user').prefetch_related('volunteers')
    if org:
        interactions = interactions.filter(organization=org)

    # Simple search
    search_query = request.GET.get('q', '')
    if search_query:
        interactions = interactions.filter(content__icontains=search_query)

    interactions = interactions.order_by('-created_at')[:100]  # Limit for performance

    # Group interactions by volunteer
    volunteer_interactions = defaultdict(list)
    unassigned_interactions = []

    for interaction in interactions:
        volunteers = list(interaction.volunteers.all())
        if volunteers:
            for volunteer in volunteers:
                volunteer_interactions[volunteer].append(interaction)
        else:
            unassigned_interactions.append(interaction)

    # Sort volunteers by name and convert to list of tuples
    grouped_interactions = sorted(
        volunteer_interactions.items(),
        key=lambda x: x[0].name.lower()
    )

    context = {
        'grouped_interactions': grouped_interactions,
        'unassigned_interactions': unassigned_interactions,
        'search_query': search_query,
        'total_interactions': len(interactions),
    }
    return render(request, 'core/interaction_list.html', context)


@login_required
def interaction_detail(request, pk):
    """View a single interaction."""
    org = get_org(request)

    queryset = Interaction.objects.select_related('user').prefetch_related('volunteers')
    if org:
        queryset = queryset.filter(organization=org)

    interaction = get_object_or_404(queryset, pk=pk)
    context = {
        'interaction': interaction,
    }
    return render(request, 'core/interaction_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def interaction_create(request):
    """Create a new interaction manually."""
    org = get_org(request)

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            result = process_interaction(content, request.user, organization=org)
            return redirect('interaction_detail', pk=result['interaction'].pk)

    return render(request, 'core/interaction_create.html')


@login_required
def volunteer_list(request):
    """List all volunteers."""
    org = get_org(request)

    volunteers = Volunteer.objects.all()
    if org:
        volunteers = volunteers.filter(organization=org)

    volunteers = volunteers.annotate(
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

    # Get unique teams for filter dropdown (scoped to org)
    teams_qs = Volunteer.objects.exclude(team='')
    if org:
        teams_qs = teams_qs.filter(organization=org)
    teams = teams_qs.values_list('team', flat=True).distinct()

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
    org = get_org(request)

    queryset = Volunteer.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    volunteer = get_object_or_404(queryset, pk=pk)
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


# ============================================================================
# Follow-up Views
# ============================================================================

@login_required
def followup_list(request):
    """List all follow-ups with filtering options."""
    from django.utils import timezone
    from datetime import timedelta

    org = get_org(request)

    # Get filter parameters
    status_filter = request.GET.get('status', 'pending')
    priority_filter = request.GET.get('priority', '')
    date_filter = request.GET.get('date', '')

    # Base queryset (scoped to organization)
    followups = FollowUp.objects.select_related('volunteer', 'created_by', 'assigned_to')
    if org:
        followups = followups.filter(organization=org)

    # Apply status filter
    if status_filter and status_filter != 'all':
        followups = followups.filter(status=status_filter)

    # Apply priority filter
    if priority_filter:
        followups = followups.filter(priority=priority_filter)

    # Apply date filter
    today = timezone.now().date()
    if date_filter == 'overdue':
        followups = followups.filter(follow_up_date__lt=today, status='pending')
    elif date_filter == 'today':
        followups = followups.filter(follow_up_date=today)
    elif date_filter == 'this_week':
        week_end = today + timedelta(days=7)
        followups = followups.filter(follow_up_date__gte=today, follow_up_date__lte=week_end)
    elif date_filter == 'no_date':
        followups = followups.filter(follow_up_date__isnull=True)

    # Get counts for sidebar/stats (scoped to organization)
    base_qs = FollowUp.objects.all()
    if org:
        base_qs = base_qs.filter(organization=org)

    overdue_count = base_qs.filter(
        follow_up_date__lt=today,
        status='pending'
    ).count()
    today_count = base_qs.filter(
        follow_up_date=today,
        status='pending'
    ).count()
    pending_count = base_qs.filter(status='pending').count()

    # Volunteers dropdown (scoped to organization)
    volunteers_qs = Volunteer.objects.all()
    if org:
        volunteers_qs = volunteers_qs.filter(organization=org)

    context = {
        'followups': followups[:50],
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'date_filter': date_filter,
        'overdue_count': overdue_count,
        'today_count': today_count,
        'pending_count': pending_count,
        'volunteers': volunteers_qs[:100],  # For the create form dropdown
    }
    return render(request, 'core/followup_list.html', context)


@login_required
def followup_detail(request, pk):
    """View details of a single follow-up."""
    org = get_org(request)

    queryset = FollowUp.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    followup = get_object_or_404(queryset, pk=pk)
    context = {
        'followup': followup,
    }
    return render(request, 'core/followup_detail.html', context)


@login_required
@require_POST
def followup_create(request):
    """Create a new follow-up."""
    from django.utils import timezone
    from datetime import datetime

    org = get_org(request)

    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    volunteer_id = request.POST.get('volunteer_id')
    follow_up_date_str = request.POST.get('follow_up_date', '')
    priority = request.POST.get('priority', 'medium')
    category = request.POST.get('category', '')

    if not title:
        if request.headers.get('HX-Request'):
            return HttpResponse('<div class="text-red-500">Error: Title is required</div>')
        return redirect('followup_list')

    # Parse follow-up date if provided
    follow_up_date = None
    if follow_up_date_str:
        try:
            follow_up_date = datetime.strptime(follow_up_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # Get volunteer if specified (scoped to organization)
    volunteer = None
    if volunteer_id:
        try:
            queryset = Volunteer.objects.all()
            if org:
                queryset = queryset.filter(organization=org)
            volunteer = queryset.get(pk=int(volunteer_id))
        except (ValueError, Volunteer.DoesNotExist):
            pass

    followup = FollowUp.objects.create(
        organization=org,
        created_by=request.user,
        title=title,
        description=description,
        volunteer=volunteer,
        follow_up_date=follow_up_date,
        priority=priority,
        category=category
    )

    if request.headers.get('HX-Request'):
        # Return the new follow-up row for HTMX
        return render(request, 'core/partials/followup_row.html', {'followup': followup})

    return redirect('followup_list')


@login_required
@require_POST
def followup_complete(request, pk):
    """Mark a follow-up as completed."""
    org = get_org(request)

    queryset = FollowUp.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    followup = get_object_or_404(queryset, pk=pk)
    notes = request.POST.get('notes', '')
    followup.mark_completed(notes)

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/followup_row.html', {'followup': followup})

    return redirect('followup_list')


@login_required
@require_POST
def followup_update(request, pk):
    """Update a follow-up's details."""
    from datetime import datetime

    org = get_org(request)

    queryset = FollowUp.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    followup = get_object_or_404(queryset, pk=pk)

    # Update fields if provided
    if 'title' in request.POST:
        followup.title = request.POST['title'].strip()
    if 'description' in request.POST:
        followup.description = request.POST['description'].strip()
    if 'priority' in request.POST:
        followup.priority = request.POST['priority']
    if 'status' in request.POST:
        followup.status = request.POST['status']
    if 'follow_up_date' in request.POST:
        date_str = request.POST['follow_up_date']
        if date_str:
            try:
                followup.follow_up_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            followup.follow_up_date = None
    if 'volunteer_id' in request.POST:
        vol_id = request.POST['volunteer_id']
        if vol_id:
            try:
                vol_qs = Volunteer.objects.all()
                if org:
                    vol_qs = vol_qs.filter(organization=org)
                followup.volunteer = vol_qs.get(pk=int(vol_id))
            except (ValueError, Volunteer.DoesNotExist):
                pass
        else:
            followup.volunteer = None

    followup.save()

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/followup_row.html', {'followup': followup})

    return redirect('followup_detail', pk=pk)


@login_required
@require_POST
def followup_delete(request, pk):
    """Delete a follow-up."""
    org = get_org(request)

    queryset = FollowUp.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    followup = get_object_or_404(queryset, pk=pk)
    followup.delete()

    if request.headers.get('HX-Request'):
        return HttpResponse('')  # Empty response removes the row

    return redirect('followup_list')


# ============================================================================
# Analytics and Reporting Views
# ============================================================================

@login_required
def analytics_dashboard(request):
    """
    Main analytics dashboard with overview metrics and quick links to reports.
    """
    from .reports import ReportGenerator, serialize_for_json
    from .models import ReportCache

    org = get_org(request)

    # Parse date range from request
    days = int(request.GET.get('days', 30))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    # Include org in cache params for multi-tenant isolation
    cache_params = {'days': days, 'org_id': org.id if org else None}
    cached = ReportCache.get_cached_report('dashboard_summary', cache_params)

    if cached:
        summary = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to, organization=org)
        summary = serialize_for_json(generator.dashboard_summary())
        # Cache for 15 minutes
        ReportCache.set_cached_report('dashboard_summary', summary, cache_params, ttl_minutes=15)

    # Get quick team care insights
    care_cached = ReportCache.get_cached_report('team_care', cache_params)
    if care_cached:
        care_report = care_cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to, organization=org)
        care_report = serialize_for_json(generator.team_care_report())
        ReportCache.set_cached_report('team_care', care_report, cache_params, ttl_minutes=15)

    context = {
        'summary': summary,
        'care_report': care_report,
        'days': days,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'core/analytics/dashboard.html', context)


@login_required
def analytics_volunteer_engagement(request):
    """
    Detailed volunteer engagement report.
    """
    from .reports import ReportGenerator, serialize_for_json
    from .models import ReportCache

    org = get_org(request)

    days = int(request.GET.get('days', 90))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    cache_params = {'days': days, 'org_id': org.id if org else None}
    cached = ReportCache.get_cached_report('volunteer_engagement', cache_params)

    if cached:
        report = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to, organization=org)
        report = serialize_for_json(generator.volunteer_engagement_report())
        ReportCache.set_cached_report('volunteer_engagement', report, cache_params, ttl_minutes=30)

    context = {
        'report': report,
        'days': days,
    }
    return render(request, 'core/analytics/volunteer_engagement.html', context)


@login_required
def analytics_team_care(request):
    """
    Team care report - volunteers needing attention.
    """
    from .reports import ReportGenerator, serialize_for_json
    from .models import ReportCache

    org = get_org(request)

    days = int(request.GET.get('days', 30))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    cache_params = {'days': days, 'org_id': org.id if org else None}
    cached = ReportCache.get_cached_report('team_care', cache_params)

    if cached:
        report = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to, organization=org)
        report = serialize_for_json(generator.team_care_report())
        ReportCache.set_cached_report('team_care', report, cache_params, ttl_minutes=15)

    context = {
        'report': report,
        'days': days,
    }
    return render(request, 'core/analytics/team_care.html', context)


@login_required
def analytics_interaction_trends(request):
    """
    Interaction trends over time.
    """
    from .reports import ReportGenerator, serialize_for_json
    from .models import ReportCache

    org = get_org(request)

    days = int(request.GET.get('days', 90))
    group_by = request.GET.get('group_by', 'week')
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    cache_params = {'days': days, 'group_by': group_by, 'org_id': org.id if org else None}
    cached = ReportCache.get_cached_report('interaction_trends', cache_params)

    if cached:
        report = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to, organization=org)
        report = serialize_for_json(generator.interaction_trends_report(group_by=group_by))
        ReportCache.set_cached_report('interaction_trends', report, cache_params, ttl_minutes=30)

    context = {
        'report': report,
        'days': days,
        'group_by': group_by,
    }
    return render(request, 'core/analytics/interaction_trends.html', context)


@login_required
def analytics_prayer_requests(request):
    """
    Prayer request summary and themes.
    """
    from .reports import ReportGenerator, serialize_for_json
    from .models import ReportCache

    org = get_org(request)

    days = int(request.GET.get('days', 90))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    cache_params = {'days': days, 'org_id': org.id if org else None}
    cached = ReportCache.get_cached_report('prayer_summary', cache_params)

    if cached:
        report = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to, organization=org)
        report = serialize_for_json(generator.prayer_request_summary())
        ReportCache.set_cached_report('prayer_summary', report, cache_params, ttl_minutes=30)

    context = {
        'report': report,
        'days': days,
    }
    return render(request, 'core/analytics/prayer_requests.html', context)


@login_required
def analytics_ai_performance(request):
    """
    AI (Aria) performance metrics.
    """
    from .reports import ReportGenerator, serialize_for_json
    from .models import ReportCache

    org = get_org(request)

    days = int(request.GET.get('days', 30))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    cache_params = {'days': days, 'org_id': org.id if org else None}
    cached = ReportCache.get_cached_report('ai_performance', cache_params)

    if cached:
        report = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to, organization=org)
        report = serialize_for_json(generator.ai_performance_report())
        ReportCache.set_cached_report('ai_performance', report, cache_params, ttl_minutes=15)

    context = {
        'report': report,
        'days': days,
    }
    return render(request, 'core/analytics/ai_performance.html', context)


@login_required
def analytics_export(request, report_type):
    """
    Export a report as JSON.
    """
    from .reports import ReportGenerator, serialize_for_json

    org = get_org(request)

    days = int(request.GET.get('days', 90))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    generator = ReportGenerator(date_from=date_from, date_to=date_to, organization=org)

    report_methods = {
        'volunteer_engagement': generator.volunteer_engagement_report,
        'team_care': generator.team_care_report,
        'interaction_trends': lambda: generator.interaction_trends_report(
            group_by=request.GET.get('group_by', 'week')
        ),
        'prayer_requests': generator.prayer_request_summary,
        'ai_performance': generator.ai_performance_report,
        'dashboard': generator.dashboard_summary,
    }

    if report_type not in report_methods:
        return JsonResponse({'error': 'Unknown report type'}, status=400)

    report_data = serialize_for_json(report_methods[report_type]())

    response = JsonResponse(report_data, json_dumps_params={'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.json"'
    return response


@login_required
@require_POST
def analytics_refresh_cache(request):
    """
    Refresh cached reports.
    """
    from .models import ReportCache

    report_type = request.POST.get('report_type')
    if report_type:
        ReportCache.clear_all(report_type=report_type)
    else:
        ReportCache.clear_all()

    if request.headers.get('HX-Request'):
        return HttpResponse('<span class="text-green-500">Cache cleared!</span>')

    return redirect('analytics_dashboard')


# ============================================================================
# Proactive Care Dashboard Views
# ============================================================================

@login_required
def care_dashboard(request):
    """
    Proactive care dashboard showing volunteers who need attention.

    Displays insights organized by priority and type, with quick actions
    for addressing each item.
    """
    from .reports import ProactiveCareGenerator, serialize_for_json
    from .models import VolunteerInsight

    org = get_org(request)

    # Generate new insights if requested
    if request.GET.get('refresh') == '1':
        generator = ProactiveCareGenerator(organization=org)
        generator.generate_all_insights()
        return redirect('care_dashboard')

    # Get dashboard data (scoped to organization)
    generator = ProactiveCareGenerator(organization=org)
    dashboard = serialize_for_json(generator.get_proactive_care_dashboard())

    # Get filter parameters
    filter_type = request.GET.get('type', '')
    filter_priority = request.GET.get('priority', '')

    # Filter insights if needed
    filtered_insights = []
    all_insights = (
        dashboard['by_priority']['urgent'] +
        dashboard['by_priority']['high'] +
        dashboard['by_priority']['medium'] +
        dashboard['by_priority']['low']
    )

    for insight in all_insights:
        if filter_type and insight['insight_type'] != filter_type:
            continue
        if filter_priority and insight['priority'] != filter_priority:
            continue
        filtered_insights.append(insight)

    # Get type choices for filter dropdown
    type_choices = [
        ('no_recent_contact', 'No Recent Contact'),
        ('prayer_need', 'Prayer Need'),
        ('birthday_upcoming', 'Birthday Upcoming'),
        ('overdue_followup', 'Overdue Follow-up'),
        ('new_volunteer', 'New Volunteer'),
        ('interaction_followup', 'Interaction Follow-up'),
    ]

    # Build type breakdown for the bottom cards (list of tuples: label, count)
    type_counts = dashboard.get('type_counts', {})
    type_breakdown = [
        (label, type_counts.get(type_value, 0))
        for type_value, label in type_choices
    ]

    context = {
        'dashboard': dashboard,
        'insights': filtered_insights if (filter_type or filter_priority) else all_insights,
        'filter_type': filter_type,
        'filter_priority': filter_priority,
        'type_choices': type_choices,
        'type_breakdown': type_breakdown,
    }
    return render(request, 'core/care/dashboard.html', context)


@login_required
@require_POST
def care_dismiss_insight(request, pk):
    """
    Dismiss an insight (mark as addressed/dismissed).
    """
    from .models import VolunteerInsight

    org = get_org(request)

    queryset = VolunteerInsight.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    insight = get_object_or_404(queryset, pk=pk)
    action = request.POST.get('action', 'dismiss')
    notes = request.POST.get('notes', '')

    if action == 'address':
        insight.status = 'actioned'
    else:
        insight.status = 'dismissed'

    insight.acknowledged_by = request.user
    insight.acknowledged_at = timezone.now()
    if notes:
        insight.context_data['resolution_notes'] = notes
        insight.save()
    else:
        insight.save()

    if request.headers.get('HX-Request'):
        return HttpResponse('')  # Remove the card from UI

    return redirect('care_dashboard')


@login_required
@require_POST
def care_create_followup(request, pk):
    """
    Create a follow-up from an insight.
    """
    from .models import VolunteerInsight

    org = get_org(request)

    queryset = VolunteerInsight.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    insight = get_object_or_404(queryset, pk=pk)

    # Create a follow-up based on the insight
    followup = FollowUp.objects.create(
        organization=org,
        created_by=request.user,
        volunteer=insight.volunteer,
        title=insight.title,
        description=f"{insight.message}\n\nSuggested action: {insight.suggested_action}",
        priority='high' if insight.priority in ['urgent', 'high'] else 'medium',
        category='care',
    )

    # Mark insight as actioned
    insight.status = 'actioned'
    insight.acknowledged_by = request.user
    insight.acknowledged_at = timezone.now()
    insight.context_data['created_followup_id'] = followup.id
    insight.save()

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/care_insight_actioned.html', {
            'insight': insight,
            'followup': followup,
        })

    return redirect('followup_detail', pk=followup.pk)


@login_required
@require_POST
def care_refresh_insights(request):
    """
    Clear existing insights and generate fresh proactive care insights.

    This does a full refresh by:
    1. Deleting all active insights for this organization
    2. Regenerating insights from scratch based on current data
    """
    from .models import VolunteerInsight
    from .reports import ProactiveCareGenerator

    org = get_org(request)

    # Clear all active insights for this organization to start fresh
    cleared_count = 0
    if org:
        cleared_count = VolunteerInsight.objects.filter(
            organization=org,
            status='active'
        ).delete()[0]
    else:
        cleared_count = VolunteerInsight.objects.filter(
            status='active'
        ).delete()[0]

    # Generate fresh insights
    generator = ProactiveCareGenerator(organization=org)
    results = generator.generate_all_insights()
    results['cleared_count'] = cleared_count

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/care_refresh_result.html', {
            'results': results,
        })

    return redirect('care_dashboard')


# ============================================================================
# Team Communication Hub Views
# ============================================================================

@login_required
def comms_hub(request):
    """
    Main communication hub - shows announcements, channels, and messages.
    """
    from .models import Announcement, Channel, DirectMessage, AnnouncementRead, Project

    org = get_org(request)

    # Get user's projects (scoped to organization)
    projects = Project.objects.filter(
        models.Q(owner=request.user) | models.Q(members=request.user)
    ).exclude(status='archived').distinct()
    if org:
        projects = projects.filter(organization=org)
    projects = projects.order_by('-updated_at')[:5]

    # Get active announcements (scoped to organization)
    now = timezone.now()
    announcements = Announcement.objects.filter(
        is_active=True
    ).filter(
        models.Q(publish_at__isnull=True) | models.Q(publish_at__lte=now)
    ).filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=now)
    )
    if org:
        announcements = announcements.filter(organization=org)
    announcements = announcements.select_related('author')[:10]

    # Mark read status for each announcement
    read_ids = set(
        AnnouncementRead.objects.filter(
            user=request.user,
            announcement__in=announcements
        ).values_list('announcement_id', flat=True)
    )
    for ann in announcements:
        ann.is_read = ann.id in read_ids

    # Get channels user can access (scoped to organization)
    channels = Channel.objects.filter(
        is_archived=False
    ).filter(
        models.Q(is_private=False) | models.Q(members=request.user)
    )
    if org:
        channels = channels.filter(organization=org)
    channels = channels.distinct()

    # Get unread DM count
    # Note: DirectMessage doesn't have organization field - it's user-to-user
    dm_qs = DirectMessage.objects.filter(
        recipient=request.user,
        is_read=False
    )
    unread_dm_count = dm_qs.count()

    # Get recent DM conversations
    recent_dms = DirectMessage.objects.filter(
        models.Q(sender=request.user) | models.Q(recipient=request.user)
    )
    recent_dms = recent_dms.select_related('sender', 'recipient').order_by('-created_at')[:20]

    # Group by conversation partner
    conversations = {}
    for dm in recent_dms:
        partner = dm.recipient if dm.sender == request.user else dm.sender
        if partner and partner.id not in conversations:
            conversations[partner.id] = {
                'partner': partner,
                'last_message': dm,
                'unread': not dm.is_read and dm.recipient == request.user
            }

    context = {
        'announcements': announcements,
        'channels': channels,
        'projects': projects,
        'conversations': list(conversations.values())[:10],
        'unread_dm_count': unread_dm_count,
    }
    return render(request, 'core/comms/hub.html', context)


@login_required
def announcements_list(request):
    """List all announcements."""
    from .models import Announcement, AnnouncementRead

    org = get_org(request)

    now = timezone.now()
    announcements = Announcement.objects.filter(
        is_active=True
    ).filter(
        models.Q(publish_at__isnull=True) | models.Q(publish_at__lte=now)
    ).filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=now)
    )
    if org:
        announcements = announcements.filter(organization=org)
    announcements = announcements.select_related('author')

    # Mark read status
    read_ids = set(
        AnnouncementRead.objects.filter(
            user=request.user,
            announcement__in=announcements
        ).values_list('announcement_id', flat=True)
    )
    for ann in announcements:
        ann.is_read = ann.id in read_ids

    context = {
        'announcements': announcements,
    }
    return render(request, 'core/comms/announcements.html', context)


@login_required
def announcement_detail(request, pk):
    """View a single announcement and mark as read."""
    from .models import Announcement, AnnouncementRead

    org = get_org(request)

    queryset = Announcement.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    announcement = get_object_or_404(queryset, pk=pk)

    # Mark as read
    AnnouncementRead.objects.get_or_create(
        announcement=announcement,
        user=request.user
    )

    context = {
        'announcement': announcement,
    }
    return render(request, 'core/comms/announcement_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def announcement_create(request):
    """Create a new announcement."""
    from django.contrib import messages
    from .models import Announcement

    org = get_org(request)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        priority = request.POST.get('priority', 'normal')
        is_pinned = request.POST.get('is_pinned') == 'on'

        if title and content:
            announcement = Announcement.objects.create(
                organization=org,
                title=title,
                content=content,
                priority=priority,
                is_pinned=is_pinned,
                author=request.user
            )

            # Send push notifications
            notifications_sent = 0
            try:
                from .notifications import notify_new_announcement
                notifications_sent = notify_new_announcement(announcement)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to send announcement notifications: {e}")
                messages.error(request, f"Announcement created but notification failed: {e}")

            if notifications_sent > 0:
                messages.success(request, f"Announcement posted! {notifications_sent} notification(s) sent.")
            else:
                messages.info(request, "Announcement posted. No other users have push notifications enabled.")

            return redirect('announcements_list')

    return render(request, 'core/comms/announcement_create.html')


@login_required
def channel_list(request):
    """List all accessible channels."""
    from .models import Channel

    org = get_org(request)

    channels = Channel.objects.filter(
        is_archived=False
    ).filter(
        models.Q(is_private=False) | models.Q(members=request.user)
    )
    if org:
        channels = channels.filter(organization=org)
    channels = channels.distinct().annotate(
        message_count=models.Count('messages')
    )

    context = {
        'channels': channels,
    }
    return render(request, 'core/comms/channels.html', context)


@login_required
def channel_detail(request, slug):
    """View a channel and its messages."""
    from .models import Channel, ChannelMessage

    org = get_org(request)

    queryset = Channel.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    channel = get_object_or_404(queryset, slug=slug)

    # Check access
    if not channel.can_access(request.user):
        return redirect('channel_list')

    messages = channel.messages.select_related('author').order_by('-created_at')[:50]
    messages = list(reversed(messages))  # Show oldest first

    context = {
        'channel': channel,
        'messages': messages,
    }
    return render(request, 'core/comms/channel_detail.html', context)


@login_required
@require_POST
def channel_send_message(request, slug):
    """Send a message to a channel."""
    from .models import Channel, ChannelMessage

    org = get_org(request)

    queryset = Channel.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    channel = get_object_or_404(queryset, slug=slug)

    if not channel.can_access(request.user):
        return HttpResponse('Access denied', status=403)

    content = request.POST.get('content', '').strip()
    if content:
        message = ChannelMessage.objects.create(
            channel=channel,
            author=request.user,
            content=content
        )

        # Check for @mentions and send notifications
        try:
            from .notifications import notify_channel_message
            from accounts.models import User
            import re

            # Parse @mentions from content
            mentioned_usernames = re.findall(r'@(\w+)', content)
            mentioned_users = []
            if mentioned_usernames:
                mentioned_users = list(User.objects.filter(username__in=mentioned_usernames))

            notify_channel_message(message, mentioned_users=mentioned_users if mentioned_users else None)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to send channel message notification: {e}")

        if request.headers.get('HX-Request'):
            return render(request, 'core/partials/channel_message.html', {
                'message': message,
                'request': request,
            })

    return redirect('channel_detail', slug=slug)


@login_required
@require_POST
def channel_message_delete(request, message_id):
    """Delete a channel message. Only the author or admins can delete."""
    from .models import ChannelMessage

    org = get_org(request)
    queryset = ChannelMessage.objects.all()
    if org:
        queryset = queryset.filter(channel__organization=org)

    message = get_object_or_404(queryset, id=message_id)
    channel = message.channel

    # Check permissions: author or admin
    is_author = message.author == request.user
    is_admin = getattr(request, 'membership', None) and request.membership.is_admin_or_above

    if not is_author and not is_admin:
        return HttpResponse('Permission denied', status=403)

    message.delete()

    if request.headers.get('HX-Request'):
        return HttpResponse('')  # Empty response removes the element

    return redirect('channel_detail', slug=channel.slug)


@login_required
@require_POST
def announcement_delete(request, pk):
    """Delete an announcement. Only the author or admins can delete."""
    from .models import Announcement

    org = get_org(request)
    queryset = Announcement.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    announcement = get_object_or_404(queryset, pk=pk)

    # Check permissions: author or admin
    is_author = announcement.author == request.user
    is_admin = getattr(request, 'membership', None) and request.membership.is_admin_or_above

    if not is_author and not is_admin:
        return HttpResponse('Permission denied', status=403)

    announcement.delete()

    if request.headers.get('HX-Request'):
        return HttpResponse('')

    return redirect('announcements_list')


@login_required
@require_POST
def dm_delete(request, message_id):
    """Delete a direct message. Only the sender can delete."""
    from .models import DirectMessage

    message = get_object_or_404(DirectMessage, id=message_id)

    # Only the sender can delete their own message
    if message.sender != request.user:
        return HttpResponse('Permission denied', status=403)

    # Store partner info for redirect
    partner = message.recipient if message.sender == request.user else message.sender

    message.delete()

    if request.headers.get('HX-Request'):
        return HttpResponse('')

    return redirect('dm_conversation', user_id=partner.id)


@login_required
@require_http_methods(["GET", "POST"])
def channel_create(request):
    """Create a new channel."""
    from .models import Channel
    from django.utils.text import slugify

    org = get_org(request)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        channel_type = request.POST.get('channel_type', 'general')
        is_private = request.POST.get('is_private') == 'on'

        if name:
            slug = slugify(name)
            # Ensure unique slug (scoped to organization if applicable)
            base_slug = slug
            counter = 1
            slug_qs = Channel.objects.filter(slug=slug)
            if org:
                slug_qs = slug_qs.filter(organization=org)
            while slug_qs.exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
                slug_qs = Channel.objects.filter(slug=slug)
                if org:
                    slug_qs = slug_qs.filter(organization=org)

            channel = Channel.objects.create(
                organization=org,
                name=name,
                slug=slug,
                description=description,
                channel_type=channel_type,
                is_private=is_private,
                created_by=request.user
            )
            if is_private:
                channel.members.add(request.user)

            return redirect('channel_detail', slug=channel.slug)

    return render(request, 'core/comms/channel_create.html')


@login_required
def dm_list(request):
    """List direct message conversations."""
    from .models import DirectMessage

    org = get_org(request)

    # Get all DMs for user (scoped to organization)
    dms = DirectMessage.objects.filter(
        models.Q(sender=request.user) | models.Q(recipient=request.user)
    )
    if org:
        dms = dms.filter(organization=org)
    dms = dms.select_related('sender', 'recipient').order_by('-created_at')

    # Group by conversation partner
    conversations = {}
    for dm in dms:
        partner = dm.recipient if dm.sender == request.user else dm.sender
        if partner and partner.id not in conversations:
            unread_qs = DirectMessage.objects.filter(
                sender=partner,
                recipient=request.user,
                is_read=False
            )
            if org:
                unread_qs = unread_qs.filter(organization=org)
            unread_count = unread_qs.count()
            conversations[partner.id] = {
                'partner': partner,
                'last_message': dm,
                'unread_count': unread_count
            }

    context = {
        'conversations': list(conversations.values()),
    }
    return render(request, 'core/comms/dm_list.html', context)


@login_required
def dm_conversation(request, user_id):
    """View conversation with a specific user."""
    from .models import DirectMessage
    from accounts.models import User

    org = get_org(request)

    partner = get_object_or_404(User, pk=user_id)

    # Get messages in this conversation (scoped to organization)
    messages = DirectMessage.objects.filter(
        models.Q(sender=request.user, recipient=partner) |
        models.Q(sender=partner, recipient=request.user)
    )
    if org:
        messages = messages.filter(organization=org)
    messages = messages.select_related('sender', 'recipient').order_by('created_at')[:100]

    # Mark unread messages as read (scoped to organization)
    unread_qs = DirectMessage.objects.filter(
        sender=partner,
        recipient=request.user,
        is_read=False
    )
    if org:
        unread_qs = unread_qs.filter(organization=org)
    unread_qs.update(is_read=True, read_at=timezone.now())

    context = {
        'partner': partner,
        'messages': messages,
    }
    return render(request, 'core/comms/dm_conversation.html', context)


@login_required
@require_POST
def dm_send(request, user_id):
    """Send a direct message to a user."""
    from .models import DirectMessage
    from accounts.models import User

    org = get_org(request)

    recipient = get_object_or_404(User, pk=user_id)
    content = request.POST.get('content', '').strip()

    if content:
        message = DirectMessage.objects.create(
            organization=org,
            sender=request.user,
            recipient=recipient,
            content=content
        )

        # Send push notification
        try:
            from .notifications import notify_new_dm
            notify_new_dm(message)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to send DM notification: {e}")

        if request.headers.get('HX-Request'):
            return render(request, 'core/partials/dm_message.html', {
                'message': message,
                'is_sender': True,
            })

    return redirect('dm_conversation', user_id=user_id)


@login_required
def dm_new(request):
    """Start a new DM conversation."""
    from accounts.models import User

    users = User.objects.exclude(pk=request.user.pk).order_by('display_name', 'username')

    context = {
        'users': users,
    }
    return render(request, 'core/comms/dm_new.html', context)


# ============================================================================
# Project and Task Views
# ============================================================================

@login_required
def project_list(request):
    """List all projects the user has access to."""
    from .models import Project

    org = get_org(request)

    # Get filter parameters
    status_filter = request.GET.get('status', '')
    my_projects = request.GET.get('mine', '') == '1'

    # Base queryset - projects user owns or is a member of (scoped to organization)
    projects = Project.objects.filter(
        models.Q(owner=request.user) | models.Q(members=request.user)
    ).distinct()
    if org:
        projects = projects.filter(organization=org)
    projects = projects.select_related('owner').prefetch_related('members', 'tasks')

    if status_filter:
        projects = projects.filter(status=status_filter)

    if my_projects:
        projects = projects.filter(owner=request.user)

    # Add task counts
    projects = projects.annotate(
        task_count=models.Count('tasks'),
        completed_task_count=models.Count('tasks', filter=models.Q(tasks__status='completed'))
    )

    context = {
        'projects': projects,
        'status_filter': status_filter,
        'my_projects': my_projects,
        'status_choices': Project.STATUS_CHOICES,
    }
    return render(request, 'core/comms/project_list.html', context)


@login_required
def project_detail(request, pk):
    """View a project and its tasks."""
    from .models import Project, Task
    from accounts.models import User

    org = get_org(request)

    queryset = Project.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    project = get_object_or_404(queryset, pk=pk)

    # Check access
    if project.owner != request.user and request.user not in project.members.all():
        return redirect('project_list')

    # Get tasks grouped by status
    tasks = project.tasks.select_related('created_by').prefetch_related('assignees')

    tasks_by_status = {
        'todo': tasks.filter(status='todo'),
        'in_progress': tasks.filter(status='in_progress'),
        'review': tasks.filter(status='review'),
        'completed': tasks.filter(status='completed'),
    }

    # Get available users for assignment (members of org if applicable)
    available_users = User.objects.filter(is_active=True).order_by('display_name', 'username')

    context = {
        'project': project,
        'tasks': tasks,
        'tasks_by_status': tasks_by_status,
        'available_users': available_users,
        'priority_choices': Task.PRIORITY_CHOICES,
    }
    return render(request, 'core/comms/project_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def project_create(request):
    """Create a new project."""
    from .models import Project, Channel
    from accounts.models import User
    from django.utils.text import slugify

    org = get_org(request)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        priority = request.POST.get('priority', 'medium')
        due_date_str = request.POST.get('due_date', '')
        create_channel = request.POST.get('create_channel') == 'on'
        member_ids = request.POST.getlist('members')

        if name:
            # Parse due date
            due_date = None
            if due_date_str:
                try:
                    from datetime import datetime
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass

            # Create project
            project = Project.objects.create(
                organization=org,
                name=name,
                description=description,
                priority=priority,
                due_date=due_date,
                owner=request.user,
                status='active'
            )

            # Add members and notify them
            if member_ids:
                for member_id in member_ids:
                    try:
                        user = User.objects.get(pk=int(member_id))
                        project.add_member(user, notify=True)
                    except (ValueError, User.DoesNotExist):
                        pass

            # Optionally create a channel for the project
            if create_channel:
                slug = slugify(name)
                base_slug = slug
                counter = 1
                slug_qs = Channel.objects.filter(slug=slug)
                if org:
                    slug_qs = slug_qs.filter(organization=org)
                while slug_qs.exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                    slug_qs = Channel.objects.filter(slug=slug)
                    if org:
                        slug_qs = slug_qs.filter(organization=org)

                channel = Channel.objects.create(
                    organization=org,
                    name=f"proj-{name[:50]}",
                    slug=slug,
                    description=f"Discussion channel for {name}",
                    channel_type='project',
                    is_private=True,
                    created_by=request.user
                )
                channel.members.add(request.user)
                channel.members.add(*project.members.all())
                project.channel = channel
                project.save()

            return redirect('project_detail', pk=project.pk)

    # Get available users
    from accounts.models import User
    available_users = User.objects.filter(is_active=True).exclude(pk=request.user.pk)

    context = {
        'available_users': available_users,
        'priority_choices': Project.PRIORITY_CHOICES,
    }
    return render(request, 'core/comms/project_create.html', context)


@login_required
@require_POST
def project_add_member(request, pk):
    """Add a member to a project."""
    from .models import Project
    from accounts.models import User

    org = get_org(request)

    queryset = Project.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    project = get_object_or_404(queryset, pk=pk)

    # Only owner can add members
    if project.owner != request.user:
        return HttpResponse('Access denied', status=403)

    user_id = request.POST.get('user_id')
    if user_id:
        try:
            user = User.objects.get(pk=int(user_id))
            project.add_member(user, notify=True)

            # Also add to project channel if exists
            if project.channel:
                project.channel.members.add(user)
        except (ValueError, User.DoesNotExist):
            pass

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/project_members.html', {'project': project})

    return redirect('project_detail', pk=pk)


@login_required
@require_POST
def project_update_status(request, pk):
    """Update project status."""
    from .models import Project

    org = get_org(request)

    queryset = Project.objects.all()
    if org:
        queryset = queryset.filter(organization=org)

    project = get_object_or_404(queryset, pk=pk)

    if project.owner != request.user:
        return HttpResponse('Access denied', status=403)

    status = request.POST.get('status')
    if status in dict(Project.STATUS_CHOICES):
        project.status = status
        if status == 'completed':
            project.completed_at = timezone.now()
        project.save()

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/project_status.html', {'project': project})

    return redirect('project_detail', pk=pk)


@login_required
@require_POST
def task_create(request, project_pk):
    """Create a new task in a project."""
    from .models import Project, Task
    from accounts.models import User

    project = get_object_or_404(Project, pk=project_pk)

    # Check access
    if project.owner != request.user and request.user not in project.members.all():
        return HttpResponse('Access denied', status=403)

    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    priority = request.POST.get('priority', 'medium')
    due_date_str = request.POST.get('due_date', '')
    assignee_ids = request.POST.getlist('assignees')

    if title:
        # Parse due date
        due_date = None
        if due_date_str:
            try:
                from datetime import datetime
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        task = Task.objects.create(
            project=project,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            created_by=request.user
        )

        # Assign users and notify them
        if assignee_ids:
            for assignee_id in assignee_ids:
                try:
                    user = User.objects.get(pk=int(assignee_id))
                    task.assign_to(user, notify=True)
                except (ValueError, User.DoesNotExist):
                    pass

        if request.headers.get('HX-Request'):
            return render(request, 'core/partials/task_card.html', {'task': task})

    return redirect('project_detail', pk=project_pk)


@login_required
@require_POST
def task_update_status(request, pk):
    """Update task status."""
    from .models import Task

    task = get_object_or_404(Task, pk=pk)

    # Check access
    project = task.project
    if project.owner != request.user and request.user not in project.members.all():
        return HttpResponse('Access denied', status=403)

    status = request.POST.get('status')
    if status in dict(Task.STATUS_CHOICES):
        task.status = status
        if status == 'completed':
            task.completed_at = timezone.now()
        task.save()

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/task_card.html', {'task': task})

    return redirect('project_detail', pk=task.project.pk)


@login_required
@require_POST
def task_assign(request, pk):
    """Assign a user to a task."""
    from .models import Task
    from accounts.models import User

    task = get_object_or_404(Task, pk=pk)

    # Check access
    project = task.project
    if project.owner != request.user and request.user not in project.members.all():
        return HttpResponse('Access denied', status=403)

    user_id = request.POST.get('user_id')
    if user_id:
        try:
            user = User.objects.get(pk=int(user_id))
            task.assign_to(user, notify=True)
        except (ValueError, User.DoesNotExist):
            pass

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/task_assignees.html', {'task': task})

    return redirect('project_detail', pk=task.project.pk)


@login_required
@require_POST
def task_comment(request, pk):
    """Add a comment to a task."""
    from .models import Task, TaskComment
    from accounts.models import User
    import re

    task = get_object_or_404(Task, pk=pk)

    # Check access
    project = task.project
    if project.owner != request.user and request.user not in project.members.all():
        return HttpResponse('Access denied', status=403)

    content = request.POST.get('content', '').strip()
    if content:
        comment = TaskComment.objects.create(
            task=task,
            author=request.user,
            content=content
        )

        # Parse @mentions
        mentioned_usernames = re.findall(r'@(\w+)', content)
        if mentioned_usernames:
            mentioned_users = User.objects.filter(username__in=mentioned_usernames)
            comment.mentioned_users.set(mentioned_users)

        # Send notifications
        try:
            from .notifications import notify_task_comment
            notify_task_comment(comment)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to send task comment notification: {e}")

        if request.headers.get('HX-Request'):
            return render(request, 'core/partials/task_comment.html', {'comment': comment})

    return redirect('project_detail', pk=task.project.pk)


@login_required
def task_detail(request, project_pk, pk):
    """View a task's details."""
    from .models import Project, Task

    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=pk, project=project)

    # Check access
    if project.owner != request.user and request.user not in project.members.all():
        return redirect('project_list')

    comments = task.comments.select_related('author').prefetch_related('mentioned_users')
    checklists = task.checklists.all()
    completed_count = checklists.filter(is_completed=True).count()

    context = {
        'project': project,
        'task': task,
        'comments': comments,
        'checklists': checklists,
        'completed_count': completed_count,
    }
    return render(request, 'core/comms/task_detail.html', context)


# ============================================================================
# My Tasks Dashboard
# ============================================================================

@login_required
def my_tasks(request):
    """
    Personal task dashboard showing all tasks assigned to the current user.
    """
    from .models import Task, Project
    from datetime import timedelta

    org = get_org(request)

    today = timezone.now().date()

    # Get filter from query params
    filter_type = request.GET.get('filter', 'all')
    sort_by = request.GET.get('sort', 'due_date')
    project_id = request.GET.get('project')

    # Base queryset - tasks assigned to current user (scoped to organization)
    tasks = Task.objects.filter(
        assignees=request.user
    ).exclude(
        status__in=['completed', 'cancelled']
    )
    if org:
        tasks = tasks.filter(project__organization=org)
    tasks = tasks.select_related('project', 'created_by').prefetch_related('assignees')

    # Apply filters
    if filter_type == 'today':
        tasks = tasks.filter(due_date=today)
    elif filter_type == 'week':
        week_end = today + timedelta(days=7)
        tasks = tasks.filter(due_date__gte=today, due_date__lte=week_end)
    elif filter_type == 'overdue':
        tasks = tasks.filter(due_date__lt=today)
    elif filter_type == 'upcoming':
        tasks = tasks.filter(due_date__gt=today)
    elif filter_type == 'no_date':
        tasks = tasks.filter(due_date__isnull=True)

    # Filter by project
    if project_id:
        tasks = tasks.filter(project_id=project_id)

    # Apply sorting
    if sort_by == 'due_date':
        tasks = tasks.order_by('due_date', '-priority', 'title')
    elif sort_by == 'priority':
        # Custom priority ordering (urgent first)
        priority_order = models.Case(
            models.When(priority='urgent', then=0),
            models.When(priority='high', then=1),
            models.When(priority='medium', then=2),
            models.When(priority='low', then=3),
            default=4,
        )
        tasks = tasks.annotate(priority_order=priority_order).order_by('priority_order', 'due_date')
    elif sort_by == 'project':
        tasks = tasks.order_by('project__name', 'due_date')
    elif sort_by == 'status':
        tasks = tasks.order_by('status', 'due_date')

    # Get counts for filter badges (scoped to organization)
    base_task_qs = Task.objects.filter(assignees=request.user)
    if org:
        base_task_qs = base_task_qs.filter(project__organization=org)

    all_count = base_task_qs.exclude(status__in=['completed', 'cancelled']).count()

    overdue_count = base_task_qs.filter(
        due_date__lt=today
    ).exclude(status__in=['completed', 'cancelled']).count()

    today_count = base_task_qs.filter(
        due_date=today
    ).exclude(status__in=['completed', 'cancelled']).count()

    week_end = today + timedelta(days=7)
    week_count = base_task_qs.filter(
        due_date__gte=today,
        due_date__lte=week_end
    ).exclude(status__in=['completed', 'cancelled']).count()

    # Get user's projects for filter dropdown (scoped to organization)
    projects = Project.objects.filter(
        models.Q(owner=request.user) | models.Q(members=request.user)
    ).distinct()
    if org:
        projects = projects.filter(organization=org)
    projects = projects.order_by('name')

    # Recently completed tasks (scoped to organization)
    completed_tasks = Task.objects.filter(
        assignees=request.user,
        status='completed'
    )
    if org:
        completed_tasks = completed_tasks.filter(project__organization=org)
    completed_tasks = completed_tasks.order_by('-completed_at')[:5]

    context = {
        'tasks': tasks,
        'filter_type': filter_type,
        'sort_by': sort_by,
        'selected_project': project_id,
        'projects': projects,
        'all_count': all_count,
        'overdue_count': overdue_count,
        'today_count': today_count,
        'week_count': week_count,
        'completed_tasks': completed_tasks,
        'today': today,
    }
    return render(request, 'core/comms/my_tasks.html', context)


# ============================================================================
# Task Template (Recurring Tasks) Views
# ============================================================================

@login_required
def template_list(request):
    """List all task templates the user has access to."""
    from .models import TaskTemplate, Project

    # Get projects user has access to
    user_projects = Project.objects.filter(
        models.Q(owner=request.user) | models.Q(members=request.user)
    ).distinct()

    templates = TaskTemplate.objects.filter(
        project__in=user_projects
    ).select_related('project', 'created_by').prefetch_related('default_assignees')

    # Group by project
    templates_by_project = {}
    for template in templates:
        if template.project not in templates_by_project:
            templates_by_project[template.project] = []
        templates_by_project[template.project].append(template)

    context = {
        'templates_by_project': templates_by_project,
        'projects': user_projects,
    }
    return render(request, 'core/comms/template_list.html', context)


@login_required
def template_create(request):
    """Create a new task template."""
    from .models import TaskTemplate, Project
    from accounts.models import User

    # Get projects user has access to
    projects = Project.objects.filter(
        models.Q(owner=request.user) | models.Q(members=request.user)
    ).distinct()

    if request.method == 'POST':
        project_id = request.POST.get('project')
        project = get_object_or_404(Project, pk=project_id)

        # Verify access
        if project.owner != request.user and request.user not in project.members.all():
            return redirect('template_list')

        # Parse recurrence days
        recurrence_type = request.POST.get('recurrence_type', 'weekly')
        recurrence_days = []

        if recurrence_type in ['weekly', 'biweekly']:
            # Get selected weekdays (0-6)
            for i in range(7):
                if request.POST.get(f'weekday_{i}'):
                    recurrence_days.append(i)
        elif recurrence_type in ['monthly', 'custom']:
            # Get selected days of month
            days_str = request.POST.get('month_days', '')
            if days_str:
                recurrence_days = [int(d.strip()) for d in days_str.split(',') if d.strip().isdigit()]

        # Parse checklist items
        checklist_str = request.POST.get('default_checklist', '')
        checklist = [item.strip() for item in checklist_str.split('\n') if item.strip()]

        template = TaskTemplate.objects.create(
            name=request.POST.get('name', ''),
            title_template=request.POST.get('title_template', ''),
            description_template=request.POST.get('description_template', ''),
            project=project,
            recurrence_type=recurrence_type,
            recurrence_days=recurrence_days,
            weekday_occurrence=int(request.POST.get('weekday_occurrence') or 0) or None,
            default_priority=request.POST.get('default_priority', 'medium'),
            days_before_due=int(request.POST.get('days_before_due', 3)),
            due_time=request.POST.get('due_time') or None,
            default_checklist=checklist,
            is_active=request.POST.get('is_active') == 'on',
            created_by=request.user
        )

        # Add default assignees
        assignee_ids = request.POST.getlist('default_assignees')
        for user_id in assignee_ids:
            try:
                user = User.objects.get(pk=user_id)
                template.default_assignees.add(user)
            except User.DoesNotExist:
                pass

        # Calculate next occurrence
        template.calculate_next_occurrence()

        return redirect('template_detail', pk=template.pk)

    # Get all users for assignee selection
    users = User.objects.filter(is_active=True).order_by('display_name', 'username')

    context = {
        'projects': projects,
        'users': users,
        'weekdays': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
    }
    return render(request, 'core/comms/template_create.html', context)


@login_required
def template_detail(request, pk):
    """View and edit a task template."""
    from .models import TaskTemplate, Task
    from accounts.models import User

    template = get_object_or_404(TaskTemplate, pk=pk)

    # Check access
    project = template.project
    if project.owner != request.user and request.user not in project.members.all():
        return redirect('template_list')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update':
            # Update template
            template.name = request.POST.get('name', template.name)
            template.title_template = request.POST.get('title_template', template.title_template)
            template.description_template = request.POST.get('description_template', '')
            template.recurrence_type = request.POST.get('recurrence_type', template.recurrence_type)
            template.default_priority = request.POST.get('default_priority', template.default_priority)
            template.days_before_due = int(request.POST.get('days_before_due', 3))
            template.due_time = request.POST.get('due_time') or None
            template.is_active = request.POST.get('is_active') == 'on'

            # Parse recurrence days
            recurrence_days = []
            if template.recurrence_type in ['weekly', 'biweekly']:
                for i in range(7):
                    if request.POST.get(f'weekday_{i}'):
                        recurrence_days.append(i)
            elif template.recurrence_type in ['monthly', 'custom']:
                days_str = request.POST.get('month_days', '')
                if days_str:
                    recurrence_days = [int(d.strip()) for d in days_str.split(',') if d.strip().isdigit()]
            template.recurrence_days = recurrence_days

            template.weekday_occurrence = int(request.POST.get('weekday_occurrence') or 0) or None

            # Parse checklist
            checklist_str = request.POST.get('default_checklist', '')
            template.default_checklist = [item.strip() for item in checklist_str.split('\n') if item.strip()]

            template.save()

            # Update assignees
            template.default_assignees.clear()
            for user_id in request.POST.getlist('default_assignees'):
                try:
                    user = User.objects.get(pk=user_id)
                    template.default_assignees.add(user)
                except User.DoesNotExist:
                    pass

            template.calculate_next_occurrence()

        elif action == 'delete':
            template.delete()
            return redirect('template_list')

    # Get upcoming occurrences preview
    upcoming = template.get_next_occurrences(count=5)
    preview_titles = [(date, template.format_title(date)) for date in upcoming]

    # Get recently generated tasks
    recent_tasks = Task.objects.filter(
        project=template.project,
        title__startswith=template.title_template.split('{')[0][:20]  # Match by title prefix
    ).order_by('-created_at')[:5]

    users = User.objects.filter(is_active=True).order_by('display_name', 'username')

    context = {
        'template': template,
        'preview_titles': preview_titles,
        'recent_tasks': recent_tasks,
        'users': users,
        'weekdays': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
    }
    return render(request, 'core/comms/template_detail.html', context)


@login_required
@require_POST
def template_generate(request, pk):
    """Manually generate a task from a template."""
    from .models import TaskTemplate
    from datetime import datetime

    template = get_object_or_404(TaskTemplate, pk=pk)

    # Check access
    project = template.project
    if project.owner != request.user and request.user not in project.members.all():
        return JsonResponse({'error': 'Access denied'}, status=403)

    # Get target date from POST or use next occurrence
    date_str = request.POST.get('target_date')
    if date_str:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        target_date = template.next_occurrence or timezone.now().date()

    # Generate the task
    task = template.generate_task(target_date, created_by=request.user)

    # Update next occurrence
    template.calculate_next_occurrence()

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/task_card.html', {'task': task})

    return redirect('task_detail', project_pk=project.pk, pk=task.pk)


# ============================================================================
# Task Checklist Views
# ============================================================================

@login_required
@require_POST
def checklist_toggle(request, pk):
    """Toggle a checklist item's completion status."""
    from .models import TaskChecklist

    item = get_object_or_404(TaskChecklist, pk=pk)
    task = item.task

    # Check access
    project = task.project
    if project.owner != request.user and request.user not in project.members.all():
        return JsonResponse({'error': 'Access denied'}, status=403)

    if item.is_completed:
        item.mark_incomplete()
    else:
        item.mark_completed(request.user)

    # Calculate task completion percentage
    total = task.checklists.count()
    completed = task.checklists.filter(is_completed=True).count()
    percent = int((completed / total) * 100) if total > 0 else 0

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/checklist_item.html', {
            'item': item,
            'task': task,
            'percent': percent,
        })

    return JsonResponse({
        'success': True,
        'is_completed': item.is_completed,
        'completed_count': completed,
        'total_count': total,
        'percent': percent,
    })


@login_required
@require_POST
def checklist_add(request, task_pk):
    """Add a new checklist item to a task."""
    from .models import Task, TaskChecklist

    task = get_object_or_404(Task, pk=task_pk)

    # Check access
    project = task.project
    if project.owner != request.user and request.user not in project.members.all():
        return JsonResponse({'error': 'Access denied'}, status=403)

    title = request.POST.get('title', '').strip()
    if not title:
        return JsonResponse({'error': 'Title is required'}, status=400)

    # Get max order
    max_order = task.checklists.aggregate(models.Max('order'))['order__max'] or 0

    item = TaskChecklist.objects.create(
        task=task,
        title=title,
        order=max_order + 1
    )

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/checklist_item.html', {'item': item, 'task': task})

    return JsonResponse({
        'success': True,
        'id': item.pk,
        'title': item.title,
    })


@login_required
@require_POST
def checklist_delete(request, pk):
    """Delete a checklist item."""
    from .models import TaskChecklist

    item = get_object_or_404(TaskChecklist, pk=pk)
    task = item.task

    # Check access
    project = task.project
    if project.owner != request.user and request.user not in project.members.all():
        return JsonResponse({'error': 'Access denied'}, status=403)

    item.delete()

    if request.headers.get('HX-Request'):
        return HttpResponse('')

    return JsonResponse({'success': True})


# ============================================================================
# Push Notification Views
# ============================================================================

@login_required
def push_vapid_key(request):
    """Return the VAPID public key for the frontend."""
    from .notifications import get_vapid_keys

    vapid_keys = get_vapid_keys()
    return JsonResponse({
        'public_key': vapid_keys['public_key'],
    })


@login_required
@require_POST
def push_subscribe(request):
    """
    Register a push subscription for the current user.

    Expects JSON body with:
    - endpoint: Push service endpoint URL
    - keys.p256dh: Public key for encryption
    - keys.auth: Auth secret
    """
    from .models import PushSubscription

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    endpoint = data.get('endpoint')
    keys = data.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')

    if not all([endpoint, p256dh, auth]):
        return JsonResponse({'error': 'Missing required subscription data'}, status=400)

    # Get device info from user agent
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    device_name = _parse_device_name(user_agent)

    # Create or update subscription
    subscription, created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'user': request.user,
            'p256dh_key': p256dh,
            'auth_key': auth,
            'user_agent': user_agent,
            'device_name': device_name,
            'is_active': True,
        }
    )

    return JsonResponse({
        'success': True,
        'created': created,
        'subscription_id': subscription.id,
        'device_name': device_name,
    })


def _parse_device_name(user_agent: str) -> str:
    """Parse user agent to get a friendly device name."""
    ua_lower = user_agent.lower()

    # Detect mobile devices first
    if 'iphone' in ua_lower:
        return 'iPhone'
    elif 'ipad' in ua_lower:
        return 'iPad'
    elif 'android' in ua_lower:
        if 'mobile' in ua_lower:
            return 'Android Phone'
        return 'Android Tablet'

    # Detect browsers on desktop
    browser = 'Browser'
    if 'chrome' in ua_lower and 'edg' not in ua_lower:
        browser = 'Chrome'
    elif 'firefox' in ua_lower:
        browser = 'Firefox'
    elif 'safari' in ua_lower and 'chrome' not in ua_lower:
        browser = 'Safari'
    elif 'edg' in ua_lower:
        browser = 'Edge'

    # Detect OS
    os_name = ''
    if 'macintosh' in ua_lower or 'mac os' in ua_lower:
        os_name = 'Mac'
    elif 'windows' in ua_lower:
        os_name = 'Windows'
    elif 'linux' in ua_lower:
        os_name = 'Linux'

    if os_name:
        return f'{browser} on {os_name}'
    return browser


@login_required
@require_POST
def push_unsubscribe(request):
    """
    Remove a push subscription.

    Expects JSON body with:
    - endpoint: Push service endpoint URL to remove
    """
    from .models import PushSubscription

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    endpoint = data.get('endpoint')
    if not endpoint:
        return JsonResponse({'error': 'Missing endpoint'}, status=400)

    # Delete subscription
    deleted, _ = PushSubscription.objects.filter(
        user=request.user,
        endpoint=endpoint
    ).delete()

    return JsonResponse({
        'success': True,
        'deleted': deleted > 0,
    })


@login_required
@require_http_methods(["GET", "POST"])
def push_preferences(request):
    """
    View and update notification preferences.
    """
    from .models import NotificationPreference, PushSubscription

    prefs = NotificationPreference.get_or_create_for_user(request.user)
    subscriptions = PushSubscription.objects.filter(user=request.user, is_active=True)

    if request.method == 'POST':
        # Update preferences from form
        prefs.announcements = request.POST.get('announcements') == 'on'
        prefs.announcements_urgent_only = request.POST.get('announcements_urgent_only') == 'on'
        prefs.direct_messages = request.POST.get('direct_messages') == 'on'
        prefs.channel_messages = request.POST.get('channel_messages') == 'on'
        prefs.channel_mentions_only = request.POST.get('channel_mentions_only') == 'on'
        prefs.care_alerts = request.POST.get('care_alerts') == 'on'
        prefs.care_urgent_only = request.POST.get('care_urgent_only') == 'on'
        prefs.followup_reminders = request.POST.get('followup_reminders') == 'on'
        prefs.quiet_hours_enabled = request.POST.get('quiet_hours_enabled') == 'on'

        # Parse quiet hours
        quiet_start = request.POST.get('quiet_hours_start', '')
        quiet_end = request.POST.get('quiet_hours_end', '')

        if quiet_start:
            try:
                from datetime import datetime
                prefs.quiet_hours_start = datetime.strptime(quiet_start, '%H:%M').time()
            except ValueError:
                pass

        if quiet_end:
            try:
                from datetime import datetime
                prefs.quiet_hours_end = datetime.strptime(quiet_end, '%H:%M').time()
            except ValueError:
                pass

        prefs.save()

        if request.headers.get('HX-Request'):
            return HttpResponse('<span class="text-green-500">Preferences saved!</span>')

        return redirect('push_preferences')

    context = {
        'prefs': prefs,
        'subscriptions': subscriptions,
    }
    return render(request, 'core/notifications/preferences.html', context)


@login_required
@require_POST
def push_test(request):
    """
    Send a test notification to the current user.
    """
    from .notifications import send_test_notification

    sent = send_test_notification(request.user)

    if request.headers.get('HX-Request'):
        if sent > 0:
            return HttpResponse(f'<span class="text-green-500">Test notification sent to {sent} device(s)!</span>')
        else:
            return HttpResponse('<span class="text-yellow-500">No active subscriptions found. Enable notifications first.</span>')

    return JsonResponse({
        'success': sent > 0,
        'sent': sent,
    })


@csrf_exempt
@require_POST
def notification_clicked(request):
    """
    Track when a notification is clicked (called from service worker).
    """
    from .models import NotificationLog

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    log_id = data.get('log_id')
    if log_id:
        NotificationLog.objects.filter(pk=log_id).update(
            status='clicked',
            clicked_at=timezone.now()
        )

    return JsonResponse({'success': True})


@login_required
@require_POST
def push_remove_device(request, subscription_id):
    """
    Remove a specific device/subscription.
    """
    from .models import PushSubscription

    deleted, _ = PushSubscription.objects.filter(
        pk=subscription_id,
        user=request.user
    ).delete()

    if request.headers.get('HX-Request'):
        return HttpResponse('')  # Remove the row

    return JsonResponse({'success': deleted > 0})


# ============================================================================
# Subscription & Billing Views
# ============================================================================

@login_required
def subscription_required(request):
    """
    Page shown when an organization's subscription has expired.

    Users are redirected here when:
    - Trial period has ended
    - Subscription was cancelled
    - Account was suspended
    """
    from .models import Organization, OrganizationMembership, SubscriptionPlan

    # Get user's organization
    membership = OrganizationMembership.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('organization', 'organization__subscription_plan').first()

    if not membership:
        return redirect('onboarding_signup')

    org = membership.organization

    # If subscription is actually active, redirect to dashboard
    if org.is_subscription_active:
        return redirect('dashboard')

    # Get available plans for upgrade
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly_cents')

    # Determine the message based on status
    if org.is_trial_expired:
        message = "Your 14-day free trial has ended."
        subtitle = "Subscribe now to continue using Aria for your team."
    elif org.subscription_status == 'cancelled':
        message = "Your subscription has been cancelled."
        subtitle = "Reactivate your subscription to continue using Aria."
    elif org.subscription_status == 'suspended':
        message = "Your account has been suspended."
        subtitle = "Please contact support to resolve this issue."
    else:
        message = "Subscription required."
        subtitle = "Please subscribe to continue using Aria."

    context = {
        'organization': org,
        'membership': membership,
        'plans': plans,
        'message': message,
        'subtitle': subtitle,
        'can_resubscribe': org.subscription_status != 'suspended',
    }

    return render(request, 'core/subscription_required.html', context)


@login_required
def billing_portal(request):
    """
    Redirect to Stripe Customer Portal for subscription management.

    Allows users to:
    - Update payment method
    - View invoices
    - Cancel subscription
    - Change plan
    """
    from .models import OrganizationMembership

    # Get user's organization
    membership = OrganizationMembership.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('organization').first()

    if not membership:
        return redirect('dashboard')

    org = membership.organization

    # Check if user has billing permission
    if not membership.can_manage_billing and membership.role != 'owner':
        messages.error(request, "You don't have permission to manage billing.")
        return redirect('dashboard')

    # Check for Stripe customer ID
    if not org.stripe_customer_id:
        messages.error(request, "No billing information found. Please contact support.")
        return redirect('dashboard')

    # Create Stripe billing portal session
    stripe_secret_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
    if not stripe_secret_key:
        messages.error(request, "Billing system is not configured.")
        return redirect('dashboard')

    try:
        import stripe
        stripe.api_key = stripe_secret_key

        session = stripe.billing_portal.Session.create(
            customer=org.stripe_customer_id,
            return_url=request.build_absolute_uri(reverse('dashboard')),
        )

        return redirect(session.url)

    except Exception as e:
        logger.error(f"Failed to create billing portal session: {e}")
        messages.error(request, "Unable to access billing portal. Please try again.")
        return redirect('dashboard')


@login_required
def subscribe(request):
    """
    Handle subscription for expired trial or reactivation.

    Creates a new Stripe checkout session for the selected plan.
    """
    from .models import OrganizationMembership, SubscriptionPlan

    # Get user's organization
    membership = OrganizationMembership.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('organization').first()

    if not membership:
        return redirect('onboarding_signup')

    org = membership.organization

    # Check if user has billing permission
    if not membership.can_manage_billing and membership.role != 'owner':
        messages.error(request, "You don't have permission to manage billing.")
        return redirect('subscription_required')

    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        billing_period = request.POST.get('billing_period', 'monthly')

        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            messages.error(request, "Invalid plan selected.")
            return redirect('subscription_required')

        # Get Stripe price ID
        if billing_period == 'yearly':
            price_key = f'STRIPE_PRICE_{plan.tier.upper()}_YEARLY'
        else:
            price_key = f'STRIPE_PRICE_{plan.tier.upper()}_MONTHLY'

        stripe_price_id = getattr(settings, price_key, None)

        if not stripe_price_id:
            messages.error(request, "This plan is not available for purchase yet.")
            return redirect('subscription_required')

        # Create Stripe checkout session
        stripe_secret_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
        if not stripe_secret_key:
            messages.error(request, "Billing system is not configured.")
            return redirect('subscription_required')

        try:
            import stripe
            stripe.api_key = stripe_secret_key

            # Create or get Stripe customer
            if not org.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=org.email,
                    name=org.name,
                    metadata={'organization_id': str(org.id)},
                )
                org.stripe_customer_id = customer.id
                org.save(update_fields=['stripe_customer_id'])

            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=org.stripe_customer_id,
                mode='subscription',
                line_items=[{
                    'price': stripe_price_id,
                    'quantity': 1,
                }],
                success_url=request.build_absolute_uri(
                    reverse('subscription_success')
                ) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri(
                    reverse('subscription_required')
                ),
                metadata={
                    'organization_id': str(org.id),
                    'plan_id': str(plan.id),
                },
            )

            return redirect(session.url)

        except Exception as e:
            logger.error(f"Failed to create checkout session: {e}")
            messages.error(request, "Unable to process payment. Please try again.")
            return redirect('subscription_required')

    # GET request - show plan selection
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly_cents')
    return render(request, 'core/subscribe.html', {
        'organization': org,
        'plans': plans,
    })


@login_required
def subscription_success(request):
    """
    Handle successful subscription checkout.

    The webhook will update the subscription status, but we show a success page.
    """
    session_id = request.GET.get('session_id')

    # The webhook handles the actual subscription activation
    # This page just shows a success message

    messages.success(request, "Welcome! Your subscription is now active.")
    return redirect('dashboard')


# ============================================================================
# Organization Onboarding Views
# ============================================================================

def onboarding_signup(request):
    """
    Public signup page for creating a new organization.

    This is the entry point for the onboarding flow. Users create an account
    and organization simultaneously.
    """
    from django.contrib.auth import login
    from accounts.models import User
    from .models import Organization, OrganizationMembership, SubscriptionPlan
    from datetime import timedelta

    # Redirect logged-in users to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        # Get form data
        org_name = request.POST.get('organization_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        errors = []

        # Validation
        if not org_name:
            errors.append('Organization name is required.')
        if not email:
            errors.append('Email is required.')
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if User.objects.filter(email=email).exists():
            errors.append('An account with this email already exists.')

        if errors:
            return render(request, 'core/onboarding/signup.html', {
                'errors': errors,
                'org_name': org_name,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
            })

        # Create user
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        # Get default plan (Starter) or use first available
        default_plan = SubscriptionPlan.objects.filter(
            is_active=True
        ).order_by('price_monthly_cents').first()

        # Calculate trial end date
        trial_days = getattr(settings, 'TRIAL_PERIOD_DAYS', 14)
        trial_ends_at = timezone.now() + timedelta(days=trial_days)

        # Create organization
        org = Organization.objects.create(
            name=org_name,
            email=email,
            subscription_plan=default_plan,
            subscription_status='trial',
            trial_ends_at=trial_ends_at,
        )

        # Create owner membership
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role='owner',
            can_manage_users=True,
            can_manage_settings=True,
            can_view_analytics=True,
            can_manage_billing=True,
        )

        # Set user's default organization
        user.default_organization = org
        user.save()

        # Log user in
        login(request, user)

        # Store org in session for onboarding flow
        request.session['onboarding_org_id'] = org.id

        return redirect('onboarding_select_plan')

    return render(request, 'core/onboarding/signup.html')


@login_required
def onboarding_select_plan(request):
    """
    Plan selection page during onboarding.

    Shows available subscription plans with features and pricing.
    """
    from .models import SubscriptionPlan, Organization

    # Get organization from session or user's default
    org_id = request.session.get('onboarding_org_id')
    if org_id:
        org = Organization.objects.filter(id=org_id).first()
    else:
        org = request.user.default_organization

    if not org:
        return redirect('onboarding_signup')

    # Get all active plans
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly_cents')

    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        billing_cycle = request.POST.get('billing_cycle', 'monthly')

        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
            # Store selection in session
            request.session['selected_plan_id'] = plan.id
            request.session['billing_cycle'] = billing_cycle

            # Update organization's plan
            org.subscription_plan = plan
            org.save()

            return redirect('onboarding_checkout')
        except SubscriptionPlan.DoesNotExist:
            pass

    context = {
        'plans': plans,
        'organization': org,
        'current_plan': org.subscription_plan,
    }
    return render(request, 'core/onboarding/select_plan.html', context)


@login_required
def onboarding_checkout(request):
    """
    Create Stripe checkout session for subscription.
    """
    import stripe
    from .models import SubscriptionPlan, Organization

    stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

    # Get organization
    org_id = request.session.get('onboarding_org_id')
    if org_id:
        org = Organization.objects.filter(id=org_id).first()
    else:
        org = request.user.default_organization

    if not org:
        return redirect('onboarding_signup')

    # Get selected plan from session
    plan_id = request.session.get('selected_plan_id')
    billing_cycle = request.session.get('billing_cycle', 'monthly')

    if not plan_id:
        return redirect('onboarding_select_plan')

    try:
        plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        return redirect('onboarding_select_plan')

    # Get the appropriate Stripe price ID from settings based on plan tier
    # Settings keys are like: STRIPE_PRICE_STARTER_MONTHLY, STRIPE_PRICE_TEAM_YEARLY
    price_key = f'STRIPE_PRICE_{plan.tier.upper()}_{billing_cycle.upper()}'
    price_id = getattr(settings, price_key, None)

    if not price_id or not stripe.api_key:
        # If no Stripe price configured, skip to next step (trial only)
        return redirect('onboarding_connect_pco')

    # Create or get Stripe customer
    if not org.stripe_customer_id:
        try:
            customer = stripe.Customer.create(
                email=org.email,
                name=org.name,
                metadata={
                    'organization_id': str(org.id),
                    'organization_slug': org.slug,
                }
            )
            org.stripe_customer_id = customer.id
            org.save()
        except stripe.error.StripeError as e:
            return render(request, 'core/onboarding/checkout_error.html', {
                'error': str(e),
                'organization': org,
            })

    # Build success/cancel URLs
    success_url = request.build_absolute_uri('/onboarding/checkout/success/')
    cancel_url = request.build_absolute_uri('/onboarding/checkout/cancel/')

    # Create checkout session
    try:
        checkout_session = stripe.checkout.Session.create(
            customer=org.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=cancel_url,
            subscription_data={
                'trial_period_days': getattr(settings, 'TRIAL_PERIOD_DAYS', 14),
                'metadata': {
                    'organization_id': str(org.id),
                },
            },
            metadata={
                'organization_id': str(org.id),
                'plan_id': str(plan.id),
            },
        )
        return redirect(checkout_session.url)
    except stripe.error.StripeError as e:
        return render(request, 'core/onboarding/checkout_error.html', {
            'error': str(e),
            'organization': org,
        })


@login_required
def onboarding_checkout_success(request):
    """
    Handle successful Stripe checkout.
    """
    import stripe
    from .models import Organization

    stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

    session_id = request.GET.get('session_id')

    # Get organization
    org_id = request.session.get('onboarding_org_id')
    if org_id:
        org = Organization.objects.filter(id=org_id).first()
    else:
        org = request.user.default_organization

    if session_id and org and stripe.api_key:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            subscription_id = session.subscription

            if subscription_id:
                org.stripe_subscription_id = subscription_id
                org.subscription_status = 'active'
                org.subscription_started_at = timezone.now()
                org.save()
        except stripe.error.StripeError:
            pass

    return redirect('onboarding_connect_pco')


@login_required
def onboarding_checkout_cancel(request):
    """
    Handle cancelled Stripe checkout.
    """
    return redirect('onboarding_select_plan')


@login_required
def onboarding_connect_pco(request):
    """
    Planning Center OAuth connection page.

    Users can connect their Planning Center account or skip this step.
    """
    from .models import Organization

    # Get organization
    org_id = request.session.get('onboarding_org_id')
    if org_id:
        org = Organization.objects.filter(id=org_id).first()
    else:
        org = request.user.default_organization

    if not org:
        return redirect('onboarding_signup')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'skip':
            return redirect('onboarding_invite_team')

        if action == 'connect':
            # For now, store manual credentials (full OAuth can be added later)
            pco_app_id = request.POST.get('pco_app_id', '').strip()
            pco_secret = request.POST.get('pco_secret', '').strip()

            if pco_app_id and pco_secret:
                org.planning_center_app_id = pco_app_id
                org.planning_center_secret = pco_secret
                org.planning_center_connected_at = timezone.now()
                org.save()
                return redirect('onboarding_invite_team')

    context = {
        'organization': org,
        'is_connected': bool(org.planning_center_app_id),
    }
    return render(request, 'core/onboarding/connect_pco.html', context)


@login_required
def onboarding_invite_team(request):
    """
    Team member invitation page.

    Users can invite team members by email or skip to complete onboarding.
    """
    from .models import Organization, OrganizationInvitation, OrganizationMembership
    from datetime import timedelta
    import secrets

    # Get organization
    org_id = request.session.get('onboarding_org_id')
    if org_id:
        org = Organization.objects.filter(id=org_id).first()
    else:
        org = request.user.default_organization

    if not org:
        return redirect('onboarding_signup')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'skip' or action == 'complete':
            # Clear onboarding session data
            request.session.pop('onboarding_org_id', None)
            request.session.pop('selected_plan_id', None)
            request.session.pop('billing_cycle', None)
            return redirect('onboarding_complete')

        if action == 'invite':
            emails = request.POST.get('emails', '').strip()
            role = request.POST.get('role', 'member')

            if emails:
                # Parse comma-separated or newline-separated emails
                email_list = [e.strip().lower() for e in emails.replace('\n', ',').split(',') if e.strip()]

                for email in email_list:
                    # Skip if already a member
                    if OrganizationMembership.objects.filter(
                        organization=org,
                        user__email=email
                    ).exists():
                        continue

                    # Skip if already invited
                    if OrganizationInvitation.objects.filter(
                        organization=org,
                        email=email,
                        status='pending'
                    ).exists():
                        continue

                    # Create invitation
                    OrganizationInvitation.objects.create(
                        organization=org,
                        email=email,
                        role=role,
                        invited_by=request.user,
                        token=secrets.token_urlsafe(32),
                        expires_at=timezone.now() + timedelta(days=7),
                    )

                # TODO: Send invitation emails when email integration is set up

    # Get existing invitations
    pending_invitations = OrganizationInvitation.objects.filter(
        organization=org,
        status='pending'
    ).order_by('-created_at')

    context = {
        'organization': org,
        'pending_invitations': pending_invitations,
        'role_choices': OrganizationMembership.ROLE_CHOICES[1:],  # Exclude 'owner'
    }
    return render(request, 'core/onboarding/invite_team.html', context)


@login_required
def onboarding_complete(request):
    """
    Onboarding completion page.

    Shows a summary and guides user to their dashboard.
    """
    org = request.user.default_organization

    context = {
        'organization': org,
    }
    return render(request, 'core/onboarding/complete.html', context)


def accept_invitation(request, token):
    """
    Accept a team invitation via token link.

    If user is logged in, adds them to the organization.
    If not, prompts them to create an account or log in.
    """
    from django.contrib.auth import login
    from accounts.models import User
    from .models import OrganizationInvitation, OrganizationMembership

    try:
        invitation = OrganizationInvitation.objects.get(
            token=token,
            status='pending'
        )
    except OrganizationInvitation.DoesNotExist:
        return render(request, 'core/onboarding/invitation_invalid.html')

    # Check if expired
    if invitation.expires_at and timezone.now() > invitation.expires_at:
        invitation.status = 'expired'
        invitation.save()
        return render(request, 'core/onboarding/invitation_expired.html', {
            'organization': invitation.organization,
        })

    org = invitation.organization

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_account':
            # Create new user account
            email = invitation.email
            password = request.POST.get('password', '')
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()

            if len(password) < 8:
                return render(request, 'core/onboarding/accept_invitation.html', {
                    'invitation': invitation,
                    'organization': org,
                    'error': 'Password must be at least 8 characters.',
                })

            # Create user
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            user.default_organization = org
            user.save()

            # Create membership
            OrganizationMembership.objects.create(
                user=user,
                organization=org,
                role=invitation.role,
                can_manage_users=invitation.role in ['admin', 'owner'],
                can_manage_settings=invitation.role in ['admin', 'owner'],
                can_view_analytics=invitation.role in ['admin', 'owner', 'leader'],
                can_manage_billing=invitation.role == 'owner',
            )

            # Mark invitation as accepted
            invitation.status = 'accepted'
            invitation.accepted_at = timezone.now()
            invitation.save()

            # Log user in
            login(request, user)

            return redirect('dashboard')

        elif action == 'accept' and request.user.is_authenticated:
            # Existing user accepting invitation
            user = request.user

            # Check if already a member
            if OrganizationMembership.objects.filter(user=user, organization=org).exists():
                return redirect('dashboard')

            # Create membership
            OrganizationMembership.objects.create(
                user=user,
                organization=org,
                role=invitation.role,
                can_manage_users=invitation.role in ['admin', 'owner'],
                can_manage_settings=invitation.role in ['admin', 'owner'],
                can_view_analytics=invitation.role in ['admin', 'owner', 'leader'],
                can_manage_billing=invitation.role == 'owner',
            )

            # Update default organization if user doesn't have one
            if not user.default_organization:
                user.default_organization = org
                user.save()

            # Mark invitation as accepted
            invitation.status = 'accepted'
            invitation.accepted_at = timezone.now()
            invitation.save()

            return redirect('dashboard')

    # Check if user is logged in and email matches
    if request.user.is_authenticated:
        if request.user.email.lower() == invitation.email.lower():
            # Show accept button
            return render(request, 'core/onboarding/accept_invitation.html', {
                'invitation': invitation,
                'organization': org,
                'show_accept': True,
            })
        else:
            # Different user logged in - show info
            return render(request, 'core/onboarding/accept_invitation.html', {
                'invitation': invitation,
                'organization': org,
                'wrong_user': True,
            })
    else:
        # Check if user exists
        existing_user = User.objects.filter(email=invitation.email).exists()

        return render(request, 'core/onboarding/accept_invitation.html', {
            'invitation': invitation,
            'organization': org,
            'existing_user': existing_user,
        })


@csrf_exempt
def stripe_webhook(request):
    """
    Handle Stripe webhook events.

    Processes subscription updates, payment failures, etc.
    """
    import stripe
    from .models import Organization

    stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')

    if not stripe.api_key:
        return HttpResponse(status=200)

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            # For testing without webhook signature verification
            import json
            event = json.loads(payload)
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    event_type = event.get('type', '')
    data = event.get('data', {}).get('object', {})

    # Handle different event types
    if event_type == 'customer.subscription.created':
        subscription_id = data.get('id')
        customer_id = data.get('customer')
        status = data.get('status')

        org = Organization.objects.filter(stripe_customer_id=customer_id).first()
        if org:
            org.stripe_subscription_id = subscription_id
            if status == 'active' or status == 'trialing':
                org.subscription_status = 'active' if status == 'active' else 'trial'
            org.save()

    elif event_type == 'customer.subscription.updated':
        subscription_id = data.get('id')
        status = data.get('status')

        org = Organization.objects.filter(stripe_subscription_id=subscription_id).first()
        if org:
            status_map = {
                'active': 'active',
                'trialing': 'trial',
                'past_due': 'past_due',
                'canceled': 'cancelled',
                'unpaid': 'past_due',
            }
            org.subscription_status = status_map.get(status, org.subscription_status)
            org.save()

    elif event_type == 'customer.subscription.deleted':
        subscription_id = data.get('id')

        org = Organization.objects.filter(stripe_subscription_id=subscription_id).first()
        if org:
            org.subscription_status = 'cancelled'
            org.subscription_ends_at = timezone.now()
            org.save()

    elif event_type == 'invoice.payment_failed':
        customer_id = data.get('customer')

        org = Organization.objects.filter(stripe_customer_id=customer_id).first()
        if org:
            org.subscription_status = 'past_due'
            org.save()

    elif event_type == 'invoice.paid':
        customer_id = data.get('customer')

        org = Organization.objects.filter(stripe_customer_id=customer_id).first()
        if org and org.subscription_status == 'past_due':
            org.subscription_status = 'active'
            org.save()

    return HttpResponse(status=200)


# =============================================================================
# Organization Settings Views
# =============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def org_settings(request):
    """Organization general settings page."""
    from .models import Organization
    from .middleware import require_permission

    org = get_org(request)
    if not org:
        return redirect('dashboard')

    membership = getattr(request, 'membership', None)
    if not membership or not membership.can_manage_settings:
        from django.contrib import messages
        messages.error(request, "You don't have permission to manage settings.")
        return redirect('dashboard')

    if request.method == 'POST':
        # Update organization settings
        org.name = request.POST.get('name', org.name)
        org.email = request.POST.get('email', org.email)
        org.phone = request.POST.get('phone', '')
        org.website = request.POST.get('website', '')
        org.timezone = request.POST.get('timezone', org.timezone)
        org.ai_assistant_name = request.POST.get('ai_assistant_name', 'Aria')

        org.save()

        from django.contrib import messages
        messages.success(request, "Settings updated successfully.")
        return redirect('org_settings')

    # Common timezones
    timezones = [
        'America/New_York',
        'America/Chicago',
        'America/Denver',
        'America/Los_Angeles',
        'America/Phoenix',
        'Pacific/Honolulu',
        'America/Anchorage',
    ]

    return render(request, 'core/settings/general.html', {
        'organization': org,
        'membership': membership,
        'timezones': timezones,
    })


@login_required
def org_settings_members(request):
    """Organization team members management page."""
    from .models import OrganizationMembership, OrganizationInvitation

    org = get_org(request)
    if not org:
        return redirect('dashboard')

    membership = getattr(request, 'membership', None)
    if not membership or not membership.can_manage_users:
        from django.contrib import messages
        messages.error(request, "You don't have permission to manage team members.")
        return redirect('dashboard')

    # Get all members
    members = OrganizationMembership.objects.filter(
        organization=org,
        is_active=True
    ).select_related('user').order_by('role', 'user__email')

    # Get pending invitations
    pending_invitations = OrganizationInvitation.objects.filter(
        organization=org,
        status='pending'
    ).order_by('-created_at')

    # Role choices for the form
    role_choices = OrganizationMembership.ROLE_CHOICES

    # Check plan limits
    plan = org.subscription_plan
    max_users = plan.max_users if plan else 5
    current_users = members.count()
    can_invite = max_users == -1 or current_users < max_users

    return render(request, 'core/settings/members.html', {
        'organization': org,
        'membership': membership,
        'members': members,
        'pending_invitations': pending_invitations,
        'role_choices': role_choices,
        'can_invite': can_invite,
        'max_users': max_users,
        'current_users': current_users,
    })


@login_required
@require_POST
def org_invite_member(request):
    """Send an invitation to join the organization."""
    from .models import OrganizationInvitation, OrganizationMembership
    from django.contrib import messages

    org = get_org(request)
    if not org:
        return redirect('dashboard')

    membership = getattr(request, 'membership', None)
    if not membership or not membership.can_manage_users:
        messages.error(request, "You don't have permission to invite members.")
        return redirect('org_settings_members')

    email = request.POST.get('email', '').strip().lower()
    role = request.POST.get('role', 'member')
    team = request.POST.get('team', '')

    if not email:
        messages.error(request, "Email is required.")
        return redirect('org_settings_members')

    # Check if already a member
    from accounts.models import User
    existing_user = User.objects.filter(email=email).first()
    if existing_user:
        if OrganizationMembership.objects.filter(user=existing_user, organization=org).exists():
            messages.error(request, f"{email} is already a member of this organization.")
            return redirect('org_settings_members')

    # Check if already invited
    if OrganizationInvitation.objects.filter(organization=org, email=email, status='pending').exists():
        messages.error(request, f"An invitation has already been sent to {email}.")
        return redirect('org_settings_members')

    # Check plan limits
    plan = org.subscription_plan
    max_users = plan.max_users if plan else 5
    current_users = OrganizationMembership.objects.filter(organization=org, is_active=True).count()
    if max_users != -1 and current_users >= max_users:
        messages.error(request, f"You've reached your plan limit of {max_users} users. Upgrade to add more.")
        return redirect('org_settings_members')

    # Owners can only be set by other owners
    if role == 'owner' and membership.role != 'owner':
        messages.error(request, "Only owners can invite new owners.")
        return redirect('org_settings_members')

    # Create invitation
    invitation = OrganizationInvitation.objects.create(
        organization=org,
        email=email,
        role=role,
        team=team,
        invited_by=request.user,
    )

    # TODO: Send invitation email
    # For now, just show the invite link
    invite_url = request.build_absolute_uri(f'/invite/{invitation.token}/')

    messages.success(
        request,
        f"Invitation sent to {email}. Share this link: {invite_url}"
    )
    return redirect('org_settings_members')


@login_required
@require_POST
def org_update_member_role(request, member_id):
    """Update a member's role."""
    from .models import OrganizationMembership
    from django.contrib import messages

    org = get_org(request)
    if not org:
        return redirect('dashboard')

    membership = getattr(request, 'membership', None)
    if not membership or not membership.can_manage_users:
        messages.error(request, "You don't have permission to manage members.")
        return redirect('org_settings_members')

    target_membership = get_object_or_404(
        OrganizationMembership,
        id=member_id,
        organization=org
    )

    # Can't change your own role
    if target_membership.user == request.user:
        messages.error(request, "You cannot change your own role.")
        return redirect('org_settings_members')

    # Can't modify owners unless you're an owner
    if target_membership.role == 'owner' and membership.role != 'owner':
        messages.error(request, "Only owners can modify other owners.")
        return redirect('org_settings_members')

    new_role = request.POST.get('role')
    if new_role not in dict(OrganizationMembership.ROLE_CHOICES):
        messages.error(request, "Invalid role.")
        return redirect('org_settings_members')

    # Can't make someone owner unless you're owner
    if new_role == 'owner' and membership.role != 'owner':
        messages.error(request, "Only owners can grant owner role.")
        return redirect('org_settings_members')

    target_membership.role = new_role
    target_membership._set_role_defaults()
    target_membership.save()

    messages.success(request, f"Role updated for {target_membership.user.email}.")
    return redirect('org_settings_members')


@login_required
@require_POST
def org_remove_member(request, member_id):
    """Remove a member from the organization."""
    from .models import OrganizationMembership
    from django.contrib import messages

    org = get_org(request)
    if not org:
        return redirect('dashboard')

    membership = getattr(request, 'membership', None)
    if not membership or not membership.can_manage_users:
        messages.error(request, "You don't have permission to manage members.")
        return redirect('org_settings_members')

    target_membership = get_object_or_404(
        OrganizationMembership,
        id=member_id,
        organization=org
    )

    # Can't remove yourself
    if target_membership.user == request.user:
        messages.error(request, "You cannot remove yourself. Transfer ownership first.")
        return redirect('org_settings_members')

    # Can't remove owners unless you're owner
    if target_membership.role == 'owner' and membership.role != 'owner':
        messages.error(request, "Only owners can remove other owners.")
        return redirect('org_settings_members')

    # Ensure at least one owner remains
    if target_membership.role == 'owner':
        owner_count = OrganizationMembership.objects.filter(
            organization=org,
            role='owner',
            is_active=True
        ).count()
        if owner_count <= 1:
            messages.error(request, "Cannot remove the last owner. Transfer ownership first.")
            return redirect('org_settings_members')

    user_email = target_membership.user.email
    target_membership.is_active = False
    target_membership.save()

    messages.success(request, f"{user_email} has been removed from the organization.")
    return redirect('org_settings_members')


@login_required
@require_POST
def org_cancel_invitation(request, invitation_id):
    """Cancel a pending invitation."""
    from .models import OrganizationInvitation
    from django.contrib import messages

    org = get_org(request)
    if not org:
        return redirect('dashboard')

    membership = getattr(request, 'membership', None)
    if not membership or not membership.can_manage_users:
        messages.error(request, "You don't have permission to manage invitations.")
        return redirect('org_settings_members')

    invitation = get_object_or_404(
        OrganizationInvitation,
        id=invitation_id,
        organization=org,
        status='pending'
    )

    invitation.status = 'expired'
    invitation.save()

    messages.success(request, f"Invitation to {invitation.email} has been cancelled.")
    return redirect('org_settings_members')


@login_required
def org_settings_billing(request):
    """Organization billing and subscription page."""
    from .models import SubscriptionPlan

    org = get_org(request)
    if not org:
        return redirect('dashboard')

    membership = getattr(request, 'membership', None)
    if not membership or not membership.can_manage_billing:
        from django.contrib import messages
        messages.error(request, "You don't have permission to manage billing.")
        return redirect('dashboard')

    # Get all available plans for comparison
    plans = SubscriptionPlan.objects.filter(
        is_active=True,
        is_public=True
    ).order_by('price_monthly_cents')

    return render(request, 'core/settings/billing.html', {
        'organization': org,
        'membership': membership,
        'plans': plans,
        'current_plan': org.subscription_plan,
    })
