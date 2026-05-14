import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SoundState {
  muted: boolean
  master: number  // 0-1
  sfx: number     // 0-1
  bgm: number     // 0-1
  bgmCurrent: string | null
  setMute: (v: boolean) => void
  setMaster: (v: number) => void
  setSfx: (v: number) => void
  setBgm: (v: number) => void
  play: (cue: 'click' | 'tab' | 'ui' | 'combat' | 'gacha' | 'events') => void
  playBgm: (slug: BgmSlug) => void
  stopBgm: () => void
}

export type BgmSlug =
  | 'abyssal_echoes'
  | 'ancient_map'
  | 'cartoon_chaos'
  | 'dark_dungeon'
  | 'mischief_maker'
  | 'wrath_of_ares'

const BGM_BASE = '/app/static/bgm'

// Singleton audio element — kept outside zustand so persist doesn't try
// to serialize it and so repeated playBgm() calls reuse the same node.
let bgmEl: HTMLAudioElement | null = null

function ensureEl(): HTMLAudioElement {
  if (bgmEl) return bgmEl
  bgmEl = new Audio()
  bgmEl.loop = true
  bgmEl.preload = 'auto'
  return bgmEl
}

function applyVolume(state: { muted: boolean; master: number; bgm: number }) {
  if (!bgmEl) return
  bgmEl.volume = state.muted ? 0 : Math.max(0, Math.min(1, state.master * state.bgm))
}

export const useSoundStore = create<SoundState>()(
  persist(
    (set, get) => ({
      muted: false,
      master: 0.6,
      sfx: 0.8,
      bgm: 0.5,
      bgmCurrent: null,
      setMute: (v) => {
        set({ muted: v })
        applyVolume(get())
      },
      setMaster: (v) => {
        const clamped = Math.max(0, Math.min(1, v))
        set({ master: clamped })
        applyVolume(get())
      },
      setSfx: (v) => set({ sfx: Math.max(0, Math.min(1, v)) }),
      setBgm: (v) => {
        const clamped = Math.max(0, Math.min(1, v))
        set({ bgm: clamped })
        applyVolume(get())
      },
      play: (_cue) => {
        if (get().muted) return
      },
      playBgm: (slug) => {
        const state = get()
        if (state.bgmCurrent === slug) {
          // already on this track — just re-apply volume in case mute flipped
          applyVolume(state)
          return
        }
        const el = ensureEl()
        el.src = `${BGM_BASE}/${slug}.mp3`
        applyVolume(state)
        set({ bgmCurrent: slug })
        // Autoplay may be blocked until user gesture; fail silently and
        // try again on the next playBgm call (which usually comes from
        // a click — DEPLOY, summon, etc).
        void el.play().catch(() => { /* deferred until next gesture */ })
      },
      stopBgm: () => {
        if (bgmEl) {
          bgmEl.pause()
          bgmEl.currentTime = 0
        }
        set({ bgmCurrent: null })
      },
    }),
    {
      name: 'heroproto_sound',
      partialize: (s) => ({ muted: s.muted, master: s.master, sfx: s.sfx, bgm: s.bgm }),
    },
  ),
)

/**
 * Pick a BGM track for a stage based on its difficulty tier. 3 dark / 3 light
 * split — escalates with difficulty.
 */
export function bgmForStageTier(tier: string | undefined | null): BgmSlug {
  switch (tier) {
    case 'LEGENDARY': return 'wrath_of_ares'
    case 'NIGHTMARE': return 'abyssal_echoes'
    case 'HARD':      return 'dark_dungeon'
    case 'NORMAL':    return 'cartoon_chaos'
    default:          return 'ancient_map'
  }
}
