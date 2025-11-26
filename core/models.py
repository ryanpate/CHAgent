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

    def set_pending_song_suggestions(self, suggestions: list):
        """Store song suggestions for user selection."""
        self.pending_song_suggestions = suggestions

    def get_pending_song_suggestions(self) -> list:
        """Get stored song suggestions."""
        return self.pending_song_suggestions or []

    def clear_pending_song_suggestions(self):
        """Clear pending song suggestions after selection."""
        self.pending_song_suggestions = []
