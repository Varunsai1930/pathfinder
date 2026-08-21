import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  fetchCatalogData,
  type AppCatalogBundle,
} from '../../data/assessmentCatalog'
import { config } from '../../lib/config'
import { supabase } from '../../lib/supabase'
import type {
  AssessmentPayload,
  AssessmentState,
  CareerCertainty,
  ConstraintsState,
  IntakeResponse,
  SkillConfidence,
  WorkStyleResponses,
} from '../../types/assessment'
import type { MatchResponse } from '../Results/ResultsPage'
import { ProgressBar } from './ProgressBar'
import { SectionConstraints } from './SectionConstraints'
import { SectionGoal } from './SectionGoal'
import { SectionInterests } from './SectionInterests'
import { SectionSkills } from './SectionSkills'

interface AssessmentPageProps {
  onBackToHome?: () => void
}

const STEP_TITLES = ['Your Goal', 'Interest Exploration', 'Technical Skills', 'Work Style & Constraints']
const MIN_GOAL_LENGTH = 10
const TIMELINE_OPTIONS = [8, 12, 24, 36]

function snapTimelineToOfferedOptions(weeks: number): number {
  return TIMELINE_OPTIONS.reduce((best, option) =>
    Math.abs(option - weeks) < Math.abs(best - weeks) ? option : best
  , TIMELINE_OPTIONS[0])
}

const INITIAL_STATE: AssessmentState = {
  interest_responses: {},
  skill_confidence: {},
  work_style_responses: {
    analytical: undefined,
    creative: undefined,
    collaborative: undefined,
    structured: undefined,
    systems_oriented: undefined,
  },
  constraints: {
    hours_per_week: '',
    target_timeline_weeks: '',
    career_certainty: '',
  },
}

