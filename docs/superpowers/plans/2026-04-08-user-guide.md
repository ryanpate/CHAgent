# User Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a comprehensive user guide accessible at `/guide/` and auto-seeded into each organization's Knowledge Base so Aria can answer "how do I..." questions about the platform.

**Architecture:** Guide content lives in `core/guide_content.py` as structured Python data. A view renders it as an HTML page at `/guide/`. A seeder function creates a Knowledge Base document from the same content. The seeder runs on org creation and via a management command for existing orgs.

**Tech Stack:** Django templates, Tailwind CSS, existing Knowledge Base pipeline (`process_document`).

**Spec:** `docs/superpowers/specs/2026-04-08-user-guide-design.md`

---

### Task 1: Guide content data

**Files:**
- Create: `core/guide_content.py`
- Create: `tests/test_user_guide.py`

- [ ] **Step 1: Write failing test for guide content structure**

```python
# tests/test_user_guide.py
import pytest
from core.guide_content import GUIDE_SECTIONS, GUIDE_GROUPS


class TestGuideContent:
    def test_guide_sections_exist(self):
        assert len(GUIDE_SECTIONS) >= 21

    def test_guide_groups_exist(self):
        assert len(GUIDE_GROUPS) == 3
        group_ids = [g['id'] for g in GUIDE_GROUPS]
        assert 'getting-started' in group_ids
        assert 'features' in group_ids
        assert 'admin' in group_ids

    def test_each_section_has_required_fields(self):
        for section in GUIDE_SECTIONS:
            assert 'id' in section, f"Section missing 'id': {section.get('title', 'unknown')}"
            assert 'title' in section
            assert 'content' in section
            assert 'plain_text' in section
            assert 'is_admin' in section
            assert 'group' in section

    def test_each_section_group_is_valid(self):
        valid_groups = {g['id'] for g in GUIDE_GROUPS}
        for section in GUIDE_SECTIONS:
            assert section['group'] in valid_groups, f"Section '{section['title']}' has invalid group '{section['group']}'"

    def test_admin_sections_flagged(self):
        admin_sections = [s for s in GUIDE_SECTIONS if s['is_admin']]
        assert len(admin_sections) >= 5
        admin_titles = [s['title'] for s in admin_sections]
        assert any('Settings' in t or 'Members' in t or 'Billing' in t or 'Security' in t or 'Planning Center' in t for t in admin_titles)

    def test_content_not_empty(self):
        for section in GUIDE_SECTIONS:
            assert len(section['content']) > 50, f"Section '{section['title']}' content too short"
            assert len(section['plain_text']) > 50, f"Section '{section['title']}' plain_text too short"

    def test_section_ids_unique(self):
        ids = [s['id'] for s in GUIDE_SECTIONS]
        assert len(ids) == len(set(ids)), "Duplicate section IDs found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_user_guide.py::TestGuideContent -v`
Expected: FAIL with `ImportError: cannot import name 'GUIDE_SECTIONS'`

- [ ] **Step 3: Create `core/guide_content.py` with all 21 sections**

