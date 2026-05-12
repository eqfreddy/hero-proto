import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { postBattle, postInteractiveStart } from '../../api/battles'
import { useUiStore } from '../../store/ui'
import { TierBadge } from '../../components/TierBadge'
import type { Hero, HeroTemplate, Stage } from '../../types'

// Tier color theming — mirrors TierBadge so stage buttons match the
// badge inside them. Used for grouped <details> sections + per-stage
// button accents.
const TIER_THEME: Record<Stage['difficulty_tier'], { bg: string; fg: string; border: string; tintBg: string }> = {
  NORMAL:    { bg: 'rgba(120,160,200,0.18)', fg: '#7ca8d8', border: 'rgba(120,160,200,0.5)',  tintBg: 'rgba(120,160,200,0.08)' },
  HARD:      { bg: 'rgba(220,140,60,0.22)',  fg: '#e8a35a', border: 'rgba(220,140,60,0.55)',  tintBg: 'rgba(220,140,60,0.10)' },
  NIGHTMARE: { bg: 'rgba(200,60,80,0.25)',   fg: '#e85a78', border: 'rgba(200,60,80,0.60)',   tintBg: 'rgba(200,60,80,0.12)' },
  LEGENDARY: { bg: 'rgba(220,180,40,0.28)',  fg: '#f5c842', border: 'rgba(220,180,40,0.65)',  tintBg: 'rgba(220,180,40,0.14)' },
}

const TIER_ORDER: Stage['difficulty_tier'][] = ['NORMAL', 'HARD', 'NIGHTMARE', 'LEGENDARY']

// Rarity color theming for hero buttons + filled slot cards. Uses the
// same CSS custom properties as RarityPill so the palette stays in sync.
const RARITY_VAR: Record<HeroTemplate['rarity'], string> = {
  COMMON:    'var(--r-common)',
  UNCOMMON:  'var(--r-uncommon)',
  RARE:      'var(--r-rare)',
  EPIC:      'var(--r-epic)',
  LEGENDARY: 'var(--r-legendary)',
  MYTH:      'var(--r-myth)',
}

const miniBtn: React.CSSProperties = {
  padding: '4px 10px',
  borderRadius: 5,
  fontSize: 11,
  fontWeight: 700,
  cursor: 'pointer',
  background: 'var(--color-surface)',
  color: 'var(--color-muted)',
  border: '1px solid rgba(255,255,255,0.12)',
}

const chipBtn: React.CSSProperties = {
  padding: '3px 9px',
  borderRadius: 12,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: 0.4,
  cursor: 'pointer',
  border: '1px solid rgba(255,255,255,0.1)',
}

function useHeroes() {
  return useQuery<Hero[]>({ queryKey: ['heroes'], queryFn: () => apiFetch('/heroes/mine'), staleTime: 5 * 60_000 })
}

function useStages() {
  return useQuery<Stage[]>({ queryKey: ['stages'], queryFn: () => apiFetch('/stages'), staleTime: 10 * 60_000 })
}

