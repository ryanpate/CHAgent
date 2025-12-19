# Cherry Hills Worship Arts Team Portal

## Project Status

**🎯 Overall Completion: ~85%** | **📊 Production-Ready Core Features** | **🚀 Active Development**

Last Updated: December 19, 2025

### Quick Stats
- **28 Database Models** across all domains
- **98 View Functions** with full CRUD operations
- **50+ Templates** for complete user journeys
- **7 Test Files** with comprehensive coverage
- **20+ Migrations** tracking schema evolution
- **Recent Focus**: PCO API optimization, query detection improvements, chat UX enhancements

### Current Sprint (December 2025)
- ✅ Improved PCO API rate limiting with caching
- ✅ Added thinking indicator for chat responses
- ✅ Enhanced blockout query patterns with date range support
- ✅ Comprehensive Aria query detection testing
- 🔄 Email notification system (in progress)
- 📋 Platform admin dashboard (planned)

---

## Project Overview

A **multi-tenant SaaS platform** for worship arts teams featuring **Aria**, an AI assistant powered by Claude that helps team members manage volunteer relationships, access Planning Center data, and track follow-up items.

Originally built for Cherry Hills Church, the platform is now designed to be offered as a paid service to other churches and worship arts teams.

### Core Purpose
- **AI Assistant (Aria)**: Ask questions about volunteers, schedules, songs, and team information
- **Planning Center Integration**: Direct access to PCO data for people, schedules, songs, chord charts, and lyrics
- **Volunteer Care**: Log interactions and track personal details to better care for volunteers
- **Follow-up Management**: Track action items, prayer requests, and reminders
- **Learning System**: Aria learns from feedback to improve responses over time
- **Multi-Tenant Architecture**: Each church/organization gets isolated data and settings

---

## Multi-Tenant SaaS Architecture

The platform supports multiple churches/organizations with complete data isolation.

### Subscription Plans

| Plan | Monthly | Yearly | Users | Volunteers | Key Features |
|------|---------|--------|-------|------------|--------------|
| **Starter** | $9.99/mo | $100/yr | 5 | 50 | PCO Integration, Push Notifications |
| **Team** | $39.99/mo | $400/yr | 15 | 200 | + Analytics, Care Insights |
| **Ministry** | $79.99/mo | $800/yr | Unlimited | Unlimited | + API Access, Custom Branding |
| **Enterprise** | Contact | Contact | Unlimited | Unlimited | + Multi-campus, Priority Support |

### Organization Model

```python
# core/models.py
class Organization(models.Model):
    """Central tenant model - all data is scoped to an organization."""
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)  # URL identifier

    # Subscription
    subscription_plan = models.ForeignKey(SubscriptionPlan)
    subscription_status = models.CharField()  # trial, active, past_due, cancelled
    trial_ends_at = models.DateTimeField()

    # Per-org Planning Center credentials
    planning_center_app_id = models.CharField()
    planning_center_secret = models.CharField()

    # Stripe billing
    stripe_customer_id = models.CharField()
    stripe_subscription_id = models.CharField()

    # Customization
    ai_assistant_name = models.CharField(default='Aria')
    primary_color = models.CharField(default='#6366f1')

    # Usage tracking
    ai_queries_this_month = models.IntegerField()
```

### Organization Membership

```python
class OrganizationMembership(models.Model):
    """Links users to organizations with role-based permissions."""
    ROLE_CHOICES = [
        ('owner', 'Owner'),        # Full control, billing
        ('admin', 'Admin'),        # Manage users, settings
        ('leader', 'Team Leader'), # Manage volunteers, analytics
        ('member', 'Member'),      # Basic access
        ('viewer', 'Viewer'),      # Read-only
    ]

    user = models.ForeignKey(User)
    organization = models.ForeignKey(Organization)
    role = models.CharField(choices=ROLE_CHOICES)

    # Granular permissions
    can_manage_users = models.BooleanField()
    can_manage_settings = models.BooleanField()
    can_view_analytics = models.BooleanField()
    can_manage_billing = models.BooleanField()
```

### Tenant Middleware

The `TenantMiddleware` (`core/middleware.py`) automatically injects organization context:

```python
# In any view, access via request:
request.organization  # Current Organization object
request.membership    # User's OrganizationMembership

# Use decorators for permission checks:
@require_organization
@require_role('admin', 'owner')
def manage_settings(request):
    ...

@require_permission('can_manage_users')
def invite_member(request):
    ...
```

### Data Isolation

All tenant-scoped models have an `organization` foreign key:
- Volunteer, Interaction, ChatMessage, FollowUp
- Announcement, Channel, Project, Task
- ResponseFeedback, ExtractedKnowledge, etc.

**Important**: All queries must filter by organization:
```python
# Correct - scoped to organization
volunteers = Volunteer.objects.filter(organization=request.organization)

# Wrong - would return all organizations' data
volunteers = Volunteer.objects.all()
```

### Key Files for Multi-Tenancy

| File | Purpose |
|------|---------|
| `core/models.py` | Organization, SubscriptionPlan, OrganizationMembership |
| `core/middleware.py` | TenantMiddleware, decorators, mixins |
| `core/context_processors.py` | Template context for organization |
| `accounts/models.py` | User with organization helpers |

