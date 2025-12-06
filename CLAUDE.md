# Cherry Hills Worship Arts Team Portal

## Project Overview

A private web application for the Cherry Hills Church Worship Arts team to log interactions with volunteers and query that information via an AI Agent powered by Claude. The system enables team members to record encounters, notes, and observations about volunteers, which the AI can later retrieve, analyze, and summarize.

### Core Purpose
- **Log Interactions**: Team members enter free-form notes about volunteer interactions (hobbies, preferences, prayer requests, feedback, etc.)
- **AI-Powered Retrieval**: Ask questions like "What is John's favorite food?" or "Which volunteers have birthdays in March?" and receive intelligent responses based on logged interactions
- **Team Care**: Better care for volunteers by remembering personal details across the entire team
- **Aggregate Insights**: Get team-wide insights like "What are the most common prayer requests?" or "Which volunteers prefer morning services?"

---

## Technical Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Framework** | Django 5.x | Built-in admin, auth, ORM, security features |
| **Database** | PostgreSQL 15+ with pgvector | Railway-native, vector search for semantic retrieval |
| **AI Provider** | Anthropic Claude API (claude-sonnet-4-20250514) | Excellent reasoning, context handling |
| **Vector Embeddings** | Anthropic Voyage or OpenAI text-embedding-3-small | Semantic search over interactions |
| **Frontend** | Django Templates + HTMX + Tailwind CSS | Simple, fast, minimal JavaScript |
| **Deployment** | Railway | Easy PostgreSQL, environment variables, GitHub integration |
| **Task Queue** | Django-Q2 or Celery (optional) | Background embedding generation |

---

## Database Schema

### Models

```python
# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """Extended user model for team members"""
    display_name = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return self.display_name or self.username


# core/models.py
from django.db import models
from django.conf import settings
from pgvector.django import VectorField

class Volunteer(models.Model):
    """
    Volunteer profiles - auto-created/linked when AI identifies 
    a volunteer in an interaction. Minimal structure, AI-driven.
    """
    name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200, db_index=True)  # lowercase for matching
    team = models.CharField(max_length=100, blank=True)  # vocals, band, tech, etc.
    planning_center_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Interaction(models.Model):
    """
    Append-only interaction log. Each entry is a team member's note
    about an encounter with one or more volunteers.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='interactions'
    )
    content = models.TextField(help_text="Free-form interaction notes")
    volunteers = models.ManyToManyField(
        Volunteer, 
        blank=True,
        related_name='interactions',
        help_text="Volunteers mentioned (auto-linked by AI)"
    )
    
    # AI-extracted metadata (populated by Claude after submission)
    ai_summary = models.TextField(blank=True, help_text="AI-generated summary")
    ai_extracted_data = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Structured data extracted by AI (hobbies, preferences, etc.)"
    )
    
    # Vector embedding for semantic search
    embedding = VectorField(dimensions=1536, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Interaction by {self.user} on {self.created_at.strftime('%Y-%m-%d')}"


class ChatMessage(models.Model):
    """
    Stores AI chat conversations for context and history.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    session_id = models.CharField(max_length=100, db_index=True)  # Group messages by session
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
```

### PostgreSQL with pgvector Setup

```sql
-- Run after initial migration
CREATE EXTENSION IF NOT EXISTS vector;

-- Create index for fast similarity search
CREATE INDEX ON core_interaction 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

---

## AI Agent Architecture

### Agent System Prompt

```python
SYSTEM_PROMPT = """You are the Cherry Hills Worship Arts Team Assistant. You help team members:
1. Log interactions with volunteers
2. Answer questions about volunteers based on logged interactions
3. Provide aggregate insights about the volunteer team

## Your Capabilities:
- When a user logs an interaction, extract and organize key information (names, preferences, prayer requests, feedback, etc.)
- When asked questions, search through past interactions to provide accurate answers
- Identify which volunteers are mentioned and link them appropriately
- Provide summaries and aggregate data when asked

## Guidelines:
- Be warm, helpful, and pastoral in tone
- Protect volunteer privacy - only share information with authenticated team members
- When uncertain, say so rather than guessing
- Format responses clearly with relevant details
- If asked about a volunteer with no logged interactions, say so clearly

## Data Extraction:
When processing a new interaction, extract and structure:
- Volunteer name(s) mentioned
- Personal details (hobbies, family, favorites, birthday, etc.)
- Prayer requests or concerns
- Feedback about services or team
- Availability or scheduling notes
- Any follow-up actions needed

## Context:
You have access to the following interaction history for context:
{context}

Current date: {current_date}
Team member asking: {user_name}
"""
```

### Agent Flow

```python
# core/agent.py
import anthropic
from django.conf import settings
from .models import Interaction, Volunteer
from .embeddings import get_embedding, search_similar

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

