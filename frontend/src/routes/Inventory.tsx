import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
import { toast } from '../store/ui'

const RARITY_ORDER: GearRarity[] = ['LEGENDARY', 'EPIC', 'RARE', 'COMMON']

type Tab = 'GEAR' | 'MATERIALS'

function gearPower(g: GearOut): number {
  const s = g.stats
  return (s.atk ?? 0) + (s.def ?? 0) + (s.spd ?? 0) * 4 + Math.round((s.hp ?? 0) / 10)
}

// Salvage preview text so user knows what they're getting before confirming.
const SALVAGE_PREVIEW: Record<GearRarity, string> = {
  COMMON:    '1× Rusted Keyboard Key',
  RARE:      '2× Rusted Key + 1× Expired Cert + 50 coins',
  EPIC:      '2× Expired Cert + 1× Legacy Punch Card + 200 coins',
  LEGENDARY: '2× Legacy Punch Card + 1× On-Call Token + 500 coins',
}

export function InventoryRoute() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<Tab>('GEAR')
  const [slotFilter, setSlotFilter] = useState<'ALL' | GearSlot | 'NAMED' | 'ARMOR'>('ALL')

  const { data: gear, isLoading: gearLoading } = useQuery({ queryKey: ['gear'], queryFn: fetchGear })
  const { data: crafting, isLoading: craftLoading } = useQuery({ queryKey: ['crafting'], queryFn: fetchCrafting })
  const { data: heroes } = useHeroes()

  const filtered = useMemo(() => {
    const items = gear ?? []
    let out = items
    if (slotFilter === 'NAMED') out = items.filter((g) => !!g.name)
    else if (slotFilter === 'ARMOR') out = items.filter((g) => ARMOR_SLOTS.includes(g.slot))
    else if (slotFilter !== 'ALL') out = items.filter((g) => g.slot === slotFilter)
    return [...out].sort((a, b) => {
      if (!!a.name !== !!b.name) return a.name ? -1 : 1
      const ra = RARITY_ORDER.indexOf(a.rarity)
      const rb = RARITY_ORDER.indexOf(b.rarity)
      if (ra !== rb) return ra - rb
      return gearPower(b) - gearPower(a)
    })
  }, [gear, slotFilter])

  const isLoading = gearLoading || craftLoading
  if (isLoading) return <SkeletonGrid count={8} height={80} />

  const heroById = new Map((heroes ?? []).map((h) => [h.id, h]))
  const namedCount = (gear ?? []).filter((g) => !!g.name).length
  const materials = (crafting?.materials ?? []).filter((m) => m.quantity > 0)

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
      <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>📦 Inventory</h2>
        <div className="muted" style={{ fontSize: 12 }}>
          {(gear ?? []).length} pieces · {namedCount} named · {materials.length} material types
        </div>
      </div>

      {/* Tab switcher */}
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
            <EmptyState icon="📦" message="No gear yet. Win battles or beat story stages to earn pieces." />
          ) : (
            <>
              <FilterRow value={slotFilter} onChange={setSlotFilter} totalNamed={namedCount} />
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12,
              }}>
                {filtered.map((g) => (
                  <GearCard
                    key={g.id}
                    gear={g}
                    equippedOnName={g.equipped_on ? heroById.get(g.equipped_on)?.template.name : undefined}
                    onUnequip={() => handleUnequip(g)}
                    onJumpToHero={() => g.equipped_on && navigate(`/app/roster/${g.equipped_on}`)}
                    onLock={() => handleLock(g)}
                    onSalvage={() => handleSalvage(g)}
                  />
                ))}
                {filtered.length === 0 && (
                  <div style={{ gridColumn: '1 / -1' }}>
                    <EmptyState icon="🔎" message="No gear matches that filter." />
                  </div>
                )}
              </div>
            </>
          )}
        </>
      )}
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
  const Tab = ({ k, label, icon, count }: { k: typeof value; label: string; icon?: string; count?: number }) => {
    const active = value === k
    return (
      <button
        onClick={() => onChange(k)}
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
      <Tab k="ALL" label="All" />
      <Tab k="NAMED" label="Named" icon="✨" count={totalNamed} />
      <Tab k="ARMOR" label="Armor" />
      {ALL_SLOTS.map((s) => (
        <Tab key={s} k={s} label={SLOT_META[s].label} icon={SLOT_META[s].icon} />
      ))}
    </div>
  )
}

