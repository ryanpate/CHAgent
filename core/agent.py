"""
AI Agent module for processing interactions and answering questions.
Uses Anthropic Claude API for natural language understanding.
"""
import json
import logging
import re
from datetime import datetime
from typing import Optional, Tuple

from django.conf import settings

from .models import Interaction, Volunteer, ChatMessage, ConversationContext
from .embeddings import get_embedding, search_similar
from .volunteer_matching import match_volunteers_for_interaction, VolunteerMatcher, MatchType

logger = logging.getLogger(__name__)

# Try to import Anthropic, handle gracefully if not available
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    anthropic = None


def is_aggregate_question(message: str) -> Tuple[bool, str]:
    """
    Detect if a question is asking for aggregate/team-wide information.

    Args:
        message: The user's question.

    Returns:
        Tuple of (is_aggregate, category) where category indicates what type
        of aggregate data is being requested (e.g., 'food', 'hobbies', 'prayer', etc.)
    """
    message_lower = message.lower().strip()

    # Patterns that indicate aggregate/team-wide questions
    aggregate_indicators = [
        r'entire\s+team',
        r'all\s+(the\s+)?volunteers?',
        r'everyone',
        r'whole\s+team',
        r'team[\s-]?wide',
        r'most\s+common',
        r'most\s+popular',
        r'most\s+frequent',
        r'how\s+many\s+(volunteers?|people)',
        r'what\s+are\s+the\s+top',
        r'list\s+all',
        r'show\s+all',
        r'across\s+(the\s+)?team',
        r'among\s+(all\s+)?(the\s+)?volunteers?',
        r'summary\s+of\s+(all|the)',
        r'overall',
        r'in\s+total',
        r'aggregate',
        r'collectively',
    ]

    is_aggregate = False
    for pattern in aggregate_indicators:
        if re.search(pattern, message_lower):
            is_aggregate = True
            break

    # Detect category of aggregate data requested
    category = 'general'
    category_patterns = {
        'food': r'food|eat|favorite\s+(food|meal|restaurant)|diet',
        'hobbies': r'hobb(y|ies)|interest|activities|free\s+time',
        'prayer': r'prayer|pray|request',
        'family': r'family|kid|children|spouse|married|wife|husband',
        'birthday': r'birthday|birth\s+date|born',
        'availability': r'availab|schedule|when\s+can',
        'feedback': r'feedback|suggestion|comment|opinion',
    }

    for cat, pattern in category_patterns.items():
        if re.search(pattern, message_lower):
            category = cat
            break

    return is_aggregate, category


def is_pco_data_query(message: str) -> Tuple[bool, str, Optional[str]]:
    """
    Detect if a question is asking for data that resides in Planning Center.

    Args:
        message: The user's question.

    Returns:
        Tuple of (is_pco_query, query_type, person_name) where:
        - is_pco_query: True if asking for PCO data
        - query_type: Type of data requested (contact, email, phone, address, birthday, etc.)
        - person_name: Extracted person name if found
    """
    message_lower = message.lower().strip()

    # Patterns that indicate PCO data queries
    pco_query_patterns = {
        'contact': r'contact\s+(info|information|details?)|how\s+(can\s+i|do\s+i|to)\s+(reach|contact|get\s+(in\s+)?touch)',
        'email': r'email(\s+address)?|e-mail',
        'phone': r'phone(\s+number)?|call|cell(\s+number)?|mobile(\s+number)?|telephone',
        'address': r'address|where\s+(does|do)\s+.+\s+live|location|mailing',
        'birthday': r'birthday|birth\s*date|when\s+(was|is)\s+.+\s+born|how\s+old',
        'anniversary': r'anniversary',
        'teams': r'what\s+team|which\s+team|team\s+(position|role)|serve\s+on|part\s+of',
        'service_history': r'when\s+did\s+.+\s+(last\s+)?serve|last\s+(time|served)|service\s+history|schedule|scheduled|serving',
    }

    is_pco_query = False
    query_type = None

    for qtype, pattern in pco_query_patterns.items():
        if re.search(pattern, message_lower):
            is_pco_query = True
            query_type = qtype
            break

    # Extract person name from the question
    person_name = None
    if is_pco_query:
        # Common patterns for extracting names (case-insensitive)
        # Names will be title-cased after extraction
        # Order matters - more specific patterns first
        name_patterns = [
            # "what is [name]'s contact" - with apostrophe
            r"what\s+is\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*)'s",
            # "what is [name] contact info" - without apostrophe (name before contact)
            r"what\s+is\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*?)\s+contact",
            # "[name]'s contact/email/phone" - with apostrophe
            r"([a-zA-Z]+(?:\s+[a-zA-Z]+)*)'s\s+(?:contact|email|phone|address|birthday)",
            # "[name]s contact info" - possessive without apostrophe (e.g., "strucks contact")
            r"([a-zA-Z]+(?:\s+[a-zA-Z]+)*s)\s+contact\s+(?:info|information|details?)",
            # "contact info for [name]"
            r"contact\s+(?:info|information|details?)\s+(?:for|of|about)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*)",
            # "for/of/about [name]" - generic
            r"(?:for|of|about)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*)",
            # "reach/call/email [name]"
            r"(?:reach|call|email)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*)",
            # "where does/when was [name]"
            r"(?:where\s+does|when\s+(?:was|is))\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*)",
        ]

        for pattern in name_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                # Remove trailing 's' if it's a possessive without apostrophe (e.g., "strucks" -> "struck")
                if extracted.lower().endswith('s') and len(extracted) > 2:
                    # Check if this looks like a possessive (followed by contact/email/phone in original)
                    if re.search(r'\b' + re.escape(extracted) + r'\s+(?:contact|email|phone)', message, re.IGNORECASE):
                        extracted = extracted[:-1]  # Remove trailing 's'
                person_name = extracted.title()  # Title-case the name
                # Filter out common false positives
                false_positives = ['I', 'What', 'Where', 'When', 'How', 'Can', 'Do', 'Does', 'Is', 'Are',
                                   'The', 'Info', 'Information', 'Details', 'Contact', 'Their', 'My', 'Your']
                if person_name not in false_positives and len(person_name) > 1:
                    break
                else:
                    person_name = None

    return is_pco_query, query_type, person_name


def _has_date_reference(message_lower: str) -> bool:
    """
    Check if a message contains a date reference (for disambiguation).

    This is used to distinguish between:
    - song_history: "when was [song] played" (no date, asking for when)
    - setlist: "what was played on [date]" (has date, asking for songs)
    """
    date_patterns = [
        r'(last|this|next)\s+(sunday|week|month|service)',
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',
        r'\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?',  # MM/DD or MM-DD format
        r'(yesterday|today|tomorrow)',
        r'(easter|christmas|thanksgiving|good\s+friday)(\s+\d{4})?',
        r'(that|the)\s+(day|date|sunday|service)',
    ]
    return any(re.search(p, message_lower) for p in date_patterns)


def _has_song_history_indicators(message_lower: str) -> bool:
    """
    Check if a message is asking about song history (when was a song played).

    These patterns indicate the user wants to know WHEN a song was played,
    not WHAT songs were played on a date.
    """
    history_patterns = [
        r'last\s+time\s+.+\s+(was\s+)?(played|used|scheduled|performed)',
        r'when\s+(was|did|is)\s+.+\s+(played|used|scheduled|performed)',
        r'how\s+(often|many\s+times|frequently)',
        r'song\s+(usage|history)',
        r'have\s+we\s+(ever\s+)?(played|used|done)',
    ]
    return any(re.search(p, message_lower) for p in history_patterns)