def process_interaction(content: str, user) -> dict:
    """
    Process a new interaction entry:
    1. Generate embedding
    2. Extract structured data via Claude
    3. Identify/create volunteer records
    4. Save interaction with metadata
    """
    
    # Step 1: Extract data with Claude
    extraction_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system="""Extract structured information from this volunteer interaction note.
        Return JSON with:
        {
            "volunteers": [{"name": "...", "team": "..."}],
            "summary": "brief summary",
            "extracted_data": {
                "hobbies": [],
                "favorites": {},
                "family": {},
                "prayer_requests": [],
                "feedback": [],
                "availability": null,
                "follow_up_needed": false,
                "other": {}
            }
        }""",
        messages=[{"role": "user", "content": content}]
    )
    
    extracted = parse_json_response(extraction_response)
    
    # Step 2: Generate embedding for semantic search
    embedding = get_embedding(content)
    
    # Step 3: Find or create volunteers
    volunteers = []
    for vol_data in extracted.get('volunteers', []):
        volunteer, _ = Volunteer.objects.get_or_create(
            normalized_name=vol_data['name'].lower().strip(),
            defaults={
                'name': vol_data['name'],
                'team': vol_data.get('team', '')
            }
        )
        volunteers.append(volunteer)
    
    # Step 4: Create interaction
    interaction = Interaction.objects.create(
        user=user,
        content=content,
        ai_summary=extracted.get('summary', ''),
        ai_extracted_data=extracted.get('extracted_data', {}),
        embedding=embedding
    )
    interaction.volunteers.set(volunteers)
    
    return {
        'interaction': interaction,
        'extracted': extracted,
        'volunteers': volunteers
    }


def query_agent(question: str, user, session_id: str) -> str:
    """
    Answer a question using RAG (Retrieval Augmented Generation):
    1. Search for relevant interactions
    2. Build context
    3. Query Claude with context
    """
    
    # Step 1: Get question embedding and find relevant interactions
    question_embedding = get_embedding(question)
    relevant_interactions = search_similar(question_embedding, limit=20)
    
    # Step 2: Build context from relevant interactions
    context_parts = []
    for interaction in relevant_interactions:
        volunteers = ", ".join([v.name for v in interaction.volunteers.all()])
        context_parts.append(f"""
--- Interaction from {interaction.created_at.strftime('%Y-%m-%d')} ---
Volunteers: {volunteers or 'Not specified'}
Notes: {interaction.content}
Summary: {interaction.ai_summary}
Extracted Data: {interaction.ai_extracted_data}
""")
    
    context = "\n".join(context_parts) if context_parts else "No relevant interactions found."
    
    # Step 3: Get chat history for this session
    from .models import ChatMessage
    history = ChatMessage.objects.filter(
        user=user, 
        session_id=session_id
    ).order_by('created_at')[:20]
    
    messages = [{"role": msg.role, "content": msg.content} for msg in history]
    messages.append({"role": "user", "content": question})
    
    # Step 4: Query Claude
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=SYSTEM_PROMPT.format(
            context=context,
            current_date=datetime.now().strftime('%Y-%m-%d'),
            user_name=user.display_name or user.username
        ),
        messages=messages
    )
    
    answer = response.content[0].text
    
    # Step 5: Save to chat history
    ChatMessage.objects.create(user=user, session_id=session_id, role='user', content=question)
    ChatMessage.objects.create(user=user, session_id=session_id, role='assistant', content=answer)
    
    return answer
```

### Embeddings Module

```python
# core/embeddings.py
import anthropic
# Or use OpenAI for embeddings (often more cost-effective)
from openai import OpenAI
from django.conf import settings
from pgvector.django import CosineDistance

# Option 1: OpenAI embeddings (recommended for cost)
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

def get_embedding(text: str) -> list[float]:
    """Generate embedding vector for text"""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def search_similar(query_embedding: list[float], limit: int = 10):
    """Find interactions most similar to query"""
    from .models import Interaction
    
    return Interaction.objects.annotate(
        distance=CosineDistance('embedding', query_embedding)
    ).order_by('distance')[:limit]
```

---

## URL Structure

```python
# config/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('core.urls')),
]

# core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('chat/', views.chat, name='chat'),
    path('chat/send/', views.chat_send, name='chat_send'),
    path('chat/new/', views.chat_new_session, name='chat_new_session'),
    path('interactions/', views.interaction_list, name='interaction_list'),
    path('interactions/<int:pk>/', views.interaction_detail, name='interaction_detail'),
    path('volunteers/', views.volunteer_list, name='volunteer_list'),
    path('volunteers/<int:pk>/', views.volunteer_detail, name='volunteer_detail'),
]

# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
```

---

## UI/UX Design Specifications

### Design System (Based on Cherry Hills Aesthetic)

```css
/* Dark mode color palette */
:root {
    --bg-primary: #0f0f0f;        /* Near black background */
    --bg-secondary: #1a1a1a;      /* Card/panel background */
    --bg-tertiary: #252525;       /* Hover states */
    --text-primary: #ffffff;       /* Main text */
    --text-secondary: #a0a0a0;    /* Muted text */
    --accent-primary: #c9a227;    /* Gold accent (warm, inviting) */
    --accent-secondary: #8b7355;  /* Muted gold */
    --border-color: #333333;      /* Subtle borders */
    --success: #22c55e;           /* Green for success states */
    --error: #ef4444;             /* Red for errors */
}

/* Typography */
--font-primary: 'Inter', system-ui, sans-serif;
--font-display: 'Playfair Display', serif;  /* For headings */
```

### Tailwind Config

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  content: ['./templates/**/*.html'],
  theme: {
    extend: {
      colors: {
        'ch-black': '#0f0f0f',
        'ch-dark': '#1a1a1a',
        'ch-gray': '#252525',
        'ch-gold': '#c9a227',
        'ch-gold-muted': '#8b7355',
      },
      fontFamily: {
        'display': ['Playfair Display', 'serif'],
      }
    }
  }
}
```

### Page Layouts

#### Base Template Structure
```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Worship Arts Portal{% endblock %} | Cherry Hills</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
</head>
<body class="bg-ch-black text-white min-h-screen">
    <!-- Sidebar Navigation -->
    <aside class="fixed left-0 top-0 h-full w-64 bg-ch-dark border-r border-gray-800 p-6">
        <div class="mb-8">
            <h1 class="font-display text-xl text-ch-gold">Cherry Hills</h1>
            <p class="text-sm text-gray-400">Worship Arts Portal</p>
        </div>
        <nav class="space-y-2">
            <a href="{% url 'dashboard' %}" class="nav-link">Dashboard</a>
            <a href="{% url 'chat' %}" class="nav-link">AI Assistant</a>
            <a href="{% url 'interaction_list' %}" class="nav-link">Interactions</a>
            <a href="{% url 'volunteer_list' %}" class="nav-link">Volunteers</a>
        </nav>
        <div class="absolute bottom-6 left-6 right-6">
            <p class="text-sm text-gray-500">{{ user.display_name }}</p>
            <a href="{% url 'logout' %}" class="text-sm text-gray-400 hover:text-white">Logout</a>
        </div>
    </aside>
    
    <!-- Main Content -->
    <main class="ml-64 p-8">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

#### Chat Interface
```html
<!-- templates/core/chat.html -->
{% extends 'base.html' %}

{% block content %}
<div class="max-w-4xl mx-auto">
    <div class="flex justify-between items-center mb-6">
        <h2 class="font-display text-2xl">AI Assistant</h2>
        <button hx-post="{% url 'chat_new_session' %}" 
                hx-target="#chat-messages"
                class="px-4 py-2 bg-ch-gray hover:bg-ch-gold hover:text-black rounded transition">
            New Conversation
        </button>
    </div>
    
    <!-- Chat Messages -->
    <div id="chat-messages" class="bg-ch-dark rounded-lg p-6 h-[500px] overflow-y-auto mb-4 space-y-4">
        {% for message in messages %}
        <div class="{% if message.role == 'user' %}ml-12{% else %}mr-12{% endif %}">
            <div class="{% if message.role == 'user' %}bg-ch-gold text-black{% else %}bg-ch-gray{% endif %} rounded-lg p-4">
                {{ message.content|linebreaks }}
            </div>
            <p class="text-xs text-gray-500 mt-1">{{ message.created_at|timesince }} ago</p>
        </div>
        {% empty %}
        <div class="text-center text-gray-400 py-12">
            <p class="mb-2">Welcome! I'm here to help you:</p>
            <ul class="text-sm space-y-1">
                <li>📝 Log interactions with volunteers</li>
                <li>🔍 Find information about volunteers</li>
                <li>📊 Get team insights and summaries</li>
            </ul>
        </div>
        {% endfor %}
    </div>
    
    <!-- Input Form -->
    <form hx-post="{% url 'chat_send' %}" 
          hx-target="#chat-messages" 
          hx-swap="beforeend"
          class="flex gap-4">
        {% csrf_token %}
        <input type="text" 
               name="message" 
               placeholder="Log an interaction or ask a question..."
               class="flex-1 bg-ch-dark border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-ch-gold"
               autocomplete="off">
        <button type="submit" 
                class="bg-ch-gold text-black px-6 py-3 rounded-lg font-medium hover:bg-yellow-500 transition">
            Send
        </button>
    </form>
    
    <!-- Quick Actions -->
    <div class="mt-4 flex gap-2 flex-wrap">
        <button class="quick-action" onclick="setMessage('Log interaction: ')">
            📝 Log Interaction
        </button>
        <button class="quick-action" onclick="setMessage('What do we know about ')">
            🔍 Find Volunteer
        </button>
        <button class="quick-action" onclick="setMessage('Show recent prayer requests')">
            🙏 Prayer Requests
        </button>
        <button class="quick-action" onclick="setMessage('Team summary for this month')">
            📊 Monthly Summary
        </button>
    </div>