```python
# core/guide_content.py
"""
User guide content for the ARIA platform.

This file is the single source of truth for guide content.
- templates/core/guide.html renders the 'content' field as HTML
- core/guide_seeder.py concatenates 'plain_text' fields for Knowledge Base
"""

GUIDE_GROUPS = [
    {'id': 'getting-started', 'title': 'Getting Started'},
    {'id': 'features', 'title': 'Features'},
    {'id': 'admin', 'title': 'Administration'},
]

GUIDE_SECTIONS = [
    # =========================================================================
    # Getting Started
    # =========================================================================
    {
        'id': 'welcome',
        'title': 'Welcome to ARIA',
        'group': 'getting-started',
        'is_admin': False,
        'content': """
        <p>ARIA is an AI-powered platform designed for worship arts teams. It helps you manage volunteer relationships, access Planning Center data, coordinate your team, and share creative work — all with the help of Aria, your AI assistant.</p>
        <p>Whether you're a worship leader, a band member, a tech volunteer, or a production crew member, ARIA gives you the tools to stay connected, organized, and inspired.</p>
        <h4>What Aria Can Help With</h4>
        <ul>
            <li><strong>Volunteer information</strong> — contact details, service history, personal notes</li>
            <li><strong>Schedules</strong> — who's serving this Sunday, team lineups, blockouts</li>
            <li><strong>Songs</strong> — setlists, lyrics, chord charts, song history</li>
            <li><strong>Team care</strong> — prayer requests, follow-ups, interaction history</li>
            <li><strong>Documents</strong> — procedures, checklists, and reference material you've uploaded</li>
        </ul>
        """,
        'plain_text': """Welcome to ARIA

ARIA is an AI-powered platform designed for worship arts teams. It helps you manage volunteer relationships, access Planning Center data, coordinate your team, and share creative work — all with the help of Aria, your AI assistant.

Whether you're a worship leader, a band member, a tech volunteer, or a production crew member, ARIA gives you the tools to stay connected, organized, and inspired.

What Aria Can Help With:
- Volunteer information — contact details, service history, personal notes
- Schedules — who's serving this Sunday, team lineups, blockouts
- Songs — setlists, lyrics, chord charts, song history
- Team care — prayer requests, follow-ups, interaction history
- Documents — procedures, checklists, and reference material you've uploaded""",
    },
    {
        'id': 'dashboard',
        'title': 'Your Dashboard',
        'group': 'getting-started',
        'is_admin': False,
        'content': """
        <p>Your dashboard is the home screen of ARIA. From here you can chat with Aria and navigate to every feature using the sidebar.</p>
        <h4>Sidebar Navigation</h4>
        <ul>
            <li><strong>Dashboard</strong> — home screen with Aria chat</li>
            <li><strong>Interactions</strong> — log and browse volunteer interactions</li>
            <li><strong>Volunteers</strong> — team member profiles and details</li>
            <li><strong>Follow-ups</strong> — action items, prayer requests, and reminders</li>
            <li><strong>Feedback</strong> — review and improve Aria's responses</li>
            <li><strong>Analytics</strong> — reports on engagement, care, and trends</li>
            <li><strong>Proactive Care</strong> — AI-generated care suggestions</li>
            <li><strong>Team Hub</strong> — announcements, channels, messages, and projects</li>
            <li><strong>My Tasks</strong> — personal task list across all projects</li>
            <li><strong>Song Submissions</strong> — suggest and vote on worship songs</li>
            <li><strong>Creative Studio</strong> — share and collaborate on creative work</li>
            <li><strong>Knowledge Base</strong> — uploaded documents Aria can reference</li>
        </ul>
        <p>At the bottom of the sidebar you'll find links to Notifications, Settings, and this Help guide.</p>
        """,
        'plain_text': """Your Dashboard

Your dashboard is the home screen of ARIA. From here you can chat with Aria and navigate to every feature using the sidebar.

Sidebar Navigation:
- Dashboard — home screen with Aria chat
- Interactions — log and browse volunteer interactions
- Volunteers — team member profiles and details
- Follow-ups — action items, prayer requests, and reminders
- Feedback — review and improve Aria's responses
- Analytics — reports on engagement, care, and trends
- Proactive Care — AI-generated care suggestions
- Team Hub — announcements, channels, messages, and projects
- My Tasks — personal task list across all projects
- Song Submissions — suggest and vote on worship songs
- Creative Studio — share and collaborate on creative work
- Knowledge Base — uploaded documents Aria can reference

At the bottom of the sidebar you'll find links to Notifications, Settings, and this Help guide.""",
    },
    {
        'id': 'chatting-with-aria',
        'title': 'Chatting with Aria',
        'group': 'getting-started',
        'is_admin': False,
        'content': """
        <p>Aria is your AI assistant, available from the Dashboard. You can ask questions in natural language and Aria will search your team's data to find answers.</p>
        <h4>How to Start</h4>
        <ol>
            <li>Go to the Dashboard</li>
            <li>Type your question in the chat box</li>
            <li>Aria will respond with relevant information from your team's data</li>
        </ol>
        <h4>Example Questions to Try</h4>
        <div class="bg-gray-800 rounded-lg p-4 space-y-2 text-sm">
            <p><em>"Who's on the team this Sunday?"</em></p>
            <p><em>"What's Sarah's email address?"</em></p>
            <p><em>"What songs did we play last Sunday?"</em></p>
            <p><em>"Show me the lyrics for Way Maker"</em></p>
            <p><em>"Who's blocked out on Easter?"</em></p>
            <p><em>"What are the most common prayer requests?"</em></p>
        </div>
        <h4>Tips for Best Results</h4>
        <ul>
            <li>Use full names when asking about a specific person (e.g., "Sarah Johnson" instead of just "Sarah")</li>
            <li>Add "the song" when asking about a song to avoid confusion with a person's name (e.g., "When did we last play the song Gratitude?")</li>
            <li>Aria understands dates like "this Sunday", "last Easter", "November 16", and "next week"</li>
            <li>Use the thumbs up/down buttons to give feedback on Aria's responses — this helps Aria improve over time</li>
        </ul>
        <h4>Starting a New Conversation</h4>
        <p>Click the "New Chat" button to start a fresh conversation. This clears the conversation history so Aria starts without prior context.</p>
        """,
        'plain_text': """Chatting with Aria

Aria is your AI assistant, available from the Dashboard. You can ask questions in natural language and Aria will search your team's data to find answers.

How to Start:
1. Go to the Dashboard
2. Type your question in the chat box
3. Aria will respond with relevant information from your team's data

Example Questions to Try:
- "Who's on the team this Sunday?"
- "What's Sarah's email address?"
- "What songs did we play last Sunday?"
- "Show me the lyrics for Way Maker"
- "Who's blocked out on Easter?"
- "What are the most common prayer requests?"

Tips for Best Results:
- Use full names when asking about a specific person (e.g., "Sarah Johnson" instead of just "Sarah")
- Add "the song" when asking about a song to avoid confusion with a person's name (e.g., "When did we last play the song Gratitude?")
- Aria understands dates like "this Sunday", "last Easter", "November 16", and "next week"
- Use the thumbs up/down buttons to give feedback on Aria's responses — this helps Aria improve over time

Starting a New Conversation:
Click the "New Chat" button to start a fresh conversation. This clears the conversation history so Aria starts without prior context.""",
    },
    {
        'id': 'first-interaction',
        'title': 'Logging Your First Interaction',
        'group': 'getting-started',
        'is_admin': False,
        'content': """
        <p>Interactions are the heart of ARIA. They're records of conversations, observations, and moments you share with your team members. Logging interactions helps your team care for volunteers better.</p>
        <h4>How to Log an Interaction</h4>
        <ol>
            <li>Go to <strong>Interactions</strong> in the sidebar</li>
            <li>Click <strong>Log Interaction</strong></li>
            <li>Write what happened — be as detailed as you'd like</li>
            <li>Submit the interaction</li>
        </ol>
        <h4>What Aria Extracts Automatically</h4>
        <p>When you log an interaction, Aria reads it and automatically extracts:</p>
        <ul>
            <li><strong>Hobbies and interests</strong> (e.g., "she loves gardening")</li>
            <li><strong>Family details</strong> (e.g., "her daughter Emma is starting kindergarten")</li>
            <li><strong>Prayer requests</strong></li>
            <li><strong>Follow-up items</strong> (e.g., "she wants to join the vocals team")</li>
        </ul>
        <p>This extracted information is stored on the volunteer's profile and helps Aria answer future questions about them.</p>
        <div class="bg-gray-800 rounded-lg p-4 text-sm">
            <p class="text-ch-gold font-semibold mb-2">Example Interaction</p>
            <p><em>"Talked with Sarah Johnson after service today. She mentioned her daughter Emma is starting kindergarten next month and she's nervous about it. Sarah loves gardening — her tomatoes are doing great this year. She might be interested in joining the vocals team in the fall."</em></p>
        </div>
        """,
        'plain_text': """Logging Your First Interaction

Interactions are the heart of ARIA. They're records of conversations, observations, and moments you share with your team members. Logging interactions helps your team care for volunteers better.

How to Log an Interaction:
1. Go to Interactions in the sidebar
2. Click Log Interaction
3. Write what happened — be as detailed as you'd like
4. Submit the interaction

What Aria Extracts Automatically:
When you log an interaction, Aria reads it and automatically extracts:
- Hobbies and interests (e.g., "she loves gardening")
- Family details (e.g., "her daughter Emma is starting kindergarten")
- Prayer requests
- Follow-up items (e.g., "she wants to join the vocals team")

This extracted information is stored on the volunteer's profile and helps Aria answer future questions about them.

Example Interaction:
"Talked with Sarah Johnson after service today. She mentioned her daughter Emma is starting kindergarten next month and she's nervous about it. Sarah loves gardening — her tomatoes are doing great this year. She might be interested in joining the vocals team in the fall.\"""",
    },
    # =========================================================================
    # Features
    # =========================================================================
    {
        'id': 'aria',
        'title': 'Aria (AI Assistant)',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>Aria is your team's AI assistant. She can answer questions about volunteers, schedules, songs, and anything you've uploaded to the Knowledge Base.</p>
        <h4>What Aria Knows</h4>
        <ul>
            <li><strong>Volunteer info</strong> — "What's John's email?" / "What are Mike's hobbies?" / "When did David last serve?"</li>
            <li><strong>Team rosters</strong> — "Who are the vocalists?" / "List the band members" / "How many guitar players do we have?"</li>
            <li><strong>Schedules</strong> — "Who's on the team this Sunday?" / "Phone numbers of people serving this weekend"</li>
            <li><strong>Songs &amp; setlists</strong> — "What songs did we play last Sunday?" / "Lyrics for Amazing Grace" / "Chord chart for Goodness of God" / "What key is Holy Spirit in?"</li>
            <li><strong>Blockouts &amp; availability</strong> — "Who's blocked out on December 14th?" / "Is Sarah available next Sunday?"</li>
            <li><strong>Aggregate insights</strong> — "What are the most common prayer requests?" / "Team summary for November"</li>
            <li><strong>Knowledge Base</strong> — "How do I turn on the sound board?" / "What's the lighting setup procedure?"</li>
        </ul>
        <h4>Smart Disambiguation</h4>
        <p>If your question is ambiguous, Aria will ask for clarification. For example, asking "When did we last play Gratitude?" might prompt Aria to ask whether you mean the song or a person named Gratitude.</p>
        <h4>Improving Aria</h4>
        <p>After each response, you can click the thumbs up or thumbs down button. Negative feedback lets you specify what went wrong (missing info, wrong volunteer, etc.), and Aria learns from this feedback over time.</p>
        """,
        'plain_text': """Aria (AI Assistant)

Aria is your team's AI assistant. She can answer questions about volunteers, schedules, songs, and anything you've uploaded to the Knowledge Base.

What Aria Knows:
- Volunteer info — "What's John's email?" / "What are Mike's hobbies?" / "When did David last serve?"
- Team rosters — "Who are the vocalists?" / "List the band members" / "How many guitar players do we have?"
- Schedules — "Who's on the team this Sunday?" / "Phone numbers of people serving this weekend"
- Songs & setlists — "What songs did we play last Sunday?" / "Lyrics for Amazing Grace" / "Chord chart for Goodness of God" / "What key is Holy Spirit in?"
- Blockouts & availability — "Who's blocked out on December 14th?" / "Is Sarah available next Sunday?"
- Aggregate insights — "What are the most common prayer requests?" / "Team summary for November"
- Knowledge Base — "How do I turn on the sound board?" / "What's the lighting setup procedure?"

Smart Disambiguation:
If your question is ambiguous, Aria will ask for clarification. For example, asking "When did we last play Gratitude?" might prompt Aria to ask whether you mean the song or a person named Gratitude.

Improving Aria:
After each response, you can click the thumbs up or thumbs down button. Negative feedback lets you specify what went wrong (missing info, wrong volunteer, etc.), and Aria learns from this feedback over time.""",
    },
    {
        'id': 'interactions',
        'title': 'Interactions',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>Interactions are records of your conversations and encounters with team members. They're the primary way ARIA builds knowledge about your volunteers.</p>
        <ul>
            <li><strong>Browse</strong> — view all logged interactions, search by keyword or volunteer name</li>
            <li><strong>View details</strong> — see Aria's AI summary, extracted data (hobbies, family, preferences), and linked volunteers</li>
            <li><strong>Create</strong> — log a new interaction from the Interactions page or by telling Aria (e.g., "Log interaction: Talked with Sarah...")</li>
        </ul>
        <p>Each interaction is automatically analyzed by Aria, who extracts structured information and stores it on the volunteer's profile. This means the more interactions you log, the better Aria knows your team.</p>
        """,
        'plain_text': """Interactions

Interactions are records of your conversations and encounters with team members. They're the primary way ARIA builds knowledge about your volunteers.

- Browse — view all logged interactions, search by keyword or volunteer name
- View details — see Aria's AI summary, extracted data (hobbies, family, preferences), and linked volunteers
- Create — log a new interaction from the Interactions page or by telling Aria (e.g., "Log interaction: Talked with Sarah...")

Each interaction is automatically analyzed by Aria, who extracts structured information and stores it on the volunteer's profile. This means the more interactions you log, the better Aria knows your team.""",
    },
    {
        'id': 'volunteers',
        'title': 'Volunteers',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>The Volunteers page shows all team members synced from Planning Center Online.</p>
        <ul>
            <li><strong>Browse profiles</strong> — see each volunteer's name, team, and contact info</li>
            <li><strong>Volunteer detail page</strong> — view interaction history, extracted knowledge (hobbies, family, preferences), and Planning Center data</li>
            <li><strong>Search</strong> — find volunteers by name or team</li>
        </ul>
        <p>Volunteer profiles are enriched over time as you log more interactions. Aria extracts and stores key details so you can quickly recall personal information when you need it.</p>
        """,
        'plain_text': """Volunteers

The Volunteers page shows all team members synced from Planning Center Online.

- Browse profiles — see each volunteer's name, team, and contact info
- Volunteer detail page — view interaction history, extracted knowledge (hobbies, family, preferences), and Planning Center data
- Search — find volunteers by name or team

Volunteer profiles are enriched over time as you log more interactions. Aria extracts and stores key details so you can quickly recall personal information when you need it.""",
    },
    {
        'id': 'followups',
        'title': 'Follow-ups',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>Follow-ups help you track action items, prayer requests, and reminders for your team members.</p>
        <h4>Creating Follow-ups</h4>
        <ul>
            <li>From the <strong>Follow-ups</strong> page, click <strong>Create Follow-up</strong></li>
            <li>From an interaction — Aria may automatically suggest follow-ups based on what you logged</li>
            <li>From a Proactive Care insight — convert a care suggestion into a follow-up</li>
        </ul>
        <h4>Follow-up Details</h4>
        <ul>
            <li><strong>Categories</strong> — prayer request, concern, action item, or feedback</li>
            <li><strong>Priority</strong> — low, medium, high, or urgent</li>
            <li><strong>Status</strong> — pending, in progress, completed, or cancelled</li>
            <li><strong>Follow-up date</strong> — set a date for when you need to follow up</li>
            <li><strong>Assignment</strong> — assign to yourself or another team member</li>
        </ul>
        <p>When a follow-up date arrives, you'll receive a push notification reminder (if notifications are enabled). You can also view all your follow-ups from the Follow-ups page, filtered by status or priority.</p>
        """,
        'plain_text': """Follow-ups

Follow-ups help you track action items, prayer requests, and reminders for your team members.

Creating Follow-ups:
- From the Follow-ups page, click Create Follow-up
- From an interaction — Aria may automatically suggest follow-ups based on what you logged
- From a Proactive Care insight — convert a care suggestion into a follow-up

Follow-up Details:
- Categories — prayer request, concern, action item, or feedback
- Priority — low, medium, high, or urgent
- Status — pending, in progress, completed, or cancelled
- Follow-up date — set a date for when you need to follow up
- Assignment — assign to yourself or another team member

When a follow-up date arrives, you'll receive a push notification reminder (if notifications are enabled). You can also view all your follow-ups from the Follow-ups page, filtered by status or priority.""",
    },
    {
        'id': 'team-hub',
        'title': 'Team Hub',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>The Team Hub is your central place for team communication. It brings together announcements, discussion channels, and direct messages.</p>
        <h4>Announcements</h4>
        <p>Team-wide broadcasts from leaders. Announcements can be normal, important, or urgent priority. Important announcements can be pinned to stay at the top.</p>
        <h4>Channels</h4>
        <p>Topic-based discussion spaces for your team. Channels can be public (everyone can see) or private (invite only). You can post messages, reply in threads, @mention team members, and attach files (images and documents up to 10 MB).</p>
        <h4>Direct Messages</h4>
        <p>Private one-on-one conversations with other team members. You can see read status and reply in threads.</p>
        """,
        'plain_text': """Team Hub

The Team Hub is your central place for team communication. It brings together announcements, discussion channels, and direct messages.

Announcements:
Team-wide broadcasts from leaders. Announcements can be normal, important, or urgent priority. Important announcements can be pinned to stay at the top.

Channels:
Topic-based discussion spaces for your team. Channels can be public (everyone can see) or private (invite only). You can post messages, reply in threads, @mention team members, and attach files (images and documents up to 10 MB).

Direct Messages:
Private one-on-one conversations with other team members. You can see read status and reply in threads.""",
    },
    {
        'id': 'projects-tasks',
        'title': 'Projects & Tasks',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>Organize your team's work with projects and tasks. Projects contain tasks organized on a visual Kanban board.</p>
        <h4>Projects</h4>
        <ul>
            <li>Create projects with a name, description, priority, and due date</li>
            <li>Add team members to a project</li>
            <li>Track progress automatically based on task completion</li>
            <li>Set up project discussions for broader conversations separate from task comments</li>
            <li>Create milestones for key deliverables</li>
        </ul>
        <h4>Tasks</h4>
        <ul>
            <li><strong>Status columns</strong> — To Do, In Progress, In Review, Completed</li>
            <li><strong>Subtasks</strong> — break tasks into smaller steps</li>
            <li><strong>Checklists</strong> — add checkbox items to a task</li>
            <li><strong>Assignments</strong> — assign one or more team members</li>
            <li><strong>Comments</strong> — discuss tasks with @mentions and file attachments</li>
            <li><strong>Decisions</strong> — mark important comments as decisions for easy reference</li>
            <li><strong>Watching</strong> — subscribe to a task for notifications without being assigned</li>
            <li><strong>Recurring tasks</strong> — set tasks to repeat weekly, biweekly, or monthly</li>
        </ul>
        <h4>Standalone Tasks</h4>
        <p>You can also create tasks outside of projects from the <strong>My Tasks</strong> page. These are great for personal to-do items or quick action items.</p>
        """,
        'plain_text': """Projects & Tasks

Organize your team's work with projects and tasks. Projects contain tasks organized on a visual Kanban board.

Projects:
- Create projects with a name, description, priority, and due date
- Add team members to a project
- Track progress automatically based on task completion
- Set up project discussions for broader conversations separate from task comments
- Create milestones for key deliverables

Tasks:
- Status columns — To Do, In Progress, In Review, Completed
- Subtasks — break tasks into smaller steps
- Checklists — add checkbox items to a task
- Assignments — assign one or more team members
- Comments — discuss tasks with @mentions and file attachments
- Decisions — mark important comments as decisions for easy reference
- Watching — subscribe to a task for notifications without being assigned
- Recurring tasks — set tasks to repeat weekly, biweekly, or monthly

Standalone Tasks:
You can also create tasks outside of projects from the My Tasks page. These are great for personal to-do items or quick action items.""",
    },
    {
        'id': 'creative-studio',
        'title': 'Creative Studio',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>The Creative Studio is a space for your team to share original creative work, collaborate on ideas, and inspire each other.</p>
        <h4>Posting Creative Work</h4>
        <ul>
            <li>Create a post with a title, type, and content (text, images, or audio)</li>
            <li><strong>Post types</strong> — lyrics, poem, artwork, audio, video concept, stage design, idea, devotional</li>
            <li><strong>Media</strong> — attach images, audio files (.mp3, .m4a, .wav), or documents</li>
            <li><strong>Tags</strong> — add comma-separated tags to help others find your work</li>
            <li><strong>Drafts</strong> — save work-in-progress posts as drafts (only visible to you)</li>
        </ul>
        <h4>Collaboration</h4>
        <ul>
            <li><strong>Reactions</strong> — respond with heart, fire, praying hands, clap, lightbulb, or star</li>
            <li><strong>Comments</strong> — leave feedback and encouragement with threaded replies</li>
            <li><strong>"Build on this"</strong> — create a new post linked to someone else's work (e.g., add a melody demo to someone's lyrics). Build chains show the creative evolution.</li>
            <li><strong>Collaboration flag</strong> — mark your post as "looking for collaborators" to invite others to contribute</li>
        </ul>
        <h4>Collections & Organization</h4>
        <ul>
            <li><strong>Collections</strong> — curated groupings like "Easter 2026" or "Songwriting Circle"</li>
            <li><strong>Filtering</strong> — filter the feed by post type, tag, or collection</li>
            <li><strong>My Work</strong> — view all your posts including drafts</li>
            <li><strong>Spotlights</strong> — leaders can spotlight standout work with an optional note of encouragement</li>
        </ul>
        """,
        'plain_text': """Creative Studio

The Creative Studio is a space for your team to share original creative work, collaborate on ideas, and inspire each other.

Posting Creative Work:
- Create a post with a title, type, and content (text, images, or audio)
- Post types — lyrics, poem, artwork, audio, video concept, stage design, idea, devotional
- Media — attach images, audio files (.mp3, .m4a, .wav), or documents
- Tags — add comma-separated tags to help others find your work
- Drafts — save work-in-progress posts as drafts (only visible to you)

Collaboration:
- Reactions — respond with heart, fire, praying hands, clap, lightbulb, or star
- Comments — leave feedback and encouragement with threaded replies
- "Build on this" — create a new post linked to someone else's work (e.g., add a melody demo to someone's lyrics). Build chains show the creative evolution.
- Collaboration flag — mark your post as "looking for collaborators" to invite others to contribute

Collections & Organization:
- Collections — curated groupings like "Easter 2026" or "Songwriting Circle"
- Filtering — filter the feed by post type, tag, or collection
- My Work — view all your posts including drafts
- Spotlights — leaders can spotlight standout work with an optional note of encouragement""",
    },
    {
        'id': 'song-submissions',
        'title': 'Song Submissions',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>The Song Submissions feature lets anyone on the team suggest new worship songs for consideration.</p>
        <ul>
            <li><strong>Submit a song</strong> — provide the song title, artist, and why you think it would be a good fit</li>
            <li><strong>View submissions</strong> — browse all submitted songs and their current status</li>
            <li><strong>Vote</strong> — upvote songs you'd like the team to play</li>
            <li><strong>Status tracking</strong> — submissions move through review stages (pending, approved, learning, in rotation, declined)</li>
        </ul>
        """,
        'plain_text': """Song Submissions

The Song Submissions feature lets anyone on the team suggest new worship songs for consideration.

- Submit a song — provide the song title, artist, and why you think it would be a good fit
- View submissions — browse all submitted songs and their current status
- Vote — upvote songs you'd like the team to play
- Status tracking — submissions move through review stages (pending, approved, learning, in rotation, declined)""",
    },
    {
        'id': 'analytics',
        'title': 'Analytics',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>The Analytics dashboard provides insights into your team's activity and engagement.</p>
        <h4>Available Reports</h4>
        <ul>
            <li><strong>Overview</strong> — key metrics and trends at a glance</li>
            <li><strong>Volunteer Engagement</strong> — participation rates and activity levels</li>
            <li><strong>Team Care</strong> — follow-up completion, prayer request trends</li>
            <li><strong>Interaction Trends</strong> — patterns in team interactions over time</li>
            <li><strong>Prayer Requests</strong> — aggregated prayer request data</li>
            <li><strong>AI Performance</strong> — Aria's response quality and feedback metrics</li>
        </ul>
        <h4>Exporting Data</h4>
        <p>You can export any report as a CSV file for further analysis. Click the Export button on any analytics page.</p>
        """,
        'plain_text': """Analytics

The Analytics dashboard provides insights into your team's activity and engagement.

Available Reports:
- Overview — key metrics and trends at a glance
- Volunteer Engagement — participation rates and activity levels
- Team Care — follow-up completion, prayer request trends
- Interaction Trends — patterns in team interactions over time
- Prayer Requests — aggregated prayer request data
- AI Performance — Aria's response quality and feedback metrics

Exporting Data:
You can export any report as a CSV file for further analysis. Click the Export button on any analytics page.""",
    },
    {
        'id': 'proactive-care',
        'title': 'Proactive Care',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>Proactive Care uses AI to identify volunteers who may need attention. The system analyzes interaction patterns and flags potential concerns.</p>
        <h4>Insight Types</h4>
        <ul>
            <li><strong>Missing/Inactive</strong> — volunteers who haven't been seen recently</li>
            <li><strong>Declining Engagement</strong> — decreasing participation over time</li>
            <li><strong>Prayer Request Follow-up</strong> — unresolved prayer requests</li>
            <li><strong>Celebration/Milestone</strong> — birthdays, anniversaries, achievements</li>
            <li><strong>General Concern</strong> — other patterns worth noting</li>
        </ul>
        <h4>Taking Action</h4>
        <p>For each insight, you can:</p>
        <ul>
            <li><strong>Create a follow-up</strong> — convert the insight into a trackable action item</li>
            <li><strong>Dismiss</strong> — if the insight isn't relevant, dismiss it from your dashboard</li>
        </ul>
        """,
        'plain_text': """Proactive Care

Proactive Care uses AI to identify volunteers who may need attention. The system analyzes interaction patterns and flags potential concerns.

Insight Types:
- Missing/Inactive — volunteers who haven't been seen recently
- Declining Engagement — decreasing participation over time
- Prayer Request Follow-up — unresolved prayer requests
- Celebration/Milestone — birthdays, anniversaries, achievements
- General Concern — other patterns worth noting

Taking Action:
For each insight, you can:
- Create a follow-up — convert the insight into a trackable action item
- Dismiss — if the insight isn't relevant, dismiss it from your dashboard""",
    },
    {
        'id': 'knowledge-base',
        'title': 'Knowledge Base',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>The Knowledge Base lets you upload documents that Aria can reference when answering questions. This is perfect for procedures, checklists, equipment guides, and reference materials.</p>
        <h4>Uploading Documents</h4>
        <ul>
            <li>Go to <strong>Knowledge Base</strong> in the sidebar</li>
            <li>Click <strong>Upload Document</strong></li>
            <li>Select a file (PDF, TXT, PNG, JPG, or JPEG — max 10 MB)</li>
            <li>Choose a category (optional) and add a description</li>
            <li>The document is processed automatically — text is extracted, chunked, and made searchable</li>
        </ul>
        <h4>How Aria Uses Documents</h4>
        <p>When you ask Aria a how-to or reference question, Aria searches your uploaded documents alongside interaction history. When Aria finds a relevant document, the response will cite the source document title.</p>
        <h4>Images in PDFs</h4>
        <p>If you upload a PDF with images (like diagrams or stage layouts), ARIA automatically extracts and describes them using AI. These images become searchable and Aria can show them inline in chat responses.</p>
        <h4>What to Upload</h4>
        <ul>
            <li>Equipment setup procedures (sound board, lighting, projectors)</li>
            <li>Volunteer onboarding checklists</li>
            <li>Team guidelines and policies</li>
            <li>Stage layout diagrams</li>
            <li>Song arrangement notes</li>
        </ul>
        """,
        'plain_text': """Knowledge Base

The Knowledge Base lets you upload documents that Aria can reference when answering questions. This is perfect for procedures, checklists, equipment guides, and reference materials.

Uploading Documents:
- Go to Knowledge Base in the sidebar
- Click Upload Document
- Select a file (PDF, TXT, PNG, JPG, or JPEG — max 10 MB)
- Choose a category (optional) and add a description
- The document is processed automatically — text is extracted, chunked, and made searchable

How Aria Uses Documents:
When you ask Aria a how-to or reference question, Aria searches your uploaded documents alongside interaction history. When Aria finds a relevant document, the response will cite the source document title.

Images in PDFs:
If you upload a PDF with images (like diagrams or stage layouts), ARIA automatically extracts and describes them using AI. These images become searchable and Aria can show them inline in chat responses.

What to Upload:
- Equipment setup procedures (sound board, lighting, projectors)
- Volunteer onboarding checklists
- Team guidelines and policies
- Stage layout diagrams
- Song arrangement notes""",
    },
    {
        'id': 'notifications',
        'title': 'Notifications',
        'group': 'features',
        'is_admin': False,
        'content': """
        <p>ARIA can send push notifications to keep you informed about team activity. Notifications work on both desktop browsers and the mobile app.</p>
        <h4>Setting Up Notifications</h4>
        <ol>
            <li>Click <strong>Notifications</strong> at the bottom of the sidebar</li>
            <li>Enable push notifications when prompted by your browser</li>
            <li>Configure which notification types you want to receive</li>
        </ol>
        <h4>Notification Types</h4>
        <ul>
            <li><strong>Announcements</strong> — new team announcements (with urgent-only option)</li>
            <li><strong>Direct Messages</strong> — new private messages</li>
            <li><strong>Channel Mentions</strong> — when someone @mentions you in a channel</li>
            <li><strong>Care Alerts</strong> — proactive care insights</li>
            <li><strong>Follow-up Reminders</strong> — when follow-up dates arrive</li>
            <li><strong>Task Updates</strong> — assigned tasks and comments on watched tasks</li>
            <li><strong>Song Submissions</strong> — new song suggestions</li>
            <li><strong>Creative Studio</strong> — new posts, comments on your work, builds, and spotlights</li>
        </ul>
        <h4>Quiet Hours</h4>
        <p>Set quiet hours to pause notifications during specific times (e.g., 10 PM to 7 AM). You can enable this from the Notifications settings page.</p>
        """,
        'plain_text': """Notifications

ARIA can send push notifications to keep you informed about team activity. Notifications work on both desktop browsers and the mobile app.

Setting Up Notifications:
1. Click Notifications at the bottom of the sidebar
2. Enable push notifications when prompted by your browser
3. Configure which notification types you want to receive

Notification Types:
- Announcements — new team announcements (with urgent-only option)
- Direct Messages — new private messages
- Channel Mentions — when someone @mentions you in a channel
- Care Alerts — proactive care insights
- Follow-up Reminders — when follow-up dates arrive
- Task Updates — assigned tasks and comments on watched tasks
- Song Submissions — new song suggestions
- Creative Studio — new posts, comments on your work, builds, and spotlights

Quiet Hours:
Set quiet hours to pause notifications during specific times (e.g., 10 PM to 7 AM). You can enable this from the Notifications settings page.""",
    },
    # =========================================================================
    # Admin
    # =========================================================================
    {
        'id': 'org-settings',
        'title': 'Organization Settings',
        'group': 'admin',
        'is_admin': True,
        'content': """
        <p>Organization settings let you customize your team's ARIA experience.</p>
        <ul>
            <li><strong>Organization name</strong> — your church or team name</li>
            <li><strong>AI assistant name</strong> — customize what your AI assistant is called (default: Aria)</li>
            <li><strong>Primary color</strong> — set your organization's accent color</li>
        </ul>
        <p>Access settings from the <strong>Settings</strong> link at the bottom of the sidebar.</p>
        """,
        'plain_text': """Organization Settings (Admin Only)

Organization settings let you customize your team's ARIA experience.

- Organization name — your church or team name
- AI assistant name — customize what your AI assistant is called (default: Aria)
- Primary color — set your organization's accent color

Access settings from the Settings link at the bottom of the sidebar.""",
    },
    {
        'id': 'managing-members',
        'title': 'Managing Members',
        'group': 'admin',
        'is_admin': True,
        'content': """
        <p>Manage your team members from Settings &gt; Members.</p>
        <h4>Inviting Members</h4>
        <p>Send email invitations to add new team members. They'll receive a link to create their account and join your organization.</p>
        <h4>Roles</h4>
        <ul>
            <li><strong>Owner</strong> — full control including billing and organization deletion</li>
            <li><strong>Admin</strong> — manage users, settings, and all features</li>
            <li><strong>Leader</strong> — manage volunteers, analytics, and spotlight creative posts</li>
            <li><strong>Member</strong> — standard access to all team features</li>
            <li><strong>Viewer</strong> — read-only access</li>
        </ul>
        <h4>Changing Roles</h4>
        <p>Click on a member's role to change it. Only owners and admins can modify roles.</p>
        <h4>Removing Members</h4>
        <p>Click the remove button next to a member to revoke their access. Their data (interactions, messages, etc.) will be preserved.</p>
        """,
        'plain_text': """Managing Members (Admin Only)

Manage your team members from Settings > Members.

Inviting Members:
Send email invitations to add new team members. They'll receive a link to create their account and join your organization.

Roles:
- Owner — full control including billing and organization deletion
- Admin — manage users, settings, and all features
- Leader — manage volunteers, analytics, and spotlight creative posts
- Member — standard access to all team features
- Viewer — read-only access

Changing Roles:
Click on a member's role to change it. Only owners and admins can modify roles.

Removing Members:
Click the remove button next to a member to revoke their access. Their data (interactions, messages, etc.) will be preserved.""",
    },
    {
        'id': 'billing',
        'title': 'Billing',
        'group': 'admin',
        'is_admin': True,
        'content': """
        <p>Manage your subscription from Settings &gt; Billing.</p>
        <h4>Plans</h4>
        <ul>
            <li><strong>Starter</strong> ($9.99/mo) — 5 users, 50 volunteers, PCO integration, push notifications</li>
            <li><strong>Team</strong> ($39.99/mo) — 15 users, 200 volunteers, plus analytics and care insights</li>
            <li><strong>Ministry</strong> ($79.99/mo) — unlimited users and volunteers, plus API access and custom branding</li>
            <li><strong>Enterprise</strong> (contact us) — multi-campus, priority support</li>
        </ul>
        <p>All plans are available with annual pricing at a discount. During the beta period, all features are free.</p>
        <h4>Managing Your Subscription</h4>
        <p>Click <strong>Manage Billing</strong> to open the Stripe customer portal where you can update payment methods, view invoices, and change plans.</p>
        """,
        'plain_text': """Billing (Admin Only)

Manage your subscription from Settings > Billing.

Plans:
- Starter ($9.99/mo) — 5 users, 50 volunteers, PCO integration, push notifications
- Team ($39.99/mo) — 15 users, 200 volunteers, plus analytics and care insights
- Ministry ($79.99/mo) — unlimited users and volunteers, plus API access and custom branding
- Enterprise (contact us) — multi-campus, priority support

All plans are available with annual pricing at a discount. During the beta period, all features are free.

Managing Your Subscription:
Click Manage Billing to open the Stripe customer portal where you can update payment methods, view invoices, and change plans.""",
    },
    {
        'id': 'security',
        'title': 'Security',
        'group': 'admin',
        'is_admin': True,
        'content': """
        <p>Protect your account with two-factor authentication (2FA).</p>
        <h4>Setting Up 2FA</h4>
        <ol>
            <li>Go to Settings &gt; Security</li>
            <li>Click <strong>Enable Two-Factor Authentication</strong></li>
            <li>Scan the QR code with your authenticator app (Google Authenticator, Authy, etc.)</li>
            <li>Enter the 6-digit code from your app to verify</li>
            <li>Save your backup codes in a safe place — these are one-time-use codes in case you lose access to your authenticator app</li>
        </ol>
        <h4>Logging In with 2FA</h4>
        <p>After enabling 2FA, you'll be asked for a 6-digit code each time you log in. Enter the code from your authenticator app or use a backup code.</p>
        <h4>Disabling 2FA</h4>
        <p>You can disable 2FA from Settings &gt; Security at any time.</p>
        """,
        'plain_text': """Security (Admin Only)

Protect your account with two-factor authentication (2FA).

Setting Up 2FA:
1. Go to Settings > Security
2. Click Enable Two-Factor Authentication
3. Scan the QR code with your authenticator app (Google Authenticator, Authy, etc.)
4. Enter the 6-digit code from your app to verify
5. Save your backup codes in a safe place — these are one-time-use codes in case you lose access to your authenticator app

Logging In with 2FA:
After enabling 2FA, you'll be asked for a 6-digit code each time you log in. Enter the code from your authenticator app or use a backup code.

Disabling 2FA:
You can disable 2FA from Settings > Security at any time.""",
    },
    {
        'id': 'planning-center',
        'title': 'Planning Center Integration',
        'group': 'admin',
        'is_admin': True,
        'content': """
        <p>ARIA connects to Planning Center Online (PCO) to pull in your team's data — people, schedules, songs, and availability.</p>
        <h4>Connecting PCO</h4>
        <ol>
            <li>Go to Settings &gt; General</li>
            <li>Enter your Planning Center App ID and Secret (from the PCO Developer portal)</li>
            <li>Save the settings</li>
        </ol>
        <h4>What Syncs from PCO</h4>
        <ul>
            <li><strong>People</strong> — team members with contact info</li>
            <li><strong>Schedules</strong> — who's serving on which dates</li>
            <li><strong>Songs</strong> — song library with lyrics, chord charts, keys, and BPM</li>
            <li><strong>Blockouts</strong> — when volunteers are unavailable</li>
        </ul>
        <h4>Troubleshooting</h4>
        <ul>
            <li>If data seems stale, Aria caches PCO data for performance. Ask Aria again and it will fetch fresh data.</li>
            <li>If you see rate limit errors (429), this usually resolves within a few minutes. PCO limits API calls per application.</li>
        </ul>
        """,
        'plain_text': """Planning Center Integration (Admin Only)

ARIA connects to Planning Center Online (PCO) to pull in your team's data — people, schedules, songs, and availability.

Connecting PCO:
1. Go to Settings > General
2. Enter your Planning Center App ID and Secret (from the PCO Developer portal)
3. Save the settings

What Syncs from PCO:
- People — team members with contact info
- Schedules — who's serving on which dates
- Songs — song library with lyrics, chord charts, keys, and BPM
- Blockouts — when volunteers are unavailable

Troubleshooting:
- If data seems stale, Aria caches PCO data for performance. Ask Aria again and it will fetch fresh data.
- If you see rate limit errors (429), this usually resolves within a few minutes. PCO limits API calls per application.""",
    },
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_user_guide.py::TestGuideContent -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/guide_content.py tests/test_user_guide.py
git commit -m "feat(guide): add user guide content data with 21 sections"
```