---

## Environment Variables

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your-app.railway.app

# Database (Railway provides automatically)
DATABASE_URL=postgres://...

# AI APIs
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...  # For embeddings

# Planning Center (now per-organization, legacy support)
PLANNING_CENTER_APP_ID=your-app-id
PLANNING_CENTER_SECRET=your-secret

# Stripe Billing
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER_MONTHLY=price_...
STRIPE_PRICE_STARTER_YEARLY=price_...
STRIPE_PRICE_TEAM_MONTHLY=price_...
STRIPE_PRICE_TEAM_YEARLY=price_...
STRIPE_PRICE_MINISTRY_MONTHLY=price_...
STRIPE_PRICE_MINISTRY_YEARLY=price_...

# Multi-Tenant Settings
TRIAL_PERIOD_DAYS=14
DEFAULT_AI_ASSISTANT_NAME=Aria
APP_DOMAIN=aria.church
USE_SUBDOMAIN_ROUTING=true

# Web Push Notifications (VAPID keys)
VAPID_PUBLIC_KEY=your-public-key
VAPID_PRIVATE_KEY=your-private-key
VAPID_CLAIMS_EMAIL=mailto:your-email@example.com
```

---

## Aria's Capabilities

Aria is the AI assistant that powers the chat interface. She can handle many types of queries:

### Volunteer Information
- **Contact Info**: "What's John Smith's email?" / "How can I reach Sarah?"
- **Personal Details**: "What are Mike's hobbies?" / "Does Lisa have kids?"
- **Service History**: "When does Emma play next?" / "When did David last serve?"
- **Availability**: "Is John blocked out on December 14th?" / "Who's available next Sunday?"

### Planning Center Schedule Queries
- **Team Schedules**: "Who's on the team this Sunday?" / "Who served on Easter?"
- **Blockouts**: "Who's blocked out on December 14th?" / "What are Sarah's blockout dates?"
- **Service Types**: Defaults to "Cherry Hills Morning Main", supports HSM/MSM with keywords

### Song & Setlist Queries
- **Setlists**: "What songs did we play last Sunday?" / "Easter setlist"
- **Song History**: "When did we last play Gratitude?" / "How often do we play Oceans?"
- **Lyrics**: "Show me the lyrics for Amazing Grace" / "What's the chorus of Way Maker?"
- **Chord Charts**: "Chord chart for Goodness of God" / "Lead sheet for Great Are You Lord"
- **Song Info**: "What key is Holy Spirit in?" / "BPM for Build My Life"

### Interaction Logging
- **Log Interactions**: "Log interaction: Talked with Sarah after service. She mentioned her daughter is starting school."
- **Auto-extraction**: Aria extracts hobbies, family info, prayer requests, and follow-up items

### Aggregate Insights
- "What are the most common prayer requests?"
- "Which volunteers have birthdays this month?"
- "Team summary for November"

### Smart Disambiguation
When queries are ambiguous, Aria asks for clarification:
- **Song vs Person**: "When did we last play Gratitude?" → Asks if you mean the song or a person
- **First Name Only**: "When does Emma play?" → Shows list of all Emmas to choose from

---

## Technical Stack

| Component | Technology |
|-----------|------------|
| **Framework** | Django 5.x |
| **Database** | PostgreSQL 15+ with pgvector |
| **AI Provider** | Anthropic Claude API (claude-sonnet-4-20250514) |
| **Vector Embeddings** | OpenAI text-embedding-3-small |
| **Frontend** | Django Templates + HTMX + Tailwind CSS |
| **Deployment** | Railway |

---

## Database Models

### Core Models

```python
# Volunteer - Profiles linked to Planning Center
Volunteer:
    name: CharField
    normalized_name: CharField (indexed, for matching)
    team: CharField (vocals, band, tech, etc.)
    planning_center_id: CharField (unique, links to PCO)

# Interaction - Append-only log of volunteer interactions
Interaction:
    user: ForeignKey (who logged it)
    content: TextField (free-form notes)
    volunteers: ManyToMany (auto-linked by AI)
    ai_summary: TextField
    ai_extracted_data: JSONField (hobbies, preferences, etc.)
    embedding_json: TextField (for semantic search)

# ChatMessage - Conversation history
ChatMessage:
    user: ForeignKey
    session_id: CharField (groups conversation)
    role: CharField (user/assistant)
    content: TextField
```

### Context & State Models

```python
# ConversationContext - Tracks conversation state per session
ConversationContext:
    session_id: CharField (unique)
    shown_interaction_ids: JSONField (deduplication)
    discussed_volunteer_ids: JSONField (context tracking)
    conversation_summary: TextField (for long conversations)
    current_topic: CharField
    message_count: IntegerField
    pending_song_suggestions: JSONField (song selection)
    current_song: JSONField (follow-up context)
    pending_date_lookup: JSONField (date confirmation)
    pending_followup: JSONField (follow-up creation)
    pending_disambiguation: JSONField (song vs person)
