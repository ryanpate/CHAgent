from django.db import models
from django.conf import settings
from django.utils import timezone
import secrets

# Try to import pgvector, fall back to a placeholder if not available
try:
    from pgvector.django import VectorField
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
    # Placeholder for development without pgvector
    VectorField = None


def generate_invitation_token():
    """Generate a secure token for organization invitations."""
    return secrets.token_urlsafe(32)


# =============================================================================
# Multi-Tenancy Models - Organization & Subscription Management
# =============================================================================

class SubscriptionPlan(models.Model):
    """
    Defines available subscription plans for organizations.
    """
    PLAN_TIER_CHOICES = [
        ('free', 'Free Trial'),
        ('starter', 'Starter'),
        ('team', 'Team'),
        ('ministry', 'Ministry'),
        ('enterprise', 'Enterprise'),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    tier = models.CharField(max_length=20, choices=PLAN_TIER_CHOICES, default='starter')
    description = models.TextField(blank=True)

    # Pricing (in cents to avoid floating point issues)
    price_monthly_cents = models.IntegerField(default=0, help_text="Monthly price in cents")
    price_yearly_cents = models.IntegerField(default=0, help_text="Yearly price in cents")

    # Limits
    max_users = models.IntegerField(default=5, help_text="Maximum team members")
    max_volunteers = models.IntegerField(default=50, help_text="Maximum volunteers tracked")
    max_ai_queries_monthly = models.IntegerField(default=500, help_text="Monthly AI query limit")

    # Feature flags
    has_pco_integration = models.BooleanField(default=True)
    has_push_notifications = models.BooleanField(default=True)
    has_analytics = models.BooleanField(default=False)
    has_care_insights = models.BooleanField(default=False)
    has_api_access = models.BooleanField(default=False)
    has_custom_branding = models.BooleanField(default=False)
    has_priority_support = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True, help_text="Show on pricing page")
    sort_order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'price_monthly_cents']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'

    def __str__(self):
        return f"{self.name} (${self.price_monthly_cents / 100:.2f}/mo)"

    @property
    def price_monthly(self):
        """Return monthly price in dollars."""
        return self.price_monthly_cents / 100

    @property
    def price_yearly(self):
        """Return yearly price in dollars."""
        return self.price_yearly_cents / 100

    # Aliases for template compatibility
    @property
    def monthly_price(self):
        """Alias for price_monthly for template use."""
        return self.price_monthly

    @property
    def yearly_price(self):
        """Alias for price_yearly for template use."""
        return self.price_yearly

    @property
    def yearly_savings(self):
        """Calculate savings when paying yearly vs monthly."""
        monthly_for_year = self.price_monthly * 12
        return monthly_for_year - self.price_yearly

    @property
    def features(self):
        """Return feature flags as a dictionary for template access."""
        return {
            'pco_integration': self.has_pco_integration,
            'push_notifications': self.has_push_notifications,
            'analytics': self.has_analytics,
            'care_insights': self.has_care_insights,
            'api_access': self.has_api_access,
            'custom_branding': self.has_custom_branding,
            'priority_support': self.has_priority_support,
        }


def generate_api_key():
    """Generate a secure API key for organizations."""
    return f"aria_{secrets.token_urlsafe(32)}"


class Organization(models.Model):
    """
    Represents a church or organization using the platform.

    This is the central tenant model - all data is scoped to an organization.
    """
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
    ]

    # Basic info
    name = models.CharField(max_length=200, help_text="Organization/Church name")
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-friendly identifier (e.g., 'cherry-hills')"
    )
    logo = models.URLField(blank=True, help_text="URL to organization logo")

    # Contact info
    email = models.EmailField(help_text="Primary contact email")
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    address = models.TextField(blank=True)
    timezone = models.CharField(
        max_length=50,
        default='America/Denver',
        help_text="Organization timezone for scheduling"
    )

    # Subscription
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='organizations'
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='trial'
    )
    trial_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the trial period ends"
    )
    subscription_started_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)

    # Billing (Stripe integration)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)

    # Planning Center Integration (per-org credentials)
    planning_center_app_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="Planning Center App ID for this organization"
    )
    planning_center_secret = models.CharField(
        max_length=200,
        blank=True,
        help_text="Planning Center Secret (encrypted at rest)"
    )
    planning_center_connected_at = models.DateTimeField(null=True, blank=True)

    # API Access
    api_key = models.CharField(
        max_length=100,
        unique=True,
        default=generate_api_key,
        help_text="API key for external integrations"
    )
    api_enabled = models.BooleanField(default=False)

    # Usage tracking
    ai_queries_this_month = models.IntegerField(default=0)
    ai_queries_reset_at = models.DateTimeField(null=True, blank=True)

    # Customization
    ai_assistant_name = models.CharField(
        max_length=50,
        default='Aria',
        help_text="Custom name for the AI assistant"
    )
    primary_color = models.CharField(
        max_length=7,
        default='#6366f1',
        help_text="Primary brand color (hex)"
    )

    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Generate slug if not provided
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Organization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_trial(self):
        """Check if organization is in trial period."""
        if self.subscription_status != 'trial':
            return False
        if self.trial_ends_at and timezone.now() > self.trial_ends_at:
            return False
        return True

    @property
    def is_trial_expired(self):
        """Check if trial period has ended without converting to paid."""
        if self.subscription_status != 'trial':
            return False
        if self.trial_ends_at and timezone.now() > self.trial_ends_at:
            return True
        return False

    @property
    def trial_days_remaining(self):
        """Get days remaining in trial."""
        if not self.is_trial or not self.trial_ends_at:
            return 0
        delta = self.trial_ends_at - timezone.now()
        return max(0, delta.days)

    @property
    def show_trial_warning(self):
        """Check if we should show trial expiring warning (3 days or less)."""
        return self.is_trial and self.trial_days_remaining <= 3

    @property
    def needs_subscription(self):
        """Check if org needs to subscribe to continue using the service."""
        # Trial expired
        if self.is_trial_expired:
            return True
        # Subscription cancelled or suspended
        if self.subscription_status in ['cancelled', 'suspended']:
            return True
        return False

    @property
    def is_subscription_active(self):
        """Check if organization has an active subscription."""
        if self.subscription_status == 'trial':
            return self.is_trial  # Only active if trial hasn't expired
        return self.subscription_status == 'active'

    @property
    def can_use_feature(self):
        """Check if org can use paid features based on subscription."""
        return self.is_subscription_active and self.is_active

    def has_feature(self, feature_name):
        """Check if organization's plan includes a specific feature."""
        if not self.subscription_plan:
            return False
        return getattr(self.subscription_plan, f'has_{feature_name}', False)

    def check_limit(self, limit_name, current_count):
        """Check if organization is within a specific limit."""
        if not self.subscription_plan:
            return False
        max_value = getattr(self.subscription_plan, f'max_{limit_name}', 0)
        if max_value == -1:  # Unlimited
            return True
        return current_count < max_value

    def increment_ai_usage(self):
        """Increment AI query counter for the month."""
        now = timezone.now()
        # Reset counter if it's a new month
        if self.ai_queries_reset_at is None or self.ai_queries_reset_at.month != now.month:
            self.ai_queries_this_month = 0
            self.ai_queries_reset_at = now
        self.ai_queries_this_month += 1
        self.save(update_fields=['ai_queries_this_month', 'ai_queries_reset_at'])

    def has_pco_credentials(self):
        """Check if Planning Center credentials are configured."""
        return bool(self.planning_center_app_id and self.planning_center_secret)

    def get_user_count(self):
        """Get number of users in this organization."""
        return self.memberships.filter(is_active=True).count()

    def get_volunteer_count(self):
        """Get number of volunteers in this organization."""
        return self.volunteers.count()


