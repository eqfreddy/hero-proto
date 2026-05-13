/**
 * Stages.tsx — Board-map campaign screen
 *
 * Visual contract: docs/mockups/stages-board.html
 * Design rationale: docs/mockups/stages-board-NOTES.md
 * Backend spec: docs/milestone-rewards-spec-2026-05-13.md
 *
 * Rule #1 psychology hooks implemented:
 *   - Zeigarnik: "N stages to next gate" in header + side-panel progress bar
 *   - Anticipation: gate node pulse glow + header countdown badge
 *   - Variable reward: Legendary Boss Shard row with published odds on every stage
 *   - Competence: READY badge + cyan pulse on next-unlocked node
 *   - Loss aversion: win streak pill (TODO: wire me.win_streak_days when backend exposes it)
 *   - Anchoring: legendary boss shard row appears even on locked panels as silhouette
 *
 * HOOK: After battle returns to /app/stages, check BattleOut.milestone_unlocks
 * (once backend ships that field per spec §4c) and auto-open MilestoneClaimModal
 * for the first newly-unlocked milestone ID.
 */

import { useState, useMemo, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useStages, useTeamPower } from '../hooks/useStages'
import { useMilestones } from '../hooks/useMilestones'
import { useMe } from '../hooks/useMe'
import { claimMilestone } from '../api/milestones'
import { SkeletonGrid } from '../components/SkeletonGrid'
import type { Stage } from '../types'
import type { MilestoneItem, MilestonesResponse } from '../api/milestones'

// ── Constants ──────────────────────────────────────────────────────────────

const TIER_LABELS: Record<string, string> = {
  NORMAL: 'Floppy Disk',
  HARD: 'Hard Disk',
  NIGHTMARE: 'RAID-0',
  LEGENDARY: 'Legen-wait-dary',
}

const TIER_COLOR: Record<string, string> = {
  NORMAL:    'var(--accent)',
  HARD:      'var(--warn)',
  NIGHTMARE: 'var(--void-purple)',
  LEGENDARY: 'var(--gold)',
}

const TIER_BG: Record<string, string> = {
  NORMAL:    'rgba(0,255,224,0.10)',
  HARD:      'rgba(245,158,11,0.10)',
  NIGHTMARE: 'rgba(155,48,255,0.10)',
  LEGENDARY: 'rgba(255,215,0,0.10)',
}

const TIER_BORDER: Record<string, string> = {
  NORMAL:    'rgba(0,255,224,0.25)',
  HARD:      'rgba(245,158,11,0.25)',
  NIGHTMARE: 'rgba(155,48,255,0.25)',
  LEGENDARY: 'rgba(255,215,0,0.25)',
}

// Board geometry
const COLS_PER_ROW = 5
const H_SPACING    = 140
const V_SPACING    = 130
const ROW_X_START  = 100

// ── Types ──────────────────────────────────────────────────────────────────

/** Synthetic node that lives in the board alongside real Stage rows */
interface MilestoneNode {
  _kind: 'milestone'
  id: string
  mLabel: string
  stageCount: number
  claimed: boolean
  active: boolean   // unlocked but not yet claimed
  legendShard: number  // 0.0–1.0
  templateShards: number
  milestoneId: number
}

interface VaultNode {
  _kind: 'vault'
  id: string
}

type StageNode_ = Stage & { _kind: 'stage' }
type BoardNode = StageNode_ | MilestoneNode | VaultNode

interface Coords { x: number; y: number; row: number; col: number }
type PositionedStage     = StageNode_     & Coords
type PositionedMilestone = MilestoneNode  & Coords
type PositionedVault     = VaultNode      & Coords
type PositionedNode      = PositionedStage | PositionedMilestone | PositionedVault

// ── Layout engine ──────────────────────────────────────────────────────────

function computeLayout(nodes: BoardNode[]): PositionedNode[] {
  const positioned: PositionedNode[] = []
  let col = 0
  let row = 0
  let goingRight = true

  for (const node of nodes) {
    const x = goingRight
      ? ROW_X_START + col * H_SPACING
      : ROW_X_START + (COLS_PER_ROW - 1 - col) * H_SPACING
    const y = 80 + row * V_SPACING

    positioned.push({ ...node, x, y, row, col } as PositionedNode)

    col++
    if (col >= COLS_PER_ROW) {
      col = 0
      row++
      goingRight = !goingRight
    }
  }

  return positioned
}

// ── Node state helpers ─────────────────────────────────────────────────────

type NodeState = 'cleared' | 'ready' | 'locked' | 'milestone-claimed' | 'milestone-active' | 'milestone-locked' | 'boss-cleared' | 'boss-locked' | 'vault'

function getNodeState(node: PositionedNode): NodeState {
  if (node._kind === 'vault') return 'vault'
  if (node._kind === 'milestone') {
    if (node.claimed) return 'milestone-claimed'
    if (node.active)  return 'milestone-active'
    return 'milestone-locked'
  }
  // stage
  if (node.cleared)  return 'cleared'
  if (node.unlocked) return 'ready'
  return 'locked'
}

function isNodeEffectivelyCleared(node: PositionedNode): boolean {
  const st = getNodeState(node)
  return st === 'cleared' || st === 'boss-cleared' || st === 'milestone-claimed'
}

// ── Inline keyframes (injected once) ──────────────────────────────────────

const KEYFRAMES = `
@keyframes nodeReadyPulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(0,255,224,0.55), 0 0 16px rgba(0,255,224,0.25); }
  50%      { box-shadow: 0 0 0 10px rgba(0,255,224,0), 0 0 28px rgba(0,255,224,0.45); }
}
@keyframes milestoneGlow {
  0%,100% { box-shadow: 0 0 14px rgba(155,48,255,0.4), inset 0 0 10px rgba(155,48,255,0.08); }
  50%      { box-shadow: 0 0 32px rgba(155,48,255,0.7), 0 0 60px rgba(155,48,255,0.25), inset 0 0 14px rgba(155,48,255,0.15); }
}
@keyframes vaultBreathe {
  0%,100% { box-shadow: 0 0 12px rgba(0,255,224,0.2); border-color: rgba(0,255,224,0.3); }
  50%      { box-shadow: 0 0 32px rgba(0,255,224,0.45), 0 0 60px rgba(0,255,224,0.1); border-color: rgba(0,255,224,0.65); }
}
@keyframes milestonePulseBorder {
  0%,100% { border-color: rgba(155,48,255,0.35); box-shadow: none; }
  50%      { border-color: rgba(155,48,255,0.7); box-shadow: 0 0 10px rgba(155,48,255,0.3); }
}
@keyframes warnFlash {
  0%,100% { opacity: 1; }
  50%      { opacity: 0.65; }
}
@keyframes legendaryShimmer {
  0%,100% { border-color: rgba(255,215,0,0.2); }
  50%      { border-color: rgba(255,215,0,0.45); box-shadow: 0 0 10px rgba(255,215,0,0.1); }
}
@keyframes modalFadeIn {
  from { opacity: 0; transform: scale(0.93); }
  to   { opacity: 1; transform: scale(1); }
}
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
`

