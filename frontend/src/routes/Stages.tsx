import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStages, useTeamPower } from '../hooks/useStages'
import { useMe } from '../hooks/useMe'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import { CoachMark } from '../components/CoachMark'
import { TierBadge } from '../components/TierBadge'
import type { Stage } from '../types'

const TIER_LABELS: Record<string, string> = { NORMAL: 'Floppy', HARD: 'Hard Disk', NIGHTMARE: 'RAID-0', LEGENDARY: "Legen'waitforit'dary" }

export function StagesRoute() {
  const { data: stages, isLoading } = useStages()
  const { data: me } = useMe()
  const teamPower = useTeamPower()
  const navigate = useNavigate()
  const [activeTier, setActiveTier] = useState<Stage['difficulty_tier']>('NORMAL')

  if (isLoading) return <SkeletonGrid />
  if (!stages?.length) return <EmptyState icon="🗺️" message="No stages available." />

  const byTier = stages.filter((s) => s.difficulty_tier === activeTier)

  function startBattle(stage: Stage) {
    navigate('/battle/setup', { state: { stageId: stage.id } })
  }

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>Stages</h2>
        <span className="muted" style={{ fontSize: 12 }}>Team power: ⚡ {teamPower}</span>
      </div>

      <div className="row" style={{ gap: 4 }}>
        {(['NORMAL', 'HARD', 'NIGHTMARE', 'LEGENDARY'] as const).map((tier) => (
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
        {byTier.map((stage, index) => {
          const powerRatio = teamPower > 0 ? teamPower / stage.recommended_power : 0
          const powerColor = powerRatio >= 1.2 ? 'var(--good)' : powerRatio >= 0.8 ? 'var(--warn)' : 'var(--bad)'
          const lockTitle = stage.requires_code
            ? `Clear ${stage.requires_code} first`
            : 'Stage locked'
          const belowFloor = stage.unlocked && stage.power_floor != null && teamPower < stage.power_floor
          const battleBtn = (
            <button
              className="primary"
              disabled={!stage.unlocked || (me?.energy ?? 0) < stage.energy_cost}
              onClick={() => startBattle(stage)}
              style={{ fontSize: 12 }}
            >
              {!stage.unlocked ? '🔒' : 'Battle'}
            </button>
          )
          return (
            <div key={stage.id} className="card" style={{ padding: '12px 16px', opacity: !stage.unlocked ? 0.5 : 1 }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
                    {stage.cleared ? '✅ ' : ''}{stage.name}
                    <TierBadge tier={stage.difficulty_tier} label={stage.display_name} size="sm" />
                    {!stage.unlocked && (
                      <span title={lockTitle} style={{ fontSize: 11, color: 'var(--bad)' }}>🔒 Locked</span>
                    )}
                  </div>
                  <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                    ⚡ {stage.energy_cost} energy · Rec. {stage.recommended_power} power
                    <span style={{ color: powerColor }}> (yours: {teamPower})</span>
                  </div>
                  {stage.power_floor != null && (
                    <div style={{ fontSize: 11, marginTop: 2, color: belowFloor ? 'var(--bad)' : 'var(--muted)' }}>
                      {belowFloor ? '⚠️' : '🛡️'} Min {stage.power_floor.toLocaleString()} power required
                    </div>
                  )}
                  <div style={{ fontSize: 11, color: 'var(--warn)', marginTop: 2 }}>
                    🪙 {stage.coin_reward}
                    {stage.first_clear_gems > 0 && !stage.cleared && ` · 💎 ${stage.first_clear_gems} first clear`}
                  </div>
                </div>
                <div className="row" style={{ gap: 6 }}>
                  {index === 0 ? (
                    <CoachMark
                      screenId="stages"
                      tooltip="Tap Battle to fight a stage. Energy refills over time."
                      side="left"
                    >
                      {battleBtn}
                    </CoachMark>
                  ) : battleBtn}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