class OrganizationMembership(models.Model):
    """
    Links users to organizations with role-based permissions.

    Users can belong to multiple organizations with different roles.
    """
    ROLE_CHOICES = [
        ('owner', 'Owner'),        # Full control, billing, can delete org
        ('admin', 'Admin'),        # Manage users, settings, full data access
        ('leader', 'Team Leader'), # Manage volunteers, view analytics
        ('member', 'Member'),      # Basic access to chat and interactions
        ('viewer', 'Viewer'),      # Read-only access
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organization_memberships'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='member'
    )

    # Permissions (can override role defaults)
    can_manage_users = models.BooleanField(default=False)
    can_manage_settings = models.BooleanField(default=False)
    can_view_analytics = models.BooleanField(default=False)
    can_manage_billing = models.BooleanField(default=False)

    # Team assignment (optional)
    team = models.CharField(
        max_length=100,
        blank=True,
        help_text="Team within the organization (e.g., 'vocals', 'band')"
    )

    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_invitations'
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'organization']
        verbose_name = 'Organization Membership'
        verbose_name_plural = 'Organization Memberships'

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"

    def save(self, *args, **kwargs):
        # Set default permissions based on role
        if not self.pk:  # Only on creation
            self._set_role_defaults()
        super().save(*args, **kwargs)

    def _set_role_defaults(self):
        """Set default permissions based on role."""
        role_permissions = {
            'owner': {
                'can_manage_users': True,
                'can_manage_settings': True,
                'can_view_analytics': True,
                'can_manage_billing': True,
            },
            'admin': {
                'can_manage_users': True,
                'can_manage_settings': True,
                'can_view_analytics': True,
                'can_manage_billing': False,
            },
            'leader': {
                'can_manage_users': False,
                'can_manage_settings': False,
                'can_view_analytics': True,
                'can_manage_billing': False,
            },
            'member': {
                'can_manage_users': False,
                'can_manage_settings': False,
                'can_view_analytics': False,
                'can_manage_billing': False,
            },
            'viewer': {
                'can_manage_users': False,
                'can_manage_settings': False,
                'can_view_analytics': False,
                'can_manage_billing': False,
            },
        }
        perms = role_permissions.get(self.role, {})
        for key, value in perms.items():
            setattr(self, key, value)

    def has_permission(self, permission):
        """Check if this membership has a specific permission."""
        return getattr(self, permission, False)

    @property
    def is_owner(self):
        return self.role == 'owner'

    @property
    def is_admin_or_above(self):
        return self.role in ['owner', 'admin']

    @property
    def is_leader_or_above(self):
        return self.role in ['owner', 'admin', 'leader']


class OrganizationInvitation(models.Model):
    """
    Pending invitations to join an organization.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=OrganizationMembership.ROLE_CHOICES,
        default='member'
    )
    team = models.CharField(max_length=100, blank=True)

    token = models.CharField(
        max_length=100,
        unique=True,
        default=generate_invitation_token
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_invitations'
    )
    message = models.TextField(blank=True, help_text="Optional personal message")

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Organization Invitation'
        verbose_name_plural = 'Organization Invitations'

    def __str__(self):
        return f"Invitation for {self.email} to {self.organization}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        """Check if invitation is still valid."""
        return (
            self.status == 'pending' and
            timezone.now() < self.expires_at
        )

    def accept(self, user):
        """Accept this invitation and create membership."""
        if not self.is_valid:
            raise ValueError("Invitation is no longer valid")

        membership, created = OrganizationMembership.objects.get_or_create(
            user=user,
            organization=self.organization,
            defaults={
                'role': self.role,
                'team': self.team,
                'invited_by': self.invited_by,
                'joined_at': timezone.now(),
            }
        )

        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.save()

        return membership


# =============================================================================
# Tenant-Scoped Base Model
# =============================================================================

class TenantModel(models.Model):
    """
    Abstract base model that adds organization scoping to models.

    Inherit from this for all models that should be scoped to an organization.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='%(class)ss'
    )

    class Meta:
        abstract = True


# =============================================================================
# Volunteer Management Models
# =============================================================================

class Volunteer(models.Model):
    """
    Volunteer profiles - auto-created/linked when AI identifies
    a volunteer in an interaction. Minimal structure, AI-driven.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='volunteers',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )
    name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200, db_index=True)  # lowercase for matching
    team = models.CharField(max_length=100, blank=True)  # vocals, band, tech, etc.
    planning_center_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        # PCO ID is unique within an organization, not globally
        unique_together = [['organization', 'planning_center_id']]
        indexes = [
            models.Index(fields=['organization', 'normalized_name']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto-generate normalized_name from name
        if not self.normalized_name:
            self.normalized_name = self.name.lower().strip()
        super().save(*args, **kwargs)


class Interaction(models.Model):
    """
    Append-only interaction log. Each entry is a team member's note
    about an encounter with one or more volunteers.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='interactions',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='interactions'
    )
    content = models.TextField(help_text="Free-form interaction notes")
    volunteers = models.ManyToManyField(
        Volunteer,
        blank=True,
        related_name='interactions',
        help_text="Volunteers mentioned (auto-linked by AI)"
    )

    # AI-extracted metadata (populated by Claude after submission)
    ai_summary = models.TextField(blank=True, help_text="AI-generated summary")
    ai_extracted_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured data extracted by AI (hobbies, preferences, etc.)"
    )

    # Vector embedding for semantic search
    # Store as JSON for SQLite compatibility, use pgvector in production
    embedding_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Vector embedding stored as JSON (for SQLite compatibility)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        user_str = self.user.display_name if self.user else 'Unknown'
        date_str = self.created_at.strftime('%Y-%m-%d') if self.created_at else 'Unknown'
        return f"Interaction by {user_str} on {date_str}"

    @property
    def embedding(self):
        """Get embedding as a list."""
        return self.embedding_json

    @embedding.setter
    def embedding(self, value):
        """Set embedding from a list."""
        self.embedding_json = value


