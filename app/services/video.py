"""YouTube video integration service.

Enforces ADR-004 and DATABASE_SCHEMA.md:
- Accepts recognized YouTube URL forms and extracts the clean 11-character video ID
- Rejects untrusted domains, malicious URLs, and arbitrary embed code
- Generates privacy-enhanced embed URLs via youtube-nocookie.com
"""
import re
from urllib.parse import urlparse, parse_qs


YOUTUBE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{11}$")

ALLOWED_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}


class VideoValidationError(ValueError):
    """Raised when a video link or identifier fails validation."""
    pass


def extract_youtube_id(url_or_id: str | None) -> str:
    """Validate input and extract an 11-character YouTube video ID.

    Accepts:
    - https://www.youtube.com/watch?v=<ID>
    - https://m.youtube.com/watch?v=<ID>
    - https://youtu.be/<ID>
    - https://www.youtube.com/embed/<ID>
    - https://www.youtube-nocookie.com/embed/<ID>
    - https://www.youtube.com/shorts/<ID>
    - Raw 11-character video ID (e.g. 'dQw4w9WgXcQ')

    Rejects:
    - Non-YouTube domains (phishing, spoofing, external links)
    - Arbitrary HTML or script injections
    - Malformed or missing IDs
    """
    if not url_or_id or not isinstance(url_or_id, str):
        raise VideoValidationError("YouTube URL or Video ID is required.")

    cleaned = url_or_id.strip()

    # Direct 11-character YouTube video ID
    if YOUTUBE_ID_REGEX.match(cleaned):
        return cleaned

    # Ensure URL has scheme for parsing if user provided domain without scheme
    if cleaned.startswith("www.") or cleaned.startswith("youtube.") or cleaned.startswith("youtu.be"):
        cleaned = "https://" + cleaned

    try:
        parsed = urlparse(cleaned)
    except Exception as e:
        raise VideoValidationError("Invalid URL format.") from e

    if parsed.scheme not in ("http", "https"):
        raise VideoValidationError("Only HTTP and HTTPS YouTube links are accepted.")

    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_YOUTUBE_HOSTS:
        raise VideoValidationError(
            f"Untrusted video domain '{hostname}'. Only official YouTube URLs are permitted."
        )

    video_id = None

    if hostname in ("youtu.be", "www.youtu.be"):
        # Pattern: youtu.be/<id>
        path_segments = [p for p in parsed.path.split("/") if p]
        if path_segments:
            video_id = path_segments[0]
    else:
        # Standard youtube.com or youtube-nocookie.com
        path = parsed.path
        if path == "/watch":
            query_args = parse_qs(parsed.query)
            v_values = query_args.get("v")
            if v_values and len(v_values) > 0:
                video_id = v_values[0]
        elif path.startswith("/embed/"):
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2 and parts[0] == "embed":
                video_id = parts[1]
        elif path.startswith("/shorts/"):
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2 and parts[0] == "shorts":
                video_id = parts[1]
        elif path.startswith("/v/"):
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2 and parts[0] == "v":
                video_id = parts[1]

    if not video_id or not YOUTUBE_ID_REGEX.match(video_id):
        raise VideoValidationError(
            "Could not extract a valid 11-character YouTube video ID from the provided link."
        )

    return video_id


def get_youtube_embed_url(video_id: str) -> str:
    """Generate a privacy-enhanced YouTube embed URL."""
    if not video_id or not YOUTUBE_ID_REGEX.match(video_id):
        raise VideoValidationError("Invalid YouTube video ID.")
    return f"https://www.youtube-nocookie.com/embed/{video_id}"


def get_youtube_thumbnail_url(video_id: str) -> str:
    """Generate the high-quality thumbnail image URL for a YouTube video."""
    if not video_id or not YOUTUBE_ID_REGEX.match(video_id):
        raise VideoValidationError("Invalid YouTube video ID.")
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
