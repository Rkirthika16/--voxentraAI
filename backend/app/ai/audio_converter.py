import os
import shutil
import subprocess
import logging
import tempfile
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger("voxentra.audio_converter")

# Error Codes
MICROPHONE_DENIED = "MICROPHONE_DENIED"
RECORDING_FAILED = "RECORDING_FAILED"
EMPTY_AUDIO = "EMPTY_AUDIO"
INVALID_AUDIO = "INVALID_AUDIO"
AUDIO_TOO_LARGE = "AUDIO_TOO_LARGE"
FFMPEG_NOT_FOUND = "FFMPEG_NOT_FOUND"
AUDIO_CONVERSION_FAILED = "AUDIO_CONVERSION_FAILED"
WHISPER_UNAVAILABLE = "WHISPER_UNAVAILABLE"
TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
EMPTY_TRANSCRIPTION = "EMPTY_TRANSCRIPTION"
LANGUAGE_DETECTION_FAILED = "LANGUAGE_DETECTION_FAILED"
TTS_FAILED = "TTS_FAILED"
SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
SESSION_EXPIRED = "SESSION_EXPIRED"
BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"

# Limits
MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # 25MB
MIN_AUDIO_SIZE_BYTES = 200  # 200 bytes


def check_ffmpeg_available() -> bool:
    """Checks if ffmpeg executable is available on system PATH."""
    return shutil.which("ffmpeg") is not None


def convert_audio_to_16k_mono_wav(
    input_path: str,
    output_path: Optional[str] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Converts any input audio file (WebM, Opus, Ogg, MP3, WAV, etc.)
    to standard 16 kHz Mono 16-bit PCM WAV for optimal Whisper speech recognition.

    Returns:
        (success: bool, output_wav_path: str, error_code: Optional[str])
    """
    if not os.path.exists(input_path):
        return False, "", "FILE_NOT_FOUND"

    file_size = os.path.getsize(input_path)
    if file_size < MIN_AUDIO_SIZE_BYTES:
        logger.warning(f"Audio file is too small ({file_size} bytes): {input_path}")
        return False, "", EMPTY_AUDIO

    if file_size > MAX_AUDIO_SIZE_BYTES:
        logger.warning(f"Audio file exceeds size limit ({file_size} bytes): {input_path}")
        return False, "", AUDIO_TOO_LARGE

    if not output_path:
        out_fd, output_path = tempfile.mkstemp(suffix="_16k_mono.wav")
        os.close(out_fd)

    if not check_ffmpeg_available():
        logger.warning("FFmpeg not found on system PATH. Attempting direct file pass-through if already WAV.")
        if input_path.lower().endswith(".wav"):
            shutil.copyfile(input_path, output_path)
            return True, output_path, None
        return False, "", FFMPEG_NOT_FOUND

    try:
        # ffmpeg -y -i <input> -ac 1 -ar 16000 -c:a pcm_s16le <output>
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-ac", "1",
            "-ar", "16000",
            "-c:a", "pcm_s16le",
            output_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if res.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {res.stderr.decode('utf-8', errors='ignore')}")
            return False, "", AUDIO_CONVERSION_FAILED

        if not os.path.exists(output_path) or os.path.getsize(output_path) < MIN_AUDIO_SIZE_BYTES:
            return False, "", EMPTY_AUDIO

        return True, output_path, None
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg conversion timed out.")
        return False, "", AUDIO_CONVERSION_FAILED
    except Exception as e:
        logger.error(f"Exception during FFmpeg conversion: {e}")
        return False, "", AUDIO_CONVERSION_FAILED
