import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { PersistStorage, StorageValue } from 'zustand/middleware'

interface AuthState {
  jwt: string | null
  setJwt: (token: string) => void
  clearJwt: () => void
}

type PersistedAuth = Pick<AuthState, 'jwt'>

const jwtStorage: PersistStorage<PersistedAuth> = {
  getItem: (name): StorageValue<PersistedAuth> | null => {
    const val = localStorage.getItem(name)
    if (!val) return null
    return { state: { jwt: val }, version: 0 }
  },
  setItem: (name, value: StorageValue<PersistedAuth>): void => {
    const jwt = value.state.jwt
    if (jwt === null) {
      localStorage.removeItem(name)
    } else {
      localStorage.setItem(name, jwt)
    }
  },
  removeItem: (name): void => localStorage.removeItem(name),
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
      partialize: (state) => ({ jwt: state.jwt }),
    }
  )
)
