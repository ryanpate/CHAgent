# Cherry Hills Worship Arts Team Portal

## Project Status

**🎯 Overall Completion: ~95%** | **📊 Production-Ready Core Features** | **🔒 Closed Beta**

Last Updated: February 26, 2026

### Quick Stats
- **40+ Database Models** across all domains (including blog, beta requests, security, knowledge base)
- **130+ View Functions** with full CRUD operations
- **105+ Templates** for complete user journeys
- **10 Test Files** with 449 passing test cases (0 failures)
- **34+ Migrations** tracking schema evolution
- **Recent Focus**: Native mobile app (Capacitor) with Face ID biometric auth, haptics, app badge count, pull-to-refresh, Knowledge Base image support, document upload, test suite stability, two-factor authentication, audit logging

### Current Sprint (February 2026)
- ✅ **Closed Beta System** - Full beta request and approval workflow
  - BetaRequest model with admin approval flow
  - Beta request form replacing open signup at `/signup/`
  - Beta confirmation page after request submission
  - Platform admin beta request management (`/platform-admin/beta-requests/`)
  - Approve/reject workflow with automatic invitation emails
  - Beta signup flow for approved users (`/beta/signup/`)
  - Beta organizations get free access (subscription_status='beta')
- ✅ **Security Hardening** - Production-grade security headers and protections
  - HSTS with 1-year max-age, subdomains, and preload
  - Content-Security-Policy via SecurityHeadersMiddleware
  - Permissions-Policy header (camera, microphone, geolocation, payment disabled)
  - Login rate limiting via django-axes (5 attempts, 30-min lockout)
  - Session timeout (24 hours, expires on browser close)
  - Referrer policy (strict-origin-when-cross-origin)
- ✅ **Security Page** (`/security/`) - Public security trust page
  - Plain-language overview (6 security cards: data protection, encryption, access controls, AI privacy, PCO, payments)
  - Collapsible technical details section
  - Responsible disclosure with security@aria.church
  - Added to sitemap and footer navigation
- ✅ **Landing Page Beta Branding** - Updated for closed beta status
  - Beta badge next to logo (gold/amber)
  - Dismissible beta banner on all public pages (localStorage persistence)
  - "Request Beta Access" CTAs replacing "Start Free Trial"
  - Beta subtitle: "Currently in closed beta -- request early access"
- ✅ **Pricing Page Beta Updates** - Free during beta messaging
  - "Free During Beta" banner
  - Updated button text and pricing notes
- ✅ **Security Round 2** - Two-Factor Authentication, Audit Logging, Error Monitoring
  - TOTP-based 2FA with QR code setup and backup codes (`pyotp` + `qrcode[pil]`)
  - TOTPDevice model with OneToOneField to User, code verification, backup codes
  - TwoFactorMiddleware enforces 2FA verification per session
  - AuditLog model with 9 action types and admin dashboard (`/platform-admin/audit-log/`)
  - Audit logging on all admin and organization management actions
  - Sentry SDK integration with `send_default_pii=False` for church data protection
  - Custom 404 and 500 error pages
  - Dependabot configuration for weekly dependency vulnerability scanning
  - 22 new tests (13 for 2FA, 9 for audit log)
- ✅ **Test Suite Fixes** - Resolved 29 pre-existing test failures (7 failures + 22 errors)
  - Fixed TenantMiddleware references to non-existent `org_select`/`org_create` URLs
  - Fixed django-axes compatibility (`force_login()` instead of `login()` in test clients)
  - Fixed blockout date fixtures using past dates (2025 → 2026)
  - Fixed analytics export test using invalid report type
  - All 370 tests now passing with 0 failures
- ✅ **Knowledge Base Documents** - Upload documents for Aria to reference in answers
  - DocumentCategory, Document, DocumentChunk models with multi-tenant isolation
  - PDF text extraction (pypdf) and plain text support
  - Chunked embedding pipeline (text-embedding-3-small) for RAG search
  - 10 views: list, upload, detail, edit, delete, download, category CRUD
  - 9 templates with dark theme matching existing design system
  - Aria integration: document chunks searched alongside interactions, cited in answers
  - Sidebar "Knowledge Base" nav item with book icon
  - Admin/owner permissions for upload/edit/delete, all members can view and query
  - 24 new tests (model, processing, search, view tests) — 394 total passing
- ✅ **Knowledge Base Image Support** - Extract and process images from PDFs, accept standalone image uploads
  - DocumentImage model for storing images with AI-generated descriptions and OCR text
  - Claude Vision integration for image description and OCR extraction
  - PDF image extraction via pypdf (filters small images, caps at 20 per PDF)
  - Standalone image uploads (PNG, JPG, JPEG) with Vision processing
  - Semantic search over image descriptions via embeddings
  - Aria includes relevant images inline in chat responses via `[IMAGE_REF:id]` tokens
  - Server-side rendering of image references to clickable `<img>` thumbnails
  - Document list shows green icon for image files, red for PDF, blue for TXT
  - Document detail shows image preview with AI description and extracted images gallery
  - 30 new tests (model, vision, extraction, search, agent, rendering, templates) — 424 total passing
- ✅ **Native Mobile App (Capacitor)** - iOS and Android apps wrapping the Django web app
  - Ionic Capacitor 6 hybrid native shell with WebView loading from aria.church
  - NativePushToken model for FCM/APNs device token registration
  - JWT authentication API (DRF + SimpleJWT) with email-based login
  - Push token registration/unregistration REST endpoints
  - Native push notification delivery via Firebase Cloud Messaging (both platforms)
  - Firebase iOS SDK (FirebaseCore + FirebaseMessaging) with APNs token forwarding
  - AppDelegate FCM token injection: MessagingDelegate receives FCM token, injects into WebView via `evaluateJavaScript` custom event
  - Proactive FCM token fetch on `applicationDidBecomeActive` as fallback
  - Firebase service account credentials loaded from `FIREBASE_CREDENTIALS_JSON` env var (Railway)
  - App-mode detection via `aria_app=1` cookie or `?app=1` query param (hides sidebar/header)
  - Native app users skip beta landing page, redirect straight to login when unauthenticated
  - Login page "Request Beta Access" link for new users
  - Login screen with JWT token storage via Capacitor Preferences
  - Face ID / Touch ID biometric authentication via `@capgo/capacitor-native-biometric`
  - Haptic feedback on all tappable elements via `@capacitor/haptics`
  - iOS (Xcode) and Android (Gradle) platform projects with app icons and splash screens
  - Custom splash screen (2732x2732 source, gold logo on #0f0f0f, LaunchScreen.storyboard with scaleAspectFill)
  - App Store/Play Store listing content and pre-submission checklist
  - Demo account management command (`create_demo_account`) for App Store review
  - App icon badge count for unread push notifications (per-device tracking via `unread_badge_count` field)
  - Badge count included in FCM payload (`apns.payload.aps.badge`) — iOS updates badge automatically
  - Badge clear on app open: native `applicationIconBadgeNumber = 0`, JS `setBadgeCount(0)`, server API
  - Badge clear API endpoint (`POST /api/push/badge-clear/`) resets count when app opens
  - Push notification tap navigation: JS `pushNotificationActionPerformed` handler navigates to notification URL
  - Cold-start notification handling: AppDelegate stores pending URL from `launchOptions`, injects into WebView after load
  - Background notification tap: `didReceiveRemoteNotification` navigates WebView to notification URL
  - Pull-to-refresh gesture on all pages (touch event handler, 60px threshold, gold spinner)
  - Push entitlements (`App.entitlements` with `aps-environment: development`)
  - 25 new tests (model, auth API, push registration, notifications, badge count, badge clear, app-mode) — 449 total passing
- ✅ **Privacy Policy Page** (`/privacy/`) - Public privacy policy for App Store compliance
  - 10 sections: data collection, AI processing, data sharing, security, retention, user rights, children's privacy
  - Legal entity: Ryan Pate operating as ARIA, contact: support@aria.church
  - SEO meta tags and BreadcrumbList schema markup
  - Added to sitemap and footer navigation on all public pages
- 📋 Create og-image.png and twitter-card.png (pending design)
- 📋 Submit sitemap to Google Search Console (manual step)
- 📋 Write first blog posts (content creation)
- 📋 Proactive care AI insight generation (planned)

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
| `core/models.py` | Organization, SubscriptionPlan, OrganizationMembership, BetaRequest |
| `core/middleware.py` | TenantMiddleware, SecurityHeadersMiddleware, decorators, mixins |
| `core/admin_views.py` | Platform admin views (beta requests, orgs, revenue, usage) |
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

# Firebase Cloud Messaging (native push)
FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}  # Full JSON from Firebase Console
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
- **Team Contact Info**: "Phone numbers of people serving this weekend" / "Email addresses of the team this Sunday"
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

