"""Cloudinary media upload and management service.

Enforces ADR-004, ADR-007, and DATABASE_SCHEMA.md:
- Server-side image upload validation (JPEG, PNG, WebP only, <= 10MB limit)
- Deep magic-bytes inspection prevents disguised malicious files
- Uploads directly to Cloudinary; no media persisted on local disk
- Safe error handling and orphan asset prevention if database writes fail
- Clean deletion preventing dangling external references
"""
import os
import logging
from typing import Dict, Any, Tuple
import cloudinary
import cloudinary.uploader
import cloudinary.utils
from flask import current_app
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models.portfolio import PortfolioImage
from app.models.home_photo import HomePagePhoto
from app.models.content import PartnerLogo

logger = logging.getLogger(__name__)

# Enforce 10 MB maximum upload limit matching Cloudinary Free tier allocation
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10,485,760 bytes

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/pjpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


class MediaValidationError(ValueError):
    """Raised when an uploaded file fails security or format validation."""
    pass


class CloudinaryUploadError(RuntimeError):
    """Raised when Cloudinary rejects an upload or connectivity fails."""
    pass


def detect_image_format_from_bytes(header_bytes: bytes) -> str | None:
    """Inspect binary magic numbers to determine true image format."""
    if len(header_bytes) >= 3 and header_bytes[:3] == b"\xff\xd8\xff":
        return "jpg"
    if len(header_bytes) >= 8 and header_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(header_bytes) >= 12 and header_bytes[:4] == b"RIFF" and header_bytes[8:12] == b"WEBP":
        return "webp"
    if len(header_bytes) >= 6 and header_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def validate_image_file(file_storage: FileStorage) -> str:
    """Validate uploaded image file size, extension, MIME type, and binary header.

    Returns the detected format string ('jpg', 'png', 'webp', or 'gif').
    Raises MediaValidationError on any validation failure.
    """
    if not file_storage or not file_storage.filename:
        raise MediaValidationError("No file was selected for upload.")

    filename = file_storage.filename.strip()
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise MediaValidationError(
            f"Unsupported file format '{ext}'. Allowed formats: JPG, PNG, WebP, and GIF."
        )

    # Content-type check if supplied by client
    content_type = (file_storage.content_type or "").lower().split(";")[0].strip()
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise MediaValidationError(
            f"Invalid file content type '{content_type}'. Must be JPEG, PNG, WebP, or GIF."
        )

    # Check file size by seeking to end
    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)

    if size <= 0:
        raise MediaValidationError("The uploaded file is empty.")

    if size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024 * 1024)
        actual_mb = round(size / (1024 * 1024), 2)
        raise MediaValidationError(
            f"File size exceeds the {max_mb} MB limit (uploaded file is {actual_mb} MB)."
        )

    # Deep magic-bytes verification
    header = stream.read(512)
    stream.seek(0)

    detected_format = detect_image_format_from_bytes(header)
    if not detected_format:
        raise MediaValidationError(
            "File signature verification failed: the file content does not match a valid JPG, PNG, WebP, or GIF image."
        )

    return detected_format


def configure_cloudinary() -> None:
    """Ensure Cloudinary SDK is initialized with environment credentials."""
    cloud_name = None
    api_key = None
    api_secret = None

    if current_app:
        cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
        api_key = current_app.config.get("CLOUDINARY_API_KEY")
        api_secret = current_app.config.get("CLOUDINARY_API_SECRET")

    cloud_name = cloud_name or os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = api_key or os.getenv("CLOUDINARY_API_KEY")
    api_secret = api_secret or os.getenv("CLOUDINARY_API_SECRET")

    if not all([cloud_name, api_key, api_secret]):
        raise CloudinaryUploadError(
            "Cloudinary credentials (CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET) "
            "are not fully configured."
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )


