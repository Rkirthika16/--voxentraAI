import React, { useState, useEffect, useRef } from 'react';
import { tollfreeApi, TollFreeMemory, TollFreeMessage } from '../api/tollfree';
import { CallScreen } from '../components/tollfree/CallScreen';
import { ConversationStatus } from '../components/tollfree/ConversationStatus';
import { LiveTranscript } from '../components/tollfree/LiveTranscript';
import { VoiceRecorder } from '../components/tollfree/VoiceRecorder';
import { ComplaintDetails } from '../components/tollfree/ComplaintDetails';
import { ConfirmationPanel } from '../components/tollfree/ConfirmationPanel';
import { CallCompleted } from '../components/tollfree/CallCompleted';

export const TollFreeIVRPage: React.FC = () => {
  // Call & Session State
  const [callActive, setCallActive] = useState<boolean>(false);
  const [callerPhone, setCallerPhone] = useState<string>('+919843098765');
  const [tollFreeNumber, setTollFreeNumber] = useState<string>('1800-425-8693');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [ivrState, setIvrState] = useState<string>('DISCONNECTED');
  const [callDuration, setCallDuration] = useState<number>(0);
  const [detectedLanguage, setDetectedLanguage] = useState<string>('Auto');
  const [languageConfidence, setLanguageConfidence] = useState<number | undefined>(undefined);

  // Messages & Memory State
  const [messages, setMessages] = useState<TollFreeMessage[]>([]);
  const [memory, setMemory] = useState<TollFreeMemory>({
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

  // Audio, Speech & TTS State
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isAiSpeaking, setIsAiSpeaking] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [ttsMuted, setTtsMuted] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Registered Complaint Result
  const [registeredComplaint, setRegisteredComplaint] = useState<{
    id?: number;
    number: string;
    department?: string;
    smsSent?: boolean;
  } | null>(null);

  const timerRef = useRef<number | null>(null);

  // Call duration counter
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

  // Browser Text-to-Speech (TTS) with Turn-Taking Management
  const speakText = (text: string, lang = 'Tanglish', onFinish?: () => void) => {
    if (ttsMuted || !window.speechSynthesis) {
      if (onFinish) onFinish();
      return;
    }

    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.95;
      utterance.pitch = 1.0;

      const voices = window.speechSynthesis.getVoices();
      const lowerLang = (lang || '').toLowerCase();

      if (lowerLang.includes('tamil') || lowerLang === 'ta') {
        const taVoice = voices.find(
          (v) => v.lang.toLowerCase().includes('ta') || v.name.toLowerCase().includes('tamil')
        );
        if (taVoice) utterance.voice = taVoice;
        utterance.lang = 'ta-IN';
      } else if (lowerLang.includes('tanglish')) {
        const inVoice = voices.find(
          (v) =>
            v.lang.toLowerCase().includes('en-in') ||
            v.lang.toLowerCase().includes('ta') ||
            v.name.toLowerCase().includes('india')
        );
        if (inVoice) utterance.voice = inVoice;
        utterance.lang = 'en-IN';
      } else {
        const enVoice = voices.find((v) => v.lang.toLowerCase().includes('en'));
        if (enVoice) utterance.voice = enVoice;
        utterance.lang = 'en-US';
      }

      utterance.onstart = () => {
        setIsAiSpeaking(true);
      };

      utterance.onend = () => {
        setIsAiSpeaking(false);
        if (onFinish) onFinish();
      };

      utterance.onerror = (e) => {
        console.warn('SpeechSynthesis error:', e);
        setIsAiSpeaking(false);
        if (onFinish) onFinish();
      };

      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.warn('TTS execution error:', err);
      setIsAiSpeaking(false);
      if (onFinish) onFinish();
    }
  };

  // Start Call Session
  const handleStartCall = async () => {
    try {
      setErrorMessage(null);
      setIsProcessing(true);
      setRegisteredComplaint(null);
      setMessages([]);
      setMemory({
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

      const data = await tollfreeApi.createSession(callerPhone, tollFreeNumber);
      setSessionId(data.session_id);
      setIvrState(data.state || 'WAITING_FOR_CITIZEN');
      setDetectedLanguage(data.language || 'Auto');
      setCallActive(true);

      const systemBannerMsg: TollFreeMessage = {
        id: Date.now(),
        role: 'system',
        content: '📞 Call Connected. Citizen speaks first — please describe your complaint in Tamil, English, or Tanglish.',
        language: 'Auto',
        created_at: new Date().toISOString(),
      };
      setMessages([systemBannerMsg]);
      // Do NOT play AI voice first — line is open for the citizen to speak first!
    } catch (err: any) {
      console.error('Failed to start tollfree call:', err);
      setErrorMessage(err.response?.data?.detail?.message || err.message || 'Failed to connect toll-free call.');
      setCallActive(false);
    } finally {
      setIsProcessing(false);
    }
  };

  // End / Hang up Call
  const handleEndCall = async () => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsAiSpeaking(false);
    setIsRecording(false);

    if (sessionId) {
      try {
        await tollfreeApi.endSession(sessionId);
      } catch (e) {
        console.warn('Error ending session:', e);
      }
    }

    setCallActive(false);
    setIvrState('DISCONNECTED');
  };

  // Process Turn Response from Server
  const handleTurnResult = (res: any, citizenTurnText: string) => {
    // Add citizen message to transcript if not already present
    const rawTranscript = res.raw_transcript || citizenTurnText;
    const normalizedTranscript = res.normalized_transcript || res.raw_transcript || citizenTurnText;

    const citizenMsg: TollFreeMessage = {
      id: Date.now() - 1,
      role: 'citizen',
      content: rawTranscript,
      normalized_content: normalizedTranscript,
      language: res.detected_language,
      created_at: new Date().toISOString(),
    };

    const aiMsg: TollFreeMessage = {
      id: Date.now(),
      role: 'ai',
      content: res.ai_reply || '...',
      language: res.detected_language,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, citizenMsg, aiMsg]);
    setIvrState(res.state);
    if (res.detected_language) {
      setDetectedLanguage(res.detected_language);
    }
    if (res.language_confidence !== undefined) {
      setLanguageConfidence(res.language_confidence);
    }
    if (res.memory) {
      setMemory(res.memory);
    }

    // Check if complaint was created
    if (res.complaint_created && (res.complaint_number || res.complaint_id)) {
      setRegisteredComplaint({
        id: res.complaint_id,
        number: res.complaint_number || `VX-2026-${String(res.complaint_id).padStart(6, '0')}`,
        department: res.department || res.memory?.department,
        smsSent: res.sms_sent,
      });
    }

    // Speak AI reply
    speakText(res.spoken_reply || res.ai_reply, res.detected_language || 'Tanglish');
  };

  // Send Audio from VoiceRecorder
  const handleSendAudio = async (audioBlob: Blob) => {
    if (!sessionId || !callActive || isProcessing) return;
    try {
      setIsProcessing(true);
      setErrorMessage(null);

      const res = await tollfreeApi.sendAudio(sessionId, audioBlob);
      handleTurnResult(res, 'Voice Utterance');
    } catch (err: any) {
      console.error('Audio processing error:', err);
      const msg = err.response?.data?.detail?.message || err.message || 'Speech processing failed. Please repeat.';
      setErrorMessage(msg);
      speakText('Sorry, unga kural thelivaga ketkavillai. Meendum sollunga.', detectedLanguage);
    } finally {
      setIsProcessing(false);
    }
  };

  // Send Text fallback
  const handleSendText = async (text: string) => {
    if (!sessionId || !callActive || isProcessing) return;
    try {
      setIsProcessing(true);
      setErrorMessage(null);

      const res = await tollfreeApi.sendMessage(sessionId, text);
      handleTurnResult(res, text);
    } catch (err: any) {
      console.error('Text turn error:', err);
      const msg = err.response?.data?.detail?.message || err.message || 'Failed to process message.';
      setErrorMessage(msg);
    } finally {
      setIsProcessing(false);
    }
  };

  // Confirm complaint directly from confirmation panel button
  const handleConfirmDirect = async () => {
    if (!sessionId || isProcessing) return;
    try {
      setIsProcessing(true);
      setErrorMessage(null);

      const res = await tollfreeApi.confirmComplaint(sessionId);
      handleTurnResult(res, 'Aama, ellam correct (Confirmed)');
    } catch (err: any) {
      console.error('Confirmation error:', err);
      setErrorMessage('Confirmation failed. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  // Reject / Correct details
  const handleRejectDirect = () => {
    handleSendText('Illa, details mathanum');
  };

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '1.5rem 1rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* 1. Header & Call Screen Dialer */}
      <CallScreen
        isCallActive={callActive}
        callerPhone={callerPhone}
        setCallerPhone={setCallerPhone}
        tollFreeNumber={tollFreeNumber}
        detectedLanguage={detectedLanguage}
        languageConfidence={languageConfidence}
        onStartCall={handleStartCall}
        onEndCall={handleEndCall}
        isProcessing={isProcessing}
      />

      {callActive && (
        <>
          {/* 2. Live Conversation Status & Call Timer */}
          <ConversationStatus
            state={ivrState}
            isAiSpeaking={isAiSpeaking}
            isRecording={isRecording}
            isProcessing={isProcessing}
            callDuration={callDuration}
          />

          {/* 3. Main 2-Column Responsive Layout */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
            {/* Left Column: Live Transcript & Voice Input */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <LiveTranscript
                messages={messages}
                isAiSpeaking={isAiSpeaking}
                isProcessing={isProcessing}
              />

              <VoiceRecorder
                isAiSpeaking={isAiSpeaking}
                isProcessing={isProcessing}
                isCallActive={callActive}
                onSendAudio={handleSendAudio}
                onSendText={handleSendText}
                ttsMuted={ttsMuted}
                onToggleMute={() => setTtsMuted(!ttsMuted)}
                errorMessage={errorMessage}
              />
            </div>

            {/* Right Column: Structured Memory, Confirmation Panel, Completed Card */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {registeredComplaint ? (
                <CallCompleted
                  complaintNumber={registeredComplaint.number}
                  department={registeredComplaint.department}
                  smsSent={registeredComplaint.smsSent}
                  onNewCall={handleStartCall}
                />
              ) : ivrState === 'CONFIRMING' ? (
                <>
                  <ConfirmationPanel
                    memory={memory}
                    onConfirm={handleConfirmDirect}
                    onReject={handleRejectDirect}
                    isProcessing={isProcessing}
                  />
                  <ComplaintDetails memory={memory} />
                </>
              ) : (
                <ComplaintDetails memory={memory} />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
