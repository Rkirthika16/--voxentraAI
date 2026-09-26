import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Send, Volume2, VolumeX, AlertCircle, Loader2 } from 'lucide-react';

interface VoiceRecorderProps {
  isAiSpeaking: boolean;
  isProcessing: boolean;
  isCallActive: boolean;
  onSendAudio: (audioBlob: Blob, transcriptionHint?: string) => void;
  onSendText: (text: string) => void;
  ttsMuted: boolean;
  onToggleMute: () => void;
  errorMessage?: string | null;
  options?: Array<{ label: string; text: string }>;
}

export const VoiceRecorder: React.FC<VoiceRecorderProps> = ({
  isAiSpeaking,
  isProcessing,
  isCallActive,
  onSendAudio,
  onSendText,
  ttsMuted,
  onToggleMute,
  errorMessage,
  options,
}) => {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordDuration, setRecordDuration] = useState<number>(0);
  const [textInput, setTextInput] = useState<string>('');
  const [micPermissionError, setMicPermissionError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const durationTimerRef = useRef<number | null>(null);
  const recognitionRef = useRef<any>(null);
  const transcriptRef = useRef<string>('');

  // Stop recording if AI starts speaking or call ends
  useEffect(() => {
    if (isAiSpeaking && isRecording) {
      stopRecording();
    }
  }, [isAiSpeaking]);

  useEffect(() => {
    if (!isCallActive && isRecording) {
      stopRecording();
    }
  }, [isCallActive]);

  const startRecording = async () => {
    if (!isCallActive || isAiSpeaking || isProcessing) return;
    setMicPermissionError(null);
    audioChunksRef.current = [];
    transcriptRef.current = '';

    // Initialize parallel Web Speech Recognition if supported
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      try {
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'ta-IN';
        recognition.onresult = (e: any) => {
          let current = '';
          for (let i = 0; i < e.results.length; i++) {
            current += e.results[i][0].transcript + ' ';
          }
          let trimmed = current.trim();
          trimmed = trimmed
            .replace(/காந்தி\s*தம்பியின்\s*வரவில்லை/gi, 'காந்திபுரத்தில் தண்ணீர் வரவில்லை')
            .replace(/காந்தி\s*தம்பியின்\s*வரல/gi, 'காந்திபுரத்தில் தண்ணீர் வரவில்லை')
            .replace(/காந்தி\s*தம்பியின்\s*பிரச்சனை/gi, 'காந்திபுரத்தில் தண்ணீர் பிரச்சினை')
            .replace(/காந்தி\s*தம்பியின்/gi, 'காந்திபுரம் தண்ணீர்')
            .replace(/காந்தி\s*தம்பி\s*தண்ணீர்/gi, 'காந்திபுரம் தண்ணீர்')
            .replace(/காந்தி\s*தம்பி/gi, 'காந்திபுரம்')
            .replace(/காந்திபுரம்\s*தம்பியின்/gi, 'காந்திபுரத்தில் தண்ணீர்')
            .replace(/காந்திபுரம்\s*தம்பி/gi, 'காந்திபுரம் தண்ணீர்')
            .replace(/காந்திபுரத்தில\s*தம்பி/gi, 'காந்திபுரத்தில் தண்ணீர்')
            .replace(/தம்பியின்\s*வரவில்லை/gi, 'தண்ணீர் வரவில்லை')
            .replace(/தம்பியின்\s*வரல/gi, 'தண்ணீர் வரவில்லை')
            .replace(/தம்பி\s*வரல/gi, 'தண்ணீர் வரவில்லை')
            .replace(/தண்ணி\s*வரல/gi, 'தண்ணீர் வரவில்லை')
            .replace(/gandhi\s*thambiyin/gi, 'Gandhipuram thanni')
            .replace(/gandhi\s*thambi/gi, 'Gandhipuram thanni')
            .replace(/gandipuram/gi, 'Gandhipuram')
            .replace(/tanni\s*varla/gi, 'thanni varala');

          transcriptRef.current = trimmed;
        };
        recognition.start();
        recognitionRef.current = recognition;
      } catch (e) {
        // Non-fatal if speech recognition is unavailable
      }
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      // Pick supported mime type
      const mimeTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/wav', 'audio/mp4'];
      let chosenMime = '';
      for (const m of mimeTypes) {
        if (MediaRecorder.isTypeSupported(m)) {
          chosenMime = m;
          break;
        }
      }

      const recorder = chosenMime ? new MediaRecorder(stream, { mimeType: chosenMime }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: chosenMime || 'audio/webm' });
        audioChunksRef.current = [];
        stream.getTracks().forEach((track) => track.stop());

        if (audioBlob.size > 300) {
          onSendAudio(audioBlob, transcriptRef.current || undefined);
        }
      };

      recorder.start(100);
      setIsRecording(true);
      setRecordDuration(0);

      durationTimerRef.current = window.setInterval(() => {
        setRecordDuration((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      console.error('Microphone error:', err);
      setMicPermissionError('Microphone permission denied or audio device not found. You can type below.');
    }
  };

  const stopRecording = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && isRecording) {
      if (mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);
      if (durationTimerRef.current) {
        clearInterval(durationTimerRef.current);
      }
    }
  };

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!textInput.trim() || isProcessing || isAiSpeaking) return;
    onSendText(textInput.trim());
    setTextInput('');
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
        padding: '1.25rem',
        backgroundColor: '#FFFFFF',
        borderRadius: '1rem',
        border: '1px solid #E2E8F0',
        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)',
      }}
    >
      {/* Audio Control Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={onToggleMute}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.4rem 0.75rem',
              borderRadius: '0.5rem',
              backgroundColor: ttsMuted ? '#FEE2E2' : '#F1F5F9',
              color: ttsMuted ? '#DC2626' : '#475569',
              border: '1px solid transparent',
              cursor: 'pointer',
              fontSize: '0.8rem',
              fontWeight: 600,
            }}
          >
            {ttsMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
            <span>{ttsMuted ? 'TTS Muted' : 'TTS Audio On'}</span>
          </button>
        </div>

        {isRecording && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#DC2626', fontWeight: 600, fontSize: '0.85rem' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: '#DC2626',
                display: 'inline-block',
                animation: 'pulse 1s infinite',
              }}
            />
            <span>Citizen Speaking ({recordDuration}s)</span>
          </div>
        )}
      </div>

      {micPermissionError && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.6rem 0.8rem',
            borderRadius: '0.5rem',
            backgroundColor: '#FEF2F2',
            color: '#991B1B',
            fontSize: '0.8rem',
          }}
        >
          <AlertCircle size={15} />
          <span>{micPermissionError}</span>
        </div>
      )}

      {errorMessage && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.6rem 0.8rem',
            borderRadius: '0.5rem',
            backgroundColor: '#FFFBEB',
            color: '#B45309',
            fontSize: '0.8rem',
          }}
        >
          <AlertCircle size={15} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main Mic Push-to-Talk / Click Button */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0.5rem 0' }}>
        <button
          type="button"
          onClick={toggleRecording}
          disabled={!isCallActive || isAiSpeaking || isProcessing}
          style={{
            width: '80px',
            height: '80px',
            borderRadius: '50%',
            backgroundColor: isRecording
              ? '#EF4444'
              : isAiSpeaking || isProcessing || !isCallActive
              ? '#94A3B8'
              : '#2563EB',
            color: '#FFFFFF',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: isAiSpeaking || isProcessing || !isCallActive ? 'not-allowed' : 'pointer',
            boxShadow: isRecording
              ? '0 0 0 10px rgba(239, 68, 68, 0.25)'
              : '0 4px 14px rgba(37, 99, 235, 0.35)',
            transition: 'all 0.2s ease-in-out',
          }}
        >
          {isProcessing ? (
            <Loader2 size={32} className="animate-spin" />
          ) : isRecording ? (
            <MicOff size={32} />
          ) : (
            <Mic size={32} />
          )}
        </button>

        <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: '#64748B', textAlign: 'center', fontWeight: 500 }}>
          {isAiSpeaking
            ? 'AI Speaking — Microphone closed to prevent echo'
            : isProcessing
            ? 'Transcribing speech & analyzing...'
            : isRecording
            ? 'Click to stop speaking & submit response'
            : isCallActive
            ? 'Click microphone to speak (Tamil / English / Tanglish)'
            : 'Start call to begin conversation'}
        </p>
      </div>

      {/* Quick Contextual Clarification & Simulation Chips */}
      {isCallActive && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', alignItems: 'center', marginTop: '0.25rem' }}>
          <span style={{ fontSize: '0.75rem', color: '#2563eb', fontWeight: 700 }}>
            {options && options.length > 0 ? '💡 Quick / Clarify Options:' : 'Quick test:'}
          </span>
          {(options && options.length > 0 ? options : [
            { label: '💧 குடிநீர் வரவில்லை', text: 'எங்கள் தெருவில் 3 நாட்களாக குடிநீர் விநியோகம் இல்லை, அண்ணா நகர்' },
            { label: '💡 Streetlight Issue', text: 'Street lights are not working on 5th cross street' },
            { label: '🗑️ குப்பை தேக்கம்', text: 'குப்பை அள்ளப்படாமல் ரோட்டில் தேங்கியுள்ளது' },
            { label: '⚡ Power Cut Hazard', text: 'Power cut since morning and live wire sparking near temple' },
            { label: '🛣️ Road Damage', text: 'Dangerous potholes and road damage on main road' },
            { label: '✅ உறுதி செய்க (Confirm)', text: 'ஆம், என் புகாரை பதிவு செய்யுங்கள்' },
          ]).map((item, i) => (
            <button
              key={i}
              type="button"
              disabled={!isCallActive || isAiSpeaking || isProcessing}
              onClick={() => onSendText(item.text)}
              style={{
                background: options && options.length > 0 ? '#EFF6FF' : '#F8FAFC',
                border: options && options.length > 0 ? '1px solid #BFDBFE' : '1px solid #CBD5E1',
                borderRadius: '9999px',
                padding: '0.25rem 0.65rem',
                fontSize: '0.73rem',
                color: options && options.length > 0 ? '#1D4ED8' : '#334155',
                cursor: !isCallActive || isAiSpeaking || isProcessing ? 'not-allowed' : 'pointer',
                fontWeight: 600,
                transition: 'all 0.15s ease',
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}

      {/* Direct Text Fallback */}
      <form onSubmit={handleTextSubmit} style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
        <input
          type="text"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          placeholder="Or type here (e.g., 'Gandhipuram-la thanni varala')..."
          disabled={!isCallActive || isAiSpeaking || isProcessing}
          style={{
            flex: 1,
            padding: '0.65rem 1rem',
            borderRadius: '0.5rem',
            border: '1px solid #CBD5E1',
            fontSize: '0.9rem',
            outline: 'none',
          }}
        />
        <button
          type="submit"
          disabled={!textInput.trim() || !isCallActive || isAiSpeaking || isProcessing}
          style={{
            padding: '0.65rem 1.25rem',
            borderRadius: '0.5rem',
            backgroundColor: '#2563EB',
            color: '#FFFFFF',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            cursor: !textInput.trim() || isAiSpeaking || isProcessing ? 'not-allowed' : 'pointer',
            opacity: !textInput.trim() || isAiSpeaking || isProcessing ? 0.6 : 1,
            fontWeight: 600,
            fontSize: '0.85rem',
          }}
        >
          <Send size={15} />
          <span>Send</span>
        </button>
      </form>
    </div>
  );
};
