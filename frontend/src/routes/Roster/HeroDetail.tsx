import { useParams, useNavigate } from 'react-router-dom'
import { useHero } from '../../hooks/useHeroes'
import { useQueryClient } from '@tanstack/react-query'
import { ascendHero, skillUpHero } from '../../api/heroes'
import { toast } from '../../store/ui'
import { RarityPill } from '../../components/RarityPill'
import { SkeletonGrid } from '../../components/SkeletonGrid'
import { useState } from 'react'

export function HeroDetailRoute() {
  const { heroId } = useParams<{ heroId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: hero, isLoading } = useHero(Number(heroId))
  const [loading, setLoading] = useState<'ascend' | 'skill' | null>(null)

  if (isLoading) return <SkeletonGrid count={3} height={100} />
  if (!hero) return <div className="muted">Hero not found.</div>

  const t = hero.template

  async function doAscend() {
    setLoading('ascend')
    try {
      await ascendHero(hero!.id)
      toast.success(`${t.name} ascended!`)
      qc.invalidateQueries({ queryKey: ['heroes'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(null) }
  }

  async function doSkillUp() {
    setLoading('skill')
    try {
      await skillUpHero(hero!.id)
      toast.success(`${t.name} skill upgraded!`)
      qc.invalidateQueries({ queryKey: ['heroes'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(null) }
  }

  return (
    <div className="stack" style={{ maxWidth: 480, margin: '0 auto' }}>
      <button onClick={() => navigate('/app/roster')} style={{ alignSelf: 'flex-start', fontSize: 12 }}>
        ← Back to Roster
      </button>
      <div className="card">
        <div className="row" style={{ gap: 16, alignItems: 'flex-start' }}>
          <img
            src={`/app/static/heroes/cards/${t.code}.png`}
            alt={t.name}
            style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 'var(--radius)', background: 'var(--bg-inset)' }}
            onError={(e) => { (e.target as HTMLImageElement).src = `/placeholder/hero/${t.code}.svg` }}
          />
          <div>
            <h2 style={{ margin: '0 0 4px' }}>{t.name}</h2>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
              <RarityPill rarity={t.rarity} size="md" />
              <span className="pill">{t.role}</span>
              <span className="pill">{t.faction}</span>
            </div>
            <div style={{ marginTop: 6, color: 'var(--muted)', fontSize: 12 }}>
              {'⭐'.repeat(hero.stars)} Level {hero.level} · Special Lv {hero.special_level}
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 13 }}>Stats</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {[['❤️ HP', hero.hp], ['⚔️ ATK', hero.atk], ['🛡️ DEF', hero.def_], ['💨 SPD', hero.spd], ['⚡ Power', hero.power]].map(([label, val]) => (
            <div key={String(label)}>
              <div className="muted" style={{ fontSize: 11 }}>{label}</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{val}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 13 }}>Upgrades</h3>
        <div className="row" style={{ gap: 8 }}>
          <button onClick={doAscend} disabled={!!loading} className="primary">
            {loading === 'ascend' ? '…' : '⭐ Star Up'}
          </button>
          <button onClick={doSkillUp} disabled={!!loading} className="secondary">
            {loading === 'skill' ? '…' : '🔮 Skill Up'}
          </button>
        </div>
      </div>
    </div>
  )
}
