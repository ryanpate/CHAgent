# Dashboard & Sidebar Redesign — Design Spec

## Problem

The dashboard is cluttered on mobile — Aria chat dominates 80% of the page, pushing stats and activity below the fold. The mobile sidebar has 14+ items that can't be scrolled, cutting off bottom links (Notifications, Settings, Logout). As the app has grown, users need a better command center to navigate features and see what needs attention.

## Solution: Command Center Dashboard + Grouped Sidebar

Two changes shipped together:
1. **Dashboard** becomes a command center with compact Aria bar, priority cards with notification badges, and an activity feed
2. **Sidebar** gets grouped sections, scroll fix, and badge counts

---

## Dashboard Layout

### Section 1: Ask Aria (compact bar)

Replaces the 400px chat window. Contains:
- Input field with placeholder "Log an interaction or ask a question..."
- Send button (gold)
- Quick action chips below: Log Interaction, This Sunday's Team, Last Setlist, Check Blockouts, Find Volunteer, Prayer Requests
- History and New Conversation buttons (small, top-right of section)

Submitting the form redirects to `/chat/?q=<url-encoded message>`. The chat page detects the `q` parameter, populates the input, and auto-submits via HTMX on load. The dashboard itself does not render chat messages — that's the chat page's job.

**Desktop**: Full-width card at top of content area.
**Mobile**: Full-width, same layout but chips wrap to 2 rows.

### Section 2: Needs Attention (priority cards)

A set of cards, each linking to a feature area. Cards with pending items show:
- SVG icon + title
- Summary text (e.g., "2 due today, 1 overdue")
- Gold circular badge with count
- Gold left-border accent (3px solid)

Cards without pending items show:
- SVG icon + title
- Neutral summary (e.g., "No pending submissions")
- No badge, no left-border accent

Cards with active items sort before cards without. The cards are:

| Card | Links to | Badge source |
|------|----------|-------------|
| Follow-ups | `/followups/` | Pending/overdue follow-ups assigned to current user |
| My Tasks | `/tasks/my/` | In-progress + to-do tasks assigned to current user |
| Team Hub | `/comms/` | Unread DMs + unread channel mentions for current user |
| Song Submissions | `/songs/` | Pending submissions (already tracked via `pending_song_count`) |

**Desktop**: Always a 4-column grid (one per card). If fewer than 4 cards have badges, inactive cards still display — just without the gold accent.
**Mobile**: Vertical stack, full-width cards.

Section label: "NEEDS ATTENTION" — small uppercase text above cards.

### Section 3: Recent Activity

Two sub-sections displayed side-by-side on desktop, stacked on mobile:

**Recent Interactions** (left/top):
- Last 5 interactions with author, time ago, content preview, volunteer tags
- "View all" link to `/interactions/`

**Most Mentioned Volunteers** (right/bottom):
- Top 5 volunteers by interaction count with team label
- "View all" link to `/volunteers/`

Section label: "RECENT ACTIVITY" — small uppercase text.

### Section 4: Quick Stats

Compact row of 3 stat boxes:
- Total Volunteers (count)
- Total Interactions (count)
- This Week (interactions created in last 7 days)

**Desktop**: 3-column row.
**Mobile**: 3-column row (compact).

### Removed from Dashboard

- Full chat message history (400px scrollable area) — now lives at `/chat/`
- Chat form HTMX behavior (beforeend swap into message area)
- Thinking indicator JS (moves to chat page)
- Copy conversation button (moves to chat page)

---

## Chat Page (`/chat/`)

The existing `chat` view currently redirects to dashboard. It becomes its own full page:

- Reuses the current chat UI from `dashboard.html` (message area, form, HTMX, thinking indicator, history modal, copy button, keyboard shortcuts)
- Full-height chat area (not 400px — uses available viewport height)
- Quick action chips below the input
- Welcome message with Aria capabilities when no messages exist

The template is `core/chat.html` (already exists as a simple redirect include — will be expanded to a full template).

Sidebar nav gets a "Chat with Aria" link pointing to `/chat/`.

---

## Sidebar Redesign

### Scroll Fix

Both mobile and desktop sidebars: the `<nav>` element gets `overflow-y: auto` and `flex: 1` so it scrolls when items exceed available height. The footer (user info, Notifications, Settings, Logout) stays pinned at the bottom via flex layout.

### Grouped Sections

Nav items organized into 5 groups with small uppercase section labels (`font-size: 10px; color: #666; text-transform: uppercase; letter-spacing: 1.5px`):

