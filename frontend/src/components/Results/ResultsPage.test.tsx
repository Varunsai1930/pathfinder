import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ResultsPage } from './ResultsPage'
import type { MatchResponse } from '../../lib/api'

const noop = () => {}

const sixRoles = [
  'frontend-developer',
  'backend-developer',
  'data-analyst',
  'cloud-devops-engineer',
  'data-engineer',
  'security-analyst',
]

const roleTitle = (roleId: string) => roleId.replace(/-/g, ' ')

function buildMatch(): MatchResponse {
  return {
    normalized_interest_profile: {},
    normalized_work_style_profile: {},
    generation_mode: 'fallback',
    recommendations: sixRoles.map((role_id, index) => ({
      rank: index + 1,
      role_id,
      role_title: roleTitle(role_id),
      pathfinder_fit_score: 80 - index,
      score_breakdown: { interest_alignment: 80, skill_readiness: 70, work_style_alignment: 60 },
      confirmed_skills: ['Git and GitHub'],
      missing_core_skills: index === 0 ? [] : ['SQL and relational data'],
      missing_supporting_skills: [],
      fit_explanation: 'Deterministic template explanation.',
    })),
  }
}

describe('ResultsPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders one ranked card per role from the persisted match, with no network call', () => {
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)
    render(<ResultsPage matchData={buildMatch()} onBackToHome={noop} onExplorePath={noop} />)

    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Top match: frontend developer')
    for (const role of sixRoles) {
      expect(screen.getByRole('heading', { level: 2, name: roleTitle(role) })).toBeTruthy()
    }
    expect(screen.getAllByText('fit score')).toHaveLength(6)
    // Persisted data renders directly — the match loader must not fire.
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('routes the clicked role through onExplorePath', () => {
    const onExplorePath = vi.fn()
    render(<ResultsPage matchData={buildMatch()} onBackToHome={noop} onExplorePath={onExplorePath} />)

    const exploreButtons = screen.getAllByText('Explore path →')
    expect(exploreButtons).toHaveLength(6)
    fireEvent.click(exploreButtons[2]!)
    expect(onExplorePath).toHaveBeenCalledTimes(1)
    expect(onExplorePath.mock.calls[0]![0].role_id).toBe('data-analyst')
  })
})
