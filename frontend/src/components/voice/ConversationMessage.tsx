import React from 'react';
import { Bot, User, Volume2 } from 'lucide-react';

export interface MessageItem {
  id: string;
  sender: 'ai' | 'citizen';
  text: string;
  language?: string;
  time: string;
  state?: string;
}

interface ConversationMessageProps {
  message: MessageItem;
  onPlayAudio?: (text: string, lang?: string) => void;
}

export const ConversationMessage: React.FC<ConversationMessageProps> = ({ message, onPlayAudio }) => {
  const isAi = message.sender === 'ai';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isAi ? 'flex-start' : 'flex-end',
        marginBottom: '1rem',
        width: '100%',
      }}
    >
      <div
        style={{
          display: 'flex',
          gap: '0.75rem',
          maxWidth: '85%',
          flexDirection: isAi ? 'row' : 'row-reverse',
        }}
      >
        <div
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: isAi ? 'linear-gradient(135deg, #6366f1, #4f46e5)' : 'linear-gradient(135deg, #10b981, #059669)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
            flexShrink: 0,
            boxShadow: isAi ? '0 0 12px rgba(99, 102, 241, 0.3)' : '0 0 12px rgba(16, 185, 129, 0.3)'
          }}
        >
          {isAi ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
        </div>

        <div
          style={{
            background: isAi ? 'var(--bg-secondary)' : 'linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(79, 70, 229, 0.25))',
            border: isAi ? '1px solid var(--border-color)' : '1px solid rgba(99, 102, 241, 0.4)',
            borderRadius: 'var(--radius-lg)',
            padding: '0.85rem 1.15rem',
            boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: isAi ? '#818cf8' : '#34d399' }}>
              {isAi ? 'VoxentraAI Assistant' : 'Citizen'}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              {message.language && (
                <span style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem', borderRadius: '4px', background: 'rgba(255, 255, 255, 0.05)', color: 'var(--text-muted)' }}>
                  {message.language}
                </span>
              )}
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                {message.time}
              </span>
            </div>
          </div>

          <p style={{ margin: 0, fontSize: '0.95rem', lineHeight: 1.5, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
            {message.text}
          </p>

          {isAi && onPlayAudio && (
            <div style={{ marginTop: '0.5rem', display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => onPlayAudio(message.text, message.language)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontSize: '0.75rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem'
                }}
                title="Listen to audio"
              >
                <Volume2 className="w-3.5 h-3.5" />
                <span>Play Voice</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