**CORE**
- Dashboard (`/`)
- Chat with Aria (`/chat/`) — new item
- Interactions (`/interactions/`)
- Volunteers (`/volunteers/`)
- Follow-ups (`/followups/`) — badge

**TEAM**
- Team Hub (`/comms/`) — badge
- My Tasks (`/tasks/my/`) — badge
- Song Submissions (`/songs/`) — badge

**CREATIVE**
- Creative Studio (`/studio/`)
- Knowledge Base (`/documents/`)

**INSIGHTS**
- Analytics (`/analytics/`)
- Proactive Care (`/care/`)
- Feedback (`/feedback/`)

**SUPPORT**
- Help (`/guide/`)

Each group is separated by spacing (16px margin-bottom on group container). No horizontal rules — whitespace and labels provide separation.

### Badge Counts in Sidebar

Small gold circular badges (18px diameter) on the right side of nav items with pending counts:
- Follow-ups: same count as dashboard card
- Team Hub: same count as dashboard card
- My Tasks: same count as dashboard card
- Song Submissions: already implemented via `pending_song_count`

---

## Backend Changes

### Context Processor Updates (`core/context_processors.py`)

Add badge counts to the global template context so both dashboard and sidebar can use them:

```python
# New counts added to organization_context():
context['pending_followup_count']  # FollowUp.objects.filter(assigned_to=user, status__in=['pending','in_progress'], organization=org).count()
context['pending_task_count']      # Task.objects.filter(assignees=user, status__in=['todo','in_progress'], organization=org).count()
context['unread_message_count']    # DirectMessage.objects.filter(recipient=user, is_read=False).count() + ChannelMessage.objects.filter(mentioned_users=user, created_at__gte=last_seen).count() — use a simple unread DM count as MVP, channel mentions as stretch
context['interactions_this_week']  # Interaction.objects.filter(organization=org, created_at__gte=week_ago).count()
```

These queries run on every authenticated page load. Keep them lightweight — simple counts with indexed fields. No complex joins.

### Dashboard View Changes (`core/views.py`)

- Remove chat message fetching and session ID cookie logic from `dashboard()`
- Remove `chat_messages` and `session_id` from context
- Add `interactions_this_week` count to context
- Keep: `total_volunteers`, `total_interactions`, `recent_interactions`, `top_volunteers`, `show_onboarding`

### Chat View Changes (`core/views.py`)

- `chat()` becomes a full view (no longer redirects to dashboard)
- Moves all chat logic from `dashboard()`: session ID cookie, chat messages query, HTMX send endpoint
- Template: `core/chat.html` with full chat UI

### URL Changes

No URL changes needed — `/chat/` already exists and routes to the `chat` view. The view behavior changes from redirect to rendering a template.

---

## Template Changes

### `templates/core/dashboard.html`
Complete rewrite — command center layout replacing the chat-heavy page.

### `templates/core/chat.html`
New full template (extends base.html) — receives the chat UI currently in dashboard.html. Includes: message area, form, HTMX handlers, thinking indicator, history modal, copy button, quick actions, keyboard shortcuts.

### `templates/base.html`
Sidebar modifications:
- Add `overflow-y: auto` to mobile sidebar `<nav>` element
- Add `overflow-y: auto` to desktop sidebar `<nav>` element  
- Add section group labels (Core, Team, Creative, Insights, Support)
- Add "Chat with Aria" nav link in Core group
- Add badge count spans to Follow-ups, Team Hub, My Tasks items
- Both mobile and desktop sidebars get identical changes

---

## Design Tokens

All styling uses existing design system values:
- `bg-ch-dark` (#1a1a1a) for cards
- `bg-ch-black` (#0f0f0f) for page background
- `text-ch-gold` (#c9a227) for accents and badges
- `bg-ch-gray` (#2a2a2a) for secondary surfaces
- SVG icons: stroke-based, 16x16 or 20x20, matching existing sidebar icons
- Badge: `bg-ch-gold text-black font-bold text-xs w-5 h-5 rounded-full flex items-center justify-center`
- Section labels: `text-[10px] text-gray-600 uppercase tracking-[1.5px] font-semibold px-3 pb-1.5`

---

## What This Does NOT Change

- No new models or migrations
- No changes to the Aria agent, chat send endpoint, or HTMX chat behavior
- No changes to any page other than dashboard, chat, and base (sidebar)
- No changes to the mobile app (Capacitor) — it loads the same web pages
- Onboarding tour remains on dashboard if `show_onboarding` is true
- Keyboard shortcut (Ctrl+K) still focuses the Aria input — just on dashboard it navigates to /chat/ or focuses the compact bar