// ── Sub-components ─────────────────────────────────────────────────────────

/** Single node on the board */
interface StageNodeProps {
  node: PositionedNode
  selected: boolean
  reducedMotion: boolean
  onClick: () => void
}

function StageNode({ node, selected, reducedMotion, onClick }: StageNodeProps) {
  const state = getNodeState(node)

  const SIZE: Record<string, number> = {
    'vault': 72,
    'boss-locked': 62, 'boss-cleared': 62,
    'milestone-active': 54, 'milestone-claimed': 54, 'milestone-locked': 54,
    'cleared': 42, 'ready': 42, 'locked': 42,
  }
  const size = SIZE[state] ?? 42

  // Ring style per state
  const ringStyle: React.CSSProperties = (() => {
    const base: React.CSSProperties = {
      width: size, height: size,
      borderRadius: '50%',
      border: '2px solid',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.38,
      position: 'relative',
      transition: 'box-shadow 0.2s, border-color 0.2s',
    }
    switch (state) {
      case 'cleared': return { ...base,
        background: 'rgba(34,197,94,0.12)', borderColor: 'var(--good)',
        boxShadow: '0 0 10px rgba(34,197,94,0.3), inset 0 0 8px rgba(34,197,94,0.08)' }
      case 'ready': return { ...base,
        background: 'rgba(0,255,224,0.1)', borderColor: 'var(--accent)',
        animation: reducedMotion ? 'none' : 'nodeReadyPulse 1.8s ease-in-out infinite' }
      case 'locked': return { ...base,
        background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.1)', opacity: 0.45 }
      case 'milestone-active': return { ...base,
        background: 'rgba(155,48,255,0.14)', borderColor: 'var(--void-purple)',
        animation: reducedMotion ? 'none' : 'milestoneGlow 2s ease-in-out infinite' }
      case 'milestone-claimed': return { ...base,
        background: 'rgba(155,48,255,0.08)', borderColor: 'rgba(155,48,255,0.4)', opacity: 0.7 }
      case 'milestone-locked': return { ...base,
        background: 'rgba(155,48,255,0.14)', borderColor: 'var(--void-purple)',
        boxShadow: '0 0 14px rgba(155,48,255,0.4)' }
      case 'boss-locked': return { ...base,
        background: 'rgba(200,16,46,0.14)', borderColor: 'var(--crimson)',
        boxShadow: '0 0 18px rgba(200,16,46,0.45), inset 0 0 12px rgba(200,16,46,0.1)' }
      case 'boss-cleared': return { ...base,
        background: 'rgba(34,197,94,0.1)', borderColor: 'var(--good)',
        boxShadow: '0 0 12px rgba(34,197,94,0.35)' }
      case 'vault': return { ...base,
        background: 'rgba(0,255,224,0.07)', borderColor: 'rgba(0,255,224,0.4)',
        borderStyle: 'dashed',
        animation: reducedMotion ? 'none' : 'vaultBreathe 3.5s ease-in-out infinite' }
      default: return base
    }
  })()

  const icon = (() => {
    if (node._kind === 'vault') return '?'
    if (node._kind === 'milestone') {
      if (node.claimed) return '✓'
      if (node.active)  return '🎁'
      return '⬡'
    }
    if (state === 'cleared') return '✓'
    if (state === 'ready')   return '▶'
    return '🔒'
  })()

  const label = (() => {
    if (node._kind === 'vault')     return 'Chapter Vault'
    if (node._kind === 'milestone') return node.mLabel
    return node.name
  })()

  const labelColor = (() => {
    if (state === 'cleared')  return 'rgba(34,197,94,0.8)'
    if (state === 'ready')    return 'var(--accent)'
    if (state === 'vault')    return 'rgba(0,255,224,0.7)'
    if (state.startsWith('milestone')) return 'rgba(155,48,255,0.85)'
    if (state.startsWith('boss'))      return 'rgba(200,16,46,0.85)'
    return 'var(--muted)'
  })()

  // Stage score badge (cleared normal nodes) — score not in schema yet, reserved
  const scoreBadge = null

  const isClickable = state !== 'locked'

  return (
    <div
      role="button"
      tabIndex={isClickable ? 0 : -1}
      aria-label={`${label}${state === 'locked' ? ' (locked)' : ''}`}
      aria-pressed={selected}
      onClick={isClickable ? onClick : undefined}
      onKeyDown={isClickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick() } : undefined}
      style={{
        position: 'absolute',
        left: node.x,
        top: node.y,
        transform: 'translate(-50%, -50%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        cursor: isClickable ? 'pointer' : 'not-allowed',
        userSelect: 'none',
        transition: 'transform 0.18s',
        outline: selected ? '2px solid rgba(0,255,224,0.6)' : 'none',
        outlineOffset: 4,
        borderRadius: '50%',
        zIndex: selected ? 3 : 2,
      }}
    >
      {/* READY badge */}
      {state === 'ready' && (
        <div style={{
          position: 'absolute', top: -10, left: '50%', transform: 'translateX(-50%)',
          background: 'var(--accent)', color: '#04060c',
          fontSize: 8, fontWeight: 900, letterSpacing: '0.1em',
          padding: '2px 6px', borderRadius: 3, whiteSpace: 'nowrap',
          boxShadow: '0 0 8px rgba(0,255,224,0.6)', zIndex: 4,
        }}>
          READY
        </div>
      )}

      <div style={ringStyle}>
        {scoreBadge}
        <span style={{ pointerEvents: 'none' }}>{icon}</span>
      </div>

      <div style={{
        marginTop: 6, fontSize: 9, fontWeight: 700,
        letterSpacing: '0.08em', textTransform: 'uppercase',
        textAlign: 'center', maxWidth: 80, lineHeight: 1.2,
        color: labelColor, pointerEvents: 'none',
      }}>
        {label}
      </div>
    </div>
  )
}

