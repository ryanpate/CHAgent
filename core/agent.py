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

from .models import Interaction, Volunteer, ChatMessage
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
        'setlist': r'(setlist|song\s*set|what\s+songs?\s+(did|do|are|were|will)|songs?\s+(from|for|on|we\s+(play|sang|did))|(last|this|next)\s+sunday|worship\s+set)',
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
        ]

        for pattern in title_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                extracted_value = match.group(1).strip()
                # Clean up common trailing words
                extracted_value = re.sub(r'\s+(chord|chart|lyric|song)s?$', '', extracted_value, flags=re.IGNORECASE)
                break

        # Try to extract date for setlist queries
        if query_type == 'setlist' and not extracted_value:
            date_patterns = [
                r'(last\s+sunday|this\s+sunday|next\s+sunday|yesterday|today)',
                r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',
                r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
                r'(\d{1,2}-\d{1,2}(?:-\d{2,4})?)',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    extracted_value = match.group(1)
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
- IMPORTANT: When song data (lyrics, chord charts) is provided from Planning Center, you may display it fully. The church has proper CCLI licensing for all songs in their Planning Center account. This is licensed content that authenticated team members are authorized to access. Do not refuse to show lyrics or chord chart content that comes from Planning Center data.

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


def query_agent(question: str, user, session_id: str) -> str:
    """
    Answer a question using RAG (Retrieval Augmented Generation):
    1. Search for relevant interactions
    2. Build context
    3. Query Claude with context

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
            if song_query_type == 'setlist':
                # Looking for a service plan/setlist
                if song_value:
                    plan = services_api.find_plan_by_date(song_value)
                    if plan:
                        song_data_context = format_plan_details(plan)
                        logger.info(f"Found plan for {song_value} with {len(plan.get('songs', []))} songs")
                    else:
                        song_data_context = f"\n[SERVICE PLAN: No service plan found for '{song_value}'. Try specifying a different date like 'last Sunday' or 'December 1'.]\n"
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

            elif song_query_type in ['chord_chart', 'lyrics', 'song_search', 'song_info']:
                # Looking for song info or attachments
                if song_value:
                    song_details = services_api.get_song_with_attachments(song_value)
                    if song_details:
                        song_data_context = format_song_details(song_details)
                        logger.info(f"Found song '{song_details.get('title')}' with {len(song_details.get('all_attachments', []))} attachments")
                    else:
                        song_data_context = f"\n[SONG: No song found matching '{song_value}'. Check the spelling or try a different search term.]\n"
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
            relevant_interactions = search_similar(question_embedding, limit=20)
        else:
            # Fallback: get recent interactions if embeddings unavailable
            relevant_interactions = list(Interaction.objects.all()[:20])

    # Step 2: Build context from relevant interactions
    context_parts = []
    for interaction in relevant_interactions:
        volunteers = ", ".join([v.name for v in interaction.volunteers.all()])
        date_str = interaction.created_at.strftime('%Y-%m-%d') if interaction.created_at else 'Unknown'
        context_parts.append(f"""
--- Interaction from {date_str} ---
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
    history = ChatMessage.objects.filter(
        user=user,
        session_id=session_id
    ).order_by('created_at')[:20]

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
