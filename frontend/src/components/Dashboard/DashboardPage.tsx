import { useEffect, useState } from 'react'
import { config } from '../../lib/config'
import { supabase } from '../../lib/supabase'
import { AskAboutResults } from '../Questions/AskAboutResults'

interface RoadmapResource {
  title: string
  url: string
  provider: string
}

interface RoadmapWeek {
  week: number
  milestone_id: string
  title: string
  objective: string
  skills: string[]
  estimated_effort_hours: number
  practical_task: string
  portfolio_deliverable: string
  resources: RoadmapResource[]
  task_id: string | null
  completed: boolean
  personalized_focus: string
}

interface RoadmapResponse {
  role_id: string
  weekly_plan: RoadmapWeek[]
  generation_mode: 'fallback' | 'llm'
  created_at: string
  updated_at: string
  adaptation_note: string
}

interface NextAction {
  milestone_id: string | null
  task_label: string | null
  message: string
}

interface TaskUpdateResponse {
  task: {
    id: string
    completed: boolean
  }
  next_action: NextAction
}

interface DashboardPageProps {
  roleId: string
  roleTitle: string
  skillReadiness?: number
  portfolioProject?: {
    title: string
    brief: string
    evidenceOfReadiness: string[]
  }
  onBackToResults: () => void
}

function responseError(status: number, fallback: string, body: unknown): Error {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail?: unknown }).detail
    if (typeof detail === 'string') return new Error(detail)
    if (detail) return new Error(JSON.stringify(detail))
  }
  return new Error(`${fallback} (${status})`)
}

function nextActionFromPlan(weeklyPlan: RoadmapWeek[]): NextAction {
  const nextWeek = weeklyPlan.find((week) => !week.completed)
  if (!nextWeek) {
    return {
      milestone_id: null,
      task_label: null,
      message: 'All five roadmap milestones are complete. Great work!',
    }
  }
  return {
    milestone_id: nextWeek.milestone_id,
    task_label: nextWeek.title,
    message: `Next: ${nextWeek.title}`,
  }
}

