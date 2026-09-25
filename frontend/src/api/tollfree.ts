import { apiClient } from './client';

export interface TollFreeMemory {
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

export interface TollFreeMessage {
  id: number;
  role: 'citizen' | 'ai' | 'system';
  content: string;
  normalized_content?: string | null;
  language?: string | null;
  audio_url?: string | null;
  created_at: string;
}

export interface TollFreeSessionResponse {
  session_id: string;
  caller_phone: string;
  toll_free_number: string;
  state: string;
  language: string;
  language_confidence?: number;
  current_field_prompted?: string | null;
  structured_memory: TollFreeMemory;
  complaint_id?: number | null;
  complaint_number?: string | null;
  created_at: string;
  updated_at: string;
  messages: TollFreeMessage[];
}

export interface TollFreeTurnResponse {
  success: boolean;
  session_id: string;
  state: string;
  detected_language: string;
  language_confidence?: number;
  ai_reply: string;
  spoken_reply: string;
  raw_transcript?: string;
  normalized_transcript?: string;
  memory: TollFreeMemory;
  next_field?: string;
  is_confirmation?: boolean;
  complaint_created?: boolean;
  complaint_id?: number;
  complaint_number?: string;
  department?: string;
  sms_sent?: boolean;
  unclear?: boolean;
  error_code?: string;
  message?: string;
}

export const tollfreeApi = {
  createSession: async (callerPhone = '+919843098765', tollFreeNumber = '1800-425-8693') => {
    const res = await apiClient.post('/tollfree/session', {
      caller_phone: callerPhone,
      toll_free_number: tollFreeNumber,
    });
    return res.data;
  },

  getSession: async (sessionId: string): Promise<TollFreeSessionResponse> => {
    const res = await apiClient.get(`/tollfree/session/${sessionId}`);
    return res.data;
  },

  sendAudio: async (sessionId: string, audioBlob: Blob): Promise<TollFreeTurnResponse> => {
    const formData = new FormData();
    const extension = audioBlob.type.includes('ogg') ? 'ogg' : audioBlob.type.includes('wav') ? 'wav' : 'webm';
    formData.append('audio', audioBlob, `tollfree_recording_${Date.now()}.${extension}`);

    const res = await apiClient.post(`/tollfree/session/${sessionId}/audio`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  sendMessage: async (sessionId: string, message: string): Promise<TollFreeTurnResponse> => {
    const res = await apiClient.post(`/tollfree/session/${sessionId}/message`, {
      message,
    });
    return res.data;
  },

  confirmComplaint: async (sessionId: string) => {
    const res = await apiClient.post(`/tollfree/session/${sessionId}/confirm`);
    return res.data;
  },

  cancelSession: async (sessionId: string) => {
    const res = await apiClient.post(`/tollfree/session/${sessionId}/cancel`);
    return res.data;
  },

  endSession: async (sessionId: string) => {
    const res = await apiClient.post(`/tollfree/session/${sessionId}/end`);
    return res.data;
  },
};
