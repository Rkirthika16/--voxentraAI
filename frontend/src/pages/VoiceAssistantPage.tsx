import React, { useState, useEffect, useRef } from 'react';
import { useVoiceConversationEngine } from '../utils/useVoiceConversationEngine';
import { VoiceStatus } from '../components/voice/VoiceStatus';
import { VoiceVisualizer } from '../components/voice/VoiceVisualizer';
import { MicrophoneButton } from '../components/voice/MicrophoneButton';
import { TranscriptionDisplay } from '../components/voice/TranscriptionDisplay';
import { LiveConversation } from '../components/voice/LiveConversation';
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
  FileText,
  RotateCcw,
  Radio,
  Keyboard
} from 'lucide-react';

export const VoiceAssistantPage: React.FC = () => {
  const [textInput, setTextInput] = useState<string>('');
  const textInputRef = useRef<HTMLInputElement | null>(null);

  const {
    sessionId,
    voiceState,
    messages,
    liveTranscription,
    normalizedTranscription,
    detectedLanguage,
    analysis,
    isHandsFreeActive,
    isAiSpeaking,
    isRecording,
    error,
    isPermissionDenied,
    isSpeechRecognitionAvailable,
    completedComplaint,
    startSession,
    sendTextMessage,
    toggleRecording,
    confirmComplaint,
    cancelConversation,
    playAiSpeech
  } = useVoiceConversationEngine({
    mode: 'assistant',
    callerPhone: '+91 98430 98765'
  });

  // Start voice session on mount
  useEffect(() => {
    startSession();
  }, []);

  const handleSendText = async (customText?: string) => {
    const text = (customText || textInput).trim();
    if (!text) return;
    setTextInput('');
    await sendTextMessage(text);
  };

  const handleReset = async () => {
    await startSession();
  };

  const handleFocusTextInput = () => {
    if (textInputRef.current) {
      textInputRef.current.focus();
    }
  };

  return (
    <div className="page-container animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: '980px', margin: '0 auto', padding: '1rem' }}>
      
      {/* 1. Header & Live Status */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
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
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h1 style={{ margin: 0, fontSize: '1.4rem', color: 'var(--text-primary)', fontWeight: 800 }}>
                Live Conversational Voice Assistant
              </h1>
              <span
                style={{
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#34d399',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  padding: '0.15rem 0.55rem',
                  borderRadius: '9999px',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.3rem'
                }}
              >
                <Radio size={11} className="animate-pulse" /> 2-WAY HANDS-FREE
              </span>
            </div>
            <p style={{ margin: '0.15rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Natural Turn-Based Voice Loop • Auto Silence Detection (VAD) • Tamil, Tanglish & English
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
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem'
          }}
        >
          <RotateCcw size={15} />
          <span>New Conversation</span>
        </button>
      </div>

      {/* 2. Real-time Status Badge */}
      <VoiceStatus
        state={voiceState}
        language={detectedLanguage !== 'Auto-Detecting...' ? detectedLanguage : undefined}
        category={analysis.category}
        location={analysis.location}
      />

      {/* Permission / Speech Engine Notice */}
      {(isPermissionDenied || !isSpeechRecognitionAvailable || error) && (
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
            justifyContent: 'space-between',
            gap: '0.5rem'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error || (isPermissionDenied ? 'Microphone permission is required for voice conversation.' : 'Speech recognition is not configured.')}</span>
          </div>
          <button
            onClick={handleFocusTextInput}
            style={{
              background: '#6366f1',
              border: 'none',
              borderRadius: '6px',
              padding: '0.3rem 0.75rem',
              color: '#ffffff',
              fontSize: '0.75rem',
              fontWeight: 700,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem'
            }}
          >
            <Keyboard size={13} /> TYPE INSTEAD
          </button>
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
            background: 'linear-gradient(180deg, rgba(99, 102, 241, 0.05), transparent)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid rgba(99, 102, 241, 0.12)',
          }}
        >
          <VoiceVisualizer isActive={isRecording || voiceState === 'CITIZEN_SPEAKING'} isAiSpeaking={isAiSpeaking} />

          <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.9rem', color: 'var(--text-secondary)', textAlign: 'center', fontWeight: 600 }}>
            {voiceState === 'AI_SPEAKING'
              ? '🔊 VoxentraAI is speaking...'
              : voiceState === 'WAITING_FOR_CITIZEN'
              ? '🎤 Your turn — Listening... Speak naturally in Tamil, Tanglish, or English.'
              : voiceState === 'CITIZEN_SPEAKING'
              ? '🔴 Listening to your voice... (Auto-submits on silence)'
              : voiceState === 'CONFIRMING'
              ? '💬 Please confirm or say "Yes, register" / "Aama" / "சரி".'
              : '⚡ Continuous two-way voice engine active.'}
          </p>

          <MicrophoneButton
            isRecording={isRecording || voiceState === 'CITIZEN_SPEAKING'}
            isProcessing={voiceState === 'PROCESSING_AUDIO' || voiceState === 'TRANSCRIBING' || voiceState === 'UNDERSTANDING'}
            onToggleRecord={toggleRecording}
            onCancel={handleReset}
          />
        </div>

        {/* Live Transcription Display */}
        <TranscriptionDisplay
          originalText={liveTranscription}
          normalizedText={normalizedTranscription}
          isProcessing={voiceState === 'PROCESSING_AUDIO' || voiceState === 'TRANSCRIBING' || voiceState === 'UNDERSTANDING'}
          onEditSubmit={(edited) => handleSendText(edited)}
        />

        {/* Live Conversation Stream */}
        <LiveConversation
          messages={messages}
          isAiResponding={voiceState === 'PROCESSING_AUDIO' || voiceState === 'TRANSCRIBING' || voiceState === 'UNDERSTANDING' || voiceState === 'GENERATING_RESPONSE'}
          onPlayAudio={(text, lang) => playAiSpeech(text, lang)}
        />

        {/* Confirmation Action Box (When state is CONFIRMING) */}
        {(voiceState === 'CONFIRMING' || (analysis.category && analysis.location && !completedComplaint)) && (
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
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#fbbf24', fontWeight: 700 }}>
              <HelpCircle className="w-5 h-5" />
              <span>Confirm Grievance Registration</span>
            </div>
            <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              Speak <strong>"Yes / ஆமாம் / Aama"</strong> to register, or click below:
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={confirmComplaint}
                style={{
                  padding: '0.65rem 1.25rem',
                  borderRadius: 'var(--radius-md)',
                  background: 'linear-gradient(135deg, #10b981, #059669)',
                  color: '#ffffff',
                  border: 'none',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)',
                }}
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Confirm & Register Grievance</span>
              </button>

              <button
                type="button"
                onClick={() => handleSendText("No, I want to update location")}
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
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800 }}>
                  Complaint Registered Successfully!
                </h3>
                <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  Assigned Public Tracking ID: <strong>{completedComplaint.number}</strong> • SMS Dispatched
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
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                }}
              >
                <span>Track Status</span>
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
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem'
                }}
              >
                <RotateCcw size={14} /> Start New Grievance
              </button>
            </div>
          </div>
        )}

        {/* Text Fallback Input Bar (Enters exact same conversation engine) */}
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
          <input
            ref={textInputRef}
            type="text"
            placeholder="Type your message here (Tamil / Tanglish / English)..."
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendText()}
            style={{
              flex: 1,
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              fontSize: '0.9rem',
              outline: 'none'
            }}
          />
          <button
            type="button"
            onClick={() => handleSendText()}
            disabled={!textInput.trim() || voiceState === 'PROCESSING_AUDIO'}
            style={{
              padding: '0.75rem 1.25rem',
              borderRadius: 'var(--radius-md)',
              background: 'var(--primary-color)',
              color: '#ffffff',
              border: 'none',
              fontWeight: 700,
              cursor: !textInput.trim() ? 'not-allowed' : 'pointer',
              opacity: textInput.trim() ? 1 : 0.5,
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
      {Boolean(analysis.category || analysis.location || analysis.problem) && (
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            padding: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: 700 }}>
            <FileText className="w-4 h-4 text-primary" />
            <span>EXTRACTED CONVERSATION MEMORY (STRUCTURED SLOTS)</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
            <div style={{ background: 'var(--bg-secondary)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Category</span>
              <p style={{ margin: '0.15rem 0 0 0', fontWeight: 700, color: 'var(--text-primary)' }}>
                {analysis.category || 'Extracting...'}
              </p>
            </div>

            <div style={{ background: 'var(--bg-secondary)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Location</span>
              <p style={{ margin: '0.15rem 0 0 0', fontWeight: 700, color: 'var(--text-primary)' }}>
                {analysis.location || 'Extracting...'}
              </p>
            </div>

            <div style={{ background: 'var(--bg-secondary)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Duration / Scope</span>
              <p style={{ margin: '0.15rem 0 0 0', fontWeight: 700, color: 'var(--text-primary)' }}>
                {analysis.duration ? `${analysis.duration}${analysis.affected_scope ? ` • ${analysis.affected_scope}` : ''}` : (analysis.affected_scope || 'Pending...')}
              </p>
            </div>

            <div style={{ background: 'var(--bg-secondary)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Assigned Department</span>
              <p style={{ margin: '0.15rem 0 0 0', fontWeight: 700, color: 'var(--text-primary)' }}>
                {analysis.department || 'Municipal Administration'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
