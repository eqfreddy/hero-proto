import { useAuthStore } from '../store/auth'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function apiFetch<T = unknown>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const jwt = useAuthStore.getState().jwt
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> ?? {}),
  }
  if (jwt) headers['Authorization'] = `Bearer ${jwt}`

  const res = await fetch(url, { ...options, headers })

  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = await res.json()
      message = body.detail ?? body.message ?? message
    } catch {}
    throw new ApiError(res.status, message)
  }

  return res.json() as Promise<T>
}

export async function apiPost<T = unknown>(url: string, body: unknown): Promise<T> {
  return apiFetch<T>(url, { method: 'POST', body: JSON.stringify(body) })
}

export async function apiDelete<T = unknown>(url: string): Promise<T> {
  return apiFetch<T>(url, { method: 'DELETE' })
}
