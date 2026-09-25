import React, { useState, useEffect, useRef } from 'react';
import { useVoiceConversationEngine } from '../utils/useVoiceConversationEngine';
import { telephonyAudio } from '../utils/telephonyAudio';
import { IVRStreetMap } from '../components/IVRStreetMap';
import { VoiceStatus } from '../components/voice/VoiceStatus';
import { Link } from 'react-router-dom';
import {
  PhoneCall,
  PhoneOff,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Building2,
  MapPin,
  CheckCircle2,
  AlertTriangle,
  Send,
  Radio,
  Globe,
  RotateCcw,
  Check,
  Shield,
  Activity,
  Hash,
  MessageCircle,
  HelpCircle,
  Keyboard
} from 'lucide-react';

export const TollFreeHelplinePage: React.FC = () => {
  // Call States: 'IDLE' | 'RINGING' | 'CONNECTED' | 'ENDED'
  const [callState, setCallState] = useState<'IDLE' | 'RINGING' | 'CONNECTED' | 'ENDED'>('IDLE');
  const [callDuration, setCallDuration] = useState<number>(0);

  // Phone & Keypad state
  const [callerPhone, setCallerPhone] = useState<string>('+91 98430 98765');
  const [dialedNumber, setDialedNumber] = useState<string>('1913');
  const [showInCallKeypad, setShowInCallKeypad] = useState<boolean>(false);
  const [speakerEnabled, setSpeakerEnabled] = useState<boolean>(true);
  const [micMuted, setMicMuted] = useState<boolean>(false);
  const [textFallbackInput, setTextFallbackInput] = useState<string>('');

  const callTimerRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const textInputRef = useRef<HTMLInputElement | null>(null);

  // Initialize unified two-way voice conversation engine
  const {
    sessionId,
    voiceState,
    messages,
    liveTranscription,
    detectedLanguage,
    analysis,
    latitude,
    longitude,
    osmLocationName,
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
    mode: 'ivr',
    callerPhone: callerPhone
  });

  // Scroll to bottom of message list on updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, voiceState, liveTranscription, isAiSpeaking]);

  // Call Duration Timer
  useEffect(() => {
    if (callState === 'CONNECTED') {
      callTimerRef.current = setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);
    } else {
      if (callTimerRef.current) {
        clearInterval(callTimerRef.current);
        callTimerRef.current = null;
      }
    }
    return () => {
      if (callTimerRef.current) clearInterval(callTimerRef.current);
    };
  }, [callState]);

  // If complaint completes during call, update call state to ENDED after confirmation
  useEffect(() => {
    if (completedComplaint && voiceState === 'CONFIRMED') {
      // Allow brief moment for citizen to view completed receipt
      const t = setTimeout(() => {
        setCallState('ENDED');
        telephonyAudio.playCallConnected();
      }, 4000);
      return () => clearTimeout(t);
    }
  }, [completedComplaint, voiceState]);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      telephonyAudio.stopRinging();
    };
  }, []);

  const formatTimer = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  // -------------------------------------------------------------
  // Telephony Flow: Initiate Inbound Call to 1913
  // -------------------------------------------------------------
  const handleStartCall = async () => {
    setCallState('RINGING');
    setCallDuration(0);
    telephonyAudio.startRinging();

    // Authentic ringback tone delay before AI picks up
    setTimeout(async () => {
      telephonyAudio.stopRinging();
      telephonyAudio.playCallConnected();
      setCallState('CONNECTED');

      // Start true two-way conversational voice session
      await startSession();
    }, 2000);
  };

  // -------------------------------------------------------------
  // Hang Up Call
  // -------------------------------------------------------------
  const handleHangup = () => {
    telephonyAudio.stopRinging();
    telephonyAudio.playHangup();
    cancelConversation();
    setCallState('ENDED');
  };

  // -------------------------------------------------------------
  // Send Typed Message Fallback
  // -------------------------------------------------------------
  const handleSendText = async () => {
    if (!textFallbackInput.trim()) return;
    const text = textFallbackInput.trim();
    setTextFallbackInput('');
    await sendTextMessage(text);
  };

  // -------------------------------------------------------------
  // Focus on Text Input
  // -------------------------------------------------------------
  const handleFocusTextInput = () => {
    if (textInputRef.current) {
      textInputRef.current.focus();
    }
  };

  // -------------------------------------------------------------
  // DTMF Keypad Tones & Digit Actions
  // -------------------------------------------------------------
  const handleKeypadPress = (digit: string) => {
    telephonyAudio.playDtmf(digit);

    if (callState === 'IDLE') {
      setDialedNumber((prev) => prev + digit);
    } else if (callState === 'CONNECTED') {
      if (digit === '1') {
        // Digit 1: Quick Confirm
        confirmComplaint();
      } else if (digit === '2') {
        // Digit 2: Edit
        sendTextMessage('I want to change details / மாற்ற வேண்டும்');
      } else if (digit === '*') {
        // Digit *: Repeat last AI reply
        const lastAi = [...messages].reverse().find((m) => m.sender === 'ai');
        if (lastAi) playAiSpeech(lastAi.text, lastAi.language);
      } else if (digit === '#') {
        // Digit #: Hang up
        handleHangup();
      }
    }
  };

  // Determine current live status label and color
  const getLiveStatusDisplay = () => {
    switch (voiceState) {
      case 'AI_SPEAKING':
        return { label: '🔊 AI SPEAKING', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)' };
      case 'WAITING_FOR_CITIZEN':
        return { label: '🎤 Your turn — Listening...', color: '#34d399', bg: 'rgba(52, 211, 153, 0.15)' };
      case 'CITIZEN_SPEAKING':
        return { label: '🔴 Listening...', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.18)' };
      case 'PROCESSING_AUDIO':
        return { label: '🧠 PROCESSING AUDIO', color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.15)' };
      case 'TRANSCRIBING':
        return { label: '⏳ TRANSCRIBING', color: '#a78bfa', bg: 'rgba(167, 139, 250, 0.15)' };
      case 'DETECTING_LANGUAGE':
        return { label: '🌐 DETECTING LANGUAGE', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.15)' };
      case 'UNDERSTANDING':
        return { label: '⏳ UNDERSTANDING', color: '#818cf8', bg: 'rgba(129, 140, 248, 0.15)' };
      case 'GENERATING_RESPONSE':
        return { label: '🧠 RESPONDING', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)' };
      case 'CONFIRMED':
        return { label: '✓ COMPLAINT REGISTERED', color: '#34d399', bg: 'rgba(52, 211, 153, 0.2)' };
      case 'ERROR':
        return { label: '⚠️ AUDIO NOTICE', color: '#f87171', bg: 'rgba(248, 113, 113, 0.15)' };
      default:
        return { label: '⚡ READY', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.1)' };
    }
  };

  const currentStatus = getLiveStatusDisplay();

  return (
    <div className="page-container" style={{ maxWidth: '1440px', padding: '1.25rem' }}>
      {/* Top Banner: Official Telephony Helpline Bar */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9))',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          borderRadius: '16px',
          padding: '1.25rem 1.75rem',
          marginBottom: '1.5rem',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #0284c7, #0369a1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 20px rgba(56, 189, 248, 0.4)'
            }}
          >
            <PhoneCall size={26} color="#fff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <h1 style={{ margin: 0, fontSize: '1.45rem', fontWeight: 800, color: '#f8fafc' }}>
                Tamil Nadu CM Public Grievance Helpline (1913)
              </h1>
              <span
                style={{
                  background: 'rgba(16, 185, 129, 0.2)',
                  color: '#34d399',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  padding: '0.2rem 0.65rem',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem'
                }}
              >
                <Radio size={12} className="animate-pulse" /> TRUE TWO-WAY VOICE ENGINE
              </span>
            </div>
            <p style={{ margin: '0.25rem 0 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>
              Hands-Free Continuous Conversation • Automatic Voice Activity Detection (VAD) • Tamil, Tanglish & English
            </p>
          </div>
        </div>

        {/* Quick Telephony Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.45rem 0.9rem', borderRadius: '10px', fontSize: '0.8rem' }}>
            <span style={{ color: '#94a3b8' }}>Citizen Phone: </span>
            <span style={{ color: '#38bdf8', fontWeight: 700 }}>{callerPhone}</span>
          </div>
          <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.45rem 0.9rem', borderRadius: '10px', fontSize: '0.8rem' }}>
            <span style={{ color: '#94a3b8' }}>Helpline: </span>
            <span style={{ color: '#f59e0b', fontWeight: 700 }}>1913 / 1800-425-1913</span>
          </div>
        </div>
      </div>

      {/* Main 2-Column Telephony Simulator Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(380px, 490px) 1fr', gap: '1.5rem', alignItems: 'start' }}>
        {/* ========================================================= */}
        {/* COLUMN 1: REALISTIC SMARTPHONE IVR DEVICE FRAME */}
        {/* ========================================================= */}
        <div
          style={{
            background: 'linear-gradient(180deg, #090d16 0%, #0f172a 100%)',
            borderRadius: '36px',
            padding: '1.25rem',
            border: '4px solid #334155',
            boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.7), 0 0 40px rgba(56, 189, 248, 0.15)',
            position: 'relative'
          }}
        >
          {/* Smartphone Speaker & Camera Notch */}
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '0.75rem' }}>
            <div
              style={{
                width: '120px',
                height: '18px',
                background: '#1e293b',
                borderRadius: '0 0 12px 12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px'
              }}
            >
              <div style={{ width: '40px', height: '4px', background: '#475569', borderRadius: '2px' }} />
              <div style={{ width: '8px', height: '8px', background: '#0284c7', borderRadius: '50%' }} />
            </div>
          </div>

          {/* Smartphone Status Bar */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '0 0.5rem 0.75rem',
              color: '#94a3b8',
              fontSize: '0.75rem',
              fontWeight: 600,
              borderBottom: '1px solid rgba(255,255,255,0.06)'
            }}
          >
            <span>TN-GOV 5G</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>{callState === 'CONNECTED' ? formatTimer(callDuration) : '19:13'}</span>
              <span>🔋 98%</span>
            </div>
          </div>

          {/* ------------------------------------------------------- */}
          {/* PHONE SCREEN: IDLE / DIALER */}
          {/* ------------------------------------------------------- */}
          {callState === 'IDLE' && (
            <div style={{ padding: '1rem 0.5rem' }}>
              <div style={{ textAlign: 'center', padding: '1rem 0' }}>
                <div
                  style={{
                    width: '68px',
                    height: '68px',
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #0284c7, #0f766e)',
                    margin: '0 auto 0.75rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: '0 0 25px rgba(56, 189, 248, 0.35)'
                  }}
                >
                  <Building2 size={34} color="#fff" />
                </div>
                <h3 style={{ margin: '0 0 0.25rem', color: '#f8fafc', fontSize: '1.25rem', fontWeight: 800 }}>
                  Tamil Nadu Helpline
                </h3>
                <div
                  style={{
                    fontSize: '1.75rem',
                    fontWeight: 800,
                    letterSpacing: '2px',
                    color: '#38bdf8',
                    fontFamily: 'monospace'
                  }}
                >
                  {dialedNumber || '1913'}
                </div>
                <p style={{ margin: '0.35rem 0 0', color: '#64748b', fontSize: '0.75rem' }}>
                  Citizen Calls Free • Hands-Free True Two-Way AI Voice
                </p>
              </div>

              {/* Realistic Keypad Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: '0.75rem',
                  maxWidth: '300px',
                  margin: '1rem auto'
                }}
              >
                {[
                  { d: '1', sub: 'CONFIRM' },
                  { d: '2', sub: 'EDIT' },
                  { d: '3', sub: 'DEF' },
                  { d: '4', sub: 'GHI' },
                  { d: '5', sub: 'JKL' },
                  { d: '6', sub: 'MNO' },
                  { d: '7', sub: 'PQRS' },
                  { d: '8', sub: 'TUV' },
                  { d: '9', sub: 'WXYZ' },
                  { d: '*', sub: 'REPEAT' },
                  { d: '0', sub: '+' },
                  { d: '#', sub: 'END' }
                ].map((item) => (
                  <button
                    key={item.d}
                    onClick={() => handleKeypadPress(item.d)}
                    style={{
                      background: 'rgba(30, 41, 59, 0.8)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: '50%',
                      width: '64px',
                      height: '64px',
                      margin: '0 auto',
                      color: '#f8fafc',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                    onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.92)')}
                    onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
                  >
                    <span style={{ fontSize: '1.35rem', fontWeight: 700, lineHeight: 1 }}>{item.d}</span>
                    <span style={{ fontSize: '0.55rem', color: '#94a3b8', letterSpacing: '0.5px' }}>{item.sub}</span>
                  </button>
                ))}
              </div>

              {/* Call Action Button */}
              <div style={{ textAlign: 'center', marginTop: '1.25rem' }}>
                <button
                  onClick={handleStartCall}
                  style={{
                    background: 'linear-gradient(135deg, #10b981, #059669)',
                    border: 'none',
                    borderRadius: '50px',
                    padding: '0.9rem 2.25rem',
                    color: '#fff',
                    fontWeight: 800,
                    fontSize: '1rem',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.65rem',
                    boxShadow: '0 10px 30px rgba(16, 185, 129, 0.45)',
                    transition: 'transform 0.15s ease'
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-2px)')}
                  onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
                >
                  <PhoneCall size={20} /> CALL 1913 HELPLINE
                </button>
              </div>
            </div>
          )}

          {/* ------------------------------------------------------- */}
          {/* PHONE SCREEN: RINGING */}
          {/* ------------------------------------------------------- */}
          {callState === 'RINGING' && (
            <div style={{ padding: '3rem 1rem', textAlign: 'center' }}>
              <div
                style={{
                  width: '90px',
                  height: '90px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #0284c7, #38bdf8)',
                  margin: '0 auto 1.5rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 0 45px rgba(56, 189, 248, 0.6)'
                }}
                className="animate-pulse"
              >
                <PhoneCall size={42} color="#fff" />
              </div>
              <h3 style={{ margin: '0 0 0.5rem', color: '#f8fafc', fontSize: '1.4rem', fontWeight: 800 }}>
                Calling 1913 Helpline...
              </h3>
              <p style={{ margin: '0 0 2rem', color: '#38bdf8', fontSize: '0.9rem' }}>
                Connecting to Tamil Nadu CM Public Grievance Centre
              </p>

              <button
                onClick={handleHangup}
                style={{
                  background: '#ef4444',
                  border: 'none',
                  borderRadius: '50%',
                  width: '68px',
                  height: '68px',
                  color: '#fff',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 8px 25px rgba(239, 68, 68, 0.45)'
                }}
              >
                <PhoneOff size={28} />
              </button>
            </div>
          )}

          {/* ------------------------------------------------------- */}
          {/* PHONE SCREEN: CONNECTED / ACTIVE TWO-WAY CALL */}
          {/* ------------------------------------------------------- */}
          {callState === 'CONNECTED' && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '580px' }}>
              {/* In-Call Header */}
              <div
                style={{
                  textAlign: 'center',
                  padding: '0.5rem 0',
                  borderBottom: '1px solid rgba(255,255,255,0.06)'
                }}
              >
                <div style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 700, letterSpacing: '1px' }}>
                  ● 2-WAY VOICE CALL IN PROGRESS
                </div>
                <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#f8fafc', margin: '0.15rem 0' }}>
                  TN Grievance Cell (1913)
                </div>
                <div style={{ fontSize: '0.85rem', color: '#38bdf8', fontWeight: 700, fontFamily: 'monospace' }}>
                  {formatTimer(callDuration)}
                </div>
              </div>

              {/* Real-time Dynamic Status Badge */}
              <div
                style={{
                  padding: '0.5rem 0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  background: currentStatus.bg,
                  border: `1px solid ${currentStatus.color}40`,
                  borderRadius: '12px',
                  margin: '0.5rem 0 0.25rem'
                }}
              >
                <span style={{ fontSize: '0.78rem', color: currentStatus.color, fontWeight: 800 }}>
                  {currentStatus.label}
                </span>
                {voiceState === 'CITIZEN_SPEAKING' && (
                  <span className="animate-ping" style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444' }} />
                )}
              </div>

              {/* Permission / Unconfigured Engine Warning with Fallback Button */}
              {(isPermissionDenied || !isSpeechRecognitionAvailable || error) && (
                <div
                  style={{
                    background: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    borderRadius: '10px',
                    padding: '0.5rem 0.75rem',
                    margin: '0.35rem 0',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '0.5rem'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#f87171', fontSize: '0.75rem' }}>
                    <AlertTriangle size={14} className="flex-shrink-0" />
                    <span>{error || (isPermissionDenied ? 'Microphone permission is required for voice conversation.' : 'Speech recognition is not configured.')}</span>
                  </div>
                  <button
                    onClick={handleFocusTextInput}
                    style={{
                      background: '#0284c7',
                      border: 'none',
                      borderRadius: '6px',
                      padding: '0.25rem 0.6rem',
                      color: '#fff',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    TYPE INSTEAD
                  </button>
                </div>
              )}

              {/* Real-Time Live Transcript Stream */}
              <div
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  padding: '0.4rem 0.2rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.55rem'
                }}
              >
                {messages.map((m) => (
                  <div
                    key={m.id}
                    style={{
                      alignSelf: m.sender === 'citizen' ? 'flex-end' : 'flex-start',
                      maxWidth: '85%',
                      background:
                        m.sender === 'citizen'
                          ? 'linear-gradient(135deg, #0284c7, #0369a1)'
                          : 'linear-gradient(135deg, #1e293b, #0f172a)',
                      color: '#f8fafc',
                      padding: '0.65rem 0.85rem',
                      borderRadius: m.sender === 'citizen' ? '16px 16px 2px 16px' : '16px 16px 16px 2px',
                      border: '1px solid rgba(255,255,255,0.08)',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
                      fontSize: '0.82rem',
                      lineHeight: 1.4
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: 700, color: m.sender === 'citizen' ? '#bae6fd' : '#38bdf8' }}>
                        {m.sender === 'citizen' ? '👤 Citizen Caller' : '🏛️ Helpline AI'}
                      </span>
                      <span style={{ fontSize: '0.6rem', color: '#94a3b8' }}>{m.time}</span>
                    </div>
                    <div style={{ whiteSpace: 'pre-line' }}>{m.text}</div>
                  </div>
                ))}

                {/* Live speech preview if citizen currently speaking */}
                {voiceState === 'CITIZEN_SPEAKING' && liveTranscription && (
                  <div
                    style={{
                      alignSelf: 'flex-end',
                      background: 'rgba(2, 132, 199, 0.3)',
                      border: '1px dashed #38bdf8',
                      borderRadius: '12px',
                      padding: '0.45rem 0.75rem',
                      fontSize: '0.78rem',
                      color: '#bae6fd'
                    }}
                  >
                    <span>🎙️ {liveTranscription}</span>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Confirmation Action Box (When state is CONFIRMING) */}
              {(voiceState === 'CONFIRMING' || voiceState === 'WAITING_FOR_CITIZEN') && analysis.category && analysis.location && (
                <div
                  style={{
                    background: 'rgba(245, 158, 11, 0.12)',
                    border: '1px solid rgba(245, 158, 11, 0.35)',
                    borderRadius: '12px',
                    padding: '0.5rem 0.75rem',
                    margin: '0.35rem 0',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '0.5rem'
                  }}
                >
                  <div style={{ fontSize: '0.72rem', color: '#fef08a' }}>
                    <span>Say <strong>"Yes / ஆமாம்"</strong> or click to confirm</span>
                  </div>
                  <div style={{ display: 'flex', gap: '0.35rem' }}>
                    <button
                      onClick={confirmComplaint}
                      style={{
                        background: '#10b981',
                        border: 'none',
                        borderRadius: '6px',
                        padding: '0.3rem 0.75rem',
                        color: '#fff',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.25rem'
                      }}
                    >
                      <CheckCircle2 size={12} /> Confirm
                    </button>
                    <button
                      onClick={() => sendTextMessage('No, change details')}
                      style={{
                        background: '#334155',
                        border: 'none',
                        borderRadius: '6px',
                        padding: '0.3rem 0.6rem',
                        color: '#cbd5e1',
                        fontSize: '0.72rem',
                        cursor: 'pointer'
                      }}
                    >
                      Change
                    </button>
                  </div>
                </div>
              )}

              {/* Text Input Fallback */}
              <div style={{ display: 'flex', gap: '0.4rem', margin: '0.35rem 0' }}>
                <input
                  ref={textInputRef}
                  type="text"
                  value={textFallbackInput}
                  onChange={(e) => setTextFallbackInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendText()}
                  placeholder="Type message (Tamil / Tanglish / English)..."
                  style={{
                    flex: 1,
                    background: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '20px',
                    padding: '0.45rem 0.85rem',
                    color: '#f8fafc',
                    fontSize: '0.8rem',
                    outline: 'none'
                  }}
                />
                <button
                  onClick={handleSendText}
                  disabled={!textFallbackInput.trim() || voiceState === 'PROCESSING_AUDIO'}
                  style={{
                    background: '#0284c7',
                    border: 'none',
                    borderRadius: '50%',
                    width: '34px',
                    height: '34px',
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: textFallbackInput.trim() ? 'pointer' : 'default',
                    opacity: textFallbackInput.trim() ? 1 : 0.4
                  }}
                >
                  <Send size={15} />
                </button>
              </div>

              {/* In-Call Phone Control Panel */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(5, 1fr)',
                  gap: '0.35rem',
                  paddingTop: '0.45rem',
                  borderTop: '1px solid rgba(255,255,255,0.08)'
                }}
              >
                {/* 1. Mute Toggle */}
                <button
                  onClick={() => setMicMuted(!micMuted)}
                  style={{
                    background: micMuted ? '#ef4444' : '#1e293b',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '0.45rem',
                    color: '#fff',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '2px',
                    cursor: 'pointer',
                    fontSize: '0.65rem'
                  }}
                >
                  {micMuted ? <MicOff size={16} /> : <Mic size={16} />}
                  <span>{micMuted ? 'Muted' : 'Mute'}</span>
                </button>

                {/* 2. Speakerphone Toggle */}
                <button
                  onClick={() => setSpeakerEnabled(!speakerEnabled)}
                  style={{
                    background: speakerEnabled ? '#0284c7' : '#1e293b',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '0.45rem',
                    color: '#fff',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '2px',
                    cursor: 'pointer',
                    fontSize: '0.65rem'
                  }}
                >
                  {speakerEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
                  <span>Speaker</span>
                </button>

                {/* 3. Speak Push-to-Talk Manual Override */}
                <button
                  onClick={toggleRecording}
                  style={{
                    background: isRecording ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 'linear-gradient(135deg, #10b981, #059669)',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '0.45rem',
                    color: '#fff',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '2px',
                    cursor: 'pointer',
                    fontSize: '0.65rem',
                    boxShadow: isRecording ? '0 0 15px rgba(239, 68, 68, 0.6)' : 'none'
                  }}
                >
                  <Mic size={16} />
                  <span>{isRecording ? 'Stop' : 'Speak'}</span>
                </button>

                {/* 4. DTMF Keypad Drawer */}
                <button
                  onClick={() => setShowInCallKeypad(!showInCallKeypad)}
                  style={{
                    background: showInCallKeypad ? '#f59e0b' : '#1e293b',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '0.45rem',
                    color: '#fff',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '2px',
                    cursor: 'pointer',
                    fontSize: '0.65rem'
                  }}
                >
                  <Hash size={16} />
                  <span>Keypad</span>
                </button>

                {/* 5. End Call */}
                <button
                  onClick={handleHangup}
                  style={{
                    background: '#ef4444',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '0.45rem',
                    color: '#fff',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '2px',
                    cursor: 'pointer',
                    fontSize: '0.65rem'
                  }}
                >
                  <PhoneOff size={16} />
                  <span>End</span>
                </button>
              </div>

              {/* In-Call Keypad Drawer Dropdown */}
              {showInCallKeypad && (
                <div
                  style={{
                    background: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '14px',
                    padding: '0.65rem',
                    marginTop: '0.4rem',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, 1fr)',
                    gap: '0.35rem'
                  }}
                >
                  {[
                    { k: '1', label: '1 (Confirm)' },
                    { k: '2', label: '2 (Edit)' },
                    { k: '*', label: '* (Repeat)' },
                    { k: '#', label: '# (End)' }
                  ].map((btn) => (
                    <button
                      key={btn.k}
                      onClick={() => handleKeypadPress(btn.k)}
                      style={{
                        background: '#1e293b',
                        border: '1px solid #475569',
                        borderRadius: '8px',
                        padding: '0.35rem',
                        color: '#f8fafc',
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      {btn.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ------------------------------------------------------- */}
          {/* PHONE SCREEN: ENDED / SUMMARY RECEIPT */}
          {/* ------------------------------------------------------- */}
          {callState === 'ENDED' && (
            <div style={{ padding: '1.5rem 0.5rem', textAlign: 'center' }}>
              <div
                style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '50%',
                  background: completedComplaint?.number ? 'linear-gradient(135deg, #10b981, #059669)' : '#ef4444',
                  margin: '0 auto 1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                {completedComplaint?.number ? <Check size={32} color="#fff" /> : <PhoneOff size={32} color="#fff" />}
              </div>

              <h3 style={{ margin: '0 0 0.25rem', color: '#f8fafc', fontSize: '1.25rem', fontWeight: 800 }}>
                {completedComplaint?.number ? 'Grievance Registered!' : 'Call Completed'}
              </h3>
              <p style={{ margin: '0 0 1rem', color: '#94a3b8', fontSize: '0.8rem' }}>
                Duration: {formatTimer(callDuration)} • Helpline 1913
              </p>

              {completedComplaint?.number && (
                <div
                  style={{
                    background: 'rgba(16, 185, 129, 0.12)',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    borderRadius: '12px',
                    padding: '0.85rem',
                    margin: '0.75rem 0',
                    textAlign: 'left'
                  }}
                >
                  <div style={{ fontSize: '0.7rem', color: '#34d399', fontWeight: 700 }}>OFFICIAL TRACKING ID</div>
                  <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#f8fafc', fontFamily: 'monospace' }}>
                    {completedComplaint.number}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                    Department: <span style={{ color: '#38bdf8' }}>{completedComplaint.department || analysis.department || 'Municipal Administration'}</span>
                  </div>
                </div>
              )}

              {/* SMS Dispatch Receipt */}
              {completedComplaint?.number && (
                <div
                  style={{
                    background: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '12px',
                    padding: '0.75rem',
                    textAlign: 'left',
                    margin: '0.75rem 0'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#38bdf8', fontSize: '0.7rem', fontWeight: 700 }}>
                    <MessageCircle size={14} /> SMS Notification Dispatched
                  </div>
                  <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', color: '#cbd5e1' }}>
                    "TN Gov Grievance #{completedComplaint.number} registered. Track status at voxentra.gov.in/track"
                  </p>
                </div>
              )}

              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1.25rem', justifyContent: 'center' }}>
                <button
                  onClick={() => setCallState('IDLE')}
                  style={{
                    background: '#0284c7',
                    border: 'none',
                    borderRadius: '20px',
                    padding: '0.65rem 1.25rem',
                    color: '#fff',
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.35rem'
                  }}
                >
                  <RotateCcw size={16} /> New Call
                </button>
                {completedComplaint?.number && (
                  <Link
                    to={`/complaints?search=${completedComplaint.number}`}
                    style={{
                      background: '#10b981',
                      border: 'none',
                      borderRadius: '20px',
                      padding: '0.65rem 1.25rem',
                      color: '#fff',
                      fontWeight: 700,
                      fontSize: '0.85rem',
                      textDecoration: 'none',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem'
                    }}
                  >
                    Track Status
                  </Link>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ========================================================= */}
        {/* COLUMN 2: REAL-TIME CONVERSATIONAL INTELLIGENCE HUD */}
        {/* ========================================================= */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Card 1: Live Voice State & Speech Intelligence */}
          <div
            style={{
              background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95))',
              border: '1px solid rgba(56, 189, 248, 0.2)',
              borderRadius: '20px',
              padding: '1.25rem',
              boxShadow: '0 8px 30px rgba(0,0,0,0.25)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <Activity size={20} color="#38bdf8" />
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc' }}>
                  Live Conversational Engine State
                </h3>
              </div>
              <span
                style={{
                  background: 'rgba(56, 189, 248, 0.15)',
                  color: '#38bdf8',
                  padding: '0.2rem 0.6rem',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  fontWeight: 700
                }}
              >
                FastAPI Unified Voice Backend
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.85rem' }}>
              <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Detected Language</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#38bdf8', marginTop: '0.2rem' }}>
                  {detectedLanguage}
                </div>
                <div style={{ fontSize: '0.65rem', color: '#10b981' }}>Auto-Preserved Per Turn</div>
              </div>

              <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>SIP Call Session ID</div>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem', fontFamily: 'monospace' }}>
                  {sessionId || 'Awaiting connection...'}
                </div>
                <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Universal Transport Engine</div>
              </div>

              <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Current Priority</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 800, color: analysis.priority === 'HIGH' || analysis.priority === 'CRITICAL' ? '#ef4444' : '#f59e0b', marginTop: '0.2rem' }}>
                  {analysis.priority || 'MEDIUM'}
                </div>
                <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Dynamic Slot Fusion</div>
              </div>
            </div>
          </div>

          {/* Card 2: Extracted 10-Point Slot Memory HUD */}
          <div
            style={{
              background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95))',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '20px',
              padding: '1.25rem',
              boxShadow: '0 8px 30px rgba(0,0,0,0.25)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <Shield size={20} color="#10b981" />
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc' }}>
                  Extracted Conversation Memory (Slots)
                </h3>
              </div>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Dynamic Memory Retention</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.65rem' }}>
              {[
                { label: 'Category', val: analysis.category },
                { label: 'Problem Description', val: analysis.problem },
                { label: 'Location / District / Area', val: analysis.location },
                { label: 'Duration', val: analysis.duration },
                { label: 'Affected Scope', val: analysis.affected_scope },
                { label: 'Department', val: analysis.department }
              ].map((slot, idx) => (
                <div
                  key={idx}
                  style={{
                    background: slot.val ? 'rgba(16, 185, 129, 0.08)' : '#0f172a',
                    border: slot.val ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(255,255,255,0.05)',
                    padding: '0.65rem 0.85rem',
                    borderRadius: '10px'
                  }}
                >
                  <div style={{ fontSize: '0.65rem', color: slot.val ? '#34d399' : '#64748b', fontWeight: 700 }}>
                    {slot.val ? '✓ ' : '○ '} {slot.label}
                  </div>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: slot.val ? '#f8fafc' : '#475569', marginTop: '0.2rem' }}>
                    {slot.val || 'Awaiting citizen speech...'}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Card 3: Interactive OpenStreetMap GIS Map */}
          <div
            style={{
              background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95))',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '20px',
              padding: '1.25rem',
              boxShadow: '0 8px 30px rgba(0,0,0,0.25)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <MapPin size={20} color="#f59e0b" />
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc' }}>
                  OpenStreetMap GIS Geolocation Pin
                </h3>
              </div>
              <span style={{ fontSize: '0.75rem', color: '#38bdf8', fontWeight: 700 }}>
                {osmLocationName || analysis.location || 'Tamil Nadu'}
              </span>
            </div>

            <div style={{ height: '230px', borderRadius: '12px', overflow: 'hidden', border: '1px solid #334155' }}>
              <IVRStreetMap
                latitude={latitude || '11.016844'}
                longitude={longitude || '76.955833'}
                locationName={osmLocationName || analysis.location || 'Tamil Nadu'}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
