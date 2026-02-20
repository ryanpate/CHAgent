"""
Phase 2: Aria Response Formatting Tests

Tests the formatting functions that convert API data into readable responses.
These tests use mock data to verify output structure without external API calls.
"""
import pytest
from unittest.mock import MagicMock, patch

# Import formatting functions from agent.py
from core.agent import (
    format_plan_details,
    format_team_schedule,
    format_person_blockouts,
    format_date_blockouts,
    format_availability_check,
    format_team_availability,
    format_song_details,
    format_song_suggestions,
    format_song_usage_history,
    format_pco_suggestions,
    format_first_name_matches,
    format_disambiguation_prompt,
    format_pco_details,
)


# =============================================================================
# MOCK DATA FIXTURES
# =============================================================================

@pytest.fixture
def mock_plan_with_team():
    """Complete service plan with team members and songs."""
    return {
        'id': '12345',
        'service_type_name': 'Cherry Hills Morning Main',
        'dates': 'December 15, 2024',
        'sort_date': '2024-12-15',
        'title': 'Third Sunday of Advent',
        'series_title': 'Advent 2024',
        'team_members': [
            {
                'name': 'John Smith',
                'team_name': 'Vocals',
                'position': 'Worship Leader',
                'status': 'Confirmed'
            },
            {
                'name': 'Sarah Johnson',
                'team_name': 'Vocals',
                'position': 'Alto',
                'status': 'Confirmed'
            },
            {
                'name': 'Mike Chen',
                'team_name': 'Band',
                'position': 'Keys',
                'status': 'Confirmed'
            },
            {
                'name': 'Lisa Williams',
                'team_name': 'Band',
                'position': 'Acoustic Guitar',
                'status': 'Unconfirmed'
            },
            {
                'name': 'David Brown',
                'team_name': 'Tech',
                'position': 'Sound',
                'status': 'Confirmed'
            },
        ],
        'songs': [
            {'title': 'O Come All Ye Faithful', 'key': 'G', 'author': 'Traditional'},
            {'title': 'Way Maker', 'key': 'E', 'author': 'Sinach'},
            {'title': 'Goodness of God', 'key': 'A', 'author': 'Bethel Music'},
        ]
    }


@pytest.fixture
def mock_plan_minimal():
    """Minimal plan with just date."""
    return {
        'dates': 'December 22, 2024',
        'service_type_name': 'Cherry Hills Morning Main',
    }


@pytest.fixture
def mock_plan_empty():
    """Empty/null plan."""
    return None


@pytest.fixture
def mock_person_details_full():
    """Complete person details from PCO."""
    return {
        'name': 'John Smith',
        'first_name': 'John',
        'last_name': 'Smith',
        'emails': [
            {'address': 'john.smith@email.com', 'primary': True, 'location': 'Home'},
            {'address': 'jsmith@work.com', 'primary': False, 'location': 'Work'},
        ],
        'phone_numbers': [
            {'number': '(555) 123-4567', 'carrier': 'mobile', 'primary': True},
            {'number': '(555) 987-6543', 'carrier': 'home', 'primary': False},
        ],
        'addresses': [
            {
                'street': '123 Main Street',
                'city': 'Highlands Ranch',
                'state': 'CO',
                'zip': '80129',
                'primary': True
            }
        ],
        'birthdate': '1985-03-15',
        'anniversary': '2010-06-20',
        'membership': 'Member',
        # Teams must be list of dicts with 'position' key
        'teams': [
            {'position': 'Worship Leader'},
            {'position': 'Audio Tech'},
        ],
    }


@pytest.fixture
def mock_person_details_minimal():
    """Person with minimal info (just name and email)."""
    return {
        'name': 'Jane Doe',
        'emails': [{'address': 'jane@example.com', 'primary': True}],
    }


@pytest.fixture
def mock_person_blockouts():
    """Person's blockout dates."""
    return {
        'found': True,  # Required flag to indicate person was found
        'person_name': 'Sarah Johnson',
        'blockouts': [
            {
                'starts_at': '2026-12-24',  # Use future date
                'ends_at': '2026-12-26',
                'reason': 'Christmas vacation'
            },
            {
                'starts_at': '2027-01-01',
                'ends_at': '2027-01-01',
                'reason': "New Year's Day"
            },
        ],
        'total_count': 2
    }


