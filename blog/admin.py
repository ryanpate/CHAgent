"""
Blog admin configuration.
"""
from django.contrib import admin
from .models import BlogPost, BlogCategory, BlogTag


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    ordering = ['order', 'name']


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'status', 'published_at', 'view_count']
    list_filter = ['status', 'category', 'published_at']
    search_fields = ['title', 'content', 'meta_description']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    ordering = ['-created_at']

    fieldsets = (
        ('Content', {
            'fields': ('title', 'slug', 'excerpt', 'content', 'category')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'focus_keyword'),
            'classes': ('collapse',)
        }),
        ('Featured Image', {
            'fields': ('featured_image_url', 'featured_image_alt'),
            'classes': ('collapse',)
        }),
        ('Publication', {
            'fields': ('status', 'author_name', 'published_at')
        }),
    )


@admin.register(BlogTag)
class BlogTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    filter_horizontal = ['posts']