def is_song_or_setlist_query(message: str) -> Tuple[bool, str, Optional[str]]:
    """
    Detect if a question is asking about songs, setlists, or chord charts.

    Args:
        message: The user's question.

    Returns:
        Tuple of (is_song_query, query_type, extracted_value) where:
        - is_song_query: True if asking about songs/setlists
        - query_type: Type of query (setlist, song, chord_chart, lyrics)
        - extracted_value: Song title or date extracted from the question
    """
    message_lower = message.lower().strip()

    # Patterns for song/setlist queries
    # Note: These patterns are used for initial detection. Disambiguation between
    # song_history and setlist happens separately based on context (date presence, etc.)
    song_query_patterns = {
        # Team/volunteer schedule - check this BEFORE setlist to catch volunteer-specific queries
        # Include both present (is/are) and past (was/were) tense for queries like "who was on the team last Sunday"
        # Also match simple past tense "who served" without auxiliary verb
        'team_schedule': r'(who\s+(is|are|was|were)\s+(on|serving|scheduled|playing|singing)|who\s+served|volunteer[s]?\s+(on|for|are)|team\s+member|who[\'s]*\s+(on|serving)|what\s+volunteer|scheduled\s+volunteer|serving\s+(on|this|next|last)|band\s+for|vocals?\s+for|tech\s+for|who\s+(do|did)\s+we\s+have)',
        # Song history - asking WHEN a song was played
        'song_history': r'when\s+(was|did)\s+(the\s+)?(this\s+)?song\s+.*(used|played|performed|scheduled)|when\s+was\s+.+\s+played\s+(last|most\s+recently)|song\s+(usage|history)|last\s+time\s+.*(song|played|used)|how\s+(often|many\s+times)\s+.*(song|play)|have\s+we\s+(ever\s+)?(played|done|used)|(?:the\s+)?(?:title|song|name)\s+is\s+|it\'?s\s+called',
        # Setlist - asking WHAT songs were played on a date
        'setlist': r'(setlist|song\s*set|what\s+(other\s+)?songs?\s+(did|do|are|were|will|was)|songs?\s+(from|for|on|we\s+(play|sang|did))|worship\s+set|played\s+on|was\s+played|last\s+played|(played|songs?)\s+(that|on\s+that)\s+(day|date|service|sunday|easter)|(songs?|play|sang|played)\s+.*(easter|christmas|good\s+friday))',
        'chord_chart': r'chord\s*chart|chords?\s+(for|to)|lead\s+sheet|charts?\s+(for|to)',
        # Lyrics patterns - include section requests like "lyrics to the bridge" or just "the lyrics"
        'lyrics': r'lyrics?\s+(for|to)|words?\s+(for|to)|(give|show|get)\s+(me\s+)?(the\s+)?lyrics|(what\s+are\s+)?the\s+lyrics|lyrics?\s+to\s+the\s+(verse|chorus|bridge|intro|outro|pre-?chorus)',
        'song_search': r'(find|search|look\s*up|get|show)\s+(the\s+)?(song|music)',
        'song_info': r'(what\s+key|which\s+key|bpm|tempo|how\s+(long|fast))\s+.*(song|play)',
    }

    # Check for date and song history indicators (used for disambiguation)
    has_date_reference = _has_date_reference(message_lower)
    has_song_history_indicators = _has_song_history_indicators(message_lower)

    is_song_query = False
    query_type = None

    # Collect all matching patterns for disambiguation
    matching_types = []
    for qtype, pattern in song_query_patterns.items():
        if re.search(pattern, message_lower):
            matching_types.append(qtype)

    if matching_types:
        is_song_query = True

        # Disambiguation logic: choose the most appropriate query type
        if 'team_schedule' in matching_types:
            # Team schedule takes priority when explicitly asking about volunteers/team
            query_type = 'team_schedule'
        elif 'chord_chart' in matching_types:
            query_type = 'chord_chart'
        elif 'lyrics' in matching_types:
            query_type = 'lyrics'
        elif 'song_search' in matching_types:
            query_type = 'song_search'
        elif 'song_info' in matching_types:
            query_type = 'song_info'
        elif 'song_history' in matching_types or 'setlist' in matching_types:
            # Key disambiguation: song_history vs setlist
            # - song_history: "when was [song] played" - asking for a DATE, no date in query
            # - setlist: "what was played on [date]" - asking for SONGS, has date in query
            if has_song_history_indicators and not has_date_reference:
                # Asking about when a song was played (no date provided)
                query_type = 'song_history'
            elif has_date_reference and not has_song_history_indicators:
                # Has a date, asking what was played on that date
                query_type = 'setlist'
            elif 'song_history' in matching_types:
                # If song_history pattern matched explicitly, prefer it
                query_type = 'song_history'
            else:
                query_type = 'setlist'
        else:
            # Fallback to first match
            query_type = matching_types[0]

    # Extract song title or date from the question
    extracted_value = None

    if is_song_query:
        # Try to extract song title (in quotes or after common patterns)
        title_patterns = [
            r'"([^"]+)"',  # Quoted title
            r"'([^']+)'",  # Single-quoted title
            r'(?:chord\s*chart|chords?|lyrics?|song)\s+(?:for|to)\s+["\']?([^"\'?]+)["\']?',
            r'(?:find|search|look\s*up|get)\s+(?:the\s+)?(?:song\s+)?["\']?([^"\'?]+)["\']?',
            # Song history patterns - "when is/was the last time [song] was played"
            r'(?:when\s+(?:is|was)\s+)?(?:the\s+)?last\s+time\s+(.+?)\s+was\s+(?:played|used|scheduled|performed)',
            # "when was the song [title] played last?"
            r'when\s+(?:was|did)\s+(?:the\s+)?song\s+["\']?(.+?)["\']?\s+(?:last\s+)?(?:used|played|performed|scheduled)',
            r'when\s+(?:was|did)\s+(?:the\s+)?song\s+["\']?(.+?)["\']?\s+(?:used|played|performed|scheduled)\s+(?:last|most\s+recently)',
            r'when\s+(?:was|did)\s+["\']?([^"\'?]+?)["\']?\s+(?:last\s+)?(?:used|played|performed|scheduled)',
            r'when\s+was\s+["\']?(.+?)["\']?\s+played\s+(?:last|most\s+recently)',
            r'(?:history|usage)\s+(?:for|of)\s+["\']?([^"\'?]+)["\']?',
            # Follow-up clarification patterns - "the title is X", "it's called X"
            r'(?:the\s+)?(?:title|song|name)\s+is\s+["\']?(.+?)["\']?$',
            r"(?:it'?s|its)\s+(?:called|titled|named)\s+[\"']?(.+?)[\"']?$",
            r"(?:it'?s|its)\s+[\"']?([A-Z][^\"']+?)[\"']?$",  # "it's Let Us Be Known" - starts with capital
        ]

        for pattern in title_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                extracted_value = match.group(1).strip()
                # Clean up common leading phrases like "the chorus of", "verse 2 in", "2nd verse of", etc.
                # Handle both "verse 2" and "2nd verse" formats (ordinal before or after section name)
                extracted_value = re.sub(
                    r'^(the\s+)?(\d+(?:st|nd|rd|th)\s+)?(chorus|verse|bridge|intro|outro|pre-?chorus|hook|refrain)(\s+\d+)?(\s+of\s+|\s+from\s+|\s+to\s+|\s+in\s+)',
                    '',
                    extracted_value,
                    flags=re.IGNORECASE
                )
                # Clean up common trailing words
                extracted_value = re.sub(r'\s+(chord|chart|lyric|song)s?$', '', extracted_value, flags=re.IGNORECASE)
                extracted_value = extracted_value.strip()

                # If the "extracted" value is just a section name, it's not a song title
                section_only_pattern = r'^(the\s+)?(\d+(?:st|nd|rd|th)\s+)?(chorus|verse|bridge|intro|outro|pre-?chorus|hook|refrain)(\s+\d+)?$'
                if re.match(section_only_pattern, extracted_value, re.IGNORECASE):
                    extracted_value = None  # Not a song title, just a section request
                    break

                if extracted_value:
                    break

        # Try to extract date for setlist or team_schedule queries
        if query_type in ['setlist', 'team_schedule'] and not extracted_value:
            date_patterns = [
                r'(last\s+sunday|this\s+sunday|next\s+sunday|yesterday|today)',
                r'(?:on\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{4})?',
                r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
                r'(\d{1,2}-\d{1,2}(?:-\d{2,4})?)',
                # Easter pattern - matches "Easter", "Easter 2025", "Easter last year", "last Easter"
                r'((?:last|this|next)\s+easter|easter(?:\s+\d{4}|\s+(?:last|this|next)\s+year)?)',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    extracted_value = match.group(0).replace('on ', '')  # Use full match, remove leading "on "
                    break

    return is_song_query, query_type, extracted_value


def detect_service_type_from_question(message: str) -> Optional[str]:
    """
    Detect if a question is asking about a specific service type.

    Args:
        message: The user's question.

    Returns:
        Service type name if detected, None otherwise (will default to main service).
    """
    message_lower = message.lower().strip()

    # Service type keywords and their mappings
    # If any of these are found, return the corresponding service type name
    service_type_patterns = {
        'HSM': [r'\bhsm\b', r'high\s+school', r'high-school', r'highschool'],
        'MSM': [r'\bmsm\b', r'middle\s+school', r'middle-school', r'middleschool'],
    }

    for service_type, patterns in service_type_patterns.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                logger.info(f"Detected service type '{service_type}' from question")
                return service_type

    # No specific service type mentioned - will default to main service
    return None


def format_plan_details(plan: dict) -> str:
    """
    Format service plan details into a readable string for the AI context.

    Args:
        plan: Plan details dict from PCO API.

    Returns:
        Formatted string with plan info and song list.
    """
    if not plan:
        return ""

    parts = [f"\n[SERVICE PLAN DATA]"]
    if plan.get('service_type_name'):
        parts.append(f"Service Type: {plan.get('service_type_name')}")
    parts.append(f"Date: {plan.get('dates') or plan.get('sort_date', 'Unknown')}")

    if plan.get('title'):
        parts.append(f"Title: {plan.get('title')}")
    if plan.get('series_title'):
        parts.append(f"Series: {plan.get('series_title')}")

    songs = plan.get('songs', [])
    if songs:
        parts.append(f"\nSong Set ({len(songs)} songs):")
        for i, song in enumerate(songs, 1):
            title = song.get('title', 'Unknown')
            key = song.get('key', '')
            author = song.get('author', '')

            song_line = f"  {i}. {title}"
            if key:
                song_line += f" (Key: {key})"
            if author:
                song_line += f" - {author}"
            parts.append(song_line)
    else:
        parts.append("\nNo songs found in this plan.")

    parts.append("[END SERVICE PLAN DATA]\n")
    return '\n'.join(parts)


def format_team_schedule(plan: dict) -> str:
    """
    Format team/volunteer schedule from a service plan for the AI context.

    Args:
        plan: Plan details dict from PCO API with team_members included.

    Returns:
        Formatted string with team member assignments.
    """
    if not plan:
        return ""

    parts = [f"\n[SERVICE TEAM SCHEDULE]"]
    if plan.get('service_type_name'):
        parts.append(f"Service Type: {plan.get('service_type_name')}")
    parts.append(f"Date: {plan.get('dates') or plan.get('sort_date', 'Unknown')}")

    if plan.get('title'):
        parts.append(f"Service: {plan.get('title')}")

    team_members = plan.get('team_members', [])
    if team_members:
        # Group by team
        teams = {}
        for member in team_members:
            team_name = member.get('team_name', 'Other')
            if team_name not in teams:
                teams[team_name] = []
            teams[team_name].append(member)

        parts.append(f"\nTeam Assignments ({len(team_members)} people):")
        for team_name in sorted(teams.keys()):
            parts.append(f"\n  {team_name}:")
            for member in teams[team_name]:
                name = member.get('name', 'Unknown')
                position = member.get('position', '')
                status = member.get('status', 'Unknown')

                member_line = f"    - {name}"
                if position:
                    member_line += f" ({position})"
                member_line += f" - {status}"
                parts.append(member_line)
    else:
        parts.append("\nNo team members assigned to this service yet.")

    # Also include songs if available
    songs = plan.get('songs', [])
    if songs:
        parts.append(f"\nSong Set ({len(songs)} songs):")
        for i, song in enumerate(songs, 1):
            title = song.get('title', 'Unknown')
            key = song.get('key', '')
            song_line = f"  {i}. {title}"
            if key:
                song_line += f" (Key: {key})"
            parts.append(song_line)

    parts.append("[END SERVICE TEAM SCHEDULE]\n")
    return '\n'.join(parts)


def format_song_details(song: dict) -> str:
    """
    Format song details into a readable string for the AI context.

    Args:
        song: Song details dict from PCO API.

    Returns:
        Formatted string with song info and attachments.
    """
    if not song:
        return ""

    parts = [f"\n[SONG DATA]"]
    parts.append(f"Title: {song.get('title', 'Unknown')}")

    if song.get('author'):
        parts.append(f"Author: {song.get('author')}")
    if song.get('ccli_number'):
        parts.append(f"CCLI#: {song.get('ccli_number')}")
    if song.get('copyright'):
        parts.append(f"Copyright: {song.get('copyright')}")

    # Track if we found any lyrics or chord content
    has_lyrics_content = False
    has_chord_content = False

    # Arrangements
    arrangements = song.get('arrangements', [])
    if arrangements:
        parts.append(f"\nArrangements ({len(arrangements)}):")
        for arr in arrangements:
            arr_info = f"  - {arr.get('name', 'Default')}"
            if arr.get('key'):
                arr_info += f" | Key: {arr.get('key')}"
            if arr.get('bpm'):
                arr_info += f" | BPM: {arr.get('bpm')}"
            if arr.get('sequence'):
                arr_info += f" | Sequence: {arr.get('sequence')}"
            parts.append(arr_info)

            # Include lyrics if available
            if arr.get('lyrics'):
                has_lyrics_content = True
                parts.append(f"\n    LYRICS ({arr.get('name', 'Default')} arrangement):")
                parts.append("    " + arr.get('lyrics').replace('\n', '\n    '))

            # Include chord chart if available
            if arr.get('chord_chart'):
                has_chord_content = True
                parts.append(f"\n    CHORD CHART ({arr.get('name', 'Default')} arrangement):")
                parts.append("    " + arr.get('chord_chart').replace('\n', '\n    '))

    # Attachments
    all_attachments = song.get('all_attachments', []) or song.get('attachments', [])
    if all_attachments:
        # First show any attachments with fetched text content (chord charts, lyrics)
        content_attachments = [a for a in all_attachments if a.get('text_content')]
        other_attachments = [a for a in all_attachments if not a.get('text_content')]

        if content_attachments:
            parts.append(f"\nChord Charts/Lyrics Content:")
            for attach in content_attachments:
                has_lyrics_content = True  # Assume attachment content includes lyrics
                filename = attach.get('filename', 'Unknown file')
                arr_name = attach.get('arrangement_name', '')
                arr_key = attach.get('arrangement_key', '')

                header = f"\n--- {filename}"
                if arr_name:
                    header += f" ({arr_name})"
                if arr_key:
                    header += f" [Key: {arr_key}]"
                header += " ---"
                parts.append(header)
                parts.append(attach.get('text_content', ''))

        if other_attachments:
            # Note: These are files we couldn't read content from
            parts.append(f"\nFiles that could not be read ({len(other_attachments)} - may be image-based PDFs):")
            for attach in other_attachments:
                filename = attach.get('filename', 'Unknown file')
                file_type = attach.get('file_type', '')
                arr_key = attach.get('arrangement_key', '')

                attach_info = f"  - {filename}"
                if arr_key:
                    attach_info += f" (Key: {arr_key})"
                if file_type:
                    attach_info += f" [{file_type}]"
                parts.append(attach_info)
    else:
        parts.append("\nNo attachments found for this song.")

    # Add explicit note about content availability
    if not has_lyrics_content and not has_chord_content:
        parts.append("\n[NOTE: No lyrics or chord chart text content could be extracted from this song's files. The files may be image-based PDFs that cannot be read as text. Please inform the user that the lyrics are not available in a readable format in Planning Center.]")

    parts.append("[END SONG DATA]\n")
    return '\n'.join(parts)


def format_song_suggestions(search_query: str, suggestions: list, conversation_context=None) -> str:
    """
    Format song search suggestions into a readable string for the AI context.

    Args:
        search_query: The song title that was searched for.
        suggestions: List of suggestion dicts with 'title', 'author', and 'score'.
        conversation_context: Optional ConversationContext to store suggestions for later selection.

    Returns:
        Formatted string with suggestions for the AI to present to the user.
    """
    if not suggestions:
        return f"\n[SONG SEARCH: No songs found matching '{search_query}'. The song may not be in the Planning Center library.]\n"

    # Store suggestions in conversation context for later selection
    if conversation_context is not None:
        # Store the suggestions with their IDs for later retrieval
        stored_suggestions = []
        for s in suggestions[:5]:
            stored_suggestions.append({
                'id': s.get('id'),
                'title': s.get('title', 'Unknown'),
                'author': s.get('author', ''),
                'score': s.get('score', 0)
            })
        conversation_context.set_pending_song_suggestions(stored_suggestions)
        conversation_context.save()
        logger.info(f"Stored {len(stored_suggestions)} pending song suggestions in context")

    parts = [f"\n[SONG SEARCH: No exact match found for '{search_query}']"]
    parts.append("Similar songs found in the Planning Center library:")

    for i, s in enumerate(suggestions[:5], 1):
        title = s.get('title', 'Unknown')
        author = s.get('author', '')
        score = s.get('score', 0)

        confidence = "high" if score >= 0.7 else "medium" if score >= 0.5 else "low"
        song_info = f"  {i}. \"{title}\""
        if author:
            song_info += f" by {author}"
        song_info += f" ({confidence} confidence)"
        parts.append(song_info)

    parts.append("")
    parts.append("ASK THE USER: Present these options to the user as a numbered list and ask which song they meant. They can respond with just the number (e.g., '1' or '2').")
    parts.append("[END SONG SUGGESTIONS]\n")

    return '\n'.join(parts)


def format_song_usage_history(usage_data: dict, conversation_context=None) -> str:
    """
    Format song usage history into a readable string for the AI context.

    Args:
        usage_data: Dict with song info and usage history.
        conversation_context: Optional ConversationContext to store suggestions for later selection.

    Returns:
        Formatted string with song usage history.
    """
    if not usage_data:
        return "\n[SONG HISTORY: Unable to retrieve song usage history.]\n"

    if not usage_data.get('found'):
        # Song not found - show suggestions
        suggestions = usage_data.get('suggestions', [])
        if suggestions:
            return format_song_suggestions(usage_data.get('song_title', 'Unknown'), suggestions, conversation_context)
        return f"\n[SONG HISTORY: No song found matching '{usage_data.get('song_title', 'Unknown')}'.]\n"

    parts = [f"\n[SONG USAGE HISTORY]"]
    parts.append(f"Song: {usage_data.get('song_title', 'Unknown')}")

    if usage_data.get('author'):
        parts.append(f"Author: {usage_data.get('author')}")

    usages = usage_data.get('usages', [])
    if usages:
        parts.append(f"\nService History ({len(usages)} recent uses):")
        for i, usage in enumerate(usages, 1):
            date = usage.get('date', 'Unknown date')
            key = usage.get('key', '')
            arr_name = usage.get('arrangement_name', '')

            usage_info = f"  {i}. {date}"
            if key:
                usage_info += f" (Key: {key})"
            if arr_name:
                usage_info += f" - {arr_name}"
            parts.append(usage_info)

        # Highlight most recent
        most_recent = usages[0].get('date', 'Unknown')
        parts.append(f"\nMost recently used: {most_recent}")
    else:
        parts.append("\nNo recent service history found for this song.")

    parts.append("[END SONG HISTORY]\n")
    return '\n'.join(parts)


def format_pco_suggestions(search_name: str, suggestions: list, local_suggestions: list = None) -> str:
    """
    Format PCO name suggestions into a readable string for the AI context.

    Args:
        search_name: The name that was searched for.
        suggestions: List of PCO suggestion dicts with 'name' and 'score'.
        local_suggestions: Optional list of local Volunteer suggestions.

    Returns:
        Formatted string with suggestions for the AI to present to the user.
    """
    if not suggestions and not local_suggestions:
        return f"\n[PLANNING CENTER: No person found matching '{search_name}' and no similar names found.]\n"

    parts = [f"\n[PLANNING CENTER: No exact match found for '{search_name}']"]
    parts.append("Similar names found that the user might have meant:")

    # Combine and deduplicate suggestions
    all_names = set()
    combined_suggestions = []

    # Add PCO suggestions
    for s in (suggestions or []):
        name = s.get('name', '')
        if name and name.lower() not in all_names:
            all_names.add(name.lower())
            combined_suggestions.append({
                'name': name,
                'score': s.get('score', 0),
                'source': 'Planning Center'
            })

    # Add local suggestions
    for s in (local_suggestions or []):
        name = s.get('name', '')
        if name and name.lower() not in all_names:
            all_names.add(name.lower())
            combined_suggestions.append({
                'name': name,
                'score': s.get('score', 0),
                'source': 'Local Database'
            })

    # Sort by score descending
    combined_suggestions.sort(key=lambda x: x['score'], reverse=True)

    # Format top suggestions
    for i, s in enumerate(combined_suggestions[:5], 1):
        confidence = "high" if s['score'] >= 0.7 else "medium" if s['score'] >= 0.5 else "low"
        parts.append(f"  {i}. {s['name']} ({confidence} confidence)")

    parts.append("")
    parts.append("ASK THE USER: Please ask the user if they meant one of these names, or if they'd like to search for someone else.")
    parts.append("[END PLANNING CENTER SUGGESTIONS]\n")

    return '\n'.join(parts)


def get_local_volunteer_suggestions(name: str, limit: int = 5) -> list:
    """
    Get name suggestions from local Volunteer database.

    Args:
        name: Name to find suggestions for.
        limit: Maximum number of suggestions.

    Returns:
        List of suggestion dicts with 'name' and 'score'.
    """
    from difflib import SequenceMatcher

    search_name = normalize_name(name)
    volunteers = Volunteer.objects.all()

    suggestions = []
    for volunteer in volunteers:
        vol_name = volunteer.name
        normalized_vol = normalize_name(vol_name)

        # Calculate similarity
        score = SequenceMatcher(None, search_name, normalized_vol).ratio()

        # Boost if last name matches
        search_parts = search_name.split()
        vol_parts = normalized_vol.split()
        if len(search_parts) >= 1 and len(vol_parts) >= 1:
            if search_parts[-1] == vol_parts[-1]:
                score = max(score, 0.6)

        if score >= 0.3:  # Low threshold for suggestions
            suggestions.append({
                'name': vol_name,
                'score': score,
                'volunteer_id': volunteer.id
            })

    # Sort by score and return top matches
    suggestions.sort(key=lambda x: x['score'], reverse=True)
    return suggestions[:limit]


def normalize_name(name: str) -> str:
    """Normalize a name for comparison (lowercase, strip whitespace)."""
    import re
    name = re.sub(r'[^\w\s]', '', name)
    return ' '.join(name.lower().split())


def format_pco_details(details: dict, query_type: str = None) -> str:
    """
    Format PCO person details into a readable string for the AI context.

    Args:
        details: Person details dict from PCO API.
        query_type: Optional specific type of data requested.

    Returns:
        Formatted string with person details.
    """
    if not details:
        return ""

    parts = [f"\n[PLANNING CENTER DATA for {details.get('name', 'Unknown')}]"]

    # Always include name
    parts.append(f"Name: {details.get('name', 'Unknown')}")

    # Birthday
    if details.get('birthdate') and query_type in [None, 'birthday', 'contact']:
        parts.append(f"Birthday: {details.get('birthdate')}")

    # Anniversary
    if details.get('anniversary') and query_type in [None, 'anniversary', 'contact']:
        parts.append(f"Anniversary: {details.get('anniversary')}")

    # Emails
    if details.get('emails') and query_type in [None, 'email', 'contact']:
        email_strs = []
        for email in details['emails']:
            primary = " (primary)" if email.get('primary') else ""
            location = f" [{email.get('location')}]" if email.get('location') else ""
            email_strs.append(f"{email.get('address')}{location}{primary}")
        if email_strs:
            parts.append(f"Email(s): {', '.join(email_strs)}")

    # Phone numbers
    if details.get('phone_numbers') and query_type in [None, 'phone', 'contact']:
        phone_strs = []
        for phone in details['phone_numbers']:
            primary = " (primary)" if phone.get('primary') else ""
            location = f" [{phone.get('location')}]" if phone.get('location') else ""
            phone_strs.append(f"{phone.get('number')}{location}{primary}")
        if phone_strs:
            parts.append(f"Phone(s): {', '.join(phone_strs)}")

    # Addresses
    if details.get('addresses') and query_type in [None, 'address', 'contact']:
        for addr in details['addresses']:
            primary = " (primary)" if addr.get('primary') else ""
            location = f" [{addr.get('location')}]" if addr.get('location') else ""
            # Handle None values by converting to empty strings
            street = addr.get('street') or ''
            city = addr.get('city') or ''
            state = addr.get('state') or ''
            zip_code = addr.get('zip') or ''
            addr_parts = [
                street,
                f"{city}, {state} {zip_code}".strip()
            ]
            addr_str = ', '.join(p for p in addr_parts if p and p.strip())
            if addr_str:
                parts.append(f"Address{location}{primary}: {addr_str}")

    # Membership/Status
    if details.get('membership'):
        parts.append(f"Membership: {details.get('membership')}")
    if details.get('status'):
        parts.append(f"Status: {details.get('status')}")

    # Teams (positions they serve in)
    if details.get('teams'):
        team_strs = []
        for team in details['teams']:
            team_strs.append(team.get('position', 'Unknown Position'))
        if team_strs:
            parts.append(f"Team Position(s): {', '.join(team_strs)}")

    # Last served date
    if details.get('last_served'):
        parts.append(f"Last Served: {details.get('last_served')}")

    # Recent service history
    if details.get('recent_schedules'):
        parts.append("Recent Service History:")
        for schedule in details['recent_schedules'][:5]:  # Show up to 5 recent
            date = schedule.get('date', 'Unknown date')
            team = schedule.get('team_name', 'Unknown team')
            position = schedule.get('team_position_name', '')
            status = schedule.get('status', '')

            # Convert status codes to readable text
            status_map = {
                'C': 'Confirmed',
                'U': 'Unconfirmed',
                'D': 'Declined',
                'B': 'Blocked'
            }
            status_text = status_map.get(status, status)

            if position:
                parts.append(f"  - {date}: {team} ({position}) - {status_text}")
            else:
                parts.append(f"  - {date}: {team} - {status_text}")

    parts.append("[END PLANNING CENTER DATA]\n")

    return '\n'.join(parts)


SYSTEM_PROMPT = """You are the Cherry Hills Worship Arts Team Assistant named Aria. You help team members:
1. Log interactions with volunteers
2. Answer questions about volunteers based on logged interactions
3. Provide aggregate insights about the volunteer team
4. Look up volunteer information from Planning Center
5. Find songs, setlists, and chord charts from Planning Center Services

## Your Capabilities:
- When a user logs an interaction, extract and organize key information (names, preferences, prayer requests, feedback, etc.)
- When asked questions, search through past interactions to provide accurate answers
- Identify which volunteers are mentioned and link them appropriately
- Provide summaries and aggregate data when asked
- Look up volunteer details from Planning Center including:
  - Contact info (email, phone, address)
  - Birthday and anniversary
  - Team positions they serve in
  - Recent service history and when they last served
- Look up songs and service plans from Planning Center Services:
  - Song setlists for specific service dates
  - Song details (author, key, arrangements)
  - Chord charts and lyrics files with download links
  - Search the song library

## Guidelines:
- Be warm, helpful, and pastoral in tone
- Protect volunteer privacy - only share information with authenticated team members
- When uncertain, say so rather than guessing
- Format responses clearly with relevant details
- If asked about a volunteer with no logged interactions, say so clearly
- When Planning Center data is provided, use it to answer contact-related questions accurately
- IMPORTANT: When song data (lyrics, chord charts) is provided from Planning Center, you MUST display it directly in your response - do NOT just offer download links. The church has proper CCLI licensing for all songs in their Planning Center account.
- When a user asks for specific sections (e.g., "2nd verse", "chorus"), find and display just that section from the lyrics data provided. Look for section markers like "Verse 1", "Verse 2", "Chorus", "Bridge", etc. in the lyrics content.
- If lyrics or chord chart content is included in the context data, always display it directly rather than pointing to download links.
- IMPORTANT: If the context indicates that lyrics/chord content could NOT be extracted (e.g., "[NOTE: No lyrics or chord chart text content could be extracted...]"), clearly tell the user that the lyrics are not available in a readable text format in Planning Center. Do NOT offer download links as an alternative - just explain that the files are likely image-based PDFs that cannot be read as text and suggest they check the song directly in Planning Center or that the worship team may need to add text-based lyrics to the song in PCO.

## Data Extraction:
When processing a new interaction, extract and structure:
- Volunteer name(s) mentioned
- Personal details (hobbies, family, favorites, birthday, etc.)
- Prayer requests or concerns
- Feedback about services or team
- Availability or scheduling notes
- Any follow-up actions needed

## Follow-up Detection:
When a user logs an interaction or mentions something that requires follow-up, you should:
1. Identify items that need follow-up (prayer requests, concerns, action items, promises made, check-ins needed)
2. Ask if they would like to create a follow-up item to track it
3. If they confirm, ask for a follow-up date (e.g., "When would you like to follow up on this?")
4. Suggest reasonable follow-up timeframes based on context:
   - Prayer requests: 1-2 weeks
   - Health concerns: 1 week
   - General check-ins: 2-4 weeks
   - Time-sensitive items: Specify urgency

When you detect something needing follow-up, respond like:
"It sounds like [volunteer name] could use some follow-up regarding [topic]. Would you like me to create a follow-up reminder for this? If so, when would you like to be reminded?"

## Context:
You have access to the following interaction history for context:
{context}

Current date: {current_date}
Team member asking: {user_name}
"""

EXTRACTION_PROMPT = """Extract structured information from this volunteer interaction note.
Return ONLY valid JSON (no markdown, no explanation) with this structure:
{
    "volunteers": [{"name": "Full Name", "team": "team name or empty string"}],
    "summary": "brief 1-2 sentence summary",
    "extracted_data": {
        "hobbies": ["list of hobbies mentioned"],
        "favorites": {"food": null, "color": null, "etc": "..."},
        "family": {"spouse": null, "children": [], "other": "..."},
        "prayer_requests": ["list of prayer requests"],
        "feedback": ["list of feedback items"],
        "availability": null,
        "follow_up_needed": false,
        "birthday": null,
        "other": {}
    }
}

If no volunteers are clearly mentioned, return an empty list for volunteers.
Only include fields that have actual data extracted from the note."""


def get_anthropic_client():
    """Get Anthropic client instance."""
    if not HAS_ANTHROPIC:
        logger.warning("Anthropic not installed. AI features will not be available.")
        return None

    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set. AI features will not be available.")
        return None

    return anthropic.Anthropic(api_key=api_key)


def parse_json_response(response) -> dict:
    """Parse JSON from Claude's response."""
    try:
        content = response.content[0].text
        # Try to parse directly
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse JSON from response: {content[:200]}")
        return {}


def process_interaction(content: str, user) -> dict:
    """
    Process a new interaction entry:
    1. Generate embedding
    2. Extract structured data via Claude
    3. Match volunteers against PCO and local database
    4. Save interaction with metadata

    Args:
        content: The interaction note content.
        user: The user who logged the interaction.

    Returns:
        Dictionary with:
        - interaction: The created Interaction object
        - extracted: Data extracted by AI
        - volunteers: List of confirmed Volunteer objects
        - pending_matches: List of VolunteerMatch objects needing confirmation
        - unmatched: List of names with no matches found
    """
    client = get_anthropic_client()
    extracted = {}

    # Step 1: Extract data with Claude (if available)
    if client:
        try:
            extraction_response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                system=EXTRACTION_PROMPT,
                messages=[{"role": "user", "content": content}]
            )
            extracted = parse_json_response(extraction_response)
        except Exception as e:
            logger.error(f"Error extracting data with Claude: {e}")

    # Step 2: Generate embedding for semantic search
    embedding = get_embedding(content)

    # Step 3: Match volunteers against PCO and local database
    volunteer_names = extracted.get('volunteers', [])
    match_result = match_volunteers_for_interaction(volunteer_names)

    confirmed_volunteers = match_result['confirmed']
    pending_matches = match_result['pending']
    unmatched = match_result['unmatched']

    # Step 4: Create interaction
    interaction = Interaction.objects.create(
        user=user,
        content=content,
        ai_summary=extracted.get('summary', ''),
        ai_extracted_data=extracted.get('extracted_data', {}),
        embedding_json=embedding
    )
    # Link confirmed volunteers
    interaction.volunteers.set(confirmed_volunteers)

    # Step 5: Extract and store knowledge from the interaction
    # This runs asynchronously-ish - we don't wait for it
    try:
        if confirmed_volunteers:
            extract_knowledge_from_interaction(interaction, user)
    except Exception as e:
        logger.error(f"Error in knowledge extraction: {e}")

    return {
        'interaction': interaction,
        'extracted': extracted,
        'volunteers': confirmed_volunteers,
        'pending_matches': pending_matches,
        'unmatched': unmatched
    }


