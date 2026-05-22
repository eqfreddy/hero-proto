// frontend/src/components/Layout/RootlordSidebar.tsx
import { useEffect, useState } from 'react'
import { useMe } from '../../hooks/useMe'
import { useQuery } from '@tanstack/react-query'
import { fetchDaily } from '../../api/daily'
import { assetUrl } from '../../api/client'

const DEFAULT_QUOTES = [
  'The ticket queue never sleeps.',
  "sudo rm -rf /your-excuses --no-preserve-root",
  "GODMODE isn't a cheat code. It's a career.",
  "Change request denied. Reality can't be reverted.",
  "I break things so you understand what's worth keeping.",
  'Monitoring is for the weak. I depend on chaos.',
  'Best practices are suggestions. I deleted the document.',
]

function pickQuote(
  me: { energy: number; energy_cap: number; arena_wins: number; arena_losses: number; pulls_since_epic: number } | undefined,
  unclaimed: number,
): string {
  if (!me) return DEFAULT_QUOTES[0]
  const energyPct = me.energy / me.energy_cap
  if (energyPct <= 0.2) return 'Energy critical. sudo reboot self.'
  if (unclaimed >= 2) return 'Resources unclaimed. This is how entropy starts.'
  if (me.pulls_since_epic >= 45) return "The pity counter nears its limit. It knows what's coming."
  if (me.arena_losses > me.arena_wins && me.arena_wins + me.arena_losses > 0)
    return 'The metrics lie. Purge the metrics.'
  const idx = Math.floor(Date.now() / 6000) % DEFAULT_QUOTES.length
  return DEFAULT_QUOTES[idx]
}

export function RootlordSidebar() {
  const { data: me } = useMe()
  const { data: daily } = useQuery({ queryKey: ['daily'], queryFn: fetchDaily, staleTime: 60_000 })
  const [quote, setQuote] = useState('')
  const [visible, setVisible] = useState(true)

  const unclaimed = (daily ?? []).filter((q) => q.status === 'COMPLETE').length

  useEffect(() => {
    const next = pickQuote(me, unclaimed)
    setQuote(next)
    let fadeTimer: ReturnType<typeof setTimeout>
    const id = setInterval(() => {
      setVisible(false)
      fadeTimer = setTimeout(() => {
        setQuote(pickQuote(me, unclaimed))
        setVisible(true)
      }, 350)
    }, 6000)
    return () => {
      clearInterval(id)
      clearTimeout(fadeTimer)
    }
  }, [me, unclaimed])

  return (
    <aside style={{
      width: 220,
      flexShrink: 0,
      background: 'linear-gradient(180deg, #0a0208 0%, var(--bg) 60%)',
      borderRight: '1px solid rgba(200, 16, 46, 0.2)',
      display: 'flex',
      flexDirection: 'column',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* crimson radial glow at top */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0,
        height: 280,
        background: 'radial-gradient(ellipse at 50% 0%, rgba(200,16,46,0.2) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      {/* animated right border gradient */}
      <div style={{
        position: 'absolute',
        top: 0, bottom: 0, right: 0,
        width: 1,
        background: 'linear-gradient(180deg, transparent, rgba(200,16,46,0.5), rgba(0,255,224,0.2), transparent)',
        pointerEvents: 'none',
      }} />

      {/* Card art */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        <img
          src={assetUrl("/app/static/heroes/cards/The_Man_The_Dev.png")}
          alt="The Rootlord"
          style={{
            width: '100%',
            display: 'block',
            maskImage: 'linear-gradient(180deg, black 50%, transparent 86%)',
            WebkitMaskImage: 'linear-gradient(180deg, black 50%, transparent 86%)',
            filter: 'drop-shadow(0 0 24px rgba(200,16,46,0.5))',
          }}
          onError={(e) => {
            ;(e.target as HTMLImageElement).style.display = 'none'
          }}
        />
      </div>

      {/* Terminal output */}
      <div style={{
        flex: 1,
        padding: '10px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        position: 'relative',
        zIndex: 1,
        fontFamily: "'Consolas', 'Courier New', monospace",
      }}>
        <div style={{ fontSize: 10, color: 'var(--muted)' }}>
          <span style={{ color: 'var(--crimson)' }}>root@void:~$</span>
          {' '}
          <span style={{ color: 'rgba(0,255,224,0.5)' }}>status</span>
        </div>

        <div style={{
          fontSize: 11,
          color: '#8a7a60',
          fontStyle: 'italic',
          lineHeight: 1.5,
          marginTop: 2,
          opacity: visible ? 1 : 0,
          transition: 'opacity 0.35s',
          minHeight: 48,
        }}>
          {quote}
        </div>

        <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>
          <span style={{ color: 'var(--crimson)' }}>root@void:~$</span>
          {' '}
          <span aria-hidden="true" style={{
            display: 'inline-block',
            width: 7, height: 12,
            background: 'var(--accent)',
            verticalAlign: 'middle',
            boxShadow: '0 0 6px var(--accent)',
            animation: 'cursor-blink 1s step-start infinite',
          }} />
        </div>

        <div style={{
          marginTop: 12,
          paddingTop: 10,
          borderTop: '1px solid rgba(255,255,255,0.04)',
          fontSize: 10,
          color: 'rgba(200,16,46,0.7)',
          fontWeight: 700,
          letterSpacing: '0.1em',
        }}>
          ◈ THE ROOTLORD
        </div>
        <div style={{ fontSize: 9, color: 'rgba(138,122,96,0.6)', fontStyle: 'italic' }}>
          MYTH · ROGUE_IT · DEVOPS
        </div>
        <div style={{ fontSize: 9, color: 'rgba(100,100,120,0.5)', marginTop: 2 }}>
          He doesn't follow best practices.
        </div>
        <div style={{ fontSize: 9, color: 'rgba(100,100,120,0.5)' }}>
          He deletes them.
        </div>
      </div>
    </aside>
  )
}
