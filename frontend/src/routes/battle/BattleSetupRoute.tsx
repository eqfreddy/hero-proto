import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { postBattle, postInteractiveStart } from '../../api/battles'
import { fetchRaid, postRaidInteractiveStart } from '../../api/raids'
import { useUiStore } from '../../store/ui'
import { TierBadge } from '../../components/TierBadge'
import type { Hero, HeroTemplate, Raid, Stage } from '../../types'
import { isNative } from '../../native'

interface TeamPreset {
  id: number
  name: string
  team: number[]
  updated_at: string
}

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

const RARITY_ORDER: HeroTemplate['rarity'][] = [
  'COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'MYTH',
]

// A hero is "vanilla" when nothing distinguishes it from another copy of
// the same template — no XP, no skill-up, no ascension above its rarity
// baseline. Vanilla copies stack into a single button with a ×N badge;
// any modification splits them back out so the player can pick the
// stronger one.
function isVanilla(h: Hero): boolean {
  return h.level === 1 && h.special_level === 0 && h.stars === 1
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

function useTeamPresets() {
  return useQuery<TeamPreset[]>({
    queryKey: ['team-presets'],
    queryFn: () => apiFetch('/me/team-presets'),
    staleTime: 30_000,
  })
}

export default function BattleSetupRoute() {
  const navigate = useNavigate()
  const location = useLocation()
  const query = new URLSearchParams(location.search)
  const raidId = Number(query.get('raid_id') ?? '')
  const isRaidSetup = Number.isFinite(raidId) && raidId > 0
  const addToast = useUiStore(s => s.addToast)
  const queryClient = useQueryClient()
  const { data: heroes = [] } = useHeroes()
  const { data: stages = [] } = useStages()
  const { data: presets = [] } = useTeamPresets()
  const { data: raid } = useQuery<Raid>({
    queryKey: ['raid', raidId],
    queryFn: () => fetchRaid(raidId),
    enabled: isRaidSetup,
  })

  const [team, setTeam] = useState<(number | null)[]>([null, null, null])
  const [selectedStageId, setSelectedStageId] = useState<number | null>(
    (location.state as { stageId?: number } | null)?.stageId ?? null
  )
  // Default to interactive combat so players see battle verbs immediately.
  // 2D classic remains available as a replay-style fallback on web.
  // Native (Capacitor) can't serve the legacy 2D battle-arena.html static
  // page, so force interactive 3D there. The toggle is also hidden below
  // when running native — see Mode selector.
  const [interactive, setInteractive] = useState(true)
  const nativeOnly3D = isNative()
  const [submitting, setSubmitting] = useState(false)
  const [roleFilter, setRoleFilter] = useState<'ALL' | 'ATK' | 'DEF' | 'SUP'>('ALL')
  const [rarityFilter, setRarityFilter] = useState<'ALL' | HeroTemplate['rarity']>('ALL')

  const teamIds = team.filter((id): id is number => id !== null)
  const teamHeroes = teamIds.map(id => heroes.find(h => h.id === id)).filter(Boolean) as typeof heroes
  const teamPower = teamHeroes.reduce((sum, h) => sum + (h.power ?? 0), 0)

  // Faction synergy preview — mirrors team_faction_synergy() in app/combat.py.
  // 3 same-faction = +10% ATK, 4 = +15/+5, 5 = +20/+10.
  const factionCounts: Record<string, number> = {}
  for (const h of teamHeroes) {
    const f = h.template?.faction
    if (f && f !== 'NEUTRAL') factionCounts[f] = (factionCounts[f] ?? 0) + 1
  }
  const dominant = Object.entries(factionCounts).sort((a, b) => b[1] - a[1])[0]
  const synergy = dominant && dominant[1] >= 3
    ? {
        faction: dominant[0],
        count: dominant[1],
        atk: dominant[1] === 3 ? 10 : dominant[1] === 4 ? 15 : 20,
        def: dominant[1] === 3 ? 0  : dominant[1] === 4 ? 5  : 10,
      }
    : null
  const oneAwaySynergy = !synergy && dominant && dominant[1] === 2
    ? { faction: dominant[0], needs: 1 }
    : null

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

  function loadPreset(p: TeamPreset) {
    const owned = new Set(heroes.map(h => h.id))
    const clean = p.team.filter(id => owned.has(id)).slice(0, 3)
    if (clean.length === 0) {
      addToast(`Preset "${p.name}" — none of its heroes are still owned`, 'info')
      return
    }
    setTeam([clean[0] ?? null, clean[1] ?? null, clean[2] ?? null])
  }

  async function savePreset() {
    if (teamIds.length === 0) {
      addToast('Pick at least one hero to save', 'info')
      return
    }
    const name = window.prompt('Preset name:', presets[0]?.name ?? 'My team')
    if (!name) return
    try {
      await apiFetch('/me/team-presets', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim().slice(0, 32), team: teamIds }),
      })
      queryClient.invalidateQueries({ queryKey: ['team-presets'] })
      addToast(`Saved "${name}"`, 'success')
    } catch (e) {
      addToast(e instanceof Error ? e.message : 'Couldn\'t save preset', 'error')
    }
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
    if (teamIds.length === 0) return
    if (!isRaidSetup && !selectedStageId) return
    setSubmitting(true)
    try {
      if (isRaidSetup) {
        const state = await postRaidInteractiveStart(raidId, teamIds)
        navigate(`/battle/${state.session_id}/play`, { state: { initState: state, encounterType: 'raid' } })
        return
      }
      const stageId = selectedStageId
      if (stageId == null) return
      if (interactive) {
        const state = await postInteractiveStart({ stage_id: stageId, team: teamIds })
        navigate(`/battle/${state.session_id}/play`, { state: { initState: state, encounterType: 'stage' } })
      } else {
        const battle = await postBattle({ stage_id: stageId, team: teamIds, target_priority: 'lowest_hp' })
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
        <button onClick={() => navigate(isRaidSetup ? '/app/raids' : '/app/stages')} style={{ background: 'none', border: 'none', color: 'var(--color-muted)', cursor: 'pointer', fontSize: 14 }}>
          ← Back
        </button>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800 }}>{isRaidSetup ? 'Raid Setup' : 'Battle Setup'}</h1>
      </div>

      {/* Stage selector — grouped by difficulty tier, each tier a
          color-coded collapsible group. */}
      {!isRaidSetup && <section style={{ marginBottom: 24 }}>
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
      </section>}

      {/* Team builder */}
      <section style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
          <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 1, margin: 0 }}>
            Your Team <span style={{ fontWeight: 400, color: 'var(--color-muted)' }}>— Power {teamPower}</span>
            {selectedStage?.recommended_power != null && teamIds.length > 0 && (() => {
              const rec = selectedStage.recommended_power
              const delta = teamPower - rec
              const ok = delta >= 0
              const tag = ok ? '✓ above rec' : `${Math.round((1 - teamPower / rec) * 100)}% below rec`
              return (
                <span style={{
                  marginLeft: 8, fontSize: 11, fontWeight: 700,
                  color: ok ? '#7fc88a' : (delta > -rec * 0.2 ? '#e8a35a' : '#e85a78'),
                }}>· {tag}</span>
              )
            })()}
            {synergy && (
              <span style={{
                marginLeft: 8, fontSize: 11, fontWeight: 700,
                color: '#ffd86b',
              }} title={`${synergy.count} × ${synergy.faction} → +${synergy.atk}% ATK${synergy.def ? `, +${synergy.def}% DEF` : ''}`}>
                · ★ {synergy.faction} ×{synergy.count} → +{synergy.atk}% ATK{synergy.def ? `, +${synergy.def}% DEF` : ''}
              </span>
            )}
            {oneAwaySynergy && (
              <span style={{
                marginLeft: 8, fontSize: 11, fontWeight: 600,
                color: 'rgba(255,216,107,0.6)',
              }} title="One more same-faction hero unlocks synergy">
                · +1 {oneAwaySynergy.faction} = +10% ATK
              </span>
            )}
          </h2>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button onClick={useLastTeam} style={miniBtn}>🕘 Last team</button>
            <button onClick={autoTeam} style={miniBtn}>⚡ Auto</button>
            <button onClick={savePreset} style={miniBtn}>💾 Save preset</button>
            <button onClick={clearTeam} style={miniBtn}>✕ Clear</button>
          </div>
        </div>
        {presets.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
            <span style={{ fontSize: 11, color: 'var(--color-muted)', alignSelf: 'center', marginRight: 2 }}>Presets:</span>
            {presets.map(p => (
              <button
                key={p.id}
                onClick={() => loadPreset(p)}
                style={{
                  ...chipBtn,
                  background: 'var(--color-surface)',
                  color: 'var(--color-text)',
                  borderColor: 'rgba(255,255,255,0.18)',
                }}
                title={`Load preset: ${p.name}`}
              >📋 {p.name}</button>
            ))}
          </div>
        )}
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

        {/* Roster — grouped by rarity, each group a color-coded
            collapsible section. Vanilla duplicates (level 1, 1★, no
            skill-ups) stack into one button with a ×N badge; modified
            copies show separately so the player can pick the stronger
            one. */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {RARITY_ORDER.map(rarity => {
            if (rarityFilter !== 'ALL' && rarityFilter !== rarity) return null
            const rarityHeroes = heroes
              .filter(h => h.template.rarity === rarity)
              .filter(h => roleFilter === 'ALL' || h.template.role === roleFilter)
            if (rarityHeroes.length === 0) return null
            const rarityColor = RARITY_VAR[rarity]

            // Bucket: vanilla copies share a key per template; modified
            // heroes each get their own bucket (unique by instance id).
            const buckets = new Map<string, Hero[]>()
            for (const h of rarityHeroes) {
              const key = isVanilla(h) ? `T${h.template.id}` : `I${h.id}`
              const arr = buckets.get(key) ?? []
              arr.push(h)
              buckets.set(key, arr)
            }
            const entries = [...buckets.values()].sort(
              (a, b) => (b[0].power ?? 0) - (a[0].power ?? 0),
            )

            return (
              <details
                key={rarity}
                open={rarityFilter === rarity || rarityHeroes.some(h => team.includes(h.id))}
                style={{
                  background: `color-mix(in srgb, ${rarityColor} 6%, var(--color-surface))`,
                  border: `1px solid color-mix(in srgb, ${rarityColor} 35%, transparent)`,
                  borderRadius: 8,
                  overflow: 'hidden',
                }}
              >
                <summary style={{
                  padding: '8px 14px', cursor: 'pointer', userSelect: 'none',
                  background: `color-mix(in srgb, ${rarityColor} 18%, var(--color-surface))`,
                  color: rarityColor,
                  fontSize: 12, fontWeight: 800, letterSpacing: 0.5, textTransform: 'uppercase',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                }}>
                  <span>{rarity} <span style={{ opacity: 0.7, fontWeight: 600, marginLeft: 6 }}>({rarityHeroes.length})</span></span>
                  <span style={{ fontSize: 11, opacity: 0.6, fontWeight: 600 }}>{entries.length} unique</span>
                </summary>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: 10 }}>
                  {entries.map(bucket => {
                    const rep = bucket[0]
                    const stacked = bucket.length > 1
                    // For a stack, "selected" reflects how many of its
                    // instances are currently slotted; clicking adds the
                    // next un-slotted instance.
                    const slottedCount = bucket.filter(h => team.includes(h.id)).length
                    const remaining = bucket.length - slottedCount
                    const onClick = () => {
                      const next = bucket.find(h => !team.includes(h.id))
                      if (next) toggleHero(next.id)
                      else if (slottedCount > 0) {
                        // All slotted — pop the most-recently slotted one off.
                        const last = [...bucket].reverse().find(h => team.includes(h.id))
                        if (last) toggleHero(last.id)
                      }
                    }
                    const fullySelected = remaining === 0 && slottedCount > 0
                    return (
                      <button
                        key={stacked ? `stack-${rep.template.id}` : `inst-${rep.id}`}
                        onClick={onClick}
                        style={{
                          padding: '6px 10px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                          background: fullySelected
                            ? `color-mix(in srgb, ${rarityColor} 35%, var(--color-surface))`
                            : slottedCount > 0
                            ? `color-mix(in srgb, ${rarityColor} 22%, var(--color-surface))`
                            : `color-mix(in srgb, ${rarityColor} 10%, var(--color-surface))`,
                          color: rarityColor,
                          border: `1px solid ${slottedCount > 0 ? rarityColor : `color-mix(in srgb, ${rarityColor} 45%, transparent)`}`,
                          boxShadow: fullySelected ? `0 0 0 1px ${rarityColor}` : 'none',
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                        }}
                        title={stacked
                          ? `${bucket.length} vanilla copies — click to add the next, click again to remove`
                          : `Lv ${rep.level} · ${rep.stars}★ · skill ${rep.special_level + 1}`}
                      >
                        <span>{rep.template.name}</span>
                        {stacked ? (
                          <span style={{ fontSize: 11, fontWeight: 800, opacity: 0.85 }}>
                            ×{remaining}{slottedCount > 0 ? ` (${slottedCount} in team)` : ''}
                          </span>
                        ) : (
                          <span style={{ opacity: 0.7, fontWeight: 500 }}>
                            Lv{rep.level}·{rep.stars}★ ({rep.power})
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>
              </details>
            )
          })}
        </div>
      </section>

      {/* Mode selector — 2D/3D segmented pill, then Fight button.
          Hidden on native: legacy 2D viewer is an HTML page served by the
          backend and can't be reached from the Capacitor file:// origin. */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
        {!nativeOnly3D && !isRaidSetup && (
          <div role="radiogroup" aria-label="Battle viewer" style={{
            display: 'inline-flex', padding: 3, borderRadius: 999,
            background: 'rgba(12,16,26,0.6)', border: '1px solid var(--border)',
            backdropFilter: 'blur(6px)',
          }}>
            <button
              role="radio" aria-checked={!interactive}
              onClick={() => setInteractive(false)}
              style={{
                padding: '6px 16px', borderRadius: 999, fontSize: 12, fontWeight: 700, letterSpacing: 0.4,
                border: 'none', cursor: 'pointer',
                background: !interactive ? 'var(--accent)' : 'transparent',
                color: !interactive ? '#0b0d10' : 'var(--muted)',
                transition: 'all 0.15s',
              }}
            >
              2D Classic
            </button>
            <button
              role="radio" aria-checked={interactive}
              onClick={() => setInteractive(true)}
              style={{
                padding: '6px 16px', borderRadius: 999, fontSize: 12, fontWeight: 700, letterSpacing: 0.4,
                border: 'none', cursor: 'pointer',
                background: interactive ? 'var(--accent)' : 'transparent',
                color: interactive ? '#0b0d10' : 'var(--muted)',
                transition: 'all 0.15s',
              }}
            >
              Manual 3D
            </button>
          </div>
        )}
        <button
          onClick={handleFight}
          disabled={teamIds.length === 0 || (!isRaidSetup && !selectedStageId) || submitting || (isRaidSetup && !raid)}
          style={{
            padding: '14px 48px', borderRadius: 10, fontSize: 16, fontWeight: 900, letterSpacing: 1.2, cursor: 'pointer',
            background: 'var(--accent)', color: '#0b0d10', border: 'none',
            boxShadow: '0 6px 24px rgba(0, 255, 224, 0.25)',
            opacity: (teamIds.length === 0 || (!isRaidSetup && !selectedStageId) || submitting || (isRaidSetup && !raid)) ? 0.4 : 1,
          }}
        >
          {submitting ? 'STARTING...' : isRaidSetup ? 'RAID ATTACK!' : 'FIGHT!'}
        </button>
      </div>
    </div>
  )
}
