import { afterEach, describe, expect, it, vi } from 'vitest'

import { loadMatch, ProfileMissingError } from './api'

/**
 * Unit tests for the shared match loader — the single code path every surface
 * (Results, Dashboard, Landing, Progress) uses to read match data. The
 * contract: GET the persisted match first, POST a recompute only on 404/405,
 * and surface ProfileMissingError when the user never completed the assessment.
 */

const headers = { Authorization: 'Bearer test-token' }

const MATCH_BODY = {
  normalized_interest_profile: {},
  normalized_work_style_profile: {},
  generation_mode: 'llm',
  recommendations: [
    {
      rank: 1,
      role_id: 'backend-developer',
      role_title: 'Backend Developer',
      pathfinder_fit_score: 81.2,
      score_breakdown: {
        interest_alignment: 80,
        skill_readiness: 85,
        work_style_alignment: 78,
      },
      confirmed_skills: ['python'],
      missing_core_skills: ['sql'],
      missing_supporting_skills: [],
      fit_explanation: 'Backend Developer is ranked #1.',
    },
  ],
}

const PROFILE_BODY = { goal_text: '', constraints: {} }

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

type RouteHandler = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

type FetchMock = ReturnType<typeof vi.fn<RouteHandler>>

/** Build a fetch stub that routes on `${METHOD} ${path}` (path after /api/v1). */
function routeFetch(routes: Record<string, () => Response | number>): FetchMock {
  return vi.fn<RouteHandler>(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    const method = (init?.method ?? 'GET').toUpperCase()
    const path = `${method} ${url.pathname.replace('/api/v1', '')}${url.search}`
    const handler = routes[path]
    if (!handler) {
      throw new Error(`unexpected fetch: ${path}`)
    }
    const response = handler()
    return typeof response === 'number' ? jsonResponse({}, response) : response
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('loadMatch — persisted fast path', () => {
  it('returns the persisted match on GET without ever recomputing', async () => {
    const fetchMock = routeFetch({ 'GET /match': () => jsonResponse(MATCH_BODY) })
    vi.stubGlobal('fetch', fetchMock)

    const result = await loadMatch(headers)

    expect(result).toEqual(MATCH_BODY)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/v1/match')
    expect(init?.headers).toEqual(headers)
  })
})

describe('loadMatch — recompute leg on 404/405', () => {
  it('POSTs a recompute when nothing is persisted and returns the fresh result', async () => {
    const fetchMock = routeFetch({
      'GET /match': () => jsonResponse({ detail: 'no persisted match' }, 404),
      'GET /profile': () => jsonResponse(PROFILE_BODY),
      'POST /match': () => jsonResponse(MATCH_BODY),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await loadMatch(headers)

    expect(result).toEqual(MATCH_BODY)
    const calls = fetchMock.mock.calls
    expect(calls).toHaveLength(3)
    const [postUrl, postInit] = calls[2]
    expect(String(postUrl)).toMatch(/\/api\/v1\/match$/)
    expect((postInit as RequestInit).method).toBe('POST')
  })

  it('keeps the personalized (no ?explain=false) recompute by default', async () => {
    const fetchMock = routeFetch({
      'GET /match': () => jsonResponse({}, 404),
      'GET /profile': () => jsonResponse(PROFILE_BODY),
      'POST /match': () => jsonResponse(MATCH_BODY),
    })
    vi.stubGlobal('fetch', fetchMock)

    await loadMatch(headers)

    const [postUrl] = fetchMock.mock.calls[2]
    expect(String(postUrl)).not.toContain('explain')
  })

  it('appends ?explain=false on the recompute when opts.explain is set', async () => {
    const fetchMock = routeFetch({
      'GET /match': () => jsonResponse({}, 404),
      'GET /profile': () => jsonResponse(PROFILE_BODY),
      'POST /match?explain=false': () => jsonResponse(MATCH_BODY),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await loadMatch(headers, 'Failed to load', { explain: true })

    expect(result).toEqual(MATCH_BODY)
    const [postUrl] = fetchMock.mock.calls[2]
    expect(String(postUrl)).toContain('/api/v1/match?explain=false')
  })

  it('treats 405 (backend predates GET /match) like 404 and recomputes', async () => {
    const fetchMock = routeFetch({
      'GET /match': () => jsonResponse({ detail: 'Method Not Allowed' }, 405),
      'GET /profile': () => jsonResponse(PROFILE_BODY),
      'POST /match': () => jsonResponse(MATCH_BODY),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await loadMatch(headers)

    expect(result).toEqual(MATCH_BODY)
  })

  it('throws ProfileMissingError when the profile itself is absent', async () => {
    const fetchMock = routeFetch({
      'GET /match': () => jsonResponse({}, 404),
      'GET /profile': () => jsonResponse({ detail: 'not found' }, 404),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(loadMatch(headers)).rejects.toBeInstanceOf(ProfileMissingError)
    // No POST was attempted for a user with no assessment on file.
    expect(fetchMock.mock.calls).toHaveLength(2)
  })
})

describe('loadMatch — failure surfaces', () => {
  it('throws the backend detail message when the recompute fails', async () => {
    const fetchMock = routeFetch({
      'GET /match': () => jsonResponse({}, 404),
      'GET /profile': () => jsonResponse(PROFILE_BODY),
      'POST /match': () => jsonResponse({ detail: 'matching failed' }, 500),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(loadMatch(headers)).rejects.toThrow('matching failed')
  })

  it('falls back to the caller-provided message when the error body is not JSON', async () => {
    const plainText = new Response('gateway exploded', { status: 502 })
    const fetchMock = vi.fn(async () => plainText)
    vi.stubGlobal('fetch', fetchMock)

    await expect(loadMatch(headers, 'Failed to load results')).rejects.toThrow(
      'Failed to load results (502)',
    )
  })
})
