import type { Guild } from '../types'
import { apiFetch, apiPost } from './client'

export interface GuildMessage { id: number; author_name: string; body: string; created_at: string }
export interface GuildApplication {
  id: number
  guild_id: number
  account_id: number
  applicant_name: string
  status: string
  message: string
  created_at: string
  reviewed_at: string | null
  reviewed_by: number | null
}
export interface GuildInvite {
  id: number
  guild_id: number
  guild_name: string
  guild_tag: string
  account_id: number
  invitee_name: string
  inviter_id: number | null
  inviter_name: string
  status: string
  message: string
  created_at: string
  decided_at: string | null
}

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
export const fetchMyApplications = (): Promise<GuildApplication[]> =>
  apiFetch('/guilds/applications/mine')
export const withdrawApplication = (appId: number) =>
  apiFetch(`/guilds/applications/${appId}`, { method: 'DELETE' })
export const fetchMyInvites = (): Promise<GuildInvite[]> =>
  apiFetch('/guilds/invites/mine')
export const acceptInvite = (inviteId: number) =>
  apiPost(`/guilds/invites/${inviteId}/accept`, {})
export const rejectInvite = (inviteId: number) =>
  apiPost(`/guilds/invites/${inviteId}/reject`, {})
export const fetchGuildApplications = (guildId: number): Promise<GuildApplication[]> =>
  apiFetch(`/guilds/${guildId}/applications`)
export const acceptApplication = (appId: number) =>
  apiPost(`/guilds/applications/${appId}/accept`, {})
export const rejectApplication = (appId: number) =>
  apiPost(`/guilds/applications/${appId}/reject`, {})
export const fetchOutgoingInvites = (guildId: number): Promise<GuildInvite[]> =>
  apiFetch(`/guilds/${guildId}/invites`)
export const cancelInvite = (inviteId: number) =>
  apiFetch(`/guilds/invites/${inviteId}`, { method: 'DELETE' })
export const invitePlayer = (guildId: number, accountId: number, message: string) =>
  apiPost(`/guilds/${guildId}/invite/${accountId}`, { message })
export const promoteMember = (guildId: number, accountId: number) =>
  apiPost(`/guilds/${guildId}/promote/${accountId}`, {})
export const demoteMember = (guildId: number, accountId: number) =>
  apiPost(`/guilds/${guildId}/demote/${accountId}`, {})
export const transferLeadership = (guildId: number, accountId: number) =>
  apiPost(`/guilds/${guildId}/transfer/${accountId}`, {})
export const kickMember = (guildId: number, accountId: number) =>
  apiPost(`/guilds/${guildId}/kick/${accountId}`, {})