</div>

<script>
function setMessage(text) {
    document.querySelector('input[name="message"]').value = text;
    document.querySelector('input[name="message"]').focus();
}
</script>
{% endblock %}
```

---

## Project Structure

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

## Configuration Files

### requirements.txt
```
Django>=5.0,<6.0
psycopg[binary]>=3.1
pgvector>=0.2.4
anthropic>=0.18.0
openai>=1.12.0
python-dotenv>=1.0.0
gunicorn>=21.2.0
whitenoise>=6.6.0
django-htmx>=1.17.0
```

### Procfile (Railway)
```
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
release: python manage.py migrate
```

### railway.toml
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"
healthcheckPath = "/health/"
healthcheckTimeout = 100
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

### .env.example
```
# Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-app.railway.app,localhost

# Database (Railway provides this automatically)
DATABASE_URL=postgres://...

# AI APIs
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...  # For embeddings (optional)

# Optional: Planning Center Integration
PLANNING_CENTER_APP_ID=
PLANNING_CENTER_SECRET=

# Web Push Notifications (VAPID keys)
# Generate with: npx web-push generate-vapid-keys
VAPID_PUBLIC_KEY=your-public-key-here
VAPID_PRIVATE_KEY=your-private-key-here
VAPID_CLAIMS_EMAIL=mailto:your-email@example.com
```

### Django Settings (Key Parts)

```python
# config/settings.py
import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-me')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_htmx',
    'accounts',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

# Database
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Auth
AUTH_USER_MODEL = 'accounts.User'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_URL = '/accounts/login/'

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security (for production)
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

---

## Deployment Instructions

### 1. GitHub Repository Setup
```bash
# Initialize repository
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/worship-arts-portal.git
git push -u origin main
```

