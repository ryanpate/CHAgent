"""
Views for the Cherry Hills Worship Arts Portal.
"""
import json
import uuid
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Count
from django.utils import timezone

from .models import Interaction, Volunteer, ChatMessage, ConversationContext, FollowUp, ResponseFeedback
from .agent import (
    query_agent,
    process_interaction,
    detect_interaction_intent,
    confirm_volunteer_match,
    skip_volunteer_match
)
from .volunteer_matching import VolunteerMatcher, MatchType

import re


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


@login_required
def dashboard(request):
    """Dashboard view with overview statistics and AI chat interface."""
    # Get or create session ID from cookie for chat
    session_id = request.COOKIES.get('chat_session_id')
    if not session_id:
        session_id = str(uuid.uuid4())

    # Get chat messages for this session
    chat_messages = ChatMessage.objects.filter(
        user=request.user,
        session_id=session_id
    ).order_by('created_at')

    context = {
        'total_volunteers': Volunteer.objects.count(),
        'total_interactions': Interaction.objects.count(),
        'recent_interactions': Interaction.objects.select_related('user').prefetch_related('volunteers')[:5],
        'top_volunteers': Volunteer.objects.annotate(
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
    message = request.POST.get('message', '').strip()
    session_id = request.COOKIES.get('chat_session_id', str(uuid.uuid4()))

    if not message:
        return HttpResponse('')

    # Check if this message should start a new conversation
    # This keeps the chat window clean and focused on one topic at a time
    start_new_session = should_start_new_conversation(message)
    if start_new_session:
        session_id = str(uuid.uuid4())

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
    # Get filter parameters
    filter_type = request.GET.get('type', 'all')  # all, positive, negative
    filter_resolved = request.GET.get('resolved', 'all')  # all, yes, no
    filter_issue = request.GET.get('issue', '')  # specific issue type

    # Base queryset
    feedbacks = ResponseFeedback.objects.select_related(
        'chat_message', 'user', 'resolved_by'
    ).order_by('-created_at')

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

    # Get counts for stats
    total_count = ResponseFeedback.objects.count()
    positive_count = ResponseFeedback.objects.filter(feedback_type='positive').count()
    negative_count = ResponseFeedback.objects.filter(feedback_type='negative').count()
    unresolved_count = ResponseFeedback.objects.filter(
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

    feedback = get_object_or_404(ResponseFeedback, pk=pk)
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


# ============================================================================
# Follow-up Views
# ============================================================================

@login_required
def followup_list(request):
    """List all follow-ups with filtering options."""
    from django.utils import timezone
    from datetime import timedelta

    # Get filter parameters
    status_filter = request.GET.get('status', 'pending')
    priority_filter = request.GET.get('priority', '')
    date_filter = request.GET.get('date', '')

    # Base queryset
    followups = FollowUp.objects.select_related('volunteer', 'created_by', 'assigned_to')

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

    # Get counts for sidebar/stats
    overdue_count = FollowUp.objects.filter(
        follow_up_date__lt=today,
        status='pending'
    ).count()
    today_count = FollowUp.objects.filter(
        follow_up_date=today,
        status='pending'
    ).count()
    pending_count = FollowUp.objects.filter(status='pending').count()

    context = {
        'followups': followups[:50],
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'date_filter': date_filter,
        'overdue_count': overdue_count,
        'today_count': today_count,
        'pending_count': pending_count,
        'volunteers': Volunteer.objects.all()[:100],  # For the create form dropdown
    }
    return render(request, 'core/followup_list.html', context)


@login_required
def followup_detail(request, pk):
    """View details of a single follow-up."""
    followup = get_object_or_404(FollowUp, pk=pk)
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

    # Get volunteer if specified
    volunteer = None
    if volunteer_id:
        try:
            volunteer = Volunteer.objects.get(pk=int(volunteer_id))
        except (ValueError, Volunteer.DoesNotExist):
            pass

    followup = FollowUp.objects.create(
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
    followup = get_object_or_404(FollowUp, pk=pk)
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

    followup = get_object_or_404(FollowUp, pk=pk)

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
                followup.volunteer = Volunteer.objects.get(pk=int(vol_id))
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
    followup = get_object_or_404(FollowUp, pk=pk)
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

    # Parse date range from request
    days = int(request.GET.get('days', 30))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    # Check cache first
    cache_params = {'days': days}
    cached = ReportCache.get_cached_report('dashboard_summary', cache_params)

    if cached:
        summary = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to)
        summary = serialize_for_json(generator.dashboard_summary())
        # Cache for 15 minutes
        ReportCache.set_cached_report('dashboard_summary', summary, cache_params, ttl_minutes=15)

    # Get quick team care insights
    care_cached = ReportCache.get_cached_report('team_care', cache_params)
    if care_cached:
        care_report = care_cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to)
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

    days = int(request.GET.get('days', 90))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    cache_params = {'days': days}
    cached = ReportCache.get_cached_report('volunteer_engagement', cache_params)

    if cached:
        report = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to)
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

    days = int(request.GET.get('days', 30))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    cache_params = {'days': days}
    cached = ReportCache.get_cached_report('team_care', cache_params)

    if cached:
        report = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to)
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

    days = int(request.GET.get('days', 90))
    group_by = request.GET.get('group_by', 'week')
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    cache_params = {'days': days, 'group_by': group_by}
    cached = ReportCache.get_cached_report('interaction_trends', cache_params)

    if cached:
        report = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to)
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

    days = int(request.GET.get('days', 90))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    cache_params = {'days': days}
    cached = ReportCache.get_cached_report('prayer_summary', cache_params)

    if cached:
        report = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to)
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

    days = int(request.GET.get('days', 30))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    cache_params = {'days': days}
    cached = ReportCache.get_cached_report('ai_performance', cache_params)

    if cached:
        report = cached
    else:
        generator = ReportGenerator(date_from=date_from, date_to=date_to)
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

    days = int(request.GET.get('days', 90))
    date_to = timezone.now()
    date_from = date_to - timedelta(days=days)

    generator = ReportGenerator(date_from=date_from, date_to=date_to)

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

    # Generate new insights if requested
    if request.GET.get('refresh') == '1':
        generator = ProactiveCareGenerator()
        generator.generate_all_insights()
        return redirect('care_dashboard')

    # Get dashboard data
    generator = ProactiveCareGenerator()
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
    ]

    context = {
        'dashboard': dashboard,
        'insights': filtered_insights if (filter_type or filter_priority) else all_insights,
        'filter_type': filter_type,
        'filter_priority': filter_priority,
        'type_choices': type_choices,
    }
    return render(request, 'core/care/dashboard.html', context)


