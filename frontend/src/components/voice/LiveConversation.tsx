import React, { useRef, useEffect } from 'react';
import { ConversationMessage, MessageItem } from './ConversationMessage';
import { Sparkles, Bot } from 'lucide-react';

interface LiveConversationProps {
  messages: MessageItem[];
  isAiResponding: boolean;
  onPlayAudio?: (text: string, lang?: string) => void;
}

export const LiveConversation: React.FC<LiveConversationProps> = ({
  messages,
  isAiResponding,
  onPlayAudio
}) => {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAiResponding]);

  if (messages.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '3rem 1.5rem',
          textAlign: 'center',
          color: 'var(--text-muted)',
          border: '1px dashed var(--border-color)',
          borderRadius: 'var(--radius-lg)',
        }}
      >
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '50%',
            background: 'rgba(99, 102, 241, 0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '1rem',
            color: '#818cf8',
          }}
        >
          <Bot className="w-8 h-8" />
        </div>
        <h3 style={{ margin: '0 0 0.5rem 0', color: 'var(--text-primary)', fontSize: '1.15rem' }}>
          Speak First — Natural Multi-Turn Voice Assistant
        </h3>
        <p style={{ margin: 0, fontSize: '0.9rem', maxWidth: '420px', lineHeight: 1.5 }}>
          Speak freely in <strong>Tamil</strong>, <strong>English</strong>, or <strong>Tanglish</strong>. No language selection or static form required.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        maxHeight: '440px',
        overflowY: 'auto',
        padding: '1rem',
        background: 'var(--bg-primary)',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-lg)',
      }}
    >
      {messages.map((msg) => (
        <ConversationMessage key={msg.id} message={msg} onPlayAudio={onPlayAudio} />
      ))}

      {isAiResponding && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#818cf8', fontSize: '0.85rem', padding: '0.5rem' }}>
          <Sparkles className="w-4 h-4 animate-spin" />
          <span>VoxentraAI is analyzing your complaint...</span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
