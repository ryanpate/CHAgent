"""Views for the Creative Studio feature."""
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_http_methods, require_POST

from .models import (
    CreativeCollection, CreativeComment, CreativePost, CreativeReaction, CreativeTag,
)

logger = logging.getLogger(__name__)


def get_org(request):
    """Get organization from request (set by TenantMiddleware)."""
    return getattr(request, 'organization', None)


def get_membership(request):
    """Get membership from request (set by TenantMiddleware)."""
    return getattr(request, 'membership', None)


def is_leader_or_above(membership):
    """Check if membership role is leader, admin, or owner."""
    if not membership:
        return False
    return membership.role in ('leader', 'admin', 'owner')


@login_required
def studio_feed(request):
    """Main creative studio feed with sidebar filters."""
    org = get_org(request)
    if not org:
        return redirect('dashboard')

    posts = CreativePost.objects.filter(
        organization=org, status='published',
    ).select_related(
        'author', 'collection', 'parent_post',
    ).prefetch_related('tags', 'reactions', 'comments').annotate(
        comment_count=Count('comments'),
        build_count=Count('builds', filter=Q(builds__status='published')),
    )

    # Apply filters
    post_type = request.GET.get('type')
    if post_type:
        posts = posts.filter(post_type=post_type)

    tag_slug = request.GET.get('tag')
    if tag_slug:
        posts = posts.filter(tags__slug=tag_slug)

    if request.GET.get('collaborative') == 'true':
        posts = posts.filter(is_collaborative=True)

    if request.GET.get('spotlighted') == 'true':
        posts = posts.filter(is_spotlighted=True)

    collections = CreativeCollection.objects.filter(
        organization=org, is_archived=False,
    )
    tags = CreativeTag.objects.filter(organization=org).order_by('name')

    context = {
        'posts': posts[:50],
        'collections': collections,
        'tags': tags,
        'post_type_choices': CreativePost.POST_TYPE_CHOICES,
        'current_type': post_type,
        'current_tag': tag_slug,
        'page_title': 'Creative Studio',
    }
    return render(request, 'core/studio/studio_feed.html', context)


