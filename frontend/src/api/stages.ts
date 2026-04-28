import type { Stage } from '../types'
import { apiFetch } from './client'

export const fetchStages = (): Promise<Stage[]> => apiFetch<Stage[]>('/stages')
