"""Tests for Cloudinary media upload and asset management service.

Enforces ADR-004, ADR-007, and DATABASE_SCHEMA.md:
- Server-side format and magic-bytes validation (JPG, PNG, WebP)
- 10 MB maximum upload size enforcement
- Rejection of malicious, empty, or disguised files
- Cloudinary server-side upload adapter
- Safe rollback and orphan asset cleanup on database failure
"""
import io
import pytest
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage

from app.services.media import (
    validate_image_file,
    detect_image_format_from_bytes,
    save_portfolio_image_safely,
    delete_portfolio_image_safely,
    MediaValidationError,
    CloudinaryUploadError,
    MAX_FILE_SIZE,
)
from app.models.portfolio import PortfolioCategory, PortfolioProject, PortfolioImage


# Sample valid image byte headers
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 100
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 100
VALID_WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 100


def create_file_storage(data: bytes, filename: str, content_type: str = "image/jpeg") -> FileStorage:
    """Helper to generate a mock FileStorage object."""
    stream = io.BytesIO(data)
    return FileStorage(stream=stream, filename=filename, content_type=content_type)


def test_magic_bytes_detection():
    """Verify binary magic byte detection for JPG, PNG, and WebP."""
    assert detect_image_format_from_bytes(VALID_JPEG_BYTES) == "jpg"
    assert detect_image_format_from_bytes(VALID_PNG_BYTES) == "png"
    assert detect_image_format_from_bytes(VALID_WEBP_BYTES) == "webp"
    assert detect_image_format_from_bytes(b"MZ\x90\x00\x03\x00\x00\x00") is None  # EXE header
    assert detect_image_format_from_bytes(b"%PDF-1.5\n") is None  # PDF header


def test_validate_image_file_valid_jpeg():
    """Verify valid JPEG file passes validation."""
    file = create_file_storage(VALID_JPEG_BYTES, "test_photo.jpg", "image/jpeg")
    assert validate_image_file(file) == "jpg"


def test_validate_image_file_valid_png():
    """Verify valid PNG file passes validation."""
    file = create_file_storage(VALID_PNG_BYTES, "graphic.png", "image/png")
    assert validate_image_file(file) == "png"


def test_validate_image_file_valid_webp():
    """Verify valid WebP file passes validation."""
    file = create_file_storage(VALID_WEBP_BYTES, "optimized.webp", "image/webp")
    assert validate_image_file(file) == "webp"


def test_validate_image_rejects_unsupported_extension():
    """Verify files with prohibited extensions are rejected."""
    bad_files = [
        ("document.pdf", b"%PDF-1.5\n" + b"\x00" * 100, "application/pdf"),
        ("script.exe", b"MZ\x90\x00" + b"\x00" * 100, "application/x-msdownload"),
        ("vector.svg", b"<svg></svg>", "image/svg+xml"),
    ]
    for filename, content, ctype in bad_files:
        file = create_file_storage(content, filename, ctype)
        with pytest.raises(MediaValidationError, match="Unsupported file format"):
            validate_image_file(file)


def test_validate_image_rejects_disguised_file():
    """Verify file with .jpg extension but text/executable content is rejected by magic bytes."""
    fake_jpg = create_file_storage(
        b"<html><script>alert('malicious')</script></html>",
        "avatar.jpg",
        "image/jpeg",
    )
    with pytest.raises(MediaValidationError, match="File signature verification failed"):
        validate_image_file(fake_jpg)


def test_validate_image_rejects_empty_file():
    """Verify empty file is rejected."""
    empty_file = create_file_storage(b"", "empty.jpg", "image/jpeg")
    with pytest.raises(MediaValidationError, match="The uploaded file is empty"):
        validate_image_file(empty_file)


def test_validate_image_rejects_oversized_file():
    """Verify file exceeding the 10 MB limit is rejected."""
    # Create stream that reports size > MAX_FILE_SIZE
    large_stream = io.BytesIO(VALID_JPEG_BYTES)
    # Seek trick: seek to size beyond limit
    file = FileStorage(stream=large_stream, filename="huge.jpg", content_type="image/jpeg")
    with patch.object(large_stream, "tell", return_value=MAX_FILE_SIZE + 1024):
        with pytest.raises(MediaValidationError, match="exceeds the 10 MB limit"):
            validate_image_file(file)