export function AssessmentPage({ onBackToHome }: AssessmentPageProps) {
  const navigate = useNavigate()
  const [catalogBundle, setCatalogBundle] = useState<AppCatalogBundle | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [currentStep, setCurrentStep] = useState<number>(1)
  const [assessmentState, setAssessmentState] = useState<AssessmentState>(INITIAL_STATE)
  const [missingFieldIds, setMissingFieldIds] = useState<string[]>([])
  const [validationError, setValidationError] = useState<string | null>(null)

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [matchLoading, setMatchLoading] = useState(false)
  const [matchError, setMatchError] = useState<string | null>(null)

  const [goalText, setGoalText] = useState('')
  const [intakeLoading, setIntakeLoading] = useState(false)
  const [intakeError, setIntakeError] = useState<string | null>(null)
  const [intakeNotice, setIntakeNotice] = useState<string | null>(null)

  const loadData = async () => {
    try {
      setIsLoading(true)
      setLoadError(null)
      const data = await fetchCatalogData()
      setCatalogBundle(data)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown network error'
      setLoadError(message)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // Handlers for state updates
  const handleInterestChange = (questionId: string, value: number) => {
    setAssessmentState((prev) => ({
      ...prev,
      interest_responses: {
        ...prev.interest_responses,
        [questionId]: value,
      },
    }))
    setMissingFieldIds((prev) => prev.filter((id) => id !== questionId))
    if (validationError) setValidationError(null)
    if (submitError) setSubmitError(null)
  }

  const handleSkillChange = (skillId: string, value: SkillConfidence) => {
    setAssessmentState((prev) => ({
      ...prev,
      skill_confidence: {
        ...prev.skill_confidence,
        [skillId]: value,
      },
    }))
    setMissingFieldIds((prev) => prev.filter((id) => id !== skillId))
    if (validationError) setValidationError(null)
    if (submitError) setSubmitError(null)
  }

  const handleBulkSetNone = () => {
    if (!catalogBundle) return
    setAssessmentState((prev) => {
      const updated = { ...prev.skill_confidence }
      for (const skill of catalogBundle.assessment.skills) {
        if (!updated[skill.id]) {
          updated[skill.id] = 'none'
        }
      }
      return { ...prev, skill_confidence: updated }
    })
    setMissingFieldIds([])
    if (validationError) setValidationError(null)
    if (submitError) setSubmitError(null)
  }

  const handleWorkStyleChange = (field: keyof WorkStyleResponses, value: number) => {
    setAssessmentState((prev) => ({
      ...prev,
      work_style_responses: {
        ...prev.work_style_responses,
        [field]: value,
      },
    }))
    setMissingFieldIds((prev) => prev.filter((id) => id !== `work_style.${field}`))
    if (validationError) setValidationError(null)
    if (submitError) setSubmitError(null)
  }

  const handleConstraintsChange = <K extends keyof ConstraintsState>(
    field: K,
    value: ConstraintsState[K]
  ) => {
    setAssessmentState((prev) => ({
      ...prev,
      constraints: {
        ...prev.constraints,
        [field]: value,
      },
    }))
    setMissingFieldIds((prev) => prev.filter((id) => id !== field))
    if (validationError) setValidationError(null)
    if (submitError) setSubmitError(null)
  }

  // Step validation
  const validateCurrentStep = (step: number): boolean => {
    if (!catalogBundle) return false
    const missing: string[] = []

    if (step === 2) {
      for (const q of catalogBundle.assessment.interest_questions) {
        if (!assessmentState.interest_responses[q.id]) {
          missing.push(q.id)
        }
      }
      if (missing.length > 0) {
        setMissingFieldIds(missing)
        setValidationError(
          `Please answer all 18 interest questions before continuing (${missing.length} remaining).`
        )
        scrollToFirstError(missing[0], 'question-')
        return false
      }
    }

    if (step === 3) {
      for (const s of catalogBundle.assessment.skills) {
        if (!assessmentState.skill_confidence[s.id]) {
          missing.push(s.id)
        }
      }
      if (missing.length > 0) {
        setMissingFieldIds(missing)
        setValidationError(
          `Please rate all 19 technical skills (${missing.length} unrated). Tip: use "Set unrated to 'None'" if applicable.`
        )
        scrollToFirstError(missing[0], 'skill-')
        return false
      }
    }

    if (step === 4) {
      const wsKeys: Array<keyof WorkStyleResponses> = [
        'analytical',
        'creative',
        'collaborative',
        'structured',
        'systems_oriented',
      ]
      for (const key of wsKeys) {
        if (assessmentState.work_style_responses[key] === undefined) {
          missing.push(`work_style.${key}`)
        }
      }
      if (
        assessmentState.constraints.hours_per_week === '' ||
        Number(assessmentState.constraints.hours_per_week) < 1
      ) {
        missing.push('hours_per_week')
      }
      if (
        assessmentState.constraints.target_timeline_weeks === '' ||
        Number(assessmentState.constraints.target_timeline_weeks) < 1
      ) {
        missing.push('target_timeline_weeks')
      }
      if (!assessmentState.constraints.career_certainty) {
        missing.push('career_certainty')
      }

      if (missing.length > 0) {
        setMissingFieldIds(missing)
        setValidationError(
          `Please complete all work-style and planning constraint fields (${missing.length} incomplete).`
        )
        scrollToFirstError(missing[0].replace('.', '-'), 'field-')
        return false
      }
    }

    setMissingFieldIds([])
    setValidationError(null)
    return true
  }

  const scrollToFirstError = (id: string, prefix = '') => {
    setTimeout(() => {
      const el = document.getElementById(`${prefix}${id}`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }, 50)
  }

  const handleNext = () => {
    if (validateCurrentStep(currentStep)) {
      setCurrentStep((prev) => Math.min(STEP_TITLES.length, prev + 1))
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const handleBack = () => {
    setValidationError(null)
    setSubmitError(null)
    setMissingFieldIds([])
    setCurrentStep((prev) => Math.max(1, prev - 1))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleGoalChange = (value: string) => {
    setGoalText(value)
    if (intakeError) setIntakeError(null)
  }

  const handleSkipIntake = () => {
    setIntakeError(null)
    setCurrentStep(2)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleIntakeSubmit = async () => {
    if (goalText.trim().length < MIN_GOAL_LENGTH) {
      setIntakeError('Tell us a little more — at least 10 characters so the draft is useful.')
      return
    }

    try {
      setIntakeLoading(true)
      setIntakeError(null)

      if (!supabase) {
        throw new Error('Supabase client is not configured. Please check your application environment variables.')
      }

      const { data: sessionData, error: sessionError } = await supabase.auth.getSession()
      if (sessionError) {
        throw new Error(`Authentication session error: ${sessionError.message}`)
      }

      const token = sessionData?.session?.access_token
      if (!token) {
        throw new Error('You must be signed in to pre-fill your assessment. Please sign in first, then try again.')
      }

      const res = await fetch(`${config.apiUrl}/api/v1/intake`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ goal_text: goalText.trim() }),
      })

      if (!res.ok) {
        let errorDetail = `Failed to generate a draft (${res.status} ${res.statusText})`
        try {
          const errJson = await res.json()
          if (errJson?.detail) {
            errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail)
          }
        } catch {
          // ignore json parse error
        }
        throw new Error(errorDetail)
      }

      const data: IntakeResponse = await res.json()

      setAssessmentState((prev) => {
        const skillConfidence = { ...prev.skill_confidence, ...data.skill_suggestions }
        const constraints = { ...prev.constraints }
        if (data.hours_per_week_suggestion) {
          constraints.hours_per_week = data.hours_per_week_suggestion
        }
        if (data.timeline_weeks_suggestion) {
          constraints.target_timeline_weeks = snapTimelineToOfferedOptions(data.timeline_weeks_suggestion)
        }
        if (data.career_certainty_suggestion) {
          constraints.career_certainty = data.career_certainty_suggestion
        }
        return {
          ...prev,
          interest_responses:
            Object.keys(data.interest_suggestions).length > 0
              ? { ...data.interest_suggestions }
              : prev.interest_responses,
          skill_confidence: skillConfidence,
          constraints,
        }
      })

      setIntakeNotice(
        data.generation_mode === 'llm'
          ? 'We drafted your assessment from your goal. Review and edit anything — you stay in control.'
          : "We couldn't generate a draft just now, so the assessment starts empty. Fill it in as normal."
      )
      setCurrentStep(2)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown network error while drafting your assessment.'
      setIntakeError(message)
    } finally {
      setIntakeLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!validateCurrentStep(4)) return

    const payload: AssessmentPayload = {
      interest_responses: assessmentState.interest_responses,
      skill_confidence: assessmentState.skill_confidence,
      work_style_responses: {
        analytical: Number(assessmentState.work_style_responses.analytical),
        creative: Number(assessmentState.work_style_responses.creative),
        collaborative: Number(assessmentState.work_style_responses.collaborative),
        structured: Number(assessmentState.work_style_responses.structured),
        systems_oriented: Number(assessmentState.work_style_responses.systems_oriented),
      },
      constraints: {
        hours_per_week: Number(assessmentState.constraints.hours_per_week),
        target_timeline_weeks: Number(assessmentState.constraints.target_timeline_weeks),
        career_certainty: assessmentState.constraints.career_certainty as CareerCertainty,
      },
    }

    try {
      setIsSubmitting(true)
      setSubmitError(null)

      if (!supabase) {
        throw new Error('Supabase client is not configured. Please check your application environment variables.')
      }

      const { data: sessionData, error: sessionError } = await supabase.auth.getSession()
      if (sessionError) {
        throw new Error(`Authentication session error: ${sessionError.message}`)
      }

      const token = sessionData?.session?.access_token
      if (!token) {
        throw new Error(
          'You must be signed in to save your assessment profile. Please enter your email on the overview page to sign in, then resubmit.'
        )
      }

      const res = await fetch(`${config.apiUrl}/api/v1/profile`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        let errorDetail = `Failed to save profile (${res.status} ${res.statusText})`
        try {
          const errJson = await res.json()
          if (errJson?.detail) {
            errorDetail = errJson.detail
          }
        } catch {
          // ignore json parse error
        }
        throw new Error(errorDetail)
      }

      await res.json()

      // Profile saved — now compute matches
      setMatchLoading(true)
      window.scrollTo({ top: 0, behavior: 'smooth' })

      const matchRes = await fetch(`${config.apiUrl}/api/v1/match`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      })

      if (!matchRes.ok) {
        let matchDetail = `Matching failed (${matchRes.status})`
        try {
          const errBody = await matchRes.json()
          if (errBody?.detail) matchDetail = typeof errBody.detail === 'string' ? errBody.detail : JSON.stringify(errBody.detail)
        } catch { /* ignore */ }
        setMatchError(matchDetail)
        setMatchLoading(false)
        return
      }

      const matchData: MatchResponse = await matchRes.json()
      setMatchLoading(false)
      navigate('/results', { state: { matchData } })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown network error while saving profile.'
      setSubmitError(message)
      setMatchLoading(false)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Loading State
  if (isLoading) {
    return (
      <div className="assessment-loading-card" role="status" aria-live="polite">
        <div className="loading-spinner" />
        <h3>Loading Career Assessment Catalog…</h3>
        <p className="loading-subtext">Fetching latest verified questions and skill taxonomy from API.</p>
      </div>
    )
  }

  // Error State
  if (loadError || !catalogBundle) {
    return (
      <div className="assessment-error-card" role="alert">
        <span className="error-icon">✕</span>
        <h3>Failed to Load Assessment Data</h3>
        <p className="error-message">{loadError ?? 'Catalog data could not be retrieved.'}</p>
        <div className="error-actions">
          <button type="button" className="btn-primary" onClick={loadData}>
            Retry Connection
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

  // Calculate answered counts for stats
  const answeredInterestsCount = Object.keys(assessmentState.interest_responses).length
  const answeredSkillsCount = Object.keys(assessmentState.skill_confidence).length
  const answeredConstraintsCount =
    Object.values(assessmentState.work_style_responses).filter((v) => v !== undefined).length +
    (assessmentState.constraints.hours_per_week !== '' ? 1 : 0) +
    (assessmentState.constraints.target_timeline_weeks !== '' ? 1 : 0) +
    (assessmentState.constraints.career_certainty !== '' ? 1 : 0)

  let completedCount = answeredInterestsCount
  let totalCount = catalogBundle.assessment.interest_questions.length
  if (currentStep === 3) {
    completedCount = answeredSkillsCount
    totalCount = catalogBundle.assessment.skills.length
  } else if (currentStep === 4) {
    completedCount = answeredConstraintsCount
    totalCount = 8
  }

  // Match loading state
  if (matchLoading) {
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

  // Match error state
  if (matchError) {
    return (
      <div className="assessment-error-card" role="alert">
        <span className="error-icon">✕</span>
        <h3>Unable to Compute Matches</h3>
        <p className="error-message">{matchError}</p>
        <div className="error-actions">
          <button type="button" className="btn-primary" onClick={() => { setMatchError(null); handleSubmit() }}>
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

  return (
    <div className="assessment-container">
      {onBackToHome && (
        <nav className="assessment-top-nav">
          <button type="button" className="btn-back-link" onClick={onBackToHome}>
            ← Back to Overview
          </button>
          <span className="brand-badge">Pathfinder • Assessment</span>
        </nav>
      )}

      <ProgressBar
        currentStep={currentStep}
        totalSteps={STEP_TITLES.length}
        stepTitles={STEP_TITLES}
        completedCount={currentStep >= 2 ? completedCount : undefined}
        totalCount={currentStep >= 2 ? totalCount : undefined}
      />

      {intakeNotice && currentStep >= 2 && (
        <div className="intake-notice" role="status">
          <span className="intake-notice-icon">✎</span>
          <span className="intake-notice-text">{intakeNotice}</span>
          <button
            type="button"
            className="intake-notice-dismiss"
            onClick={() => setIntakeNotice(null)}
            aria-label="Dismiss pre-fill notice"
          >
            Dismiss
          </button>
        </div>
      )}

      {validationError && (
        <div className="validation-banner" role="alert">
          <span className="validation-icon">⚠</span>
          <span className="validation-text">{validationError}</span>
        </div>
      )}

      {submitError && (
        <div className="validation-banner" role="alert">
          <span className="validation-icon">✕</span>
          <span className="validation-text">{submitError}</span>
        </div>
      )}

      <main className="assessment-body">
        {currentStep === 1 && (
          <SectionGoal
            goalText={goalText}
            onGoalChange={handleGoalChange}
            onPrefill={handleIntakeSubmit}
            onSkip={handleSkipIntake}
            isLoading={intakeLoading}
            error={intakeError}
          />
        )}

        {currentStep === 2 && (
          <SectionInterests
            catalog={catalogBundle.assessment}
            responses={assessmentState.interest_responses}
            onChange={handleInterestChange}
            missingQuestionIds={missingFieldIds}
          />
        )}

        {currentStep === 3 && (
          <SectionSkills
            skills={catalogBundle.assessment.skills}
            skillConfidence={assessmentState.skill_confidence}
            onChange={handleSkillChange}
            onBulkSetNone={handleBulkSetNone}
            missingSkillIds={missingFieldIds}
          />
        )}

        {currentStep === 4 && (
          <SectionConstraints
            workStyleResponses={assessmentState.work_style_responses}
            constraints={assessmentState.constraints}
            onWorkStyleChange={handleWorkStyleChange}
            onConstraintsChange={handleConstraintsChange}
            missingFields={missingFieldIds}
          />
        )}
      </main>

      {currentStep > 1 && (
        <footer className="assessment-footer-actions">
          <button type="button" className="btn-secondary btn-nav" onClick={handleBack} disabled={isSubmitting}>
            ← Back to {STEP_TITLES[currentStep - 2]}
          </button>

          {currentStep < STEP_TITLES.length ? (
            <button type="button" className="btn-primary btn-nav" onClick={handleNext}>
              Continue to {STEP_TITLES[currentStep]} →
            </button>
          ) : (
            <button
              type="button"
              className="btn-primary btn-nav btn-submit"
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Saving Profile…' : 'Submit assessment →'}
            </button>
          )}
        </footer>
      )}
    </div>
  )
}
