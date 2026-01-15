"""
Automated tests for Aria RAG query detection.

These tests verify that the query detection functions correctly identify
the type of query from user input. This is Phase 1 of RAG testing -
no external APIs required.

Run with: pytest tests/test_aria_query_detection.py -v
"""
import pytest
from core.agent import (
    is_aggregate_question,
    is_analytics_query,
    is_pco_data_query,
    is_blockout_query,
    is_song_or_setlist_query,
    check_ambiguous_song_or_person,
    check_disambiguation_response,
    detect_service_type_from_question,
)


# =============================================================================
# Test Data: Query Detection Test Cases
# =============================================================================

class TestVolunteerContactQueries:
    """Test detection of volunteer contact information queries."""

    @pytest.mark.parametrize("query,expected_type", [
        # Email queries
        ("What's John Smith's email?", "email"),
        ("What is Sarah's email address?", "email"),
        ("Get me Lisa's email", "email"),
        ("john's email?", "email"),
        ("Email for David", "email"),

        # Phone queries
        ("What's Mike's phone number?", "phone"),
        ("Sarah's cell number", "phone"),
        ("How can I call John?", "phone"),
        ("David's mobile", "phone"),

        # General contact
        ("Contact info for Sarah Johnson", "contact"),
        ("How can I reach John?", "contact"),
        ("How do I get in touch with Mike?", "contact"),
        ("What's the best way to contact Lisa?", "contact"),

        # Address
        ("Where does John live?", "address"),
        ("What's Sarah's address?", "address"),
        ("Mike's mailing address", "address"),
    ])
    def test_contact_query_detection(self, query, expected_type):
        """Verify contact queries are correctly detected."""
        is_pco, query_type, person_name = is_pco_data_query(query)
        assert is_pco is True, f"Query '{query}' should be detected as PCO query"
        assert query_type == expected_type, f"Query '{query}' should be type '{expected_type}', got '{query_type}'"

    @pytest.mark.parametrize("query,expected_name", [
        ("What's John Smith's email?", "John Smith"),
        ("Contact info for Sarah Johnson", "Sarah Johnson"),
        ("How can I reach Mike?", "Mike"),
        ("Lisa's phone number", "Lisa"),
        ("Email for David Chen", "David Chen"),
    ])
    def test_name_extraction_from_contact_queries(self, query, expected_name):
        """Verify person names are correctly extracted from contact queries."""
        is_pco, query_type, person_name = is_pco_data_query(query)
        assert person_name is not None, f"Should extract name from '{query}'"
        assert person_name.lower() == expected_name.lower(), \
            f"Expected '{expected_name}', got '{person_name}' from '{query}'"


class TestServiceHistoryQueries:
    """Test detection of service history and schedule queries."""

    @pytest.mark.parametrize("query,expected_type", [
        # Past service
        ("When did John last serve?", "service_history"),
        ("When was Sarah's last time playing?", "service_history"),
        ("When did Mike play most recently?", "service_history"),

        # Future service
        ("When does Sarah play next?", "service_history"),
        ("When is John serving next?", "service_history"),
        ("Is Lisa scheduled this Sunday?", "service_history"),
        ("When will Mike be playing?", "service_history"),
    ])
    def test_service_history_detection(self, query, expected_type):
        """Verify service history queries are correctly detected."""
        is_pco, query_type, person_name = is_pco_data_query(query)
        assert is_pco is True, f"Query '{query}' should be detected as PCO query"
        assert query_type == expected_type, f"Query '{query}' should be type '{expected_type}', got '{query_type}'"


class TestTeamScheduleQueries:
    """Test detection of team schedule queries (who's serving)."""

    @pytest.mark.parametrize("query", [
        "Who's on the team this Sunday?",
        "Who is serving this week?",
        "Who's playing this Sunday?",
        "What's the team for this Sunday?",
        "Who do we have this weekend?",
        "Who was on the team last Sunday?",
        "Who served on Easter?",
        "Who played on December 14th?",
        "Who's scheduled for next Sunday?",
        "Who is on the team for Christmas Eve?",
    ])
    def test_team_schedule_detection(self, query):
        """Verify team schedule queries are detected as song/setlist with team_schedule type."""
        is_song, query_type, extracted = is_song_or_setlist_query(query)
        assert is_song is True, f"Query '{query}' should be detected as song/setlist query"
        assert query_type == "team_schedule", f"Query '{query}' should be type 'team_schedule', got '{query_type}'"


