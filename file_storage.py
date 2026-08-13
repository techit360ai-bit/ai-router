"""
File storage service with S3-compatible upload and text extraction.

Uses environment variables for credentials — defaults to local mode with test values.
Replace AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY with real credentials in production.
"""
import os
import hashlib
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "techit-dev-uploads")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "test-access-key")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test-secret-key")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT", "http://localhost:9000")

LOCAL_UPLOAD_DIR = Path("/tmp/techit-uploads")
IS_LOCAL_MODE = AWS_ACCESS_KEY_ID == "test-access-key"
MAX_UPLOAD_BYTES = max(1, int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))))
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_CONTENT_TYPES = {
    "text/plain", "text/markdown", "text/csv", "application/pdf",
    "image/png", "image/jpeg", "image/webp", "application/octet-stream",
}
EXTENSION_CONTENT_TYPES = {
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/plain", "text/markdown", "application/octet-stream"},
    ".csv": {"text/plain", "text/csv", "application/octet-stream"},
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".png": {"image/png", "application/octet-stream"},
    ".jpg": {"image/jpeg", "application/octet-stream"},
    ".jpeg": {"image/jpeg", "application/octet-stream"},
    ".webp": {"image/webp", "application/octet-stream"},
}


class FileValidationError(ValueError):
    pass


class FileStorageService:
    def __init__(self):
        environment = os.getenv("ENVIRONMENT", "development").strip().lower()
        if environment in {"production", "staging"} and IS_LOCAL_MODE:
            raise RuntimeError("Private object storage credentials are required outside development")
        if IS_LOCAL_MODE:
            logger.warning(
                "FileStorage running in LOCAL MODE — replace credentials for production"
            )
            LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            self._client = None
        else:
            try:
                import boto3
                self._client = boto3.client(
                    "s3",
                    aws_access_key_id=AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                    region_name=AWS_REGION,
                    endpoint_url=AWS_S3_ENDPOINT if "localhost" in AWS_S3_ENDPOINT else None,
                )
            except ImportError:
                if environment in {"production", "staging"}:
                    raise RuntimeError("boto3 is required for production file storage")
                logger.warning("boto3 not installed — falling back to local storage")
                self._client = None

    @staticmethod
    def validate_upload(file_bytes: bytes, filename: str, content_type: str, *, document_only: bool = False) -> None:
        if not file_bytes:
            raise FileValidationError("File is empty")
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise FileValidationError(f"File exceeds the {MAX_UPLOAD_BYTES} byte upload limit")
        if not filename or len(filename) > 255 or re.search(r"[\x00-\x1f]", filename):
            raise FileValidationError("Filename is invalid")
        extension = Path(filename).suffix.lower()
        allowed = {".txt", ".md", ".csv", ".pdf"} if document_only else ALLOWED_EXTENSIONS
        if extension not in allowed:
            raise FileValidationError("File type is not allowed")
        normalized_content_type = content_type.split(";", 1)[0].lower()
        if normalized_content_type not in ALLOWED_CONTENT_TYPES:
            raise FileValidationError("Content type is not allowed")
        if normalized_content_type not in EXTENSION_CONTENT_TYPES[extension]:
            raise FileValidationError("File extension and content type do not match")
        if extension == ".pdf" and not file_bytes.startswith(b"%PDF-"):
            raise FileValidationError("PDF signature is invalid")
        if extension == ".png" and not file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise FileValidationError("PNG signature is invalid")
        if extension in {".jpg", ".jpeg"} and not file_bytes.startswith(b"\xff\xd8\xff"):
            raise FileValidationError("JPEG signature is invalid")
        if extension == ".webp" and not (file_bytes.startswith(b"RIFF") and file_bytes[8:12] == b"WEBP"):
            raise FileValidationError("WebP signature is invalid")

    def _file_key(self, filename: str) -> str:
        name_hash = hashlib.sha256(f"{filename}-{os.urandom(8).hex()}".encode()).hexdigest()[:16]
        ext = Path(filename).suffix
        return f"uploads/{name_hash}{ext}"

    def upload_file(self, file_bytes: bytes, filename: str, content_type: str) -> dict:
        key = self._file_key(filename)

        if self._client and not IS_LOCAL_MODE:
            self._client.put_object(
                Bucket=AWS_S3_BUCKET,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
                ServerSideEncryption=os.getenv("AWS_S3_SERVER_SIDE_ENCRYPTION", "AES256"),
            )
            # Keep private objects private. URLs are signed only when an
            # authenticated download is explicitly requested.
            url = self.generate_presigned_url(key, int(os.getenv("UPLOAD_URL_TTL_SECONDS", "900")))
        else:
            local_path = LOCAL_UPLOAD_DIR / key.replace("/", "_")
            local_path.write_bytes(file_bytes)
            url = f"file://{local_path}"

        return {
            "url": url,
            "key": key,
            "size": len(file_bytes),
            "content_type": content_type,
            "filename": filename,
        }

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        if self._client and not IS_LOCAL_MODE:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": AWS_S3_BUCKET, "Key": key},
                ExpiresIn=expires_in,
            )
        local_path = LOCAL_UPLOAD_DIR / key.replace("/", "_")
        return f"file://{local_path}"

    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        ext = Path(filename).suffix.lower()

        if ext in (".txt", ".md", ".csv"):
            try:
                return file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return file_bytes.decode("latin-1", errors="replace")

        if ext == ".pdf":
            try:
                from pypdf import PdfReader
                import io
                reader = PdfReader(io.BytesIO(file_bytes))
                text_parts = []
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text_parts.append(extracted)
                return "\n".join(text_parts)
            except ImportError:
                logger.warning("pypdf not installed — cannot extract PDF text")
                return ""
            except Exception as e:
                logger.warning(f"PDF extraction failed: {e}")
                return ""

        return ""


file_storage = FileStorageService()