class ChatMessage(models.Model):
    """
    Stores AI chat conversations for context and history.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    session_id = models.CharField(max_length=100, db_index=True)  # Group messages by session
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


class ConversationContext(models.Model):
    """
    Tracks conversation state and context across multiple messages.

    This model enables:
    - Deduplication of shown interactions (avoid repeating the same info)
    - Tracking which volunteers are being discussed
    - Maintaining a running summary for long conversations
    - Better context-aware RAG retrieval
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='conversation_contexts',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversation_contexts'
    )
    session_id = models.CharField(max_length=100, db_index=True, unique=True)

    # Track which interactions have already been shown to avoid repetition
    shown_interaction_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of Interaction IDs already shown in this conversation"
    )

    # Track which volunteers are being discussed for context-aware retrieval
    discussed_volunteer_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of Volunteer IDs mentioned/discussed in this conversation"
    )

    # Running summary of the conversation for long conversations
    conversation_summary = models.TextField(
        blank=True,
        help_text="AI-generated summary of conversation so far (for long conversations)"
    )

    # Current topic being discussed
    current_topic = models.CharField(
        max_length=500,
        blank=True,
        help_text="The current topic or volunteer being discussed"
    )

    # Message count for determining when to summarize
    message_count = models.IntegerField(default=0)

    # Store pending song suggestions for user selection
    pending_song_suggestions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of song suggestions waiting for user selection"
    )

    # Track the current song being discussed for follow-up queries
    current_song = models.JSONField(
        default=dict,
        blank=True,
        help_text="Current song being discussed (title, id, etc.) for context in follow-up queries"
    )

    # Store pending date lookup for confirmation (e.g., "Would you like me to look up April 20, 2025?")
    pending_date_lookup = models.JSONField(
        default=dict,
        blank=True,
        help_text="Pending date lookup waiting for user confirmation (date, query_type)"
    )

    # Store pending follow-up items waiting for date confirmation
    pending_followup = models.JSONField(
        default=dict,
        blank=True,
        help_text="Pending follow-up item waiting for date (title, description, volunteer_name, category)"
    )

    # Store pending disambiguation when query could be song or person
    pending_disambiguation = models.JSONField(
        default=dict,
        blank=True,
        help_text="Pending disambiguation when query is ambiguous (extracted_value, original_query)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Context for session {self.session_id[:8]}... ({self.message_count} messages)"

    def add_shown_interactions(self, interaction_ids: list):
        """Add interaction IDs to the shown list."""
        if not self.shown_interaction_ids:
            self.shown_interaction_ids = []
        # Use set to avoid duplicates
        current = set(self.shown_interaction_ids)
        current.update(interaction_ids)
        self.shown_interaction_ids = list(current)

    def add_discussed_volunteers(self, volunteer_ids: list):
        """Add volunteer IDs to the discussed list."""
        if not self.discussed_volunteer_ids:
            self.discussed_volunteer_ids = []
        # Use set to avoid duplicates
        current = set(self.discussed_volunteer_ids)
        current.update(volunteer_ids)
        self.discussed_volunteer_ids = list(current)

    def increment_message_count(self, count: int = 1):
        """Increment the message count."""
        self.message_count += count

    def should_summarize(self) -> bool:
        """Check if the conversation is long enough to warrant summarization."""
        return self.message_count >= 15  # Summarize after 15 messages

    def clear_context(self):
        """Clear the conversation context for a fresh start."""
        self.shown_interaction_ids = []
        self.discussed_volunteer_ids = []
        self.conversation_summary = ""
        self.current_topic = ""
        self.message_count = 0
        self.pending_song_suggestions = []
        self.current_song = {}
        self.pending_date_lookup = {}
        self.pending_followup = {}

    def set_pending_song_suggestions(self, suggestions: list):
        """Store song suggestions for user selection."""
        self.pending_song_suggestions = suggestions

    def get_pending_song_suggestions(self) -> list:
        """Get stored song suggestions."""
        return self.pending_song_suggestions or []

    def clear_pending_song_suggestions(self):
        """Clear pending song suggestions after selection."""
        self.pending_song_suggestions = []

    def set_current_song(self, song_title: str, song_id: str = None):
        """Store the currently discussed song for follow-up queries."""
        self.current_song = {
            'title': song_title,
            'id': song_id
        }

    def get_current_song(self) -> dict:
        """Get the currently discussed song."""
        return self.current_song or {}

    def get_current_song_title(self) -> str:
        """Get just the title of the currently discussed song."""
        if self.current_song:
            return self.current_song.get('title', '')
        return ''

    def clear_current_song(self):
        """Clear the current song context."""
        self.current_song = {}

    def set_pending_date_lookup(self, date_str: str, query_type: str = 'setlist'):
        """Store a pending date lookup for user confirmation."""
        self.pending_date_lookup = {
            'date': date_str,
            'query_type': query_type
        }

    def get_pending_date_lookup(self) -> dict:
        """Get the pending date lookup."""
        return self.pending_date_lookup or {}

    def clear_pending_date_lookup(self):
        """Clear the pending date lookup after use."""
        self.pending_date_lookup = {}

    def set_pending_followup(self, title: str, description: str = '', volunteer_name: str = '', category: str = ''):
        """Store a pending follow-up waiting for date confirmation."""
        self.pending_followup = {
            'title': title,
            'description': description,
            'volunteer_name': volunteer_name,
            'category': category
        }

    def get_pending_followup(self) -> dict:
        """Get the pending follow-up."""
        return self.pending_followup or {}

    def clear_pending_followup(self):
        """Clear the pending follow-up after use."""
        self.pending_followup = {}

    def set_pending_disambiguation(self, extracted_value: str, original_query: str):
        """Store a pending disambiguation when query is ambiguous between song and person."""
        self.pending_disambiguation = {
            'extracted_value': extracted_value,
            'original_query': original_query
        }

    def get_pending_disambiguation(self) -> dict:
        """Get the pending disambiguation."""
        return self.pending_disambiguation or {}

    def clear_pending_disambiguation(self):
        """Clear the pending disambiguation after use."""
        self.pending_disambiguation = {}


class FollowUp(models.Model):
    """
    Tracks items that require follow-up action.

    Created automatically when the AI detects something needing follow-up
    (prayer requests, concerns, action items, etc.) or manually by team members.
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='followups',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )

    # Who created this follow-up
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_followups',
        help_text="Team member who created this follow-up"
    )

    # Who is assigned to handle this follow-up (optional)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_followups',
        help_text="Team member assigned to handle this follow-up"
    )

    # Which volunteer(s) this follow-up is about (optional)
    volunteer = models.ForeignKey(
        Volunteer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='followups',
        help_text="Volunteer this follow-up is about"
    )

    # The follow-up details
    title = models.CharField(
        max_length=200,
        help_text="Brief title/summary of the follow-up"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of what needs to be followed up on"
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Category (e.g., 'prayer_request', 'concern', 'action_item', 'feedback')"
    )

    # Scheduling
    follow_up_date = models.DateField(
        null=True,
        blank=True,
        help_text="When to follow up"
    )
    reminder_sent = models.BooleanField(
        default=False,
        help_text="Whether a reminder has been sent for this follow-up"
    )

    # Status tracking
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # Completion details
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this follow-up was completed"
    )
    completion_notes = models.TextField(
        blank=True,
        help_text="Notes about how this was resolved"
    )

    # Link to source interaction (if auto-created from a conversation)
    source_interaction = models.ForeignKey(
        Interaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='followups',
        help_text="The interaction that triggered this follow-up"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['follow_up_date', '-priority', '-created_at']
        verbose_name = 'Follow-up'
        verbose_name_plural = 'Follow-ups'

    def __str__(self):
        volunteer_name = self.volunteer.name if self.volunteer else 'General'
        return f"{self.title} ({volunteer_name})"

    def mark_completed(self, notes: str = ''):
        """Mark this follow-up as completed."""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        if notes:
            self.completion_notes = notes
        self.save()

    @property
    def is_overdue(self) -> bool:
        """Check if this follow-up is past its due date."""
        from django.utils import timezone
        if self.follow_up_date and self.status == 'pending':
            return self.follow_up_date < timezone.now().date()
        return False

    @property
    def is_due_soon(self) -> bool:
        """Check if this follow-up is due within the next 3 days."""
        from django.utils import timezone
        from datetime import timedelta
        if self.follow_up_date and self.status == 'pending':
            today = timezone.now().date()
            return today <= self.follow_up_date <= today + timedelta(days=3)
        return False


# =============================================================================
# Learning System Models - Enable Aria to learn and improve from interactions
# =============================================================================

class ResponseFeedback(models.Model):
    """
    Stores user feedback (thumbs up/down) on AI responses.

    This enables:
    - Tracking which responses were helpful
    - Using highly-rated responses as few-shot examples
    - Identifying areas where Aria needs improvement
    - Capturing detailed issue reports for negative feedback
    """
    FEEDBACK_CHOICES = [
        ('positive', 'Helpful'),
        ('negative', 'Not Helpful'),
    ]

    ISSUE_TYPE_CHOICES = [
        ('missing_info', 'Information was missing'),
        ('wrong_info', 'Information was incorrect'),
        ('wrong_volunteer', 'Wrong volunteer identified'),
        ('no_response', 'No useful response'),
        ('slow_response', 'Response was too slow'),
        ('formatting', 'Response formatting issue'),
        ('other', 'Other issue'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='response_feedbacks',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )

    # The chat message this feedback is for
    chat_message = models.OneToOneField(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name='feedback',
        help_text="The AI response being rated"
    )

    # Who provided the feedback
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='response_feedbacks'
    )

    feedback_type = models.CharField(
        max_length=10,
        choices=FEEDBACK_CHOICES,
        help_text="Whether the response was helpful or not"
    )

    # Issue tracking fields for negative feedback
    issue_type = models.CharField(
        max_length=20,
        choices=ISSUE_TYPE_CHOICES,
        blank=True,
        help_text="Category of issue (for negative feedback)"
    )

    expected_result = models.TextField(
        blank=True,
        help_text="What the user expected to see"
    )

    # Optional comment explaining the feedback
    comment = models.TextField(
        blank=True,
        help_text="Optional explanation for the feedback"
    )

    # Context about the query for learning
    query_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of query (e.g., 'volunteer_info', 'setlist', 'lyrics')"
    )

    # Resolution tracking
    resolved = models.BooleanField(
        default=False,
        help_text="Whether this issue has been addressed"
    )

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_feedbacks',
        help_text="Admin who resolved this issue"
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the issue was resolved"
    )

    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes about how the issue was resolved"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Response Feedback'
        verbose_name_plural = 'Response Feedbacks'

    def __str__(self):
        return f"{self.feedback_type} feedback on message {self.chat_message_id}"

    @classmethod
    def get_positive_examples(cls, query_type: str = None, limit: int = 5):
        """
        Get highly-rated responses that can be used as few-shot examples.

        Args:
            query_type: Optional filter by query type.
            limit: Maximum number of examples to return.

        Returns:
            QuerySet of positive feedback with related chat messages.
        """
        qs = cls.objects.filter(feedback_type='positive').select_related('chat_message')
        if query_type:
            qs = qs.filter(query_type=query_type)
        return qs.order_by('-created_at')[:limit]


class LearnedCorrection(models.Model):
    """
    Stores corrections learned from user feedback.

    When users correct Aria (e.g., "Actually her name is spelled Sarah, not Sara"),
    this correction is stored and used to improve future responses.
    """
    CORRECTION_TYPE_CHOICES = [
        ('spelling', 'Spelling/Name'),
        ('fact', 'Factual Correction'),
        ('preference', 'Terminology Preference'),
        ('context', 'Contextual Correction'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='learned_corrections',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )

    # The incorrect value
    incorrect_value = models.CharField(
        max_length=500,
        db_index=True,
        help_text="The incorrect term/value that was used"
    )

    # The correct value
    correct_value = models.CharField(
        max_length=500,
        help_text="The correct term/value to use instead"
    )

    correction_type = models.CharField(
        max_length=20,
        choices=CORRECTION_TYPE_CHOICES,
        default='spelling'
    )

    # Optional: Link to a specific volunteer if it's about them
    volunteer = models.ForeignKey(
        Volunteer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='corrections',
        help_text="The volunteer this correction is about (if applicable)"
    )

    # Who provided this correction
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='provided_corrections'
    )

    # How many times this correction has been applied
    times_applied = models.IntegerField(default=0)

    # Is this correction active?
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-times_applied', '-created_at']
        unique_together = ['incorrect_value', 'volunteer']
        verbose_name = 'Learned Correction'
        verbose_name_plural = 'Learned Corrections'

    def __str__(self):
        return f"'{self.incorrect_value}' → '{self.correct_value}'"

    def apply(self):
        """Record that this correction was applied."""
        self.times_applied += 1
        self.save(update_fields=['times_applied'])

    @classmethod
    def find_correction(cls, text: str, volunteer=None):
        """
        Check if any corrections apply to the given text.

        Args:
            text: The text to check for corrections.
            volunteer: Optional volunteer context.

        Returns:
            The matching LearnedCorrection or None.
        """
        text_lower = text.lower()

        # First check volunteer-specific corrections
        if volunteer:
            correction = cls.objects.filter(
                is_active=True,
                volunteer=volunteer,
                incorrect_value__iexact=text
            ).first()
            if correction:
                return correction

        # Then check general corrections
        correction = cls.objects.filter(
            is_active=True,
            volunteer__isnull=True,
            incorrect_value__iexact=text
        ).first()

        return correction

    @classmethod
    def apply_corrections(cls, text: str, volunteer=None) -> str:
        """
        Apply all relevant corrections to a piece of text.

        Args:
            text: The text to correct.
            volunteer: Optional volunteer context.

        Returns:
            The corrected text.
        """
        import re

        # Get all active corrections
        corrections = cls.objects.filter(is_active=True)
        if volunteer:
            corrections = corrections.filter(
                models.Q(volunteer=volunteer) | models.Q(volunteer__isnull=True)
            )
        else:
            corrections = corrections.filter(volunteer__isnull=True)

        for correction in corrections:
            # Case-insensitive replacement
            pattern = re.compile(re.escape(correction.incorrect_value), re.IGNORECASE)
            if pattern.search(text):
                text = pattern.sub(correction.correct_value, text)
                correction.apply()

        return text


class ExtractedKnowledge(models.Model):
    """
    Stores structured knowledge extracted from interactions.

    This builds a knowledge base about volunteers that can be used
    to provide better, more informed responses.
    """
    KNOWLEDGE_TYPE_CHOICES = [
        ('hobby', 'Hobby/Interest'),
        ('family', 'Family Info'),
        ('preference', 'Preference'),
        ('birthday', 'Birthday'),
        ('anniversary', 'Anniversary'),
        ('prayer_request', 'Prayer Request'),
        ('health', 'Health Info'),
        ('work', 'Work/Career'),
        ('availability', 'Availability'),
        ('skill', 'Skill/Talent'),
        ('contact', 'Contact Info'),
        ('other', 'Other'),
    ]

    CONFIDENCE_CHOICES = [
        ('high', 'High - Directly stated'),
        ('medium', 'Medium - Inferred'),
        ('low', 'Low - Uncertain'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='extracted_knowledge',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )

    # The volunteer this knowledge is about
    volunteer = models.ForeignKey(
        Volunteer,
        on_delete=models.CASCADE,
        related_name='knowledge',
        help_text="The volunteer this knowledge is about"
    )

    knowledge_type = models.CharField(
        max_length=20,
        choices=KNOWLEDGE_TYPE_CHOICES,
        db_index=True
    )

    # The key (e.g., "favorite_food", "spouse_name", "birthday")
    key = models.CharField(
        max_length=100,
        help_text="The knowledge key (e.g., 'favorite_food', 'children_count')"
    )

    # The value (e.g., "Pizza", "Sarah", "March 15")
    value = models.TextField(
        help_text="The knowledge value"
    )

    # Confidence level in this knowledge
    confidence = models.CharField(
        max_length=10,
        choices=CONFIDENCE_CHOICES,
        default='medium'
    )

    # Source interaction (where we learned this)
    source_interaction = models.ForeignKey(
        Interaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='extracted_knowledge',
        help_text="The interaction where this was learned"
    )

    # Who extracted this (could be AI or human)
    extracted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='extracted_knowledge'
    )

    # Has this been verified by a human?
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether this knowledge has been verified by a human"
    )

    # Is this knowledge still current/valid?
    is_current = models.BooleanField(
        default=True,
        help_text="Whether this knowledge is still current"
    )

    # When this knowledge was last confirmed/used
    last_confirmed = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this knowledge was last confirmed as accurate"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-confidence', '-updated_at']
        verbose_name = 'Extracted Knowledge'
        verbose_name_plural = 'Extracted Knowledge'
        # Prevent duplicate knowledge entries
        unique_together = ['volunteer', 'knowledge_type', 'key']

    def __str__(self):
        return f"{self.volunteer.name}: {self.key} = {self.value}"

    def verify(self, user=None):
        """Mark this knowledge as verified."""
        from django.utils import timezone
        self.is_verified = True
        self.last_confirmed = timezone.now()
        self.confidence = 'high'
        self.save()

    def mark_outdated(self):
        """Mark this knowledge as no longer current."""
        self.is_current = False
        self.save(update_fields=['is_current', 'updated_at'])

    @classmethod
    def get_volunteer_profile(cls, volunteer) -> dict:
        """
        Get all current knowledge about a volunteer as a structured profile.

        Args:
            volunteer: The Volunteer instance.

        Returns:
            Dict with knowledge organized by type.
        """
        knowledge = cls.objects.filter(
            volunteer=volunteer,
            is_current=True
        ).order_by('-confidence', '-updated_at')

        profile = {}
        for k in knowledge:
            if k.knowledge_type not in profile:
                profile[k.knowledge_type] = {}
            profile[k.knowledge_type][k.key] = {
                'value': k.value,
                'confidence': k.confidence,
                'verified': k.is_verified,
                'last_updated': k.updated_at.isoformat() if k.updated_at else None
            }

        return profile

    @classmethod
    def update_or_create_knowledge(cls, volunteer, knowledge_type: str, key: str,
                                   value: str, source_interaction=None,
                                   confidence: str = 'medium', user=None):
        """
        Update existing knowledge or create new entry.

        Args:
            volunteer: The volunteer this is about.
            knowledge_type: Type of knowledge.
            key: The knowledge key.
            value: The knowledge value.
            source_interaction: Optional source interaction.
            confidence: Confidence level.
            user: User who extracted this.

        Returns:
            Tuple of (ExtractedKnowledge, created).
        """
        from django.utils import timezone

        obj, created = cls.objects.update_or_create(
            volunteer=volunteer,
            knowledge_type=knowledge_type,
            key=key,
            defaults={
                'value': value,
                'confidence': confidence,
                'source_interaction': source_interaction,
                'extracted_by': user,
                'is_current': True,
            }
        )

        # Update last_confirmed only when updating existing knowledge (not creating)
        if not created:
            obj.last_confirmed = timezone.now()
            obj.save(update_fields=['last_confirmed'])

        return obj, created


class QueryPattern(models.Model):
    """
    Stores successful query patterns for intent recognition improvement.

    When a query leads to a helpful response (positive feedback),
    the pattern is stored to help with similar future queries.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='query_patterns',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )

    # The original query text
    query_text = models.TextField(
        help_text="The original query from the user"
    )

    # Normalized/cleaned version for matching
    normalized_query = models.CharField(
        max_length=500,
        db_index=True,
        help_text="Normalized version of the query for matching"
    )

    # The detected intent/query type
    detected_intent = models.CharField(
        max_length=50,
        db_index=True,
        help_text="The intent that was detected (e.g., 'volunteer_info', 'setlist')"
    )

    # Extracted entities
    extracted_entities = models.JSONField(
        default=dict,
        blank=True,
        help_text="Entities extracted from the query (names, dates, etc.)"
    )

    # Link to the positive feedback that validated this pattern
    validated_by_feedback = models.ForeignKey(
        ResponseFeedback,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validated_patterns'
    )

    # How often this pattern has been matched
    match_count = models.IntegerField(default=1)

    # Success rate (positive responses / total uses)
    success_count = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-match_count', '-success_count']
        verbose_name = 'Query Pattern'
        verbose_name_plural = 'Query Patterns'

    def __str__(self):
        return f"'{self.normalized_query[:50]}...' → {self.detected_intent}"

    @property
    def success_rate(self) -> float:
        """Calculate the success rate for this pattern."""
        if self.match_count == 0:
            return 0.0
        return self.success_count / self.match_count

    def record_match(self, was_successful: bool = True):
        """Record that this pattern was matched."""
        self.match_count += 1
        if was_successful:
            self.success_count += 1
        self.save(update_fields=['match_count', 'success_count', 'updated_at'])

    @classmethod
    def find_similar_pattern(cls, query: str, threshold: float = 0.7):
        """
        Find a similar pattern to help with intent detection.

        Args:
            query: The new query to match.
            threshold: Minimum similarity threshold.

        Returns:
            The best matching QueryPattern or None.
        """
        from difflib import SequenceMatcher

        normalized = cls.normalize_query(query)
        patterns = cls.objects.filter(success_count__gte=1).order_by('-success_count')[:100]

        best_match = None
        best_score = threshold

        for pattern in patterns:
            score = SequenceMatcher(None, normalized, pattern.normalized_query).ratio()
            # Boost score based on success rate
            score *= (0.5 + 0.5 * pattern.success_rate)

            if score > best_score:
                best_score = score
                best_match = pattern

        return best_match

    @staticmethod
    def normalize_query(query: str) -> str:
        """Normalize a query for pattern matching."""
        import re
        # Lowercase
        normalized = query.lower().strip()
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        # Remove punctuation except question marks
        normalized = re.sub(r'[^\w\s?]', '', normalized)
        return normalized


