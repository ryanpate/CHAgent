"""
Planning Center Integration for syncing and matching volunteers.
Optional feature - requires PLANNING_CENTER_APP_ID and PLANNING_CENTER_SECRET.
"""
import logging
import re
from difflib import SequenceMatcher
from typing import Optional

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache keys for PCO data
PCO_PEOPLE_CACHE_KEY = 'pco_people_list'
PCO_PLANS_CACHE_KEY = 'pco_plans_list'
PCO_BLOCKOUTS_CACHE_KEY = 'pco_person_blockouts'  # Per-person blockouts cache
PCO_CACHE_TIMEOUT = 3600  # 1 hour
PCO_PLANS_CACHE_TIMEOUT = 900  # 15 minutes for plans (they change more often)
PCO_BLOCKOUTS_CACHE_TIMEOUT = 14400  # 4 hours for blockouts (they change rarely)

# Rate limiting settings for blockout queries
PCO_BLOCKOUT_RATE_LIMIT_CALLS = 10  # Number of calls before delay
PCO_BLOCKOUT_RATE_LIMIT_DELAY = 1.0  # Delay in seconds after rate limit threshold

# Default service type - Cherry Hills Sunday Morning Main Service
# This is used when no specific service type is requested
DEFAULT_SERVICE_TYPE_NAME = 'Cherry Hills Morning Main'
# Keywords to identify non-main services (case-insensitive)
YOUTH_SERVICE_KEYWORDS = ['hsm', 'msm', 'high school', 'middle school', 'youth', 'student']