```

### Follow-up System

```python
# FollowUp - Action items and reminders
FollowUp:
    created_by: ForeignKey
    assigned_to: ForeignKey
    volunteer: ForeignKey (optional)
    title: CharField
    description: TextField
    category: CharField (prayer_request, concern, action_item, feedback)
    priority: CharField (low, medium, high, urgent)
    status: CharField (pending, in_progress, completed, cancelled)
    follow_up_date: DateField
    reminder_sent: BooleanField
    completed_at: DateTimeField
    completion_notes: TextField
    source_interaction: ForeignKey (optional)
```

### Learning System

```python
# ResponseFeedback - Tracks AI response quality
ResponseFeedback:
    chat_message: OneToOneField
    feedback_type: CharField (positive/negative)
    issue_type: CharField (missing_info, wrong_info, wrong_volunteer, etc.)
    expected_result: TextField
    comment: TextField
    query_type: CharField (volunteer_info, setlist, lyrics, etc.)
    resolved: BooleanField
    resolved_by: ForeignKey
    resolution_notes: TextField

# LearnedCorrection - Spelling/fact corrections
LearnedCorrection:
    incorrect_value: CharField
    correct_value: CharField
    correction_type: CharField (spelling, fact, preference, context)
    volunteer: ForeignKey (optional)
    times_applied: IntegerField
    is_active: BooleanField

# ExtractedKnowledge - Structured volunteer facts
ExtractedKnowledge:
    volunteer: ForeignKey
    knowledge_type: CharField (hobby, family, preference, birthday, etc.)
    key: CharField (e.g., "favorite_food")
    value: TextField
    confidence: CharField (high, medium, low)
    source_interaction: ForeignKey
    is_verified: BooleanField
    is_current: BooleanField
```

---

## Planning Center Integration

### PlanningCenterAPI (People)
```python
# Search and retrieve people
get_people(team_id, use_cache)        # All people with caching
search_people(query)                   # Search by name
get_person_details(person_id)          # Full details with emails, phones
search_person_with_suggestions(name)   # Returns match or suggestions
search_by_first_name(first_name)       # For disambiguation
find_matches(name, threshold)          # Fuzzy matching
```

### PlanningCenterServicesAPI (Services & Songs)
```python
# Service Plans
get_service_types()                    # All service types
get_plans(service_type_id, future_only, past_only)
find_plan_by_date(date_str, service_type)
get_plan_with_team(date_str)           # Full team assignments
get_plan_details(service_type_id, plan_id)  # Songs, items

# Songs
search_songs(query)                    # Search by title/author
get_song_details(song_id)              # Individual song
get_song_usage_history(song_title)     # When song was played
get_song_with_attachments(song_title)  # Chord charts, lyrics

# Blockouts & Availability
get_person_blockouts(name, date_range)
get_blockouts_for_date(date)           # Who's blocked on date
check_person_availability(name, date)
get_team_availability_for_date(date)
```

### Service Type Configuration
```python
DEFAULT_SERVICE_TYPE_NAME = 'Cherry Hills Morning Main'
YOUTH_SERVICE_KEYWORDS = ['hsm', 'msm', 'high school', 'middle school']
```

| Query | Service Type |
|-------|--------------|
| "Who's on team Sunday?" | Cherry Hills Morning Main |
| "HSM team this week" | High School Ministry |
| "MSM setlist" | Middle School Ministry |

```
worship-arts-portal/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/
│   ├── __init__.py
│   ├── admin.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
├── core/
│   ├── __init__.py
│   ├── admin.py
│   ├── agent.py           # AI Agent logic
│   ├── embeddings.py      # Vector embedding functions
│   ├── models.py          # All models (see below)
│   ├── notifications.py   # Push notification service
│   ├── planning_center.py # Planning Center API integration
│   ├── urls.py
│   └── views.py
├── templates/
│   ├── base.html
│   ├── accounts/
│   │   └── login.html
│   └── core/
│       ├── dashboard.html
│       ├── chat.html
│       ├── chat_message.html
│       ├── interaction_list.html
│       ├── interaction_detail.html
│       ├── volunteer_list.html
│       ├── volunteer_detail.html
│       ├── followup_list.html
│       ├── followup_detail.html
│       ├── care_dashboard.html
│       ├── push_preferences.html
│       ├── analytics/
│       │   ├── dashboard.html
│       │   ├── engagement.html
│       │   ├── care.html
│       │   ├── trends.html
│       │   ├── prayer.html
│       │   └── ai.html
│       ├── comms/
│       │   ├── hub.html
│       │   ├── announcements_list.html
│       │   ├── announcement_detail.html
│       │   ├── announcement_create.html
│       │   ├── channel_list.html
│       │   ├── channel_detail.html
│       │   ├── channel_create.html
│       │   ├── dm_list.html
│       │   ├── dm_conversation.html
│       │   ├── project_list.html
│       │   ├── project_detail.html
│       │   ├── project_create.html
│       │   └── task_detail.html
│       └── partials/
│           ├── task_card.html
│           └── task_comment.html
├── static/
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   └── sw.js          # Service Worker for PWA
│   └── icons/
│       ├── icon-192x192.png
│       └── badge-72x72.png
├── requirements.txt
├── Procfile
├── railway.toml
├── manage.py
└── .env.example
```
### Date Parsing
Aria understands many date formats:
- **Relative**: "last Sunday", "this Sunday", "next Sunday", "yesterday", "today"
- **Holidays**: "Easter", "last Easter", "Christmas Eve", "Thanksgiving"
- **Specific**: "November 16", "11/16/2025", "2025-11-16"

### Core Models Summary

| Model | Purpose |
|-------|---------|
| `Volunteer` | Volunteer profiles with Planning Center integration |
| `Interaction` | Logged interactions with volunteers |
| `ChatMessage` | AI chat conversation history |
| `FollowUp` | Follow-up tasks for volunteers |
| `ChatFeedback` | User feedback on AI responses |
| `ReportCache` | Cached analytics reports |
| `VolunteerInsight` | AI-generated care insights |
| `Announcement` | Team announcements |
| `Channel` | Discussion channels |
| `ChannelMessage` | Channel messages with @mentions |
| `DirectMessage` | Private messages |
| `Project` | Team projects |
| `Task` | Project tasks |
| `TaskComment` | Task comments with @mentions |
| `PushSubscription` | Push notification subscriptions |
| `NotificationPreference` | User notification settings |
| `NotificationLog` | Notification delivery log |

---

## Query Detection

The agent detects query types using pattern matching:

### `is_pco_data_query(message)`
Detects: contact, email, phone, address, birthday, anniversary, teams, service_history

### `is_song_or_setlist_query(message)`
Detects: team_schedule, song_history, setlist, chord_chart, lyrics, song_search, song_info

### `is_blockout_query(message)`
Detects: person_blockouts, date_blockouts, availability_check, team_availability

### `is_aggregate_question(message)`
Detects: team-wide queries about food, hobbies, prayer, family, birthday, availability, feedback

### `check_ambiguous_song_or_person(message)`
Detects: queries like "when did we play Gratitude" that could be song or person

# Optional: Planning Center Integration
PLANNING_CENTER_APP_ID=
PLANNING_CENTER_SECRET=

# Web Push Notifications (VAPID keys)
# Generate with: npx web-push generate-vapid-keys
VAPID_PUBLIC_KEY=your-public-key-here
VAPID_PRIVATE_KEY=your-private-key-here
VAPID_CLAIMS_EMAIL=mailto:your-email@example.com
```
---

