import React from 'react';
import { Phone, PhoneOff, Shield, Radio, Volume2, Sparkles } from 'lucide-react';
import { LanguageIndicator } from './LanguageIndicator';

interface CallScreenProps {
  isCallActive: boolean;
  callerPhone: string;
  setCallerPhone: (phone: string) => void;
  tollFreeNumber: string;
  detectedLanguage: string;
  languageConfidence?: number;
  onStartCall: () => void;
  onEndCall: () => void;
  isProcessing: boolean;
}

export const CallScreen: React.FC<CallScreenProps> = ({
  isCallActive,
  callerPhone,
  setCallerPhone,
  tollFreeNumber,
  detectedLanguage,
  languageConfidence,
  onStartCall,
  onEndCall,
  isProcessing,
}) => {
  return (
    <div
      style={{
        background: 'linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%)',
        color: '#FFFFFF',
        borderRadius: '1.25rem',
        padding: '1.5rem',
        boxShadow: '0 10px 25px -5px rgba(30, 58, 138, 0.25)',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '0.75rem',
              backgroundColor: 'rgba(255, 255, 255, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backdropFilter: 'blur(8px)',
            }}
          >
            <Shield size={24} className="text-white" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
                Toll-Free AI IVR Helpline
              </h1>
              <span
                style={{
                  padding: '0.15rem 0.5rem',
                  borderRadius: '9999px',
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                }}
              >
                2-Way Voice
              </span>
            </div>
            <p style={{ margin: 0, fontSize: '0.85rem', color: '#BFDBFE' }}>
              Tamil Nadu Citizen Grievance Redressal • Toll-Free: {tollFreeNumber}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <LanguageIndicator language={detectedLanguage} confidence={languageConfidence} />

          {isCallActive ? (
            <button
              type="button"
              onClick={onEndCall}
              disabled={isProcessing}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.55rem 1.25rem',
                borderRadius: '0.75rem',
                backgroundColor: '#EF4444',
                color: '#FFFFFF',
                fontWeight: 700,
                fontSize: '0.85rem',
                border: 'none',
                cursor: isProcessing ? 'not-allowed' : 'pointer',
                boxShadow: '0 4px 6px -1px rgba(239, 68, 68, 0.3)',
              }}
            >
              <PhoneOff size={16} />
              <span>End Call</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={onStartCall}
              disabled={isProcessing}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.55rem 1.5rem',
                borderRadius: '0.75rem',
                backgroundColor: '#10B981',
                color: '#FFFFFF',
                fontWeight: 800,
                fontSize: '0.85rem',
                border: 'none',
                cursor: isProcessing ? 'not-allowed' : 'pointer',
                boxShadow: '0 4px 6px -1px rgba(16, 185, 129, 0.3)',
              }}
            >
              <Phone size={16} />
              <span>Dial Toll-Free</span>
            </button>
          )}
        </div>
      </div>

      {!isCallActive && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '0.75rem 1rem',
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
            borderRadius: '0.75rem',
            backdropFilter: 'blur(4px)',
          }}
        >
          <span style={{ fontSize: '0.85rem', color: '#E0E7FF', fontWeight: 600 }}>Simulated Caller Phone:</span>
          <input
            type="text"
            value={callerPhone}
            onChange={(e) => setCallerPhone(e.target.value)}
            placeholder="+91 98430 98765"
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: '0.4rem',
              border: '1px solid rgba(255, 255, 255, 0.3)',
              backgroundColor: 'rgba(255, 255, 255, 0.15)',
              color: '#FFFFFF',
              fontSize: '0.85rem',
              fontWeight: 600,
              outline: 'none',
              width: '170px',
            }}
          />
          <span style={{ fontSize: '0.75rem', color: '#BFDBFE', marginLeft: 'auto' }}>
            Tamil / English / Tanglish auto-detected from first spoken turn
          </span>
        </div>
      )}
    </div>
  );
};
