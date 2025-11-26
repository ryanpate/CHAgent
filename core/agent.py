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
        # Common patterns for extracting names
        name_patterns = [
            r"(?:for|of|about|contact|reach|call|email)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'s\s+(?:contact|email|phone|address|birthday)",
            r"what\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'s",
            r"(?:where\s+does|when\s+(?:was|is))\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        ]

        for pattern in name_patterns:
            match = re.search(pattern, message)
            if match:
                person_name = match.group(1).strip()
                # Filter out common false positives
                false_positives = ['I', 'What', 'Where', 'When', 'How', 'Can', 'Do', 'Does', 'Is', 'Are', 'The']
                if person_name not in false_positives:
                    break
                else:
                    person_name = None

    return is_pco_query, query_type, person_name


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
    song_query_patterns = {
        'setlist': r'(setlist|song\s*set|what\s+(other\s+)?songs?\s+(did|do|are|were|will|was)|songs?\s+(from|for|on|we\s+(play|sang|did))|(last|this|next)\s+sunday|worship\s+set|played\s+on|was\s+played|last\s+played|(played|songs?)\s+(that|on\s+that)\s+(day|date|service|sunday)|(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2})',
        'song_history': r'when\s+(was|did)\s+(the\s+)?(this\s+)?song\s+.*(used|played|performed|scheduled)|when\s+was\s+.+\s+played\s+(last|most\s+recently)|song\s+(usage|history)|last\s+time\s+.*(song|played|used)|how\s+(often|many\s+times)\s+.*(song|played)',
        'chord_chart': r'chord\s*chart|chords?\s+(for|to)|lead\s+sheet|charts?\s+(for|to)',
        'lyrics': r'lyrics?\s+(for|to)|words?\s+(for|to)',
        'song_search': r'(find|search|look\s*up|get|show)\s+(the\s+)?(song|music)',
        'song_info': r'(what\s+key|which\s+key|bpm|tempo|how\s+(long|fast))\s+.*(song|play)',
    }

    is_song_query = False
    query_type = None

    for qtype, pattern in song_query_patterns.items():
        if re.search(pattern, message_lower):
            is_song_query = True
            query_type = qtype
            break

    # Extract song title or date from the question
    extracted_value = None

    if is_song_query:
        # Try to extract song title (in quotes or after common patterns)
        title_patterns = [
            r'"([^"]+)"',  # Quoted title
            r"'([^']+)'",  # Single-quoted title
            r'(?:chord\s*chart|chords?|lyrics?|song)\s+(?:for|to)\s+["\']?([^"\'?]+)["\']?',
            r'(?:find|search|look\s*up|get)\s+(?:the\s+)?(?:song\s+)?["\']?([^"\'?]+)["\']?',
            # Song history patterns - match "when was the song [title] played last?"
            r'when\s+(?:was|did)\s+(?:the\s+)?song\s+["\']?(.+?)["\']?\s+(?:last\s+)?(?:used|played|performed|scheduled)',
            r'when\s+(?:was|did)\s+(?:the\s+)?song\s+["\']?(.+?)["\']?\s+(?:used|played|performed|scheduled)\s+(?:last|most\s+recently)',
            r'when\s+(?:was|did)\s+["\']?([^"\'?]+?)["\']?\s+(?:last\s+)?(?:used|played|performed|scheduled)',
            r'when\s+was\s+["\']?(.+?)["\']?\s+played\s+(?:last|most\s+recently)',
            r'(?:history|usage)\s+(?:for|of)\s+["\']?([^"\'?]+)["\']?',
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
                break

        # Try to extract date for setlist queries
        if query_type == 'setlist' and not extracted_value:
            date_patterns = [
                r'(last\s+sunday|this\s+sunday|next\s+sunday|yesterday|today)',
                r'(?:on\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?',
                r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
                r'(\d{1,2}-\d{1,2}(?:-\d{2,4})?)',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    extracted_value = match.group(0).replace('on ', '')  # Use full match, remove leading "on "
                    break

    return is_song_query, query_type, extracted_value


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
                parts.append(f"\n    LYRICS ({arr.get('name', 'Default')} arrangement):")
                parts.append("    " + arr.get('lyrics').replace('\n', '\n    '))

            # Include chord chart if available
            if arr.get('chord_chart'):
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
            parts.append(f"\nOther Available Files ({len(other_attachments)}):")
            for attach in other_attachments:
                filename = attach.get('filename', 'Unknown file')
                file_type = attach.get('file_type', '')
                url = attach.get('url', '')
                arr_key = attach.get('arrangement_key', '')

                attach_info = f"  - {filename}"
                if arr_key:
                    attach_info += f" (Key: {arr_key})"
                if file_type:
                    attach_info += f" [{file_type}]"
                parts.append(attach_info)

                if url:
                    parts.append(f"    Download: {url}")
    else:
        parts.append("\nNo attachments found for this song.")

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
- IMPORTANT: When song data (lyrics, chord charts) is provided from Planning Center, you MUST display it directly in your response - do NOT just offer download links. The church has proper CCLI licensing for all songs in their Planning Center account. This is licensed content that authenticated team members are authorized to access.
- When a user asks for specific sections (e.g., "2nd verse", "chorus"), find and display just that section from the lyrics data provided. Look for section markers like "Verse 1", "Verse 2", "Chorus", "Bridge", etc. in the lyrics content.
- If lyrics or chord chart content is included in the context data, always display it directly rather than pointing to download links.

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

            if song_query_type == 'setlist':
                # Looking for a service plan/setlist
                date_to_lookup = song_value

                # If no date extracted but message has contextual reference, look up from conversation
                if not date_to_lookup and has_contextual_date_reference(question):
                    logger.info("Contextual date reference detected, searching conversation history")
                    date_to_lookup = extract_date_from_conversation(user, session_id)
                    if date_to_lookup:
                        logger.info(f"Resolved contextual date reference to: {date_to_lookup}")

                if date_to_lookup:
                    plan = services_api.find_plan_by_date(date_to_lookup)
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
                        song_data_context = f"\n[SERVICE PLAN: No service plan found for '{date_to_lookup}'. Try specifying a different date like 'last Sunday' or 'December 1'.]\n"
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
                    else:
                        song_data_context = f"\n[SONG HISTORY: Could not find song '{song_title}' in the Planning Center library.]\n"

            elif song_query_type in ['chord_chart', 'lyrics', 'song_search', 'song_info']:
                # Looking for song info or attachments - use fuzzy search with suggestions
                if song_value:
                    search_result = services_api.search_song_with_suggestions(song_value)

                    if search_result['found'] and search_result['song']:
                        song_data_context = format_song_details(search_result['song'])
                        logger.info(f"Found song '{search_result['song'].get('title')}' with {len(search_result['song'].get('all_attachments', []))} attachments")
                    elif search_result['suggestions']:
                        # No exact match - provide suggestions for AI to ask user and store for selection
                        song_data_context = format_song_suggestions(song_value, search_result['suggestions'], conversation_context)
                        logger.info(f"No match for '{song_value}', providing {len(search_result['suggestions'])} suggestions")
                    else:
                        song_data_context = f"\n[SONG: No songs found matching '{song_value}'. The song may not be in the Planning Center library.]\n"
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
