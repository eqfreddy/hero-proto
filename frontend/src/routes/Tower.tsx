import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchTower, attemptTower, fetchTowerLeaderboard } from '../api/tower'
import { useHeroes } from '../hooks/useHeroes'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'

export function TowerRoute() {
  const qc = useQueryClient()
  const { data: status, isLoading } = useQuery({
    queryKey: ['tower'],
    queryFn: fetchTower,
    refetchInterval: 60_000,
  })
  const { data: heroes } = useHeroes()
  const { data: leaderboard } = useQuery({
    queryKey: ['tower-leaderboard'],
    queryFn: fetchTowerLeaderboard,
    refetchInterval: 60_000,
  })
  const [busy, setBusy] = useState(false)
  const [last, setLast] = useState<{ won: boolean; floor: number } | null>(null)

  if (isLoading || !status) return <SkeletonGrid count={3} height={80} />

  const top3 = (heroes ?? []).slice().sort((a, b) => b.power - a.power).slice(0, 3)
  const team = top3.map((h) => h.id)
  const canAttempt = status.attempts_remaining > 0 && team.length > 0

  async function attempt() {
    setBusy(true)
    setLast(null)
    try {
      const r = await attemptTower(team)
      setLast({ won: r.won, floor: r.floor_attempted })
      const parts: string[] = []
      if (r.rewards.coins) parts.push(`🪙 ${r.rewards.coins}`)
      if (r.rewards.gems) parts.push(`💎 ${r.rewards.gems}`)
      if (r.rewards.shards) parts.push(`✦ ${r.rewards.shards}`)
      if (r.won) toast.success(`Floor ${r.floor_attempted} cleared! ${parts.join(' · ')}`)
      else toast.error(`Floor ${r.floor_attempted} — defeated. Tweak your team and retry.`)
      qc.invalidateQueries({ queryKey: ['tower'] })
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Attempt failed')
    } finally {
      setBusy(false)
    }
  }

  const preview = status.next_floor_preview
  const milestone = preview.floor % 5 === 0 || preview.floor % 10 === 0

  return (
    <div className="stack" style={{ gap: 14 }}>
      <h2 style={{ margin: 0 }}>🗼 Tower of Trials</h2>

      <div className="card" style={{ padding: 16 }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--accent)', letterSpacing: '0.12em', textTransform: 'uppercase', fontWeight: 800 }}>
              Current Floor
            </div>
            <div style={{ fontSize: 36, fontWeight: 900, marginTop: 2 }}>
              {status.floor}
            </div>
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              All-time best: {status.best_floor} · Season {status.season_key}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="muted" style={{ fontSize: 11 }}>Attempts today</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>
              {status.attempts_remaining} / {status.attempts_max}
            </div>
            <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>resets at UTC midnight</div>
          </div>
        </div>
      </div>

      <div className="card" style={{
        padding: 14,
        borderLeft: `3px solid ${milestone ? 'var(--warn)' : 'var(--border)'}`,
      }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700 }}>Next: Floor {preview.floor}</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
              {preview.enemy_count} enemy{preview.enemy_count > 1 ? 'ies' : ''} · level {preview.enemy_level}
            </div>
            <div style={{ fontSize: 12, marginTop: 4 }}>
              Rewards: 🪙 {preview.rewards.coins ?? 0}
              {preview.rewards.gems ? <span style={{ marginLeft: 8 }}>💎 {preview.rewards.gems}</span> : null}
              {preview.rewards.shards ? <span style={{ marginLeft: 8 }}>✦ {preview.rewards.shards}</span> : null}
              {milestone && <span style={{ marginLeft: 8, color: 'var(--warn)', fontWeight: 700 }}>★ milestone</span>}
            </div>
          </div>
          <button
            className="primary"
            disabled={!canAttempt || busy}
            onClick={attempt}
            style={{ minWidth: 110 }}
          >
            {busy ? '…' : canAttempt ? 'Attempt' : 'No attempts'}
          </button>
        </div>
        <div className="muted" style={{ fontSize: 11, marginTop: 10 }}>
          Auto-runs your top-3 power heroes: {top3.map((h) => h.template.name).join(' · ') || '—'}
        </div>
        {last && (
          <div style={{
            marginTop: 8, padding: '6px 10px', borderRadius: 4, fontSize: 12,
            background: last.won ? 'rgba(46, 204, 113, 0.15)' : 'rgba(231, 76, 60, 0.15)',
            color: last.won ? 'var(--good)' : 'var(--bad)',
          }}>
            Last run: floor {last.floor} — {last.won ? '✓ cleared' : '✗ defeated'}
          </div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 13 }}>Top Climbers</h3>
        {!leaderboard || leaderboard.length === 0 ? (
          <EmptyState icon="🗼" message="No climbers yet — be the first." />
        ) : (
          <table style={{ width: '100%', fontSize: 12 }}>
            <thead>
              <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
                <th>#</th><th>Player</th><th style={{ textAlign: 'right' }}>Best</th><th style={{ textAlign: 'right' }}>Now</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.map((row, i) => (
                <tr key={row.account_id} style={{ borderTop: '1px solid var(--border)' }}>
                  <td style={{ padding: '4px 0', fontWeight: 700, color: i < 3 ? 'var(--warn)' : 'inherit' }}>{i + 1}</td>
                  <td>#{row.account_id}</td>
                  <td style={{ textAlign: 'right', fontWeight: 700 }}>{row.best_floor}</td>
                  <td style={{ textAlign: 'right', color: 'var(--muted)' }}>{row.current_floor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Next 5 floors reward ladder */}
      <FloorLadder currentFloor={status.floor} />

      {/* Season record card */}
      <SeasonRecord
        currentFloor={status.floor}
        bestFloor={status.best_floor}
        seasonKey={status.season_key}
      />
    </div>
  )
}

// ── reward ladder ─────────────────────────────────────────────────────────────

/** Returns a hardcoded reward description for a given floor number. */
function floorReward(floor: number): string {
  if (floor % 25 === 0) return `🪙 ${floor * 30} coins · 💎 5 gems · ✦ 2 shards · 🖼 cosmetic frame`
  if (floor % 10 === 0) return `🪙 ${floor * 20} coins · 💎 2 gems · ✦ 1 epic gear shard`
  if (floor % 5 === 0)  return `🪙 ${floor * 15} coins · ✦ 1 rare gear shard`
  return `🪙 ${floor * 10} coins`
}

function FloorLadder({ currentFloor }: { currentFloor: number }) {
  const floors = Array.from({ length: 5 }, (_, i) => currentFloor + 1 + i)

  return (
    <div className="card">
      <h3 style={{ marginTop: 0, fontSize: 13 }}>🪜 Upcoming Floors</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {floors.map((f) => {
          const isMilestone = f % 5 === 0
          return (
            <div
              key={f}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '7px 0',
                borderBottom: '1px solid var(--border)',
                gap: 8,
              }}
            >
              <span style={{
                fontWeight: isMilestone ? 800 : 600,
                fontSize: 13,
                color: isMilestone ? 'var(--warn)' : 'inherit',
                flexShrink: 0,
              }}>
                Floor {f}{isMilestone ? ' ★' : ''}
              </span>
              <span className="muted" style={{ fontSize: 11, textAlign: 'right' }}>
                {floorReward(f)}
              </span>
            </div>
          )
        })}
      </div>
      <div className="muted" style={{ fontSize: 10, marginTop: 8 }}>
        Rewards shown are estimates — milestones (×5, ×10, ×25) grant bonus drops.
      </div>
    </div>
  )
}