class TestBlockoutQueries:
    """Test detection of blockout and availability queries."""

    @pytest.mark.parametrize("query,expected_type", [
        # Person blockouts
        ("When is Sarah blocked out?", "person_blockouts"),
        ("What are John's blockout dates?", "person_blockouts"),
        ("Show me Mike's blockouts", "person_blockouts"),
        ("Lisa's blockout dates", "person_blockouts"),

        # Date blockouts
        ("Who's blocked out on December 14th?", "date_blockouts"),
        ("Who can't make it this Sunday?", "date_blockouts"),
        ("Who has blockouts for Christmas Eve?", "date_blockouts"),

        # Availability check
        ("Is John available on December 21st?", "availability_check"),
        ("Can Sarah serve this Sunday?", "availability_check"),
        ("Is Mike free for Christmas Eve?", "availability_check"),

        # Team availability
        ("Team availability for this Sunday", "team_availability"),
        ("Who's available next week?", "team_availability"),
    ])
    def test_blockout_query_detection(self, query, expected_type):
        """Verify blockout queries are correctly detected."""
        is_blockout, query_type, person_name, date_ref = is_blockout_query(query)
        assert is_blockout is True, f"Query '{query}' should be detected as blockout query"
        assert query_type == expected_type, f"Query '{query}' should be type '{expected_type}', got '{query_type}'"


class TestSetlistQueries:
    """Test detection of setlist queries."""

    @pytest.mark.parametrize("query", [
        "What songs did we play last Sunday?",
        "Show me the setlist from last week",
        "What did we sing on Easter?",
        "What songs were on the set on 11/16?",
        "Setlist for November 16th, 2024",
        "Songs from Christmas Eve",
    ])
    def test_setlist_query_detection(self, query):
        """Verify setlist queries are correctly detected."""
        is_song, query_type, extracted = is_song_or_setlist_query(query)
        assert is_song is True, f"Query '{query}' should be detected as song query"
        assert query_type == "setlist", f"Query '{query}' should be type 'setlist', got '{query_type}'"


class TestSongHistoryQueries:
    """Test detection of song history queries (when was song played)."""

    @pytest.mark.parametrize("query", [
        "When did we last play Gratitude?",
        "When was the last time we did Way Maker?",
        "Have we ever played Oceans?",
        "How often do we play Build My Life?",
        "Song usage history for Holy Spirit",
    ])
    def test_song_history_detection(self, query):
        """Verify song history queries are detected (asking WHEN a song was played)."""
        is_song, query_type, extracted = is_song_or_setlist_query(query)
        assert is_song is True, f"Query '{query}' should be detected as song query"
        # Note: Some of these might be detected as ambiguous - that's okay
        # The key is they should be song-related


class TestChordChartQueries:
    """Test detection of chord chart queries."""

    @pytest.mark.parametrize("query", [
        "Chord chart for Goodness of God",
        "Get me the chords for Way Maker",
        "Lead sheet for Great Are You Lord",
        "Charts for Build My Life",
        "Show me the chord chart for Amazing Grace",
        "Chords to Holy Spirit",
    ])
    def test_chord_chart_detection(self, query):
        """Verify chord chart queries are correctly detected."""
        is_song, query_type, extracted = is_song_or_setlist_query(query)
        assert is_song is True, f"Query '{query}' should be detected as song query"
        assert query_type == "chord_chart", f"Query '{query}' should be type 'chord_chart', got '{query_type}'"


class TestLyricsQueries:
    """Test detection of lyrics queries."""

    @pytest.mark.parametrize("query", [
        "Show me the lyrics for Holy Spirit",
        "What's the chorus of Way Maker?",
        "Lyrics to the bridge of Gratitude",
        "What are the words to Amazing Grace?",
        "Give me the lyrics for Oceans",
        "Lyrics to the verse of Build My Life",
    ])
    def test_lyrics_detection(self, query):
        """Verify lyrics queries are correctly detected."""
        is_song, query_type, extracted = is_song_or_setlist_query(query)
        assert is_song is True, f"Query '{query}' should be detected as song query"
        assert query_type == "lyrics", f"Query '{query}' should be type 'lyrics', got '{query_type}'"


class TestSongInfoQueries:
    """Test detection of song info queries (key, tempo)."""

    @pytest.mark.parametrize("query", [
        "What key is Goodness of God in?",
        "What's the BPM for Way Maker?",
        "How fast is Build My Life?",
        "What tempo is Great Are You Lord?",
    ])
    def test_song_info_detection(self, query):
        """Verify song info queries are correctly detected."""
        is_song, query_type, extracted = is_song_or_setlist_query(query)
        assert is_song is True, f"Query '{query}' should be detected as song query"
        assert query_type == "song_info", f"Query '{query}' should be type 'song_info', got '{query_type}'"