## URL Structure

```python
# Dashboard & Chat
path('', views.dashboard, name='dashboard')
path('chat/', views.chat, name='chat')
path('chat/send/', views.chat_send, name='chat_send')
path('chat/new/', views.chat_new_session, name='chat_new_session')
path('chat/feedback/', views.chat_feedback, name='chat_feedback')
path('chat/feedback/submit/', views.chat_feedback_submit, name='chat_feedback_submit')

# Interactions
path('interactions/', views.interaction_list, name='interaction_list')
path('interactions/<int:pk>/', views.interaction_detail, name='interaction_detail')
path('interactions/create/', views.interaction_create, name='interaction_create')

# Volunteers
path('volunteers/', views.volunteer_list, name='volunteer_list')
path('volunteers/<int:pk>/', views.volunteer_detail, name='volunteer_detail')
path('volunteers/match/<int:pk>/confirm/', views.volunteer_match_confirm)
path('volunteers/match/<int:pk>/create/', views.volunteer_match_create)
path('volunteers/match/<int:pk>/skip/', views.volunteer_match_skip)

# Follow-ups
path('followups/', views.followup_list, name='followup_list')
path('followups/<int:pk>/', views.followup_detail, name='followup_detail')
path('followups/create/', views.followup_create, name='followup_create')
path('followups/<int:pk>/complete/', views.followup_complete)
path('followups/<int:pk>/update/', views.followup_update)
path('followups/<int:pk>/delete/', views.followup_delete)

# Feedback Dashboard
path('feedback/', views.feedback_dashboard, name='feedback_dashboard')
path('feedback/<int:pk>/resolve/', views.feedback_resolve)
```

---

## Environment Variables

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your-app.railway.app

# Database (Railway provides automatically)
DATABASE_URL=postgres://...

# AI APIs
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...  # For embeddings

# Planning Center
PLANNING_CENTER_APP_ID=your-app-id
PLANNING_CENTER_SECRET=your-secret
```

---

## Key Files

```
CHAgent/
├── CLAUDE.md                 # Project documentation (this file)
├── SKILL.md                  # Development patterns & workflows for Claude Code
├── core/
│   ├── agent.py              # AI agent logic, query detection, RAG
│   ├── planning_center.py    # PCO API integration
│   ├── models.py             # Database models (incl. Organization, SubscriptionPlan)
│   ├── views.py              # View handlers
│   ├── urls.py               # URL routing
│   ├── embeddings.py         # Vector search
│   ├── middleware.py         # TenantMiddleware, permission decorators
│   ├── context_processors.py # Organization template context
│   ├── notifications.py      # Push notification service
│   └── volunteer_matching.py # Name matching logic
├── templates/
│   ├── base.html             # Layout with sidebar
│   └── core/
│       ├── dashboard.html    # Main chat interface
│       ├── interaction_*.html
│       ├── volunteer_*.html
│       ├── followup_*.html
│       └── feedback_*.html
├── config/
│   ├── settings.py           # Incl. Stripe & multi-tenant config
│   └── urls.py
└── accounts/
    └── models.py             # Custom User with org helpers
