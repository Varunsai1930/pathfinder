import { useEffect, useState } from 'react'
import { AssessmentPage } from './components/Assessment/AssessmentPage'
import { LoginPage } from './components/Login/LoginPage'
import { SignUpPage } from './components/Login/SignUpPage'
import { supabase } from './lib/supabase'

const roles = [
  ['Frontend Developer', 'Build accessible interfaces and browser experiences.'],
  ['Backend Developer', 'Design the systems and APIs behind products.'],
  ['Data Analyst', 'Turn data into insights and confident decisions.'],
  ['Cloud/DevOps Engineer', 'Automate delivery and run reliable infrastructure.'],
]

type AppView = 'landing' | 'login' | 'signup' | 'assessment'

function App() {
  const [currentView, setCurrentView] = useState<AppView>('landing')
  const [userEmail, setUserEmail] = useState<string | null>(null)

  useEffect(() => {
    if (!supabase) return

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.user?.email) {
        setUserEmail(session.user.email)
      }
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUserEmail(session?.user?.email ?? null)
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [])

  async function handleSignOut() {
    if (!supabase) return
    await supabase.auth.signOut()
    setUserEmail(null)
  }

  if (currentView === 'assessment') {
    return (
      <main>
        <AssessmentPage onBackToHome={() => setCurrentView('landing')} />
      </main>
    )
  }

  if (currentView === 'login') {
    return (
      <LoginPage
        userEmail={userEmail}
        onBackToHome={() => setCurrentView('landing')}
        onContinue={() => setCurrentView('assessment')}
        onGoToSignUp={() => setCurrentView('signup')}
      />
    )
  }

  if (currentView === 'signup') {
    return (
      <SignUpPage
        userEmail={userEmail}
        onBackToHome={() => setCurrentView('landing')}
        onContinue={() => setCurrentView('assessment')}
        onGoToLogin={() => setCurrentView('login')}
      />
    )
  }

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
            <button type="button" className="nav-link-btn" onClick={() => setCurrentView('login')}>
              Log in
            </button>
          )}
          <button
            type="button"
            className="nav-cta"
            onClick={() => setCurrentView(userEmail ? 'assessment' : 'signup')}
          >
            {userEmail ? 'Start Assessment →' : 'Sign up'}
          </button>
        </div>
      </nav>

      <section className="hero" id="top">
        <div>
          <h1>Choose a career path with evidence—not guesswork.</h1>
          <p className="lede">
            Pathfinder compares your interests, current skills, and available time with clear entry-level technology paths. You get a transparent fit score and an actionable plan.
          </p>

          <div className="hero-cta-group">
            <button
              type="button"
              className="btn-hero-primary"
              onClick={() => setCurrentView(userEmail ? 'assessment' : 'signup')}
            >
              {userEmail ? 'Start Free Assessment →' : 'Sign up to Start →'}
            </button>
          </div>

          {userEmail ? (
            <div className="hero-signed-in">
              <p>Signed in as <strong>{userEmail}</strong></p>
              <button type="button" className="btn-ghost" onClick={handleSignOut}>
                Sign out
              </button>
            </div>
          ) : null}
        </div>

        <aside className="score-card" aria-label="Example PathFinder score">
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
        </aside>
      </section>

      <section className="steps" id="how-it-works">
        <p className="eyebrow">HOW IT WORKS</p>
        <div className="step-grid">
          <article>
            <b>01</b>
            <h2>Explore your profile</h2>
            <p>Share your interests, skills, work preferences, and time available each week.</p>
          </article>
          <article>
            <b>02</b>
            <h2>Compare career fits</h2>
            <p>See how four focused tech careers align with your profile—and where the gaps are.</p>
          </article>
          <article>
            <b>03</b>
            <h2>Follow a real plan</h2>
            <p>Turn one selected path into milestones, weekly tasks, and a project that proves your progress.</p>
          </article>
        </div>
      </section>

      <section className="paths" id="paths">
        <p className="eyebrow">FOUR FOCUSED PATHS</p>
        <h2>Start broad enough to explore, focused enough to act.</h2>
        <div className="role-grid">
          {roles.map(([title, description]) => (
            <article key={title}>
              <h3>{title}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  )
}

export default App
