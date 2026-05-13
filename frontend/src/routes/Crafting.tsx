import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchCrafting, craftRecipe, type Recipe } from '../api/crafting'
import { SLOT_META, RARITY_COLOR } from '../api/gear'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'

const MATERIAL_RARITY_COLOR: Record<string, string> = {
  COMMON: 'var(--r-common)',
  UNCOMMON: 'var(--r-uncommon, #6fa)',
  RARE: 'var(--r-rare)',
  EPIC: 'var(--r-epic)',
  LEGENDARY: 'var(--r-legendary)',
}

export function CraftingRoute() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['crafting'], queryFn: fetchCrafting })

  if (isLoading) return <SkeletonGrid />
  if (!data) return null

  const gearRecipes = data.recipes.filter((r) => r.gear_output != null)
  const currencyRecipes = data.recipes.filter((r) => r.gear_output == null)

  const handleCraft = async (r: Recipe) => {
    try {
      await craftRecipe(r.code)
      toast.success(`${r.name} crafted!`)
      qc.invalidateQueries({ queryKey: ['crafting'] })
      qc.invalidateQueries({ queryKey: ['me'] })
      if (r.gear_output) qc.invalidateQueries({ queryKey: ['gear'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>⚒️ Crafting</h2>

      {/* Materials — when empty, collapse to a one-line subtitle instead of a
          full-width card. Saves vertical space on a screen that's already sparse. */}
      {(() => {
        const owned = data.materials.filter((m) => m.quantity > 0)
        if (owned.length === 0) {
          return (
            <div className="muted" style={{ fontSize: 12, marginTop: -4 }}>
              🧪 No materials yet — win battles and raids to start collecting.
            </div>
          )
        }
        return (
          <div className="card">
            <h3 style={{ marginTop: 0, marginBottom: 10 }}>🧪 Materials</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {owned.map((m) => (
                <div
                  key={m.code}
                  title={m.description}
                  style={{
                    padding: '4px 10px', borderRadius: 6, fontSize: 12,
                    background: 'var(--bg-inset)',
                    border: `1px solid ${MATERIAL_RARITY_COLOR[m.rarity] ?? 'var(--border)'}`,
                    color: MATERIAL_RARITY_COLOR[m.rarity] ?? 'var(--text)',
                  }}
                >
                  {m.icon} {m.name} ×{m.quantity}
                </div>
              ))}
            </div>
          </div>
        )
      })()}

      {/* Gear recipes */}
      {gearRecipes.length > 0 && (
        <>
          <h3 style={{ margin: '4px 0 0' }}>⚙️ Gear Crafting</h3>
          <div className="stack" style={{ gap: 8 }}>
            {gearRecipes.map((r) => <RecipeCard key={r.code} recipe={r} onCraft={() => handleCraft(r)} />)}
          </div>
        </>
      )}

      {/* Currency / resource recipes */}
      <h3 style={{ margin: '4px 0 0' }}>💱 Resource Exchange</h3>
      <div className="stack" style={{ gap: 8 }}>
        {currencyRecipes.map((r) => <RecipeCard key={r.code} recipe={r} onCraft={() => handleCraft(r)} />)}
      </div>
    </div>
  )
}

function RecipeCard({ recipe: r, onCraft }: { recipe: Recipe; onCraft: () => void }) {
  return (
    <div className="card" style={{ padding: '12px 14px', opacity: r.craftable ? 1 : 0.6 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 13 }}>{r.icon} {r.name}</div>
          <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{r.description}</div>

          {/* Gear output badge */}
          {r.gear_output && (
            <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <span style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 999,
                background: 'var(--bg-inset)',
                color: r.gear_output.rarity ? RARITY_COLOR[r.gear_output.rarity as keyof typeof RARITY_COLOR] ?? 'var(--text)' : 'var(--text)',
                border: `1px solid ${r.gear_output.rarity ? RARITY_COLOR[r.gear_output.rarity as keyof typeof RARITY_COLOR] ?? 'var(--border)' : 'var(--border)'}`,
                fontWeight: 700,
              }}>
                {r.gear_output.slot
                  ? `${SLOT_META[r.gear_output.slot as keyof typeof SLOT_META]?.icon ?? '📦'} ${r.gear_output.rarity ?? 'random rarity'} ${SLOT_META[r.gear_output.slot as keyof typeof SLOT_META]?.label ?? r.gear_output.slot}`
                  : `📦 ${r.gear_output.rarity ?? 'EPIC'} gear (random slot)`}
              </span>
            </div>
          )}

          {/* Cost summary */}
          <div style={{ marginTop: 6, display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 11, color: 'var(--muted)' }}>
            {Object.entries(r.materials).map(([code, qty]) => (
              <span key={code}>{qty}× {code.replace(/_/g, ' ')}</span>
            ))}
            {r.coin_cost > 0 && <span>{r.coin_cost.toLocaleString()} coins</span>}
            {r.gem_cost > 0 && <span>{r.gem_cost} 💎</span>}
          </div>

          {!r.craftable && r.blocking_reason && (
            <div style={{ fontSize: 11, color: 'var(--bad)', marginTop: 4 }}>{r.blocking_reason}</div>
          )}
        </div>

        <button
          className="primary"
          style={{ fontSize: 12, flexShrink: 0 }}
          disabled={!r.craftable}
          onClick={onCraft}
        >
          Craft
        </button>
      </div>
    </div>
  )
}