def confirm_volunteer_match(
    interaction_id: int,
    original_name: str,
    volunteer_id: Optional[int] = None,
    pco_id: Optional[str] = None,
    create_new: bool = False
) -> Optional[Volunteer]:
    """
    Confirm a pending volunteer match for an interaction.

    Args:
        interaction_id: ID of the interaction to update.
        original_name: The original extracted name.
        volunteer_id: ID of existing volunteer to link (if selected).
        pco_id: PCO person ID to create/link from (if selected).
        create_new: If True, create a new volunteer with original_name.

    Returns:
        The linked Volunteer, or None if interaction not found.
    """
    try:
        interaction = Interaction.objects.get(id=interaction_id)
    except Interaction.DoesNotExist:
        logger.error(f"Interaction {interaction_id} not found")
        return None

    matcher = VolunteerMatcher()

    if volunteer_id:
        # Link to existing volunteer
        try:
            volunteer = Volunteer.objects.get(id=volunteer_id)
            interaction.volunteers.add(volunteer)
            logger.info(f"Linked interaction {interaction_id} to volunteer {volunteer.name}")
            return volunteer
        except Volunteer.DoesNotExist:
            logger.error(f"Volunteer {volunteer_id} not found")
            return None

    elif pco_id:
        # Create/get volunteer from PCO
        from .planning_center import PlanningCenterAPI
        pco_api = PlanningCenterAPI()
        person = pco_api.get_person_by_id(pco_id)

        if person:
            attrs = person.get('attributes', {})
            pco_name = f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip()
            volunteer = matcher.get_or_create_volunteer(
                name=pco_name or original_name,
                pco_id=pco_id
            )
            interaction.volunteers.add(volunteer)
            logger.info(f"Linked interaction {interaction_id} to PCO volunteer {volunteer.name}")
            return volunteer
        else:
            logger.error(f"PCO person {pco_id} not found")
            return None

    elif create_new:
        # Create new volunteer with original name
        volunteer = matcher.get_or_create_volunteer(name=original_name)
        interaction.volunteers.add(volunteer)
        logger.info(f"Created and linked new volunteer {volunteer.name} to interaction {interaction_id}")
        return volunteer

    return None


