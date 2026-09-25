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
    "audio/ogg", "application/ogg", "video/ogg",
    "audio/aac", "audio/flac", "application/octet-stream"
}


def validate_audio_file(file: UploadFile) -> Tuple[str, str]:
    """
    Validates audio file extension and MIME type.
    Supports browser MediaRecorder codecs (e.g. audio/webm;codecs=opus).
    Returns: (sanitized_filename, extension)
    """
    if not file.filename:
        raise BadRequestException("Audio file must have a valid filename")

    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise BadRequestException(
            f"Unsupported audio format '{ext}'. Allowed formats: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
        )

    # Note: browser MediaRecorder sends headers like 'audio/webm;codecs=opus' or 'video/webm'
    if file.content_type:
        base_mime = file.content_type.split(";")[0].strip().lower()
        if base_mime not in ALLOWED_AUDIO_MIME_TYPES and not base_mime.startswith("audio/"):
            raise BadRequestException(f"Unsupported MIME type '{file.content_type}' for audio file")

    return file.filename, ext



def validate_phone(phone: str) -> bool:
    """Validates Indian phone numbers (10 digits, optionally prefixed with +91 or 0)."""
    if not phone:
        return True
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    pattern = r'^(\+91|0)?[6-9]\d{9}$'
    return bool(re.match(pattern, cleaned))
