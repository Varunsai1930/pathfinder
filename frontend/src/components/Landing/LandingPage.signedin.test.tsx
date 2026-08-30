import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: async () => ({
        data: { session: { access_token: 'test-token' } },
        error: null,
      }),
    },
  },
}))

import { LandingPage } from './LandingPage'

const noop = () => {}

const matchResponse = {
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
      fit_explanation: '',
    },
  ],
  generation_mode: 'llm',
}

describe('LandingPage (signed in with a persisted match)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('prefetches the top path on mount and renders the welcome-back card', async () => {
    const fetchMock = vi.fn<(url: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(
      async () =>
        new Response(JSON.stringify(matchResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(
      <LandingPage
        userEmail="user@example.com"
        onSignIn={noop}
        onStart={noop}
        onSignOut={noop}
        onAskQuestions={noop}
        onOpenDashboard={vi.fn()}
        onTrackProgress={vi.fn()}
        onViewResults={noop}
      />,
    )

    // Await the async chain (session -> GET /match) before asserting on it.
    expect(await screen.findByText('Track my progress →')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 2, name: 'Backend Developer' })).toBeTruthy()
    expect(screen.getByText('Continue my path — Backend Developer →')).toBeTruthy()
    expect(screen.getByText('Pick up your milestones right where you left them.')).toBeTruthy()

    // The persisted match was fetched with auth — exactly once: the settled
    // guard keeps the mount + auth-state triggers from double-fetching.
    const matchCalls = fetchMock.mock.calls.filter(([url]) => String(url).includes('/api/v1/match'))
    expect(matchCalls).toHaveLength(1)
    expect(matchCalls[0][0]).toContain('/api/v1/match')
    expect(matchCalls[0][1]).toEqual({ headers: { Authorization: 'Bearer test-token' } })
  })
})