def skip_volunteer_match(interaction_id: int, original_name: str) -> bool:
    """
    Skip linking a volunteer for an interaction.

    This is used when the user doesn't want to link any volunteer
    for a particular mentioned name.

    Args:
        interaction_id: ID of the interaction.
        original_name: The name that was skipped.

    Returns:
        True if successful.
    """
    logger.info(f"Skipped volunteer match for '{original_name}' in interaction {interaction_id}")
    return True


def extract_knowledge_from_interaction(interaction, user=None):
    """
    Extract structured knowledge from an interaction and store it.

    Uses Claude to analyze the interaction content and extract facts about
    volunteers that can be stored in the knowledge base.

    Args:
        interaction: The Interaction instance.
        user: Optional user who is extracting this knowledge.

    Returns:
        List of created/updated ExtractedKnowledge objects.
    """
    from .models import ExtractedKnowledge

    # Get volunteers linked to this interaction
    volunteers = list(interaction.volunteers.all())
    if not volunteers:
        return []

    client = get_anthropic_client()
    if not client:
        return []

    # Build the extraction prompt
    volunteer_names = ", ".join([v.name for v in volunteers])
    extraction_prompt = f"""Analyze this interaction about volunteer(s): {volunteer_names}

Extract any factual information mentioned about them. For each piece of information, provide:
- volunteer_name: Which volunteer this is about
- knowledge_type: One of: hobby, family, preference, birthday, anniversary, prayer_request, health, work, availability, skill, contact, other
- key: A short descriptive key (e.g., "favorite_food", "spouse_name", "child_age")
- value: The actual information
- confidence: "high" (directly stated), "medium" (clearly implied), or "low" (inferred/uncertain)

Return a JSON array of knowledge items. If no extractable knowledge, return empty array [].

Example output:
[
  {{"volunteer_name": "Sarah", "knowledge_type": "family", "key": "spouse_name", "value": "Mike", "confidence": "high"}},
  {{"volunteer_name": "Sarah", "knowledge_type": "hobby", "key": "gardening", "value": "Enjoys growing tomatoes", "confidence": "high"}}
]

Interaction content:
{interaction.content}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": extraction_prompt}]
        )

        # Parse the response
        response_text = response.content[0].text
        knowledge_items = parse_json_response_as_list(response_text)

        if not knowledge_items:
            return []

        # Store extracted knowledge
        created_knowledge = []
        volunteer_lookup = {v.name.lower(): v for v in volunteers}

        for item in knowledge_items:
            volunteer_name = item.get('volunteer_name', '').lower()
            volunteer = volunteer_lookup.get(volunteer_name)

            if not volunteer:
                # Try partial match
                for v_name, v in volunteer_lookup.items():
                    if volunteer_name in v_name or v_name in volunteer_name:
                        volunteer = v
                        break

            if not volunteer:
                continue

            knowledge_type = item.get('knowledge_type', 'other')
            key = item.get('key', '')
            value = item.get('value', '')
            confidence = item.get('confidence', 'medium')

            if not key or not value:
                continue

            # Store the knowledge
            knowledge, created = ExtractedKnowledge.update_or_create_knowledge(
                volunteer=volunteer,
                knowledge_type=knowledge_type,
                key=key,
                value=value,
                source_interaction=interaction,
                confidence=confidence,
                user=user
            )
            created_knowledge.append(knowledge)

            if created:
                logger.info(f"Extracted new knowledge: {volunteer.name} - {key}: {value}")
            else:
                logger.info(f"Updated knowledge: {volunteer.name} - {key}: {value}")

        return created_knowledge

    except Exception as e:
        logger.error(f"Error extracting knowledge from interaction: {e}")
        return []


def parse_json_response_as_list(response_text: str) -> list:
    """
    Parse a JSON array from Claude's response.

    Args:
        response_text: The raw response text.

    Returns:
        A list of dictionaries, or empty list if parsing fails.
    """
    import json
    import re

    # Try to extract JSON array from the response
    try:
        # First try direct parse
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in the response
    json_match = re.search(r'\[[\s\S]*\]', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return []


def get_or_create_conversation_context(user, session_id: str) -> ConversationContext:
    """
    Get or create a ConversationContext for the given session.

    Args:
        user: The user making the request.
        session_id: The chat session ID.

    Returns:
        The ConversationContext for this session.
    """
    context, created = ConversationContext.objects.get_or_create(
        session_id=session_id,
        defaults={'user': user}
    )
    if created:
        logger.info(f"Created new conversation context for session {session_id[:8]}...")
    return context


def extract_volunteer_ids_from_interactions(interactions) -> list:
    """
    Extract unique volunteer IDs from a list of interactions.

    Args:
        interactions: QuerySet or list of Interaction objects.

    Returns:
        List of unique volunteer IDs.
    """
    volunteer_ids = set()
    for interaction in interactions:
        for volunteer in interaction.volunteers.all():
            volunteer_ids.add(volunteer.id)
    return list(volunteer_ids)


def summarize_conversation(client, messages: list, current_summary: str = "") -> str:
    """
    Generate a summary of the conversation for long conversations.

    This helps maintain context without exceeding token limits.

    Args:
        client: Anthropic client instance.
        messages: List of message dicts with 'role' and 'content'.
        current_summary: Any existing summary to incorporate.

    Returns:
        A concise summary of the conversation.
    """
    if not client or len(messages) < 5:
        return current_summary

    # Build conversation text for summarization
    conv_text = ""
    for msg in messages[-10:]:  # Only summarize recent messages
        role = "User" if msg['role'] == 'user' else "Assistant"
        conv_text += f"{role}: {msg['content'][:500]}\n\n"

    summary_prompt = f"""Summarize this conversation between a team member and an AI assistant about volunteers.
