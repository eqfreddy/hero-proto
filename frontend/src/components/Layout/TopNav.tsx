import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'
import { useMe } from '../../hooks/useMe'
import { BellButton } from './BellPopover'
import { SoundButton } from './SoundPopover'

function fmtBig(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`
  return String(n)
}

export function TopNav() {
  const clearJwt = useAuthStore((s) => s.clearJwt)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { data: me } = useMe()

  function logout() {
    clearJwt()
    qc.clear()
    window.location.href = '/'
  }

  return (
    <header className="topnav">
      <div className="topnav-bar">
        <button type="button" className="topnav-brand" onClick={() => navigate('/app/me')}>
          [ HERO-PROTO ]
        </button>
        {me && (
          <div className="topnav-curr" aria-label="currency">
            <span className="c"><span className="dot c"></span>{me.energy}</span>
            <span className="c"><span className="dot p"></span>{fmtBig(me.gems)}</span>
            <span className="c"><span className="dot g"></span>{fmtBig(me.coins)}</span>
          </div>
        )}
        <div className="topnav-actions">
          <BellButton />
          <SoundButton />
          <button onClick={logout} className="icon-btn" aria-label="Sign out" title="Sign out" style={{ fontSize: 13 }}>
            ⏻
          </button>
        </div>
      </div>

    </header>
  )
}
