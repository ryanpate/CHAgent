from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class SongSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
        ('rejected', 'Not Added'),
    ]

    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='song_submissions',
    )

    # Song info
    title = models.CharField(max_length=200)
    artist = models.CharField(max_length=200)
    link = models.URLField(blank=True)

    # Submitter info
    submitter_name = models.CharField(max_length=200, blank=True)
    submitter_comment = models.TextField(blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='song_submissions',
    )

    # Review
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_song_submissions',
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Denormalized voting data
    average_rating = models.FloatField(default=0.0)
    vote_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} by {self.artist}"

    def update_rating(self):
        """Recalculate average_rating and vote_count from votes."""
        from django.db.models import Avg, Count
        stats = self.votes.aggregate(avg=Avg('rating'), count=Count('id'))
        self.average_rating = round(stats['avg'] or 0.0, 1)
        self.vote_count = stats['count'] or 0
        self.save(update_fields=['average_rating', 'vote_count'])


class SongVote(models.Model):
    submission = models.ForeignKey(
        SongSubmission,
        on_delete=models.CASCADE,
        related_name='votes',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['submission', 'user']

    def __str__(self):
        return f"{self.user} rated {self.submission.title}: {self.rating}/5"
