import React, { useEffect, useRef } from 'react';
import { Bot, User, Sparkles, Volume2, ShieldAlert } from 'lucide-react';
import { TollFreeMessage } from '../../api/tollfree';

interface LiveTranscriptProps {
  messages: TollFreeMessage[];
  isAiSpeaking: boolean;
  isProcessing: boolean;
}

export const LiveTranscript: React.FC<LiveTranscriptProps> = ({
  messages,
  isAiSpeaking,
  isProcessing,
}) => {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAiSpeaking, isProcessing]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '420px',
        backgroundColor: '#F8FAFC',
        borderRadius: '1rem',
        border: '1px solid #E2E8F0',
        overflow: 'hidden',
        boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.02)',
      }}
    >
      <div
        style={{
          padding: '0.75rem 1rem',
          backgroundColor: '#FFFFFF',
          borderBottom: '1px solid #E2E8F0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '0.9rem', color: '#1E293B' }}>
          <Sparkles size={16} className="text-indigo-600" />
          <span>Live Conversation Transcript</span>
        </div>
        <span style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 500 }}>
          {messages.length} messages
        </span>
      </div>

      <div
        style={{
          flex: 1,
          padding: '1rem',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.85rem',
        }}
      >
        {messages.length === 0 ? (
          <div
            style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#94A3B8',
              textAlign: 'center',
              padding: '1rem',
            }}
          >
            <Bot size={36} style={{ marginBottom: '0.5rem', opacity: 0.5 }} />
            <p style={{ fontSize: '0.9rem', fontWeight: 500 }}>Call connected. AI greeting incoming...</p>
          </div>
        ) : (
          messages.map((msg) => {
            const isCitizen = msg.role === 'citizen';
            return (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: isCitizen ? 'flex-end' : 'flex-start',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    marginBottom: '0.2rem',
                    fontSize: '0.75rem',
                    color: '#64748B',
                    fontWeight: 600,
                  }}
                >
                  {isCitizen ? (
                    <>
                      <span>Citizen</span>
                      <User size={13} />
                    </>
                  ) : (
                    <>
                      <Bot size={13} className="text-indigo-600" />
                      <span>VoxentraAI</span>
                    </>
                  )}
                  {msg.language && (
                    <span
                      style={{
                        padding: '0.1rem 0.4rem',
                        borderRadius: '0.25rem',
                        backgroundColor: '#E2E8F0',
                        fontSize: '0.7rem',
                        fontWeight: 600,
                      }}
                    >
                      {msg.language}
                    </span>
                  )}
                </div>

                <div
                  style={{
                    maxWidth: '85%',
                    padding: '0.75rem 1rem',
                    borderRadius: isCitizen ? '1rem 1rem 0.2rem 1rem' : '1rem 1rem 1rem 0.2rem',
                    backgroundColor: isCitizen ? '#2563EB' : '#FFFFFF',
                    color: isCitizen ? '#FFFFFF' : '#1E293B',
                    border: isCitizen ? 'none' : '1px solid #E2E8F0',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                    fontSize: '0.9rem',
                    lineHeight: '1.45',
                  }}
                >
                  <p style={{ margin: 0 }}>{msg.content}</p>

                  {/* Show raw vs normalized if available and different */}
                  {msg.normalized_content && msg.normalized_content !== msg.content && (
                    <div
                      style={{
                        marginTop: '0.4rem',
                        paddingTop: '0.4rem',
                        borderTop: isCitizen ? '1px solid rgba(255,255,255,0.2)' : '1px solid #F1F5F9',
                        fontSize: '0.75rem',
                        opacity: 0.9,
                      }}
                    >
                      <span style={{ fontWeight: 600 }}>Normalized: </span>
                      {msg.normalized_content}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {isProcessing && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#64748B', fontSize: '0.8rem', fontStyle: 'italic' }}>
            <span className="animate-spin inline-block w-3 h-3 border-2 border-indigo-500 border-t-transparent rounded-full" />
            <span>AI understanding citizen response...</span>
          </div>
        )}

        <div ref={scrollRef} />
      </div>
    </div>
  );
};