---

### Task 2: Guide view, URL, and template

**Files:**
- Modify: `core/views.py` (append view function)
- Modify: `core/urls.py` (add URL pattern)
- Create: `templates/core/guide.html`
- Modify: `tests/test_user_guide.py`

- [ ] **Step 1: Write failing tests for guide view**

```python
# tests/test_user_guide.py (append)
from django.test import Client


class TestGuideView:
    @pytest.fixture
    def client_alpha(self, db, user_alpha_owner, org_alpha):
        client = Client()
        client.force_login(user_alpha_owner)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    @pytest.fixture
    def member_client(self, db, user_alpha_member, org_alpha):
        client = Client()
        client.force_login(user_alpha_member)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    def test_guide_renders(self, client_alpha):
        response = client_alpha.get('/guide/')
        assert response.status_code == 200
        assert 'User Guide' in response.content.decode()

    def test_guide_shows_all_feature_sections(self, client_alpha):
        response = client_alpha.get('/guide/')
        content = response.content.decode()
        assert 'Welcome to ARIA' in content
        assert 'Chatting with Aria' in content
        assert 'Creative Studio' in content
        assert 'Knowledge Base' in content
        assert 'Notifications' in content

    def test_guide_admin_sections_visible_for_owner(self, client_alpha):
        response = client_alpha.get('/guide/')
        content = response.content.decode()
        assert 'Organization Settings' in content
        assert 'Managing Members' in content
        assert 'Billing' in content

    def test_guide_admin_sections_hidden_for_member(self, member_client):
        response = member_client.get('/guide/')
        content = response.content.decode()
        assert 'Organization Settings' not in content
        assert 'Managing Members' not in content
        assert 'Billing' not in content

    def test_guide_requires_login(self, db):
        client = Client()
        response = client.get('/guide/')
        assert response.status_code == 302
        assert '/accounts/login/' in response.url
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_user_guide.py::TestGuideView -v`
Expected: FAIL (404 — no URL pattern)