### Knowledge Base Documents
- **Procedural Questions**: "How do I turn on the sound board?" / "What's the lighting setup procedure?"
- **Reference Lookups**: "What's our onboarding checklist?" / "Show me the volunteer guidelines"
- **Image Queries**: "What does the stage layout look like?" / "Show me the lighting diagram"
- **Citations**: Aria cites the source document title when answering from uploaded documents
- **Inline Images**: When relevant images are found, Aria displays them as clickable thumbnails in chat
- Admins/owners upload PDF, TXT, or image (PNG/JPG/JPEG) documents at `/documents/upload/`
- Images in PDFs are automatically extracted, described by Claude Vision, and made searchable
- Aria searches document text and image descriptions alongside interactions

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
| **Mobile App** | Ionic Capacitor 6 (iOS + Android) |
| **Mobile Auth** | Django REST Framework + SimpleJWT |
| **Native Push** | Firebase Cloud Messaging (FCM/APNs) |
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
│   ├── sitemaps.py        # SEO sitemap configuration
│   ├── urls.py
│   └── views.py
├── blog/                   # SEO Blog App
│   ├── __init__.py
│   ├── admin.py           # Blog admin interface
│   ├── apps.py
│   ├── models.py          # BlogPost, BlogCategory, BlogTag
│   ├── sitemaps.py        # BlogSitemap for SEO
│   ├── urls.py
│   └── views.py
├── templates/
│   ├── base.html
│   ├── 404.html               # Custom 404 error page
│   ├── 500.html               # Standalone 500 error page
│   ├── accounts/
│   │   └── login.html
│   ├── blog/              # Blog templates
│   │   ├── base_blog.html
│   │   ├── post_list.html
│   │   ├── post_detail.html
│   │   ├── category_list.html
│   │   └── tag_list.html
│   ├── resources/         # SEO Resource pages
│   │   ├── base_resource.html
│   │   ├── list.html
│   │   ├── volunteer_application_template.html
│   │   ├── schedule_template.html
│   │   └── pco_setup_guide.html
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
│       ├── security.html          # Public security page
│       ├── privacy.html           # Public privacy policy page
│       ├── push_preferences.html
│       ├── admin/
│       │   ├── base.html
│       │   ├── audit_log.html     # Admin audit log dashboard
│       │   └── beta_requests.html # Beta request admin
│       ├── auth/
│       │   ├── totp_setup.html        # 2FA QR code setup
│       │   ├── totp_backup_codes.html # Backup codes display
│       │   └── totp_login.html        # 2FA login verification
│       ├── onboarding/
│       │   ├── base_public.html   # Beta banner, badge
│       │   ├── signup.html        # Beta request form
│       │   ├── beta_confirmation.html  # Request received
│       │   ├── beta_signup.html   # Approved user signup
│       │   └── pricing.html       # Beta pricing notes
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
│       ├── settings/
│       │   ├── general.html       # General settings (with Security tab)
│       │   ├── members.html       # Member settings (with Security tab)
│       │   ├── billing.html       # Billing settings (with Security tab)
│       │   └── security.html      # Security settings (2FA enable/disable)
│       └── partials/
│           ├── task_card.html
│           └── task_comment.html
├── .github/
│   └── dependabot.yml     # Weekly pip dependency scanning
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
| `BetaRequest` | Beta access requests with admin approval workflow |
| `AuditLog` | Admin action audit trail with IP tracking and details |
| `TOTPDevice` | TOTP 2FA devices with backup codes per user |
| `DocumentCategory` | Knowledge Base document categories per organization |
| `Document` | Uploaded documents (PDF/TXT/Image) with extracted text and metadata |
| `DocumentChunk` | Chunked document text with embeddings for semantic search |
| `DocumentImage` | Images (from PDF extraction or standalone upload) with AI descriptions, OCR text, and embeddings |
| `NativePushToken` | Native app push tokens (iOS APNs / Android FCM) per user with badge count |

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

# Public Pages
path('security/', views.security_page, name='security')
path('privacy/', views.privacy_policy, name='privacy')

# Security Settings & 2FA
path('settings/security/', views.security_settings, name='security_settings')
path('settings/security/2fa/setup/', views.totp_setup, name='totp_setup')
path('settings/security/2fa/verify-setup/', views.totp_verify_setup, name='totp_verify_setup')
path('settings/security/2fa/disable/', views.totp_disable, name='totp_disable')
path('login/2fa/', views.totp_login_verify, name='totp_login_verify')

# Knowledge Base
path('documents/', views.document_list, name='document_list')
path('documents/upload/', views.document_upload, name='document_upload')
path('documents/<int:pk>/', views.document_detail, name='document_detail')
path('documents/<int:pk>/edit/', views.document_edit, name='document_edit')
path('documents/<int:pk>/delete/', views.document_delete, name='document_delete')
path('documents/<int:pk>/download/', views.document_download, name='document_download')
path('documents/categories/', views.document_category_list, name='document_category_list')
path('documents/categories/create/', views.document_category_create, name='document_category_create')
path('documents/categories/<int:pk>/edit/', views.document_category_edit, name='document_category_edit')
path('documents/categories/<int:pk>/delete/', views.document_category_delete, name='document_category_delete')

# Platform Admin - Audit Log
path('platform-admin/audit-log/', admin_views.admin_audit_log, name='admin_audit_log')

# Mobile App API (JWT Auth + Push Token Registration)
path('api/auth/token/', api_views.EmailTokenObtainPairView.as_view(), name='api_token_obtain')
path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='api_token_refresh')
path('api/push/register/', api_views.register_push_token, name='api_push_register')
path('api/push/unregister/', api_views.unregister_push_token, name='api_push_unregister')
path('api/push/badge-clear/', api_views.clear_badge_count, name='api_push_badge_clear')
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

# Firebase Cloud Messaging (native push)
FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}  # Full JSON from Firebase Console

