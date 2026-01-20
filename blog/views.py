"""
Blog views for SEO content.
"""
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import F

from .models import BlogPost, BlogCategory, BlogTag


def blog_list(request):
    """List all published blog posts with pagination."""
    posts = BlogPost.objects.filter(
        status='published',
        published_at__lte=timezone.now()
    ).select_related('category').prefetch_related('tags').order_by('-published_at')

    # Pagination - 10 posts per page
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get categories for sidebar
    categories = BlogCategory.objects.all()

    # Get recent posts for sidebar
    recent_posts = posts[:5]

    context = {
        'page_obj': page_obj,
        'categories': categories,
        'recent_posts': recent_posts,
        'meta_title': 'Worship Team Management Blog | Tips & Best Practices | Aria',
        'meta_description': 'Learn best practices for worship team management, volunteer coordination, and church technology. Tips for using Planning Center, building volunteer relationships, and more.',
    }
    return render(request, 'blog/post_list.html', context)


def post_detail(request, slug):
    """Display a single blog post."""
    post = get_object_or_404(
        BlogPost.objects.select_related('category').prefetch_related('tags'),
        slug=slug,
        status='published',
        published_at__lte=timezone.now()
    )

    # Increment view count
    BlogPost.objects.filter(pk=post.pk).update(view_count=F('view_count') + 1)

    # Get related posts from same category
    related_posts = []
    if post.category:
        related_posts = BlogPost.objects.filter(
            category=post.category,
            status='published',
            published_at__lte=timezone.now()
        ).exclude(pk=post.pk).order_by('-published_at')[:3]

    # Get all categories for sidebar
    categories = BlogCategory.objects.all()

    context = {
        'post': post,
        'related_posts': related_posts,
        'categories': categories,
        'meta_title': post.get_meta_title(),
        'meta_description': post.get_meta_description(),
    }
    return render(request, 'blog/post_detail.html', context)


def category_list(request, slug):
    """List posts in a specific category."""
    category = get_object_or_404(BlogCategory, slug=slug)

    posts = BlogPost.objects.filter(
        category=category,
        status='published',
        published_at__lte=timezone.now()
    ).prefetch_related('tags').order_by('-published_at')

    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = BlogCategory.objects.all()

    context = {
        'category': category,
        'page_obj': page_obj,
        'categories': categories,
        'meta_title': f'{category.name} Articles | Aria Blog',
        'meta_description': category.meta_description or f'Articles about {category.name.lower()} for worship teams and churches.',
    }
    return render(request, 'blog/category_list.html', context)


def tag_list(request, slug):
    """List posts with a specific tag."""
    tag = get_object_or_404(BlogTag, slug=slug)

    posts = tag.posts.filter(
        status='published',
        published_at__lte=timezone.now()
    ).prefetch_related('tags').order_by('-published_at')

    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = BlogCategory.objects.all()

    context = {
        'tag': tag,
        'page_obj': page_obj,
        'categories': categories,
        'meta_title': f'Posts Tagged "{tag.name}" | Aria Blog',
        'meta_description': f'Articles tagged with {tag.name} for worship teams and churches.',
    }
    return render(request, 'blog/tag_list.html', context)
