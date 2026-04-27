import { create } from 'zustand'
import { persist, StateStorage } from 'zustand/middleware'

interface AuthState {
  jwt: string | null
  setJwt: (token: string) => void
  clearJwt: () => void
}

// Custom storage that stores only the JWT value (not the full state object)
const jwtStorage: StateStorage = {
  getItem: (name) => {
    const token = localStorage.getItem(name)
    if (!token) return null
    // Return Zustand's expected persist format with the token in the state
    return JSON.stringify({ state: { jwt: token }, version: 0 })
  },
  setItem: (name, value) => {
    let jwtValue: string | null = null

    if (typeof value === 'string') {
      try {
        const parsed = JSON.parse(value)
        jwtValue = parsed.state?.jwt
      } catch (e) {
        // Fall through
      }
    } else if (typeof value === 'object' && value !== null) {
      // value is already the state object
      jwtValue = (value as any).state?.jwt
    }

    if (jwtValue === null) {
      localStorage.removeItem(name)
    } else if (jwtValue) {
      localStorage.setItem(name, jwtValue)
    }
  },
  removeItem: (name) => {
    localStorage.removeItem(name)
  },
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      jwt: null,
      setJwt: (token) => set({ jwt: token }),
      clearJwt: () => set({ jwt: null }),
    }),
    {
      name: 'heroproto_jwt',
      storage: jwtStorage,
    }
  )
)