class TestAnalyticsQueries:
    """Test detection of analytics and reporting queries."""

    @pytest.mark.parametrize("query,expected_type", [
        # Overview
        ("Team overview", "overview"),
        ("How are we doing as a team?", "overview"),
        ("Give me team stats", "overview"),
        ("Team summary", "overview"),

        # Engagement
        ("Volunteer engagement report", "engagement"),
        ("Who are our most engaged volunteers?", "engagement"),

        # Care - includes volunteers needing attention/reach out
        ("Which volunteers need attention?", "care"),
        ("Who needs a check-in?", "care"),
        ("Show me volunteers I should reach out to", "care"),
        ("Overdue follow-ups", "care"),

        # Proactive
        ("Proactive care dashboard", "proactive"),
        ("Care alerts", "proactive"),
        ("What should I focus on today?", "proactive"),

        # Trends
        ("Interaction trends", "trends"),
        ("How have interactions been?", "trends"),

        # Prayer
        ("Prayer request summary", "prayer"),
        ("What are people praying about?", "prayer"),

        # AI performance
        ("How is Aria doing?", "ai"),
        ("AI performance stats", "ai"),
    ])
    def test_analytics_query_detection(self, query, expected_type):
        """Verify analytics queries are correctly detected."""
        is_analytics, report_type = is_analytics_query(query)
        assert is_analytics is True, f"Query '{query}' should be detected as analytics query"
        assert report_type == expected_type, f"Query '{query}' should be type '{expected_type}', got '{report_type}'"


class TestAggregateQueries:
    """Test detection of aggregate/team-wide queries."""

    @pytest.mark.parametrize("query,expected_category", [
        # Food
        ("What are everyone's favorite foods?", "food"),
        ("Show me all dietary restrictions on the team", "food"),

        # Hobbies
        ("What hobbies do our volunteers have?", "hobbies"),
        ("Who likes hiking?", "hobbies"),

        # Family
        ("How many volunteers have kids?", "family"),
        ("Which volunteers are married?", "family"),

        # Birthday
        ("Who has birthdays this month?", "birthday"),
        ("Show me all upcoming birthdays", "birthday"),

        # Prayer
        ("What are the most common prayer requests?", "prayer"),
        ("Prayer themes across the team", "prayer"),

        # Availability
        ("Who's usually available on Sundays?", "availability"),
        ("Team availability patterns", "availability"),
    ])
    def test_aggregate_query_detection(self, query, expected_category):
        """Verify aggregate queries are correctly detected."""
        is_aggregate, category = is_aggregate_question(query)
        assert is_aggregate is True, f"Query '{query}' should be detected as aggregate query"
        assert category == expected_category, f"Query '{query}' should have category '{expected_category}', got '{category}'"


class TestDisambiguationDetection:
    """Test detection of ambiguous queries that need clarification."""

    @pytest.mark.parametrize("query", [
        "When did we last play Gratitude?",
        "Have we played Grace recently?",
        "When was Joy last on the schedule?",
    ])
    def test_ambiguous_song_person_detection(self, query):
        """Verify ambiguous song/person queries are detected."""
        is_ambiguous, extracted, matches_song, matches_person = check_ambiguous_song_or_person(query)
        # These SHOULD be detected as potentially ambiguous
        # (though the actual response depends on whether matching songs/people exist)
        assert extracted is not None, f"Query '{query}' should extract a value for disambiguation"

    @pytest.mark.parametrize("query,expected_choice", [
        ("The song", "song"),
        ("It's a song", "song"),
        ("The worship song", "song"),
        ("The person", "person"),
        ("The volunteer", "person"),
        ("Someone named", "person"),
    ])
    def test_disambiguation_response_detection(self, query, expected_choice):
        """Verify disambiguation responses are correctly interpreted."""
        is_response, choice = check_disambiguation_response(query)
        assert is_response is True, f"'{query}' should be recognized as disambiguation response"
        assert choice == expected_choice, f"'{query}' should be interpreted as '{expected_choice}', got '{choice}'"