Focus on:
- Which volunteers were discussed
- Key information learned about them
- Any actions or follow-ups mentioned
- The main topics covered

Previous summary (if any): {current_summary}

Recent conversation:
{conv_text}

Provide a concise 2-4 sentence summary that captures the essential context."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": summary_prompt}]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Error summarizing conversation: {e}")
        return current_summary


def filter_interactions_by_context(
    interactions,
    conversation_context: ConversationContext,
    prioritize_discussed: bool = True
) -> list:
    """
    Filter and prioritize interactions based on conversation context.

    - Excludes interactions already shown (unless we need them)
    - Prioritizes interactions about volunteers being discussed

    Args:
        interactions: QuerySet or list of Interaction objects.
        conversation_context: The ConversationContext for this session.
        prioritize_discussed: Whether to prioritize discussed volunteers.

    Returns:
        Filtered and prioritized list of interactions.
    """
    shown_ids = set(conversation_context.shown_interaction_ids or [])
    discussed_volunteer_ids = set(conversation_context.discussed_volunteer_ids or [])

    # Separate into new vs already-shown
    new_interactions = []
    shown_interactions = []

    for interaction in interactions:
        if interaction.id in shown_ids:
            shown_interactions.append(interaction)
        else:
            new_interactions.append(interaction)

    # If prioritizing discussed volunteers, sort new interactions
    if prioritize_discussed and discussed_volunteer_ids:
        def interaction_priority(interaction):
            # Higher priority (lower number) for interactions with discussed volunteers
            interaction_volunteer_ids = {v.id for v in interaction.volunteers.all()}
            overlap = len(interaction_volunteer_ids & discussed_volunteer_ids)
            return -overlap  # Negative so more overlap = higher priority

        new_interactions.sort(key=interaction_priority)

    # Return new interactions first, then shown ones if needed for context
    # Limit shown interactions to avoid too much repetition
    result = new_interactions + shown_interactions[:3]

    return result


def extract_date_from_conversation(user, session_id: str) -> Optional[str]:
    """
    Extract a recently mentioned date from conversation history.

    This helps resolve contextual references like "that day" or "that service"
    by looking for dates mentioned in recent messages.

    Args:
        user: The user making the request.
        session_id: The chat session ID.

    Returns:
        A date string if found, None otherwise.
    """
    # Get recent messages from this session
    recent_messages = ChatMessage.objects.filter(
        user=user,
        session_id=session_id
    ).order_by('-created_at')[:10]

    # Date patterns to look for in conversation
    date_patterns = [
        # "November 23, 2025" or "November 23rd, 2025"
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4}',
        # "November 23" or "November 23rd"
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?',
        # "11/23/2025" or "11-23-2025"
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
        # "last Sunday", "this Sunday"
        r'(last|this|next)\s+sunday',
    ]

    for msg in recent_messages:
        content = msg.content.lower()
        for pattern in date_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                date_str = match.group(0)
                logger.info(f"Found date '{date_str}' in conversation context")
                return date_str

    return None


def has_contextual_date_reference(message: str) -> bool:
    """
    Check if a message has a contextual date reference like "that day".

    Args:
        message: The user's message.

    Returns:
        True if the message references a date contextually.
    """
    contextual_patterns = [
        r'that\s+(day|date|service|sunday|week)',
        r'same\s+(day|date|service|sunday)',
        r'the\s+same\s+(day|date)',
        r'on\s+that\s+(day|date)',
    ]

    message_lower = message.lower()
    for pattern in contextual_patterns:
        if re.search(pattern, message_lower):
            return True
    return False


def detect_song_selection(message: str, pending_suggestions: list) -> Optional[int]:
    """
    Detect if a user message is selecting a song from pending suggestions.

    Args:
        message: The user's message.
        pending_suggestions: List of pending song suggestions from context.

    Returns:
        Index (0-based) of the selected song, or None if not a selection.
    """
    if not pending_suggestions:
        return None

    message_lower = message.lower().strip()
    num_options = len(pending_suggestions)

    # Pattern 1: Just a number (e.g., "1", "2", "3")
    if message_lower.isdigit():
        selection = int(message_lower)
        if 1 <= selection <= num_options:
            return selection - 1  # Convert to 0-based index
        return None

    # Pattern 2: Ordinal words (e.g., "first", "second", "third")
    ordinal_map = {
        'first': 1, 'one': 1, '1st': 1,
        'second': 2, 'two': 2, '2nd': 2,
        'third': 3, 'three': 3, '3rd': 3,
        'fourth': 4, 'four': 4, '4th': 4,
        'fifth': 5, 'five': 5, '5th': 5,
    }

    for ordinal, num in ordinal_map.items():
        if ordinal in message_lower and num <= num_options:
            return num - 1

    # Pattern 3: "option X", "number X", "choice X"
    option_patterns = [
        r'(?:option|number|choice|#)\s*(\d+)',
        r'(?:the\s+)?(\d+)(?:st|nd|rd|th)?\s*(?:one|option|song)?',
    ]

    for pattern in option_patterns:
        match = re.search(pattern, message_lower)
        if match:
            selection = int(match.group(1))
            if 1 <= selection <= num_options:
                return selection - 1

    # Pattern 4: Song title match - user might type part of the title
    for i, suggestion in enumerate(pending_suggestions):
        title = suggestion.get('title', '').lower()
        # Check if user typed a significant portion of the title
        if title and len(message_lower) >= 3:
            if message_lower in title or title.startswith(message_lower):
                return i

    return None


def handle_song_selection(selection_index: int, pending_suggestions: list, query_type: str = 'song_info') -> str:
    """
    Handle a song selection by fetching the full details of the selected song.

    Args:
        selection_index: 0-based index of the selected song.
        pending_suggestions: List of pending song suggestions.
        query_type: Type of data requested (lyrics, chord_chart, song_info, song_history).

    Returns:
        Formatted string with the song details.
    """
    if selection_index < 0 or selection_index >= len(pending_suggestions):
        return "\n[SONG SELECTION: Invalid selection. Please choose a number from the list.]\n"

    selected_song = pending_suggestions[selection_index]
    song_title = selected_song.get('title', '')
    song_id = selected_song.get('id')

    logger.info(f"User selected song: '{song_title}' (index {selection_index}, id {song_id})")

    from .planning_center import PlanningCenterServicesAPI
    services_api = PlanningCenterServicesAPI()

    if not services_api.is_configured:
        return "\n[SONG SELECTION: Planning Center is not configured.]\n"

    if query_type == 'song_history':
        # User wanted to know when the song was played
        usage_history = services_api.get_song_usage_history(song_title)
        if usage_history:
            return format_song_usage_history(usage_history)
        else:
            return f"\n[SONG HISTORY: Could not find usage history for '{song_title}'.]\n"
    else:
        # Get full song details with attachments - always use get_song_with_attachments
        # to ensure we fetch the actual content (lyrics, chord charts)
        song_details = services_api.get_song_with_attachments(song_title, fetch_content=True)

        if song_details:
            return format_song_details(song_details)
        else:
            return f"\n[SONG: Could not retrieve details for '{song_title}'.]\n"


def detect_confirmation(message: str) -> bool:
    """
    Detect if a user message is a confirmation/affirmation.

    Args:
        message: The user's message.

    Returns:
        True if the message is a confirmation.
    """
    message_lower = message.lower().strip()

    # Direct affirmations
    affirmations = [
        'yes', 'yeah', 'yep', 'yup', 'sure', 'ok', 'okay', 'please',
        'please do', 'go ahead', 'do it', 'yes please', 'that would be great',
        'sounds good', 'perfect', 'absolutely', 'definitely', 'of course',
        'correct', 'right', 'that\'s right', 'exactly', 'yes, please',
        'y', 'yea', 'aye', 'affirmative'
    ]

    if message_lower in affirmations:
        return True

    # Check for affirmation at the start of the message
    for affirmation in affirmations:
        if message_lower.startswith(affirmation + ' ') or message_lower.startswith(affirmation + ','):
            return True
        if message_lower.startswith(affirmation + '.') or message_lower.startswith(affirmation + '!'):
            return True

    return False


