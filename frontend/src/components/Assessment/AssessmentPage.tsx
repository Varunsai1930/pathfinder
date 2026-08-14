import { useEffect, useState } from 'react'
import {
  fetchCatalogData,
  type AppCatalogBundle,
} from '../../data/assessmentCatalog'
import type {
  AssessmentPayload,
  AssessmentState,
  CareerCertainty,
  ConstraintsState,
  SkillConfidence,
  WorkStyleResponses,
} from '../../types/assessment'
import { ProgressBar } from './ProgressBar'
import { SectionConstraints } from './SectionConstraints'
import { SectionInterests } from './SectionInterests'
import { SectionSkills } from './SectionSkills'

interface AssessmentPageProps {
  onBackToHome?: () => void
}

const STEP_TITLES = ['Interest Exploration', 'Technical Skills', 'Work Style & Constraints']

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
  const [catalogBundle, setCatalogBundle] = useState<AppCatalogBundle | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [currentStep, setCurrentStep] = useState<number>(1)
  const [assessmentState, setAssessmentState] = useState<AssessmentState>(INITIAL_STATE)
  const [missingFieldIds, setMissingFieldIds] = useState<string[]>([])
  const [validationError, setValidationError] = useState<string | null>(null)
  const [submittedPayload, setSubmittedPayload] = useState<AssessmentPayload | null>(null)

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
  }

  // Step validation
  const validateCurrentStep = (step: number): boolean => {
    if (!catalogBundle) return false
    const missing: string[] = []

    if (step === 1) {
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

    if (step === 2) {
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

    if (step === 3) {
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
      setCurrentStep((prev) => Math.min(3, prev + 1))
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const handleBack = () => {
    setValidationError(null)
    setMissingFieldIds([])
    setCurrentStep((prev) => Math.max(1, prev - 1))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleSubmit = () => {
    if (!validateCurrentStep(3)) return

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

    console.log('Assessment payload:', payload)
    setSubmittedPayload(payload)
    window.scrollTo({ top: 0, behavior: 'smooth' })
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
  if (currentStep === 2) {
    completedCount = answeredSkillsCount
    totalCount = catalogBundle.assessment.skills.length
  } else if (currentStep === 3) {
    completedCount = answeredConstraintsCount
    totalCount = 8
  }

  // Submitted view confirmation
  if (submittedPayload) {
    return (
      <div className="assessment-submitted-container" role="status" aria-live="polite">
        <div className="submitted-card">
          <span className="eyebrow">STEP COMPLETE</span>
          <h2>Assessment Ready for Matching</h2>
          <p className="submitted-lede">
            All 3 sections completed. The assembled payload was successfully logged to the console in the exact shape expected by the backend.
          </p>

          <div className="payload-preview-box">
            <div className="payload-preview-header">
              <span className="dm-mono-tag">CONSOLE LOGGED PAYLOAD</span>
              <span className="status-badge">Valid MatchProfile</span>
            </div>
            <pre className="payload-code">
              {JSON.stringify(submittedPayload, null, 2)}
            </pre>
          </div>

          <div className="submitted-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setSubmittedPayload(null)
                setCurrentStep(1)
              }}
            >
              Edit Assessment Responses
            </button>
            {onBackToHome && (
              <button type="button" className="btn-primary" onClick={onBackToHome}>
                Return to Overview
              </button>
            )}
          </div>
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
        totalSteps={3}
        stepTitles={STEP_TITLES}
        completedCount={completedCount}
        totalCount={totalCount}
      />

      {validationError && (
        <div className="validation-banner" role="alert">
          <span className="validation-icon">⚠</span>
          <span className="validation-text">{validationError}</span>
        </div>
      )}

      <main className="assessment-body">
        {currentStep === 1 && (
          <SectionInterests
            catalog={catalogBundle.assessment}
            responses={assessmentState.interest_responses}
            onChange={handleInterestChange}
            missingQuestionIds={missingFieldIds}
          />
        )}

        {currentStep === 2 && (
          <SectionSkills
            skills={catalogBundle.assessment.skills}
            skillConfidence={assessmentState.skill_confidence}
            onChange={handleSkillChange}
            onBulkSetNone={handleBulkSetNone}
            missingSkillIds={missingFieldIds}
          />
        )}

        {currentStep === 3 && (
          <SectionConstraints
            workStyleResponses={assessmentState.work_style_responses}
            constraints={assessmentState.constraints}
            onWorkStyleChange={handleWorkStyleChange}
            onConstraintsChange={handleConstraintsChange}
            missingFields={missingFieldIds}
          />
        )}
      </main>

      <footer className="assessment-footer-actions">
        {currentStep > 1 ? (
          <button type="button" className="btn-secondary btn-nav" onClick={handleBack}>
            ← Back to {STEP_TITLES[currentStep - 2]}
          </button>
        ) : (
          <div />
        )}

        {currentStep < 3 ? (
          <button type="button" className="btn-primary btn-nav" onClick={handleNext}>
            Continue to {STEP_TITLES[currentStep]} →
          </button>
        ) : (
          <button type="button" className="btn-primary btn-nav btn-submit" onClick={handleSubmit}>
            Submit assessment →
          </button>
        )}
      </footer>
    </div>
  )
}
