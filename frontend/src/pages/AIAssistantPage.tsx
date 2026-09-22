import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { assistantApi } from '../api/assistant';
import { complaintsApi } from '../api/complaints';
import {
  AssistantMessage,
  ActionSuggestion,
  ComplaintDraft,
  ComplaintCollectionState,
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
  Trash2,
  Check,
  Circle,
  FileText,
  Navigation,
  Milestone,
  Map,
  Landmark,
  Calendar,
  Repeat,
  Activity,
  PlusCircle,
  UserCheck,
  ChevronRight,
  ShieldCheck,
  CheckCircle
} from 'lucide-react';

const FIELD_CONFIG = [
  { key: 'problem_description', labelEn: 'Problem Description', labelTa: 'பிரச்சனை விவரம்', icon: FileText },
  { key: 'exact_location', labelEn: 'Exact Location', labelTa: 'சரியான இடம்', icon: Navigation },
  { key: 'street_road_name', labelEn: 'Street / Road Name', labelTa: 'தெரு / சாலை பெயர்', icon: Milestone },
  { key: 'district_area', labelEn: 'District / Area', labelTa: 'மாவட்டம் / பகுதி', icon: Map },
  { key: 'landmark', labelEn: 'Landmark', labelTa: 'அடையாளம்', icon: Landmark },
  { key: 'date_and_time', labelEn: 'Date & Time', labelTa: 'தேதி & நேரம்', icon: Calendar },
  { key: 'frequency', labelEn: 'Frequency', labelTa: 'நிகழ்வு வீதம்', icon: Repeat },
  { key: 'current_status', labelEn: 'Current Status', labelTa: 'தற்போதைய நிலை', icon: Activity },
  { key: 'additional_details', labelEn: 'Additional Details', labelTa: 'கூடுதல் விவரம்', icon: PlusCircle },
  { key: 'citizen_details', labelEn: 'Citizen Contact', labelTa: 'தொடர்பு விவரம்', icon: UserCheck },
];