def detect_correction(message: str) -> tuple:
    """
    Detect if a user message contains a correction.

    Patterns detected:
    - "Actually, it's X not Y"
    - "No, her name is spelled X"
    - "It's X, not Y"
    - "You mean X"
    - "I meant X"
    - "The correct spelling is X"

    Args:
        message: The user's message.

    Returns:
        Tuple of (is_correction, incorrect_value, correct_value, correction_type)
    """
    import re

    message_lower = message.lower().strip()

    # Pattern: "Actually, it's X not Y" or "Actually X, not Y"
    match = re.search(
        r'actually[,.]?\s*(?:it\'?s\s+)?["\']?(\w+(?:\s+\w+)?)["\']?\s*[,.]?\s*not\s+["\']?(\w+(?:\s+\w+)?)["\']?',
        message_lower
    )
    if match:
        correct = match.group(1).strip()
        incorrect = match.group(2).strip()
        return (True, incorrect, correct, 'spelling')

    # Pattern: "No, her/his name is X" or "No, it's X"
    match = re.search(
        r'no[,.]?\s+(?:(?:her|his|their)\s+name\s+is|it\'?s)\s+["\']?(\w+(?:\s+\w+)?)["\']?',
        message_lower
    )
    if match:
        correct = match.group(1).strip()
        return (True, None, correct, 'spelling')

    # Pattern: "It's X, not Y"
    match = re.search(
        r'it\'?s\s+["\']?(\w+(?:\s+\w+)?)["\']?\s*[,.]?\s*not\s+["\']?(\w+(?:\s+\w+)?)["\']?',
        message_lower
    )
    if match:
        correct = match.group(1).strip()
        incorrect = match.group(2).strip()
        return (True, incorrect, correct, 'spelling')

    # Pattern: "The correct X is Y" or "The right X is Y"
    match = re.search(
        r'the\s+(?:correct|right)\s+(?:spelling|name|term|word)\s+is\s+["\']?(\w+(?:\s+\w+)?)["\']?',
        message_lower
    )
    if match:
        correct = match.group(1).strip()
        return (True, None, correct, 'spelling')

    # Pattern: "spelled X" or "spelt X"
    match = re.search(
        r'(?:spelled|spelt)\s+["\']?(\w+(?:\s+\w+)?)["\']?',
        message_lower
    )
    if match:
        correct = match.group(1).strip()
        return (True, None, correct, 'spelling')

    # Pattern: "should be X" or "should say X"
    match = re.search(
        r'should\s+(?:be|say)\s+["\']?(\w+(?:\s+\w+)?)["\']?(?:\s*[,.]?\s*not\s+["\']?(\w+(?:\s+\w+)?)["\']?)?',
        message_lower
    )
    if match:
        correct = match.group(1).strip()
        incorrect = match.group(2).strip() if match.group(2) else None
        return (True, incorrect, correct, 'fact')

    return (False, None, None, None)


def store_correction(incorrect: str, correct: str, correction_type: str, user, volunteer=None):
    """
    Store a learned correction in the database.

    Args:
        incorrect: The incorrect value.
        correct: The correct value.
        correction_type: Type of correction (spelling, fact, preference, context).
        user: The user providing the correction.
        volunteer: Optional volunteer this correction is about.

    Returns:
        The created or updated LearnedCorrection.
    """
    from .models import LearnedCorrection

    if not incorrect or not correct:
        return None

    # Check if this correction already exists
    existing = LearnedCorrection.objects.filter(
        incorrect_value__iexact=incorrect,
        volunteer=volunteer,
        is_active=True
    ).first()

    if existing:
        # Update if different correct value
        if existing.correct_value.lower() != correct.lower():
            existing.correct_value = correct
            existing.correction_type = correction_type
            existing.save()
        return existing

    # Create new correction
    correction = LearnedCorrection.objects.create(
        incorrect_value=incorrect,
        correct_value=correct,
        correction_type=correction_type,
        corrected_by=user,
        volunteer=volunteer
    )

    logger.info(f"Stored correction: '{incorrect}' → '{correct}' (type: {correction_type})")
    return correction


def apply_learned_corrections(text: str, volunteer=None) -> str:
    """
    Apply any learned corrections to a piece of text.

    Args:
        text: The text to correct.
        volunteer: Optional volunteer context.

    Returns:
        The text with corrections applied.
    """
    from .models import LearnedCorrection
    return LearnedCorrection.apply_corrections(text, volunteer)


def get_volunteer_knowledge_context(volunteer) -> str:
    """
    Get accumulated knowledge about a volunteer for context.

    Args:
        volunteer: The Volunteer instance.

    Returns:
        A formatted string with known information about the volunteer.
    """
    from .models import ExtractedKnowledge

    profile = ExtractedKnowledge.get_volunteer_profile(volunteer)
    if not profile:
        return ""

    parts = [f"\n[KNOWN INFORMATION ABOUT {volunteer.name.upper()}]"]

    type_labels = {
        'hobby': 'Hobbies/Interests',
        'family': 'Family',
        'preference': 'Preferences',
        'birthday': 'Birthday',
        'anniversary': 'Anniversary',
        'prayer_request': 'Prayer Requests',
        'health': 'Health',
        'work': 'Work/Career',
        'availability': 'Availability',
        'skill': 'Skills',
        'contact': 'Contact Info',
        'other': 'Other'
    }

    for knowledge_type, items in profile.items():
        label = type_labels.get(knowledge_type, knowledge_type.title())
        parts.append(f"\n{label}:")
        for key, data in items.items():
            value = data['value']
            confidence = data.get('confidence', 'medium')
            verified = " (verified)" if data.get('verified') else ""
            parts.append(f"  - {key}: {value}{verified}")

    parts.append("")
    return "\n".join(parts)


