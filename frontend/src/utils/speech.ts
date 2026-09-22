/**
 * VoxentraAI Advanced Multilingual Audio & Speech Controller
 * - Real Multilingual Text-to-Speech (Tamil, Hindi, English, Tanglish)
 * - Automatic Phonetic Fallback for Windows without Tamil OS pack
 * - Reliable Telephony Sound Effects (Ringtone, DTMF, IVR Beep, Success Chimes)
 * - Real-time High Accuracy Speech Recognition (Tamil & English)
 */

export interface TTSOptions {
  language?: 'Tamil' | 'Hindi' | 'English' | 'Tanglish' | 'ta-IN' | 'hi-IN' | 'en-IN' | string;
  rate?: number;     // 0.8 to 1.2
  pitch?: number;    // 0.8 to 1.2
  volume?: number;   // 0 to 1
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (err: any) => void;
}

class SpeechController {
  private synth: SpeechSynthesis | null = null;
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private voices: SpeechSynthesisVoice[] = [];
  private audioCtx: AudioContext | null = null;
  private ringOscillators: OscillatorNode[] = [];
  private ringInterval: any = null;

  // DTMF Frequency standard matrix
  private dtmfFrequencies: { [key: string]: [number, number] } = {
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

  constructor() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      this.synth = window.speechSynthesis;
      this.loadVoices();
      if (this.synth.onvoiceschanged !== undefined) {
        this.synth.onvoiceschanged = () => this.loadVoices();
      }
    }
  }

  private getAudioContext(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    if (!this.audioCtx) {
      const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtxClass) {
        this.audioCtx = new AudioCtxClass();
      }
    }
    if (this.audioCtx && this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }
    return this.audioCtx;
  }

  private loadVoices() {
    if (!this.synth) return;
    this.voices = this.synth.getVoices();
  }

  public isTTSSupported(): boolean {
    return typeof window !== 'undefined' && 'speechSynthesis' in window;
  }

  public isSTTSupported(): boolean {
    return (
      typeof window !== 'undefined' &&
      ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)
    );
  }

  public getVoices(): SpeechSynthesisVoice[] {
    if (this.voices.length === 0 && this.synth) {
      this.voices = this.synth.getVoices();
    }
    return this.voices;
  }

  public hasTamilVoice(): boolean {
    const voices = this.getVoices();
    return voices.some(
      (v) =>
        v.lang.startsWith('ta') ||
        v.name.toLowerCase().includes('tamil') ||
        v.name.toLowerCase().includes('valluvar')
    );
  }

  private cleanTextForSpeech(text: string): string {
    if (!text) return '';
    return text
      .replace(/[*#_`~>]/g, '') // remove markdown symbols
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // replace markdown links with text
      .replace(/VOX-\d{4}-\d+/gi, (m) => m.replace(/-/g, ' '))
      .replace(/\s+/g, ' ')
      .trim();
  }

  private selectVoiceForLanguage(lang: string, hasTamilScript = false): { voice: SpeechSynthesisVoice | null; targetLang: string } {
    const voices = this.getVoices();
    const l = (lang || '').toLowerCase();

    // 1. TAMIL (தமிழ்) - explicit or auto-detected from Tamil script
    if (hasTamilScript || l.includes('tamil') || l.includes('ta')) {
      const tamilVoice = voices.find(
        (v) =>
          v.lang.toLowerCase().startsWith('ta') ||
          v.name.toLowerCase().includes('tamil') ||
          v.name.toLowerCase().includes('valluvar') ||
          v.name.toLowerCase().includes('pallava') ||
          v.name.toLowerCase().includes('tamizh')
      );
      return { voice: tamilVoice || null, targetLang: 'ta-IN' };
    }

    // 2. HINDI (हिन्दी)
    if (l.includes('hindi') || l.includes('hi')) {
      const hindiVoice = voices.find(
        (v) =>
          v.lang.toLowerCase().startsWith('hi') ||
          v.name.toLowerCase().includes('hindi') ||
          v.name.toLowerCase().includes('hemant') ||
          v.name.toLowerCase().includes('kalpana') ||
          v.name.toLowerCase().includes('swara') ||
          v.name.toLowerCase().includes('madhur')
      );
      return { voice: hindiVoice || null, targetLang: 'hi-IN' };
    }

    // 3. TANGLISH / INDIAN ENGLISH
    if (l.includes('tanglish') || l.includes('en-in') || l.includes('india')) {
      const indianVoice = voices.find(
        (v) =>
          v.lang === 'en-IN' ||
          v.name.toLowerCase().includes('india') ||
          v.name.toLowerCase().includes('ravi') ||
          v.name.toLowerCase().includes('heera') ||
          v.name.toLowerCase().includes('neerja') ||
          v.name.toLowerCase().includes('prabhat')
      );
      return { voice: indianVoice || null, targetLang: 'en-IN' };
    }

    // 4. NATURAL ENGLISH
    const generalEnglish = voices.find(
      (v) =>
        v.lang.startsWith('en') &&
        (v.name.toLowerCase().includes('natural') ||
          v.name.toLowerCase().includes('google') ||
          v.name.toLowerCase().includes('siri') ||
          v.name.toLowerCase().includes('samantha') ||
          v.name.toLowerCase().includes('zira') ||
          v.name.toLowerCase().includes('david') ||
          v.name.toLowerCase().includes('jenny'))
    );
    if (generalEnglish) return { voice: generalEnglish, targetLang: 'en-US' };

    return { voice: voices[0] || null, targetLang: 'en-US' };
  }

  private resumeInterval: any = null;

  public unlock(): void {
    if (typeof window === 'undefined') return;
    try {
      const ctx = this.getAudioContext();
      if (ctx && ctx.state === 'suspended') {
        ctx.resume();
      }
      if (this.synth) {
        if (this.synth.paused) {
          this.synth.resume();
        }
      }
    } catch (e) {}
  }

  /**
   * Speaks out the text clearly in the requested language (Tamil, Hindi, English, Tanglish).
   */
  public speak(text: string, options: TTSOptions = {}): void {
    if (!this.synth || !text) return;

    this.unlock();

    // Clear previous keep-alive interval
    if (this.resumeInterval) {
      clearInterval(this.resumeInterval);
      this.resumeInterval = null;
    }

    // Cancel previous speech safely
    try {
      this.synth.cancel();
      if (this.synth.paused) {
        this.synth.resume();
      }
    } catch (e) {}

    setTimeout(() => {
      if (!this.synth) return;

      const textToSpeak = this.cleanTextForSpeech(text);
      if (!textToSpeak) return;

      const hasTamilScript = /[\u0B80-\u0BFF]/.test(textToSpeak);
      const hasHindiScript = /[\u0900-\u097F]/.test(textToSpeak);

      let effectiveLang = options.language || 'English';
      if (hasTamilScript) {
        effectiveLang = 'Tamil';
      } else if (hasHindiScript) {
        effectiveLang = 'Hindi';
      }

      const { voice, targetLang } = this.selectVoiceForLanguage(effectiveLang, hasTamilScript);

      const utterance = new SpeechSynthesisUtterance(textToSpeak);
      this.currentUtterance = utterance;
      // Anchor to window to prevent Chromium garbage collection bug
      (window as any).__voxentra_utterance = utterance;

      // Assign voice and exact BCP 47 language tag
      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang || targetLang;
      } else {
        utterance.lang = targetLang;
      }

      utterance.rate = options.rate ?? (effectiveLang === 'Tamil' ? 0.90 : 0.95);
      utterance.pitch = options.pitch ?? 1.0;
      utterance.volume = options.volume ?? 1.0;

      utterance.onstart = () => {
        if (this.resumeInterval) clearInterval(this.resumeInterval);
        this.resumeInterval = setInterval(() => {
          if (this.synth && this.synth.speaking) {
            this.synth.resume();
          }
        }, 1500);

        if (options.onStart) options.onStart();
      };

      utterance.onend = () => {
        if (this.resumeInterval) {
          clearInterval(this.resumeInterval);
          this.resumeInterval = null;
        }
        this.currentUtterance = null;
        (window as any).__voxentra_utterance = null;
        if (options.onEnd) options.onEnd();
      };

      utterance.onerror = (err) => {
        if (this.resumeInterval) {
          clearInterval(this.resumeInterval);
          this.resumeInterval = null;
        }
        this.currentUtterance = null;
        (window as any).__voxentra_utterance = null;
        console.warn('TTS speak error:', err);

        // Fallback: If browser failed due to language-unavailable, retry with default system voice
        if (err && (err as any).error === 'language-unavailable' && targetLang !== 'en-US') {
          try {
            const fallbackUtt = new SpeechSynthesisUtterance(textToSpeak);
            fallbackUtt.lang = 'en-IN';
            fallbackUtt.rate = 0.95;
            this.synth?.speak(fallbackUtt);
          } catch (e) {}
        }

        if (options.onError) options.onError(err);
      };

      try {
        if (this.synth.paused) {
          this.synth.resume();
        }
        this.synth.speak(utterance);
        if (this.synth.paused) {
          this.synth.resume();
        }
      } catch (e) {
        console.warn('TTS speak error:', e);
      }
    }, 50);
  }

  public stop(): void {
    if (this.resumeInterval) {
      clearInterval(this.resumeInterval);
      this.resumeInterval = null;
    }
    if (this.synth) {
      try {
        this.synth.cancel();
        this.currentUtterance = null;
        (window as any).__voxentra_utterance = null;
      } catch (e) {}
    }
    this.stopRingTone();
  }

  public isSpeaking(): boolean {
    return !!(this.synth && this.synth.speaking);
  }

  // -------------------------------------------------------------
  // DTMF Telephone Keypad Audio Generator
  // -------------------------------------------------------------
  public playDTMF(digit: string, durationMs = 120): void {
    const ctx = this.getAudioContext();
    if (!ctx) return;

    const freqs = this.dtmfFrequencies[digit] || [800, 1300];
    try {
      const oscLow = ctx.createOscillator();
      const oscHigh = ctx.createOscillator();
      const gainNode = ctx.createGain();

      oscLow.type = 'sine';
      oscLow.frequency.setValueAtTime(freqs[0], ctx.currentTime);

      oscHigh.type = 'sine';
      oscHigh.frequency.setValueAtTime(freqs[1], ctx.currentTime);

      gainNode.gain.setValueAtTime(0.09, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + durationMs / 1000);

      oscLow.connect(gainNode);
      oscHigh.connect(gainNode);
      gainNode.connect(ctx.destination);

      oscLow.start(ctx.currentTime);
      oscHigh.start(ctx.currentTime);
      oscLow.stop(ctx.currentTime + durationMs / 1000);
      oscHigh.stop(ctx.currentTime + durationMs / 1000);
    } catch (e) {}
  }

  public playClearSound(): void {
    const ctx = this.getAudioContext();
    if (!ctx) return;
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(520, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(140, ctx.currentTime + 0.18);

      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.18);
    } catch (e) {}
  }

  public playNeonClick(): void {
    const ctx = this.getAudioContext();
    if (!ctx) return;
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(1400, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.06);

      gain.gain.setValueAtTime(0.07, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.06);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.06);
    } catch (e) {}
  }

  public playRingTone(durationSeconds = 2.5): void {
    this.stopRingTone();
    const ctx = this.getAudioContext();
    if (!ctx) return;

    const playPulse = () => {
      try {
        const osc1 = ctx.createOscillator();
        const osc2 = ctx.createOscillator();
        const gainNode = ctx.createGain();

        osc1.type = 'sine';
        osc2.type = 'sine';
        osc1.frequency.value = 440;
        osc2.frequency.value = 480;

        gainNode.gain.setValueAtTime(0.12, ctx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 1.2);

        osc1.connect(gainNode);
        osc2.connect(gainNode);
        gainNode.connect(ctx.destination);

        osc1.start(ctx.currentTime);
        osc2.start(ctx.currentTime);
        osc1.stop(ctx.currentTime + 1.2);
        osc2.stop(ctx.currentTime + 1.2);

        this.ringOscillators.push(osc1, osc2);
      } catch (e) {}
    };

    playPulse();
    this.ringInterval = setInterval(playPulse, 2000);

    setTimeout(() => {
      this.stopRingTone();
    }, durationSeconds * 1000);
  }

  public stopRingTone(): void {
    if (this.ringInterval) {
      clearInterval(this.ringInterval);
      this.ringInterval = null;
    }
    this.ringOscillators.forEach((osc) => {
      try {
        osc.stop();
        osc.disconnect();
      } catch (e) {}
    });
    this.ringOscillators = [];
  }

  public playBeep(): void {
    const ctx = this.getAudioContext();
    if (!ctx) return;
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(850, ctx.currentTime);
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.35);
    } catch (e) {}
  }

  public playConnectChime(): void {
    const ctx = this.getAudioContext();
    if (!ctx) return;
    try {
      const freqs = [523.25, 659.25, 783.99]; // C5, E5, G5 major triad
      freqs.forEach((freq, idx) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = freq;
        const startTime = ctx.currentTime + idx * 0.08;
        gain.gain.setValueAtTime(0.1, startTime);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.4);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(startTime);
        osc.stop(startTime + 0.4);
      });
    } catch (e) {}
  }

  public playSuccessChime(): void {
    const ctx = this.getAudioContext();
    if (!ctx) return;
    try {
      const notes = [587.33, 739.99, 880.0, 1174.66]; // D5, F#5, A5, D6
      notes.forEach((freq, idx) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = freq;
        const startTime = ctx.currentTime + idx * 0.09;
        gain.gain.setValueAtTime(0.12, startTime);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.5);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(startTime);
        osc.stop(startTime + 0.5);
      });
    } catch (e) {}
  }

  /**
   * Creates a robust browser SpeechRecognition instance with continuous stream & auto-transcription.
   */
  public createRecognition(
    lang: 'ta-IN' | 'hi-IN' | 'en-IN' | 'en-US' = 'ta-IN',
    onResult: (transcript: string, isFinal: boolean) => void,
    onError?: (err: any) => void,
    onEnd?: () => void
  ): any {
    if (!this.isSTTSupported()) return null;

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = lang;
    recognition.maxAlternatives = 1;

    let fullTranscript = '';

    recognition.onresult = (event: any) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          fullTranscript += ' ' + event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }

      const combined = (fullTranscript + ' ' + interim).trim();
      onResult(combined, false);
    };

    if (onError) recognition.onerror = onError;
    if (onEnd) {
      recognition.onend = () => {
        onResult(fullTranscript.trim(), true);
        onEnd();
      };
    }

    return recognition;
  }
}

export const speech = new SpeechController();
