import { useAuthStore } from '../store/auth'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

// When the SPA is served from file:// (Capacitor mobile prod build) relative
// URLs have no host. Builds for that target must set VITE_API_BASE_URL to the
// absolute API root, e.g. "https://hero-proto.fly.dev". Web/dev builds leave
// it unset so relative paths hit the same origin.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

function resolveUrl(path: string): string {
  if (!API_BASE) return path
  if (/^https?:\/\//i.test(path)) return path
  return API_BASE + (path.startsWith('/') ? path : '/' + path)
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

  const res = await fetch(resolveUrl(url), { ...options, headers })

  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = await res.json()
      const raw = body.detail ?? body.message
      if (Array.isArray(raw)) {
        message = raw.map((e: { msg?: string }) => e.msg ?? JSON.stringify(e)).join('; ')
      } else if (raw != null && typeof raw === 'object' && 'detail' in raw) {
        // Structured error e.g. power-floor rejection: { detail, required, current }
        const structured = raw as { detail: string; required?: number; current?: number }
        if (structured.required != null && structured.current != null) {
          message = `${structured.detail} (need ${structured.required.toLocaleString()}, have ${structured.current.toLocaleString()})`
        } else {
          message = String(structured.detail)
        }
      } else if (raw != null) {
        message = String(raw)
      }
    } catch {}
    if (res.status === 401) {
      useAuthStore.getState().clearJwt()
      // Let the caller throw; the component's error boundary or query will
      // surface the error while auth state is already wiped.
    }
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
