import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LandingPage } from './LandingPage'

const noop = () => {}

function renderLanding(userEmail: string | null = null) {
  return render(
    <LandingPage
      userEmail={userEmail}
      onSignIn={noop}
      onStart={noop}
      onSignOut={noop}
      onAskQuestions={noop}
      onOpenDashboard={vi.fn()}
      onTrackProgress={noop}
      onViewResults={noop}
    />,
  )
}

describe('LandingPage', () => {
  it('renders the hero headline and primary CTA for signed-out visitors', () => {
    renderLanding()
    expect(screen.getByText("The AI can persuade. It can't decide.")).toBeTruthy()
    expect(screen.getByText('Sign up to Start →')).toBeTruthy()
  })

  it('lists all six career paths and drops the removed QA role', () => {
    renderLanding()
    expect(screen.getByText('SIX FOCUSED PATHS')).toBeTruthy()
    for (const title of [
      'Frontend Developer',
      'Backend Developer',
      'Data Analyst',
      'Cloud/DevOps Engineer',
      'Data Engineer',
      'Security Analyst',
    ]) {
      // Role cards are the only level-3 headings; the example score card's
      // "Data Analyst" is an h2 and must not collide with this query.
      expect(screen.getByRole('heading', { level: 3, name: title })).toBeTruthy()
    }
    expect(screen.queryByText('QA Automation Engineer')).toBeNull()
  })

  it('shows the static example score card for signed-out visitors', () => {
    renderLanding()
    expect(screen.getByText('Understand the why, then take the next step.')).toBeTruthy()
    expect(screen.queryByText('Track my progress →')).toBeNull()
  })
})