def test_save_portfolio_image_safely_success(app, db_session):
    """Verify successful Cloudinary upload and database record creation."""
    with app.app_context():
        # Setup category and project
        category = PortfolioCategory(name="Test Category", slug="test-cat")
        db_session.add(category)
        db_session.flush()

        project = PortfolioProject(
            title="Upload Test Project",
            slug="upload-test-proj",
            summary="Test summary",
            description="Test description",
            category_id=category.id,
        )
        db_session.add(project)
        db_session.commit()

        file = create_file_storage(VALID_JPEG_BYTES, "sample.jpg", "image/jpeg")

        mock_cloudinary_result = {
            "public_id": "factbox/portfolio/test_asset_123",
            "secure_url": "https://res.cloudinary.com/factbox/image/upload/v1234/factbox/portfolio/test_asset_123.jpg",
            "width": 1920,
            "height": 1080,
            "format": "jpg",
            "bytes": len(VALID_JPEG_BYTES),
        }

        with patch("app.services.media.configure_cloudinary"):
            with patch("cloudinary.uploader.upload", return_value=mock_cloudinary_result):
                image = save_portfolio_image_safely(
                    project_id=project.id,
                    file_storage=file,
                    alt_text="Documentary scene in rural community",
                    caption="Field recording session",
                    display_order=1,
                )

                assert image.id is not None
                assert image.cloudinary_public_id == "factbox/portfolio/test_asset_123"
                assert image.alt_text == "Documentary scene in rural community"
                assert image.caption == "Field recording session"
                assert image.width == 1920
                assert image.height == 1080
                assert image.display_order == 1


def test_save_portfolio_image_orphan_cleanup_on_db_failure(app, db_session):
    """Verify orphan asset is cleaned from Cloudinary if database commit fails."""
    with app.app_context():
        category = PortfolioCategory(name="Fail Category", slug="fail-cat")
        db_session.add(category)
        db_session.flush()

        project = PortfolioProject(
            title="Fail Project",
            slug="fail-project",
            summary="Fail summary",
            description="Fail description",
            category_id=category.id,
        )
        db_session.add(project)
        db_session.commit()

        file = create_file_storage(VALID_JPEG_BYTES, "sample.jpg", "image/jpeg")

        mock_cloudinary_result = {
            "public_id": "factbox/portfolio/orphan_to_cleanup",
            "secure_url": "https://res.cloudinary.com/factbox/image/upload/orphan.jpg",
            "width": 800,
            "height": 600,
            "format": "jpg",
            "bytes": 500,
        }

        with patch("app.services.media.configure_cloudinary"):
            with patch("cloudinary.uploader.upload", return_value=mock_cloudinary_result):
                with patch("app.services.media.delete_image_from_cloudinary") as mock_delete:
                    # Force DB commit to fail
                    with patch.object(db_session, "commit", side_effect=RuntimeError("Simulated DB Disk Full")):
                        with pytest.raises(RuntimeError, match="Simulated DB Disk Full"):
                            save_portfolio_image_safely(
                                project_id=project.id,
                                file_storage=file,
                                alt_text="Alt text",
                            )

                        # Verify orphan asset cleanup was executed!
                        mock_delete.assert_called_once_with("factbox/portfolio/orphan_to_cleanup")


def test_delete_portfolio_image_safely(app, db_session):
    """Verify deleting a PortfolioImage deletes the DB record and purges Cloudinary asset."""
    with app.app_context():
        category = PortfolioCategory(name="Del Category", slug="del-cat")
        db_session.add(category)
        db_session.flush()

        project = PortfolioProject(
            title="Del Project",
            slug="del-project",
            summary="Summary",
            description="Description",
            category_id=category.id,
        )
        db_session.add(project)
        db_session.flush()

        image = PortfolioImage(
            project_id=project.id,
            cloudinary_public_id="factbox/portfolio/image_to_delete",
            secure_url="https://res.cloudinary.com/factbox/image/upload/sample.jpg",
            alt_text="Alt text",
            display_order=0,
        )
        db_session.add(image)
        db_session.commit()

        image_id = image.id

        with patch("app.services.media.delete_image_from_cloudinary") as mock_delete:
            success = delete_portfolio_image_safely(image_id)
            assert success is True
            # Database record removed
            assert db_session.get(PortfolioImage, image_id) is None
            # Cloudinary cleanup called
            mock_delete.assert_called_once_with("factbox/portfolio/image_to_delete")
