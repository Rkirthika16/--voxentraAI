import React, { useState, useEffect, useRef } from 'react';
import { ivrApi } from '../api/ivr';
import { IVRProcessSpeechResponse } from '../types';
import { speech } from '../utils/speech';
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
  ArrowRight,
  Sparkles,
  Radio,
  Flame,
  Globe,
  RotateCcw,
  Check,
  Headphones
} from 'lucide-react';

interface ChatMessage {
  id: string;
  sender: 'ai' | 'citizen';
  text: string;
  language: string;
  time: string;
}

export const TollFreeHelplinePage: React.FC = () => {
  // Call States: 'IDLE' -> 'CALLING' -> 'CONNECTED' -> 'RECORDING' -> 'PROCESSING' -> 'DONE'
  const [callState, setCallState] = useState<'IDLE' | 'CALLING' | 'CONNECTED' | 'RECORDING' | 'PROCESSING' | 'DONE'>('IDLE');
  const [language, setLanguage] = useState<'ta' | 'en' | 'hi'>('ta');
  const [callerPhone, setCallerPhone] = useState('+91 98430 98765');
  const tollFreeNumber = '1913';

  // Voice Interaction State
  const [isRecording, setIsRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [spokenText, setSpokenText] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [result, setResult] = useState<IVRProcessSpeechResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isAiSpeaking, setIsAiSpeaking] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<any>(null);
  const recognitionRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, callState]);

  useEffect(() => {
    return () => {
      speech.stop();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Speak AI Audio Response with reliable volume & fallback
  const playVoice = (text: string, lang: string) => {
    speech.stop();
    setIsAiSpeaking(true);
    speech.speak(text, {
      language: lang,
      volume: 1.0,
      rate: 0.94,
      onStart: () => setIsAiSpeaking(true),
      onEnd: () => setIsAiSpeaking(false),
      onError: () => setIsAiSpeaking(false)
    });
  };

  // 1. INITIATE TOLL-FREE CALL
  const handleStartCall = async () => {
    speech.unlock();
    setError(null);
    setCallState('CALLING');
    setResult(null);
    setMessages([]);
    setSpokenText('');
    setIsAiSpeaking(false);

    // Play phone ringtone
    speech.playRingTone(2.0);

    try {
      const initData = await ivrApi.initiateCall(callerPhone, tollFreeNumber);

      setTimeout(() => {
        speech.stopRingTone();
        speech.playConnectChime();
        setCallState('CONNECTED');

        // Greeting formulation based on citizen's language
        let greeting = initData.greeting_tamil + " " + initData.prompt_tamil;
        let langName = 'Tamil';

        if (language === 'hi') {
          greeting = "नमस्ते! वॉक्सेंट्रा तमिलनाडु सरकारी हेल्पलाइन में आपका स्वागत है. कृपया अपनी ग्राम पंचायत या नागरिक समस्या बताएं.";
          langName = 'Hindi';
        } else if (language === 'en') {
          greeting = initData.greeting_english + " " + initData.prompt_english;
          langName = 'English';
        }

        const aiMsg: ChatMessage = {
          id: `ai_${Date.now()}`,
          sender: 'ai',
          text: greeting,
          language: langName,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages([aiMsg]);

        // Speak greeting aloud immediately
        playVoice(greeting, langName);
      }, 1500);

    } catch (err: any) {
      speech.stopRingTone();
      setError('Could not connect to Toll-Free service. Please check network connection.');
      setCallState('IDLE');
    }
  };

  // 2. END CALL
  const handleEndCall = () => {
    speech.stop();
    speech.stopRingTone();
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) {}
    }
    if (timerRef.current) clearInterval(timerRef.current);
    setIsRecording(false);
    setIsAiSpeaking(false);
    setCallState('IDLE');
  };

  // 3. START CONTINUOUS SPEECH RECOGNITION
  const handleStartRecording = async () => {
    setError(null);
    speech.stop();
    setIsAiSpeaking(false);
    speech.playBeep();

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
          console.warn('Microphone stream optional notice:', mediaErr);
        }
      }

      setIsRecording(true);
      setCallState('RECORDING');
      setRecordSeconds(0);
      setSpokenText('');

      // Continuous Speech Recognition in Tamil / English
      if (speech.isSTTSupported()) {
        const sttLang = language === 'ta' ? 'ta-IN' : (language === 'hi' ? 'hi-IN' : 'en-IN');
        const rec = speech.createRecognition(
          sttLang as any,
          (transcript, isFinal) => {
            setSpokenText(transcript);
          },
          (err) => console.log('STT status:', err),
          () => {
            // Finished recognition turn
          }
        );
        if (rec) {
          recognitionRef.current = rec;
          try { rec.start(); } catch (e) {}
        }
      }

      timerRef.current = setInterval(() => {
        setRecordSeconds((s) => s + 1);
      }, 1000);
    } catch (err) {
      console.warn('Record start notice:', err);
    }
  };

  // 4. SUBMIT SPOKEN GRIEVANCE (AI AUTOMATICALLY CLASSIFIES DEPT & RESPONDS WITH VOICE)
  const handleSubmitSpokenProblem = async (customText?: string) => {
    speech.unlock();
    const textToProcess = (customText || spokenText).trim();
    if (!textToProcess) {
      setError('Please speak your grievance clearly into the microphone.');
      return;
    }

    setError(null);
    speech.stop();
    if (timerRef.current) clearInterval(timerRef.current);
    setIsRecording(false);

    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) {}
    }
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
    }

    // Add citizen's spoken message to conversation stream
    const citizenMsg: ChatMessage = {
      id: `cit_${Date.now()}`,
      sender: 'citizen',
      text: textToProcess,
      language: language,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages((prev) => [...prev, citizenMsg]);
    setCallState('PROCESSING');

    try {
      // Backend automatically extracts Department, Location, Priority, and registers Ticket
      const res = await ivrApi.processSpeech({
        caller_phone: callerPhone,
        speech_text: textToProcess,
        language_hint: language,
      });

      speech.playSuccessChime();
      setResult(res);
      setCallState('DONE');

      // AI Spoken Voice Response formulation
      let replyText = res.confirmation_spoken_tamil || `வணக்கம். உங்கள் ${res.category} புகார் எண் ${res.complaint_number} வெற்றிகரமாக பதிவு செய்யப்பட்டது. இது ${res.suggested_department} துறைக்கு அனுப்பப்பட்டுள்ளது.`;
      let spokenLang = 'Tamil';

      if (language === 'hi') {
        replyText = `धन्यवाद! आपकी ${res.category} शिकायत संख्या ${res.complaint_number} दर्ज हो चुकी है और ${res.suggested_department} विभाग को तुरंत भेज दी गई है. आपके मोबाइल पर एसएमएस भेजा गया है.`;
        spokenLang = 'Hindi';
      } else if (language === 'en' || (res.detected_language === 'English' && language !== 'ta')) {
        replyText = res.confirmation_spoken_english || `Thank you. Your ${res.category} grievance ${res.complaint_number} has been registered and forwarded to ${res.suggested_department}.`;
        spokenLang = 'English';
      }

      const aiReply: ChatMessage = {
        id: `ai_${Date.now()}`,
        sender: 'ai',
        text: replyText,
        language: spokenLang,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages((prev) => [...prev, aiReply]);

      // AI speaks out loud to the citizen
      playVoice(replyText, spokenLang);

    } catch (err: any) {
      setError('Failed to process spoken grievance. Please try again.');
      setCallState('CONNECTED');
    }
  };

  return (
    <div className="page-container animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem', maxWidth: '950px', margin: '0 auto' }}>
      
      {/* 1. Header & Language Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, #10b981, #059669)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              boxShadow: '0 0 20px rgba(16, 185, 129, 0.3)',
            }}
          >
            <PhoneCall size={24} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.75rem', marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              Toll-Free Civic Helpline (1913)
            </h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Tamil Nadu Citizen Grievance Portal • Automatic AI Department Routing & Voice Redressal
            </p>
          </div>
        </div>

        {/* Language Selection */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            background: 'var(--bg-input)',
            padding: '0.35rem 0.6rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-color)',
          }}
        >
          <Globe size={15} color="#38bdf8" />
          <button
            onClick={() => setLanguage('ta')}
            className={`btn btn-sm ${language === 'ta' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
          >
            தமிழ்
          </button>
          <button
            onClick={() => setLanguage('en')}
            className={`btn btn-sm ${language === 'en' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
          >
            English
          </button>
          <button
            onClick={() => setLanguage('hi')}
            className={`btn btn-sm ${language === 'hi' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
          >
            हिन्दी
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: '1rem 1.25rem',
            borderRadius: 'var(--radius-md)',
            background: 'var(--color-danger-bg)',
            border: '1px solid var(--color-danger)',
            color: '#fca5a5',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.9rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} style={{ background: 'none', border: 'none', color: '#ffffff', cursor: 'pointer', fontWeight: 600, fontSize: '0.8rem' }}>
            Dismiss
          </button>
        </div>
      )}

      {/* 2. Primary Call Connection Card */}
      <div
        className="glass-card"
        style={{
          padding: '2.5rem 2rem',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '1.5rem',
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.95))',
          border: '1px solid rgba(59, 130, 246, 0.25)',
        }}
      >
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 'var(--radius-full)', padding: '0.35rem 1rem', fontSize: '0.85rem', color: '#34d399', fontWeight: 700 }}>
          <Radio size={15} className={callState !== 'IDLE' ? 'animate-pulse' : ''} />
          <span>TOLL-FREE CIVIC HELPLINE • 1913</span>
        </div>

        <div>
          <div style={{ fontSize: 'clamp(2.5rem, 6vw, 4rem)', fontWeight: 800, fontFamily: 'var(--font-heading)', color: '#ffffff', letterSpacing: '-0.03em', lineHeight: 1 }}>
            1913
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginTop: '0.75rem', maxWidth: '600px' }}>
            Call from any basic mobile phone or click below. The AI answers, listens to your problem, automatically assigns the responsible Tamil Nadu department, and speaks your ticket ID back to you.
          </p>
        </div>

        {/* Action Button */}
        <div>
          {callState === 'IDLE' ? (
            <button
              onClick={handleStartCall}
              className="btn btn-primary btn-lg"
              style={{
                background: 'linear-gradient(135deg, #10b981, #059669)',
                boxShadow: '0 0 25px rgba(16, 185, 129, 0.4)',
                fontWeight: 700,
                fontSize: '1.15rem',
                padding: '0.9rem 2.5rem',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <PhoneCall size={22} />
              <span>Call 1913 Helpline</span>
            </button>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center' }}>
              <button
                onClick={handleEndCall}
                className="btn btn-danger btn-lg"
                style={{
                  fontWeight: 700,
                  fontSize: '1rem',
                  padding: '0.8rem 2rem',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <PhoneOff size={18} />
                <span>End Call</span>
              </button>
              <span style={{ fontSize: '0.85rem', color: '#34d399', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '0.6rem 1.2rem', borderRadius: 'var(--radius-md)', fontWeight: 600 }}>
                ● Call Connected (AI Audio Active)
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 3. Live AI Voice Dialogue & Grievance Recording */}
      {callState !== 'IDLE' && (
        <div className="glass-card animate-fade-in" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Headphones size={20} color="#38bdf8" />
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Government AI Voice Assistant</h3>
            </div>
            {isAiSpeaking && (
              <span style={{ background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.4)', color: '#38bdf8', padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-full)', fontSize: '0.75rem', fontWeight: 700 }} className="animate-pulse">
                🔊 AI Speaking Aloud...
              </span>
            )}
          </div>

          {/* Dialogue Message History */}
          <div
            style={{
              background: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-color)',
              padding: '1.25rem',
              minHeight: '220px',
              maxHeight: '340px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
            }}
          >
            {messages.map((msg) => (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: msg.sender === 'ai' ? 'flex-start' : 'flex-end',
                }}
              >
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: '0.25rem', fontWeight: 600 }}>
                  {msg.sender === 'ai' ? '🤖 Government AI Assistant' : '👤 Citizen (You)'} • {msg.time}
                </span>
                <div
                  style={{
                    padding: '0.9rem 1.25rem',
                    borderRadius: 'var(--radius-md)',
                    maxWidth: '85%',
                    fontSize: '0.95rem',
                    lineHeight: '1.6',
                    background: msg.sender === 'ai' ? 'rgba(59, 130, 246, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                    border: msg.sender === 'ai' ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid rgba(16, 185, 129, 0.3)',
                    color: '#ffffff',
                  }}
                >
                  <p>{msg.text}</p>
                  {msg.sender === 'ai' && (
                    <div style={{ marginTop: '0.6rem', display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => playVoice(msg.text, msg.language)}
                        className="btn btn-secondary btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}
                      >
                        <Volume2 size={13} /> Replay AI Voice
                      </button>
                      {isAiSpeaking && (
                        <button
                          onClick={() => { speech.stop(); setIsAiSpeaking(false); }}
                          className="btn btn-secondary btn-sm"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}
                        >
                          <VolumeX size={13} /> Stop
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick 1-Click Problem Test Pills for Instant Redressal */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Sparkles size={14} color="#38bdf8" /> Fast 1-Tap Civic Grievance Presets (Test Any Department Instantly):
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={() => { setSpokenText('திருவாரூர்ல ஸ்ட்ரீட் லைட் எரியல.'); handleSubmitSpokenProblem('திருவாரூர்ல ஸ்ட்ரீட் லைட் எரியல.'); }}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-full)', background: 'rgba(245, 158, 11, 0.15)', borderColor: 'rgba(245, 158, 11, 0.4)', color: '#fbbf24' }}
              >
                🏮 Thiruvarur Streetlight (திருவாரூர் ஸ்ட்ரீட் லைட்)
              </button>
              <button
                type="button"
                onClick={() => { setSpokenText('மதுரை பஞ்சாயத்து குடிநீர் பைப் உடைஞ்சு தண்ணி வீணாகுது.'); handleSubmitSpokenProblem('மதுரை பஞ்சாயத்து குடிநீர் பைப் உடைஞ்சு தண்ணி வீணாகுது.'); }}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-full)', background: 'rgba(56, 189, 248, 0.15)', borderColor: 'rgba(56, 189, 248, 0.4)', color: '#38bdf8' }}
              >
                💧 Madurai Water Leak (குடிநீர் பைப் உடைப்பு)
              </button>
              <button
                type="button"
                onClick={() => { setSpokenText('ஈரோடு கிராமத்துல கரண்ட் கட் ஆயிடுச்சு மின்சாரம் இல்ல.'); handleSubmitSpokenProblem('ஈரோடு கிராமத்துல கரண்ட் கட் ஆயிடுச்சு மின்சாரம் இல்ல.'); }}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-full)', background: 'rgba(234, 179, 8, 0.15)', borderColor: 'rgba(234, 179, 8, 0.4)', color: '#fef08a' }}
              >
                ⚡ Erode Power Cut (மின்வெட்டு கரண்ட் கட்)
              </button>
              <button
                type="button"
                onClick={() => { setSpokenText('சேலம் மெயின் ரோடு ரொம்ப பள்ளமா இருக்கு விபத்து நடக்குது.'); handleSubmitSpokenProblem('சேலம் மெயின் ரோடு ரொம்ப பள்ளமா இருக்கு விபத்து நடக்குது.'); }}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-full)', background: 'rgba(249, 115, 22, 0.15)', borderColor: 'rgba(249, 115, 22, 0.4)', color: '#fdba74' }}
              >
                🛣️ Salem Damaged Road (ரோடு பள்ளம்)
              </button>
              <button
                type="button"
                onClick={() => { setSpokenText('திருச்சி தெருவுல குப்பை அள்ளவில்லை ரொம்ப துர்நாற்றம்.'); handleSubmitSpokenProblem('திருச்சி தெருவுல குப்பை அள்ளவில்லை ரொம்ப துர்நாற்றம்.'); }}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-full)', background: 'rgba(16, 185, 129, 0.15)', borderColor: 'rgba(16, 185, 129, 0.4)', color: '#6ee7b7' }}
              >
                🗑️ Trichy Garbage (குப்பை அள்ளவில்லை)
              </button>
              <button
                type="button"
                onClick={() => { setSpokenText('வேலூர் சாக்கடை அடைத்து கழிவுநீர் தெருவில் தேங்கி உள்ளது.'); handleSubmitSpokenProblem('வேலூர் சாக்கடை அடைத்து கழிவுநீர் தெருவில் தேங்கி உள்ளது.'); }}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-full)', background: 'rgba(139, 92, 246, 0.15)', borderColor: 'rgba(139, 92, 246, 0.4)', color: '#c4b5fd' }}
              >
                🌊 Vellore Drainage (சாக்கடை அடைப்பு)
              </button>
            </div>
          </div>

          {/* Voice & Text Input Section */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              {isRecording ? (
                <button
                  type="button"
                  onClick={() => handleSubmitSpokenProblem()}
                  className="btn btn-warning"
                  style={{ flex: 1, padding: '0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '0.95rem' }}
                >
                  <MicOff size={18} /> Stop & Submit Voice Grievance ({recordSeconds}s)
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleStartRecording}
                  className="btn btn-primary"
                  style={{ flex: 1, padding: '0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '0.95rem' }}
                >
                  <Mic size={18} /> Tap to Speak Your Grievance (Microphone)
                </button>
              )}
            </div>

            {/* Editable Spoken Text Input */}
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="text"
                value={spokenText}
                onChange={(e) => setSpokenText(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSubmitSpokenProblem(); }}
                placeholder="Or type/edit your grievance here (e.g. திருவாரூர்ல ஸ்ட்ரீட் லைட் எரியல / Water pipe leak in Madurai)..."
                className="input-field"
                style={{ flex: 1, padding: '0.75rem 1rem', fontSize: '0.9rem' }}
              />
              <button
                type="button"
                onClick={() => handleSubmitSpokenProblem()}
                className="btn btn-primary"
                style={{ padding: '0.75rem 1.25rem', display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700 }}
              >
                <Send size={16} /> Submit
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. Automated Ticket Confirmation & Department Transfer Card */}
      {result && (
        <div
          className="glass-card animate-fade-in"
          style={{
            padding: '2rem',
            border: '2px solid rgba(16, 185, 129, 0.5)',
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(15, 23, 42, 0.95))',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ width: '44px', height: '44px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CheckCircle2 size={26} />
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#34d399', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Grievance Auto-Routed & Registered
                </span>
                <h2 style={{ fontSize: '1.85rem', fontFamily: 'monospace', fontWeight: 800 }}>
                  {result.complaint_number}
                </h2>
              </div>
            </div>

            <Link
              to={`/complaints/${result.complaint_id}`}
              className="btn btn-primary btn-sm"
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
            >
              <span>View Full Ticket Record</span>
              <ArrowRight size={14} />
            </Link>
          </div>

          <div className="grid-3">
            <div style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 700 }}>
                Automatically Assigned Department
              </span>
              <p style={{
                fontSize: '1rem',
                fontWeight: 800,
                color: result.suggested_department.includes('Lighting') ? '#fbbf24' : (result.suggested_department.includes('Water') ? '#38bdf8' : (result.suggested_department.includes('Electricity') ? '#fef08a' : (result.suggested_department.includes('Road') ? '#fdba74' : (result.suggested_department.includes('Sanitation') ? '#6ee7b7' : '#93c5fd')))),
                marginTop: '0.35rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}>
                <Building2 size={18} />
                {result.suggested_department}
              </p>
            </div>

            <div style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 700 }}>
                Extracted Village / Location
              </span>
              <p style={{ fontSize: '0.95rem', fontWeight: 700, color: '#34d399', marginTop: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <MapPin size={16} />
                {result.extracted_location || 'Tamil Nadu'}
              </p>
            </div>

            <div style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 700 }}>
                Assessed Priority
              </span>
              <p style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fbbf24', marginTop: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Flame size={16} />
                {result.priority}
              </p>
            </div>
          </div>

          {/* SMS Dispatch Receipt */}
          <div style={{ background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '1rem', borderRadius: 'var(--radius-md)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 600, color: '#93c5fd' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <MessageSquare size={15} />
                SMS Delivered to Caller ({result.caller_phone})
              </span>
              <span style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', padding: '0.15rem 0.5rem', borderRadius: 'var(--radius-full)', fontSize: '0.7rem' }}>
                SMS DELIVERED
              </span>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
              {result.sms_text}
            </p>
          </div>
        </div>
      )}

    </div>
  );
};
