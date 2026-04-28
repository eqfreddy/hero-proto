import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchShop, buyProduct, exchangeShards } from '../api/shop'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { useState } from 'react'

export function ShopRoute() {
  const qc = useQueryClient()
  const { data: shop, isLoading } = useQuery({
    queryKey: ['shop'], queryFn: fetchShop, staleTime: 2 * 60_000,
  })
  const [buying, setBuying] = useState<string | null>(null)
  const [exchanging, setExchanging] = useState(false)

  if (isLoading) return <SkeletonGrid count={6} height={100} />
  if (!shop) return <div className="muted">Shop unavailable.</div>

  async function buy(sku: string) {
    setBuying(sku)
    try {
      const res = await buyProduct(sku)
      const parts = Object.entries(res.granted ?? {}).filter(([, v]) => Number(v) > 0).map(([k, v]) => `+${v} ${k}`)
      toast.success(parts.length ? `Purchased! ${parts.join(', ')}` : 'Purchased!')
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['shop'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Purchase failed')
    } finally {
      setBuying(null)
    }
  }

  async function doExchange() {
    setExchanging(true)
    try {
      const res = await exchangeShards()
      toast.success(`+${res.shards_granted} shards!`)
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['shop'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Exchange failed')
    } finally {
      setExchanging(false)
    }
  }

  const sx = shop.shard_exchange

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Shop</h2>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Gem → Shard Exchange</h3>
        <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
          {sx.gems_per_batch} 💎 → {sx.shards_per_batch} ✦ shards · {sx.remaining_today}/{sx.max_per_day} trades left today
        </div>
        <button
          className="primary"
          onClick={doExchange}
          disabled={exchanging || sx.remaining_today <= 0}
        >
          {exchanging ? '…' : `Trade ${sx.gems_per_batch} 💎 for ${sx.shards_per_batch} ✦`}
        </button>
      </div>

      {shop.starter && (
        <div className="card" style={{ border: '1px solid var(--r-legendary)', background: 'rgba(255,216,107,0.05)' }}>
          <div style={{ fontSize: 11, color: 'var(--r-legendary)', textTransform: 'uppercase', fontWeight: 700, marginBottom: 6 }}>
            ⭐ Starter Bundle
          </div>
          <div style={{ fontWeight: 700 }}>{shop.starter.title}</div>
          <div className="muted" style={{ fontSize: 12, margin: '4px 0 10px' }}>{shop.starter.description}</div>
          <button className="primary" onClick={() => buy(shop.starter!.sku)} disabled={!!buying}>
            {buying === shop.starter.sku ? '…' : `$${(shop.starter.price_cents / 100).toFixed(2)}`}
          </button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
        {shop.products.map((p) => (
          <div key={p.sku} className="card">
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{p.title}</div>
            <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>{p.description}</div>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span style={{ fontSize: 12, color: 'var(--warn)' }}>
                {p.price_cents === 0 ? 'Free' : `$${(p.price_cents / 100).toFixed(2)}`}
              </span>
              <button
                className="primary"
                style={{ fontSize: 12 }}
                onClick={() => buy(p.sku)}
                disabled={!!buying}
              >
                {buying === p.sku ? '…' : 'Buy'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {shop.history.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Recent Purchases</h3>
          <div className="stack" style={{ gap: 6 }}>
            {shop.history.map((h) => (
              <div key={h.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span>{h.title}</span>
                <span className="muted">{h.granted_short}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
