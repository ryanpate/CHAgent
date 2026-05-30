# User Guide Design Spec

**Date:** 2026-04-08
**Status:** Approved
**Author:** Ryan Pate + Claude

## Overview

A comprehensive user guide for the ARIA worship arts platform, accessible both as an in-app page (`/guide/`) and through Aria's Knowledge Base. The guide covers all features for both regular team members and administrators, written in a clear and professional tone.

## Goals

- Give new users a self-serve way to learn every feature of the platform
- Enable Aria to answer "how do I..." questions about the app itself by seeding the guide into each org's Knowledge Base
- Cover both member and admin features in one guide, with admin sections clearly marked
- Structure as a hybrid: Getting Started walkthrough up front, then feature-by-feature reference

## Delivery

### 1. Authenticated Help Page (`/guide/`)

- **URL:** `/guide/`
- **Auth:** `@login_required`
- **Template:** `templates/core/guide.html` extending `base.html`
- **Layout:** Single long-form page with:
  - Sticky left sidebar table of contents (desktop) / collapsible accordion (mobile)
  - Anchored sections with smooth scroll
  - Admin-only sections marked with a gold "Admin" badge and gold left border
  - Admin sections wrapped in `{% if is_admin %}` to hide from non-admin users
  - Example Aria queries in styled callout boxes

### 2. Sidebar Navigation

- Add a "Help" link at the bottom of the sidebar, below the user profile section, near Settings/Logout
- Uses a question-mark-circle Heroicon (outline)
- Present in both mobile and desktop sidebars
- No active state tracking needed (standalone page)

### 3. Knowledge Base Auto-Seeding

- When a new org is created (beta signup or standard onboarding), automatically create a "Getting Started with ARIA" document in the org's Knowledge Base
- Create a "Help & Guides" `DocumentCategory` if it doesn't exist
- Create a `Document` with the guide content as plain text (no HTML)
- Run the existing `process_document()` pipeline to chunk and embed for Aria search
- **Content source:** A `core/guide_content.py` file containing the guide as structured Python constants. The `/guide/` template and the seeder both reference this file (DRY).
- **Existing orgs:** A `seed_guide` management command creates the document for all existing orgs that don't already have it
- **Idempotent:** Seeding skips orgs that already have a document titled "Getting Started with ARIA"

## Content Structure

### Getting Started (Walkthrough)

**1. Welcome to ARIA**
- What the platform does: AI-powered assistant for worship arts teams
- Who it's for: worship leaders, team members, production crews
- What Aria can help with at a high level

**2. Your Dashboard**
- Overview of the main screen layout
- Sidebar navigation explained (each icon and where it goes)
- How to access settings and notifications

**3. Chatting with Aria**
- How to start a conversation
- Types of questions Aria can answer (volunteers, schedules, songs, care)
- Example queries to try
- How to give feedback on responses (thumbs up/down)
- Starting a new conversation session

**4. Logging Your First Interaction**
- What interactions are and why they matter
- Step-by-step: navigate to Interactions > Create
- What Aria extracts automatically (hobbies, family, prayer requests)
- How interactions connect to volunteer profiles

### Feature Reference