- [ ] **Step 3: Add view function to `core/views.py`**

Append to `core/views.py`:

```python
@login_required
def user_guide(request):
    """Render the comprehensive user guide page."""
    from .guide_content import GUIDE_SECTIONS, GUIDE_GROUPS

    membership = getattr(request, 'membership', None)
    is_admin = membership and membership.role in ('owner', 'admin') if membership else False

    sections = GUIDE_SECTIONS if is_admin else [s for s in GUIDE_SECTIONS if not s['is_admin']]
    groups = GUIDE_GROUPS if is_admin else [g for g in GUIDE_GROUPS if g['id'] != 'admin']

    context = {
        'sections': sections,
        'groups': groups,
        'is_admin': is_admin,
        'page_title': 'User Guide',
    }
    return render(request, 'core/guide.html', context)
```

- [ ] **Step 4: Add URL pattern to `core/urls.py`**

Insert before the closing `]` (currently at line 209):

```python
    # User Guide
    path('guide/', views.user_guide, name='user_guide'),
```

- [ ] **Step 5: Create `templates/core/guide.html`**

```html
{% extends 'base.html' %}
{% block title %}User Guide{% endblock %}
{% block content %}
<div class="max-w-7xl mx-auto px-4 py-6">
  <div class="flex gap-8">
    <!-- Table of Contents Sidebar -->
    <nav class="hidden lg:block w-64 flex-shrink-0">
      <div class="sticky top-6">
        <h2 class="text-lg font-bold text-white mb-4">User Guide</h2>
        {% for group in groups %}
        <div class="mb-4">
          <h3 class="text-ch-gold text-xs uppercase font-semibold mb-2">{{ group.title }}</h3>
          <div class="space-y-1">
            {% for section in sections %}
            {% if section.group == group.id %}
            <a href="#{{ section.id }}" class="block text-sm text-gray-400 hover:text-white transition py-0.5">
              {% if section.is_admin %}<span class="text-ch-gold text-xs">[Admin]</span> {% endif %}{{ section.title }}
            </a>
            {% endif %}
            {% endfor %}
          </div>
        </div>
        {% endfor %}
      </div>
    </nav>

    <!-- Mobile TOC -->
    <div class="lg:hidden mb-6 w-full" x-data="{ tocOpen: false }">
      <button @click="tocOpen = !tocOpen" class="w-full bg-ch-dark rounded-lg px-4 py-3 flex items-center justify-between text-white">
        <span class="font-semibold">Table of Contents</span>
        <svg class="w-5 h-5 transform transition" :class="{ 'rotate-180': tocOpen }" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
      </button>
      <div x-show="tocOpen" x-transition class="bg-ch-dark rounded-b-lg px-4 pb-4">
        {% for group in groups %}
        <div class="mb-3">
          <h3 class="text-ch-gold text-xs uppercase font-semibold mb-1">{{ group.title }}</h3>
          {% for section in sections %}
          {% if section.group == group.id %}
          <a href="#{{ section.id }}" @click="tocOpen = false" class="block text-sm text-gray-400 hover:text-white py-0.5">{{ section.title }}</a>
          {% endif %}
          {% endfor %}
        </div>
        {% endfor %}
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 min-w-0 max-w-3xl">
      <h1 class="text-3xl font-bold text-white mb-2 lg:hidden">User Guide</h1>
      {% for section in sections %}
      <section id="{{ section.id }}" class="mb-10 scroll-mt-6 {% if section.is_admin %}border-l-4 border-ch-gold pl-6{% endif %}">
        <div class="flex items-center gap-2 mb-3">
          <h2 class="text-xl font-bold text-white">{{ section.title }}</h2>
          {% if section.is_admin %}
          <span class="text-xs bg-ch-gold/20 text-ch-gold px-2 py-0.5 rounded font-semibold">Admin</span>
          {% endif %}
        </div>
        <div class="prose prose-invert prose-sm max-w-none text-gray-300 [&_h4]:text-white [&_h4]:font-semibold [&_h4]:mt-4 [&_h4]:mb-2 [&_ul]:space-y-1 [&_ol]:space-y-1 [&_li]:text-gray-300 [&_strong]:text-white [&_p]:mb-3 [&_em]:text-gray-400">
          {{ section.content|safe }}
        </div>
      </section>
      {% endfor %}
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_user_guide.py -v`
Expected: All 12 tests PASS (7 content + 5 view)

