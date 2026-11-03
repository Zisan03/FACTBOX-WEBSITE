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
from app.models.tombstone import MediaDeletionTombstone

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


def count_cloudinary_references(
    public_id: str,
    exclude_home_photo_id: Any = None,
    exclude_partner_logo_id: Any = None,
    exclude_portfolio_image_id: Any = None,
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


def is_system_asset(public_id: str | None) -> bool:
    """Check if public ID belongs to curated initial showcase or partner assets."""
    if not public_id:
        return False
    return public_id in SYSTEM_SHOWCASE_PIDS or public_id in SYSTEM_PARTNER_LOGO_PIDS


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
    - Reconstructs the PostgreSQL record with its original metadata in an inactive/unpublished
      state so an administrator can review before publishing.
    - Removes the tombstone record so future seeding remains clean.
    """
    tombstone = db.session.get(MediaDeletionTombstone, tombstone_id)
    if not tombstone:
        return False, "Deletion record not found."

    asset_type = tombstone.asset_type
    data = tombstone.original_data or {}

    if asset_type == "home_page_photo":
        pid = tombstone.cloudinary_public_id or data.get("cloudinary_public_id")
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
        )
        db.session.add(photo)
        db.session.delete(tombstone)
        db.session.commit()
        return True, f"Photo '{photo.title or photo.alt_text}' was successfully restored to the reserve pool."

    elif asset_type == "partner_logo":
        pid = tombstone.cloudinary_public_id or data.get("logo_cloudinary_public_id")
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
        )
        db.session.add(logo)
        db.session.delete(tombstone)
        db.session.commit()
        return True, f"Partner logo '{logo.name}' was successfully restored (unpublished)."

    return False, f"Unknown asset type '{asset_type}'."



