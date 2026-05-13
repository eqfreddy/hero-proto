import { useMemo, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchGear, unequipGear, toggleLockGear, salvageGear,
  ALL_SLOTS, ARMOR_SLOTS, SLOT_META, SET_META, RARITY_COLOR,
  type GearOut, type GearSlot, type GearRarity,
} from '../api/gear'
import { fetchCrafting } from '../api/crafting'
import { useHeroes } from '../hooks/useHeroes'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import { CoachMark } from '../components/CoachMark'
import { toast } from '../store/ui'

const RARITY_ORDER: GearRarity[] = ['LEGENDARY', 'EPIC', 'RARE', 'COMMON']

const RARITY_LABEL: Record<GearRarity, string> = {
  LEGENDARY: 'Legendary',
  EPIC: 'Epic',
  RARE: 'Rare',
  COMMON: 'Common',
}

const RARITY_EMOJI: Record<GearRarity, string> = {
  LEGENDARY: '🟡',
  EPIC: '🟣',
  RARE: '🔵',
  COMMON: '⚪',
}

type Tab = 'GEAR' | 'MATERIALS'

function gearPower(g: GearOut): number {
  const s = g.stats
  return (s.atk ?? 0) + (s.def ?? 0) + (s.spd ?? 0) * 4 + Math.round((s.hp ?? 0) / 10)
}

const SALVAGE_PREVIEW: Record<GearRarity, string> = {
  COMMON:    '1× Rusted Keyboard Key',
  RARE:      '2× Rusted Key + 1× Expired Cert + 50 coins',
  EPIC:      '2× Expired Cert + 1× Legacy Punch Card + 200 coins',
  LEGENDARY: '2× Legacy Punch Card + 1× On-Call Token + 500 coins',
}

// Top 3 stats by value, highest first
function topStats(g: GearOut): Array<[string, number]> {
  return Object.entries(g.stats)
    .filter(([, v]) => v != null && v > 0)
    .sort(([, a], [, b]) => (b as number) - (a as number))
    .slice(0, 3) as Array<[string, number]>
}

const STAT_ICON: Record<string, string> = {
  hp: '❤️', atk: '⚔️', def: '🛡️', spd: '💨',
}

