from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended user model for team members."""
    display_name = models.CharField(max_length=100, blank=True)

    # Platform administration
    is_superadmin = models.BooleanField(
        default=False,
        help_text="Platform administrator with access to all organizations"
    )

    # Default organization for users with multiple orgs
    default_organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_users',
        help_text="Default organization when user has multiple memberships"
    )

    def __str__(self):
        return self.display_name or self.username

    def get_organizations(self):
        """Get all organizations this user belongs to."""
        from core.models import OrganizationMembership
        return [
            m.organization for m in
            OrganizationMembership.objects.filter(
                user=self,
                is_active=True
            ).select_related('organization')
        ]

    def get_organization_membership(self, organization):
        """Get user's membership in a specific organization."""
        from core.models import OrganizationMembership
        try:
            return OrganizationMembership.objects.get(
                user=self,
                organization=organization,
                is_active=True
            )
        except OrganizationMembership.DoesNotExist:
            return None

    def is_member_of(self, organization):
        """Check if user is a member of the given organization."""
        return self.get_organization_membership(organization) is not None

    def has_role_in(self, organization, role):
        """Check if user has a specific role in an organization."""
        membership = self.get_organization_membership(organization)
        if not membership:
            return False
        return membership.role == role

    def has_any_role_in(self, organization, roles):
        """Check if user has any of the specified roles in an organization."""
        membership = self.get_organization_membership(organization)
        if not membership:
            return False
        return membership.role in roles

    def get_primary_organization(self):
        """Get user's primary organization (default or first one)."""
        if self.default_organization:
            return self.default_organization

        orgs = self.get_organizations()
        return orgs[0] if orgs else None

    @property
    def organization_count(self):
        """Get count of organizations user belongs to."""
        from core.models import OrganizationMembership
        return OrganizationMembership.objects.filter(
            user=self,
            is_active=True
        ).count()
