import type { ShopProduct } from '../types'
import { apiFetch, apiPost } from './client'

export interface PurchaseHistory {
  id: number; title: string; sku: string; state: string
  price_cents: number; created_at: string; granted_short: string
}
export interface ShardExchange {
  gems_per_batch: number; shards_per_batch: number
  max_per_day: number; used_today: number; remaining_today: number
}
export interface ShopData {
  products: ShopProduct[]; starter: ShopProduct | null
  history: PurchaseHistory[]; shard_exchange: ShardExchange
}

export const fetchShop = (): Promise<ShopData> =>
  Promise.all([
    apiFetch<ShopProduct[]>('/shop/products'),
    apiFetch<PurchaseHistory[]>('/shop/purchases/mine'),
    apiFetch<ShardExchange>('/shop/shard-exchange'),
  ]).then(([products, history, shard_exchange]) => ({
    products: products.filter(p => p.kind !== 'STARTER_BUNDLE'),
    starter: products.find(p => p.kind === 'STARTER_BUNDLE') ?? null,
    history,
    shard_exchange,
  }))
export const buyProduct = (sku: string, stripe_token?: string): Promise<{ granted: Record<string, unknown> }> =>
  apiPost('/shop/purchases', { sku, ...(stripe_token ? { stripe_token } : {}) })
export const exchangeShards = (): Promise<{ shards_granted: number }> =>
  apiPost('/shop/shard-exchange', {})
