"""
BPM extraction service with cascading fallback strategy.

Priority order:
1. PCO arrangement BPM (already in arrangement.bpm)
2. Parse chord chart text for BPM patterns
3. Analyze MP3 audio using librosa
4. Look up BPM from SongBPM API
"""
import logging
import re
import tempfile
from typing import Optional, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# SongBPM API configuration
SONGBPM_API_BASE = "https://api.getsongbpm.com"
SONGBPM_API_KEY = getattr(settings, 'SONGBPM_API_KEY', '')

# BPM extraction regex patterns for chord charts
BPM_PATTERNS = [
    # Standard BPM notations
    r'(?:tempo|bpm|beats?\s*per\s*min(?:ute)?)\s*[:=]?\s*(\d{2,3})',
    r'(\d{2,3})\s*(?:bpm|beats?\s*per\s*min(?:ute)?)',
    # Quarter note = X notation
    r'[♩♪]\s*[:=]?\s*(\d{2,3})',
    r'(?:quarter\s*note|q\.?\s*note)\s*[:=]?\s*(\d{2,3})',
    # Tempo marking with number
    r'(?:♩|q)\s*=\s*(\d{2,3})',
    # In header/metadata sections
    r'(?:^|\n)\s*(?:tempo|speed)\s*[:=]?\s*(\d{2,3})',
]

# Reasonable BPM range for worship music
MIN_BPM = 40
MAX_BPM = 200