@pytest.fixture
def mock_date_blockouts():
    """Who is blocked out on a specific date."""
    return {
        'date': 'December 24, 2024',
        'blocked_people': [
            {'name': 'Sarah Johnson', 'reason': 'Christmas vacation'},
            {'name': 'Mike Chen', 'reason': 'Family travel'},
            {'name': 'Lisa Williams', 'reason': None},
        ],
        'total_blocked': 3
    }


@pytest.fixture
def mock_availability_check():
    """Single person availability check."""
    return {
        'found': True,  # Required flag
        'person_name': 'John Smith',
        'date': 'December 15, 2024',
        'available': True,  # Use 'available' not 'is_available'
    }


@pytest.fixture
def mock_availability_check_blocked():
    """Person who is blocked out."""
    return {
        'found': True,  # Required flag
        'person_name': 'Sarah Johnson',
        'date': 'December 24, 2024',
        'available': False,  # Use 'available' not 'is_available'
        'blockout': {
            'starts_at': '2024-12-24',
            'ends_at': '2024-12-26',
            'reason': 'Christmas vacation'
        }
    }


@pytest.fixture
def mock_team_availability():
    """Team availability for a date."""
    return {
        'date': 'December 15, 2024',
        'available': [
            {'name': 'John Smith', 'teams': ['Vocals']},
            {'name': 'Mike Chen', 'teams': ['Band']},
            {'name': 'David Brown', 'teams': ['Tech']},
        ],
        'blocked': [
            {'name': 'Sarah Johnson', 'reason': 'Prior commitment'},
        ],
        'unknown': [
            {'name': 'Lisa Williams'},
        ]
    }


@pytest.fixture
def mock_song_full():
    """Complete song details with attachments."""
    return {
        'title': 'Way Maker',
        'author': 'Sinach',
        'admin': 'Integrity Music',
        'ccli_number': '7115744',
        'copyright': '2016 Integrity Music',
        'key': 'E',
        'bpm': 68,
        'time_signature': '4/4',
        'themes': ['Worship', 'Praise', 'Faith'],
        'attachments': [
            {
                'filename': 'Way Maker - E.pdf',
                'file_type': 'chord_chart',
                'url': 'https://example.com/charts/waymaker-e.pdf'
            },
            {
                'filename': 'Way Maker - Lyrics.pdf',
                'file_type': 'lyrics',
                'url': 'https://example.com/lyrics/waymaker.pdf'
            },
        ],
        'lyrics': """Verse 1:
You are here, moving in our midst
I worship You, I worship You
You are here, working in this place
I worship You, I worship You

Chorus:
Way maker, miracle worker
Promise keeper, light in the darkness
My God, that is who You are"""
    }


@pytest.fixture
def mock_song_minimal():
    """Song with minimal info."""
    return {
        'title': 'Amazing Grace',
        'author': 'John Newton',
    }


@pytest.fixture
def mock_song_suggestions():
    """List of song suggestions for disambiguation."""
    return [
        {'title': 'Gratitude', 'author': 'Brandon Lake', 'id': '123'},
        {'title': 'Grateful', 'author': 'Elevation Worship', 'id': '456'},
        {'title': 'Gratitude (Live)', 'author': 'Brandon Lake', 'id': '789'},
    ]


@pytest.fixture
def mock_song_usage_history():
    """Song usage history."""
    return {
        'found': True,  # Required flag
        'song_title': 'Way Maker',
        'author': 'Sinach',
        'usages': [  # Use 'usages' not 'recent_plays'
            {'date': '2024-12-08', 'key': 'E', 'arrangement_name': 'Default'},
            {'date': '2024-11-24', 'key': 'E', 'arrangement_name': 'Default'},
            {'date': '2024-11-10', 'key': 'D', 'arrangement_name': 'Acoustic'},
        ],
    }


