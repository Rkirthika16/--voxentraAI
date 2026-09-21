import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ivrApi } from '../api/ivr';
import { speech } from '../utils/speech';
import { IVRProcessSpeechResponse } from '../types';
import {
  Shield,
  PhoneCall,
  PhoneOff,
  Mic,
  MicOff,
  Volume2,
  Sparkles,
  Building2,
  CheckCircle2,
  Radio,
  Send,
  ArrowRight,
  RotateCcw,
  Activity
} from 'lucide-react';

interface ChatTurn {
  id: string;
  sender: 'ai' | 'citizen';
  text: string;
  language: string;
  time: string;
}

export const LandingPage: React.FC = () => {
  const { demoLogin } = useAuth();
  const navigate = useNavigate();

  // Call simulation state
  const [callState, setCallState] = useState<'IDLE' | 'CALLING' | 'CONNECTED' | 'RECORDING' | 'PROCESSING' | 'TRANSFERRED'>('IDLE');
  const [selectedLang, setSelectedLang] = useState<'ta' | 'en' | 'hi'>('ta');
  const [callerPhone, setCallerPhone] = useState('+91 98430 98765');
  const [spokenText, setSpokenText] = useState('');
  const [dialogueTurns, setDialogueTurns] = useState<ChatTurn[]>([]);
  const [isAiSpeaking, setIsAiSpeaking] = useState(false);
  const [transferData, setTransferData] = useState<IVRProcessSpeechResponse | null>(null);
  const [callDuration, setCallDuration] = useState(0);

  // Live Microphone / Voice Recording State
  const [isRecording, setIsRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const recognitionRef = useRef<any>(null);
  const recordTimerRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  const timerRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [dialogueTurns, callState, spokenText]);

  useEffect(() => {
    return () => {
      speech.stop();
      if (timerRef.current) clearInterval(timerRef.current);
      if (recordTimerRef.current) clearInterval(recordTimerRef.current);
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
    };
  }, []);

  const playVoice = (text: string, lang: string) => {
    speech.stop();
    setIsAiSpeaking(true);
    speech.speak(text, {
      language: lang,
      volume: 1.0,
      rate: 0.95,
      onStart: () => setIsAiSpeaking(true),
      onEnd: () => setIsAiSpeaking(false),
      onError: () => setIsAiSpeaking(false)
    });
  };

  const handleStartCall = async () => {
    setCallState('CALLING');
    setTransferData(null);
    setDialogueTurns([]);
    setSpokenText('');
    setCallDuration(0);

    speech.playRingTone(1.8);

    try {
      const initData = await ivrApi.initiateCall(callerPhone, '1913');

      setTimeout(() => {
        speech.stopRingTone();
        speech.playConnectChime();
        setCallState('CONNECTED');

        timerRef.current = setInterval(() => {
          setCallDuration(prev => prev + 1);
        }, 1000);

        let greeting = initData.greeting_tamil + ' ' + initData.prompt_tamil;
        let langCode = 'ta-IN';
        let langLabel = 'Tamil';

        if (selectedLang === 'en') {
          greeting = initData.greeting_english + ' ' + initData.prompt_english;
          langCode = 'en-IN';
          langLabel = 'English';
        }

        const initialTurn: ChatTurn = {
          id: `ai_${Date.now()}`,
          sender: 'ai',
          text: greeting,
          language: langLabel,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        };

        setDialogueTurns([initialTurn]);
        playVoice(greeting, langCode);
      }, 1800);
    } catch (err) {
      speech.stopRingTone();
      setCallState('IDLE');
      alert('Helpline telephony bridge offline. Please check backend connection.');
    }
  };

  const handleEndCall = () => {
    speech.stop();
    speech.playBeep();
    stopRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
    setCallState('IDLE');
  };

  // 🎙️ START LIVE MICROPHONE RECORDING
  const startRecording = async () => {
    speech.stop();
    setIsRecording(true);
    setRecordSeconds(0);

    // Play recording beep
    speech.playBeep();

    // Start timer
    recordTimerRef.current = setInterval(() => {
      setRecordSeconds(prev => prev + 1);
    }, 1000);

    // Initialize Web Speech API for real-time speech-to-text
    const langCode = selectedLang === 'ta' ? 'ta-IN' : 'en-IN';
    const rec = speech.createRecognition(
      langCode,
      (transcript: string) => {
        if (transcript) {
          setSpokenText(transcript);
        }
      },
      (err: any) => {
        console.warn('Speech recognition notice:', err);
      },
      () => {
        setIsRecording(false);
      }
    );

    if (rec) {
      recognitionRef.current = rec;
      try {
        rec.start();
      } catch (e) {
        console.warn('Recognition start issue:', e);
      }
    }

    // Capture audio stream with MediaRecorder if available
    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        mediaRecorder.start();
      }
    } catch (e) {
      console.warn('MediaRecorder permission notice:', e);
    }
  };

  // 🛑 STOP LIVE MICROPHONE RECORDING
  const stopRecording = (autoSend = true) => {
    setIsRecording(false);
    if (recordTimerRef.current) {
      clearInterval(recordTimerRef.current);
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {}
    }

    if (autoSend && spokenText.trim()) {
      handleSendSpeech();
    }
  };

  const handleSendSpeech = async (customText?: string) => {
    const textToSend = (customText || spokenText).trim();
    if (!textToSend) return;

    if (isRecording) {
      stopRecording(false);
    }

    const citizenTurn: ChatTurn = {
      id: `cit_${Date.now()}`,
      sender: 'citizen',
      text: textToSend,
      language: selectedLang === 'ta' ? 'Tamil / Tanglish' : 'English',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    };

    setDialogueTurns(prev => [...prev, citizenTurn]);
    setSpokenText('');
    setCallState('PROCESSING');
    speech.stop();

    try {
      const res = await ivrApi.processSpeech({
        speech_text: textToSend,
        caller_phone: callerPhone,
        call_sid: `CALL_${Date.now().toString(36)}`,
        language_hint: selectedLang
      });

      setTransferData(res);
      setCallState('TRANSFERRED');

      const spokenMsg = res.confirmation_spoken_tamil || res.confirmation_spoken_english || res.sms_text;
      
      const aiResponseTurn: ChatTurn = {
        id: `ai_resp_${Date.now()}`,
        sender: 'ai',
        text: spokenMsg,
        language: res.detected_language,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      };

      setDialogueTurns(prev => [...prev, aiResponseTurn]);
      playVoice(spokenMsg, res.detected_language === 'Tamil' ? 'ta-IN' : 'en-IN');
    } catch (err: any) {
      setCallState('CONNECTED');
      alert(err.response?.data?.detail || 'Failed to process voice input.');
    }
  };

  const handleDemoAccess = async (role: 'ADMIN' | 'OFFICER_WATER' | 'OFFICER_ROADS') => {
    await demoLogin(role === 'OFFICER_ROADS' ? 'OFFICER_ROADS' : role);
    if (role === 'ADMIN') navigate('/admin');
    else navigate('/officer');
  };

  const sampleCalls = [
    {
      label: '💧 Drinking Water Main Leak (Tamil/Tanglish)',
      text: 'Gandhipuram bus stand pakkathula drinking water main pipe odanju neriya thanni waste aaguthu. Seekiram sari pannunga.',
      lang: 'ta'
    },
    {
      label: '🛣️ Deep Pothole & Road Hazard (Tamil)',
      text: 'ஆர்.எஸ் புரம் மெயின் ரோட்டில் பெரிய பள்ளம் விழுந்து விபத்து நடக்கிறது. உடனடியாக தார் ரோடு போட வேண்டும்.',
      lang: 'ta'
    },
    {
      label: '⚡ Sparking Transformer / Electrical Hazard (English)',
      text: 'Electrical transformer sparking with fire hazard near Ukkadam junction street light pole number 42.',
      lang: 'en'
    },
    {
      label: '🗑️ Garbage Overflow & Drainage (Tanglish)',
      text: 'Singanallur market pakkam kuppai romba naala allala, romba smell varudhu sanitary team anupunga.',
      lang: 'ta'
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3rem', paddingBottom: '4rem' }}>
      {/* Top Banner */}
      <section
        style={{
          background: 'linear-gradient(135deg, rgba(30, 58, 138, 0.45), rgba(15, 23, 42, 0.85))',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          borderRadius: 'var(--radius-xl)',
          padding: '2.5rem 2rem',
          position: 'relative',
          overflow: 'hidden'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1.5rem' }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(59, 130, 246, 0.2)', border: '1px solid rgba(59, 130, 246, 0.4)', borderRadius: 'var(--radius-full)', padding: '0.35rem 1rem', fontSize: '0.85rem', color: '#93c5fd', fontWeight: 600, marginBottom: '0.75rem' }}>
              <Radio size={15} className="animate-pulse" color="#60a5fa" />
              <span>Tamil Nadu Municipal Telephony & AI Dispatch Command Center</span>
            </div>
            <h1 style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.7rem)', fontWeight: 800, lineHeight: 1.2, marginBottom: '0.75rem' }}>
              Non-Web Citizen Telephony Helpline & <br />
              <span style={{ background: 'linear-gradient(135deg, #60a5fa, #34d399, #a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                AI Automated Department Dispatch
              </span>
            </h1>
            <p style={{ color: 'var(--text-muted)', maxWidth: '680px', fontSize: '1.05rem', lineHeight: 1.6 }}>
              Citizens dial <strong>1913 Toll-Free</strong> on standard phones. Our AI Voice Agent converses in <strong>Tamil & English</strong>, records and transcribes speech, extracts grievance & location, and transfers the ticket into the designated Department Officer Queue.
            </p>
          </div>

          {/* Quick Staff Login Links */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', minWidth: '240px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 700 }}>
              Direct Command Portals:
            </span>
            <button
              onClick={() => handleDemoAccess('ADMIN')}
              className="btn btn-primary"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem', padding: '0.85rem 1.25rem', fontWeight: 700 }}
            >
              <Shield size={18} />
              <span>👑 Admin Command Center</span>
            </button>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
              <button
                onClick={() => handleDemoAccess('OFFICER_WATER')}
                className="btn btn-secondary btn-sm"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', background: 'rgba(59, 130, 246, 0.15)', borderColor: 'rgba(59, 130, 246, 0.4)', color: '#60a5fa' }}
              >
                💧 Water Queue
              </button>
              <button
                onClick={() => handleDemoAccess('OFFICER_ROADS')}
                className="btn btn-secondary btn-sm"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', background: 'rgba(245, 158, 11, 0.15)', borderColor: 'rgba(245, 158, 11, 0.4)', color: '#fbbf24' }}
              >
                🛣️ Roads Queue
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Main Interactive Workspace: Live AI Telephony Dispatch Simulator */}
      <section style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 420px) 1fr', gap: '2rem', alignItems: 'start' }}>
        
        {/* Left Column: Phone Call Simulator & Voice Recording Controls */}
        <div className="glass-card" style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: callState === 'IDLE' ? 'rgba(100, 116, 139, 0.2)' : 'rgba(34, 197, 94, 0.2)', color: callState === 'IDLE' ? '#94a3b8' : '#4ade80', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <PhoneCall size={18} className={callState !== 'IDLE' ? 'animate-pulse' : ''} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.1rem', margin: 0, fontWeight: 700 }}>1913 Toll-Free Helpline</h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Non-Web Citizen Inbound Simulator</span>
              </div>
            </div>

            {callState !== 'IDLE' && (
              <span style={{ fontSize: '0.8rem', fontWeight: 700, padding: '0.25rem 0.6rem', borderRadius: 'var(--radius-full)', background: 'rgba(34, 197, 94, 0.15)', color: '#4ade80', border: '1px solid rgba(34, 197, 94, 0.3)' }}>
                {Math.floor(callDuration / 60)}:{(callDuration % 60).toString().padStart(2, '0')}
              </span>
            )}
          </div>

          {/* Caller Details & Language Select */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.25rem', display: 'block' }}>Caller Phone Number (Citizen):</label>
              <input
                type="text"
                value={callerPhone}
                onChange={(e) => setCallerPhone(e.target.value)}
                disabled={callState !== 'IDLE'}
                className="input-field"
                style={{ width: '100%', fontSize: '0.9rem', padding: '0.6rem 0.85rem' }}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.25rem', display: 'block' }}>Helpline Spoken Language:</label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setSelectedLang('ta')}
                  disabled={callState !== 'IDLE'}
                  style={{
                    padding: '0.5rem',
                    borderRadius: 'var(--radius-md)',
                    border: selectedLang === 'ta' ? '2px solid #3b82f6' : '1px solid var(--border-color)',
                    background: selectedLang === 'ta' ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                    color: selectedLang === 'ta' ? '#93c5fd' : 'var(--text-muted)',
                    fontWeight: 700,
                    cursor: 'pointer',
                    fontSize: '0.85rem'
                  }}
                >
                  🇮🇳 தமிழ் / Tanglish
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedLang('en')}
                  disabled={callState !== 'IDLE'}
                  style={{
                    padding: '0.5rem',
                    borderRadius: 'var(--radius-md)',
                    border: selectedLang === 'en' ? '2px solid #3b82f6' : '1px solid var(--border-color)',
                    background: selectedLang === 'en' ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                    color: selectedLang === 'en' ? '#93c5fd' : 'var(--text-muted)',
                    fontWeight: 700,
                    cursor: 'pointer',
                    fontSize: '0.85rem'
                  }}
                >
                  🌐 English
                </button>
              </div>
            </div>
          </div>

          {/* Primary Call Controls */}
          {callState === 'IDLE' ? (
            <button
              onClick={handleStartCall}
              className="btn btn-primary btn-lg"
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.75rem',
                background: 'linear-gradient(135deg, #16a34a, #22c55e)',
                fontWeight: 700,
                fontSize: '1rem',
                boxShadow: '0 0 20px rgba(34, 197, 94, 0.3)'
              }}
            >
              <PhoneCall size={20} />
              <span>Place Call to 1913 Helpline</span>
            </button>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {/* 🎙️ LIVE MICROPHONE VOICE RECORDING BUTTON */}
              {!isRecording ? (
                <button
                  onClick={startRecording}
                  disabled={callState === 'PROCESSING'}
                  className="btn btn-lg"
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.75rem',
                    background: 'linear-gradient(135deg, #2563eb, #3b82f6)',
                    color: '#ffffff',
                    fontWeight: 700,
                    fontSize: '1rem',
                    boxShadow: '0 0 20px rgba(59, 130, 246, 0.4)'
                  }}
                >
                  <Mic size={20} className="animate-pulse" />
                  <span>🎙️ Tap to Speak (Record Voice)</span>
                </button>
              ) : (
                <button
                  onClick={() => stopRecording(true)}
                  className="btn btn-danger btn-lg"
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.75rem',
                    fontWeight: 700,
                    fontSize: '1rem',
                    boxShadow: '0 0 25px rgba(239, 68, 68, 0.5)',
                    animation: 'pulse 1.5s infinite'
                  }}
                >
                  <MicOff size={20} />
                  <span>🛑 Stop & Send Voice ({recordSeconds}s)</span>
                </button>
              )}

              {/* End Call Button */}
              <button
                onClick={handleEndCall}
                className="btn btn-secondary btn-sm"
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  color: '#f87171',
                  borderColor: 'rgba(239, 68, 68, 0.3)'
                }}
              >
                <PhoneOff size={16} />
                <span>Hang Up / Disconnect Call</span>
              </button>
            </div>
          )}

          {/* Live Recording Active Visualizer */}
          {isRecording && (
            <div
              style={{
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                borderRadius: 'var(--radius-md)',
                padding: '0.75rem 1rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#f87171', fontWeight: 600, fontSize: '0.85rem' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444', animation: 'ping 1s infinite' }} />
                <span>Microphone Listening ({selectedLang === 'ta' ? 'Tamil' : 'English'})...</span>
              </div>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f87171' }}>
                00:{(recordSeconds % 60).toString().padStart(2, '0')}
              </span>
            </div>
          )}

          {/* Quick Voice Scenarios */}
          {callState !== 'IDLE' && (
            <div style={{ marginTop: '0.25rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>
                Or Click Quick Spoken Grievance Samples:
              </span>
              {sampleCalls.map((sample, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendSpeech(sample.text)}
                  disabled={callState === 'PROCESSING' || isRecording}
                  style={{
                    textAlign: 'left',
                    padding: '0.6rem 0.75rem',
                    background: 'rgba(30, 41, 59, 0.6)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-light)',
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.2rem'
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.5)')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.08)')}
                >
                  <span style={{ fontWeight: 600, color: '#60a5fa' }}>{sample.label}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    "{sample.text}"
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Live Telephony AI Dialogue & Department Auto-Transfer */}
        <div className="glass-card" style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', minHeight: '520px', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <Sparkles size={20} color="#60a5fa" />
              <div>
                <h3 style={{ fontSize: '1.15rem', margin: 0, fontWeight: 700 }}>Live AI Voice Dialogue & Auto-Routing</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Conversational Speech Engine with Immediate Officer Queue Transfer</span>
              </div>
            </div>

            {isAiSpeaking && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(59, 130, 246, 0.15)', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-full)', border: '1px solid rgba(59, 130, 246, 0.3)', color: '#60a5fa', fontSize: '0.8rem', fontWeight: 600 }}>
                <Volume2 size={16} className="animate-pulse" />
                <span>AI Speaking Aloud...</span>
              </div>
            )}
          </div>

          {/* Dialogue Log Stream */}
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem', padding: '0.5rem', marginBottom: '1rem', minHeight: '260px' }}>
            {dialogueTurns.length === 0 ? (
              <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)', textAlign: 'center', padding: '3rem 1rem' }}>
                <Radio size={40} style={{ opacity: 0.3, marginBottom: '1rem' }} />
                <h4 style={{ fontSize: '1.1rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Telephony Dispatch Line Idle</h4>
                <p style={{ fontSize: '0.85rem', maxWidth: '420px', margin: 0 }}>
                  Click <strong>"Place Call to 1913 Helpline"</strong> on the left, then click <strong>"🎙️ Tap to Speak (Record Voice)"</strong> to speak your grievance directly. The AI will speak aloud and transfer the ticket to the designated department.
                </p>
              </div>
            ) : (
              dialogueTurns.map((turn) => (
                <div
                  key={turn.id}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: turn.sender === 'ai' ? 'flex-start' : 'flex-end',
                    gap: '0.25rem'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                    <span>{turn.sender === 'ai' ? '🤖 Voxentra AI Voice Agent' : `📞 Citizen (${callerPhone})`}</span>
                    <span>•</span>
                    <span>{turn.time}</span>
                  </div>
                  <div
                    style={{
                      maxWidth: '85%',
                      padding: '0.85rem 1.15rem',
                      borderRadius: turn.sender === 'ai' ? '4px 16px 16px 16px' : '16px 4px 16px 16px',
                      background: turn.sender === 'ai' ? 'rgba(30, 41, 59, 0.8)' : 'linear-gradient(135deg, #2563eb, #3b82f6)',
                      border: turn.sender === 'ai' ? '1px solid rgba(59, 130, 246, 0.3)' : 'none',
                      color: '#ffffff',
                      fontSize: '0.95rem',
                      lineHeight: 1.5
                    }}
                  >
                    {turn.text}
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Department Transfer Result Card */}
          {transferData && (
            <div
              style={{
                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(5, 150, 105, 0.2))',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                borderRadius: 'var(--radius-lg)',
                padding: '1.25rem',
                marginBottom: '1rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#34d399', fontWeight: 700, fontSize: '0.95rem' }}>
                  <CheckCircle2 size={18} />
                  <span>Transferred to Department: {transferData.suggested_department}</span>
                </div>
                <span style={{ fontSize: '0.8rem', background: 'rgba(16, 185, 129, 0.25)', padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-sm)', color: '#6ee7b7', fontWeight: 700 }}>
                  Ticket #{transferData.complaint_number}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', fontSize: '0.85rem' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Category:</span>
                  <strong>{transferData.category}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Extracted Location:</span>
                  <strong>{transferData.extracted_location || 'Tamil Nadu'}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Priority / Severity:</span>
                  <span style={{ color: transferData.priority === 'CRITICAL' ? '#f87171' : transferData.priority === 'HIGH' ? '#fbbf24' : '#60a5fa', fontWeight: 700 }}>
                    {transferData.priority}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>SMS Confirmation:</span>
                  <span style={{ color: '#34d399', fontWeight: 600 }}>Sent to {callerPhone}</span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.25rem' }}>
                <Link
                  to="/officer"
                  className="btn btn-sm"
                  style={{ background: 'rgba(59, 130, 246, 0.2)', border: '1px solid rgba(59, 130, 246, 0.4)', color: '#93c5fd', fontWeight: 700 }}
                >
                  <span>👀 Inspect in Officer Queue ➔</span>
                </Link>
                <Link
                  to="/admin"
                  className="btn btn-sm"
                  style={{ background: 'rgba(16, 185, 129, 0.2)', border: '1px solid rgba(16, 185, 129, 0.4)', color: '#6ee7b7', fontWeight: 700 }}
                >
                  <span>📊 View in Admin Dashboard ➔</span>
                </Link>
              </div>
            </div>
          )}

          {/* Citizen Speech Input Box & Direct Mic Controls */}
          {callState !== 'IDLE' && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="text"
                value={spokenText}
                onChange={(e) => setSpokenText(e.target.value)}
                placeholder={isRecording ? "Listening to your voice recording..." : "Type or speak what the calling citizen says (Tamil / English / Tanglish)..."}
                className="input-field"
                style={{ flex: 1, padding: '0.75rem 1rem', borderColor: isRecording ? '#ef4444' : undefined }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSendSpeech();
                }}
              />
              
              {!isRecording ? (
                <button
                  type="button"
                  onClick={startRecording}
                  title="Record Voice"
                  className="btn btn-secondary"
                  style={{ padding: '0.75rem 0.9rem', color: '#60a5fa', borderColor: 'rgba(59, 130, 246, 0.4)' }}
                >
                  <Mic size={18} />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => stopRecording(true)}
                  title="Stop Recording"
                  className="btn btn-danger"
                  style={{ padding: '0.75rem 0.9rem' }}
                >
                  <MicOff size={18} />
                </button>
              )}

              <button
                onClick={() => handleSendSpeech()}
                disabled={!spokenText.trim() || callState === 'PROCESSING'}
                className="btn btn-primary"
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.75rem 1.25rem', fontWeight: 700 }}
              >
                <Send size={16} />
                <span>Send</span>
              </button>
            </div>
          )}
        </div>
      </section>

      {/* Municipal Workflow Summary */}
      <section className="glass-card" style={{ padding: '2rem' }}>
        <h3 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: '1.5rem', textAlign: 'center' }}>
          🏛️ How Non-Web Citizen Telephony Dispatches to Municipal Departments
        </h3>

        <div className="grid-3" style={{ gap: '1.5rem' }}>
          <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: 'var(--radius-md)', background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '0.75rem' }}>
              <PhoneCall size={20} />
            </div>
            <h4 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.5rem' }}>1. Citizen Phone Call (1913)</h4>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', lineHeight: 1.5, margin: 0 }}>
              Rural and urban citizens dial the 1913 Toll-Free helpline using standard feature phones or landlines without any internet or web application.
            </p>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: 'var(--radius-md)', background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '0.75rem' }}>
              <Sparkles size={20} />
            </div>
            <h4 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.5rem' }}>2. Multilingual AI Voice Triage</h4>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', lineHeight: 1.5, margin: 0 }}>
              Voxentra Voice AI converses naturally in Tamil, English, or Tanglish, extracts the village / panchayat, assesses severity, and informs the caller.
            </p>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: 'var(--radius-md)', background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '0.75rem' }}>
              <Building2 size={20} />
            </div>
            <h4 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.5rem' }}>3. Auto-Transfer to Department</h4>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', lineHeight: 1.5, margin: 0 }}>
              The ticket is immediately assigned to the appropriate Department Officer (Water, Roads, Electricity, Sanitation) with live tracking and SMS alerts.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};