def upload_image_to_cloudinary(
    file_storage: FileStorage,
    folder: str = "factbox/portfolio",
) -> Dict[str, Any]:
    """Validate and upload an image to Cloudinary.

    Returns dict containing public_id, secure_url, width, height, format, and bytes.
    """
    validate_image_file(file_storage)
    configure_cloudinary()

    try:
        file_storage.stream.seek(0)
        result = cloudinary.uploader.upload(
            file_storage.stream,
            folder=folder,
            resource_type="image",
            allowed_formats=["jpg", "jpeg", "png", "webp", "gif"],
            unique_filename=True,
            overwrite=False,
        )
    except Exception as e:
        logger.error(f"Cloudinary upload failed: {str(e)}")
        raise CloudinaryUploadError(f"Cloudinary upload failed: {str(e)}") from e

    return {
        "public_id": result["public_id"],
        "secure_url": result["secure_url"],
        "width": result.get("width"),
        "height": result.get("height"),
        "format": result.get("format"),
        "bytes": result.get("bytes"),
    }


def delete_image_from_cloudinary(public_id: str) -> bool:
    """Delete an image asset from Cloudinary.

    Safe operation: handles errors without throwing to avoid breaking calling flows.
    """
    if not public_id:
        return False

    try:
        configure_cloudinary()
        res = cloudinary.uploader.destroy(public_id, invalidate=True)
        return res.get("result") == "ok"
    except Exception as e:
        logger.warning(f"Failed to delete Cloudinary asset '{public_id}': {str(e)}")
        return False


def get_optimized_delivery_url(
    public_id: str,
    width: int | None = None,
    height: int | None = None,
    crop: str = "limit",
    quality: str = "auto",
    fetch_format: str = "auto",
) -> str:
    """Generate an optimized, responsive delivery URL with auto format and quality."""
    try:
        configure_cloudinary()
        options = {
            "secure": True,
            "quality": quality,
            "fetch_format": fetch_format,
        }
        if width:
            options["width"] = width
        if height:
            options["height"] = height
        if width or height:
            options["crop"] = crop

        url, _ = cloudinary.utils.cloudinary_url(public_id, **options)
        return url
    except Exception:
        # Fallback if unconfigured
        return f"https://res.cloudinary.com/factbox/image/upload/{public_id}"


def save_portfolio_image_safely(
    project_id: Any,
    file_storage: FileStorage,
    alt_text: str,
    caption: str | None = None,
    display_order: int = 0,
) -> PortfolioImage:
    """Upload image to Cloudinary and commit record to PostgreSQL.

    Orphan Prevention:
    If the PostgreSQL commit fails after Cloudinary upload succeeds,
    the newly created Cloudinary asset is automatically destroyed to prevent orphan storage leaks.
    """
    if not alt_text or not alt_text.strip():
        raise MediaValidationError("Alt text is required for accessibility and SEO.")

    upload_meta = upload_image_to_cloudinary(file_storage, folder="factbox/portfolio")
    public_id = upload_meta["public_id"]

    image_record = PortfolioImage(
        project_id=project_id,
        cloudinary_public_id=public_id,
        secure_url=upload_meta["secure_url"],
        alt_text=alt_text.strip(),
        caption=caption.strip() if caption else None,
        width=upload_meta.get("width"),
        height=upload_meta.get("height"),
        display_order=display_order,
    )

    db.session.add(image_record)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Clean up orphan asset immediately
        logger.error(
            f"Database commit failed for image on project {project_id}. "
            f"Rolling back and removing orphan Cloudinary asset {public_id}."
        )
        delete_image_from_cloudinary(public_id)
        raise e

    return image_record


def delete_portfolio_image_safely(image_id: Any) -> bool:
    """Delete a PortfolioImage and clean up external Cloudinary asset if unshared."""
    image_record = db.session.get(PortfolioImage, image_id)
    if not image_record:
        return False

    public_id = image_record.cloudinary_public_id

    # Check for any other records pointing to the same Cloudinary public ID
    other_references = (
        PortfolioImage.query.filter(
            PortfolioImage.id != image_record.id,
            PortfolioImage.cloudinary_public_id == public_id,
        ).count()
    )

    db.session.delete(image_record)
    db.session.commit()

    # Only destroy from Cloudinary if no other DB record references it
    if other_references == 0:
        delete_image_from_cloudinary(public_id)

    return True