@login_required
@require_POST
def care_dismiss_insight(request, pk):
    """
    Dismiss an insight (mark as addressed/dismissed).
    """
    from .models import VolunteerInsight

    insight = get_object_or_404(VolunteerInsight, pk=pk)
    action = request.POST.get('action', 'dismiss')
    notes = request.POST.get('notes', '')

    if action == 'address':
        insight.status = 'addressed'
    else:
        insight.status = 'dismissed'

    insight.addressed_by = request.user
    insight.addressed_at = timezone.now()
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

    insight = get_object_or_404(VolunteerInsight, pk=pk)

    # Create a follow-up based on the insight
    followup = FollowUp.objects.create(
        created_by=request.user,
        volunteer=insight.volunteer,
        title=insight.title,
        description=f"{insight.message}\n\nSuggested action: {insight.suggested_action}",
        priority='high' if insight.priority in ['urgent', 'high'] else 'medium',
        category='care',
    )

    # Mark insight as addressed
    insight.status = 'addressed'
    insight.addressed_by = request.user
    insight.addressed_at = timezone.now()
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
    Generate new proactive care insights.
    """
    from .reports import ProactiveCareGenerator

    generator = ProactiveCareGenerator()
    results = generator.generate_all_insights()

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/care_refresh_result.html', {
            'results': results,
        })

    return redirect('care_dashboard')
