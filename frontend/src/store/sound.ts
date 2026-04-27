import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SoundState {
  muted: boolean
  master: number  // 0-1
  sfx: number     // 0-1
  setMute: (v: boolean) => void
  setMaster: (v: number) => void
  setSfx: (v: number) => void
  play: (cue: 'click' | 'tab' | 'ui' | 'combat' | 'gacha' | 'events') => void
}

export const useSoundStore = create<SoundState>()(
  persist(
    (set, get) => ({
      muted: false,
      master: 0.6,
      sfx: 0.8,
      setMute: (v) => set({ muted: v }),
      setMaster: (v) => set({ master: Math.max(0, Math.min(1, v)) }),
      setSfx: (v) => set({ sfx: Math.max(0, Math.min(1, v)) }),
      play: (_cue) => {
        if (get().muted) return
        // Stub — real audio implementation wired in later
      },
    }),
    { name: 'heroproto_sound', partialize: (s) => ({ muted: s.muted, master: s.master, sfx: s.sfx }) }
  )
)
