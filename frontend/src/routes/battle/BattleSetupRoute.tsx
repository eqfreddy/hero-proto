import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { postBattle, postInteractiveStart } from '../../api/battles'
import { useUiStore } from '../../store/ui'
import type { Hero, Stage } from '../../types'

function useHeroes() {
  return useQuery<Hero[]>({ queryKey: ['heroes'], queryFn: () => apiFetch('/heroes/mine'), staleTime: 5 * 60_000 })
}

function useStages() {
  return useQuery<Stage[]>({ queryKey: ['stages'], queryFn: () => apiFetch('/stages'), staleTime: 10 * 60_000 })
}

export default function BattleSetupRoute() {
  const navigate = useNavigate()
  const addToast = useUiStore(s => s.addToast)
  const { data: heroes = [] } = useHeroes()
  const { data: stages = [] } = useStages()

  const [team, setTeam] = useState<(number | null)[]>([null, null, null])
  const [selectedStageId, setSelectedStageId] = useState<number | null>(null)
  const [interactive, setInteractive] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const teamIds = team.filter((id): id is number => id !== null)
  const teamPower = teamIds
    .map(id => heroes.find(h => h.id === id))
    .filter(Boolean)
    .reduce((sum, h) => sum + (h!.power ?? 0), 0)

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

      {/* Stage selector */}
      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Select Stage</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {stages.map(s => (
            <button
              key={s.id}
              onClick={() => setSelectedStageId(s.id)}
              style={{
                padding: '8px 14px', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                background: selectedStageId === s.id ? 'var(--color-accent)' : 'var(--color-surface)',
                color: selectedStageId === s.id ? '#fff' : 'var(--color-text)',
                border: '1px solid ' + (selectedStageId === s.id ? 'var(--color-accent)' : 'rgba(255,255,255,0.1)'),
              }}
            >
              {s.name}
            </button>
          ))}
        </div>
        {selectedStage && (
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--color-muted)' }}>
            Energy cost: {selectedStage.energy_cost} · Recommended power: {selectedStage.recommended_power ?? '—'}
          </div>
        )}
      </section>

      {/* Team builder */}
      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
          Your Team <span style={{ fontWeight: 400, color: 'var(--color-muted)' }}>— Power {teamPower}</span>
        </h2>
        <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
          {team.map((heroId, idx) => {
            const hero = heroes.find(h => h.id === heroId)
            return (
              <div
                key={idx}
                onClick={() => heroId !== null && setTeam(prev => { const n = [...prev]; n[idx] = null; return n })}
                style={{
                  width: 80, height: 90, borderRadius: 8, border: '2px dashed rgba(255,255,255,0.15)',
                  background: hero ? 'var(--color-surface)' : 'transparent',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  cursor: hero ? 'pointer' : 'default', fontSize: 11, color: 'var(--color-muted)',
                }}
              >
                {hero ? (
                  <>
                    <div style={{ fontWeight: 700, color: 'var(--color-text)', textAlign: 'center', padding: '0 4px' }}>{hero.template.name}</div>
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

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {[...heroes].sort((a, b) => (b.power ?? 0) - (a.power ?? 0)).map(h => {
            const selected = team.includes(h.id)
            return (
              <button
                key={h.id}
                onClick={() => toggleHero(h.id)}
                style={{
                  padding: '6px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  background: selected ? 'var(--color-accent)' : 'var(--color-surface)',
                  color: selected ? '#fff' : 'var(--color-text)',
                  border: '1px solid ' + (selected ? 'var(--color-accent)' : 'rgba(255,255,255,0.1)'),
                }}
              >
                {h.template.name} ({h.power})
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