export const AIAssistantPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [sessionId, setSessionId] = useState<string>('');
  const [messages, setMessages] = useState<AssistantMessage[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: "👋 **Vanakkam & Welcome to Voxentra AI Multilingual Civic Assistant!**\n\nI can speak and understand **Tamil (தமிழ்), English, and Tanglish**.\n\nI will guide you step-by-step to collect all **10 required details** and register your grievance directly with the government department.\n\n**How can I help you today? Please state your civic issue.**",
      spoken_text: "Welcome to Voxentra AI. I am your multilingual civic assistant. Please describe the problem you would like to report.",
      detected_language: 'English',
      intent: 'GREETING',
      suggested_actions: [
        { label: '💧 Water pipeline leakage', action_type: 'QUICK_PROMPT', payload: { prompt: 'Water pipeline is broken and leaking severely in Gandhipuram, Coimbatore' } },
        { label: '⚡ Transformer fuse spark', action_type: 'QUICK_PROMPT', payload: { prompt: 'Electric fuse sparking on Peelamedu main road' } },
        { label: '🗑️ Uncollected garbage', action_type: 'QUICK_PROMPT', payload: { prompt: 'Garbage dump has not been cleared for 3 days in RS Puram' } },
        { label: '🔍 Track complaint status', action_type: 'QUICK_PROMPT', payload: { prompt: 'Track my complaint status' } },
      ],
      timestamp: new Date(),
    }
  ]);

  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedLang, setSelectedLang] = useState<'Auto' | 'ta-IN' | 'en-IN' | 'Tanglish'>('Auto');
  const [speechRate, setSpeechRate] = useState<number>(1.0);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestionsResponse | null>(null);
  const [collectionState, setCollectionState] = useState<ComplaintCollectionState | null>(null);
  const [audioPlayer, setAudioPlayer] = useState<HTMLAudioElement | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    const newSid = `sess_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    setSessionId(newSid);

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

  const stopSpeaking = () => {
    if (audioPlayer) {
      audioPlayer.pause();
      audioPlayer.currentTime = 0;
    }
    speech.stop();
    setIsSpeaking(false);
  };

  const handleSpeakText = (textToSpeak: string, language?: string) => {
    if (!textToSpeak) return;
    stopSpeaking();
    speech.unlock();
    setIsSpeaking(true);

    const effectiveLanguage = language || (selectedLang === 'ta-IN' ? 'Tamil' : selectedLang === 'Tanglish' ? 'Tanglish' : selectedLang === 'en-IN' ? 'English' : undefined);

    // Try backend streaming TTS first for crystal clear Tamil/English audio
    try {
      const ttsLang = (effectiveLanguage === 'Tamil' || /[\u0B80-\u0BFF]/.test(textToSpeak)) ? 'ta' : 'en';
      const audioUrl = `/api/v1/assistant/tts?text=${encodeURIComponent(textToSpeak)}&lang=${ttsLang}`;
      const audio = new Audio(audioUrl);
      setAudioPlayer(audio);

      audio.onplay = () => setIsSpeaking(true);
      audio.onended = () => setIsSpeaking(false);
      audio.onerror = () => {
        // Fallback to client synthesis
        speech.speak(textToSpeak, {
          language: effectiveLanguage,
          rate: speechRate,
          onStart: () => setIsSpeaking(true),
          onEnd: () => setIsSpeaking(false),
          onError: () => setIsSpeaking(false),
        });
      };

      audio.play().catch(() => {
        speech.speak(textToSpeak, {
          language: effectiveLanguage,
          rate: speechRate,
          onStart: () => setIsSpeaking(true),
          onEnd: () => setIsSpeaking(false),
          onError: () => setIsSpeaking(false),
        });
      });
    } catch {
      speech.speak(textToSpeak, {
        language: effectiveLanguage,
        rate: speechRate,
        onStart: () => setIsSpeaking(true),
        onEnd: () => setIsSpeaking(false),
        onError: () => setIsSpeaking(false),
      });
    }
  };

  const handleSendMessage = async (customMessage?: string) => {
    const textToSend = (customMessage || inputText).trim();
    if (!textToSend || isLoading) return;

    speech.unlock();
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

      if (res.collection_state) {
        setCollectionState(res.collection_state);
      }

      const assistantMsg: AssistantMessage = {
        id: `ast_${Date.now()}`,
        sender: 'assistant',
        text: res.reply_text,
        spoken_text: res.spoken_text,
        detected_language: res.detected_language,
        intent: res.intent,
        draft_complaint: res.draft_complaint,
        status_info: res.status_info,
        collection_state: res.collection_state,
        suggested_actions: res.suggested_actions,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMsg]);

      const textToSpeak = res.spoken_text || res.reply_text;
      if (autoSpeak && textToSpeak) {
        handleSpeakText(textToSpeak, res.detected_language);
      }
    } catch (err: any) {
      console.error('Assistant error:', err);
      setError(err.response?.data?.detail || 'Failed to get response from AI assistant.');
    } finally {
      setIsLoading(false);
    }
  };

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
          console.warn('Recognition start failed, fallback to audio recording', e);
        }
      }
    }

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

        setIsLoading(true);
        try {
          const langHint = selectedLang === 'ta-IN' ? 'ta' : selectedLang === 'en-IN' ? 'en' : undefined;
          const res = await assistantApi.voiceChat(audioBlob, 'voice_query.webm', sessionId, langHint);

          if (res.collection_state) {
            setCollectionState(res.collection_state);
          }

          const assistantMsg: AssistantMessage = {
            id: `ast_${Date.now()}`,
            sender: 'assistant',
            text: res.reply_text,
            spoken_text: res.spoken_text,
            detected_language: res.detected_language,
            intent: res.intent,
            draft_complaint: res.draft_complaint,
            status_info: res.status_info,
            collection_state: res.collection_state,
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
      const prompt = action.payload?.prompt;
      if (prompt) handleSendMessage(prompt);
    } else if (action.action_type === 'CALL_HELPLINE') {
      const phone = action.payload?.phone;
      window.open(`tel:${phone}`, '_self');
    } else if (action.action_type === 'TRACK_COMPLAINT') {
      const trackingNumber = action.payload?.tracking_number;
      if (trackingNumber) {
        navigate(`/track?number=${encodeURIComponent(trackingNumber)}`);
      } else {
        navigate('/track');
      }
    }
  };

  const handleResetSession = async () => {
    stopSpeaking();
    if (sessionId) {
      try {
        await assistantApi.resetCollectionSession(sessionId);
      } catch (e) {}
    }
    const newSid = `sess_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    setSessionId(newSid);
    setCollectionState(null);
    setMessages([
      {
        id: `welcome_${Date.now()}`,
        sender: 'assistant',
        text: "✨ **Conversation reset!**\n\nI am ready to help you report a new civic complaint or track an existing one in **Tamil, English, or Tanglish**.\n\nPlease describe what problem has occurred.",
        spoken_text: "Session reset. Please describe what problem has occurred.",
        detected_language: 'English',
        intent: 'GREETING',
        suggested_actions: [
          { label: '💧 Water pipeline leak', action_type: 'QUICK_PROMPT', payload: { prompt: 'Water pipeline leakage near Gandhipuram bus stand' } },
          { label: '⚡ Electricity spark', action_type: 'QUICK_PROMPT', payload: { prompt: 'Power cut and electric spark in my street' } },
          { label: '🔍 Track complaint', action_type: 'QUICK_PROMPT', payload: { prompt: 'Track my complaint' } }
        ],
        timestamp: new Date()
      }
    ]);
  };

  const completionPct = collectionState ? collectionState.completion_percentage : 0;
  const completedCount = collectionState ? collectionState.completed_fields_count : 0;

  return (
    <div className="page-container" style={{ maxWidth: '1200px', paddingBottom: '3rem' }}>
      {/* Top Banner Header */}
      <div
        className="glass-card animate-fade-in"
        style={{
          padding: '1.25rem 1.75rem',
          marginBottom: '1.25rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.85), rgba(15, 23, 42, 0.95))',
          border: '1px solid rgba(59, 130, 246, 0.35)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          {/* Animated AI Talking Avatar Orb */}
          <div
            style={{
              position: 'relative',
              width: '60px',
              height: '60px',
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
              <Radio size={26} color="#ffffff" className="animate-spin-slow" />
            ) : isListening ? (
              <Mic size={26} color="#ffffff" />
            ) : (
              <Sparkles size={26} color="#ffffff" />
            )}

            <span
              style={{
                position: 'absolute',
                bottom: '2px',
                right: '2px',
                width: '13px',
                height: '13px',
                borderRadius: '50%',
                backgroundColor: isSpeaking ? '#10b981' : isListening ? '#ef4444' : '#3b82f6',
                border: '2px solid var(--bg-card)',
              }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.2rem', flexWrap: 'wrap' }}>
              <h1 style={{ fontSize: '1.4rem', fontWeight: 700, margin: 0 }}>
                Multilingual AI Citizen Interaction & Grievance Intake
              </h1>
              <span
                style={{
                  fontSize: '0.72rem',
                  padding: '0.15rem 0.6rem',
                  borderRadius: 'var(--radius-full)',
                  background: 'rgba(59, 130, 246, 0.2)',
                  color: '#60a5fa',
                  fontWeight: 600,
                  border: '1px solid rgba(59, 130, 246, 0.3)',
                }}
              >
                தமிழ் • Tanglish • English
              </span>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
              {isSpeaking
                ? '🗣️ AI is speaking...'
                : isListening
                ? '🎙️ Listening to your voice (Speak in Tamil / English)...'
                : '10-Point automated complaint collection, validation, and direct department forwarding.'}
            </p>
          </div>
        </div>

        {/* Header Toolbar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
          {/* Language Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', background: 'var(--bg-input)', padding: '0.3rem 0.6rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', fontSize: '0.8rem' }}>
            <Globe2 size={14} color="#38bdf8" />
            <select
              value={selectedLang}
              onChange={(e) => setSelectedLang(e.target.value as any)}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-main)', fontSize: '0.8rem', cursor: 'pointer', outline: 'none' }}
            >
              <option value="Auto" style={{ background: '#1e293b' }}>🌐 Auto Detect Language</option>
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

          {/* Reset / Clear Button */}
          <button
            type="button"
            onClick={handleResetSession}
            className="btn btn-secondary btn-sm"
            title="Reset Grievance Intake Session"
            style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}
          >
            <RotateCcw size={14} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {error && <ErrorMessage message={error} />}

      {/* Main Grid: Chat Stream (Left) + 10-Point Collection Tracker (Right) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) 340px',
          gap: '1.25rem',
          alignItems: 'start',
        }}
      >
        {/* Left Column: Conversational Chat Interface */}
        <div
          className="glass-card"
          style={{
            display: 'flex',
            flexDirection: 'column',
            height: '620px',
            padding: '1.25rem',
            background: 'rgba(15, 23, 42, 0.75)',
            backdropFilter: 'blur(16px)',
            border: '1px solid var(--border-color)',
          }}
        >
          {/* Messages Feed */}
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
                    maxWidth: '88%',
                    padding: '1rem 1.25rem',
                    borderRadius: 'var(--radius-lg)',
                    background: msg.sender === 'user'
                      ? 'linear-gradient(135deg, #2563eb, #1d4ed8)'
                      : 'rgba(30, 41, 59, 0.9)',
                    border: msg.sender === 'user'
                      ? '1px solid rgba(59, 130, 246, 0.4)'
                      : '1px solid var(--border-color)',
                    color: 'var(--text-main)',
                    boxShadow: '0 4px 15px rgba(0, 0, 0, 0.2)',
                  }}
                >
                  {/* Assistant Message Header */}
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
                          <span
                            style={{
                              padding: '0.1rem 0.4rem',
                              borderRadius: '4px',
                              background: 'rgba(56, 189, 248, 0.15)',
                              color: '#7dd3fc',
                              fontSize: '0.7rem',
                            }}
                          >
                            {msg.detected_language}
                          </span>
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
                        title="Replay Audio"
                      >
                        <Volume2 size={14} /> Listen
                      </button>
                    </div>
                  )}

                  {/* Message Body */}
                  <div
                    style={{
                      fontSize: '0.92rem',
                      lineHeight: '1.6',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {msg.text}
                  </div>

                  {/* Suggestion Chips */}
                  {msg.suggested_actions && msg.suggested_actions.length > 0 && (
                    <div
                      style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '0.5rem',
                        marginTop: '0.85rem',
                        paddingTop: '0.6rem',
                        borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                      }}
                    >
                      {msg.suggested_actions.map((act, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleActionClick(act)}
                          style={{
                            background: act.action_type === 'TRACK_COMPLAINT'
                              ? 'linear-gradient(135deg, #10b981, #059669)'
                              : act.action_type === 'CALL_HELPLINE'
                              ? 'rgba(239, 68, 68, 0.2)'
                              : 'rgba(59, 130, 246, 0.18)',
                            border: act.action_type === 'TRACK_COMPLAINT'
                              ? '1px solid #10b981'
                              : act.action_type === 'CALL_HELPLINE'
                              ? '1px solid rgba(239, 68, 68, 0.5)'
                              : '1px solid rgba(59, 130, 246, 0.4)',
                            color: act.action_type === 'TRACK_COMPLAINT'
                              ? '#ffffff'
                              : act.action_type === 'CALL_HELPLINE'
                              ? '#fca5a5'
                              : '#bfdbfe',
                            borderRadius: 'var(--radius-full)',
                            padding: '0.35rem 0.8rem',
                            fontSize: '0.8rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            transition: 'all 0.2s ease',
                          }}
                        >
                          {act.action_type === 'TRACK_COMPLAINT' && <CheckCircle size={13} />}
                          {act.action_type === 'CALL_HELPLINE' && <PhoneCall size={13} />}
                          <span>{act.label}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '0.25rem', padding: '0 0.5rem' }}>
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}

            {isLoading && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', padding: '0.5rem' }}>
                <Sparkles size={16} className="animate-spin-slow" color="#3b82f6" />
                <span style={{ fontSize: '0.85rem' }}>Voxentra AI is analyzing input & formulating response...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Suggestions Chips Footer */}
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
                width: '44px',
                height: '44px',
                borderRadius: '50%',
                flexShrink: 0,
                boxShadow: isListening ? '0 0 18px rgba(239, 68, 68, 0.7)' : 'none',
                animation: isListening ? 'pulse 1s infinite' : 'none',
              }}
              title={isListening ? 'Stop listening' : 'Start speaking with AI (Tamil / English)'}
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
                  ? '🎙️ Listening to you... (Speak now in Tamil or English)'
                  : 'Speak or type your answer / grievance details here...'
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
                width: '42px',
                height: '42px',
                borderRadius: '50%',
                flexShrink: 0,
                opacity: !inputText.trim() ? 0.5 : 1,
              }}
            >
              <Send size={16} />
            </button>
          </form>
        </div>

        {/* Right Column: 10-Point Intake Progress Tracker Panel */}
        <div
          className="glass-card animate-fade-in"
          style={{
            padding: '1.25rem',
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
          }}
        >
          {/* Tracker Header */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#60a5fa', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                10-Point Intake Tracker
              </span>
              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: completionPct === 100 ? '#10b981' : '#38bdf8' }}>
                {completedCount}/10 Collected
              </span>
            </div>

            {/* Progress Bar */}
            <div
              style={{
                width: '100%',
                height: '8px',
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                borderRadius: '4px',
                overflow: 'hidden',
                marginTop: '0.35rem',
              }}
            >
              <div
                style={{
                  width: `${completionPct}%`,
                  height: '100%',
                  background: completionPct === 100
                    ? 'linear-gradient(90deg, #10b981, #06b6d4)'
                    : 'linear-gradient(90deg, #3b82f6, #8b5cf6)',
                  borderRadius: '4px',
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
          </div>

          {/* 10 Details Visual Checklist */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.45rem',
              maxHeight: '440px',
              overflowY: 'auto',
              paddingRight: '0.25rem',
            }}
          >
            {FIELD_CONFIG.map((field, idx) => {
              const Icon = field.icon;
              const val = collectionState?.fields?.[field.key];
              const isFilled = Boolean(val && String(val).trim());
              const isCurrent = collectionState?.current_field_prompted === field.key;

              return (
                <div
                  key={field.key}
                  style={{
                    padding: '0.55rem 0.75rem',
                    borderRadius: 'var(--radius-md)',
                    background: isFilled
                      ? 'rgba(16, 185, 129, 0.1)'
                      : isCurrent
                      ? 'rgba(59, 130, 246, 0.2)'
                      : 'rgba(255, 255, 255, 0.03)',
                    border: isFilled
                      ? '1px solid rgba(16, 185, 129, 0.35)'
                      : isCurrent
                      ? '1px solid rgba(59, 130, 246, 0.6)'
                      : '1px solid rgba(255, 255, 255, 0.06)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.2rem',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 600 }}>
                        {idx + 1}.
                      </span>
                      <Icon size={14} color={isFilled ? '#34d399' : isCurrent ? '#60a5fa' : '#94a3b8'} />
                      <span style={{ fontSize: '0.78rem', fontWeight: 600, color: isFilled ? '#e2e8f0' : 'var(--text-muted)' }}>
                        {field.labelEn}
                      </span>
                    </div>

                    {isFilled ? (
                      <CheckCircle2 size={14} color="#10b981" />
                    ) : isCurrent ? (
                      <span style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.4)', color: '#93c5fd', fontWeight: 700 }}>
                        ACTIVE
                      </span>
                    ) : (
                      <Circle size={12} color="rgba(255,255,255,0.2)" />
                    )}
                  </div>

                  {/* Captured Field Value */}
                  {isFilled && (
                    <div
                      style={{
                        fontSize: '0.74rem',
                        color: '#a7f3d0',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        paddingLeft: '1.4rem',
                      }}
                      title={String(val)}
                    >
                      {String(val)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Status Note */}
          <div
            style={{
              padding: '0.75rem',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(30, 41, 59, 0.5)',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              fontSize: '0.75rem',
              color: 'var(--text-dim)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <ShieldCheck size={18} color="#38bdf8" />
            <span>AI validates completeness before submitting to avoid missing field rejections.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