export default function BattleSetupRoute() {
  const navigate = useNavigate()
  const location = useLocation()
  const addToast = useUiStore(s => s.addToast)
  const { data: heroes = [] } = useHeroes()
  const { data: stages = [] } = useStages()

  const [team, setTeam] = useState<(number | null)[]>([null, null, null])
  const [selectedStageId, setSelectedStageId] = useState<number | null>(
    (location.state as { stageId?: number } | null)?.stageId ?? null
  )
  const [interactive, setInteractive] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [roleFilter, setRoleFilter] = useState<'ALL' | 'ATK' | 'DEF' | 'SUP'>('ALL')
  const [rarityFilter, setRarityFilter] = useState<'ALL' | HeroTemplate['rarity']>('ALL')

  const teamIds = team.filter((id): id is number => id !== null)
  const teamPower = teamIds
    .map(id => heroes.find(h => h.id === id))
    .filter(Boolean)
    .reduce((sum, h) => sum + (h!.power ?? 0), 0)

  async function useLastTeam() {
    try {
      const res = await apiFetch<{ team: number[]; source: string }>('/me/last-team')
      const owned = new Set(heroes.map(h => h.id))
      const cleaned = res.team.filter(id => owned.has(id)).slice(0, 3)
      if (cleaned.length === 0) {
        addToast(res.source === 'empty' ? 'No prior battle yet' : 'Last team\'s heroes no longer owned', 'info')
        return
      }
      const padded: (number | null)[] = [cleaned[0] ?? null, cleaned[1] ?? null, cleaned[2] ?? null]
      setTeam(padded)
    } catch (e) {
      addToast(e instanceof Error ? e.message : 'Couldn\'t load last team', 'error')
    }
  }

  function autoTeam() {
    const top3 = [...heroes].sort((a, b) => (b.power ?? 0) - (a.power ?? 0)).slice(0, 3)
    setTeam([top3[0]?.id ?? null, top3[1]?.id ?? null, top3[2]?.id ?? null])
  }

  function clearTeam() {
    setTeam([null, null, null])
  }

  function toggleHero(heroId: number) {
    setTeam(prev => {
      const idx = prev.indexOf(heroId)
      if (idx !== -1) {
        const next = [...prev]
        next[idx] = null
        return next
      }
      const empty = prev.findIndex(s => s === null)
      if (empty === -1) return prev
      const next = [...prev]
      next[empty] = heroId
      return next
    })
  }

  async function handleFight() {
    if (teamIds.length === 0 || !selectedStageId) return
    setSubmitting(true)
    try {
      if (interactive) {
        const state = await postInteractiveStart({ stage_id: selectedStageId, team: teamIds })
        navigate(`/battle/${state.session_id}/play`, { state: { initState: state } })
      } else {
        const battle = await postBattle({ stage_id: selectedStageId, team: teamIds, target_priority: 'lowest_hp' })
        navigate(`/battle/${battle.id}/replay`)
      }
    } catch (e) {
      addToast(e instanceof Error ? e.message : 'Battle failed', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const selectedStage = stages.find(s => s.id === selectedStageId)

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto', color: 'var(--color-text)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <button onClick={() => navigate('/app/stages')} style={{ background: 'none', border: 'none', color: 'var(--color-muted)', cursor: 'pointer', fontSize: 14 }}>
          ← Back
        </button>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800 }}>Battle Setup</h1>
      </div>

      {/* Stage selector — grouped by difficulty tier, each tier a
          color-coded collapsible group. */}
      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Select Stage</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {TIER_ORDER.map(tier => {
            const tierStages = stages.filter(s => s.difficulty_tier === tier)
            if (tierStages.length === 0) return null
            const theme = TIER_THEME[tier]
            const hasSelection = tierStages.some(s => s.id === selectedStageId)
            return (
              <details
                key={tier}
                open={hasSelection || tier === 'NORMAL'}
                style={{
                  background: theme.tintBg,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 8,
                  overflow: 'hidden',
                }}
              >
                <summary style={{
                  padding: '10px 14px', cursor: 'pointer', userSelect: 'none',
                  background: theme.bg, color: theme.fg,
                  fontSize: 13, fontWeight: 800, letterSpacing: 0.5, textTransform: 'uppercase',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                }}>
                  <span>{tier} <span style={{ opacity: 0.7, fontWeight: 600, marginLeft: 6 }}>({tierStages.length})</span></span>
                  <span style={{ fontSize: 11, opacity: 0.7, fontWeight: 600 }}>{hasSelection ? '✓ selected' : 'click to expand'}</span>
                </summary>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, padding: 12 }}>
                  {tierStages.map(s => {
                    const isSel = selectedStageId === s.id
                    return (
                      <button
                        key={s.id}
                        onClick={() => setSelectedStageId(s.id)}
                        style={{
                          padding: '8px 14px', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                          background: isSel ? theme.bg : 'var(--color-surface)',
                          color: isSel ? theme.fg : 'var(--color-text)',
                          border: '1px solid ' + (isSel ? theme.border : 'rgba(255,255,255,0.1)'),
                          boxShadow: isSel ? `0 0 0 1px ${theme.border}` : 'none',
                        }}
                      >
                        {s.name}
                        <TierBadge tier={s.difficulty_tier} size="sm" />
                      </button>
                    )
                  })}
                </div>
              </details>
            )
          })}
        </div>
        {selectedStage && (
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--color-muted)' }}>
            Energy cost: {selectedStage.energy_cost} · Recommended power: {selectedStage.recommended_power ?? '—'}
          </div>
        )}
      </section>

      {/* Team builder */}
      <section style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
          <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 1, margin: 0 }}>
            Your Team <span style={{ fontWeight: 400, color: 'var(--color-muted)' }}>— Power {teamPower}</span>
          </h2>
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={useLastTeam} style={miniBtn}>🕘 Last team</button>
            <button onClick={autoTeam} style={miniBtn}>⚡ Auto (best power)</button>
            <button onClick={clearTeam} style={miniBtn}>✕ Clear</button>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
          {team.map((heroId, idx) => {
            const hero = heroes.find(h => h.id === heroId)
            const rarityColor = hero ? RARITY_VAR[hero.template.rarity] : null
            return (
              <div
                key={idx}
                onClick={() => heroId !== null && setTeam(prev => { const n = [...prev]; n[idx] = null; return n })}
                style={{
                  width: 80, height: 90, borderRadius: 8,
                  border: rarityColor ? `2px solid ${rarityColor}` : '2px dashed rgba(255,255,255,0.15)',
                  background: rarityColor
                    ? `color-mix(in srgb, ${rarityColor} 18%, var(--color-surface))`
                    : 'transparent',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  cursor: hero ? 'pointer' : 'default', fontSize: 11, color: 'var(--color-muted)',
                  boxShadow: rarityColor ? `0 0 0 1px color-mix(in srgb, ${rarityColor} 35%, transparent)` : 'none',
                }}
              >
                {hero ? (
                  <>
                    <div style={{ fontWeight: 700, color: rarityColor ?? 'var(--color-text)', textAlign: 'center', padding: '0 4px' }}>{hero.template.name}</div>
                    <div style={{ color: 'var(--color-muted)', marginTop: 2 }}>Lv {hero.level}</div>
                    <div style={{ fontSize: 10, marginTop: 2, color: 'rgba(255,255,255,0.3)' }}>click to remove</div>
                  </>
                ) : (
                  <span>Slot {idx + 1}</span>
                )}
              </div>
            )
          })}
        </div>

        {/* Filter chips — role + rarity */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
          {(['ALL', 'ATK', 'DEF', 'SUP'] as const).map(r => (
            <button
              key={r}
              onClick={() => setRoleFilter(r)}
              style={{
                ...chipBtn,
                background: roleFilter === r ? 'var(--color-accent)' : 'var(--color-surface)',
                color: roleFilter === r ? '#fff' : 'var(--color-muted)',
                borderColor: roleFilter === r ? 'var(--color-accent)' : 'rgba(255,255,255,0.1)',
              }}
            >{r === 'ALL' ? 'All roles' : r}</button>
          ))}
          <span style={{ width: 1, background: 'rgba(255,255,255,0.1)', margin: '0 2px' }} />
          {(['ALL', 'COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'MYTH'] as const).map(r => {
            const active = rarityFilter === r
            const c = r === 'ALL' ? null : RARITY_VAR[r as HeroTemplate['rarity']]
            return (
              <button
                key={r}
                onClick={() => setRarityFilter(r)}
                style={{
                  ...chipBtn,
                  background: active && c ? `color-mix(in srgb, ${c} 30%, var(--color-surface))` : (active ? 'var(--color-accent)' : 'var(--color-surface)'),
                  color: active && c ? c : (active ? '#fff' : 'var(--color-muted)'),
                  borderColor: active && c ? c : (active ? 'var(--color-accent)' : 'rgba(255,255,255,0.1)'),
                }}
              >{r === 'ALL' ? 'All rarities' : r}</button>
            )
          })}
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {[...heroes]
            .filter(h => roleFilter === 'ALL' || h.template.role === roleFilter)
            .filter(h => rarityFilter === 'ALL' || h.template.rarity === rarityFilter)
            .sort((a, b) => (b.power ?? 0) - (a.power ?? 0))
            .map(h => {
            const selected = team.includes(h.id)
            const rarityColor = RARITY_VAR[h.template.rarity]
            return (
              <button
                key={h.id}
                onClick={() => toggleHero(h.id)}
                style={{
                  padding: '6px 10px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                  background: selected
                    ? `color-mix(in srgb, ${rarityColor} 35%, var(--color-surface))`
                    : `color-mix(in srgb, ${rarityColor} 10%, var(--color-surface))`,
                  color: rarityColor,
                  border: `1px solid ${selected ? rarityColor : `color-mix(in srgb, ${rarityColor} 45%, transparent)`}`,
                  boxShadow: selected ? `0 0 0 1px ${rarityColor}` : 'none',
                }}
              >
                {h.template.name} <span style={{ opacity: 0.7, fontWeight: 500 }}>({h.power})</span>
              </button>
            )
          })}
        </div>
      </section>

      {/* Interactive toggle + Fight button */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: 'var(--color-muted)' }}>
          <input
            type="checkbox"
            checked={interactive}
            onChange={e => setInteractive(e.target.checked)}
            style={{ width: 16, height: 16, accentColor: 'var(--color-accent)', cursor: 'pointer' }}
          />
          Interactive mode
        </label>
        <button
          onClick={handleFight}
          disabled={teamIds.length === 0 || !selectedStageId || submitting}
          style={{
            padding: '12px 32px', borderRadius: 8, fontSize: 15, fontWeight: 800, cursor: 'pointer',
            background: 'var(--color-accent)', color: '#fff', border: 'none',
            opacity: (teamIds.length === 0 || !selectedStageId || submitting) ? 0.5 : 1,
          }}
        >
          {submitting ? 'Starting…' : 'Fight!'}
        </button>
      </div>
    </div>
  )
}