# Error Monitoring
SENTRY_DSN=https://your-dsn@sentry.io/project-id
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
│   ├── models.py             # Database models (incl. Organization, BetaRequest, AuditLog, TOTPDevice)
│   ├── views.py              # View handlers (incl. 2FA setup/verify/disable)
│   ├── admin_views.py        # Platform admin views (incl. beta requests, audit log)
│   ├── urls.py               # URL routing
│   ├── sitemaps.py           # SEO sitemap for static/resource pages
│   ├── embeddings.py         # Vector search (interactions, document chunks, image descriptions)
│   ├── document_processing.py # Document text extraction, chunking, image extraction, Claude Vision processing
│   ├── middleware.py         # TenantMiddleware, TwoFactorMiddleware, SecurityHeadersMiddleware
│   ├── context_processors.py # Organization template context
│   ├── notifications.py      # Push notification service (web + native)
│   ├── api_views.py          # Mobile app API (JWT auth, push token registration)
│   ├── api_urls.py           # Mobile app API URL routing
│   └── volunteer_matching.py # Name matching logic
├── blog/                     # SEO Blog App
│   ├── models.py             # BlogPost, BlogCategory, BlogTag
│   ├── views.py              # Blog list/detail views
│   ├── urls.py               # Blog URL routing
│   ├── sitemaps.py           # BlogSitemap for search engines
│   └── admin.py              # Blog admin interface
├── templates/
│   ├── base.html             # Layout with sidebar
│   ├── blog/                 # Blog templates with SEO
│   ├── resources/            # SEO resource page templates
│   └── core/
│       ├── dashboard.html    # Main chat interface
│       ├── security.html     # Public security page
│       ├── privacy.html      # Public privacy policy page
│       ├── interaction_*.html
│       ├── volunteer_*.html
│       ├── followup_*.html
│       ├── feedback_*.html
│       ├── admin/
│       │   ├── audit_log.html       # Admin audit log dashboard
│       │   └── beta_requests.html   # Beta admin dashboard
│       ├── auth/
│       │   ├── totp_setup.html      # 2FA QR code setup
│       │   ├── totp_backup_codes.html # Backup codes display
│       │   └── totp_login.html      # 2FA login verification
│       ├── documents/               # Knowledge Base templates
│       │   ├── document_list.html   # Document grid with search/filter
│       │   ├── document_upload.html # Upload form (PDF/TXT)
│       │   ├── document_detail.html # Document metadata and text preview
│       │   ├── document_edit.html   # Edit document metadata
│       │   ├── document_confirm_delete.html
│       │   ├── category_list.html   # Category management
│       │   ├── category_create.html
│       │   ├── category_edit.html
│       │   └── category_confirm_delete.html
│       ├── settings/security.html   # Security settings (2FA)
│       └── onboarding/
│           ├── signup.html           # Beta request form
│           ├── beta_confirmation.html # Request received
│           └── beta_signup.html      # Approved user signup
├── tests/
│   ├── test_beta_request.py  # Beta system & security tests (26 tests)
│   ├── test_documents.py     # Knowledge Base document tests (24 tests)
│   ├── test_2fa.py           # Two-factor authentication tests (13 tests)
│   ├── test_audit_log.py     # Audit log model & integration tests (9 tests)
│   └── test_native_push.py   # Mobile app API & push notification tests (17 tests)
├── mobile/                   # Capacitor Native App
│   ├── capacitor.config.ts   # Capacitor config (app ID, server URL, plugins)
│   ├── package.json          # npm dependencies (Capacitor plugins)
│   ├── store-listing.md      # App Store / Play Store listing content
│   ├── src/
│   │   ├── index.html        # Login screen + tab bar UI
│   │   ├── app.js            # App init, tab navigation, More menu
│   │   ├── auth.js           # JWT login, refresh, token storage
│   │   ├── push.js           # FCM/APNs push registration
│   │   └── styles.css        # Dark theme mobile styles
│   ├── resources/            # App icon and splash screen source images
│   ├── ios/                  # Xcode project (generated by Capacitor)
│   └── android/              # Android Studio project (generated by Capacitor)
├── docs/plans/               # Design docs & implementation plans
├── config/
│   ├── settings.py           # Incl. Stripe, security, django-axes, DRF, JWT config
│   └── urls.py               # Main URL routing incl. sitemap and API
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

## Beta Testing System

The platform is currently in closed beta. Users request access through a form, and platform admins approve requests.

### BetaRequest Model

```python
class BetaRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('invited', 'Invited'),
        ('signed_up', 'Signed Up'),
    ]
    CHURCH_SIZE_CHOICES = [
        ('small', 'Under 100'),
        ('medium', '100-500'),
        ('large', '500-2,000'),
        ('mega', '2,000+'),
    ]

    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    church_name = models.CharField(max_length=200)
    church_size = models.CharField(max_length=20, choices=CHURCH_SIZE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    invitation = models.ForeignKey(OrganizationInvitation, null=True, blank=True)
    referral_source = models.CharField(max_length=100, blank=True)
```

### Beta Flow

1. Visitor fills out beta request form at `/signup/` (name, email, church name, church size)
2. Request saved as `pending`, confirmation page shown
3. Platform admin sees pending requests in `/platform-admin/beta-requests/`
4. On approval: invitation email sent with signup link to `/beta/signup/`
5. Approved user creates account, organization created with `subscription_status='beta'`
6. Beta orgs skip Stripe checkout, get full feature access

### URL Routes

```python
# Beta request (public)
path('signup/', views.onboarding_signup, name='onboarding_signup')  # Beta request form
path('beta/signup/', views.beta_signup, name='beta_signup')  # Approved user account creation

# Beta admin (platform admin only)
path('platform-admin/beta-requests/', admin_views.admin_beta_requests, name='admin_beta_requests')
path('platform-admin/beta-requests/<int:pk>/approve/', admin_views.admin_beta_approve, name='admin_beta_approve')
path('platform-admin/beta-requests/<int:pk>/reject/', admin_views.admin_beta_reject, name='admin_beta_reject')
```

### Organization Beta Status

Beta organizations have `subscription_status='beta'` which:
- Skips Stripe checkout during onboarding
- Grants full feature access (equivalent to Ministry plan)
- Shows in platform admin as beta status

---

## Security

### Security Page

Public security page at `/security/` explaining the platform's security measures:
- Plain-language overview for church leadership (6 security cards)
- Collapsible technical details for IT staff
- Responsible disclosure contact: security@aria.church

### Privacy Policy

Public privacy policy at `/privacy/` required for App Store submission:
- 10 sections covering data collection, AI processing, data sharing, security, retention, user rights, children's privacy
- Legal entity: Ryan Pate operating as ARIA
- Contact: support@aria.church
- Added to sitemap and footer navigation

### Security Headers (SecurityHeadersMiddleware)

Custom middleware in `core/middleware.py` adds:
- **Content-Security-Policy**: Restricts resource loading origins
- **Permissions-Policy**: Disables camera, microphone, geolocation, payment APIs

### Security Configuration (settings.py)

```python
# HSTS (production only)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Session timeout
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Referrer policy
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Login rate limiting (django-axes)
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCK_OUT_BY_COMBINATION_USER_AND_IP = True
AXES_RESET_ON_SUCCESS = True
```

### Two-Factor Authentication (TOTP)

Custom TOTP implementation using `pyotp` + `qrcode[pil]` (avoids template conflicts with HTMX+Tailwind):

