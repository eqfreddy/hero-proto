import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStages, useTeamPower } from '../hooks/useStages'
import { useMe } from '../hooks/useMe'
import { apiPost } from '../api/client'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import type { Stage } from '../types'

const TIER_LABELS = { NORMAL: 'Normal', HARD: 'Hard', NIGHTMARE: 'Nightmare' }

export function StagesRoute() {
  const { data: stages, isLoading } = useStages()
  const { data: me } = useMe()
  const teamPower = useTeamPower()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [activeTier, setActiveTier] = useState<Stage['difficulty_tier']>('NORMAL')
  const [battling, setBattling] = useState<number | null>(null)

  if (isLoading) return <SkeletonGrid />
  if (!stages?.length) return <EmptyState icon="🗺️" message="No stages available." />

  const byTier = stages.filter((s) => s.difficulty_tier === activeTier)

  async function startBattle(stage: Stage) {
    if (!me) return
    setBattling(stage.id)
    try {
      const res = await apiPost<{ id: number; outcome: string; log?: unknown[] }>('/battles', {
        stage_id: stage.id,
        hero_ids: [],
      })
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['stages'] })
      if (res.log) {
        navigate(`/battle/${res.id}/watch`)
      } else {
        toast.success(res.outcome === 'WIN' ? '⚔️ Victory!' : '💀 Defeated.')
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Battle failed')
    } finally {
      setBattling(null)
    }
  }

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>Stages</h2>
        <span className="muted" style={{ fontSize: 12 }}>Team power: ⚡ {teamPower}</span>
      </div>

      <div className="row" style={{ gap: 4 }}>
        {(['NORMAL', 'HARD', 'NIGHTMARE'] as const).map((tier) => (
          <button
            key={tier}
            onClick={() => setActiveTier(tier)}
            style={{
              fontSize: 12, padding: '4px 14px',
              background: activeTier === tier ? 'var(--accent)' : 'var(--panel)',
              color: activeTier === tier ? '#0b0d10' : 'var(--muted)',
              border: '1px solid var(--border)', borderRadius: 4,
              fontWeight: activeTier === tier ? 700 : 400,
            }}
          >
            {TIER_LABELS[tier]}
          </button>
        ))}
      </div>

      <div className="stack" style={{ gap: 8 }}>
        {byTier.map((stage) => {
          const powerRatio = teamPower > 0 ? teamPower / stage.recommended_power : 0
          const powerColor = powerRatio >= 1.2 ? 'var(--good)' : powerRatio >= 0.8 ? 'var(--warn)' : 'var(--bad)'
          return (
            <div key={stage.id} className="card" style={{ padding: '12px 16px', opacity: stage.locked ? 0.5 : 1 }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>
                    {stage.cleared ? '✅ ' : ''}{stage.name}
                  </div>
                  <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                    ⚡ {stage.energy_cost} energy · Rec. {stage.recommended_power} power
                    <span style={{ color: powerColor }}> (yours: {teamPower})</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--warn)', marginTop: 2 }}>
                    🪙 {stage.coin_reward}
                    {stage.first_clear_gems > 0 && !stage.cleared && ` · 💎 ${stage.first_clear_gems} first clear`}
                  </div>
                </div>
                <div className="row" style={{ gap: 6 }}>
                  <button
                    className="primary"
                    disabled={stage.locked || battling === stage.id || (me?.energy ?? 0) < stage.energy_cost}
                    onClick={() => startBattle(stage)}
                    style={{ fontSize: 12 }}
                  >
                    {battling === stage.id ? '…' : stage.locked ? '🔒' : 'Battle'}
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
