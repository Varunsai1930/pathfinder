import { useState } from 'react'
import { config } from '../../lib/config'
import { supabase } from '../../lib/supabase'

interface SignUpPageProps {
  userEmail: string | null
  onBackToHome: () => void
  onContinue: () => void
  onGoToLogin: () => void
}

export function SignUpPage({ userEmail, onBackToHome, onContinue, onGoToLogin }: SignUpPageProps) {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function requestSignUp(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!supabase) {
      setMessage('Sign-up is ready to connect once Supabase environment variables are added.')
      return
    }

    setIsSubmitting(true)
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: window.location.origin,
      },
    })
    setMessage(error ? error.message : 'Check your email for a secure sign-up link.')
    setIsSubmitting(false)
  }

  return (
    <main className="login-page">
      <nav className="assessment-top-nav">
        <button type="button" className="btn-back-link" onClick={onBackToHome}>
          ← Back to Overview
        </button>
        <span className="brand-badge">Pathfinder • Sign up</span>
      </nav>

      <section className="login-card" aria-labelledby="signup-title">
        <p className="eyebrow">CREATE YOUR ACCOUNT</p>
        <h1 id="signup-title">Welcome to Career Pathfinder</h1>
        <p className="login-greeting">
          Please sign up to find our paths in your career.
        </p>

        {userEmail ? (
          <div className="login-signed-in">
            <p>Signed in as <strong>{userEmail}</strong></p>
            <button type="button" className="btn-primary" onClick={onContinue}>
              Continue to Assessment →
            </button>
          </div>
        ) : (
          <form className="login-form" onSubmit={requestSignUp}>
            <label htmlFor="signup-email">Email address</label>
            <input
              id="signup-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              required
            />
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Sending…' : 'Create account'}
            </button>
            {message && <p className="message" role="status">{message}</p>}
          </form>
        )}

        {!userEmail && (
          <p className="auth-switch">
            Already have an account?{' '}
            <button type="button" className="auth-switch-link" onClick={onGoToLogin}>
              Log in
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