class ReportCache(models.Model):
    """
    Caches generated reports to avoid expensive recomputation.

    Reports are cached with a TTL and regenerated on-demand when expired.
    """
    REPORT_TYPE_CHOICES = [
        ('volunteer_engagement', 'Volunteer Engagement'),
        ('team_care', 'Team Care'),
        ('interaction_trends', 'Interaction Trends'),
        ('prayer_summary', 'Prayer Request Summary'),
        ('ai_performance', 'AI Performance'),
        ('service_participation', 'Service Participation'),
        ('dashboard_summary', 'Dashboard Summary'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='report_caches',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )

    report_type = models.CharField(
        max_length=50,
        choices=REPORT_TYPE_CHOICES,
        db_index=True
    )

    # Parameters used to generate this report (for cache key)
    parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Parameters used to generate this report (date range, filters, etc.)"
    )

    # The cached report data
    data = models.JSONField(
        help_text="The generated report data"
    )

    # Cache management
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        help_text="When this cache entry expires"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Report Cache'
        verbose_name_plural = 'Report Caches'
        indexes = [
            models.Index(fields=['report_type', 'expires_at']),
        ]

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @classmethod
    def get_cached_report(cls, report_type: str, parameters: dict = None) -> dict:
        """
        Get a cached report if available and not expired.

        Args:
            report_type: Type of report to retrieve
            parameters: Parameters to match

        Returns:
            Cached report data or None
        """
        from django.utils import timezone

        params = parameters or {}
        cache_entry = cls.objects.filter(
            report_type=report_type,
            parameters=params,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()

        if cache_entry:
            return cache_entry.data
        return None

    @classmethod
    def set_cached_report(cls, report_type: str, data: dict,
                          parameters: dict = None, ttl_minutes: int = 30) -> 'ReportCache':
        """
        Cache a generated report.

        Args:
            report_type: Type of report
            data: Report data to cache
            parameters: Parameters used to generate
            ttl_minutes: Time to live in minutes

        Returns:
            The created cache entry
        """
        from django.utils import timezone
        from datetime import timedelta

        params = parameters or {}

        # Delete old cache entries for this report type + params
        cls.objects.filter(
            report_type=report_type,
            parameters=params
        ).delete()

        return cls.objects.create(
            report_type=report_type,
            parameters=params,
            data=data,
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes)
        )

    @classmethod
    def clear_expired(cls) -> int:
        """Delete all expired cache entries. Returns count deleted."""
        from django.utils import timezone
        count, _ = cls.objects.filter(expires_at__lt=timezone.now()).delete()
        return count

    @classmethod
    def clear_all(cls, report_type: str = None) -> int:
        """
        Clear all cached reports, optionally filtered by type.

        Args:
            report_type: Optional type to filter by

        Returns:
            Count of deleted entries
        """
        qs = cls.objects.all()
        if report_type:
            qs = qs.filter(report_type=report_type)
        count, _ = qs.delete()
        return count


