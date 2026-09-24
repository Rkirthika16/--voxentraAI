import React, { useState, useEffect, useRef } from 'react';
import { ivrApi } from '../api/ivr';
import { voiceApi } from '../api/voice';
import { speech } from '../utils/speech';
import { telephonyAudio } from '../utils/telephonyAudio';
import { IVRStreetMap } from '../components/IVRStreetMap';
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
  MessageSquare,
  Sparkles,
  Radio,
  Globe,
  RotateCcw,
  Check,
  Headphones,
  Shield,
  Activity,
  Smartphone,
  Hash,
  Delete,
  Clock,
  MessageCircle,
  FileText,
  HelpCircle,
  CheckCircle
} from 'lucide-react';

interface ChatMessage {
  id: string;
  sender: 'ai' | 'citizen';
  text: string;
  language: string;
  time: string;
  intent?: string;
  audioBase64?: string | null;
}

export const TollFreeHelplinePage: React.FC = () => {
  // Call States: 'IDLE' | 'DIALING' | 'RINGING' | 'CONNECTED' | 'ENDED'
  const [callState, setCallState] = useState<'IDLE' | 'DIALING' | 'RINGING' | 'CONNECTED' | 'ENDED'>('IDLE');
  const [callDuration, setCallDuration] = useState<number>(0);

  // Phone & Keypad state
  const [callerPhone, setCallerPhone] = useState<string>('+91 98430 98765');
  const [dialedNumber, setDialedNumber] = useState<string>('1913');
  const [showInCallKeypad, setShowInCallKeypad] = useState<boolean>(false);
  const [speakerEnabled, setSpeakerEnabled] = useState<boolean>(true);
  const [micMuted, setMicMuted] = useState<boolean>(false);

  // Voice & Conversation State
  const [detectedLanguage, setDetectedLanguage] = useState<string>('Auto-Detecting...');
  const [languageConfidence, setLanguageConfidence] = useState<number>(0.98);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [isAiSpeaking, setIsAiSpeaking] = useState<boolean>(false);
  const [spokenText, setSpokenText] = useState<string>('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentCallSid, setCurrentCallSid] = useState<string>('');
  const [collectionFields, setCollectionFields] = useState<Record<string, any>>({});
  const [isConfirmationPending, setIsConfirmationPending] = useState<boolean>(false);
  const [createdComplaintNumber, setCreatedComplaintNumber] = useState<string | null>(null);
  const [assignedDepartment, setAssignedDepartment] = useState<string | null>(null);
  const [smsSentStatus, setSmsSentStatus] = useState<boolean>(false);
  const [distressLevel, setDistressLevel] = useState<string>('NORMAL');
  const [urgencyScore, setUrgencyScore] = useState<number>(45);

  // GIS Location Pin
  const [currentLatitude, setCurrentLatitude] = useState<string | number | null>('11.016844');
  const [currentLongitude, setCurrentLongitude] = useState<string | number | null>('76.955833');
  const [osmLocationName, setOsmLocationName] = useState<string | null>('Coimbatore, Tamil Nadu');

  // Audio / Mic Refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const callTimerRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, callState, isProcessing, isAiSpeaking]);

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

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      telephonyAudio.stopRinging();
      speech.stop();
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const formatTimer = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  // -------------------------------------------------------------
  // Telephony Flow: Initiate Inbound Call
  // -------------------------------------------------------------
  const handleStartCall = async () => {
    speech.stop();
    setCallState('RINGING');
    setCallDuration(0);
    setMessages([]);
    setCreatedComplaintNumber(null);
    setCollectionFields({});
    setIsConfirmationPending(false);
    setSmsSentStatus(false);

    telephonyAudio.startRinging();

    try {
      // 1. Initiate toll-free call session via API
      const initRes = await ivrApi.initiateCall(callerPhone, dialedNumber || '1913');
      const sid = initRes.call_sid;
      setCurrentCallSid(sid);

      // Simulate 1.8s ringback delay for authentic telephone experience
      setTimeout(async () => {
        telephonyAudio.stopRinging();
        telephonyAudio.playCallConnected();
        setCallState('CONNECTED');

        // Welcome greeting from Tamil Nadu CM Helpline
        const welcomeTamil = initRes.greeting_tamil + ' ' + initRes.prompt_tamil;
        const welcomeEn = initRes.greeting_english + ' ' + initRes.prompt_english;

        const initialMsg: ChatMessage = {
          id: `ai_${Date.now()}`,
          sender: 'ai',
          text: `${initRes.greeting_tamil}\n${initRes.prompt_tamil}\n\n${initRes.greeting_english}`,
          language: 'Tamil & English',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages([initialMsg]);

        if (speakerEnabled) {
          playVoice(welcomeTamil, 'Tamil', () => {
            // Auto-start listening after welcome message so Citizen Speaks First!
            startRecording(sid);
          });
        } else {
          startRecording(sid);
        }
      }, 2000);
    } catch (err: any) {
      telephonyAudio.stopRinging();
      setCallState('IDLE');
      alert(`Call failed to connect: ${err.message || 'Please check backend server'}`);
    }
  };

  // -------------------------------------------------------------
  // Hang Up Call
  // -------------------------------------------------------------
  const handleHangup = () => {
    telephonyAudio.stopRinging();
    telephonyAudio.playHangup();
    speech.stop();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      try {
        mediaRecorderRef.current.stop();
      } catch {}
    }
    setIsRecording(false);
    setIsAiSpeaking(false);
    setCallState('ENDED');
  };

  // -------------------------------------------------------------
  // Audio Speech Synthesis
  // -------------------------------------------------------------
  const playVoice = (text: string, lang: string, onDone?: () => void) => {
    if (!speakerEnabled) {
      if (onDone) onDone();
      return;
    }
    speech.stop();
    setIsAiSpeaking(true);
    speech.speak(text, {
      language: lang,
      volume: 1.0,
      rate: 0.94,
      onStart: () => setIsAiSpeaking(true),
      onEnd: () => {
        setIsAiSpeaking(false);
        if (onDone) onDone();
      },
      onError: () => {
        setIsAiSpeaking(false);
        if (onDone) onDone();
      }
    });
  };

  // -------------------------------------------------------------
  // Microphone Recording & Turn Processing
  // -------------------------------------------------------------
  const startRecording = async (sidOverride?: string) => {
    if (isRecording || micMuted) return;
    const sid = sidOverride || currentCallSid;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach((track) => track.stop());
        if (audioBlob.size > 2000) {
          await processVoiceAudioTurn(audioBlob, sid);
        }
      };

      recorder.start();
      setIsRecording(true);
    } catch (e) {
      console.warn('Microphone access note: Using text input mode or web speech fallback');
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  // Process voice audio through backend speech recognition and IVR understanding
  const processVoiceAudioTurn = async (audioBlob: Blob, sid: string) => {
    setIsProcessing(true);
    try {
      const audioFile = new File([audioBlob], `ivr_${Date.now()}.webm`, { type: 'audio/webm' });
      const voiceRes = await voiceApi.sendAudioTurn(sid, audioFile, callerPhone);

      const userText = voiceRes.transcription || 'Voice message sent';
      const userMsg: ChatMessage = {
        id: `user_${Date.now()}`,
        sender: 'citizen',
        text: userText,
        language: voiceRes.detected_language || 'Auto',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      const aiText = voiceRes.ai_text || voiceRes.ai_spoken || 'Understood.';
      const aiMsg: ChatMessage = {
        id: `ai_${Date.now()}`,
        sender: 'ai',
        text: aiText,
        language: voiceRes.detected_language || 'Tamil',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        audioBase64: voiceRes.audio_base64
      };

      setMessages((prev) => [...prev, userMsg, aiMsg]);
      setDetectedLanguage(voiceRes.detected_language || 'Tamil');

      if (voiceRes.context) {
        setCollectionFields(voiceRes.context);
        if (voiceRes.context.location) {
          setOsmLocationName(voiceRes.context.location);
        }
      }

      if (voiceRes.state === 'CONFIRMING') {
        setIsConfirmationPending(true);
      }

      if (voiceRes.complaint_number) {
        setCreatedComplaintNumber(voiceRes.complaint_number);
        setSmsSentStatus(true);
      }

      // Play audio response
      const spokenText = voiceRes.ai_spoken || voiceRes.ai_text;
      if (speakerEnabled) {
        playVoice(spokenText, voiceRes.detected_language || 'Tamil', () => {
          if (voiceRes.state !== 'COMPLETED') {
            startRecording(sid);
          }
        });
      }
    } catch (err: any) {
      console.error('Audio processing error:', err);
    } finally {
      setIsProcessing(false);
    }
  };

  // -------------------------------------------------------------
  // Send Text Turn (Fallback for Noisy Environment)
  // -------------------------------------------------------------
  const handleSendTextMessage = async () => {
    if (!spokenText.trim() || isProcessing) return;

    const textToSend = spokenText.trim();
    setSpokenText('');
    setIsProcessing(true);

    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      sender: 'citizen',
      text: textToSend,
      language: detectedLanguage,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const dialogueRes = await ivrApi.dialogueTurn({
        call_sid: currentCallSid,
        dialogue_turn: messages.length + 1,
        caller_phone: callerPhone,
        user_speech: textToSend,
        language_preference: 'Auto'
      });

      const aiText = dialogueRes.ai_spoken_reply || 'Understood.';
      const aiMsg: ChatMessage = {
        id: `ai_${Date.now()}`,
        sender: 'ai',
        text: aiText,
        language: dialogueRes.detected_language || 'Tamil',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages((prev) => [...prev, aiMsg]);
      setDetectedLanguage(dialogueRes.detected_language || 'Tamil');
      setLanguageConfidence(dialogueRes.language_confidence || 0.98);

      if (dialogueRes.collection_state) {
        setCollectionFields(dialogueRes.collection_state);
      }

      if (dialogueRes.is_confirmation_pending) {
        setIsConfirmationPending(true);
      }

      if (dialogueRes.complaint_number) {
        setCreatedComplaintNumber(dialogueRes.complaint_number);
        setAssignedDepartment(dialogueRes.suggested_department || 'Municipal Administration');
        setSmsSentStatus(true);
      }

      if (dialogueRes.latitude && dialogueRes.longitude) {
        setCurrentLatitude(dialogueRes.latitude);
        setCurrentLongitude(dialogueRes.longitude);
        setOsmLocationName(dialogueRes.osm_location_name || 'Tamil Nadu');
      }

      if (speakerEnabled) {
        playVoice(aiText, dialogueRes.detected_language || 'Tamil', () => {
          if (!dialogueRes.is_completed) {
            startRecording(currentCallSid);
          }
        });
      }
    } catch (e: any) {
      console.error('Dialogue error:', e);
    } finally {
      setIsProcessing(false);
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
      // In-call DTMF processing
      if (digit === '1') {
        // Digit 1: Quick Confirm
        setSpokenText('ஆமாம் சரி (Yes, Confirm)');
      } else if (digit === '2') {
        // Digit 2: Edit / Correct
        setSpokenText('மாற்ற வேண்டும் (Edit Details)');
      } else if (digit === '*') {
        // Digit *: Repeat last prompt
        if (messages.length > 0) {
          const lastAi = [...messages].reverse().find((m) => m.sender === 'ai');
          if (lastAi) playVoice(lastAi.text, lastAi.language);
        }
      } else if (digit === '#') {
        // Digit #: Hang up
        handleHangup();
      }
    }
  };

  return (
    <div className="page-container" style={{ maxWidth: '1400px', padding: '1.25rem' }}>
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
                <Radio size={12} className="animate-pulse" /> SIP TRUNK ACTIVE
              </span>
            </div>
            <p style={{ margin: '0.25rem 0 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>
              Real-time telephone IVR simulation supporting Tamil, Tanglish & English • Exotel / Twilio Virtual PBX
            </p>
          </div>
        </div>

        {/* Quick Telephony Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.45rem 0.9rem', borderRadius: '10px', fontSize: '0.8rem' }}>
            <span style={{ color: '#94a3b8' }}>Caller Phone: </span>
            <span style={{ color: '#38bdf8', fontWeight: 700 }}>{callerPhone}</span>
          </div>
          <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.45rem 0.9rem', borderRadius: '10px', fontSize: '0.8rem' }}>
            <span style={{ color: '#94a3b8' }}>Helpline: </span>
            <span style={{ color: '#f59e0b', fontWeight: 700 }}>1913 / 1800-425-1913</span>
          </div>
        </div>
      </div>

      {/* Main 2-Column Telephony Simulator Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(360px, 480px) 1fr', gap: '1.5rem', alignItems: 'start' }}>
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
          {/* PHONE SCREEN CONTENT: IDLE / DIALER */}
          {/* ------------------------------------------------------- */}
          {callState === 'IDLE' && (
            <div style={{ padding: '1rem 0.5rem' }}>
              {/* Caller Display */}
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
                  Citizen Calls Free of Cost • 24x7 AI Assistance
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
          {/* PHONE SCREEN CONTENT: RINGING */}
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
          {/* PHONE SCREEN CONTENT: CONNECTED / ACTIVE CALL */}
          {/* ------------------------------------------------------- */}
          {callState === 'CONNECTED' && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '560px' }}>
              {/* In-Call Header */}
              <div
                style={{
                  textAlign: 'center',
                  padding: '0.6rem 0',
                  borderBottom: '1px solid rgba(255,255,255,0.06)'
                }}
              >
                <div style={{ fontSize: '0.8rem', color: '#10b981', fontWeight: 700, letterSpacing: '1px' }}>
                  ● CALL IN PROGRESS
                </div>
                <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#f8fafc', margin: '0.2rem 0' }}>
                  TN Grievance Cell (1913)
                </div>
                <div style={{ fontSize: '0.9rem', color: '#38bdf8', fontWeight: 700, fontFamily: 'monospace' }}>
                  {formatTimer(callDuration)}
                </div>
              </div>

              {/* Live Audio Visualizer Bar */}
              <div
                style={{
                  padding: '0.65rem 1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '4px',
                  background: 'rgba(15, 23, 42, 0.6)',
                  borderRadius: '12px',
                  margin: '0.65rem 0'
                }}
              >
                <div style={{ fontSize: '0.75rem', color: isRecording ? '#ef4444' : isAiSpeaking ? '#38bdf8' : '#94a3b8', fontWeight: 700, marginRight: '0.5rem' }}>
                  {isRecording ? '🎙️ LISTENING TO CITIZEN' : isAiSpeaking ? '🔊 AGENT SPEAKING' : '⚡ READY'}
                </div>
                {[12, 24, 38, 18, 44, 28, 50, 20, 34, 16, 26, 40].map((h, i) => (
                  <div
                    key={i}
                    style={{
                      width: '3px',
                      height: (isRecording || isAiSpeaking) ? `${h}px` : '4px',
                      background: isRecording ? '#ef4444' : isAiSpeaking ? '#38bdf8' : '#475569',
                      borderRadius: '2px',
                      transition: 'height 0.15s ease'
                    }}
                  />
                ))}
              </div>

              {/* Real-Time Live Transcript Stream */}
              <div
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  padding: '0.5rem 0.25rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.65rem'
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

                {isProcessing && (
                  <div style={{ alignSelf: 'flex-start', background: '#1e293b', padding: '0.5rem 0.75rem', borderRadius: '12px', fontSize: '0.75rem', color: '#38bdf8' }}>
                    <span className="animate-pulse">⏳ AI recognizing speech & updating slots...</span>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Text Input Fallback (for noisy backgrounds) */}
              <div style={{ display: 'flex', gap: '0.4rem', margin: '0.4rem 0' }}>
                <input
                  type="text"
                  value={spokenText}
                  onChange={(e) => setSpokenText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendTextMessage()}
                  placeholder="Type complaint if noisy..."
                  style={{
                    flex: 1,
                    background: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '20px',
                    padding: '0.5rem 0.85rem',
                    color: '#f8fafc',
                    fontSize: '0.8rem',
                    outline: 'none'
                  }}
                />
                <button
                  onClick={handleSendTextMessage}
                  disabled={!spokenText.trim() || isProcessing}
                  style={{
                    background: '#0284c7',
                    border: 'none',
                    borderRadius: '50%',
                    width: '36px',
                    height: '36px',
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: spokenText.trim() ? 'pointer' : 'default',
                    opacity: spokenText.trim() ? 1 : 0.4
                  }}
                >
                  <Send size={16} />
                </button>
              </div>

              {/* In-Call Phone Control Panel */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(5, 1fr)',
                  gap: '0.4rem',
                  paddingTop: '0.5rem',
                  borderTop: '1px solid rgba(255,255,255,0.08)'
                }}
              >
                {/* 1. Mute Toggle */}
                <button
                  onClick={() => setMicMuted(!micMuted)}
                  style={{
                    background: micMuted ? '#ef4444' : '#1e293b',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '0.5rem',
                    color: '#fff',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '2px',
                    cursor: 'pointer',
                    fontSize: '0.65rem'
                  }}
                >
                  {micMuted ? <MicOff size={18} /> : <Mic size={18} />}
                  <span>{micMuted ? 'Muted' : 'Mute'}</span>
                </button>

                {/* 2. Speakerphone Toggle */}
                <button
                  onClick={() => setSpeakerEnabled(!speakerEnabled)}
                  style={{
                    background: speakerEnabled ? '#0284c7' : '#1e293b',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '0.5rem',
                    color: '#fff',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '2px',
                    cursor: 'pointer',
                    fontSize: '0.65rem'
                  }}
                >
                  {speakerEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
                  <span>Speaker</span>
                </button>

                {/* 3. Speak Push-to-Talk */}
                <button
                  onClick={isRecording ? stopRecording : () => startRecording(currentCallSid)}
                  style={{
                    background: isRecording ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 'linear-gradient(135deg, #10b981, #059669)',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '0.5rem',
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
                  <Mic size={18} />
                  <span>{isRecording ? 'Stop' : 'Speak'}</span>
                </button>

                {/* 4. DTMF Keypad Drawer */}
                <button
                  onClick={() => setShowInCallKeypad(!showInCallKeypad)}
                  style={{
                    background: showInCallKeypad ? '#f59e0b' : '#1e293b',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '0.5rem',
                    color: '#fff',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '2px',
                    cursor: 'pointer',
                    fontSize: '0.65rem'
                  }}
                >
                  <Hash size={18} />
                  <span>Keypad</span>
                </button>

                {/* 5. End Call */}
                <button
                  onClick={handleHangup}
                  style={{
                    background: '#ef4444',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '0.5rem',
                    color: '#fff',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '2px',
                    cursor: 'pointer',
                    fontSize: '0.65rem'
                  }}
                >
                  <PhoneOff size={18} />
                  <span>End</span>
                </button>
              </div>

              {/* In-Call Keypad Drawer Dropdown */}
              {showInCallKeypad && (
                <div
                  style={{
                    background: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '16px',
                    padding: '0.75rem',
                    marginTop: '0.5rem',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, 1fr)',
                    gap: '0.4rem'
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
                        padding: '0.4rem',
                        color: '#f8fafc',
                        fontSize: '0.7rem',
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
          {/* PHONE SCREEN CONTENT: ENDED / SUMMARY */}
          {/* ------------------------------------------------------- */}
          {callState === 'ENDED' && (
            <div style={{ padding: '1.5rem 0.5rem', textAlign: 'center' }}>
              <div
                style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '50%',
                  background: createdComplaintNumber ? 'linear-gradient(135deg, #10b981, #059669)' : '#ef4444',
                  margin: '0 auto 1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                {createdComplaintNumber ? <Check size={32} color="#fff" /> : <PhoneOff size={32} color="#fff" />}
              </div>

              <h3 style={{ margin: '0 0 0.25rem', color: '#f8fafc', fontSize: '1.25rem', fontWeight: 800 }}>
                {createdComplaintNumber ? 'Grievance Registered!' : 'Call Completed'}
              </h3>
              <p style={{ margin: '0 0 1rem', color: '#94a3b8', fontSize: '0.8rem' }}>
                Duration: {formatTimer(callDuration)} • Helpline 1913
              </p>

              {createdComplaintNumber && (
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
                  <div style={{ fontSize: '0.7rem', color: '#34d399', fontWeight: 700 }}>COMPLAINT TRACKING ID</div>
                  <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#f8fafc', fontFamily: 'monospace' }}>
                    {createdComplaintNumber}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                    Department: <span style={{ color: '#38bdf8' }}>{assignedDepartment || 'Municipal Administration'}</span>
                  </div>
                </div>
              )}

              {/* Virtual SMS Receipt */}
              {smsSentStatus && (
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
                    <MessageCircle size={14} /> SMS Notification Delivered
                  </div>
                  <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', color: '#cbd5e1' }}>
                    "TN Gov Grievance #{createdComplaintNumber} registered. Track status at voxentra.gov.in/track"
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
                {createdComplaintNumber && (
                  <Link
                    to={`/tracking?id=${createdComplaintNumber}`}
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
        {/* COLUMN 2: REAL-TIME TELEPHONY INTELLIGENCE HUD */}
        {/* ========================================================= */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Card 1: Live Telephony & Speech Intelligence */}
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
                  Live Telephony & AI Speech Intelligence
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
                G.711 / PCM HD Voice
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.85rem' }}>
              <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Detected Language</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#38bdf8', marginTop: '0.2rem' }}>
                  {detectedLanguage}
                </div>
                <div style={{ fontSize: '0.65rem', color: '#10b981' }}>Accuracy: {(languageConfidence * 100).toFixed(0)}%</div>
              </div>

              <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>SIP Call Session ID</div>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem', fontFamily: 'monospace' }}>
                  {currentCallSid || 'CA_virtual_sip_trunk'}
                </div>
                <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>PSTN Trunk: Exotel / Twilio</div>
              </div>

              <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Urgency & Distress</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 800, color: urgencyScore > 70 ? '#ef4444' : '#f59e0b', marginTop: '0.2rem' }}>
                  {urgencyScore}/100 • {distressLevel}
                </div>
                <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Multimodal Acoustic Fusion</div>
              </div>
            </div>
          </div>

          {/* Card 2: Extracted 10-Point Slot Checklist */}
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
                  10-Point Grievance Information HUD
                </h3>
              </div>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Zero Hallucination Validation</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.65rem' }}>
              {[
                { label: 'Category / Problem', val: collectionFields.problem || collectionFields.category || collectionFields.problem_description },
                { label: 'District & Area', val: collectionFields.location || collectionFields.district_area },
                { label: 'Street / Road', val: collectionFields.street || collectionFields.street_road_name },
                { label: 'Landmark', val: collectionFields.landmark },
                { label: 'Duration', val: collectionFields.duration || collectionFields.date_and_time },
                { label: 'Affected Scope', val: collectionFields.affected_scope || collectionFields.frequency },
                { label: 'Assigned Department', val: collectionFields.department || assignedDepartment }
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
                    {slot.val || 'Awaiting caller response...'}
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
                  OpenStreetMap GIS Location Pin
                </h3>
              </div>
              <span style={{ fontSize: '0.75rem', color: '#38bdf8', fontWeight: 700 }}>
                {osmLocationName || 'Tamil Nadu'}
              </span>
            </div>

            <div style={{ height: '220px', borderRadius: '12px', overflow: 'hidden', border: '1px solid #334155' }}>
              <IVRStreetMap
                latitude={currentLatitude || '11.016844'}
                longitude={currentLongitude || '76.955833'}
                locationName={osmLocationName || 'Tamil Nadu'}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