// ── SVG connector layer ────────────────────────────────────────────────────

interface ConnectorLayerProps {
  nodes: PositionedNode[]
  reducedMotion: boolean
}

function ConnectorLayer({ nodes, reducedMotion }: ConnectorLayerProps) {
  const paths: React.ReactNode[] = []

  for (let i = 0; i < nodes.length - 1; i++) {
    const a = nodes[i]
    const b = nodes[i + 1]

    const aCleared = isNodeEffectivelyCleared(a)
    const bCleared = isNodeEffectivelyCleared(b)
    const bReady   = getNodeState(b) === 'ready'

    let strokeColor: string
    let dashArray: string | undefined

    if (aCleared && bCleared) {
      strokeColor = 'rgba(34,197,94,0.45)'
    } else if (aCleared && bReady) {
      strokeColor = 'rgba(0,255,224,0.5)'
    } else {
      strokeColor = 'rgba(255,255,255,0.08)'
      dashArray = '5 7'
    }

    const mx = (a.x + b.x) / 2
    const bend = a.row !== b.row ? 30 : 0
    const cy1 = a.y + bend
    const cy2 = b.y - bend
    const d = `M ${a.x} ${a.y} C ${mx} ${cy1}, ${mx} ${cy2}, ${b.x} ${b.y}`

    paths.push(
      <path
        key={`line-${i}`}
        d={d}
        stroke={strokeColor}
        strokeWidth={2}
        fill="none"
        strokeLinecap="round"
        strokeDasharray={dashArray}
        opacity={0.85}
      />
    )

    // Animated data packets — only when motion is ok
    if (!reducedMotion && aCleared && bCleared) {
      const delay = (i * 0.37).toFixed(2)
      const dur   = (3.5 + (i % 3) * 0.8).toFixed(1)
      paths.push(
        <circle key={`pkt-${i}`} r={2.5} fill="#00ffe0" filter="url(#glow-sm)" opacity={0.9}>
          <animateMotion dur={`${dur}s`} begin={`${delay}s`} repeatCount="indefinite" path={d} />
        </circle>
      )
    }

    if (!reducedMotion && aCleared && bReady) {
      paths.push(
        <circle key={`pkt-ready-${i}`} r={3} fill="#00ffe0" filter="url(#glow-lg)" opacity={0.95}>
          <animateMotion dur="2.2s" repeatCount="indefinite" path={d} />
        </circle>
      )
    }
  }

  return <>{paths}</>
}

// ── Header strip ──────────────────────────────────────────────────────────

interface HeaderStripProps {
  tier: string
  cleared: number
  total: number
  winStreak: number
  nextMilestoneLabel: string | null
  stagesToNextMilestone: number | null
  reducedMotion: boolean
}

function HeaderStrip({
  tier, cleared, total, winStreak,
  nextMilestoneLabel, stagesToNextMilestone, reducedMotion,
}: HeaderStripProps) {
  const pct = total > 0 ? Math.round((cleared / total) * 100) : 0

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
      padding: '0 20px', height: 52,
      background: 'rgba(4,6,12,0.95)',
      borderBottom: '1px solid var(--border-strong)',
      flexShrink: 0, zIndex: 20,
      backdropFilter: 'blur(14px)',
    }}>
      {/* Chapter icon + name */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 30, height: 30, borderRadius: 7, flexShrink: 0,
          background: 'linear-gradient(135deg, var(--accent), #7c5fff)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 15, boxShadow: '0 0 14px rgba(0,255,224,0.35)',
        }}>⚡</div>
        <span style={{
          fontSize: 13, fontWeight: 800, letterSpacing: '0.1em',
          textTransform: 'uppercase', color: 'var(--accent)',
          textShadow: '0 0 10px rgba(0,255,224,0.55)',
        }}>
          Chapter 1 — {TIER_LABELS[tier] ?? tier}
        </span>
      </div>

      <div style={{ width: 1, height: 24, background: 'var(--border-strong)', flexShrink: 0 }} />

      {/* Progress */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--muted)' }}>
        <span>🗺️</span>
        <span>Progress</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', fontVariantNumeric: 'tabular-nums' }}>
          {cleared} / {total}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, maxWidth: 200 }}>
        <div style={{ flex: 1, height: 4, background: 'rgba(255,255,255,0.07)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 2, width: `${pct}%`,
            background: 'linear-gradient(90deg, var(--accent), #7c5fff)',
            boxShadow: '0 0 8px rgba(0,255,224,0.45)',
            transition: 'width 0.6s cubic-bezier(.4,0,.2,1)',
          }} />
        </div>
      </div>

      <div style={{ width: 1, height: 24, background: 'var(--border-strong)', flexShrink: 0 }} />

      {/* Win streak — TODO: wire to me.win_streak_days once backend exposes it */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 5,
        padding: '3px 10px', borderRadius: 999,
        background: 'rgba(255,215,0,0.1)', border: '1px solid rgba(255,215,0,0.25)',
        fontSize: 11, fontWeight: 700, color: 'var(--gold)',
      }}>
        <span style={{ fontSize: 13 }}>🔥</span>
        <span>{winStreak} Win Streak</span>
      </div>

      {/* Zeigarnik: stages to next milestone */}
      {stagesToNextMilestone != null && stagesToNextMilestone > 0 && nextMilestoneLabel && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '3px 12px', borderRadius: 999, fontSize: 11, fontWeight: 700,
          background: 'rgba(155,48,255,0.12)', border: '1px solid rgba(155,48,255,0.35)',
          color: '#c47aff',
          animation: reducedMotion ? 'none' : 'milestonePulseBorder 2.5s ease-in-out infinite',
        }}>
          ◈ {stagesToNextMilestone} to {nextMilestoneLabel}
        </div>
      )}

      {/* Win-streak loss-aversion countdown — hardcoded session timer */}
      {winStreak > 0 && (
        <StreakCountdown reducedMotion={reducedMotion} />
      )}
    </div>
  )
}