def save_home_page_photo_safely(
    file_storage: FileStorage,
    alt_text: str,
    title: str | None = None,
    caption: str | None = None,
    display_order: int = 0,
    is_active: bool = True,
) -> HomePagePhoto:
    """Upload hero photo to Cloudinary and commit HomePagePhoto record to PostgreSQL.

    Orphan Prevention:
    If the PostgreSQL commit fails after Cloudinary upload succeeds,
    the newly created Cloudinary asset is automatically destroyed to prevent orphan storage leaks.
    """
    if not alt_text or not alt_text.strip():
        raise MediaValidationError("Alt text is required for accessibility and SEO.")

    upload_meta = upload_image_to_cloudinary(file_storage, folder="factbox/home_hero")
    public_id = upload_meta["public_id"]

    photo = HomePagePhoto(
        title=title.strip() if title else None,
        caption=caption.strip() if caption else None,
        cloudinary_public_id=public_id,
        secure_url=upload_meta["secure_url"],
        alt_text=alt_text.strip(),
        display_order=max(0, display_order),
        is_active=is_active,
    )

    db.session.add(photo)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(
            f"Database commit failed for HomePagePhoto. Rolling back and removing orphan Cloudinary asset {public_id}: {e}"
        )
        delete_image_from_cloudinary(public_id)
        raise e

    return photo


def delete_home_page_photo_safely(photo_id: Any) -> bool:
    """Delete a HomePagePhoto and remove its Cloudinary asset."""
    photo = db.session.get(HomePagePhoto, photo_id)
    if not photo:
        return False

    public_id = photo.cloudinary_public_id
    db.session.delete(photo)
    db.session.commit()

    if public_id:
        delete_image_from_cloudinary(public_id)

    return True


def save_partner_logo_safely(
    file_storage: FileStorage,
    name: str,
    alt_text: str,
    website_url: str | None = None,
    display_order: int = 0,
    is_published: bool = True,
) -> PartnerLogo:
    """Upload partner logo to Cloudinary and commit PartnerLogo record to PostgreSQL.

    Orphan Prevention:
    If the PostgreSQL commit fails after Cloudinary upload succeeds,
    the newly created Cloudinary asset is automatically destroyed to prevent orphan storage leaks.
    """
    if not name or not name.strip():
        raise MediaValidationError("Organization name is required.")
    if not alt_text or not alt_text.strip():
        raise MediaValidationError("Alt text is required for accessibility and SEO.")

    upload_meta = upload_image_to_cloudinary(file_storage, folder="factbox/partner_logos")
    public_id = upload_meta["public_id"]

    logo = PartnerLogo(
        name=name.strip(),
        logo_cloudinary_public_id=public_id,
        logo_secure_url=upload_meta["secure_url"],
        website_url=website_url.strip() if website_url else None,
        alt_text=alt_text.strip(),
        display_order=max(0, display_order),
        is_published=is_published,
    )

    db.session.add(logo)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(
            f"Database commit failed for PartnerLogo. Rolling back and removing orphan Cloudinary asset {public_id}: {e}"
        )
        delete_image_from_cloudinary(public_id)
        raise e

    return logo


def delete_partner_logo_safely(logo_id: Any) -> bool:
    """Delete a PartnerLogo and remove its Cloudinary asset."""
    logo = db.session.get(PartnerLogo, logo_id)
    if not logo:
        return False

    public_id = logo.logo_cloudinary_public_id
    db.session.delete(logo)
    db.session.commit()

    if public_id:
        delete_image_from_cloudinary(public_id)

    return True


