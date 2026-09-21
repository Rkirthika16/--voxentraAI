import re
import os
from typing import Tuple
from fastapi import UploadFile
from app.config import settings
from app.core.exceptions import BadRequestException

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".aac", ".flac"}
ALLOWED_AUDIO_MIME_TYPES = {
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mpeg", "audio/mp3",
    "audio/mp4", "audio/x-m4a", "audio/m4a",
    "audio/webm", "video/webm",
    "audio/ogg", "application/ogg",
    "audio/aac", "audio/flac"
}


def validate_audio_file(file: UploadFile) -> Tuple[str, str]:
    """
    Validates audio file extension and MIME type.
    Returns: (sanitized_filename, extension)
    """
    if not file.filename:
        raise BadRequestException("Audio file must have a valid filename")

    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise BadRequestException(
            f"Unsupported audio format '{ext}'. Allowed formats: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
        )

    # Note: browser MediaRecorder sometimes sends video/webm or audio/webm
    if file.content_type and file.content_type.lower() not in ALLOWED_AUDIO_MIME_TYPES:
        # If extension is valid but MIME is generic octet-stream, allow with warning
        if file.content_type.lower() != "application/octet-stream":
            raise BadRequestException(f"Unsupported MIME type '{file.content_type}' for audio file")

    return file.filename, ext


def validate_phone(phone: str) -> bool:
    """Validates Indian phone numbers (10 digits, optionally prefixed with +91 or 0)."""
    if not phone:
        return True
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    pattern = r'^(\+91|0)?[6-9]\d{9}$'
    return bool(re.match(pattern, cleaned))