```python
class TOTPDevice(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='totp_device')
    secret = models.CharField(max_length=32)
    is_verified = models.BooleanField(default=False)
    backup_codes = models.JSONField(default=list, blank=True)  # Hashed with make_password

    def verify_code(self, code): ...        # Validates TOTP code with 1-step tolerance
    def verify_backup_code(self, code): ... # One-time use, removes after verification
    def generate_backup_codes(self): ...    # Generates 10 backup codes
    def get_provisioning_uri(self): ...     # QR code URI for authenticator apps
```

**Flow:**
1. User enables 2FA at `/settings/security/` → redirected to `/settings/security/2fa/setup/`
2. QR code displayed for authenticator app scanning
3. User enters verification code at `/settings/security/2fa/verify-setup/`
4. 10 backup codes displayed (one-time view)
5. On subsequent logins, `TwoFactorMiddleware` redirects to `/login/2fa/` for code entry
6. Session flag `request.session['2fa_verified'] = True` tracks verification state

### Audit Logging

Admin action audit trail with IP tracking:

```python
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('beta_approve', 'Beta Request Approved'),
        ('beta_reject', 'Beta Request Rejected'),
        ('org_status_change', 'Organization Status Changed'),
        ('org_impersonate', 'Organization Impersonated'),
        ('user_role_change', 'User Role Changed'),
        ('user_removed', 'User Removed'),
        ('invitation_sent', 'Invitation Sent'),
        ('invitation_cancelled', 'Invitation Cancelled'),
        ('settings_updated', 'Settings Updated'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    details = models.JSONField(default=dict)
```

**Admin Dashboard**: `/platform-admin/audit-log/` with action type filtering and pagination (25/page).

**Instrumented Actions**:
- Admin views: beta approve/reject, org impersonate, org status change
- Org views: invite member, update role, remove member, cancel invitation

### Error Monitoring (Sentry)

```python
# config/settings.py - production only (not in DEBUG mode)
import sentry_sdk
sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN', ''),
    send_default_pii=False,  # Protects church member data
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
)
```

Custom error pages: `templates/404.html` (extends base.html), `templates/500.html` (standalone HTML for resilience).

### Dependency Scanning (Dependabot)

`.github/dependabot.yml` configured for weekly pip dependency vulnerability scanning.

### Security Summary

| Protection | Implementation |
|-----------|---------------|
| HTTPS/TLS | Railway auto-SSL + SECURE_SSL_REDIRECT |
| HSTS | 1-year max-age, subdomains, preload |
| CSRF | Django built-in with trusted origins |
| XSS | Template auto-escaping + X-XSS-Protection |
| Content-Type Sniffing | X-Content-Type-Options: nosniff |
| Clickjacking | X-Frame-Options: DENY + frame-ancestors 'none' |
| CSP | SecurityHeadersMiddleware |
| Rate Limiting | django-axes (5 attempts, 30-min lockout) |
| Session Security | 24-hour timeout, secure cookies |
| Password Security | PBKDF2 + 4 validators |
| Two-Factor Auth | TOTP with backup codes via TwoFactorMiddleware |
| Audit Logging | AuditLog model with admin dashboard |
| Error Monitoring | Sentry SDK with PII protection |
| Dependency Scanning | Dependabot weekly pip audits |
| Multi-tenant Isolation | Org-scoped queries via TenantMiddleware |
| Invitation Security | Cryptographic tokens (secrets.token_urlsafe) |

---

## SEO Infrastructure

Complete technical SEO implementation for organic search visibility.

### Meta Tags (All Public Pages)

All public pages include comprehensive meta tags via `templates/core/onboarding/base_public.html`:

```html
<!-- SEO Meta Tags -->
<meta name="description" content="{% block meta_description %}...{% endblock %}">
<meta name="keywords" content="worship team management, church volunteer software...">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://aria.church{{ request.path }}">

<!-- Open Graph (Facebook, LinkedIn) -->
<meta property="og:type" content="website">
<meta property="og:title" content="{% block og_title %}...{% endblock %}">
<meta property="og:description" content="{% block og_description %}...{% endblock %}">
<meta property="og:image" content="https://aria.church/static/og-image.png">
<meta property="og:url" content="https://aria.church{{ request.path }}">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="...">
<meta name="twitter:description" content="...">
<meta name="twitter:image" content="https://aria.church/static/twitter-card.png">
```

### Schema.org Structured Data

JSON-LD structured data for rich search results:

| Schema Type | Page | Purpose |
|-------------|------|---------|
| `Organization` | All pages (base) | Company info for Knowledge Graph |
| `SoftwareApplication` | Landing page | App info with pricing, features |
| `FAQPage` | Pricing page | 6 FAQs for rich snippets |
| `Product` | Pricing page | Individual plan details |
| `BreadcrumbList` | All pages | Navigation breadcrumbs |
| `HowTo` | PCO Setup Guide | Step-by-step instructions |
| `Article` | Blog posts | Article metadata |

### Blog System

Django app for SEO content marketing (`blog/`):

```python
# blog/models.py
class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    excerpt = models.TextField(max_length=300)
    content = models.TextField()
    category = models.ForeignKey(BlogCategory)
    tags = models.ManyToManyField(BlogTag)

    # SEO fields
    meta_title = models.CharField(max_length=60)      # For <title> tag
    meta_description = models.CharField(max_length=160)  # For meta description
    focus_keyword = models.CharField(max_length=100)  # Primary keyword
    featured_image_url = models.URLField()

    status = models.CharField(choices=[('draft','Draft'),('published','Published')])
    published_at = models.DateTimeField()
    author = models.ForeignKey(User)
```

### Resource Pages

SEO-optimized content pages for organic traffic:

| URL | Purpose | Schema |
|-----|---------|--------|
| `/resources/` | Resource listing | BreadcrumbList |
| `/resources/volunteer-application-template/` | Lead magnet | BreadcrumbList |
| `/resources/worship-schedule-template/` | Lead magnet | BreadcrumbList |
| `/resources/planning-center-setup-guide/` | Tutorial | HowTo, BreadcrumbList |

### Sitemap Configuration

Dynamic sitemap generation (`core/sitemaps.py`, `blog/sitemaps.py`):

```python
# Sitemap includes:
# - Static pages: /, /pricing/, /signup/
# - Resource pages: /resources/*, with per-page priorities
# - Blog posts: /blog/<slug>/ (published only)
# - Blog categories: /blog/category/<slug>/

# URL: /sitemap.xml
```

### SEO URL Routes

```python
# Blog URLs (config/urls.py)
path('blog/', include('blog.urls', namespace='blog')),

# Resource URLs (core/urls.py)
path('resources/', views.resources_list, name='resources_list'),
path('resources/volunteer-application-template/', views.resource_volunteer_application),
path('resources/worship-schedule-template/', views.resource_schedule_template),
path('resources/planning-center-setup-guide/', views.resource_pco_guide),

# Privacy
path('privacy/', views.privacy_policy, name='privacy'),

# Sitemap
path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
```

### Pending SEO Items