class VolunteerInsight(models.Model):
    """
    AI-generated insights about volunteer engagement and care needs.

    These insights are proactively generated to help team leaders
    identify volunteers who may need attention, follow-up, or care.
    """
    INSIGHT_TYPE_CHOICES = [
        ('engagement_drop', 'Engagement Drop'),
        ('no_recent_contact', 'No Recent Contact'),
        ('prayer_need', 'Prayer Need'),
        ('birthday_upcoming', 'Birthday Upcoming'),
        ('anniversary_upcoming', 'Anniversary Upcoming'),
        ('new_volunteer', 'New Volunteer Check-in'),
        ('returning', 'Returning After Absence'),
        ('overdue_followup', 'Overdue Follow-up'),
        ('frequent_declines', 'Frequent Schedule Declines'),
        ('milestone', 'Service Milestone'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('actioned', 'Actioned'),
        ('dismissed', 'Dismissed'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='volunteer_insights',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )

    volunteer = models.ForeignKey(
        Volunteer,
        on_delete=models.CASCADE,
        related_name='insights',
        help_text='The volunteer this insight is about'
    )

    insight_type = models.CharField(
        max_length=30,
        choices=INSIGHT_TYPE_CHOICES,
        db_index=True,
        help_text='Type of care insight'
    )

    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium',
        db_index=True
    )

    title = models.CharField(
        max_length=200,
        help_text='Short title for the insight'
    )

    message = models.TextField(
        help_text='Detailed description of the insight'
    )

    suggested_action = models.TextField(
        blank=True,
        help_text='Recommended action to take'
    )

    # Context data for the insight
    context_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional context (days since contact, dates, etc.)'
    )

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True
    )

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_insights'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-priority', '-created_at']
        verbose_name = 'Volunteer Insight'
        verbose_name_plural = 'Volunteer Insights'
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['insight_type', 'status']),
        ]

    def __str__(self):
        return f"{self.get_insight_type_display()} - {self.volunteer.name}"

    def acknowledge(self, user):
        """Mark the insight as acknowledged."""
        self.status = 'acknowledged'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()

    def mark_actioned(self, user):
        """Mark the insight as actioned (follow-up completed)."""
        self.status = 'actioned'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()

    def dismiss(self, user):
        """Dismiss the insight."""
        self.status = 'dismissed'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()

    @classmethod
    def get_active_insights(cls, limit: int = None):
        """Get all active insights ordered by priority."""
        qs = cls.objects.filter(status='active').select_related('volunteer')
        if limit:
            qs = qs[:limit]
        return qs

    @classmethod
    def get_insights_for_volunteer(cls, volunteer_id: int):
        """Get all active insights for a specific volunteer."""
        return cls.objects.filter(
            volunteer_id=volunteer_id,
            status='active'
        ).order_by('-priority', '-created_at')


