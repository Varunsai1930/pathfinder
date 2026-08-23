import { useEffect, useState } from 'react'
import { config } from '../../lib/config'
import { supabase } from '../../lib/supabase'

interface TopPath {
  role_id: string
  role_title: string
  fit: number
}

interface LandingPageProps {
  userEmail: string | null
  onSignIn: () => void
  onStart: () => void
  onSignOut: () => void
  onAskQuestions: () => void
  onOpenDashboard: (roleId: string, roleTitle?: string) => void
  onViewResults: () => void
}

const roles = [
  ['Frontend Developer', 'Build accessible interfaces and browser experiences.'],
  ['Backend Developer', 'Design the systems and APIs behind products.'],
  ['Data Analyst', 'Turn data into insights and confident decisions.'],
  ['Cloud/DevOps Engineer', 'Automate delivery and run reliable infrastructure.'],
  ['Data Engineer', 'Build the pipelines that move, model, and trust data.'],
  ['Security Analyst', 'Find weaknesses early and defend what you ship.'],
]

/** Load the signed-in user's real top path (persisted match first) for the
 *  welcome-back card; silently keeps the example card when none exists. */
function useTopPath(userEmail: string | null): TopPath | null {
  const [topPath, setTopPath] = useState<TopPath | null>(null)

  useEffect(() => {
    if (!userEmail || !supabase) return
    const client = supabase
    let cancelled = false

    const load = async () => {
      try {
        const { data: sessionData } = await client.auth.getSession()
        const token = sessionData?.session?.access_token
        if (!token) return
        const headers = { Authorization: `Bearer ${token}` }

        let res = await fetch(`${config.apiUrl}/api/v1/match`, { headers })
        if (res.status === 404) {
          // No fresh persisted result: compute once only if a profile exists.
          const profileRes = await fetch(`${config.apiUrl}/api/v1/profile`, { headers })
          if (profileRes.status === 404) return
          res = await fetch(`${config.apiUrl}/api/v1/match`, { method: 'POST', headers })
        }
        if (!res.ok) return
        const data = await res.json()
        const top = data.recommendations?.[0]
        if (!cancelled && top) {
          setTopPath({
            role_id: top.role_id,
            role_title: top.role_title,
            fit: Math.round(top.pathfinder_fit_score),
          })
        }
      } catch {
        // Landing stays on the example card — never block the page on this.
      }
    }

    void load()
    return () => { cancelled = true }
  }, [userEmail])

  return topPath
}

export function LandingPage({
  userEmail,
  onSignIn,
  onStart,
  onSignOut,
  onAskQuestions,
  onOpenDashboard,
  onViewResults,
}: LandingPageProps) {
  const topPath = useTopPath(userEmail)

  return (
    <main>
      <nav className="nav" aria-label="Primary navigation">
        <a className="brand" href="#top">
          Pathfinder<span>•</span>
        </a>
        <a href="#how-it-works">How it works</a>
        <a href="#paths">Career paths</a>
        <div className="nav-auth">
          {userEmail ? (
            <span className="nav-user-email">{userEmail}</span>
          ) : (
            <button type="button" className="nav-link-btn" onClick={onSignIn}>
              Log in
            </button>
          )}
          <button type="button" className="nav-cta" onClick={onStart}>
            {userEmail ? 'Start Assessment →' : 'Sign up'}
          </button>
        </div>
      </nav>

      <section className="hero" id="top">
        <div>
          <h1>The AI can persuade. It can't decide.</h1>
          <p className="lede">
            Every other tool tells you what to learn. Pathfinder shows you the math, then explains
            it in plain language — describe your goal in your own words, get a transparent fit
            score for six tech careers, and follow a plan you can audit.
          </p>

          <div className="hero-cta-group">
            {topPath ? (
              <>
                <button
                  type="button"
                  className="btn-hero-primary"
                  onClick={() => onOpenDashboard(topPath.role_id, topPath.role_title)}
                >
                  Continue my path — {topPath.role_title} →
                </button>
                <button type="button" className="btn-ghost" onClick={onViewResults}>
                  View my results
                </button>
              </>
            ) : (
              <button type="button" className="btn-hero-primary" onClick={onStart}>
                {userEmail ? 'Start Free Assessment →' : 'Sign up to Start →'}
              </button>
            )}
          </div>

          {userEmail ? (
            <div className="hero-signed-in">
              <p>Signed in as <strong>{userEmail}</strong></p>
              <button type="button" className="btn-ghost" onClick={onSignOut}>
                Sign out
              </button>
            </div>
          ) : null}
        </div>

        <aside className="score-card" aria-label="Example PathFinder score">
          {topPath ? (
            <>
              <p>YOUR TOP PATH</p>
              <h2>{topPath.role_title}</h2>
              <strong>
                {topPath.fit} <small>fit score</small>
              </strong>
              <button
                type="button"
                className="btn-primary"
                onClick={() => onOpenDashboard(topPath.role_id, topPath.role_title)}
              >
                Go to my dashboard →
              </button>
              <footer>Pick up your milestones right where you left them.</footer>
            </>
          ) : (
            <>
              <p>YOUR TOP PATH</p>
              <h2>Data Analyst</h2>
              <strong>
                82 <small>fit score</small>
              </strong>
              <ul>
                <li>
                  <span>Interest alignment</span>
                  <b>90</b>
                </li>
                <li>
                  <span>Current skill readiness</span>
                  <b>71</b>
                </li>
                <li>
                  <span>Work-style alignment</span>
                  <b>84</b>
                </li>
              </ul>
              <footer>Understand the why, then take the next step.</footer>
            </>
          )}
        </aside>
      </section>

      <section className="steps" id="how-it-works">
        <p className="eyebrow">HOW IT WORKS</p>
        <div className="step-grid">
          <article>
            <b>01</b>
            <h2>Start with your goal</h2>
            <p>Describe what you want in your own words. Pathfinder drafts your interests, skills, and time constraints from it — you review and edit every part.</p>
          </article>
          <article>
            <b>02</b>
            <h2>Compare career fits</h2>
            <p>See how six focused tech careers align with your profile—and where the gaps are.</p>
          </article>
          <article>
            <b>03</b>
            <h2>Follow a real plan</h2>
            <p>Turn one selected path into milestones, weekly tasks, and a project that proves your progress.</p>
          </article>
        </div>
      </section>

      <section className="paths" id="paths">
        <p className="eyebrow">SIX FOCUSED PATHS</p>
        <h2>Start broad enough to explore, focused enough to act.</h2>
        <div className="role-grid">
          {roles.map(([title, description]) => (
            <article key={title}>
              <h3>{title}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
        {!userEmail ? (
          <div className="paths-qa">
            <button type="button" className="btn-primary" onClick={onAskQuestions}>
              Pathfinder Q&A →
            </button>
            <p>Ask about career fit, skill gaps, and next steps after you sign in.</p>
          </div>
        ) : null}
      </section>
    </main>
  )
}
