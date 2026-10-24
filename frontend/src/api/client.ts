import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 120_000,
  headers: { Accept: 'application/json' },
})

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail || error.message || 'Le serveur ne répond pas.'
  }
  return error instanceof Error ? error.message : 'Une erreur inattendue est survenue.'
}