@pytest.fixture
def mock_pco_suggestions():
    """PCO person search suggestions."""
    return [
        {'name': 'John Smith', 'id': '111', 'email': 'john@example.com'},
        {'name': 'John Smithson', 'id': '222', 'email': 'johns@example.com'},
        {'name': 'Johnny Smith', 'id': '333', 'email': None},
    ]


@pytest.fixture
def mock_first_name_matches():
    """Multiple people with same first name."""
    return [
        {'name': 'Sarah Johnson', 'team': 'Vocals', 'id': '101'},
        {'name': 'Sarah Williams', 'team': 'Band', 'id': '102'},
        {'name': 'Sarah Chen', 'team': 'Tech', 'id': '103'},
    ]


# =============================================================================
# TEST: format_team_schedule
# =============================================================================

class TestFormatTeamSchedule:
    """Tests for team schedule formatting."""

    def test_formats_complete_schedule(self, mock_plan_with_team):
        """Test formatting a complete team schedule."""
        result = format_team_schedule(mock_plan_with_team)

        # Check header
        assert '[SERVICE TEAM SCHEDULE]' in result
        assert 'Cherry Hills Morning Main' in result
        assert 'December 15, 2024' in result

        # Check team groupings
        assert 'Vocals:' in result
        assert 'Band:' in result
        assert 'Tech:' in result

        # Check team members
        assert 'John Smith' in result
        assert 'Worship Leader' in result
        assert 'Sarah Johnson' in result
        assert 'Mike Chen' in result
        assert 'Keys' in result

        # Check status
        assert 'Confirmed' in result
        assert 'Unconfirmed' in result

        # Check songs included
        assert 'Song Set' in result
        assert 'O Come All Ye Faithful' in result
        assert 'Way Maker' in result

        # Check footer
        assert '[END SERVICE TEAM SCHEDULE]' in result

    def test_handles_empty_team(self, mock_plan_minimal):
        """Test formatting when no team members assigned."""
        result = format_team_schedule(mock_plan_minimal)

        assert '[SERVICE TEAM SCHEDULE]' in result
        assert 'No team members assigned' in result

    def test_handles_null_plan(self, mock_plan_empty):
        """Test handling null/empty plan."""
        result = format_team_schedule(mock_plan_empty)
        assert result == ""

    def test_groups_members_by_team(self, mock_plan_with_team):
        """Test that members are properly grouped by team."""
        result = format_team_schedule(mock_plan_with_team)

        # Check that all team names appear as headers
        assert 'Vocals:' in result
        assert 'Band:' in result
        assert 'Tech:' in result

        # All members should be present somewhere in the result
        assert 'John Smith' in result
        assert 'Sarah Johnson' in result
        assert 'Mike Chen' in result
        assert 'Lisa Williams' in result
        assert 'David Brown' in result


# =============================================================================
# TEST: format_pco_details
# =============================================================================

class TestFormatPcoDetails:
    """Tests for PCO person details formatting."""

    def test_formats_full_contact_info(self, mock_person_details_full):
        """Test formatting complete person details."""
        result = format_pco_details(mock_person_details_full)

        # Check name
        assert 'John Smith' in result

        # Check emails
        assert 'john.smith@email.com' in result

        # Check phone numbers
        assert '(555) 123-4567' in result

        # Check address
        assert '123 Main Street' in result
        assert 'Highlands Ranch' in result

        # Check team positions
        assert 'Worship Leader' in result

    def test_formats_email_query(self, mock_person_details_full):
        """Test formatting for email-specific query."""
        result = format_pco_details(mock_person_details_full, query_type='email')

        # Email should be present
        assert 'john.smith@email.com' in result

    def test_formats_phone_query(self, mock_person_details_full):
        """Test formatting for phone-specific query."""
        result = format_pco_details(mock_person_details_full, query_type='phone')

        # Phone should be present
        assert '(555) 123-4567' in result

    def test_handles_minimal_info(self, mock_person_details_minimal):
        """Test formatting with minimal person info."""
        result = format_pco_details(mock_person_details_minimal)

        assert 'Jane Doe' in result
        assert 'jane@example.com' in result

    def test_shows_pco_header(self, mock_person_details_full):
        """Test that PCO data header/footer are shown."""
        result = format_pco_details(mock_person_details_full)

        # Header includes person name
        assert '[PLANNING CENTER DATA for John Smith]' in result
        assert '[END PLANNING CENTER DATA]' in result