| Item | Status | Notes |
|------|--------|-------|
| `og-image.png` (1200x630) | Pending | Social sharing image |
| `twitter-card.png` (1200x600) | Pending | Twitter card image |
| Google Search Console | Pending | Submit sitemap manually |
| Rich Results Test | Pending | Validate schema markup |
| First blog posts | Pending | Content creation needed |

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
- [x] **SEO Infrastructure**: Meta tags, Open Graph, Twitter Cards, Schema.org JSON-LD
- [x] **Blog System**: Full Django blog with SEO optimization and admin interface
- [x] **Resource Pages**: SEO-optimized content pages with lead magnets
- [x] **Closed Beta System**: Beta request form, admin approval, invitation flow
- [x] **Security Hardening**: HSTS, CSP, Permissions-Policy, django-axes rate limiting, session timeout
- [x] **Security Page**: Public `/security/` page with plain-language and technical security details
- [x] **Privacy Policy**: Public `/privacy/` page with 10 sections covering data collection, AI processing, sharing, retention, and user rights
- [x] **Two-Factor Authentication**: TOTP-based 2FA with QR setup, backup codes, login enforcement
- [x] **Audit Logging**: Admin action audit trail with IP tracking and filterable dashboard
- [x] **Error Monitoring**: Sentry SDK integration with PII protection and custom error pages
- [x] **Dependency Scanning**: Dependabot configuration for weekly vulnerability scanning
- [x] **Knowledge Base**: Document upload with RAG search, Aria integration, and citation support
- [x] **Knowledge Base Image Support**: PDF image extraction, standalone image uploads, Claude Vision descriptions, inline image display in chat
- [x] **Native Mobile App**: iOS and Android apps via Capacitor with JWT auth, Face ID/Touch ID biometric login, haptic feedback, app badge count, pull-to-refresh, and FCM push notifications

---

## Recent Improvements (January 2026)

### SEO Infrastructure (New!)
- **Technical SEO**: Complete meta tag implementation across all public pages
  - Meta descriptions, keywords, canonical URLs, robots directives
  - Open Graph tags for Facebook/LinkedIn sharing
  - Twitter Card tags for Twitter sharing
- **Structured Data**: JSON-LD Schema.org markup for rich search results
  - Organization, SoftwareApplication, FAQPage, Product, BreadcrumbList, HowTo, Article
- **Blog System**: Full Django blog app with SEO optimization
  - BlogPost, BlogCategory, BlogTag models with SEO fields
  - Admin interface for content management
  - BlogSitemap for search engine indexing
- **Resource Pages**: SEO-optimized content pages
  - Volunteer application template, schedule template, PCO setup guide
  - Each with appropriate schema markup and meta tags
- **Sitemap**: Dynamic XML sitemap including all public pages, blog posts, and resources

### Compound Query Detection
- **Team Contact Queries**: Ask for phone numbers/emails of people serving on a date
  - "What are the phone numbers of the people serving this weekend?"
  - "Email addresses of volunteers scheduled this Sunday"
  - "Contact info for everyone on the team January 15th"
- **Smart Detection**: Distinguishes between individual contact queries ("John's phone") and team queries
- **Generic Name Rejection**: Won't mistake "the people serving" as a person name

### Performance & Optimization
- **Lightweight Contact API**: New `get_person_contact_info_only()` reduces API calls from 10+ to 2 per person
- **Compound Query Optimization**: Team contact queries now use ~35 API calls instead of 150+
- **PCO API Rate Limiting**: Intelligent caching and rate limiting to prevent 429 errors
- **Blockout Query Optimization**: Added caching for team member lookups, reducing API calls by 80%
- **Status Detection**: Smart detection of active vs. inactive team members to minimize API requests
- **BPM Cache**: Database-backed caching for song BPM lookups with negative cache to avoid repeated API calls

### User Experience
- **Thinking Indicator**: Context-aware loading messages while Aria processes queries
- **Date Range Support**: Natural language date ranges (e.g., "first week of February 2026")
- **Pagination**: Full team member queries with automatic pagination handling
- **Team Hub**: Centralized task management with My Tasks and Team Tasks views
- **Standalone Tasks**: Create tasks outside of projects for quick action items

### Platform Administration
- **Admin Dashboard**: Complete super-admin dashboard with MRR/ARR, user counts, and AI usage
- **Organization Management**: View, filter, search all organizations with usage metrics
- **Impersonation Mode**: Support-friendly organization impersonation for debugging
- **Revenue Analytics**: Churn rate, plan distribution, and subscription metrics

### Quality & Testing
- **Automated Tests**: Comprehensive query detection tests with 190 test cases across 6 files
- **Compound Query Tests**: 24 new tests for team contact queries and generic name rejection
- **Response Formatting**: Phase 2 tests for verifying AI response quality
- **RAG Test Prompts**: Documented test scenarios for retrieval-augmented generation
- **Multi-tenant Isolation Tests**: Verify data isolation between organizations

---

## Recent Improvements (February 2026)

### Closed Beta System
- **Beta Request Form**: Replaced open signup with beta request form at `/signup/`
  - Collects name, email, church name, church size
  - Unique email constraint prevents duplicate requests
  - Confirmation page with request details shown after submission
- **Admin Approval Workflow**: Platform admins manage beta requests at `/platform-admin/beta-requests/`
  - Filter by status (pending, approved, rejected, invited, signed_up)
  - One-click approve/reject with automatic invitation emails
  - Approved users receive signup link via email
- **Beta Signup Flow**: Approved users create accounts at `/beta/signup/`
  - Pre-filled email from beta request
  - Creates organization with `subscription_status='beta'`
  - Skips Stripe checkout (free during beta)
  - Routes directly to Planning Center connection
- **Beta Branding**: All public pages updated for closed beta status
  - Gold/amber beta badge next to logo
  - Dismissible beta banner on all public pages (localStorage)
  - "Request Beta Access" CTAs replacing "Start Free Trial"
  - Pricing page shows "Free During Beta" messaging

### Security Hardening
- **HSTS**: Strict-Transport-Security with 1-year max-age, includeSubDomains, preload
- **CSP**: Content-Security-Policy via SecurityHeadersMiddleware
  - `default-src 'self'`, `script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com`
  - `style-src 'self' 'unsafe-inline'`, `img-src 'self' data: https:`
  - `font-src 'self' https://fonts.gstatic.com`, `frame-ancestors 'none'`
- **Permissions-Policy**: camera=(), microphone=(), geolocation=(), payment=()
- **Login Rate Limiting**: django-axes with 5 failed attempts, 30-minute lockout, IP+username tracking
- **Session Security**: 24-hour timeout, expires on browser close
- **Referrer Policy**: strict-origin-when-cross-origin

### Security Page (`/security/`)
- **Plain-Language Overview**: 6 security cards covering data protection, encryption, access controls, AI privacy, Planning Center security, and payments
- **Technical Details**: Collapsible section with transport security, CSP, authentication, multi-tenant isolation, infrastructure, session security, and invitation security details
- **Responsible Disclosure**: security@aria.church contact for reporting vulnerabilities
- **SEO**: Added to sitemap and footer navigation

### New Tests
- **26 new tests** in `tests/test_beta_request.py` covering:
  - BetaRequest model creation, uniqueness, and string representation
  - Beta request form display, submission, duplicate handling, and validation
  - Landing page beta branding (badge, CTAs, banner)
  - Pricing page beta messaging
  - Security headers (CSP, Permissions-Policy)
  - Security page content sections
  - Beta admin views (list, approve, reject, access control)
  - Beta signup flow (page access, org creation, rejection of uninvited users)
  - Security settings (session timeout, browser close expiry)
