import { apiFetch, apiPost } from './client'

export interface Friend { id: number; name: string; arena_rating: number; status: string }
export interface DmThread { account_id: number; name: string; last_message: string; unread: number; last_at: string }
export interface DmMessage { id: number; sender_id: number; body: string; created_at: string; deleted: boolean }

export const fetchFriends = (): Promise<Friend[]> => apiFetch('/friends')
export const searchUsers = (q: string): Promise<Friend[]> => apiFetch(`/friends/search?q=${encodeURIComponent(q)}`)
export const sendFriendRequest = (id: number) => apiPost(`/friends/${id}/request`, {})
export const fetchDmThreads = (): Promise<DmThread[]> => apiFetch('/dm/threads')
export const fetchDms = (id: number): Promise<DmMessage[]> => apiFetch(`/dm/with/${id}`)
export const sendDm = (id: number, body: string) => apiPost(`/dm/${id}`, { body })
