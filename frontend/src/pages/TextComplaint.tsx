import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { analysisApi } from '../api/analysis';
import { AnalysisResult } from '../types';
import { Sparkles, ArrowRight, HelpCircle, MapPin } from 'lucide-react';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { AIProcessing } from './AIProcessing';

export const TextComplaint: React.FC = () => {
  const [text, setText] = useState('');
  const [locationHint, setLocationHint] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const presets = [
    {
      label: 'Tanglish (Water)',
      text: 'Gandhipuram bus stand pakkam thanni pipe odanju pochu, kudikka thanni varala romba waste aaguthu.',
    },
    {
      label: 'Tamil (Electricity Emergency)',
      text: 'பீளமேடு பகுதியில் மின்சார கம்பி அறுந்து விழுந்து தீப்பொறி பறக்கிறது. உயிருக்கு ஆபத்து.',
    },
    {
      label: 'English (Road Pothole)',
      text: 'Massive pothole near RS Puram junction causing severe traffic accidents and vehicle damage.',
    },
    {
      label: 'Tanglish (Garbage/Sanitation)',
      text: 'Ukkadam market kitta kuppai thotti romba naala alli podala, mosamana naaththam adikuthu.',
    }
  ];

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || text.trim().length < 5) {
      setError('Please provide at least 5 characters describing the issue.');
      return;
    }

    setError(null);
    setIsAnalyzing(true);

    try {
      // Append location hint if provided
      const fullText = locationHint.trim() ? `${text} (Location: ${locationHint})` : text;
      const result = await analysisApi.analyzeText(fullText);
      setAnalysisResult(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to analyze text. Please check your backend connection.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (analysisResult) {
    return (
      <AIProcessing
        analysis={analysisResult}
        onReset={() => setAnalysisResult(null)}
        source="WEB_TEXT"
      />
    );
  }

  return (
    <div className="glass-card animate-fade-in" style={{ padding: '2rem' }}>
      <form onSubmit={handleAnalyze}>
        {error && <ErrorMessage message={error} />}

        {/* Quick Example Presets */}
        <div style={{ marginBottom: '1.25rem' }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.4rem' }}>
            Quick Test Examples (Click to Autofill):
          </label>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {presets.map((p, idx) => (
              <button
                key={idx}
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setText(p.text)}
                style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="complaint-text">
            Describe Your Complaint (Tamil, English, or Tanglish) *
          </label>
          <textarea
            id="complaint-text"
            className="form-textarea"
            rows={5}
            required
            placeholder="e.g. Gandhipuram-la thanni pipe odanju pochu / சாலையில் பெரிய பள்ளம் உள்ளது / Streetlight broken in Anna Nagar..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="location-hint">
            Specific Street / Area Landmark (Optional)
          </label>
          <div style={{ position: 'relative' }}>
            <input
              id="location-hint"
              type="text"
              className="form-input"
              placeholder="e.g. Near Gandhipuram Bus Stand, Peelamedu, T Nagar..."
              value={locationHint}
              onChange={(e) => setLocationHint(e.target.value)}
              style={{ paddingLeft: '2.5rem' }}
            />
            <MapPin size={16} color="#64748b" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.25rem', display: 'block' }}>
            Our AI will automatically extract Tamil Nadu locations if included in the description.
          </span>
        </div>

        <button
          type="submit"
          className="btn btn-primary"
          style={{ width: '100%', marginTop: '0.5rem' }}
          disabled={isAnalyzing}
        >
          {isAnalyzing ? (
            'Analyzing with AI...'
          ) : (
            <>
              <Sparkles size={16} /> Analyze Complaint with AI <ArrowRight size={16} />
            </>
          )}
        </button>
      </form>
    </div>
  );
};