- **29 test fixes** across middleware, view isolation, and response formatting tests:
  - Fixed django-axes compatibility in all test clients (`force_login()`)
  - Fixed TenantMiddleware fallback paths for missing URL patterns
  - Fixed date-sensitive fixtures and invalid report type references
  - Full suite: **370 passed, 0 failures, 0 errors**

### Security Round 2
- **Two-Factor Authentication (TOTP)**:
  - TOTPDevice model with `pyotp` + `qrcode[pil]` (custom implementation for HTMX+Tailwind compatibility)
  - QR code setup flow at `/settings/security/2fa/setup/`
  - 10 hashed backup codes (one-time use, hashed with `make_password`)
  - TwoFactorMiddleware enforces verification per session
  - Login 2FA verification at `/login/2fa/`
  - Security settings page at `/settings/security/` with enable/disable UI
  - 13 tests in `tests/test_2fa.py` (model + setup views + login flow)
- **Audit Logging**:
  - AuditLog model with 9 action types tracking admin and org management actions
  - `log_admin_action()` helper with `get_client_ip()` (handles Railway reverse proxy)
  - Admin audit log dashboard at `/platform-admin/audit-log/` with action type filtering
  - Instrumented 8 views: beta approve/reject, org impersonate/status change, invite/role/remove/cancel
  - 9 tests in `tests/test_audit_log.py` (model + integration + admin views)
- **Sentry Error Monitoring**:
  - Sentry SDK integration in `config/settings.py` (production only, not in DEBUG)
  - `send_default_pii=False` to protect church member data
  - Custom 404 page (extends base.html) and 500 page (standalone HTML for resilience)
- **Dependabot Configuration**:
  - `.github/dependabot.yml` for weekly pip dependency vulnerability scanning
  - `pip-audit` added to requirements.txt for local vulnerability scanning

### Test Suite Fixes
Resolved 29 pre-existing test failures (7 failures + 22 errors) caused by 4 distinct issues:
- **`NoReverseMatch: 'org_select'`** (3 failures): TenantMiddleware referenced non-existent URL names `org_select` and `org_create`. Fixed by redirecting to `/onboarding/`, auto-selecting first org for multi-org users, and returning `HttpResponseForbidden` for non-members. Also added `organization__is_active=True` filter to membership queries.
- **`AxesBackendRequestParameterRequired`** (22 errors + 2 failures): `client.login()` incompatible with django-axes (requires request object). Changed to `client.force_login()` in `conftest.py` fixtures and 3 test files.
- **`Database access not allowed`** (1 failure): Test missing `db` fixture parameter for session save. Added `db` to `test_middleware_no_org_for_unauthenticated_user`.
- **Blockout date assertion** (1 failure): Fixture dates in 2025 were now in the past, causing blockouts to render differently. Updated to 2026/2027 dates and matching assertions.
- **Analytics export report type** (1 failure): Test used `'engagement'` but view expects `'volunteer_engagement'`.

Result: **370 tests passing, 0 failures, 0 errors**.

### Knowledge Base Image Support
- **DocumentImage Model**: New model for storing images with AI-generated descriptions, OCR text, and embeddings
  - Supports both PDF-extracted images (`source_type='pdf_extract'`) and standalone uploads (`source_type='standalone'`)
  - Organization-scoped with foreign key to Document
  - Fields: image_file, description, ocr_text, embedding_json, width, height, processing_error
  - Migration: `core.0027_alter_document_file_type_documentimage`
- **Claude Vision Integration**: `describe_image_with_vision()` sends images to `claude-sonnet-4-20250514`
  - Single prompt generates both DESCRIPTION and OCR_TEXT sections
  - Document title provided as context for domain-aware descriptions
  - Graceful error handling — failed images saved with `processing_error`, don't block text processing
- **PDF Image Extraction**: `extract_images_from_pdf()` uses pypdf's `page.images` API
  - `_filter_small_images()` removes images below 50x50 pixels (decorative artifacts)
  - `_cap_images()` limits to 20 images per PDF (cost control)
  - Pillow normalizes extracted images to PNG/JPEG format
- **Standalone Image Upload**: Upload form accepts `.png,.jpg,.jpeg` files
  - File type detection sets `file_type='image'` for image extensions
  - `_process_standalone_image()` creates Document + DocumentImage + Vision processing
  - Description stored in `Document.extracted_text` for detail page display
- **Image Semantic Search**: `search_similar_images()` in `core/embeddings.py`
  - Cosine similarity search over DocumentImage.embedding_json
  - Organization-scoped, configurable limit and similarity threshold
- **Agent Integration**: `_build_image_context()` in `core/agent.py`
  - Image search results included alongside document chunk context
  - System prompt instructs Aria to use `[IMAGE_REF:id]` tokens for relevant images
- **Chat Image Rendering**: `render_image_refs()` in `core/views.py`
  - Replaces `[IMAGE_REF:id]` tokens with clickable `<img>` HTML before saving ChatMessage
  - Organization-scoped security — cross-org references silently stripped
  - Thumbnails (`max-w-sm max-h-64`) open full size in new tab
- **Template Updates**:
  - Document list: green image icon for image files, red for PDF, blue for TXT
  - Document detail: Image Preview section with AI description and OCR text
  - Document detail: Extracted Images gallery for PDFs (responsive grid with page numbers)
- **30 new tests** across 8 test classes:
  - DocumentImage model CRUD and org isolation
  - Claude Vision API mocking and error handling
  - PDF extraction, filtering, and capping
  - Pipeline integration and error resilience
  - Standalone upload view and file type validation
  - Image semantic search and org isolation
  - Agent context building and empty results
  - Image reference rendering, security, and cross-org stripping
  - Template icon and preview rendering
  - Full suite: **424 tests passing, 0 failures, 0 errors**

### Native Mobile App (Capacitor)
- **Architecture**: Hybrid native shell (Ionic Capacitor 6) wrapping the existing Django web app in a WebView
  - App loads pages from `aria.church` — WebView renders Django templates directly
  - Web sidebar navigation preserved (native tab bar not used since remote pages replace local HTML)
  - Login via Django's standard login page at `/accounts/login/`
  - External links open in system browser via `@capacitor/browser`
  - **IMPORTANT: Capacitor bridge on remote pages** — `registerPlugin()` is NOT available; use `Capacitor.Plugins.X` direct access instead (e.g., `Capacitor.Plugins.NativeBiometric`, `Capacitor.Plugins.Haptics`)
  - Native plugin code must live in Django templates (not `mobile/src/`), since `server.url` loads remote pages and local JS is never executed
- **Face ID / Touch ID Biometric Login** (`templates/accounts/login.html`):
  - `@capgo/capacitor-native-biometric` v8.4.2 for Keychain credential storage
  - Retry loop waits up to 2s for Capacitor plugin bridge to be ready
  - On first manual login, credentials stored via `setCredentials()` (deferred with `setTimeout` to avoid blocking form POST)
  - On subsequent logins, auto-prompts Face ID/Touch ID, auto-fills and submits form
  - `NSFaceIDUsageDescription` in `Info.plist` for Face ID permission
  - Console logging with `[ARIA]` prefix for Safari Web Inspector debugging
