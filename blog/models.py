"""
Blog models for SEO content management.
"""
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class BlogCategory(models.Model):
    """Category for organizing blog posts."""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    meta_description = models.CharField(max_length=160, blank=True,
        help_text="SEO meta description for category page (max 160 chars)")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Blog Categories"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:category', kwargs={'slug': self.slug})

    def published_posts(self):
        return self.posts.filter(status='published', published_at__lte=timezone.now())


class BlogPost(models.Model):
    """Blog post for SEO content."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    # Core content
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200)
    excerpt = models.TextField(max_length=300, blank=True,
        help_text="Brief summary shown in listings (max 300 chars)")
    content = models.TextField(help_text="Full post content (supports Markdown)")

    # Categorization
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='posts')

    # SEO fields
    meta_title = models.CharField(max_length=60, blank=True,
        help_text="SEO title tag (max 60 chars). Leave blank to use post title.")
    meta_description = models.CharField(max_length=160, blank=True,
        help_text="SEO meta description (max 160 chars)")
    focus_keyword = models.CharField(max_length=100, blank=True,
        help_text="Primary keyword to optimize for")

    # Featured image
    featured_image_url = models.URLField(blank=True,
        help_text="URL for the featured image (for og:image)")
    featured_image_alt = models.CharField(max_length=200, blank=True,
        help_text="Alt text for featured image")

    # Publication
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    author_name = models.CharField(max_length=100, default="Aria Team",
        help_text="Display name for the author")
    published_at = models.DateTimeField(null=True, blank=True)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        # Auto-set published_at when publishing
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        # Generate excerpt from content if not provided
        if not self.excerpt and self.content:
            self.excerpt = self.content[:297] + '...' if len(self.content) > 300 else self.content
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:post_detail', kwargs={'slug': self.slug})

    def get_meta_title(self):
        """Return meta title or fallback to post title."""
        return self.meta_title if self.meta_title else f"{self.title} | Aria Blog"

    def get_meta_description(self):
        """Return meta description or fallback to excerpt."""
        return self.meta_description if self.meta_description else self.excerpt

    def is_published(self):
        """Check if post is published and publication date has passed."""
        if self.status != 'published':
            return False
        if not self.published_at:
            return False
        return self.published_at <= timezone.now()

    def reading_time(self):
        """Estimate reading time based on word count (200 wpm average)."""
        word_count = len(self.content.split())
        minutes = max(1, round(word_count / 200))
        return f"{minutes} min read"


class BlogTag(models.Model):
    """Tags for blog posts (many-to-many)."""
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    posts = models.ManyToManyField(BlogPost, related_name='tags', blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:tag', kwargs={'slug': self.slug})
