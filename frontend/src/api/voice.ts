import { apiClient } from './client';

export interface VoiceSessionResponse {
  session_id: string;
  state: 'IDLE' | 'LISTENING' | 'PROCESSING' | 'AI_RESPONDING' | 'SPEAKING' | 'WAITING_FOR_USER' | 'CONFIRMING' | 'COMPLETED' | 'ERROR';
  greeting_text?: string;
  greeting_spoken?: string;
  audio_base64?: string | null;
  detected_language?: string;
  ai_text?: string;
  ai_spoken?: string;
  transcription?: string;
  original_transcription?: string;
  normalized_transcription?: string;
  context?: Record<string, any>;
  confirmation_required?: boolean;
  conversation_complete?: boolean;
  complaint_number?: string;
  complaint_id?: number;
  department?: string;
  error?: string;
  speech_recognition_available?: boolean;
}

export const voiceApi = {
  /**
   * Starts a new conversational voice session.
   */
  startSession: async (callerPhone = '+919843098765'): Promise<VoiceSessionResponse> => {
    const res = await apiClient.post<VoiceSessionResponse>('/voice/session', {
      caller_phone: callerPhone,
    });
    return res.data;
  },

  /**
   * Sends recorded audio blob for transcription & conversational AI reasoning.
   */
  sendAudioTurn: async (
    sessionId: string,
    audioBlob: Blob,
    callerPhone = '+919843098765'
  ): Promise<VoiceSessionResponse> => {
    const formData = new FormData();
    formData.append('file', audioBlob, 'turn_audio.wav');
    formData.append('caller_phone', callerPhone);

    const res = await apiClient.post<VoiceSessionResponse>(`/voice/session/${sessionId}/audio`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  /**
   * Sends text fallback turn to conversational voice engine.
   */
  sendMessageTurn: async (
    sessionId: string,
    message: string,
    callerPhone = '+919843098765'
  ): Promise<VoiceSessionResponse> => {
    const res = await apiClient.post<VoiceSessionResponse>(`/voice/session/${sessionId}/message`, {
      message,
      caller_phone: callerPhone,
    });
    return res.data;
  },

  /**
   * Gets current structured conversation state and extracted slots.
   */
  getSessionState: async (sessionId: string): Promise<VoiceSessionResponse> => {
    const res = await apiClient.get<VoiceSessionResponse>(`/voice/session/${sessionId}`);
    return res.data;
  },

  /**
   * Confirms grievance registration and creates official complaint in database.
   */
  confirmSession: async (
    sessionId: string,
    citizenName = 'Citizen Caller',
    callerPhone = '+919843098765'
  ): Promise<VoiceSessionResponse> => {
    const res = await apiClient.post<VoiceSessionResponse>(`/voice/session/${sessionId}/confirm`, {
      citizen_name: citizenName,
      caller_phone: callerPhone,
    });
    return res.data;
  },

  /**
   * Cancels active conversation session.
   */
  cancelSession: async (sessionId: string): Promise<{ session_id: string; state: string; message: string }> => {
    const res = await apiClient.post(`/voice/session/${sessionId}/cancel`);
    return res.data;
  },
};