- **Haptic Feedback** (`templates/base.html`):
  - `@capacitor/haptics` provides light impact on all tappable elements (links, buttons, nav items)
  - Uses `Capacitor.Plugins.Haptics.impact({ style: 'LIGHT' })` — only works on physical devices, not simulator
- **Capacitor Native Detection** (`templates/base.html`):
  - Detects native app via `Capacitor.isNativePlatform()` or `Capacitor.Plugins.SplashScreen` presence
  - Adds `capacitor-native` CSS class for safe-area status bar padding
  - Does NOT hide sidebar/hamburger menu (web nav is the primary nav in remote-page architecture)
- **Demo Account** (`core/management/commands/create_demo_account.py`):
  - Management command for App Store review: `python manage.py create_demo_account`
  - Creates `demo@aria.church` / `AppReview2026!` with sample org, volunteers, interactions, follow-ups
- **Backend: NativePushToken Model** (`core/models.py`):
  - Stores FCM/APNs device tokens per user with platform (ios/android) and device name
  - `unique_together` on user + token prevents duplicate registrations
  - `is_active` flag for soft-disabling tokens
  - Migration: `core.0028_nativepushtoken`
- **Backend: JWT Auth API** (`core/api_views.py`, `core/api_urls.py`):
  - Django REST Framework + SimpleJWT with email-based login (custom serializer)
  - `POST /api/auth/token/` — obtain access + refresh tokens
  - `POST /api/auth/token/refresh/` — refresh expired access tokens
  - `POST /api/push/register/` — register/update native push token (authenticated)
  - `DELETE /api/push/unregister/` — remove push token on logout
  - CORS configured for `capacitor://localhost` and `http://localhost`
  - 100/minute user rate throttle
- **Backend: Native Push Delivery** (`core/notifications.py`):
  - `send_native_push()` increments `unread_badge_count` and sends to FCM for both Android and iOS
  - `_send_fcm()` includes `apns.payload.aps.badge` for iOS app icon badge count
  - Extended `send_notification_to_user()` to include native push tokens alongside web push
  - Inactive tokens (`is_active=False`) are skipped
- **Backend: Badge Clear API** (`core/api_views.py`):
  - `POST /api/push/badge-clear/` — resets `unread_badge_count` to 0 for all authenticated user's tokens
  - Called automatically on page load in native app to clear badge when app opens
- **Badge Clear on App Open** (`templates/base.html`):
  - Calls `PushNotifications.removeAllDeliveredNotifications()` to clear notification center
  - Fires `fetch('/api/push/badge-clear/')` to reset server-side badge counter
- **Pull-to-Refresh** (`templates/base.html`):
  - Pure JS touch gesture handler — detects touchstart/touchmove/touchend events
  - Only activates at scroll position 0 (top of page) and when Capacitor is detected
  - Gold spinner indicator appears during pull gesture (60px threshold)
  - On release past threshold: triggers `window.location.reload()`
  - CSS: `.ptr-indicator` with `.pulling` and `.refreshing` animation states
