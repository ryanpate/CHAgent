"""
AI Agent module for processing interactions and answering questions.
Uses Anthropic Claude API for natural language understanding.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from django.conf import settings

from .models import Interaction, Volunteer, ChatMessage
from .embeddings import get_embedding, search_similar

logger = logging.getLogger(__name__)

# Try to import Anthropic, handle gracefully if not available
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    anthropic = None


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
    3. Identify/create volunteer records
    4. Save interaction with metadata

    Args:
        content: The interaction note content.
        user: The user who logged the interaction.

    Returns:
        Dictionary with interaction, extracted data, and volunteers.
    """
    client = get_anthropic_client()
    extracted = {}
    volunteers = []

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

    # Step 3: Find or create volunteers
    for vol_data in extracted.get('volunteers', []):
        name = vol_data.get('name', '').strip()
        if not name:
            continue

        volunteer, created = Volunteer.objects.get_or_create(
            normalized_name=name.lower().strip(),
            defaults={
                'name': name,
                'team': vol_data.get('team', '')
            }
        )
        # Update team if provided and not already set
        if not volunteer.team and vol_data.get('team'):
            volunteer.team = vol_data.get('team')
            volunteer.save()

        volunteers.append(volunteer)

    # Step 4: Create interaction
    interaction = Interaction.objects.create(
        user=user,
        content=content,
        ai_summary=extracted.get('summary', ''),
        ai_extracted_data=extracted.get('extracted_data', {}),
        embedding_json=embedding
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

    # Step 1: Get question embedding and find relevant interactions
    question_embedding = get_embedding(question)

    relevant_interactions = []
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

    context = "\n".join(context_parts) if context_parts else "No relevant interactions found in the database."

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
