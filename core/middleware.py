"""
Multi-tenant middleware for organization-scoped requests.

This middleware injects the current organization into each request,
enabling tenant isolation throughout the application.
"""
import logging
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware that sets the current organization on the request.

    Determines the organization from:
    1. Subdomain (e.g., cherry-hills.aria.church)
    2. Session (for authenticated users)
    3. URL path (e.g., /org/cherry-hills/...)

    Sets request.organization and request.membership for use in views.
    """

    # URLs that don't require organization context
    PUBLIC_URLS = [
        '/accounts/login/',
        '/accounts/logout/',
        '/accounts/register/',
        '/health/',
        '/admin/',
        '/org/select/',
        '/org/create/',
        '/invitation/',
        '/pricing/',
        '/security/',
        '/api/public/',
        # Onboarding flow
        '/beta/',
        '/signup/',
        '/onboarding/',
        '/invite/',
        '/webhooks/',
        # Subscription/billing pages (must be accessible when expired)
        '/billing/',
        '/subscribe/',
        # Platform admin portal
        '/platform-admin/',
    ]

    def process_request(self, request):
        """Set organization context on the request."""
        from .models import Organization, OrganizationMembership

        # Initialize organization context
        request.organization = None
        request.membership = None

        # Skip for public URLs
        if self._is_public_url(request.path):
            return None

        # Skip for unauthenticated users (they'll be redirected by auth)
        if not request.user.is_authenticated:
            return None

        # Try to get organization from various sources
        organization = self._get_organization_from_request(request)

        if organization:
            request.organization = organization

            # Get user's membership in this organization
            try:
                request.membership = OrganizationMembership.objects.get(
                    user=request.user,
                    organization=organization,
                    is_active=True
                )
            except OrganizationMembership.DoesNotExist:
                # User is not a member of this organization
                logger.warning(
                    f"User {request.user} tried to access org {organization.slug} "
                    "without membership"
                )
                return self._handle_no_membership(request)

            # Check if subscription is valid
            subscription_redirect = self._check_subscription_status(request, organization)
            if subscription_redirect:
                return subscription_redirect
        else:
            # No organization context - check if user has any orgs
            memberships = OrganizationMembership.objects.filter(
                user=request.user,
                is_active=True
            ).select_related('organization')

            if memberships.count() == 0:
                # User has no organizations - redirect to create one
                if not request.path.startswith('/org/'):
                    return redirect('org_create')
            elif memberships.count() == 1:
                # User has exactly one org - use it automatically
                membership = memberships.first()
                request.organization = membership.organization
                request.membership = membership
                # Store in session
                request.session['organization_id'] = membership.organization.id
            else:
                # User has multiple orgs - redirect to selector
                if not request.path.startswith('/org/'):
                    return redirect('org_select')

        return None

    def _is_public_url(self, path):
        """Check if the URL is public (no org context needed)."""
        for url in self.PUBLIC_URLS:
            if path.startswith(url):
                return True
        return False

    def _get_organization_from_request(self, request):
        """
        Try to determine the organization from the request.

        Priority:
        1. Subdomain
        2. URL path parameter
        3. Session
        """
        from .models import Organization

        # 1. Try subdomain (e.g., cherry-hills.aria.church)
        org = self._get_org_from_subdomain(request)
        if org:
            return org

        # 2. Try URL path (e.g., /org/cherry-hills/...)
        org = self._get_org_from_path(request)
        if org:
            return org

        # 3. Try session
        org_id = request.session.get('organization_id')
        if org_id:
            try:
                return Organization.objects.get(id=org_id, is_active=True)
            except Organization.DoesNotExist:
                # Clear invalid session data
                del request.session['organization_id']

        return None

    def _get_org_from_subdomain(self, request):
        """Extract organization from subdomain."""
        from .models import Organization

        host = request.get_host().split(':')[0]  # Remove port

        # Expected format: {org-slug}.aria.church or {org-slug}.localhost
        # Skip if no subdomain or if it's www
        parts = host.split('.')
        if len(parts) >= 2:
            subdomain = parts[0].lower()
            if subdomain not in ['www', 'api', 'admin', 'localhost']:
                try:
                    return Organization.objects.get(slug=subdomain, is_active=True)
                except Organization.DoesNotExist:
                    pass

        return None

    def _get_org_from_path(self, request):
        """Extract organization from URL path."""
        from .models import Organization

        # Expected format: /org/{slug}/...
        path_parts = request.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[0] == 'org':
            slug = path_parts[1]
            try:
                return Organization.objects.get(slug=slug, is_active=True)
            except Organization.DoesNotExist:
                pass

        return None

    def _check_subscription_status(self, request, organization):
        """
        Check if the organization's subscription allows access.

        Returns a redirect response if subscription is invalid, None otherwise.
        """
        # Check if organization needs to subscribe
        if organization.needs_subscription:
            logger.info(
                f"Organization {organization.slug} subscription expired, "
                f"redirecting user {request.user} to billing"
            )
            return redirect('subscription_required')

        # Check for past_due status - allow access but they'll see a warning
        if organization.subscription_status == 'past_due':
            logger.warning(
                f"Organization {organization.slug} has past due subscription"
            )
            # Don't redirect, but the template will show a warning banner

        return None

    def _handle_no_membership(self, request):
        """Handle when user tries to access an org they're not a member of."""
        # Redirect to org selector or show error
        return redirect('org_select')


