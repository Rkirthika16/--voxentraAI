import React from 'react';
import {
  PhoneCall,
  Mic,
  Volume2,
  Cpu,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Loader2,
  Clock
} from 'lucide-react';

interface ConversationStatusProps {
  state: string;
  isAiSpeaking: boolean;
  isRecording: boolean;
  isProcessing: boolean;
  callDuration: number;
}

export const ConversationStatus: React.FC<ConversationStatusProps> = ({
  state,
  isAiSpeaking,
  isRecording,
  isProcessing,
  callDuration,
}) => {
  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getStatusConfig = () => {
    if (state === 'COMPLETED') {
      return {
        label: 'Complaint Registered',
        icon: <CheckCircle2 size={16} className="text-emerald-500" />,
        bg: '#ECFDF5',
        text: '#065F46',
        border: '#10B981',
      };
    }
    if (state === 'ERROR') {
      return {
        label: 'Error Occurred',
        icon: <AlertCircle size={16} className="text-red-500" />,
        bg: '#FEF2F2',
        text: '#991B1B',
        border: '#EF4444',
      };
    }
    if (isAiSpeaking) {
      return {
        label: 'AI Speaking (Mic Off)',
        icon: <Volume2 size={16} className="animate-pulse text-indigo-500" />,
        bg: '#EEF2FF',
        text: '#3730A3',
        border: '#6366F1',
      };
    }
    if (isProcessing) {
      return {
        label: 'Transcribing & Understanding...',
        icon: <Loader2 size={16} className="animate-spin text-amber-500" />,
        bg: '#FFFBEB',
        text: '#92400E',
        border: '#F59E0B',
      };
    }
    if (isRecording) {
      return {
        label: 'Citizen Speaking (Recording)',
        icon: <Mic size={16} className="animate-pulse text-red-500" />,
        bg: '#FEF2F2',
        text: '#991B1B',
        border: '#EF4444',
      };
    }
    if (state === 'CONFIRMING') {
      return {
        label: 'Awaiting Final Confirmation',
        icon: <HelpCircle size={16} className="text-amber-500" />,
        bg: '#FFFBEB',
        text: '#B45309',
        border: '#F59E0B',
      };
    }
    if (state === 'WAITING_FOR_CITIZEN' || state === 'COLLECTING') {
      return {
        label: 'Listening for Citizen',
        icon: <Mic size={16} className="text-emerald-500" />,
        bg: '#ECFDF5',
        text: '#065F46',
        border: '#10B981',
      };
    }
    return {
      label: 'Connected',
      icon: <PhoneCall size={16} className="text-blue-500" />,
      bg: '#EFF6FF',
      text: '#1E40AF',
      border: '#3B82F6',
    };
  };

  const status = getStatusConfig();

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.6rem 1rem',
        borderRadius: '0.75rem',
        backgroundColor: '#FFFFFF',
        border: '1px solid #E2E8F0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.3rem 0.75rem',
            borderRadius: '9999px',
            backgroundColor: status.bg,
            color: status.text,
            border: `1px solid ${status.border}`,
            fontSize: '0.8rem',
            fontWeight: 700,
          }}
        >
          {status.icon}
          <span>{status.label}</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#64748B', fontSize: '0.85rem', fontWeight: 600 }}>
        <Clock size={15} />
        <span>{formatTime(callDuration)}</span>
      </div>
    </div>
  );
};
