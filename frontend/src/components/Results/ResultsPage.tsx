import { useEffect, useState } from 'react'
import { config } from '../../lib/config'
import { supabase } from '../../lib/supabase'

/* ------------------------------------------------------------------ */
/*  Types matching backend MatchResponse                               */
/* ------------------------------------------------------------------ */

interface ScoreBreakdown {
  interest_alignment: number
  skill_readiness: number
  work_style_alignment: number
}

export interface CareerRecommendation {
  rank: number
  role_id: string
  role_title: string
  pathfinder_fit_score: number
  score_breakdown: ScoreBreakdown
  confirmed_skills: string[]
  missing_core_skills: string[]
  missing_supporting_skills: string[]
}

export interface MatchResponse {
  normalized_interest_profile: Record<string, number>
  normalized_work_style_profile: Record<string, number>
  recommendations: CareerRecommendation[]
}

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */

interface ResultsPageProps {
  /** Pre-fetched match data — if provided, skips the /match call. */
  matchData?: MatchResponse | null
  onBackToHome?: () => void
  onEditAssessment?: () => void
  onExplorePath?: (recommendation: CareerRecommendation) => void
}

/* ------------------------------------------------------------------ */
/*  Role icon mapping                                                  */
/* ------------------------------------------------------------------ */

const ROLE_ICONS: Record<string, string> = {
  'frontend-developer': '🎨',
  'backend-developer': '⚙️',
  'data-analyst': '📊',
  'cloud-devops-engineer': '☁️',
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ResultsPage({ matchData: preloaded, onBackToHome, onEditAssessment, onExplorePath }: ResultsPageProps) {
  const [matchData, setMatchData] = useState<MatchResponse | null>(preloaded ?? null)
  const [isLoading, setIsLoading] = useState(!preloaded)
  const [error, setError] = useState<string | null>(null)

  const fetchMatch = async () => {
    try {
      setIsLoading(true)
      setError(null)

      if (!supabase) {
        throw new Error('Supabase client is not configured.')
      }

      const { data: sessionData, error: sessionError } = await supabase.auth.getSession()
      if (sessionError) throw new Error(`Auth error: ${sessionError.message}`)

      const token = sessionData?.session?.access_token
      if (!token) throw new Error('You must be signed in to view results.')

      const res = await fetch(`${config.apiUrl}/api/v1/match`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      })

      if (!res.ok) {
        let detail = `Matching failed (${res.status})`
        try {
          const body = await res.json()
          if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
        } catch { /* ignore */ }
        throw new Error(detail)
      }

      const data: MatchResponse = await res.json()
      setMatchData(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error while computing matches.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!preloaded) {
      fetchMatch()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /* ----- Loading State ----- */
  if (isLoading) {
    return (
      <div className="assessment-loading-card" role="status" aria-live="polite">
        <div className="loading-spinner" />
        <h3>Computing Your Career Matches…</h3>
        <p className="loading-subtext">
          Analyzing your interests, skills, and work style against four focused career paths.
        </p>
      </div>
    )
  }

  /* ----- Error State ----- */
  if (error || !matchData) {
    return (
      <div className="assessment-error-card" role="alert">
        <span className="error-icon">✕</span>
        <h3>Unable to Compute Matches</h3>
        <p className="error-message">{error ?? 'Match data could not be retrieved.'}</p>
        <div className="error-actions">
          <button type="button" className="btn-primary" onClick={fetchMatch}>
            Retry
          </button>
          {onBackToHome && (
            <button type="button" className="btn-secondary" onClick={onBackToHome}>
              Back to Overview
            </button>
          )}
        </div>
      </div>
    )
  }

  /* ----- Results ----- */
  const { recommendations } = matchData
  const topRec = recommendations[0]

  return (
    <div className="results-container">
      <nav className="assessment-top-nav">
        {onBackToHome ? (
          <button type="button" className="btn-back-link" onClick={onBackToHome}>
            ← Back to Overview
          </button>
        ) : <div />}
        <span className="brand-badge">Pathfinder • Results</span>
      </nav>

      {/* Hero summary */}
      <header className="results-hero">
        <span className="eyebrow">YOUR PATHFINDER RESULTS</span>
        <h1 className="results-headline">
          Top match: <strong>{topRec.role_title}</strong>
        </h1>
        <p className="results-lede">
          Based on your interest profile, current skills, and work-style preferences,
          here's how each career path aligns with you.
        </p>
      </header>

      {/* Cards grid */}
      <div className="results-grid">
        {recommendations.map((rec) => (
          <article
            key={rec.role_id}
            className={`results-card ${rec.rank === 1 ? 'results-card--top' : ''}`}
            id={`result-${rec.role_id}`}
          >
            {/* Rank + role header */}
            <div className="results-card-header">
              <div className="results-rank-badge">
                {rec.rank === 1 ? '★' : `#${rec.rank}`}
              </div>
              <div>
                <span className="results-role-icon">{ROLE_ICONS[rec.role_id] ?? '💻'}</span>
                <h2 className="results-role-title">{rec.role_title}</h2>
              </div>
            </div>

            {/* Fit score */}
            <div className="results-score-block">
              <span className="results-fit-number">
                {Math.round(rec.pathfinder_fit_score)}
              </span>
              <span className="results-fit-label">fit score</span>
            </div>

            {/* Breakdown bars */}
            <div className="results-breakdown">
              <BreakdownBar
                label="Interest alignment"
                value={rec.score_breakdown.interest_alignment}
                weight="55%"
              />
              <BreakdownBar
                label="Skill readiness"
                value={rec.score_breakdown.skill_readiness}
                weight="35%"
              />
              <BreakdownBar
                label="Work-style fit"
                value={rec.score_breakdown.work_style_alignment}
                weight="10%"
              />
            </div>

            {/* Skill gaps — top 2 missing core skills */}
            {rec.missing_core_skills.length > 0 && (
              <div className="results-gaps">
                <span className="results-gaps-label">Biggest skill gaps</span>
                <ul className="results-gaps-list">
                  {rec.missing_core_skills.slice(0, 2).map((skill) => (
                    <li key={skill}>{skill}</li>
                  ))}
                </ul>
              </div>
            )}

            {onExplorePath && (
              <button
                type="button"
                className="results-explore-button"
                onClick={() => onExplorePath(rec)}
              >
                Explore path →
              </button>
            )}
          </article>
        ))}
      </div>

      {/* Actions */}
      <footer className="results-footer">
        {onEditAssessment && (
          <button type="button" className="btn-secondary" onClick={onEditAssessment}>
            Edit Assessment Responses
          </button>
        )}
        {onBackToHome && (
          <button type="button" className="btn-primary" onClick={onBackToHome}>
            Return to Overview
          </button>
        )}
      </footer>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Breakdown bar sub-component                                        */
/* ------------------------------------------------------------------ */

function BreakdownBar({ label, value, weight }: { label: string; value: number; weight: string }) {
  const rounded = Math.round(value)
  return (
    <div className="breakdown-row">
      <div className="breakdown-meta">
        <span className="breakdown-label">{label}</span>
        <span className="breakdown-weight">{weight}</span>
      </div>
      <div className="breakdown-track">
        <div
          className="breakdown-fill"
          style={{ width: `${Math.min(100, rounded)}%` }}
        />
      </div>
      <span className="breakdown-value">{rounded}</span>
    </div>
  )
}
