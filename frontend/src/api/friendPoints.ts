import { apiFetch, apiPost } from './client'
import type { SummonPullOutcome } from './summon'

export interface FriendPointsStatus {
  balance: number
  pings_sent_today: number
  pings_remaining_today: number
  pings_daily_cap: number
  fp_per_ping: number
  fp_per_summon: number
  fp_pulls_since_epic: number
  fp_pity_threshold: number
}

export interface FpPingResult {
  sent: boolean
  fp_granted: number
  fp_recipient_granted: number
  balance: number
}

export interface FpSummonResult extends SummonPullOutcome {}

export const fetchFriendPoints = (): Promise<FriendPointsStatus> =>
  apiFetch<FriendPointsStatus>('/friend-points')

export const pingFriend = (friendId: number) =>
  apiPost<FpPingResult>(`/friend-points/ping/${friendId}`, {})

export const summonFriendBanner = () =>
  apiPost<FpSummonResult>('/friend-points/summon', {})