```

> **Note**: See `SKILL.md` for detailed development patterns including multi-tenant coding, adding AI query types, and common workflows.

---

## Analytics and Reporting Dashboard

The analytics dashboard provides comprehensive insights into team activities, volunteer engagement, and AI performance.

### Features

- **Overview Dashboard**: Key metrics and trends at a glance
- **Volunteer Engagement**: Track volunteer activity and participation rates
- **Team Care Metrics**: Monitor follow-ups, prayer requests, and care activities
- **Interaction Trends**: Visualize interaction patterns over time
- **Prayer Request Analytics**: Aggregate prayer request data and trends
- **AI Performance**: Monitor AI response quality and feedback

### URL Routes

```python
# Analytics endpoints
path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
path('analytics/engagement/', views.analytics_volunteer_engagement, name='analytics_volunteer_engagement'),
path('analytics/care/', views.analytics_team_care, name='analytics_team_care'),
path('analytics/trends/', views.analytics_interaction_trends, name='analytics_interaction_trends'),
path('analytics/prayer/', views.analytics_prayer_requests, name='analytics_prayer_requests'),
path('analytics/ai/', views.analytics_ai_performance, name='analytics_ai_performance'),
path('analytics/export/<str:report_type>/', views.analytics_export, name='analytics_export'),
path('analytics/refresh/', views.analytics_refresh_cache, name='analytics_refresh_cache'),
```

### Report Caching

Reports are cached using the `ReportCache` model for performance:
- Cached reports are refreshed on demand or periodically
- Export functionality supports CSV format

---

## Proactive Care Dashboard

AI-powered volunteer care system that identifies volunteers who may need attention.

### VolunteerInsight Model

```python
class VolunteerInsight(models.Model):
    """
    AI-generated insights about volunteers who may need attention.
    """
    INSIGHT_TYPES = [
        ('missing', 'Missing/Inactive'),
        ('declining', 'Declining Engagement'),
        ('prayer', 'Prayer Request Follow-up'),
        ('celebration', 'Celebration/Milestone'),
        ('concern', 'General Concern'),
    ]

    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    volunteer = models.ForeignKey(Volunteer, on_delete=models.CASCADE)
    insight_type = models.CharField(max_length=20, choices=INSIGHT_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS)
    title = models.CharField(max_length=200)
    description = models.TextField()
    suggested_actions = models.JSONField(default=list)
    is_dismissed = models.BooleanField(default=False)
    followup_created = models.BooleanField(default=False)
