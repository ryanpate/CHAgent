"""
Analytics and Reporting for Cherry Hills Worship Arts Portal.

This module provides comprehensive reporting capabilities:
- Volunteer engagement metrics
- Team care insights
- Interaction trends
- Prayer request themes
- Service participation analysis
- AI performance metrics
"""
from datetime import datetime, timedelta, date
from collections import Counter, defaultdict
from typing import Optional, Any
import logging

from django.db.models import Count, Q, Avg, F, Max
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone

from .models import (
    Volunteer,
    Interaction,
    FollowUp,
    ResponseFeedback,
    ExtractedKnowledge,
    ChatMessage,
)

logger = logging.getLogger(__name__)


def serialize_for_json(obj: Any) -> Any:
    """
    Recursively convert datetime objects to ISO format strings for JSON serialization.

    Args:
        obj: Any object (dict, list, datetime, etc.)

    Returns:
        JSON-serializable version of the object
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        # Handle model instances or other objects with __dict__
        return str(obj)
    return obj


class ReportGenerator:
    """
    Generates various analytics reports for the Worship Arts team.

    All methods return dictionaries that can be easily rendered in templates
    or serialized to JSON for API responses.
    """

    def __init__(self, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None):
        """
        Initialize the report generator with optional date range.

        Args:
            date_from: Start date for reports (default: 90 days ago)
            date_to: End date for reports (default: now)
        """
        self.date_to = date_to or timezone.now()
        self.date_from = date_from or (self.date_to - timedelta(days=90))

    # =========================================================================
    # VOLUNTEER ENGAGEMENT REPORTS
    # =========================================================================

    def volunteer_engagement_report(self) -> dict:
        """
        Generate a comprehensive volunteer engagement report.

        Returns:
            Dict containing:
            - total_volunteers: Total count
            - active_volunteers: Volunteers with interactions in date range
            - inactive_volunteers: Volunteers with no recent interactions
            - engagement_by_team: Breakdown by team
            - top_engaged: Most interacted-with volunteers
            - least_engaged: Volunteers needing attention
            - new_volunteers: Recently added
        """
        all_volunteers = Volunteer.objects.all()
        total = all_volunteers.count()

        # Volunteers with interactions in date range
        active_volunteer_ids = Interaction.objects.filter(
            created_at__gte=self.date_from,
            created_at__lte=self.date_to
        ).values_list('volunteers__id', flat=True).distinct()

        active_count = len(set(v for v in active_volunteer_ids if v is not None))
        inactive_count = total - active_count

        # Engagement by team
        engagement_by_team = {}
        teams = all_volunteers.exclude(team='').values_list('team', flat=True).distinct()

        for team in teams:
            team_volunteers = all_volunteers.filter(team=team)
            team_total = team_volunteers.count()
            team_active = team_volunteers.filter(id__in=active_volunteer_ids).count()
            engagement_by_team[team] = {
                'total': team_total,
                'active': team_active,
                'inactive': team_total - team_active,
                'engagement_rate': round((team_active / team_total * 100) if team_total > 0 else 0, 1)
            }

        # Top engaged volunteers (most interactions)
        top_engaged = Volunteer.objects.annotate(
            interaction_count=Count(
                'interactions',
                filter=Q(
                    interactions__created_at__gte=self.date_from,
                    interactions__created_at__lte=self.date_to
                )
            )
        ).filter(interaction_count__gt=0).order_by('-interaction_count')[:10]

        # Least engaged (have interactions but none recently)
        least_engaged = Volunteer.objects.annotate(
            total_interactions=Count('interactions'),
            recent_interactions=Count(
                'interactions',
                filter=Q(
                    interactions__created_at__gte=self.date_from,
                    interactions__created_at__lte=self.date_to
                )
            )
        ).filter(total_interactions__gt=0, recent_interactions=0).order_by('-total_interactions')[:10]

        # New volunteers (created in date range)
        new_volunteers = all_volunteers.filter(
            created_at__gte=self.date_from,
            created_at__lte=self.date_to
        ).order_by('-created_at')[:10]

        return {
            'date_range': {
                'from': self.date_from,
                'to': self.date_to,
            },
            'total_volunteers': total,
            'active_volunteers': active_count,
            'inactive_volunteers': inactive_count,
            'engagement_rate': round((active_count / total * 100) if total > 0 else 0, 1),
            'engagement_by_team': engagement_by_team,
            'top_engaged': [
                {
                    'id': v.id,
                    'name': v.name,
                    'team': v.team,
                    'interaction_count': v.interaction_count
                }
                for v in top_engaged
            ],
            'least_engaged': [
                {
                    'id': v.id,
                    'name': v.name,
                    'team': v.team,
                    'total_interactions': v.total_interactions,
                    'days_since_interaction': self._days_since_last_interaction(v)
                }
                for v in least_engaged
            ],
            'new_volunteers': [
                {
                    'id': v.id,
                    'name': v.name,
                    'team': v.team,
                    'created_at': v.created_at
                }
                for v in new_volunteers
            ]
        }

    def _days_since_last_interaction(self, volunteer) -> Optional[int]:
        """Get days since volunteer's last interaction."""
        last_interaction = volunteer.interactions.order_by('-created_at').first()
        if last_interaction:
            delta = timezone.now() - last_interaction.created_at
            return delta.days
        return None

    # =========================================================================
    # TEAM CARE REPORT
    # =========================================================================

    def team_care_report(self) -> dict:
        """
        Generate a report highlighting volunteers who need attention.

        Returns:
            Dict containing:
            - overdue_followups: Follow-ups past their due date
            - upcoming_followups: Follow-ups due in next 7 days
            - recent_prayer_requests: Recent prayer requests to be aware of
            - volunteers_to_check_in: Volunteers not interacted with recently
            - upcoming_birthdays: Birthdays in next 30 days
        """
        today = timezone.now().date()

        # Overdue follow-ups
        overdue_followups = FollowUp.objects.filter(
            status='pending',
            follow_up_date__lt=today
        ).select_related('volunteer', 'created_by').order_by('follow_up_date')[:20]

        # Upcoming follow-ups (next 7 days)
        upcoming_followups = FollowUp.objects.filter(
            status='pending',
            follow_up_date__gte=today,
            follow_up_date__lte=today + timedelta(days=7)
        ).select_related('volunteer', 'created_by').order_by('follow_up_date')[:20]

        # Recent prayer requests (from extracted knowledge)
        recent_prayer_requests = ExtractedKnowledge.objects.filter(
            knowledge_type='prayer_request',
            is_current=True,
            created_at__gte=self.date_from
        ).select_related('volunteer').order_by('-created_at')[:15]

        # Volunteers to check in with (no interactions in 30+ days but have previous interactions)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        volunteers_needing_checkin = Volunteer.objects.annotate(
            total_interactions=Count('interactions'),
            recent_interactions=Count(
                'interactions',
                filter=Q(interactions__created_at__gte=thirty_days_ago)
            )
        ).filter(
            total_interactions__gt=0,
            recent_interactions=0
        ).order_by('-total_interactions')[:15]

        # Upcoming birthdays (from extracted knowledge)
        # Parse birthday values and check if they fall within next 30 days
        upcoming_birthdays = self._get_upcoming_birthdays(days=30)

        return {
            'generated_at': timezone.now(),
            'overdue_followups': [
                {
                    'id': f.id,
                    'title': f.title,
                    'volunteer_name': f.volunteer.name if f.volunteer else 'General',
                    'volunteer_id': f.volunteer.id if f.volunteer else None,
                    'due_date': f.follow_up_date,
                    'days_overdue': (today - f.follow_up_date).days,
                    'priority': f.priority,
                    'category': f.category,
                    'created_by': f.created_by.display_name if f.created_by else 'Unknown'
                }
                for f in overdue_followups
            ],
            'overdue_count': overdue_followups.count() if hasattr(overdue_followups, 'count') else len(overdue_followups),
            'upcoming_followups': [
                {
                    'id': f.id,
                    'title': f.title,
                    'volunteer_name': f.volunteer.name if f.volunteer else 'General',
                    'volunteer_id': f.volunteer.id if f.volunteer else None,
                    'due_date': f.follow_up_date,
                    'days_until': (f.follow_up_date - today).days,
                    'priority': f.priority,
                    'category': f.category
                }
                for f in upcoming_followups
            ],
            'recent_prayer_requests': [
                {
                    'volunteer_name': pr.volunteer.name,
                    'volunteer_id': pr.volunteer.id,
                    'request': pr.value,
                    'date': pr.created_at,
                    'is_verified': pr.is_verified
                }
                for pr in recent_prayer_requests
            ],
            'volunteers_needing_checkin': [
                {
                    'id': v.id,
                    'name': v.name,
                    'team': v.team,
                    'total_interactions': v.total_interactions,
                    'days_since_interaction': self._days_since_last_interaction(v)
                }
                for v in volunteers_needing_checkin
            ],
            'upcoming_birthdays': upcoming_birthdays
        }

    def _get_upcoming_birthdays(self, days: int = 30) -> list:
        """Get volunteers with birthdays in the next N days."""
        birthday_knowledge = ExtractedKnowledge.objects.filter(
            knowledge_type='birthday',
            is_current=True
        ).select_related('volunteer')

        upcoming = []
        today = timezone.now().date()

        for bk in birthday_knowledge:
            try:
                # Try to parse common birthday formats
                birthday_str = bk.value.strip()
                birthday_date = None

                # Try various formats
                for fmt in ['%B %d', '%b %d', '%m/%d', '%m-%d', '%B %d, %Y', '%m/%d/%Y']:
                    try:
                        parsed = datetime.strptime(birthday_str, fmt)
                        # Set year to current year for comparison
                        birthday_date = parsed.replace(year=today.year).date()
                        # If birthday already passed this year, use next year
                        if birthday_date < today:
                            birthday_date = birthday_date.replace(year=today.year + 1)
                        break
                    except ValueError:
                        continue

                if birthday_date and (birthday_date - today).days <= days:
                    upcoming.append({
                        'volunteer_name': bk.volunteer.name,
                        'volunteer_id': bk.volunteer.id,
                        'birthday': birthday_str,
                        'date': birthday_date,
                        'days_until': (birthday_date - today).days
                    })
            except Exception:
                continue

        # Sort by days until birthday
        upcoming.sort(key=lambda x: x['days_until'])
        return upcoming[:15]

    # =========================================================================
    # INTERACTION TRENDS REPORT
    # =========================================================================

    def interaction_trends_report(self, group_by: str = 'week') -> dict:
        """
        Generate a report on interaction trends over time.

        Args:
            group_by: How to group data ('day', 'week', 'month')

        Returns:
            Dict containing:
            - trend_data: Time series of interaction counts
            - by_user: Breakdown by team member
            - by_team: Breakdown by volunteer team
            - peak_times: When most interactions are logged
            - total_stats: Summary statistics
        """
        interactions = Interaction.objects.filter(
            created_at__gte=self.date_from,
            created_at__lte=self.date_to
        )

        # Time series trend
        if group_by == 'day':
            trunc_func = TruncDate
        elif group_by == 'month':
            trunc_func = TruncMonth
        else:
            trunc_func = TruncWeek

        trend_data = interactions.annotate(
            period=trunc_func('created_at')
        ).values('period').annotate(
            count=Count('id')
        ).order_by('period')

        # By user (team member who logged)
        by_user = interactions.values(
            'user__display_name', 'user__username', 'user_id'
        ).annotate(
            count=Count('id')
        ).order_by('-count')

        # By volunteer team
        by_team = defaultdict(int)
        for interaction in interactions.prefetch_related('volunteers'):
            for volunteer in interaction.volunteers.all():
                if volunteer.team:
                    by_team[volunteer.team] += 1
                else:
                    by_team['Unassigned'] += 1

        # Peak logging times (hour of day)
        hour_counts = Counter()
        day_counts = Counter()
        for interaction in interactions:
            hour_counts[interaction.created_at.hour] += 1
            day_counts[interaction.created_at.strftime('%A')] += 1

        # Total stats
        total_count = interactions.count()
        unique_volunteers = interactions.values('volunteers').distinct().count()

        return {
            'date_range': {
                'from': self.date_from,
                'to': self.date_to,
            },
            'group_by': group_by,
            'trend_data': [
                {
                    'period': item['period'].isoformat() if item['period'] else None,
                    'count': item['count']
                }
                for item in trend_data
            ],
            'by_user': [
                {
                    'user_id': item['user_id'],
                    'display_name': item['user__display_name'] or item['user__username'] or 'Unknown',
                    'count': item['count']
                }
                for item in by_user
            ],
            'by_team': dict(sorted(by_team.items(), key=lambda x: x[1], reverse=True)),
            'peak_hours': dict(hour_counts.most_common(5)),
            'peak_days': dict(day_counts.most_common()),
            'total_stats': {
                'total_interactions': total_count,
                'unique_volunteers_mentioned': unique_volunteers,
                'avg_per_day': round(total_count / max((self.date_to - self.date_from).days, 1), 1),
            }
        }

    # =========================================================================
    # PRAYER REQUEST SUMMARY
    # =========================================================================

    def prayer_request_summary(self) -> dict:
        """
        Generate a summary of prayer requests and themes.

        Returns:
            Dict containing:
            - total_prayer_requests: Count
            - recent_requests: List of recent requests
            - common_themes: AI-extracted themes/categories
            - by_volunteer: Requests grouped by volunteer
            - pending_followups: Prayer-related follow-ups
        """
        # Get prayer requests from extracted knowledge
        prayer_knowledge = ExtractedKnowledge.objects.filter(
            knowledge_type='prayer_request',
            is_current=True
        ).select_related('volunteer').order_by('-created_at')

        total = prayer_knowledge.count()
        recent = prayer_knowledge[:20]

        # Extract common themes from prayer request content
        theme_counter = Counter()
        common_keywords = [
            'health', 'healing', 'family', 'work', 'job', 'marriage',
            'children', 'kids', 'grief', 'loss', 'anxiety', 'stress',
            'financial', 'money', 'relationship', 'guidance', 'direction',
            'peace', 'strength', 'wisdom', 'surgery', 'cancer', 'illness',
            'transition', 'moving', 'decision', 'school', 'college'
        ]

        for pr in prayer_knowledge:
            value_lower = pr.value.lower()
            for keyword in common_keywords:
                if keyword in value_lower:
                    theme_counter[keyword.title()] += 1

        # Group by volunteer
        by_volunteer = defaultdict(list)
        for pr in prayer_knowledge:
            by_volunteer[pr.volunteer.name].append({
                'request': pr.value,
                'date': pr.created_at,
                'is_verified': pr.is_verified
            })

        # Prayer-related follow-ups
        prayer_followups = FollowUp.objects.filter(
            Q(category='prayer_request') | Q(title__icontains='prayer') | Q(description__icontains='prayer'),
            status='pending'
        ).select_related('volunteer')[:15]

        return {
            'generated_at': timezone.now(),
            'total_prayer_requests': total,
            'recent_requests': [
                {
                    'volunteer_name': pr.volunteer.name,
                    'volunteer_id': pr.volunteer.id,
                    'request': pr.value,
                    'date': pr.created_at,
                    'is_verified': pr.is_verified
                }
                for pr in recent
            ],
            'common_themes': dict(theme_counter.most_common(10)),
            'by_volunteer': dict(by_volunteer),
            'pending_followups': [
                {
                    'id': f.id,
                    'title': f.title,
                    'volunteer_name': f.volunteer.name if f.volunteer else 'General',
                    'due_date': f.follow_up_date,
                    'priority': f.priority
                }
                for f in prayer_followups
            ]
        }

    # =========================================================================
    # AI PERFORMANCE REPORT
    # =========================================================================

    def ai_performance_report(self) -> dict:
        """
        Generate a report on AI (Aria) performance based on feedback.

        Returns:
            Dict containing:
            - total_responses: Total AI responses
            - feedback_rate: Percentage of responses that received feedback
            - positive_rate: Percentage of positive feedback
            - issue_breakdown: Common issue types
            - resolution_rate: How many issues have been resolved
            - trend: Feedback trend over time
        """
        # All feedback in date range
        feedback = ResponseFeedback.objects.filter(
            created_at__gte=self.date_from,
            created_at__lte=self.date_to
        )

        total_feedback = feedback.count()
        positive = feedback.filter(feedback_type='positive').count()
        negative = feedback.filter(feedback_type='negative').count()

        # Issue breakdown (for negative feedback)
        issue_breakdown = dict(
            feedback.filter(
                feedback_type='negative'
            ).exclude(
                issue_type=''
            ).values('issue_type').annotate(
                count=Count('id')
            ).values_list('issue_type', 'count')
        )

        # Resolution rate
        resolved = feedback.filter(feedback_type='negative', resolved=True).count()
        resolution_rate = round((resolved / negative * 100) if negative > 0 else 100, 1)

        # Feedback trend over time
        trend = feedback.annotate(
            week=TruncWeek('created_at')
        ).values('week', 'feedback_type').annotate(
            count=Count('id')
        ).order_by('week')

        # Total chat messages (to calculate feedback rate)
        total_ai_responses = ChatMessage.objects.filter(
            role='assistant',
            created_at__gte=self.date_from,
            created_at__lte=self.date_to
        ).count()

        # Recent unresolved issues
        unresolved_issues = feedback.filter(
            feedback_type='negative',
            resolved=False
        ).select_related('chat_message', 'user').order_by('-created_at')[:10]

        return {
            'date_range': {
                'from': self.date_from,
                'to': self.date_to,
            },
            'total_ai_responses': total_ai_responses,
            'total_feedback': total_feedback,
            'feedback_rate': round((total_feedback / total_ai_responses * 100) if total_ai_responses > 0 else 0, 1),
            'positive_count': positive,
            'negative_count': negative,
            'positive_rate': round((positive / total_feedback * 100) if total_feedback > 0 else 0, 1),
            'issue_breakdown': issue_breakdown,
            'resolution_rate': resolution_rate,
            'unresolved_count': negative - resolved,
            'trend': [
                {
                    'week': item['week'].isoformat() if item['week'] else None,
                    'feedback_type': item['feedback_type'],
                    'count': item['count']
                }
                for item in trend
            ],
            'unresolved_issues': [
                {
                    'id': f.id,
                    'issue_type': f.issue_type,
                    'issue_type_display': dict(ResponseFeedback.ISSUE_TYPE_CHOICES).get(f.issue_type, f.issue_type),
                    'comment': f.comment[:100] + '...' if len(f.comment) > 100 else f.comment,
                    'expected_result': f.expected_result[:100] + '...' if len(f.expected_result) > 100 else f.expected_result,
                    'user': f.user.display_name if hasattr(f.user, 'display_name') else str(f.user),
                    'created_at': f.created_at
                }
                for f in unresolved_issues
            ]
        }

    # =========================================================================
    # SERVICE PARTICIPATION (via Planning Center)
    # =========================================================================

    def service_participation_report(self, service_type: str = None) -> dict:
        """
        Generate a report on service participation patterns.

        This uses Planning Center data if available, otherwise falls back
        to interaction data.

        Args:
            service_type: Optional filter by service type

        Returns:
            Dict containing participation metrics
        """
        # Try to get Planning Center data
        try:
            from .planning_center import PlanningCenterAPI
            pco = PlanningCenterAPI()

            # Get recent plans
            plans = pco.get_recent_plans(limit=10, service_type_name=service_type)

            participation_data = []
            volunteer_service_counts = Counter()

            for plan in plans:
                plan_id = plan.get('id')
                plan_date = plan.get('attributes', {}).get('dates', 'Unknown')

                # Get team members for this plan
                team_members = pco.get_plan_team_members(plan_id)

                participation_data.append({
                    'date': plan_date,
                    'plan_id': plan_id,
                    'team_count': len(team_members),
                    'team_members': [tm.get('name', 'Unknown') for tm in team_members[:10]]
                })

                for member in team_members:
                    name = member.get('name', 'Unknown')
                    volunteer_service_counts[name] += 1

            # Most active volunteers
            most_active = volunteer_service_counts.most_common(15)

            return {
                'source': 'planning_center',
                'service_type': service_type or 'All Services',
                'recent_services': participation_data,
                'most_active_volunteers': [
                    {'name': name, 'service_count': count}
                    for name, count in most_active
                ],
                'total_unique_volunteers': len(volunteer_service_counts),
                'avg_team_size': round(
                    sum(p['team_count'] for p in participation_data) / len(participation_data)
                    if participation_data else 0,
                    1
                )
            }
        except Exception as e:
            logger.warning(f"Could not fetch Planning Center data: {e}")

            # Fall back to interaction-based estimates
            return self._fallback_participation_report()

    def _fallback_participation_report(self) -> dict:
        """Fallback participation report using interaction data."""
        # Use interaction frequency as a proxy for participation
        volunteer_activity = Volunteer.objects.annotate(
            interaction_count=Count(
                'interactions',
                filter=Q(
                    interactions__created_at__gte=self.date_from,
                    interactions__created_at__lte=self.date_to
                )
            )
        ).filter(interaction_count__gt=0).order_by('-interaction_count')

        return {
            'source': 'interactions',
            'note': 'Based on interaction frequency (Planning Center data unavailable)',
            'most_active_volunteers': [
                {
                    'name': v.name,
                    'team': v.team,
                    'interaction_count': v.interaction_count
                }
                for v in volunteer_activity[:15]
            ],
            'total_active_volunteers': volunteer_activity.count()
        }

    # =========================================================================
    # DASHBOARD SUMMARY
    # =========================================================================

    def dashboard_summary(self) -> dict:
        """
        Generate a quick summary for the analytics dashboard.

        Returns aggregated key metrics for quick overview.
        """
        today = timezone.now().date()
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # Quick counts
        total_volunteers = Volunteer.objects.count()
        total_interactions = Interaction.objects.count()
        recent_interactions = Interaction.objects.filter(
            created_at__gte=thirty_days_ago
        ).count()

        # Follow-up stats
        pending_followups = FollowUp.objects.filter(status='pending').count()
        overdue_followups = FollowUp.objects.filter(
            status='pending',
            follow_up_date__lt=today
        ).count()

        # Feedback stats
        recent_feedback = ResponseFeedback.objects.filter(
            created_at__gte=thirty_days_ago
        )
        positive_feedback = recent_feedback.filter(feedback_type='positive').count()
        total_recent_feedback = recent_feedback.count()

        # Active team members (who have logged interactions)
        active_team_members = Interaction.objects.filter(
            created_at__gte=thirty_days_ago
        ).values('user').distinct().count()

        # Prayer requests this month
        prayer_requests = ExtractedKnowledge.objects.filter(
            knowledge_type='prayer_request',
            created_at__gte=thirty_days_ago
        ).count()

        return {
            'generated_at': timezone.now(),
            'volunteers': {
                'total': total_volunteers,
                'with_recent_interactions': Volunteer.objects.filter(
                    interactions__created_at__gte=thirty_days_ago
                ).distinct().count()
            },
            'interactions': {
                'total': total_interactions,
                'last_30_days': recent_interactions,
                'avg_per_day': round(recent_interactions / 30, 1)
            },
            'followups': {
                'pending': pending_followups,
                'overdue': overdue_followups,
                'due_today': FollowUp.objects.filter(
                    status='pending',
                    follow_up_date=today
                ).count()
            },
            'ai_feedback': {
                'total_recent': total_recent_feedback,
                'positive_rate': round(
                    (positive_feedback / total_recent_feedback * 100)
                    if total_recent_feedback > 0 else 0,
                    1
                )
            },
            'team': {
                'active_members': active_team_members
            },
            'care': {
                'prayer_requests_this_month': prayer_requests,
                'volunteers_needing_checkin': Volunteer.objects.annotate(
                    recent_interactions=Count(
                        'interactions',
                        filter=Q(interactions__created_at__gte=thirty_days_ago)
                    ),
                    total_interactions=Count('interactions')
                ).filter(
                    total_interactions__gt=0,
                    recent_interactions=0
                ).count()
            }
        }


