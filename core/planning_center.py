"""
Planning Center Integration for syncing volunteers.
Optional feature - requires PLANNING_CENTER_APP_ID and PLANNING_CENTER_SECRET.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


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

    def get_people(self, team_id: str = None) -> dict:
        """
        Fetch people from Planning Center.

        Args:
            team_id: Optional team ID to filter by.

        Returns:
            API response as dict.
        """
        if team_id:
            endpoint = f"/services/v2/teams/{team_id}/people"
        else:
            endpoint = "/people/v2/people"

        return self._get(endpoint)

    def get_teams(self) -> dict:
        """Fetch all teams from Planning Center Services."""
        return self._get("/services/v2/teams")

    def sync_volunteers(self) -> dict:
        """
        Sync Planning Center people with local Volunteer records.

        Returns:
            Dict with counts of created and updated volunteers.
        """
        from .models import Volunteer

        if not self.is_configured:
            return {'error': 'Planning Center not configured'}

        data = self.get_people()
        created_count = 0
        updated_count = 0

        for person in data.get('data', []):
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


def sync_planning_center():
    """Convenience function to sync Planning Center data."""
    api = PlanningCenterAPI()
    return api.sync_volunteers()
