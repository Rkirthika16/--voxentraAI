import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { assistantApi } from '../api/assistant';
import { speech } from '../utils/speech';
import { AssistantMessage, ActionSuggestion } from '../types';
import {
  Sparkles,
  Mic,
  MicOff,
  Send,
  Volume2,
  VolumeX,
  X,
  Maximize2,
  PhoneCall,
  ExternalLink,
  Radio
} from 'lucide-react';

export const VoiceAssistantWidget: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  // Don't show floating widget if already on the full /assistant page
  if (location.pathname === '/assistant') {
    return null;
  }

  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<AssistantMessage[]>([
    {
      id: 'init',
      sender: 'assistant',
      text: "👋 **Vanakkam!** I'm Voxentra AI.\nSpeak or type your civic grievance in Tamil or English.",
      spoken_text: "Welcome to Voxentra AI. How can I assist your civic grievance today?",
      timestamp: new Date(),
      suggested_actions: [
        { label: '💧 Water Leakage', action_type: 'QUICK_PROMPT', payload: { prompt: 'Water pipe leak near Gandhipuram' } },
        { label: '⚡ Power Outage', action_type: 'QUICK_PROMPT', payload: { prompt: 'Power cut in Peelamedu' } },
        { label: '🔍 Track Status', action_type: 'QUICK_PROMPT', payload: { prompt: 'Track my complaint status' } },
      ]
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState<string>(() => `widget_${Date.now()}`);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  const handleSpeak = (text: string) => {
    if (!text) return;
    setIsSpeaking(true);
    speech.speak(text, {
      onStart: () => setIsSpeaking(true),
      onEnd: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  const handleSend = async (customPrompt?: string) => {
    const textToSend = (customPrompt || inputText).trim();
    if (!textToSend || isLoading) return;

    speech.stop();
    setIsSpeaking(false);

    const userMsg: AssistantMessage = {
      id: `u_${Date.now()}`,
      sender: 'user',
      text: textToSend,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setIsLoading(true);

    try {
      const res = await assistantApi.chat(textToSend, sessionId);
      const botMsg: AssistantMessage = {
        id: `a_${Date.now()}`,
        sender: 'assistant',
        text: res.reply_text,
        spoken_text: res.spoken_text,
        detected_language: res.detected_language,
        intent: res.intent,
        draft_complaint: res.draft_complaint,
        suggested_actions: res.suggested_actions,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, botMsg]);

      if (autoSpeak && res.spoken_text) {
        handleSpeak(res.spoken_text);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleMic = () => {
    if (isListening) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
      setIsListening(false);
      return;
    }

    speech.stop();
    setIsSpeaking(false);

    if (speech.isSTTSupported()) {
      const recognition = speech.createRecognition(
        'en-IN',
        (transcript, isFinal) => {
          setInputText(transcript);
          if (isFinal && transcript.trim()) {
            setIsListening(false);
            handleSend(transcript);
          }
        },
        () => setIsListening(false),
        () => setIsListening(false)
      );

      if (recognition) {
        recognitionRef.current = recognition;
        try {
          recognition.start();
          setIsListening(true);
        } catch (e) {
          setIsListening(false);
        }
      }
    }
  };

  const handleAction = (act: ActionSuggestion) => {
    if (act.action_type === 'QUICK_PROMPT') {
      if (act.payload.prompt === 'edit_draft') {
        setIsOpen(false);
        navigate('/submit', { state: { draft: act.payload.draft } });
        return;
      }
      handleSend(act.payload.prompt);
    } else if (act.action_type === 'CALL_HELPLINE') {
      window.open(`tel:${act.payload.phone}`, '_self');
    } else if (act.action_type === 'TRACK_COMPLAINT') {
      setIsOpen(false);
      if (act.payload.tracking_number) {
        navigate(`/track?number=${encodeURIComponent(act.payload.tracking_number)}`);
      } else {
        navigate('/track');
      }
    } else if (act.action_type === 'SUBMIT_DRAFT') {
      setIsOpen(false);
      navigate('/assistant');
    }
  };

  return (
    <div style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 9999 }}>
      {/* Expanded Chat Popup */}
      {isOpen && (
        <div
          className="glass-card animate-fade-in"
          style={{
            position: 'absolute',
            bottom: '72px',
            right: '0',
            width: '380px',
            maxWidth: 'calc(100vw - 32px)',
            height: '520px',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 12px 40px rgba(0, 0, 0, 0.5)',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            background: 'rgba(15, 23, 42, 0.95)',
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '0.85rem 1rem',
              background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.98))',
              borderBottom: '1px solid var(--border-color)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: isSpeaking ? 'linear-gradient(135deg, #10b981, #06b6d4)' : 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: isSpeaking ? '0 0 12px rgba(16, 185, 129, 0.8)' : 'none',
                }}
              >
                {isSpeaking ? <Radio size={16} color="#fff" /> : <Sparkles size={16} color="#fff" />}
              </div>
              <div>
                <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)' }}>Voxentra AI Voice</div>
                <div style={{ fontSize: '0.7rem', color: isSpeaking ? '#34d399' : '#38bdf8' }}>
                  {isSpeaking ? 'Talking...' : 'Ready to listen'}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <button
                type="button"
                onClick={() => setAutoSpeak(!autoSpeak)}
                style={{ background: 'none', border: 'none', color: autoSpeak ? '#38bdf8' : 'var(--text-dim)', cursor: 'pointer', padding: '4px' }}
                title={autoSpeak ? 'Mute AI voice' : 'Enable AI voice'}
              >
                {autoSpeak ? <Volume2 size={16} /> : <VolumeX size={16} />}
              </button>

              <button
                type="button"
                onClick={() => {
                  setIsOpen(false);
                  navigate('/assistant');
                }}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px' }}
                title="Open full AI assistant center"
              >
                <Maximize2 size={16} />
              </button>

              <button
                type="button"
                onClick={() => {
                  speech.stop();
                  setIsOpen(false);
                }}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px' }}
                title="Close"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '0.85rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.85rem',
              fontSize: '0.85rem',
            }}
          >
            {messages.map((m) => (
              <div
                key={m.id}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: m.sender === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <div
                  style={{
                    maxWidth: '90%',
                    padding: '0.65rem 0.85rem',
                    borderRadius: 'var(--radius-md)',
                    background: m.sender === 'user' ? '#2563eb' : 'rgba(30, 41, 59, 0.9)',
                    border: m.sender === 'user' ? 'none' : '1px solid var(--border-color)',
                    color: '#fff',
                    whiteSpace: 'pre-wrap',
                    lineHeight: '1.4',
                  }}
                >
                  {m.text}

                  {m.suggested_actions && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.5rem' }}>
                      {m.suggested_actions.map((act, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => handleAction(act)}
                          style={{
                            background: 'rgba(59, 130, 246, 0.2)',
                            border: '1px solid rgba(59, 130, 246, 0.4)',
                            color: '#93c5fd',
                            borderRadius: 'var(--radius-full)',
                            padding: '0.2rem 0.5rem',
                            fontSize: '0.72rem',
                            cursor: 'pointer',
                          }}
                        >
                          {act.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isLoading && (
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Sparkles size={13} className="animate-spin-slow" color="#38bdf8" />
                <span>Thinking & analyzing...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            style={{
              padding: '0.5rem',
              borderTop: '1px solid var(--border-color)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              background: 'rgba(15, 23, 42, 0.8)',
            }}
          >
            <button
              type="button"
              onClick={toggleMic}
              style={{
                width: '34px',
                height: '34px',
                borderRadius: '50%',
                background: isListening ? '#ef4444' : '#3b82f6',
                border: 'none',
                color: '#fff',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title="Voice speak"
            >
              {isListening ? <MicOff size={15} /> : <Mic size={15} />}
            </button>

            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Speak or type grievance..."
              style={{
                flex: 1,
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                color: '#fff',
                fontSize: '0.8rem',
                padding: '0.45rem 0.6rem',
                outline: 'none',
              }}
            />

            <button
              type="submit"
              disabled={!inputText.trim() || isLoading}
              style={{
                width: '34px',
                height: '34px',
                borderRadius: '50%',
                background: '#2563eb',
                border: 'none',
                color: '#fff',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                opacity: !inputText.trim() ? 0.5 : 1,
              }}
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      )}

      {/* Floating Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '58px',
          height: '58px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
          border: '2px solid rgba(255, 255, 255, 0.2)',
          boxShadow: '0 8px 30px rgba(37, 99, 235, 0.5)',
          color: '#ffffff',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          transform: isOpen ? 'rotate(90deg) scale(0.95)' : 'scale(1)',
        }}
        title="Voxentra AI Voice Assistant"
      >
        {isOpen ? <X size={26} /> : <Sparkles size={26} />}
      </button>
    </div>
  );
};
