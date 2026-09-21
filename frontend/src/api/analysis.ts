import { apiClient } from './client';
import { AnalysisResult, AudioPredictionResponse } from '../types';

export const analysisApi = {
  analyzeText: async (text: string, languageHint?: string): Promise<AnalysisResult> => {
    const res = await apiClient.post<AnalysisResult>('/analysis/text', {
      text,
      language_hint: languageHint,
    });
    return res.data;
  },

  analyzeAudio: async (audioBlob: Blob, filename = 'voice_recording.webm'): Promise<AnalysisResult> => {
    const formData = new FormData();
    formData.append('file', audioBlob, filename);

    const res = await apiClient.post<AnalysisResult>('/analysis/audio', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  predictAudio: async (
    audioBlob: Blob,
    filename = 'voice_recording.wav',
    languageHint?: string,
    transcriptionOverride?: string
  ): Promise<AudioPredictionResponse> => {
    const formData = new FormData();
    formData.append('file', audioBlob, filename);
    if (languageHint) formData.append('language_hint', languageHint);
    if (transcriptionOverride) formData.append('transcription_override', transcriptionOverride);

    const res = await apiClient.post<AudioPredictionResponse>('/analysis/audio-prediction', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  transcribeAudio: async (audioBlob: Blob, filename = 'voice_recording.webm') => {
    const formData = new FormData();
    formData.append('file', audioBlob, filename);

    const res = await apiClient.post('/audio/transcribe', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  getSpeechStatus: async () => {
    const res = await apiClient.get('/audio/status');
    return res.data;
  }
};