```

### URL Routes

```python
# Proactive Care Dashboard
path('care/', views.care_dashboard, name='care_dashboard'),
path('care/dismiss/<int:pk>/', views.care_dismiss_insight, name='care_dismiss_insight'),
path('care/followup/<int:pk>/', views.care_create_followup, name='care_create_followup'),
path('care/refresh/', views.care_refresh_insights, name='care_refresh_insights'),
```

---

## Team Communication Hub

Internal communication system for the worship arts team with announcements, channels, and direct messages.

### Models

#### Announcement
Team-wide announcements with priority levels and scheduling.

```python
class Announcement(models.Model):
    PRIORITY_CHOICES = [
        ('normal', 'Normal'),
        ('important', 'Important'),
        ('urgent', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    is_pinned = models.BooleanField(default=False)
    publish_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
```

#### Channel
Team discussion channels (public or private).

```python
class Channel(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_private = models.BooleanField(default=False)
    members = models.ManyToManyField(User, blank=True, related_name='channel_memberships')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
```

#### ChannelMessage
Messages within channels with @mention support.

```python
class ChannelMessage(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    mentioned_users = models.ManyToManyField(User, blank=True, related_name='channel_mentions_received')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)  # For threads
```

#### DirectMessage
Private messages between team members.

```python
class DirectMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
```

### URL Routes

```python
# Team Communication Hub
path('comms/', views.comms_hub, name='comms_hub'),
path('comms/announcements/', views.announcements_list, name='announcements_list'),
path('comms/announcements/<int:pk>/', views.announcement_detail, name='announcement_detail'),
path('comms/announcements/new/', views.announcement_create, name='announcement_create'),
path('comms/channels/', views.channel_list, name='channel_list'),
path('comms/channels/new/', views.channel_create, name='channel_create'),
path('comms/channels/<slug:slug>/', views.channel_detail, name='channel_detail'),
path('comms/channels/<slug:slug>/send/', views.channel_send_message, name='channel_send_message'),
path('comms/messages/', views.dm_list, name='dm_list'),
path('comms/messages/new/', views.dm_new, name='dm_new'),
path('comms/messages/<int:user_id>/', views.dm_conversation, name='dm_conversation'),
path('comms/messages/<int:user_id>/send/', views.dm_send, name='dm_send'),
```

---

## Project and Task Management

Kanban-style project and task management for team coordination.

### Models

#### Project
```python
class Project(models.Model):
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_projects')
    members = models.ManyToManyField(User, blank=True, related_name='projects')
    channel = models.OneToOneField(Channel, on_delete=models.SET_NULL, null=True, blank=True)  # Optional linked channel
```

#### Task
```python
class Task(models.Model):
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('review', 'In Review'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    assignees = models.ManyToManyField(User, blank=True, related_name='assigned_tasks')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    due_date = models.DateField(null=True, blank=True)
    due_time = models.TimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
```

#### TaskComment
```python
class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    mentioned_users = models.ManyToManyField(User, blank=True, related_name='task_comment_mentions')
```

### URL Routes

```python
# Projects and Tasks
path('comms/projects/', views.project_list, name='project_list'),
path('comms/projects/new/', views.project_create, name='project_create'),
path('comms/projects/<int:pk>/', views.project_detail, name='project_detail'),
path('comms/projects/<int:pk>/add-member/', views.project_add_member, name='project_add_member'),
path('comms/projects/<int:pk>/status/', views.project_update_status, name='project_update_status'),
path('comms/projects/<int:project_pk>/tasks/new/', views.task_create, name='task_create'),
path('comms/projects/<int:project_pk>/tasks/<int:pk>/', views.task_detail, name='task_detail'),
path('tasks/<int:pk>/status/', views.task_update_status, name='task_update_status'),
path('tasks/<int:pk>/assign/', views.task_assign, name='task_assign'),
path('tasks/<int:pk>/comment/', views.task_comment, name='task_comment'),
```

### Features

- **Kanban Board**: Visual task board with drag-and-drop columns (To Do, In Progress, In Review, Completed)
- **Task Assignment**: Assign multiple team members to tasks
- **Due Dates**: Set due dates and times with overdue indicators
- **Comments**: Task discussions with @mention support
- **Progress Tracking**: Automatic project progress calculation based on task completion
- **Push Notifications**: Notifications when assigned to tasks or mentioned in comments

---

## PWA Push Notifications

Web push notification system for real-time alerts on mobile and desktop.

### Setup

1. **Generate VAPID Keys**:
```bash
npx web-push generate-vapid-keys
```

2. **Configure Environment Variables**:
```
VAPID_PUBLIC_KEY=your-public-key
VAPID_PRIVATE_KEY=your-private-key
VAPID_CLAIMS_EMAIL=mailto:your-email@example.com
```

3. **Install pywebpush**:
```bash
pip install pywebpush
```

### Models

#### PushSubscription
```python
class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.TextField(unique=True)
    p256dh_key = models.CharField(max_length=200)
    auth_key = models.CharField(max_length=100)
    device_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
```

#### NotificationPreference
```python
class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    announcements = models.BooleanField(default=True)
    announcements_urgent_only = models.BooleanField(default=False)
    direct_messages = models.BooleanField(default=True)
    channel_messages = models.BooleanField(default=False)
    channel_mentions_only = models.BooleanField(default=True)
    care_alerts = models.BooleanField(default=True)
    followup_reminders = models.BooleanField(default=True)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
```

### URL Routes

```python
# Push Notifications
path('notifications/', views.push_preferences, name='push_preferences'),
path('notifications/vapid-key/', views.push_vapid_key, name='push_vapid_key'),
path('notifications/subscribe/', views.push_subscribe, name='push_subscribe'),
path('notifications/unsubscribe/', views.push_unsubscribe, name='push_unsubscribe'),
path('notifications/test/', views.push_test, name='push_test'),
path('notifications/clicked/', views.notification_clicked, name='notification_clicked'),
path('notifications/device/<int:subscription_id>/remove/', views.push_remove_device, name='push_remove_device'),
```

### Notification Types

| Type | Triggered By |
|------|-------------|
| `announcement` | New team announcements |
| `dm` | New direct messages |
| `channel` | Channel messages (when mentioned) |
| `care` | Proactive care alerts |
| `followup` | Follow-up reminders |
| `project` | Added to a project |
| `task` | Assigned to a task, task comments |

### Notification Functions (core/notifications.py)

```python
# Send to a single user
send_notification_to_user(user, notification_type, title, body, url, data, priority)

# Send to multiple users
send_notification_to_users(users, notification_type, title, body, url, data, priority)

# Event-specific helpers
notify_new_announcement(announcement)
notify_new_dm(message)
notify_channel_message(message, mentioned_users)
notify_care_alert(insight)
notify_followup_due(followup)
notify_project_assignment(project, user)
notify_task_assignment(task, user)
notify_task_comment(comment)
notify_user_mentioned(message, mentioned_users)
```

### Service Worker

The PWA service worker (`static/js/sw.js`) handles:
- Push notification display
- Notification click actions (opens relevant URL)
- Offline caching for static assets

---

## Example Usage Scenarios

### Logging an Interaction
**User Input:**
> "Talked with Sarah Johnson after service today. She mentioned her daughter Emma is starting kindergarten next month and she's nervous about it. Sarah loves gardening - her tomatoes are doing great this year. She might be interested in joining the vocals team in the fall."

**AI Processing:**
- Creates/links Volunteer: Sarah Johnson
- Extracts: family (daughter Emma, kindergarten), hobbies (gardening), interests (vocals team)
- Stores with embedding for future search
## Development Notes

### Adding New Query Types
1. Add pattern to appropriate `is_*_query()` function in `agent.py`
2. Add handler in `query_agent()` to process the query
3. Add formatter function if needed (e.g., `format_*_details()`)
4. Update disambiguation if query could be confused with others

### Testing Queries
All query detection functions log their results:
```
logger.info(f"PCO query pattern matched: '{qtype}' for message: '{message[:50]}...'")
```

Check Railway logs to debug query detection issues.

### Conversation Context
The `ConversationContext` model tracks:
- Which interactions have been shown (deduplication)
- Which volunteers are being discussed (context)
- Pending selections (songs, dates, disambiguations)
- Message count (for summarization at 15+ messages)

### Rate Limiting
PCO API calls are rate-limited:
- 0.5s delay every 20 requests for blockout queries
- Scoped queries to team members instead of all 517+ people

---

## Common Issues

### "Column does not exist" errors
Run migrations: `python manage.py migrate`

### PCO rate limits (429 errors)
- Check if query is scoped to team members
- Add delays between bulk requests

## Implemented Features

The following features have been implemented:

- [x] **PWA with Push Notifications**: Real-time notifications on mobile and desktop
- [x] **Team Communication Hub**: Announcements, channels, and direct messages
- [x] **Project & Task Management**: Kanban-style task boards with assignments
- [x] **Analytics Dashboard**: Comprehensive reporting and insights
- [x] **Proactive Care System**: AI-powered volunteer care alerts
- [x] **Follow-up Management**: Track and manage volunteer follow-ups
- [x] **@Mentions**: Tag team members in channels and task comments
- [x] **Multi-Tenant Foundation**: Organization model, subscriptions, memberships

---

## Recent Improvements (December 2025)

### Performance & Optimization
- **PCO API Rate Limiting**: Implemented intelligent caching and rate limiting to prevent 429 errors
- **Blockout Query Optimization**: Added caching for team member lookups, reducing API calls by 80%
- **Status Detection**: Smart detection of active vs. inactive team members to minimize API requests

### User Experience
- **Thinking Indicator**: Context-aware loading messages while Aria processes queries
- **Date Range Support**: Natural language date ranges (e.g., "first week of February 2026")
- **Pagination**: Full team member queries with automatic pagination handling

### Quality & Testing
- **Automated Tests**: Comprehensive query detection tests with 40+ test cases
- **Response Formatting**: Phase 2 tests for verifying AI response quality
- **RAG Test Prompts**: Documented test scenarios for retrieval-augmented generation

---

## SaaS Development Roadmap

### Phase 1: Multi-Tenant Infrastructure (✅ Complete - 100%)
- [x] Organization & SubscriptionPlan models
- [x] OrganizationMembership with role-based permissions
- [x] TenantMiddleware for request context injection
- [x] Data migration for existing Cherry Hills data

### Phase 2: Tenant-Scoped Queries (✅ Complete - 100%)
- [x] Update all views with `.filter(organization=request.organization)`
- [x] Update Planning Center API for per-org credentials
- [x] Add organization-scoped caching

### Phase 3: Organization Onboarding (✅ Complete - 100%)
- [x] Public signup page with organization creation (`/signup/`)
- [x] Planning Center OAuth flow per-organization (`/onboarding/connect-pco/`)
- [x] Stripe checkout integration (`/onboarding/checkout/`)
- [x] Team member invitation flow (`/onboarding/invite-team/`, `/invite/<token>/`)

### Phase 4: Public Marketing (✅ Complete - 95%)
- [x] Landing page explaining Aria's capabilities (`/`)
- [x] Pricing page with plan comparison (`/pricing/`)
- [x] Demo/trial signup flow (14-day trial via onboarding)
- [ ] Customer testimonials (optional enhancement)

### Phase 5: Organization Management (✅ Complete - 100%)
- [x] Organization settings UI (`/settings/`)
- [x] Team member management - invite, roles, permissions (`/settings/members/`)
- [x] Billing dashboard - Stripe portal integration (`/settings/billing/`)
- [x] Usage analytics per organization (`/analytics/`)

### Phase 6: Platform Administration (🔄 In Progress - 20%)
- [ ] Super-admin dashboard for all organizations
- [ ] Usage metrics and revenue reporting across all orgs
- [ ] Customer support tools and ticketing
- [ ] Comprehensive audit logging
- [ ] Organization health monitoring

### Phase 7: Enterprise Features (📋 Planned - 0%)
- [ ] REST API endpoints for integrations
- [ ] API documentation with OpenAPI/Swagger
- [ ] Webhook system for external integrations
- [ ] Custom domain support per organization
- [ ] White-label branding options
- [ ] Multi-campus organization support
- [ ] Advanced SSO (SAML, OAuth providers)

---

## Technical Debt & Known Issues

### High Priority
- **Email Integration**: Team member invitations require manual sharing (2 TODOs in core/views.py:3704, 4125)
- **Proactive Care AI**: VolunteerInsight model exists but AI generation logic incomplete
- **Learning System**: ResponseFeedback and LearnedCorrection models underutilized in query processing
- **Error Handling**: Some views have basic try/except, need more granular error handling

### Medium Priority
- **View Decomposition**: Some views exceed 100 lines and could be split into smaller functions
- **Docstrings**: Missing docstrings in some modules (especially helper functions)
- **Frontend State**: Limited client-side state management, relies heavily on page reloads
- **Custom Branding**: Organization has branding fields but not fully integrated into all templates

### Low Priority
- **Code Coverage**: Test coverage good but could be expanded to edge cases
- **Performance Profiling**: No Django Debug Toolbar or performance monitoring in production
- **Accessibility**: Basic accessibility but could use ARIA labels and keyboard navigation improvements

---

## Future Enhancements (Prioritized)

### 🔥 High Priority (Q1 2026)
1. **Email Notifications**: Email digest for prayer requests, follow-ups, and team invitations
2. **Platform Admin Dashboard**: Super-admin interface for monitoring all organizations
3. **Proactive Care AI**: Complete AI-powered volunteer care insight generation
4. **Learning System Activation**: Utilize feedback models to improve query responses

### 🎯 Medium Priority (Q2 2026)
5. **REST API**: RESTful API endpoints for integrations (Enterprise plan feature)
6. **Webhooks**: Event-based webhooks for external system integration
7. **Global Search**: Unified search across interactions, messages, tasks, volunteers
8. **Calendar Integration**: Sync tasks and due dates with Google/Outlook calendars
9. **PDF Reports**: Monthly PDF reports of team interactions and analytics

### 💡 Nice to Have (Q3-Q4 2026)
10. **File Attachments**: Attach files to tasks, messages, and interactions
11. **Voice Input**: Speech-to-text for quick interaction logging
12. **Mobile App**: Native mobile app with React Native (PWA already functional)
13. **Custom Domains**: Organizations can use their own domain (e.g., team.churchname.com)
14. **White-labeling**: Full custom branding for Enterprise customers
15. **Multi-campus**: Support for organizations with multiple campuses/locations
16. **Advanced Analytics**: Predictive analytics for volunteer engagement trends
17. **Two-Factor Authentication**: Enhanced security for organization owners
18. **Audit Logging**: Comprehensive activity logs for compliance and security

---

## Recommended Next Steps

### Immediate Actions (This Week)
1. **Complete Email Integration**: Finish email notification system for team invitations
   - Add email templates for invitations, welcome messages, password resets
   - Configure email backend (SendGrid, AWS SES, or Mailgun)
   - Update TODO items in core/views.py:3704, 4125

2. **Test Coverage Expansion**: Add integration tests for critical flows
   - End-to-end onboarding flow test
   - Stripe webhook handling tests
   - Multi-tenant data isolation tests

3. **Documentation Update**: Create deployment and operations guide
   - Environment variable documentation with examples
   - Database backup and restore procedures
   - Monitoring and alerting setup guide

### Short-term Goals (Next 2 Weeks)
4. **Platform Admin Dashboard**: Build super-admin interface
   - List all organizations with status, plan, and usage
   - Revenue metrics and subscription analytics
   - Quick actions: impersonate org, suspend/activate

5. **Proactive Care AI**: Complete AI insight generation
   - Implement scheduled task to analyze volunteer activity
   - Generate insights for missing/declining volunteers
   - Auto-create follow-up suggestions

6. **Error Monitoring**: Set up production error tracking
   - Integrate Sentry or similar service
   - Add custom error pages (404, 500)
   - Implement graceful degradation for PCO API failures

### Medium-term Goals (Next Month)
7. **REST API Development**: Start API v1 for Enterprise customers
   - Design API schema and versioning strategy
   - Implement authentication (API keys, OAuth2)
   - Create OpenAPI documentation

8. **Performance Optimization**: Implement caching strategy
   - Add Redis for session storage and caching
   - Optimize database queries with select_related/prefetch_related
   - Add database indexes based on slow query analysis

9. **Security Hardening**: Complete security audit
   - Enable CSRF protection on all forms
   - Add rate limiting on authentication endpoints
   - Implement content security policy (CSP) headers
   - Regular dependency updates for security patches

### Long-term Vision (Q1-Q2 2026)
10. **Beta Launch Preparation**: Prepare for public beta
    - Create onboarding tutorial/walkthrough
    - Build help center with documentation
    - Set up customer support system (Intercom, Help Scout)
    - Create marketing materials and demo videos

11. **Scale Infrastructure**: Prepare for growth
    - Database optimization for 100+ organizations
    - CDN setup for static assets
    - Auto-scaling configuration
    - Performance testing under load

12. **Enterprise Features**: Build enterprise tier capabilities
    - SSO integration (SAML, Google Workspace, Microsoft)
    - Advanced audit logging
    - Custom domain support
    - White-label branding
    - Priority support system

---

## Contributing & Development Workflow

### Tips for Success
- Add "the song" to clearly indicate song queries vs. people
- Use full names for person queries to avoid disambiguation
- When Aria shows a list, user can select which person they meant
- All queries must filter by organization for multi-tenant safety
