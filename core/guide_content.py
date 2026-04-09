"""
User guide content for the ARIA platform.

Contains all sections of the user guide organized into groups.
Used by the /guide/ view for rendering and by the Knowledge Base
seeder for making guide content searchable by Aria.
"""

GUIDE_GROUPS = [
    {
        'id': 'getting-started',
        'title': 'Getting Started',
        'icon': 'rocket',
    },
    {
        'id': 'features',
        'title': 'Features',
        'icon': 'star',
    },
    {
        'id': 'admin',
        'title': 'Administration',
        'icon': 'cog',
    },
]

GUIDE_SECTIONS = [
    # =========================================================================
    # GETTING STARTED
    # =========================================================================
    {
        'id': 'welcome',
        'title': 'Welcome to ARIA',
        'group': 'getting-started',
        'is_admin': False,
        'content': (
            '<p>ARIA is a platform built for worship arts teams that combines an AI assistant, '
            'volunteer care tools, and Planning Center integration into one place. Whether you '
            'lead a team of five or fifty, ARIA helps you stay connected to the people you serve with.</p>'
            '<p>At the heart of the platform is <strong>Aria</strong>, an AI assistant that knows '
            'your team. Aria can answer questions about volunteers, pull up schedules and setlists '
            'from Planning Center, find song details like keys and chord charts, and surface '
            'information from past interactions you have logged.</p>'
            '<h4>What you can do with ARIA</h4>'
            '<ul>'
            '<li><strong>Ask Aria anything</strong> about your volunteers, schedules, songs, and team history</li>'
            '<li><strong>Log interactions</strong> after conversations with volunteers and let Aria extract key details automatically</li>'
            '<li><strong>Track follow-ups</strong> so prayer requests, action items, and reminders never slip through the cracks</li>'
            '<li><strong>Browse your team</strong> with volunteer profiles synced from Planning Center</li>'
            '<li><strong>Upload documents</strong> to a Knowledge Base that Aria can reference when answering questions</li>'
            '<li><strong>Communicate with your team</strong> through announcements, channels, and direct messages</li>'
            '<li><strong>Manage projects and tasks</strong> with a Kanban board, assignments, and comments</li>'
            '</ul>'
            '<p>This guide walks through every feature so you can get the most out of the platform.</p>'
        ),
        'plain_text': (
            'ARIA is a platform built for worship arts teams that combines an AI assistant, '
            'volunteer care tools, and Planning Center integration into one place. Whether you '
            'lead a team of five or fifty, ARIA helps you stay connected to the people you serve with.\n\n'
            'At the heart of the platform is Aria, an AI assistant that knows your team. Aria can '
            'answer questions about volunteers, pull up schedules and setlists from Planning Center, '
            'find song details like keys and chord charts, and surface information from past '
            'interactions you have logged.\n\n'
            'What you can do with ARIA:\n'
            '- Ask Aria anything about your volunteers, schedules, songs, and team history\n'
            '- Log interactions after conversations with volunteers and let Aria extract key details automatically\n'
            '- Track follow-ups so prayer requests, action items, and reminders never slip through the cracks\n'
            '- Browse your team with volunteer profiles synced from Planning Center\n'
            '- Upload documents to a Knowledge Base that Aria can reference when answering questions\n'
            '- Communicate with your team through announcements, channels, and direct messages\n'
            '- Manage projects and tasks with a Kanban board, assignments, and comments\n\n'
            'This guide walks through every feature so you can get the most out of the platform.'
        ),
    },
    {
        'id': 'dashboard',
        'title': 'Your Dashboard',
        'group': 'getting-started',
        'is_admin': False,
        'content': (
            '<p>When you log in, you land on the dashboard. This is your home base with quick access '
            'to everything in the platform. The left sidebar is your primary navigation and stays '
            'visible on every page.</p>'
            '<h4>Sidebar Navigation</h4>'
            '<ul>'
            '<li><strong>Dashboard</strong> — your home screen with an overview of recent activity</li>'
            '<li><strong>Chat</strong> — talk to Aria, your AI assistant</li>'
            '<li><strong>Interactions</strong> — browse and create interaction logs with volunteers</li>'
            '<li><strong>Volunteers</strong> — view volunteer profiles synced from Planning Center</li>'
            '<li><strong>Follow-ups</strong> — manage action items, prayer requests, and reminders</li>'
            '<li><strong>Team Hub</strong> — announcements, channels, and direct messages</li>'
            '<li><strong>Projects</strong> — project boards and task management</li>'
            '<li><strong>Creative Studio</strong> — share and collaborate on creative ideas</li>'
            '<li><strong>Analytics</strong> — reports on engagement, care, trends, and AI performance</li>'
            '<li><strong>Care</strong> — proactive care dashboard with AI-generated insights</li>'
            '<li><strong>Knowledge Base</strong> — upload documents for Aria to reference</li>'
            '</ul>'
            '<p>At the bottom of the sidebar you will find <strong>Settings</strong> (organization, members, '
            'billing, security) and <strong>Notifications</strong> (push notification preferences).</p>'
            '<p>On mobile devices, the sidebar collapses into a hamburger menu in the top-left corner. '
            'Tap it to reveal the full navigation.</p>'
        ),
        'plain_text': (
            'When you log in, you land on the dashboard. This is your home base with quick access '
            'to everything in the platform. The left sidebar is your primary navigation and stays '
            'visible on every page.\n\n'
            'Sidebar Navigation:\n'
            '- Dashboard — your home screen with an overview of recent activity\n'
            '- Chat — talk to Aria, your AI assistant\n'
            '- Interactions — browse and create interaction logs with volunteers\n'
            '- Volunteers — view volunteer profiles synced from Planning Center\n'
            '- Follow-ups — manage action items, prayer requests, and reminders\n'
            '- Team Hub — announcements, channels, and direct messages\n'
            '- Projects — project boards and task management\n'
            '- Creative Studio — share and collaborate on creative ideas\n'
            '- Analytics — reports on engagement, care, trends, and AI performance\n'
            '- Care — proactive care dashboard with AI-generated insights\n'
            '- Knowledge Base — upload documents for Aria to reference\n\n'
            'At the bottom of the sidebar you will find Settings (organization, members, '
            'billing, security) and Notifications (push notification preferences).\n\n'
            'On mobile devices, the sidebar collapses into a hamburger menu in the top-left corner. '
            'Tap it to reveal the full navigation.'
        ),
    },
    {
        'id': 'chatting-with-aria',
        'title': 'Chatting with Aria',
        'group': 'getting-started',
        'is_admin': False,
        'content': (
            '<p>Aria is your AI assistant. Open the <strong>Chat</strong> page from the sidebar to start a '
            'conversation. Type your question in the message box and press Send. Aria will respond in '
            'a few seconds with an answer drawn from your interaction history, Planning Center data, '
            'and uploaded documents.</p>'
            '<h4>Example queries to try</h4>'
            '<div class="bg-gray-800 rounded-lg p-4 space-y-2 text-sm">'
            '<p>"What are Sarah Johnson\'s hobbies?"</p>'
            '<p>"Who\'s on the team this Sunday?"</p>'
            '<p>"When did we last play Goodness of God?"</p>'
            '<p>"Show me the chord chart for Way Maker"</p>'
            '<p>"What are the most common prayer requests?"</p>'
            '<p>"How do I set up the sound board?"</p>'
            '</div>'
            '<h4>Tips for better results</h4>'
            '<ul>'
            '<li>Use <strong>full names</strong> when asking about a specific person — "Sarah Johnson" works better than just "Sarah"</li>'
            '<li>Add <strong>"the song"</strong> to song queries to help Aria distinguish songs from people — "When did we last play the song Gratitude?"</li>'
            '<li>Aria understands many <strong>date formats</strong>: "last Sunday", "this Easter", "November 16", "next week"</li>'
            '<li>Use the <strong>thumbs up / thumbs down</strong> buttons on responses to help Aria improve over time</li>'
            '</ul>'
            '<p>To clear the conversation and start fresh, click <strong>New Conversation</strong> at the '
            'top of the chat page. Your past conversations are saved and continue to inform Aria\'s responses.</p>'
        ),
        'plain_text': (
            'Aria is your AI assistant. Open the Chat page from the sidebar to start a '
            'conversation. Type your question in the message box and press Send. Aria will respond in '
            'a few seconds with an answer drawn from your interaction history, Planning Center data, '
            'and uploaded documents.\n\n'
            'Example queries to try:\n'
            '- "What are Sarah Johnson\'s hobbies?"\n'
            '- "Who\'s on the team this Sunday?"\n'
            '- "When did we last play Goodness of God?"\n'
            '- "Show me the chord chart for Way Maker"\n'
            '- "What are the most common prayer requests?"\n'
            '- "How do I set up the sound board?"\n\n'
            'Tips for better results:\n'
            '- Use full names when asking about a specific person — "Sarah Johnson" works better than just "Sarah"\n'
            '- Add "the song" to song queries to help Aria distinguish songs from people — "When did we last play the song Gratitude?"\n'
            '- Aria understands many date formats: "last Sunday", "this Easter", "November 16", "next week"\n'
            '- Use the thumbs up / thumbs down buttons on responses to help Aria improve over time\n\n'
            'To clear the conversation and start fresh, click New Conversation at the '
            'top of the chat page. Your past conversations are saved and continue to inform Aria\'s responses.'
        ),
    },
    {
        'id': 'first-interaction',
        'title': 'Logging Your First Interaction',
        'group': 'getting-started',
        'is_admin': False,
        'content': (
            '<p>Interactions are the foundation of how Aria learns about your volunteers. Every time '
            'you have a meaningful conversation with someone on your team, logging it gives Aria '
            'context she can draw on later.</p>'
            '<h4>How to log an interaction</h4>'
            '<ol>'
            '<li>Go to <strong>Interactions</strong> in the sidebar</li>'
            '<li>Click <strong>Create Interaction</strong></li>'
            '<li>Write a free-form note about the conversation — include names, topics, and any personal '
            'details shared</li>'
            '<li>Click <strong>Save</strong></li>'
            '</ol>'
            '<p>After you save, Aria automatically processes the interaction and extracts structured data:</p>'
            '<ul>'
            '<li><strong>Hobbies and interests</strong> — "She mentioned she loves hiking"</li>'
            '<li><strong>Family information</strong> — "His daughter Emma is starting kindergarten"</li>'
            '<li><strong>Prayer requests</strong> — "Please pray for her mom\'s surgery next week"</li>'
            '<li><strong>Follow-up items</strong> — "He asked about joining the vocals team"</li>'
            '</ul>'
            '<h4>Example interaction</h4>'
            '<div class="bg-gray-800 rounded-lg p-4 space-y-2 text-sm">'
            '<p>"Talked with Sarah Johnson after service today. She mentioned her daughter Emma is starting '
            'kindergarten next month and she\'s nervous about it. Sarah loves gardening — her tomatoes are '
            'doing great this year. She might be interested in joining the vocals team in the fall."</p>'
            '</div>'
            '<p>From this single note, Aria extracts family info (daughter Emma, kindergarten), hobbies '
            '(gardening), and a potential follow-up (vocals team interest). The next time you or anyone '
            'on your team asks Aria about Sarah, this context is available instantly.</p>'
        ),
        'plain_text': (
            'Interactions are the foundation of how Aria learns about your volunteers. Every time '
            'you have a meaningful conversation with someone on your team, logging it gives Aria '
            'context she can draw on later.\n\n'
            'How to log an interaction:\n'
            '1. Go to Interactions in the sidebar\n'
            '2. Click Create Interaction\n'
            '3. Write a free-form note about the conversation — include names, topics, and any personal '
            'details shared\n'
            '4. Click Save\n\n'
            'After you save, Aria automatically processes the interaction and extracts structured data:\n'
            '- Hobbies and interests — "She mentioned she loves hiking"\n'
            '- Family information — "His daughter Emma is starting kindergarten"\n'
            '- Prayer requests — "Please pray for her mom\'s surgery next week"\n'
            '- Follow-up items — "He asked about joining the vocals team"\n\n'
            'Example interaction:\n'
            '"Talked with Sarah Johnson after service today. She mentioned her daughter Emma is starting '
            'kindergarten next month and she\'s nervous about it. Sarah loves gardening — her tomatoes are '
            'doing great this year. She might be interested in joining the vocals team in the fall."\n\n'
            'From this single note, Aria extracts family info (daughter Emma, kindergarten), hobbies '
            '(gardening), and a potential follow-up (vocals team interest). The next time you or anyone '
            'on your team asks Aria about Sarah, this context is available instantly.'
        ),
    },

    # =========================================================================
    # FEATURES
    # =========================================================================
    {
        'id': 'aria',
        'title': 'Aria (AI Assistant)',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>Aria is the AI assistant at the center of the platform. She draws on your interaction history, '
            'Planning Center data, and uploaded Knowledge Base documents to answer questions about your team.</p>'
            '<h4>What Aria can do</h4>'
            '<ul>'
            '<li><strong>Volunteer information</strong> — contact details, hobbies, family info, personal preferences</li>'
            '<li><strong>Team rosters</strong> — "Who are the vocalists?" or "List the band members"</li>'
            '<li><strong>Schedules</strong> — "Who\'s on the team this Sunday?" or "Who served on Easter?"</li>'
            '<li><strong>Songs and setlists</strong> — song history, lyrics, chord charts, keys, BPM</li>'
            '<li><strong>Blockouts and availability</strong> — "Who\'s blocked out on December 14th?"</li>'
            '<li><strong>Aggregate insights</strong> — "What are the most common prayer requests?" or "Team summary for November"</li>'
            '<li><strong>Knowledge Base</strong> — answers from uploaded documents like procedures, guides, and checklists</li>'
            '</ul>'
            '<h4>Disambiguation</h4>'
            '<p>When a query is ambiguous, Aria asks for clarification rather than guessing. If you search for '
            '"Emma" and there are multiple people named Emma, Aria will list them and ask which one you mean. '
            'If you ask "When did we play Gratitude?", Aria may ask whether you mean the song or a person.</p>'
            '<h4>Feedback and improvement</h4>'
            '<p>Every response has thumbs up and thumbs down buttons. Your feedback teaches Aria to give '
            'better answers over time. If a response is wrong or missing information, the thumbs down lets '
            'you describe what you expected so the team can review it.</p>'
        ),
        'plain_text': (
            'Aria is the AI assistant at the center of the platform. She draws on your interaction history, '
            'Planning Center data, and uploaded Knowledge Base documents to answer questions about your team.\n\n'
            'What Aria can do:\n'
            '- Volunteer information — contact details, hobbies, family info, personal preferences\n'
            '- Team rosters — "Who are the vocalists?" or "List the band members"\n'
            '- Schedules — "Who\'s on the team this Sunday?" or "Who served on Easter?"\n'
            '- Songs and setlists — song history, lyrics, chord charts, keys, BPM\n'
            '- Blockouts and availability — "Who\'s blocked out on December 14th?"\n'
            '- Aggregate insights — "What are the most common prayer requests?" or "Team summary for November"\n'
            '- Knowledge Base — answers from uploaded documents like procedures, guides, and checklists\n\n'
            'Disambiguation:\n'
            'When a query is ambiguous, Aria asks for clarification rather than guessing. If you search for '
            '"Emma" and there are multiple people named Emma, Aria will list them and ask which one you mean. '
            'If you ask "When did we play Gratitude?", Aria may ask whether you mean the song or a person.\n\n'
            'Feedback and improvement:\n'
            'Every response has thumbs up and thumbs down buttons. Your feedback teaches Aria to give '
            'better answers over time. If a response is wrong or missing information, the thumbs down lets '
            'you describe what you expected so the team can review it.'
        ),
    },
    {
        'id': 'interactions',
        'title': 'Interactions',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>The Interactions page is where you browse and create logs of conversations with your volunteers. '
            'Every interaction you log becomes part of Aria\'s knowledge, making her smarter about your team '
            'over time.</p>'
            '<h4>Browsing interactions</h4>'
            '<p>The interaction list shows all logged interactions for your organization, sorted by most recent. '
            'Each entry shows who logged it, when, which volunteers were mentioned, and a brief preview of the content.</p>'
            '<h4>Interaction details</h4>'
            '<p>Click into any interaction to see the full note along with Aria\'s AI-generated summary and '
            'extracted data. The detail view shows:</p>'
            '<ul>'
            '<li><strong>AI Summary</strong> — a concise summary of the conversation</li>'
            '<li><strong>Extracted knowledge</strong> — hobbies, family info, preferences, and other structured data</li>'
            '<li><strong>Linked volunteers</strong> — people mentioned in the interaction, auto-matched by Aria</li>'
            '<li><strong>Follow-ups created</strong> — any action items or prayer requests that were extracted</li>'
            '</ul>'
            '<h4>Creating interactions</h4>'
            '<p>Click <strong>Create Interaction</strong> and write a free-form note about your conversation. '
            'Include names, personal details, prayer requests, and anything else worth remembering. Aria '
            'processes the note within seconds of saving.</p>'
            '<p>You can also log interactions through Aria by typing something like "Log interaction: Talked '
            'with Mike after rehearsal. He mentioned his wife is recovering from surgery." Aria will create '
            'the interaction and extract data just like the form would.</p>'
        ),
        'plain_text': (
            'The Interactions page is where you browse and create logs of conversations with your volunteers. '
            'Every interaction you log becomes part of Aria\'s knowledge, making her smarter about your team '
            'over time.\n\n'
            'Browsing interactions:\n'
            'The interaction list shows all logged interactions for your organization, sorted by most recent. '
            'Each entry shows who logged it, when, which volunteers were mentioned, and a brief preview of the content.\n\n'
            'Interaction details:\n'
            'Click into any interaction to see the full note along with Aria\'s AI-generated summary and '
            'extracted data. The detail view shows:\n'
            '- AI Summary — a concise summary of the conversation\n'
            '- Extracted knowledge — hobbies, family info, preferences, and other structured data\n'
            '- Linked volunteers — people mentioned in the interaction, auto-matched by Aria\n'
            '- Follow-ups created — any action items or prayer requests that were extracted\n\n'
            'Creating interactions:\n'
            'Click Create Interaction and write a free-form note about your conversation. '
            'Include names, personal details, prayer requests, and anything else worth remembering. Aria '
            'processes the note within seconds of saving.\n\n'
            'You can also log interactions through Aria by typing something like "Log interaction: Talked '
            'with Mike after rehearsal. He mentioned his wife is recovering from surgery." Aria will create '
            'the interaction and extract data just like the form would.'
        ),
    },
    {
        'id': 'volunteers',
        'title': 'Volunteers',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>The Volunteers page shows profiles for every team member in your organization. Profiles are '
            'synced from Planning Center and enriched with data from your logged interactions.</p>'
            '<h4>Browsing volunteers</h4>'
            '<p>The volunteer list displays names and teams. Use the search bar to find someone quickly or '
            'filter by team (vocals, band, tech, etc.).</p>'
            '<h4>Volunteer detail page</h4>'
            '<p>Each volunteer\'s detail page brings together everything ARIA knows about them:</p>'
            '<ul>'
            '<li><strong>Contact information</strong> — email, phone, address (from Planning Center)</li>'
            '<li><strong>Team and role</strong> — which team they serve on</li>'
            '<li><strong>Personal details</strong> — hobbies, family, preferences extracted from interactions</li>'
            '<li><strong>Interaction history</strong> — every logged interaction that mentions this person</li>'
            '<li><strong>Follow-ups</strong> — open and completed follow-up items related to this volunteer</li>'
            '<li><strong>Service history</strong> — when they last served and upcoming schedule dates</li>'
            '</ul>'
            '<h4>Planning Center sync</h4>'
            '<p>Volunteer profiles are automatically synced from Planning Center. When someone is added to or '
            'removed from a team in PCO, the change is reflected in ARIA. Contact details like email and phone '
            'always come directly from PCO to stay up to date.</p>'
            '<h4>Volunteer matching</h4>'
            '<p>When you log an interaction mentioning a name, Aria uses fuzzy matching to link it to the '
            'correct volunteer profile. If the match is uncertain, you will be prompted to confirm, create '
            'a new profile, or skip the match.</p>'
        ),
        'plain_text': (
            'The Volunteers page shows profiles for every team member in your organization. Profiles are '
            'synced from Planning Center and enriched with data from your logged interactions.\n\n'
            'Browsing volunteers:\n'
            'The volunteer list displays names and teams. Use the search bar to find someone quickly or '
            'filter by team (vocals, band, tech, etc.).\n\n'
            'Volunteer detail page:\n'
            'Each volunteer\'s detail page brings together everything ARIA knows about them:\n'
            '- Contact information — email, phone, address (from Planning Center)\n'
            '- Team and role — which team they serve on\n'
            '- Personal details — hobbies, family, preferences extracted from interactions\n'
            '- Interaction history — every logged interaction that mentions this person\n'
            '- Follow-ups — open and completed follow-up items related to this volunteer\n'
            '- Service history — when they last served and upcoming schedule dates\n\n'
            'Planning Center sync:\n'
            'Volunteer profiles are automatically synced from Planning Center. When someone is added to or '
            'removed from a team in PCO, the change is reflected in ARIA. Contact details like email and phone '
            'always come directly from PCO to stay up to date.\n\n'
            'Volunteer matching:\n'
            'When you log an interaction mentioning a name, Aria uses fuzzy matching to link it to the '
            'correct volunteer profile. If the match is uncertain, you will be prompted to confirm, create '
            'a new profile, or skip the match.'
        ),
    },
    {
        'id': 'followups',
        'title': 'Follow-ups',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>Follow-ups help you track action items, prayer requests, and reminders so nothing falls '
            'through the cracks. They can be created manually, extracted from interactions by Aria, or '
            'generated from the proactive care dashboard.</p>'
            '<h4>Creating follow-ups</h4>'
            '<p>There are three ways to create a follow-up:</p>'
            '<ol>'
            '<li><strong>Manually</strong> — go to Follow-ups and click Create Follow-up</li>'
            '<li><strong>From interactions</strong> — Aria auto-extracts follow-up items when you log an interaction</li>'
            '<li><strong>From care insights</strong> — the proactive care dashboard suggests follow-ups for volunteers who need attention</li>'
            '</ol>'
            '<h4>Follow-up details</h4>'
            '<ul>'
            '<li><strong>Categories</strong> — prayer request, concern, action item, or feedback</li>'
            '<li><strong>Priority</strong> — low, medium, high, or urgent</li>'
            '<li><strong>Status workflow</strong> — pending, in progress, completed, or cancelled</li>'
            '<li><strong>Follow-up date</strong> — when the follow-up should happen; triggers a reminder notification</li>'
            '<li><strong>Assignment</strong> — assign to yourself or another team member</li>'
            '</ul>'
            '<h4>Notifications</h4>'
            '<p>When a follow-up date arrives, the assigned person receives a push notification reminder. '
            'On the native iOS app, a local notification is scheduled at 9:00 AM on the follow-up date. '
            'Completed and cancelled follow-ups have their reminders automatically cleared.</p>'
        ),
        'plain_text': (
            'Follow-ups help you track action items, prayer requests, and reminders so nothing falls '
            'through the cracks. They can be created manually, extracted from interactions by Aria, or '
            'generated from the proactive care dashboard.\n\n'
            'Creating follow-ups:\n'
            'There are three ways to create a follow-up:\n'
            '1. Manually — go to Follow-ups and click Create Follow-up\n'
            '2. From interactions — Aria auto-extracts follow-up items when you log an interaction\n'
            '3. From care insights — the proactive care dashboard suggests follow-ups for volunteers who need attention\n\n'
            'Follow-up details:\n'
            '- Categories — prayer request, concern, action item, or feedback\n'
            '- Priority — low, medium, high, or urgent\n'
            '- Status workflow — pending, in progress, completed, or cancelled\n'
            '- Follow-up date — when the follow-up should happen; triggers a reminder notification\n'
            '- Assignment — assign to yourself or another team member\n\n'
            'Notifications:\n'
            'When a follow-up date arrives, the assigned person receives a push notification reminder. '
            'On the native iOS app, a local notification is scheduled at 9:00 AM on the follow-up date. '
            'Completed and cancelled follow-ups have their reminders automatically cleared.'
        ),
    },
    {
        'id': 'team-hub',
        'title': 'Team Hub',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>The Team Hub is your central place for team communication. It includes announcements, '
            'discussion channels, and direct messages — all built into the platform so your team does not '
            'need a separate messaging app.</p>'
            '<h4>Announcements</h4>'
            '<p>Announcements are team-wide messages from leaders. They support three priority levels: '
            'normal, important, and urgent. Important and urgent announcements are visually highlighted. '
            'Announcements can be <strong>pinned</strong> to stay at the top of the list and can have a '
            'publish date and expiration date for scheduling.</p>'
            '<h4>Channels</h4>'
            '<p>Channels are discussion spaces organized by topic. They can be <strong>public</strong> '
            '(visible to everyone in the organization) or <strong>private</strong> (invite-only). Inside '
            'a channel you can:</p>'
            '<ul>'
            '<li>Post messages and reply in <strong>threads</strong> to keep discussions organized</li>'
            '<li>Use <strong>@mentions</strong> to notify specific people — type @ followed by their name</li>'
            '<li>Share files up to <strong>10 MB</strong></li>'
            '</ul>'
            '<h4>Direct Messages</h4>'
            '<p>Send private messages to any member of your organization. Direct messages show '
            '<strong>read status</strong> so you know when your message has been seen. You can also '
            'reply in threads to keep longer conversations organized.</p>'
        ),
        'plain_text': (
            'The Team Hub is your central place for team communication. It includes announcements, '
            'discussion channels, and direct messages — all built into the platform so your team does not '
            'need a separate messaging app.\n\n'
            'Announcements:\n'
            'Announcements are team-wide messages from leaders. They support three priority levels: '
            'normal, important, and urgent. Important and urgent announcements are visually highlighted. '
            'Announcements can be pinned to stay at the top of the list and can have a '
            'publish date and expiration date for scheduling.\n\n'
            'Channels:\n'
            'Channels are discussion spaces organized by topic. They can be public '
            '(visible to everyone in the organization) or private (invite-only). Inside '
            'a channel you can:\n'
            '- Post messages and reply in threads to keep discussions organized\n'
            '- Use @mentions to notify specific people — type @ followed by their name\n'
            '- Share files up to 10 MB\n\n'
            'Direct Messages:\n'
            'Send private messages to any member of your organization. Direct messages show '
            'read status so you know when your message has been seen. You can also '
            'reply in threads to keep longer conversations organized.'
        ),
    },
    {
        'id': 'projects-tasks',
        'title': 'Projects & Tasks',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>Projects and tasks give your team a structured way to plan and track work. Whether you are '
            'organizing a Christmas production or onboarding new volunteers, projects keep everything in one place.</p>'
            '<h4>Projects</h4>'
            '<p>Each project has a status (planning, active, on hold, completed, archived), members, and an '
            'optional linked discussion channel. Projects track progress automatically based on how many tasks '
            'are completed. You can set milestones with start and due dates.</p>'
            '<h4>Tasks</h4>'
            '<p>Tasks live inside projects and are displayed on a <strong>Kanban board</strong> with columns: '
            'To Do, In Progress, In Review, and Completed. Each task supports:</p>'
            '<ul>'
            '<li><strong>Subtasks and checklists</strong> — break work into smaller steps</li>'
            '<li><strong>Assignments</strong> — assign one or more team members</li>'
            '<li><strong>Due dates and times</strong> — with overdue indicators when past due</li>'
            '<li><strong>Comments</strong> — discuss the task with @mention support</li>'
            '<li><strong>Priority levels</strong> — low, medium, high, or urgent</li>'
            '<li><strong>Decisions and notes</strong> — capture context and rationale</li>'
            '<li><strong>Watching</strong> — follow a task to get notified of updates</li>'
            '<li><strong>Recurring tasks</strong> — set tasks to repeat on a schedule</li>'
            '</ul>'
            '<h4>Standalone tasks</h4>'
            '<p>Not everything needs a project. You can create standalone tasks from the <strong>My Tasks</strong> '
            'view for quick action items. These appear alongside your project tasks in a unified list.</p>'
        ),
        'plain_text': (
            'Projects and tasks give your team a structured way to plan and track work. Whether you are '
            'organizing a Christmas production or onboarding new volunteers, projects keep everything in one place.\n\n'
            'Projects:\n'
            'Each project has a status (planning, active, on hold, completed, archived), members, and an '
            'optional linked discussion channel. Projects track progress automatically based on how many tasks '
            'are completed. You can set milestones with start and due dates.\n\n'
            'Tasks:\n'
            'Tasks live inside projects and are displayed on a Kanban board with columns: '
            'To Do, In Progress, In Review, and Completed. Each task supports:\n'
            '- Subtasks and checklists — break work into smaller steps\n'
            '- Assignments — assign one or more team members\n'
            '- Due dates and times — with overdue indicators when past due\n'
            '- Comments — discuss the task with @mention support\n'
            '- Priority levels — low, medium, high, or urgent\n'
            '- Decisions and notes — capture context and rationale\n'
            '- Watching — follow a task to get notified of updates\n'
            '- Recurring tasks — set tasks to repeat on a schedule\n\n'
            'Standalone tasks:\n'
            'Not everything needs a project. You can create standalone tasks from the My Tasks '
            'view for quick action items. These appear alongside your project tasks in a unified list.'
        ),
    },
    {
        'id': 'creative-studio',
        'title': 'Creative Studio',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>The Creative Studio is a space for your team to share ideas, inspiration, and creative work. '
            'Think of it as a shared mood board and collaboration space for your worship arts team.</p>'
            '<h4>Posting</h4>'
            '<p>Create posts with different types to categorize your content — ideas, inspiration, arrangements, '
            'visuals, and more. Posts support media attachments, tags for organization, and can be saved as '
            '<strong>drafts</strong> before publishing. Each post type helps the team filter and find relevant content.</p>'
            '<h4>Collaboration</h4>'
            '<p>The Studio is built for interaction. On any post you can:</p>'
            '<ul>'
            '<li><strong>React</strong> with 6 reaction types to show appreciation or agreement</li>'
            '<li><strong>Comment</strong> to share feedback or ask questions</li>'
            '<li><strong>Build on this</strong> — create a new post linked to an existing one to iterate on an idea</li>'
            '<li>Flag a post for <strong>collaboration</strong> to invite others to contribute</li>'
            '</ul>'
            '<h4>Organization</h4>'
            '<p>Keep your creative content organized with:</p>'
            '<ul>'
            '<li><strong>Collections</strong> — group related posts together (e.g., "Easter 2026 Ideas")</li>'
            '<li><strong>Filtering</strong> — filter by post type, tag, or author</li>'
            '<li><strong>My Work</strong> — quickly find everything you have posted</li>'
            '<li><strong>Spotlights</strong> — featured posts highlighted by team leaders</li>'
            '</ul>'
        ),
        'plain_text': (
            'The Creative Studio is a space for your team to share ideas, inspiration, and creative work. '
            'Think of it as a shared mood board and collaboration space for your worship arts team.\n\n'
            'Posting:\n'
            'Create posts with different types to categorize your content — ideas, inspiration, arrangements, '
            'visuals, and more. Posts support media attachments, tags for organization, and can be saved as '
            'drafts before publishing. Each post type helps the team filter and find relevant content.\n\n'
            'Collaboration:\n'
            'The Studio is built for interaction. On any post you can:\n'
            '- React with 6 reaction types to show appreciation or agreement\n'
            '- Comment to share feedback or ask questions\n'
            '- Build on this — create a new post linked to an existing one to iterate on an idea\n'
            '- Flag a post for collaboration to invite others to contribute\n\n'
            'Organization:\n'
            'Keep your creative content organized with:\n'
            '- Collections — group related posts together (e.g., "Easter 2026 Ideas")\n'
            '- Filtering — filter by post type, tag, or author\n'
            '- My Work — quickly find everything you have posted\n'
            '- Spotlights — featured posts highlighted by team leaders'
        ),
    },
    {
        'id': 'song-submissions',
        'title': 'Song Submissions',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>Song Submissions lets team members suggest new songs for the worship rotation. Instead of '
            'scattered text messages and emails, song ideas flow through a single, organized process.</p>'
            '<h4>Submitting a song</h4>'
            '<p>Navigate to Song Submissions from the sidebar and click <strong>Submit a Song</strong>. '
            'Fill in the song title, artist, and why you think it would be a good fit for the team. '
            'You can include a link to a recording or video for reference.</p>'
            '<h4>Viewing submissions</h4>'
            '<p>All team members can browse submitted songs. Each submission shows the song details, '
            'who submitted it, and the current status. This gives everyone visibility into what songs '
            'are being considered.</p>'
            '<h4>Voting</h4>'
            '<p>Team members can vote on submissions to indicate their interest. Votes help leaders '
            'gauge team enthusiasm and prioritize which songs to learn next. The vote count is displayed '
            'on each submission.</p>'
            '<h4>Status tracking</h4>'
            '<p>Leaders can update the status of submissions as they move through the review process. '
            'Statuses let the submitter and the rest of the team know whether a song is under review, '
            'approved for the rotation, or passed on for now.</p>'
        ),
        'plain_text': (
            'Song Submissions lets team members suggest new songs for the worship rotation. Instead of '
            'scattered text messages and emails, song ideas flow through a single, organized process.\n\n'
            'Submitting a song:\n'
            'Navigate to Song Submissions from the sidebar and click Submit a Song. '
            'Fill in the song title, artist, and why you think it would be a good fit for the team. '
            'You can include a link to a recording or video for reference.\n\n'
            'Viewing submissions:\n'
            'All team members can browse submitted songs. Each submission shows the song details, '
            'who submitted it, and the current status. This gives everyone visibility into what songs '
            'are being considered.\n\n'
            'Voting:\n'
            'Team members can vote on submissions to indicate their interest. Votes help leaders '
            'gauge team enthusiasm and prioritize which songs to learn next. The vote count is displayed '
            'on each submission.\n\n'
            'Status tracking:\n'
            'Leaders can update the status of submissions as they move through the review process. '
            'Statuses let the submitter and the rest of the team know whether a song is under review, '
            'approved for the rotation, or passed on for now.'
        ),
    },
    {
        'id': 'analytics',
        'title': 'Analytics',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>The Analytics dashboard gives you data-driven insights into how your team is doing. '
            'Reports are organized into six areas, each focusing on a different aspect of team health.</p>'
            '<h4>Report types</h4>'
            '<ul>'
            '<li><strong>Overview</strong> — key metrics at a glance: total interactions, active volunteers, '
            'open follow-ups, and trends over time</li>'
            '<li><strong>Volunteer Engagement</strong> — participation rates, who is serving frequently, '
            'and who may be stepping back</li>'
            '<li><strong>Team Care</strong> — follow-up completion rates, prayer request trends, and care activity</li>'
            '<li><strong>Interaction Trends</strong> — how many interactions are being logged over time, '
            'broken down by team member</li>'
            '<li><strong>Prayer Requests</strong> — aggregate prayer request data and common themes</li>'
            '<li><strong>AI Performance</strong> — how well Aria is answering questions based on feedback scores</li>'
            '</ul>'
            '<h4>Exporting data</h4>'
            '<p>Every report can be exported as a <strong>CSV file</strong> for use in spreadsheets or '
            'presentations. Click the Export button on any report page to download the data.</p>'
            '<p>Reports are cached for performance and can be refreshed on demand using the Refresh button. '
            'This ensures you are always looking at up-to-date numbers without slowing down the platform.</p>'
        ),
        'plain_text': (
            'The Analytics dashboard gives you data-driven insights into how your team is doing. '
            'Reports are organized into six areas, each focusing on a different aspect of team health.\n\n'
            'Report types:\n'
            '- Overview — key metrics at a glance: total interactions, active volunteers, '
            'open follow-ups, and trends over time\n'
            '- Volunteer Engagement — participation rates, who is serving frequently, '
            'and who may be stepping back\n'
            '- Team Care — follow-up completion rates, prayer request trends, and care activity\n'
            '- Interaction Trends — how many interactions are being logged over time, '
            'broken down by team member\n'
            '- Prayer Requests — aggregate prayer request data and common themes\n'
            '- AI Performance — how well Aria is answering questions based on feedback scores\n\n'
            'Exporting data:\n'
            'Every report can be exported as a CSV file for use in spreadsheets or '
            'presentations. Click the Export button on any report page to download the data.\n\n'
            'Reports are cached for performance and can be refreshed on demand using the Refresh button. '
            'This ensures you are always looking at up-to-date numbers without slowing down the platform.'
        ),
    },
    {
        'id': 'proactive-care',
        'title': 'Proactive Care',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>The Proactive Care dashboard uses AI to identify volunteers who may need attention. Instead '
            'of waiting for problems to surface, the care system proactively highlights situations where a '
            'check-in or follow-up could make a difference.</p>'
            '<h4>Insight types</h4>'
            '<p>Aria generates five types of care insights:</p>'
            '<ul>'
            '<li><strong>Missing / Inactive</strong> — volunteers who have not served or been seen recently</li>'
            '<li><strong>Declining Engagement</strong> — volunteers whose participation is trending downward</li>'
            '<li><strong>Prayer Request Follow-up</strong> — prayer requests that may need a check-in</li>'
            '<li><strong>Celebration / Milestone</strong> — birthdays, anniversaries, or achievements worth recognizing</li>'
            '<li><strong>General Concern</strong> — other situations that warrant attention based on interaction data</li>'
            '</ul>'
            '<p>Each insight includes a priority level (low, medium, high, urgent), a description of the '
            'situation, and suggested actions.</p>'
            '<h4>Taking action</h4>'
            '<p>From any insight, you can:</p>'
            '<ul>'
            '<li><strong>Create a follow-up</strong> — turn the insight into a tracked follow-up item assigned to a team member</li>'
            '<li><strong>Dismiss</strong> — mark the insight as reviewed if no action is needed</li>'
            '</ul>'
            '<p>The care dashboard refreshes its insights periodically. You can also trigger a manual refresh '
            'to get the latest analysis.</p>'
        ),
        'plain_text': (
            'The Proactive Care dashboard uses AI to identify volunteers who may need attention. Instead '
            'of waiting for problems to surface, the care system proactively highlights situations where a '
            'check-in or follow-up could make a difference.\n\n'
            'Insight types:\n'
            'Aria generates five types of care insights:\n'
            '- Missing / Inactive — volunteers who have not served or been seen recently\n'
            '- Declining Engagement — volunteers whose participation is trending downward\n'
            '- Prayer Request Follow-up — prayer requests that may need a check-in\n'
            '- Celebration / Milestone — birthdays, anniversaries, or achievements worth recognizing\n'
            '- General Concern — other situations that warrant attention based on interaction data\n\n'
            'Each insight includes a priority level (low, medium, high, urgent), a description of the '
            'situation, and suggested actions.\n\n'
            'Taking action:\n'
            'From any insight, you can:\n'
            '- Create a follow-up — turn the insight into a tracked follow-up item assigned to a team member\n'
            '- Dismiss — mark the insight as reviewed if no action is needed\n\n'
            'The care dashboard refreshes its insights periodically. You can also trigger a manual refresh '
            'to get the latest analysis.'
        ),
    },
    {
        'id': 'knowledge-base',
        'title': 'Knowledge Base',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>The Knowledge Base lets you upload documents that Aria can reference when answering questions. '
            'This is perfect for procedures, checklists, setup guides, and any other reference material '
            'your team needs.</p>'
            '<h4>What to upload</h4>'
            '<p>Here are some examples of documents that work well in the Knowledge Base:</p>'
            '<ul>'
            '<li>Sound board setup procedures</li>'
            '<li>Lighting rig configuration guides</li>'
            '<li>New volunteer onboarding checklists</li>'
            '<li>Stage layout diagrams (as images)</li>'
            '<li>Team policies and guidelines</li>'
            '</ul>'
            '<h4>Supported file types</h4>'
            '<p>You can upload <strong>PDF</strong>, <strong>TXT</strong>, <strong>PNG</strong>, and '
            '<strong>JPG/JPEG</strong> files up to <strong>10 MB</strong> each.</p>'
            '<h4>How documents are processed</h4>'
            '<p>When you upload a document, ARIA processes it through a pipeline:</p>'
            '<ol>'
            '<li>Text is extracted from the file (PDFs are parsed, images are analyzed with AI vision)</li>'
            '<li>The text is split into smaller chunks for efficient searching</li>'
            '<li>Each chunk is embedded as a vector so Aria can find relevant passages by meaning</li>'
            '<li>Images in PDFs are extracted and described using AI vision</li>'
            '</ol>'
            '<h4>How Aria uses documents</h4>'
            '<p>When you ask Aria a question, she searches the Knowledge Base alongside your interaction '
            'history. If a document contains relevant information, Aria includes it in her answer and '
            '<strong>cites the source document</strong> by title. Images from documents can also appear '
            'inline in chat responses as clickable thumbnails.</p>'
            '<p>Admins and owners can upload, edit, and delete documents. All team members can view '
            'documents and ask Aria questions about them.</p>'
        ),
        'plain_text': (
            'The Knowledge Base lets you upload documents that Aria can reference when answering questions. '
            'This is perfect for procedures, checklists, setup guides, and any other reference material '
            'your team needs.\n\n'
            'What to upload:\n'
            'Here are some examples of documents that work well in the Knowledge Base:\n'
            '- Sound board setup procedures\n'
            '- Lighting rig configuration guides\n'
            '- New volunteer onboarding checklists\n'
            '- Stage layout diagrams (as images)\n'
            '- Team policies and guidelines\n\n'
            'Supported file types:\n'
            'You can upload PDF, TXT, PNG, and JPG/JPEG files up to 10 MB each.\n\n'
            'How documents are processed:\n'
            'When you upload a document, ARIA processes it through a pipeline:\n'
            '1. Text is extracted from the file (PDFs are parsed, images are analyzed with AI vision)\n'
            '2. The text is split into smaller chunks for efficient searching\n'
            '3. Each chunk is embedded as a vector so Aria can find relevant passages by meaning\n'
            '4. Images in PDFs are extracted and described using AI vision\n\n'
            'How Aria uses documents:\n'
            'When you ask Aria a question, she searches the Knowledge Base alongside your interaction '
            'history. If a document contains relevant information, Aria includes it in her answer and '
            'cites the source document by title. Images from documents can also appear '
            'inline in chat responses as clickable thumbnails.\n\n'
            'Admins and owners can upload, edit, and delete documents. All team members can view '
            'documents and ask Aria questions about them.'
        ),
    },
    {
        'id': 'notifications',
        'title': 'Notifications',
        'group': 'features',
        'is_admin': False,
        'content': (
            '<p>ARIA supports push notifications on both web browsers and the native iOS app so you '
            'never miss important updates from your team.</p>'
            '<h4>Setting up notifications</h4>'
            '<ol>'
            '<li>Go to <strong>Notifications</strong> in the sidebar (at the bottom)</li>'
            '<li>Click <strong>Enable Push Notifications</strong> and allow the browser permission when prompted</li>'
            '<li>Choose which notification types you want to receive</li>'
            '</ol>'
            '<h4>Notification types</h4>'
            '<p>You can enable or disable each type independently:</p>'
            '<ul>'
            '<li><strong>Announcements</strong> — new team announcements (with option for urgent only)</li>'
            '<li><strong>Direct Messages</strong> — when someone sends you a private message</li>'
            '<li><strong>Channel Messages</strong> — activity in channels (with option for @mentions only)</li>'
            '<li><strong>Care Alerts</strong> — proactive care insights about volunteers</li>'
            '<li><strong>Follow-up Reminders</strong> — when a follow-up date arrives</li>'
            '<li><strong>Project Updates</strong> — when you are added to a project</li>'
            '<li><strong>Task Assignments</strong> — when you are assigned to a task or mentioned in comments</li>'
            '<li><strong>Song Submissions</strong> — new song submissions and status updates</li>'
            '</ul>'
            '<h4>Quiet hours</h4>'
            '<p>Enable quiet hours to pause notifications during specific times — for example, overnight. '
            'Set a start and end time, and ARIA will hold notifications until quiet hours end.</p>'
        ),
        'plain_text': (
            'ARIA supports push notifications on both web browsers and the native iOS app so you '
            'never miss important updates from your team.\n\n'
            'Setting up notifications:\n'
            '1. Go to Notifications in the sidebar (at the bottom)\n'
            '2. Click Enable Push Notifications and allow the browser permission when prompted\n'
            '3. Choose which notification types you want to receive\n\n'
            'Notification types:\n'
            'You can enable or disable each type independently:\n'
            '- Announcements — new team announcements (with option for urgent only)\n'
            '- Direct Messages — when someone sends you a private message\n'
            '- Channel Messages — activity in channels (with option for @mentions only)\n'
            '- Care Alerts — proactive care insights about volunteers\n'
            '- Follow-up Reminders — when a follow-up date arrives\n'
            '- Project Updates — when you are added to a project\n'
            '- Task Assignments — when you are assigned to a task or mentioned in comments\n'
            '- Song Submissions — new song submissions and status updates\n\n'
            'Quiet hours:\n'
            'Enable quiet hours to pause notifications during specific times — for example, overnight. '
            'Set a start and end time, and ARIA will hold notifications until quiet hours end.'
        ),
    },

    # =========================================================================
    # ADMIN
    # =========================================================================
    {
        'id': 'org-settings',
        'title': 'Organization Settings',
        'group': 'admin',
        'is_admin': True,
        'content': (
            '<p>Organization settings let admins and owners customize the platform for their team. '
            'Go to <strong>Settings</strong> in the sidebar to access these options.</p>'
            '<h4>General settings</h4>'
            '<ul>'
            '<li><strong>Organization name</strong> — the name displayed throughout the platform and in emails</li>'
            '<li><strong>AI assistant name</strong> — customize what your AI assistant is called (default is "Aria"). '
            'This changes the name everywhere in the interface, including chat responses and notifications.</li>'
            '<li><strong>Primary color</strong> — set a brand color for your organization. This color is used '
            'for accents throughout the interface (default is indigo #6366f1).</li>'
            '</ul>'
            '<p>Changes to these settings take effect immediately across the platform for all team members.</p>'
            '<p>Only users with the <strong>admin</strong> or <strong>owner</strong> role can modify organization '
            'settings. Other team members can view the settings page but cannot make changes.</p>'
        ),
        'plain_text': (
            'Organization settings let admins and owners customize the platform for their team. '
            'Go to Settings in the sidebar to access these options.\n\n'
            'General settings:\n'
            '- Organization name — the name displayed throughout the platform and in emails\n'
            '- AI assistant name — customize what your AI assistant is called (default is "Aria"). '
            'This changes the name everywhere in the interface, including chat responses and notifications.\n'
            '- Primary color — set a brand color for your organization. This color is used '
            'for accents throughout the interface (default is indigo #6366f1).\n\n'
            'Changes to these settings take effect immediately across the platform for all team members.\n\n'
            'Only users with the admin or owner role can modify organization '
            'settings. Other team members can view the settings page but cannot make changes.'
        ),
    },
    {
        'id': 'managing-members',
        'title': 'Managing Members',
        'group': 'admin',
        'is_admin': True,
        'content': (
            '<p>Manage your team members from <strong>Settings > Members</strong>. This is where you '
            'invite new people, assign roles, and remove members who have left the team.</p>'
            '<h4>Inviting members</h4>'
            '<p>Click <strong>Invite Member</strong> and enter their email address. They will receive an '
            'email with a link to create their account and join your organization. Invitations expire '
            'after a set period and can be cancelled from the members page.</p>'
            '<h4>Roles</h4>'
            '<p>Each member has a role that determines what they can access:</p>'
            '<ul>'
            '<li><strong>Owner</strong> — full control over the organization, including billing and the ability to delete the org</li>'
            '<li><strong>Admin</strong> — manage members, settings, and all platform features; cannot delete the org or manage billing</li>'
            '<li><strong>Team Leader</strong> — manage volunteers, view analytics, and access all team features</li>'
            '<li><strong>Member</strong> — standard access to chat, interactions, follow-ups, and communication tools</li>'
            '<li><strong>Viewer</strong> — read-only access; can browse but cannot create or modify content</li>'
            '</ul>'
            '<h4>Changing roles</h4>'
            '<p>Admins and owners can change any member\'s role from the members page. Click the role '
            'dropdown next to a member\'s name and select the new role.</p>'
            '<h4>Removing members</h4>'
            '<p>To remove someone from the organization, click the remove button next to their name. '
            'Their data (interactions, messages) remains in the system but they will no longer be able '
            'to log in or access the organization.</p>'
        ),
        'plain_text': (
            'Manage your team members from Settings > Members. This is where you '
            'invite new people, assign roles, and remove members who have left the team.\n\n'
            'Inviting members:\n'
            'Click Invite Member and enter their email address. They will receive an '
            'email with a link to create their account and join your organization. Invitations expire '
            'after a set period and can be cancelled from the members page.\n\n'
            'Roles:\n'
            'Each member has a role that determines what they can access:\n'
            '- Owner — full control over the organization, including billing and the ability to delete the org\n'
            '- Admin — manage members, settings, and all platform features; cannot delete the org or manage billing\n'
            '- Team Leader — manage volunteers, view analytics, and access all team features\n'
            '- Member — standard access to chat, interactions, follow-ups, and communication tools\n'
            '- Viewer — read-only access; can browse but cannot create or modify content\n\n'
            'Changing roles:\n'
            'Admins and owners can change any member\'s role from the members page. Click the role '
            'dropdown next to a member\'s name and select the new role.\n\n'
            'Removing members:\n'
            'To remove someone from the organization, click the remove button next to their name. '
            'Their data (interactions, messages) remains in the system but they will no longer be able '
            'to log in or access the organization.'
        ),
    },
    {
        'id': 'billing',
        'title': 'Billing',
        'group': 'admin',
        'is_admin': True,
        'content': (
            '<p>Manage your subscription and payment details from <strong>Settings > Billing</strong>. '
            'ARIA offers four plans to fit teams of every size.</p>'
            '<h4>Plans</h4>'
            '<ul>'
            '<li><strong>Starter</strong> — $9.99/month (or $100/year) — up to 5 users and 50 volunteers. '
            'Includes PCO integration and push notifications.</li>'
            '<li><strong>Team</strong> — $39.99/month (or $400/year) — up to 15 users and 200 volunteers. '
            'Adds analytics and care insights.</li>'
            '<li><strong>Ministry</strong> — $79.99/month (or $800/year) — unlimited users and volunteers. '
            'Adds API access and custom branding.</li>'
            '<li><strong>Enterprise</strong> — contact us for pricing — unlimited everything plus multi-campus '
            'support, priority support, and custom integrations.</li>'
            '</ul>'
            '<h4>Annual discount</h4>'
            '<p>All plans offer a discount when billed annually. The yearly price is roughly two months free '
            'compared to monthly billing.</p>'
            '<h4>Beta access</h4>'
            '<p>Organizations accepted during the closed beta period get full access to all features for '
            'free. Beta organizations are not required to enter payment details until the beta period ends.</p>'
            '<h4>Managing your subscription</h4>'
            '<p>Click <strong>Manage Billing</strong> to open the Stripe customer portal where you can '
            'update your payment method, change plans, view invoices, and cancel your subscription.</p>'
        ),
        'plain_text': (
            'Manage your subscription and payment details from Settings > Billing. '
            'ARIA offers four plans to fit teams of every size.\n\n'
            'Plans:\n'
            '- Starter — $9.99/month (or $100/year) — up to 5 users and 50 volunteers. '
            'Includes PCO integration and push notifications.\n'
            '- Team — $39.99/month (or $400/year) — up to 15 users and 200 volunteers. '
            'Adds analytics and care insights.\n'
            '- Ministry — $79.99/month (or $800/year) — unlimited users and volunteers. '
            'Adds API access and custom branding.\n'
            '- Enterprise — contact us for pricing — unlimited everything plus multi-campus '
            'support, priority support, and custom integrations.\n\n'
            'Annual discount:\n'
            'All plans offer a discount when billed annually. The yearly price is roughly two months free '
            'compared to monthly billing.\n\n'
            'Beta access:\n'
            'Organizations accepted during the closed beta period get full access to all features for '
            'free. Beta organizations are not required to enter payment details until the beta period ends.\n\n'
            'Managing your subscription:\n'
            'Click Manage Billing to open the Stripe customer portal where you can '
            'update your payment method, change plans, view invoices, and cancel your subscription.'
        ),
    },
    {
        'id': 'security',
        'title': 'Security',
        'group': 'admin',
        'is_admin': True,
        'content': (
            '<p>ARIA includes two-factor authentication (2FA) to add an extra layer of security to your '
            'account. When enabled, you will need both your password and a code from an authenticator app '
            'to log in.</p>'
            '<h4>Setting up 2FA</h4>'
            '<ol>'
            '<li>Go to <strong>Settings > Security</strong></li>'
            '<li>Click <strong>Enable Two-Factor Authentication</strong></li>'
            '<li>Scan the QR code with your authenticator app (Google Authenticator, Authy, 1Password, etc.)</li>'
            '<li>Enter the 6-digit code from your authenticator app to verify the setup</li>'
            '<li>Save the <strong>10 backup codes</strong> displayed — each can be used once if you lose access '
            'to your authenticator app</li>'
            '</ol>'
            '<h4>Logging in with 2FA</h4>'
            '<p>After entering your email and password, you will be prompted for a 6-digit code from your '
            'authenticator app. Enter the current code and click Verify. If you cannot access your '
            'authenticator, use one of your backup codes instead.</p>'
            '<h4>Disabling 2FA</h4>'
            '<p>If you need to turn off two-factor authentication, go to <strong>Settings > Security</strong> '
            'and click <strong>Disable 2FA</strong>. You will need to confirm your decision. Note that '
            'disabling 2FA reduces the security of your account.</p>'
            '<p>We recommend that all admins and owners enable 2FA to protect sensitive team and organization data.</p>'
        ),
        'plain_text': (
            'ARIA includes two-factor authentication (2FA) to add an extra layer of security to your '
            'account. When enabled, you will need both your password and a code from an authenticator app '
            'to log in.\n\n'
            'Setting up 2FA:\n'
            '1. Go to Settings > Security\n'
            '2. Click Enable Two-Factor Authentication\n'
            '3. Scan the QR code with your authenticator app (Google Authenticator, Authy, 1Password, etc.)\n'
            '4. Enter the 6-digit code from your authenticator app to verify the setup\n'
            '5. Save the 10 backup codes displayed — each can be used once if you lose access '
            'to your authenticator app\n\n'
            'Logging in with 2FA:\n'
            'After entering your email and password, you will be prompted for a 6-digit code from your '
            'authenticator app. Enter the current code and click Verify. If you cannot access your '
            'authenticator, use one of your backup codes instead.\n\n'
            'Disabling 2FA:\n'
            'If you need to turn off two-factor authentication, go to Settings > Security '
            'and click Disable 2FA. You will need to confirm your decision. Note that '
            'disabling 2FA reduces the security of your account.\n\n'
            'We recommend that all admins and owners enable 2FA to protect sensitive team and organization data.'
        ),
    },
    {
        'id': 'planning-center',
        'title': 'Planning Center Integration',
        'group': 'admin',
        'is_admin': True,
        'content': (
            '<p>ARIA connects to Planning Center Online (PCO) to pull in your team\'s people, schedules, '
            'songs, and blockout data. This integration is what powers Aria\'s ability to answer questions '
            'about who is serving, what songs are planned, and when people are available.</p>'
            '<h4>Connecting to Planning Center</h4>'
            '<ol>'
            '<li>Go to <strong>Settings > General</strong> (or during onboarding, the PCO connection step)</li>'
            '<li>Enter your Planning Center <strong>App ID</strong> and <strong>Secret</strong> — these are '
            'generated in your Planning Center developer settings</li>'
            '<li>Click <strong>Save</strong> to establish the connection</li>'
            '</ol>'
            '<h4>What syncs from Planning Center</h4>'
            '<ul>'
            '<li><strong>People</strong> — names, emails, phone numbers, and team assignments</li>'
            '<li><strong>Schedules</strong> — service plans with team member assignments and positions</li>'
            '<li><strong>Songs</strong> — song library with titles, artists, keys, BPM, and attachments (chord charts, lyrics)</li>'
            '<li><strong>Blockouts</strong> — date ranges when team members are unavailable</li>'
            '</ul>'
            '<h4>Troubleshooting</h4>'
            '<ul>'
            '<li><strong>Data seems stale</strong> — PCO data is cached for performance. Aria refreshes data '
            'periodically, but you can ask her to check again by rephrasing your question or starting a new conversation.</li>'
            '<li><strong>Rate limit errors</strong> — if you see rate limit messages, PCO is temporarily '
            'limiting API requests. Wait a few minutes and try again. ARIA automatically manages rate limits '
            'and retries requests.</li>'
            '<li><strong>Missing people or teams</strong> — verify that the people and teams exist in your '
            'PCO Services application, not just in PCO People. ARIA pulls from Services for team data.</li>'
            '</ul>'
        ),
        'plain_text': (
            'ARIA connects to Planning Center Online (PCO) to pull in your team\'s people, schedules, '
            'songs, and blockout data. This integration is what powers Aria\'s ability to answer questions '
            'about who is serving, what songs are planned, and when people are available.\n\n'
            'Connecting to Planning Center:\n'
            '1. Go to Settings > General (or during onboarding, the PCO connection step)\n'
            '2. Enter your Planning Center App ID and Secret — these are '
            'generated in your Planning Center developer settings\n'
            '3. Click Save to establish the connection\n\n'
            'What syncs from Planning Center:\n'
            '- People — names, emails, phone numbers, and team assignments\n'
            '- Schedules — service plans with team member assignments and positions\n'
            '- Songs — song library with titles, artists, keys, BPM, and attachments (chord charts, lyrics)\n'
            '- Blockouts — date ranges when team members are unavailable\n\n'
            'Troubleshooting:\n'
            '- Data seems stale — PCO data is cached for performance. Aria refreshes data '
            'periodically, but you can ask her to check again by rephrasing your question or starting a new conversation.\n'
            '- Rate limit errors — if you see rate limit messages, PCO is temporarily '
            'limiting API requests. Wait a few minutes and try again. ARIA automatically manages rate limits '
            'and retries requests.\n'
            '- Missing people or teams — verify that the people and teams exist in your '
            'PCO Services application, not just in PCO People. ARIA pulls from Services for team data.'
        ),
    },
]