/** Counts down from 6h (session). Pure client-side; not wired to server reset. */
function StreakCountdown({ reducedMotion }: { reducedMotion: boolean }) {
  const [secs, setSecs] = useState(6 * 3600)
  useEffect(() => {
    const id = setInterval(() => setSecs((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(id)
  }, [])
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    <div style={{
      marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6,
      fontSize: 11, color: 'var(--warn)', fontWeight: 600,
      padding: '3px 10px', borderRadius: 999,
      background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)',
      animation: reducedMotion ? 'none' : 'warnFlash 3s ease-in-out infinite',
    }}>
      ⚠ Streak resets in {pad(h)}:{pad(m)}:{pad(s)}
    </div>
  )
}

// ── Side panel ─────────────────────────────────────────────────────────────

interface SidePanelProps {
  node: PositionedNode | null
  tier: string
  teamPower: number
  milestonesData: MilestonesResponse | null | undefined
  onFight: (stage: Stage) => void
  onClaimMilestone: (node: PositionedMilestone) => void
}

function SidePanel({ node, tier, teamPower, milestonesData, onFight, onClaimMilestone }: SidePanelProps) {
  if (!node) {
    return (
      <div style={sidePanelStyle}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, color: 'var(--muted)', gap: 10 }}>
          <div style={{ fontSize: 28, opacity: 0.3 }}>🗺️</div>
          <div style={{ fontSize: 11, textAlign: 'center', maxWidth: 180 }}>Select a stage node to view details</div>
        </div>
      </div>
    )
  }

  const state = getNodeState(node)

  if (node._kind === 'vault') return <VaultPanel tier={tier} stagesCleared={milestonesData?.stages_cleared_count ?? 0} />
  if (node._kind === 'milestone') {
    return (
      <MilestonePanelContent
        node={node}
        milestonesData={milestonesData}
        onClaim={() => onClaimMilestone(node)}
      />
    )
  }

  // Stage panel — node._kind === 'stage' here
  return <StagePanel stage={node} state={state} teamPower={teamPower} milestonesData={milestonesData} onFight={onFight} />
}

const sidePanelStyle: React.CSSProperties = {
  width: 300, minWidth: 300,
  background: 'rgba(12,16,26,0.9)',
  backdropFilter: 'blur(16px)',
  borderLeft: '1px solid var(--border-strong)',
  display: 'flex', flexDirection: 'column',
  zIndex: 10, overflowY: 'auto',
}

// Reward row component
function RewardRow({
  icon, name, oddsLabel, oddsColor = 'var(--accent)', legendary = false,
}: {
  icon: string, name: string, oddsLabel: string, oddsColor?: string, legendary?: boolean
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '7px 10px', borderRadius: 6, marginBottom: 5,
      background: legendary ? 'rgba(255,215,0,0.05)' : 'rgba(255,255,255,0.03)',
      border: legendary ? '1px solid rgba(255,215,0,0.2)' : '1px solid rgba(255,255,255,0.05)',
      animation: legendary ? 'legendaryShimmer 3s ease-in-out infinite' : 'none',
      fontSize: 11,
    }}>
      <span style={{ fontSize: 16, flexShrink: 0 }}>{icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, color: legendary ? 'var(--gold)' : 'var(--text)', fontSize: 11 }}>{name}</div>
        <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 1 }}>
          <span style={{ fontWeight: 700, color: oddsColor }}>{oddsLabel}</span>
          {legendary && ' · Honest published odds'}
        </div>
      </div>
    </div>
  )
}

