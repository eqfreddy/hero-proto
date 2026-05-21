import type { Hero } from '../types'
import { RarityPill } from './RarityPill'
import { HeroPortrait } from './HeroPortrait'

interface Props {
  hero: Hero
  onClick?: () => void
  selected?: boolean
}

export function HeroCard({ hero, onClick, selected }: Props) {
  const { template: t } = hero

  return (
    <div
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick() } : undefined}
      style={{
        background: 'var(--panel)',
        border: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 'var(--radius)',
        overflow: 'hidden',
        cursor: onClick ? 'pointer' : 'default',
        position: 'relative',
        transition: 'border-color 0.15s',
      }}
    >
      <div style={{ position: 'relative', aspectRatio: '1', background: 'var(--bg-inset)', overflow: 'hidden' }}>
        <HeroPortrait
          code={t.code}
          name={t.name}
          rarity={t.rarity}
          role={t.role}
          faction={t.faction}
          style={{ height: '100%', borderRadius: 0, border: 'none', boxShadow: 'none' }}
        />
        {hero.dupe_count > 1 && (
          <span style={{
            position: 'absolute', top: 4, right: 4,
            background: 'rgba(0,0,0,0.75)', color: 'var(--warn)',
            fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
          }}>
            ×{hero.dupe_count}
          </span>
        )}
        {hero.has_variance && (
          <span style={{
            position: 'absolute', bottom: 4, right: 4, fontSize: 9,
            color: hero.variance_net > 0 ? 'var(--good)' : 'var(--bad)',
            background: 'rgba(0,0,0,0.7)', padding: '1px 4px', borderRadius: 3,
          }}>
            {hero.variance_net > 0 ? '+' : ''}{(hero.variance_net * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <div style={{ padding: '8px 10px' }}>
        <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {t.name}
        </div>
        <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 4, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
          {t.role} · {t.faction.replace('_', ' ')}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <RarityPill rarity={t.rarity} />
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>
            ⚡ {hero.power}
          </span>
        </div>
        <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 3 }}>
          {'⭐'.repeat(hero.stars)} Lv {hero.level}
        </div>
      </div>
    </div>
  )
}
