import React, { useState, useEffect, useRef } from 'react';
import { voiceApi, VoiceSessionResponse } from '../api/voice';
import { speech } from '../utils/speech';
import { VoiceStatus, VoiceState } from '../components/voice/VoiceStatus';
import { VoiceVisualizer } from '../components/voice/VoiceVisualizer';
import { MicrophoneButton } from '../components/voice/MicrophoneButton';
import { TranscriptionDisplay } from '../components/voice/TranscriptionDisplay';
import { LiveConversation } from '../components/voice/LiveConversation';
import { MessageItem } from '../components/voice/ConversationMessage';
import { Link } from 'react-router-dom';
import {
  Sparkles,
  Bot,
  Send,
  CheckCircle2,
  AlertTriangle,
  Building2,
  MapPin,
  Clock,
  ArrowRight,
  ShieldAlert,
  HelpCircle,
  FileText
} from 'lucide-react';

export const VoiceAssistantPage: React.FC = () => {
  const [sessionId, setSessionId] = useState<string>('');
  const [voiceState, setVoiceState] = useState<VoiceState>('IDLE');
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [spokenText, setSpokenText] = useState<string>('');
  const [normalizedText, setNormalizedText] = useState<string>('');
  const [textInput, setTextInput] = useState<string>('');
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isAiSpeaking, setIsAiSpeaking] = useState<boolean>(false);
  const [detectedLanguage, setDetectedLanguage] = useState<string>('Auto-Detecting...');
  const [context, setContext] = useState<Record<string, any>>({});
  const [error, setError] = useState<string | null>(null);
  const [completedComplaint, setCompletedComplaint] = useState<{
    id?: number;
    number?: string;
    department?: string;
    summary?: string;
  } | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recognitionRef = useRef<any>(null);

  // Initialize live voice assistant session on mount
  useEffect(() => {
    initSession();
    return () => {
      speech.stop();
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
    };
  }, []);

  const initSession = async () => {
    setError(null);
    setVoiceState('PROCESSING');
    try {
      const res = await voiceApi.startSession();
      setSessionId(res.session_id);
      setContext(res.context || {});
      setVoiceState('WAITING_FOR_USER');

      if (res.greeting_text) {
        const aiMsg: MessageItem = {
          id: `ai_${Date.now()}`,
          sender: 'ai',
          text: res.greeting_text,
          language: 'Tamil',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages([aiMsg]);

        // Speak greeting aloud
        playVoiceAudio(res.greeting_spoken || res.greeting_text, 'Tamil', res.audio_base64);
      }
    } catch (err: any) {
      setError('Unable to start live voice assistant session. Backend might be offline.');
      setVoiceState('ERROR');
    }
  };

  const playVoiceAudio = (text: string, lang = 'Tamil', base64Audio?: string | null) => {
    speech.stop();
    setIsAiSpeaking(true);

    if (base64Audio) {
      try {
        const snd = new Audio(`data:audio/mp3;base64,${base64Audio}`);
        snd.onended = () => setIsAiSpeaking(false);
        snd.onerror = () => {
          speech.speak(text, {
            language: lang,
            onStart: () => setIsAiSpeaking(true),
            onEnd: () => setIsAiSpeaking(false),
            onError: () => setIsAiSpeaking(false)
          });
        };
        snd.play().catch(() => {
          speech.speak(text, {
            language: lang,
            onStart: () => setIsAiSpeaking(true),
            onEnd: () => setIsAiSpeaking(false),
            onError: () => setIsAiSpeaking(false)
          });
        });
        return;
      } catch (e) {}
    }

    speech.speak(text, {
      language: lang,
      onStart: () => setIsAiSpeaking(true),
      onEnd: () => setIsAiSpeaking(false),
      onError: () => setIsAiSpeaking(false)
    });
  };

  const handleToggleRecord = async () => {
    speech.unlock();
    if (isRecording) {
      // Stop recording and send audio turn
      stopRecordingAndSend();
    } else {
      // Start recording
      startRecording();
    }
  };

  const startRecording = async () => {
    setError(null);
    speech.stop();
    setIsAiSpeaking(false);
    setSpokenText('');
    setNormalizedText('');

    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          const mediaRecorder = new MediaRecorder(stream);
          mediaRecorderRef.current = mediaRecorder;
          audioChunksRef.current = [];

          mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunksRef.current.push(e.data);
          };

          mediaRecorder.start(250);
        } catch (mediaErr) {
          console.warn('Microphone stream error:', mediaErr);
        }
      }

      setIsRecording(true);
      setVoiceState('LISTENING');

      // Continuous Speech Recognition
      if (speech.isSTTSupported()) {
        const rec = speech.createRecognition(
          'en-IN' as any,
          (transcript) => setSpokenText(transcript),
          (err) => console.log('STT status:', err),
          () => {}
        );
        if (rec) {
          recognitionRef.current = rec;
          try { rec.start(); } catch (e) {}
        }
      }
    } catch (err: any) {
      setError('Microphone permission was denied or is not supported in your browser.');
      setVoiceState('ERROR');
    }
  };

  const stopRecordingAndSend = async () => {
    setIsRecording(false);
    setVoiceState('PROCESSING');

    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) {}
    }

    if (mediaRecorderRef.current) {
      try { mediaRecorderRef.current.stop(); } catch (e) {}
    }

    setTimeout(async () => {
      const textToSend = spokenText.trim();
      const audioBlob = audioChunksRef.current.length > 0
        ? new Blob(audioChunksRef.current, { type: 'audio/wav' })
        : null;

      if (!textToSend && (!audioBlob || audioBlob.size === 0)) {
        setError('No speech was detected. Please speak your grievance clearly.');
        setVoiceState('WAITING_FOR_USER');
        return;
      }

      // Add citizen turn message to UI
      const citizenMsg: MessageItem = {
        id: `cit_${Date.now()}`,
        sender: 'citizen',
        text: textToSend || 'Voice Recording (Processing...)',
        language: detectedLanguage,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages((prev) => [...prev, citizenMsg]);

      try {
        let res: VoiceSessionResponse;
        if (audioBlob && audioBlob.size > 500) {
          res = await voiceApi.sendAudioTurn(sessionId, audioBlob);
        } else {
          res = await voiceApi.sendMessageTurn(sessionId, textToSend);
        }

        handleTurnResponse(res);
      } catch (err: any) {
        setError('Failed to process voice turn. Falling back to text mode.');
        setVoiceState('WAITING_FOR_USER');
      }
    }, 400);
  };

  const handleSendTextMessage = async (customMessage?: string) => {
    const text = (customMessage || textInput).trim();
    if (!text) return;

    setTextInput('');
    setError(null);
    speech.stop();
    setVoiceState('PROCESSING');

    const citizenMsg: MessageItem = {
      id: `cit_${Date.now()}`,
      sender: 'citizen',
      text: text,
      language: detectedLanguage,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages((prev) => [...prev, citizenMsg]);

    try {
      const res = await voiceApi.sendMessageTurn(sessionId, text);
      handleTurnResponse(res);
    } catch (err: any) {
      setError('Failed to process message.');
      setVoiceState('WAITING_FOR_USER');
    }
  };

  const handleTurnResponse = (res: VoiceSessionResponse) => {
    if (res.detected_language) setDetectedLanguage(res.detected_language);
    if (res.context) setContext(res.context);
    if (res.transcription) setSpokenText(res.transcription);
    if (res.normalized_transcription) setNormalizedText(res.normalized_transcription);

    const replyText = res.ai_text || res.ai_spoken || '';
    const spokenLang = res.detected_language || 'Tamil';

    const aiMsg: MessageItem = {
      id: `ai_${Date.now()}`,
      sender: 'ai',
      text: replyText,
      language: spokenLang,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      state: res.state
    };
    setMessages((prev) => [...prev, aiMsg]);

    if (res.conversation_complete || res.state === 'COMPLETED') {
      setCompletedComplaint({
        id: res.complaint_id,
        number: res.complaint_number || 'VX-2026-000001',
        department: res.department || res.context?.department || 'Municipal Administration',
        summary: res.context?.summary || replyText
      });
      setVoiceState('COMPLETED');
    } else if (res.confirmation_required || res.state === 'CONFIRMING') {
      setVoiceState('CONFIRMING');
    } else {
      setVoiceState('WAITING_FOR_USER');
    }

    // Play AI spoken voice
    playVoiceAudio(res.ai_spoken || replyText, spokenLang, res.audio_base64);
  };

  const handleConfirmComplaint = async () => {
    setVoiceState('PROCESSING');
    try {
      const res = await voiceApi.confirmSession(sessionId);
      handleTurnResponse(res);
    } catch (err: any) {
      setError('Failed to confirm complaint.');
      setVoiceState('CONFIRMING');
    }
  };

  const handleReset = async () => {
    speech.stop();
    try {
      if (sessionId) await voiceApi.cancelSession(sessionId);
    } catch (e) {}
    setMessages([]);
    setContext({});
    setSpokenText('');
    setNormalizedText('');
    setCompletedComplaint(null);
    initSession();
  };

  return (
    <div className="page-container animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: '960px', margin: '0 auto' }}>
      
      {/* 1. Header & Live Status */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div
            style={{
              width: '46px',
              height: '46px',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, #6366f1, #4f46e5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              boxShadow: '0 0 20px rgba(99, 102, 241, 0.4)',
            }}
          >
            <Bot className="w-6 h-6" />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.4rem', color: 'var(--text-primary)', fontWeight: 700 }}>
              Live Conversational Voice Assistant
            </h1>
            <p style={{ margin: '0.15rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Citizen Speaks First • Auto Language Recognition (Tamil, Tanglish, English) • Dynamic Context
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleReset}
          style={{
            padding: '0.5rem 0.9rem',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            color: 'var(--text-secondary)',
            fontSize: '0.85rem',
            cursor: 'pointer',
          }}
        >
          New Conversation
        </button>
      </div>

      {/* 2. Real-time Status Banner */}
      <VoiceStatus
        state={voiceState}
        language={detectedLanguage !== 'Auto-Detecting...' ? detectedLanguage : undefined}
        category={context.category}
        location={context.location}
      />

      {/* Error Alert */}
      {error && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            background: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#f87171',
            fontSize: '0.875rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem'
          }}
        >
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 3. Main Conversational Card */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-xl)',
          padding: '1.5rem',
          boxShadow: 'var(--shadow-lg)',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.25rem',
        }}
      >
        {/* Visualizer & Mic Hero */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem 1rem',
            background: 'linear-gradient(180deg, rgba(99, 102, 241, 0.04), transparent)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid rgba(99, 102, 241, 0.1)',
          }}
        >
          <VoiceVisualizer isActive={isRecording} isAiSpeaking={isAiSpeaking} />

          <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.9rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
            {isRecording
              ? '🎙️ Listening... Speak naturally in Tamil, English, or Tanglish. Click to finish.'
              : voiceState === 'CONFIRMING'
              ? '💬 Please confirm or say "Yes, register" / "Aama" to create your complaint.'
              : isAiSpeaking
              ? '🔊 VoxentraAI is speaking...'
              : 'Click microphone to speak your grievance.'}
          </p>

          <MicrophoneButton
            isRecording={isRecording}
            isProcessing={voiceState === 'PROCESSING'}
            onToggleRecord={handleToggleRecord}
            onCancel={handleReset}
          />
        </div>

        {/* Live Transcription Display */}
        <TranscriptionDisplay
          originalText={spokenText}
          normalizedText={normalizedText}
          isProcessing={voiceState === 'PROCESSING'}
          onEditSubmit={(edited) => handleSendTextMessage(edited)}
        />

        {/* Live Conversation Stream */}
        <LiveConversation
          messages={messages}
          isAiResponding={voiceState === 'PROCESSING'}
          onPlayAudio={(text, lang) => playVoiceAudio(text, lang)}
        />

        {/* Confirmation Action Box (When state is CONFIRMING) */}
        {voiceState === 'CONFIRMING' && (
          <div
            style={{
              padding: '1.25rem',
              borderRadius: 'var(--radius-lg)',
              background: 'rgba(245, 158, 11, 0.1)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#fbbf24', fontWeight: 600 }}>
              <HelpCircle className="w-5 h-5" />
              <span>Confirm Grievance Registration</span>
            </div>
            <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              Are the gathered complaint details correct? Click "Confirm & Register" or speak "Yes / ஆமாம் / Correct".
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={handleConfirmComplaint}
                style={{
                  padding: '0.65rem 1.25rem',
                  borderRadius: 'var(--radius-md)',
                  background: 'linear-gradient(135deg, #10b981, #059669)',
                  color: '#ffffff',
                  border: 'none',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)',
                }}
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Confirm & Register</span>
              </button>

              <button
                type="button"
                onClick={() => handleSendTextMessage("No, I want to change location")}
                style={{
                  padding: '0.65rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-secondary)',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                Change Details
              </button>
            </div>
          </div>
        )}

        {/* Completion Card */}
        {completedComplaint && (
          <div
            style={{
              padding: '1.5rem',
              borderRadius: 'var(--radius-lg)',
              background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(5, 150, 105, 0.2))',
              border: '1px solid rgba(16, 185, 129, 0.4)',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#34d399' }}>
              <CheckCircle2 className="w-7 h-7" />
              <div>
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700 }}>
                  Complaint Registered Successfully!
                </h3>
                <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  Assigned Public Tracking ID: <strong>{completedComplaint.number}</strong>
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <Link
                to={`/complaints?search=${completedComplaint.number}`}
                style={{
                  padding: '0.6rem 1.25rem',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--primary-color)',
                  color: '#ffffff',
                  textDecoration: 'none',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                }}
              >
                <span>Track Complaint</span>
                <ArrowRight className="w-4 h-4" />
              </Link>

              <button
                type="button"
                onClick={handleReset}
                style={{
                  padding: '0.6rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-secondary)',
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                }}
              >
                Start New Grievance
              </button>
            </div>
          </div>
        )}

        {/* Text Fallback Input Bar */}
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
          <input
            type="text"
            placeholder="Type your message here (Tamil / Tanglish / English) if you prefer typing..."
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendTextMessage()}
            style={{
              flex: 1,
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              fontSize: '0.9rem',
            }}
          />
          <button
            type="button"
            onClick={() => handleSendTextMessage()}
            disabled={!textInput.trim() || voiceState === 'PROCESSING'}
            style={{
              padding: '0.75rem 1.25rem',
              borderRadius: 'var(--radius-md)',
              background: 'var(--primary-color)',
              color: '#ffffff',
              border: 'none',
              fontWeight: 600,
              cursor: !textInput.trim() || voiceState === 'PROCESSING' ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            <Send className="w-4 h-4" />
            <span>Send</span>
          </button>
        </div>
      </div>

      {/* 4. Structured Memory Context Card */}
      {Object.keys(context).length > 0 && (
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            padding: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: 600 }}>
            <FileText className="w-4 h-4" />
            <span>EXTRACTED CONVERSATION MEMORY (STRUCTURED SLOTS)</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
            <div style={{ background: 'var(--bg-secondary)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Category</span>
              <p style={{ margin: '0.15rem 0 0 0', fontWeight: 600, color: 'var(--text-primary)' }}>
                {context.category || 'Extracting...'}
              </p>
            </div>

            <div style={{ background: 'var(--bg-secondary)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Location</span>
              <p style={{ margin: '0.15rem 0 0 0', fontWeight: 600, color: 'var(--text-primary)' }}>
                {context.location || 'Extracting...'}
              </p>
            </div>

            <div style={{ background: 'var(--bg-secondary)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Duration / Scope</span>
              <p style={{ margin: '0.15rem 0 0 0', fontWeight: 600, color: 'var(--text-primary)' }}>
                {context.duration ? `${context.duration}${context.affected_scope ? ` • ${context.affected_scope}` : ''}` : (context.affected_scope || 'Pending...')}
              </p>
            </div>

            <div style={{ background: 'var(--bg-secondary)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Department</span>
              <p style={{ margin: '0.15rem 0 0 0', fontWeight: 600, color: 'var(--text-primary)' }}>
                {context.department || 'Municipal Administration'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
