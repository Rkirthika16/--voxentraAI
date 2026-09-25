import { useState, useEffect, useRef, useCallback } from 'react';
import { ivrApi } from '../api/ivr';
import { voiceApi } from '../api/voice';
import { speech } from './speech';
import { VoiceState } from '../components/voice/VoiceStatus';
import { MessageItem } from '../components/voice/ConversationMessage';
import { ConversationalAnalysis } from '../types';

export interface VoiceConversationOptions {
  mode?: 'ivr' | 'assistant';
  callerPhone?: string;
  onTurnComplete?: (analysis: ConversationalAnalysis, state: VoiceState) => void;
  onComplaintConfirmed?: (complaintNumber: string, complaintId: number, analysis: ConversationalAnalysis) => void;
}

export function useVoiceConversationEngine(options: VoiceConversationOptions = {}) {
  const { mode = 'ivr', callerPhone = '+919843098765', onTurnComplete, onComplaintConfirmed } = options;

  // Session State
  const [sessionId, setSessionId] = useState<string>('');
  const [voiceState, setVoiceState] = useState<VoiceState>('IDLE');
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [liveTranscription, setLiveTranscription] = useState<string>('');
  const [normalizedTranscription, setNormalizedTranscription] = useState<string>('');
  const [detectedLanguage, setDetectedLanguage] = useState<string>('Auto-Detecting...');
  const [latitude, setLatitude] = useState<string | number | null>('11.016844');
  const [longitude, setLongitude] = useState<string | number | null>('76.955833');
  const [osmLocationName, setOsmLocationName] = useState<string | null>('Coimbatore, Tamil Nadu');
  const [analysis, setAnalysis] = useState<ConversationalAnalysis>({
    category: '',
    location: '',
    problem: '',
    duration: '',
    affected_scope: '',
    priority: 'MEDIUM',
    department: ''
  });

  // State flags
  const [isHandsFreeActive, setIsHandsFreeActive] = useState<boolean>(false);
  const [isAiSpeaking, setIsAiSpeaking] = useState<boolean>(false);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isPermissionDenied, setIsPermissionDenied] = useState<boolean>(false);
  const [isSpeechRecognitionAvailable, setIsSpeechRecognitionAvailable] = useState<boolean>(true);
  const [completedComplaint, setCompletedComplaint] = useState<{
    id?: number;
    number?: string;
    department?: string;
  } | null>(null);

  // Audio & VAD Refs
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const vadAnimationRef = useRef<number | null>(null);
  const recognitionRef = useRef<any>(null);
  const currentAudioElementRef = useRef<HTMLAudioElement | null>(null);

  // VAD Timing Refs
  const isSpeakingRef = useRef<boolean>(false);
  const speechStartTimeRef = useRef<number>(0);
  const lastSpeechTimeRef = useRef<number>(0);
  const silenceTimerRef = useRef<any>(null);
  const isAiSpeakingRef = useRef<boolean>(false);
  const isHandsFreeActiveRef = useRef<boolean>(false);
  const sessionIdRef = useRef<string>('');

  // Keep refs in sync
  useEffect(() => {
    isAiSpeakingRef.current = isAiSpeaking;
  }, [isAiSpeaking]);

  useEffect(() => {
    isHandsFreeActiveRef.current = isHandsFreeActive;
  }, [isHandsFreeActive]);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopAllAudio();
    };
  }, []);

  const stopAllAudio = () => {
    speech.stop();
    if (currentAudioElementRef.current) {
      currentAudioElementRef.current.pause();
      currentAudioElementRef.current = null;
    }
    if (vadAnimationRef.current) {
      cancelAnimationFrame(vadAnimationRef.current);
      vadAnimationRef.current = null;
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      try { mediaRecorderRef.current.stop(); } catch (e) {}
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      try { audioContextRef.current.close(); } catch (e) {}
      audioContextRef.current = null;
    }
  };

  /**
   * Initializes or restarts a two-way conversational session
   */
  const startSession = async () => {
    stopAllAudio();
    setError(null);
    setIsPermissionDenied(false);
    setMessages([]);
    setLiveTranscription('');
    setNormalizedTranscription('');
    setCompletedComplaint(null);
    setVoiceState('PROCESSING');

    try {
      const res = mode === 'ivr'
        ? await ivrApi.startConversationalSession(callerPhone)
        : await voiceApi.startSession(callerPhone);

      setSessionId(res.session_id);
      sessionIdRef.current = res.session_id;
      if (res.analysis) setAnalysis(res.analysis);
      if (res.detected_language) setDetectedLanguage(res.detected_language);
      setIsSpeechRecognitionAvailable(res.speech_recognition_available !== false);

      const welcomeText = res.response_text || res.greeting_text || 'வணக்கம். உங்கள் புகாரைக் கூறவும்.';
      const welcomeSpoken = res.ai_spoken || res.greeting_spoken || welcomeText;
      const initialLang = res.language || res.detected_language || 'Tamil';

      const aiMsg: MessageItem = {
        id: `ai_${Date.now()}`,
        sender: 'ai',
        text: welcomeText,
        language: initialLang,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        state: res.conversation_state || 'WAITING_FOR_CITIZEN'
      };
      setMessages([aiMsg]);

      // Enable hands-free mode
      setIsHandsFreeActive(true);
      isHandsFreeActiveRef.current = true;

      // Play AI welcome speech. When finished, automatic microphone loop triggers!
      playAiSpeech(welcomeSpoken, initialLang, res.audio_base64, () => {
        armCitizenMicrophone();
      });
    } catch (err: any) {
      console.error('Session start error:', err);
      setError('Unable to start conversational session. Backend may be offline.');
      setVoiceState('ERROR');
    }
  };

  /**
   * Plays AI speech via high-quality base64 audio stream or Web Speech TTS fallback
   */
  const playAiSpeech = (
    spokenText: string,
    lang = 'Tamil',
    base64Audio?: string | null,
    onFinished?: () => void
  ) => {
    // Interruption Safety: AI is speaking -> mute microphone capture
    setIsAiSpeaking(true);
    isAiSpeakingRef.current = true;
    setVoiceState('AI_SPEAKING');

    // If microphone recorder is active, pause/stop it so AI's own voice is not captured
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) {}
    }

    const handleSpeechEnd = () => {
      setIsAiSpeaking(false);
      isAiSpeakingRef.current = false;
      setVoiceState('WAITING_FOR_CITIZEN');
      if (onFinished && isHandsFreeActiveRef.current) {
        onFinished();
      }
    };

    if (base64Audio) {
      try {
        if (currentAudioElementRef.current) {
          currentAudioElementRef.current.pause();
        }
        const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
        currentAudioElementRef.current = audio;
        audio.onended = handleSpeechEnd;
        audio.onerror = () => {
          // Fallback to Web Speech API synthesis
          speech.speak(spokenText, {
            language: lang,
            onStart: () => {
              setIsAiSpeaking(true);
              isAiSpeakingRef.current = true;
              setVoiceState('AI_SPEAKING');
            },
            onEnd: handleSpeechEnd,
            onError: handleSpeechEnd
          });
        };
        audio.play().catch(() => {
          speech.speak(spokenText, {
            language: lang,
            onStart: () => {
              setIsAiSpeaking(true);
              isAiSpeakingRef.current = true;
              setVoiceState('AI_SPEAKING');
            },
            onEnd: handleSpeechEnd,
            onError: handleSpeechEnd
          });
        });
        return;
      } catch (e) {
        console.warn('Audio element error:', e);
      }
    }

    // Web Speech API fallback
    speech.speak(spokenText, {
      language: lang,
      onStart: () => {
        setIsAiSpeaking(true);
        isAiSpeakingRef.current = true;
        setVoiceState('AI_SPEAKING');
      },
      onEnd: handleSpeechEnd,
      onError: handleSpeechEnd
    });
  };

  /**
   * Arms the citizen microphone for hands-free VAD and continuous speech detection
   */
  const armCitizenMicrophone = async () => {
    // Interruption safety check: do not listen if AI is speaking
    if (isAiSpeakingRef.current) return;

    setError(null);
    setLiveTranscription('');
    setVoiceState('WAITING_FOR_CITIZEN');

    try {
      // 1. Acquire microphone stream if not already open
      if (!mediaStreamRef.current || !mediaStreamRef.current.active) {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        });
        mediaStreamRef.current = stream;
      }

      const stream = mediaStreamRef.current;

      // 2. Set up AudioContext and AnalyserNode for energy-based Voice Activity Detection (VAD)
      const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        audioContextRef.current = new AudioCtxClass();
      }
      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume();
      }

      const audioCtx = audioContextRef.current;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.2;
      source.connect(analyser);
      analyserRef.current = analyser;

      // 3. Set up MediaRecorder to capture turn audio
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.start(200);
      setIsRecording(true);

      // 4. Set up Web Speech Recognition for live visual feedback
      if (speech.isSTTSupported()) {
        try {
          const rec = speech.createRecognition(
            'en-IN' as any,
            (transcript, isFinal) => {
              if (!isAiSpeakingRef.current) {
                setLiveTranscription(transcript);
                if (transcript && !isSpeakingRef.current) {
                  isSpeakingRef.current = true;
                  setVoiceState('CITIZEN_SPEAKING');
                }
              }
            },
            (err) => console.log('STT status:', err),
            () => {}
          );
          if (rec) {
            recognitionRef.current = rec;
            try { rec.start(); } catch (e) {}
          }
        } catch (sttErr) {
          console.log('Web speech init:', sttErr);
        }
      }

      // 5. Start VAD loop
      startVadLoop();
    } catch (err: any) {
      console.warn('Microphone permission error:', err);
      setIsPermissionDenied(true);
      setError('Microphone permission is required for voice conversation.');
      setVoiceState('ERROR');
    }
  };

  /**
   * Real-time Voice Activity Detection (VAD) loop with energy threshold and silence detection
   */
  const startVadLoop = () => {
    if (!analyserRef.current) return;

    const analyser = analyserRef.current;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const SPEECH_THRESHOLD = 18; // RMS amplitude threshold for speech detection
    const SILENCE_TIMEOUT_MS = 1600; // Silence duration before turn is considered finished
    const MIN_SPEECH_DURATION_MS = 650; // Minimum duration citizen must speak

    isSpeakingRef.current = false;
    speechStartTimeRef.current = 0;
    lastSpeechTimeRef.current = 0;

    const checkVolume = () => {
      // If AI started speaking, halt VAD
      if (isAiSpeakingRef.current) {
        return;
      }

      analyser.getByteFrequencyData(dataArray);

      // Calculate average RMS energy
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
      }
      const avg = sum / bufferLength;

      const now = Date.now();

      if (avg > SPEECH_THRESHOLD) {
        // Speech detected!
        if (!isSpeakingRef.current) {
          isSpeakingRef.current = true;
          speechStartTimeRef.current = now;
          setVoiceState('CITIZEN_SPEAKING');
        }
        lastSpeechTimeRef.current = now;

        // Clear any pending silence timer
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
      } else {
        // Silence or low energy
        if (isSpeakingRef.current && lastSpeechTimeRef.current > 0) {
          const silenceDuration = now - lastSpeechTimeRef.current;
          const totalSpeechDuration = now - speechStartTimeRef.current;

          if (silenceDuration > SILENCE_TIMEOUT_MS && totalSpeechDuration > MIN_SPEECH_DURATION_MS) {
            // End of citizen turn detected! Automatically submit turn
            isSpeakingRef.current = false;
            if (vadAnimationRef.current) {
              cancelAnimationFrame(vadAnimationRef.current);
              vadAnimationRef.current = null;
            }
            triggerSubmitTurn();
            return;
          }
        }
      }

      vadAnimationRef.current = requestAnimationFrame(checkVolume);
    };

    vadAnimationRef.current = requestAnimationFrame(checkVolume);
  };

  /**
   * Automatically stops recording and submits the turn to FastAPI conversation engine
   */
  const triggerSubmitTurn = async () => {
    setIsRecording(false);
    setVoiceState('PROCESSING_AUDIO');

    if (vadAnimationRef.current) {
      cancelAnimationFrame(vadAnimationRef.current);
      vadAnimationRef.current = null;
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) {}
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      try { mediaRecorderRef.current.stop(); } catch (e) {}
    }

    // Small delay to allow final audio chunks to accumulate
    setTimeout(async () => {
      setVoiceState('TRANSCRIBING');

      const audioBlob = audioChunksRef.current.length > 0
        ? new Blob(audioChunksRef.current, { type: 'audio/wav' })
        : null;
      const textFallback = liveTranscription.trim();

      const currentSid = sessionIdRef.current;
      if (!currentSid) {
        setVoiceState('WAITING_FOR_CITIZEN');
        return;
      }

      // Add citizen turn message bubble to live chat
      const citizenMsg: MessageItem = {
        id: `cit_${Date.now()}`,
        sender: 'citizen',
        text: textFallback || '🎤 [Spoken Voice Turn]',
        language: detectedLanguage,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages((prev) => [...prev, citizenMsg]);

      try {
        setVoiceState('DETECTING_LANGUAGE');
        let res: any;

        if (audioBlob && audioBlob.size > 800) {
          res = mode === 'ivr'
            ? await ivrApi.sendAudioTurn(currentSid, audioBlob, callerPhone)
            : await voiceApi.sendAudioTurn(currentSid, audioBlob, callerPhone);
        } else if (textFallback) {
          res = mode === 'ivr'
            ? await ivrApi.sendMessageTurn(currentSid, textFallback, callerPhone)
            : await voiceApi.sendMessageTurn(currentSid, textFallback, callerPhone);
        } else {
          // No audio captured
          setVoiceState('WAITING_FOR_CITIZEN');
          armCitizenMicrophone();
          return;
        }

        setVoiceState('UNDERSTANDING');
        handleTurnResponse(res);
      } catch (turnErr: any) {
        console.error('Turn submission error:', turnErr);
        setError('Failed to process voice turn. Please speak again or type your complaint.');
        setVoiceState('WAITING_FOR_CITIZEN');
        armCitizenMicrophone();
      }
    }, 350);
  };

  /**
   * Processes backend turn response and handles continuous conversation loop
   */
  const handleTurnResponse = (res: any) => {
    setVoiceState('GENERATING_RESPONSE');

    if (res.language || res.detected_language) {
      setDetectedLanguage(res.language || res.detected_language);
    }
    if (res.analysis) {
      setAnalysis(res.analysis);
      if (res.analysis.location) {
        setOsmLocationName(res.analysis.location);
      }
    }
    if (res.latitude && res.longitude) {
      setLatitude(res.latitude);
      setLongitude(res.longitude);
      if (res.osm_location_name) {
        setOsmLocationName(res.osm_location_name);
      }
    }
    if (res.transcription) {
      setLiveTranscription(res.transcription);
    }
    if (res.normalized_transcription) {
      setNormalizedTranscription(res.normalized_transcription);
    }

    const replyText = res.response_text || res.ai_text || res.ai_spoken || '';
    const spokenText = res.ai_spoken || res.response_text || replyText;
    const spokenLang = res.language || res.detected_language || 'Tamil';

    // Add AI response bubble
    const aiMsg: MessageItem = {
      id: `ai_${Date.now()}`,
      sender: 'ai',
      text: replyText,
      language: spokenLang,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      state: res.conversation_state
    };
    setMessages((prev) => [...prev, aiMsg]);

    if (onTurnComplete && res.analysis) {
      onTurnComplete(res.analysis, res.conversation_state);
    }

    // Check if complaint has been confirmed & registered
    if (res.conversation_state === 'CONFIRMED' || res.conversation_complete || res.complaint_number) {
      const compNum = res.complaint_number || 'VX-2026-000001';
      const compId = res.complaint_id || 1;
      const deptName = res.analysis?.department || 'Municipal Administration';

      setCompletedComplaint({
        id: compId,
        number: compNum,
        department: deptName
      });

      if (onComplaintConfirmed && res.analysis) {
        onComplaintConfirmed(compNum, compId, res.analysis);
      }

      // Speak final confirmation, then conclude conversation
      playAiSpeech(spokenText, spokenLang, res.audio_base64, () => {
        setVoiceState('CONFIRMED');
        setIsHandsFreeActive(false);
      });
      return;
    }

    // Conversation is continuing!
    // Speak response, then automatically return to WAITING_FOR_CITIZEN and arm microphone!
    playAiSpeech(spokenText, spokenLang, res.audio_base64, () => {
      armCitizenMicrophone();
    });
  };

  /**
   * Text-based fallback input submitting to exact same conversation engine
   */
  const sendTextMessage = async (text: string) => {
    const raw = text.trim();
    if (!raw) return;

    setError(null);
    speech.stop();
    setLiveTranscription(raw);
    setVoiceState('PROCESSING');

    const citizenMsg: MessageItem = {
      id: `cit_${Date.now()}`,
      sender: 'citizen',
      text: raw,
      language: detectedLanguage,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages((prev) => [...prev, citizenMsg]);

    const currentSid = sessionIdRef.current;
    if (!currentSid) return;

    try {
      const res = mode === 'ivr'
        ? await ivrApi.sendMessageTurn(currentSid, raw, callerPhone)
        : await voiceApi.sendMessageTurn(currentSid, raw, callerPhone);

      handleTurnResponse(res);
    } catch (err: any) {
      console.error('Text turn error:', err);
      setError('Failed to process message. Please try again.');
      setVoiceState('WAITING_FOR_CITIZEN');
    }
  };

  /**
   * Manual Speak / Stop button fallback toggle
   */
  const toggleRecording = () => {
    speech.unlock();
    if (isRecording || voiceState === 'CITIZEN_SPEAKING') {
      triggerSubmitTurn();
    } else {
      armCitizenMicrophone();
    }
  };

  /**
   * Manual confirmation button fallback
   */
  const confirmComplaint = async () => {
    const currentSid = sessionIdRef.current;
    if (!currentSid) return;
    setVoiceState('PROCESSING');

    try {
      const res = mode === 'ivr'
        ? await ivrApi.confirmSession(currentSid, callerPhone)
        : await voiceApi.confirmSession(currentSid, 'Citizen Caller', callerPhone);

      handleTurnResponse(res);
    } catch (err) {
      setError('Failed to confirm complaint.');
      setVoiceState('CONFIRMING');
    }
  };

  /**
   * Cancel and reset conversation
   */
  const cancelConversation = async () => {
    stopAllAudio();
    const currentSid = sessionIdRef.current;
    if (currentSid) {
      try {
        if (mode === 'ivr') {
          await ivrApi.cancelSession(currentSid);
        } else {
          await voiceApi.cancelSession(currentSid);
        }
      } catch (e) {}
    }
    setVoiceState('CANCELLED');
    setIsHandsFreeActive(false);
  };

  return {
    sessionId,
    voiceState,
    setVoiceState,
    messages,
    liveTranscription,
    normalizedTranscription,
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
  };
}
