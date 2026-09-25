import { apiClient } from './client';
import {
  IVRCallInitiateResponse,
  IVRProcessSpeechResponse,
  IVRCallDialogueResponse,
  InboundSMSResponse,
  ManualSMSResponse,
  TelephonyLogsResponse
} from '../types';

export const ivrApi = {
  /**
   * Initiates a toll-free call session and gets bilingual IVR prompts.
   */
  initiateCall: async (callerPhone = '+919843098765', tollFreeNumber = '1800-425-1913'): Promise<IVRCallInitiateResponse> => {
    const res = await apiClient.post<IVRCallInitiateResponse>('/ivr/initiate-call', {
      caller_phone: callerPhone,
      toll_free_number: tollFreeNumber,
    });
    return res.data;
  },

  /**
   * Sends a conversational dialogue turn to the speaking AI during a toll-free call.
   */
  dialogueTurn: async (params: {
    call_sid: string;
    caller_phone?: string;
    dialogue_turn: number;
    user_speech: string;
    conversation_history?: any[];
    language_preference?: string;
  }): Promise<IVRCallDialogueResponse> => {
    const res = await apiClient.post<IVRCallDialogueResponse>('/ivr/dialogue-turn', params);
    return res.data;
  },

  /**
   * Processes speech transcript or text through the AI engine and dispatches to department.
   */
  processSpeech: async (params: {
    call_sid?: string;
    caller_phone?: string;
    speech_text: string;
    language_hint?: string;
  }): Promise<IVRProcessSpeechResponse> => {
    const res = await apiClient.post<IVRProcessSpeechResponse>('/ivr/process-call', params);
    return res.data;
  },

  /**
   * Uploads real audio recording from the caller, runs audio prediction & transcription, and executes department routing.
   */
  uploadVoiceRecording: async (
    audioBlob: Blob,
    callSid?: string,
    callerPhone = '+919843098765',
    languageHint?: string
  ): Promise<IVRProcessSpeechResponse> => {
    const formData = new FormData();
    formData.append('file', audioBlob, 'tollfree_call.wav');
    if (callSid) formData.append('call_sid', callSid);
    formData.append('caller_phone', callerPhone);
    if (languageHint) formData.append('language_hint', languageHint);

    const res = await apiClient.post<IVRProcessSpeechResponse>('/ivr/voice-recording', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  /**
   * Simulates an incoming SMS sent from a villager's mobile phone to the helpline.
   */
  simulateInboundSms: async (params: {
    from_phone: string;
    to_phone?: string;
    message_body: string;
    sms_sid?: string;
  }): Promise<InboundSMSResponse> => {
    const res = await apiClient.post<InboundSMSResponse>('/ivr/simulate-inbound-sms', params);
    return res.data;
  },

  /**
   * Dispatches a manual SMS from an officer/operator to a citizen's phone.
   */
  sendManualSms: async (params: {
    to_phone: string;
    message: string;
    complaint_number?: string;
  }): Promise<ManualSMSResponse> => {
    const res = await apiClient.post<ManualSMSResponse>('/ivr/send-manual-sms', params);
    return res.data;
  },

  /**
   * Retrieves the real-time ring buffer of telephony call & SMS logs.
   */
  getTelephonyLogs: async (limit = 50): Promise<TelephonyLogsResponse> => {
    const res = await apiClient.get<TelephonyLogsResponse>('/ivr/telephony-logs', {
      params: { limit },
    });
    return res.data;
  },

  /**
   * Starts a true two-way conversational voice session with automatic turn taking.
   */
  startConversationalSession: async (callerPhone = '+919843098765'): Promise<any> => {
    const res = await apiClient.post('/ivr/session', {
      caller_phone: callerPhone,
    });
    return res.data;
  },

  /**
   * Sends caller microphone audio turn to unified conversational engine.
   */
  sendAudioTurn: async (sessionId: string, audioBlob: Blob, callerPhone = '+919843098765'): Promise<any> => {
    const formData = new FormData();
    formData.append('file', audioBlob, 'turn_audio.wav');
    formData.append('caller_phone', callerPhone);

    const res = await apiClient.post(`/ivr/session/${sessionId}/audio`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  /**
   * Sends text fallback turn to unified conversational engine.
   */
  sendMessageTurn: async (sessionId: string, message: string, callerPhone = '+919843098765'): Promise<any> => {
    const formData = new FormData();
    formData.append('message', message);
    formData.append('caller_phone', callerPhone);

    const res = await apiClient.post(`/ivr/session/${sessionId}/message`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  /**
   * Gets active session state and memory from backend.
   */
  getSessionState: async (sessionId: string): Promise<any> => {
    const res = await apiClient.get(`/ivr/session/${sessionId}`);
    return res.data;
  },

  /**
   * Confirms session and generates official complaint record in database.
   */
  confirmSession: async (sessionId: string, callerPhone = '+919843098765'): Promise<any> => {
    const formData = new FormData();
    formData.append('caller_phone', callerPhone);

    const res = await apiClient.post(`/ivr/session/${sessionId}/confirm`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  /**
   * Cancels active conversation session.
   */
  cancelSession: async (sessionId: string): Promise<any> => {
    const res = await apiClient.post(`/ivr/session/${sessionId}/cancel`);
    return res.data;
  },
};