class PlanningCenterAPI:
    """Client for Planning Center Online API."""

    BASE_URL = "https://api.planningcenteronline.com"

    def __init__(self):
        self.app_id = settings.PLANNING_CENTER_APP_ID
        self.secret = settings.PLANNING_CENTER_SECRET

    @property
    def is_configured(self) -> bool:
        """Check if Planning Center credentials are configured."""
        return bool(self.app_id and self.secret)

    def _get(self, endpoint: str, params: dict = None, retry_on_429: bool = True) -> dict:
        """
        Make authenticated GET request to Planning Center API.

        Args:
            endpoint: API endpoint path.
            params: Optional query parameters.
            retry_on_429: If True, retry with exponential backoff on rate limit errors.

        Returns:
            JSON response dict or empty dict on error.
        """
        import time

        if not self.is_configured:
            logger.warning("Planning Center not configured")
            return {}

        url = f"{self.BASE_URL}{endpoint}"
        max_retries = 3 if retry_on_429 else 1
        base_delay = 2.0  # Start with 2 second delay

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    auth=(self.app_id, self.secret),
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < max_retries - 1:
                    # Rate limited - wait with exponential backoff
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited (429), waiting {delay}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(delay)
                    continue
                logger.error(f"Planning Center API error: {e}")
                raise  # Re-raise to let caller handle it
            except requests.RequestException as e:
                logger.error(f"Planning Center API error: {e}")
                return {}

        return {}

    def _get_all_pages(self, endpoint: str, params: dict = None) -> list:
        """
        Fetch all pages from a paginated Planning Center endpoint.

        Args:
            endpoint: API endpoint path.
            params: Optional query parameters.

        Returns:
            List of all data items across all pages.
        """
        all_data = []
        params = params or {}
        params['per_page'] = 100  # Max per page

        while endpoint:
            result = self._get(endpoint, params)
            all_data.extend(result.get('data', []))

            # Check for next page
            links = result.get('links', {})
            next_url = links.get('next')
            if next_url:
                # Extract just the endpoint part from full URL
                endpoint = next_url.replace(self.BASE_URL, '')
                params = {}  # Params are in the URL for pagination
            else:
                endpoint = None

        return all_data

    def get_people(self, team_id: str = None, use_cache: bool = True) -> list:
        """
        Fetch people from Planning Center.

        Args:
            team_id: Optional team ID to filter by.
            use_cache: Whether to use cached results.

        Returns:
            List of person records.
        """
        if not self.is_configured:
            return []

        # Check cache first
        cache_key = f"{PCO_PEOPLE_CACHE_KEY}_{team_id or 'all'}"
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                return cached

        if team_id:
            endpoint = f"/services/v2/teams/{team_id}/people"
        else:
            endpoint = "/people/v2/people"

        people = self._get_all_pages(endpoint)

        # Cache results
        if people:
            cache.set(cache_key, people, PCO_CACHE_TIMEOUT)

        return people

    def get_teams(self) -> dict:
        """Fetch all teams from Planning Center Services."""
        return self._get("/services/v2/teams")

    def search_people(self, query: str) -> list:
        """
        Search for people in Planning Center by name.

        Args:
            query: Name to search for.

        Returns:
            List of matching person records.
        """
        if not self.is_configured:
            return []

        # PCO People API supports searching
        endpoint = "/people/v2/people"
        params = {
            'where[search_name]': query,
            'per_page': 25
        }

        result = self._get(endpoint, params)
        return result.get('data', [])

    def get_person_by_id(self, person_id: str) -> Optional[dict]:
        """
        Get a specific person by their PCO ID.

        Args:
            person_id: Planning Center person ID.

        Returns:
            Person record or None.
        """
        if not self.is_configured:
            return None

        endpoint = f"/people/v2/people/{person_id}"
        result = self._get(endpoint)
        return result.get('data')

    def get_person_details(self, person_id: str) -> Optional[dict]:
        """
        Get detailed information about a person including contact info.

        Args:
            person_id: Planning Center person ID.

        Returns:
            Dict with person details, emails, phone numbers, and addresses.
        """
        if not self.is_configured:
            return None

        # Get basic person info
        person = self.get_person_by_id(person_id)
        if not person:
            return None

        attrs = person.get('attributes', {})
        details = {
            'id': person_id,
            'name': f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip(),
            'first_name': attrs.get('first_name', ''),
            'last_name': attrs.get('last_name', ''),
            'birthdate': attrs.get('birthdate'),
            'anniversary': attrs.get('anniversary'),
            'gender': attrs.get('gender'),
            'membership': attrs.get('membership'),
            'status': attrs.get('status'),
            'emails': [],
            'phone_numbers': [],
            'addresses': [],
            'teams': [],
            'recent_schedules': [],
            'last_served': None,
            'in_services': False  # Flag to indicate if person was found in Services API
        }

        # Get emails
        emails_result = self._get(f"/people/v2/people/{person_id}/emails")
        for email in emails_result.get('data', []):
            email_attrs = email.get('attributes', {})
            details['emails'].append({
                'address': email_attrs.get('address'),
                'location': email_attrs.get('location'),
                'primary': email_attrs.get('primary', False)
            })

        # Get phone numbers
        phones_result = self._get(f"/people/v2/people/{person_id}/phone_numbers")
        for phone in phones_result.get('data', []):
            phone_attrs = phone.get('attributes', {})
            details['phone_numbers'].append({
                'number': phone_attrs.get('number'),
                'carrier': phone_attrs.get('carrier'),
                'location': phone_attrs.get('location'),
                'primary': phone_attrs.get('primary', False)
            })

        # Get addresses
        addresses_result = self._get(f"/people/v2/people/{person_id}/addresses")
        for addr in addresses_result.get('data', []):
            addr_attrs = addr.get('attributes', {})
            details['addresses'].append({
                'street': addr_attrs.get('street'),
                'city': addr_attrs.get('city'),
                'state': addr_attrs.get('state'),
                'zip': addr_attrs.get('zip'),
                'location': addr_attrs.get('location'),
                'primary': addr_attrs.get('primary', False)
            })

        # Get team memberships from Services API
        # First, search for this person in Services
        services_person = self._find_services_person(person_id)
        if services_person:
            details['in_services'] = True
            services_person_id = services_person.get('id')
            logger.info(f"Found Services person ID: {services_person_id}")

            # Get team positions (what teams they're on)
            # Note: This endpoint may return empty if person has no team assignments
            team_positions = self._get(f"/services/v2/people/{services_person_id}/team_positions")
            logger.info(f"Team positions response: {len(team_positions.get('data', []))} positions found")

            for position in team_positions.get('data', []):
                pos_attrs = position.get('attributes', {})
                # Get the team name from the relationship
                team_id = position.get('relationships', {}).get('team', {}).get('data', {}).get('id')
                team_name = pos_attrs.get('name', 'Unknown Position')

                details['teams'].append({
                    'position': team_name,
                    'team_id': team_id,
                    'created_at': pos_attrs.get('created_at')
                })

            # Get recent schedules (when they served)
            # Use plan_person endpoint which is more reliable
            schedules_result = self._get(
                f"/services/v2/people/{services_person_id}/schedules",
                params={'order': '-sort_date', 'per_page': 20}
            )
            logger.info(f"Schedules response: {len(schedules_result.get('data', []))} schedules found")

            # Get today's date for filtering past schedules
            from datetime import datetime
            today_str = datetime.now().date().isoformat()

            for schedule in schedules_result.get('data', []):
                sched_attrs = schedule.get('attributes', {})
                sort_date = sched_attrs.get('sort_date')

                details['recent_schedules'].append({
                    'date': sort_date,
                    'team_name': sched_attrs.get('team_name'),
                    'team_position_name': sched_attrs.get('team_position_name'),
                    'plan_title': sched_attrs.get('plan_title', ''),
                    'status': sched_attrs.get('status'),
                    'decline_reason': sched_attrs.get('decline_reason')
                })

                # Track last served date (confirmed schedules only, past dates only)
                # Only consider dates that have already passed (not future scheduled dates)
                if sched_attrs.get('status') == 'C' and sort_date:  # C = Confirmed
                    # Compare date portion only (YYYY-MM-DD format)
                    schedule_date = sort_date[:10] if len(sort_date) >= 10 else sort_date
                    if schedule_date <= today_str:  # Only past or today's dates
                        if not details['last_served'] or schedule_date > details['last_served'][:10]:
                            details['last_served'] = sort_date

            if not details['recent_schedules']:
                logger.info(f"No schedules found for Services person {services_person_id}")
        else:
            logger.info(f"Person {person_id} ({details.get('name')}) not found in Services - they may not be a scheduled volunteer")

        return details

    def _find_services_person(self, people_person_id: str) -> Optional[dict]:
        """
        Find the Services person record that matches a People person ID.

        PCO has separate People and Services databases. This finds the Services
        person by matching on email (most reliable) or exact full name match.

        Args:
            people_person_id: The person ID from the People API.

        Returns:
            Services person record or None.
        """
        # Get the person's details from People API
        person = self.get_person_by_id(people_person_id)
        if not person:
            logger.warning(f"Could not find People record for ID {people_person_id}")
            return None

        attrs = person.get('attributes', {})
        first_name = attrs.get('first_name', '')
        last_name = attrs.get('last_name', '')

        if not first_name or not last_name:
            logger.warning(f"Person {people_person_id} missing first or last name")
            return None

        # Get the person's emails from People API for matching
        emails_result = self._get(f"/people/v2/people/{people_person_id}/emails")
        person_emails = set()
        for email_data in emails_result.get('data', []):
            email_addr = email_data.get('attributes', {}).get('address', '').lower().strip()
            if email_addr:
                person_emails.add(email_addr)

        search_name = f"{first_name} {last_name}"
        logger.info(f"Searching Services for '{search_name}' (has {len(person_emails)} emails)")

        candidates = []

        # Method 1: Try searching by first_name in Services API
        # PCO Services API uses where[first_name] not where[name]
        search_result = self._get("/services/v2/people", params={
            'where[first_name]': first_name,
            'per_page': 50
        })
        candidates = search_result.get('data', [])
        logger.info(f"Services first_name search returned {len(candidates)} candidates for '{first_name}'")

        # If that didn't work, try with last_name
        if not candidates:
            search_result = self._get("/services/v2/people", params={
                'where[last_name]': last_name,
                'per_page': 50
            })
            candidates = search_result.get('data', [])
            logger.info(f"Services last_name search returned {len(candidates)} candidates for '{last_name}'")

        # If still no results, paginate through all services people
        if not candidates:
            logger.info(f"Name searches returned no results, fetching all services people with pagination")
            candidates = self._get_all_services_people()

        # Method 1: Match by email (most reliable - emails are unique)
        if person_emails:
            for services_person in candidates:
                sp_attrs = services_person.get('attributes', {})
                # Services person records have email directly in attributes
                sp_email = (sp_attrs.get('email') or '').lower().strip()
                if sp_email and sp_email in person_emails:
                    logger.info(f"Found Services person by email ({sp_email}): {sp_attrs.get('first_name')} {sp_attrs.get('last_name')} (ID: {services_person.get('id')})")
                    return services_person

        # Method 2: Exact first AND last name match
        # Only match if BOTH first and last name match exactly (case-insensitive)
        target_first = first_name.lower().strip()
        target_last = last_name.lower().strip()

        for services_person in candidates:
            sp_attrs = services_person.get('attributes', {})
            sp_first = (sp_attrs.get('first_name') or '').lower().strip()
            sp_last = (sp_attrs.get('last_name') or '').lower().strip()

            if sp_first == target_first and sp_last == target_last:
                logger.info(f"Found Services person by exact name: {sp_attrs.get('first_name')} {sp_attrs.get('last_name')} (ID: {services_person.get('id')})")
                return services_person

        logger.info(f"No Services person found for {first_name} {last_name}")
        return None

    def _get_all_services_people(self, max_pages: int = 10) -> list:
        """
        Fetch all services people with pagination.

        Args:
            max_pages: Maximum number of pages to fetch (safety limit)

        Returns:
            List of all services person records
        """
        all_people = []
        offset = 0
        per_page = 100

        for page in range(max_pages):
            result = self._get("/services/v2/people", params={
                'per_page': per_page,
                'offset': offset
            })

            data = result.get('data', [])
            if not data:
                break

            all_people.extend(data)
            logger.info(f"Fetched page {page + 1} of services people: {len(data)} records (total: {len(all_people)})")

            # Check if there are more pages
            if len(data) < per_page:
                break

            offset += per_page

        return all_people

    def search_person_with_details(self, name: str) -> Optional[dict]:
        """
        Search for a person by name and return their full details.

        Args:
            name: Name to search for.

        Returns:
            Dict with person details or None if not found.
        """
        matches = self.find_matches(name, threshold=0.7)
        if not matches:
            return None

        # Get the best match
        best_match = matches[0]
        return self.get_person_details(best_match['pco_id'])

    def search_person_with_suggestions(self, name: str) -> dict:
        """
        Search for a person by name, returning details if found or suggestions if not.

        Args:
            name: Name to search for.

        Returns:
            Dict with:
            - 'found': True/False
            - 'details': Person details if found
            - 'suggestions': List of similar names if not found
            - 'search_name': The original search name
        """
        result = {
            'found': False,
            'details': None,
            'suggestions': [],
            'search_name': name
        }

        # Try to find good matches (threshold 0.7)
        good_matches = self.find_matches(name, threshold=0.7)
        if good_matches:
            # Found a good match
            best_match = good_matches[0]
            result['found'] = True
            result['details'] = self.get_person_details(best_match['pco_id'])
            return result

        # No good match - look for suggestions with lower threshold
        suggestions = self.find_matches(name, threshold=0.4)
        if suggestions:
            result['suggestions'] = [
                {
                    'name': s['name'],
                    'score': s['score'],
                    'pco_id': s['pco_id']
                }
                for s in suggestions[:5]  # Top 5 suggestions
            ]

        return result

    def search_by_first_name(self, first_name: str, limit: int = 10) -> dict:
        """
        Search for people by first name only, returning all matches.

        This is used when a user provides only a first name and we need
        to ask them to clarify which person they mean.

        Args:
            first_name: First name to search for.
            limit: Maximum number of matches to return.

        Returns:
            Dict with:
            - 'matches': List of people with this first name
            - 'count': Number of matches found
            - 'search_name': The original search name
        """
        result = {
            'matches': [],
            'count': 0,
            'search_name': first_name
        }

        if not self.is_configured:
            return result

        first_name_lower = first_name.lower().strip()

        # Get all people and filter by first name
        all_people = self.get_people(use_cache=True)

        matches = []
        for person in all_people:
            attrs = person.get('attributes', {})
            pco_first = (attrs.get('first_name') or '').lower().strip()

            # Check for exact first name match or close match
            if pco_first == first_name_lower or pco_first.startswith(first_name_lower):
                full_name = f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip()
                matches.append({
                    'name': full_name,
                    'first_name': attrs.get('first_name', ''),
                    'last_name': attrs.get('last_name', ''),
                    'pco_id': person.get('id')
                })

        # Sort by last name for consistent ordering
        matches.sort(key=lambda x: x.get('last_name', '').lower())

        result['matches'] = matches[:limit]
        result['count'] = len(matches)

        logger.info(f"First name search for '{first_name}': found {len(matches)} matches")
        return result

    def get_name_suggestions(self, name: str, limit: int = 5) -> list:
        """
        Get name suggestions from PCO for a given search name.

        Args:
            name: Name to find suggestions for.
            limit: Maximum number of suggestions to return.

        Returns:
            List of suggestion dicts with name and score.
        """
        matches = self.find_matches(name, threshold=0.3)
        return [
            {'name': m['name'], 'score': m['score']}
            for m in matches[:limit]
        ]

    def find_matches(self, name: str, threshold: float = 0.6) -> list:
        """
        Find PCO people matching a given name using fuzzy matching.

        Args:
            name: Name to match against.
            threshold: Minimum similarity score (0-1).

        Returns:
            List of matches with scores: [{'person': {...}, 'score': 0.95}, ...]
        """
        if not self.is_configured:
            return []

        # Normalize the search name
        search_name = normalize_name(name)

        # First try direct API search
        direct_results = self.search_people(name)

        # Get all people for fuzzy matching
        all_people = self.get_people(use_cache=True)

        matches = []
        seen_ids = set()

        # Score direct search results (they get a boost)
        for person in direct_results:
            pco_id = person.get('id')
            if pco_id in seen_ids:
                continue
            seen_ids.add(pco_id)

            attrs = person.get('attributes', {})
            pco_name = f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip()
            score = calculate_name_similarity(search_name, pco_name)

            # Boost score for direct search matches
            score = min(1.0, score + 0.1)

            if score >= threshold:
                matches.append({
                    'person': person,
                    'name': pco_name,
                    'score': score,
                    'pco_id': pco_id
                })

        # Fuzzy match against all people
        for person in all_people:
            pco_id = person.get('id')
            if pco_id in seen_ids:
                continue
            seen_ids.add(pco_id)

            attrs = person.get('attributes', {})
            pco_name = f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip()

            if not pco_name:
                continue

            score = calculate_name_similarity(search_name, pco_name)

            if score >= threshold:
                matches.append({
                    'person': person,
                    'name': pco_name,
                    'score': score,
                    'pco_id': pco_id
                })

        # Sort by score descending
        matches.sort(key=lambda x: x['score'], reverse=True)

        return matches[:10]  # Return top 10 matches

    def sync_volunteers(self) -> dict:
        """
        Sync Planning Center people with local Volunteer records.

        Returns:
            Dict with counts of created and updated volunteers.
        """
        from .models import Volunteer

        if not self.is_configured:
            return {'error': 'Planning Center not configured'}

        people = self.get_people(use_cache=False)
        created_count = 0
        updated_count = 0

        for person in people:
            attrs = person.get('attributes', {})
            first_name = attrs.get('first_name', '')
            last_name = attrs.get('last_name', '')
            full_name = f"{first_name} {last_name}".strip()

            if not full_name:
                continue

            volunteer, created = Volunteer.objects.update_or_create(
                planning_center_id=person['id'],
                defaults={
                    'name': full_name,
                    'normalized_name': full_name.lower()
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        logger.info(f"Planning Center sync: {created_count} created, {updated_count} updated")
        return {
            'created': created_count,
            'updated': updated_count
        }


def normalize_name(name: str) -> str:
    """
    Normalize a name for comparison.

    Args:
        name: Name to normalize.

    Returns:
        Normalized lowercase name with extra whitespace removed.
    """
    # Remove special characters, keep letters and spaces
    name = re.sub(r'[^\w\s]', '', name)
    # Normalize whitespace and lowercase
    return ' '.join(name.lower().split())


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two names.

    Uses a combination of:
    - Exact match check
    - SequenceMatcher ratio
    - Partial name matching (first/last name swaps, nicknames)

    Args:
        name1: First name.
        name2: Second name.

    Returns:
        Similarity score between 0 and 1.
    """
    # Normalize both names
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    # Exact match
    if n1 == n2:
        return 1.0

    # SequenceMatcher for overall similarity
    base_score = SequenceMatcher(None, n1, n2).ratio()

    # Check if one name contains the other (partial match)
    if n1 in n2 or n2 in n1:
        base_score = max(base_score, 0.85)

    # Split into parts and check for component matches
    parts1 = n1.split()
    parts2 = n2.split()

    # Check if last names match (common for first name variations)
    if len(parts1) >= 2 and len(parts2) >= 2:
        if parts1[-1] == parts2[-1]:  # Last names match
            # Boost score if last names match
            base_score = max(base_score, 0.7)
            # If first name is similar too, boost more
            first_similarity = SequenceMatcher(None, parts1[0], parts2[0]).ratio()
            if first_similarity > 0.5:
                base_score = max(base_score, 0.75 + first_similarity * 0.2)

    # Check for reversed name order (Last, First vs First Last)
    if len(parts1) >= 2 and len(parts2) >= 2:
        reversed_n1 = ' '.join(reversed(parts1))
        reversed_score = SequenceMatcher(None, reversed_n1, n2).ratio()
        base_score = max(base_score, reversed_score)

    return base_score


def sync_planning_center():
    """Convenience function to sync Planning Center data."""
    api = PlanningCenterAPI()
    return api.sync_volunteers()


def clear_pco_cache():
    """Clear the PCO people cache to force fresh data."""
    cache.delete(f"{PCO_PEOPLE_CACHE_KEY}_all")
    logger.info("PCO cache cleared")


# ============================================================================
# Service Plans and Songs API Methods
# ============================================================================

class PlanningCenterServicesAPI(PlanningCenterAPI):
    """Extended API client with Services-specific methods for songs and plans."""

    def search_services_by_first_name(self, first_name: str, limit: int = 15) -> dict:
        """
        Search for services people by first name only, returning all matches.

        This is used when a user provides only a first name and we need
        to ask them to clarify which person they mean for service-related queries.

        Args:
            first_name: First name to search for.
            limit: Maximum number of matches to return.

        Returns:
            Dict with:
            - 'matches': List of people with this first name in Services
            - 'count': Number of matches found
            - 'search_name': The original search name
        """
        result = {
            'matches': [],
            'count': 0,
            'search_name': first_name
        }

        if not self.is_configured:
            return result

        first_name_lower = first_name.lower().strip()

        # First try the PCO first_name search (more efficient)
        search_result = self._get("/services/v2/people", params={
            'where[first_name]': first_name,
            'per_page': 100
        })

        candidates = search_result.get('data', [])
        logger.info(f"Services first_name search for disambiguation returned {len(candidates)} candidates for '{first_name}'")

        matches = []
        for person in candidates:
            attrs = person.get('attributes', {})
            pco_first = (attrs.get('first_name') or '').lower().strip()

            # Check for exact first name match or close match
            if pco_first == first_name_lower or pco_first.startswith(first_name_lower):
                full_name = f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip()
                matches.append({
                    'name': full_name,
                    'first_name': attrs.get('first_name', ''),
                    'last_name': attrs.get('last_name', ''),
                    'pco_id': person.get('id')
                })

        # Sort by last name for consistent ordering
        matches.sort(key=lambda x: x.get('last_name', '').lower())

        result['matches'] = matches[:limit]
        result['count'] = len(matches)

        logger.info(f"Services first name search for '{first_name}': found {len(matches)} matches")
        return result

    def get_service_types(self) -> list:
        """
        Get all service types (e.g., Sunday AM, Wednesday PM).

        Returns:
            List of service type records.
        """
        result = self._get("/services/v2/service_types")
        return result.get('data', [])

    def get_plans(self, service_type_id: str, future_only: bool = False, past_only: bool = False, limit: int = 10) -> list:
        """
        Get plans (services) for a service type.

        Args:
            service_type_id: The service type ID.
            future_only: Only return future plans.
            past_only: Only return past plans.
            limit: Maximum number of plans to return.

        Returns:
            List of plan records.
        """
        params = {'per_page': limit, 'order': '-sort_date'}

        if future_only:
            params['filter'] = 'future'
        elif past_only:
            params['filter'] = 'past'

        result = self._get(f"/services/v2/service_types/{service_type_id}/plans", params)
        return result.get('data', [])

    def get_plans_by_date_range(self, service_type_id: str, start_date: str, end_date: str, limit: int = 10) -> list:
        """
        Get plans for a service type within a specific date range.

        Args:
            service_type_id: The service type ID.
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            limit: Maximum number of plans to return.

        Returns:
            List of plan records within the date range.
        """
        # PCO API supports after and before filters
        params = {
            'per_page': limit,
            'order': '-sort_date',
            'filter': f'after,before',
            'after': start_date,
            'before': end_date
        }

        result = self._get(f"/services/v2/service_types/{service_type_id}/plans", params)
        return result.get('data', [])

    def get_recent_plans(self, limit: int = 10) -> list:
        """
        Get recent plans across all service types.

        Args:
            limit: Maximum number of plans to return.

        Returns:
            List of plan records with service type info.
        """
        service_types = self.get_service_types()
        all_plans = []

        for st in service_types:
            st_id = st.get('id')
            st_name = st.get('attributes', {}).get('name', 'Unknown')
            plans = self.get_plans(st_id, past_only=True, limit=5)

            for plan in plans:
                plan['service_type_name'] = st_name
                plan['service_type_id'] = st_id
                all_plans.append(plan)

        # Sort by date descending and limit
        all_plans.sort(key=lambda p: p.get('attributes', {}).get('sort_date', ''), reverse=True)
        return all_plans[:limit]

    def get_plan_items(self, service_type_id: str, plan_id: str) -> list:
        """
        Get all items in a plan (songs, headers, media, etc.).

        Args:
            service_type_id: The service type ID.
            plan_id: The plan ID.

        Returns:
            List of plan items.
        """
        result = self._get(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items",
            params={'include': 'song,arrangement', 'per_page': 100}
        )
        return result.get('data', []), result.get('included', [])

    def get_plan_details(self, service_type_id: str, plan_id: str) -> dict:
        """
        Get detailed plan info including all songs.

        Args:
            service_type_id: The service type ID.
            plan_id: The plan ID.

        Returns:
            Dict with plan details and song list.
        """
        # Get plan info
        plan_result = self._get(f"/services/v2/service_types/{service_type_id}/plans/{plan_id}")
        plan = plan_result.get('data', {})
        plan_attrs = plan.get('attributes', {})

        # Get items
        items_data, included = self.get_plan_items(service_type_id, plan_id)

        # Build lookup for included songs and arrangements
        songs_lookup = {}
        arrangements_lookup = {}
        for inc in included:
            if inc.get('type') == 'Song':
                songs_lookup[inc.get('id')] = inc
            elif inc.get('type') == 'Arrangement':
                arrangements_lookup[inc.get('id')] = inc

        # Build song list
        songs = []
        for item in items_data:
            item_attrs = item.get('attributes', {})
            item_type = item_attrs.get('item_type')

            if item_type == 'song':
                song_rel = item.get('relationships', {}).get('song', {}).get('data', {})
                arr_rel = item.get('relationships', {}).get('arrangement', {}).get('data', {})

                song_id = song_rel.get('id') if song_rel else None
                arr_id = arr_rel.get('id') if arr_rel else None

                song_data = songs_lookup.get(song_id, {})
                arr_data = arrangements_lookup.get(arr_id, {})

                song_attrs = song_data.get('attributes', {})
                arr_attrs = arr_data.get('attributes', {})

                songs.append({
                    'title': item_attrs.get('title') or song_attrs.get('title', 'Unknown'),
                    'song_id': song_id,
                    'arrangement_id': arr_id,
                    'key': item_attrs.get('key_name') or arr_attrs.get('name'),
                    'sequence': item_attrs.get('sequence'),
                    'length': item_attrs.get('length'),
                    'author': song_attrs.get('author'),
                    'ccli_number': song_attrs.get('ccli_number')
                })

        return {
            'id': plan_id,
            'service_type_id': service_type_id,
            'title': plan_attrs.get('title'),
            'dates': plan_attrs.get('dates'),
            'sort_date': plan_attrs.get('sort_date'),
            'series_title': plan_attrs.get('series_title'),
            'songs': songs
        }

    def get_plan_team_members(self, service_type_id: str, plan_id: str) -> list:
        """
        Get team members scheduled for a service plan.

        Args:
            service_type_id: The service type ID.
            plan_id: The plan ID.

        Returns:
            List of team member assignments with names, positions, and status.
        """
        # Get team members for this plan
        result = self._get(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members",
            params={'include': 'person,team', 'per_page': 100}
        )

        team_members_data = result.get('data', [])
        included = result.get('included', [])

        # Build lookup for included people and teams
        people_lookup = {}
        teams_lookup = {}
        for inc in included:
            if inc.get('type') == 'Person':
                people_lookup[inc.get('id')] = inc
            elif inc.get('type') == 'Team':
                teams_lookup[inc.get('id')] = inc

        # Build team member list
        team_members = []
        for tm in team_members_data:
            tm_attrs = tm.get('attributes', {})
            tm_rels = tm.get('relationships', {})

            # Get person info
            person_rel = tm_rels.get('person', {}).get('data', {})
            person_id = person_rel.get('id') if person_rel else None
            person_data = people_lookup.get(person_id, {})
            person_attrs = person_data.get('attributes', {})

            # Get team info
            team_rel = tm_rels.get('team', {}).get('data', {})
            team_id = team_rel.get('id') if team_rel else None
            team_data = teams_lookup.get(team_id, {})
            team_attrs = team_data.get('attributes', {})

            # Status codes: C=Confirmed, U=Unconfirmed, D=Declined
            status = tm_attrs.get('status', 'U')
            status_map = {
                'C': 'Confirmed',
                'U': 'Unconfirmed',
                'D': 'Declined',
                'B': 'Blocked out'
            }

            team_members.append({
                'name': tm_attrs.get('name') or f"{person_attrs.get('first_name', '')} {person_attrs.get('last_name', '')}".strip(),
                'team_name': team_attrs.get('name', 'Unknown Team'),
                'position': tm_attrs.get('team_position_name', ''),
                'status': status_map.get(status, status),
                'status_code': status,
                'notes': tm_attrs.get('notes', ''),
                'person_id': person_id
            })

        # Sort by team name, then by name
        team_members.sort(key=lambda x: (x['team_name'], x['name']))

        return team_members

    def find_person_upcoming_services(self, person_name: str, max_plans: int = 8) -> list:
        """
        Find a person's upcoming scheduled services by searching through plans.

        This is used when we can't find the person in the global Services people
        list but they might still be scheduled for services.

        Args:
            person_name: Name of the person to search for.
            max_plans: Maximum number of upcoming plans to check.

        Returns:
            List of scheduled services with date, team, position, and status.
        """
        from difflib import SequenceMatcher

        # Normalize the search name
        search_first = person_name.split()[0].lower() if person_name else ''
        search_last = person_name.split()[-1].lower() if person_name and len(person_name.split()) > 1 else ''
        search_full = person_name.lower()

        logger.info(f"Searching upcoming plans for '{person_name}'")

        upcoming_services = []

        # Get upcoming plans for the main service type
        from datetime import datetime, timedelta
        today = datetime.now().date()
        future_date = today + timedelta(days=90)  # Look 90 days ahead

        # Get the main service type
        service_types = self._get("/services/v2/service_types")
        main_service_type = None
        for st in service_types.get('data', []):
            st_name = st.get('attributes', {}).get('name', '')
            if 'morning' in st_name.lower() and 'main' in st_name.lower():
                main_service_type = st
                break
            elif 'sunday' in st_name.lower() and not any(x in st_name.lower() for x in ['hsm', 'msm', 'youth', 'student']):
                main_service_type = st

        if not main_service_type:
            # Just use the first service type
            if service_types.get('data'):
                main_service_type = service_types['data'][0]

        if not main_service_type:
            logger.warning("No service types found")
            return []

        service_type_id = main_service_type.get('id')

        # Get upcoming plans
        plans_result = self._get(
            f"/services/v2/service_types/{service_type_id}/plans",
            params={
                'filter': 'future',
                'per_page': max_plans,
                'order': 'sort_date'
            }
        )

        plans = plans_result.get('data', [])
        logger.info(f"Found {len(plans)} upcoming plans to search")

        for plan in plans:
            plan_id = plan.get('id')
            plan_attrs = plan.get('attributes', {})
            plan_date = plan_attrs.get('sort_date', plan_attrs.get('dates', ''))

            # Get team members for this plan
            team_members = self.get_plan_team_members(service_type_id, plan_id)

            # Search for the person in team members
            for tm in team_members:
                tm_name = (tm.get('name') or '').lower()

                # Check for match using fuzzy matching
                # Match if first AND last name match, or if full name is very similar
                tm_parts = tm_name.split()
                tm_first = tm_parts[0] if tm_parts else ''
                tm_last = tm_parts[-1] if len(tm_parts) > 1 else ''

                is_match = False

                # Exact first and last name match
                if search_first and search_last:
                    if tm_first == search_first and tm_last == search_last:
                        is_match = True

                # Fuzzy full name match
                if not is_match:
                    similarity = SequenceMatcher(None, search_full, tm_name).ratio()
                    if similarity > 0.85:
                        is_match = True

                if is_match:
                    logger.info(f"Found '{tm.get('name')}' scheduled for {plan_date}")
                    upcoming_services.append({
                        'date': plan_date,
                        'team_name': tm.get('team_name', ''),
                        'position': tm.get('position', ''),
                        'status': tm.get('status', ''),
                        'service_type': main_service_type.get('attributes', {}).get('name', '')
                    })

        return upcoming_services

    def get_plan_with_team(self, date_str: str, service_type: str = None) -> Optional[dict]:
        """
        Find a plan by date and include team member assignments.

        Args:
            date_str: Date string to search for.
            service_type: Optional service type name (e.g., "HSM", "Cherry Hills Morning Main").
                         If not specified, defaults to the main Sunday morning service.

        Returns:
            Dict with plan details, songs, and team members.
        """
        plan_details = self.find_plan_by_date(date_str, service_type=service_type)
        if not plan_details:
            return None

        service_type_id = plan_details.get('service_type_id')
        plan_id = plan_details.get('id')

        if service_type_id and plan_id:
            team_members = self.get_plan_team_members(service_type_id, plan_id)
            plan_details['team_members'] = team_members

        return plan_details

    def search_songs(self, query: str, limit: int = 10) -> list:
        """
        Search for songs in the library.

        Args:
            query: Search query (title, author, etc.).
            limit: Maximum results.

        Returns:
            List of song records.
        """
        # Try title search first
        result = self._get(
            "/services/v2/songs",
            params={'where[title]': query, 'per_page': limit}
        )
        songs = result.get('data', [])

        # If no results, try broader search
        if not songs:
            result = self._get("/services/v2/songs", params={'per_page': 100})
            all_songs = result.get('data', [])

            # Filter by query
            query_lower = query.lower()
            songs = [
                s for s in all_songs
                if query_lower in (s.get('attributes', {}).get('title') or '').lower()
                or query_lower in (s.get('attributes', {}).get('author') or '').lower()
            ][:limit]

        return songs

    def search_song_with_suggestions(self, query: str, threshold: float = 0.4) -> dict:
        """
        Search for a song by title or attachment filename, returning suggestions if no exact match found.

        Args:
            query: Song title to search for.
            threshold: Minimum similarity score for suggestions (0-1).

        Returns:
            Dict with:
            - 'found': True if exact/good match found
            - 'song': Song details if found (with attachments)
            - 'suggestions': List of similar song titles if not found
            - 'search_query': The original search query
        """
        result = {
            'found': False,
            'song': None,
            'suggestions': [],
            'search_query': query
        }

        query_lower = query.lower().strip()

        # Get all songs using pagination
        all_songs = self._get_all_pages("/services/v2/songs")
        logger.info(f"Searching through {len(all_songs)} songs for '{query}'")

        # Build list of songs with similarity scores
        matches = []
        for song in all_songs:
            song_attrs = song.get('attributes', {})
            title = song_attrs.get('title') or ''
            title_lower = title.lower()
            author = song_attrs.get('author', '')

            # Calculate similarity score based on title
            score = calculate_name_similarity(query_lower, title_lower)

            # Boost score for exact matches or if query is contained in title
            if query_lower == title_lower:
                score = 1.0
            elif query_lower in title_lower:
                score = max(score, 0.85)
            elif title_lower in query_lower:
                score = max(score, 0.75)

            # Check if query matches the main title (before parentheses or subtitle)
            # This handles cases like "I Stand Amazed" matching "I Stand Amazed (How Marvelous)"
            main_title = title_lower.split('(')[0].strip()
            if main_title and (query_lower == main_title or query_lower.rstrip('?!.,') == main_title):
                score = max(score, 0.95)  # Very high score for main title match
            elif main_title.startswith(query_lower.rstrip('?!.,')):
                score = max(score, 0.85)  # Query is prefix of main title

            # Also check if title starts with the query (prefix match)
            if title_lower.startswith(query_lower.rstrip('?!.,')):
                score = max(score, 0.90)

            # Check if any word in the query matches a word in the title
            query_words = set(query_lower.split())
            title_words = set(title_lower.split())
            common_words = query_words & title_words
            # Filter out common words like "the", "a", "in", "of"
            common_words -= {'the', 'a', 'an', 'in', 'of', 'to', 'for', 'and', 'is', 'i'}
            if common_words:
                score = max(score, 0.5 + (len(common_words) * 0.1))

            if score >= threshold:
                matches.append({
                    'song': song,
                    'title': title,
                    'score': score,
                    'song_id': song.get('id'),
                    'author': author,
                    'match_type': 'title'
                })

        # Sort by score descending
        matches.sort(key=lambda x: x['score'], reverse=True)

        if matches:
            best_match = matches[0]
            # If we have a good match (score >= 0.75), consider it found
            if best_match['score'] >= 0.75:
                result['found'] = True
                result['song'] = self.get_song_with_attachments(best_match['title'])
                logger.info(f"Found song '{best_match['title']}' with score {best_match['score']:.2f}")
            else:
                # No good match - provide suggestions
                result['suggestions'] = [
                    {
                        'title': m['title'],
                        'author': m['author'],
                        'score': m['score'],
                        'song_id': m['song_id']
                    }
                    for m in matches[:5]  # Top 5 suggestions
                ]
                logger.info(f"No good match for '{query}', providing {len(result['suggestions'])} suggestions")
        else:
            logger.info(f"No songs found matching '{query}'")

        return result

    def get_song_usage_history(self, song_title: str, limit: int = 10) -> Optional[dict]:
        """
        Get the usage history of a song - when it was last played in services.

        Args:
            song_title: Title of the song to look up.
            limit: Maximum number of past usages to return.

        Returns:
            Dict with song info and list of past service dates, or None if not found.
        """
        # First find the song
        search_result = self.search_song_with_suggestions(song_title)

        if not search_result['found'] or not search_result['song']:
            # Return suggestions if we have them
            if search_result['suggestions']:
                return {
                    'found': False,
                    'song_title': song_title,
                    'suggestions': search_result['suggestions'],
                    'usages': []
                }
            return None

        song = search_result['song']
        song_id = song.get('id')
        actual_title = song.get('title', song_title)

        # Get song schedule items (past usages)
        try:
            # The song_schedules endpoint returns when a song was scheduled
            schedules_result = self._get(
                f"/services/v2/songs/{song_id}/song_schedules",
                params={'order': '-sort_date', 'per_page': limit}
            )
            schedules = schedules_result.get('data', [])

            usages = []
            for sched in schedules:
                sched_attrs = sched.get('attributes', {})
                plan_id = sched.get('relationships', {}).get('plan', {}).get('data', {}).get('id')
                service_type_id = sched.get('relationships', {}).get('service_type', {}).get('data', {}).get('id')

                usage = {
                    'date': sched_attrs.get('plan_dates') or sched_attrs.get('sort_date', '')[:10],
                    'plan_id': plan_id,
                    'service_type_id': service_type_id,
                    'arrangement_name': sched_attrs.get('arrangement_name'),
                    'key': sched_attrs.get('key_name')
                }
                usages.append(usage)

            # If song_schedules returned no results, fall back to searching through plans
            # This handles cases where songs are in plans but not properly linked in song_schedules
            if not usages:
                logger.info(f"No song_schedules found for '{actual_title}', searching through recent plans")
                fallback_result = self._get_song_usage_from_plans(song_id, actual_title, limit)
                usages = fallback_result.get('usages', [])

            return {
                'found': True,
                'song_title': actual_title,
                'song_id': song_id,
                'author': song.get('author', ''),
                'usages': usages,
                'total_times_used': len(usages)
            }

        except Exception as e:
            logger.error(f"Error getting song usage history: {e}")
            # Fall back to searching through recent plans
            return self._get_song_usage_from_plans(song_id, actual_title, limit)

    def _get_song_usage_from_plans(self, song_id: str, song_title: str, limit: int = 10) -> dict:
        """
        Fallback method to find song usage by searching through recent plans.

        Args:
            song_id: The song ID.
            song_title: The song title.
            limit: Maximum results.

        Returns:
            Dict with usage history.
        """
        usages = []
        plans = self.get_recent_plans(limit=60)

        for plan in plans:
            service_type_id = plan.get('service_type_id')
            plan_id = plan.get('id')
            plan_attrs = plan.get('attributes', {})

            # Get plan items to check for this song
            items_data, included = self.get_plan_items(service_type_id, plan_id)

            for item in items_data:
                item_attrs = item.get('attributes', {})
                if item_attrs.get('item_type') == 'song':
                    item_title = item_attrs.get('title', '').lower()
                    if song_title.lower() in item_title or item_title in song_title.lower():
                        usages.append({
                            'date': plan_attrs.get('dates') or plan_attrs.get('sort_date', '')[:10],
                            'plan_id': plan_id,
                            'service_type_id': service_type_id,
                            'key': item_attrs.get('key_name')
                        })
                        break

            if len(usages) >= limit:
                break

        return {
            'found': True,
            'song_title': song_title,
            'song_id': song_id,
            'usages': usages,
            'total_times_used': len(usages)
        }

    def get_song_details(self, song_id: str) -> dict:
        """
        Get detailed song info including arrangements and attachments.

        Args:
            song_id: The song ID.

        Returns:
            Dict with song details, arrangements, and attachments.
        """
        # Get song info
        song_result = self._get(f"/services/v2/songs/{song_id}")
        song = song_result.get('data', {})
        song_attrs = song.get('attributes', {})

        # Get arrangements (including lyrics and chord chart content)
        arr_result = self._get(f"/services/v2/songs/{song_id}/arrangements")
        arrangements = []
        for arr in arr_result.get('data', []):
            arr_attrs = arr.get('attributes', {})
            arrangements.append({
                'id': arr.get('id'),
                'name': arr_attrs.get('name'),
                'key': arr_attrs.get('chord_chart_key'),
                'bpm': arr_attrs.get('bpm'),
                'meter': arr_attrs.get('meter'),
                'length': arr_attrs.get('length'),
                'sequence': arr_attrs.get('sequence_short'),
                'lyrics': arr_attrs.get('lyrics'),  # Full lyrics text
                'chord_chart': arr_attrs.get('chord_chart'),  # Chord chart content
                'notes': arr_attrs.get('notes')
            })

        # Get song-level attachments
        attach_result = self._get(f"/services/v2/songs/{song_id}/attachments")
        attachments = []
        for attach in attach_result.get('data', []):
            attach_attrs = attach.get('attributes', {})
            attachments.append({
                'id': attach.get('id'),
                'filename': attach_attrs.get('filename'),
                'file_type': attach_attrs.get('filetype'),
                'url': attach_attrs.get('url'),
                'streamable': attach_attrs.get('streamable'),
                'downloadable': attach_attrs.get('downloadable')
            })

        return {
            'id': song_id,
            'title': song_attrs.get('title'),
            'author': song_attrs.get('author'),
            'copyright': song_attrs.get('copyright'),
            'ccli_number': song_attrs.get('ccli_number'),
            'themes': song_attrs.get('themes'),
            'created_at': song_attrs.get('created_at'),
            'arrangements': arrangements,
            'attachments': attachments
        }

    def get_arrangement_attachments(self, song_id: str, arrangement_id: str) -> list:
        """
        Get attachments for a specific arrangement (chord charts, lyrics, etc.).

        Args:
            song_id: The song ID.
            arrangement_id: The arrangement ID.

        Returns:
            List of attachment records with download URLs.
        """
        result = self._get(f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}/attachments")
        attachments = []

        for attach in result.get('data', []):
            attach_attrs = attach.get('attributes', {})
            attachments.append({
                'id': attach.get('id'),
                'filename': attach_attrs.get('filename'),
                'file_type': attach_attrs.get('filetype'),
                'content_type': attach_attrs.get('content_type'),
                'url': attach_attrs.get('url'),
                'streamable': attach_attrs.get('streamable'),
                'downloadable': attach_attrs.get('downloadable'),
                'size': attach_attrs.get('size')
            })

        return attachments

    def fetch_attachment_content(self, attachment_url: str, content_type: str = None, filename: str = None, max_size: int = 2000000, file_type: str = None) -> Optional[str]:
        """
        Fetch the text content of an attachment from its URL.

        Supports text files and PDF extraction.

        Args:
            attachment_url: The URL to download from.
            content_type: The content type of the file.
            filename: The filename (used to detect file type).
            max_size: Maximum file size to download (default 2MB for PDFs).
            file_type: The file type from PCO (e.g., 'pdf', 'txt').

        Returns:
            Text content of the file, or None if not fetchable.
        """
        if not attachment_url:
            return None

        # Content types we can read as text
        text_content_types = [
            'text/plain',
            'text/html',
            'application/json',
            'text/xml',
            'application/xml',
        ]

        # File extensions we can read as text (for chord charts, lyrics)
        text_extensions = ['.txt', '.cho', '.chopro', '.chordpro', '.onsong', '.pro']

        # Check file type
        url_lower = attachment_url.lower()
        filename_lower = (filename or '').lower()
        file_type_lower = (file_type or '').lower()

        is_pdf = (
            file_type_lower == 'pdf' or
            (content_type and 'pdf' in content_type.lower()) or
            filename_lower.endswith('.pdf') or
            '.pdf' in filename_lower or
            url_lower.endswith('.pdf') or
            '.pdf?' in url_lower
        )

        is_text = False
        if not is_pdf:
            if content_type and any(ct in content_type.lower() for ct in text_content_types):
                is_text = True
            elif any(url_lower.endswith(ext) or f'{ext}?' in url_lower for ext in text_extensions):
                is_text = True
            elif any(filename_lower.endswith(ext) for ext in text_extensions):
                is_text = True

        if not is_text and not is_pdf:
            logger.debug(f"Skipping unsupported attachment type: {content_type} / {filename} / {file_type}")
            return None

        try:
            response = requests.get(
                attachment_url,
                auth=(self.app_id, self.secret),
                timeout=30
            )
            response.raise_for_status()

            # Check content length
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > max_size:
                logger.warning(f"Attachment too large: {content_length} bytes")
                return None

            if is_pdf:
                return self._extract_pdf_text(response.content)
            else:
                return response.text[:max_size]

        except requests.RequestException as e:
            logger.error(f"Error fetching attachment: {e}")
            return None

    def _extract_pdf_text(self, pdf_content: bytes) -> Optional[str]:
        """
        Extract text content from a PDF file.

        First tries direct text extraction with pypdf. If that fails (image-based PDF),
        falls back to OCR using pytesseract.

        Args:
            pdf_content: Raw PDF bytes.

        Returns:
            Extracted text or None if extraction fails.
        """
        from io import BytesIO

        # First try direct text extraction with pypdf
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(pdf_content))
            text_parts = []

            for page in reader.pages:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_parts.append(page_text)

            if text_parts:
                full_text = '\n\n'.join(text_parts)
                # Check if we got meaningful text (not just whitespace/symbols)
                if len(full_text.strip()) > 50:
                    logger.info(f"Extracted {len(full_text)} characters from PDF ({len(reader.pages)} pages)")
                    return full_text

            # If we get here, text extraction didn't work well - try OCR
            logger.info("PDF text extraction yielded little content, attempting OCR...")

        except ImportError:
            logger.warning("pypdf not installed - trying OCR directly")
        except Exception as e:
            logger.warning(f"pypdf extraction failed: {e} - trying OCR")

        # Fall back to OCR for image-based PDFs
        return self._extract_pdf_text_ocr(pdf_content)

    def _extract_pdf_text_ocr(self, pdf_content: bytes) -> Optional[str]:
        """
        Extract text from a PDF using OCR (for scanned/image-based PDFs).

        Args:
            pdf_content: Raw PDF bytes.

        Returns:
            Extracted text or None if OCR fails.
        """
        try:
            from pdf2image import convert_from_bytes
            import pytesseract

            # Convert PDF pages to images
            logger.info("Converting PDF to images for OCR...")
            images = convert_from_bytes(pdf_content, dpi=300)

            text_parts = []
            for i, image in enumerate(images):
                logger.info(f"Running OCR on page {i + 1}/{len(images)}...")
                # Run OCR on each page
                page_text = pytesseract.image_to_string(image)
                if page_text and page_text.strip():
                    text_parts.append(page_text)

            if text_parts:
                full_text = '\n\n'.join(text_parts)
                logger.info(f"OCR extracted {len(full_text)} characters from {len(images)} pages")
                return full_text
            else:
                logger.warning("OCR could not extract any text from PDF")
                return None

        except ImportError as e:
            logger.warning(f"OCR libraries not available: {e}")
            return None
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return None

    def get_song_with_attachments(self, song_title: str, fetch_content: bool = True) -> Optional[dict]:
        """
        Search for a song and get all its attachments across arrangements.

        Args:
            song_title: Title to search for.
            fetch_content: If True, fetch text content from attachments.

        Returns:
            Dict with song info and all attachments, or None if not found.
        """
        songs = self.search_songs(song_title, limit=5)
        if not songs:
            return None

        # Find best match
        best_match = None
        title_lower = song_title.lower()

        for song in songs:
            song_attrs = song.get('attributes', {})
            if (song_attrs.get('title') or '').lower() == title_lower:
                best_match = song
                break

        if not best_match:
            best_match = songs[0]

        song_id = best_match.get('id')
        details = self.get_song_details(song_id)

        # Get attachments for each arrangement
        all_attachments = details.get('attachments', [])[:]
        for arr in details.get('arrangements', []):
            arr_id = arr.get('id')
            if arr_id:
                arr_attachments = self.get_arrangement_attachments(song_id, arr_id)
                for attach in arr_attachments:
                    attach['arrangement_name'] = arr.get('name')
                    attach['arrangement_key'] = arr.get('key')
                all_attachments.extend(arr_attachments)

        # Fetch text content from attachments if requested
        if fetch_content:
            for attach in all_attachments:
                url = attach.get('url')
                content_type = attach.get('content_type')
                filename = attach.get('filename', '')
                filename_lower = filename.lower()
                file_type = attach.get('file_type', '').lower()

                # Try to fetch content for:
                # - Files with chord/lyric/chart keywords
                # - Any PDF files (they often contain lyrics/charts)
                # - Text-based formats
                # - Files with "numbers" or "lead" in the name (common chart formats)
                should_fetch = (
                    'chord' in filename_lower or
                    'lyric' in filename_lower or
                    'chart' in filename_lower or
                    'numbers' in filename_lower or
                    'lead' in filename_lower or
                    'sheet' in filename_lower or
                    filename_lower.endswith('.pdf') or
                    '.pdf' in filename_lower or
                    file_type == 'pdf' or
                    'pdf' in (content_type or '').lower() or
                    filename_lower.endswith(('.txt', '.cho', '.chopro', '.chordpro', '.onsong', '.pro'))
                )

                if url and should_fetch:
                    content = self.fetch_attachment_content(url, content_type, filename, file_type=file_type)
                    if content:
                        attach['text_content'] = content
                        logger.info(f"Fetched content from attachment: {filename}")
                    else:
                        logger.warning(f"Could not extract content from attachment: {filename} (type: {file_type})")

        details['all_attachments'] = all_attachments
        return details

    def find_plans_for_target_date(self, target_date, window_days: int = 0) -> list:
        """
        Find plans across all service types for a specific target date.

        This is more efficient than get_plans_for_date_range when looking for a known date
        (like Easter, Thanksgiving, etc.) because it uses date filtering in the API
        rather than fetching many plans and filtering locally.

        Args:
            target_date: The target date (datetime.date object).
            window_days: Days before/after target to search (default 0 for exact date only).

        Returns:
            List of plan records matching the date window, with service_type_name included.
        """
        from datetime import timedelta

        # Calculate date range
        start_date = (target_date - timedelta(days=window_days)).isoformat()
        end_date = (target_date + timedelta(days=window_days)).isoformat()
        target_str = target_date.isoformat()

        logger.info(f"Searching for plans on {target_str} (window: ±{window_days} days)")

        service_types = self.get_service_types()
        matching_plans = []
        seen_plan_ids = set()

        for st in service_types:
            st_id = st.get('id')
            st_name = st.get('attributes', {}).get('name', 'Unknown')

            # Use date range filter if supported, otherwise fetch and filter
            plans = self.get_plans_by_date_range(st_id, start_date, end_date, limit=10)

            # If no results from date range filter, fall back to recent plans
            if not plans:
                # Fetch a small number of recent plans and filter
                plans = self.get_plans(st_id, past_only=True, limit=5)

            for plan in plans:
                plan_id = plan.get('id')
                if plan_id in seen_plan_ids:
                    continue

                plan_date = plan.get('attributes', {}).get('sort_date', '')[:10]

                # Check if plan is within our window
                if window_days == 0:
                    # Exact date match only
                    if plan_date == target_str:
                        plan['service_type_name'] = st_name
                        plan['service_type_id'] = st_id
                        matching_plans.append(plan)
                        seen_plan_ids.add(plan_id)
                else:
                    # Within window
                    if start_date <= plan_date <= end_date:
                        plan['service_type_name'] = st_name
                        plan['service_type_id'] = st_id
                        matching_plans.append(plan)
                        seen_plan_ids.add(plan_id)

        logger.info(f"Found {len(matching_plans)} plans for target date {target_str}")
        return matching_plans

    def get_plans_for_date_range(self, include_future: bool = True, include_past: bool = True, limit: int = 30, use_cache: bool = True) -> list:
        """
        Get plans across all service types, including both past and/or future plans.

        Args:
            include_future: Include future plans.
            include_past: Include past plans.
            limit: Maximum number of plans per service type to fetch.
            use_cache: Whether to use cached results.

        Returns:
            List of plan records with service type info.
        """
        from datetime import datetime
        today = datetime.now().date()

        # Check cache first
        cache_key = f"{PCO_PLANS_CACHE_KEY}_future{include_future}_past{include_past}_limit{limit}"
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.info(f"Using cached plans list ({len(cached)} plans)")
                return cached

        service_types = self.get_service_types()
        all_plans = []
        seen_plan_ids = set()  # Avoid duplicates

        for st in service_types:
            st_id = st.get('id')
            st_name = st.get('attributes', {}).get('name', 'Unknown')

            # Fetch past plans (descending order - most recent first)
            if include_past:
                past_plans = self.get_plans(st_id, past_only=True, limit=limit)
                logger.info(f"Fetched {len(past_plans)} past plans for service type '{st_name}'")
                for plan in past_plans:
                    plan_id = plan.get('id')
                    if plan_id not in seen_plan_ids:
                        plan['service_type_name'] = st_name
                        plan['service_type_id'] = st_id
                        all_plans.append(plan)
                        seen_plan_ids.add(plan_id)

            # Fetch future plans separately to ensure we get them
            if include_future:
                # Try both: PCO's filter and also a no-filter approach
                future_plans = self.get_plans(st_id, future_only=True, limit=limit)
                logger.info(f"Fetched {len(future_plans)} future plans for service type '{st_name}'")

                if not future_plans:
                    # Fallback: fetch all plans and filter locally for future dates
                    # This handles cases where PCO's filter might not work as expected
                    logger.info(f"No future plans from filter, trying unfiltered fetch...")
                    all_st_plans = self._get(
                        f"/services/v2/service_types/{st_id}/plans",
                        params={'per_page': 50, 'order': 'sort_date'}  # Ascending order to get upcoming first
                    ).get('data', [])

                    for plan in all_st_plans:
                        plan_date_str = plan.get('attributes', {}).get('sort_date', '')[:10]
                        if plan_date_str:
                            try:
                                plan_date = datetime.strptime(plan_date_str, '%Y-%m-%d').date()
                                if plan_date >= today:
                                    future_plans.append(plan)
                            except ValueError:
                                pass

                    logger.info(f"Found {len(future_plans)} future plans from unfiltered fetch")

                for plan in future_plans:
                    plan_id = plan.get('id')
                    if plan_id not in seen_plan_ids:
                        plan['service_type_name'] = st_name
                        plan['service_type_id'] = st_id
                        all_plans.append(plan)
                        seen_plan_ids.add(plan_id)

        # Sort by date
        all_plans.sort(key=lambda p: p.get('attributes', {}).get('sort_date', ''), reverse=True)
        logger.info(f"Total plans: {len(all_plans)} (include_future={include_future}, include_past={include_past})")

        # Cache results
        if all_plans:
            cache.set(cache_key, all_plans, PCO_PLANS_CACHE_TIMEOUT)

        return all_plans

    def _calculate_easter(self, year: int):
        """
        Calculate Easter Sunday for a given year using the Anonymous Gregorian algorithm.

        Args:
            year: The year to calculate Easter for.

        Returns:
            A date object for Easter Sunday.
        """
        from datetime import date
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(year, month, day)

    def find_plan_by_date(self, date_str: str, service_type: str = None) -> Optional[dict]:
        """
        Find a plan by date string.

        Args:
            date_str: Date string to search for (e.g., "December 1", "last Sunday", "12/1", "Easter 2025").
            service_type: Optional service type name to filter by (e.g., "HSM", "Cherry Hills Morning Main").
                         If not specified, defaults to the main Sunday morning service.

        Returns:
            Plan details or None.
        """
        from datetime import datetime, timedelta
        import re

        # Try to parse the date
        today = datetime.now().date()
        target_date = None

        # Handle relative dates
        date_lower = date_str.lower()
        if 'last sunday' in date_lower:
            days_since_sunday = (today.weekday() + 1) % 7
            if days_since_sunday == 0:
                days_since_sunday = 7
            target_date = today - timedelta(days=days_since_sunday)
        elif 'this sunday' in date_lower or 'next sunday' in date_lower:
            days_until_sunday = (6 - today.weekday()) % 7
            if days_until_sunday == 0:
                days_until_sunday = 7
            target_date = today + timedelta(days=days_until_sunday)
        elif 'yesterday' in date_lower:
            target_date = today - timedelta(days=1)
        elif 'today' in date_lower:
            target_date = today
        elif 'easter' in date_lower:
            # Handle Easter date queries
            # Supported formats:
            # - "Easter 2025" / "easter 2024"
            # - "Easter last year" / "Easter this year" / "Easter next year"
            # - "last Easter" / "this Easter" / "next Easter"
            year_match = re.search(r'easter\s*(\d{4})', date_lower)
            if year_match:
                year = int(year_match.group(1))
            elif 'last year' in date_lower or 'last easter' in date_lower:
                year = today.year - 1
            elif 'next year' in date_lower or 'next easter' in date_lower:
                year = today.year + 1
            elif 'this year' in date_lower or 'this easter' in date_lower:
                year = today.year
            else:
                # Default to current year if no modifier specified
                year = today.year
            target_date = self._calculate_easter(year)
            logger.info(f"Calculated Easter {year} as {target_date}")
        else:
            # Clean up the date string - remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
            clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)

            # Try parsing various formats
            formats = [
                '%B %d, %Y',   # November 16, 2025
                '%B %d %Y',    # November 16 2025
                '%B %d',       # November 16
                '%b %d, %Y',   # Nov 16, 2025
                '%b %d %Y',    # Nov 16 2025
                '%b %d',       # Nov 16
                '%m/%d/%Y',    # 11/16/2025
                '%m/%d/%y',    # 11/16/25
                '%m/%d',       # 11/16
                '%m-%d-%Y',    # 11-16-2025
                '%m-%d',       # 11-16
                '%Y-%m-%d',    # 2025-11-16
            ]
            for fmt in formats:
                try:
                    parsed = datetime.strptime(clean_date.strip(), fmt)
                    # If no year in format, assume current year
                    if parsed.year == 1900:
                        parsed = parsed.replace(year=today.year)
                    target_date = parsed.date()
                    break
                except ValueError:
                    continue

        if not target_date:
            logger.warning(f"Could not parse date: {date_str}")
            return None

        target_str = target_date.isoformat()
        logger.info(f"Looking for plan on {target_str}")

        # OPTIMIZED SEARCH: First try exact date, then expand if needed
        # This is much more efficient than fetching 30-60 plans and filtering

        # Step 1: Try to find plans on the exact target date
        matching_plans = self.find_plans_for_target_date(target_date, window_days=0)

        # Step 2: If no exact match, expand to ±14 days (2 weeks / ~2 Sundays)
        if not matching_plans:
            logger.info(f"No exact match for {target_str}, expanding search to ±14 days")
            matching_plans = self.find_plans_for_target_date(target_date, window_days=14)

            # Filter to prefer plans closest to target date
            if matching_plans:
                # Sort by proximity to target date
                matching_plans.sort(
                    key=lambda p: abs(
                        (datetime.strptime(p.get('attributes', {}).get('sort_date', '')[:10], '%Y-%m-%d').date() - target_date).days
                    )
                )

        if not matching_plans:
            logger.info(f"No plan found for date {target_str}")
            return None

        logger.info(f"Found {len(matching_plans)} plans for date {target_str}")

        # Helper to get plan details and include service_type_name
        def get_plan_with_service_name(plan_data):
            service_type_id = plan_data.get('service_type_id')
            plan_id = plan_data.get('id')
            service_name = plan_data.get('service_type_name', '')
            details = self.get_plan_details(service_type_id, plan_id)
            if details:
                details['service_type_name'] = service_name
            return details

        # If a specific service type was requested, filter to that
        if service_type:
            service_type_lower = service_type.lower()
            for plan in matching_plans:
                plan_service_name = (plan.get('service_type_name') or '').lower()
                # Check for partial match (e.g., "HSM" matches "HSM Sunday")
                if service_type_lower in plan_service_name or plan_service_name in service_type_lower:
                    logger.info(f"Found matching plan for '{service_type}': {plan.get('id')} ({plan.get('service_type_name')})")
                    return get_plan_with_service_name(plan)
            # If specific type not found, log and return None
            logger.info(f"No plan found for service type '{service_type}' on {target_str}")
            return None

        # No specific service type requested - prioritize main service
        # First, look for the default main service
        default_name_lower = DEFAULT_SERVICE_TYPE_NAME.lower()
        for plan in matching_plans:
            plan_service_name = (plan.get('service_type_name') or '').lower()
            if default_name_lower in plan_service_name or plan_service_name in default_name_lower:
                logger.info(f"Found main service plan: {plan.get('id')} ({plan.get('service_type_name')})")
                return get_plan_with_service_name(plan)

        # If main service not found, look for any non-youth service
        for plan in matching_plans:
            plan_service_name = (plan.get('service_type_name') or '').lower()
            is_youth_service = any(keyword in plan_service_name for keyword in YOUTH_SERVICE_KEYWORDS)
            if not is_youth_service:
                logger.info(f"Found non-youth service plan: {plan.get('id')} ({plan.get('service_type_name')})")
                return get_plan_with_service_name(plan)

        # Fallback: return first matching plan
        plan = matching_plans[0]
        logger.info(f"Fallback to first plan: {plan.get('id')} ({plan.get('service_type_name')})")
        return get_plan_with_service_name(plan)

    # ========== BLOCKOUT METHODS ==========

    def get_person_blockouts(self, person_name: str) -> dict:
        """
        Get a person's blockout dates from Planning Center Services.

        Args:
            person_name: Name of the person to look up.

        Returns:
            Dict with:
            - 'found': True if person was found
            - 'person_name': The matched person's name
            - 'blockouts': List of blockout records with dates and reasons
        """
        from difflib import SequenceMatcher

        result = {
            'found': False,
            'person_name': person_name,
            'blockouts': [],
            'services_person_id': None
        }

        # First, find the person in Services
        services_person = self._find_services_person_by_name(person_name)
        if not services_person:
            logger.info(f"Could not find '{person_name}' in Services for blockout lookup")
            return result

        person_id = services_person.get('id')
        person_attrs = services_person.get('attributes', {})
        actual_name = f"{person_attrs.get('first_name', '')} {person_attrs.get('last_name', '')}".strip()

        result['found'] = True
        result['person_name'] = actual_name or person_name
        result['services_person_id'] = person_id

        # Get blockouts for this person
        blockouts_result = self._get(
            f"/services/v2/people/{person_id}/blockouts",
            params={'per_page': 50, 'order': 'starts_at'}
        )

        for blockout in blockouts_result.get('data', []):
            attrs = blockout.get('attributes', {})
            result['blockouts'].append({
                'id': blockout.get('id'),
                'starts_at': attrs.get('starts_at'),
                'ends_at': attrs.get('ends_at'),
                'reason': attrs.get('reason', ''),
                'repeat_frequency': attrs.get('repeat_frequency'),
                'repeat_interval': attrs.get('repeat_interval'),
                'repeat_period': attrs.get('repeat_period'),
                'share': attrs.get('share', False),
                'created_at': attrs.get('created_at')
            })

        logger.info(f"Found {len(result['blockouts'])} blockouts for {actual_name}")
        return result

    def _find_services_person_by_name(self, person_name: str) -> Optional[dict]:
        """
        Find a Services person record by name.

        Args:
            person_name: Name to search for.

        Returns:
            Services person record or None.
        """
        from difflib import SequenceMatcher

        if not person_name:
            return None

        # Parse the name
        name_parts = person_name.strip().split()
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[-1] if len(name_parts) > 1 else ''

        # Try searching by first name
        search_result = self._get("/services/v2/people", params={
            'where[first_name]': first_name,
            'per_page': 50
        })
        candidates = search_result.get('data', [])

        # Also try last name search if first name didn't find enough
        if len(candidates) < 3:
            last_search = self._get("/services/v2/people", params={
                'where[last_name]': last_name,
                'per_page': 50
            })
            for p in last_search.get('data', []):
                if p not in candidates:
                    candidates.append(p)

        # If still no results, paginate through all
        if not candidates:
            candidates = self._get_all_services_people_list()

        # Find best match
        search_full = person_name.lower().strip()
        best_match = None
        best_score = 0

        for person in candidates:
            attrs = person.get('attributes', {})
            p_first = (attrs.get('first_name') or '').lower()
            p_last = (attrs.get('last_name') or '').lower()
            p_full = f"{p_first} {p_last}".strip()

            # Exact match
            if p_first == first_name.lower() and p_last == last_name.lower():
                return person

            # Fuzzy match
            score = SequenceMatcher(None, search_full, p_full).ratio()
            if score > best_score and score > 0.7:
                best_score = score
                best_match = person

        return best_match

    def _get_all_services_people_list(self, max_pages: int = 5) -> list:
        """
        Fetch services people with pagination for name matching.

        Args:
            max_pages: Maximum pages to fetch.

        Returns:
            List of services person records.
        """
        all_people = []
        offset = 0
        per_page = 100

        for _ in range(max_pages):
            result = self._get("/services/v2/people", params={
                'per_page': per_page,
                'offset': offset
            })
            data = result.get('data', [])
            if not data:
                break
            all_people.extend(data)
            if len(data) < per_page:
                break
            offset += per_page

        return all_people

    def _get_cached_person_blockouts(self, person_id: str) -> list:
        """
        Get blockouts for a person, using cache when available.

        Args:
            person_id: The PCO person ID.

        Returns:
            List of blockout records.
        """
        cache_key = f"{PCO_BLOCKOUTS_CACHE_KEY}_{person_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            blockouts_result = self._get(
                f"/services/v2/people/{person_id}/blockouts",
                params={'per_page': 50}
            )
            blockouts = blockouts_result.get('data', [])
            cache.set(cache_key, blockouts, PCO_BLOCKOUTS_CACHE_TIMEOUT)
            return blockouts
        except Exception as e:
            logger.warning(f"Error fetching blockouts for person {person_id}: {e}")
            return []

    def get_blockouts_for_date(self, date_str: str) -> dict:
        """
        Get team members who are blocked out on a specific date.

        OPTIMIZED: This method uses multiple strategies to minimize API calls:
        1. First checks team_member status codes (B=Blocked) - no extra API calls
        2. Uses cached blockouts when available
        3. Falls back to individual API calls only for uncached people

        Args:
            date_str: Date string to check (e.g., "December 14", "12/14/2025").

        Returns:
            Dict with:
            - 'date': The parsed date
            - 'blocked_people': List of people blocked out on that date
            - 'total_people_checked': Number of people checked
            - 'api_calls_made': Number of API calls (for monitoring optimization)
        """
        from datetime import datetime, timedelta

        result = {
            'date': date_str,
            'date_parsed': None,
            'blocked_people': [],
            'total_people_checked': 0,
            'api_calls_made': 0,
            'cache_hits': 0
        }

        # Parse the date
        target_date = self._parse_date_string(date_str)
        if not target_date:
            logger.warning(f"Could not parse date: {date_str}")
            return result

        result['date_parsed'] = target_date.isoformat()

        # First, try to find the service plan for this date
        plan = self.find_plan_by_date(date_str)

        team_member_ids = set()
        team_member_names = {}  # Map ID to name
        already_blocked = set()  # People already known to be blocked (from status)

        if plan and plan.get('plan_id'):
            plan_id = plan.get('plan_id')
            service_type_id = plan.get('service_type_id')

            if service_type_id and plan_id:
                # OPTIMIZATION: Get team members with person data included
                # The status field already tells us who declined due to blockout
                # PAGINATION: Fetch all pages to get all team members
                offset = 0
                per_page = 100

                while True:
                    team_result = self._get(
                        f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members",
                        params={'include': 'person', 'per_page': per_page, 'offset': offset}
                    )
                    result['api_calls_made'] += 1

                    members_data = team_result.get('data', [])
                    if not members_data:
                        break  # No more results

                    # Build person lookup from included data
                    people_lookup = {}
                    for inc in team_result.get('included', []):
                        if inc.get('type') == 'Person':
                            people_lookup[inc.get('id')] = inc

                    for member in members_data:
                        attrs = member.get('attributes', {})
                        name = attrs.get('name', '')
                        status = attrs.get('status', '')

                        # Get person_id from relationships
                        person_id = None
                        relationships = member.get('relationships', {})
                        person_data = relationships.get('person', {}).get('data', {})
                        if person_data:
                            person_id = person_data.get('id')

                        if person_id:
                            team_member_ids.add(person_id)
                            team_member_names[person_id] = name

                            # OPTIMIZATION: If status is 'B' (Blocked), they're already blocked!
                            # No need to make additional API call
                            if status == 'B':
                                already_blocked.add(person_id)
                                result['blocked_people'].append({
                                    'name': name,
                                    'person_id': person_id,
                                    'reason': 'Blocked (from schedule status)',
                                    'starts_at': None,
                                    'ends_at': None
                                })

                    # Check if we got fewer results than requested (last page)
                    if len(members_data) < per_page:
                        break

                    offset += per_page

                logger.info(f"Found {len(team_member_ids)} team members, {len(already_blocked)} already blocked from status")

        # If no plan found, get all services people with pagination
        if not team_member_ids:
            logger.info(f"No plan found for {date_str}, checking all services people")
            offset = 0
            per_page = 100

            while True:
                services_people = self._get(
                    "/services/v2/people",
                    params={'per_page': per_page, 'offset': offset, 'order': '-updated_at'}
                )
                result['api_calls_made'] += 1

                people_data = services_people.get('data', [])
                if not people_data:
                    break

                for person in people_data:
                    person_id = person.get('id')
                    attrs = person.get('attributes', {})
                    name = f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip()
                    if person_id:
                        team_member_ids.add(person_id)
                        team_member_names[person_id] = name

                if len(people_data) < per_page:
                    break

                offset += per_page

            logger.info(f"Using {len(team_member_ids)} services people (all pages)")

        result['total_people_checked'] = len(team_member_ids)

        # Check blockouts for remaining people (not already known to be blocked)
        # OPTIMIZATION: Use cached blockouts when available
        people_to_check = team_member_ids - already_blocked

        import time
        api_call_count = 0

        for person_id in people_to_check:
            person_name = team_member_names.get(person_id, 'Unknown')

            # Try to get from cache first
            cache_key = f"{PCO_BLOCKOUTS_CACHE_KEY}_{person_id}"
            cached_blockouts = cache.get(cache_key)

            if cached_blockouts is not None:
                # Use cached data
                result['cache_hits'] += 1
                blockouts = cached_blockouts
            else:
                # Rate limiting: add delay to avoid 429 errors
                api_call_count += 1
                if api_call_count > 0 and api_call_count % PCO_BLOCKOUT_RATE_LIMIT_CALLS == 0:
                    time.sleep(PCO_BLOCKOUT_RATE_LIMIT_DELAY)

                # Fetch from API with retry logic
                try:
                    blockouts_result = self._get(
                        f"/services/v2/people/{person_id}/blockouts",
                        params={'per_page': 50},
                        retry_on_429=True
                    )
                    result['api_calls_made'] += 1
                    blockouts = blockouts_result.get('data', [])
                    # Cache for next time
                    cache.set(cache_key, blockouts, PCO_BLOCKOUTS_CACHE_TIMEOUT)
                except Exception as e:
                    logger.warning(f"Error checking blockouts for {person_name}: {e}")
                    continue

            # Check if any blockout covers the target date
            for blockout in blockouts:
                b_attrs = blockout.get('attributes', {})
                starts_at = b_attrs.get('starts_at')
                ends_at = b_attrs.get('ends_at')

                if self._date_in_blockout_range(target_date, starts_at, ends_at):
                    result['blocked_people'].append({
                        'name': person_name,
                        'person_id': person_id,
                        'reason': b_attrs.get('reason', ''),
                        'starts_at': starts_at,
                        'ends_at': ends_at
                    })
                    break  # Person is blocked, no need to check more blockouts

        logger.info(
            f"Blockout check for {target_date}: {len(result['blocked_people'])} blocked, "
            f"{result['api_calls_made']} API calls, {result['cache_hits']} cache hits"
        )
        return result

    def _date_in_blockout_range(self, check_date, starts_at: str, ends_at: str) -> bool:
        """
        Check if a date falls within a blockout range.

        Args:
            check_date: Date to check (datetime.date object).
            starts_at: Blockout start date string.
            ends_at: Blockout end date string.

        Returns:
            True if the date is within the blockout range.
        """
        from datetime import datetime

        if not starts_at:
            return False

        try:
            # Parse ISO format dates (YYYY-MM-DDTHH:MM:SS)
            start_date = datetime.fromisoformat(starts_at.replace('Z', '+00:00')).date()

            if ends_at:
                end_date = datetime.fromisoformat(ends_at.replace('Z', '+00:00')).date()
            else:
                end_date = start_date

            return start_date <= check_date <= end_date
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing blockout dates: {e}")
            return False

    def check_person_availability(self, person_name: str, date_str: str) -> dict:
        """
        Check if a specific person is available on a given date.

        Args:
            person_name: Name of the person to check.
            date_str: Date to check availability for.

        Returns:
            Dict with:
            - 'person_name': The matched person's name
            - 'date': The date checked
            - 'available': True if available, False if blocked
            - 'blockout_reason': Reason for blockout if blocked
        """
        result = {
            'found': False,
            'person_name': person_name,
            'date': date_str,
            'date_parsed': None,
            'available': True,
            'blockout_reason': '',
            'blockout_dates': None
        }

        # Parse the date
        target_date = self._parse_date_string(date_str)
        if not target_date:
            logger.warning(f"Could not parse date: {date_str}")
            return result

        result['date_parsed'] = target_date.isoformat()

        # Find the person
        services_person = self._find_services_person_by_name(person_name)
        if not services_person:
            logger.info(f"Could not find '{person_name}' in Services")
            return result

        person_id = services_person.get('id')
        attrs = services_person.get('attributes', {})
        actual_name = f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip()

        result['found'] = True
        result['person_name'] = actual_name

        # Check their blockouts
        blockouts_result = self._get(
            f"/services/v2/people/{person_id}/blockouts",
            params={'per_page': 50}
        )

        for blockout in blockouts_result.get('data', []):
            b_attrs = blockout.get('attributes', {})
            starts_at = b_attrs.get('starts_at')
            ends_at = b_attrs.get('ends_at')

            if self._date_in_blockout_range(target_date, starts_at, ends_at):
                result['available'] = False
                result['blockout_reason'] = b_attrs.get('reason', 'No reason provided')
                result['blockout_dates'] = {
                    'starts_at': starts_at,
                    'ends_at': ends_at
                }
                break

        status = "available" if result['available'] else f"blocked out ({result['blockout_reason']})"
        logger.info(f"{actual_name} is {status} on {target_date}")
        return result

    def get_team_availability_for_date(self, date_str: str, team_name: str = None) -> dict:
        """
        Get availability status for team members on a specific date.

        Instead of checking all services people, this method finds the service
        plan for that date and checks only team members associated with that service.

        Args:
            date_str: Date to check.
            team_name: Optional team name to filter (e.g., "Band", "Vocals").

        Returns:
            Dict with available and unavailable team members.
        """
        import time

        result = {
            'date': date_str,
            'date_parsed': None,
            'team_name': team_name,
            'available': [],
            'blocked': [],
            'total_checked': 0
        }

        # Parse the date
        target_date = self._parse_date_string(date_str)
        if not target_date:
            logger.warning(f"Could not parse date: {date_str}")
            return result

        result['date_parsed'] = target_date.isoformat()

        # Get team members from the plan for this date
        team_member_ids = set()
        team_member_names = {}

        plan = self.find_plan_by_date(date_str)

        if plan and plan.get('plan_id'):
            plan_id = plan.get('plan_id')
            service_type_id = plan.get('service_type_id')

            if service_type_id and plan_id:
                team_result = self._get(
                    f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members",
                    params={'per_page': 100}
                )

                team_name_lower = (team_name or '').lower()

                for member in team_result.get('data', []):
                    attrs = member.get('attributes', {})
                    name = attrs.get('name', '')
                    member_team = attrs.get('team_position_name', '')

                    # Filter by team name if specified
                    if team_name_lower and team_name_lower not in (member_team or '').lower():
                        continue

                    # Get person_id from relationships
                    person_id = None
                    relationships = member.get('relationships', {})
                    person_data = relationships.get('person', {}).get('data', {})
                    if person_data:
                        person_id = person_data.get('id')

                    if person_id:
                        team_member_ids.add(person_id)
                        team_member_names[person_id] = name

                logger.info(f"Found {len(team_member_ids)} team members from plan for {date_str}")

        # If no plan found, use a limited sample
        if not team_member_ids:
            logger.info(f"No plan found for {date_str}, using recent active people")
            services_people = self._get(
                "/services/v2/people",
                params={'per_page': 50, 'order': '-updated_at'}
            )

            for person in services_people.get('data', []):
                person_id = person.get('id')
                attrs = person.get('attributes', {})
                name = f"{attrs.get('first_name', '')} {attrs.get('last_name', '')}".strip()
                if person_id:
                    team_member_ids.add(person_id)
                    team_member_names[person_id] = name

        result['total_checked'] = len(team_member_ids)

        # Check each person's availability with rate limiting
        checked = 0
        for person_id in team_member_ids:
            person_name = team_member_names.get(person_id, 'Unknown')

            # Rate limiting
            checked += 1
            if checked > 0 and checked % PCO_BLOCKOUT_RATE_LIMIT_CALLS == 0:
                time.sleep(PCO_BLOCKOUT_RATE_LIMIT_DELAY)

            try:
                blockouts_result = self._get(
                    f"/services/v2/people/{person_id}/blockouts",
                    params={'per_page': 50},
                    retry_on_429=True
                )

                is_blocked = False
                block_reason = ''

                for blockout in blockouts_result.get('data', []):
                    b_attrs = blockout.get('attributes', {})
                    if self._date_in_blockout_range(target_date, b_attrs.get('starts_at'), b_attrs.get('ends_at')):
                        is_blocked = True
                        block_reason = b_attrs.get('reason', '')
                        break

                if is_blocked:
                    result['blocked'].append({
                        'name': person_name,
                        'reason': block_reason
                    })
                else:
                    result['available'].append({
                        'name': person_name
                    })

                checked += 1
            except Exception as e:
                logger.warning(f"Error checking availability for {person_name}: {e}")
                continue

        logger.info(f"Availability check for {target_date}: {len(result['available'])} available, {len(result['blocked'])} blocked")
        return result

    def _parse_date_string(self, date_str: str):
        """
        Parse various date string formats into a date object.

        Args:
            date_str: Date string to parse.

        Returns:
            datetime.date object or None if parsing fails.
        """
        from datetime import datetime, timedelta
        import re

        if not date_str:
            return None

        date_str_lower = date_str.lower().strip()
        today = datetime.now().date()

        # Handle relative dates
        if date_str_lower in ['today', 'tonight']:
            return today
        elif date_str_lower == 'tomorrow':
            return today + timedelta(days=1)
        elif date_str_lower == 'yesterday':
            return today - timedelta(days=1)

        # Handle "this/next/last Sunday" etc.
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day_name in enumerate(day_names):
            if day_name in date_str_lower:
                current_weekday = today.weekday()
                target_weekday = i

                if 'next' in date_str_lower:
                    days_ahead = (target_weekday - current_weekday + 7) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    return today + timedelta(days=days_ahead)
                elif 'last' in date_str_lower:
                    days_back = (current_weekday - target_weekday + 7) % 7
                    if days_back == 0:
                        days_back = 7
                    return today - timedelta(days=days_back)
                else:  # "this Sunday" or just "Sunday"
                    days_ahead = (target_weekday - current_weekday + 7) % 7
                    return today + timedelta(days=days_ahead)

        # Handle MM/DD/YYYY or MM-DD-YYYY
        date_patterns = [
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', '%m/%d/%Y'),
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', '%m-%d-%Y'),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),
        ]

        for pattern, fmt in date_patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    return datetime.strptime(match.group(0), fmt).date()
                except ValueError:
                    continue

        # Handle "December 14" or "December 14, 2025" or "Dec 14"
        month_names = {
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
            'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
            'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
            'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
        }

        for month_str, month_num in month_names.items():
            pattern = rf'{month_str}\w*\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?'
            match = re.search(pattern, date_str_lower)
            if match:
                day = int(match.group(1))
                year = int(match.group(2)) if match.group(2) else today.year
                try:
                    return datetime(year, month_num, day).date()
                except ValueError:
                    continue

        logger.warning(f"Could not parse date string: {date_str}")
        return None

    def expand_week_reference(self, date_str: str) -> list:
        """
        Expand a week-of-month reference into individual dates.

        Args:
            date_str: Date string like "first week of February 2026".

        Returns:
            List of (date, formatted_date_with_weekday) tuples for each day in the week,
            or empty list if not a week reference.
        """
        from datetime import datetime, timedelta
        import re

        if not date_str:
            return []

        date_str_lower = date_str.lower().strip()

        # Check for week-of-month pattern
        week_pattern = r'(first|second|third|fourth|last)\s+week\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+(\d{4}))?'
        match = re.search(week_pattern, date_str_lower)

        if not match:
            return []

        week_ordinal = match.group(1)
        month_str = match.group(2)
        year_str = match.group(3)

        # Map month names to numbers
        month_names = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }

        month = month_names.get(month_str)
        if not month:
            return []

        # Determine year
        today = datetime.now().date()
        if year_str:
            year = int(year_str)
        else:
            year = today.year

        # Find the first day of the month
        first_of_month = datetime(year, month, 1).date()

        # Map ordinals to week numbers (0-indexed for calculation)
        ordinal_map = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'last': -1}
        week_num = ordinal_map.get(week_ordinal, 0)

        # Calculate the start of the target week
        if week_num == -1:
            # Last week of month - find last day, then go back to Sunday
            if month == 12:
                last_of_month = datetime(year + 1, 1, 1).date() - timedelta(days=1)
            else:
                last_of_month = datetime(year, month + 1, 1).date() - timedelta(days=1)

            # Find the Sunday of the last week (week starts on Sunday)
            days_since_sunday = (last_of_month.weekday() + 1) % 7
            week_start = last_of_month - timedelta(days=days_since_sunday)
        else:
            # First day of first week is the first Sunday on or before the 7th
            # Or we can define week 1 as days 1-7, week 2 as days 8-14, etc.
            # For simplicity: first week = days 1-7, second week = days 8-14, etc.
            week_start = first_of_month + timedelta(days=week_num * 7)

        # Generate all days in the week (Sunday to Saturday)
        dates = []
        for i in range(7):
            current_date = week_start + timedelta(days=i)
            # Only include dates that are in the target month
            if current_date.month == month:
                weekday_name = current_date.strftime('%A')
                formatted = f"{current_date.strftime('%B')} {current_date.day}, {current_date.year} ({weekday_name})"
                dates.append((current_date, formatted))

        logger.info(f"Expanded '{date_str}' to {len(dates)} dates: {[d[1] for d in dates]}")
        return dates

    def get_blockouts_for_date_range(self, date_str: str) -> dict:
        """
        Get blockouts for a date range (like "first week of February 2026").

        OPTIMIZED: Instead of calling get_blockouts_for_date for each day (which would
        make N*M API calls), this fetches each person's blockouts ONCE and checks
        locally if any blockout covers any date in the range.

        Args:
            date_str: Date range string.

        Returns:
            Dict with consolidated blockout information for all dates in range.
        """
        import time

        dates = self.expand_week_reference(date_str)

        if not dates:
            # Not a date range, use single date check
            return None

        result = {
            'date_range': date_str,
            'dates_checked': [],
            'all_blocked_people': {},  # name -> list of blocked dates
            'total_people_checked': 0,
            'api_calls_made': 0,
            'cache_hits': 0
        }

        # Extract date objects for local comparison
        date_objects = [(d[0], d[1]) for d in dates]
        for date_obj, formatted in date_objects:
            result['dates_checked'].append({'date': formatted, 'blocked_count': 0})

        # Step 1: Get team members ONCE (use the first date to find the relevant plan)
        first_date_str = date_objects[0][1].split(' (')[0]  # e.g., "February 1, 2026"
        plan = self.find_plan_by_date(first_date_str)

        team_member_ids = set()
        team_member_names = {}

        if plan and plan.get('plan_id'):
            plan_id = plan.get('plan_id')
            service_type_id = plan.get('service_type_id')

            if service_type_id and plan_id:
                # Fetch all team members with pagination
                offset = 0
                per_page = 100

                while True:
                    team_result = self._get(
                        f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members",
                        params={'include': 'person', 'per_page': per_page, 'offset': offset}
                    )
                    result['api_calls_made'] += 1

                    members_data = team_result.get('data', [])
                    if not members_data:
                        break

                    for member in members_data:
                        attrs = member.get('attributes', {})
                        name = attrs.get('name', '')
                        person_id = None
                        relationships = member.get('relationships', {})
                        person_data = relationships.get('person', {}).get('data', {})
                        if person_data:
                            person_id = person_data.get('id')

                        if person_id:
                            team_member_ids.add(person_id)
                            team_member_names[person_id] = name

                    if len(members_data) < per_page:
                        break
                    offset += per_page

        result['total_people_checked'] = len(team_member_ids)
        logger.info(f"Date range check: Found {len(team_member_ids)} team members to check")

        # Step 2: Fetch blockouts for each person ONCE (with rate limiting and caching)
        api_call_count = 0
        for person_id in team_member_ids:
            person_name = team_member_names.get(person_id, 'Unknown')

            # Check cache first
            cache_key = f"{PCO_BLOCKOUTS_CACHE_KEY}_{person_id}"
            cached_blockouts = cache.get(cache_key)

            if cached_blockouts is not None:
                result['cache_hits'] += 1
                blockouts = cached_blockouts
            else:
                # Rate limiting: add delay to avoid 429 errors
                api_call_count += 1
                if api_call_count > 0 and api_call_count % PCO_BLOCKOUT_RATE_LIMIT_CALLS == 0:
                    time.sleep(PCO_BLOCKOUT_RATE_LIMIT_DELAY)

                try:
                    blockouts_result = self._get(
                        f"/services/v2/people/{person_id}/blockouts",
                        params={'per_page': 50},
                        retry_on_429=True
                    )
                    result['api_calls_made'] += 1
                    blockouts = blockouts_result.get('data', [])
                    cache.set(cache_key, blockouts, PCO_BLOCKOUTS_CACHE_TIMEOUT)
                except Exception as e:
                    logger.warning(f"Error fetching blockouts for {person_name}: {e}")
                    continue

            # Step 3: Check locally if any blockout covers any date in the range
            for date_obj, formatted_date in date_objects:
                for blockout in blockouts:
                    b_attrs = blockout.get('attributes', {})
                    starts_at = b_attrs.get('starts_at')
                    ends_at = b_attrs.get('ends_at')

                    if self._date_in_blockout_range(date_obj, starts_at, ends_at):
                        # This person is blocked on this date
                        if person_name not in result['all_blocked_people']:
                            result['all_blocked_people'][person_name] = []
                        if formatted_date not in result['all_blocked_people'][person_name]:
                            result['all_blocked_people'][person_name].append(formatted_date)

                        # Update the blocked count for this date
                        for date_info in result['dates_checked']:
                            if date_info['date'] == formatted_date:
                                date_info['blocked_count'] += 1
                                break
                        break  # Found a blockout for this date, move to next date

        logger.info(
            f"Date range check for '{date_str}': {len(result['all_blocked_people'])} unique people blocked, "
            f"{result['api_calls_made']} API calls, {result['cache_hits']} cache hits"
        )

        return result
