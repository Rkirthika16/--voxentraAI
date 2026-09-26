import { apiClient } from './client';

export interface NewIVRMemory {
  category: string | null;
  problem: string | null;
  location: string | null;
  duration: string | null;
  affected_scope: string | null;
  frequency: string | null;
  severity: string | null;
  priority: string | null;
  department: string | null;
  citizen_name: string | null;
}

export interface NewIVRMessage {
  id: number;
  role: 'citizen' | 'ai' | 'system';
  content: string;
  normalized_content?: string | null;
  language?: string | null;
  audio_url?: string | null;
  created_at: string;
}

export interface NewIVRSessionResponse {
  session_id: string;
  caller_phone: string;
  state: string;
  language: string;
  language_confidence?: number;
  current_field_prompted?: string | null;
  structured_memory: NewIVRMemory;
  complaint_id?: number | null;
  complaint_number?: string | null;
  created_at: string;
  updated_at: string;
  messages: NewIVRMessage[];
}

export interface NewIVRTurnResponse {
  success: boolean;
  session_id: string;
  state: string;
  detected_language: string;
  language_confidence?: number;
  ai_reply: string;
  spoken_reply: string;
  memory: NewIVRMemory;
  next_field?: string;
  question_count?: number;
  max_questions?: number;
  is_confirmation?: boolean;
  complaint_created?: boolean;
  complaint_id?: number;
  complaint_number?: string;
  department?: string;
  sms_sent?: boolean;
  unclear?: boolean;
  transcription?: string;
  error_code?: string;
  message?: string;
}

export const newIvrApi = {
  createSession: async (callerPhone = '+919843098765', languagePreference = 'Auto') => {
    const res = await apiClient.post('/new-ivr/session', {
      caller_phone: callerPhone,
      language_preference: languagePreference,
    });
    return res.data;
  },

  getSession: async (sessionId: string): Promise<NewIVRSessionResponse> => {
    const res = await apiClient.get(`/new-ivr/session/${sessionId}`);
    return res.data;
  },

  sendAudio: async (sessionId: string, audioBlob: Blob, transcriptionHint?: string): Promise<NewIVRTurnResponse> => {
    const formData = new FormData();
    const extension = audioBlob.type.includes('ogg') ? 'ogg' : audioBlob.type.includes('wav') ? 'wav' : 'webm';
    formData.append('audio', audioBlob, `mic_recording_${Date.now()}.${extension}`);
    if (transcriptionHint) {
      formData.append('transcription_hint', transcriptionHint);
    }

    const res = await apiClient.post(`/new-ivr/session/${sessionId}/audio`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  sendMessage: async (sessionId: string, message: string): Promise<NewIVRTurnResponse> => {
    const res = await apiClient.post(`/new-ivr/session/${sessionId}/message`, {
      message,
    });
    return res.data;
  },

  confirmComplaint: async (sessionId: string) => {
    const res = await apiClient.post(`/new-ivr/session/${sessionId}/confirm`);
    return res.data;
  },

  cancelConfirmation: async (sessionId: string) => {
    const res = await apiClient.post(`/new-ivr/session/${sessionId}/cancel`);
    return res.data;
  },

  endSession: async (sessionId: string) => {
    const res = await apiClient.post(`/new-ivr/session/${sessionId}/end`);
    return res.data;
  },

  getStatus: async (sessionId: string) => {
    const res = await apiClient.get(`/new-ivr/session/${sessionId}/status`);
    return res.data;
  },
};
