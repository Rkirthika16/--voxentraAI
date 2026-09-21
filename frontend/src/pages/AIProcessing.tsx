import React, { useState } from 'react';
import { AnalysisResult } from '../types';
import { ConfirmationPage } from './ConfirmationPage';
import { PriorityBadge } from '../components/PriorityBadge';
import {
  Sparkles,
  MapPin,
  Building2,
  AlertTriangle,
  Globe,
  FileCheck,
  RotateCcw,
  ArrowRight,
  Info
} from 'lucide-react';

interface AIProcessingProps {
  analysis: AnalysisResult;
  onReset: () => void;
  source: string;
}

export const AIProcessing: React.FC<AIProcessingProps> = ({ analysis, onReset, source }) => {
  const [isConfirming, setIsConfirming] = useState(false);

  if (isConfirming) {
    return (
      <ConfirmationPage
        initialAnalysis={analysis}
        onBack={() => setIsConfirming(false)}
        source={source}
      />
    );
  }

  return (
    <div className="glass-card animate-fade-in" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Sparkles size={20} color="#3b82f6" />
          <h3 style={{ fontSize: '1.25rem' }}>AI Complaint Analysis</h3>
        </div>
        <span
          style={{
            fontSize: '0.75rem',
            background: 'rgba(59, 130, 246, 0.15)',
            color: '#60a5fa',
            padding: '0.2rem 0.65rem',
            borderRadius: 'var(--radius-full)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            textTransform: 'uppercase',
            fontWeight: 600,
          }}
        >
          Method: {analysis.analysis_method}
        </span>
      </div>

      {/* Warnings & Suggestions */}
      {analysis.warnings && analysis.warnings.length > 0 && (
        <div
          style={{
            background: 'rgba(245, 158, 11, 0.1)',
            border: '1px solid rgba(245, 158, 11, 0.3)',
            borderRadius: 'var(--radius-md)',
            padding: '0.85rem 1.25rem',
            color: '#fbbf24',
            fontSize: '0.85rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600, marginBottom: '0.35rem' }}>
            <AlertTriangle size={16} /> AI Verification Recommendations
          </div>
          <ul style={{ paddingLeft: '1.25rem', margin: 0 }}>
            {analysis.warnings.map((w, idx) => (
              <li key={idx} style={{ marginTop: '0.2rem' }}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Extracted Details Grid */}
      <div className="grid-2">
        {/* Category & Department */}
        <div style={{ background: 'var(--bg-input)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '0.3rem' }}>
            Detected Category & Department
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.25rem' }}>
            {analysis.category}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem', color: '#a78bfa' }}>
            <Building2 size={14} />
            <span>{analysis.suggested_department}</span>
          </div>
        </div>

        {/* Priority & Language */}
        <div style={{ background: 'var(--bg-input)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '0.3rem' }}>
            Assessed Priority & Language
          </div>
          <div style={{ marginBottom: '0.4rem' }}>
            <PriorityBadge priority={analysis.priority} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem', color: '#38bdf8' }}>
            <Globe size={14} />
            <span>Detected Language: {analysis.detected_language}</span>
          </div>
        </div>
      </div>

      {/* Location */}
      <div style={{ background: 'var(--bg-input)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '0.3rem' }}>
          Extracted Location & Coordinates
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem', fontWeight: 600, color: 'var(--text-main)' }}>
          <MapPin size={16} color="#38bdf8" />
          <span>{analysis.extracted_location || 'Not specifically detected (You can add manually in next step)'}</span>
        </div>
        {analysis.latitude && analysis.longitude && (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            GPS Coordinates: {analysis.latitude}, {analysis.longitude}
          </div>
        )}
      </div>

      {/* Summary */}
      <div style={{ background: 'rgba(15, 23, 42, 0.7)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '0.3rem' }}>
          AI Structured Summary
        </div>
        <p style={{ color: 'var(--text-main)', fontSize: '0.95rem', lineHeight: '1.4' }}>
          {analysis.summary}
        </p>
      </div>

      {/* Navigation Buttons */}
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
        <button type="button" onClick={onReset} className="btn btn-secondary">
          <RotateCcw size={16} /> Edit Original Input
        </button>

        <button type="button" onClick={() => setIsConfirming(true)} className="btn btn-primary">
          <FileCheck size={16} /> Review & Confirm Submission <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
};
