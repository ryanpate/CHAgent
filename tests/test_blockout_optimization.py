"""
Tests for PCO blockout optimization.

These tests verify the optimization strategies:
1. Status 'B' detection (no extra API calls)
2. Caching of blockouts
3. API call tracking
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from django.core.cache import cache


class TestDateInBlockoutRange:
    """Tests for the _date_in_blockout_range helper method."""

    @pytest.fixture
    def api(self):
        """Create a mock API instance."""
        with patch('core.planning_center.PlanningCenterServicesAPI._get'):
            from core.planning_center import PlanningCenterServicesAPI
            return PlanningCenterServicesAPI()

    def test_date_within_range(self, api):
        """Date within blockout range should return True."""
        check_date = date(2025, 12, 15)
        starts_at = "2025-12-14T00:00:00Z"
        ends_at = "2025-12-16T23:59:59Z"

        assert api._date_in_blockout_range(check_date, starts_at, ends_at) is True

    def test_date_on_start(self, api):
        """Date on start of blockout should return True."""
        check_date = date(2025, 12, 14)
        starts_at = "2025-12-14T00:00:00Z"
        ends_at = "2025-12-20T23:59:59Z"

        assert api._date_in_blockout_range(check_date, starts_at, ends_at) is True

    def test_date_on_end(self, api):
        """Date on end of blockout should return True."""
        check_date = date(2025, 12, 20)
        starts_at = "2025-12-14T00:00:00Z"
        ends_at = "2025-12-20T23:59:59Z"

        assert api._date_in_blockout_range(check_date, starts_at, ends_at) is True

    def test_date_before_range(self, api):
        """Date before blockout range should return False."""
        check_date = date(2025, 12, 10)
        starts_at = "2025-12-14T00:00:00Z"
        ends_at = "2025-12-20T23:59:59Z"

        assert api._date_in_blockout_range(check_date, starts_at, ends_at) is False

    def test_date_after_range(self, api):
        """Date after blockout range should return False."""
        check_date = date(2025, 12, 25)
        starts_at = "2025-12-14T00:00:00Z"
        ends_at = "2025-12-20T23:59:59Z"

        assert api._date_in_blockout_range(check_date, starts_at, ends_at) is False

    def test_single_day_blockout(self, api):
        """Single day blockout (no ends_at) should work."""
        check_date = date(2025, 12, 14)
        starts_at = "2025-12-14T00:00:00Z"
        ends_at = None

        assert api._date_in_blockout_range(check_date, starts_at, ends_at) is True

    def test_single_day_blockout_different_day(self, api):
        """Single day blockout on different day should return False."""
        check_date = date(2025, 12, 15)
        starts_at = "2025-12-14T00:00:00Z"
        ends_at = None

        assert api._date_in_blockout_range(check_date, starts_at, ends_at) is False

    def test_missing_starts_at(self, api):
        """Missing starts_at should return False."""
        check_date = date(2025, 12, 14)

        assert api._date_in_blockout_range(check_date, None, None) is False
        assert api._date_in_blockout_range(check_date, "", None) is False

    def test_invalid_date_format(self, api):
        """Invalid date format should return False (not raise)."""
        check_date = date(2025, 12, 14)

        assert api._date_in_blockout_range(check_date, "not-a-date", None) is False


class TestGetCachedPersonBlockouts:
    """Tests for the _get_cached_person_blockouts helper method."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before each test."""
        cache.clear()
        yield
        cache.clear()

    @pytest.fixture
    def mock_blockouts_data(self):
        """Sample blockouts response data."""
        return {
            'data': [
                {
                    'id': '123',
                    'type': 'Blockout',
                    'attributes': {
                        'reason': 'Vacation',
                        'starts_at': '2025-12-14T00:00:00Z',
                        'ends_at': '2025-12-21T00:00:00Z'
                    }
                }
            ]
        }

    def test_fetches_and_caches_on_miss(self, mock_blockouts_data):
        """Should fetch from API and cache on cache miss."""
        with patch('core.planning_center.PlanningCenterServicesAPI._get') as mock_get:
            mock_get.return_value = mock_blockouts_data

            from core.planning_center import PlanningCenterServicesAPI
            api = PlanningCenterServicesAPI()

            result = api._get_cached_person_blockouts('12345')

            # Should have called API
            mock_get.assert_called_once()
            assert len(result) == 1

            # Should be cached now
            cache_key = 'pco_person_blockouts_12345'
            cached = cache.get(cache_key)
            assert cached is not None
            assert len(cached) == 1

    def test_returns_cached_data_on_hit(self, mock_blockouts_data):
        """Should return cached data without API call on cache hit."""
        # Pre-populate cache
        cache_key = 'pco_person_blockouts_12345'
        cache.set(cache_key, mock_blockouts_data['data'], 1800)

        with patch('core.planning_center.PlanningCenterServicesAPI._get') as mock_get:
            from core.planning_center import PlanningCenterServicesAPI
            api = PlanningCenterServicesAPI()

            result = api._get_cached_person_blockouts('12345')

            # Should NOT have called API
            mock_get.assert_not_called()
            assert len(result) == 1

    def test_handles_api_error_gracefully(self):
        """Should return empty list on API error."""
        with patch('core.planning_center.PlanningCenterServicesAPI._get') as mock_get:
            mock_get.side_effect = Exception("API Error")

            from core.planning_center import PlanningCenterServicesAPI
            api = PlanningCenterServicesAPI()

            result = api._get_cached_person_blockouts('12345')

            assert result == []


