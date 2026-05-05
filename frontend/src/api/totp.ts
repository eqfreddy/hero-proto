import { apiFetch } from './client'

export interface TotpEnrollOut {
  otpauth_uri: string
  secret: string
}

export interface TotpConfirmOut {
  recovery_codes: string[]
}

export interface TotpRegenerateOut {
  recovery_codes: string[]
}

export const enrollTotp = () =>
  apiFetch<TotpEnrollOut>('/auth/2fa/enroll', { method: 'POST', body: '{}' })

export const confirmTotp = (code: string) =>
  apiFetch<TotpConfirmOut>('/auth/2fa/confirm', {
    method: 'POST',
    body: JSON.stringify({ code }),
  })

export const disableTotp = (code: string) =>
  apiFetch<{ totp_enabled: boolean }>('/auth/2fa/disable', {
    method: 'POST',
    body: JSON.stringify({ code }),
  })

export const regenerateCodes = (code: string) =>
  apiFetch<TotpRegenerateOut>('/auth/2fa/regenerate-codes', {
    method: 'POST',
    body: JSON.stringify({ code }),
  })
