import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Play, Pause, Upload, RotateCcw, AlertCircle, CheckCircle } from 'lucide-react';

interface AudioRecorderProps {
  onAudioReady: (audioBlob: Blob, filename?: string) => void;
  onClear: () => void;
  isProcessing?: boolean;
}

export const AudioRecorder: React.FC<AudioRecorderProps> = ({ onAudioReady, onClear, isProcessing = false }) => {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordingTime, setRecordingTime] = useState<number>(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<any>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  const startRecording = async () => {
    setErrorMsg(null);
    audioChunksRef.current = [];

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setErrorMsg('Microphone access is not supported in this browser. Please upload an audio file or type your complaint.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const url = URL.createObjectURL(audioBlob);
        setRecordedBlob(audioBlob);
        setAudioUrl(url);
        setUploadedFileName('voice_complaint.webm');
        onAudioReady(audioBlob, 'voice_complaint.webm');

        // Stop all audio tracks
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);

      timerIntervalRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      console.error('Error accessing microphone:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setErrorMsg('Microphone permission was denied. Please allow microphone access in browser settings or upload an audio file.');
      } else {
        setErrorMsg(`Unable to access microphone: ${err.message || 'Unknown error'}`);
      }
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    }
  };

  const handleReset = () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setRecordedBlob(null);
    setUploadedFileName(null);
    setRecordingTime(0);
    setIsRecording(false);
    setIsPlaying(false);
    setErrorMsg(null);
    onClear();
  };

  const togglePlayback = () => {
    if (!audioElementRef.current) return;
    if (isPlaying) {
      audioElementRef.current.pause();
      setIsPlaying(false);
    } else {
      audioElementRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorMsg(null);
    const file = e.target.files?.[0];
    if (!file) return;

    // Check size (max 25MB)
    if (file.size > 25 * 1024 * 1024) {
      setErrorMsg('File exceeds maximum size of 25MB.');
      return;
    }

    const url = URL.createObjectURL(file);
    setAudioUrl(url);
    setRecordedBlob(file);
    setUploadedFileName(file.name);
    onAudioReady(file, file.name);
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="glass-card" style={{ padding: '1.75rem', textAlign: 'center' }}>
      {errorMsg && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: 'var(--radius-md)',
            padding: '0.75rem 1rem',
            marginBottom: '1.25rem',
            color: '#fca5a5',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <AlertCircle size={16} color="#ef4444" style={{ flexShrink: 0 }} />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Recording State Controls */}
      {!recordedBlob ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.25rem' }}>
          <div
            style={{
              width: '84px',
              height: '84px',
              borderRadius: '50%',
              background: isRecording ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 'linear-gradient(135deg, #3b82f6, #2563eb)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: isRecording ? '0 0 30px rgba(239, 68, 68, 0.6)' : '0 4px 20px rgba(37, 99, 235, 0.4)',
              transition: 'all 0.3s ease',
              animation: isRecording ? 'pulse 1.5s infinite' : 'none',
            }}
            onClick={isRecording ? stopRecording : startRecording}
          >
            {isRecording ? <Square size={32} color="#ffffff" /> : <Mic size={36} color="#ffffff" />}
          </div>

          <div>
            <h4 style={{ fontSize: '1.1rem', marginBottom: '0.25rem' }}>
              {isRecording ? 'Listening & Recording...' : 'Tap to Record Your Voice'}
            </h4>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              {isRecording ? `Recording Time: ${formatTimer(recordingTime)}` : 'Speak in Tamil, English, or Tanglish'}
            </p>
          </div>

          {isRecording ? (
            <button onClick={stopRecording} className="btn btn-danger btn-sm">
              <Square size={14} /> Stop Recording
            </button>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '0.5rem' }}>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="btn btn-secondary btn-sm"
              >
                <Upload size={14} /> Upload Audio File (.m4a, .mp3, .wav)
              </button>
              <input
                type="file"
                ref={fileInputRef}
                style={{ display: 'none' }}
                accept="audio/*,.m4a,.mp3,.wav,.webm,.ogg"
                onChange={handleFileUpload}
              />
            </div>
          )}
        </div>
      ) : (
        /* Audio Preview State */
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#10b981', fontWeight: 600 }}>
            <CheckCircle size={20} />
            <span>Audio Ready ({uploadedFileName})</span>
          </div>

          <audio
            ref={audioElementRef}
            src={audioUrl || ''}
            onEnded={() => setIsPlaying(false)}
            style={{ display: 'none' }}
          />

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button onClick={togglePlayback} className="btn btn-primary btn-sm">
              {isPlaying ? <Pause size={14} /> : <Play size={14} />}
              {isPlaying ? 'Pause Audio' : 'Listen Recording'}
            </button>

            <button onClick={handleReset} className="btn btn-secondary btn-sm" disabled={isProcessing}>
              <RotateCcw size={14} /> Record Again
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