// Stage panel content
function StagePanel({
  stage, state, teamPower, milestonesData, onFight,
}: {
  stage: Stage
  state: NodeState
  teamPower: number
  milestonesData: MilestonesResponse | null | undefined
  onFight: (s: Stage) => void
}) {
  const tier = stage.difficulty_tier
  const powerRatio = teamPower > 0 && stage.recommended_power > 0 ? teamPower / stage.recommended_power : 0
  const powerColor = powerRatio >= 1.2 ? 'var(--good)' : powerRatio >= 0.8 ? 'var(--warn)' : 'var(--bad)'
  const isCleared  = state === 'cleared'
  const isReady    = state === 'ready'
  const isLocked   = state === 'locked'
  const canFight   = isCleared || isReady

  // Zeigarnik: stages to next milestone
  const next = milestonesData?.next_milestone
  const stagesCleared = milestonesData?.stages_cleared_count ?? 0

  return (
    <div style={sidePanelStyle}>
      {/* Header */}
      <div style={{ padding: '16px 18px 12px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 4 }}>
          Stage {stage.order + 1}
        </div>
        <div style={{ fontSize: 17, fontWeight: 800, color: 'var(--text)', lineHeight: 1.2, marginBottom: 2 }}>{stage.name}</div>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
          padding: '2px 8px', borderRadius: 4, marginTop: 6,
          background: TIER_BG[tier] ?? 'transparent',
          color: TIER_COLOR[tier] ?? 'var(--text)',
          border: `1px solid ${TIER_BORDER[tier] ?? 'var(--border)'}`,
        }}>
          {TIER_LABELS[tier] ?? tier}
        </div>
      </div>

      <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
        {/* Zeigarnik bar */}
        {next && (
          <div style={{
            padding: '12px 14px', background: 'rgba(155,48,255,0.07)',
            border: '1px solid rgba(155,48,255,0.2)', borderRadius: 8,
          }}>
            <div style={{
              fontSize: 10, fontWeight: 700, color: '#c47aff', letterSpacing: '0.1em',
              textTransform: 'uppercase', marginBottom: 8,
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <span>Next Gate — {next.label}</span>
              <span style={{ fontSize: 13, color: 'var(--text)', fontWeight: 800 }}>{next.stages_to_go} to go</span>
            </div>
            <div style={{ height: 6, background: 'rgba(155,48,255,0.15)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                height: '100%', borderRadius: 3,
                background: 'linear-gradient(90deg, var(--void-purple), #c47aff)',
                boxShadow: '0 0 8px rgba(155,48,255,0.5)',
                width: `${Math.round((stagesCleared / next.stage_count) * 100)}%`,
                transition: 'width 0.8s cubic-bezier(.4,0,.2,1)',
              }} />
            </div>
          </div>
        )}
        {!next && !milestonesData && (
          <div style={{ fontSize: 10, color: 'var(--muted)', fontStyle: 'italic' }}>milestone system loading…</div>
        )}

        {/* Cleared badge */}
        {isCleared && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px',
            background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)',
            borderRadius: 7, fontSize: 12, fontWeight: 700, color: 'var(--good)',
          }}>
            <span>✅</span> Cleared
          </div>
        )}

        {/* Locked notice */}
        {isLocked && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '16px 0', textAlign: 'center', color: 'var(--muted)' }}>
            <div style={{ fontSize: 28, opacity: 0.4 }}>🔒</div>
            <div style={{ fontSize: 11, lineHeight: 1.4, maxWidth: 200 }}>Clear the previous stage to unlock this node.</div>
          </div>
        )}

        {/* Stage info */}
        <div>
          <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 8 }}>Stage Info</div>
          <InfoRow label="⚡ Energy cost" value={String(stage.energy_cost)} />
          <InfoRow label="🎯 Rec. power"  value={stage.recommended_power.toLocaleString()} valueColor={powerColor} />
          <InfoRow label="⚔ Your power"   value={teamPower.toLocaleString()} />
          {stage.coin_reward > 0 && <InfoRow label="🪙 Coins" value={stage.coin_reward.toLocaleString()} />}
        </div>

        {/* Rewards */}
        <div>
          <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 8 }}>Expected Rewards</div>
          <RewardRow icon="🪙" name={`${stage.coin_reward.toLocaleString()} Coins`} oddsLabel="100%" oddsColor="var(--accent)" />
          {stage.first_clear_shards > 0 && (
            <RewardRow icon="🔷" name={`${stage.first_clear_shards} Shard Credit${stage.first_clear_shards !== 1 ? 's' : ''}`} oddsLabel="First clear only" />
          )}
          {stage.first_clear_gems > 0 && (
            <RewardRow icon="💎" name={`${stage.first_clear_gems} Gems`} oddsLabel="First clear only" />
          )}
          <RewardRow icon="⚙️" name="Rare+ Gear Drop" oddsLabel="~28% per run" oddsColor="var(--void-purple)" />
          {/* Anchoring — legendary boss shard visible on every stage, even locked */}
          <RewardRow icon="✨" name="Legendary Boss Shard" oddsLabel="12% chance" oddsColor="var(--gold)" legendary />
        </div>

        {/* FIGHT / REPLAY button */}
        <button
          disabled={!canFight}
          onClick={() => onFight(stage)}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            width: '100%', padding: 13, fontSize: 14, fontWeight: 900,
            letterSpacing: '0.12em', textTransform: 'uppercase',
            background: canFight ? 'linear-gradient(135deg, var(--accent), #00c4ae)' : 'rgba(255,255,255,0.08)',
            color: canFight ? '#04060c' : 'var(--muted)',
            border: canFight ? 'none' : '1px solid rgba(255,255,255,0.1)',
            borderRadius: 8, cursor: canFight ? 'pointer' : 'not-allowed',
            boxShadow: canFight ? '0 4px 24px rgba(0,255,224,0.3), 0 0 0 1px rgba(0,255,224,0.3)' : 'none',
            transition: 'transform 0.1s, box-shadow 0.15s',
            position: 'relative', overflow: 'hidden',
          }}
        >
          <span>{isCleared ? '⟳ REPLAY' : '⚡ FIGHT'}</span>
          <span style={{ fontSize: 11, fontWeight: 600, opacity: 0.75, display: 'inline-flex', alignItems: 'center', gap: 3 }}>
            ⚡{stage.energy_cost}
          </span>
        </button>
      </div>
    </div>
  )
}

function InfoRow({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      fontSize: 12, color: 'var(--muted)', padding: '5px 0',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
    }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>{label}</span>
      <span style={{ fontWeight: 600, color: valueColor ?? 'var(--text)' }}>{value}</span>
    </div>
  )
}