# =============================================================================
# Team Communication Hub Models
# =============================================================================

class Announcement(models.Model):
    """
    Team-wide announcements that all members can see.

    Used for important updates, reminders, and information
    that needs to reach the entire Worship Arts team.
    """
    PRIORITY_CHOICES = [
        ('normal', 'Normal'),
        ('important', 'Important'),
        ('urgent', 'Urgent'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='announcements',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )

    title = models.CharField(max_length=200)
    content = models.TextField(help_text="Announcement content (supports markdown)")

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='announcements'
    )

    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='normal'
    )

    # Optional: target specific teams
    target_teams = models.JSONField(
        default=list,
        blank=True,
        help_text="List of team names to target, empty means all teams"
    )

    # Pinned announcements stay at top
    is_pinned = models.BooleanField(default=False)

    # Scheduling
    publish_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Schedule announcement for future (null = immediate)"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Auto-hide after this date"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-priority', '-created_at']
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        """Check if announcement should be visible."""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.publish_at and self.publish_at > now:
            return False
        if self.expires_at and self.expires_at < now:
            return False
        return True


class AnnouncementRead(models.Model):
    """Track which users have read which announcements."""
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name='reads'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='announcement_reads'
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['announcement', 'user']


class Channel(models.Model):
    """
    Chat channels for team communication.

    Channels can be team-specific (e.g., "Vocals", "Band") or
    topic-specific (e.g., "Sunday Planning", "Equipment").
    """
    CHANNEL_TYPE_CHOICES = [
        ('team', 'Team Channel'),
        ('topic', 'Topic Channel'),
        ('project', 'Project Channel'),
        ('general', 'General'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='channels',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)

    channel_type = models.CharField(
        max_length=10,
        choices=CHANNEL_TYPE_CHOICES,
        default='general'
    )

    # For team channels, link to team name
    team_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="For team channels, the team this channel is for"
    )

    # Members (if empty, all users can access)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='channels'
    )

    # Channel settings
    is_private = models.BooleanField(
        default=False,
        help_text="Private channels require membership"
    )
    is_archived = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_channels'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Channel'
        verbose_name_plural = 'Channels'
        # Slug is unique within an organization
        unique_together = [['organization', 'slug']]

    def __str__(self):
        return f"#{self.name}"

    def can_access(self, user):
        """Check if user can access this channel."""
        if not self.is_private:
            return True
        return self.members.filter(pk=user.pk).exists()


class ChannelMessage(models.Model):
    """
    Messages within a channel.
    """
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='channel_messages'
    )

    content = models.TextField()

    # @mentions of users
    mentioned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='channel_mentions_received'
    )

    # Optional: attach to a volunteer or interaction
    mentioned_volunteers = models.ManyToManyField(
        Volunteer,
        blank=True,
        related_name='channel_mentions'
    )

    # For replies/threads
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )

    is_edited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Channel Message'
        verbose_name_plural = 'Channel Messages'

    def __str__(self):
        return f"{self.author} in {self.channel}: {self.content[:50]}"


class DirectMessage(models.Model):
    """
    Private direct messages between two users.
    """
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='received_messages'
    )

    content = models.TextField()

    # Read status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Direct Message'
        verbose_name_plural = 'Direct Messages'

    def __str__(self):
        return f"DM from {self.sender} to {self.recipient}"

    def mark_as_read(self):
        """Mark message as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


# =============================================================================
# Project and Task Management Models
# =============================================================================

class Project(models.Model):
    """
    Projects for team coordination with tasks and deadlines.
    """
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='projects',
        null=True,  # Temporary: allows migration of existing data
        blank=True
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planning'
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )

    # Dates
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Team members
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_projects'
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='projects'
    )

    # Optional: link to a channel for project discussions
    channel = models.OneToOneField(
        Channel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project'
    )

    # For service-specific projects (e.g., "Easter 2025")
    service_date = models.DateField(
        null=True,
        blank=True,
        help_text="For service-specific projects"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'

    def __str__(self):
        return self.name

    @property
    def is_overdue(self):
        """Check if project is overdue."""
        if self.due_date and self.status not in ['completed', 'archived']:
            return timezone.now().date() > self.due_date
        return False

    @property
    def progress_percent(self):
        """Calculate project progress based on completed tasks."""
        total = self.tasks.count()
        if total == 0:
            return 0
        completed = self.tasks.filter(status='completed').count()
        return int((completed / total) * 100)

    def add_member(self, user, notify=True):
        """Add a member to the project and optionally send notification."""
        if user not in self.members.all():
            self.members.add(user)
            if notify:
                from .notifications import notify_project_assignment
                notify_project_assignment(self, user)


class Task(models.Model):
    """
    Tasks within a project with assignments and due dates.
    """
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('review', 'In Review'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='tasks'
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='todo'
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )

    # Assignment
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='assigned_tasks'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks'
    )

    # Dates
    due_date = models.DateField(null=True, blank=True)
    due_time = models.TimeField(null=True, blank=True, help_text="Optional specific time")
    completed_at = models.DateTimeField(null=True, blank=True)

    # Ordering within project
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-priority', 'due_date', 'created_at']
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'

    def __str__(self):
        return f"{self.title} ({self.project.name})"

    @property
    def is_overdue(self):
        """Check if task is overdue."""
        if self.due_date and self.status not in ['completed', 'cancelled']:
            return timezone.now().date() > self.due_date
        return False

    def assign_to(self, user, notify=True):
        """Assign task to a user and optionally send notification."""
        if user not in self.assignees.all():
            self.assignees.add(user)
            if notify:
                from .notifications import notify_task_assignment
                notify_task_assignment(self, user)

    def mark_completed(self):
        """Mark task as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])


class TaskComment(models.Model):
    """
    Comments on tasks for discussion and updates.
    """
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_comments'
    )

    content = models.TextField()

    # @mentions in comments
    mentioned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='task_comment_mentions'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Task Comment'
        verbose_name_plural = 'Task Comments'

    def __str__(self):
        return f"Comment by {self.author} on {self.task.title}"


class TaskChecklist(models.Model):
    """
    Checklist items (subtasks) within a task.
    Allows breaking down complex tasks into smaller steps.
    """
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='checklists'
    )
    title = models.CharField(max_length=200)
    is_completed = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_checklist_items'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Task Checklist Item'
        verbose_name_plural = 'Task Checklist Items'

    def __str__(self):
        status = "✓" if self.is_completed else "○"
        return f"{status} {self.title}"

    def mark_completed(self, user):
        """Mark this checklist item as completed."""
        self.is_completed = True
        self.completed_by = user
        self.completed_at = timezone.now()
        self.save(update_fields=['is_completed', 'completed_by', 'completed_at', 'updated_at'])

    def mark_incomplete(self):
        """Mark this checklist item as incomplete."""
        self.is_completed = False
        self.completed_by = None
        self.completed_at = None
        self.save(update_fields=['is_completed', 'completed_by', 'completed_at', 'updated_at'])