export function DashboardPage({ roleId, roleTitle, skillReadiness, portfolioProject, onBackToResults }: DashboardPageProps) {
  const [roadmap, setRoadmap] = useState<RoadmapResponse | null>(null)
  const [nextAction, setNextAction] = useState<NextAction | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [patchError, setPatchError] = useState<string | null>(null)
  const [updatingTaskId, setUpdatingTaskId] = useState<string | null>(null)

  const getAuthHeaders = async (): Promise<HeadersInit> => {
    if (!supabase) throw new Error('Supabase client is not configured.')
    const { data: sessionData, error: sessionError } = await supabase.auth.getSession()
    if (sessionError) throw new Error(`Auth error: ${sessionError.message}`)
    const token = sessionData?.session?.access_token
    if (!token) throw new Error('You must be signed in to view your roadmap.')
    return { Authorization: `Bearer ${token}` }
  }

  const fetchRoadmap = async (): Promise<RoadmapResponse> => {
    const headers = await getAuthHeaders()
    const response = await fetch(`${config.apiUrl}/api/v1/roadmaps/${roleId}`, { headers })
    if (response.ok) return response.json() as Promise<RoadmapResponse>

    if (response.status !== 404) {
      let body: unknown = null
      try { body = await response.json() } catch { /* response was not JSON */ }
      throw responseError(response.status, 'Unable to load roadmap', body)
    }

    const createResponse = await fetch(`${config.apiUrl}/api/v1/roadmaps/${roleId}`, {
      method: 'POST',
      headers,
    })
    if (!createResponse.ok) {
      let body: unknown = null
      try { body = await createResponse.json() } catch { /* response was not JSON */ }
      throw responseError(createResponse.status, 'Unable to create roadmap', body)
    }

    const reloaded = await fetch(`${config.apiUrl}/api/v1/roadmaps/${roleId}`, { headers })
    if (!reloaded.ok) {
      let body: unknown = null
      try { body = await reloaded.json() } catch { /* response was not JSON */ }
      throw responseError(reloaded.status, 'Unable to load newly created roadmap', body)
    }
    return reloaded.json() as Promise<RoadmapResponse>
  }

  const loadRoadmap = async () => {
    try {
      setIsLoading(true)
      setLoadError(null)
      const data = await fetchRoadmap()
      setRoadmap(data)
      setNextAction(nextActionFromPlan(data.weekly_plan))
    } catch (error: unknown) {
      setLoadError(error instanceof Error ? error.message : 'Unable to load your roadmap.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadRoadmap()
    // roleId identifies the selected route and is intentionally the only dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roleId])

  const toggleTask = async (week: RoadmapWeek) => {
    if (!roadmap || !week.task_id || updatingTaskId) return

    const previousRoadmap = roadmap
    const previousNextAction = nextAction
    const desiredCompletion = !week.completed
    const optimisticPlan = roadmap.weekly_plan.map((item) => (
      item.task_id === week.task_id ? { ...item, completed: desiredCompletion } : item
    ))

    setPatchError(null)
    setUpdatingTaskId(week.task_id)
    setRoadmap({ ...roadmap, weekly_plan: optimisticPlan })
    setNextAction(nextActionFromPlan(optimisticPlan))

    try {
      const headers = await getAuthHeaders()
      const response = await fetch(`${config.apiUrl}/api/v1/tasks/${week.task_id}`, {
        method: 'PATCH',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed: desiredCompletion }),
      })
      if (!response.ok) {
        let body: unknown = null
        try { body = await response.json() } catch { /* response was not JSON */ }
        throw responseError(response.status, 'Unable to update task', body)
      }

      const data: TaskUpdateResponse = await response.json()
      setRoadmap((current) => current ? {
        ...current,
        weekly_plan: current.weekly_plan.map((item) => (
          item.task_id === data.task.id ? { ...item, completed: data.task.completed } : item
        )),
      } : current)
      setNextAction(data.next_action)
    } catch (error: unknown) {
      setRoadmap(previousRoadmap)
      setNextAction(previousNextAction)
      setPatchError(error instanceof Error ? error.message : 'Unable to update task. Please try again.')
    } finally {
      setUpdatingTaskId(null)
    }
  }

  if (isLoading) {
    return (
      <div className="assessment-loading-card" role="status" aria-live="polite">
        <div className="loading-spinner" />
        <h3>Loading Your Career Path…</h3>
        <p className="loading-subtext">Preparing your milestones and checklist.</p>
      </div>
    )
  }

  if (loadError || !roadmap) {
    return (
      <div className="assessment-error-card" role="alert">
        <span className="error-icon">✕</span>
        <h3>Unable to Load Your Roadmap</h3>
        <p className="error-message">{loadError ?? 'Roadmap data could not be retrieved.'}</p>
        <div className="error-actions">
          <button type="button" className="btn-primary" onClick={() => void loadRoadmap()}>
            Retry
          </button>
          <button type="button" className="btn-secondary" onClick={onBackToResults}>
            Back to Results
          </button>
        </div>
      </div>
    )
  }

  const completedCount = roadmap.weekly_plan.filter((week) => week.completed).length

  return (
    <div className="dashboard-container">
      <nav className="assessment-top-nav">
        <button type="button" className="btn-back-link" onClick={onBackToResults}>
          ← Back to Results
        </button>
        <span className="brand-badge">Pathfinder • Career Path</span>
      </nav>

      <header className="dashboard-hero">
        <div>
          <p className="eyebrow">YOUR CAREER PATH</p>
          <h1>{roleTitle}</h1>
          <p className="dashboard-lede">A five-week milestone plan built from the skills and practical work needed for this path.</p>
        </div>
        <div className="dashboard-readiness" aria-label="Roadmap progress">
          {skillReadiness !== undefined && (
            <p><span>Current readiness</span><strong>{Math.round(skillReadiness)}%</strong></p>
          )}
          <p><span>Milestones complete</span><strong>{completedCount}/5</strong></p>
        </div>
      </header>

      <section className="next-action-banner" aria-live="polite">
        <span className="next-action-label">NEXT BEST ACTION</span>
        <p>{nextAction?.message ?? 'Choose a milestone to continue.'}</p>
      </section>

      {roadmap.adaptation_note && (
        <section className="roadmap-adaptation" aria-label="Personalized roadmap pacing">
          <span>PERSONALIZED PACING</span>
          <p>{roadmap.adaptation_note}</p>
        </section>
      )}

      {patchError && (
        <div className="dashboard-error" role="alert">
          <span>✕</span>
          <p>{patchError}</p>
        </div>
      )}

      {portfolioProject && (
        <section className="dashboard-project-brief" aria-labelledby="portfolio-project-title">
          <p className="eyebrow">PORTFOLIO PROJECT BRIEF</p>
          <h2 id="portfolio-project-title">{portfolioProject.title}</h2>
          <p>{portfolioProject.brief}</p>
          <ul>
            {portfolioProject.evidenceOfReadiness.map((evidence) => <li key={evidence}>{evidence}</li>)}
          </ul>
        </section>
      )}

      <section className="dashboard-milestones" aria-label="Five roadmap milestones">
        {roadmap.weekly_plan.map((week) => (
          <article className={`dashboard-milestone ${week.completed ? 'dashboard-milestone--complete' : ''}`} key={week.milestone_id}>
            <div className="dashboard-week">Week {week.week}</div>
            <div className="dashboard-milestone-content">
              <div className="dashboard-milestone-heading">
                <div>
                  <h2>{week.title}</h2>
                  <p>{week.objective}</p>
                </div>
                <label className="task-checkbox">
                  <input
                    type="checkbox"
                    checked={week.completed}
                    disabled={!week.task_id || updatingTaskId !== null}
                    onChange={() => void toggleTask(week)}
                    aria-label={`Mark ${week.title} as ${week.completed ? 'incomplete' : 'complete'}`}
                  />
                  <span>{week.completed ? 'Complete' : 'Mark complete'}</span>
                </label>
              </div>

              <div className="dashboard-task-grid">
                <div>
                  <span>Practical task</span>
                  <p>{week.practical_task}</p>
                </div>
                <div>
                  <span>Portfolio deliverable</span>
                  <p>{week.portfolio_deliverable}</p>
                </div>
              </div>

              {week.personalized_focus && <p className="milestone-personalized-focus">{week.personalized_focus}</p>}

              <div className="dashboard-milestone-footer">
                <span className="dashboard-skills">Skills: {week.skills.join(', ')}</span>
                <span>{week.estimated_effort_hours} estimated hours</span>
              </div>

              <div className="dashboard-resources">
                <span>Resources</span>
                <ul>
                  {week.resources.map((resource) => (
                    <li key={resource.url}>
                      <a href={resource.url} target="_blank" rel="noreferrer">
                        {resource.title} <small>({resource.provider})</small>
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </article>
        ))}
      </section>

      <AskAboutResults roleId={roleId} />
    </div>
  )
}
