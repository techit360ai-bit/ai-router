"""Security boundaries for private founder uploads."""

from __future__ import annotations

import pytest

from file_storage import FileStorageService, FileValidationError, MAX_UPLOAD_BYTES


def test_upload_validation_rejects_empty_oversized_and_executable_files() -> None:
    with pytest.raises(FileValidationError, match="empty"):
        FileStorageService.validate_upload(b"", "idea.pdf", "application/pdf")
    with pytest.raises(FileValidationError, match="exceeds"):
        FileStorageService.validate_upload(b"x" * (MAX_UPLOAD_BYTES + 1), "idea.pdf", "application/pdf")
    with pytest.raises(FileValidationError, match="not allowed"):
        FileStorageService.validate_upload(b"binary", "payload.exe", "application/octet-stream")


def test_document_upload_rejects_images() -> None:
    with pytest.raises(FileValidationError, match="not allowed"):
        FileStorageService.validate_upload(b"image", "pitch.png", "image/png", document_only=True)


def test_upload_validation_rejects_mismatched_or_spoofed_content() -> None:
    with pytest.raises(FileValidationError, match="do not match"):
        FileStorageService.validate_upload(b"plain text", "idea.pdf", "text/plain")
    with pytest.raises(FileValidationError, match="signature"):
        FileStorageService.validate_upload(b"not really a PDF", "idea.pdf", "application/pdf")
    FileStorageService.validate_upload(b"%PDF-1.7\n", "idea.pdf", "application/pdf")