class TestServiceTypeDetection:
    """Test detection of specific service types (HSM, MSM)."""

    @pytest.mark.parametrize("query,expected_service", [
        ("Who's on the HSM team this Sunday?", "HSM"),
        ("Who's serving MSM this week?", "MSM"),
        ("Who's on the youth team?", None),  # Not specific enough
        ("Who's playing for high school?", "HSM"),
        ("Middle school team", "MSM"),
    ])
    def test_service_type_detection(self, query, expected_service):
        """Verify service type keywords are detected."""
        service_type = detect_service_type_from_question(query)
        assert service_type == expected_service, \
            f"Query '{query}' should detect service type '{expected_service}', got '{service_type}'"


class TestClearSongVsPersonPatterns:
    """Test that clear song/person patterns are NOT flagged as ambiguous."""

    @pytest.mark.parametrize("query", [
        # Clear song patterns
        "Chord chart for Gratitude",
        "Lyrics to the song Gratitude",
        "What songs did we play?",
        "Show me the setlist",

        # Clear person patterns
        "What's John's email?",
        "When does Sarah serve next?",
        "Is Mike blocked out?",
    ])
    def test_clear_patterns_not_ambiguous(self, query):
        """Verify that clear song/person queries are NOT flagged as ambiguous."""
        is_ambiguous, extracted, matches_song, matches_person = check_ambiguous_song_or_person(query)
        assert is_ambiguous is False, f"Query '{query}' should NOT be flagged as ambiguous"


class TestEdgeCases:
    """Test edge cases and potential problem queries."""

    @pytest.mark.parametrize("query", [
        # Typos (should still attempt to parse)
        "Waht's johns emial?",
        "who's servng on sundya?",

        # Informal grammar
        "john email?",
        "sarah schedule?",

        # Mixed case
        "WHAT'S JOHN'S EMAIL?",
        "Who Is On The Team?",
    ])
    def test_handles_imperfect_input(self, query):
        """Verify queries with typos/grammar issues are handled gracefully."""
        # These should at minimum not crash
        # Some may be detected, some may not - that's okay
        try:
            is_pco, _, _ = is_pco_data_query(query)
            is_song, _, _ = is_song_or_setlist_query(query)
            is_blockout, _, _, _ = is_blockout_query(query)
            is_analytics, _ = is_analytics_query(query)
            is_aggregate, _ = is_aggregate_question(query)
            # If we get here without exception, the test passes
            assert True
        except Exception as e:
            pytest.fail(f"Query '{query}' caused exception: {e}")

    @pytest.mark.parametrize("query", [
        # Non-queries (shouldn't match anything)
        "Hello",
        "Thanks!",
        "Okay",
        "Got it",
    ])
    def test_non_queries_not_matched(self, query):
        """Verify casual messages don't trigger query detection."""
        is_pco, _, _ = is_pco_data_query(query)
        is_blockout, _, _, _ = is_blockout_query(query)
        is_analytics, _ = is_analytics_query(query)

        # These simple messages shouldn't match specific queries
        # (aggregate might match "general" which is okay)
        assert not is_pco, f"'{query}' should not be detected as PCO query"
        assert not is_blockout, f"'{query}' should not be detected as blockout query"
        assert not is_analytics, f"'{query}' should not be detected as analytics query"


class TestQueryPrioritization:
    """Test that overlapping patterns are correctly prioritized."""

    def test_team_schedule_over_setlist(self):
        """Team schedule queries should be detected as team_schedule, not setlist."""
        query = "Who's playing this Sunday?"
        is_song, query_type, _ = is_song_or_setlist_query(query)
        assert is_song is True
        assert query_type == "team_schedule", f"Expected 'team_schedule', got '{query_type}'"

    def test_chord_chart_over_song_history(self):
        """Chord chart queries should be detected as chord_chart."""
        query = "Chord chart for the song we played last week"
        is_song, query_type, _ = is_song_or_setlist_query(query)
        assert is_song is True
        assert query_type == "chord_chart", f"Expected 'chord_chart', got '{query_type}'"

    def test_lyrics_over_general_song(self):
        """Lyrics queries should be detected as lyrics."""
        query = "What are the lyrics to Way Maker?"
        is_song, query_type, _ = is_song_or_setlist_query(query)
        assert is_song is True
        assert query_type == "lyrics", f"Expected 'lyrics', got '{query_type}'"


