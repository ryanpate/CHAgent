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
