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

export const fetchShop = (): Promise<ShopData> => apiFetch<ShopData>('/shop')
export const buyProduct = (sku: string, stripe_token?: string): Promise<{ granted: Record<string, unknown> }> =>
  apiPost('/shop/buy', { sku, ...(stripe_token ? { stripe_token } : {}) })
export const exchangeShards = (): Promise<{ shards_granted: number }> =>
  apiPost('/shop/shard-exchange', {})