- [ ] **Step 7: Commit**

```bash
git add core/views.py core/urls.py templates/core/guide.html tests/test_user_guide.py
git commit -m "feat(guide): add /guide/ page with TOC sidebar and admin sections"
```

---

### Task 3: Sidebar "Help" link

**Files:**
- Modify: `templates/base.html` (lines ~512 and ~626)
- Modify: `tests/test_user_guide.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_user_guide.py (append)
class TestGuideSidebar:
    @pytest.fixture
    def client_alpha(self, db, user_alpha_owner, org_alpha):
        client = Client()
        client.force_login(user_alpha_owner)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    def test_help_link_in_sidebar(self, client_alpha):
        response = client_alpha.get('/guide/')
        content = response.content.decode()
        assert '/guide/' in content
        assert 'Help' in content
```

- [ ] **Step 2: Add Help link to mobile sidebar**

In `templates/base.html`, find the mobile sidebar's bottom section (around line 512, the `<div class="flex items-center gap-4">` with Notifications). Add before the Notifications link:

```html
                    <a href="{% url 'user_guide' %}" @click="sidebarOpen = false" class="text-gray-400 hover:text-white transition flex items-center gap-1">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        Help
                    </a>
```

- [ ] **Step 3: Add Help link to desktop sidebar**

In `templates/base.html`, find the desktop sidebar's bottom section (around line 626, the `<div class="flex items-center gap-4">` with Notifications). Add before the Notifications link:

```html
                    <a href="{% url 'user_guide' %}" class="text-gray-400 hover:text-white transition flex items-center gap-1">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        Help
                    </a>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_user_guide.py -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add templates/base.html tests/test_user_guide.py
git commit -m "feat(guide): add Help link to sidebar navigation"
```

---

### Task 4: Guide seeder and management command

**Files:**
- Create: `core/guide_seeder.py`
- Create: `core/management/commands/seed_guide.py`
- Modify: `tests/test_user_guide.py`

- [ ] **Step 1: Write failing tests for seeder**

```python
# tests/test_user_guide.py (append)
from core.models import Document, DocumentCategory, DocumentChunk


class TestGuideSeeder:
    def test_seed_creates_category(self, db, org_alpha):
        from core.guide_seeder import seed_guide_document
        seed_guide_document(org_alpha)
        assert DocumentCategory.objects.filter(
            organization=org_alpha, name='Help & Guides'
        ).exists()

    def test_seed_creates_document(self, db, org_alpha):
        from core.guide_seeder import seed_guide_document
        seed_guide_document(org_alpha)
        doc = Document.objects.filter(
            organization=org_alpha, title='Getting Started with ARIA'
        ).first()
        assert doc is not None
        assert doc.file_type == 'txt'
        assert len(doc.extracted_text) > 500

    def test_seed_is_idempotent(self, db, org_alpha):
        from core.guide_seeder import seed_guide_document
        seed_guide_document(org_alpha)
        seed_guide_document(org_alpha)
        assert Document.objects.filter(
            organization=org_alpha, title='Getting Started with ARIA'
        ).count() == 1

    def test_seed_creates_chunks(self, db, org_alpha):
        from core.guide_seeder import seed_guide_document
        seed_guide_document(org_alpha)
        doc = Document.objects.get(
            organization=org_alpha, title='Getting Started with ARIA'
        )
        assert DocumentChunk.objects.filter(document=doc).count() > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_user_guide.py::TestGuideSeeder -v`
