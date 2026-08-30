import { useEffect, useState } from 'react'
import { config } from '../../lib/config'
import { supabase } from '../../lib/supabase'
import { loadMatch, ProfileMissingError } from '../../lib/api'

interface WeeklyItem {
  week: number
  milestone_id: string
  title: string
  practical_task: string
  estimated_effort_hours: number
  task_id: string | null
  completed: boolean
  time_spent_minutes: number | null
  quiz_score: number | null
}

interface RoadmapResponse {
  role_id: string
  weekly_plan: WeeklyItem[]
}

interface ProgressPageProps {
  onBackToHome: () => void
  onOpenDashboard: (roleId: string, roleTitle?: string) => void
  onViewResults: () => void
}

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'no-assessment' }
  | { kind: 'no-roadmap'; roleId: string; roleTitle: string }
  | {
      kind: 'ready'
      roleId: string
      roleTitle: string
      plan: WeeklyItem[]
    }

async function detailFrom(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json()
    if (body?.detail) return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  } catch { /* not JSON */ }
  return fallback
}

export function ProgressPage({ onBackToHome, onOpenDashboard, onViewResults }: ProgressPageProps) {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        if (!supabase) throw new Error('Supabase client is not configured.')
        const { data: sessionData, error: sessionError } = await supabase.auth.getSession()
        if (sessionError) throw new Error(`Auth error: ${sessionError.message}`)
        const token = sessionData?.session?.access_token
        if (!token) throw new Error('You must be signed in to view your progress.')
        const headers = { Authorization: `Bearer ${token}` }

        // Static catalog for role titles (public, no auth needed).
        const [profileRes, catalogRes] = await Promise.all([
          fetch(`${config.apiUrl}/api/v1/profile`, { headers }),
          fetch(`${config.apiUrl}/api/v1/catalog/roles`),
        ])
        if (profileRes.status === 404) {
          if (!cancelled) setState({ kind: 'no-assessment' })
          return
        }
        if (!profileRes.ok) throw new Error(await detailFrom(profileRes, 'Could not load your profile.'))
        const profile = await profileRes.json()
        const catalog = catalogRes.ok ? await catalogRes.json() : null
        const titleFor = (roleId: string) =>
          catalog?.roles?.find((r: { id: string; title: string }) => r.id === roleId)?.title ?? roleId.replace(/-/g, ' ')

        // Track the path the learner actually explored; fall back to their top match.
        let roleId: string | null = profile.selected_role_id ?? null
        if (!roleId) {
          try {
            const data = await loadMatch(headers, 'Could not load your results.', { explain: true })
            roleId = data.recommendations?.[0]?.role_id ?? null
          } catch (err: unknown) {
            if (err instanceof ProfileMissingError) {
              if (!cancelled) setState({ kind: 'no-assessment' })
              return
            }
            throw err
          }
        }
        if (!roleId) {
          if (!cancelled) setState({ kind: 'no-assessment' })
          return
        }

        const roadmapRes = await fetch(`${config.apiUrl}/api/v1/roadmaps/${roleId}`, { headers })
        if (roadmapRes.status === 404) {
          if (!cancelled) setState({ kind: 'no-roadmap', roleId, roleTitle: titleFor(roleId) })
          return
        }
        if (!roadmapRes.ok) throw new Error(await detailFrom(roadmapRes, 'Could not load your roadmap.'))
        const roadmap: RoadmapResponse = await roadmapRes.json()
        if (!cancelled) {
          setState({ kind: 'ready', roleId, roleTitle: titleFor(roleId), plan: roadmap.weekly_plan })
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setState({ kind: 'error', message: err instanceof Error ? err.message : 'Unknown error while loading progress.' })
        }
      }
    }

    void load()
    return () => { cancelled = true }
  }, [])

  if (state.kind === 'loading') {
    return (
      <div className="assessment-loading-card" role="status" aria-live="polite">
        <div className="loading-spinner" />
        <h3>Loading your progress…</h3>
      </div>
    )
  }

  if (state.kind === 'error') {
    return (
      <div className="assessment-error-card" role="alert">
        <span className="error-icon">✕</span>
        <h3>Unable to Load Progress</h3>
        <p className="error-message">{state.message}</p>
        <div className="error-actions">
          <button type="button" className="btn-primary" onClick={() => window.location.reload()}>Retry</button>
          <button type="button" className="btn-secondary" onClick={onBackToHome}>Back to Home</button>
        </div>
      </div>
    )
  }

  if (state.kind === 'no-assessment') {
    return (
      <div className="progress-page">
        <nav className="assessment-top-nav">
          <button type="button" className="btn-back-link" onClick={onBackToHome}>← Back to Home</button>
          <span className="brand-badge">Pathfinder • Progress</span>
        </nav>
        <section className="progress-empty">
          <h2>Nothing to track yet</h2>
          <p>Complete the assessment and explore a path first — then this page shows your milestones, what's left, and what's next.</p>
          <button type="button" className="btn-primary" onClick={onViewResults}>View my results</button>
        </section>
      </div>
    )
  }

  if (state.kind === 'no-roadmap') {
    return (
      <div className="progress-page">
        <nav className="assessment-top-nav">
          <button type="button" className="btn-back-link" onClick={onBackToHome}>← Back to Home</button>
          <span className="brand-badge">Pathfinder • Progress</span>
        </nav>
        <section className="progress-empty">
          <h2>No plan started for {state.roleTitle}</h2>
          <p>Open this path's dashboard once to generate its milestone plan, then track it here.</p>
          <button type="button" className="btn-primary" onClick={() => onOpenDashboard(state.roleId, state.roleTitle)}>
            Open dashboard
          </button>
        </section>
      </div>
    )
  }

  const plan = state.plan
  const completed = plan.filter((w) => w.completed)
  const remaining = plan.filter((w) => !w.completed)
  const totalHours = plan.reduce((sum, w) => sum + w.estimated_effort_hours, 0)
  const doneHours = completed.reduce((sum, w) => sum + w.estimated_effort_hours, 0)
  const loggedMinutes = completed.reduce((sum, w) => sum + (w.time_spent_minutes ?? 0), 0)
  const pct = plan.length ? Math.round((completed.length / plan.length) * 100) : 0
  const next = remaining.length ? remaining.reduce((a, b) => (a.week <= b.week ? a : b)) : null

  // 140px ring, r=60 → circumference = 2πr ≈ 376.99
  const circumference = 2 * Math.PI * 60
  const dashOffset = circumference * (1 - pct / 100)

  return (
    <div className="progress-page">
      <nav className="assessment-top-nav">
        <button type="button" className="btn-back-link" onClick={onBackToHome}>← Back to Home</button>
        <span className="brand-badge">Pathfinder • Progress</span>
      </nav>

      <header className="progress-header">
        <p className="eyebrow">YOUR PROGRESS</p>
        <h1>{state.roleTitle}</h1>
      </header>

      <section className="progress-summary" aria-label="Progress summary">
        <div className="progress-ring" role="img" aria-label={`${pct}% of milestones complete`}>
          <svg viewBox="0 0 140 140" width="140" height="140">
            <circle cx="70" cy="70" r="60" className="progress-ring-track" />
            <circle
              cx="70" cy="70" r="60"
              className="progress-ring-fill"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
            />
          </svg>
          <div className="progress-ring-center">
            <strong>{pct}%</strong>
            <span>complete</span>
          </div>
        </div>
        <div className="progress-stats">
          <div className="progress-stat">
            <strong>{completed.length} of {plan.length}</strong>
            <span>milestones completed</span>
          </div>
          <div className="progress-stat">
            <strong>{doneHours}h of {totalHours}h</strong>
            <span>planned effort finished</span>
          </div>
          <div className="progress-stat">
            <strong>{loggedMinutes > 0 ? `${Math.round(loggedMinutes / 60)}h ${loggedMinutes % 60}m` : '—'}</strong>
            <span>time actually logged</span>
          </div>
        </div>
      </section>

      {next && (
        <section className="progress-next" aria-labelledby="progress-next-title">
          <p className="eyebrow">NEXT THING TO DO</p>
          <h2 id="progress-next-title">{next.title}</h2>
          <p className="progress-next-task">{next.practical_task}</p>
          <div className="progress-next-meta">
            <span>Week {next.week}</span>
            <span>≈ {next.estimated_effort_hours} hours of focused work</span>
          </div>
          <button
            type="button"
            className="btn-primary"
            onClick={() => onOpenDashboard(state.roleId, state.roleTitle)}
          >
            Work on it — open dashboard →
          </button>
        </section>
      )}

      {!next && (
        <section className="progress-next progress-next--done">
          <p className="eyebrow">ALL DONE</p>
          <h2>Every milestone complete. Great work!</h2>
          <p className="progress-next-task">Review your portfolio deliverable — it's the evidence of everything you built.</p>
        </section>
      )}

      <section className="progress-lists">
        <div className="progress-list">
          <h3>Completed ({completed.length})</h3>
          {completed.length === 0 && <p className="progress-list-empty">Nothing yet — your first milestone is waiting above.</p>}
          <ul>
            {completed.map((w) => (
              <li key={w.milestone_id} className="progress-item progress-item--done">
                <span className="progress-check" aria-hidden="true">✓</span>
                <div>
                  <b>{w.title}</b>
                  <small>
                    Week {w.week} · {w.estimated_effort_hours}h
                    {w.time_spent_minutes != null ? ` · logged ${w.time_spent_minutes}m` : ''}
                    {w.quiz_score != null ? ` · quiz ${w.quiz_score}%` : ''}
                  </small>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="progress-list">
          <h3>Remaining ({remaining.length})</h3>
          {remaining.length === 0 && <p className="progress-list-empty">Nothing left — you finished the whole path.</p>}
          <ul>
            {remaining.map((w) => (
              <li key={w.milestone_id} className="progress-item">
                <span className="progress-dot" aria-hidden="true" />
                <div>
                  <b>{w.title}</b>
                  <small>Week {w.week} · {w.estimated_effort_hours}h</small>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  )
}