# =============================================================================
# TEST: format_person_blockouts
# =============================================================================

class TestFormatPersonBlockouts:
    """Tests for person blockout formatting."""

    def test_formats_blockouts_list(self, mock_person_blockouts):
        """Test formatting person's blockout dates."""
        result = format_person_blockouts(mock_person_blockouts)

        assert 'Sarah Johnson' in result
        assert '2026-12-24' in result or 'December 24' in result
        assert 'Christmas vacation' in result
        assert '2027-01-01' in result or 'January 1' in result

    def test_shows_blockout_count(self, mock_person_blockouts):
        """Test that blockout count is shown."""
        result = format_person_blockouts(mock_person_blockouts)

        # Should mention blockouts (function shows count in header)
        assert 'Blockout' in result

    def test_handles_empty_blockouts(self):
        """Test handling when person has no blockouts."""
        data = {
            'found': True,
            'person_name': 'John Smith',
            'blockouts': [],
            'total_count': 0
        }
        result = format_person_blockouts(data)

        assert 'John Smith' in result
        # Should indicate no blockouts
        assert 'no' in result.lower() or 'No blockouts' in result


# =============================================================================
# TEST: format_date_blockouts
# =============================================================================

class TestFormatDateBlockouts:
    """Tests for date-based blockout formatting."""

    def test_formats_blocked_people(self, mock_date_blockouts):
        """Test formatting who is blocked on a date."""
        result = format_date_blockouts(mock_date_blockouts)

        assert 'December 24, 2024' in result
        assert 'Sarah Johnson' in result
        assert 'Mike Chen' in result
        assert 'Lisa Williams' in result
        assert 'Christmas vacation' in result

    def test_shows_total_blocked(self, mock_date_blockouts):
        """Test that total blocked count is shown."""
        result = format_date_blockouts(mock_date_blockouts)

        # Should mention 3 people blocked
        assert '3' in result

    def test_handles_no_blockouts(self):
        """Test when no one is blocked."""
        data = {
            'date': 'December 15, 2024',
            'blocked_people': [],
            'total_blocked': 0
        }
        result = format_date_blockouts(data)

        assert 'December 15' in result
        # Should indicate no one blocked
        assert 'no' in result.lower() or '0' in result or 'none' in result.lower()


# =============================================================================
# TEST: format_availability_check
# =============================================================================

class TestFormatAvailabilityCheck:
    """Tests for individual availability check formatting."""

    def test_formats_available_person(self, mock_availability_check):
        """Test formatting when person is available."""
        result = format_availability_check(mock_availability_check)

        assert 'John Smith' in result
        assert 'December 15' in result
        assert 'available' in result.lower()

    def test_formats_blocked_person(self, mock_availability_check_blocked):
        """Test formatting when person is blocked."""
        result = format_availability_check(mock_availability_check_blocked)

        assert 'Sarah Johnson' in result
        assert 'December 24' in result
        assert 'Christmas vacation' in result
        # Should indicate not available or blocked
        assert 'blocked' in result.lower() or 'not available' in result.lower() or 'unavailable' in result.lower()


# =============================================================================
# TEST: format_team_availability
# =============================================================================

class TestFormatTeamAvailability:
    """Tests for team availability formatting."""

    def test_formats_team_availability(self, mock_team_availability):
        """Test formatting team availability for a date."""
        result = format_team_availability(mock_team_availability)

        assert 'December 15' in result

        # Available people
        assert 'John Smith' in result
        assert 'Mike Chen' in result
        assert 'David Brown' in result

        # Blocked people
        assert 'Sarah Johnson' in result
        assert 'Prior commitment' in result

    def test_groups_by_availability_status(self, mock_team_availability):
        """Test that people are grouped by availability."""
        result = format_team_availability(mock_team_availability)

        # Should have sections for available and blocked
        assert 'available' in result.lower()
        assert 'blocked' in result.lower() or 'unavailable' in result.lower()


# =============================================================================
# TEST: format_song_details
# =============================================================================

