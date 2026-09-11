import { afterEach, describe, expect, it, vi } from 'vitest'

/**
 * Unit tests for the runtime config module: the URL normalization rules that
 * every API/Supebase client depends on (trailing-slash stripping, PostgREST
 * suffix removal) and the auth gate that decides whether Supabase is wired up.
 */

const BASE_ENV = {
  VITE_API_URL: 'http://localhost:8000',
  VITE_SUPABASE_URL: undefined,
  VITE_SUPABASE_ANON_KEY: undefined,
}

async function loadConfigWith(env: Record<string, string | undefined>) {
  vi.resetModules()
  vi.stubEnv('VITE_API_URL', env.VITE_API_URL ?? '')
  vi.stubEnv('VITE_SUPABASE_URL', env.VITE_SUPABASE_URL ?? '')
  vi.stubEnv('VITE_SUPABASE_ANON_KEY', env.VITE_SUPABASE_ANON_KEY ?? '')
  const { config } = await import('./config')
  vi.unstubAllEnvs()
  return config
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('config.apiUrl normalization', () => {
  it('passes through a clean URL unchanged', async () => {
    const config = await loadConfigWith({ ...BASE_ENV, VITE_API_URL: 'http://localhost:8000' })
    expect(config.apiUrl).toBe('http://localhost:8000')
  })

  it('strips one trailing slash from the API URL', async () => {
    const config = await loadConfigWith({ ...BASE_ENV, VITE_API_URL: 'http://localhost:8000/' })
    expect(config.apiUrl).toBe('http://localhost:8000')
  })

  it('drops the Supabase PostgREST suffix but keeps the project origin', async () => {
    const config = await loadConfigWith({
      ...BASE_ENV,
      VITE_SUPABASE_URL: 'https://demo.supabase.co/rest/v1/',
      VITE_SUPABASE_ANON_KEY: 'anon-key',
    })
    expect(config.supabaseUrl).toBe('https://demo.supabase.co')
  })
})

describe('config.hasSupabaseAuth gate', () => {
  it('is false without both Supabase URL and anon key', async () => {
    const config = await loadConfigWith(BASE_ENV)
    expect(config.hasSupabaseAuth).toBe(false)
  })

  it('is false when only the URL is set', async () => {
    const config = await loadConfigWith({ ...BASE_ENV, VITE_SUPABASE_URL: 'https://demo.supabase.co' })
    expect(config.hasSupabaseAuth).toBe(false)
  })

  it('is true when URL and anon key are both present', async () => {
    const config = await loadConfigWith({
      ...BASE_ENV,
      VITE_SUPABASE_URL: 'https://demo.supabase.co',
      VITE_SUPABASE_ANON_KEY: 'anon-key',
    })
    expect(config.hasSupabaseAuth).toBe(true)
  })
})
