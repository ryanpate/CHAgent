"""
Platform administration views for superadmins.

These views allow platform administrators to monitor and manage
all organizations, users, subscriptions, and usage metrics across
the entire platform.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.contrib import messages

from .models import (
    Organization, SubscriptionPlan, OrganizationMembership,
    Volunteer, Interaction, ChatMessage, FollowUp,
    Announcement, Channel, Project, Task, BetaRequest
)
from accounts.models import User
from .middleware import require_superadmin


@login_required
@require_superadmin
def admin_dashboard(request):
    """
    Platform admin dashboard with overview metrics.

    Shows key metrics across all organizations:
    - Total organizations, active/trial/expired counts
    - Total revenue (MRR, ARR)
    - User counts
    - AI usage
    - Recent signups
    """
    # Organization metrics
    total_orgs = Organization.objects.count()
    active_orgs = Organization.objects.filter(subscription_status='active').count()
    trial_orgs = Organization.objects.filter(subscription_status='trial').count()
    past_due_orgs = Organization.objects.filter(subscription_status='past_due').count()
    cancelled_orgs = Organization.objects.filter(subscription_status='cancelled').count()

    # Revenue metrics (from active subscriptions)
    active_subscriptions = Organization.objects.filter(
        subscription_status__in=['active', 'past_due']
    ).select_related('subscription_plan')

    mrr = sum(
        org.subscription_plan.price_monthly_cents if org.subscription_plan else 0
        for org in active_subscriptions
    ) / 100  # Convert cents to dollars

    arr = mrr * 12

    # User metrics
    total_users = User.objects.count()
    active_users_30d = User.objects.filter(
        last_login__gte=timezone.now() - timedelta(days=30)
    ).count()

    # AI usage metrics
    total_ai_queries = Organization.objects.aggregate(
        total=Sum('ai_queries_this_month')
    )['total'] or 0

    # Recent signups (last 30 days)
    recent_orgs = Organization.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    ).order_by('-created_at')[:10]

    # Subscription plan distribution
    plan_distribution = Organization.objects.values(
        'subscription_plan__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')

    context = {
        'total_orgs': total_orgs,
        'active_orgs': active_orgs,
        'trial_orgs': trial_orgs,
        'past_due_orgs': past_due_orgs,
        'cancelled_orgs': cancelled_orgs,
        'mrr': mrr,
        'arr': arr,
        'total_users': total_users,
        'active_users_30d': active_users_30d,
        'total_ai_queries': total_ai_queries,
        'recent_orgs': recent_orgs,
        'plan_distribution': plan_distribution,
    }

    return render(request, 'core/admin/dashboard.html', context)


@login_required
@require_superadmin
def admin_organizations_list(request):
    """
    List all organizations with filtering and search.

    Filters:
    - status (active, trial, past_due, cancelled)
    - plan tier
    - search by name
    """
    organizations = Organization.objects.all().select_related('subscription_plan')

    # Apply filters
    status = request.GET.get('status')
    if status:
        organizations = organizations.filter(subscription_status=status)

    plan = request.GET.get('plan')
    if plan:
        organizations = organizations.filter(subscription_plan__slug=plan)

    search = request.GET.get('search')
    if search:
        organizations = organizations.filter(
            Q(name__icontains=search) |
            Q(slug__icontains=search) |
            Q(email__icontains=search)
        )

    # Annotate with usage metrics
    organizations = organizations.annotate(
        member_count=Count('memberships', filter=Q(memberships__is_active=True)),
        volunteer_count=Count('volunteers', distinct=True),
        interaction_count=Count('interactions', distinct=True),
    )

    # Order by most recent first
    organizations = organizations.order_by('-created_at')

    # Get all plans for filter dropdown
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order')

    context = {
        'organizations': organizations,
        'plans': plans,
        'current_status': status,
        'current_plan': plan,
        'search_query': search,
    }

    return render(request, 'core/admin/organizations_list.html', context)


@login_required
@require_superadmin
def admin_organization_detail(request, org_id):
    """
    Detailed view of a single organization.

    Shows:
    - Organization details
    - Subscription info
    - Members and roles
    - Usage statistics
    - Recent activity
    """
    organization = get_object_or_404(
        Organization.objects.select_related('subscription_plan'),
        id=org_id
    )

    # Get members
    memberships = OrganizationMembership.objects.filter(
        organization=organization
    ).select_related('user').order_by('-role', 'user__display_name')

    # Usage statistics
    stats = {
        'volunteers': Volunteer.objects.filter(organization=organization).count(),
        'interactions': Interaction.objects.filter(organization=organization).count(),
        'chat_messages': ChatMessage.objects.filter(organization=organization).count(),
        'followups': FollowUp.objects.filter(organization=organization).count(),
        'announcements': Announcement.objects.filter(organization=organization).count(),
        'channels': Channel.objects.filter(organization=organization).count(),
        'projects': Project.objects.filter(organization=organization).count(),
        'tasks': Task.objects.filter(project__organization=organization).count(),
    }

    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_activity = {
        'interactions': Interaction.objects.filter(
            organization=organization,
            created_at__gte=thirty_days_ago
        ).count(),
        'chat_messages': ChatMessage.objects.filter(
            organization=organization,
            created_at__gte=thirty_days_ago
        ).count(),
        'followups_created': FollowUp.objects.filter(
            organization=organization,
            created_at__gte=thirty_days_ago
        ).count(),
    }

    context = {
        'organization': organization,
        'memberships': memberships,
        'stats': stats,
        'recent_activity': recent_activity,
    }

    return render(request, 'core/admin/organization_detail.html', context)


@login_required
@require_superadmin
def admin_organization_impersonate(request, org_id):
    """
    Impersonate an organization for support purposes.

    Sets the organization in the session so admin can view the platform
    as if they were a member of that organization.
    """
    organization = get_object_or_404(Organization, id=org_id)

    # Store impersonation in session
    request.session['impersonating_org_id'] = org_id
    request.session['organization_id'] = org_id
    request.session['admin_impersonating'] = True

    messages.success(
        request,
        f"Now viewing as {organization.name}. Click 'Exit Impersonation' to return to admin panel."
    )

    # Redirect to organization dashboard
    return redirect('dashboard')


@login_required
@require_superadmin
def admin_exit_impersonation(request):
    """Exit organization impersonation mode."""
    if 'impersonating_org_id' in request.session:
        del request.session['impersonating_org_id']
    if 'organization_id' in request.session:
        del request.session['organization_id']
    if 'admin_impersonating' in request.session:
        del request.session['admin_impersonating']

    messages.info(request, "Exited impersonation mode")
    return redirect('admin_dashboard')


@login_required
@require_superadmin
def admin_organization_update_status(request, org_id):
    """Update organization subscription status."""
    if request.method == 'POST':
        organization = get_object_or_404(Organization, id=org_id)
        new_status = request.POST.get('status')

        if new_status in dict(Organization.STATUS_CHOICES):
            organization.subscription_status = new_status
            organization.save()

            messages.success(
                request,
                f"Updated {organization.name} status to {new_status}"
            )
        else:
            messages.error(request, "Invalid status")

    return redirect('admin_organization_detail', org_id=org_id)


@login_required
@require_superadmin
def admin_revenue_analytics(request):
    """
    Revenue and subscription analytics.

    Shows:
    - MRR/ARR trends over time
    - Subscription churn rate
    - Revenue by plan
    - Lifetime value metrics
    """
    # Current revenue
    active_subscriptions = Organization.objects.filter(
        subscription_status__in=['active', 'past_due']
    ).select_related('subscription_plan')

    mrr = sum(
        org.subscription_plan.price_monthly_cents if org.subscription_plan else 0
        for org in active_subscriptions
    ) / 100

    arr = mrr * 12

    # Revenue by plan
    revenue_by_plan = {}
    for org in active_subscriptions:
        if org.subscription_plan:
            plan_name = org.subscription_plan.name
            plan_revenue = org.subscription_plan.price_monthly_cents / 100
            revenue_by_plan[plan_name] = revenue_by_plan.get(plan_name, 0) + plan_revenue

    # Churn calculations (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    churned_count = Organization.objects.filter(
        subscription_status='cancelled',
        updated_at__gte=thirty_days_ago
    ).count()

    active_count_30d_ago = Organization.objects.filter(
        Q(subscription_status='active') |
        Q(subscription_status='cancelled', updated_at__gte=thirty_days_ago)
    ).count()

    churn_rate = (churned_count / active_count_30d_ago * 100) if active_count_30d_ago > 0 else 0

    # New subscriptions (last 30 days)
    new_subscriptions = Organization.objects.filter(
        subscription_status='active',
        subscription_started_at__gte=thirty_days_ago
    ).count()

    # Average revenue per organization
    avg_revenue = mrr / len(active_subscriptions) if active_subscriptions else 0

    context = {
        'mrr': mrr,
        'arr': arr,
        'revenue_by_plan': revenue_by_plan,
        'churn_rate': churn_rate,
        'churned_count': churned_count,
        'new_subscriptions': new_subscriptions,
        'avg_revenue': avg_revenue,
        'active_subscription_count': len(active_subscriptions),
    }

    return render(request, 'core/admin/revenue_analytics.html', context)


@login_required
@require_superadmin
def admin_usage_analytics(request):
    """
    Platform usage analytics.

    Shows:
    - AI query volumes
    - Feature adoption rates
    - Active users
    - Platform health metrics
    """
    # AI usage
    total_ai_queries = Organization.objects.aggregate(
        total=Sum('ai_queries_this_month')
    )['total'] or 0

    # Top AI users
    top_ai_orgs = Organization.objects.filter(
        ai_queries_this_month__gt=0
    ).order_by('-ai_queries_this_month')[:10]

    # Feature adoption
    orgs_with_volunteers = Organization.objects.annotate(
        vol_count=Count('volunteers')
    ).filter(vol_count__gt=0).count()

    orgs_with_interactions = Organization.objects.annotate(
        int_count=Count('interactions')
    ).filter(int_count__gt=0).count()

    orgs_with_followups = Organization.objects.annotate(
        fu_count=Count('followups')
    ).filter(fu_count__gt=0).count()

    orgs_with_channels = Organization.objects.annotate(
        ch_count=Count('channels')
    ).filter(ch_count__gt=0).count()

    orgs_with_projects = Organization.objects.annotate(
        proj_count=Count('projects')
    ).filter(proj_count__gt=0).count()

    total_orgs = Organization.objects.filter(subscription_status__in=['active', 'trial']).count()

    feature_adoption = {
        'Volunteers': (orgs_with_volunteers / total_orgs * 100) if total_orgs > 0 else 0,
        'Interactions': (orgs_with_interactions / total_orgs * 100) if total_orgs > 0 else 0,
        'Follow-ups': (orgs_with_followups / total_orgs * 100) if total_orgs > 0 else 0,
        'Channels': (orgs_with_channels / total_orgs * 100) if total_orgs > 0 else 0,
        'Projects': (orgs_with_projects / total_orgs * 100) if total_orgs > 0 else 0,
    }

    # User activity
    active_users_7d = User.objects.filter(
        last_login__gte=timezone.now() - timedelta(days=7)
    ).count()

    active_users_30d = User.objects.filter(
        last_login__gte=timezone.now() - timedelta(days=30)
    ).count()

    total_users = User.objects.count()

    context = {
        'total_ai_queries': total_ai_queries,
        'top_ai_orgs': top_ai_orgs,
        'feature_adoption': feature_adoption,
        'active_users_7d': active_users_7d,
        'active_users_30d': active_users_30d,
        'total_users': total_users,
    }

    return render(request, 'core/admin/usage_analytics.html', context)


@login_required
@require_superadmin
def admin_users_list(request):
    """
    List all platform users with activity metrics.
    """
    users = User.objects.annotate(
        org_count=Count('organization_memberships', filter=Q(organization_memberships__is_active=True))
    ).order_by('-date_joined')

    # Apply search
    search = request.GET.get('search')
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(display_name__icontains=search)
        )

    context = {
        'users': users,
        'search_query': search,
    }

    return render(request, 'core/admin/users_list.html', context)


@login_required
@require_superadmin
def admin_beta_requests(request):
    """List all beta requests with filtering."""
    status_filter = request.GET.get('status', '')
    requests_qs = BetaRequest.objects.all().order_by('-created_at')
    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)

    context = {
        'beta_requests': requests_qs,
        'status_filter': status_filter,
        'pending_count': BetaRequest.objects.filter(status='pending').count(),
    }
    return render(request, 'core/admin/beta_requests.html', context)


@login_required
@require_superadmin
def admin_beta_approve(request, pk):
    """Approve a beta request and send invitation email."""
    from django.core.mail import send_mail
    from django.conf import settings as django_settings

    beta_req = get_object_or_404(BetaRequest, pk=pk)

    if request.method == 'POST' and beta_req.status == 'pending':
        beta_req.status = 'approved'
        beta_req.reviewed_at = timezone.now()
        beta_req.reviewed_by = request.user
        beta_req.save()

        try:
            send_mail(
                subject='Your Aria Beta Access is Approved!',
                message=(
                    f"Hi {beta_req.name},\n\n"
                    f"Great news! Your beta access request for {beta_req.church_name} has been approved.\n\n"
                    f"You can now create your account and get started:\n"
                    f"{getattr(django_settings, 'SITE_URL', 'https://aria.church')}/beta/signup/?email={beta_req.email}\n\n"
                    f"During the beta period, all features are free. We'd love your feedback!\n\n"
                    f"Welcome to Aria,\n"
                    f"The Aria Team"
                ),
                from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@aria.church'),
                recipient_list=[beta_req.email],
                fail_silently=True,
            )
            beta_req.status = 'invited'
            beta_req.save()
        except Exception:
            pass

        messages.success(request, f'Beta request from {beta_req.church_name} approved.')

    return redirect('admin_beta_requests')


@login_required
@require_superadmin
def admin_beta_reject(request, pk):
    """Reject a beta request."""
    beta_req = get_object_or_404(BetaRequest, pk=pk)

    if request.method == 'POST' and beta_req.status == 'pending':
        beta_req.status = 'rejected'
        beta_req.reviewed_at = timezone.now()
        beta_req.reviewed_by = request.user
        beta_req.rejection_reason = request.POST.get('reason', '')
        beta_req.save()
        messages.success(request, f'Beta request from {beta_req.church_name} rejected.')

    return redirect('admin_beta_requests')