### 2. Railway Deployment
1. Go to [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Add PostgreSQL: Click "New" → "Database" → "PostgreSQL"
5. Set environment variables in Railway dashboard:
   - `SECRET_KEY` (generate a secure random string)
   - `ANTHROPIC_API_KEY` (from Anthropic console)
   - `OPENAI_API_KEY` (optional, for embeddings)
   - `DEBUG=False`
   - `ALLOWED_HOSTS=your-app.railway.app`

### 3. Enable pgvector
After deployment, connect to your Railway PostgreSQL and run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 4. Create Admin User
```bash
# In Railway CLI or console
python manage.py createsuperuser
```

---

## Optional: Planning Center Integration

### Service Type Configuration

The system defaults to **Cherry Hills Morning Main** service when no specific service type is requested. This ensures queries like "Who was on the team last Sunday?" return the main Sunday service, not youth services.

```python
# core/planning_center.py

# Default service type for plan lookups
DEFAULT_SERVICE_TYPE_NAME = 'Cherry Hills Morning Main'

# Keywords that identify youth/non-main services (case-insensitive)
YOUTH_SERVICE_KEYWORDS = ['hsm', 'msm', 'high school', 'middle school', 'youth', 'student']
```

**Service Type Detection:**
- `HSM` or `high school` → High School Ministry
- `MSM` or `middle school` → Middle School Ministry
- No service specified → Cherry Hills Morning Main (default)

**Examples:**
| Query | Service Type Returned |
|-------|----------------------|
| "Who was on the team November 16?" | Cherry Hills Morning Main |
| "What songs were played last Easter?" | Cherry Hills Morning Main |
| "Who was serving at HSM last Sunday?" | High School Ministry |
| "MSM team for November 16" | Middle School Ministry |

### Optimized Date Lookups

The system uses an efficient two-step search for date-based queries:

1. **Exact Date Search**: First searches for plans on the exact calculated date
2. **Expanded Window**: If no match, expands to ±14 days (2 weeks)

This dramatically reduces API calls compared to fetching many plans and filtering locally.

```python
# Efficient target date search
def find_plans_for_target_date(self, target_date, window_days: int = 0) -> list:
    """
    Search for plans on a specific date using PCO's date filters.

    Args:
        target_date: The target date (datetime.date object)
        window_days: Days before/after to search (0 = exact date only)
    """
```

**Supported Date Formats:**
- Relative: `last Sunday`, `this Sunday`, `next Sunday`, `yesterday`, `today`
- Holidays: `Easter`, `last Easter`, `Easter 2024`, `Thanksgiving`, `Christmas Eve`
- Specific: `November 16`, `11/16/2025`, `2025-11-16`

### Basic API Usage

```python
# core/planning_center.py
import requests
from django.conf import settings

class PlanningCenterAPI:
    BASE_URL = "https://api.planningcenteronline.com"
    
    def __init__(self):
        self.app_id = settings.PLANNING_CENTER_APP_ID
        self.secret = settings.PLANNING_CENTER_SECRET
    
    def get_people(self, team_id=None):
        """Fetch people from Planning Center"""
        url = f"{self.BASE_URL}/services/v2/teams/{team_id}/people" if team_id else f"{self.BASE_URL}/people/v2/people"
        response = requests.get(url, auth=(self.app_id, self.secret))
        return response.json()
    
    def sync_volunteers(self):
        """Sync Planning Center people with local Volunteer records"""
        from .models import Volunteer
        
        data = self.get_people()
        for person in data.get('data', []):
            attrs = person['attributes']
            Volunteer.objects.update_or_create(
                planning_center_id=person['id'],
                defaults={
                    'name': f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip(),
                    'normalized_name': f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip().lower()
                }
            )
```

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

### Querying Information
**User Question:**
> "What volunteers have kids starting school soon?"

**AI Response:**
> "Based on recent interactions, Sarah Johnson mentioned her daughter Emma is starting kindergarten next month. She expressed some nervousness about this transition. This might be a good opportunity to check in with her and offer support."

### Aggregate Query
**User Question:**
> "What are the most common hobbies among our volunteers?"

**AI Response:**
> "Based on logged interactions, here are the most mentioned hobbies:
> 1. Gardening (mentioned by Sarah Johnson, Mike Peters)
> 2. Hiking (mentioned by David Lee, Amy Chen, Mike Peters)
> 3. Reading (mentioned by Lisa Brown, David Lee)
> Would you like more details about any of these?"

---

## Scalability Considerations

1. **Database**: PostgreSQL on Railway scales automatically. For >1000 volunteers, consider adding more vector index lists.

2. **Embeddings**: Process in background using Django-Q2 to avoid blocking requests.

3. **Caching**: Add Redis for caching frequent queries (volunteer lists, recent interactions).

4. **API Costs**: 
   - Claude Sonnet: ~$0.003-0.015 per query
   - OpenAI Embeddings: ~$0.0001 per embedding
   - Estimated monthly cost for moderate use: $10-30

5. **Rate Limiting**: Add django-ratelimit for API endpoints.

---

## Security Notes

- All routes require authentication (LoginRequiredMixin)
- CSRF protection enabled for all forms
- SQL injection prevented via Django ORM
- XSS prevented via Django template escaping
- HTTPS enforced in production
- Environment variables for all secrets
- Append-only interactions for audit trail

---

## Implemented Features

The following features have been implemented:

- [x] **PWA with Push Notifications**: Real-time notifications on mobile and desktop
- [x] **Team Communication Hub**: Announcements, channels, and direct messages
- [x] **Project & Task Management**: Kanban-style task boards with assignments
- [x] **Analytics Dashboard**: Comprehensive reporting and insights
- [x] **Proactive Care System**: AI-powered volunteer care alerts
- [x] **Follow-up Management**: Track and manage volunteer follow-ups
- [x] **@Mentions**: Tag team members in channels and task comments

---

## Future Enhancements

1. **Planning Center OAuth**: Full two-way sync with OAuth authentication
2. **Email Notifications**: Email digest for prayer requests and follow-ups
3. **PDF Reports**: Monthly PDF reports of team interactions
4. **Voice Input**: Speech-to-text for quick interaction logging
5. **Team Permissions**: Role-based access control (admin, leader, member)
6. **Calendar Integration**: Sync tasks and due dates with Google/Outlook calendars
7. **Recurring Tasks**: Support for recurring task templates
8. **File Attachments**: Attach files to tasks and messages
9. **Search**: Global search across interactions, messages, and tasks
10. **Mobile App**: Native mobile app with React Native (PWA already available)
