import { useEffect, useState } from 'react'
import { config } from '../../lib/config'
import { supabase } from '../../lib/supabase'
import { AskAboutResults } from '../Questions/AskAboutResults'
import type { CareerRecommendation, MatchResponse } from '../Results/ResultsPage'
import { ErrorBoundary, Skeleton } from '../ErrorBoundary'

interface Course {
  id: string
  title: string
  provider: string
  url: string
  skill_ids: string[]
  prerequisites: string[]
  level: string
  duration_hours: number
  description: string
}

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
  time_spent_minutes?: number | null
  quiz_score?: number | null
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
    time_spent_minutes?: number | null
    quiz_score?: number | null
  }
  next_action: NextAction
  skill_progression?: { upgraded_skills: string[]; milestone_id: string; message: string } | null
  telemetry_summary?: {
    completed_count: number
    total_count: number
    completion_rate: number
    avg_time_spent_minutes: number | null
    avg_quiz_score: number | null
    pace_note: string
  } | null
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
  onBackToHome: () => void
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

export function DashboardPage({ roleId, roleTitle, skillReadiness, portfolioProject, onBackToHome }: DashboardPageProps) {
  const [roadmap, setRoadmap] = useState<RoadmapResponse | null>(null)
  const [nextAction, setNextAction] = useState<NextAction | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [patchError, setPatchError] = useState<string | null>(null)
  const [updatingTaskId, setUpdatingTaskId] = useState<string | null>(null)
  const [skillRec, setSkillRec] = useState<CareerRecommendation | null>(null)
  const [skillLoading, setSkillLoading] = useState(true)
  const [skillError, setSkillError] = useState<string | null>(null)
  const [telemetryDraft, setTelemetryDraft] = useState<Record<string, { time: string; quiz: string }>>({})
  const [feedbackNote, setFeedbackNote] = useState<string | null>(null)
  const [courses, setCourses] = useState<Course[]>([])
  const [coursesLoading, setCoursesLoading] = useState(true)
  const [skillNameToIdMap, setSkillNameToIdMap] = useState<Map<string, string> | null>(null)

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

  const loadSkillDevelopment = async () => {
    try {
      setSkillLoading(true)
      setSkillError(null)
      const headers = await getAuthHeaders()
      const response = await fetch(`${config.apiUrl}/api/v1/match`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
      })
      if (!response.ok) {
        let body: unknown = null
        try {
          body = await response.json()
        } catch {
          /* not JSON */
        }
        throw responseError(response.status, 'Unable to load skill development', body)
      }
      const data = (await response.json()) as MatchResponse
      const rec = data.recommendations.find((item) => item.role_id === roleId) ?? null
      setSkillRec(rec)
    } catch (error: unknown) {
      setSkillError(error instanceof Error ? error.message : 'Unable to load skill development.')
    } finally {
      setSkillLoading(false)
    }
  }

  useEffect(() => {
    void loadSkillDevelopment()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roleId])

  useEffect(() => {
    let cancelled = false
    async function loadCoursesAndSkills() {
      try {
        setCoursesLoading(true)
        const [coursesRes, assessmentRes] = await Promise.all([
          fetch(`${config.apiUrl}/api/v1/catalog/courses`),
          fetch(`${config.apiUrl}/api/v1/catalog/assessment`),
        ])
        if (!coursesRes.ok) throw new Error(`Failed to load courses (${coursesRes.status})`)
        const data = (await coursesRes.json()) as { courses: Course[] }
        if (!cancelled) setCourses(data.courses)
        // Derive skill name -> id map from assessment catalog (removes hardcode brittleness)
        if (assessmentRes.ok) {
          const assessment = (await assessmentRes.json()) as { skills: { id: string; name: string }[] }
          const map = new Map<string, string>()
          for (const s of assessment.skills) {
            map.set(s.name.toLowerCase(), s.id)
          }
          if (!cancelled) setSkillNameToIdMap(map)
        }
      } catch {
        if (!cancelled) setCourses([])
      } finally {
        if (!cancelled) setCoursesLoading(false)
      }
    }
    void loadCoursesAndSkills()
    return () => { cancelled = true }
  }, [])

  const toggleTask = async (week: RoadmapWeek) => {
    if (!roadmap || !week.task_id || updatingTaskId) return

    const previousRoadmap = roadmap
    const previousNextAction = nextAction
    const desiredCompletion = !week.completed
    const draft = telemetryDraft[week.milestone_id] ?? { time: '', quiz: '' }
    const parsedTime = draft.time.trim() === '' ? null : Number(draft.time)
    const parsedQuiz = draft.quiz.trim() === '' ? null : Number(draft.quiz)
    if (desiredCompletion) {
      if (parsedTime !== null && (!Number.isFinite(parsedTime) || parsedTime < 0 || parsedTime > 10080)) {
        setPatchError('Time spent must be 0–10080 minutes.')
        return
      }
      if (parsedQuiz !== null && (!Number.isFinite(parsedQuiz) || parsedQuiz < 0 || parsedQuiz > 100)) {
        setPatchError('Quiz score must be 0–100.')
        return
      }
    }
    const optimisticPlan = roadmap.weekly_plan.map((item) => (
      item.task_id === week.task_id
        ? {
            ...item,
            completed: desiredCompletion,
            time_spent_minutes: desiredCompletion ? parsedTime : item.time_spent_minutes,
            quiz_score: desiredCompletion ? parsedQuiz : item.quiz_score,
          }
        : item
    ))

    setPatchError(null)
    setFeedbackNote(null)
    setUpdatingTaskId(week.task_id)
    setRoadmap({ ...roadmap, weekly_plan: optimisticPlan })
    setNextAction(nextActionFromPlan(optimisticPlan))

    try {
      const headers = await getAuthHeaders()
      const payload: Record<string, unknown> = { completed: desiredCompletion }
      if (desiredCompletion) {
        if (parsedTime !== null) payload.time_spent_minutes = parsedTime
        if (parsedQuiz !== null) payload.quiz_score = parsedQuiz
      }
      const response = await fetch(`${config.apiUrl}/api/v1/tasks/${week.task_id}`, {
        method: 'PATCH',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
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
          item.task_id === data.task.id
            ? {
                ...item,
                completed: data.task.completed,
                time_spent_minutes: data.task.time_spent_minutes ?? item.time_spent_minutes ?? null,
                quiz_score: data.task.quiz_score ?? item.quiz_score ?? null,
              }
            : item
        )),
      } : current)
      setNextAction(data.next_action)
      if (data.skill_progression?.upgraded_skills?.length) {
        setFeedbackNote(`Skill feedback loop: ${data.skill_progression.upgraded_skills.join(', ')} promoted to practised. Your skill readiness will adapt on next match.`)
        // Re-fetch skill development so dashboard reflects promoted skills
        void loadSkillDevelopment()
      } else if (desiredCompletion && data.telemetry_summary) {
        const s = data.telemetry_summary
        if (s.avg_quiz_score !== null && s.avg_quiz_score < 60) {
          setFeedbackNote(`Learning pattern: quiz avg ${s.avg_quiz_score}% — next recommendations lean toward review.`)
        } else if (s.avg_time_spent_minutes !== null && s.avg_time_spent_minutes > 180) {
          setFeedbackNote(`Learning pattern: avg ${s.avg_time_spent_minutes} min per milestone — pacing adapted.`)
        }
      }
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
          <button type="button" className="btn-secondary" onClick={onBackToHome}>
            Back to Home
          </button>
        </div>
      </div>
    )
  }

  const completedCount = roadmap.weekly_plan.filter((week) => week.completed).length
  const telemetrySummary = (() => {
    const completed = roadmap.weekly_plan.filter((w) => w.completed)
    const times = completed.map((w) => w.time_spent_minutes).filter((v): v is number => typeof v === 'number')
    const quizzes = completed.map((w) => w.quiz_score).filter((v): v is number => typeof v === 'number')
    const avgTime = times.length ? Math.round(times.reduce((a, b) => a + b, 0) / times.length) : null
    const avgQuiz = quizzes.length ? Math.round(quizzes.reduce((a, b) => a + b, 0) / quizzes.length) : null
    const estimatedTotal = roadmap.weekly_plan.reduce((sum, w) => sum + w.estimated_effort_hours * 60, 0)
    const actualTotal = times.reduce((a, b) => a + b, 0)
    const paceRatio = times.length ? actualTotal / (completed.reduce((sum, w) => sum + w.estimated_effort_hours * 60, 0) || 1) : null
    let paceLabel = 'No telemetry yet'
    if (paceRatio !== null) {
      if (paceRatio < 0.8) paceLabel = 'Faster than estimated'
      else if (paceRatio > 1.3) paceLabel = 'Slower than estimated'
      else paceLabel = 'On pace'
    }
    return { completed, avgTime, avgQuiz, estimatedTotal, actualTotal, paceRatio, paceLabel, timesCount: times.length, quizCount: quizzes.length }
  })()

  return (
    <div className="dashboard-container">
      <nav className="assessment-top-nav">
        <button type="button" className="btn-back-link" onClick={onBackToHome}>
          ← Back to Home
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

      <ErrorBoundary>
        <section className="skill-development" aria-labelledby="skill-development-title">
        <div className="skill-development-header">
          <div>
            <p className="eyebrow">Skill development</p>
            <h2 id="skill-development-title">Where you stand for {roleTitle}</h2>
            <p className="skill-development-lede">
              Derived from your saved assessment (POST /match + GET /roadmaps/{roleId}) — no new backend call. Use the milestone checklist below to build evidence for the to-develop skills.
            </p>
          </div>
          <span className="skill-development-badge">From your match</span>
        </div>

        {skillLoading ? (
          <Skeleton lines={3} />
        ) : skillError ? (
          <p className="skill-development-error" role="alert">{skillError}</p>
        ) : !skillRec ? (
          <p className="skill-development-status">No match data found for this role yet. Complete the assessment and view results to see your skill breakdown.</p>
        ) : (
          <div className="skill-development-grid">
            <div className="skill-column skill-column--confirmed">
              <h3>Confirmed strengths</h3>
              <p className="skill-column-note">Checked — already at practised / project-ready for this path.</p>
              {skillRec.confirmed_skills.length === 0 ? (
                <p className="skill-empty">No confirmed skills yet. The milestones will build from foundations — every to-develop skill below is a starting point.</p>
              ) : (
                <ul className="skill-list skill-list--confirmed">
                  {skillRec.confirmed_skills.map((skill) => (
                    <li key={`confirmed-${skill}`}>
                      <span className="skill-check" aria-hidden="true">✓</span>
                      <span>{skill}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="skill-column skill-column--todo">
              <h3>To develop</h3>
              <p className="skill-column-note">Build these through the 5-week milestones.</p>
              {skillRec.missing_core_skills.length === 0 && skillRec.missing_supporting_skills.length === 0 ? (
                <p className="skill-empty">No missing skills — you are ready to focus on the portfolio evidence and milestone depth.</p>
              ) : (
                <div className="skill-todo-groups">
                  {skillRec.missing_core_skills.length > 0 && (
                    <div className="skill-todo-group">
                      <span className="skill-todo-label">Core — priority</span>
                      <ul className="skill-list skill-list--todo">
                        {skillRec.missing_core_skills.map((skill) => (
                          <li key={`core-${skill}`}>
                            <span className="skill-dot" aria-hidden="true">○</span>
                            <span>{skill}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {skillRec.missing_supporting_skills.length > 0 && (
                    <div className="skill-todo-group">
                      <span className="skill-todo-label">Supporting</span>
                      <ul className="skill-list skill-list--todo">
                        {skillRec.missing_supporting_skills.map((skill) => (
                          <li key={`supporting-${skill}`}>
                            <span className="skill-dot" aria-hidden="true">○</span>
                            <span>{skill}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
        </section>
      </ErrorBoundary>

      <ErrorBoundary>
        <section className="recommended-courses" aria-labelledby="recommended-courses-title">
        <div className="recommended-courses-header">
          <div>
            <p className="eyebrow">Recommended courses</p>
            <h2 id="recommended-courses-title">Courses for your gaps</h2>
            <p className="recommended-courses-lede">
              Curated from <code>GET /api/v1/catalog/courses</code> (grounded course catalog, {courses.length} courses). Filtered to your missing skills for {roleTitle} — prerequisites show the structured path.
            </p>
          </div>
          <span className="recommended-courses-badge">{coursesLoading ? '…' : `${courses.length} in catalog`}</span>
        </div>
        {skillLoading || coursesLoading ? (
          <Skeleton lines={2} />
        ) : !skillRec ? (
          <p className="recommended-courses-status">Complete the assessment to see course recommendations.</p>
        ) : (() => {
            const skillNameToId = (name: string): string => {
              const lower = name.toLowerCase().trim()
              if (skillNameToIdMap?.has(lower)) return skillNameToIdMap.get(lower)!
              const map: Record<string, string> = {
                'html and css': 'html-css',
                'javascript': 'javascript',
                'react': 'react',
                'git and github': 'git',
                'web accessibility': 'accessibility',
                'frontend testing': 'testing',
                'automated testing': 'testing',
                'python': 'python',
                'api design': 'api-design',
                'sql and relational data': 'sql',
                'authentication basics': 'authentication',
                'spreadsheets': 'spreadsheets',
                'data visualisation': 'data-visualization',
                'data visualization': 'data-visualization',
                'descriptive statistics': 'statistics',
                'data storytelling': 'data-storytelling',
                'linux and shell': 'linux',
                'cloud fundamentals': 'cloud-basics',
                'containers': 'containers',
                'ci/cd': 'ci-cd',
                'monitoring and observability': 'monitoring',
                'monitoring': 'monitoring',
              }
              if (map[lower]) return map[lower]
              return lower.replace(/\s+and\s+/g, ' ').replace(/\s+/g, '-').replace(/\//g, '-').replace(/--+/g, '-')
            }
            const missingIds = new Set([...skillRec.missing_core_skills, ...skillRec.missing_supporting_skills].map(skillNameToId))
            const confirmedIds = new Set(skillRec.confirmed_skills.map(skillNameToId))
            const recommended = courses.filter((c) => c.skill_ids.some((sid) => missingIds.has(sid)))
            const toShow = recommended.length ? recommended : confirmedIds.size ? courses.filter((c) => c.skill_ids.some((sid) => confirmedIds.has(sid))).slice(0, 3) : courses.slice(0, 3)
            if (toShow.length === 0) return <p className="recommended-courses-status">No courses match — your gaps are already covered by milestones.</p>
            return (
              <div className="courses-grid">
                {toShow.slice(0, 6).map((course) => {
                  const isPrereqMet = (prereq: string) => confirmedIds.has(prereq.toLowerCase())
                  return (
                    <article key={course.id} className="course-card">
                      <div className="course-card-header">
                        <span className="course-level">{course.level}</span>
                        <span className="course-duration">{course.duration_hours}h</span>
                      </div>
                      <h3>{course.title}</h3>
                      <p className="course-provider">{course.provider}</p>
                      <p className="course-desc">{course.description}</p>
                      <div className="course-skills">
                        {course.skill_ids.map((sid) => (
                          <span key={sid} className="course-skill-tag">{sid}</span>
                        ))}
                      </div>
                      {course.prerequisites.length > 0 && (
                        <div className="course-prereqs">
                          <span>Prerequisites → Course</span>
                          <div className="prereq-graph" aria-label={`Prerequisites for ${course.title}`}>
                            {course.prerequisites.map((pr) => (
                              <span key={pr} className="prereq-chain">
                                <span className={`prereq-node ${isPrereqMet(pr) ? 'prereq-node--met' : 'prereq-node--missing'}`}>
                                  {isPrereqMet(pr) ? '✓' : '○'} {pr}
                                </span>
                                <span className="prereq-arrow" aria-hidden="true">→</span>
                              </span>
                            ))}
                            <span className="prereq-node prereq-node--target">{course.skill_ids[0]}</span>
                          </div>
                          <ul style={{ display: 'none' }} aria-hidden="true">
                            {course.prerequisites.map((pr) => (
                              <li key={pr} className={isPrereqMet(pr) ? 'prereq-met' : 'prereq-missing'}>
                                {isPrereqMet(pr) ? '✓' : '○'} {pr}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <a href={course.url} target="_blank" rel="noreferrer" className="course-link">View course →</a>
                    </article>
                  )
                })}
              </div>
            )
          })()}
        </section>
      </ErrorBoundary>

      {feedbackNote && (
        <div className="dashboard-feedback" role="status" aria-live="polite">
          <span>↻ Feedback loop</span>
          <p>{feedbackNote}</p>
        </div>
      )}

      <ErrorBoundary>
        <section className="learning-patterns" aria-labelledby="learning-patterns-title">
        <div className="learning-patterns-header">
          <div>
            <p className="eyebrow">Learning patterns</p>
            <h2 id="learning-patterns-title">How you learn — telemetry</h2>
            <p className="learning-patterns-lede">
              Time on task and quiz scores adapt next recommendations. Completing milestones promotes their skills via the feedback loop; pace and quiz trends shape the next-action hint.
            </p>
          </div>
          <span className="learning-patterns-badge">{telemetrySummary.completed.length}/5 done</span>
        </div>
        <div className="learning-patterns-grid">
          <div className="learning-stat">
            <span className="learning-stat-label">Completion</span>
            <strong className="learning-stat-value">{Math.round((telemetrySummary.completed.length / 5) * 100)}%</strong>
            <span className="learning-stat-sub">{telemetrySummary.completed.length} of 5 milestones</span>
            <div className="learning-progress-track"><div className="learning-progress-fill" style={{ width: `${(telemetrySummary.completed.length / 5) * 100}%` }} /></div>
          </div>
          <div className="learning-stat">
            <span className="learning-stat-label">Avg time on task</span>
            <strong className="learning-stat-value">{telemetrySummary.avgTime !== null ? `${telemetrySummary.avgTime} min` : '—'}</strong>
            <span className="learning-stat-sub">{telemetrySummary.timesCount ? `${telemetrySummary.paceLabel} • ${telemetrySummary.actualTotal} min actual vs ${telemetrySummary.estimatedTotal} min estimated` : 'Log time when marking complete'}</span>
          </div>
          <div className="learning-stat">
            <span className="learning-stat-label">Avg quiz score</span>
            <strong className="learning-stat-value">{telemetrySummary.avgQuiz !== null ? `${telemetrySummary.avgQuiz}%` : '—'}</strong>
            <span className="learning-stat-sub">{telemetrySummary.quizCount ? `Across ${telemetrySummary.quizCount} completed` : 'Log a score per milestone'}</span>
          </div>
        </div>
        {telemetrySummary.avgQuiz !== null && telemetrySummary.avgQuiz < 60 && (
          <p className="learning-insight learning-insight--warn">Insight: quiz average below 60% — next milestones will lean toward review. Consider revisiting the skill-development gaps before advancing.</p>
        )}
        {telemetrySummary.paceRatio !== null && telemetrySummary.paceRatio > 1.3 && (
          <p className="learning-insight">Insight: slower than estimated — try 30-min focus blocks or reducing weekly hours to stay sustainable.</p>
        )}
        {telemetrySummary.paceRatio !== null && telemetrySummary.paceRatio < 0.8 && (
          <p className="learning-insight">Insight: faster than estimated — you can take on stretch content or move up the next portfolio slice.</p>
        )}
        </section>
      </ErrorBoundary>

      {(() => {
        if (telemetrySummary.avgQuiz === null || telemetrySummary.avgQuiz >= 60) return null
        const lowest = [...roadmap.weekly_plan]
          .filter((w) => typeof w.quiz_score === 'number')
          .sort((a, b) => (a.quiz_score ?? 100) - (b.quiz_score ?? 100))[0]
        const next = roadmap.weekly_plan.find((w) => !w.completed)
        return (
          <section className="adaptive-order" aria-labelledby="adaptive-order-title">
            <p className="eyebrow">Adaptive roadmap</p>
            <h3 id="adaptive-order-title">Suggested order adjustment</h3>
            <p>
              Your quiz average is {telemetrySummary.avgQuiz}% — lower than the 60% threshold. {lowest ? `Consider reviewing Week ${lowest.week}: ${lowest.title} (quiz ${lowest.quiz_score}%)` : 'Review recent milestones'} before advancing
              {next ? ` to Week ${next.week}: ${next.title}` : ''}. This keeps prerequisites solid while you build confidence.
            </p>
          </section>
        )
      })()}

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

              <div className="milestone-telemetry">
                <div className="telemetry-inputs">
                  <label>
                    <span>Time spent (min)</span>
                    <input
                      type="number"
                      min={0}
                      max={10080}
                      placeholder={String(week.estimated_effort_hours * 60)}
                      value={telemetryDraft[week.milestone_id]?.time ?? ''}
                      onChange={(e) =>
                        setTelemetryDraft((prev) => ({
                          ...prev,
                          [week.milestone_id]: { time: e.target.value, quiz: prev[week.milestone_id]?.quiz ?? '' },
                        }))
                      }
                      disabled={!!week.completed}
                      aria-label={`Time spent for ${week.title} in minutes`}
                    />
                  </label>
                  <label>
                    <span>Quiz %</span>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      placeholder="—"
                      value={telemetryDraft[week.milestone_id]?.quiz ?? ''}
                      onChange={(e) =>
                        setTelemetryDraft((prev) => ({
                          ...prev,
                          [week.milestone_id]: { time: prev[week.milestone_id]?.time ?? '', quiz: e.target.value },
                        }))
                      }
                      disabled={!!week.completed}
                      aria-label={`Quiz score for ${week.title}`}
                    />
                  </label>
                </div>
                {week.completed && (week.time_spent_minutes != null || week.quiz_score != null) && (
                  <p className="telemetry-logged">
                    Logged: {week.time_spent_minutes != null ? `${week.time_spent_minutes} min` : '—'} {week.time_spent_minutes != null ? `vs ${week.estimated_effort_hours * 60} min est.` : ''} {week.quiz_score != null ? `• Quiz ${week.quiz_score}%` : ''}
                  </p>
                )}
                {week.completed && week.time_spent_minutes == null && week.quiz_score == null && (
                  <p className="telemetry-hint">No telemetry logged for this milestone — add time/quiz before next completion to refine adaptations.</p>
                )}
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