class OrganizationContextMixin:
    """
    Mixin for class-based views that require organization context.

    Provides:
    - self.organization - Current organization
    - self.membership - User's membership in the organization
    - get_queryset() filtering by organization
    """

    def dispatch(self, request, *args, **kwargs):
        """Ensure organization context is available."""
        if not hasattr(request, 'organization') or not request.organization:
            return HttpResponseForbidden("Organization context required")

        self.organization = request.organization
        self.membership = request.membership

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Filter queryset by current organization."""
        queryset = super().get_queryset()

        # Check if model has organization field
        if hasattr(queryset.model, 'organization'):
            queryset = queryset.filter(organization=self.organization)

        return queryset

    def get_context_data(self, **kwargs):
        """Add organization to template context."""
        context = super().get_context_data(**kwargs)
        context['organization'] = self.organization
        context['membership'] = self.membership
        return context


def get_current_organization(request):
    """
    Utility function to get current organization from request.

    Returns None if no organization context.
    """
    return getattr(request, 'organization', None)


def require_organization(view_func):
    """
    Decorator for function-based views that require organization context.

    Usage:
        @login_required
        @require_organization
        def my_view(request):
            org = request.organization
            ...
    """
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'organization') or not request.organization:
            return HttpResponseForbidden("Organization context required")
        return view_func(request, *args, **kwargs)

    return wrapper


def require_permission(permission):
    """
    Decorator to require a specific permission within the organization.

    Usage:
        @login_required
        @require_organization
        @require_permission('can_manage_users')
        def manage_users(request):
            ...
    """
    from functools import wraps

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            membership = getattr(request, 'membership', None)
            if not membership:
                return HttpResponseForbidden("Organization membership required")

            if not membership.has_permission(permission):
                return HttpResponseForbidden(f"Permission denied: {permission}")

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_role(*roles):
    """
    Decorator to require specific role(s) within the organization.

    Usage:
        @login_required
        @require_organization
        @require_role('owner', 'admin')
        def admin_settings(request):
            ...
    """
    from functools import wraps

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            membership = getattr(request, 'membership', None)
            if not membership:
                return HttpResponseForbidden("Organization membership required")

            if membership.role not in roles:
                return HttpResponseForbidden(f"Role required: {', '.join(roles)}")

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_superadmin(view_func):
    """
    Decorator to require platform superadmin access.

    Usage:
        @login_required
        @require_superadmin
        def admin_dashboard(request):
            ...
    """
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Authentication required")

        if not request.user.is_superadmin:
            return HttpResponseForbidden("Platform administrator access required")

        return view_func(request, *args, **kwargs)

    return wrapper


class TenantQuerySetMixin:
    """
    Mixin for model managers to automatically filter by organization.

    Usage:
        class VolunteerManager(TenantQuerySetMixin, models.Manager):
            pass

        class Volunteer(models.Model):
            objects = VolunteerManager()
    """

    def get_queryset(self):
        """Return base queryset - filtering happens at view level."""
        return super().get_queryset()

    def for_organization(self, organization):
        """Filter queryset for a specific organization."""
        return self.get_queryset().filter(organization=organization)

    def for_request(self, request):
        """Filter queryset for the organization in the request."""
        org = get_current_organization(request)
        if org:
            return self.for_organization(org)
        return self.get_queryset().none()


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Adds security headers not covered by Django's SecurityMiddleware.
    """

    def process_response(self, request, response):
        # Content Security Policy
        csp = "; ".join([
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self'",
            "frame-ancestors 'none'",
        ])
        response['Content-Security-Policy'] = csp

        # Permissions Policy
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'

        return response
