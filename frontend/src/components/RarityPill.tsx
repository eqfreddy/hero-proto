import type { HeroTemplate } from '../types'

const RARITY_COLORS: Record<HeroTemplate['rarity'], string> = {
  COMMON: 'var(--r-common)',
  UNCOMMON: 'var(--r-uncommon)',
  RARE: 'var(--r-rare)',
  EPIC: 'var(--r-epic)',
  LEGENDARY: 'var(--r-legendary)',
  MYTH: 'var(--r-myth)',
}

interface Props { rarity: HeroTemplate['rarity']; size?: 'sm' | 'md' }
export function RarityPill({ rarity, size = 'sm' }: Props) {
  const color = RARITY_COLORS[rarity]
  return (
    <span style={{
      display: 'inline-block', padding: size === 'sm' ? '1px 6px' : '2px 8px',
      borderRadius: 10, fontSize: size === 'sm' ? 10 : 11, fontWeight: 700,
      background: `color-mix(in srgb, ${color} 20%, transparent)`,
      border: `1px solid ${color}`, color,
    }}>
      {rarity}
    </span>
  )
}
