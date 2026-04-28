import { useState } from 'react'
import { useSoundStore } from '../../store/sound'

export function SoundButton() {
  const [open, setOpen] = useState(false)
  const { muted, master, sfx, setMute, setMaster, setSfx } = useSoundStore()

  return (
    <div style={{ position: 'relative' }}>
      <button onClick={() => setOpen((v) => !v)}
        aria-label={muted ? 'Sound (muted) — open settings' : 'Sound — open settings'}
        aria-expanded={open}
        aria-haspopup="dialog"
        style={{ background: 'transparent', border: '1px solid var(--border)', color: muted ? 'var(--bad)' : 'var(--muted)', padding: '4px 8px', borderRadius: 4, fontSize: 14 }}>
        {muted ? '🔇' : '🔊'}
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 40, right: 0, zIndex: 100,
          background: 'var(--panel)', border: '1px solid var(--border)',
          borderRadius: 8, padding: 14, minWidth: 240, boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        }}>
          <h3 style={{ margin: '0 0 10px', fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase' }}>Sound</h3>
          <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 12, marginBottom: 8 }}>
            <span>Mute</span>
            <input type="checkbox" checked={muted} onChange={(e) => setMute(e.target.checked)} style={{ width: 18, height: 18 }} />
          </label>
          <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 12, marginBottom: 8 }}>
            <span>Master {Math.round(master * 100)}%</span>
            <input type="range" min={0} max={100} value={Math.round(master * 100)}
              onChange={(e) => setMaster(Number(e.target.value) / 100)} style={{ flex: 1 }} />
          </label>
          <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <span>SFX {Math.round(sfx * 100)}%</span>
            <input type="range" min={0} max={100} value={Math.round(sfx * 100)}
              onChange={(e) => setSfx(Number(e.target.value) / 100)} style={{ flex: 1 }} />
          </label>
        </div>
      )}
    </div>
  )
}
