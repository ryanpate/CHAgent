"""
Volunteer matching service for linking interaction mentions to PCO volunteers.

This module handles:
- Finding volunteers by name in local DB and PCO
- Fuzzy matching for uncertain matches
- Creating pending matches for user confirmation
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from django.db.models import Q

from .models import Volunteer
from .planning_center import PlanningCenterAPI, normalize_name, calculate_name_similarity

logger = logging.getLogger(__name__)

# Thresholds for match confidence
EXACT_MATCH_THRESHOLD = 0.95  # Auto-link without confirmation
LIKELY_MATCH_THRESHOLD = 0.75  # Suggest but ask for confirmation
MIN_MATCH_THRESHOLD = 0.6  # Show as possible match


class MatchType(Enum):
    """Types of volunteer matches."""
    EXACT = "exact"  # Perfect match, auto-link
    LIKELY = "likely"  # High confidence, needs confirmation
    POSSIBLE = "possible"  # Lower confidence, offer as option
    NONE = "none"  # No match found


@dataclass
class VolunteerMatch:
    """Represents a potential volunteer match."""
    name: str  # Original extracted name
    match_type: MatchType
    volunteer: Optional[Volunteer] = None  # Matched local volunteer
    pco_id: Optional[str] = None  # PCO person ID if from PCO
    pco_name: Optional[str] = None  # Name from PCO
    score: float = 0.0  # Match confidence score
    alternatives: list = None  # Other possible matches

    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


class VolunteerMatcher:
    """
    Service for matching mentioned names to volunteers.

    Checks in order:
    1. Local database exact match
    2. Local database fuzzy match
    3. PCO exact match
    4. PCO fuzzy match
    """

    def __init__(self):
        self.pco_api = PlanningCenterAPI()

    def find_volunteer(self, name: str) -> VolunteerMatch:
        """
        Find the best match for a volunteer name.

        Args:
            name: Name to search for.

        Returns:
            VolunteerMatch with results.
        """
        if not name or not name.strip():
            return VolunteerMatch(name=name, match_type=MatchType.NONE)

        normalized = normalize_name(name)

        # Step 1: Check local database for exact match
        local_exact = self._find_local_exact(normalized)
        if local_exact:
            return VolunteerMatch(
                name=name,
                match_type=MatchType.EXACT,
                volunteer=local_exact,
                pco_id=local_exact.planning_center_id,
                score=1.0
            )

        # Step 2: Check PCO for exact match
        if self.pco_api.is_configured:
            pco_exact = self._find_pco_exact(name)
            if pco_exact:
                # Check if we have this PCO person locally
                local_by_pco = Volunteer.objects.filter(
                    planning_center_id=pco_exact['pco_id']
                ).first()

                if local_by_pco:
                    return VolunteerMatch(
                        name=name,
                        match_type=MatchType.EXACT,
                        volunteer=local_by_pco,
                        pco_id=pco_exact['pco_id'],
                        pco_name=pco_exact['name'],
                        score=pco_exact['score']
                    )
                else:
                    # Have PCO match but not local - exact enough to auto-create
                    return VolunteerMatch(
                        name=name,
                        match_type=MatchType.EXACT,
                        volunteer=None,
                        pco_id=pco_exact['pco_id'],
                        pco_name=pco_exact['name'],
                        score=pco_exact['score']
                    )

        # Step 3: Fuzzy match against local database
        local_fuzzy = self._find_local_fuzzy(normalized)

        # Step 4: Fuzzy match against PCO
        pco_fuzzy = []
        if self.pco_api.is_configured:
            pco_fuzzy = self._find_pco_fuzzy(name)

        # Combine and rank all matches
        all_matches = self._combine_matches(local_fuzzy, pco_fuzzy)

        if not all_matches:
            return VolunteerMatch(name=name, match_type=MatchType.NONE)

        # Get best match
        best = all_matches[0]
        alternatives = all_matches[1:5]  # Top 4 alternatives

        if best['score'] >= LIKELY_MATCH_THRESHOLD:
            match_type = MatchType.LIKELY
        elif best['score'] >= MIN_MATCH_THRESHOLD:
            match_type = MatchType.POSSIBLE
        else:
            return VolunteerMatch(
                name=name,
                match_type=MatchType.NONE,
                alternatives=[self._match_to_dict(m) for m in alternatives]
            )

        return VolunteerMatch(
            name=name,
            match_type=match_type,
            volunteer=best.get('volunteer'),
            pco_id=best.get('pco_id'),
            pco_name=best.get('pco_name'),
            score=best['score'],
            alternatives=[self._match_to_dict(m) for m in alternatives]
        )

    def _find_local_exact(self, normalized_name: str) -> Optional[Volunteer]:
        """Find exact match in local database."""
        return Volunteer.objects.filter(
            normalized_name=normalized_name
        ).first()

    def _find_local_fuzzy(self, normalized_name: str) -> list:
        """Find fuzzy matches in local database."""
        matches = []

        # Get all volunteers and score them
        for volunteer in Volunteer.objects.all():
            score = calculate_name_similarity(normalized_name, volunteer.normalized_name)
            if score >= MIN_MATCH_THRESHOLD:
                matches.append({
                    'volunteer': volunteer,
                    'pco_id': volunteer.planning_center_id,
                    'pco_name': None,
                    'name': volunteer.name,
                    'score': score,
                    'source': 'local'
                })

        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches[:10]

    def _find_pco_exact(self, name: str) -> Optional[dict]:
        """Find exact match in PCO."""
        matches = self.pco_api.find_matches(name, threshold=EXACT_MATCH_THRESHOLD)
        if matches and matches[0]['score'] >= EXACT_MATCH_THRESHOLD:
            return matches[0]
        return None

    def _find_pco_fuzzy(self, name: str) -> list:
        """Find fuzzy matches in PCO."""
        pco_matches = self.pco_api.find_matches(name, threshold=MIN_MATCH_THRESHOLD)

        results = []
        for m in pco_matches:
            # Check if we have this PCO person locally
            local_vol = Volunteer.objects.filter(
                planning_center_id=m['pco_id']
            ).first()

            results.append({
                'volunteer': local_vol,
                'pco_id': m['pco_id'],
                'pco_name': m['name'],
                'name': local_vol.name if local_vol else m['name'],
                'score': m['score'],
                'source': 'pco'
            })

        return results

    def _combine_matches(self, local_matches: list, pco_matches: list) -> list:
        """Combine and deduplicate matches from local and PCO."""
        combined = {}

        # Add local matches
        for m in local_matches:
            key = f"local_{m['volunteer'].id}" if m['volunteer'] else m['name']
            combined[key] = m

        # Add/merge PCO matches
        for m in pco_matches:
            pco_key = f"pco_{m['pco_id']}"
            local_key = f"local_{m['volunteer'].id}" if m['volunteer'] else None

            # If we already have this volunteer from local, keep higher score
            if local_key and local_key in combined:
                if m['score'] > combined[local_key]['score']:
                    combined[local_key]['score'] = m['score']
                    combined[local_key]['pco_id'] = m['pco_id']
                    combined[local_key]['pco_name'] = m['pco_name']
            elif pco_key not in combined:
                combined[pco_key] = m

        # Sort by score
        result = list(combined.values())
        result.sort(key=lambda x: x['score'], reverse=True)
        return result

    def _match_to_dict(self, match: dict) -> dict:
        """Convert internal match dict to serializable format."""
        return {
            'name': match.get('pco_name') or match.get('name'),
            'volunteer_id': match['volunteer'].id if match.get('volunteer') else None,
            'pco_id': match.get('pco_id'),
            'score': match['score'],
            'source': match.get('source', 'unknown')
        }

    def get_or_create_volunteer(
        self,
        name: str,
        pco_id: Optional[str] = None,
        team: str = ""
    ) -> Volunteer:
        """
        Get an existing volunteer or create a new one.

        If pco_id is provided, will try to match by PCO ID first.

        Args:
            name: Volunteer name.
            pco_id: Optional Planning Center ID.
            team: Optional team name.

        Returns:
            Volunteer instance (existing or newly created).
        """
        normalized = normalize_name(name)

        # Try to find by PCO ID first
        if pco_id:
            volunteer = Volunteer.objects.filter(planning_center_id=pco_id).first()
            if volunteer:
                # Update name if different
                if volunteer.name.lower() != name.lower():
                    logger.info(f"Updating volunteer name from '{volunteer.name}' to '{name}'")
                    volunteer.name = name
                    volunteer.normalized_name = normalized
                    volunteer.save()
                return volunteer

        # Try to find by normalized name
        volunteer = Volunteer.objects.filter(normalized_name=normalized).first()
        if volunteer:
            # Update PCO ID if we have it and they don't
            if pco_id and not volunteer.planning_center_id:
                volunteer.planning_center_id = pco_id
                volunteer.save()
            return volunteer

        # Create new volunteer
        volunteer = Volunteer.objects.create(
            name=name,
            normalized_name=normalized,
            planning_center_id=pco_id,
            team=team
        )
        logger.info(f"Created new volunteer: {name} (PCO ID: {pco_id})")
        return volunteer


def match_volunteers_for_interaction(extracted_names: list) -> dict:
    """
    Match a list of extracted volunteer names.

    Args:
        extracted_names: List of dicts with 'name' and optional 'team'.

    Returns:
        Dict with:
        - 'confirmed': List of Volunteer objects that were auto-linked
        - 'pending': List of VolunteerMatch objects needing confirmation
        - 'unmatched': List of names with no matches found
    """
    matcher = VolunteerMatcher()
    result = {
        'confirmed': [],
        'pending': [],
        'unmatched': []
    }

    for vol_data in extracted_names:
        name = vol_data.get('name', '').strip()
        team = vol_data.get('team', '')

        if not name:
            continue

        match = matcher.find_volunteer(name)

        if match.match_type == MatchType.EXACT:
            # Auto-link this volunteer
            if match.volunteer:
                result['confirmed'].append(match.volunteer)
            else:
                # Create from PCO data
                volunteer = matcher.get_or_create_volunteer(
                    name=match.pco_name or name,
                    pco_id=match.pco_id,
                    team=team
                )
                result['confirmed'].append(volunteer)

        elif match.match_type in (MatchType.LIKELY, MatchType.POSSIBLE):
            # Needs user confirmation
            result['pending'].append(match)

        else:
            # No match found
            result['unmatched'].append({
                'name': name,
                'team': team
            })

    return result
