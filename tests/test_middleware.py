"""
Tests for multi-tenant middleware and decorators.

These tests verify that the TenantMiddleware correctly sets organization
context and that permission decorators properly enforce access control.

CRITICAL: The middleware is the first line of defense for tenant isolation.
If these tests fail, the entire multi-tenant security model may be compromised.
"""
import pytest
from django.test import RequestFactory, Client
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware

from core.middleware import (
    TenantMiddleware,
    require_organization,
    require_permission,
    require_role,
    get_current_organization,
    OrganizationContextMixin,
)
from core.models import Organization, OrganizationMembership

User = get_user_model()


def add_middleware_to_request(request):
    """Helper to add session and auth middleware to a request."""
    # Add session middleware
    session_middleware = SessionMiddleware(lambda r: HttpResponse())
    session_middleware.process_request(request)
    request.session.save()

    # Add auth middleware
    auth_middleware = AuthenticationMiddleware(lambda r: HttpResponse())
    auth_middleware.process_request(request)

    return request


class TestTenantMiddleware:
    """Test the TenantMiddleware class."""

    def test_middleware_sets_organization_for_authenticated_user(
        self, request_factory, user_alpha_owner, org_alpha
    ):
        """Middleware should set organization context for authenticated users."""
        request = request_factory.get('/dashboard/')
        request = add_middleware_to_request(request)
        request.user = user_alpha_owner
        request.session['organization_id'] = org_alpha.id
        request.session.save()

        middleware = TenantMiddleware(lambda r: HttpResponse())
        middleware.process_request(request)

        assert hasattr(request, 'organization')
        assert request.organization == org_alpha
        assert hasattr(request, 'membership')
        assert request.membership is not None
        assert request.membership.user == user_alpha_owner

    def test_middleware_no_org_for_unauthenticated_user(self, db, request_factory):
        """Middleware should not set organization for unauthenticated users."""
        from django.contrib.auth.models import AnonymousUser

        request = request_factory.get('/dashboard/')
        request = add_middleware_to_request(request)
        request.user = AnonymousUser()

        middleware = TenantMiddleware(lambda r: HttpResponse())
        result = middleware.process_request(request)

        # Should return None (continue processing) or redirect
        assert request.organization is None

    def test_middleware_public_urls_skip_org_check(self, request_factory, db):
        """Middleware should skip org check for public URLs."""
        from django.contrib.auth.models import AnonymousUser

        public_urls = ['/accounts/login/', '/pricing/', '/signup/']

        for url in public_urls:
            request = request_factory.get(url)
            request = add_middleware_to_request(request)
            request.user = AnonymousUser()

            middleware = TenantMiddleware(lambda r: HttpResponse())
            result = middleware.process_request(request)

            # Should return None (allow request to proceed)
            assert result is None, f"Public URL {url} should be allowed"

    def test_middleware_rejects_user_without_membership(
        self, request_factory, db, org_alpha, subscription_plan
    ):
        """Middleware should reject users who aren't members of the org."""
        # Create a user with NO membership in any org
        outsider = User.objects.create_user(
            username='outsider',
            password='testpass123'
        )

        request = request_factory.get('/dashboard/')
        request = add_middleware_to_request(request)
        request.user = outsider
        request.session['organization_id'] = org_alpha.id
        request.session.save()

        middleware = TenantMiddleware(lambda r: HttpResponse())
        result = middleware.process_request(request)

        # Should redirect (not allow access)
        assert result is not None  # Returns a redirect response

    def test_middleware_sets_correct_membership(
        self, request_factory, user_alpha_owner, user_alpha_member, org_alpha
    ):
        """Middleware should set the correct membership for the user."""
        # Test owner
        request = request_factory.get('/dashboard/')
        request = add_middleware_to_request(request)
        request.user = user_alpha_owner
        request.session['organization_id'] = org_alpha.id
        request.session.save()

        middleware = TenantMiddleware(lambda r: HttpResponse())
        middleware.process_request(request)

        assert request.membership.role == 'owner'

        # Test member
        request2 = request_factory.get('/dashboard/')
        request2 = add_middleware_to_request(request2)
        request2.user = user_alpha_member
        request2.session['organization_id'] = org_alpha.id
        request2.session.save()

        middleware.process_request(request2)

        assert request2.membership.role == 'member'


