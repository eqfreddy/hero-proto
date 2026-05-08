import type { Stage } from '../types'

const TIER_STYLE: Record<Stage['difficulty_tier'], { label: string; bg: string; fg: string; border: string }> = {
  NORMAL:    { label: 'NORMAL',    bg: 'rgba(120,160,200,0.15)', fg: '#7ca8d8', border: 'rgba(120,160,200,0.4)' },
  HARD:      { label: 'HARD',      bg: 'rgba(220,140,60,0.18)',  fg: '#e8a35a', border: 'rgba(220,140,60,0.5)' },
  NIGHTMARE: { label: 'NIGHTMARE', bg: 'rgba(200,60,80,0.20)',   fg: '#e85a78', border: 'rgba(200,60,80,0.55)' },
}

export function TierBadge({ tier, size = 'md' }: { tier: Stage['difficulty_tier']; size?: 'sm' | 'md' }) {
  const s = TIER_STYLE[tier]
  if (!s) return null
  const fontSize = size === 'sm' ? 9 : 10
  const padding = size === 'sm' ? '1px 5px' : '2px 7px'
  return (
    <span
      style={{
        display: 'inline-block',
        fontSize,
        fontWeight: 800,
        letterSpacing: 0.6,
        padding,
        borderRadius: 3,
        background: s.bg,
        color: s.fg,
        border: `1px solid ${s.border}`,
        verticalAlign: 'middle',
        lineHeight: 1.2,
      }}
    >
      {s.label}
    </span>
  )
}