class TestFormatSongDetails:
    """Tests for song details formatting."""

    def test_formats_complete_song(self, mock_song_full):
        """Test formatting complete song details."""
        result = format_song_details(mock_song_full)

        assert 'Way Maker' in result
        assert 'Sinach' in result
        # CCLI number should be shown
        assert '7115744' in result

    def test_includes_attachments(self, mock_song_full):
        """Test that attachments are listed."""
        result = format_song_details(mock_song_full)

        # Should mention files/attachments
        assert 'pdf' in result.lower() or 'chart' in result.lower() or 'file' in result.lower()

    def test_shows_song_header(self, mock_song_full):
        """Test that song data header is shown."""
        result = format_song_details(mock_song_full)

        assert '[SONG DATA]' in result
        assert '[END SONG DATA]' in result

    def test_handles_minimal_song(self, mock_song_minimal):
        """Test formatting song with minimal info."""
        result = format_song_details(mock_song_minimal)

        assert 'Amazing Grace' in result
        assert 'John Newton' in result


# =============================================================================
# TEST: format_song_suggestions
# =============================================================================

class TestFormatSongSuggestions:
    """Tests for song suggestion formatting."""

    def test_formats_multiple_suggestions(self, mock_song_suggestions):
        """Test formatting multiple song suggestions."""
        result = format_song_suggestions('Gratitude', mock_song_suggestions)

        # Should list all suggestions
        assert 'Gratitude' in result
        assert 'Brandon Lake' in result
        assert 'Grateful' in result
        assert 'Elevation Worship' in result

    def test_indicates_disambiguation_needed(self, mock_song_suggestions):
        """Test that result indicates user should clarify."""
        result = format_song_suggestions('Gratitude', mock_song_suggestions)

        # Should ask which one or indicate multiple matches
        assert 'which' in result.lower() or 'multiple' in result.lower() or 'found' in result.lower()

    def test_handles_empty_suggestions(self):
        """Test handling no suggestions."""
        result = format_song_suggestions('NonexistentSong', [])

        # Should indicate no results
        assert 'no' in result.lower() or 'not found' in result.lower() or "couldn't find" in result.lower()


# =============================================================================
# TEST: format_song_usage_history
# =============================================================================

class TestFormatSongUsageHistory:
    """Tests for song usage history formatting."""

    def test_formats_usage_history(self, mock_song_usage_history):
        """Test formatting song usage history."""
        result = format_song_usage_history(mock_song_usage_history)

        assert 'Way Maker' in result
        assert 'Sinach' in result  # author
        assert '2024-12-08' in result  # most recent date

    def test_shows_recent_plays(self, mock_song_usage_history):
        """Test that recent plays are listed."""
        result = format_song_usage_history(mock_song_usage_history)

        # Should show recent dates
        assert '2024-12-08' in result
        assert '2024-11-24' in result

    def test_handles_never_played(self):
        """Test handling song never played."""
        data = {
            'found': True,
            'song_title': 'New Song',
            'usages': []
        }
        result = format_song_usage_history(data)

        assert 'New Song' in result
        # Should indicate no recent history
        assert 'No recent' in result or 'no' in result.lower()


# =============================================================================
# TEST: format_pco_suggestions
# =============================================================================

class TestFormatPcoSuggestions:
    """Tests for PCO person suggestion formatting."""

    def test_formats_person_suggestions(self, mock_pco_suggestions):
        """Test formatting person search suggestions."""
        result = format_pco_suggestions('John', mock_pco_suggestions)

        assert 'John Smith' in result
        assert 'John Smithson' in result
        assert 'Johnny Smith' in result

    def test_shows_numbered_suggestions(self, mock_pco_suggestions):
        """Test that suggestions are numbered."""
        result = format_pco_suggestions('John', mock_pco_suggestions)

        # Should show numbered list
        assert '1.' in result or '1)' in result
        assert '2.' in result or '2)' in result

    def test_handles_no_matches(self):
        """Test handling no matching people."""
        result = format_pco_suggestions('Zzzzz', [])

        # Should indicate no results
        assert 'no' in result.lower() or 'not found' in result.lower() or "couldn't" in result.lower()