# =============================================================================
# HELPER FUNCTIONS FOR ARIA INTEGRATION
# =============================================================================

def get_analytics_summary_for_aria() -> str:
    """
    Generate a text summary of analytics for Aria to use in responses.

    This is called when users ask Aria for team insights or statistics.
    """
    generator = ReportGenerator()
    summary = generator.dashboard_summary()

    text_parts = [
        f"**Team Overview (Last 30 Days)**",
        f"",
        f"**Volunteers:** {summary['volunteers']['total']} total, "
        f"{summary['volunteers']['with_recent_interactions']} with recent interactions",
        f"",
        f"**Interactions:** {summary['interactions']['last_30_days']} logged "
        f"(avg {summary['interactions']['avg_per_day']}/day)",
        f"",
        f"**Follow-ups:** {summary['followups']['pending']} pending, "
        f"{summary['followups']['overdue']} overdue, "
        f"{summary['followups']['due_today']} due today",
        f"",
        f"**Care Needs:** {summary['care']['prayer_requests_this_month']} prayer requests this month, "
        f"{summary['care']['volunteers_needing_checkin']} volunteers haven't been contacted in 30+ days",
    ]

    if summary['ai_feedback']['total_recent'] > 0:
        text_parts.extend([
            f"",
            f"**AI Feedback:** {summary['ai_feedback']['positive_rate']}% positive feedback rate"
        ])

    return "\n".join(text_parts)