class TestGetBlockoutsForDateOptimization:
    """Tests for the optimized get_blockouts_for_date method."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before each test."""
        cache.clear()
        yield
        cache.clear()

    @pytest.fixture
    def mock_plan_response(self):
        """Mock response for find_plan_by_date."""
        return {
            'plan_id': '123',
            'service_type_id': '456',
            'date': '2025-12-14'
        }

    @pytest.fixture
    def mock_team_members_with_blocked(self):
        """Mock team members response with status='B' for blocked."""
        return {
            'data': [
                {
                    'id': 'tm1',
                    'type': 'TeamMember',
                    'attributes': {
                        'name': 'John Smith',
                        'status': 'C'  # Confirmed
                    },
                    'relationships': {
                        'person': {'data': {'id': '100', 'type': 'Person'}}
                    }
                },
                {
                    'id': 'tm2',
                    'type': 'TeamMember',
                    'attributes': {
                        'name': 'Sarah Johnson',
                        'status': 'B'  # Blocked - optimization should catch this!
                    },
                    'relationships': {
                        'person': {'data': {'id': '200', 'type': 'Person'}}
                    }
                },
                {
                    'id': 'tm3',
                    'type': 'TeamMember',
                    'attributes': {
                        'name': 'Mike Wilson',
                        'status': 'U'  # Unconfirmed
                    },
                    'relationships': {
                        'person': {'data': {'id': '300', 'type': 'Person'}}
                    }
                }
            ],
            'included': []
        }

    def test_detects_blocked_status_without_api_call(
        self, mock_plan_response, mock_team_members_with_blocked
    ):
        """Should detect status='B' and not make extra API call for that person."""
        with patch('core.planning_center.PlanningCenterServicesAPI._get') as mock_get:
            with patch('core.planning_center.PlanningCenterServicesAPI.find_plan_by_date') as mock_find_plan:
                mock_find_plan.return_value = mock_plan_response

                # First call is team_members, rest are blockouts
                mock_get.side_effect = [
                    mock_team_members_with_blocked,  # team_members
                    {'data': []},  # blockouts for John (100)
                    {'data': []},  # blockouts for Mike (300)
                ]

                from core.planning_center import PlanningCenterServicesAPI
                api = PlanningCenterServicesAPI()

                result = api.get_blockouts_for_date('December 14, 2025')

                # Sarah should be in blocked_people (from status B)
                blocked_names = [p['name'] for p in result['blocked_people']]
                assert 'Sarah Johnson' in blocked_names

                # Verify we only made 3 API calls:
                # 1 for team_members, 2 for individual blockouts (John and Mike)
                # Sarah was skipped because status='B'
                assert result['api_calls_made'] == 3

    def test_uses_cache_for_blockouts(self, mock_plan_response, mock_team_members_with_blocked):
        """Should use cached blockouts and report cache hits."""
        # Pre-populate cache for John (person_id=100)
        cache_key = 'pco_person_blockouts_100'
        cache.set(cache_key, [], 1800)  # Empty blockouts

        with patch('core.planning_center.PlanningCenterServicesAPI._get') as mock_get:
            with patch('core.planning_center.PlanningCenterServicesAPI.find_plan_by_date') as mock_find_plan:
                mock_find_plan.return_value = mock_plan_response

                mock_get.side_effect = [
                    mock_team_members_with_blocked,  # team_members
                    {'data': []},  # blockouts for Mike (300) only
                ]

                from core.planning_center import PlanningCenterServicesAPI
                api = PlanningCenterServicesAPI()

                result = api.get_blockouts_for_date('December 14, 2025')

                # Should have 1 cache hit (John)
                assert result['cache_hits'] == 1

                # Should have only 2 API calls:
                # 1 for team_members, 1 for Mike's blockouts
                # John was from cache, Sarah was from status
                assert result['api_calls_made'] == 2

    def test_returns_metrics(self, mock_plan_response, mock_team_members_with_blocked):
        """Should return metrics for monitoring optimization."""
        with patch('core.planning_center.PlanningCenterServicesAPI._get') as mock_get:
            with patch('core.planning_center.PlanningCenterServicesAPI.find_plan_by_date') as mock_find_plan:
                mock_find_plan.return_value = mock_plan_response
                mock_get.side_effect = [
                    mock_team_members_with_blocked,
                    {'data': []},
                    {'data': []},
                ]

                from core.planning_center import PlanningCenterServicesAPI
                api = PlanningCenterServicesAPI()

                result = api.get_blockouts_for_date('December 14, 2025')

                # Check all expected keys are present
                assert 'date' in result
                assert 'date_parsed' in result
                assert 'blocked_people' in result
                assert 'total_people_checked' in result
                assert 'api_calls_made' in result
                assert 'cache_hits' in result

    def test_handles_invalid_date(self):
        """Should handle invalid date gracefully."""
        with patch('core.planning_center.PlanningCenterServicesAPI._get'):
            from core.planning_center import PlanningCenterServicesAPI
            api = PlanningCenterServicesAPI()

            # Patch the date parser to return None
            with patch.object(api, '_parse_date_string', return_value=None):
                result = api.get_blockouts_for_date('not-a-valid-date')

                assert result['blocked_people'] == []
                assert result['api_calls_made'] == 0

    def test_finds_blockouts_in_date_range(self, mock_plan_response):
        """Should correctly identify people with blockouts covering the date."""
        team_members = {
            'data': [
                {
                    'id': 'tm1',
                    'type': 'TeamMember',
                    'attributes': {'name': 'John Smith', 'status': 'C'},
                    'relationships': {'person': {'data': {'id': '100', 'type': 'Person'}}}
                }
            ],
            'included': []
        }

        blockouts_response = {
            'data': [
                {
                    'id': 'b1',
                    'type': 'Blockout',
                    'attributes': {
                        'reason': 'Family Trip',
                        'starts_at': '2025-12-10T00:00:00Z',
                        'ends_at': '2025-12-20T00:00:00Z'
                    }
                }
            ]
        }

        with patch('core.planning_center.PlanningCenterServicesAPI._get') as mock_get:
            with patch('core.planning_center.PlanningCenterServicesAPI.find_plan_by_date') as mock_find_plan:
                mock_find_plan.return_value = mock_plan_response
                mock_get.side_effect = [team_members, blockouts_response]

                from core.planning_center import PlanningCenterServicesAPI
                api = PlanningCenterServicesAPI()

                result = api.get_blockouts_for_date('December 14, 2025')

                assert len(result['blocked_people']) == 1
                assert result['blocked_people'][0]['name'] == 'John Smith'
                assert result['blocked_people'][0]['reason'] == 'Family Trip'

    def test_paginates_through_all_team_members(self, mock_plan_response):
        """Should fetch all team members across multiple pages (more than 100)."""
        # Create page 1 with 100 members
        page1_members = []
        for i in range(100):
            page1_members.append({
                'id': f'tm{i}',
                'type': 'TeamMember',
                'attributes': {'name': f'Person {i}', 'status': 'C'},
                'relationships': {'person': {'data': {'id': str(i), 'type': 'Person'}}}
            })

        # Create page 2 with 50 more members
        page2_members = []
        for i in range(100, 150):
            page2_members.append({
                'id': f'tm{i}',
                'type': 'TeamMember',
                'attributes': {'name': f'Person {i}', 'status': 'C'},
                'relationships': {'person': {'data': {'id': str(i), 'type': 'Person'}}}
            })

        page1_response = {'data': page1_members, 'included': []}
        page2_response = {'data': page2_members, 'included': []}
        empty_response = {'data': []}

        with patch('core.planning_center.PlanningCenterServicesAPI._get') as mock_get:
            with patch('core.planning_center.PlanningCenterServicesAPI.find_plan_by_date') as mock_find_plan:
                mock_find_plan.return_value = mock_plan_response

                # Responses: page1, page2, then empty blockouts for all 150 people
                blockout_responses = [empty_response] * 150
                mock_get.side_effect = [page1_response, page2_response] + blockout_responses

                from core.planning_center import PlanningCenterServicesAPI
                api = PlanningCenterServicesAPI()

                result = api.get_blockouts_for_date('December 14, 2025')

                # Should have checked all 150 team members
                assert result['total_people_checked'] == 150

                # API calls: 2 for pagination + 150 for individual blockouts
                assert result['api_calls_made'] == 152


class TestBlockoutCacheTimeout:
    """Tests for cache timeout configuration."""

    def test_cache_constants_defined(self):
        """Cache constants should be properly defined."""
        from core.planning_center import PCO_BLOCKOUTS_CACHE_KEY, PCO_BLOCKOUTS_CACHE_TIMEOUT

        assert PCO_BLOCKOUTS_CACHE_KEY == 'pco_person_blockouts'
        assert PCO_BLOCKOUTS_CACHE_TIMEOUT == 1800  # 30 minutes