def extract_bpm_from_text(text: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Extract BPM from chord chart or lyrics text using regex patterns.

    Common patterns in chord charts:
    - "Tempo: 72"
    - "BPM = 120"
    - "72 BPM"
    - "♩ = 84"
    - "Quarter note = 72"

    Args:
        text: Chord chart or lyrics text content

    Returns:
        Tuple of (bpm, matched_pattern) or (None, None) if not found
    """
    if not text:
        return None, None

    text_lower = text.lower()

    for pattern in BPM_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            try:
                bpm = int(match)
                if MIN_BPM <= bpm <= MAX_BPM:
                    logger.info(f"Extracted BPM {bpm} from text using pattern: {pattern}")
                    return bpm, pattern
            except (ValueError, TypeError):
                continue

    return None, None


def analyze_audio_bpm(audio_url: str, auth: tuple = None) -> Tuple[Optional[int], Optional[dict]]:
    """
    Analyze audio file to detect BPM using librosa.

    Downloads the audio file, extracts tempo using librosa's beat tracking,
    and returns the estimated BPM.

    Args:
        audio_url: URL to download the audio file from
        auth: Optional (app_id, secret) tuple for PCO authentication

    Returns:
        Tuple of (bpm, metadata) or (None, None) if analysis fails
        metadata includes: {'method': 'librosa', 'duration': float, 'confidence': str}
    """
    try:
        import librosa
    except ImportError:
        logger.warning("librosa not installed - skipping audio analysis")
        return None, None

    if not audio_url:
        return None, None

    try:
        # Download the audio file
        logger.info(f"Downloading audio for BPM analysis: {audio_url[:100]}...")

        if auth:
            response = requests.get(audio_url, auth=auth, timeout=60)
        else:
            response = requests.get(audio_url, timeout=60)

        response.raise_for_status()

        # Check content length (limit to 50MB)
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > 50 * 1024 * 1024:
            logger.warning(f"Audio file too large for analysis: {content_length} bytes")
            return None, None

        # Write to temp file for librosa processing
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=True) as tmp_file:
            tmp_file.write(response.content)
            tmp_file.flush()

            # Load audio with librosa
            # Use a lower sample rate for faster processing
            y, sr = librosa.load(tmp_file.name, sr=22050, mono=True, duration=120)

            # Estimate tempo using librosa's beat tracking
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)

            # Handle case where tempo is an array (older librosa versions)
            if hasattr(tempo, '__iter__'):
                tempo = float(tempo[0]) if len(tempo) > 0 else None
            else:
                tempo = float(tempo)

            if tempo and MIN_BPM <= tempo <= MAX_BPM:
                bpm = round(tempo)
                duration = librosa.get_duration(y=y, sr=sr)

                # Calculate confidence based on consistency of beat detection
                confidence = 'high' if len(beat_frames) > 20 else 'medium' if len(beat_frames) > 10 else 'low'

                metadata = {
                    'method': 'librosa',
                    'duration_analyzed': duration,
                    'beat_count': len(beat_frames),
                    'raw_tempo': tempo,
                    'confidence': confidence,
                }

                logger.info(f"Audio analysis found BPM: {bpm} (raw: {tempo:.2f}, beats: {len(beat_frames)})")
                return bpm, metadata
            else:
                logger.warning(f"Audio analysis returned invalid tempo: {tempo}")
                return None, None

    except requests.RequestException as e:
        logger.error(f"Error downloading audio for BPM analysis: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Error analyzing audio for BPM: {e}")
        return None, None


def lookup_bpm_songbpm(title: str, artist: str = None) -> Tuple[Optional[int], Optional[dict]]:
    """
    Look up BPM from SongBPM API (getsongbpm.com).

    IMPORTANT: Per GetSongBPM API terms, a backlink to GetSongBPM.com is REQUIRED
    when displaying BPM data from this source. The format_song_details() function
    in agent.py includes this attribution automatically.

    Args:
        title: Song title to search for
        artist: Optional artist name for more accurate matching

    Returns:
        Tuple of (bpm, metadata) or (None, None) if not found
        metadata includes: {'songbpm_id': str, 'matched_title': str, 'matched_artist': str}
    """
    api_key = getattr(settings, 'SONGBPM_API_KEY', '')
    if not api_key:
        logger.warning("SONGBPM_API_KEY not configured - skipping SongBPM lookup")
        return None, None

    if not title:
        return None, None

    try:
        # First search for the song
        search_query = title
        if artist:
            search_query = f"{artist} {title}"

        search_url = f"{SONGBPM_API_BASE}/search/"
        params = {
            'api_key': api_key,
            'type': 'song',
            'lookup': search_query,
        }

        logger.info(f"Searching SongBPM API for: {search_query}")
        response = requests.get(search_url, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()

        # Check for search results
        search_results = data.get('search', [])
        if not search_results:
            logger.info(f"No results from SongBPM API for: {search_query}")
            return None, None

        # Find best match (first result that has tempo)
        for result in search_results:
            song_id = result.get('id')
            if not song_id:
                continue

            # Get full song details
            song_url = f"{SONGBPM_API_BASE}/song/"
            song_params = {
                'api_key': api_key,
                'id': song_id,
            }

            song_response = requests.get(song_url, params=song_params, timeout=15)
            song_response.raise_for_status()
            song_data = song_response.json()

            song_info = song_data.get('song', {})
            tempo = song_info.get('tempo')

            if tempo:
                try:
                    bpm = int(float(tempo))
                    if MIN_BPM <= bpm <= MAX_BPM:
                        metadata = {
                            'songbpm_id': song_id,
                            'matched_title': song_info.get('title', ''),
                            'matched_artist': song_info.get('artist', {}).get('name', ''),
                            'key': song_info.get('key_of', ''),
                            'time_signature': song_info.get('time_sig', ''),
                        }
                        logger.info(f"SongBPM API found BPM {bpm} for '{song_info.get('title')}'")
                        return bpm, metadata
                except (ValueError, TypeError):
                    continue

        logger.info(f"No valid BPM found in SongBPM results for: {search_query}")
        return None, None

    except requests.RequestException as e:
        logger.error(f"Error calling SongBPM API: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Unexpected error in SongBPM lookup: {e}")
        return None, None


def get_song_bpm(song_id: str, organization=None, song_details: dict = None,
                 services_api=None) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Main BPM retrieval function with cascading fallback strategy.

    Priority order:
    1. Check cache first
    2. PCO arrangement BPM
    3. Parse chord chart text
    4. Analyze MP3 audio
    5. SongBPM API lookup

    Args:
        song_id: PCO song ID
        organization: Organization instance (for multi-tenant caching)
        song_details: Pre-fetched song details dict (optional, will fetch if not provided)
        services_api: PlanningCenterServicesAPI instance (optional)

    Returns:
        Tuple of (bpm, source, confidence) or (None, None, None) if not found
        - bpm: Integer BPM value
        - source: One of 'pco', 'chord_chart', 'audio_analysis', 'songbpm_api'
        - confidence: One of 'high', 'medium', 'low'
    """
    from .models import SongBPMCache
    from .planning_center import PlanningCenterServicesAPI

    # Step 0: Check cache first
    cached_bpm, cached_source, cached_confidence = SongBPMCache.get_cached_bpm(
        song_id, organization
    )
    if cached_bpm:
        logger.info(f"Using cached BPM {cached_bpm} for song {song_id} (source: {cached_source})")
        return cached_bpm, cached_source, cached_confidence

    # Initialize API if not provided
    if services_api is None:
        services_api = PlanningCenterServicesAPI()

    # Fetch song details if not provided
    if song_details is None and services_api.is_configured:
        song_details = services_api.get_song_details(song_id)

    if not song_details:
        logger.warning(f"Could not fetch song details for {song_id}")
        return None, None, None

    song_title = song_details.get('title', '')
    song_author = song_details.get('author', '')
    arrangements = song_details.get('arrangements', [])

    # Step 1: Check PCO arrangement BPM
    for arr in arrangements:
        pco_bpm = arr.get('bpm')
        if pco_bpm and isinstance(pco_bpm, (int, float)) and MIN_BPM <= pco_bpm <= MAX_BPM:
            bpm = int(pco_bpm)
            arr_id = arr.get('id')

            # Cache it
            SongBPMCache.set_cached_bpm(
                pco_song_id=song_id,
                bpm=bpm,
                bpm_source='pco',
                song_title=song_title,
                organization=organization,
                arrangement_id=arr_id,
                song_artist=song_author,
                confidence='high',
                source_metadata={'arrangement_name': arr.get('name')}
            )

            logger.info(f"Found BPM {bpm} from PCO arrangement for '{song_title}'")
            return bpm, 'pco', 'high'

    # Step 2: Parse chord chart text
    for arr in arrangements:
        chord_chart_text = arr.get('chord_chart', '')
        if chord_chart_text:
            bpm, pattern = extract_bpm_from_text(chord_chart_text)
            if bpm:
                SongBPMCache.set_cached_bpm(
                    pco_song_id=song_id,
                    bpm=bpm,
                    bpm_source='chord_chart',
                    song_title=song_title,
                    organization=organization,
                    song_artist=song_author,
                    confidence='medium',
                    source_metadata={'matched_pattern': pattern, 'arrangement_name': arr.get('name')}
                )

                logger.info(f"Found BPM {bpm} from chord chart for '{song_title}'")
                return bpm, 'chord_chart', 'medium'

    # Also check attachments for chord chart text
    attachments = song_details.get('all_attachments', [])
    for attach in attachments:
        content = attach.get('text_content', '')
        if content:
            bpm, pattern = extract_bpm_from_text(content)
            if bpm:
                SongBPMCache.set_cached_bpm(
                    pco_song_id=song_id,
                    bpm=bpm,
                    bpm_source='chord_chart',
                    song_title=song_title,
                    organization=organization,
                    song_artist=song_author,
                    confidence='medium',
                    source_metadata={'matched_pattern': pattern, 'filename': attach.get('filename')}
                )

                logger.info(f"Found BPM {bpm} from attachment for '{song_title}'")
                return bpm, 'chord_chart', 'medium'

    # Step 3: Analyze MP3 audio attachments
    auth = (services_api.app_id, services_api.secret) if services_api.is_configured else None

    for attach in attachments:
        content_type = attach.get('content_type', '')
        filename = attach.get('filename', '')
        url = attach.get('url', '')

        # Check if this is an audio file
        is_audio = (
            'audio' in content_type.lower() or
            filename.lower().endswith(('.mp3', '.m4a', '.wav', '.flac', '.ogg')) or
            attach.get('streamable', False)
        )

        if is_audio and url:
            bpm, metadata = analyze_audio_bpm(url, auth=auth)
            if bpm:
                confidence = metadata.get('confidence', 'medium') if metadata else 'medium'
                SongBPMCache.set_cached_bpm(
                    pco_song_id=song_id,
                    bpm=bpm,
                    bpm_source='audio_analysis',
                    song_title=song_title,
                    organization=organization,
                    song_artist=song_author,
                    confidence=confidence,
                    source_metadata=metadata or {}
                )

                logger.info(f"Found BPM {bpm} from audio analysis for '{song_title}'")
                return bpm, 'audio_analysis', confidence

    # Step 4: SongBPM API lookup (final fallback)
    bpm, metadata = lookup_bpm_songbpm(song_title, song_author)
    if bpm:
        SongBPMCache.set_cached_bpm(
            pco_song_id=song_id,
            bpm=bpm,
            bpm_source='songbpm_api',
            song_title=song_title,
            organization=organization,
            song_artist=song_author,
            confidence='medium',
            source_metadata=metadata or {}
        )

        logger.info(f"Found BPM {bpm} from SongBPM API for '{song_title}'")
        return bpm, 'songbpm_api', 'medium'

    logger.info(f"No BPM found for '{song_title}' from any source")
    return None, None, None