// ── Gear card ────────────────────────────────────────────────────────────────

function GearCard({ gear, equippedOnName, onUnequip, onJumpToHero, onLock, onSalvage }: {
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

  return (
    <div className="card" style={{
      padding: 14,
      borderColor: isNamed ? rarityColor : gear.locked ? 'var(--accent)' : 'var(--border)',
      borderWidth: isNamed || gear.locked ? 2 : 1,
      background: isNamed
        ? `linear-gradient(180deg, color-mix(in srgb, ${rarityColor} 14%, var(--panel)) 0%, var(--panel) 60%)`
        : 'var(--panel)',
      position: 'relative',
    }}>
      {isNamed && (
        <span style={{
          position: 'absolute', top: -8, right: 12,
          fontSize: 10, fontWeight: 800, padding: '2px 8px',
          borderRadius: 999, background: rarityColor, color: '#0b0d10',
          letterSpacing: 0.5, textTransform: 'uppercase',
        }}>
          ✨ Named
        </span>
      )}
      {gear.locked && !isNamed && (
        <span style={{
          position: 'absolute', top: -8, right: 12,
          fontSize: 10, fontWeight: 800, padding: '2px 8px',
          borderRadius: 999, background: 'var(--accent)', color: '#0b0d10',
          letterSpacing: 0.5,
        }}>
          🔒 Locked
        </span>
      )}

      <div className="row" style={{ alignItems: 'flex-start', gap: 10 }}>
        <div style={{
          width: 46, height: 46, borderRadius: 'var(--radius)',
          background: 'var(--bg-inset)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 24, flexShrink: 0,
          border: `1px solid ${isNamed ? rarityColor : 'var(--border)'}`,
        }}>
          {meta.icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: isNamed ? rarityColor : 'var(--text)' }}>
            {gear.name ?? meta.label}
          </div>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
            {meta.label} · <span style={{ color: rarityColor }}>{gear.rarity}</span> · {set.label}
          </div>
        </div>
      </div>

      {gear.flavor && (
        <div style={{
          marginTop: 8, fontSize: 11, fontStyle: 'italic', lineHeight: 1.5,
          color: 'var(--muted)', borderLeft: `2px solid ${rarityColor}`, paddingLeft: 8,
        }}>
          "{gear.flavor}"
        </div>
      )}

      <div style={{ marginTop: 10, display: 'flex', gap: 10, flexWrap: 'wrap', fontSize: 12 }}>
        {Object.entries(gear.stats).map(([k, v]) => (
          <span key={k} style={{ color: 'var(--text)' }}>
            <span className="muted" style={{ marginRight: 2 }}>
              {k === 'hp' ? '❤️' : k === 'atk' ? '⚔️' : k === 'def' ? '🛡️' : '💨'}
            </span>
            <strong>{k.toUpperCase()}</strong> +{v}
          </span>
        ))}
      </div>

      <div style={{ marginTop: 10, fontSize: 11, color: 'var(--muted)' }}>
        Set bonus: {set.bonus} <span className="muted">({set.pieces}-pc)</span>
      </div>

      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {gear.equipped_on ? (
          <div className="row" style={{ justifyContent: 'space-between', gap: 6 }}>
            <button onClick={onJumpToHero} style={{ fontSize: 11, flex: 1 }}>
              Equipped on {equippedOnName ?? 'hero'} →
            </button>
            <button onClick={onUnequip} className="secondary" style={{ fontSize: 11 }}>
              Unequip
            </button>
          </div>
        ) : (
          <div className="muted" style={{ fontSize: 11, fontStyle: 'italic' }}>Unequipped</div>
        )}

        {!isNamed && (
          <div className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
            <button
              onClick={onLock}
              className="secondary"
              style={{ fontSize: 11, opacity: 0.8 }}
              title={gear.locked ? 'Unlock this gear' : 'Lock to protect from salvage'}
            >
              {gear.locked ? '🔓 Unlock' : '🔒 Lock'}
            </button>
            <button
              onClick={onSalvage}
              className="secondary"
              disabled={gear.locked}
              style={{ fontSize: 11, color: gear.locked ? 'var(--muted)' : 'var(--bad)', opacity: gear.locked ? 0.4 : 1 }}
              title={gear.locked ? 'Unlock first to salvage' : `Salvage for: ${SALVAGE_PREVIEW[gear.rarity]}`}
            >
              ⚒️ Salvage
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
