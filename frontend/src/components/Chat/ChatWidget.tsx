import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { config } from '../../lib/config'
import { supabase } from '../../lib/supabase'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  generationMode?: 'fallback' | 'llm'
  isError?: boolean
  pending?: boolean
}

interface AskQuestionResponse {
  answer: string
  generation_mode: 'fallback' | 'llm'
}

export function ChatWidget() {
  const titleId = useId()
  const inputId = useId()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    const list = listRef.current
    if (!list) return
    list.scrollTop = list.scrollHeight
  }, [messages, open, isLoading, error])

  useEffect(() => {
    if (!open) return

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = draft.trim()
    if (!text) return
    if (text.length < 3) {
      setError('Enter a question with at least three characters.')
      return
    }
    if (text.length > 500) {
      setError('Question must be 500 characters or fewer.')
      return
    }

    // Friendly auth guard before calling API — same pattern as AskAboutResults.tsx / DashboardPage.tsx
    if (!supabase) {
      const msg = 'Sign in to chat — authentication is not configured.'
      setError(msg)
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'user', text },
        { id: crypto.randomUUID(), role: 'assistant', text: msg, isError: true },
      ])
      setDraft('')
      return
    }

    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', text }
    const pendingId = crypto.randomUUID()
    const pendingMessage: ChatMessage = {
      id: pendingId,
      role: 'assistant',
      text: 'Thinking…',
      pending: true,
    }

    setMessages((current) => [...current, userMessage, pendingMessage])
    setDraft('')
    setError(null)
    setIsLoading(true)

    try {
      const { data: sessionData, error: sessionError } = await supabase.auth.getSession()
      if (sessionError) throw new Error(`Auth error: ${sessionError.message}`)
      const token = sessionData?.session?.access_token
      if (!token) throw new Error('Sign in to chat to ask about your results.')

      const response = await fetch(`${config.apiUrl}/api/v1/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ question: text }),
      })

      if (!response.ok) {
        let detail = `Unable to answer your question (${response.status})`
        try {
          const body = await response.json()
          if (typeof body?.detail === 'string') detail = body.detail
          else if (body?.detail) detail = JSON.stringify(body.detail)
        } catch {
          /* response was not JSON */
        }
        throw new Error(detail)
      }

      const data = (await response.json()) as AskQuestionResponse
      setMessages((current) =>
        current.map((m) =>
          m.id === pendingId
            ? { ...m, text: data.answer, generationMode: data.generation_mode, pending: false }
            : m,
        ),
      )
    } catch (caught: unknown) {
      const msg = caught instanceof Error ? caught.message : 'Unable to answer your question.'
      setError(msg)
      setMessages((current) =>
        current.map((m) =>
          m.id === pendingId ? { ...m, text: msg, isError: true, pending: false } : m,
        ),
      )
    } finally {
      setIsLoading(false)
    }
  }

  const isSendDisabled = !draft.trim() || isLoading

  return (
    <div className="chat-widget">
      {open ? (
        <section
          className="chat-panel"
          role="dialog"
          aria-labelledby={titleId}
          aria-describedby="chat-panel-note"
        >
          <header className="chat-panel-header">
            <div>
              <p className="eyebrow">Pathfinder chat</p>
              <h2 id={titleId}>Ask Pathfinder</h2>
            </div>
            <span className="chat-soon-badge" id="chat-panel-note">
              Grounded Q&A
            </span>
          </header>

          <div className="chat-messages" ref={listRef} aria-live="polite">
            {messages.length === 0 ? (
              <p className="chat-empty">
                Ask about your scores, skill gaps, or roadmap milestones. Answers use only your
                Pathfinder data.
              </p>
            ) : (
              <ul>
                {messages.map((message) => (
                  <li
                    key={message.id}
                    className={`chat-bubble chat-bubble--${message.role}${message.isError ? ' chat-bubble--error' : ''}${message.pending ? ' chat-bubble--pending' : ''}`}
                    style={
                      message.isError
                        ? {
                            borderColor: 'var(--border-danger)',
                            background: 'var(--accent-danger-soft)',
                            color: 'var(--text-danger)',
                          }
                        : message.pending
                          ? { opacity: 0.85 }
                          : undefined
                    }
                    aria-live={message.pending ? 'polite' : undefined}
                  >
                    <span className="sr-only">
                      {message.role === 'user' ? 'You' : 'Pathfinder'}:{' '}
                    </span>
                    <span>{message.text}</span>
                    {message.role === 'assistant' && message.generationMode && !message.pending && !message.isError && (
                      <small
                        style={{
                          display: 'block',
                          marginTop: '6px',
                          font: "600 0.68rem 'DM Mono', monospace",
                          letterSpacing: '0.06em',
                          textTransform: 'uppercase',
                          color: 'var(--text-secondary)',
                        }}
                      >
                        {message.generationMode === 'llm'
                          ? 'Personalized from your data'
                          : 'Grounded Pathfinder guidance'}
                      </small>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {error && (
            <p
              id="chat-error"
              role="alert"
              style={{
                margin: '0 14px',
                padding: '8px 10px',
                borderRadius: '8px',
                background: 'var(--accent-danger-soft)',
                border: '1px solid var(--border-danger)',
                color: 'var(--text-danger)',
                fontSize: '0.82rem',
                lineHeight: 1.5,
              }}
            >
              {error}
            </p>
          )}

          <form className="chat-composer" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor={inputId}>
              Message
            </label>
            <input
              id={inputId}
              ref={inputRef}
              value={draft}
              maxLength={500}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask about your results…"
              autoComplete="off"
              disabled={isLoading}
              aria-describedby={error ? 'chat-error' : undefined}
            />
            <button type="submit" className="btn-primary btn-compact" disabled={isSendDisabled}>
              {isLoading ? 'Thinking…' : 'Send'}
            </button>
          </form>
        </section>
      ) : null}

      <button
        type="button"
        className={`chat-fab${open ? ' chat-fab--open' : ''}`}
        aria-label={open ? 'Close chat' : 'Open chat'}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        {open ? <CloseIcon /> : <ChatIcon />}
      </button>
    </div>
  )
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
      <path
        d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
      <path
        d="M18 6 6 18M6 6l12 12"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}