def get_volunteers_needing_attention() -> list:
    """
    Get a list of volunteers who need attention.

    Used by Aria to proactively suggest check-ins.
    """
    generator = ReportGenerator()
    care_report = generator.team_care_report()

    return care_report['volunteers_needing_checkin']


def get_prayer_request_summary_for_aria() -> str:
    """
    Generate a prayer request summary for Aria.
    """
    generator = ReportGenerator()
    report = generator.prayer_request_summary()

    if not report['recent_requests']:
        return "No recent prayer requests have been logged."

    text_parts = [
        f"**Recent Prayer Requests** ({report['total_prayer_requests']} total)",
        ""
    ]

    for pr in report['recent_requests'][:10]:
        date_str = pr['date'].strftime('%b %d') if pr['date'] else 'Unknown'
        text_parts.append(f"- **{pr['volunteer_name']}** ({date_str}): {pr['request']}")

    if report['common_themes']:
        themes = ', '.join(report['common_themes'].keys())
        text_parts.extend([
            "",
            f"**Common themes:** {themes}"
        ])

    return "\n".join(text_parts)


# =============================================================================
# PROACTIVE CARE GENERATOR
# =============================================================================

class ProactiveCareGenerator:
    """
    Generates proactive care insights for volunteers.

    This class analyzes volunteer data to identify those who may need
    attention, follow-up, or special care from the team.
    """

    def __init__(self):
        self.today = timezone.now().date()
        self.now = timezone.now()

    def generate_all_insights(self) -> dict:
        """
        Generate all types of proactive care insights.

        Returns:
            Dict with counts and lists of generated insights by type.
        """
        results = {
            'generated_at': self.now,
            'total_new': 0,
            'by_type': {},
        }

        # Generate each type of insight
        generators = [
            ('no_recent_contact', self._generate_no_contact_insights),
            ('prayer_need', self._generate_prayer_insights),
            ('birthday_upcoming', self._generate_birthday_insights),
            ('overdue_followup', self._generate_overdue_followup_insights),
            ('new_volunteer', self._generate_new_volunteer_insights),
        ]

        for insight_type, generator_func in generators:
            count = generator_func()
            results['by_type'][insight_type] = count
            results['total_new'] += count

        return results

    def _generate_no_contact_insights(self) -> int:
        """Generate insights for volunteers with no recent contact."""
        from .models import VolunteerInsight

        thirty_days_ago = self.now - timedelta(days=30)
        sixty_days_ago = self.now - timedelta(days=60)

        # Find volunteers with interactions but none recently
        volunteers_needing_contact = Volunteer.objects.annotate(
            total_interactions=Count('interactions'),
            recent_interactions=Count(
                'interactions',
                filter=Q(interactions__created_at__gte=thirty_days_ago)
            ),
            last_interaction_date=Max('interactions__created_at')
        ).filter(
            total_interactions__gt=0,
            recent_interactions=0
        )

        count = 0
        for volunteer in volunteers_needing_contact:
            # Check if we already have an active insight for this
            existing = VolunteerInsight.objects.filter(
                volunteer=volunteer,
                insight_type='no_recent_contact',
                status='active'
            ).exists()

            if not existing:
                days_since = (self.now - volunteer.last_interaction_date).days if volunteer.last_interaction_date else 999

                # Determine priority based on how long since contact
                if days_since > 90:
                    priority = 'high'
                elif days_since > 60:
                    priority = 'medium'
                else:
                    priority = 'low'

                VolunteerInsight.objects.create(
                    volunteer=volunteer,
                    insight_type='no_recent_contact',
                    priority=priority,
                    title=f"No contact with {volunteer.name} in {days_since} days",
                    message=f"{volunteer.name} hasn't had any logged interactions in {days_since} days. "
                            f"Consider reaching out to check in on them.",
                    suggested_action=f"Send a message or schedule a brief check-in with {volunteer.name}.",
                    context_data={
                        'days_since_contact': days_since,
                        'total_interactions': volunteer.total_interactions,
                        'team': volunteer.team or 'Unassigned'
                    }
                )
                count += 1

        return count

    def _generate_prayer_insights(self) -> int:
        """Generate insights for volunteers with recent prayer requests."""
        from .models import VolunteerInsight

        seven_days_ago = self.now - timedelta(days=7)

        # Find recent prayer requests
        recent_prayers = ExtractedKnowledge.objects.filter(
            knowledge_type='prayer_request',
            is_current=True,
            created_at__gte=seven_days_ago
        ).select_related('volunteer')

        count = 0
        for prayer in recent_prayers:
            # Check if we already have an active insight for this prayer
            existing = VolunteerInsight.objects.filter(
                volunteer=prayer.volunteer,
                insight_type='prayer_need',
                status='active',
                context_data__contains={'prayer_id': prayer.id}
            ).exists()

            if not existing:
                VolunteerInsight.objects.create(
                    volunteer=prayer.volunteer,
                    insight_type='prayer_need',
                    priority='medium',
                    title=f"Prayer request from {prayer.volunteer.name}",
                    message=f"{prayer.volunteer.name} shared a prayer request: {prayer.value[:100]}{'...' if len(prayer.value) > 100 else ''}",
                    suggested_action="Follow up to see how they're doing and if there's anything the team can do to help.",
                    context_data={
                        'prayer_id': prayer.id,
                        'prayer_text': prayer.value,
                        'logged_date': prayer.created_at.isoformat()
                    }
                )
                count += 1

        return count

    def _generate_birthday_insights(self) -> int:
        """Generate insights for upcoming volunteer birthdays."""
        from .models import VolunteerInsight

        # Get birthdays from extracted knowledge
        birthday_knowledge = ExtractedKnowledge.objects.filter(
            knowledge_type='birthday',
            is_current=True
        ).select_related('volunteer')

        count = 0
        for bk in birthday_knowledge:
            try:
                # Parse the birthday
                birthday_str = bk.value.strip()
                birthday_date = None

                for fmt in ['%B %d', '%b %d', '%m/%d', '%m-%d', '%B %d, %Y', '%m/%d/%Y']:
                    try:
                        parsed = datetime.strptime(birthday_str, fmt)
                        birthday_date = parsed.replace(year=self.today.year).date()
                        if birthday_date < self.today:
                            birthday_date = birthday_date.replace(year=self.today.year + 1)
                        break
                    except ValueError:
                        continue

                if birthday_date:
                    days_until = (birthday_date - self.today).days

                    # Only create insights for birthdays within 7 days
                    if 0 <= days_until <= 7:
                        existing = VolunteerInsight.objects.filter(
                            volunteer=bk.volunteer,
                            insight_type='birthday_upcoming',
                            status='active'
                        ).exists()

                        if not existing:
                            if days_until == 0:
                                priority = 'urgent'
                                title = f"Today is {bk.volunteer.name}'s birthday!"
                            elif days_until == 1:
                                priority = 'high'
                                title = f"{bk.volunteer.name}'s birthday is tomorrow"
                            else:
                                priority = 'medium'
                                title = f"{bk.volunteer.name}'s birthday in {days_until} days"

                            VolunteerInsight.objects.create(
                                volunteer=bk.volunteer,
                                insight_type='birthday_upcoming',
                                priority=priority,
                                title=title,
                                message=f"{bk.volunteer.name}'s birthday is {birthday_str}. "
                                        f"Consider sending a card or acknowledgment.",
                                suggested_action="Send a birthday message or coordinate with the team for a small celebration.",
                                context_data={
                                    'birthday': birthday_str,
                                    'days_until': days_until
                                }
                            )
                            count += 1
            except Exception:
                continue

        return count

    def _generate_overdue_followup_insights(self) -> int:
        """Generate insights for overdue follow-ups."""
        from .models import VolunteerInsight

        overdue_followups = FollowUp.objects.filter(
            status='pending',
            follow_up_date__lt=self.today,
            volunteer__isnull=False
        ).select_related('volunteer')

        count = 0
        for followup in overdue_followups:
            existing = VolunteerInsight.objects.filter(
                volunteer=followup.volunteer,
                insight_type='overdue_followup',
                status='active',
                context_data__contains={'followup_id': followup.id}
            ).exists()

            if not existing:
                days_overdue = (self.today - followup.follow_up_date).days

                if days_overdue > 14:
                    priority = 'urgent'
                elif days_overdue > 7:
                    priority = 'high'
                else:
                    priority = 'medium'

                VolunteerInsight.objects.create(
                    volunteer=followup.volunteer,
                    insight_type='overdue_followup',
                    priority=priority,
                    title=f"Overdue follow-up for {followup.volunteer.name}",
                    message=f"Follow-up '{followup.title}' was due {days_overdue} days ago.",
                    suggested_action=f"Complete or reschedule the follow-up: {followup.title}",
                    context_data={
                        'followup_id': followup.id,
                        'followup_title': followup.title,
                        'due_date': followup.follow_up_date.isoformat(),
                        'days_overdue': days_overdue
                    }
                )
                count += 1

        return count

    def _generate_new_volunteer_insights(self) -> int:
        """Generate insights for new volunteers who may need check-ins."""
        from .models import VolunteerInsight

        # Volunteers created in the last 30 days
        thirty_days_ago = self.now - timedelta(days=30)

        new_volunteers = Volunteer.objects.filter(
            created_at__gte=thirty_days_ago
        ).annotate(
            interaction_count=Count('interactions')
        )

        count = 0
        for volunteer in new_volunteers:
            # Only flag if they have few interactions (may be falling through cracks)
            if volunteer.interaction_count < 2:
                existing = VolunteerInsight.objects.filter(
                    volunteer=volunteer,
                    insight_type='new_volunteer',
                    status='active'
                ).exists()

                if not existing:
                    days_since_added = (self.now - volunteer.created_at).days

                    VolunteerInsight.objects.create(
                        volunteer=volunteer,
                        insight_type='new_volunteer',
                        priority='medium',
                        title=f"New volunteer {volunteer.name} may need attention",
                        message=f"{volunteer.name} was added {days_since_added} days ago but only has "
                                f"{volunteer.interaction_count} logged interaction(s). "
                                f"Consider scheduling an onboarding check-in.",
                        suggested_action="Schedule a welcome call or check-in to see how they're settling in.",
                        context_data={
                            'days_since_added': days_since_added,
                            'interaction_count': volunteer.interaction_count,
                            'team': volunteer.team or 'Unassigned'
                        }
                    )
                    count += 1

        return count

    def get_proactive_care_dashboard(self) -> dict:
        """
        Get data for the proactive care dashboard.

        Returns:
            Dict with active insights grouped by priority and type.
        """
        from .models import VolunteerInsight

        active_insights = VolunteerInsight.objects.filter(
            status='active'
        ).select_related('volunteer').order_by('-priority', '-created_at')

        # Group by priority
        by_priority = {
            'urgent': [],
            'high': [],
            'medium': [],
            'low': [],
        }

        # Group by type
        by_type = defaultdict(list)

        for insight in active_insights:
            insight_data = {
                'id': insight.id,
                'volunteer_id': insight.volunteer.id,
                'volunteer_name': insight.volunteer.name,
                'volunteer_team': insight.volunteer.team,
                'insight_type': insight.insight_type,
                'insight_type_display': insight.get_insight_type_display(),
                'priority': insight.priority,
                'title': insight.title,
                'message': insight.message,
                'suggested_action': insight.suggested_action,
                'context_data': insight.context_data,
                'created_at': insight.created_at,
            }

            by_priority[insight.priority].append(insight_data)
            by_type[insight.insight_type].append(insight_data)

        # Summary counts
        total_active = active_insights.count()
        urgent_count = len(by_priority['urgent'])
        high_count = len(by_priority['high'])

        return {
            'generated_at': self.now,
            'total_active': total_active,
            'urgent_count': urgent_count,
            'high_count': high_count,
            'needs_attention': urgent_count + high_count,
            'by_priority': by_priority,
            'by_type': dict(by_type),
            'type_counts': {
                insight_type: len(insights)
                for insight_type, insights in by_type.items()
            }
        }


def get_proactive_care_for_aria() -> str:
    """
    Generate a proactive care summary for Aria.
    """
    generator = ProactiveCareGenerator()
    dashboard = generator.get_proactive_care_dashboard()

    if dashboard['total_active'] == 0:
        return "Great news! There are no volunteers currently flagged as needing special attention."

    text_parts = [
        f"**Proactive Care Summary**",
        f"",
        f"**{dashboard['total_active']}** volunteers need attention:",
    ]

    if dashboard['urgent_count'] > 0:
        text_parts.append(f"- **{dashboard['urgent_count']} urgent** (immediate action needed)")

    if dashboard['high_count'] > 0:
        text_parts.append(f"- **{dashboard['high_count']} high priority**")

    text_parts.append("")
    text_parts.append("**Top priorities:**")

    # Show top 5 urgent/high priority items
    all_urgent_high = dashboard['by_priority']['urgent'] + dashboard['by_priority']['high']
    for insight in all_urgent_high[:5]:
        text_parts.append(f"- {insight['title']}")

    text_parts.append("")
    text_parts.append("View the [Proactive Care Dashboard](/care/) for full details.")

    return "\n".join(text_parts)
