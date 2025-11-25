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
