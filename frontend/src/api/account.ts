import { apiFetch, apiPost } from './client'
export interface Session {
  id: number
  issued_at: string
  expires_at: string
  last_used_at: string | null
  ip: string | null
  user_agent: string | null
  is_current: boolean
}
export const fetchSessions = (): Promise<Session[]> => apiFetch('/me/sessions')
export const revokeSession = (id: number) => apiPost(`/me/sessions/${id}/revoke`, {})
export const revokeAllSessions = () => apiPost('/me/sessions/revoke-all', {})
export const requestDataExport = () => apiFetch<{ download_url: string }>('/me/export')
export const deleteAccount = (confirmEmail: string) =>
  apiFetch('/me', { method: 'DELETE', body: JSON.stringify({ confirm_email: confirmEmail }) })
