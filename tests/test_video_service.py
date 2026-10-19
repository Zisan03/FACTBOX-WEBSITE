"""Tests for YouTube video integration service.

Enforces ADR-004 and DATABASE_SCHEMA.md:
- Extracts clean 11-character video ID from all valid YouTube URL forms
- Rejects untrusted domains, spoofed hostnames, and arbitrary/malicious inputs
- Enforces privacy-enhanced embed URLs via youtube-nocookie.com
"""
import pytest
from app.services.video import (
    extract_youtube_id,
    get_youtube_embed_url,
    get_youtube_thumbnail_url,
    VideoValidationError,
)


def test_extract_youtube_id_standard_watch():
    """Verify standard watch URL parses correctly."""
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert extract_youtube_id(url) == "dQw4w9WgXcQ"


def test_extract_youtube_id_with_parameters():
    """Verify watch URL with timestamp and tracking parameters parses correctly."""
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s&feature=shared"
    assert extract_youtube_id(url) == "dQw4w9WgXcQ"


def test_extract_youtube_id_short_share():
    """Verify youtu.be short URL parses correctly."""
    url = "https://youtu.be/dQw4w9WgXcQ"
    assert extract_youtube_id(url) == "dQw4w9WgXcQ"


def test_extract_youtube_id_short_share_with_query():
    """Verify youtu.be short URL with query parameters parses correctly."""
    url = "https://youtu.be/dQw4w9WgXcQ?t=15"
    assert extract_youtube_id(url) == "dQw4w9WgXcQ"


def test_extract_youtube_id_embed_url():
    """Verify embed URL format parses correctly."""
    url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
    assert extract_youtube_id(url) == "dQw4w9WgXcQ"


def test_extract_youtube_id_nocookie_embed():
    """Verify youtube-nocookie.com embed URL parses correctly."""
    url = "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
    assert extract_youtube_id(url) == "dQw4w9WgXcQ"


def test_extract_youtube_id_shorts():
    """Verify YouTube shorts URL parses correctly."""
    url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
    assert extract_youtube_id(url) == "dQw4w9WgXcQ"


def test_extract_youtube_id_raw_id():
    """Verify direct 11-character video ID is accepted."""
    assert extract_youtube_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_youtube_id_rejects_untrusted_domain():
    """Verify untrusted domains and phishing attempts are rejected."""
    bad_urls = [
        "https://evil.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com.attacker.com/watch?v=dQw4w9WgXcQ",
        "https://vimeo.com/123456789",
        "http://not-youtube.com/dQw4w9WgXcQ",
    ]
    for url in bad_urls:
        with pytest.raises(VideoValidationError, match="Untrusted video domain"):
            extract_youtube_id(url)


def test_extract_youtube_id_rejects_malformed_input():
    """Verify malformed, invalid, or injected inputs are rejected."""
    invalid_inputs = [
        "",
        None,
        "   ",
        "https://www.youtube.com/watch?v=short",  # < 11 chars
        "https://www.youtube.com/watch?v=this_is_way_too_long_to_be_a_youtube_id",
        "https://www.youtube.com/watch?v=invalid@char",
        "<script>alert('xss')</script>",
        "javascript:alert(1)",
    ]
    for inp in invalid_inputs:
        with pytest.raises(VideoValidationError):
            extract_youtube_id(inp)


def test_privacy_enhanced_embed_url():
    """Verify embed URLs strictly use the privacy-enhanced youtube-nocookie.com origin."""
    video_id = "dQw4w9WgXcQ"
    embed_url = get_youtube_embed_url(video_id)
    assert embed_url == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
    assert "youtube-nocookie.com" in embed_url


def test_youtube_thumbnail_url():
    """Verify thumbnail URL generation."""
    video_id = "dQw4w9WgXcQ"
    thumb_url = get_youtube_thumbnail_url(video_id)
    assert thumb_url == "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