- **Mobile App** (`mobile/`):
  - `capacitor.config.ts` — App ID `church.aria.app`, server URL `https://aria.church`
  - `src/auth.js` — JWT login, refresh, biometric functions (used by local app, not remote pages)
  - `src/push.js` — FCM registration, push action handler with navigation events
  - `src/app.js` — App init, haptics, biometric flow (used by local app, not remote pages)
  - `src/index.html` — Login form + 5-tab navigation bar (local fallback)
  - `src/styles.css` — Dark theme (#0f0f0f background, #c9a227 gold accent)
- **Native Platforms**:
  - `mobile/ios/` — Xcode project with Capacitor plugins + NativeBiometric, Firebase iOS SDK, app icons, splash screens
  - `mobile/android/` — Android Studio project with generated icons and splash screens
  - Platform-specific assets generated via `@capacitor/assets`
- **App Store Preparation** (`mobile/store-listing.md`):
  - App name, description, keywords, category, privacy/support URLs
  - Screenshot requirements for iPhone 6.7", 5.5", iPad Pro, and Android
  - Pre-submission checklist (developer accounts, Firebase, APNs, screenshots)
- **Dependencies Added** (`requirements.txt`):
  - `djangorestframework>=3.14.0`, `djangorestframework-simplejwt>=5.3.0`
  - `django-cors-headers>=4.3.0`, `firebase-admin>=6.0.0`
- **Mobile npm Dependencies** (`mobile/package.json`):
  - `@capgo/capacitor-native-biometric` ^8.4.2 — Face ID / Touch ID with Keychain storage
  - `@capacitor/haptics` ^8.0.1 — Native haptic feedback
- **Settings Changes** (`config/settings.py`):
  - Added `rest_framework` and `corsheaders` to INSTALLED_APPS
  - `CorsMiddleware` added to MIDDLEWARE
  - REST_FRAMEWORK config with JWT + Session auth, 100/min throttle
  - SIMPLE_JWT config: 1-hour access, 30-day refresh, rotation enabled
  - CORS_ALLOWED_ORIGINS for Capacitor WebView origins
- **25 new tests** in `tests/test_native_push.py` across 8 test classes:
  - NativePushToken model CRUD, uniqueness, tenant isolation, and badge count field
  - JWT auth token obtain and refresh via email credentials
  - Push token register, update, unregister, and auth requirement
  - Native push notification delivery with FCM mocking
  - Badge count increment in push payload and across multiple sends
  - Badge clear API endpoint (resets count, resets all user tokens, requires auth)
  - App-mode template detection (sidebar hidden vs shown)
  - Full suite: **449 tests passing, 0 failures, 0 errors**

#### Capacitor Remote-Page Architecture Notes
> **Critical**: When `server.url` is set in `capacitor.config.ts`, the WebView loads pages from the remote server. Local files in `mobile/src/` are bundled but never displayed. This means:
> - All native plugin calls must be in **Django templates** (not local JS files)
> - Use `window.Capacitor.Plugins.PluginName` to access plugins (NOT `Capacitor.registerPlugin()`)
> - `window.Capacitor.Plugins` contains all installed plugins on remote pages
> - Native bridge calls during form submission must be deferred (`setTimeout`) to avoid cancelling the POST navigation (`NSURLErrorDomain -999`)
> - The web sidebar/hamburger menu is the primary navigation (no native tab bar on remote pages)
> - Haptics only work on physical devices (not in the iOS Simulator)
> - Face ID in Simulator requires: Features → Face ID → Enrolled

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

### Phase 6: Platform Administration (🔄 In Progress - 90%)
- [x] Super-admin dashboard for all organizations (`/platform-admin/`)
- [x] Usage metrics and revenue reporting across all orgs
- [x] Organization impersonation for support
- [x] User management and activity metrics
- [x] Beta request management with approve/reject workflow (`/platform-admin/beta-requests/`)
- [x] Comprehensive audit logging (`/platform-admin/audit-log/`)
- [ ] Customer support tools and ticketing
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
- **Proactive Care AI**: VolunteerInsight model exists but AI generation logic incomplete
- **Learning System**: ResponseFeedback and LearnedCorrection models implemented but underutilized in query processing
- **Large View File**: `core/views.py` is 4530 lines with 102 functions - consider splitting into multiple files

### Medium Priority
- **View Decomposition**: Some views exceed 100 lines and could be split into smaller functions
- **Docstrings**: Missing docstrings in some modules (especially helper functions)
- **Frontend State**: Limited client-side state management, relies heavily on page reloads
- **Custom Branding**: Organization has branding fields but not fully integrated into all templates
- **Agent File Size**: `core/agent.py` is 4183 lines - consider modularizing query handlers

### Low Priority
- **Code Coverage**: Test coverage good but could be expanded to edge cases
- **Performance Profiling**: No Django Debug Toolbar or performance monitoring in production
- **Accessibility**: Basic accessibility but could use ARIA labels and keyboard navigation improvements

---

## Future Enhancements (Prioritized)

### 🔥 High Priority (Q1 2026)
1. **Email Digests**: Scheduled email summaries for prayer requests and follow-up reminders
2. **Proactive Care AI**: Complete AI-powered volunteer care insight generation
3. **Learning System Activation**: Utilize feedback models to improve query responses
4. **Aria Response Quality**: Improve consistency and accuracy of AI responses

### 🎯 Medium Priority (Q2 2026)
5. **REST API**: RESTful API endpoints for integrations (Enterprise plan feature)
6. **Webhooks**: Event-based webhooks for external system integration
7. **Global Search**: Unified search across interactions, messages, tasks, volunteers
8. **Calendar Integration**: Sync tasks and due dates with Google/Outlook calendars
9. **PDF Reports**: Monthly PDF reports of team interactions and analytics

### 💡 Nice to Have (Q3-Q4 2026)
10. **File Attachments**: Attach files to tasks, messages, and interactions
11. **Voice Input**: Speech-to-text for quick interaction logging
12. ~~**Mobile App**~~: ✅ Complete - Native iOS/Android app via Capacitor with JWT auth, tab bar, and FCM push
13. **Custom Domains**: Organizations can use their own domain (e.g., team.churchname.com)
14. **White-labeling**: Full custom branding for Enterprise customers
15. **Multi-campus**: Support for organizations with multiple campuses/locations
16. **Advanced Analytics**: Predictive analytics for volunteer engagement trends
17. ~~**Two-Factor Authentication**~~: ✅ Complete - TOTP with backup codes and login enforcement
18. ~~**Audit Logging**~~: ✅ Complete - Admin action audit trail with dashboard

---

## Recommended Next Steps

### Immediate Actions (This Week)
1. **SEO Completion**: Finish remaining SEO tasks
   - Create `og-image.png` (1200x630) and `twitter-card.png` (1200x600)
   - Submit sitemap to Google Search Console
   - Validate schemas with Google Rich Results Test
   - Write first 2 blog posts targeting long-tail keywords

2. **Proactive Care AI**: Complete AI insight generation
   - Implement scheduled task (Django-Q or Celery) to analyze volunteer activity
   - Generate insights for missing/declining volunteers
   - Auto-create follow-up suggestions from interactions

3. **Error Monitoring**: ✅ Complete
   - ~~Integrate Sentry or similar service~~ (done - Sentry SDK with PII protection)
   - ~~Add custom error pages (404, 500)~~ (done)
   - Implement graceful degradation for PCO API failures

### Short-term Goals (Next 2 Weeks)
3. **Learning System Activation**: Utilize existing feedback models
   - Use LearnedCorrection to auto-correct common misspellings in queries
   - Apply ExtractedKnowledge during Aria responses
   - Track ResponseFeedback metrics on admin dashboard

4. **Code Organization**: Split large files for maintainability
   - Break `core/views.py` (4530 lines) into domain-specific modules
   - Modularize `core/agent.py` (4183 lines) by query type
   - Create separate files for PCO queries, volunteer queries, song queries

5. **Test Coverage Expansion**: Add integration tests for critical flows
   - End-to-end onboarding flow test
   - Stripe webhook handling tests
   - Aria query-response integration tests

### Medium-term Goals (Next Month)
6. **REST API Development**: Start API v1 for Enterprise customers
   - Design API schema and versioning strategy
   - Implement authentication (API keys, OAuth2)
   - Create OpenAPI documentation

7. **Performance Optimization**: Implement caching strategy
   - Add Redis for session storage and caching
   - Profile slow database queries
   - Add database indexes based on slow query analysis

8. **Security Hardening**: ✅ Complete
   - ~~Add rate limiting on authentication endpoints~~ (done - django-axes)
   - ~~Implement content security policy (CSP) headers~~ (done - SecurityHeadersMiddleware)
   - Regular dependency updates for security patches

### Long-term Vision (Q1-Q2 2026)
9. **Beta Launch Preparation**: ✅ Partially Complete
    - ~~Closed beta system with admin approval~~ (done)
    - ~~Security page and hardening~~ (done)
    - Create onboarding tutorial/walkthrough
    - Build help center with documentation
    - Set up customer support system (Intercom, Help Scout)
    - Create marketing materials and demo videos

10. **Scale Infrastructure**: Prepare for growth
    - Database optimization for 100+ organizations
    - CDN setup for static assets
    - Auto-scaling configuration
    - Performance testing under load

11. **Enterprise Features**: Build enterprise tier capabilities
    - SSO integration (SAML, Google Workspace, Microsoft)
    - ~~Advanced audit logging~~ (done - AuditLog with admin dashboard)
    - Custom domain support
    - White-label branding
    - Priority support system

---

## Recommendations for Improvement

### User Experience (UX)
1. **Conversation History**: Add ability to search/filter past conversations with Aria
2. **Quick Actions**: Add keyboard shortcuts for common tasks (Ctrl+K for quick search)
3. **Mobile Responsiveness**: Test and optimize all views for mobile devices
4. **Loading States**: Add skeleton loaders for async content instead of just spinners
5. **Onboarding Tutorial**: First-time user walkthrough highlighting key features
6. **Dark Mode**: Implement dark theme option using organization's `primary_color` field

### Site Efficiency
1. **Query Deduplication**: Cache identical Aria queries within a session
2. **Lazy Loading**: Implement lazy loading for long lists (volunteers, interactions)
3. **Database Indexes**: Add composite indexes for common query patterns:
   - `(organization_id, created_at)` on Interaction, ChatMessage
   - `(organization_id, status)` on FollowUp, Task
4. **API Response Compression**: Enable gzip compression for API responses
5. **Image Optimization**: Compress and resize uploaded images automatically

### Aria Correctness & Responsiveness
1. **Query Confidence Scoring**: Return confidence level with responses, ask for clarification when low
2. **Context Window Optimization**: Summarize long conversation contexts to reduce token usage
3. **Feedback Loop**: When users correct Aria, automatically create LearnedCorrection entries
4. **Response Caching**: Cache responses for identical queries (e.g., "who's on team Sunday")
5. **Streaming Responses**: Implement streaming for long responses to improve perceived speed
6. **Error Recovery**: Graceful handling when PCO API is unavailable (use cached data)
7. **Query Logging**: Log all queries with response times for performance analysis

### Code Quality
1. **Type Hints**: Add comprehensive type hints throughout codebase
2. **API Rate Limiting**: Add per-organization rate limiting for API endpoints
3. **Audit Logging**: ✅ Complete - Admin action audit trail with dashboard and IP tracking
4. **Health Checks**: Add `/health` endpoint for monitoring (database, PCO API, Anthropic API)

---

## Contributing & Development Workflow

### Tips for Success
- Add "the song" to clearly indicate song queries vs. people
- Use full names for person queries to avoid disambiguation
- When Aria shows a list, user can select which person they meant
- All queries must filter by organization for multi-tenant safety
