import io


def test_audio_upload_invalid_extension(client):
    fake_exe = io.BytesIO(b"executable data")
    files = {"file": ("malicious.exe", fake_exe, "application/x-msdownload")}
    response = client.post("/api/v1/audio/transcribe", files=files)
    assert response.status_code == 400
    assert "Unsupported audio format" in response.json()["detail"]


def test_speech_status_endpoint(client):
    response = client.get("/api/v1/audio/status")
    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "engine" in data


def test_audio_upload_browser_mediarecorder_mime(client):
    """Verify audio/webm;codecs=opus is accepted by validator."""
    from fastapi import UploadFile
    from app.utils.validators import validate_audio_file
    
    file = UploadFile(file=io.BytesIO(b"dummy audio content"), filename="mic_recording.webm", headers={"content-type": "audio/webm;codecs=opus"})
    sanitized, ext = validate_audio_file(file)
    assert ext == ".webm"
    assert sanitized == "mic_recording.webm"


