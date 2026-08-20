import { AskAboutResults } from './AskAboutResults'

interface QuestionsPageProps {
  userEmail: string | null
  onBackToHome: () => void
  onSignIn: () => void
  onSignUp: () => void
}

export function QuestionsPage({
  userEmail,
  onBackToHome,
  onSignIn,
  onSignUp,
}: QuestionsPageProps) {
  return (
    <main className="questions-page">
      <nav className="assessment-top-nav">
        <button type="button" className="btn-back-link" onClick={onBackToHome}>
          ← Back to Overview
        </button>
        <span className="brand-badge">Pathfinder • Q&A</span>
      </nav>

      {userEmail ? (
        <AskAboutResults />
      ) : (
        <section className="login-card" aria-labelledby="qa-title">
          <p className="eyebrow">GROUNDED PATHFINDER Q&A</p>
          <h1 id="qa-title">Ask about your results.</h1>
          <p>
            Sign in to ask about fit scores, skill gaps, or roadmap milestones.
            Answers use only your Pathfinder data — complete the assessment first
            so there is something to ask about.
          </p>
          <div className="questions-auth-actions">
            <button type="button" className="btn-primary" onClick={onSignIn}>
              Log in to ask →
            </button>
            <button type="button" className="btn-secondary" onClick={onSignUp}>
              Sign up
            </button>
          </div>
        </section>
      )}
    </main>
  )
}
