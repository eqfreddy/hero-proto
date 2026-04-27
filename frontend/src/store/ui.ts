import { create } from 'zustand'

export type ToastKind = 'success' | 'error' | 'info'

export interface Toast {
  id: string
  message: string
  kind: ToastKind
}

interface UiState {
  toasts: Toast[]
  addToast: (message: string, kind: ToastKind) => void
  dismissToast: (id: string) => void
}

export const useUiStore = create<UiState>((set) => ({
  toasts: [],
  addToast: (message, kind) => {
    const id = Math.random().toString(36).slice(2)
    set((s) => ({ toasts: [...s.toasts, { id, message, kind }] }))
    const ttl = kind === 'error' ? 5000 : 3500
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), ttl)
  },
  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

// Convenience helpers matching the old toast.js API
export const toast = {
  success: (msg: string) => useUiStore.getState().addToast(msg, 'success'),
  error: (msg: string) => useUiStore.getState().addToast(msg, 'error'),
  info: (msg: string) => useUiStore.getState().addToast(msg, 'info'),
}
