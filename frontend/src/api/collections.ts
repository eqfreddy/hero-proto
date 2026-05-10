import { apiFetch, apiPost } from './client'
import type { Collection, CollectionDrop } from '../types'

export const fetchCollections = (): Promise<Collection[]> =>
  apiFetch<Collection[]>('/collections')

export const claimCollection = (code: string): Promise<{ granted: Record<string, unknown> }> =>
  apiPost<{ granted: Record<string, unknown> }>(`/collections/${code}/claim`, {})

export const openEightTrack = (): Promise<{ pieces: CollectionDrop[] }> =>
  apiPost<{ pieces: CollectionDrop[] }>('/collections/8-track/open', {})
