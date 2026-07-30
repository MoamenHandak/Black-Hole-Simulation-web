/**
 * Web Audio API Cosmic Synth & Ambience Generator
 */

class CosmicAudioEngine {
    constructor() {
        this.ctx = null;
        this.isMuted = true;
        this.masterGain = null;
        this.droneOsc1 = null;
        this.droneOsc2 = null;
        this.filter = null;
    }

    init() {
        if (this.ctx) return;
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;

        this.ctx = new AudioCtx();
        this.masterGain = this.ctx.createGain();
        this.masterGain.gain.setValueAtTime(0.0, this.ctx.currentTime);

        // Low-pass filter for cosmic hum
        this.filter = this.ctx.createBiquadFilter();
        this.filter.type = 'lowpass';
        this.filter.frequency.setValueAtTime(140, this.ctx.currentTime);

        // Sub-bass drone oscillator 1 (Gravitational wave hum)
        this.droneOsc1 = this.ctx.createOscillator();
        this.droneOsc1.type = 'sine';
        this.droneOsc1.frequency.setValueAtTime(55, this.ctx.currentTime); // A1 note

        // Sub-bass drone oscillator 2 (Detuned)
        this.droneOsc2 = this.ctx.createOscillator();
        this.droneOsc2.type = 'triangle';
        this.droneOsc2.frequency.setValueAtTime(55.4, this.ctx.currentTime);

        // LFO for subtle pulse
        const lfo = this.ctx.createOscillator();
        lfo.type = 'sine';
        lfo.frequency.setValueAtTime(0.1, this.ctx.currentTime);

        const lfoGain = this.ctx.createGain();
        lfoGain.gain.setValueAtTime(40, this.ctx.currentTime);

        lfo.connect(lfoGain);
        lfoGain.connect(this.filter.frequency);

        this.droneOsc1.connect(this.filter);
        this.droneOsc2.connect(this.filter);
        this.filter.connect(this.masterGain);
        this.masterGain.connect(this.ctx.destination);

        this.droneOsc1.start();
        this.droneOsc2.start();
        lfo.start();
    }

    toggleMute() {
        this.init();
        if (this.ctx && this.ctx.state === 'suspended') {
            this.ctx.resume();
        }

        this.isMuted = !this.isMuted;
        if (this.masterGain) {
            const now = this.ctx.currentTime;
            this.masterGain.gain.cancelScheduledValues(now);
            this.masterGain.gain.linearRampToValueAtTime(this.isMuted ? 0.0 : 0.22, now + 0.5);
        }
        return this.isMuted;
    }

    updateMassPitch(massFactor) {
        if (!this.ctx || !this.droneOsc1) return;
        // Adjust hum frequency based on black hole mass (heavier = deeper frequency)
        const targetFreq = Math.max(25, 75 - massFactor * 25);
        const now = this.ctx.currentTime;
        this.droneOsc1.frequency.setTargetAtTime(targetFreq, now, 0.2);
        this.droneOsc2.frequency.setTargetAtTime(targetFreq * 1.008, now, 0.2);
    }
}

export const audioEngine = new CosmicAudioEngine();
