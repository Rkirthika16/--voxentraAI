import { apiClient } from './client';
import { AssistantResponse, SuggestionsResponse } from '../types';

export const assistantApi = {
  chat: async (
    message: string,
    sessionId?: string,
    languageHint?: string,
    context?: Record<string, any>
  ): Promise<AssistantResponse> => {
    const res = await apiClient.post<AssistantResponse>('/assistant/chat', {
      message,
      session_id: sessionId,
      language_hint: languageHint,
      context: context || {},
    });
    return res.data;
  },

  voiceChat: async (
    audioBlob: Blob,
    filename = 'voice_query.webm',
    sessionId?: string,
    languageHint?: string
  ): Promise<AssistantResponse> => {
    const formData = new FormData();
    formData.append('file', audioBlob, filename);
    if (sessionId) formData.append('session_id', sessionId);
    if (languageHint) formData.append('language_hint', languageHint);

    const res = await apiClient.post<AssistantResponse>('/assistant/voice-chat', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  getSuggestions: async (): Promise<SuggestionsResponse> => {
    const res = await apiClient.get<SuggestionsResponse>('/assistant/suggestions');
    return res.data;
  },
};
