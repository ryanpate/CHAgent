# Cherry Hills Worship Arts Team Portal

## Project Overview

A private web application for the Cherry Hills Church Worship Arts team featuring **Aria**, an AI assistant powered by Claude that helps team members manage volunteer relationships, access Planning Center data, and track follow-up items.

### Core Purpose
- **AI Assistant (Aria)**: Ask questions about volunteers, schedules, songs, and team information
- **Planning Center Integration**: Direct access to PCO data for people, schedules, songs, chord charts, and lyrics
- **Volunteer Care**: Log interactions and track personal details to better care for volunteers
- **Follow-up Management**: Track action items, prayer requests, and reminders
- **Learning System**: Aria learns from feedback to improve responses over time

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

### Date Parsing
Aria understands many date formats:
- **Relative**: "last Sunday", "this Sunday", "next Sunday", "yesterday", "today"
- **Holidays**: "Easter", "last Easter", "Christmas Eve", "Thanksgiving"
- **Specific**: "November 16", "11/16/2025", "2025-11-16"

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
├── core/
│   ├── agent.py              # AI agent logic, query detection, RAG
│   ├── planning_center.py    # PCO API integration
│   ├── models.py             # Database models
│   ├── views.py              # View handlers
│   ├── urls.py               # URL routing
│   ├── embeddings.py         # Vector search
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
│   ├── settings.py
│   └── urls.py
└── accounts/
    └── models.py             # Custom User model
```

---

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

### Song/Person confusion
- Add "the song" to clearly indicate song queries
- Use full names for person queries

### First-name ambiguity
- Aria will show a list of matching people
- User selects which person they meant