// ── season record card ────────────────────────────────────────────────────────

function SeasonRecord({
  currentFloor,
  bestFloor,
  seasonKey,
}: {
  currentFloor: number
  bestFloor: number
  seasonKey: string
}) {
  const isNewHigh = currentFloor > 0 && currentFloor >= bestFloor

  return (
    <div className="card">
      <h3 style={{ marginTop: 0, fontSize: 13 }}>📊 Season Record</h3>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div className="muted" style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Season
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, marginTop: 2 }}>{seasonKey}</div>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>Current floor: {currentFloor}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="muted" style={{ fontSize: 11 }}>All-time best</div>
          <div style={{
            fontSize: 32,
            fontWeight: 900,
            lineHeight: 1,
            marginTop: 2,
            color: isNewHigh ? 'var(--warn)' : 'inherit',
            // pulse glow when at a new all-time high
            animation: isNewHigh ? 'towerBestPulse 2s ease-in-out infinite' : 'none',
          }}>
            {bestFloor}
          </div>
          {isNewHigh && (
            <div style={{ fontSize: 10, color: 'var(--warn)', marginTop: 2, fontWeight: 700 }}>
              ★ New high!
            </div>
          )}
        </div>
      </div>

      {/* Inline keyframes for the pulse glow — injected once via a style tag */}
      {isNewHigh && (
        <style>{`
          @keyframes towerBestPulse {
            0%, 100% { text-shadow: 0 0 6px color-mix(in srgb, var(--warn) 60%, transparent); }
            50%       { text-shadow: 0 0 18px color-mix(in srgb, var(--warn) 90%, transparent); }
          }
        `}</style>
      )}
    </div>
  )
}
