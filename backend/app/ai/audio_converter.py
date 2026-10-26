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


def get_ffmpeg_executable() -> Optional[str]:
    """Finds ffmpeg executable on PATH or in standard Windows installation directories."""
    # 1. Check current PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 2. Search common Windows package manager paths
    user_profile = os.environ.get("USERPROFILE", "")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    program_data = os.environ.get("ProgramData", "C:\\ProgramData")

    candidate_patterns = [
        os.path.join(local_app_data, "Microsoft", "WinGet", "Packages"),
        os.path.join(program_files, "ffmpeg", "bin"),
        os.path.join(program_data, "chocolatey", "bin"),
        os.path.join(user_profile, "scoop", "shims"),
        "C:\\ffmpeg\\bin",
        "C:\\tools\\ffmpeg\\bin",
    ]

    for base in candidate_patterns:
        if not os.path.exists(base):
            continue
        if os.path.isfile(os.path.join(base, "ffmpeg.exe")):
            ffmpeg_path = os.path.join(base, "ffmpeg.exe")
            # Prepend directory to PATH
            os.environ["PATH"] = base + os.pathsep + os.environ.get("PATH", "")
            return ffmpeg_path
        # Recursively look in WinGet Packages
        for root, dirs, files in os.walk(base):
            if "ffmpeg.exe" in files:
                ffmpeg_path = os.path.join(root, "ffmpeg.exe")
                os.environ["PATH"] = root + os.pathsep + os.environ.get("PATH", "")
                return ffmpeg_path

    return None


def check_ffmpeg_available() -> bool:
    """Checks if ffmpeg executable is available on system PATH or known paths."""
    return get_ffmpeg_executable() is not None


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

    ffmpeg_bin = get_ffmpeg_executable()
    if not ffmpeg_bin:
        logger.warning("FFmpeg not found on system PATH. Attempting direct file pass-through if already WAV.")
        if input_path.lower().endswith(".wav"):
            shutil.copyfile(input_path, output_path)
            return True, output_path, None
        return False, "", FFMPEG_NOT_FOUND

    try:
        # ffmpeg -y -i <input> -ac 1 -ar 16000 -c:a pcm_s16le <output>
        cmd = [
            ffmpeg_bin,
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


def mulaw_to_wav_bytes(mulaw_bytes: bytes, in_rate: int = 8000, out_rate: int = 16000) -> bytes:
    """
    Converts 8 kHz 8-bit mu-law raw telephony audio stream bytes
    to standard 16 kHz 16-bit mono PCM WAV bytes for Whisper speech recognition.
    """
    if not mulaw_bytes:
        return b""

    import io
    import wave
    try:
        import audioop
        pcm_data = audioop.ulaw2lin(mulaw_bytes, 2)
        if in_rate != out_rate:
            pcm_data, _ = audioop.ratecv(pcm_data, 2, 1, in_rate, out_rate, None)
    except Exception:
        # Software fallback for pure linear decoding
        bias = 0x84
        pcm_arr = bytearray()
        for b in mulaw_bytes:
            comp = ~b & 0xFF
            sign = comp & 0x80
            exponent = (comp >> 4) & 0x07
            mantissa = comp & 0x0F
            sample = ((mantissa << 3) + bias) << exponent
            sample -= bias
            val = -sample if sign else sample
            val = max(-32768, min(32767, val))
            # Resample by 2x repetition if in_rate=8000, out_rate=16000
            for _ in range(out_rate // in_rate):
                pcm_arr.extend(val.to_bytes(2, byteorder='little', signed=True))
        pcm_data = bytes(pcm_arr)

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(out_rate)
        wav.writeframes(pcm_data)
    return buf.getvalue()


def pcm_or_wav_to_mulaw(audio_bytes: bytes, in_rate: int = 16000, out_rate: int = 8000) -> bytes:
    """
    Converts 16 kHz PCM/WAV (or raw PCM) audio bytes to 8 kHz mu-law bytes for telephone audio streaming.
    """
    if not audio_bytes:
        return b""

    import io
    import wave

    raw_pcm = audio_bytes
    actual_in_rate = in_rate

    # If header contains RIFF WAV header, extract raw PCM frames
    if audio_bytes.startswith(b"RIFF"):
        try:
            with wave.open(io.BytesIO(audio_bytes), 'rb') as wav:
                actual_in_rate = wav.getframerate()
                raw_pcm = wav.readframes(wav.getnframes())
                if wav.getnchannels() > 1:
                    import audioop
                    raw_pcm = audioop.tomono(raw_pcm, 2, 0.5, 0.5)
        except Exception:
            raw_pcm = audio_bytes[44:] if len(audio_bytes) > 44 else audio_bytes

    try:
        import audioop
        if actual_in_rate != out_rate:
            raw_pcm, _ = audioop.ratecv(raw_pcm, 2, 1, actual_in_rate, out_rate, None)
        return audioop.lin2ulaw(raw_pcm, 2)
    except Exception:
        # Software fallback
        res = bytearray()
        step = 2 * (actual_in_rate // out_rate) if actual_in_rate >= out_rate else 2
        for i in range(0, len(raw_pcm) - 1, max(2, step)):
            val = int.from_bytes(raw_pcm[i:i+2], byteorder='little', signed=True)
            # Encode linear to mu-law
            sign = 0x80 if val < 0 else 0x00
            val = abs(val)
            val += 0x84
            val = min(val, 0x7FFF)
            exp = 7
            for e in range(8):
                if val < (1 << (e + 8)):
                    exp = e
                    break
            mantissa = (val >> (exp + 3)) & 0x0F
            mulaw = ~(sign | (exp << 4) | mantissa) & 0xFF
            res.append(mulaw)
        return bytes(res)

