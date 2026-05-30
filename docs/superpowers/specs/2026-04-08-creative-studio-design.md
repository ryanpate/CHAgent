# Creative Studio Design Spec

**Date:** 2026-04-08
**Status:** Approved
**Author:** Ryan Pate + Claude

## Overview

A dedicated creative space within the worship arts portal where team members share original creative work, collaborate on projects, and engage with each other's artistic output. Separate from the operational Comms hub, the Creative Studio is a community-driven space focused on works-in-progress, feedback, encouragement, and co-creation.

## Goals

- Give worship arts teams a space to share original creative work (lyrics, poems, artwork, audio, stage designs, ideas)
- Enable collaboration through feedback, reactions, and "build on this" derivative works
- Keep content discoverable through tags, collections, and type filters without forcing upfront organization
- Allow leaders to spotlight standout work to elevate and encourage the team
- Light Aria integration for tag suggestions, related posts, and collection suggestions -- no AI-generated creative content

## Approach: The Workshop

A hybrid feed + collections model:

- **Main feed** shows all recent posts chronologically with sidebar filters
- **Collections** provide curated groupings (e.g., "Easter 2026", "Songwriting Circle")
- **"Build on this"** links derivative works back to the original, creating visible creative chains
- **Spotlight** lets leaders/admins pin and annotate standout work

## Data Model

### CreativePost

The central content unit.

| Field | Type | Notes |
|-------|------|-------|
| `author` | FK(User) | Post creator |
| `organization` | FK(Organization) | Tenant isolation |
| `post_type` | CharField(choices) | `lyrics`, `poem`, `artwork`, `audio`, `video_concept`, `stage_design`, `idea`, `devotional`, `other` |
| `title` | CharField(200) | Required |
| `content` | TextField | Written content, descriptions, or idea text |
| `media_file` | FileField | Optional -- images, audio files, PDFs |
| `media_type` | CharField(choices) | `image`, `audio`, `document`, `none` |
| `status` | CharField(choices) | `draft`, `published`, `archived` |
| `is_collaborative` | BooleanField | Default False -- "looking for collaborators" flag |
| `is_spotlighted` | BooleanField | Default False |
| `spotlighted_by` | FK(User) | Nullable -- who spotlighted it |
| `spotlight_note` | CharField(200) | Optional leader quote on spotlight |
| `parent_post` | FK(self) | Nullable -- for "build on this" chain |
| `tags` | M2M(CreativeTag) | Lightweight categorization |
| `collection` | FK(CreativeCollection) | Nullable -- optional grouping |
| `embedding_json` | TextField | Nullable -- embedding for related post search |
| `created_at` | DateTimeField | auto_now_add |
| `updated_at` | DateTimeField | auto_now |

### CreativeCollection

Themed groupings for posts.

| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(100) | e.g., "Easter 2026", "Songwriting Circle" |
| `description` | TextField | Blank allowed |
| `organization` | FK(Organization) | Tenant isolation |
| `created_by` | FK(User) | |
| `cover_image` | FileField | Optional collection cover |
| `is_archived` | BooleanField | Default False |
| `created_at` | DateTimeField | auto_now_add |

### CreativeTag

Lightweight post categorization.

| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(50) | |
| `organization` | FK(Organization) | Tenant isolation |
| `slug` | SlugField | For URL filtering |

Unique together: `(name, organization)`

### CreativeComment

Feedback on posts.

| Field | Type | Notes |
|-------|------|-------|
| `post` | FK(CreativePost) | related_name='comments' |
| `author` | FK(User) | |
| `content` | TextField | |
| `parent` | FK(self) | Nullable -- threading |
| `mentioned_users` | M2M(User) | @mention support |
| `created_at` | DateTimeField | auto_now_add |
| `updated_at` | DateTimeField | auto_now |

### CreativeReaction

Emoji reactions on posts.

| Field | Type | Notes |
|-------|------|-------|
| `post` | FK(CreativePost) | related_name='reactions' |
| `user` | FK(User) | |
| `reaction_type` | CharField(choices) | `heart`, `fire`, `pray`, `clap`, `lightbulb`, `star` |

Unique together: `(post, user, reaction_type)` -- one reaction of each type per user per post.

## Navigation & URL Structure

### Sidebar Placement

New top-level nav item: **"Creative Studio"** (or "Studio") with a paintbrush/palette icon. Positioned between "Documents" and "Analytics" in the sidebar.

### URLs

```
/studio/                              # Main feed (all recent posts)
/studio/post/create/                  # Create new post
/studio/post/<id>/                    # Post detail (comments, reactions, build-on chain)
/studio/post/<id>/edit/               # Edit own post
/studio/post/<id>/delete/             # Delete own post
/studio/post/<id>/build-on/           # Create a new post linked to this one
/studio/post/<id>/spotlight/          # Toggle spotlight (admin/leader/owner)
/studio/post/<id>/react/              # Add/remove reaction (HTMX)
/studio/post/<id>/comment/            # Add comment (HTMX)
/studio/collections/                  # Browse all collections
/studio/collections/create/           # Create new collection
/studio/collections/<id>/             # Collection detail (posts within it)
/studio/collections/<id>/edit/        # Edit collection
/studio/collections/<id>/delete/      # Delete collection
/studio/spotlights/                   # View all spotlighted posts
/studio/my-work/                      # Filter to current user's posts
```

### Feed Filtering

The main feed at `/studio/` supports query params:

- `?type=lyrics` -- filter by post type
- `?tag=easter` -- filter by tag slug
- `?collaborative=true` -- show only "looking for collaborators" posts
- `?spotlighted=true` -- show only spotlighted posts