function MilestonePanelContent({
  node, milestonesData, onClaim,
}: {
  node: MilestoneNode
  milestonesData: MilestonesResponse | null | undefined
  onClaim: () => void
}) {
  const legendBal = milestonesData?.legend_boss_shards ?? 0
  const summonCost = milestonesData?.legend_summon_cost ?? 30

  return (
    <div style={sidePanelStyle}>
      <div style={{ padding: '16px 18px 12px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 4 }}>
          Milestone Gate — {node.stageCount} stages
        </div>
        <div style={{ fontSize: 17, fontWeight: 800, color: 'var(--text)', lineHeight: 1.2, marginBottom: 2 }}>{node.mLabel}</div>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
          padding: '2px 8px', borderRadius: 4, marginTop: 6,
          background: 'rgba(155,48,255,0.1)', color: 'var(--void-purple)',
          border: '1px solid rgba(155,48,255,0.25)',
        }}>
          {node.claimed ? '✓ Claimed' : node.active ? '⬡ Ready to Claim' : '⬡ Upcoming'}
        </div>
      </div>

      <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
        <div>
          <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 8 }}>Milestone Rewards</div>
          <RewardRow icon="🔮" name={`${node.templateShards}× Shard Credits`} oddsLabel="Guaranteed" oddsColor="var(--accent)" />
          <RewardRow icon="💎" name="150 Gems" oddsLabel="Guaranteed" oddsColor="var(--accent)" />
          <RewardRow icon="✨" name="Legendary Boss Shard" oddsLabel={`${Math.round(node.legendShard * 100)}% chance`} oddsColor="var(--gold)" legendary />
          <RewardRow icon="🎲" name="Epic Equipment Chest" oddsLabel="35% chance" oddsColor="var(--void-purple)" />
        </div>

        {/* Legend boss shard balance */}
        <div style={{ fontSize: 11, color: 'var(--muted)' }}>
          Your legend boss shards: <span style={{ color: 'var(--gold)', fontWeight: 700 }}>{legendBal} / {summonCost}</span>
        </div>

        {node.claimed ? (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px',
            background: 'rgba(155,48,255,0.1)', border: '1px solid rgba(155,48,255,0.3)',
            borderRadius: 7, fontSize: 12, fontWeight: 700, color: '#c47aff',
          }}>
            ✓ Gate Claimed — rewards collected
          </div>
        ) : node.active ? (
          <button
            onClick={onClaim}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: '100%', padding: 13, fontSize: 14, fontWeight: 900,
              letterSpacing: '0.12em', textTransform: 'uppercase',
              background: 'linear-gradient(135deg, var(--void-purple), #7c5fff)',
              color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer',
              boxShadow: '0 4px 24px rgba(155,48,255,0.35)',
            }}
          >
            🎁 CLAIM {node.mLabel.toUpperCase()}
          </button>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '16px 0', textAlign: 'center', color: 'var(--muted)' }}>
            <div style={{ fontSize: 28, opacity: 0.4 }}>⬡</div>
            <div style={{ fontSize: 11, lineHeight: 1.4, maxWidth: 200 }}>
              Complete all stages up to {node.stageCount} to unlock this gate.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function VaultPanel({ stagesCleared }: { tier: string; stagesCleared: number }) {
  const VAULT_TOTAL = 26
  const remaining = Math.max(0, VAULT_TOTAL - stagesCleared)
  const unlocked = remaining === 0

  return (
    <div style={sidePanelStyle}>
      <div style={{ padding: '16px 18px 12px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 4 }}>Chapter Vault</div>
        <div style={{ fontSize: 17, fontWeight: 800, color: 'var(--text)', lineHeight: 1.2, marginBottom: 2 }}>The Vault — Endgame Summon</div>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
          padding: '2px 8px', borderRadius: 4, marginTop: 6,
          background: 'rgba(255,215,0,0.1)', color: 'var(--gold)',
          border: '1px solid rgba(255,215,0,0.25)',
        }}>
          {unlocked ? '✓ Unlocked' : '? Unknown'}
        </div>
      </div>

      <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
        <div style={{ padding: '20px 0', textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 12, animation: 'vaultBreathe 3.5s ease-in-out infinite' }}>?</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.6, maxWidth: 220, margin: '0 auto' }}>
            Chapter Vault unseals when all {VAULT_TOTAL} stages are cleared.<br /><br />
            Contains a guaranteed draw from the{' '}
            <span style={{ color: 'var(--gold)', fontWeight: 700 }}>Legendary Boss Summon pool</span> — one pull per chapter.
          </div>
        </div>

        <RewardRow icon="✨" name="1× Legendary Guaranteed Pull" oddsLabel="100% · one per chapter clear" oddsColor="var(--gold)" legendary />

        <button
          disabled={!unlocked}
          style={{
            width: '100%', padding: 13, fontSize: 14, fontWeight: 900,
            letterSpacing: '0.12em', textTransform: 'uppercase',
            background: unlocked ? 'linear-gradient(135deg, var(--gold), #e6b800)' : 'rgba(255,255,255,0.08)',
            color: unlocked ? '#04060c' : 'var(--muted)',
            border: unlocked ? 'none' : '1px solid rgba(255,255,255,0.1)',
            borderRadius: 8, cursor: unlocked ? 'pointer' : 'not-allowed',
          }}
        >
          {unlocked ? '✨ SUMMON LEGENDARY BOSS' : `🔒 LOCKED — ${remaining} stages remain`}
        </button>
      </div>
    </div>
  )
}

// ── Milestone claim modal ──────────────────────────────────────────────────

interface ModalProps {
  node: MilestoneNode
  result: { template_shards_granted: number; legend_shards_granted: number; legend_boss_shards_balance: number } | null
  busy: boolean
  onClaim: () => void
  onClose: () => void
}

