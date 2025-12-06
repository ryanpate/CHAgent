from django.db import models
from django.conf import settings

# Try to import pgvector, fall back to a placeholder if not available
try:
    from pgvector.django import VectorField
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
    # Placeholder for development without pgvector
    VectorField = None


class Volunteer(models.Model):
    """
    Volunteer profiles - auto-created/linked when AI identifies
    a volunteer in an interaction. Minimal structure, AI-driven.
    """
    name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200, db_index=True)  # lowercase for matching
    team = models.CharField(max_length=100, blank=True)  # vocals, band, tech, etc.
    planning_center_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

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
                'last_confirmed': timezone.now() if not created else None
            }
        )

        return obj, created


class QueryPattern(models.Model):
    """
    Stores successful query patterns for intent recognition improvement.

    When a query leads to a helpful response (positive feedback),
    the pattern is stored to help with similar future queries.
    """
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

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
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