Expected: FAIL with `ImportError: cannot import name 'seed_guide_document'`

- [ ] **Step 3: Create `core/guide_seeder.py`**

```python
# core/guide_seeder.py
"""Seed the user guide into an organization's Knowledge Base."""
import logging

from .guide_content import GUIDE_SECTIONS, GUIDE_GROUPS
from .models import Document, DocumentCategory

logger = logging.getLogger(__name__)

GUIDE_TITLE = 'Getting Started with ARIA'
GUIDE_CATEGORY = 'Help & Guides'


def _build_plain_text():
    """Concatenate all sections' plain_text into a single document."""
    parts = []
    for group in GUIDE_GROUPS:
        group_sections = [s for s in GUIDE_SECTIONS if s['group'] == group['id']]
        if group_sections:
            parts.append(f"{'=' * 60}")
            parts.append(group['title'].upper())
            parts.append(f"{'=' * 60}\n")
            for section in group_sections:
                parts.append(section['plain_text'].strip())
                parts.append('')  # blank line between sections
    return '\n'.join(parts)


def seed_guide_document(organization):
    """
    Create or skip the Getting Started guide in an org's Knowledge Base.

    Idempotent: skips if a document with the guide title already exists.
    """
    # Check if already seeded
    if Document.objects.filter(
        organization=organization, title=GUIDE_TITLE
    ).exists():
        logger.info(f"Guide already exists for {organization.name}, skipping")
        return None

    # Get or create category
    category, _ = DocumentCategory.objects.get_or_create(
        organization=organization,
        name=GUIDE_CATEGORY,
        defaults={'description': 'Help documentation and user guides'},
    )

    # Build plain text content
    plain_text = _build_plain_text()

    # Create document
    doc = Document.objects.create(
        organization=organization,
        title=GUIDE_TITLE,
        description='Comprehensive guide to all ARIA features for new and existing users.',
        category=category,
        file_type='txt',
        extracted_text=plain_text,
        processing_status='completed',
        page_count=1,
    )

    # Chunk and embed
    from .document_processing import chunk_text
    from .models import DocumentChunk
    from .embeddings import get_embedding
    import json

    chunks = chunk_text(plain_text)
    for i, chunk_text_content in enumerate(chunks):
        embedding = get_embedding(chunk_text_content)
        DocumentChunk.objects.create(
            document=doc,
            chunk_index=i,
            content=chunk_text_content,
            embedding_json=json.dumps(embedding) if embedding else None,
        )

    logger.info(f"Seeded guide for {organization.name}: {len(chunks)} chunks")
    return doc
```