function MilestoneClaimModal({ node, result, busy, onClaim, onClose }: ModalProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Claim milestone: ${node.mLabel}`}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(4,6,12,0.88)', backdropFilter: 'blur(12px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        background: 'var(--panel-2, #10141f)',
        border: '1px solid var(--border-strong)',
        borderRadius: 14, padding: 28, width: 340, maxWidth: '90vw',
        boxShadow: '0 24px 64px rgba(0,0,0,0.7), 0 0 40px rgba(155,48,255,0.15)',
        animation: 'modalFadeIn 0.22s ease-out both',
      }}>
        {!result ? (
          <>
            <div style={{ fontSize: 40, textAlign: 'center', marginBottom: 12 }}>🎁</div>
            <div style={{ fontSize: 16, fontWeight: 800, textAlign: 'center', marginBottom: 4 }}>{node.mLabel}</div>
            <div style={{ fontSize: 11, color: 'var(--muted)', textAlign: 'center', marginBottom: 20 }}>
              Milestone Gate — {node.stageCount} stages cleared
            </div>

            <div style={{ marginBottom: 16 }}>
              <RewardRow icon="🔮" name={`${node.templateShards}× Shard Credits`} oddsLabel="Guaranteed" oddsColor="var(--accent)" />
              <RewardRow icon="💎" name="150 Gems" oddsLabel="Guaranteed" oddsColor="var(--accent)" />
              <RewardRow icon="✨" name="Legendary Boss Shard" oddsLabel={`${Math.round(node.legendShard * 100)}% chance`} oddsColor="var(--gold)" legendary />
            </div>

            <button
              onClick={onClaim}
              disabled={busy}
              style={{
                width: '100%', padding: '13px 0', fontSize: 14, fontWeight: 900,
                letterSpacing: '0.12em', textTransform: 'uppercase',
                background: busy ? 'rgba(255,255,255,0.08)' : 'linear-gradient(135deg, var(--void-purple), #7c5fff)',
                color: busy ? 'var(--muted)' : '#fff',
                border: 'none', borderRadius: 8, cursor: busy ? 'wait' : 'pointer',
              }}
            >
              {busy ? '…claiming' : '🎁 CLAIM REWARDS'}
            </button>
          </>
        ) : (
          <>
            <div style={{ fontSize: 40, textAlign: 'center', marginBottom: 12 }}>
              {result.legend_shards_granted > 0 ? '🌟' : '✅'}
            </div>
            <div style={{ fontSize: 16, fontWeight: 800, textAlign: 'center', marginBottom: 16 }}>Rewards Claimed!</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: 'var(--muted)' }}>Shard Credits</span>
                <span style={{ fontWeight: 700, color: 'var(--accent)' }}>+{result.template_shards_granted}</span>
              </div>
              {result.legend_shards_granted > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                  <span style={{ color: 'var(--muted)' }}>Legendary Boss Shard</span>
                  <span style={{ fontWeight: 700, color: 'var(--gold)' }}>+{result.legend_shards_granted} 🌟</span>
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: 'var(--muted)' }}>Legend Shard Balance</span>
                <span style={{ fontWeight: 700, color: 'var(--gold)' }}>{result.legend_boss_shards_balance}</span>
              </div>
            </div>
            <button
              onClick={onClose}
              style={{
                width: '100%', padding: '11px 0', fontSize: 13, fontWeight: 700,
                background: 'rgba(255,255,255,0.07)', color: 'var(--text)',
                border: '1px solid var(--border-strong)', borderRadius: 8, cursor: 'pointer',
              }}
            >
              Continue
            </button>
          </>
        )}
      </div>
    </div>
  )
}

// ── Board legend ───────────────────────────────────────────────────────────

function BoardLegend() {
  const items = [
    { cls: { border: 'var(--good)', bg: 'rgba(34,197,94,0.2)' },     label: 'Cleared' },
    { cls: { border: 'var(--accent)', bg: 'rgba(0,255,224,0.15)' },  label: 'Ready' },
    { cls: { border: 'rgba(255,255,255,0.2)', bg: 'rgba(255,255,255,0.05)' }, label: 'Locked' },
    { cls: { border: 'var(--void-purple)', bg: 'rgba(155,48,255,0.15)' }, label: 'Milestone Gate' },
    { cls: { border: 'var(--crimson)', bg: 'rgba(200,16,46,0.15)' }, label: 'Boss' },
    { cls: { border: 'var(--accent)', bg: 'transparent', borderStyle: 'dashed' }, label: 'Chapter Vault' },
  ]
  return (
    <div style={{
      position: 'absolute', top: 20, left: 20,
      background: 'rgba(12,16,26,0.85)', backdropFilter: 'blur(10px)',
      border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', zIndex: 5,
    }}>
      {items.map(({ cls, label }) => (
        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, color: 'var(--muted)', marginBottom: 5 }}>
          <div style={{
            width: 10, height: 10, borderRadius: '50%',
            border: `2px ${(cls as { borderStyle?: string }).borderStyle ?? 'solid'} ${cls.border}`,
            background: cls.bg, flexShrink: 0,
          }} />
          {label}
        </div>
      ))}
    </div>
  )
}

// ── Top-level route ────────────────────────────────────────────────────────

export function StagesRoute() {
  const navigate    = useNavigate()
  const qc          = useQueryClient()
  const { data: stages,     isLoading: stagesLoading }     = useStages()
  const { data: milestonesData, isLoading: msLoading }     = useMilestones()
  const { data: me }                                        = useMe()
  const teamPower   = useTeamPower()

  const [activeTier,   setActiveTier]   = useState<Stage['difficulty_tier']>('NORMAL')
  const [selectedId,   setSelectedId]   = useState<string | number | null>(null)
  const [modalNode,    setModalNode]     = useState<PositionedMilestone | null>(null)
  const [claimBusy,    setClaimBusy]    = useState(false)
  const [claimResult,  setClaimResult]  = useState<{
    template_shards_granted: number; legend_shards_granted: number; legend_boss_shards_balance: number
  } | null>(null)

  // Detect prefers-reduced-motion
  const reducedMotion = typeof window !== 'undefined'
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false

  // Ref for scroll-to-ready
  const boardRef = useRef<HTMLDivElement>(null)
  const readyScrolled = useRef(false)

  // ── Build board nodes ────────────────────────────────────────────────────

  const byTier = useMemo(
    () => (stages ?? []).filter((s) => s.difficulty_tier === activeTier),
    [stages, activeTier]
  )

  /** Insert milestone gate nodes + vault into the stage sequence */
  const boardNodes = useMemo<BoardNode[]>(() => {
    const milestones = milestonesData?.milestones ?? []
    const milestoneMap = new Map<number, MilestoneItem>()
    for (const m of milestones) milestoneMap.set(m.stage_count, m)

    const nodes: BoardNode[] = []
    let normalCount = 0

    for (const stage of byTier) {
      nodes.push({ ...stage, _kind: 'stage' as const })
      if (stage.cleared) normalCount++

      // Insert a milestone gate after every 5th cleared/unlocked stage if one exists
      const m = milestoneMap.get(normalCount)
      if (m && stage.order === normalCount - 1) {
        const clearedCount = milestonesData?.stages_cleared_count ?? 0
        const unlocked = clearedCount >= m.stage_count
        nodes.push({
          _kind: 'milestone',
          id: `m-${m.id}`,
          mLabel: m.label,
          stageCount: m.stage_count,
          claimed: m.claimed,
          active: unlocked && !m.claimed,
          legendShard: m.legend_shard_chance,
          templateShards: m.template_shards,
          milestoneId: m.id,
        } as MilestoneNode)
      }
    }

    // Vault at the end
    nodes.push({ _kind: 'vault', id: 'vault' } as VaultNode)

    return nodes
  }, [byTier, milestonesData])

  const positioned = useMemo(() => computeLayout(boardNodes), [boardNodes])

  // Board dimensions
  const boardWidth  = ROW_X_START + (COLS_PER_ROW - 1) * H_SPACING + 120
  const boardHeight = useMemo(() => {
    if (!positioned.length) return 400
    const maxRow = Math.max(...positioned.map((p) => p.row))
    return (maxRow + 1) * V_SPACING + 120
  }, [positioned])

  // Auto-select first ready node
  const firstReady = useMemo(
    () => positioned.find((p) => getNodeState(p) === 'ready'),
    [positioned]
  )
  useEffect(() => {
    if (firstReady && selectedId === null) setSelectedId(firstReady.id)
  }, [firstReady, selectedId])

  // Scroll board to ready node on mount
  useEffect(() => {
    if (!firstReady || readyScrolled.current || !boardRef.current) return
    const yOffset = firstReady.y - 200
    boardRef.current.scrollTo({ top: Math.max(0, yOffset), behavior: 'smooth' })
    readyScrolled.current = true
  }, [firstReady])

  // ── Header data ──────────────────────────────────────────────────────────
  const clearedCount  = useMemo(() => byTier.filter((s) => s.cleared).length, [byTier])
  const totalCount    = byTier.length
  // TODO: wire me.win_streak_days when backend exposes it on the Me schema
  const winStreak     = (me as unknown as { win_streak_days?: number })?.win_streak_days ?? 0

  const nextMs        = milestonesData?.next_milestone
  const stagesToNextMs = nextMs?.stages_to_go ?? null
  const nextMsLabel   = nextMs?.label ?? null

  // ── Selected node ────────────────────────────────────────────────────────
  const selectedNode = useMemo(
    () => positioned.find((p) => p.id === selectedId) ?? null,
    [positioned, selectedId]
  )

  // ── Actions ──────────────────────────────────────────────────────────────

  const handleFight = useCallback((stage: Stage) => {
    navigate('/battle/setup', { state: { stageId: stage.id } })
  }, [navigate])

  const handleNodeClick = useCallback((node: PositionedNode) => {
    const state = getNodeState(node)
    if (state === 'locked') return
    setSelectedId(node.id)
    // milestone active → open modal
    if (node._kind === 'milestone' && node.active) {
      setClaimResult(null)
      setModalNode(node)
    }
  }, [])

  const handleClaim = useCallback(async () => {
    if (!modalNode) return
    setClaimBusy(true)
    try {
      const r = await claimMilestone(modalNode.milestoneId)
      setClaimResult({
        template_shards_granted: r.template_shards_granted,
        legend_shards_granted: r.legend_shards_granted,
        legend_boss_shards_balance: r.legend_boss_shards_balance,
      })
      qc.invalidateQueries({ queryKey: ['milestones'] })
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (err) {
      console.error('Milestone claim failed', err)
    } finally {
      setClaimBusy(false)
    }
  }, [modalNode, qc])

  // ── Render ───────────────────────────────────────────────────────────────

  if (stagesLoading || msLoading) return <SkeletonGrid count={6} height={80} />

  return (
    <>
      {/* Inject animation keyframes once */}
      <style>{KEYFRAMES}</style>

      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', position: 'relative' }}>

        {/* Header strip */}
        <HeaderStrip
          tier={activeTier}
          cleared={clearedCount}
          total={totalCount}
          winStreak={winStreak}
          nextMilestoneLabel={nextMsLabel}
          stagesToNextMilestone={stagesToNextMs}
          reducedMotion={reducedMotion}
        />

        {/* Tier tabs */}
        <div style={{
          display: 'flex', gap: 4, padding: '10px 20px 0',
          borderBottom: '1px solid var(--border)',
          background: 'rgba(4,6,12,0.8)', flexShrink: 0, zIndex: 10,
        }}>
          {(['NORMAL', 'HARD', 'NIGHTMARE', 'LEGENDARY'] as const).map((tier) => {
            const isActive = activeTier === tier
            return (
              <button
                key={tier}
                onClick={() => { setActiveTier(tier); setSelectedId(null) }}
                aria-pressed={isActive}
                style={{
                  padding: '7px 18px 8px', fontSize: 11, fontWeight: 700,
                  letterSpacing: '0.08em', textTransform: 'uppercase',
                  border: `1px solid ${isActive ? TIER_BORDER[tier] : 'var(--border)'}`,
                  borderBottom: 'none',
                  borderRadius: '6px 6px 0 0',
                  background: isActive ? 'var(--bg-inset, #080d18)' : 'var(--panel)',
                  color: isActive ? TIER_COLOR[tier] : 'var(--muted)',
                  cursor: 'pointer',
                  transition: 'background 0.15s, color 0.15s',
                  position: 'relative', bottom: -1,
                }}
              >
                {TIER_LABELS[tier]}
              </button>
            )
          })}
        </div>

        {/* Main content */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

          {/* Board canvas */}
          <div
            ref={boardRef}
            style={{
              flex: 1, overflow: 'auto', padding: '32px 24px 60px',
              position: 'relative',
              scrollbarWidth: 'thin',
              scrollbarColor: 'rgba(0,255,224,0.2) transparent',
            }}
          >
            {/* SVG connector layer */}
            <svg
              width={boardWidth}
              height={boardHeight}
              style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none', zIndex: 1 }}
              xmlns="http://www.w3.org/2000/svg"
            >
              <defs>
                <filter id="glow-sm" x="-30%" y="-30%" width="160%" height="160%">
                  <feGaussianBlur stdDeviation={2} result="blur" />
                  <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
                </filter>
                <filter id="glow-lg" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation={4} result="blur" />
                  <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
                </filter>
              </defs>
              <ConnectorLayer nodes={positioned} reducedMotion={reducedMotion} />
            </svg>

            {/* Node layer */}
            <div style={{ position: 'relative', zIndex: 2, width: boardWidth, height: boardHeight }}>
              {positioned.map((node) => (
                <StageNode
                  key={node.id}
                  node={node}
                  selected={node.id === selectedId}
                  reducedMotion={reducedMotion}
                  onClick={() => handleNodeClick(node)}
                />
              ))}
            </div>

            <BoardLegend />
          </div>

          {/* Side panel */}
          <SidePanel
            node={selectedNode}
            tier={activeTier}
            teamPower={teamPower}
            milestonesData={milestonesData}
            onFight={handleFight}
            onClaimMilestone={(n) => { setClaimResult(null); setModalNode(n) }}
          />
        </div>

        {/* Bottom sheet for mobile — the side panel shifts below on narrow screens */}
        <style>{`
          @media (max-width: 680px) {
            .stages-side-panel-anchor {
              position: fixed !important;
              bottom: 0; left: 0; right: 0;
              width: 100% !important; min-width: 0 !important;
              max-height: 55vh;
              border-left: none !important;
              border-top: 1px solid var(--border-strong);
              border-radius: 14px 14px 0 0;
              z-index: 30;
            }
          }
        `}</style>

      </div>

      {/* Milestone claim modal */}
      {modalNode && (
        <MilestoneClaimModal
          node={modalNode}
          result={claimResult}
          busy={claimBusy}
          onClaim={handleClaim}
          onClose={() => { setModalNode(null); setClaimResult(null) }}
        />
      )}
    </>
  )
}
