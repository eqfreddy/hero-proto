import { apiFetch, apiPost } from './client'
export interface Session { id: number; created_at: string; last_used: string; ip_address: string; is_current: boolean }
export const fetchSessions = (): Promise<Session[]> => apiFetch('/me/sessions')
export const revokeSession = (id: number) => apiPost(`/me/sessions/${id}/revoke`, {})
export const revokeAllSessions = () => apiPost('/me/sessions/revoke-all', {})
export const requestDataExport = () => apiFetch<{ download_url: string }>('/me/export')
export const deleteAccount = () => apiPost('/me/delete', {})
