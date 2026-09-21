import React, { useState, useEffect } from 'react';
import { analysisApi } from '../api/analysis';
import { AnalysisResult, AudioPredictionResponse } from '../types';
import { AudioRecorder } from '../components/AudioRecorder';
import { AIProcessing } from './AIProcessing';
import { ErrorMessage } from '../components/ErrorMessage';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Sparkles, Mic, Info, Cpu, Flame, Activity, Waves, Building2 } from 'lucide-react';

export const VoiceComplaint: React.FC = () => {
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioFilename, setAudioFilename] = useState<string>('voice_recording.webm');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [audioPrediction, setAudioPrediction] = useState<AudioPredictionResponse | null>(null);
  const [speechStatus, setSpeechStatus] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    analysisApi.getSpeechStatus()
      .then((status) => setSpeechStatus(status))
      .catch(() => {});
  }, []);

  const handleAudioReady = async (blob: Blob, filename?: string) => {
    setAudioBlob(blob);
    if (filename) setAudioFilename(filename);
    setError(null);

    // Run quick audio prediction in background
    try {
      const pred = await analysisApi.predictAudio(blob, filename || 'voice_recording.wav');
      setAudioPrediction(pred);
    } catch (e) {
      console.warn('Voice preview prediction note:', e);
    }
  };

  const handleClear = () => {
    setAudioBlob(null);
    setAnalysisResult(null);
    setAudioPrediction(null);
    setError(null);
  };

  const handleAnalyzeAudio = async () => {
    if (!audioBlob) {
      setError('Please record audio or upload an audio file first.');
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    try {
      const result = await analysisApi.analyzeAudio(audioBlob, audioFilename);
      setAnalysisResult(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Audio processing failed. You can also type your complaint.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (analysisResult) {
    return (
      <AIProcessing
        analysis={analysisResult}
        onReset={handleClear}
        source="WEB_VOICE"
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Speech Engine Status Info */}
      <div
        style={{
          background: 'rgba(59, 130, 246, 0.08)',
          border: '1px solid rgba(59, 130, 246, 0.25)',
          borderRadius: 'var(--radius-md)',
          padding: '0.85rem 1.25rem',
          fontSize: '0.85rem',
          color: 'var(--text-muted)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Info size={16} color="#38bdf8" />
          <span>
            Speech Engine: <strong>{speechStatus?.engine || 'Local / Whisper'}</strong> (
            {speechStatus?.available ? (
              <span style={{ color: '#34d399' }}>Active & Ready</span>
            ) : (
              <span style={{ color: '#fbbf24' }}>Deterministic Fallback AI Available</span>
            )}
            )
          </span>
        </div>
        <span style={{ fontSize: '0.75rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <Cpu size={14} /> Multimodal Audio Prediction Active
        </span>
      </div>

      {error && <ErrorMessage message={error} />}

      <AudioRecorder
        onAudioReady={handleAudioReady}
        onClear={handleClear}
        isProcessing={isAnalyzing}
      />

      {/* Audio Prediction Diagnostic Preview Card */}
      {audioPrediction && (
        <div
          className="glass-card animate-fade-in"
          style={{
            padding: '1.25rem',
            background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.7))',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            borderRadius: 'var(--radius-lg)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Waves size={16} /> Instant Audio Prediction
            </span>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                padding: '0.2rem 0.6rem',
                borderRadius: 'var(--radius-full)',
                background: audioPrediction.urgency_score >= 80 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                color: audioPrediction.urgency_score >= 80 ? '#f87171' : '#60a5fa',
              }}
            >
              <Flame size={12} style={{ display: 'inline', marginRight: '3px' }} />
              Urgency: {audioPrediction.urgency_score}%
            </span>
          </div>

          <div className="grid-3" style={{ gap: '0.75rem', fontSize: '0.8rem' }}>
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>Predicted Category</span>
              <strong style={{ color: '#e2e8f0' }}>{audioPrediction.predicted_category}</strong>
            </div>
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>Distress Emotion</span>
              <strong style={{ color: '#fbbf24' }}>{audioPrediction.distress_level.replace(/_/g, ' ')}</strong>
            </div>
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>Acoustic Metrics</span>
              <span style={{ color: '#34d399' }}>{audioPrediction.acoustic_metrics.rms_energy_db} dBFS • {audioPrediction.acoustic_metrics.noise_profile.replace(/_/g, ' ')}</span>
            </div>
          </div>
        </div>
      )}

      {audioBlob && (
        <button
          onClick={handleAnalyzeAudio}
          className="btn btn-primary"
          style={{ width: '100%', padding: '0.85rem' }}
          disabled={isAnalyzing}
        >
          {isAnalyzing ? (
            <LoadingSpinner message="Transcribing speech & analyzing grievance..." size="sm" />
          ) : (
            <>
              <Sparkles size={16} /> Process Voice with AI Pipeline
            </>
          )}
        </button>
      )}
    </div>
  );
};
