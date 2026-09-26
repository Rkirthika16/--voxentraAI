import React, { useState, useEffect, useRef } from 'react';
import {
  Phone,
  PhoneOff,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Send,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sparkles,
  RefreshCw,
  FileText,
  MapPin,
  Building,
  ShieldAlert,
  HelpCircle,
  Languages
} from 'lucide-react';
import { newIvrApi, NewIVRMemory, NewIVRMessage } from '../api/newIvr';

export const LiveTwoWayIVRPage: React.FC = () => {
  // Call & Session State
  const [callActive, setCallActive] = useState<boolean>(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [ivrState, setIvrState] = useState<string>('CALL_DISCONNECTED');
  const [callDuration, setCallDuration] = useState<number>(0);
  const [detectedLanguage, setDetectedLanguage] = useState<string>('Auto');
  const [questionCount, setQuestionCount] = useState<number>(0);
  const [maxQuestions, setMaxQuestions] = useState<number>(10);

  // Messages & Memory State
  const [messages, setMessages] = useState<NewIVRMessage[]>([]);
  const [memory, setMemory] = useState<NewIVRMemory>({
    category: null,
    problem: null,
    location: null,
    duration: null,
    affected_scope: null,
    frequency: null,
    severity: null,
    priority: 'MEDIUM',
    department: null,
    citizen_name: null,
  });

  // Audio & Speech Recording
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isAiSpeaking, setIsAiSpeaking] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [ttsMuted, setTtsMuted] = useState<boolean>(false);
  const [textInput, setTextInput] = useState<string>('');
  const [liveTranscript, setLiveTranscript] = useState<string>('');
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Complaint Registered Success
  const [registeredComplaint, setRegisteredComplaint] = useState<{
    id?: number;
    number: string;
    department?: string;
    smsSent?: boolean;
  } | null>(null);

  // References
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);
  const recognitionRef = useRef<any>(null);
  const transcriptRef = useRef<string>('');
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  // Auto-scroll chat
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessing, isAiSpeaking, liveTranscript]);

  // Call duration timer
  useEffect(() => {
    if (callActive) {
      timerRef.current = window.setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setCallDuration(0);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [callActive]);

  // Format seconds into MM:SS
  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // High Quality Text-to-Speech (TTS) with server audio and browser fallback
  const speakText = (text: string, lang = 'Tanglish', onFinish?: () => void) => {
    if (ttsMuted) {
      if (onFinish) onFinish();
      return;
    }

    const langCode = lang.toLowerCase().includes('ta') || lang === 'Tamil' ? 'ta' : 'en';

    // 1. Try server-side crystal clear TTS audio stream
    try {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.src = '';
      }

      const ttsUrl = `/api/v1/new-ivr/tts?text=${encodeURIComponent(text)}&lang=${langCode}`;
      const audio = new Audio(ttsUrl);
      audioPlayerRef.current = audio;

      setIsAiSpeaking(true);
      setIvrState('AI_SPEAKING');

      audio.onended = () => {
        setIsAiSpeaking(false);
        setIvrState('WAITING_FOR_CITIZEN');
        if (onFinish) onFinish();
      };

      audio.onerror = () => {
        // Fallback to browser Web Speech API
        playBrowserSpeechFallback(text, lang, onFinish);
      };

      audio.play().catch(() => {
        // Fallback to browser Web Speech API if autoplay restricted
        playBrowserSpeechFallback(text, lang, onFinish);
      });
      return;
    } catch (e) {
      playBrowserSpeechFallback(text, lang, onFinish);
    }
  };

  const playBrowserSpeechFallback = (text: string, lang: string, onFinish?: () => void) => {
    if (!window.speechSynthesis) {
      setIsAiSpeaking(false);
      setIvrState('WAITING_FOR_CITIZEN');
      if (onFinish) onFinish();
      return;
    }

    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);

      const voices = window.speechSynthesis.getVoices();
      const tamilVoice = voices.find((v) => v.lang.includes('ta') || v.name.toLowerCase().includes('tamil'));
      const indianEnglishVoice = voices.find((v) => v.lang.includes('en-IN') || v.name.toLowerCase().includes('india'));
      const englishVoice = voices.find((v) => v.lang.startsWith('en'));

      if (lang === 'Tamil' && tamilVoice) {
        utterance.voice = tamilVoice;
        utterance.lang = 'ta-IN';
      } else if (indianEnglishVoice) {
        utterance.voice = indianEnglishVoice;
        utterance.lang = 'en-IN';
      } else if (englishVoice) {
        utterance.voice = englishVoice;
        utterance.lang = 'en-US';
      }

      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      setIsAiSpeaking(true);
      setIvrState('AI_SPEAKING');

      utterance.onend = () => {
        setIsAiSpeaking(false);
        setIvrState('WAITING_FOR_CITIZEN');
        if (onFinish) onFinish();
      };

      utterance.onerror = () => {
        setIsAiSpeaking(false);
        setIvrState('WAITING_FOR_CITIZEN');
        if (onFinish) onFinish();
      };

      window.speechSynthesis.speak(utterance);
    } catch (e) {
      setIsAiSpeaking(false);
      setIvrState('WAITING_FOR_CITIZEN');
      if (onFinish) onFinish();
    }
  };

  // Language Selection Preference (Default: Tamil)
  const [selectedLanguage, setSelectedLanguage] = useState<string>('Tamil');

  // Start Call Flow
  const handleStartCall = async (langChoice?: string) => {
    try {
      setErrorCode(null);
      setErrorMessage(null);
      setIsProcessing(true);
      setRegisteredComplaint(null);
      setLiveTranscript('');
      transcriptRef.current = '';
      setQuestionCount(0);

      const chosenLang = langChoice || selectedLanguage || 'Tamil';
      const res = await newIvrApi.createSession('+919843098765', chosenLang);
      setSessionId(res.session_id);
      setCallActive(true);
      setIvrState('WAITING_FOR_CITIZEN');
      setDetectedLanguage(res.language || chosenLang);
      setMemory(res.structured_memory);

      const systemMsg: NewIVRMessage = {
        id: 1,
        role: 'system',
        content: `📞 Call Connected. Language: ${chosenLang}. Citizen speaks first — please describe your civic issue in Tamil, Tanglish, or English.`,
        language: chosenLang,
        created_at: new Date().toISOString(),
      };
      setMessages([systemMsg]);
      setIsProcessing(false);

      // Microphone activates for citizen to speak
      setTimeout(() => {
        startRecording(chosenLang);
      }, 300);
    } catch (err: any) {
      setIsProcessing(false);
      setErrorCode('BACKEND_UNAVAILABLE');
      setErrorMessage(err.message || 'Failed to connect to IVR server.');
    }
  };

  // End Call Flow
  const handleEndCall = async () => {
    stopRecording();
    window.speechSynthesis?.cancel();
    setIsAiSpeaking(false);

    if (sessionId) {
      try {
        await newIvrApi.endSession(sessionId);
      } catch (err) {
        // ignore
      }
    }
    setCallActive(false);
    setIvrState('COMPLETED');
  };

  // Microphone Recording with Web Speech Recognition
  const startRecording = async (overrideLang?: string) => {
    if (isRecording || isAiSpeaking) return;

    try {
      setErrorCode(null);
      setErrorMessage(null);
      transcriptRef.current = '';
      setLiveTranscript('');

      const activeLang = overrideLang || detectedLanguage || selectedLanguage || 'Tamil';

      // Initialize Web Speech Recognition
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        try {
          const recognition = new SpeechRecognition();
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = activeLang === 'English' ? 'en-IN' : 'ta-IN';
          recognition.onresult = (e: any) => {
            let current = '';
            for (let i = 0; i < e.results.length; i++) {
              current += e.results[i][0].transcript + ' ';
            }
            const trimmed = current.trim();
            transcriptRef.current = trimmed;
            setLiveTranscript(trimmed);
          };
          recognition.onerror = (e: any) => {
            console.debug('Speech recognition error/warning:', e);
          };
          recognition.start();
          recognitionRef.current = recognition;
        } catch (e) {
          console.debug('Speech recognition start failed:', e);
        }
      }

      // Supported mime type
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
        ? 'audio/ogg;codecs=opus'
        : 'audio/webm';

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        const capturedTranscript = transcriptRef.current;
        setLiveTranscript('');
        if (audioBlob.size > 100 || capturedTranscript) {
          submitAudio(audioBlob, capturedTranscript || undefined);
        }
      };

      mediaRecorder.start(250);
      mediaRecorderRef.current = mediaRecorder;
      setIsRecording(true);
      setIvrState('RECORDING');
    } catch (err: any) {
      setIsRecording(false);
      setErrorCode('MICROPHONE_DENIED');
      setErrorMessage('Microphone access was denied or unsupported. You can also use the text input below to interact.');
    }
  };

  const stopRecording = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  // Submit recorded audio to backend
  const submitAudio = async (audioBlob: Blob, transcriptionHint?: string) => {
    if (!sessionId) return;

    setIsProcessing(true);
    setIvrState('TRANSCRIBING');

    try {
      const res = await newIvrApi.sendAudio(sessionId, audioBlob, transcriptionHint);
      setIsProcessing(false);

      if (!res.success && res.error_code) {
        setErrorCode(res.error_code);
        setErrorMessage(res.message || 'Audio processing encountered an issue.');
        return;
      }

      // Add citizen spoken utterance to UI transcript
      const citizenSpeech = res.transcription || transcriptionHint || 'Voice Utterance';
      const userMsg: NewIVRMessage = {
        id: Date.now(),
        role: 'citizen',
        content: citizenSpeech,
        language: res.detected_language || detectedLanguage,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      handleTurnResponse(res);
    } catch (err: any) {
      setIsProcessing(false);
      setErrorCode('TRANSCRIPTION_FAILED');
      setErrorMessage(err.message || 'Speech recognition failed. Please try text response.');
    }
  };

  // Submit typed text
  const handleSendText = async (e?: React.FormEvent, directText?: string) => {
    if (e) e.preventDefault();
    const userText = (directText || textInput).trim();
    if (!userText || !sessionId || isProcessing) return;

    setTextInput('');
    setIsProcessing(true);
    setIvrState('UNDERSTANDING');

    // Add citizen message to UI immediately
    const userMsg: NewIVRMessage = {
      id: Date.now(),
      role: 'citizen',
      content: userText,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await newIvrApi.sendMessage(sessionId, userText);
      setIsProcessing(false);
      handleTurnResponse(res);
    } catch (err: any) {
      setIsProcessing(false);
      setErrorCode('TRANSCRIPTION_FAILED');
      setErrorMessage(err.message || 'Failed to submit response.');
    }
  };

  // Handle Turn Response from Backend
  const handleTurnResponse = (res: any) => {
    if (res.detected_language) {
      setDetectedLanguage(res.detected_language);
    }
    if (res.memory) {
      setMemory(res.memory);
    }
    if (res.state) {
      setIvrState(res.state);
    }
    if (res.question_count !== undefined) {
      setQuestionCount(res.question_count);
    }
    if (res.max_questions !== undefined) {
      setMaxQuestions(res.max_questions);
    }

    // Append AI Response
    if (res.ai_reply) {
      const aiMsg: NewIVRMessage = {
        id: Date.now() + 1,
        role: 'ai',
        content: res.ai_reply,
        normalized_content: res.spoken_reply,
        language: res.detected_language,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, aiMsg]);

      // Speak response
      speakText(res.spoken_reply || res.ai_reply, res.detected_language || 'Tanglish', () => {
        // If call is still active and not completed, turn on mic for next turn
        if (res.state !== 'COMPLETED') {
          startRecording();
        }
      });
    }

    // Check if complaint was registered
    if (res.complaint_created && res.complaint_number) {
      setRegisteredComplaint({
        id: res.complaint_id,
        number: res.complaint_number,
        department: res.department,
        smsSent: res.sms_sent,
      });
    }
  };

  // Confirm / Cancel handlers
  const handleConfirm = async () => {
    if (!sessionId) return;
    setIsProcessing(true);
    setIvrState('REGISTERING_COMPLAINT');
    try {
      const res = await newIvrApi.confirmComplaint(sessionId);
      setIsProcessing(false);
      handleTurnResponse(res);
    } catch (err: any) {
      setIsProcessing(false);
      setErrorCode('REGISTRATION_FAILED');
      setErrorMessage(err.message || 'Failed to confirm complaint.');
    }
  };

  const handleCancel = async () => {
    if (!sessionId) return;
    setIsProcessing(true);
    try {
      const res = await newIvrApi.cancelConfirmation(sessionId);
      setIsProcessing(false);
      handleTurnResponse(res);
    } catch (err: any) {
      setIsProcessing(false);
    }
  };

  return (
    <div className="page-container" style={{ maxWidth: '1100px', margin: '0 auto', padding: '1.5rem 1rem' }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: '#eff6ff', color: '#1d4ed8', padding: '0.35rem 0.85rem', borderRadius: '9999px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem' }}>
          <Sparkles size={16} /> Two-Way Multilingual AI Citizen Grievance IVR
        </div>
        <h1 style={{ fontSize: '2rem', fontWeight: 800, color: '#0f172a', margin: '0 0 0.5rem 0' }}>
          VoxentraAI Live AI Voice Grievance Redressal
        </h1>
        <p style={{ color: '#64748b', fontSize: '0.95rem', maxWidth: '650px', margin: '0 auto' }}>
          Speak naturally in <strong>Tamil, English, or Tanglish</strong>. The AI listens, understands your problem, asks relevant follow-up questions one by one, and registers your complaint.
        </p>
      </div>

      {/* Error Alert */}
      {errorCode && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.75rem', padding: '1rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'flex-start', gap: '0.75rem', color: '#991b1b' }}>
          <AlertCircle size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>Error Code: {errorCode}</div>
            <div style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>{errorMessage}</div>
          </div>
        </div>
      )}

      {/* Language Preference Control Bar */}
      <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '0.85rem', padding: '0.75rem 1.25rem', marginBottom: '1.25rem', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Languages size={18} style={{ color: '#2563eb' }} />
          <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1e293b' }}>Select AI Voice Language:</span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
          {[
            { id: 'Tamil', label: '🇮🇳 தமிழ் (Tamil - Recommended)', sub: 'Primary Tamil Nadu Helpline Voice' },
            { id: 'Tanglish', label: '🗣️ Tanglish (Tamil + English)', sub: 'Tamil in English text' },
            { id: 'English', label: '🌐 English', sub: 'Standard English' },
            { id: 'Auto', label: '✨ Auto Detect', sub: 'Adaptive' },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setSelectedLanguage(item.id);
                setDetectedLanguage(item.id);
              }}
              style={{
                padding: '0.35rem 0.75rem',
                borderRadius: '0.55rem',
                fontSize: '0.8rem',
                fontWeight: 600,
                border: selectedLanguage === item.id ? '2px solid #2563eb' : '1px solid #cbd5e1',
                background: selectedLanguage === item.id ? '#eff6ff' : '#f8fafc',
                color: selectedLanguage === item.id ? '#1d4ed8' : '#475569',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid: Call Console & Memory Card */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)', gap: '1.5rem' }}>
        {/* Left Column: Live Call Interface */}
        <div style={{ background: '#ffffff', borderRadius: '1rem', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column', height: '650px', overflow: 'hidden' }}>
          {/* Call Header Bar */}
          <div style={{ background: '#0f172a', color: '#ffffff', padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: callActive ? '#22c55e' : '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffffff' }}>
                <Phone size={20} />
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: '1rem' }}>Toll-Free Helpline 1800-425-VOX</div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span>State: {ivrState}</span>
                  {callActive && (
                    <>
                      <span>•</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', color: '#4ade80' }}>
                        <Clock size={12} /> {formatTime(callDuration)}
                      </span>
                    </>
                  )}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {callActive && questionCount > 0 && (
                <div style={{ background: '#2563eb', padding: '0.25rem 0.6rem', borderRadius: '0.5rem', fontSize: '0.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#ffffff' }}>
                  <HelpCircle size={13} /> Q {questionCount}/{maxQuestions}
                </div>
              )}
              <div style={{ background: '#1e293b', padding: '0.25rem 0.6rem', borderRadius: '0.5rem', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#38bdf8' }}>
                <Languages size={14} /> {detectedLanguage}
              </div>
              <button
                onClick={() => setTtsMuted(!ttsMuted)}
                title={ttsMuted ? 'Unmute AI Voice' : 'Mute AI Voice'}
                style={{ background: '#1e293b', border: 'none', color: '#ffffff', width: '34px', height: '34px', borderRadius: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
              >
                {ttsMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
              </button>
            </div>
          </div>

          {/* Conversation Transcript Feed */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem', background: '#f8fafc' }}>
            {!callActive && messages.length === 0 && (
              <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748b' }}>
                <Phone size={48} style={{ margin: '0 auto 1rem', color: '#94a3b8', opacity: 0.5 }} />
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#334155', marginBottom: '0.5rem' }}>Helpline is Ready</h3>
                <p style={{ fontSize: '0.875rem', maxWidth: '380px', margin: '0 auto' }}>
                  Click <strong>Start AI Voice Call</strong> to talk to VoxentraAI in Tamil, English, or Tanglish.
                </p>
              </div>
            )}

            {messages.map((msg, idx) => {
              const isAi = msg.role === 'ai';
              return (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    flexDirection: isAi ? 'row' : 'row-reverse',
                    alignItems: 'flex-start',
                    gap: '0.65rem',
                  }}
                >
                  <div
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '50%',
                      background: isAi ? '#2563eb' : '#059669',
                      color: '#ffffff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      flexShrink: 0,
                    }}
                  >
                    {isAi ? 'AI' : 'You'}
                  </div>
                  <div
                    style={{
                      maxWidth: '75%',
                      background: isAi ? '#ffffff' : '#059669',
                      color: isAi ? '#0f172a' : '#ffffff',
                      padding: '0.75rem 1rem',
                      borderRadius: '0.85rem',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                      border: isAi ? '1px solid #e2e8f0' : 'none',
                      fontSize: '0.9rem',
                      lineHeight: '1.45',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {msg.content}
                  </div>
                </div>
              );
            })}

            {isProcessing && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#64748b', fontSize: '0.85rem' }}>
                <RefreshCw size={16} className="animate-spin" />
                <span>AI is listening and processing...</span>
              </div>
            )}

            {isAiSpeaking && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#2563eb', fontSize: '0.85rem' }}>
                <Volume2 size={16} className="animate-pulse" />
                <span>AI is speaking... (Microphone is muted)</span>
              </div>
            )}

            <div ref={chatBottomRef} />
          </div>

          {/* Interactive Call Controls Bar */}
          <div style={{ padding: '1rem', background: '#ffffff', borderTop: '1px solid #e2e8f0' }}>
            {!callActive ? (
              <button
                onClick={() => handleStartCall()}
                style={{
                  width: '100%',
                  padding: '0.85rem',
                  background: '#2563eb',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '0.75rem',
                  fontWeight: 700,
                  fontSize: '1rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.65rem',
                  boxShadow: '0 4px 6px -1px rgba(37,99,235,0.2)',
                }}
              >
                <Phone size={20} /> Start AI Voice Call
              </button>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {/* Live Speech Recognition Indicator */}
                {isRecording && (
                  <div style={{ background: '#fef3c7', border: '1px dashed #f59e0b', borderRadius: '0.65rem', padding: '0.5rem 0.75rem', color: '#92400e', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Mic size={16} className="animate-pulse" style={{ color: '#dc2626' }} />
                    <span style={{ fontWeight: 600 }}>{liveTranscript ? `Hearing: "${liveTranscript}"` : 'Listening to your microphone... Speak your complaint now.'}</span>
                  </div>
                )}

                {/* Voice Action Row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                  {isRecording ? (
                    <button
                      onClick={stopRecording}
                      style={{
                        flex: 1,
                        padding: '0.75rem',
                        background: '#dc2626',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '0.65rem',
                        fontWeight: 700,
                        fontSize: '0.9rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '0.5rem',
                        animation: 'pulse 1.5s infinite',
                      }}
                    >
                      <MicOff size={18} /> Stop Speaking & Send
                    </button>
                  ) : (
                    <button
                      onClick={() => startRecording()}
                      disabled={isAiSpeaking || isProcessing}
                      style={{
                        flex: 1,
                        padding: '0.75rem',
                        background: isAiSpeaking ? '#94a3b8' : '#059669',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '0.65rem',
                        fontWeight: 700,
                        fontSize: '0.9rem',
                        cursor: isAiSpeaking ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '0.5rem',
                      }}
                    >
                      <Mic size={18} /> {isAiSpeaking ? 'Waiting for AI...' : 'Speak Now'}
                    </button>
                  )}

                  <button
                    onClick={handleEndCall}
                    title="End Call"
                    style={{
                      padding: '0.75rem 1.25rem',
                      background: '#fee2e2',
                      color: '#dc2626',
                      border: '1px solid #fca5a5',
                      borderRadius: '0.65rem',
                      fontWeight: 700,
                      fontSize: '0.9rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                    }}
                  >
                    <PhoneOff size={18} /> End
                  </button>
                </div>

                {/* Quick Simulation Chips */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', marginRight: '0.2rem' }}>Quick test:</span>
                  {[
                    { label: '💧 குடிநீர் வரவில்லை', text: 'எங்கள் தெருவில் 3 நாட்களாக குடிநீர் விநியோகம் இல்லை, அண்ணா நகர்' },
                    { label: '💡 Streetlight Issue', text: 'Street lights are not working on 5th cross street' },
                    { label: '🗑️ குப்பை தேக்கம்', text: 'குப்பை அள்ளப்படாமல் ரோட்டில் தேங்கியுள்ளது' },
                    { label: '✅ உறுதி செய்க (Confirm)', text: 'ஆம், என் புகாரை பதிவு செய்யுங்கள்' }
                  ].map((item, i) => (
                    <button
                      key={i}
                      type="button"
                      disabled={isProcessing}
                      onClick={() => handleSendText(undefined, item.text)}
                      style={{
                        background: '#f8fafc',
                        border: '1px solid #cbd5e1',
                        borderRadius: '9999px',
                        padding: '0.2rem 0.55rem',
                        fontSize: '0.72rem',
                        color: '#334155',
                        cursor: isProcessing ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>

                {/* Text Fallback Row */}
                <form onSubmit={(e) => handleSendText(e)} style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    type="text"
                    value={textInput}
                    onChange={(e) => setTextInput(e.target.value)}
                    placeholder="Or type your response here in Tamil/English/Tanglish..."
                    disabled={isProcessing}
                    style={{
                      flex: 1,
                      padding: '0.65rem 0.85rem',
                      border: '1px solid #cbd5e1',
                      borderRadius: '0.5rem',
                      fontSize: '0.875rem',
                      outline: 'none',
                    }}
                  />
                  <button
                    type="submit"
                    disabled={!textInput.trim() || isProcessing}
                    style={{
                      padding: '0.65rem 1rem',
                      background: '#0f172a',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '0.5rem',
                      cursor: !textInput.trim() || isProcessing ? 'not-allowed' : 'pointer',
                      opacity: !textInput.trim() || isProcessing ? 0.6 : 1,
                    }}
                  >
                    <Send size={16} />
                  </button>
                </form>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Live Memory & Complaint Details Card */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Registration Success Receipt Card */}
          {registeredComplaint && (
            <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '1rem', padding: '1.25rem', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', color: '#15803d', fontWeight: 800, fontSize: '1.1rem', marginBottom: '0.5rem' }}>
                <CheckCircle2 size={24} /> Complaint Successfully Registered!
              </div>
              <p style={{ fontSize: '0.85rem', color: '#166534', margin: '0 0 1rem 0' }}>
                Your grievance has been stored in the official state portal and routed to the designated engineering squad.
              </p>
              <div style={{ background: '#ffffff', padding: '0.85rem', borderRadius: '0.65rem', border: '1px solid #bbf7d0', marginBottom: '0.75rem' }}>
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>Official Complaint ID</div>
                <div style={{ fontSize: '1.35rem', fontWeight: 900, color: '#1e293b', letterSpacing: '0.5px' }}>
                  {registeredComplaint.number}
                </div>
              </div>
              <div style={{ fontSize: '0.85rem', color: '#334155' }}>
                <strong>Department:</strong> {registeredComplaint.department || 'Municipal Administration'}
              </div>
              {registeredComplaint.smsSent && (
                <div style={{ fontSize: '0.8rem', color: '#047857', marginTop: '0.35rem' }}>
                  ✓ SMS confirmation sent via Twilio to your phone number.
                </div>
              )}
            </div>
          )}

          {/* Structured Conversation Memory Card */}
          <div style={{ background: '#ffffff', borderRadius: '1rem', border: '1px solid #e2e8f0', padding: '1.25rem', boxShadow: '0 2px 4px rgba(0,0,0,0.04)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid #f1f5f9', paddingBottom: '0.75rem' }}>
              <div style={{ fontWeight: 800, fontSize: '1rem', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <FileText size={18} color="#2563eb" /> AI Memory & Slots
              </div>
              <span style={{ fontSize: '0.75rem', color: '#64748b', background: '#f8fafc', padding: '0.2rem 0.5rem', borderRadius: '0.25rem' }}>
                Turn-by-turn
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.875rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed #e2e8f0', paddingBottom: '0.5rem' }}>
                <span style={{ color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <HelpCircle size={14} /> Category:
                </span>
                <span style={{ fontWeight: 600, color: memory.category ? '#0f172a' : '#94a3b8' }}>
                  {memory.category || 'Extracting...'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed #e2e8f0', paddingBottom: '0.5rem' }}>
                <span style={{ color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <Building size={14} /> Department:
                </span>
                <span style={{ fontWeight: 600, color: memory.department ? '#0f172a' : '#94a3b8' }}>
                  {memory.department || 'Auto-routing...'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed #e2e8f0', paddingBottom: '0.5rem' }}>
                <span style={{ color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <MapPin size={14} /> Location:
                </span>
                <span style={{ fontWeight: 600, color: memory.location ? '#0f172a' : '#94a3b8' }}>
                  {memory.location || 'Awaiting slot...'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed #e2e8f0', paddingBottom: '0.5rem' }}>
                <span style={{ color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <Clock size={14} /> Duration:
                </span>
                <span style={{ fontWeight: 600, color: memory.duration ? '#0f172a' : '#94a3b8' }}>
                  {memory.duration || 'Awaiting slot...'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed #e2e8f0', paddingBottom: '0.5rem' }}>
                <span style={{ color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <ShieldAlert size={14} /> Affected Scope:
                </span>
                <span style={{ fontWeight: 600, color: memory.affected_scope ? '#0f172a' : '#94a3b8' }}>
                  {memory.affected_scope || 'Awaiting slot...'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '0.25rem' }}>
                <span style={{ color: '#64748b' }}>Priority:</span>
                <span
                  style={{
                    fontWeight: 700,
                    padding: '0.15rem 0.5rem',
                    borderRadius: '0.35rem',
                    fontSize: '0.75rem',
                    background: memory.priority === 'CRITICAL' ? '#fee2e2' : memory.priority === 'HIGH' ? '#ffedd5' : '#f0fdf4',
                    color: memory.priority === 'CRITICAL' ? '#b91c1c' : memory.priority === 'HIGH' ? '#c2410c' : '#15803d',
                  }}
                >
                  {memory.priority || 'MEDIUM'}
                </span>
              </div>
            </div>

            {/* Quick Confirmation Actions when AI prompts confirmation */}
            {ivrState === 'CONFIRMATION' && (
              <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid #e2e8f0', display: 'flex', gap: '0.5rem' }}>
                <button
                  onClick={handleConfirm}
                  disabled={isProcessing}
                  style={{
                    flex: 1,
                    padding: '0.65rem',
                    background: '#059669',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '0.5rem',
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                  }}
                >
                  ✓ Confirm & Register
                </button>
                <button
                  onClick={handleCancel}
                  disabled={isProcessing}
                  style={{
                    flex: 1,
                    padding: '0.65rem',
                    background: '#f1f5f9',
                    color: '#475569',
                    border: '1px solid #cbd5e1',
                    borderRadius: '0.5rem',
                    fontWeight: 600,
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                  }}
                >
                  Edit Information
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
