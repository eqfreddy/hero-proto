import type { Me } from '../types'
import { apiFetch } from './client'

export const fetchMe = (): Promise<Me> => apiFetch<Me>('/me')
