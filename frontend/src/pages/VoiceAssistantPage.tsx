import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../api/client';

type ConversationState =
  | 'IDLE'
  | 'LISTENING'
  | 'PROCESSING'
  | 'AI_RESPONDING'
  | 'SPEAKING'
  | 'WAITING_FOR_USER'
  | 'CONFIRMING'
  | 'COMPLETED'
  | 'ERROR';

interface TurnMessage {
  turnIndex: number;
  sender: 'citizen' | 'ai';
  text: string;
  spokenText?: string;
  detectedLanguage?: string;
  timestamp: string;
}

interface ContextState {
  session_id?: string;
  language?: string;
  category?: string;
  problem?: string;
  location?: string;
  district?: string;
  area?: string;
  street?: string;
  landmark?: string;
  duration?: string;
  severity?: string;
  affected_scope?: string;
  priority?: string;
  department?: string;
  summary?: string;
  confirmation_required?: boolean;
  conversation_complete?: boolean;
  complaint_number?: string;
  complaint_id?: number;
}

export const VoiceAssistantPage: React.FC = () => {
  const [sessionId, setSessionId] = useState<string>(() => `conv_${Math.random().toString(36).substring(2, 11)}`);
  const [convState, setConvState] = useState<ConversationState>('IDLE');
  const [transcript, setTranscript] = useState<string>('');
  const [interimSpeech, setInterimSpeech] = useState<string>('');
  const [messages, setMessages] = useState<TurnMessage[]>([]);
  const [context, setContext] = useState<ContextState>({});
  const [textInput, setTextInput] = useState<string>('');
  const [isSpeechRecognitionSupported, setIsSpeechRecognitionSupported] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const recognitionRef = useRef<any>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const isSpeakingRef = useRef<boolean>(false);

  // Auto scroll chat to bottom
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, interimSpeech, convState]);

  // Setup Web Speech API for in-browser speech recognition
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setIsSpeechRecognitionSupported(false);
      return;
    }

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = 'ta-IN'; // Multi-lingual recognition accepts Tamil/English/Tanglish

    rec.onstart = () => {
      setConvState('LISTENING');
      setInterimSpeech('');
      setErrorMessage(null);
    };

    rec.onresult = (event: any) => {
      let current = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        current += event.results[i][0].transcript;
      }
      setInterimSpeech(current);
    };

    rec.onerror = (event: any) => {
      console.warn('Speech recognition error:', event.error);
      if (event.error === 'no-speech') {
        setConvState('WAITING_FOR_USER');
      } else {
        setErrorMessage(`Microphone error: ${event.error}. You can use the text box below.`);
        setConvState('ERROR');
      }
    };

    rec.onend = () => {
      if (interimSpeech && interimSpeech.trim()) {
        submitSpeechTurn(interimSpeech.trim());
      } else {
        if (convState === 'LISTENING') {
          setConvState('WAITING_FOR_USER');
        }
      }
    };

    recognitionRef.current = rec;

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (e) {}
      }
      window.speechSynthesis.cancel();
    };
  }, [interimSpeech, convState]);

  // Speak AI response aloud using native Web Speech Synthesis or backend TTS
  const speakText = (textToSpeak: string, lang: string = 'Tamil') => {
    if (!window.speechSynthesis) return;

    window.speechSynthesis.cancel();
    isSpeakingRef.current = true;
    setConvState('SPEAKING');

    const clean = textToSpeak.replace(/[*#_`~>📋🏢📍⏱️👥⚡]/g, '').trim();
    const utterance = new SpeechSynthesisUtterance(clean);

    // Try finding suitable voice for Tamil or English
    const voices = window.speechSynthesis.getVoices();
    if (lang === 'Tamil') {
      const taVoice = voices.find(v => v.lang.includes('ta') || v.name.toLowerCase().includes('tamil'));
      if (taVoice) utterance.voice = taVoice;
      utterance.lang = 'ta-IN';
    } else {
      const enVoice = voices.find(v => v.lang.includes('en-IN') || v.lang.includes('en'));
      if (enVoice) utterance.voice = enVoice;
      utterance.lang = 'en-IN';
    }

    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    utterance.onend = () => {
      isSpeakingRef.current = false;
      setConvState(context.conversation_complete ? 'COMPLETED' : (context.confirmation_required ? 'CONFIRMING' : 'WAITING_FOR_USER'));
    };

    utterance.onerror = () => {
      isSpeakingRef.current = false;
      setConvState(context.conversation_complete ? 'COMPLETED' : (context.confirmation_required ? 'CONFIRMING' : 'WAITING_FOR_USER'));
    };

    window.speechSynthesis.speak(utterance);
  };

  // Start listening to citizen voice
  const handleStartListening = () => {
    setErrorMessage(null);
    window.speechSynthesis.cancel();

    if (!isSpeechRecognitionSupported) {
      setErrorMessage("Speech recognition is not supported in this browser. Please type your message below.");
      return;
    }

    try {
      if (recognitionRef.current) {
        recognitionRef.current.start();
      }
    } catch (e) {
      console.warn("Recognition already started or busy", e);
    }
  };

  // Stop listening
  const handleStopListening = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
    }
  };

  // Cancel and reset session
  const handleResetConversation = () => {
    window.speechSynthesis.cancel();
    handleStopListening();
    const newId = `conv_${Math.random().toString(36).substring(2, 11)}`;
    setSessionId(newId);
    setConvState('IDLE');
    setMessages([]);
    setContext({});
    setTranscript('');
    setInterimSpeech('');
    setTextInput('');
    setErrorMessage(null);
  };

  // Send turn to backend
  const submitSpeechTurn = async (speechText: string) => {
    if (!speechText.trim()) return;

    setConvState('PROCESSING');
    setInterimSpeech('');
    setTranscript(speechText);

    // Append Citizen Turn to history
    const citizenMsg: TurnMessage = {
      turnIndex: messages.length + 1,
      sender: 'citizen',
      text: speechText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages(prev => [...prev, citizenMsg]);

    try {
      const response = await apiClient.post('/conversation/turn', {
        session_id: sessionId,
        user_speech: speechText,
        caller_phone: '+919843098765'
      });

      const data = response.data;
      setContext(data.context || {});

      const aiMsg: TurnMessage = {
        turnIndex: messages.length + 2,
        sender: 'ai',
        text: data.ai_text,
        spokenText: data.ai_spoken,
        detectedLanguage: data.detected_language,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, aiMsg]);

      // Speak response aloud
      speakText(data.ai_spoken || data.ai_text, data.detected_language);

    } catch (err: any) {
      console.error("Conversation turn error:", err);
      setErrorMessage("Could not reach VoxentraAI engine. Please verify server connection.");
      setConvState('ERROR');
    }
  };

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!textInput.trim()) return;
    const text = textInput.trim();
    setTextInput('');
    submitSpeechTurn(text);
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '1.5rem 1rem' }}>
      {/* Top Banner */}
      <div style={{
        background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #31104b 100%)',
        borderRadius: '16px',
        padding: '2rem',
        color: '#fff',
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.3)',
        marginBottom: '1.5rem',
        position: 'relative',
        overflow: 'hidden'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
              <span style={{
                background: '#8b5cf6',
                color: '#fff',
                fontSize: '0.75rem',
                fontWeight: 700,
                padding: '0.2rem 0.6rem',
                borderRadius: '999px',
                textTransform: 'uppercase',
                letterSpacing: '0.05em'
              }}>
                Natural Live Voice AI
              </span>
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                fontSize: '0.8rem',
                color: '#34d399',
                background: 'rgba(52, 211, 153, 0.1)',
                padding: '0.2rem 0.5rem',
                borderRadius: '6px'
              }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#34d399', display: 'inline-block' }}></span>
                Citizen Speaks First
              </span>
            </div>
            <h1 style={{ fontSize: '2rem', fontWeight: 800, margin: '0 0 0.5rem 0', letterSpacing: '-0.02em' }}>
              VoxentraAI Conversational Voice Helpline
            </h1>
            <p style={{ color: '#cbd5e1', margin: 0, fontSize: '1rem', maxWidth: '650px', lineHeight: 1.5 }}>
              Speak naturally in Tamil, English, or Tanglish without choosing menus or questionnaires. VoxentraAI understands, clarifies missing information, and registers your complaint automatically.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={handleResetConversation}
              style={{
                background: 'rgba(255, 255, 255, 0.1)',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                color: '#fff',
                padding: '0.5rem 1rem',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '0.875rem',
                fontWeight: 600,
                transition: 'all 0.2s'
              }}
            >
              🔄 Reset / New Call
            </button>
          </div>
        </div>
      </div>

      {/* Main Layout Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '1.5rem', alignItems: 'start' }}>
        {/* Left Column: Voice Interaction & Dialogue History */}
        <div style={{
          background: '#ffffff',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: '580px'
        }}>
          {/* Status Header */}
          <div style={{
            padding: '1rem 1.25rem',
            borderBottom: '1px solid #f1f5f9',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: '#fafafa',
            borderTopLeftRadius: '16px',
            borderTopRightRadius: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              {convState === 'LISTENING' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#ef4444', fontWeight: 700, fontSize: '0.9rem' }}>
                  <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#ef4444', animation: 'pulse 1.5s infinite' }}></span>
                  🎤 Listening... You can speak now
                </div>
              )}
              {convState === 'PROCESSING' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#f59e0b', fontWeight: 700, fontSize: '0.9rem' }}>
                  <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#f59e0b', animation: 'spin 1s linear infinite' }}></span>
                  🤖 Processing & understanding context...
                </div>
              )}
              {convState === 'SPEAKING' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#8b5cf6', fontWeight: 700, fontSize: '0.9rem' }}>
                  <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#8b5cf6', animation: 'bounce 1s infinite' }}></span>
                  🔊 VoxentraAI is speaking...
                </div>
              )}
              {convState === 'WAITING_FOR_USER' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#3b82f6', fontWeight: 700, fontSize: '0.9rem' }}>
                  🎤 Your turn. Click mic or speak your reply.
                </div>
              )}
              {convState === 'CONFIRMING' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#10b981', fontWeight: 700, fontSize: '0.9rem' }}>
                  📋 Review summary & say "Aama / Yes" to register.
                </div>
              )}
              {convState === 'COMPLETED' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#059669', fontWeight: 700, fontSize: '0.9rem' }}>
                  ✅ Complaint Registered Successfully!
                </div>
              )}
              {convState === 'IDLE' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#64748b', fontWeight: 600, fontSize: '0.9rem' }}>
                  Tap microphone below to start speaking directly
                </div>
              )}
              {convState === 'ERROR' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#dc2626', fontWeight: 600, fontSize: '0.9rem' }}>
                  ⚠️ {errorMessage || "Voice input error"}
                </div>
              )}
            </div>

            {context.language && (
              <span style={{
                background: '#ede9fe',
                color: '#6d28d9',
                fontSize: '0.75rem',
                fontWeight: 700,
                padding: '0.2rem 0.5rem',
                borderRadius: '6px'
              }}>
                🌐 {context.language}
              </span>
            )}
          </div>

          {/* Conversation History Stream */}
          <div
            ref={chatScrollRef}
            style={{
              flex: 1,
              padding: '1.25rem',
              overflowY: 'auto',
              maxHeight: '380px',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
              background: '#f8fafc'
            }}
          >
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#94a3b8' }}>
                <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🎙️</div>
                <h3 style={{ margin: '0 0 0.5rem 0', color: '#334155', fontWeight: 700 }}>No Fixed Menu — Just Speak</h3>
                <p style={{ margin: 0, fontSize: '0.9rem', maxWidth: '420px', marginInline: 'auto' }}>
                  Example: <em>"Gandhipuram-la thanni varala"</em> or <em>"எங்க தெருவுல 3 நாளா கரண்ட் இல்ல"</em> or <em>"Potholes on Cross Cut Road"</em>
                </p>
              </div>
            )}

            {messages.map((m, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: m.sender === 'citizen' ? 'flex-end' : 'flex-start'
                }}
              >
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  marginBottom: '0.25rem',
                  fontSize: '0.75rem',
                  color: '#64748b'
                }}>
                  <span>{m.sender === 'citizen' ? '👤 Citizen (You)' : '🤖 VoxentraAI'}</span>
                  <span>• {m.timestamp}</span>
                </div>
                <div style={{
                  background: m.sender === 'citizen' ? '#2563eb' : '#ffffff',
                  color: m.sender === 'citizen' ? '#ffffff' : '#1e293b',
                  padding: '0.85rem 1.15rem',
                  borderRadius: m.sender === 'citizen' ? '16px 16px 2px 16px' : '16px 16px 16px 2px',
                  maxWidth: '85%',
                  fontSize: '0.95rem',
                  lineHeight: 1.5,
                  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
                  border: m.sender === 'citizen' ? 'none' : '1px solid #e2e8f0',
                  whiteSpace: 'pre-wrap'
                }}>
                  {m.text}
                </div>
              </div>
            ))}

            {interimSpeech && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                <div style={{ fontSize: '0.75rem', color: '#ef4444', marginBottom: '0.25rem' }}>Listening...</div>
                <div style={{
                  background: 'rgba(37, 99, 235, 0.15)',
                  color: '#1d4ed8',
                  padding: '0.75rem 1rem',
                  borderRadius: '16px 16px 2px 16px',
                  maxWidth: '85%',
                  fontSize: '0.95rem',
                  fontStyle: 'italic',
                  border: '1px dashed #60a5fa'
                }}>
                  {interimSpeech}...
                </div>
              </div>
            )}
          </div>

          {/* Voice Microphone Control Panel */}
          <div style={{
            padding: '1.25rem',
            borderTop: '1px solid #f1f5f9',
            background: '#ffffff',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '1rem',
            borderBottomLeftRadius: '16px',
            borderBottomRightRadius: '16px'
          }}>
            {/* Big Pulsing Mic Button */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <button
                onClick={convState === 'LISTENING' ? handleStopListening : handleStartListening}
                disabled={convState === 'PROCESSING' || convState === 'SPEAKING'}
                style={{
                  width: '76px',
                  height: '76px',
                  borderRadius: '50%',
                  border: 'none',
                  background: convState === 'LISTENING'
                    ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
                    : 'linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)',
                  color: '#ffffff',
                  fontSize: '2rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: (convState === 'PROCESSING' || convState === 'SPEAKING') ? 'not-allowed' : 'pointer',
                  boxShadow: convState === 'LISTENING'
                    ? '0 0 0 12px rgba(239, 68, 68, 0.25), 0 10px 15px -3px rgba(239, 68, 68, 0.4)'
                    : '0 10px 20px -5px rgba(109, 40, 217, 0.4)',
                  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  transform: convState === 'LISTENING' ? 'scale(1.08)' : 'scale(1)'
                }}
                title={convState === 'LISTENING' ? "Click to stop listening" : "Click to start speaking"}
              >
                {convState === 'LISTENING' ? '⏹️' : '🎙️'}
              </button>

              {convState === 'LISTENING' && (
                <button
                  onClick={handleStopListening}
                  style={{
                    background: '#fee2e2',
                    color: '#991b1b',
                    border: '1px solid #fca5a5',
                    padding: '0.5rem 1rem',
                    borderRadius: '8px',
                    fontWeight: 600,
                    fontSize: '0.85rem',
                    cursor: 'pointer'
                  }}
                >
                  Done Speaking
                </button>
              )}
            </div>

            <div style={{ fontSize: '0.85rem', color: '#64748b', fontWeight: 500 }}>
              {convState === 'LISTENING' ? "Listening to your voice... Speak your complaint" : "Tap microphone to speak directly"}
            </div>

            {/* Text Fallback Input */}
            <form onSubmit={handleTextSubmit} style={{ width: '100%', display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
              <input
                type="text"
                value={textInput}
                onChange={e => setTextInput(e.target.value)}
                placeholder="Or type your complaint here in Tamil, English, or Tanglish..."
                disabled={convState === 'PROCESSING'}
                style={{
                  flex: 1,
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.9rem',
                  outline: 'none'
                }}
              />
              <button
                type="submit"
                disabled={!textInput.trim() || convState === 'PROCESSING'}
                style={{
                  background: '#2563eb',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '10px',
                  padding: '0 1.25rem',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                  cursor: (!textInput.trim() || convState === 'PROCESSING') ? 'not-allowed' : 'pointer'
                }}
              >
                Send
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Structured Live Context Card */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{
            background: '#ffffff',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            padding: '1.25rem',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)'
          }}>
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.05rem', fontWeight: 700, color: '#1e293b', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>📊</span> Live Complaint Context
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.875rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>
                <span style={{ color: '#64748b' }}>Language:</span>
                <span style={{ fontWeight: 600, color: '#0f172a' }}>{context.language || 'Auto-detecting...'}</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>
                <span style={{ color: '#64748b' }}>Category:</span>
                <span style={{
                  fontWeight: 700,
                  color: context.category ? '#2563eb' : '#94a3b8',
                  background: context.category ? '#dbeafe' : 'transparent',
                  padding: context.category ? '0.1rem 0.4rem' : '0',
                  borderRadius: '4px'
                }}>
                  {context.category || 'Extracting...'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>
                <span style={{ color: '#64748b' }}>Location:</span>
                <span style={{ fontWeight: 600, color: context.location ? '#0f172a' : '#94a3b8' }}>
                  {context.location || 'Pending...'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>
                <span style={{ color: '#64748b' }}>Duration:</span>
                <span style={{ fontWeight: 600, color: context.duration ? '#0f172a' : '#94a3b8' }}>
                  {context.duration || 'Pending...'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>
                <span style={{ color: '#64748b' }}>Affected Scope:</span>
                <span style={{ fontWeight: 600, color: context.affected_scope ? '#0f172a' : '#94a3b8' }}>
                  {context.affected_scope || 'Pending...'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>
                <span style={{ color: '#64748b' }}>Priority:</span>
                <span style={{
                  fontWeight: 700,
                  color: context.priority === 'CRITICAL' ? '#dc2626' : (context.priority === 'HIGH' ? '#ea580c' : '#16a34a')
                }}>
                  {context.priority || 'MEDIUM'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>
                <span style={{ color: '#64748b' }}>Department:</span>
                <span style={{ fontWeight: 600, color: '#334155' }}>
                  {context.department || 'Auto-routing...'}
                </span>
              </div>

              {context.complaint_number && (
                <div style={{
                  marginTop: '0.5rem',
                  padding: '0.85rem',
                  background: '#ecfdf5',
                  border: '1px solid #a7f3d0',
                  borderRadius: '10px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '0.75rem', color: '#065f46', fontWeight: 600, textTransform: 'uppercase' }}>Tracking ID Issued</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#047857', marginTop: '0.25rem' }}>{context.complaint_number}</div>
                  <Link
                    to={`/complaints/${context.complaint_id}`}
                    style={{
                      display: 'inline-block',
                      marginTop: '0.5rem',
                      fontSize: '0.8rem',
                      color: '#059669',
                      fontWeight: 700,
                      textDecoration: 'underline'
                    }}
                  >
                    View Status & Details →
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* Quick Simulation Chips */}
          <div style={{
            background: '#ffffff',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            padding: '1.25rem',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)'
          }}>
            <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', fontWeight: 700, color: '#475569' }}>
              💡 Quick Test Phrases
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <button
                onClick={() => submitSpeechTurn("Gandhipuram-la thanni varala.")}
                style={{
                  textAlign: 'left',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '8px',
                  fontSize: '0.8rem',
                  color: '#334155',
                  cursor: 'pointer'
                }}
              >
                🌊 <strong>Tanglish Water</strong>: "Gandhipuram-la thanni varala."
              </button>
              <button
                onClick={() => submitSpeechTurn("எங்க தெருவுல 3 நாளா கரண்ட் இல்ல.")}
                style={{
                  textAlign: 'left',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '8px',
                  fontSize: '0.8rem',
                  color: '#334155',
                  cursor: 'pointer'
                }}
              >
                ⚡ <strong>Tamil Power</strong>: "எங்க தெருவுல 3 நாளா கரண்ட் இல்ல."
              </button>
              <button
                onClick={() => submitSpeechTurn("Heavy garbage accumulated on Cross Cut Road for four days.")}
                style={{
                  textAlign: 'left',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '8px',
                  fontSize: '0.8rem',
                  color: '#334155',
                  cursor: 'pointer'
                }}
              >
                🗑️ <strong>English Sanitation</strong>: "Heavy garbage on Cross Cut Road."
              </button>
              <button
                onClick={() => submitSpeechTurn("Aama, register pannunga.")}
                style={{
                  textAlign: 'left',
                  background: '#f0fdf4',
                  border: '1px solid #bbf7d0',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '8px',
                  fontSize: '0.8rem',
                  color: '#15803d',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                ✅ <strong>Confirmation</strong>: "Aama, register pannunga."
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
