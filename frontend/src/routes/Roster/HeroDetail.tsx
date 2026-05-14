import { useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useHero } from '../../hooks/useHeroes'
import {
  ascendHeroWithShards, fetchTemplateShards, skillUpHero,
  SHARDS_TO_ASCEND_FROM, SHARDS_TO_SKILL_UP,
} from '../../api/heroes'
import {
  fetchGear, equipGear, unequipGear,
  ALL_SLOTS, SLOT_META, RARITY_COLOR,
  type GearOut, type GearSlot,
} from '../../api/gear'
import { toast } from '../../store/ui'
import { RarityPill } from '../../components/RarityPill'
import { SkeletonGrid } from '../../components/SkeletonGrid'

export function HeroDetailRoute() {
  const { heroId } = useParams<{ heroId: string }>()
  const heroIdNum = Number(heroId)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: hero, isLoading } = useHero(heroIdNum)
  const { data: allGear } = useQuery({ queryKey: ['gear'], queryFn: fetchGear })
  const [loading, setLoading] = useState<'skill' | 'shards' | null>(null)
  const [pickerSlot, setPickerSlot] = useState<GearSlot | null>(null)
  const { data: shards } = useQuery({ queryKey: ['template-shards'], queryFn: fetchTemplateShards })

  const equippedBySlot = useMemo(() => {
    const map = new Map<GearSlot, GearOut>()
    for (const g of allGear ?? []) {
      if (g.equipped_on === heroIdNum) map.set(g.slot, g)
    }
    return map
  }, [allGear, heroIdNum])

  const availableForSlot = useMemo(() => {
    if (!pickerSlot) return []
    return (allGear ?? []).filter((g) => g.slot === pickerSlot && g.equipped_on !== heroIdNum)
  }, [allGear, pickerSlot, heroIdNum])

  if (isLoading) return <SkeletonGrid count={3} height={100} />
  if (!hero) return <div className="muted">Hero not found.</div>

  const t = hero.template

  async function doAscendWithShards() {
    setLoading('shards')
    try {
      await ascendHeroWithShards(hero!.id)
      toast.success(`${t.name} ascended via shards!`)
      qc.invalidateQueries({ queryKey: ['heroes'] })
      qc.invalidateQueries({ queryKey: ['template-shards'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(null) }
  }

  async function doSkillUp() {
    setLoading('skill')
    try {
      await skillUpHero(hero!.id)
      toast.success(`${t.name} skill upgraded!`)
      qc.invalidateQueries({ queryKey: ['heroes'] })
      qc.invalidateQueries({ queryKey: ['template-shards'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(null) }
  }

  async function unequip(g: GearOut) {
    try {
      await unequipGear(g.id)
      qc.invalidateQueries({ queryKey: ['gear'] })
      qc.invalidateQueries({ queryKey: ['heroes'] })
      toast.success('Unequipped')
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  async function equip(g: GearOut) {
    try {
      await equipGear(g.id, heroIdNum)
      qc.invalidateQueries({ queryKey: ['gear'] })
      qc.invalidateQueries({ queryKey: ['heroes'] })
      toast.success(`Equipped ${g.name ?? SLOT_META[g.slot].label}`)
      setPickerSlot(null)
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  return (
    <div className="stack" style={{ maxWidth: 640, margin: '0 auto' }}>
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
          {[['❤️ HP', hero.hp], ['⚔️ ATK', hero.atk], ['🛡️ DEF', hero.def], ['💨 SPD', hero.spd], ['⚡ Power', hero.power]].map(([label, val]) => (
            <div key={String(label)}>
              <div className="muted" style={{ fontSize: 11 }}>{label}</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{val}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
          <h3 style={{ margin: 0, fontSize: 13 }}>Equipment</h3>
          <button onClick={() => navigate('/app/inventory')} style={{ fontSize: 11 }}>
            Inventory →
          </button>
        </div>

        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8,
        }}>
          {ALL_SLOTS.map((slot) => {
            const g = equippedBySlot.get(slot)
            const meta = SLOT_META[slot]
            const rarityColor = g ? RARITY_COLOR[g.rarity] : 'var(--border)'
            const isNamed = !!g?.name
            return (
              <button
                key={slot}
                onClick={() => g ? unequip(g) : setPickerSlot(slot)}
                title={g ? `${g.name ?? meta.label} — click to unequip` : `Empty ${meta.label} slot`}
                style={{
                  padding: 10,
                  background: g
                    ? `linear-gradient(180deg, color-mix(in srgb, ${rarityColor} 14%, var(--bg-inset)) 0%, var(--bg-inset) 80%)`
                    : 'var(--bg-inset)',
                  border: `1px solid ${rarityColor}`,
                  borderRadius: 'var(--radius)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  position: 'relative',
                }}
              >
                {isNamed && (
                  <span style={{
                    position: 'absolute', top: 4, right: 4,
                    fontSize: 9, fontWeight: 800, padding: '1px 5px',
                    borderRadius: 999, background: rarityColor, color: '#0b0d10',
                  }}>✨</span>
                )}
                <div style={{ fontSize: 18 }}>{meta.icon}</div>
                <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>{meta.label}</div>
                <div style={{
                  fontSize: 11, fontWeight: 600,
                  color: g ? rarityColor : 'var(--muted)',
                  marginTop: 2,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {g ? (g.name ?? g.rarity) : '— empty —'}
                </div>
              </button>
            )
          })}
        </div>
        <div className="muted" style={{ fontSize: 10, marginTop: 8, textAlign: 'center' }}>
          Click an empty slot to equip · click a filled slot to unequip
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 13 }}>Upgrades</h3>
        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          {hero.stars < 6 && (() => {
            const cost = SHARDS_TO_ASCEND_FROM[hero.stars] ?? 0
            const have = shards?.[t.code] ?? 0
            const ok = have >= cost
            return (
              <button
                onClick={doAscendWithShards}
                disabled={!!loading || !ok}
                className="primary"
                style={{ background: ok ? undefined : 'var(--bg-inset)', color: ok ? undefined : 'var(--muted)' }}
                title={`Spend ${cost} ${t.name} shards (you have ${have})`}
              >
                {loading === 'shards' ? '…' : `🌟 Ascend (${have}/${cost} shards)`}
              </button>
            )
          })()}
          {(() => {
            const skillCost = SHARDS_TO_SKILL_UP[hero.special_level]
            if (skillCost == null) {
              return (
                <button disabled className="secondary" title="Skill at max level">
                  🔮 Skill Maxed
                </button>
              )
            }
            const have = shards?.[t.code] ?? 0
            const ok = have >= skillCost
            return (
              <button
                onClick={doSkillUp}
                disabled={!!loading || !ok}
                className="secondary"
                style={{ background: ok ? undefined : 'var(--bg-inset)', color: ok ? undefined : 'var(--muted)' }}
                title={`Spend ${skillCost} ${t.name} shards (you have ${have})`}
              >
                {loading === 'skill' ? '…' : `🔮 Skill Up (${have}/${skillCost} shards)`}
              </button>
            )
          })()}
        </div>
        {hero.stars < 6 && (
          <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
            Tip: every duplicate pull of {t.name} grants template shards. Spend them
            here instead of feeding a whole hero. Max ascension is 6★.
          </div>
        )}
      </div>

      {pickerSlot && (
        <div
          role="dialog"
          aria-modal="true"
          onClick={(e) => { if (e.target === e.currentTarget) setPickerSlot(null) }}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 16, zIndex: 1000,
          }}
        >
          <div className="card" style={{ maxWidth: 480, width: '100%', maxHeight: '80vh', overflowY: 'auto' }}>
            <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 14 }}>
                {SLOT_META[pickerSlot].icon} Equip {SLOT_META[pickerSlot].label}
              </h3>
              <button onClick={() => setPickerSlot(null)} style={{ fontSize: 11 }}>Cancel</button>
            </div>
            {availableForSlot.length === 0 ? (
              <div className="muted" style={{ textAlign: 'center', padding: 20, fontSize: 13 }}>
                No {SLOT_META[pickerSlot].label.toLowerCase()} pieces available.
              </div>
            ) : (
              <div className="stack" style={{ gap: 6 }}>
                {[...availableForSlot]
                  .sort((a, b) => {
                    if (!!a.name !== !!b.name) return a.name ? -1 : 1
                    return ['LEGENDARY', 'EPIC', 'RARE', 'COMMON'].indexOf(a.rarity)
                         - ['LEGENDARY', 'EPIC', 'RARE', 'COMMON'].indexOf(b.rarity)
                  })
                  .map((g) => (
                    <button
                      key={g.id}
                      onClick={() => equip(g)}
                      style={{
                        padding: 10, textAlign: 'left',
                        background: g.name
                          ? `linear-gradient(180deg, color-mix(in srgb, ${RARITY_COLOR[g.rarity]} 14%, var(--panel)) 0%, var(--panel) 80%)`
                          : 'var(--panel)',
                        border: `1px solid ${RARITY_COLOR[g.rarity]}`,
                      }}
                    >
                      <div style={{ fontWeight: 700, color: g.name ? RARITY_COLOR[g.rarity] : 'var(--text)' }}>
                        {g.name ? `✨ ${g.name}` : `${g.rarity} ${SLOT_META[g.slot].label}`}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                        {Object.entries(g.stats).map(([k, v]) => `${k.toUpperCase()} +${v}`).join(' · ')}
                      </div>
                      {g.equipped_on && (
                        <div style={{ fontSize: 10, color: 'var(--warn)', marginTop: 2 }}>
                          Currently on another hero — moving here will unequip.
                        </div>
                      )}
                    </button>
                  ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
