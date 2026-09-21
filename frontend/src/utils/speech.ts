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

  private selectVoiceForLanguage(lang: string): { voice: SpeechSynthesisVoice | null; isFallback: boolean } {
    const voices = this.getVoices();
    const l = lang.toLowerCase();

    // 1. TAMIL (தமிழ்)
    if (l.includes('tamil') || l.includes('ta')) {
      const tamilVoice = voices.find(
        (v) =>
          v.lang.startsWith('ta') ||
          v.name.toLowerCase().includes('tamil') ||
          v.name.toLowerCase().includes('valluvar')
      );
      if (tamilVoice) return { voice: tamilVoice, isFallback: false };
    }

    // 2. HINDI (हिन्दी)
    if (l.includes('hindi') || l.includes('hi')) {
      const hindiVoice = voices.find(
        (v) =>
          v.lang.startsWith('hi') ||
          v.name.toLowerCase().includes('hindi') ||
          v.name.toLowerCase().includes('hemant') ||
          v.name.toLowerCase().includes('kalpana')
      );
      if (hindiVoice) return { voice: hindiVoice, isFallback: false };
    }

    // 3. INDIAN ENGLISH / TANGLISH
    const indianVoice = voices.find(
      (v) =>
        v.lang === 'en-IN' ||
        v.name.toLowerCase().includes('india') ||
        v.name.toLowerCase().includes('ravi') ||
        v.name.toLowerCase().includes('heera') ||
        v.name.toLowerCase().includes('neerja')
    );
    if (indianVoice) return { voice: indianVoice, isFallback: true };

    // 4. NATURAL ENGLISH
    const generalEnglish = voices.find(
      (v) =>
        v.lang.startsWith('en') &&
        (v.name.toLowerCase().includes('natural') ||
          v.name.toLowerCase().includes('google') ||
          v.name.toLowerCase().includes('siri') ||
          v.name.toLowerCase().includes('samantha') ||
          v.name.toLowerCase().includes('zira') ||
          v.name.toLowerCase().includes('david'))
    );
    if (generalEnglish) return { voice: generalEnglish, isFallback: true };

    return { voice: voices[0] || null, isFallback: true };
  }

  /**
   * Translates high-frequency Tamil status sentences to clean phonetic Tanglish
   * if the user's OS has no Tamil TTS engine installed, ensuring clear audio.
   */
  public getPhoneticTamilFallback(text: string): string {
    if (!text) return '';
    // If text already contains mostly latin characters, return as is
    const hasTamilScript = /[\u0B80-\u0BFF]/.test(text);
    if (!hasTamilScript) return text;

    // Common greetings & IVR responses converted to audible phonetic speech
    if (text.includes('வணக்கம்') && text.includes('நல்வரவு')) {
      return "Vanakkam! Welcome to Voxentra Tamil Nadu Government Toll-Free Civic Grievance Helpline. Please state your village problem or complaint now.";
    }

    if (text.includes('வெற்றிகரமாக பதிவு செய்யப்பட்டது') || text.includes('புகார் எண்') || text.includes('பதிவு செய்யப்பட்டது')) {
      // Extract complaint number if present
      const match = text.match(/VOX[-\s]\d{4}[-\s]\d+/i) || text.match(/VOX-\d+/i) || text.match(/\d{4,}/);
      const ticket = match ? match[0].replace(/-/g, ' ') : "";

      // Detect specific department mentioned
      let dept = "concerned civic department";
      if (text.includes("Street Lighting") || text.includes("தெருவிளக்கு") || text.includes("லைட்")) {
        dept = "Street Lighting Department";
      } else if (text.includes("Water Supply") || text.includes("குடிநீர்") || text.includes("தண்ணீர்")) {
        dept = "Water Supply and Sewage Department";
      } else if (text.includes("Electricity") || text.includes("மின்சாரம்") || text.includes("கரண்ட்")) {
        dept = "Electricity and Power Department";
      } else if (text.includes("Roads") || text.includes("சாலை") || text.includes("ரோடு")) {
        dept = "Roads and Transport Department";
      } else if (text.includes("Sanitation") || text.includes("குப்பை") || text.includes("தூய்மை")) {
        dept = "Sanitation and Solid Waste Department";
      } else if (text.includes("Drainage") || text.includes("சாக்கடை") || text.includes("வடிகால்")) {
        dept = "Drainage and Stormwater Department";
      } else if (text.includes("Public Safety") || text.includes("ரேஷன்") || text.includes("அவசரம்")) {
        dept = "Public Safety and Emergency Department";
      }

      return `Vanakkam. Your grievance has been registered successfully with Complaint ID ${ticket}, and assigned directly to the ${dept}. A confirmation SMS has been dispatched to your mobile.`;
    }

    return "Vanakkam. Your complaint has been received and routed to the municipal department.";
  }

  /**
   * Speaks out the text clearly in the requested language (Tamil, Hindi, English, Tanglish).
   */
  public speak(text: string, options: TTSOptions = {}): void {
    if (!this.synth || !text) return;

    // Cancel previous speech safely
    try {
      this.synth.cancel();
      if (this.synth.paused) {
        this.synth.resume();
      }
    } catch (e) {}

    setTimeout(() => {
      if (!this.synth) return;

      const lang = options.language || 'Tamil';
      const { voice, isFallback } = this.selectVoiceForLanguage(lang);

      let textToSpeak = this.cleanTextForSpeech(text);

      // If Tamil script is requested but browser has NO Tamil TTS voice, use audible phonetic speech
      if ((lang.toLowerCase().includes('ta') || lang.toLowerCase().includes('tamil')) && isFallback && /[\u0B80-\u0BFF]/.test(textToSpeak)) {
        textToSpeak = this.getPhoneticTamilFallback(textToSpeak);
      }

      const utterance = new SpeechSynthesisUtterance(textToSpeak);
      this.currentUtterance = utterance;

      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
      } else {
        utterance.lang = 'en-IN';
      }

      utterance.rate = options.rate ?? 0.95;
      utterance.pitch = options.pitch ?? 1.0;
      utterance.volume = options.volume ?? 1.0;

      utterance.onstart = () => {
        if (options.onStart) options.onStart();
      };

      utterance.onend = () => {
        this.currentUtterance = null;
        if (options.onEnd) options.onEnd();
      };

      utterance.onerror = (err) => {
        this.currentUtterance = null;
        if (options.onError) options.onError(err);
      };

      try {
        this.synth.speak(utterance);
        // Workaround for Chrome/Edge long utterance garbage collection bug
        if (this.synth.paused) {
          this.synth.resume();
        }
      } catch (e) {
        console.warn('TTS speak error:', e);
      }
    }, 60);
  }

  public stop(): void {
    if (this.synth) {
      try {
        this.synth.cancel();
        this.currentUtterance = null;
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