# =============================================================================
# TEST: format_first_name_matches
# =============================================================================

class TestFormatFirstNameMatches:
    """Tests for first name disambiguation formatting."""

    def test_formats_multiple_matches(self, mock_first_name_matches):
        """Test formatting multiple people with same first name."""
        result = format_first_name_matches('Sarah', mock_first_name_matches)

        assert 'Sarah Johnson' in result
        assert 'Sarah Williams' in result
        assert 'Sarah Chen' in result

    def test_shows_numbered_list(self, mock_first_name_matches):
        """Test that matches are shown as numbered list."""
        result = format_first_name_matches('Sarah', mock_first_name_matches)

        # Should show numbered list
        assert '1.' in result or '1)' in result
        assert '2.' in result or '2)' in result

    def test_indicates_disambiguation_needed(self, mock_first_name_matches):
        """Test that result asks user to clarify."""
        result = format_first_name_matches('Sarah', mock_first_name_matches)

        # Should ask which Sarah
        assert 'which' in result.lower() or 'clarify' in result.lower() or 'Multiple' in result


# =============================================================================
# TEST: format_disambiguation_prompt
# =============================================================================

class TestFormatDisambiguationPrompt:
    """Tests for song/person disambiguation prompt formatting."""

    def test_formats_both_options(self):
        """Test formatting when both song and person exist."""
        result = format_disambiguation_prompt('Gratitude', has_song_match=True, has_person_match=True)

        assert 'Gratitude' in result
        assert 'song' in result.lower()
        assert 'person' in result.lower() or 'volunteer' in result.lower()

    def test_formats_song_only(self):
        """Test formatting when only song exists."""
        result = format_disambiguation_prompt('Way Maker', has_song_match=True, has_person_match=False)

        assert 'Way Maker' in result
        assert 'song' in result.lower()

    def test_formats_person_only(self):
        """Test formatting when only person exists."""
        result = format_disambiguation_prompt('Grace', has_song_match=False, has_person_match=True)

        assert 'Grace' in result
        assert 'person' in result.lower() or 'volunteer' in result.lower()


# =============================================================================
# TEST: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_none_values_in_dict(self):
        """Test handling None values in data dictionaries."""
        plan = {
            'dates': None,
            'service_type_name': None,
            'team_members': None,
            'songs': None,
        }
        # Should not raise an error
        result = format_team_schedule(plan)
        assert isinstance(result, str)

    def test_handles_empty_strings(self):
        """Test handling empty strings in data."""
        person = {
            'name': '',
            'emails': [],
            'phone_numbers': [],
        }
        result = format_pco_details(person)
        assert isinstance(result, str)

    def test_handles_special_characters_in_names(self):
        """Test handling special characters in names."""
        plan = {
            'dates': 'December 15, 2024',
            'service_type_name': "St. Mary's Morning Service",
            'team_members': [
                {'name': "Sarah O'Brien", 'team_name': 'Vocals', 'position': 'Lead', 'status': 'Confirmed'},
                {'name': 'José García', 'team_name': 'Band', 'position': 'Guitar', 'status': 'Confirmed'},
            ],
            'songs': []
        }
        result = format_team_schedule(plan)

        assert "Sarah O'Brien" in result
        assert 'José García' in result

    def test_handles_very_long_lists(self):
        """Test handling large number of team members."""
        team_members = [
            {'name': f'Person {i}', 'team_name': 'Team', 'position': 'Member', 'status': 'Confirmed'}
            for i in range(50)
        ]
        plan = {
            'dates': 'December 15, 2024',
            'team_members': team_members,
            'songs': []
        }
        result = format_team_schedule(plan)

        # Should complete without error and contain some members
        assert 'Person 0' in result
        assert 'Person 49' in result

    def test_handles_unicode_in_lyrics(self):
        """Test handling unicode characters in lyrics."""
        song = {
            'title': 'Cornerstone',
            'author': 'Hillsong',
            'lyrics': 'My hope is built on nothing less\nThan Jesus\' blood and righteousness\n♪ ♫'
        }
        result = format_song_details(song)

        assert 'Cornerstone' in result
        # Should not crash on unicode
        assert isinstance(result, str)