export function InventoryRoute() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<Tab>('GEAR')
  const [slotFilter, setSlotFilter] = useState<'ALL' | GearSlot | 'NAMED' | 'ARMOR'>('ALL')
  // Set of collapsed rarity keys
  const [collapsedRarities, setCollapsedRarities] = useState<Set<GearRarity>>(new Set())

  const { data: gear, isLoading: gearLoading } = useQuery({ queryKey: ['gear'], queryFn: fetchGear })
  const { data: crafting, isLoading: craftLoading } = useQuery({ queryKey: ['crafting'], queryFn: fetchCrafting })
  const { data: heroes } = useHeroes()

  const isLoading = gearLoading || craftLoading
  if (isLoading) return <SkeletonGrid count={8} height={72} />

  const heroById = new Map((heroes ?? []).map((h) => [h.id, h]))
  const namedCount = (gear ?? []).filter((g) => !!g.name).length
  const materials = (crafting?.materials ?? []).filter((m) => m.quantity > 0)

  // Apply slot/named/armor filter, then group by rarity
  const filteredGear = useMemo(() => {
    const items = gear ?? []
    let out = items
    if (slotFilter === 'NAMED') out = items.filter((g) => !!g.name)
    else if (slotFilter === 'ARMOR') out = items.filter((g) => ARMOR_SLOTS.includes(g.slot))
    else if (slotFilter !== 'ALL') out = items.filter((g) => g.slot === slotFilter)
    return out
  }, [gear, slotFilter])

  // Group into rarity sections, each sorted named-first then by power desc
  const raritySections = useMemo(() => {
    return RARITY_ORDER
      .map((rarity) => {
        const items = filteredGear
          .filter((g) => g.rarity === rarity)
          .sort((a, b) => {
            if (!!a.name !== !!b.name) return a.name ? -1 : 1
            return gearPower(b) - gearPower(a)
          })
        return { rarity, items }
      })
      .filter((s) => s.items.length > 0)
  }, [filteredGear])

  const toggleCollapse = (r: GearRarity) => {
    setCollapsedRarities((prev) => {
      const next = new Set(prev)
      if (next.has(r)) next.delete(r)
      else next.add(r)
      return next
    })
  }

  const handleUnequip = async (g: GearOut) => {
    try {
      await unequipGear(g.id)
      qc.invalidateQueries({ queryKey: ['gear'] })
      qc.invalidateQueries({ queryKey: ['heroes'] })
      toast.success('Unequipped')
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  const handleLock = async (g: GearOut) => {
    try {
      await toggleLockGear(g.id)
      qc.invalidateQueries({ queryKey: ['gear'] })
      toast.success(g.locked ? 'Unlocked' : 'Locked')
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  const handleSalvage = async (g: GearOut) => {
    const preview = SALVAGE_PREVIEW[g.rarity]
    if (!confirm(`Salvage this ${g.rarity} ${g.slot}?\n\nYou will receive:\n${preview}\n\nThis cannot be undone.`)) return
    try {
      const result = await salvageGear(g.id)
      qc.invalidateQueries({ queryKey: ['gear'] })
      qc.invalidateQueries({ queryKey: ['crafting'] })
      const summary = Object.entries(result.yielded).map(([k, v]) => `+${v} ${k}`).join(', ')
      toast.success(`Salvaged! Got: ${summary}`)
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  return (
    <div className="stack">
      {/* ── Header ── */}
      <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>📦 Inventory</h2>
        <div className="muted" style={{ fontSize: 12 }}>
          {(gear ?? []).length} pieces · {namedCount} named · {materials.length} material types
        </div>
      </div>

      {/* ── Tab switcher ── */}
      <div style={{ display: 'flex', gap: 6 }}>
        {(['GEAR', 'MATERIALS'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            style={{
              fontSize: 12, padding: '5px 14px', borderRadius: 999, cursor: 'pointer',
              background: activeTab === t ? 'var(--accent)' : 'var(--bg-inset)',
              color: activeTab === t ? '#0b0d10' : 'var(--muted)',
              border: `1px solid ${activeTab === t ? 'var(--accent)' : 'var(--border)'}`,
              fontWeight: activeTab === t ? 700 : 500,
            }}
          >
            {t === 'GEAR' ? `⚔️ Gear (${(gear ?? []).length})` : `🧪 Materials (${materials.length})`}
          </button>
        ))}
      </div>

      {activeTab === 'MATERIALS' ? (
        <MaterialsPanel materials={materials} />
      ) : (
        <>
          {(!gear || gear.length === 0) ? (
            /* ── Empty state coach card ── */
            <div className="card" style={{
              padding: 28, textAlign: 'center',
              borderColor: 'var(--accent)', borderWidth: 1,
              background: 'linear-gradient(180deg, color-mix(in srgb, var(--accent) 6%, var(--panel)) 0%, var(--panel) 80%)',
            }}>
              <div style={{ fontSize: 36, marginBottom: 10 }}>📦</div>
              <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 6, color: 'var(--text)' }}>
                Your inventory is empty
              </div>
              <div className="muted" style={{ fontSize: 12, lineHeight: 1.6, maxWidth: 320, margin: '0 auto 16px' }}>
                Win battles to drop gear. Higher difficulty stages yield better rarity drops.
                Legendary pieces require Elite or higher.
              </div>
              <Link to="/app/stages">
                <button style={{
                  padding: '8px 20px', borderRadius: 999, fontSize: 13, cursor: 'pointer',
                  background: 'var(--accent)', color: '#0b0d10', fontWeight: 700, border: 'none',
                }}>
                  ⚔️ Go to Stages
                </button>
              </Link>
            </div>
          ) : (
            <>
              {/* ── Filter row + rarity toggle hint ── */}
              <CoachMark
                screenId="inventory"
                tooltip="Drag gear onto a hero slot to boost their stats."
                side="left"
              >
                <FilterRow value={slotFilter} onChange={setSlotFilter} totalNamed={namedCount} />
              </CoachMark>

              {raritySections.length === 0 ? (
                <EmptyState icon="🔎" message="No gear matches that filter." />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                  {raritySections.map(({ rarity, items }) => {
                    const color = RARITY_COLOR[rarity]
                    const collapsed = collapsedRarities.has(rarity)
                    return (
                      <section key={rarity}>
                        {/* Section header */}
                        <button
                          onClick={() => toggleCollapse(rarity)}
                          aria-expanded={!collapsed}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 8,
                            width: '100%', background: 'none', border: 'none',
                            padding: '6px 0', cursor: 'pointer', marginBottom: collapsed ? 0 : 10,
                            borderBottom: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
                          }}
                        >
                          <span style={{ color, fontSize: 14 }}>
                            {RARITY_EMOJI[rarity]} {RARITY_LABEL[rarity].toUpperCase()}
                          </span>
                          <span style={{
                            fontSize: 11, padding: '1px 7px', borderRadius: 999,
                            background: `color-mix(in srgb, ${color} 18%, transparent)`,
                            color, fontWeight: 700, border: `1px solid color-mix(in srgb, ${color} 35%, transparent)`,
                          }}>
                            {items.length} {items.length === 1 ? 'item' : 'items'}
                          </span>
                          <span className="muted" style={{ marginLeft: 'auto', fontSize: 11 }}>
                            {collapsed ? '▶ expand' : '▼ collapse'}
                          </span>
                        </button>

                        {/* Gear tile grid */}
                        {!collapsed && (
                          <div style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(3, 1fr)',
                            gap: 8,
                          }}
                          className="inv-grid"
                          >
                            {items.map((g) => (
                              <GearTile
                                key={g.id}
                                gear={g}
                                equippedOnName={g.equipped_on ? heroById.get(g.equipped_on)?.template.name : undefined}
                                onUnequip={() => handleUnequip(g)}
                                onJumpToHero={() => g.equipped_on && navigate(`/app/roster/${g.equipped_on}`)}
                                onLock={() => handleLock(g)}
                                onSalvage={() => handleSalvage(g)}
                              />
                            ))}
                          </div>
                        )}
                      </section>
                    )
                  })}
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* Responsive grid styles injected once */}
      <style>{`
        @media (max-width: 700px) {
          .inv-grid { grid-template-columns: 1fr !important; }
        }
        @media (min-width: 701px) and (max-width: 1023px) {
          .inv-grid { grid-template-columns: repeat(2, 1fr) !important; }
        }
      `}</style>
    </div>
  )
}

// ── Gear tile (compact ~80px tall when no flavor) ────────────────────────────

function GearTile({ gear, equippedOnName, onUnequip, onJumpToHero, onLock, onSalvage }: {
  gear: GearOut
  equippedOnName?: string
  onUnequip: () => void
  onJumpToHero: () => void
  onLock: () => void
  onSalvage: () => void
}) {
  const meta = SLOT_META[gear.slot]
  const set = SET_META[gear.set]
  const isNamed = !!gear.name
  const rarityColor = RARITY_COLOR[gear.rarity]
  const stats = topStats(gear)

  return (
    <div
      className="card"
      style={{
        padding: '10px 12px',
        borderLeft: `3px solid ${rarityColor}`,
        borderTop: '1px solid var(--border)',
        borderRight: '1px solid var(--border)',
        borderBottom: '1px solid var(--border)',
        background: isNamed
          ? `linear-gradient(135deg, color-mix(in srgb, ${rarityColor} 10%, var(--panel)) 0%, var(--panel) 70%)`
          : 'var(--panel)',
        position: 'relative',
        minHeight: 0,
      }}
    >
      {/* Row 1: slot icon + name + badges */}
      <div className="row" style={{ alignItems: 'center', gap: 8, minWidth: 0 }}>
        <div style={{
          width: 30, height: 30, borderRadius: 'var(--radius-sm)',
          background: 'var(--bg-inset)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 16, flexShrink: 0,
          border: `1px solid color-mix(in srgb, ${rarityColor} 40%, transparent)`,
        }}>
          {meta.icon}
        </div>

        <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
          <div style={{
            fontWeight: 700, fontSize: 12,
            color: isNamed ? rarityColor : 'var(--text)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {gear.name ?? meta.label}
          </div>
          <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 1 }}>
            {meta.label} · {set.label}
          </div>
        </div>

        {/* Badges: lock + named */}
        <div style={{ display: 'flex', gap: 3, flexShrink: 0 }}>
          {gear.locked && (
            <span title="Locked" style={{
              fontSize: 11, lineHeight: 1, padding: '2px 5px', borderRadius: 4,
              background: 'color-mix(in srgb, var(--accent) 15%, transparent)',
              border: '1px solid var(--accent)', color: 'var(--accent)',
            }}>
              🔒
            </span>
          )}
          {isNamed && (
            <span title="Named piece" style={{
              fontSize: 9, fontWeight: 800, padding: '2px 5px', borderRadius: 4,
              background: `color-mix(in srgb, ${rarityColor} 20%, transparent)`,
              border: `1px solid ${rarityColor}`, color: rarityColor,
              letterSpacing: 0.3, textTransform: 'uppercase',
            }}>
              ✨
            </span>
          )}
        </div>
      </div>

      {/* Flavor text for named pieces */}
      {gear.flavor && (
        <div style={{
          marginTop: 6, fontSize: 10, fontStyle: 'italic', lineHeight: 1.4,
          color: 'var(--muted)', borderLeft: `2px solid color-mix(in srgb, ${rarityColor} 50%, transparent)`,
          paddingLeft: 6,
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}>
          "{gear.flavor}"
        </div>
      )}

      {/* Row 2: top 3 stats inline */}
      <div style={{ marginTop: 6, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {stats.map(([k, v]) => (
          <span key={k} style={{ fontSize: 11, color: 'var(--text)', whiteSpace: 'nowrap' }}>
            {STAT_ICON[k]}<strong style={{ marginLeft: 2 }}>{k.toUpperCase()}</strong>
            <span style={{ color: 'var(--muted)', marginLeft: 2 }}>+{v}</span>
          </span>
        ))}
      </div>

      {/* Row 3: equipped / actions */}
      <div style={{ marginTop: 7, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 4 }}>
        {gear.equipped_on ? (
          <button
            onClick={onJumpToHero}
            style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 4, cursor: 'pointer',
              background: 'color-mix(in srgb, var(--good) 12%, transparent)',
              border: '1px solid var(--good)', color: 'var(--good)',
              flex: 1, textAlign: 'left', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}
            title={`Equipped on ${equippedOnName ?? 'hero'}`}
          >
            ⚔ {equippedOnName ?? 'hero'} →
          </button>
        ) : (
          <span style={{ fontSize: 10, color: 'var(--muted)', fontStyle: 'italic' }}>Unequipped</span>
        )}

        <div style={{ display: 'flex', gap: 3, flexShrink: 0 }}>
          {gear.equipped_on && (
            <button
              onClick={onUnequip}
              style={{
                fontSize: 10, padding: '2px 7px', borderRadius: 4, cursor: 'pointer',
                background: 'var(--bg-inset)', border: '1px solid var(--border)', color: 'var(--muted)',
              }}
              title="Unequip"
            >
              ↩
            </button>
          )}
          {!isNamed && (
            <>
              <button
                onClick={onLock}
                style={{
                  fontSize: 10, padding: '2px 7px', borderRadius: 4, cursor: 'pointer',
                  background: 'var(--bg-inset)', border: '1px solid var(--border)', color: 'var(--muted)',
                }}
                title={gear.locked ? 'Unlock' : 'Lock to protect from salvage'}
              >
                {gear.locked ? '🔓' : '🔒'}
              </button>
              <button
                onClick={onSalvage}
                disabled={gear.locked}
                style={{
                  fontSize: 10, padding: '2px 7px', borderRadius: 4, cursor: gear.locked ? 'not-allowed' : 'pointer',
                  background: gear.locked ? 'var(--bg-inset)' : 'color-mix(in srgb, var(--bad) 10%, transparent)',
                  border: `1px solid ${gear.locked ? 'var(--border)' : 'var(--bad)'}`,
                  color: gear.locked ? 'var(--muted)' : 'var(--bad)',
                  opacity: gear.locked ? 0.4 : 1,
                }}
                title={gear.locked ? 'Unlock first to salvage' : `Salvage for: ${SALVAGE_PREVIEW[gear.rarity]}`}
              >
                ⚒
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Materials panel ──────────────────────────────────────────────────────────

const MATERIAL_RARITY_COLOR: Record<string, string> = {
  COMMON: 'var(--r-common)',
  UNCOMMON: 'var(--r-uncommon, #6fa)',
  RARE: 'var(--r-rare)',
  EPIC: 'var(--r-epic)',
  LEGENDARY: 'var(--r-legendary)',
}

function MaterialsPanel({ materials }: { materials: Array<{ code: string; name: string; rarity: string; description: string; icon: string; quantity: number }> }) {
  if (materials.length === 0) {
    return <EmptyState icon="🧪" message="No materials yet. Win battles and raids to collect crafting components." />
  }
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
      {materials.map((m) => {
        const color = MATERIAL_RARITY_COLOR[m.rarity] ?? 'var(--muted)'
        return (
          <div key={m.code} className="card" style={{ padding: 12, borderColor: color, borderWidth: 1 }}>
            <div className="row" style={{ gap: 10, alignItems: 'flex-start' }}>
              <div style={{
                width: 40, height: 40, borderRadius: 8, background: 'var(--bg-inset)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 22, flexShrink: 0, border: `1px solid ${color}`,
              }}>
                {m.icon}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 13, color }}>{m.name}</div>
                <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 1 }}>{m.rarity}</div>
              </div>
              <div style={{
                fontSize: 18, fontWeight: 900, color,
                alignSelf: 'center', minWidth: 32, textAlign: 'right',
              }}>
                ×{m.quantity}
              </div>
            </div>
            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted)', fontStyle: 'italic', lineHeight: 1.4 }}>
              {m.description}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Filter row ───────────────────────────────────────────────────────────────

function FilterRow({ value, onChange, totalNamed }: {
  value: 'ALL' | GearSlot | 'NAMED' | 'ARMOR'
  onChange: (v: 'ALL' | GearSlot | 'NAMED' | 'ARMOR') => void
  totalNamed: number
}) {
  const baseStyle = { fontSize: 12, padding: '5px 12px', borderRadius: 999, cursor: 'pointer' as const }
  const Chip = ({ k, label, icon, count }: { k: typeof value; label: string; icon?: string; count?: number }) => {
    const active = value === k
    return (
      <button
        onClick={() => onChange(k)}
        aria-pressed={active}
        style={{
          ...baseStyle,
          background: active ? 'var(--accent)' : 'var(--bg-inset)',
          color: active ? '#0b0d10' : 'var(--muted)',
          border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
          fontWeight: active ? 700 : 500,
        }}
      >
        {icon && <span style={{ marginRight: 4 }}>{icon}</span>}{label}
        {typeof count === 'number' && count > 0 && (
          <span style={{
            marginLeft: 6, padding: '0 6px', borderRadius: 8,
            background: active ? '#0b0d10' : 'var(--bad)',
            color: active ? 'var(--accent)' : 'white',
            fontSize: 10, fontWeight: 800,
          }}>{count}</span>
        )}
      </button>
    )
  }

  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      <Chip k="ALL" label="All" />
      <Chip k="NAMED" label="Named" icon="✨" count={totalNamed} />
      <Chip k="ARMOR" label="Armor" />
      {ALL_SLOTS.map((s) => (
        <Chip key={s} k={s} label={SLOT_META[s].label} icon={SLOT_META[s].icon} />
      ))}
    </div>
  )
}
