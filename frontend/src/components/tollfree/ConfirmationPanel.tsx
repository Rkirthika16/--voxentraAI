import React from 'react';
import { CheckCircle2, XCircle, AlertCircle, Sparkles } from 'lucide-react';
import { TollFreeMemory } from '../../api/tollfree';

interface ConfirmationPanelProps {
  memory: TollFreeMemory;
  onConfirm: () => void;
  onReject: () => void;
  isProcessing: boolean;
}

export const ConfirmationPanel: React.FC<ConfirmationPanelProps> = ({
  memory,
  onConfirm,
  onReject,
  isProcessing,
}) => {
  return (
    <div
      style={{
        padding: '1.25rem',
        borderRadius: '1rem',
        backgroundColor: '#FEFCE8',
        border: '2px solid #FDE047',
        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.85rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#854D0E', fontWeight: 700, fontSize: '0.95rem' }}>
        <AlertCircle size={18} className="text-yellow-600" />
        <span>Pre-Registration Confirmation Turn</span>
      </div>

      <p style={{ margin: 0, fontSize: '0.85rem', color: '#713F12', lineHeight: 1.4 }}>
        The AI has summarized the complaint details from your conversation. Please verify that all information is accurate before official registration into the municipal database.
      </p>

      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.25rem' }}>
        <button
          type="button"
          onClick={onConfirm}
          disabled={isProcessing}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            padding: '0.65rem 1rem',
            backgroundColor: '#16A34A',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '0.5rem',
            fontWeight: 700,
            fontSize: '0.85rem',
            cursor: isProcessing ? 'not-allowed' : 'pointer',
            opacity: isProcessing ? 0.7 : 1,
          }}
        >
          <CheckCircle2 size={16} />
          <span>Yes, Details Are Correct (Aama / Yes)</span>
        </button>

        <button
          type="button"
          onClick={onReject}
          disabled={isProcessing}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            padding: '0.65rem 1rem',
            backgroundColor: '#DC2626',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '0.5rem',
            fontWeight: 700,
            fontSize: '0.85rem',
            cursor: isProcessing ? 'not-allowed' : 'pointer',
            opacity: isProcessing ? 0.7 : 1,
          }}
        >
          <XCircle size={16} />
          <span>No, Make A Correction (Illa / No)</span>
        </button>
      </div>
    </div>
  );
};