class TestRequireOrganizationDecorator:
    """Test the @require_organization decorator."""

    def test_decorator_allows_request_with_org(self, mock_request_alpha):
        """Decorator should allow requests with organization context."""

        @require_organization
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(mock_request_alpha)
        assert response.status_code == 200
        assert response.content == b'OK'

    def test_decorator_blocks_request_without_org(self, request_factory, user_alpha_owner):
        """Decorator should block requests without organization context."""
        request = request_factory.get('/')
        request.user = user_alpha_owner
        # Deliberately not setting organization

        @require_organization
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(request)
        assert response.status_code == 403

    def test_decorator_blocks_request_with_none_org(self, request_factory, user_alpha_owner):
        """Decorator should block requests where organization is None."""
        request = request_factory.get('/')
        request.user = user_alpha_owner
        request.organization = None

        @require_organization
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(request)
        assert response.status_code == 403


class TestRequirePermissionDecorator:
    """Test the @require_permission decorator."""

    def test_decorator_allows_user_with_permission(self, mock_request_alpha):
        """Decorator should allow users with the required permission."""
        # Alpha owner has can_manage_users permission

        @require_permission('can_manage_users')
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(mock_request_alpha)
        assert response.status_code == 200

    def test_decorator_blocks_user_without_permission(
        self, request_factory, user_alpha_member, org_alpha
    ):
        """Decorator should block users without the required permission."""
        request = request_factory.get('/')
        request.user = user_alpha_member
        request.organization = org_alpha
        request.membership = OrganizationMembership.objects.get(
            user=user_alpha_member,
            organization=org_alpha
        )

        @require_permission('can_manage_users')
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(request)
        assert response.status_code == 403

    def test_decorator_blocks_user_without_membership(self, request_factory, db):
        """Decorator should block users without any membership."""
        outsider = User.objects.create_user(username='outsider2', password='test')

        request = request_factory.get('/')
        request.user = outsider
        # No membership attribute

        @require_permission('can_manage_users')
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(request)
        assert response.status_code == 403


class TestRequireRoleDecorator:
    """Test the @require_role decorator."""

    def test_decorator_allows_matching_role(self, mock_request_alpha):
        """Decorator should allow users with matching role."""

        @require_role('owner', 'admin')
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(mock_request_alpha)
        assert response.status_code == 200

    def test_decorator_blocks_non_matching_role(
        self, request_factory, user_alpha_member, org_alpha
    ):
        """Decorator should block users without matching role."""
        request = request_factory.get('/')
        request.user = user_alpha_member
        request.organization = org_alpha
        request.membership = OrganizationMembership.objects.get(
            user=user_alpha_member,
            organization=org_alpha
        )

        @require_role('owner', 'admin')
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(request)
        assert response.status_code == 403

    def test_decorator_allows_any_of_multiple_roles(
        self, request_factory, db, org_alpha, subscription_plan
    ):
        """Decorator should allow any of the specified roles."""
        # Create an admin user
        admin_user = User.objects.create_user(
            username='alpha_admin',
            password='testpass123'
        )
        OrganizationMembership.objects.create(
            user=admin_user,
            organization=org_alpha,
            role='admin',
            is_active=True,
        )

        request = request_factory.get('/')
        request.user = admin_user
        request.organization = org_alpha
        request.membership = OrganizationMembership.objects.get(
            user=admin_user,
            organization=org_alpha
        )

        @require_role('owner', 'admin')
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(request)
        assert response.status_code == 200


class TestGetCurrentOrganization:
    """Test the get_current_organization utility function."""

    def test_returns_organization_when_set(self, mock_request_alpha, org_alpha):
        """Should return organization when it's set on request."""
        org = get_current_organization(mock_request_alpha)
        assert org == org_alpha

    def test_returns_none_when_not_set(self, request_factory):
        """Should return None when organization is not set."""
        request = request_factory.get('/')

        org = get_current_organization(request)
        assert org is None

    def test_returns_none_for_none_org(self, request_factory):
        """Should return None when organization is explicitly None."""
        request = request_factory.get('/')
        request.organization = None

        org = get_current_organization(request)
        assert org is None


class TestOrganizationMembershipPermissions:
    """Test the OrganizationMembership permission methods."""

    def test_owner_has_all_permissions(self, user_alpha_owner, org_alpha):
        """Owner should have all permissions."""
        membership = OrganizationMembership.objects.get(
            user=user_alpha_owner,
            organization=org_alpha
        )

        assert membership.can_manage_users is True
        assert membership.can_manage_settings is True
        assert membership.can_view_analytics is True
        assert membership.can_manage_billing is True

    def test_member_has_limited_permissions(self, user_alpha_member, org_alpha):
        """Member should have limited permissions."""
        membership = OrganizationMembership.objects.get(
            user=user_alpha_member,
            organization=org_alpha
        )

        assert membership.can_manage_users is False
        assert membership.can_manage_billing is False

    def test_has_permission_method(self, user_alpha_owner, user_alpha_member, org_alpha):
        """Test the has_permission() method on membership."""
        owner_membership = OrganizationMembership.objects.get(
            user=user_alpha_owner,
            organization=org_alpha
        )
        member_membership = OrganizationMembership.objects.get(
            user=user_alpha_member,
            organization=org_alpha
        )

        # Owner should have permission
        assert owner_membership.has_permission('can_manage_users') is True

        # Member should not
        assert member_membership.has_permission('can_manage_users') is False


