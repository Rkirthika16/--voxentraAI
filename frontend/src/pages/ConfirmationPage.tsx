import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnalysisResult, ComplaintPriority, Complaint } from '../types';
import { complaintsApi } from '../api/complaints';
import { ComplaintSuccess } from './ComplaintSuccess';
import { ErrorMessage } from '../components/ErrorMessage';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { CheckCircle, ArrowLeft, Shield, MapPin, Tag, AlertTriangle } from 'lucide-react';

interface ConfirmationPageProps {
  initialAnalysis: AnalysisResult;
  onBack: () => void;
  source: string;
}

const CATEGORIES = [
  'Water',
  'Electricity',
  'Roads',
  'Sanitation/Garbage',
  'Drainage',
  'Streetlights',
  'Public Safety',
  'Other',
];

export const ConfirmationPage: React.FC<ConfirmationPageProps> = ({ initialAnalysis, onBack, source }) => {
  const [title, setTitle] = useState(
    initialAnalysis.summary || `${initialAnalysis.category} issue reported`
  );
  const [description, setDescription] = useState(
    initialAnalysis.original_text || initialAnalysis.transcription || ''
  );
  const [category, setCategory] = useState(initialAnalysis.category || 'Other');
  const [location, setLocation] = useState(initialAnalysis.extracted_location || '');
  const [latitude, setLatitude] = useState(initialAnalysis.latitude || '');
  const [longitude, setLongitude] = useState(initialAnalysis.longitude || '');
  const [priority, setPriority] = useState<ComplaintPriority>(initialAnalysis.priority || 'MEDIUM');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedComplaint, setSubmittedComplaint] = useState<Complaint | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const result = await complaintsApi.createComplaint({
        title,
        description,
        category,
        location: location.trim() || undefined,
        latitude: latitude.trim() || undefined,
        longitude: longitude.trim() || undefined,
        priority,
        language: initialAnalysis.detected_language,
        source: source as any,
        ai_metadata: {
          analysis_method: initialAnalysis.analysis_method,
          detected_language: initialAnalysis.detected_language,
          normalized_text: initialAnalysis.normalized_text,
          metadata: initialAnalysis.metadata,
        },
        citizen_confirmed: true,
      });

      setSubmittedComplaint(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit complaint. Please check your backend connection.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submittedComplaint) {
    return <ComplaintSuccess complaint={submittedComplaint} />;
  }

  return (
    <div className="glass-card animate-fade-in" style={{ padding: '2rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
        <button type="button" onClick={onBack} className="btn btn-secondary btn-sm" style={{ padding: '0.4rem 0.6rem' }}>
          <ArrowLeft size={16} />
        </button>
        <div>
          <h2 style={{ fontSize: '1.4rem' }}>Review & Confirm Grievance</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Verify or correct the AI-extracted information before final department routing.
          </p>
        </div>
      </div>

      {error && <ErrorMessage message={error} />}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div className="form-group">
          <label className="form-label" htmlFor="conf-title">Complaint Title / Summary *</label>
          <input
            id="conf-title"
            type="text"
            required
            className="form-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="conf-desc">Complaint Description *</label>
          <textarea
            id="conf-desc"
            required
            className="form-textarea"
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div className="grid-2">
          <div className="form-group">
            <label className="form-label" htmlFor="conf-cat">Category & Department *</label>
            <select
              id="conf-cat"
              className="form-select"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="conf-pri">Priority / Urgency *</label>
            <select
              id="conf-pri"
              className="form-select"
              value={priority}
              onChange={(e) => setPriority(e.target.value as ComplaintPriority)}
            >
              <option value="LOW">Low Priority (Minor issue)</option>
              <option value="MEDIUM">Medium Priority (Standard grievance)</option>
              <option value="HIGH">High Priority (Urgent repair needed)</option>
              <option value="CRITICAL">Critical / Emergency (Life-safety hazard)</option>
            </select>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="conf-loc">Location / Landmark *</label>
          <div style={{ position: 'relative' }}>
            <input
              id="conf-loc"
              type="text"
              required
              className="form-input"
              placeholder="e.g. Gandhipuram Central Bus Stand, Coimbatore"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              style={{ paddingLeft: '2.5rem' }}
            />
            <MapPin size={16} color="#64748b" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
          </div>
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-lg"
          style={{ width: '100%', marginTop: '0.5rem', background: 'linear-gradient(135deg, #10b981, #059669)' }}
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <LoadingSpinner message="Registering grievance & generating tracking ID..." size="sm" />
          ) : (
            <>
              <CheckCircle size={18} /> Confirm & Register Grievance
            </>
          )}
        </button>
      </form>
    </div>
  );
};
