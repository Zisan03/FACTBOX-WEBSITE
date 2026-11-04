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
from app.models.portfolio import PortfolioImage, PortfolioVideo, PortfolioProject
from app.models.home_photo import HomePagePhoto
from app.models.content import PartnerLogo
from app.models.media import WebsiteMedia
from app.models.tombstone import MediaDeletionTombstone

logger = logging.getLogger(__name__)

# Enforce upload limits matching Cloudinary Free tier allocation
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB for images
MAX_VIDEO_FILE_SIZE = 50 * 1024 * 1024  # 50 MB for videos

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/pjpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
ALLOWED_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
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


def validate_video_file(file_storage: FileStorage) -> str:
    """Validate uploaded video file size, extension, and content type.

    Returns the detected format string ('mp4', 'webm', or 'mov').
    Raises MediaValidationError on validation failure.
    """
    if not file_storage or not file_storage.filename:
        raise MediaValidationError("No file was selected for upload.")

    filename = file_storage.filename.strip()
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise MediaValidationError(
            f"Unsupported video format '{ext}'. Allowed formats: MP4, WebM, and MOV."
        )

    content_type = (file_storage.content_type or "").lower().split(";")[0].strip()
    if content_type and content_type not in ALLOWED_VIDEO_MIME_TYPES:
        raise MediaValidationError(
            f"Invalid video content type '{content_type}'. Must be video/mp4, video/webm, or video/quicktime."
        )

    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)

    if size <= 0:
        raise MediaValidationError("The uploaded video file is empty.")

    if size > MAX_VIDEO_FILE_SIZE:
        max_mb = MAX_VIDEO_FILE_SIZE // (1024 * 1024)
        actual_mb = round(size / (1024 * 1024), 2)
        raise MediaValidationError(
            f"Video file size exceeds the {max_mb} MB limit (uploaded file is {actual_mb} MB)."
        )

    return ext.lstrip(".")


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


def upload_video_to_cloudinary(
    file_storage: FileStorage,
    folder: str = "factbox/videos",
) -> Dict[str, Any]:
    """Validate and upload a video file to Cloudinary."""
    validate_video_file(file_storage)
    configure_cloudinary()

    try:
        file_storage.stream.seek(0)
        result = cloudinary.uploader.upload(
            file_storage.stream,
            folder=folder,
            resource_type="video",
            allowed_formats=["mp4", "webm", "mov"],
            unique_filename=True,
            overwrite=False,
        )
    except Exception as e:
        logger.error(f"Cloudinary video upload failed: {str(e)}")
        raise CloudinaryUploadError(f"Cloudinary video upload failed: {str(e)}") from e

    return {
        "public_id": result["public_id"],
        "secure_url": result["secure_url"],
        "width": result.get("width"),
        "height": result.get("height"),
        "format": result.get("format"),
        "duration": result.get("duration"),
        "bytes": result.get("bytes"),
    }


def delete_image_from_cloudinary(public_id: str, resource_type: str = "image") -> bool:
    """Delete an image or video asset from Cloudinary.

    Safe operation: handles errors without throwing to avoid breaking calling flows.
    """
    if not public_id:
        return False

    try:
        configure_cloudinary()
        res = cloudinary.uploader.destroy(public_id, resource_type=resource_type, invalidate=True)
        return res.get("result") == "ok"
    except Exception as e:
        logger.warning(f"Failed to delete Cloudinary asset '{public_id}': {str(e)}")
        return False


def check_cloudinary_asset_exists(public_id: str, resource_type: str = "image") -> bool:
    """Check if an asset exists in Cloudinary storage without throwing exceptions.

    Returns True if confirmed to exist or if it is a protected system showcase asset.
    Returns False if confirmed missing or destroyed.
    """
    if not public_id:
        return False

    if is_system_asset(public_id):
        return True

    try:
        configure_cloudinary()
        import cloudinary.api
        try:
            res = cloudinary.api.resource(public_id, resource_type=resource_type)
        except Exception:
            if resource_type == "image":
                res = cloudinary.api.resource(public_id, resource_type="video")
            else:
                raise
        return bool(res and res.get("public_id"))
    except Exception as e:
        err_msg = str(e).lower()
        if "not found" in err_msg or "404" in err_msg:
            return False
        logger.warning(f"Cloudinary asset check for '{public_id}': {e}")
        if current_app and current_app.config.get("TESTING"):
            return current_app.config.get("TEST_CLOUDINARY_ASSET_EXISTS", True)
        return False