**5. Aria (AI Assistant)**
- Volunteer info queries (contact, personal details, service history)
- Team roster queries (by team name)
- Schedule queries (who's serving, team contact info)
- Song & setlist queries (history, lyrics, chord charts, BPM)
- Blockout & availability queries
- Aggregate insights (prayer requests, birthdays, team summaries)
- Knowledge Base queries (how-to, procedures, reference docs)
- Tips: use full names, add "the song" for song queries, date formats Aria understands
- Feedback: how positive/negative feedback improves responses

**6. Interactions**
- Browsing the interaction list (search, filter by volunteer)
- Viewing interaction details (AI summary, extracted data, linked volunteers)
- Creating new interactions
- How interactions feed into Aria's knowledge

**7. Volunteers**
- Browsing the volunteer list
- Volunteer detail page (contact info, interaction history, extracted knowledge)
- Planning Center sync: how volunteer profiles connect to PCO
- Matching volunteers to PCO records

**8. Follow-ups**
- What follow-ups are (action items, prayer requests, reminders)
- Creating follow-ups (from scratch or from interactions)
- Categories: prayer request, concern, action item, feedback
- Priority levels and status workflow (pending > in progress > completed)
- Setting follow-up dates and reminders
- Completing and adding completion notes

**9. Team Hub**
- Announcements: viewing, creating (Admin), priority levels, pinning
- Channels: joining, posting, threading, @mentions, file attachments
- Direct Messages: sending, read status, conversations
- Overview of the hub dashboard

**10. Projects & Tasks**
- Creating projects with status, priority, dates
- Task boards: To Do, In Progress, In Review, Completed
- Creating tasks (in projects or standalone via My Tasks)
- Subtasks and checklists
- Assigning team members
- Task comments with @mentions and file attachments
- Marking decisions in comments
- Watching tasks for notifications
- Recurring tasks and project templates
- My Tasks view: personal task list across all projects

**11. Creative Studio**
- What it's for: sharing creative work, collaboration, inspiration
- Creating a post: choosing type, adding content/media, tags, collections
- Post types: lyrics, poem, artwork, audio, video concept, stage design, idea, devotional
- Reactions: heart, fire, pray, clap, lightbulb, star
- Commenting on posts
- "Build on this": creating derivative works linked to the original
- Collaboration flag: marking posts as open for collaborators
- Collections: browsing and organizing by theme (e.g., "Easter 2026")
- Spotlights: how leaders highlight standout work (Admin/Leader)
- My Work: viewing your own posts including drafts
- Filtering: by type, tag, collaborative, spotlighted

**12. Song Submissions**
- Suggesting a new song for the team
- Viewing submission status
- Voting on submissions (if enabled)

**13. Analytics**
- Dashboard overview: key metrics at a glance
- Volunteer engagement: activity and participation
- Team care: follow-ups, prayer requests
- Interaction trends: patterns over time
- Prayer request analytics
- AI performance: response quality metrics
- Exporting reports as CSV

**14. Proactive Care**
- What care insights are: AI-identified volunteers who may need attention
- Insight types: missing/inactive, declining engagement, prayer follow-up, celebration, concern
- Reviewing and dismissing insights
- Creating follow-ups from insights

**15. Knowledge Base**
- What it's for: upload documents so Aria can reference them
- Supported file types: PDF, TXT, PNG, JPG, JPEG
- How uploads work: text extraction, chunking, embedding
- Images in PDFs: automatic extraction and AI description
- Organizing with categories
- How Aria cites documents in answers
- Best practices: what to upload (procedures, checklists, reference guides)

**16. Notifications**
- Enabling push notifications
- Notification types: announcements, DMs, channel mentions, care alerts, follow-up reminders, task assignments, studio posts/comments/builds/spotlights
- Per-type toggles
- Quiet hours
- Managing devices

### Admin Sections (marked with gold "Admin" badge)

**17. Organization Settings**
- General settings: org name, AI assistant name, primary color
- Viewing org status and plan

**18. Managing Members**
- Inviting new members (email invitations)
- Roles explained: Owner, Admin, Leader, Member, Viewer
- Role permissions breakdown (what each role can/can't do)
- Changing roles
- Removing members

**19. Billing**
- Subscription plans: Starter, Team, Ministry, Enterprise
- Managing billing via Stripe portal
- Changing plans
- Beta status (free during beta)

**20. Security**
- Enabling two-factor authentication (TOTP)
- Setting up an authenticator app
- Backup codes: what they are, how to use them
- Disabling 2FA

**21. Planning Center Integration**
- Connecting your PCO account
- Per-organization credentials
- What data syncs from PCO (people, schedules, songs, blockouts)
- Troubleshooting common PCO issues

## View

```python
@login_required
def user_guide(request):
    org = getattr(request, 'organization', None)
    membership = getattr(request, 'membership', None)
    is_admin = membership and membership.role in ('owner', 'admin') if membership else False
    context = {
        'is_admin': is_admin,
        'page_title': 'User Guide',
    }
    return render(request, 'core/guide.html', context)
```

## URL

```python
path('guide/', views.user_guide, name='user_guide'),
```

## Content Source File

`core/guide_content.py` -- contains the guide content as a list of section dicts:

```python
GUIDE_SECTIONS = [
    {
        'id': 'welcome',            # anchor ID
        'title': 'Welcome to ARIA',
        'content': '...',           # HTML content for the /guide/ page
        'plain_text': '...',        # Plain text version for Knowledge Base seeding
        'is_admin': False,          # True = only shown to admin/owner
        'group': 'getting-started', # For TOC grouping
    },
    ...
]

GUIDE_GROUPS = [
    {'id': 'getting-started', 'title': 'Getting Started'},
    {'id': 'features', 'title': 'Features'},
    {'id': 'admin', 'title': 'Administration'},
]
```

Used by:
- `templates/core/guide.html` -- iterates sections, renders HTML content with styling
- `core/guide_seeder.py` -- concatenates `plain_text` fields for Knowledge Base document

## Auto-Seeding

`core/guide_seeder.py`:

```python
def seed_guide_document(organization):
    """Create or update the Getting Started guide in an org's Knowledge Base."""
    # 1. Get or create "Help & Guides" category
    # 2. Check if "Getting Started with ARIA" document exists (skip if so)
    # 3. Create Document with plain text guide content
    # 4. Run process_document() to chunk and embed
```

**Hook into:**
- `views.beta_signup` -- after org creation
- `views.onboarding_create_org` (or equivalent) -- after org creation

**Management command:** `core/management/commands/seed_guide.py`
- Iterates all active organizations
- Calls `seed_guide_document(org)` for each
- Reports: created/skipped/total

## Templates

```
templates/core/guide.html           # Full guide page with TOC sidebar
```

## Testing

- `test_guide_page_renders` -- GET `/guide/` returns 200 for authenticated user
- `test_guide_admin_sections_visible_for_owner` -- admin content present for owner role
- `test_guide_admin_sections_hidden_for_member` -- admin content absent for member role
- `test_seed_guide_document_creates_document` -- seeder creates Document + chunks
- `test_seed_guide_document_idempotent` -- running twice doesn't duplicate
- `test_seed_guide_creates_category` -- "Help & Guides" category created
- `test_guide_in_sidebar` -- `/guide/` page contains "Help" nav link