class TaskTemplate(models.Model):
    """
    Templates for recurring tasks with dynamic title generation.

    Title placeholders:
    - {date} - Full date (e.g., "December 3rd, 2024")
    - {day} - Day with ordinal (e.g., "3rd")
    - {day_num} - Day number (e.g., "3")
    - {month} - Month name (e.g., "December")
    - {month_short} - Short month (e.g., "Dec")
    - {year} - Year (e.g., "2024")
    - {weekday} - Weekday name (e.g., "Sunday")
    - {weekday_short} - Short weekday (e.g., "Sun")

    Example: "Stage Set {month} {day}" → "Stage Set December 3rd"
    """
    RECURRENCE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Every 2 Weeks'),
        ('monthly', 'Monthly (same day)'),
        ('monthly_weekday', 'Monthly (same weekday)'),  # e.g., "2nd Sunday"
        ('custom', 'Custom Days'),
    ]

    name = models.CharField(
        max_length=200,
        help_text="Internal name for this template (e.g., 'Weekly Stage Set')"
    )
    title_template = models.CharField(
        max_length=200,
        help_text="Task title with placeholders. Example: 'Stage Set {month} {day}'"
    )
    description_template = models.TextField(
        blank=True,
        help_text="Optional description with same placeholders"
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='task_templates'
    )

    # Recurrence settings
    recurrence_type = models.CharField(
        max_length=20,
        choices=RECURRENCE_CHOICES,
        default='weekly'
    )
    recurrence_days = models.JSONField(
        default=list,
        blank=True,
        help_text="For weekly: [0-6] (Mon-Sun). For monthly: [1-31]. For custom: specific dates."
    )
    # For monthly_weekday: which occurrence (1st, 2nd, 3rd, 4th, -1 for last)
    weekday_occurrence = models.IntegerField(
        null=True,
        blank=True,
        help_text="For monthly weekday: 1=first, 2=second, -1=last, etc."
    )

    # Default task settings
    default_assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='task_template_assignments',
        help_text="Team members automatically assigned to generated tasks"
    )
    default_priority = models.CharField(
        max_length=10,
        choices=Task.PRIORITY_CHOICES,
        default='medium'
    )
    default_status = models.CharField(
        max_length=20,
        choices=Task.STATUS_CHOICES,
        default='todo'
    )

    # Timing
    days_before_due = models.IntegerField(
        default=3,
        help_text="Create task this many days before the due date"
    )
    due_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Default due time for generated tasks"
    )

    # Default checklist items (created with each task)
    default_checklist = models.JSONField(
        default=list,
        blank=True,
        help_text="List of checklist item titles to create with each task"
    )

    # Auto-generation tracking
    is_active = models.BooleanField(default=True)
    last_generated_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of the last task generated from this template"
    )
    next_occurrence = models.DateField(
        null=True,
        blank=True,
        help_text="Next date a task will be generated for"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_task_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['project', 'name']
        verbose_name = 'Task Template'
        verbose_name_plural = 'Task Templates'

    def __str__(self):
        return f"{self.name} ({self.project.name})"

    def _ordinal(self, n):
        """Convert number to ordinal (1st, 2nd, 3rd, etc.)"""
        if 11 <= (n % 100) <= 13:
            suffix = 'th'
        else:
            suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
        return f"{n}{suffix}"

    def format_title(self, target_date):
        """
        Format the title template with the target date.

        Args:
            target_date: datetime.date object

        Returns:
            Formatted title string
        """
        placeholders = {
            'date': target_date.strftime('%B ') + self._ordinal(target_date.day) + target_date.strftime(', %Y'),
            'day': self._ordinal(target_date.day),
            'day_num': str(target_date.day),
            'month': target_date.strftime('%B'),
            'month_short': target_date.strftime('%b'),
            'year': str(target_date.year),
            'weekday': target_date.strftime('%A'),
            'weekday_short': target_date.strftime('%a'),
        }

        title = self.title_template
        for key, value in placeholders.items():
            title = title.replace('{' + key + '}', value)

        return title

    def format_description(self, target_date):
        """Format the description template with the target date."""
        if not self.description_template:
            return ''

        placeholders = {
            'date': target_date.strftime('%B ') + self._ordinal(target_date.day) + target_date.strftime(', %Y'),
            'day': self._ordinal(target_date.day),
            'day_num': str(target_date.day),
            'month': target_date.strftime('%B'),
            'month_short': target_date.strftime('%b'),
            'year': str(target_date.year),
            'weekday': target_date.strftime('%A'),
            'weekday_short': target_date.strftime('%a'),
        }

        description = self.description_template
        for key, value in placeholders.items():
            description = description.replace('{' + key + '}', value)

        return description

    def get_next_occurrences(self, from_date=None, count=5):
        """
        Calculate the next N occurrence dates based on recurrence settings.

        Args:
            from_date: Start calculating from this date (defaults to today)
            count: Number of occurrences to return

        Returns:
            List of datetime.date objects
        """
        from datetime import timedelta
        import calendar

        if from_date is None:
            from_date = timezone.now().date()

        occurrences = []
        current = from_date

        # Maximum iterations to prevent infinite loops
        max_iterations = 365 * 2

        iteration = 0
        while len(occurrences) < count and iteration < max_iterations:
            iteration += 1

            if self.recurrence_type == 'daily':
                if current >= from_date:
                    occurrences.append(current)
                current += timedelta(days=1)

            elif self.recurrence_type == 'weekly':
                # recurrence_days is list of weekday numbers [0-6] where 0=Monday, 6=Sunday
                weekday = current.weekday()
                if weekday in self.recurrence_days and current >= from_date:
                    occurrences.append(current)
                current += timedelta(days=1)

            elif self.recurrence_type == 'biweekly':
                weekday = current.weekday()
                if weekday in self.recurrence_days and current >= from_date:
                    # Check if this is an "on" week (every other week)
                    week_num = current.isocalendar()[1]
                    if week_num % 2 == 0:  # Even weeks
                        occurrences.append(current)
                current += timedelta(days=1)

            elif self.recurrence_type == 'monthly':
                # recurrence_days is list of day numbers [1-31]
                if current.day in self.recurrence_days and current >= from_date:
                    occurrences.append(current)
                current += timedelta(days=1)

            elif self.recurrence_type == 'monthly_weekday':
                # e.g., "2nd Sunday of every month"
                weekday = current.weekday()
                if weekday in self.recurrence_days and current >= from_date:
                    # Check if this is the right occurrence
                    occurrence_num = (current.day - 1) // 7 + 1
                    if self.weekday_occurrence == -1:
                        # Last occurrence of this weekday
                        days_in_month = calendar.monthrange(current.year, current.month)[1]
                        is_last = current.day + 7 > days_in_month
                        if is_last:
                            occurrences.append(current)
                    elif occurrence_num == self.weekday_occurrence:
                        occurrences.append(current)
                current += timedelta(days=1)

            elif self.recurrence_type == 'custom':
                # recurrence_days contains specific date strings or patterns
                # For simplicity, treat as specific day-of-month numbers
                if current.day in self.recurrence_days and current >= from_date:
                    occurrences.append(current)
                current += timedelta(days=1)

        return occurrences

    def generate_task(self, target_date, created_by=None):
        """
        Generate a task for the specified target date.

        Args:
            target_date: The due date for the task
            created_by: User creating the task (defaults to template creator)

        Returns:
            Created Task instance
        """
        title = self.format_title(target_date)
        description = self.format_description(target_date)

        task = Task.objects.create(
            project=self.project,
            title=title,
            description=description,
            status=self.default_status,
            priority=self.default_priority,
            due_date=target_date,
            due_time=self.due_time,
            created_by=created_by or self.created_by
        )

        # Add default assignees
        for assignee in self.default_assignees.all():
            task.assignees.add(assignee)

        # Create default checklist items
        for i, item_title in enumerate(self.default_checklist):
            TaskChecklist.objects.create(
                task=task,
                title=item_title,
                order=i
            )

        # Update tracking
        self.last_generated_date = target_date
        self.save(update_fields=['last_generated_date', 'updated_at'])

        # Send notifications to assignees
        from .notifications import notify_task_assignment
        for assignee in task.assignees.all():
            notify_task_assignment(task, assignee)

        return task

    def calculate_next_occurrence(self):
        """Calculate and update the next occurrence date."""
        today = timezone.now().date()
        start_from = self.last_generated_date or today

        # Get next occurrences starting from the day after the last generated
        if self.last_generated_date:
            start_from = self.last_generated_date + timezone.timedelta(days=1)

        occurrences = self.get_next_occurrences(from_date=start_from, count=1)

        if occurrences:
            self.next_occurrence = occurrences[0]
        else:
            self.next_occurrence = None

        self.save(update_fields=['next_occurrence', 'updated_at'])
        return self.next_occurrence


# =============================================================================
# Push Notification Models
# =============================================================================

class PushSubscription(models.Model):
    """
    Stores push notification subscriptions for users.

    Each subscription represents a browser/device that can receive
    push notifications via the Web Push API.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions'
    )

    # Web Push subscription data
    endpoint = models.TextField(unique=True)
    p256dh_key = models.CharField(max_length=200, help_text="Public key for encryption")
    auth_key = models.CharField(max_length=100, help_text="Auth secret for encryption")

    # Device info for user management
    user_agent = models.TextField(blank=True)
    device_name = models.CharField(max_length=100, blank=True, help_text="Friendly name like 'iPhone' or 'Chrome on Mac'")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Push Subscription'
        verbose_name_plural = 'Push Subscriptions'

    def __str__(self):
        return f"{self.user.username} - {self.device_name or 'Unknown device'}"

    def to_webpush_dict(self):
        """Return subscription info in format needed by pywebpush."""
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh_key,
                "auth": self.auth_key
            }
        }


class NotificationPreference(models.Model):
    """
    User preferences for what notifications they want to receive.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )

    # Notification types
    announcements = models.BooleanField(default=True, help_text="New team announcements")
    announcements_urgent_only = models.BooleanField(default=False, help_text="Only urgent announcements")

    direct_messages = models.BooleanField(default=True, help_text="New direct messages")

    channel_messages = models.BooleanField(default=False, help_text="New channel messages")
    channel_mentions_only = models.BooleanField(default=True, help_text="Only when mentioned in channels")

    care_alerts = models.BooleanField(default=True, help_text="Proactive care alerts")
    care_urgent_only = models.BooleanField(default=False, help_text="Only urgent care alerts")

    followup_reminders = models.BooleanField(default=True, help_text="Follow-up due date reminders")

    # Quiet hours (don't send notifications during these times)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True, help_text="Start of quiet hours (e.g., 22:00)")
    quiet_hours_end = models.TimeField(null=True, blank=True, help_text="End of quiet hours (e.g., 07:00)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'

    def __str__(self):
        return f"Notification preferences for {self.user.username}"

    def should_send_now(self):
        """Check if we're outside quiet hours."""
        if not self.quiet_hours_enabled:
            return True

        if not self.quiet_hours_start or not self.quiet_hours_end:
            return True

        now = timezone.localtime().time()
        start = self.quiet_hours_start
        end = self.quiet_hours_end

        # Handle overnight quiet hours (e.g., 22:00 - 07:00)
        if start > end:
            # Quiet if after start OR before end
            return not (now >= start or now <= end)
        else:
            # Quiet if between start and end
            return not (start <= now <= end)

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create notification preferences for a user."""
        prefs, created = cls.objects.get_or_create(user=user)
        return prefs


class NotificationLog(models.Model):
    """
    Log of notifications sent for debugging and analytics.
    """
    NOTIFICATION_TYPES = [
        ('announcement', 'Announcement'),
        ('dm', 'Direct Message'),
        ('channel', 'Channel Message'),
        ('care', 'Care Alert'),
        ('followup', 'Follow-up Reminder'),
        ('test', 'Test Notification'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('clicked', 'Clicked'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_logs'
    )
    subscription = models.ForeignKey(
        PushSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    body = models.TextField()
    url = models.CharField(max_length=500, blank=True, help_text="URL to open when notification clicked")
    data = models.JSONField(default=dict, blank=True, help_text="Additional data sent with notification")

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'

    def __str__(self):
        return f"{self.notification_type}: {self.title} -> {self.user.username}"


class SongBPMCache(models.Model):
    """
    Caches BPM values for songs with source tracking.

    BPM values are retrieved from multiple sources in priority order:
    1. PCO arrangement BPM (authoritative)
    2. Chord chart text parsing
    3. Audio analysis (librosa)
    4. SongBPM API lookup
    """
    BPM_SOURCE_CHOICES = [
        ('pco', 'Planning Center'),
        ('chord_chart', 'Chord Chart Text'),
        ('audio_analysis', 'Audio Analysis'),
        ('songbpm_api', 'SongBPM API'),
        ('manual', 'Manual Entry'),
    ]

    CONFIDENCE_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='song_bpm_caches',
        null=True,
        blank=True
    )

    # PCO song identifiers
    pco_song_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Planning Center Online song ID"
    )
    pco_arrangement_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="PCO arrangement ID (if BPM is arrangement-specific)"
    )

    # Song metadata for SongBPM API lookups and display
    song_title = models.CharField(
        max_length=255,
        help_text="Song title for display and API lookups"
    )
    song_artist = models.CharField(
        max_length=255,
        blank=True,
        help_text="Song artist/author for API lookups"
    )

    # BPM data
    bpm = models.PositiveIntegerField(
        help_text="Beats per minute (tempo)"
    )
    bpm_source = models.CharField(
        max_length=20,
        choices=BPM_SOURCE_CHOICES,
        db_index=True,
        help_text="Source where BPM was obtained"
    )
    confidence = models.CharField(
        max_length=10,
        choices=CONFIDENCE_CHOICES,
        default='high',
        help_text="Confidence level of the BPM value"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Source-specific metadata
    source_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata from the BPM source"
    )

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Song BPM Cache'
        verbose_name_plural = 'Song BPM Caches'
        indexes = [
            models.Index(fields=['pco_song_id', 'organization']),
            models.Index(fields=['song_title', 'song_artist']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'pco_song_id', 'pco_arrangement_id'],
                name='unique_org_song_arrangement_bpm'
            )
        ]

    def __str__(self):
        return f"{self.song_title} - {self.bpm} BPM ({self.get_bpm_source_display()})"

    @classmethod
    def get_cached_bpm(cls, pco_song_id: str, organization=None, arrangement_id: str = None):
        """
        Get cached BPM for a song.

        Args:
            pco_song_id: PCO song ID
            organization: Organization instance (for multi-tenant)
            arrangement_id: Optional arrangement ID for arrangement-specific BPM

        Returns:
            Tuple of (bpm, source, confidence) or (None, None, None) if not cached
        """
        filters = {'pco_song_id': pco_song_id}
        if organization:
            filters['organization'] = organization
        if arrangement_id:
            filters['pco_arrangement_id'] = arrangement_id

        cache_entry = cls.objects.filter(**filters).first()
        if cache_entry:
            return (cache_entry.bpm, cache_entry.bpm_source, cache_entry.confidence)
        return (None, None, None)

    @classmethod
    def set_cached_bpm(cls, pco_song_id: str, bpm: int, bpm_source: str,
                       song_title: str, organization=None, arrangement_id: str = None,
                       song_artist: str = '', confidence: str = 'high',
                       source_metadata: dict = None):
        """
        Cache a BPM value for a song.

        Args:
            pco_song_id: PCO song ID
            bpm: BPM value
            bpm_source: Source of the BPM (pco, chord_chart, audio_analysis, songbpm_api)
            song_title: Song title
            organization: Organization instance
            arrangement_id: Optional arrangement ID
            song_artist: Song artist/author
            confidence: Confidence level (high, medium, low)
            source_metadata: Additional metadata from the source

        Returns:
            SongBPMCache instance
        """
        defaults = {
            'bpm': bpm,
            'bpm_source': bpm_source,
            'song_title': song_title,
            'song_artist': song_artist or '',
            'confidence': confidence,
            'source_metadata': source_metadata or {},
        }

        lookup = {
            'pco_song_id': pco_song_id,
            'organization': organization,
            'pco_arrangement_id': arrangement_id,
        }

        cache_entry, created = cls.objects.update_or_create(
            **lookup, defaults=defaults
        )
        return cache_entry
