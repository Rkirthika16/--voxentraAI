import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { assistantApi } from '../api/assistant';
import { complaintsApi } from '../api/complaints';
import {
  AssistantMessage,
  ActionSuggestion,
  ComplaintDraft,
  SuggestionsResponse
} from '../types';
import { speech } from '../utils/speech';
import { useAuth } from '../context/AuthContext';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { PriorityBadge } from '../components/PriorityBadge';
import {
  Sparkles,
  Mic,
  MicOff,
  Send,
  Volume2,
  VolumeX,
  RotateCcw,
  PhoneCall,
  CheckCircle2,
  ExternalLink,
  MapPin,
  Building2,
  AlertTriangle,
  ArrowRight,
  Radio,
  Globe2,
  HelpCircle,
  Clock,
  Trash2
} from 'lucide-react';

export const AIAssistantPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [messages, setMessages] = useState<AssistantMessage[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: "👋 **Vanakkam & Welcome to Voxentra AI Voice Assistant!**\n\nI am your intelligent Tamil Nadu Civic Companion. You can **talk or type** in **Tamil, English, or Tanglish**.\n\nHow can I help you today?",
      spoken_text: "Welcome to Voxentra AI. I am your civic companion. How can I help you today?",
      detected_language: 'English',
      intent: 'GREETING',
      suggested_actions: [
        { label: '💧 Water leak in Gandhipuram', action_type: 'QUICK_PROMPT', payload: { prompt: 'Water pipeline leakage near Gandhipuram bus stand, Coimbatore' } },
        { label: '⚡ Power outage in Peelamedu', action_type: 'QUICK_PROMPT', payload: { prompt: 'Power cut and sparking transformer in Peelamedu' } },
        { label: '🔍 Track complaint status', action_type: 'QUICK_PROMPT', payload: { prompt: 'Track my complaint status' } },
        { label: '🚨 Emergency helpline numbers', action_type: 'QUICK_PROMPT', payload: { prompt: 'What are the emergency helpline numbers in Tamil Nadu?' } },
      ],
      timestamp: new Date(),
    }
  ]);

  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [selectedLang, setSelectedLang] = useState<'Auto' | 'ta-IN' | 'en-IN' | 'Tanglish'>('Auto');
  const [speechRate, setSpeechRate] = useState<number>(1.0);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestionsResponse | null>(null);
  const [submittingDraft, setSubmittingDraft] = useState<boolean>(false);
  const [submittedId, setSubmittedId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    // Generate session ID
    setSessionId(`sess_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`);

    // Load dynamic suggestions
    assistantApi.getSuggestions()
      .then(data => setSuggestions(data))
      .catch(() => {});

    return () => {
      speech.stop();
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSpeakText = (textToSpeak: string, language?: string) => {
    if (!textToSpeak) return;
    speech.unlock();
    setIsSpeaking(true);

    const effectiveLanguage = language || (selectedLang === 'ta-IN' ? 'Tamil' : selectedLang === 'Tanglish' ? 'Tanglish' : selectedLang === 'en-IN' ? 'English' : undefined);

    speech.speak(textToSpeak, {
      language: effectiveLanguage,
      rate: speechRate,
      onStart: () => setIsSpeaking(true),
      onEnd: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  const stopSpeaking = () => {
    speech.stop();
    setIsSpeaking(false);
  };

  const handleSendMessage = async (customMessage?: string) => {
    const textToSend = (customMessage || inputText).trim();
    if (!textToSend || isLoading) return;

    // Unlock browser audio context immediately on user click
    speech.unlock();
    // Stop speaking previous response
    stopSpeaking();

    const userMessage: AssistantMessage = {
      id: `user_${Date.now()}`,
      sender: 'user',
      text: textToSend,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsLoading(true);
    setError(null);

    try {
      const langHint = selectedLang === 'ta-IN' ? 'Tamil' : selectedLang === 'en-IN' ? 'English' : selectedLang === 'Tanglish' ? 'Tanglish' : undefined;
      const res = await assistantApi.chat(textToSend, sessionId, langHint);

      const assistantMsg: AssistantMessage = {
        id: `ast_${Date.now()}`,
        sender: 'assistant',
        text: res.reply_text,
        spoken_text: res.spoken_text,
        detected_language: res.detected_language,
        intent: res.intent,
        draft_complaint: res.draft_complaint,
        status_info: res.status_info,
        suggested_actions: res.suggested_actions,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMsg]);

      // Auto-speak AI response if enabled
      const textToSpeak = res.spoken_text || res.reply_text;
      if (autoSpeak && textToSpeak) {
        const speakLanguage = langHint || res.detected_language || (selectedLang === 'ta-IN' ? 'Tamil' : undefined);
        handleSpeakText(textToSpeak, speakLanguage);
      }
    } catch (err: any) {

      console.error('Assistant error:', err);
      setError(err.response?.data?.detail || 'Failed to get response from AI assistant.');
    } finally {
      setIsLoading(false);
    }
  };

  // Start real-time speech recognition
  const toggleVoiceInput = () => {
    if (isListening) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
      setIsListening(false);
      return;
    }

    stopSpeaking();
    setError(null);

    if (speech.isSTTSupported()) {
      const lang = selectedLang === 'ta-IN' ? 'ta-IN' : 'en-IN';
      const recognition = speech.createRecognition(
        lang,
        (transcript, isFinal) => {
          setInputText(transcript);
          if (isFinal && transcript.trim()) {
            setIsListening(false);
            handleSendMessage(transcript);
          }
        },
        (err) => {
          console.warn('Speech recognition error:', err);
          setIsListening(false);
          // Fallback to audio recorder recording
          startAudioBlobRecording();
        },
        () => setIsListening(false)
      );

      if (recognition) {
        recognitionRef.current = recognition;
        try {
          recognition.start();
          setIsListening(true);
          return;
        } catch (e) {
          console.warn('Could not start recognition, using audio recorder fallback', e);
        }
      }
    }

    // Fallback: Audio blob recorder
    startAudioBlobRecording();
  };

  const startAudioBlobRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Microphone access is not supported in this browser.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach(t => t.stop());
        setIsListening(false);

        // Send audio to voice chat API
        setIsLoading(true);
        try {
          const langHint = selectedLang === 'ta-IN' ? 'ta' : selectedLang === 'en-IN' ? 'en' : undefined;
          const res = await assistantApi.voiceChat(audioBlob, 'voice_query.webm', sessionId, langHint);

          const assistantMsg: AssistantMessage = {
            id: `ast_${Date.now()}`,
            sender: 'assistant',
            text: res.reply_text,
            spoken_text: res.spoken_text,
            detected_language: res.detected_language,
            intent: res.intent,
            draft_complaint: res.draft_complaint,
            status_info: res.status_info,
            suggested_actions: res.suggested_actions,
            timestamp: new Date(),
            isAudio: true,
          };

          setMessages(prev => [...prev, assistantMsg]);

          if (autoSpeak && res.spoken_text) {
            handleSpeakText(res.spoken_text, res.detected_language);
          }
        } catch (err: any) {
          setError(err.response?.data?.detail || 'Voice processing failed.');
        } finally {
          setIsLoading(false);
        }
      };

      mediaRecorder.start();
      setIsListening(true);
    } catch (err: any) {
      setError('Microphone access denied: ' + (err.message || 'Unknown error'));
      setIsListening(false);
    }
  };

  const handleActionClick = async (action: ActionSuggestion) => {
    if (action.action_type === 'QUICK_PROMPT') {
      const prompt = action.payload.prompt;
      if (prompt === 'edit_draft') {
        navigate('/submit', { state: { draft: action.payload.draft } });
        return;
      }
      handleSendMessage(prompt);
    } else if (action.action_type === 'CALL_HELPLINE') {
      const phone = action.payload.phone;
      window.open(`tel:${phone}`, '_self');
    } else if (action.action_type === 'TRACK_COMPLAINT') {
      const trackingNumber = action.payload.tracking_number;
      if (trackingNumber) {
        navigate(`/track?number=${encodeURIComponent(trackingNumber)}`);
      } else {
        navigate('/track');
      }
    } else if (action.action_type === 'SUBMIT_DRAFT') {
      const draft: ComplaintDraft = action.payload as ComplaintDraft;
      // Submit draft directly
      setSubmittingDraft(true);
      setError(null);
      try {
        const created = await complaintsApi.createComplaint({
          title: draft.title,
          description: draft.description,
          category: draft.category,
          location: draft.extracted_location || 'Tamil Nadu',
          latitude: draft.latitude,
          longitude: draft.longitude,
          priority: draft.priority,
          source: 'WEB_VOICE',
        });

        setSubmittedId(created.complaint_number);

        const confirmMsg: AssistantMessage = {
          id: `ast_conf_${Date.now()}`,
          sender: 'assistant',
          text: `🎉 **Grievance Registered Successfully!**\n\n- **Tracking ID:** \`${created.complaint_number}\`\n- **Category:** ${created.category}\n- **Department:** ${created.department_name || draft.suggested_department}\n- **Status:** **Submitted (Assigned to Field Officer)**\n\nYour complaint has been queued for official action. You can track progress anytime with your Tracking ID.`,
          spoken_text: `Your grievance has been successfully registered with Tracking ID ${created.complaint_number} and forwarded to ${created.department_name || draft.suggested_department}.`,
          detected_language: 'English',
          intent: 'CONFIRMATION',
          suggested_actions: [
            { label: '👁️ View in Live Tracker', action_type: 'TRACK_COMPLAINT', payload: { tracking_number: created.complaint_number } },
            { label: '📜 View My Complaint History', action_type: 'QUICK_PROMPT', payload: { prompt: 'Track my complaint status' } }
          ],
          timestamp: new Date(),
        };

        setMessages(prev => [...prev, confirmMsg]);
        if (autoSpeak) {
          handleSpeakText(`Your grievance has been successfully registered with Tracking ID ${created.complaint_number}.`);
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to submit complaint automatically. You can review and submit manually.');
      } finally {
        setSubmittingDraft(false);
      }
    }
  };

  const clearChat = () => {
    stopSpeaking();
    setMessages([
      {
        id: `welcome_${Date.now()}`,
        sender: 'assistant',
        text: "✨ Conversation cleared. What else can I assist you with today?",
        spoken_text: "Conversation cleared. How can I help you?",
        detected_language: 'English',
        intent: 'GREETING',
        suggested_actions: [
          { label: '💧 Water pipeline leak', action_type: 'QUICK_PROMPT', payload: { prompt: 'Water pipeline leakage near Gandhipuram bus stand' } },
          { label: '⚡ Electricity fuse spark', action_type: 'QUICK_PROMPT', payload: { prompt: 'Power cut and electric spark in my street' } },
          { label: '🔍 Track complaint', action_type: 'QUICK_PROMPT', payload: { prompt: 'Track my complaint' } }
        ],
        timestamp: new Date()
      }
    ]);
  };

  return (
    <div className="page-container" style={{ maxWidth: '1050px', paddingBottom: '3rem' }}>
      {/* Header Banner */}
      <div
        className="glass-card animate-fade-in"
        style={{
          padding: '1.5rem 2rem',
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.95))',
          border: '1px solid rgba(59, 130, 246, 0.3)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          {/* Animated AI Talking Avatar Orb */}
          <div
            style={{
              position: 'relative',
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: isSpeaking
                ? 'linear-gradient(135deg, #10b981, #06b6d4)'
                : isListening
                ? 'linear-gradient(135deg, #ef4444, #f59e0b)'
                : 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: isSpeaking
                ? '0 0 25px rgba(16, 185, 129, 0.7)'
                : isListening
                ? '0 0 25px rgba(239, 68, 68, 0.7)'
                : '0 0 20px rgba(59, 130, 246, 0.4)',
              transition: 'all 0.4s ease',
              animation: isSpeaking ? 'pulse 1.2s infinite alternate' : isListening ? 'pulse 0.8s infinite' : 'none',
            }}
          >
            {isSpeaking ? (
              <Radio size={28} color="#ffffff" className="animate-spin-slow" />
            ) : isListening ? (
              <Mic size={28} color="#ffffff" />
            ) : (
              <Sparkles size={28} color="#ffffff" />
            )}

            {/* Speaking Status Dot */}
            <span
              style={{
                position: 'absolute',
                bottom: '2px',
                right: '2px',
                width: '14px',
                height: '14px',
                borderRadius: '50%',
                backgroundColor: isSpeaking ? '#10b981' : isListening ? '#ef4444' : '#3b82f6',
                border: '2px solid var(--bg-card)',
              }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Voxentra AI Voice & Talking Assistant</h1>
              <span
                style={{
                  fontSize: '0.7rem',
                  padding: '0.15rem 0.5rem',
                  borderRadius: 'var(--radius-full)',
                  background: 'rgba(59, 130, 246, 0.2)',
                  color: '#60a5fa',
                  fontWeight: 600,
                  border: '1px solid rgba(59, 130, 246, 0.3)',
                }}
              >
                குரல் உதவியாளர்
              </span>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
              {isSpeaking
                ? '🗣️ AI is speaking...'
                : isListening
                ? '🎙️ Listening to your voice (speak in Tamil / English)...'
                : 'Speak or type civic grievances in Tamil, Tanglish, or English.'}
            </p>
          </div>
        </div>

        {/* Controls Toolbar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Language Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', background: 'var(--bg-input)', padding: '0.3rem 0.6rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', fontSize: '0.8rem' }}>
            <Globe2 size={14} color="#38bdf8" />
            <select
              value={selectedLang}
              onChange={(e) => setSelectedLang(e.target.value as any)}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-main)', fontSize: '0.8rem', cursor: 'pointer', outline: 'none' }}
            >
              <option value="Auto" style={{ background: '#1e293b' }}>🌐 Auto Detect</option>
              <option value="ta-IN" style={{ background: '#1e293b' }}>🇮🇳 தமிழ் (Tamil)</option>
              <option value="Tanglish" style={{ background: '#1e293b' }}>🗣️ Tanglish (Tamil in English)</option>
              <option value="en-IN" style={{ background: '#1e293b' }}>🇬🇧 English (India)</option>
            </select>
          </div>

          {/* Auto Speak Toggle */}
          <button
            type="button"
            onClick={() => {
              if (isSpeaking) stopSpeaking();
              setAutoSpeak(!autoSpeak);
            }}
            className={`btn btn-sm ${autoSpeak ? 'btn-primary' : 'btn-secondary'}`}
            title={autoSpeak ? 'Voice response enabled' : 'Voice response muted'}
            style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}
          >
            {autoSpeak ? <Volume2 size={14} /> : <VolumeX size={14} />}
            <span>{autoSpeak ? 'Voice: On' : 'Voice: Off'}</span>
          </button>

          {/* Clear Button */}
          <button
            type="button"
            onClick={clearChat}
            className="btn btn-secondary btn-sm"
            title="Clear conversation"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {error && <ErrorMessage message={error} />}

      {/* Main Chat Stream Container */}
      <div
        className="glass-card"
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '580px',
          padding: '1.25rem',
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(16px)',
          border: '1px solid var(--border-color)',
        }}
      >
        {/* Messages List */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            paddingRight: '0.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.25rem',
          }}
        >
          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: msg.sender === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              <div
                style={{
                  maxWidth: '85%',
                  padding: '1rem 1.25rem',
                  borderRadius: 'var(--radius-lg)',
                  background: msg.sender === 'user'
                    ? 'linear-gradient(135deg, #2563eb, #1d4ed8)'
                    : 'rgba(30, 41, 59, 0.85)',
                  border: msg.sender === 'user'
                    ? '1px solid rgba(59, 130, 246, 0.4)'
                    : '1px solid var(--border-color)',
                  color: 'var(--text-main)',
                  boxShadow: '0 4px 15px rgba(0, 0, 0, 0.2)',
                }}
              >
                {/* Assistant Message Header with Speaker & Lang */}
                {msg.sender === 'assistant' && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '0.65rem',
                      paddingBottom: '0.4rem',
                      borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                      fontSize: '0.75rem',
                      color: 'var(--text-dim)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Sparkles size={14} color="#38bdf8" />
                      <strong style={{ color: '#38bdf8' }}>Voxentra AI</strong>
                      {msg.detected_language && (
                        <span style={{ opacity: 0.8 }}>({msg.detected_language})</span>
                      )}
                    </div>

                    <button
                      onClick={() => handleSpeakText(msg.spoken_text || msg.text, msg.detected_language)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: isSpeaking ? '#10b981' : 'var(--text-muted)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.25rem',
                        fontSize: '0.75rem',
                      }}
                      title="Speak / Replay AI response"
                    >
                      <Volume2 size={14} /> Listen
                    </button>
                  </div>
                )}

                {/* Message Body */}
                <div
                  style={{
                    fontSize: '0.92rem',
                    lineHeight: '1.55',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {msg.text}
                </div>

                {/* Draft Complaint Card Inside Message */}
                {msg.draft_complaint && (
                  <div
                    style={{
                      marginTop: '1rem',
                      padding: '1rem',
                      borderRadius: 'var(--radius-md)',
                      background: 'rgba(15, 23, 42, 0.9)',
                      border: '1px solid rgba(59, 130, 246, 0.4)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#60a5fa', textTransform: 'uppercase' }}>
                        Draft Grievance Ready
                      </span>
                      <PriorityBadge priority={msg.draft_complaint.priority} />
                    </div>

                    <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.35rem' }}>
                      {msg.draft_complaint.title}
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Building2 size={13} color="#a78bfa" />
                        <span>{msg.draft_complaint.suggested_department}</span>
                      </div>
                      {msg.draft_complaint.extracted_location && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <MapPin size={13} color="#38bdf8" />
                          <span>{msg.draft_complaint.extracted_location}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Action Buttons Chips */}
                {msg.suggested_actions && msg.suggested_actions.length > 0 && (
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                      marginTop: '0.85rem',
                      paddingTop: '0.5rem',
                      borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                    }}
                  >
                    {msg.suggested_actions.map((act, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleActionClick(act)}
                        disabled={submittingDraft}
                        style={{
                          background: act.action_type === 'SUBMIT_DRAFT'
                            ? 'linear-gradient(135deg, #10b981, #059669)'
                            : act.action_type === 'CALL_HELPLINE'
                            ? 'rgba(239, 68, 68, 0.2)'
                            : 'rgba(59, 130, 246, 0.15)',
                          border: act.action_type === 'SUBMIT_DRAFT'
                            ? '1px solid #10b981'
                            : act.action_type === 'CALL_HELPLINE'
                            ? '1px solid rgba(239, 68, 68, 0.5)'
                            : '1px solid rgba(59, 130, 246, 0.35)',
                          color: act.action_type === 'SUBMIT_DRAFT'
                            ? '#ffffff'
                            : act.action_type === 'CALL_HELPLINE'
                            ? '#fca5a5'
                            : '#93c5fd',
                          borderRadius: 'var(--radius-full)',
                          padding: '0.35rem 0.75rem',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.35rem',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        {act.action_type === 'SUBMIT_DRAFT' && <CheckCircle2 size={13} />}
                        {act.action_type === 'CALL_HELPLINE' && <PhoneCall size={13} />}
                        {act.action_type === 'TRACK_COMPLAINT' && <ExternalLink size={13} />}
                        <span>{act.label}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Timestamp */}
              <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '0.25rem', padding: '0 0.5rem' }}>
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}

          {isLoading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', padding: '0.5rem' }}>
              <Sparkles size={16} className="animate-spin-slow" color="#3b82f6" />
              <span style={{ fontSize: '0.85rem' }}>Voxentra AI is analyzing & generating spoken response...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Suggestion Chips Footer */}
        {suggestions && suggestions.sample_questions.length > 0 && (
          <div
            style={{
              padding: '0.5rem 0',
              overflowX: 'auto',
              whiteSpace: 'nowrap',
              display: 'flex',
              gap: '0.5rem',
              borderTop: '1px solid rgba(255, 255, 255, 0.05)',
              marginBottom: '0.5rem',
            }}
          >
            {suggestions.sample_questions.map((sq, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSendMessage(sq.query)}
                style={{
                  background: 'rgba(30, 41, 59, 0.6)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: 'var(--radius-full)',
                  padding: '0.25rem 0.65rem',
                  color: 'var(--text-muted)',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  flexShrink: 0,
                  transition: 'all 0.2s ease',
                }}
              >
                {sq.label}
              </button>
            ))}
          </div>
        )}

        {/* Input Controls Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.65rem',
            background: 'var(--bg-input)',
            borderRadius: 'var(--radius-lg)',
            padding: '0.4rem 0.6rem',
            border: '1px solid var(--border-color)',
          }}
        >
          {/* Voice Microphone Toggle */}
          <button
            type="button"
            onClick={toggleVoiceInput}
            className={`btn btn-icon ${isListening ? 'btn-danger' : 'btn-primary'}`}
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '50%',
              flexShrink: 0,
              boxShadow: isListening ? '0 0 15px rgba(239, 68, 68, 0.6)' : 'none',
              animation: isListening ? 'pulse 1s infinite' : 'none',
            }}
            title={isListening ? 'Stop listening' : 'Start speaking with AI'}
          >
            {isListening ? <MicOff size={18} /> : <Mic size={18} />}
          </button>

          {/* Text Input */}
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={
              isListening
                ? 'Listening to you... (Speak now)'
                : 'Ask a question or speak your grievance in Tamil / English...'
            }
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              color: 'var(--text-main)',
              fontSize: '0.92rem',
              outline: 'none',
              padding: '0.4rem 0.25rem',
            }}
          />

          {/* Send Button */}
          <button
            type="submit"
            disabled={!inputText.trim() || isLoading}
            className="btn btn-primary btn-icon"
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              flexShrink: 0,
              opacity: !inputText.trim() ? 0.5 : 1,
            }}
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
};