def get_optimized_delivery_url(
    public_id: str,
    width: int | None = None,
    height: int | None = None,
    crop: str = "limit",
    quality: str = "auto",
    fetch_format: str = "auto",
    resource_type: str = "image",
) -> str:
    """Generate an optimized, responsive delivery URL with auto format and quality."""
    try:
        configure_cloudinary()
        options = {
            "secure": True,
            "quality": quality,
            "fetch_format": fetch_format,
            "resource_type": resource_type,
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
        return f"https://res.cloudinary.com/factbox/{resource_type}/upload/{public_id}"


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


def delete_portfolio_image_safely(
    image_id: Any,
    admin_email: str | None = None,
    destroy_cloudinary: bool = True,
) -> bool:
    """Delete a PortfolioImage, record tombstone, and conditionally remove Cloudinary asset."""
    image_record = db.session.get(PortfolioImage, image_id)
    if not image_record:
        return False

    public_id = image_record.cloudinary_public_id
    image_title = getattr(image_record, "title", None) or image_record.alt_text

    # Snapshot metadata for deliberate restoration
    snapshot = {
        "project_id": str(image_record.project_id),
        "cloudinary_public_id": public_id,
        "title": getattr(image_record, "title", None),
        "secure_url": image_record.secure_url,
        "alt_text": image_record.alt_text,
        "caption": image_record.caption,
        "width": image_record.width,
        "height": image_record.height,
        "display_order": image_record.display_order,
    }

    tombstone = MediaDeletionTombstone(
        asset_type="portfolio_image",
        cloudinary_public_id=public_id,
        title_or_name=image_title,
        original_data=snapshot,
        deleted_by=admin_email,
        reason="Administrator media deletion",
    )
    db.session.add(tombstone)

    # Check for other records pointing to the same Cloudinary public ID
    other_references = count_cloudinary_references(public_id, exclude_portfolio_image_id=image_record.id)

    db.session.delete(image_record)
    db.session.commit()

    # Only destroy from Cloudinary if no other DB record references it and not a system asset
    if destroy_cloudinary and other_references == 0 and not is_system_asset(public_id):
        delete_image_from_cloudinary(public_id)

    return True


def delete_portfolio_video_safely(
    video_id: Any,
    admin_email: str | None = None,
) -> bool:
    """Delete a PortfolioVideo and record tombstone."""
    video_record = db.session.get(PortfolioVideo, video_id)
    if not video_record:
        return False

    snapshot = {
        "project_id": str(video_record.project_id),
        "youtube_video_id": video_record.youtube_video_id,
        "title": video_record.title,
        "display_order": video_record.display_order,
    }

    tombstone = MediaDeletionTombstone(
        asset_type="portfolio_video",
        cloudinary_public_id=None,
        title_or_name=video_record.title or video_record.youtube_video_id,
        original_data=snapshot,
        deleted_by=admin_email,
        reason="Administrator media deletion",
    )
    db.session.add(tombstone)
    db.session.delete(video_record)
    db.session.commit()
    return True


def save_website_media_safely(
    title: str,
    category: str = "brand_asset",
    file_storage: FileStorage | None = None,
    youtube_url: str | None = None,
    alt_text: str | None = None,
    caption: str | None = None,
    status: str = "unpublished",
    display_order: int = 0,
) -> WebsiteMedia:
    """Save an official brand asset, homepage video, or general website media.
    
    Orphan prevention:
    If Cloudinary upload succeeds but PostgreSQL commit fails, destroys Cloudinary asset.
    """
    if not title or not title.strip():
        raise MediaValidationError("Title is required for website media.")

    clean_title = title.strip()
    clean_cat = category.strip() if category else "brand_asset"
    public_id = None
    secure_url = None
    youtube_video_id = None
    media_type = "image"

    if youtube_url and youtube_url.strip():
        from app.services.video import extract_youtube_id
        youtube_video_id = extract_youtube_id(youtube_url)
        media_type = "video"
    elif file_storage and file_storage.filename:
        filename_lower = file_storage.filename.strip().lower()
        _, ext = os.path.splitext(filename_lower)
        is_video = ext in ALLOWED_VIDEO_EXTENSIONS or clean_cat == "homepage_video" or (file_storage.content_type or "").startswith("video/")
        if is_video:
            upload_meta = upload_video_to_cloudinary(file_storage, folder="factbox/videos")
            public_id = upload_meta["public_id"]
            secure_url = upload_meta["secure_url"]
            media_type = "video"
        else:
            folder = "factbox/brand" if clean_cat == "brand_asset" else "factbox/media"
            upload_meta = upload_image_to_cloudinary(file_storage, folder=folder)
            public_id = upload_meta["public_id"]
            secure_url = upload_meta["secure_url"]
            media_type = "image"
    else:
        raise MediaValidationError("An image/video file or YouTube video URL is required.")

    media = WebsiteMedia(
        title=clean_title,
        category=clean_cat,
        media_type=media_type,
        cloudinary_public_id=public_id,
        secure_url=secure_url,
        youtube_video_id=youtube_video_id,
        alt_text=alt_text.strip() if alt_text else clean_title,
        caption=caption.strip() if caption else None,
        status=status,
        display_order=max(0, display_order),
    )

    db.session.add(media)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        if public_id:
            logger.error(
                f"Database commit failed for WebsiteMedia. Rolling back and removing orphan Cloudinary asset {public_id}: {e}"
            )
            delete_image_from_cloudinary(public_id, resource_type=media_type)
        raise e

    return media


def delete_website_media_safely(
    media_id: Any,
    admin_email: str | None = None,
    destroy_cloudinary: bool = True,
) -> bool:
    """Delete a WebsiteMedia item, record tombstone, and conditionally remove Cloudinary asset."""
    media = db.session.get(WebsiteMedia, media_id)
    if not media:
        return False

    public_id = media.cloudinary_public_id
    media_title = media.title

    snapshot = {
        "title": media.title,
        "category": media.category,
        "media_type": media.media_type,
        "cloudinary_public_id": media.cloudinary_public_id,
        "secure_url": media.secure_url,
        "youtube_video_id": media.youtube_video_id,
        "alt_text": media.alt_text,
        "caption": media.caption,
        "status": media.status,
        "display_order": media.display_order,
    }

    tombstone = MediaDeletionTombstone(
        asset_type="website_media",
        cloudinary_public_id=public_id,
        title_or_name=media_title,
        original_data=snapshot,
        deleted_by=admin_email,
        reason="Administrator media library deletion",
    )
    db.session.add(tombstone)

    references = count_cloudinary_references(public_id, exclude_website_media_id=media.id) if public_id else 0

    db.session.delete(media)
    db.session.commit()

    if public_id and destroy_cloudinary and references == 0 and not is_system_asset(public_id):
        res_type = "video" if media.media_type == "video" else "image"
        delete_image_from_cloudinary(public_id, resource_type=res_type)

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


def count_cloudinary_references(
    public_id: str,
    exclude_home_photo_id: Any = None,
    exclude_partner_logo_id: Any = None,
    exclude_portfolio_image_id: Any = None,
    exclude_website_media_id: Any = None,
) -> int:
    """Count how many records in PostgreSQL reference this Cloudinary public ID."""
    if not public_id:
        return 0

    count = 0
    hp_q = HomePagePhoto.query.filter_by(cloudinary_public_id=public_id)
    if exclude_home_photo_id:
        hp_q = hp_q.filter(HomePagePhoto.id != exclude_home_photo_id)
    count += hp_q.count()

    pl_q = PartnerLogo.query.filter_by(logo_cloudinary_public_id=public_id)
    if exclude_partner_logo_id:
        pl_q = pl_q.filter(PartnerLogo.id != exclude_partner_logo_id)
    count += pl_q.count()

    pi_q = PortfolioImage.query.filter_by(cloudinary_public_id=public_id)
    if exclude_portfolio_image_id:
        pi_q = pi_q.filter(PortfolioImage.id != exclude_portfolio_image_id)
    count += pi_q.count()

    wm_q = WebsiteMedia.query.filter_by(cloudinary_public_id=public_id)
    if exclude_website_media_id:
        wm_q = wm_q.filter(WebsiteMedia.id != exclude_website_media_id)
    count += wm_q.count()

    return count


SYSTEM_PARTNER_LOGO_PIDS = {
    "factbox/partner_logos/gsjax2legfdz502bt23d",
    "factbox/partner_logos/g725yqqj331tkqwrr2yn",
    "factbox/partner_logos/wxxsdt6cjltdr0sua0v7",
    "factbox/partner_logos/gdxqtejvs8qkswywzvax",
    "factbox/partner_logos/pwf156ifhqoe6ckfedim",
    "factbox/partner_logos/ort5r7yhkpguiy9gpve5",
    "factbox/partner_logos/mluqwd4yhmbkdfso5zrr",
}

SYSTEM_SHOWCASE_PIDS = {
    "factbox/home_hero/vobloojextsk2ucwsmsi",
    "factbox/home_hero/emwghkdazvbdt153sfpp",
    "factbox/home_hero/i53doietpynralczswjz",
    "factbox/home_hero/xfx85kgr4mjtucwdim4b",
    "factbox/home_hero/zswgxxhygc4unwibalsy",
    "factbox/home_hero/qp8xbacdin1nyzua3ity",
    "factbox/home_hero/ei804zdxlbrymogcbyxm",
    "factbox/home_hero/ksgxefammqhfcylffoks",
    "factbox/home_hero/ltjoie8ua6cvwwzjsfi2",
    "factbox/home_hero/qn4cknhojqhqrtogicjq",
    "factbox/home_hero/smgb4jqqcx8wyafbhcwh",
    "factbox/home_hero/hb8e8lltox5qgkw41uj0",
    "factbox/home_hero/lsh4rvjzg62kntvjqw7x",
    "factbox/home_hero/oax73qwkxjsqzplsqdim",
    "factbox/home_hero/idzaqfvsccnvstyfrwmi",
    "factbox/home_hero/hcdz2x3fxtztfhkuvet9",
    "factbox/home_hero/z6nidpkdiso8ygxxpuec",
    "factbox/home_hero/ttktjsyf7j5dbnvqdyys",
    "factbox/home_hero/scpemyioaskwmoo7nlfg",
    "factbox/home_hero/no82qe6s8q6vd0uj2zfm",
    "factbox/home_hero/j5wmdstsaca2hgd2gei1",
    "factbox/home_hero/ztowroteennxanfaz77q",
    "factbox/home_hero/mwgwkyvyjkvd7ykpmd6c",
    "factbox/home_hero/ubxt7mjvtt2earl8hltp",
    "factbox/home_hero/tqybvwohve0sn6pfnkf7",
    "factbox/home_hero/ugbot3wtqah57evrqal5",
    "factbox/home_hero/ihlk1nigc6mpz6xi7uwy",
    "factbox/home_hero/xzi4oy5yyicj72zkkyuz",
    "factbox/home_hero/np4nnhd9fgskvtopvhrh",
    "factbox/home_hero/ypl01q1pytvw4uvzmgal",
    "factbox/home_hero/l0cwq2erjuufwrjruf0w",
}


SYSTEM_VIDEO_PIDS = {
    "factbox/videos/yysipv6v94ru5c4uxmpu",
}


def is_system_asset(public_id: str | None) -> bool:
    """Check if public ID belongs to curated initial showcase, partner, or video assets."""
    if not public_id:
        return False
    return (
        public_id in SYSTEM_SHOWCASE_PIDS
        or public_id in SYSTEM_PARTNER_LOGO_PIDS
        or public_id in SYSTEM_VIDEO_PIDS
    )


def delete_home_page_photo_safely(
    photo_id: Any,
    admin_email: str | None = None,
    destroy_cloudinary: bool = True,
) -> bool:
    """Delete a HomePagePhoto, create a deletion tombstone, and conditionally remove Cloudinary asset.
    
    Pillars 3 & 5 Compliance:
    - Records an immutable tombstone in media_deletion_tombstone with a full metadata snapshot.
    - Prevents deployments, restarts, and safe seed commands from resurrecting the photo.
    - Preserves system/showcase and shared Cloudinary assets so deliberate restoration remains possible.
    """
    photo = db.session.get(HomePagePhoto, photo_id)
    if not photo:
        return False

    public_id = photo.cloudinary_public_id
    photo_title = photo.title or photo.alt_text

    # 1. Snapshot metadata for deliberate restoration
    snapshot = {
        "title": photo.title,
        "caption": photo.caption,
        "cloudinary_public_id": photo.cloudinary_public_id,
        "secure_url": photo.secure_url,
        "alt_text": photo.alt_text,
        "display_order": photo.display_order,
        "is_active": photo.is_active,
    }

    # 2. Record deletion tombstone
    existing_tombstone = MediaDeletionTombstone.query.filter_by(
        asset_type="home_page_photo",
        cloudinary_public_id=public_id,
    ).first()
    if not existing_tombstone:
        tombstone = MediaDeletionTombstone(
            asset_type="home_page_photo",
            cloudinary_public_id=public_id,
            title_or_name=photo_title,
            original_data=snapshot,
            deleted_by=admin_email,
            reason="Administrator dashboard deletion",
        )
        db.session.add(tombstone)

    # 3. Check references across PostgreSQL
    references = count_cloudinary_references(public_id, exclude_home_photo_id=photo.id)

    # 4. Remove database record
    db.session.delete(photo)
    db.session.commit()

    # 5. Cloudinary asset lifecycle rules (Pillar 5):
    # Only destroy if explicitly requested AND unshared AND not a protected system showcase asset
    if destroy_cloudinary and references == 0 and not is_system_asset(public_id):
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


def delete_partner_logo_safely(
    logo_id: Any,
    admin_email: str | None = None,
    destroy_cloudinary: bool = True,
) -> bool:
    """Delete a PartnerLogo, create a deletion tombstone, and conditionally remove Cloudinary asset.
    
    Pillars 3 & 5 Compliance:
    - Records an immutable tombstone in media_deletion_tombstone with a full metadata snapshot.
    - Prevents deployments, restarts, and safe seed commands from resurrecting the logo.
    - Preserves system and shared Cloudinary assets so deliberate restoration remains possible.
    """
    logo = db.session.get(PartnerLogo, logo_id)
    if not logo:
        return False

    public_id = logo.logo_cloudinary_public_id
    logo_name = logo.name

    # 1. Snapshot metadata for deliberate restoration
    snapshot = {
        "name": logo.name,
        "logo_cloudinary_public_id": logo.logo_cloudinary_public_id,
        "logo_secure_url": logo.logo_secure_url,
        "website_url": logo.website_url,
        "alt_text": logo.alt_text,
        "display_order": logo.display_order,
        "is_published": logo.is_published,
    }

    # 2. Record deletion tombstone
    existing_tombstone = MediaDeletionTombstone.query.filter_by(
        asset_type="partner_logo",
        cloudinary_public_id=public_id,
    ).first()
    if not existing_tombstone:
        tombstone = MediaDeletionTombstone(
            asset_type="partner_logo",
            cloudinary_public_id=public_id,
            title_or_name=logo_name,
            original_data=snapshot,
            deleted_by=admin_email,
            reason="Administrator dashboard deletion",
        )
        db.session.add(tombstone)

    # 3. Check references across PostgreSQL
    references = count_cloudinary_references(public_id, exclude_partner_logo_id=logo.id)

    # 4. Remove database record
    db.session.delete(logo)
    db.session.commit()

    # 5. Cloudinary asset lifecycle rules (Pillar 5):
    if destroy_cloudinary and references == 0 and not is_system_asset(public_id):
        delete_image_from_cloudinary(public_id)

    return True


def restore_deleted_media(tombstone_id: Any) -> Tuple[bool, str]:
    """Restore a previously deleted media item from its tombstone record.
    
    Pillars 3 & 8 Compliance:
    - Verifies that the underlying Cloudinary asset exists before reporting successful restoration.
    - If Cloudinary asset no longer exists, rejects restoration with clear error.
    - Reconstructs the PostgreSQL record with its original metadata in an inactive/unpublished
      state so an administrator can review before publishing.
    - Removes the tombstone record so future seeding remains clean.
    """
    tombstone = db.session.get(MediaDeletionTombstone, tombstone_id)
    if not tombstone:
        return False, "Deletion record not found."

    asset_type = tombstone.asset_type
    data = tombstone.original_data or {}
    pid = tombstone.cloudinary_public_id or data.get("cloudinary_public_id") or data.get("logo_cloudinary_public_id")

    # If it is a Cloudinary asset, verify it still exists before attempting restoration!
    res_type = "video" if data.get("media_type") == "video" else "image"
    if pid and not check_cloudinary_asset_exists(pid, resource_type=res_type):
        return False, f"Cannot restore '{tombstone.title_or_name}': The original file is no longer available in Cloudinary storage."

    if asset_type == "home_page_photo":
        existing = HomePagePhoto.query.filter_by(cloudinary_public_id=pid).first()
        if existing:
            db.session.delete(tombstone)
            db.session.commit()
            return True, f"Photo '{existing.title or existing.alt_text}' is already present in the library."

        photo = HomePagePhoto(
            title=data.get("title") or tombstone.title_or_name,
            caption=data.get("caption"),
            cloudinary_public_id=pid,
            secure_url=data.get("secure_url"),
            alt_text=data.get("alt_text") or "Restored documentary photo",
            display_order=data.get("display_order", 0),
            is_active=False,  # Restored as reserve/inactive for safety
            is_archived=False,
        )
        db.session.add(photo)
        db.session.delete(tombstone)
        db.session.commit()
        return True, f"Photo '{photo.title or photo.alt_text}' was successfully restored to the reserve pool."

    elif asset_type == "partner_logo":
        existing = PartnerLogo.query.filter_by(logo_cloudinary_public_id=pid).first()
        if existing:
            db.session.delete(tombstone)
            db.session.commit()
            return True, f"Partner logo '{existing.name}' is already present in the library."

        logo = PartnerLogo(
            name=data.get("name") or tombstone.title_or_name,
            logo_cloudinary_public_id=pid,
            logo_secure_url=data.get("logo_secure_url"),
            website_url=data.get("website_url"),
            alt_text=data.get("alt_text") or "Restored partner logo",
            display_order=data.get("display_order", 0),
            is_published=False,  # Restored as unpublished for safety
            is_archived=False,
        )
        db.session.add(logo)
        db.session.delete(tombstone)
        db.session.commit()
        return True, f"Partner logo '{logo.name}' was successfully restored (unpublished)."

    elif asset_type == "website_media":
        if pid:
            existing = WebsiteMedia.query.filter_by(cloudinary_public_id=pid).first()
            if existing:
                db.session.delete(tombstone)
                db.session.commit()
                return True, f"Media '{existing.title}' is already present in the library."

        media = WebsiteMedia(
            title=data.get("title") or tombstone.title_or_name or "Restored Website Media",
            category=data.get("category", "brand_asset"),
            media_type=data.get("media_type", "image"),
            cloudinary_public_id=pid,
            secure_url=data.get("secure_url"),
            youtube_video_id=data.get("youtube_video_id"),
            alt_text=data.get("alt_text") or "Restored website media",
            caption=data.get("caption"),
            status="unpublished",
            display_order=data.get("display_order", 0),
        )
        db.session.add(media)
        db.session.delete(tombstone)
        db.session.commit()
        return True, f"Media '{media.title}' was successfully restored (unpublished)."

    elif asset_type == "portfolio_image":
        import uuid
        project_id_raw = data.get("project_id")
        project = None
        if project_id_raw:
            try:
                project = db.session.get(PortfolioProject, uuid.UUID(str(project_id_raw)))
            except Exception:
                project = None
        if not project:
            project = PortfolioProject.query.first()

        if not project:
            return False, f"Cannot restore image '{tombstone.title_or_name}': Associated project no longer exists."

        existing = PortfolioImage.query.filter_by(cloudinary_public_id=pid).first()
        if existing:
            db.session.delete(tombstone)
            db.session.commit()
            return True, f"Portfolio image '{tombstone.title_or_name}' is already present in the library."

        image = PortfolioImage(
            project_id=project.id,
            cloudinary_public_id=pid,
            title=data.get("title"),
            secure_url=data.get("secure_url"),
            alt_text=data.get("alt_text") or "Restored portfolio image",
            caption=data.get("caption"),
            width=data.get("width"),
            height=data.get("height"),
            display_order=data.get("display_order", 0),
            is_archived=False,
        )
        db.session.add(image)
        db.session.delete(tombstone)
        db.session.commit()
        return True, f"Portfolio image '{image.alt_text}' was successfully restored to project '{project.title}'."

    elif asset_type == "portfolio_video":
        import uuid
        project_id_raw = data.get("project_id")
        project = None
        if project_id_raw:
            try:
                project = db.session.get(PortfolioProject, uuid.UUID(str(project_id_raw)))
            except Exception:
                project = None
        if not project:
            project = PortfolioProject.query.first()

        if not project:
            return False, f"Cannot restore video: Associated project no longer exists."

        yt_id = data.get("youtube_video_id")
        video = PortfolioVideo(
            project_id=project.id,
            youtube_video_id=yt_id,
            title=data.get("title") or tombstone.title_or_name,
            display_order=data.get("display_order", 0),
            is_archived=False,
        )
        db.session.add(video)
        db.session.delete(tombstone)
        db.session.commit()
        return True, f"Portfolio video '{video.title or yt_id}' was successfully restored to project '{project.title}'."

    return False, f"Unknown asset type '{asset_type}'."


# ============================================================================
# Canonical Curated Homepage Video Asset (Single Source of Truth)
# ============================================================================

CURATED_HOMEPAGE_VIDEO = {
    "title": "Strategic Storytelling Documentary Reel",
    "category": "homepage_video",
    "media_type": "video",
    "cloudinary_public_id": "factbox/videos/yysipv6v94ru5c4uxmpu",
    "secure_url": "https://res.cloudinary.com/qvv0ipup/video/upload/v1793829178/factbox/videos/yysipv6v94ru5c4uxmpu.mp4",
    "alt_text": "Fact Box Consult documentary storytelling and cinematic field production video",
    "caption": "34-second cinematic documentary highlight showcasing high-impact storytelling, community fieldwork, and audiovisual advocacy across West Africa.",
    "status": "active",
    "display_order": 1,
}


def sync_curated_homepage_video(admin_email: str | None = None, force_restore: bool = False) -> Tuple[bool, str]:
    """Register or synchronize the canonical 34-second Strategic Storytelling homepage video.

    Single source of truth for the curated homepage video asset.
    - Consults media_deletion_tombstone before adding records; respects administrator deletions.
    - Idempotent: safe to run repeatedly; preserves existing record without duplicates.
    - Activates existing record if it was inactive or category/url drifted.
    - Safe error handling with rollback on failure.
    """
    video_pid = CURATED_HOMEPAGE_VIDEO["cloudinary_public_id"]
    video_title = CURATED_HOMEPAGE_VIDEO["title"]
    video_url = CURATED_HOMEPAGE_VIDEO["secure_url"]

    # 1. Check deletion tombstones
    tombstone = MediaDeletionTombstone.query.filter_by(
        asset_type="website_media"
    ).filter(
        (MediaDeletionTombstone.cloudinary_public_id == video_pid)
        | (MediaDeletionTombstone.title_or_name == video_title)
    ).first()

    if tombstone:
        if not force_restore:
            return (
                False,
                f"[SKIPPED - DELETED BY ADMIN] Homepage video '{video_title}' ({video_pid}) is protected by an administrator deletion tombstone.",
            )
        else:
            db.session.delete(tombstone)
            db.session.flush()

    # 2. Check if already exists
    existing = WebsiteMedia.query.filter(
        (WebsiteMedia.cloudinary_public_id == video_pid)
        | (WebsiteMedia.title == video_title)
    ).first()

    if existing:
        existing.category = CURATED_HOMEPAGE_VIDEO["category"]
        existing.media_type = CURATED_HOMEPAGE_VIDEO["media_type"]
        existing.cloudinary_public_id = video_pid
        existing.secure_url = video_url
        if existing.status != "active":
            existing.status = "active"
        try:
            db.session.commit()
            return True, f"Homepage video '{existing.title}' is already registered and active."
        except Exception as e:
            db.session.rollback()
            logger.exception("Failed to update existing homepage video: %s", e)
            return False, f"Database error updating homepage video: {e}"

    # 3. Create new WebsiteMedia record
    video_record = WebsiteMedia(
        title=video_title,
        category=CURATED_HOMEPAGE_VIDEO["category"],
        media_type=CURATED_HOMEPAGE_VIDEO["media_type"],
        cloudinary_public_id=video_pid,
        secure_url=video_url,
        alt_text=CURATED_HOMEPAGE_VIDEO["alt_text"],
        caption=CURATED_HOMEPAGE_VIDEO["caption"],
        status=CURATED_HOMEPAGE_VIDEO["status"],
        display_order=CURATED_HOMEPAGE_VIDEO["display_order"],
    )
    db.session.add(video_record)
    try:
        db.session.commit()
        return True, f"Homepage video '{video_title}' registered successfully in Central Media Library."
    except Exception as e:
        db.session.rollback()
        logger.exception("Failed to insert curated homepage video: %s", e)
        return False, f"Database error registering homepage video: {e}"