@login_required
def studio_my_work(request):
    """Show current user's posts (including drafts)."""
    org = get_org(request)
    if not org:
        return redirect('dashboard')

    posts = CreativePost.objects.filter(
        organization=org, author=request.user,
    ).exclude(status='archived').select_related(
        'collection', 'parent_post',
    ).prefetch_related('tags', 'reactions', 'comments').annotate(
        comment_count=Count('comments'),
        build_count=Count('builds', filter=Q(builds__status='published')),
    )

    context = {
        'posts': posts,
        'page_title': 'My Work',
        'collections': CreativeCollection.objects.filter(organization=org, is_archived=False),
        'tags': CreativeTag.objects.filter(organization=org).order_by('name'),
        'post_type_choices': CreativePost.POST_TYPE_CHOICES,
    }
    return render(request, 'core/studio/studio_feed.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def studio_post_create(request):
    """Create a new creative post."""
    org = get_org(request)
    if not org:
        return redirect('dashboard')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        post_type = request.POST.get('post_type', 'other')
        content = request.POST.get('content', '')
        status = request.POST.get('status', 'draft')
        collection_id = request.POST.get('collection')
        is_collaborative = request.POST.get('is_collaborative') == 'on'
        parent_id = request.POST.get('parent_post')

        if not title:
            return render(request, 'core/studio/post_create.html', {
                'error': 'Title is required.',
                'collections': CreativeCollection.objects.filter(organization=org, is_archived=False),
                'post_type_choices': CreativePost.POST_TYPE_CHOICES,
            })

        post = CreativePost.objects.create(
            author=request.user,
            organization=org,
            post_type=post_type,
            title=title,
            content=content,
            status=status,
            is_collaborative=is_collaborative,
            collection_id=collection_id if collection_id else None,
            parent_post_id=parent_id if parent_id else None,
        )

        # Handle media upload
        media = request.FILES.get('media_file')
        if media:
            ext = media.name.rsplit('.', 1)[-1].lower() if '.' in media.name else ''
            if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
                post.media_type = 'image'
            elif ext in ('mp3', 'm4a', 'wav'):
                post.media_type = 'audio'
            elif ext in ('pdf', 'doc', 'docx', 'txt'):
                post.media_type = 'document'
            else:
                post.media_type = 'none'
            post.media_file = media
            post.save()

        # Handle tags
        tag_names = request.POST.get('tags', '')
        if tag_names:
            from django.utils.text import slugify
            for tag_name in [t.strip() for t in tag_names.split(',') if t.strip()]:
                tag, _ = CreativeTag.objects.get_or_create(
                    name=tag_name, organization=org,
                    defaults={'slug': slugify(tag_name)},
                )
                post.tags.add(tag)

        # Notify on publish
        if status == 'published':
            try:
                from .notifications import notify_new_studio_post, notify_studio_build
                notify_new_studio_post(post)
                if post.parent_post:
                    notify_studio_build(post)
            except Exception:
                logger.exception("Failed to send studio notifications")

            # Generate embedding for related posts
            if post.content:
                from .embeddings import get_embedding
                import json
                embedding = get_embedding(post.content[:8000])
                if embedding:
                    post.embedding_json = json.dumps(embedding)
                    post.save(update_fields=['embedding_json'])

        return redirect('studio_post_detail', pk=post.pk)

    # GET -- render form
    parent_post = None
    initial_title = ''
    initial_collection = None
    parent_id = request.GET.get('parent')
    if parent_id:
        parent_post = get_object_or_404(
            CreativePost, pk=parent_id, organization=org, status='published',
        )
        initial_title = f'Re: {parent_post.title}'
        initial_collection = parent_post.collection_id

    context = {
        'collections': CreativeCollection.objects.filter(organization=org, is_archived=False),
        'post_type_choices': CreativePost.POST_TYPE_CHOICES,
        'parent_post': parent_post,
        'initial_title': initial_title,
        'initial_collection': initial_collection,
    }
    return render(request, 'core/studio/post_create.html', context)


@login_required
def studio_post_build_on(request, pk):
    """Redirect to create form with parent pre-filled."""
    org = get_org(request)
    parent = get_object_or_404(CreativePost, pk=pk, organization=org, status='published')
    return redirect(f'/studio/post/create/?parent={parent.pk}')


@login_required
def studio_post_detail(request, pk):
    """View a single creative post with comments, reactions, and build chain."""
    org = get_org(request)
    if not org:
        return redirect('dashboard')

    post = CreativePost.objects.filter(
        pk=pk, organization=org,
    ).select_related(
        'author', 'collection', 'parent_post', 'spotlighted_by',
    ).prefetch_related('tags', 'reactions', 'comments__author').first()

    if not post:
        raise Http404

    # Draft visibility: only author can see drafts
    if post.status == 'draft' and post.author != request.user:
        raise Http404

    comments = post.comments.filter(parent__isnull=True).select_related('author').prefetch_related(
        'replies__author', 'mentioned_users',
    )

    builds = CreativePost.objects.filter(
        parent_post=post, status='published',
    ).select_related('author')

    # Build reaction summary
    reaction_summary = {}
    for reaction in post.reactions.all():
        rt = reaction.reaction_type
        if rt not in reaction_summary:
            reaction_summary[rt] = {
                'count': 0,
                'user_reacted': False,
                'emoji': dict(CreativeReaction.REACTION_CHOICES).get(rt, rt),
            }
        reaction_summary[rt]['count'] += 1
        if reaction.user_id == request.user.id:
            reaction_summary[rt]['user_reacted'] = True

    membership = get_membership(request)

    # Related posts via embeddings
    related_posts = []
    if post.embedding_json:
        import json
        try:
            from .embeddings import search_similar_posts
            embedding = json.loads(post.embedding_json)
            related_posts = search_similar_posts(
                embedding, organization=org, exclude_post_id=post.pk, limit=3,
            )
        except (json.JSONDecodeError, TypeError):
            pass

    context = {
        'post': post,
        'comments': comments,
        'builds': builds,
        'reaction_summary': reaction_summary,
        'reaction_choices': CreativeReaction.REACTION_CHOICES,
        'can_spotlight': is_leader_or_above(membership),
        'can_edit': post.author == request.user,
        'can_delete': post.author == request.user or (membership and membership.role in ('admin', 'owner')),
        'related_posts': related_posts,
    }
    return render(request, 'core/studio/post_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def studio_post_edit(request, pk):
    """Edit an existing creative post (author only)."""
    org = get_org(request)
    post = get_object_or_404(CreativePost, pk=pk, organization=org)
    if post.author != request.user:
        return HttpResponseForbidden()

    if request.method == 'POST':
        post.title = request.POST.get('title', post.title).strip()
        post.post_type = request.POST.get('post_type', post.post_type)
        post.content = request.POST.get('content', post.content)
        post.status = request.POST.get('status', post.status)
        post.is_collaborative = request.POST.get('is_collaborative') == 'on'
        collection_id = request.POST.get('collection')
        post.collection_id = collection_id if collection_id else None

        media = request.FILES.get('media_file')
        if media:
            ext = media.name.rsplit('.', 1)[-1].lower() if '.' in media.name else ''
            if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
                post.media_type = 'image'
            elif ext in ('mp3', 'm4a', 'wav'):
                post.media_type = 'audio'
            elif ext in ('pdf', 'doc', 'docx', 'txt'):
                post.media_type = 'document'
            post.media_file = media

        post.save()

        # Update tags
        tag_names = request.POST.get('tags', '')
        post.tags.clear()
        if tag_names:
            from django.utils.text import slugify
            for tag_name in [t.strip() for t in tag_names.split(',') if t.strip()]:
                tag, _ = CreativeTag.objects.get_or_create(
                    name=tag_name, organization=org,
                    defaults={'slug': slugify(tag_name)},
                )
                post.tags.add(tag)

        return redirect('studio_post_detail', pk=post.pk)

    context = {
        'post': post,
        'collections': CreativeCollection.objects.filter(organization=org, is_archived=False),
        'post_type_choices': CreativePost.POST_TYPE_CHOICES,
    }
    return render(request, 'core/studio/post_edit.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def studio_post_delete(request, pk):
    """Delete a creative post (author or admin/owner)."""
    org = get_org(request)
    post = get_object_or_404(CreativePost, pk=pk, organization=org)
    membership = get_membership(request)
    if post.author != request.user and (not membership or membership.role not in ('admin', 'owner')):
        return HttpResponseForbidden()

    if request.method == 'POST':
        post.delete()
        return redirect('studio_feed')

    return render(request, 'core/studio/post_confirm_delete.html', {'post': post})


@login_required
@require_POST
def studio_post_comment(request, pk):
    """Add a comment to a post (HTMX)."""
    org = get_org(request)
    post = get_object_or_404(CreativePost, pk=pk, organization=org, status='published')
    content = request.POST.get('content', '').strip()
    if not content:
        return render(request, 'core/studio/partials/comment.html', {'comment': None})

    comment = CreativeComment.objects.create(
        post=post, author=request.user, content=content,
    )

    from .notifications import notify_studio_comment
    notify_studio_comment(comment)

    return render(request, 'core/studio/partials/comment.html', {'comment': comment})


@login_required
@require_POST
def studio_post_react(request, pk):
    """Toggle a reaction on a post (HTMX)."""
    org = get_org(request)
    post = get_object_or_404(CreativePost, pk=pk, organization=org, status='published')
    reaction_type = request.POST.get('reaction_type')
    if reaction_type not in dict(CreativeReaction.REACTION_CHOICES):
        return HttpResponseBadRequest()

    existing = CreativeReaction.objects.filter(
        post=post, user=request.user, reaction_type=reaction_type,
    )
    if existing.exists():
        existing.delete()
    else:
        CreativeReaction.objects.create(
            post=post, user=request.user, reaction_type=reaction_type,
        )

    # Return updated reaction bar
    reaction_summary = {}
    for reaction in post.reactions.all():
        rt = reaction.reaction_type
        if rt not in reaction_summary:
            reaction_summary[rt] = {'count': 0, 'user_reacted': False, 'emoji': dict(CreativeReaction.REACTION_CHOICES).get(rt, rt)}
        reaction_summary[rt]['count'] += 1
        if reaction.user_id == request.user.id:
            reaction_summary[rt]['user_reacted'] = True

    return render(request, 'core/studio/partials/reaction_bar.html', {
        'post': post,
        'reaction_summary': reaction_summary,
        'reaction_choices': CreativeReaction.REACTION_CHOICES,
    })


@login_required
@require_POST
def studio_post_spotlight(request, pk):
    """Toggle spotlight on a post (leader/admin/owner only)."""
    org = get_org(request)
    membership = get_membership(request)
    if not is_leader_or_above(membership):
        return HttpResponseForbidden()

    post = get_object_or_404(CreativePost, pk=pk, organization=org, status='published')

    if post.is_spotlighted:
        post.is_spotlighted = False
        post.spotlighted_by = None
        post.spotlight_note = ''
    else:
        post.is_spotlighted = True
        post.spotlighted_by = request.user
        post.spotlight_note = request.POST.get('spotlight_note', '')
        from .notifications import notify_studio_spotlight
        notify_studio_spotlight(post)

    post.save()
    return redirect('studio_post_detail', pk=post.pk)


@login_required
def studio_collection_list(request):
    """Browse all collections."""
    org = get_org(request)
    if not org:
        return redirect('dashboard')
    collections = CreativeCollection.objects.filter(
        organization=org, is_archived=False,
    ).annotate(post_count=Count('posts', filter=Q(posts__status='published')))
    membership = get_membership(request)
    context = {
        'collections': collections,
        'can_manage': is_leader_or_above(membership),
    }
    return render(request, 'core/studio/collection_list.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def studio_collection_create(request):
    """Create a new collection (leader/admin/owner only)."""
    org = get_org(request)
    membership = get_membership(request)
    if not is_leader_or_above(membership):
        return HttpResponseForbidden()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '')
        if name:
            CreativeCollection.objects.create(
                name=name, description=description,
                organization=org, created_by=request.user,
            )
            return redirect('studio_collection_list')

    return render(request, 'core/studio/collection_create.html')


@login_required
def studio_collection_detail(request, pk):
    """View posts within a collection."""
    org = get_org(request)
    collection = get_object_or_404(CreativeCollection, pk=pk, organization=org)
    posts = CreativePost.objects.filter(
        collection=collection, status='published',
    ).select_related('author').prefetch_related('tags', 'reactions', 'comments').annotate(
        comment_count=Count('comments'),
        build_count=Count('builds', filter=Q(builds__status='published')),
    )
    membership = get_membership(request)
    context = {
        'collection': collection,
        'posts': posts,
        'can_manage': is_leader_or_above(membership),
        'post_type_choices': CreativePost.POST_TYPE_CHOICES,
    }
    return render(request, 'core/studio/collection_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def studio_collection_edit(request, pk):
    """Edit a collection (leader/admin/owner only)."""
    org = get_org(request)
    membership = get_membership(request)
    if not is_leader_or_above(membership):
        return HttpResponseForbidden()
    collection = get_object_or_404(CreativeCollection, pk=pk, organization=org)

    if request.method == 'POST':
        collection.name = request.POST.get('name', collection.name).strip()
        collection.description = request.POST.get('description', collection.description)
        collection.save()
        return redirect('studio_collection_detail', pk=collection.pk)

    return render(request, 'core/studio/collection_create.html', {'collection': collection})


@login_required
@require_http_methods(["GET", "POST"])
def studio_collection_delete(request, pk):
    """Delete a collection (leader/admin/owner only)."""
    org = get_org(request)
    membership = get_membership(request)
    if not is_leader_or_above(membership):
        return HttpResponseForbidden()
    collection = get_object_or_404(CreativeCollection, pk=pk, organization=org)

    if request.method == 'POST':
        collection.delete()
        return redirect('studio_collection_list')

    return render(request, 'core/studio/collection_confirm_delete.html', {'collection': collection})
