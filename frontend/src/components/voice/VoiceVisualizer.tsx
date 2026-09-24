import React from 'react';

interface VoiceVisualizerProps {
  isActive: boolean;
  isAiSpeaking: boolean;
}

export const VoiceVisualizer: React.FC<VoiceVisualizerProps> = ({ isActive, isAiSpeaking }) => {
  const bars = [16, 28, 42, 60, 36, 50, 68, 40, 24, 48, 64, 32];

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '4px',
        height: '40px',
        padding: '0.25rem 1rem',
      }}
    >
      {bars.map((height, i) => {
        let currentHeight = 6;
        if (isActive) {
          currentHeight = Math.max(8, (height * (0.4 + (i % 3) * 0.3)));
        } else if (isAiSpeaking) {
          currentHeight = Math.max(10, (height * (0.6 + (i % 2) * 0.2)));
        }

        const barColor = isActive
          ? '#ef4444'
          : isAiSpeaking
          ? '#10b981'
          : 'var(--text-muted)';

        return (
          <div
            key={i}
            style={{
              width: '4px',
              height: `${currentHeight}px`,
              backgroundColor: barColor,
              borderRadius: '2px',
              transition: 'height 0.15s ease, background-color 0.2s ease',
            }}
          />
        );
      })}
    </div>
  );
};
