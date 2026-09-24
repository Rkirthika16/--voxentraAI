// Web Audio API Telephony Sound Synthesizer (0 external assets required)
class TelephonyAudioService {
  private ctx: AudioContext | null = null;
  private ringOsc1: OscillatorNode | null = null;
  private ringOsc2: OscillatorNode | null = null;
  private ringGain: GainNode | null = null;
  private ringInterval: any = null;

  private getContext(): AudioContext {
    if (!this.ctx || this.ctx.state === 'closed') {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      this.ctx = new AudioCtx();
    }
    if (this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
    return this.ctx;
  }

  // DTMF Frequencies: [Row Hz, Col Hz]
  private dtmfFrequencies: Record<string, [number, number]> = {
    '1': [697, 1209],
    '2': [697, 1336],
    '3': [697, 1477],
    '4': [770, 1209],
    '5': [770, 1336],
    '6': [770, 1477],
    '7': [852, 1209],
    '8': [852, 1336],
    '9': [852, 1477],
    '*': [941, 1209],
    '0': [941, 1336],
    '#': [941, 1477],
  };

  playDtmf(digit: string, durationMs: number = 180): void {
    try {
      const freqs = this.dtmfFrequencies[digit];
      if (!freqs) return;

      const ctx = this.getContext();
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gainNode = ctx.createGain();

      osc1.frequency.value = freqs[0];
      osc2.frequency.value = freqs[1];

      gainNode.gain.setValueAtTime(0.12, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + durationMs / 1000);

      osc1.connect(gainNode);
      osc2.connect(gainNode);
      gainNode.connect(ctx.destination);

      osc1.start();
      osc2.start();

      osc1.stop(ctx.currentTime + durationMs / 1000);
      osc2.stop(ctx.currentTime + durationMs / 1000);
    } catch {
      // Audio playback fails gracefully if muted
    }
  }

  startRinging(): void {
    this.stopRinging();
    try {
      const ctx = this.getContext();
      const playBurst = () => {
        try {
          const osc1 = ctx.createOscillator();
          const osc2 = ctx.createOscillator();
          const gain = ctx.createGain();

          osc1.frequency.value = 400; // India/UK ring standard
          osc2.frequency.value = 450;

          gain.gain.setValueAtTime(0.1, ctx.currentTime);
          gain.gain.setValueAtTime(0.1, ctx.currentTime + 1.2);
          gain.gain.linearRampToValueAtTime(0.0001, ctx.currentTime + 1.25);

          osc1.connect(gain);
          osc2.connect(gain);
          gain.connect(ctx.destination);

          osc1.start();
          osc2.start();
          osc1.stop(ctx.currentTime + 1.3);
          osc2.stop(ctx.currentTime + 1.3);
        } catch {
          // Ignore
        }
      };

      playBurst();
      this.ringInterval = setInterval(playBurst, 3000);
    } catch {
      // Ignore
    }
  }

  stopRinging(): void {
    if (this.ringInterval) {
      clearInterval(this.ringInterval);
      this.ringInterval = null;
    }
  }

  playCallConnected(): void {
    this.stopRinging();
    try {
      const ctx = this.getContext();
      const now = ctx.currentTime;

      // Pleasant 2-tone connect chime (523Hz -> 659Hz)
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.frequency.setValueAtTime(523.25, now); // C5
      osc.frequency.setValueAtTime(659.25, now + 0.12); // E5

      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.35);
    } catch {
      // Ignore
    }
  }

  playHangup(): void {
    this.stopRinging();
    try {
      const ctx = this.getContext();
      const now = ctx.currentTime;

      // 3 fast busy beeps (425Hz)
      [0, 0.22, 0.44].forEach((offset) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = 425;
        gain.gain.setValueAtTime(0.15, now + offset);
        gain.gain.setValueAtTime(0.001, now + offset + 0.15);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + offset);
        osc.stop(now + offset + 0.16);
      });
    } catch {
      // Ignore
    }
  }
}

export const telephonyAudio = new TelephonyAudioService();
