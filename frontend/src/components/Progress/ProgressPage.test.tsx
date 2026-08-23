import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProgressPage } from './ProgressPage'

const noop = () => {}

function renderProgress() {
  return render(
    <ProgressPage
      onBackToHome={noop}
      onOpenDashboard={vi.fn()}
      onViewResults={noop}
    />,
  )
}

describe('ProgressPage', () => {
  // No Supabase env in tests, so the loader deterministically lands on the
  // error card — this pins the mount + failure flow without any network.
  it('mounts and surfaces a clean error card when auth is not configured', async () => {
    renderProgress()
    expect(await screen.findByText('Unable to Load Progress')).toBeTruthy()
    expect(await screen.findByText('Supabase client is not configured.')).toBeTruthy()
    expect(screen.getByText('Back to Home')).toBeTruthy()
  })
})
