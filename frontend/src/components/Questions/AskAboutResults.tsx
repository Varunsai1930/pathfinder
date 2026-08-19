import { useState, type FormEvent } from 'react'
import { config } from '../../lib/config'
import { supabase } from '../../lib/supabase'

interface QuestionResponse {
  answer: string
  generation_mode: 'fallback' | 'llm'
}

interface AskAboutResultsProps {
  roleId?: string
}

export function AskAboutResults({ roleId }: AskAboutResultsProps) {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<QuestionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isAsking, setIsAsking] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedQuestion = question.trim()
    if (trimmedQuestion.length < 3) {
      setError('Enter a question with at least three characters.')
      return
    }
    try {
      setIsAsking(true)
      setError(null)
      setAnswer(null)
      if (!supabase) throw new Error('Supabase client is not configured.')
      const { data, error: sessionError } = await supabase.auth.getSession()
      if (sessionError) throw new Error(`Auth error: ${sessionError.message}`)
      const token = data.session?.access_token
      if (!token) throw new Error('You must be signed in to ask about your results.')
      const response = await fetch(`${config.apiUrl}/api/v1/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ question: trimmedQuestion, ...(roleId ? { role_id: roleId } : {}) }),
      })
      if (!response.ok) {
        let detail = `Unable to answer your question (${response.status})`
        try {
          const body = await response.json()
          if (typeof body?.detail === 'string') detail = body.detail
        } catch { /* response was not JSON */ }
        throw new Error(detail)
      }
      setAnswer(await response.json() as QuestionResponse)
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Unable to answer your question.')
    } finally {
      setIsAsking(false)
    }
  }

  return (
    <section className="ask-results" aria-labelledby="ask-results-heading">
      <div>
        <p className="eyebrow">GROUNDED PATHFINDER Q&A</p>
        <h2 id="ask-results-heading">Ask about your results</h2>
        <p>Ask about the scores, skill gaps, or {roleId ? 'this roadmap’s' : 'your'} milestones. Answers use only your Pathfinder data.</p>
      </div>
      <form onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor="pathfinder-question">Your question</label>
        <div className="ask-results-input-row">
          <input
            id="pathfinder-question"
            value={question}
            maxLength={500}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={roleId ? 'What should I work on next?' : 'Why is this role a good match?'}
            disabled={isAsking}
          />
          <button type="submit" className="btn-primary" disabled={isAsking}>
            {isAsking ? 'Thinking…' : 'Ask'}
          </button>
        </div>
      </form>
      {error && <p className="ask-results-error" role="alert">{error}</p>}
      {answer && (
        <div className="ask-results-answer" role="status" aria-live="polite">
          <span>PATHFINDER ANSWER</span>
          <p>{answer.answer}</p>
          <small>{answer.generation_mode === 'llm' ? 'Personalized from your data' : 'Grounded Pathfinder guidance'}</small>
        </div>
      )}
    </section>
  )
}
