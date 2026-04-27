import type { Guild } from '../types'
import { apiFetch, apiPost } from './client'

export interface GuildMessage { id: number; author_name: string; body: string; created_at: string }
export interface GuildApplication { id: number; applicant_name: string; message: string }

export const fetchMyGuild = (): Promise<{ guild: Guild | null; my_role: string | null }> =>
  apiFetch('/guilds/mine')
export const fetchAllGuilds = (): Promise<Guild[]> => apiFetch('/guilds')
export const fetchGuildMessages = (id: number): Promise<GuildMessage[]> =>
  apiFetch(`/guilds/${id}/messages?limit=20`)
export const sendGuildMessage = (id: number, body: string) =>
  apiPost(`/guilds/${id}/messages`, { body })
export const applyToGuild = (id: number, message: string) =>
  apiPost(`/guilds/${id}/apply`, { message })
export const createGuild = (name: string, tag: string, description: string) =>
  apiPost('/guilds', { name, tag, description })
export const leaveGuild = (id: number) => apiPost(`/guilds/${id}/leave`, {})
export const acceptApplication = (appId: number) =>
  apiPost(`/guilds/applications/${appId}/accept`, {})
export const rejectApplication = (appId: number) =>
  apiPost(`/guilds/applications/${appId}/reject`, {})