- [ ] **Step 4: Create management command `core/management/commands/seed_guide.py`**

```python
# core/management/commands/seed_guide.py
"""
Seed the user guide into all active organizations' Knowledge Bases.

Usage:
    python manage.py seed_guide
"""
from django.core.management.base import BaseCommand

from core.guide_seeder import seed_guide_document
from core.models import Organization


class Command(BaseCommand):
    help = 'Seed the Getting Started guide into all active organizations'

    def handle(self, *args, **options):
        orgs = Organization.objects.filter(is_active=True)
        created = 0
        skipped = 0

        for org in orgs:
            result = seed_guide_document(org)
            if result:
                created += 1
                self.stdout.write(f"  Created guide for: {org.name}")
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Created: {created}, Skipped (already exists): {skipped}, Total orgs: {orgs.count()}"
        ))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_user_guide.py -v`
Expected: All 17 tests PASS

- [ ] **Step 6: Commit**

```bash
git add core/guide_seeder.py core/management/commands/seed_guide.py tests/test_user_guide.py
git commit -m "feat(guide): add guide seeder and seed_guide management command"
```

---

### Task 5: Hook seeder into beta signup

**Files:**
- Modify: `core/views.py:5441` (beta_signup function, after org creation)
- Modify: `tests/test_user_guide.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_user_guide.py (append)
class TestGuideSeedOnBetaSignup:
    def test_beta_signup_seeds_guide(self, db):
        from core.models import Organization, SubscriptionPlan, BetaRequest, Document

        plan = SubscriptionPlan.objects.create(
            name='Ministry', tier='ministry', is_active=True,
            price_monthly_cents=7999, price_yearly_cents=79900,
        )
        beta_req = BetaRequest.objects.create(
            name='Test User', email='test@church.org',
            church_name='Test Church', church_size='medium',
            status='approved',
        )

        client = Client()
        response = client.post('/beta/signup/?email=test@church.org', {
            'email': 'test@church.org',
            'password': 'TestPass123!',
            'first_name': 'Test',
            'last_name': 'User',
        })

        org = Organization.objects.get(name='Test Church')
        assert Document.objects.filter(
            organization=org, title='Getting Started with ARIA'
        ).exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_user_guide.py::TestGuideSeedOnBetaSignup -v`
Expected: FAIL (guide document doesn't exist after signup)

- [ ] **Step 3: Add seeder call to beta_signup view**

In `core/views.py`, find the `beta_signup` function. After the org creation and membership creation (around line 5434, after `user.save()`), add:

```python
        # Seed user guide into Knowledge Base
        try:
            from .guide_seeder import seed_guide_document
            seed_guide_document(org)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to seed guide for {org.name}: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_user_guide.py -v`
Expected: All 18 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_user_guide.py
git commit -m "feat(guide): auto-seed guide on beta signup org creation"
```

---

### Task 6: Run full test suite

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All 734+ existing tests pass, plus ~18 new guide tests, 0 failures

- [ ] **Step 2: Fix any regressions**

If any tests break, fix them.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve any test regressions from user guide feature"
```
