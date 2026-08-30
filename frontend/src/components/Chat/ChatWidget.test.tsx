import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

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

import { ChatWidget } from './ChatWidget'

const questionResponse = {
  answer: 'Your top result is Backend Developer (#1, 72 fit score).',
  generation_mode: 'fallback',
}

describe('ChatWidget', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends the question to POST /questions and renders the grounded answer', async () => {
    const fetchMock = vi.fn<(url: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(
      async () =>
        new Response(JSON.stringify(questionResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    )
    vi.stubGlobal('fetch', fetchMock)
    render(<ChatWidget />)

    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))
    fireEvent.change(screen.getByPlaceholderText('Ask about your results…'), {
      target: { value: 'Why backend?' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText(questionResponse.answer)).toBeTruthy()
    expect(screen.getByText('Grounded Pathfinder guidance')).toBeTruthy()

    const calls = fetchMock.mock.calls.filter(([url]) => String(url).includes('/api/v1/questions'))
    expect(calls).toHaveLength(1)
    const init = calls[0]![1] as RequestInit
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body)).question).toBe('Why backend?')
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer test-token')
  })

  it('rejects too-short questions without calling the API', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<ChatWidget />)

    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))
    fireEvent.change(screen.getByPlaceholderText('Ask about your results…'), { target: { value: 'hi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('Enter a question with at least three characters.')).toBeTruthy()
    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled())
  })
})
