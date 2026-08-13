import { useState } from 'react'
import { config } from './lib/config'
import { supabase } from './lib/supabase'

const roles = [
  ['Frontend Developer', 'Build accessible interfaces and browser experiences.'],
  ['Backend Developer', 'Design the systems and APIs behind products.'],
  ['Data Analyst', 'Turn data into insights and confident decisions.'],
  ['Cloud/DevOps Engineer', 'Automate delivery and run reliable infrastructure.'],
]

function App() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function requestSignIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!supabase) {
      setMessage('Sign-in is ready to connect once Supabase environment variables are added.')
      return
    }

    setIsSubmitting(true)
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin },
    })
    setMessage(error ? error.message : 'Check your email for a secure sign-in link.')
    setIsSubmitting(false)
  }

  return (
    <main>
      <nav className="nav" aria-label="Primary navigation">
        <a className="brand" href="#top">Pathfinder<span>•</span></a>
        <a href="#how-it-works">How it works</a>
        <a href="#paths">Career paths</a>
      </nav>

      <section className="hero" id="top">
        <div>
          <p className="eyebrow">FOR INDIAN TECH STUDENTS</p>
          <h1>Choose a career path with evidence—not guesswork.</h1>
          <p className="lede">Pathfinder compares your interests, current skills, and available time with clear entry-level technology paths. You get a transparent fit score and an actionable plan.</p>
          <form className="sign-in" onSubmit={requestSignIn}>
            <label htmlFor="email">Start with your email</label>
            <div className="form-row">
              <input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" required />
              <button disabled={isSubmitting}>{isSubmitting ? 'Sending…' : 'Get started'}</button>
            </div>
            {message && <p className="message" role="status">{message}</p>}
          </form>
          {!config.hasSupabaseAuth && <p className="preview-note">Preview mode: authentication configuration is pending.</p>}
        </div>
        <aside className="score-card" aria-label="Example PathFinder score">
          <p>YOUR TOP PATH</p>
          <h2>Data Analyst</h2>
          <strong>82 <small>fit score</small></strong>
          <ul>
            <li><span>Interest alignment</span><b>90</b></li>
            <li><span>Current skill readiness</span><b>71</b></li>
            <li><span>Work-style alignment</span><b>84</b></li>
          </ul>
          <footer>Understand the why, then take the next step.</footer>
        </aside>
      </section>

      <section className="steps" id="how-it-works">
        <p className="eyebrow">HOW IT WORKS</p>
        <div className="step-grid">
          <article><b>01</b><h2>Explore your profile</h2><p>Share your interests, skills, work preferences, and time available each week.</p></article>
          <article><b>02</b><h2>Compare career fits</h2><p>See how four focused tech careers align with your profile—and where the gaps are.</p></article>
          <article><b>03</b><h2>Follow a real plan</h2><p>Turn one selected path into milestones, weekly tasks, and a project that proves your progress.</p></article>
        </div>
      </section>

      <section className="paths" id="paths">
        <p className="eyebrow">FOUR FOCUSED PATHS</p>
        <h2>Start broad enough to explore, focused enough to act.</h2>
        <div className="role-grid">
          {roles.map(([title, description]) => <article key={title}><h3>{title}</h3><p>{description}</p></article>)}
        </div>
      </section>
    </main>
  )
}

export default App