class TestCompoundTeamContactQueries:
    """Test detection of compound queries for team contact information."""

    @pytest.mark.parametrize("query,expected_contact_type", [
        # Phone queries for team
        ("What are the phone numbers of the people serving this weekend?", "phone"),
        ("Get me the phone numbers for everyone on the team this Sunday", "phone"),
        ("Phone numbers of volunteers scheduled this week", "phone"),
        ("Contact info for the team serving Sunday", "contact"),
        ("Email addresses of people playing this weekend", "email"),
        ("Show me phone numbers for team members serving this Sunday", "phone"),
        ("Get phone numbers for the volunteers on the schedule this weekend", "phone"),
        # Team name variations (band, vocals, tech, etc.)
        ("What are the phone numbers of the band team members for this sunday", "phone"),
        ("Phone numbers of the band for this sunday", "phone"),
        ("Contact info for the vocals team for next sunday", "contact"),
        ("Email addresses of the tech team for this weekend", "email"),
        # Simpler patterns without "serving/scheduled"
        ("Phone numbers for the team this sunday", "phone"),
        ("Contact info for the band this weekend", "contact"),
        ("Phone numbers of team members for this sunday", "phone"),
    ])
    def test_compound_query_detection(self, query, expected_contact_type):
        """Verify compound team contact queries are correctly detected."""
        from core.agent import is_compound_team_contact_query
        is_compound, contact_type, date_ref = is_compound_team_contact_query(query)
        assert is_compound is True, f"Query '{query}' should be detected as compound query"
        assert contact_type == expected_contact_type, f"Expected contact type '{expected_contact_type}', got '{contact_type}'"

    @pytest.mark.parametrize("query,expected_date_contains", [
        ("What are the phone numbers of the people serving this weekend?", "weekend"),
        ("Phone numbers of volunteers scheduled this Sunday", "sunday"),
        ("Contact info for team serving next Sunday", "next sunday"),
        ("Get phone numbers for people on team January 15th", "january 15"),
    ])
    def test_compound_query_date_extraction(self, query, expected_date_contains):
        """Verify date references are extracted from compound queries."""
        from core.agent import is_compound_team_contact_query
        is_compound, contact_type, date_ref = is_compound_team_contact_query(query)
        assert is_compound is True, f"Query '{query}' should be detected as compound query"
        assert date_ref is not None, f"Should extract date from '{query}'"
        assert expected_date_contains.lower() in date_ref.lower(), \
            f"Date '{date_ref}' should contain '{expected_date_contains}'"

    @pytest.mark.parametrize("query", [
        # These should NOT be detected as compound queries
        "What's John Smith's phone number?",  # Specific person
        "Phone number for Sarah",  # Specific person
        "Who's serving this Sunday?",  # Team schedule only, no contact
        "Contact info for Mike",  # Specific person
        "Get me the setlist for this Sunday",  # Setlist query
    ])
    def test_non_compound_queries_not_matched(self, query):
        """Verify non-compound queries are not detected as compound queries."""
        from core.agent import is_compound_team_contact_query
        is_compound, _, _ = is_compound_team_contact_query(query)
        assert not is_compound, f"Query '{query}' should NOT be detected as compound query"


class TestGenericNameRejection:
    """Test that generic terms are not extracted as person names."""

    @pytest.mark.parametrize("query", [
        "Phone numbers of the people serving this weekend",
        "Contact info for the team this Sunday",
        "Email addresses of volunteers scheduled",
        "How can I reach everyone on the team?",
        "Phone numbers for folks serving",
    ])
    def test_generic_terms_not_extracted_as_names(self, query):
        """Verify generic group terms are not extracted as person names."""
        is_pco, query_type, person_name = is_pco_data_query(query)
        # If detected as PCO query, person_name should be None (not a generic term)
        if is_pco:
            assert person_name is None or person_name.lower() not in [
                'the people', 'people', 'team', 'volunteers', 'everyone',
                'folks', 'members', 'the people serving', 'the team',
            ], f"Generic term '{person_name}' should not be extracted as name from '{query}'"

    @pytest.mark.parametrize("query,expected_name", [
        # Real person names should still be extracted
        ("What's John Smith's phone number?", "John Smith"),
        ("Contact info for Sarah Johnson", "Sarah Johnson"),
        ("Email for Mike", "Mike"),
    ])
    def test_real_names_still_extracted(self, query, expected_name):
        """Verify real person names are still extracted correctly."""
        is_pco, query_type, person_name = is_pco_data_query(query)
        assert is_pco is True, f"Query '{query}' should be detected as PCO query"
        assert person_name is not None, f"Should extract name from '{query}'"
        assert person_name.lower() == expected_name.lower(), \
            f"Expected '{expected_name}', got '{person_name}' from '{query}'"