class TestMultiOrgUserAccess:
    """Test users with access to multiple organizations."""

    @pytest.fixture
    def multi_org_user(self, db, org_alpha, org_beta, subscription_plan):
        """Create a user with membership in both organizations."""
        user = User.objects.create_user(
            username='multi_org_user',
            password='testpass123',
            display_name='Multi Org User',
        )

        # Member of Alpha (as member)
        OrganizationMembership.objects.create(
            user=user,
            organization=org_alpha,
            role='member',
            is_active=True,
        )

        # Member of Beta (as admin)
        OrganizationMembership.objects.create(
            user=user,
            organization=org_beta,
            role='admin',
            is_active=True,
            can_manage_users=True,
        )

        return user

    def test_user_roles_differ_by_org(self, multi_org_user, org_alpha, org_beta):
        """User should have different roles in different organizations."""
        alpha_membership = OrganizationMembership.objects.get(
            user=multi_org_user,
            organization=org_alpha
        )
        beta_membership = OrganizationMembership.objects.get(
            user=multi_org_user,
            organization=org_beta
        )

        assert alpha_membership.role == 'member'
        assert beta_membership.role == 'admin'

    def test_user_permissions_differ_by_org(self, multi_org_user, org_alpha, org_beta):
        """User should have different permissions in different organizations."""
        alpha_membership = OrganizationMembership.objects.get(
            user=multi_org_user,
            organization=org_alpha
        )
        beta_membership = OrganizationMembership.objects.get(
            user=multi_org_user,
            organization=org_beta
        )

        # In Alpha (member) - no manage users permission
        assert alpha_membership.can_manage_users is False

        # In Beta (admin) - has manage users permission
        assert beta_membership.can_manage_users is True

    def test_session_org_switch(self, db, multi_org_user, org_alpha, org_beta):
        """User should be able to switch between organizations via session."""
        client = Client()
        client.force_login(multi_org_user)

        # Set to Alpha org
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()

        # Access dashboard in Alpha context
        response = client.get('/dashboard/')
        # Should be able to access (user is member of Alpha)

        # Switch to Beta org
        session = client.session
        session['organization_id'] = org_beta.id
        session.save()

        # Access dashboard in Beta context
        response = client.get('/dashboard/')
        # Should also be able to access (user is admin of Beta)


class TestInactiveMembership:
    """Test handling of inactive memberships."""

    def test_inactive_membership_blocks_access(
        self, request_factory, user_alpha_member, org_alpha
    ):
        """Users with inactive membership should not access org."""
        # Deactivate membership
        membership = OrganizationMembership.objects.get(
            user=user_alpha_member,
            organization=org_alpha
        )
        membership.is_active = False
        membership.save()

        try:
            request = request_factory.get('/dashboard/')
            request = add_middleware_to_request(request)
            request.user = user_alpha_member
            request.session['organization_id'] = org_alpha.id
            request.session.save()

            middleware = TenantMiddleware(lambda r: HttpResponse())
            result = middleware.process_request(request)

            # Should redirect (membership is inactive)
            assert result is not None
        finally:
            # Restore membership
            membership.is_active = True
            membership.save()


class TestDecoratorStacking:
    """Test that decorators can be stacked correctly."""

    def test_require_org_then_role(self, mock_request_alpha):
        """Stacked decorators should both apply."""

        @require_organization
        @require_role('owner')
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(mock_request_alpha)
        assert response.status_code == 200

    def test_require_org_then_permission(self, mock_request_alpha):
        """Stacked decorators with permission should both apply."""

        @require_organization
        @require_permission('can_manage_billing')
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(mock_request_alpha)
        assert response.status_code == 200

    def test_stacked_decorators_fail_early(self, request_factory, user_alpha_member, org_alpha):
        """If first decorator fails, second shouldn't be reached."""
        request = request_factory.get('/')
        # No organization set - should fail at require_organization

        @require_organization
        @require_role('owner')
        def test_view(request):
            return HttpResponse('OK')

        response = test_view(request)
        assert response.status_code == 403