## UI Layout

### Main Feed (`/studio/`)

Card feed with sidebar filters (matches existing app patterns):

- **Left sidebar** contains:
  - Post type filter list (All, Lyrics, Artwork, Audio, Ideas, etc.)
  - Collections list (links to collection detail pages)
  - Tags cloud/list (clickable to filter feed)
  - "My Work" link
  - "Spotlights" link
  - "Looking for Collaborators" link
  - "+ New Post" button

- **Main content area** contains:
  - Chronological feed of post cards
  - Each card shows: author avatar + name, post type badge, title, content preview or media thumbnail, tags, reaction counts, comment count, collaboration flag, build-on count
  - Spotlighted posts get a gold border and star badge
  - Pagination or infinite scroll

### Post Detail (`/studio/post/<id>/`)

Full post view with:

- **Header**: author avatar, name, timestamp, collection link, post type badge, collaboration flag
- **Spotlight banner**: gold left-border with leader's quote (if spotlighted)
- **Content area**: rendered by type -- lyrics/poems in serif italic, images inline, audio with simple player, ideas in standard text
- **Tags**: below content
- **Reaction bar**: emoji buttons with counts + "Build on this" action + "Share" (native share in app mode)
- **Build-on chain**: gold left-bordered section listing derivative works with author, type badge, and preview
- **Comments**: threaded with author avatars, reply button, per-comment reactions, @mention support, file attachment
- **Comment input**: textarea with @mention autocomplete, attach button, post button

### Post Create (`/studio/post/create/`)

Form fields:
- Title (required)
- Post type dropdown
- Content textarea
- Media upload (optional)
- Collection dropdown (optional, includes "None")
- Tags input (type-ahead with existing tags, create new)
- "Looking for collaborators" toggle
- "Save as Draft" and "Publish" buttons

When accessed via "Build on this":
- Title pre-filled with "Re: [original title]"
- `parent_post` set automatically
- Same collection as parent (editable)
- Link back to original post shown at top of form

## Permissions

| Action | Who |
|--------|-----|
| Create posts | All members |
| Comment and react | All members |
| "Build on this" | All members |
| Edit/delete own posts | Post author |
| Toggle collaboration flag | Post author |
| Move post between collections | Post author |
| Spotlight posts | Admin, Owner, Leader |
| Manage collections (create/edit/delete) | Admin, Owner, Leader |
| Delete any post | Admin, Owner |
| View draft posts | Author only |

## Notifications

Integrated with existing push notification system (`core/notifications.py`).

| Event | Recipients | Preference Field |
|-------|-----------|-----------------|
| New post published | All org members | `studio_new_posts` (default True) |
| Comment on your post | Post author | `studio_comments` (default True) |
| Someone builds on your post | Post author | `studio_builds` (default True) |
| @mentioned in a comment | Mentioned user | Uses existing mention notification |
| Post spotlighted | Post author | `studio_spotlights` (default True) |

New fields on `NotificationPreference` model: `studio_new_posts`, `studio_comments`, `studio_builds`, `studio_spotlights` (all BooleanField, default True).

## Aria Integration

Light-touch AI assist -- no AI-generated creative content.

- **Tag suggestions**: When creating/editing a post, Aria analyzes the content and suggests relevant tags from existing org tags or new ones. Implemented as an HTMX endpoint that returns tag suggestions.
- **Related posts**: On post detail view, a "Related in Studio" section at the bottom showing 2-3 posts with similar content/tags. Each `CreativePost` gets an `embedding_json` field (TextField, nullable) populated on publish via OpenAI `text-embedding-3-small` (same as interactions/documents). Cosine similarity search finds related posts within the same organization.
- **Collection suggestions**: When posting, if the post's content is semantically similar to posts in an existing collection (via embedding comparison), suggest adding it to that collection.

## File Upload

Reuses existing `MessageAttachment` validation with extended audio support:

- **Max size**: 10MB
- **Allowed image types**: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`
- **Allowed audio types**: `.mp3`, `.m4a`, `.wav` (new)
- **Allowed document types**: `.pdf`, `.doc`, `.docx`, `.txt`
- Images render inline in post cards and detail view
- Audio gets a simple HTML5 `<audio>` player
- Documents get a download link with file type icon

## Templates

```
templates/core/studio/
  studio_feed.html            # Main feed with sidebar filters
  post_detail.html            # Full post view with comments/reactions/builds
  post_create.html            # Create/edit post form
  post_confirm_delete.html    # Delete confirmation
  collection_list.html        # Browse collections
  collection_detail.html      # Posts within a collection
  collection_create.html      # Create/edit collection form
  collection_confirm_delete.html
  partials/
    post_card.html            # Reusable post card for feed
    comment.html              # Single comment (for HTMX append)
    reaction_bar.html         # Reaction buttons (for HTMX swap)
    build_chain.html          # Build-on chain section
    tag_suggestions.html      # Aria tag suggestions partial
```

## Testing

Tests should cover:

- **Model tests**: CreativePost CRUD, tenant isolation, build-on chain relationships, reaction uniqueness, tag slug generation
- **View tests**: feed filtering, post create/edit/delete permissions, spotlight permissions, collection management, draft visibility
- **Notification tests**: new post, comment, build-on, spotlight, @mention notifications and preference respecting
- **Aria tests**: tag suggestion endpoint, related posts query
- **Template tests**: post type rendering (lyrics vs artwork vs audio), spotlight banner, collaboration badge
