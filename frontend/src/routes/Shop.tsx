import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchShop, buyProduct, exchangeShards } from '../api/shop'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { isNative } from '../native'

const NATIVE = isNative()

type ShopTab = 'coins' | 'gems' | 'qol'

const TAB_META: { id: ShopTab; icon: string; label: string; kinds: string[] }[] = [
  { id: 'coins', icon: '🪙', label: 'Coin Shop',  kinds: ['COIN_PACK'] },
  { id: 'gems',  icon: '💎', label: 'Gem Shop',   kinds: ['GEM_PACK', 'STARTER_BUNDLE', 'SHARD_PACK', 'ACCESS_CARD_PACK'] },
  { id: 'qol',   icon: '⚙️', label: 'QoL Shop',   kinds: ['WEEKLY_BUNDLE', 'SEASONAL_BUNDLE'] },
]

const GEM_TAB_KINDS = new Set(['GEM_PACK', 'COIN_PACK', 'STARTER_BUNDLE', 'SHARD_PACK', 'ACCESS_CARD_PACK'])

export function ShopRoute() {
  const qc = useQueryClient()
  const { data: shop, isLoading } = useQuery({
    queryKey: ['shop'],
    queryFn: fetchShop,
    staleTime: 2 * 60_000,
  })
  const [tab, setTab] = useState<ShopTab>('coins')
  const [buying, setBuying] = useState<string | null>(null)
  const [exchanging, setExchanging] = useState(false)

  if (isLoading) return <SkeletonGrid count={8} height={100} />
  if (!shop) return <div className="muted">Shop unavailable.</div>

  async function buy(sku: string) {
    setBuying(sku)
    try {
      const res = await buyProduct(sku)
      const parts = Object.entries(res.granted ?? {})
        .filter(([, v]) => Number(v) > 0)
        .map(([k, v]) => `+${v} ${k}`)
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
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Exchange failed')
    } finally {
      setExchanging(false)
    }
  }

  const meta = TAB_META.find((t) => t.id === tab)!
  const rawProducts =
    tab === 'qol'
      ? shop.products.filter((p) => !GEM_TAB_KINDS.has(p.kind))
      : shop.products.filter((p) => meta.kinds.includes(p.kind))
  // On native, drop real-money products — IAP is web-only until Play Billing ships.
  const products = NATIVE ? rawProducts.filter((p) => p.price_cents === 0) : rawProducts

  const sx = shop.shard_exchange

  return (
    <div className="stack">
      {/* Tab selector */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {TAB_META.map(({ id, icon, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            style={{
              padding: '16px 12px',
              borderRadius: 8,
              cursor: 'pointer',
              border: `1px solid ${tab === id ? 'rgba(0,255,224,0.4)' : 'var(--border)'}`,
              background: tab === id ? 'rgba(0,255,224,0.06)' : 'var(--panel)',
              color: tab === id ? 'var(--accent)' : 'var(--muted)',
              textAlign: 'center',
              transition: 'all 0.15s',
              boxShadow: tab === id ? '0 0 20px rgba(0,255,224,0.08)' : 'none',
            }}
          >
            <div style={{ fontSize: 28, marginBottom: 6 }}>{icon}</div>
            <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              {label}
            </div>
          </button>
        ))}
      </div>

      {/* Gem tab: shard exchange */}
      {tab === 'gems' && (
        <div className="card" style={{ borderColor: 'rgba(155,48,255,0.3)' }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>💎→✦ Shard Exchange</div>
          <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
            {sx.gems_per_batch}💎 → {sx.shards_per_batch}✦ · {sx.remaining_today}/{sx.max_per_day} trades left today
          </div>
          <button
            className="primary"
            onClick={doExchange}
            disabled={exchanging || sx.remaining_today <= 0}
          >
            {exchanging ? '…' : `Trade ${sx.gems_per_batch}💎 for ${sx.shards_per_batch}✦`}
          </button>
        </div>
      )}

      {/* Products grid */}
      {products.length === 0 && (
        <div className="card muted" style={{ textAlign: 'center', padding: 32 }}>
          Nothing in this shop yet — check back soon.
        </div>
      )}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: 12,
        }}
      >
        {products.map((p) => (
          <div
            key={p.sku}
            className="card"
            style={{
              borderColor:
                p.kind === 'COIN_PACK' ? 'rgba(255,215,0,0.2)' : 'var(--border)',
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{p.title}</div>
            <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
              {p.description}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span
                style={{
                  fontSize: 12,
                  color: p.price_cents === 0 ? 'var(--good)' : 'var(--warn)',
                  fontWeight: 700,
                }}
              >
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

      {/* Gem tab: starter bundle (web only — real money) */}
      {tab === 'gems' && shop.starter && !NATIVE && (
        <div
          className="card"
          style={{ border: '1px solid var(--r-legendary)', background: 'rgba(255,215,0,0.04)' }}
        >
          <div
            style={{
              fontSize: 11,
              color: 'var(--r-legendary)',
              textTransform: 'uppercase',
              fontWeight: 700,
              marginBottom: 6,
            }}
          >
            ⭐ Starter Bundle
          </div>
          <div style={{ fontWeight: 700 }}>{shop.starter.title}</div>
          <div className="muted" style={{ fontSize: 12, margin: '4px 0 10px' }}>
            {shop.starter.description}
          </div>
          <button
            className="primary"
            onClick={() => buy(shop.starter!.sku)}
            disabled={!!buying}
          >
            {buying === shop.starter.sku ? '…' : `$${(shop.starter.price_cents / 100).toFixed(2)}`}
          </button>
        </div>
      )}

      {/* Purchase history */}
      {shop.history.length > 0 && (
        <div className="card">
          <div style={{ fontWeight: 700, marginBottom: 10 }}>Recent Purchases</div>
          <div className="stack" style={{ gap: 6 }}>
            {shop.history.map((h) => (
              <div
                key={h.id}
                style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}
              >
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
