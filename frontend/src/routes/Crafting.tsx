import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchCrafting, craftRecipe } from '../api/crafting'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'

export function CraftingRoute() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['crafting'], queryFn: fetchCrafting })

  if (isLoading) return <SkeletonGrid />
  if (!data) return null

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>⚒️ Crafting</h2>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Materials</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {data.materials.filter((m) => m.quantity > 0).map((m) => (
            <div key={m.code} style={{ padding: '4px 10px', background: 'var(--bg-inset)', borderRadius: 6, fontSize: 12 }}>
              {m.icon} {m.name} ×{m.quantity}
            </div>
          ))}
        </div>
      </div>
      <div className="stack" style={{ gap: 8 }}>
        {data.recipes.map((r) => (
          <div key={r.id} className="card" style={{ padding: '12px 14px', opacity: r.craftable ? 1 : 0.6 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>{r.name}</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{r.description}</div>
                {!r.craftable && r.blocking_reason && (
                  <div style={{ fontSize: 11, color: 'var(--bad)', marginTop: 2 }}>{r.blocking_reason}</div>
                )}
              </div>
              <button className="primary" style={{ fontSize: 12 }}
                disabled={!r.craftable}
                onClick={async () => {
                  try { await craftRecipe(r.id); toast.success(`${r.name} crafted!`); qc.invalidateQueries({ queryKey: ['crafting'] }); qc.invalidateQueries({ queryKey: ['me'] }) }
                  catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                }}>Craft</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
