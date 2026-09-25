import os
import shutil
import subprocess
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("voxentra.audio_utils")


def is_ffmpeg_installed() -> bool:
    """Checks whether ffmpeg binary is accessible in PATH."""
    return shutil.which("ffmpeg") is not None


def convert_audio_to_wav_16k(input_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Converts any webm, opus, ogg, mp3 audio file into a 16kHz Mono 16-bit PCM WAV
    ideal for Whisper speech recognition.
    """
    if not os.path.exists(input_path):
        return {
            "success": False,
            "error": "INPUT_FILE_NOT_FOUND",
            "message": f"Input audio file not found at {input_path}"
        }

    if not is_ffmpeg_installed():
        return {
            "success": False,
            "error": "FFMPEG_NOT_FOUND",
            "message": "FFmpeg is not installed or not in PATH. On Windows, install via: winget install Gyan.FFmpeg or choco install ffmpeg."
        }

    if not output_path:
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}_16k.wav"

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            output_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if res.returncode != 0:
            logger.warning(f"FFmpeg conversion failed: {res.stderr.decode('utf-8', errors='ignore')}")
            return {
                "success": False,
                "error": "CONVERSION_FAILED",
                "message": f"FFmpeg failed with exit code {res.returncode}"
            }

        return {
            "success": True,
            "output_path": output_path,
            "sample_rate": 16000,
            "channels": 1
        }
    except Exception as e:
        logger.error(f"Error during audio conversion: {e}")
        return {
            "success": False,
            "error": "CONVERSION_EXCEPTION",
            "message": str(e)
        }
