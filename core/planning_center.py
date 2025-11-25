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

# Cache key for PCO people list
PCO_PEOPLE_CACHE_KEY = 'pco_people_list'
PCO_CACHE_TIMEOUT = 3600  # 1 hour


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

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated GET request to Planning Center API."""
        if not self.is_configured:
            logger.warning("Planning Center not configured")
            return {}

        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = requests.get(
                url,
                auth=(self.app_id, self.secret),
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Planning Center API error: {e}")
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
            'last_served': None
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
            services_person_id = services_person.get('id')

            # Get team positions (what teams they're on)
            # Note: This endpoint may return 404 if person has no team assignments
            team_positions = self._get(f"/services/v2/people/{services_person_id}/team_positions")
            if team_positions:
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
            # Note: This endpoint may return 404 if person has no schedule history
            schedules_result = self._get(
                f"/services/v2/people/{services_person_id}/schedules",
                params={'order': '-sort_date', 'per_page': 10}
            )
            if schedules_result:
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

                    # Track last served date (confirmed schedules only)
                    if sched_attrs.get('status') == 'C' and sort_date:  # C = Confirmed
                        if not details['last_served'] or sort_date > details['last_served']:
                            details['last_served'] = sort_date

        return details

    def _find_services_person(self, people_person_id: str) -> Optional[dict]:
        """
        Find the Services person record that matches a People person ID.

        PCO has separate People and Services databases. This finds the Services
        person by searching for their name.

        Args:
            people_person_id: The person ID from the People API.

        Returns:
            Services person record or None.
        """
        # Get the person's name from People API
        person = self.get_person_by_id(people_person_id)
        if not person:
            return None

        attrs = person.get('attributes', {})
        first_name = attrs.get('first_name', '')
        last_name = attrs.get('last_name', '')

        if not first_name or not last_name:
            return None

        # Search in Services for this person
        # Services API allows searching by name
        services_people = self._get(
            "/services/v2/people",
            params={'where[first_name]': first_name, 'where[last_name]': last_name}
        )

        data = services_people.get('data', [])
        if data:
            return data[0]  # Return first match

        return None

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
