// hero-proto sound system.
//
// Pure Web Audio API. No external library, no shipped audio files —
// every sound is synthesized at runtime from oscillators + envelopes. Keeps
// the PWA payload small and the system instant-loading.
//
// To swap in real audio files later: each sound entry below has a `play()`
// closure. Replace the body with `loadAndPlay(url)` (Howler-style) and the
// rest of the API doesn't have to change.
//
// Public API:
//   sound.play(name)       fire a one-shot SFX by name
//   sound.setMute(bool)
//   sound.setMaster(0..1)
//   sound.setSfx(0..1)
//   sound.muted / .master / .sfx (read-only properties)
//   sound.test()           preview every sound in sequence (used by settings UI)
//
// Settings persist in localStorage under "heroproto_sound".
//
// Mobile autoplay: AudioContext starts suspended on iOS Safari. We resume()
// on the first user interaction (any click). Until then, play() is a no-op.

(function () {
  'use strict';

  const STORAGE_KEY = 'heroproto_sound';
  const DEFAULT_SETTINGS = { muted: false, master: 0.6, sfx: 0.8 };

  // --- Settings ------------------------------------------------------------
  let settings = loadSettings();

  function loadSettings() {
    try {
      const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (raw && typeof raw === 'object') {
        return { ...DEFAULT_SETTINGS, ...raw };
      }
    } catch {}
    return { ...DEFAULT_SETTINGS };
  }
  function saveSettings() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)); } catch {}
  }

  // --- AudioContext lifecycle ----------------------------------------------
  let ctx = null;
  let masterGain = null;
  let resumed = false;

  function ensureContext() {
    if (ctx) return ctx;
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return null;
    ctx = new Ctor();
    masterGain = ctx.createGain();
    masterGain.gain.value = effectiveVolume();
    masterGain.connect(ctx.destination);
    return ctx;
  }

  function effectiveVolume() {
    if (settings.muted) return 0;
    return settings.master * settings.sfx;
  }

  function applyVolume() {
    if (masterGain) masterGain.gain.value = effectiveVolume();
  }

  // Resume audio context on the first user interaction. iOS Safari requires
  // this. Listener is one-shot and fires for any click anywhere on the page.
  function setupAutoresume() {
    if (resumed) return;
    const trigger = () => {
      ensureContext();
      if (ctx && ctx.state === 'suspended') {
        ctx.resume().catch(() => {});
      }
      resumed = true;
      window.removeEventListener('click', trigger, true);
      window.removeEventListener('touchstart', trigger, true);
      window.removeEventListener('keydown', trigger, true);
    };
    window.addEventListener('click', trigger, true);
    window.addEventListener('touchstart', trigger, true);
    window.addEventListener('keydown', trigger, true);
  }

  // --- Synth primitives ----------------------------------------------------
  // Tiny helpers that build oscillator + envelope graphs. Each takes the
  // current time (ctx.currentTime) and a config object. All return Promise<void>
  // that resolves when the sound finishes — useful for chaining (test()).

  function tone({ freq = 440, type = 'sine', dur = 0.15, attack = 0.005, release = 0.05, gain = 0.3, detune = 0 }) {
    if (!ctx || !masterGain) return Promise.resolve();
    const t0 = ctx.currentTime;
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.value = freq;
    osc.detune.value = detune;
    const env = ctx.createGain();
    env.gain.setValueAtTime(0, t0);
    env.gain.linearRampToValueAtTime(gain, t0 + attack);
    env.gain.linearRampToValueAtTime(gain, t0 + dur - release);
    env.gain.linearRampToValueAtTime(0, t0 + dur);
    osc.connect(env).connect(masterGain);
    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
    return new Promise(resolve => setTimeout(resolve, dur * 1000));
  }

  // White noise burst — keyboard click, hit impact, etc.
  function noise({ dur = 0.04, gain = 0.25, lowpass = 4000, attack = 0.001, release = 0.02 }) {
    if (!ctx || !masterGain) return Promise.resolve();
    const t0 = ctx.currentTime;
    const buffer = ctx.createBuffer(1, ctx.sampleRate * dur, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    const filt = ctx.createBiquadFilter();
    filt.type = 'lowpass';
    filt.frequency.value = lowpass;
    const env = ctx.createGain();
    env.gain.setValueAtTime(0, t0);
    env.gain.linearRampToValueAtTime(gain, t0 + attack);
    env.gain.linearRampToValueAtTime(0, t0 + dur);
    src.connect(filt).connect(env).connect(masterGain);
    src.start(t0);
    src.stop(t0 + dur + 0.02);
    return new Promise(resolve => setTimeout(resolve, dur * 1000));
  }

  // Pitched arpeggio — for "ascending success" cues.
  async function arpeggio({ notes, type = 'sine', noteDur = 0.10, gain = 0.25 }) {
    for (const f of notes) {
      await tone({ freq: f, type, dur: noteDur, attack: 0.005, release: 0.04, gain });
    }
  }

  // Detuned chord — for legendary/myth pulls. Plays multiple oscillators at once.
  function chord({ notes, type = 'triangle', dur = 0.6, gain = 0.20 }) {
    if (!ctx || !masterGain) return Promise.resolve();
    const t0 = ctx.currentTime;
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      osc.type = type;
      osc.frequency.value = freq;
      osc.detune.value = (i - 1) * 8;  // small detune per voice for thickness
      const env = ctx.createGain();
      env.gain.setValueAtTime(0, t0);
      env.gain.linearRampToValueAtTime(gain, t0 + 0.04);
      env.gain.linearRampToValueAtTime(gain * 0.7, t0 + dur * 0.5);
      env.gain.linearRampToValueAtTime(0, t0 + dur);
      osc.connect(env).connect(masterGain);
      osc.start(t0);
      osc.stop(t0 + dur + 0.02);
    });
    return new Promise(resolve => setTimeout(resolve, dur * 1000));
  }

  // Frequency sweep — used for "rising" cues + dial-up handshake feel.
  function sweep({ from = 220, to = 880, dur = 0.4, type = 'sawtooth', gain = 0.15 }) {
    if (!ctx || !masterGain) return Promise.resolve();
    const t0 = ctx.currentTime;
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.setValueAtTime(from, t0);
    osc.frequency.exponentialRampToValueAtTime(to, t0 + dur);
    const env = ctx.createGain();
    env.gain.setValueAtTime(0, t0);
    env.gain.linearRampToValueAtTime(gain, t0 + 0.04);
    env.gain.linearRampToValueAtTime(0, t0 + dur);
    osc.connect(env).connect(masterGain);
    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
    return new Promise(resolve => setTimeout(resolve, dur * 1000));
  }

  // --- Sound bank ----------------------------------------------------------
  // Each entry is a function returning a Promise. Names are referenced by
  // sound.play(name).
  const SOUNDS = {
    // ---- UI ----
    click: () => noise({ dur: 0.025, gain: 0.18, lowpass: 6000 }),
    tab:   () => tone({ freq: 660, type: 'triangle', dur: 0.06, gain: 0.15, attack: 0.002, release: 0.03 }),
    error: () => arpeggio({ notes: [440, 330], type: 'square', noteDur: 0.08, gain: 0.18 }),
    success: () => arpeggio({ notes: [523.25, 783.99], type: 'sine', noteDur: 0.08, gain: 0.22 }),
    toast: () => tone({ freq: 880, type: 'sine', dur: 0.10, gain: 0.18 }),

    // ---- Combat ----
    hit:    () => noise({ dur: 0.06, gain: 0.32, lowpass: 2000 }),
    crit:   async () => { await noise({ dur: 0.05, gain: 0.4, lowpass: 1500 }); await tone({ freq: 1200, type: 'square', dur: 0.10, gain: 0.2 }); },
    death:  () => sweep({ from: 440, to: 80, dur: 0.45, type: 'sawtooth', gain: 0.18 }),
    victory: () => arpeggio({ notes: [523.25, 659.25, 783.99, 1046.50], type: 'sine', noteDur: 0.10, gain: 0.25 }),
    defeat: () => arpeggio({ notes: [440, 392, 349.23, 261.63], type: 'triangle', noteDur: 0.18, gain: 0.18 }),

    // ---- Gacha pulls (rarity-keyed) ----
    pull_common:    () => noise({ dur: 0.04, gain: 0.18, lowpass: 5000 }),
    pull_uncommon:  () => arpeggio({ notes: [523.25, 659.25], type: 'sine', noteDur: 0.08, gain: 0.22 }),
    pull_rare:      () => arpeggio({ notes: [523.25, 659.25, 783.99], type: 'sine', noteDur: 0.09, gain: 0.24 }),
    pull_epic:      async () => {
      await sweep({ from: 220, to: 660, dur: 0.18, type: 'triangle', gain: 0.18 });
      await chord({ notes: [523.25, 659.25, 783.99], type: 'triangle', dur: 0.40, gain: 0.20 });
    },
    pull_legendary: async () => {
      await sweep({ from: 110, to: 880, dur: 0.30, type: 'sawtooth', gain: 0.18 });
      await chord({ notes: [392, 523.25, 659.25, 783.99, 1046.50], type: 'triangle', dur: 0.60, gain: 0.22 });
    },
    pull_myth: async () => {
      // Prismatic / ethereal — detuned major chord stack with longer decay.
      await sweep({ from: 80, to: 1100, dur: 0.40, type: 'sine', gain: 0.16 });
      await chord({ notes: [261.63, 329.63, 392.00, 493.88, 587.33, 783.99], type: 'sine', dur: 0.90, gain: 0.20 });
    },

    // ---- Notifications + game events ----
    pager:        () => arpeggio({ notes: [880, 880], type: 'square', noteDur: 0.08, gain: 0.22 }),
    mailbox:      () => arpeggio({ notes: [659.25, 880], type: 'sine', noteDur: 0.10, gain: 0.20 }),
    coin_grant:   () => arpeggio({ notes: [523.25, 659.25, 783.99], type: 'sine', noteDur: 0.06, gain: 0.18 }),
    quest_claim:  () => arpeggio({ notes: [659.25, 783.99, 1046.50], type: 'triangle', noteDur: 0.08, gain: 0.22 }),
    purchase:     async () => { await tone({ freq: 880, type: 'sine', dur: 0.08, gain: 0.18 }); await tone({ freq: 1318.51, type: 'sine', dur: 0.12, gain: 0.20 }); },
    daily_bonus:  () => arpeggio({ notes: [392, 523.25, 659.25, 783.99], type: 'triangle', noteDur: 0.09, gain: 0.20 }),
  };

  // --- Public API ----------------------------------------------------------
  const sound = {
    play(name) {
      ensureContext();
      if (!ctx) return;
      const fn = SOUNDS[name];
      if (!fn) {
        if (window.console) console.debug('[sound] unknown sound:', name);
        return;
      }
      try { fn(); } catch (e) { if (window.console) console.warn('[sound] play failed:', e); }
    },

    /** Preview every sound in sequence. Used by the settings UI's "test all". */
    async test(category = 'all') {
      ensureContext();
      if (!ctx) return;
      const groups = {
        ui:     ['click', 'tab', 'success', 'error', 'toast'],
        combat: ['hit', 'crit', 'death', 'victory', 'defeat'],
        gacha:  ['pull_common', 'pull_uncommon', 'pull_rare', 'pull_epic', 'pull_legendary', 'pull_myth'],
        events: ['pager', 'mailbox', 'coin_grant', 'quest_claim', 'purchase', 'daily_bonus'],
      };
      const list = category === 'all'
        ? [].concat(...Object.values(groups))
        : (groups[category] || []);
      for (const name of list) {
        await SOUNDS[name]();
        await new Promise(r => setTimeout(r, 120));
      }
    },

    setMute(b)   { settings.muted = !!b; applyVolume(); saveSettings(); },
    setMaster(v) { settings.master = Math.max(0, Math.min(1, +v)); applyVolume(); saveSettings(); },
    setSfx(v)    { settings.sfx    = Math.max(0, Math.min(1, +v)); applyVolume(); saveSettings(); },

    get muted()  { return settings.muted; },
    get master() { return settings.master; },
    get sfx()    { return settings.sfx; },
  };

  setupAutoresume();
  window.sound = sound;
})();