def extract_followup_date(message: str):
    """
    Extract a date from a message that might specify when to follow up.

    Args:
        message: The user's message.

    Returns:
        A date object if found, None otherwise.
    """
    from datetime import datetime, timedelta
    import re

    message_lower = message.lower().strip()
    today = datetime.now().date()

    # Patterns for relative dates
    if re.search(r'(in\s+)?a?\s*week|next\s+week|1\s+week', message_lower):
        return today + timedelta(weeks=1)
    if re.search(r'(in\s+)?two\s+weeks?|2\s+weeks?', message_lower):
        return today + timedelta(weeks=2)
    if re.search(r'(in\s+)?three\s+weeks?|3\s+weeks?', message_lower):
        return today + timedelta(weeks=3)
    if re.search(r'(in\s+)?a\s+month|next\s+month|1\s+month', message_lower):
        return today + timedelta(days=30)
    if re.search(r'tomorrow', message_lower):
        return today + timedelta(days=1)
    if re.search(r'(in\s+)?a?\s*few\s+days?|couple\s+(of\s+)?days?', message_lower):
        return today + timedelta(days=3)

    # Try to extract specific date formats
    date_patterns = [
        (r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', '%m/%d/%Y'),
        (r'(\d{1,2})-(\d{1,2})(?:-(\d{2,4}))?', '%m-%d-%Y'),
    ]

    for pattern, fmt in date_patterns:
        match = re.search(pattern, message_lower)
        if match:
            try:
                date_str = match.group(0)
                if len(date_str.split('/')[-1]) <= 2 or len(date_str.split('-')[-1]) <= 2:
                    # Add current year
                    date_str = date_str + '/' + str(today.year) if '/' in date_str else date_str + '-' + str(today.year)
                parsed = datetime.strptime(date_str, fmt)
                return parsed.date()
            except ValueError:
                pass

    # Try month day patterns
    month_pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?'
    match = re.search(month_pattern, message_lower)
    if match:
        try:
            month_str = match.group(1)
            day = int(match.group(2))
            year = int(match.group(3)) if match.group(3) else today.year
            month = datetime.strptime(month_str, '%B').month
            return datetime(year, month, day).date()
        except ValueError:
            pass

    return None


def create_followup_from_pending(pending: dict, follow_up_date, user) -> 'FollowUp':
    """
    Create a FollowUp from pending data.

    Args:
        pending: Dict with title, description, volunteer_name, category.
        follow_up_date: The date to follow up.
        user: The user creating the follow-up.

    Returns:
        The created FollowUp object.
    """
    from .models import FollowUp, Volunteer

    title = pending.get('title', 'Follow-up')
    description = pending.get('description', '')
    volunteer_name = pending.get('volunteer_name', '')
    category = pending.get('category', '')

    # Try to find the volunteer
    volunteer = None
    if volunteer_name:
        volunteer = Volunteer.objects.filter(
            normalized_name__icontains=volunteer_name.lower()
        ).first()

    followup = FollowUp.objects.create(
        created_by=user,
        volunteer=volunteer,
        title=title,
        description=description,
        category=category,
        follow_up_date=follow_up_date,
        priority='medium'
    )

    logger.info(f"Created follow-up: '{title}' for {follow_up_date}")
    return followup


def handle_pending_date_lookup(pending_lookup: dict, query_type: str = None, service_type: str = None) -> str:
    """
    Handle a pending date lookup by fetching the data from Planning Center.

    Args:
        pending_lookup: Dict with 'date', 'query_type', and optionally 'service_type'.
        query_type: Override query type if provided.
        service_type: Override service type if provided (e.g., 'HSM', 'MSM').

    Returns:
        Formatted string with the service data.
    """
    date_str = pending_lookup.get('date', '')
    lookup_type = query_type or pending_lookup.get('query_type', 'setlist')
    lookup_service_type = service_type or pending_lookup.get('service_type')

    if not date_str:
        return "\n[DATE LOOKUP: No date specified.]\n"

    logger.info(f"Handling pending date lookup: '{date_str}' (type: {lookup_type}, service_type: {lookup_service_type})")

    from .planning_center import PlanningCenterServicesAPI
    services_api = PlanningCenterServicesAPI()

    if not services_api.is_configured:
        return "\n[DATE LOOKUP: Planning Center is not configured.]\n"

    if lookup_type == 'team_schedule':
        plan_with_team = services_api.get_plan_with_team(date_str, service_type=lookup_service_type)
        if plan_with_team:
            return format_team_schedule(plan_with_team)
        else:
            return f"\n[SERVICE SCHEDULE: No service plan found for '{date_str}'.]\n"
    else:
        # Default to setlist lookup
        plan = services_api.find_plan_by_date(date_str, service_type=lookup_service_type)
        if plan:
            return format_plan_details(plan)
        else:
            return f"\n[SERVICE PLAN: No service plan found for '{date_str}'.]\n"


def query_agent(question: str, user, session_id: str) -> str:
    """
    Answer a question using RAG (Retrieval Augmented Generation):
    1. Get/create conversation context for tracking state
    2. Search for relevant interactions (with deduplication)
    3. Build context
    4. Query Claude with context
    5. Update conversation context

    Args:
        question: The user's question.
        user: The user asking the question.
        session_id: The chat session ID for conversation history.

    Returns:
        The AI assistant's response.
    """
    client = get_anthropic_client()
    if not client:
        return "I'm sorry, but the AI service is not currently available. Please check that the ANTHROPIC_API_KEY is configured."

    # Get or create conversation context for this session
    conversation_context = get_or_create_conversation_context(user, session_id)
    logger.info(f"Conversation context: {conversation_context.message_count} messages, "
                f"{len(conversation_context.shown_interaction_ids or [])} shown interactions, "
                f"{len(conversation_context.discussed_volunteer_ids or [])} discussed volunteers")

    # Check if user is selecting from pending song suggestions
    pending_suggestions = conversation_context.get_pending_song_suggestions()
    if pending_suggestions:
        selection_index = detect_song_selection(question, pending_suggestions)
        if selection_index is not None:
            logger.info(f"Detected song selection: index {selection_index}")

            # Determine what type of query this was originally (default to song_info)
            # We can infer from the most recent assistant message mentioning songs
            query_type = 'song_info'
            recent_messages = ChatMessage.objects.filter(
                user=user,
                session_id=session_id,
                role='assistant'
            ).order_by('-created_at')[:3]

            for msg in recent_messages:
                msg_lower = msg.content.lower()
                if 'when was' in msg_lower or 'played' in msg_lower or 'history' in msg_lower:
                    query_type = 'song_history'
                    break
                elif 'lyrics' in msg_lower:
                    query_type = 'lyrics'
                    break
                elif 'chord' in msg_lower:
                    query_type = 'chord_chart'
                    break

            # Handle the selection and get the song data
            song_data_context = handle_song_selection(selection_index, pending_suggestions, query_type)

            # Clear the pending suggestions
            conversation_context.clear_pending_song_suggestions()
            conversation_context.save()

            # Build a response using the selected song's data
            selected_song = pending_suggestions[selection_index]
            selected_title = selected_song.get('title', 'Unknown')

            # Save the user's selection to chat history
            ChatMessage.objects.create(
                user=user,
                session_id=session_id,
                role='user',
                content=question
            )

            # Query Claude with the selected song data
            user_name = user.display_name if user.display_name else user.username
            selection_messages = [{"role": "user", "content": f"I selected song number {selection_index + 1}: \"{selected_title}\". Please provide the information about this song."}]

            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    system=SYSTEM_PROMPT.format(
                        context=song_data_context,
                        current_date=datetime.now().strftime('%Y-%m-%d'),
                        user_name=user_name
                    ),
                    messages=selection_messages
                )
                answer = response.content[0].text
            except Exception as e:
                logger.error(f"Error querying Claude for song selection: {e}")
                answer = f"I found the song \"{selected_title}\" but encountered an error retrieving the details. Please try again."

            # Save assistant response to chat history
            ChatMessage.objects.create(
                user=user,
                session_id=session_id,
                role='assistant',
                content=answer
            )

            # Update conversation context
            conversation_context.increment_message_count(2)
            conversation_context.save()

            return answer

    # Check if user is confirming a pending date lookup
    pending_date = conversation_context.get_pending_date_lookup()
    if pending_date and detect_confirmation(question):
        logger.info(f"Detected confirmation for pending date lookup: {pending_date}")

        # Handle the date lookup
        date_data_context = handle_pending_date_lookup(pending_date)

        # Clear the pending lookup
        conversation_context.clear_pending_date_lookup()
        conversation_context.save()

        # Save the user's confirmation to chat history
        ChatMessage.objects.create(
            user=user,
            session_id=session_id,
            role='user',
            content=question
        )

        # Query Claude with the date data
        user_name = user.display_name if user.display_name else user.username
        date_str = pending_date.get('date', 'the requested date')
        lookup_messages = [{"role": "user", "content": f"Yes, please look up the service for {date_str}."}]

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                system=SYSTEM_PROMPT.format(
                    context=date_data_context,
                    current_date=datetime.now().strftime('%Y-%m-%d'),
                    user_name=user_name
                ),
                messages=lookup_messages
            )
            answer = response.content[0].text
        except Exception as e:
            logger.error(f"Error querying Claude for date lookup: {e}")
            answer = f"I found the service plan for {date_str} but encountered an error formatting the response. Please try again."

        # Save assistant response to chat history
        ChatMessage.objects.create(
            user=user,
            session_id=session_id,
            role='assistant',
            content=answer
        )

        # Update conversation context
        conversation_context.increment_message_count(2)
        conversation_context.save()

        return answer

    # Check if user is providing a date for a pending follow-up
    pending_followup = conversation_context.get_pending_followup()
    if pending_followup:
        # Try to extract a date from the message
        followup_date = extract_followup_date(question)
        if followup_date:
            logger.info(f"Creating follow-up with date: {followup_date}")

            # Create the follow-up
            followup = create_followup_from_pending(pending_followup, followup_date, user)

            # Clear the pending follow-up
            conversation_context.clear_pending_followup()
            conversation_context.save()

            # Save the user's message to chat history
            ChatMessage.objects.create(
                user=user,
                session_id=session_id,
                role='user',
                content=question
            )

            # Respond confirming the follow-up was created
            answer = f"I've created a follow-up reminder for \"{pending_followup.get('title', 'Follow-up')}\" scheduled for {followup_date.strftime('%B %d, %Y')}. You can view and manage it on the Follow-ups page."

            # Save assistant response to chat history
            ChatMessage.objects.create(
                user=user,
                session_id=session_id,
                role='assistant',
                content=answer
            )

            # Update conversation context
            conversation_context.increment_message_count(2)
            conversation_context.save()

            return answer

    # Check if this is a PCO data query (contact info, email, phone, etc.)
    pco_query, pco_query_type, pco_person_name = is_pco_data_query(question)
    pco_data_context = ""

    if pco_query and pco_person_name:
        logger.info(f"PCO data query detected: {pco_query_type} for '{pco_person_name}'")
        from .planning_center import PlanningCenterAPI
        pco_api = PlanningCenterAPI()

        if pco_api.is_configured:
            # Use search with suggestions to handle misspellings
            search_result = pco_api.search_person_with_suggestions(pco_person_name)

            if search_result['found'] and search_result['details']:
                pco_data_context = format_pco_details(search_result['details'], pco_query_type)
                logger.info(f"Found PCO data for {search_result['details'].get('name')}")
            else:
                # No exact match - get suggestions from both PCO and local database
                pco_suggestions = search_result.get('suggestions', [])
                local_suggestions = get_local_volunteer_suggestions(pco_person_name)
                pco_data_context = format_pco_suggestions(
                    pco_person_name,
                    pco_suggestions,
                    local_suggestions
                )
                logger.info(f"No PCO match for '{pco_person_name}', providing {len(pco_suggestions)} PCO + {len(local_suggestions)} local suggestions")
        else:
            logger.warning("PCO query detected but Planning Center is not configured")

    # Check if this is a song/setlist query
    song_query, song_query_type, song_value = is_song_or_setlist_query(question)
    song_data_context = ""

    if song_query:
        logger.info(f"Song query detected: {song_query_type} for '{song_value}'")
        from .planning_center import PlanningCenterServicesAPI
        services_api = PlanningCenterServicesAPI()

        if services_api.is_configured:
            # Check if user is asking about lyrics/chords (even in setlist context)
            wants_lyrics_or_chords = bool(re.search(r'lyrics?|chords?|words|chart', question.lower()))

            # Detect service type from the question (e.g., HSM, MSM)
            # If none specified, will default to main Sunday morning service
            requested_service_type = detect_service_type_from_question(question)

            if song_query_type == 'team_schedule':
                # Looking for team/volunteer schedule for a service
                date_to_lookup = song_value

                # If no date extracted but message has contextual reference, look up from conversation
                if not date_to_lookup and has_contextual_date_reference(question):
                    logger.info("Contextual date reference detected, searching conversation history")
                    date_to_lookup = extract_date_from_conversation(user, session_id)
                    if date_to_lookup:
                        logger.info(f"Resolved contextual date reference to: {date_to_lookup}")

                if date_to_lookup:
                    plan_with_team = services_api.get_plan_with_team(date_to_lookup, service_type=requested_service_type)
                    if plan_with_team:
                        song_data_context = format_team_schedule(plan_with_team)
                        logger.info(f"Found plan for {date_to_lookup} with {len(plan_with_team.get('team_members', []))} team members")
                    else:
                        song_data_context = f"\n[SERVICE SCHEDULE: No service plan found for '{date_to_lookup}'. The AI should ask if the user wants to try a different date.]\n"
                        # Store the date as pending so user can confirm
                        conversation_context.set_pending_date_lookup(date_to_lookup, 'team_schedule')
                        conversation_context.save()
                        logger.info(f"Stored pending date lookup for '{date_to_lookup}' (team_schedule)")
                else:
                    song_data_context = "\n[SERVICE SCHEDULE: Please specify a date to see the volunteer schedule (e.g., 'this Sunday', 'November 30', 'next Sunday').]\n"

            elif song_query_type == 'setlist':
                # Looking for a service plan/setlist
                date_to_lookup = song_value

                # If no date extracted but message has contextual reference, look up from conversation
                if not date_to_lookup and has_contextual_date_reference(question):
                    logger.info("Contextual date reference detected, searching conversation history")
                    date_to_lookup = extract_date_from_conversation(user, session_id)
                    if date_to_lookup:
                        logger.info(f"Resolved contextual date reference to: {date_to_lookup}")

                if date_to_lookup:
                    plan = services_api.find_plan_by_date(date_to_lookup, service_type=requested_service_type)
                    if plan:
                        song_data_context = format_plan_details(plan)
                        logger.info(f"Found plan for {date_to_lookup} with {len(plan.get('songs', []))} songs")

                        # If asking about lyrics/chords, also fetch attachments for songs in the plan
                        if wants_lyrics_or_chords and plan.get('songs'):
                            song_details_parts = []
                            for song in plan.get('songs', [])[:5]:  # Limit to first 5 to avoid timeout
                                song_title = song.get('title')
                                if song_title:
                                    song_details = services_api.get_song_with_attachments(song_title)
                                    if song_details:
                                        song_details_parts.append(format_song_details(song_details))
                                        logger.info(f"Fetched attachments for '{song_title}'")
                            if song_details_parts:
                                song_data_context += "\n" + "\n".join(song_details_parts)
                    else:
                        song_data_context = f"\n[SERVICE PLAN: No service plan found for '{date_to_lookup}'. The AI should ask if the user wants to try a different date or confirm this is the correct date.]\n"
                        # Store the date as pending so user can confirm
                        conversation_context.set_pending_date_lookup(date_to_lookup, 'setlist')
                        conversation_context.save()
                        logger.info(f"Stored pending date lookup for '{date_to_lookup}'")
                else:
                    # No date specified - get recent plans
                    recent_plans = services_api.get_recent_plans(limit=5)
                    if recent_plans:
                        parts = ["\n[RECENT SERVICE PLANS]"]
                        for plan in recent_plans:
                            plan_attrs = plan.get('attributes', {})
                            st_name = plan.get('service_type_name', 'Unknown')
                            parts.append(f"- {plan_attrs.get('dates', 'Unknown date')} ({st_name})")
                        parts.append("\nAsk about a specific date to see the song set.")
                        parts.append("[END RECENT PLANS]\n")
                        song_data_context = '\n'.join(parts)

            elif song_query_type == 'song_history':
                # Looking for when a song was last used in services
                # Try to get the song title from context or previous messages
                song_title = song_value
                if not song_title:
                    # Check if we can extract a song name from the question
                    # This handles cases like "when was this song last used"
                    # where "this song" refers to a previous song in the conversation
                    song_data_context = "\n[SONG HISTORY: Please specify which song you want to look up the service history for.]\n"
                else:
                    usage_history = services_api.get_song_usage_history(song_title)
                    if usage_history:
                        song_data_context = format_song_usage_history(usage_history, conversation_context)
                        logger.info(f"Got usage history for '{song_title}': {usage_history.get('total_times_used', 0)} uses")
                        # Store the song title for follow-up queries (e.g., "give me the lyrics to the bridge")
                        if usage_history.get('found'):
                            actual_title = usage_history.get('song_title', song_title)
                            conversation_context.set_current_song(actual_title)
                            conversation_context.save()
                            logger.info(f"Stored current song context: '{actual_title}'")
                    else:
                        song_data_context = f"\n[SONG HISTORY: Could not find song '{song_title}' in the Planning Center library.]\n"

            elif song_query_type in ['chord_chart', 'lyrics', 'song_search', 'song_info']:
                # Looking for song info or attachments - use fuzzy search with suggestions
                # If no song title provided, check if we have a current song in context
                song_to_lookup = song_value

                # Check if the extracted value is a reference to a previous song
                # (e.g., "the song", "this song", "that song", "it")
                song_reference_patterns = [
                    r'^(the|this|that)\s+song$',
                    r'^it$',
                    r'^(the|this|that)\s+one$',
                    r'^same\s+song$',
                ]
                is_song_reference = False
                if song_to_lookup:
                    for pattern in song_reference_patterns:
                        if re.match(pattern, song_to_lookup.lower().strip()):
                            is_song_reference = True
                            logger.info(f"Detected song reference '{song_to_lookup}', will use context")
                            break

                # Use current song from context if no title provided OR if it's a reference
                if not song_to_lookup or is_song_reference:
                    current_song_title = conversation_context.get_current_song_title()
                    if current_song_title:
                        song_to_lookup = current_song_title
                        logger.info(f"Using current song from context: '{current_song_title}'")

                if song_to_lookup:
                    search_result = services_api.search_song_with_suggestions(song_to_lookup)

                    if search_result['found'] and search_result['song']:
                        song_data_context = format_song_details(search_result['song'])
                        # Store the song for future follow-ups
                        actual_title = search_result['song'].get('title', song_to_lookup)
                        conversation_context.set_current_song(actual_title)
                        conversation_context.save()
                        logger.info(f"Found song '{actual_title}' with {len(search_result['song'].get('all_attachments', []))} attachments")
                    elif search_result['suggestions']:
                        # No exact match - provide suggestions for AI to ask user and store for selection
                        song_data_context = format_song_suggestions(song_to_lookup, search_result['suggestions'], conversation_context)
                        logger.info(f"No match for '{song_to_lookup}', providing {len(search_result['suggestions'])} suggestions")
                    else:
                        song_data_context = f"\n[SONG: No songs found matching '{song_to_lookup}'. The song may not be in the Planning Center library.]\n"
                else:
                    song_data_context = "\n[SONG: Please specify a song title to search for.]\n"
        else:
            logger.warning("Song query detected but Planning Center is not configured")

    # Check if this is an aggregate question requiring broader data access
    aggregate, category = is_aggregate_question(question)

    # Step 1: Get relevant interactions
    relevant_interactions = []

    if aggregate:
        # For aggregate questions, get ALL interactions to ensure comprehensive answers
        logger.info(f"Aggregate question detected (category: {category}). Fetching all interactions.")
        all_interactions = Interaction.objects.select_related('user').prefetch_related('volunteers').all()

        # For category-specific queries, prioritize interactions with relevant extracted data
        if category != 'general':
            # Map categories to extracted_data fields
            category_fields = {
                'food': ['favorites'],
                'hobbies': ['hobbies'],
                'prayer': ['prayer_requests'],
                'family': ['family'],
                'birthday': ['birthday'],
                'availability': ['availability'],
                'feedback': ['feedback'],
            }

            fields = category_fields.get(category, [])
            prioritized = []
            other = []

            for interaction in all_interactions:
                has_relevant_data = False
                if interaction.ai_extracted_data:
                    for field in fields:
                        value = interaction.ai_extracted_data.get(field)
                        if value and (isinstance(value, list) and len(value) > 0 or
                                      isinstance(value, dict) and any(v for v in value.values()) or
                                      isinstance(value, str) and value):
                            has_relevant_data = True
                            break

                if has_relevant_data:
                    prioritized.append(interaction)
                else:
                    other.append(interaction)

            # Combine prioritized first, then others (limit to prevent token overflow)
            relevant_interactions = prioritized[:100] + other[:50]
            logger.info(f"Found {len(prioritized)} interactions with {category} data, {len(other)} others")
        else:
            # General aggregate - get all (up to 150 to prevent token overflow)
            relevant_interactions = list(all_interactions[:150])
    else:
        # Standard semantic search for non-aggregate questions
        question_embedding = get_embedding(question)

        if question_embedding:
            # Get more interactions than needed, then filter by context
            raw_interactions = search_similar(question_embedding, limit=30)
            # Filter and prioritize based on conversation context
            relevant_interactions = filter_interactions_by_context(
                raw_interactions,
                conversation_context,
                prioritize_discussed=True
            )[:20]  # Limit to top 20 after filtering
        else:
            # Fallback: get recent interactions if embeddings unavailable
            raw_interactions = list(Interaction.objects.all()[:30])
            relevant_interactions = filter_interactions_by_context(
                raw_interactions,
                conversation_context,
                prioritize_discussed=True
            )[:20]

    # Track which interactions we're showing (for context deduplication)
    shown_interaction_ids = [i.id for i in relevant_interactions]

    # Step 2: Build context from relevant interactions
    context_parts = []
    new_interaction_ids = []  # Track new interactions being shown for the first time
    already_shown_ids = set(conversation_context.shown_interaction_ids or [])

    for interaction in relevant_interactions:
        volunteers = ", ".join([v.name for v in interaction.volunteers.all()])
        date_str = interaction.created_at.strftime('%Y-%m-%d') if interaction.created_at else 'Unknown'

        # Mark if this interaction was previously shown
        previously_shown = interaction.id in already_shown_ids
        marker = " (previously discussed)" if previously_shown else ""

        if not previously_shown:
            new_interaction_ids.append(interaction.id)

        context_parts.append(f"""
--- Interaction from {date_str}{marker} ---
Volunteers: {volunteers or 'Not specified'}
Notes: {interaction.content}
Summary: {interaction.ai_summary or 'No summary'}
Extracted Data: {json.dumps(interaction.ai_extracted_data) if interaction.ai_extracted_data else 'None'}
""")

    if context_parts:
        context = "\n".join(context_parts)
        if aggregate:
            context = f"[AGGREGATE QUERY - You have access to {len(relevant_interactions)} interactions covering the full team. Analyze ALL the data below to provide comprehensive team-wide insights.]\n\n" + context
    else:
        context = "No relevant interactions found in the database."

    # Add learned knowledge about discussed volunteers
    # This gives Aria accumulated knowledge about volunteers from past interactions
    try:
        from .models import ExtractedKnowledge
        discussed_vols = conversation_context.discussed_volunteer_ids or []
        # Also extract volunteer names from the current question
        for interaction in relevant_interactions:
            for vol in interaction.volunteers.all():
                if vol.id not in discussed_vols:
                    discussed_vols.append(vol.id)

        # Get knowledge context for discussed volunteers (limit to 5 to avoid token overflow)
        knowledge_context_parts = []
        for vol_id in discussed_vols[:5]:
            try:
                vol = Volunteer.objects.get(id=vol_id)
                vol_knowledge = get_volunteer_knowledge_context(vol)
                if vol_knowledge:
                    knowledge_context_parts.append(vol_knowledge)
            except Volunteer.DoesNotExist:
                pass

        if knowledge_context_parts:
            knowledge_context = "\n[LEARNED KNOWLEDGE FROM PAST INTERACTIONS]\n" + "\n".join(knowledge_context_parts)
            context = knowledge_context + "\n" + context
            logger.info(f"Added learned knowledge for {len(knowledge_context_parts)} volunteers")
    except Exception as e:
        logger.error(f"Error adding learned knowledge to context: {e}")

    # Check if user is providing a correction and learn from it
    try:
        is_correction, incorrect, correct, correction_type = detect_correction(question)
        if is_correction and correct:
            # Try to find which volunteer this correction might be about
            correction_volunteer = None
            for interaction in relevant_interactions:
                for vol in interaction.volunteers.all():
                    if incorrect and incorrect.lower() in vol.name.lower():
                        correction_volunteer = vol
                        break
                    if correct.lower() in vol.name.lower():
                        correction_volunteer = vol
                        break
                if correction_volunteer:
                    break

            # Store the correction for future use
            if incorrect:
                store_correction(incorrect, correct, correction_type, user, correction_volunteer)
                logger.info(f"Learned correction: '{incorrect}' → '{correct}'")
    except Exception as e:
        logger.error(f"Error processing correction: {e}")

    # Add PCO data to context if available
    if pco_data_context:
        context = pco_data_context + "\n" + context

    # Add song/setlist data to context if available
    if song_data_context:
        context = song_data_context + "\n" + context

    # Step 3: Get chat history for this session
    all_history = ChatMessage.objects.filter(
        user=user,
        session_id=session_id
    ).order_by('created_at')

    # For long conversations, use summarization to maintain context
    history_count = all_history.count()
    messages = []

    if conversation_context.should_summarize() and conversation_context.conversation_summary:
        # Include summary as a system-like context for long conversations
        summary_context = f"\n[CONVERSATION SUMMARY: {conversation_context.conversation_summary}]\n"
        context = summary_context + context

        # Only include recent messages (last 10) plus the summary
        recent_history = list(all_history[max(0, history_count - 10):])
        messages = [{"role": msg.role, "content": msg.content} for msg in recent_history]
        logger.info(f"Using conversation summary with {len(recent_history)} recent messages")
    else:
        # Normal case: include up to 20 recent messages
        history = list(all_history[:20])
        messages = [{"role": msg.role, "content": msg.content} for msg in history]

    messages.append({"role": "user", "content": question})

    # Step 4: Query Claude
    try:
        user_name = user.display_name if user.display_name else user.username
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=SYSTEM_PROMPT.format(
                context=context,
                current_date=datetime.now().strftime('%Y-%m-%d'),
                user_name=user_name
            ),
            messages=messages
        )
        answer = response.content[0].text
    except Exception as e:
        logger.error(f"Error querying Claude: {e}")
        return f"I encountered an error while processing your question. Please try again later."

    # Step 5: Save to chat history
    ChatMessage.objects.create(
        user=user,
        session_id=session_id,
        role='user',
        content=question
    )
    ChatMessage.objects.create(
        user=user,
        session_id=session_id,
        role='assistant',
        content=answer
    )

    # Step 6: Update conversation context
    # Add newly shown interactions
    if new_interaction_ids:
        conversation_context.add_shown_interactions(new_interaction_ids)
        logger.info(f"Added {len(new_interaction_ids)} new interactions to shown list")

    # Add discussed volunteers from the interactions we showed
    discussed_volunteer_ids = extract_volunteer_ids_from_interactions(relevant_interactions)
    if discussed_volunteer_ids:
        conversation_context.add_discussed_volunteers(discussed_volunteer_ids)

    # Increment message count (user + assistant = 2 messages)
    conversation_context.increment_message_count(2)

    # Generate summary if conversation is getting long and we don't have one yet
    if conversation_context.should_summarize() and not conversation_context.conversation_summary:
        all_messages = [{"role": msg.role, "content": msg.content}
                        for msg in all_history]
        all_messages.append({"role": "user", "content": question})
        all_messages.append({"role": "assistant", "content": answer})

        new_summary = summarize_conversation(client, all_messages, "")
        if new_summary:
            conversation_context.conversation_summary = new_summary
            logger.info(f"Generated conversation summary: {new_summary[:100]}...")

    # Save the updated context
    conversation_context.save()

    return answer


def detect_interaction_intent(message: str) -> bool:
    """
    Detect if a message appears to be logging a new interaction vs asking a question.

    Args:
        message: The user's message.

    Returns:
        True if the message appears to be logging an interaction, False if it's a question.
    """
    message_lower = message.lower().strip()

    # Check for explicit interaction logging prefixes
    interaction_prefixes = [
        'log interaction:',
        'log:',
        'interaction:',
        'talked with',
        'talked to',
        'spoke with',
        'spoke to',
        'met with',
        'met ',
        'had coffee with',
        'chatted with',
        'conversation with',
    ]

    for prefix in interaction_prefixes:
        if message_lower.startswith(prefix):
            return True

    # Check for question indicators
    question_indicators = [
        'what ',
        'who ',
        'where ',
        'when ',
        'why ',
        'how ',
        'which ',
        'is ',
        'are ',
        'do ',
        'does ',
        'can ',
        'could ',
        'would ',
        'should ',
        'tell me',
        'show me',
        'find ',
        'search ',
        'list ',
        '?',
    ]

    for indicator in question_indicators:
        if indicator in message_lower:
            return False

    # Default to treating longer messages as interactions
    return len(message) > 100
