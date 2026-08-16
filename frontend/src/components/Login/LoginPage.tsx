import { useState } from 'react'
import { config } from '../../lib/config'
import { supabase } from '../../lib/supabase'

interface LoginPageProps {
  userEmail: string | null
  onBackToHome: () => void
  onContinue: () => void
  onGoToSignUp: () => void
}

export function LoginPage({ userEmail, onBackToHome, onContinue, onGoToSignUp }: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function requestLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!supabase) {
      setMessage('Login is ready to connect once Supabase environment variables are added.')
      return
    }

    setIsSubmitting(true)
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: window.location.origin,
        shouldCreateUser: false,
      },
    })
    setMessage(
      error
        ? error.message
        : 'Check your email for a secure login link.',
    )
    setIsSubmitting(false)
  }

  return (
    <main className="login-page">
      <nav className="assessment-top-nav">
        <button type="button" className="btn-back-link" onClick={onBackToHome}>
          ← Back to Overview
        </button>
        <span className="brand-badge">Pathfinder • Log in</span>
      </nav>

      <section className="login-card" aria-labelledby="login-title">
        <p className="eyebrow">WELCOME BACK</p>
        <h1 id="login-title">Log in to continue your path.</h1>
        <p>
          Use a secure email link to return to your assessment, roadmap milestones, and task progress.
        </p>

        {userEmail ? (
          <div className="login-signed-in">
            <p>Signed in as <strong>{userEmail}</strong></p>
            <button type="button" className="btn-primary" onClick={onContinue}>
              Continue to Assessment →
            </button>
          </div>
        ) : (
          <form className="login-form" onSubmit={requestLogin}>
            <label htmlFor="login-email">Email address</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              required
            />
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Sending…' : 'Send login link'}
            </button>
            {message && <p className="message" role="status">{message}</p>}
          </form>
        )}

        {!userEmail && (
          <p className="auth-switch">
            New to Pathfinder?{' '}
            <button type="button" className="auth-switch-link" onClick={onGoToSignUp}>
              Sign up
            </button>
          </p>
        )}

        {!config.hasSupabaseAuth && (
          <p className="preview-note">Preview mode: authentication configuration is pending.</p>
        )}
      </section>
    </main>
  )
}
