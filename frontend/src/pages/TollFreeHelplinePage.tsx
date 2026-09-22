import React, { useState, useEffect, useRef } from 'react';
import { ivrApi } from '../api/ivr';
import { IVRProcessSpeechResponse } from '../types';
import { speech } from '../utils/speech';
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
  ArrowRight,
  Sparkles,
  Radio,
  Flame,
  Globe,
  RotateCcw,
  Check,
  Headphones,
  Compass,
  Navigation
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
  
  // Real-time Automatic Language Recognition State (No manual option needed)
  const [detectedLanguage, setDetectedLanguage] = useState<string>('Auto-Detecting...');
  const [languageConfidence, setLanguageConfidence] = useState<number>(0.98);

  const [callerPhone, setCallerPhone] = useState('+91 98430 98765');
  const tollFreeNumber = '1913';

  // Voice & Turn Interaction State
  const [isRecording, setIsRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [spokenText, setSpokenText] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isAiSpeaking, setIsAiSpeaking] = useState(false);
  const [dialogueTurn, setDialogueTurn] = useState(1);
  const [currentCallSid, setCurrentCallSid] = useState('');
  const [collectionFields, setCollectionFields] = useState<Record<string, any>>({});
  const [isConfirmationPending, setIsConfirmationPending] = useState(false);
  const [summaryText, setSummaryText] = useState('');

  // OpenStreetMap GIS Live Classification State
  const [currentLatitude, setCurrentLatitude] = useState<string | number | null>(null);
  const [currentLongitude, setCurrentLongitude] = useState<string | number | null>(null);
  const [osmLocationName, setOsmLocationName] = useState<string | null>(null);

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

  // 1. INITIATE ZERO-SELECTION TOLL-FREE CALL (Citizen speaks first)
  const handleStartCall = async () => {
    speech.unlock();
    setError(null);
    setCallState('CALLING');
    setResult(null);
    setMessages([]);
    setSpokenText('');
    setIsAiSpeaking(false);
    setDialogueTurn(1);
    setCollectionFields({});
    setIsConfirmationPending(false);
    setSummaryText('');
    setDetectedLanguage('Auto-Detecting...');
    setCurrentLatitude(null);
    setCurrentLongitude(null);
    setOsmLocationName(null);

    // Play phone ringtone
    speech.playRingTone(1.8);

    try {
      const initData = await ivrApi.initiateCall(callerPhone, tollFreeNumber);
      setCurrentCallSid(initData.call_sid);

      setTimeout(() => {
        speech.stopRingTone();
        speech.playConnectChime();
        setCallState('CONNECTED');

        // Universal bilingual IVR welcoming prompt
        const greeting = "வணக்கம். வாக்ஸென்ட்ரா தமிழ்நாடு அரசு குறைதீர்ப்பு சேவைக்கு நல்வரவு. Welcome to Voxentra Tamil Nadu Civic Helpline. Please state your grievance in Tamil, English, or Tanglish after the tone.";
        
        const aiMsg: ChatMessage = {
          id: `ai_${Date.now()}`,
          sender: 'ai',
          text: greeting,
          language: 'Tamil',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages([aiMsg]);

        // Speak greeting aloud
        playVoice(greeting, 'Tamil');

        // Automatically start recording so citizen can speak immediately
        setTimeout(() => {
          handleStartRecording();
        }, 3200);
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
      try { mediaRecorderRef.current.stop(); } catch (e) {}
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) {}
    }
    if (timerRef.current) clearInterval(timerRef.current);
    setIsRecording(false);
    setIsAiSpeaking(false);
    setCallState('IDLE');
  };

  // 3. START SPEECH RECOGNITION (Captures Tamil, Tanglish & English naturally)
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
          console.warn('Microphone stream notice:', mediaErr);
        }
      }

      setIsRecording(true);
      setCallState('RECORDING');
      setRecordSeconds(0);
      setSpokenText('');

      // Continuous Speech Recognition with auto-language capture
      if (speech.isSTTSupported()) {
        const rec = speech.createRecognition(
          'ta-IN' as any,
          (transcript) => {
            setSpokenText(transcript);
          },
          (err) => console.log('STT status:', err),
          () => {}
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

  // 4. SUBMIT SPOKEN GRIEVANCE TURN-BY-TURN (AI auto-detects language and classifies OSM location)
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
      try { mediaRecorderRef.current.stop(); } catch (e) {}
    }

    // Add citizen's spoken message to conversation stream
    const citizenMsg: ChatMessage = {
      id: `cit_${Date.now()}`,
      sender: 'citizen',
      text: textToProcess,
      language: detectedLanguage,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages((prev) => [...prev, citizenMsg]);
    setCallState('PROCESSING');

    try {
      const activeSid = currentCallSid || `CA_${Date.now()}`;

      // Zero-Selection Dialogue Turn (Auto-Language Detection + OpenStreetMap GIS Classification)
      const res = await ivrApi.dialogueTurn({
        call_sid: activeSid,
        caller_phone: callerPhone,
        dialogue_turn: dialogueTurn,
        user_speech: textToProcess,
        language_preference: 'Auto',
      });

      setDialogueTurn(res.dialogue_turn);
      
      // Update Auto-detected Language & Confidence
      if (res.detected_language) {
        setDetectedLanguage(res.detected_language);
      }
      if (res.language_confidence) {
        setLanguageConfidence(res.language_confidence);
      }

      // Update OpenStreetMap GIS Geocoordinates & Location Name
      if (res.latitude && res.longitude) {
        setCurrentLatitude(res.latitude);
        setCurrentLongitude(res.longitude);
      }
      if (res.osm_location_name) {
        setOsmLocationName(res.osm_location_name);
      }

      if (res.collection_state) {
        setCollectionFields(res.collection_state);
      }
      setIsConfirmationPending(Boolean(res.is_confirmation_pending));
      if (res.summary) {
        setSummaryText(res.summary);
      }

      if (res.is_completed) {
        speech.playSuccessChime();
        setResult({
          complaint_number: res.complaint_number || 'VOX-2026-0001',
          complaint_id: res.complaint_id || 1,
          category: res.extracted_category || 'General Civic',
          suggested_department: res.suggested_department || 'Municipal Administration',
          extracted_location: res.extracted_location || res.osm_location_name || 'Tamil Nadu',
          latitude: res.latitude || currentLatitude,
          longitude: res.longitude || currentLongitude,
          status: 'SUBMITTED',
          sms_text: `[Govt of TN / Voxentra] Grievance #${res.complaint_number} registered. Dept: ${res.suggested_department}. Status: Assigned to Field Officer.`
        });
        setCallState('DONE');
      } else {
        setCallState('CONNECTED');
      }

      const replyText = res.ai_spoken_reply;
      const spokenLang = res.detected_language || 'Tamil';

      const aiReply: ChatMessage = {
        id: `ai_${Date.now()}`,
        sender: 'ai',
        text: replyText,
        language: spokenLang,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages((prev) => [...prev, aiReply]);
      setSpokenText('');

      // AI speaks out loud to the citizen in their detected language
      playVoice(replyText, spokenLang);

    } catch (err: any) {
      setError('Failed to process spoken turn. Please try again.');
      setCallState('CONNECTED');
    }
  };

  return (
    <div className="page-container animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem', maxWidth: '980px', margin: '0 auto' }}>
      
      {/* 1. Header & Zero-Selection Auto-Recognition Indicator */}
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
              Tamil Nadu Citizen Grievance Portal • Zero-Selection Conversational Voice IVR & OpenStreetMap GIS
            </p>
          </div>
        </div>

        {/* Live Auto-Recognized Language Badge (No Manual Selection Required) */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            background: 'rgba(15, 23, 42, 0.8)',
            padding: '0.5rem 0.9rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid rgba(56, 189, 248, 0.3)',
          }}
        >
          <Globe size={16} color="#38bdf8" />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600 }}>
              RECOGNIZED LANGUAGE:
            </span>
            <span style={{ fontSize: '0.85rem', color: '#34d399', fontWeight: 700 }}>
              {detectedLanguage === 'Auto-Detecting...' ? '🌐 Auto-Detect (தமிழ் / Tanglish / English)' : `✓ ${detectedLanguage} (${Math.round(languageConfidence * 100)}%)`}
            </span>
          </div>
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
          <span>TOLL-FREE HELPLINE • 1913 • CITIZEN TALKS FIRST</span>
        </div>

        <div>
          <div style={{ fontSize: 'clamp(2.5rem, 6vw, 4rem)', fontWeight: 800, fontFamily: 'var(--font-heading)', color: '#ffffff', letterSpacing: '-0.03em', lineHeight: 1 }}>
            1913
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginTop: '0.75rem', maxWidth: '650px' }}>
            No language keypad options needed. Connect and speak your grievance in Tamil, Tanglish, or English. The AI listens, auto-identifies your dialect, accurately pinpoints your street on OpenStreetMap, and dispatches to the department.
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
              <span>Call 1913 Helpline (Speak Grievance)</span>
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
                ● Call Live • Turn {dialogueTurn} (AI Listening & Responding)
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 3. Live AI Voice Dialogue, Street Map GIS & Grievance Recording */}
      {callState !== 'IDLE' && (
        <div className="glass-card animate-fade-in" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Headphones size={20} color="#38bdf8" />
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Government AI Voice Assistant (Tamil Nadu)</h3>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.4)', color: '#34d399', padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-full)', fontSize: '0.75rem', fontWeight: 700 }}>
                🌐 Detected: {detectedLanguage}
              </span>
              {isAiSpeaking && (
                <span style={{ background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.4)', color: '#38bdf8', padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-full)', fontSize: '0.75rem', fontWeight: 700 }} className="animate-pulse">
                  🔊 AI Speaking Aloud...
                </span>
              )}
            </div>
          </div>

          {/* 10-Point Intake HUD Indicator */}
          {Object.keys(collectionFields).length > 0 && (
            <div style={{ background: 'rgba(15, 23, 42, 0.7)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: 'var(--radius-md)', padding: '0.85rem 1.2rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Sparkles size={14} /> 10-Point Grievance Intake Progress:
                </span>
                <span style={{ fontSize: '0.75rem', color: '#34d399', fontWeight: 700 }}>
                  {Object.values(collectionFields).filter(v => v && String(v).trim()).length}/10 Details Collected
                </span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                {[
                  { k: 'problem_description', label: 'Problem' },
                  { k: 'district_area', label: 'District/Area' },
                  { k: 'street_road_name', label: 'Street/Road' },
                  { k: 'landmark', label: 'Landmark' },
                  { k: 'exact_location', label: 'Exact Spot' },
                  { k: 'date_and_time', label: 'Time' },
                  { k: 'frequency', label: 'Frequency' },
                  { k: 'current_status', label: 'Status' },
                  { k: 'additional_details', label: 'Hazards' },
                  { k: 'citizen_details', label: 'Citizen Phone' }
                ].map(item => {
                  const val = collectionFields[item.k];
                  const isFilled = val && String(val).trim();
                  return (
                    <span
                      key={item.k}
                      style={{
                        fontSize: '0.7rem',
                        padding: '0.2rem 0.5rem',
                        borderRadius: 'var(--radius-sm)',
                        background: isFilled ? 'rgba(16, 185, 129, 0.2)' : 'rgba(100, 116, 139, 0.2)',
                        border: isFilled ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(100, 116, 139, 0.3)',
                        color: isFilled ? '#34d399' : '#94a3b8',
                        fontWeight: 600
                      }}
                    >
                      {isFilled ? '✓' : '○'} {item.label}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* OpenStreetMap GIS Location Classifier Widget */}
          <IVRStreetMap
            latitude={currentLatitude || collectionFields['latitude']}
            longitude={currentLongitude || collectionFields['longitude']}
            locationName={osmLocationName || collectionFields['district_area']}
            districtArea={collectionFields['district_area']}
            streetName={collectionFields['street_road_name']}
            landmark={collectionFields['landmark']}
            exactLocation={collectionFields['exact_location']}
            category={collectionFields['problem_description']}
            height="260px"
          />

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
                  <p style={{ whiteSpace: 'pre-line' }}>{msg.text}</p>
                  {msg.sender === 'ai' && (
                    <div style={{ marginTop: '0.6rem', display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => playVoice(msg.text, msg.language)}
                        className="btn btn-secondary btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}
                      >
                        <Volume2 size={13} /> Replay Voice
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

          {/* Confirmation Action Card if pending confirmation */}
          {isConfirmationPending && callState !== 'DONE' && (
            <div style={{ background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(5, 150, 105, 0.25))', border: '1px solid rgba(16, 185, 129, 0.4)', padding: '1.25rem', borderRadius: 'var(--radius-md)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#34d399', fontWeight: 700 }}>
                <CheckCircle2 size={18} />
                <span>All 10 Details Gathered & Location Pinpointed • Confirm with AI:</span>
              </div>
              <p style={{ fontSize: '0.85rem', color: '#e2e8f0', margin: 0 }}>
                Shall we register this grievance and forward it to the department now?
              </p>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => handleSubmitSpokenProblem('Yes, confirm and register this complaint now')}
                  className="btn btn-primary btn-sm"
                  style={{ background: '#10b981', borderColor: '#059669', fontWeight: 700 }}
                >
                  <Check size={16} /> ✅ ஆமாம் / Yes, Confirm & Submit
                </button>
                <button
                  type="button"
                  onClick={() => handleSubmitSpokenProblem('I want to change some details')}
                  className="btn btn-secondary btn-sm"
                >
                  ✏️ விவரத்தை மாற்று / Edit
                </button>
              </div>
            </div>
          )}

          {/* Realistic 1-Click Citizen Speech Tester Presets in Tamil, Tanglish & English */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Sparkles size={14} color="#38bdf8" /> Citizen Voice Quick-Test Prompts (Click to Simulate Citizen Speaking):
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={() => { setSpokenText('கோயம்புத்தூர் காந்திபுரம் 5-வது கிராஸ் கட் ரோட்ல குடிநீர் பைப் உடைஞ்சு தண்ணி ரோட்ல ஓடுது, முருகன் கோவில் பக்கத்துல கதவு எண் 45'); handleSubmitSpokenProblem('கோயம்புத்தூர் காந்திபுரம் 5-வது கிராஸ் கட் ரோட்ல குடிநீர் பைப் உடைஞ்சு தண்ணி ரோட்ல ஓடுது, முருகன் கோவில் பக்கத்துல கதவு எண் 45'); }}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-full)', background: 'rgba(56, 189, 248, 0.15)', borderColor: 'rgba(56, 189, 248, 0.4)', color: '#38bdf8' }}
              >
                🗣️ தமிழ்: காந்திபுரம் 5-வது கிராஸ் கட் ரோடு பைப் உடைப்பு
              </button>
              <button
                type="button"
                onClick={() => { setSpokenText('Chennai Anna Nagar 2nd Avenue la street light eriyala romba dark ah irukku near Nilgiris supermarket opposite Door 12'); handleSubmitSpokenProblem('Chennai Anna Nagar 2nd Avenue la street light eriyala romba dark ah irukku near Nilgiris supermarket opposite Door 12'); }}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-full)', background: 'rgba(245, 158, 11, 0.15)', borderColor: 'rgba(245, 158, 11, 0.4)', color: '#fbbf24' }}
              >
                🗣️ Tanglish: Anna Nagar 2nd Ave street light issue
              </button>
              <button
                type="button"
                onClick={() => { setSpokenText('Sewage drainage water is overflowing on Trichy Road, Singanallur opposite Bus Depot since yesterday morning'); handleSubmitSpokenProblem('Sewage drainage water is overflowing on Trichy Road, Singanallur opposite Bus Depot since yesterday morning'); }}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-full)', background: 'rgba(249, 115, 22, 0.15)', borderColor: 'rgba(249, 115, 22, 0.4)', color: '#fdba74' }}
              >
                🗣️ English: Singanallur Trichy Road drainage overflow
              </button>
              <button
                type="button"
                onClick={() => { setSpokenText('மதுரை மேலூர் மெயின் ரோட்ல பெரிய குப்பை குமிஞ்சிருக்கு துர்நாற்றம் வீசுது அரசு பள்ளி அருகில்'); handleSubmitSpokenProblem('மதுரை மேலூர் மெயின் ரோட்ல பெரிய குப்பை குமிஞ்சிருக்கு துர்நாற்றம் வீசுது அரசு பள்ளி அருகில்'); }}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: 'var(--radius-full)', background: 'rgba(139, 92, 246, 0.15)', borderColor: 'rgba(139, 92, 246, 0.4)', color: '#c4b5fd' }}
              >
                🗣️ தமிழ்: மதுரை மேலூர் மெயின் ரோடு குப்பை தேக்கம்
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
                placeholder="Citizen speaks or types here (e.g. காந்திபுரம் கிராஸ் கட் ரோடு / Anna Nagar street light problem)..."
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
              <div
                style={{
                  width: '42px',
                  height: '42px',
                  borderRadius: '50%',
                  background: 'rgba(16, 185, 129, 0.25)',
                  border: '2px solid #10b981',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#34d399',
                }}
              >
                <CheckCircle2 size={24} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#34d399' }}>
                  Grievance Registered Successfully via Toll-Free Helpline!
                </h3>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Tracking ID: <strong style={{ color: '#ffffff' }}>#{result.complaint_number}</strong> • OpenStreetMap Location Verified
                </span>
              </div>
            </div>

            <span style={{ background: 'rgba(16, 185, 129, 0.2)', border: '1px solid #10b981', color: '#34d399', padding: '0.35rem 0.85rem', borderRadius: 'var(--radius-full)', fontSize: '0.8rem', fontWeight: 700 }}>
              STATUS: ASSIGNED TO FIELD OFFICER
            </span>
          </div>

          {/* Details Summary Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>DEPARTMENT ROUTED</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700, color: '#38bdf8' }}>
                <Building2 size={16} />
                <span>{result.suggested_department}</span>
              </div>
            </div>

            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>OPENSTREETMAP LOCATION</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700, color: '#fbbf24' }}>
                <MapPin size={16} />
                <span>{result.extracted_location}</span>
              </div>
            </div>

            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>AUTOMATIC SMS DISPATCH</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700, color: '#34d399' }}>
                <MessageSquare size={16} />
                <span>Sent to {callerPhone}</span>
              </div>
            </div>
          </div>

          {/* Action Links */}
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
            <Link to={`/complaints/${result.complaint_id}`} className="btn btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>View Official Complaint Record</span>
              <ArrowRight size={16} />
            </Link>
            <button
              onClick={() => {
                setCallState('IDLE');
                setResult(null);
                setMessages([]);
                setCollectionFields({});
              }}
              className="btn btn-secondary"
            >
              Start New Toll-Free Helpline Call
            </button>
          </div>
        </div>
      )}

    </div>
  );
};
