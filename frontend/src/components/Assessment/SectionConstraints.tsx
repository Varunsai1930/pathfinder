import type { CareerCertainty, ConstraintsState, WorkStyleResponses } from '../../types/assessment'

interface SectionConstraintsProps {
  workStyleResponses: Record<keyof WorkStyleResponses, number | undefined>
  constraints: ConstraintsState
  onWorkStyleChange: (field: keyof WorkStyleResponses, value: number) => void
  onConstraintsChange: <K extends keyof ConstraintsState>(
    field: K,
    value: ConstraintsState[K]
  ) => void
  missingFields: string[]
}

const WORK_STYLE_FIELDS: Array<{
  key: keyof WorkStyleResponses
  title: string
  description: string
  lowLabel: string
  highLabel: string
}> = [
  {
    key: 'analytical',
    title: 'Analytical Rigor',
    description: 'Decomposing complex problems with quantitative evidence, metrics, and structured logic.',
    lowLabel: 'Intuitive / Exploratory',
    highLabel: 'Deep Data & Proof',
  },
  {
    key: 'creative',
    title: 'Creative Problem Solving',
    description: 'Inventing new visual presentations, novel workflows, and imaginative user solutions.',
    lowLabel: 'Follow Established Patterns',
    highLabel: 'Invent New Solutions',
  },
  {
    key: 'collaborative',
    title: 'Collaborative Interaction',
    description: 'Working in cross-functional squads with frequent stakeholder communication and feedback.',
    lowLabel: 'Autonomous / Solo Focus',
    highLabel: 'High Squad Interaction',
  },
  {
    key: 'structured',
    title: 'Structured Process & Standards',
    description: 'Following disciplined protocols, rigorous test routines, and strict architectural conventions.',
    lowLabel: 'Rapid & Flexible',
    highLabel: 'Strict & Methodical',
  },
  {
    key: 'systems_oriented',
    title: 'Systems & Architecture Thinking',
    description: 'Understanding multi-tier interactions, dependency graphs, distributed pipelines, and reliability.',
    lowLabel: 'Single-Module Focus',
    highLabel: 'Holistic Architecture',
  },
]

const TIMELINE_OPTIONS: Array<{ value: number; label: string; subtext: string }> = [
  { value: 8, label: '8 Weeks', subtext: 'Intensive (~2 months sprint)' },
  { value: 12, label: '12 Weeks', subtext: 'Standard (~3 months roadmap)' },
  { value: 24, label: '24 Weeks', subtext: 'Semester (~6 months pace)' },
  { value: 36, label: '36 Weeks', subtext: 'Comprehensive (~9 months plan)' },
]

const CERTAINTY_OPTIONS: Array<{ value: CareerCertainty; title: string; desc: string }> = [
  {
    value: 'exploring',
    title: 'Exploring Options',
    desc: 'Open to discovering which tech role aligns best with my natural strengths.',
  },
  {
    value: 'deciding',
    title: 'Deciding Between 2–3 Paths',
    desc: 'Have a few favorite directions in mind and want data-driven comparison.',
  },
  {
    value: 'committed',
    title: 'Committed to a Role',
    desc: 'Clear on my target path and looking for a structured weekly execution plan.',
  },
]

const QUICK_HOURS = [8, 12, 15, 20, 30]

export function SectionConstraints({
  workStyleResponses,
  constraints,
  onWorkStyleChange,
  onConstraintsChange,
  missingFields,
}: SectionConstraintsProps) {
  return (
    <div className="assessment-section" role="region" aria-labelledby="section-constraints-heading">
      <div className="section-intro">
        <h3 id="section-constraints-heading" className="section-title">
          Work Style & Study Constraints
        </h3>
        <p className="section-subtitle">
          Define your working preferences, available study bandwidth, and target timeline so your recommendations and pacing remain realistic.
        </p>
      </div>

      {/* Part A: Work Styles */}
      <section className="constraints-block" aria-labelledby="heading-work-styles">
        <div className="block-header">
          <span className="eyebrow">PART A</span>
          <h4 id="heading-work-styles" className="block-title">
            Work-Style Preferences
          </h4>
          <p className="block-subtitle">Rate how you prefer to operate on technical projects (1 = Minimal preference, 5 = Core priority).</p>
        </div>

        <div className="work-style-grid">
          {WORK_STYLE_FIELDS.map(({ key, title, description, lowLabel, highLabel }) => {
            const currentVal = workStyleResponses[key]
            const isMissing = missingFields.includes(`work_style.${key}`)

            return (
              <article
                key={key}
                id={`field-work_style-${key}`}
                className={`work-style-card ${isMissing ? 'work-style-card--missing' : ''} ${
                  currentVal !== undefined ? 'work-style-card--answered' : ''
                }`}
              >
                <div className="card-top">
                  <h5 className="work-style-title">{title}</h5>
                  {isMissing && (
                  <span className="missing-badge" id={`field-work_style-${key}-note`}>
                    Rating required
                  </span>
                )}
                </div>
                <p className="work-style-desc">{description}</p>

                <fieldset
                  className="work-style-rating"
                  aria-describedby={isMissing ? `field-work_style-${key}-note` : undefined}
                >
                  <legend className="sr-only">Rating for {title}</legend>
                  <div className="rating-scale-labels">
                    <span className="edge-label">{lowLabel}</span>
                    <span className="edge-label">{highLabel}</span>
                  </div>

                  <div className="segmented-rating-bar">
                    {[1, 2, 3, 4, 5].map((val) => {
                      const isSelected = currentVal === val
                      const inputId = `workstyle-${key}-${val}`

                      return (
                        <label
                          key={val}
                          htmlFor={inputId}
                          className={`rating-pill ${isSelected ? 'rating-pill--active' : ''}`}
                        >
                          <input
                            type="radio"
                            id={inputId}
                            name={`workstyle-${key}`}
                            value={val}
                            checked={isSelected}
                            onChange={() => onWorkStyleChange(key, val)}
                            className="sr-only"
                            aria-invalid={isMissing || undefined}
                          />
                          <span className="rating-num">{val}</span>
                        </label>
                      )
                    })}
                  </div>
                </fieldset>
              </article>
            )
          })}
        </div>
      </section>

      {/* Part B: Time & Schedule Constraints */}
      <section className="constraints-block" aria-labelledby="heading-study-constraints">
        <div className="block-header">
          <span className="eyebrow">PART B</span>
          <h4 id="heading-study-constraints" className="block-title">
            Time & Roadmap Planning
          </h4>
          <p className="block-subtitle">Your available weekly commitment and target preparation milestone.</p>
        </div>

        <div className="planning-inputs-grid">
          {/* Weekly Available Hours */}
          <article
            id="field-hours_per_week"
            className={`planning-card ${
              missingFields.includes('hours_per_week') ? 'planning-card--missing' : ''
            }`}
          >
            <div className="card-top">
              <label htmlFor="hours-input" className="input-label">
                Weekly Study Time
              </label>
              {missingFields.includes('hours_per_week') && (
                <span className="missing-badge" id="hours-required-note">Required</span>
              )}
            </div>
            <p className="input-helper">How many hours can you dedicate to learning and building each week?</p>

            <div className="hours-input-wrapper">
              <div className="hours-numeric-row">
                <input
                  id="hours-input"
                  type="number"
                  min={1}
                  max={60}
                  step={1}
                  value={constraints.hours_per_week}
                  onChange={(e) => {
                    const val = e.target.value === '' ? '' : Math.max(1, Math.min(60, Number(e.target.value)))
                    onConstraintsChange('hours_per_week', val)
                  }}
                  placeholder="e.g. 15"
                  className="hours-input"
                  aria-invalid={missingFields.includes('hours_per_week') || undefined}
                  aria-describedby={
                    missingFields.includes('hours_per_week') ? 'hours-required-note' : undefined
                  }
                />
                <span className="hours-unit">hours / week</span>
              </div>

              <div className="quick-select-row">
                <span className="quick-label">Quick select:</span>
                {QUICK_HOURS.map((h) => (
                  <button
                    key={h}
                    type="button"
                    className={`quick-chip ${constraints.hours_per_week === h ? 'quick-chip--active' : ''}`}
                    onClick={() => onConstraintsChange('hours_per_week', h)}
                  >
                    {h} hrs
                  </button>
                ))}
              </div>
            </div>
          </article>

          {/* Target Timeline */}
          <article
            id="field-target_timeline_weeks"
            className={`planning-card ${
              missingFields.includes('target_timeline_weeks') ? 'planning-card--missing' : ''
            }`}
          >
            <div className="card-top">
              <span className="input-label">Target Preparation Timeline</span>
              {missingFields.includes('target_timeline_weeks') && (
                <span className="missing-badge" id="timeline-required-note">Required</span>
              )}
            </div>
            <p className="input-helper">When do you aim to complete your milestone portfolio project?</p>

            <div className="timeline-options-grid">
              {TIMELINE_OPTIONS.map(({ value, label, subtext }) => {
                const isSelected = constraints.target_timeline_weeks === value
                const inputId = `timeline-${value}`

                return (
                  <label
                    key={value}
                    htmlFor={inputId}
                    className={`timeline-option ${isSelected ? 'timeline-option--active' : ''}`}
                  >
                    <input
                      type="radio"
                      id={inputId}
                      name="target_timeline_weeks"
                      value={value}
                      checked={isSelected}
                      onChange={() => onConstraintsChange('target_timeline_weeks', value)}
                      className="sr-only"
                      aria-invalid={missingFields.includes('target_timeline_weeks') || undefined}
                      aria-describedby={
                        missingFields.includes('target_timeline_weeks') ? 'timeline-required-note' : undefined
                      }
                    />
                    <span className="timeline-label">{label}</span>
                    <span className="timeline-subtext">{subtext}</span>
                  </label>
                )
              })}
            </div>
          </article>
        </div>
      </section>

      {/* Part C: Career Certainty */}
      <section className="constraints-block" aria-labelledby="heading-career-certainty">
        <div className="block-header">
          <span className="eyebrow">PART C</span>
          <h4 id="heading-career-certainty" className="block-title">
            Career Direction Certainty{' '}
            {missingFields.includes('career_certainty') && (
              <span className="missing-badge" id="certainty-required-note">
                Selection required
              </span>
            )}
          </h4>
          <p className="block-subtitle">Help us tailor how exploratory versus specialized your initial guidance will be.</p>
        </div>

        <div
          id="field-career_certainty"
          className={`certainty-options-list ${
            missingFields.includes('career_certainty') ? 'certainty-options-list--missing' : ''
          }`}
        >
          {CERTAINTY_OPTIONS.map(({ value, title, desc }) => {
            const isSelected = constraints.career_certainty === value
            const inputId = `certainty-${value}`

            return (
              <label
                key={value}
                htmlFor={inputId}
                className={`certainty-card ${isSelected ? 'certainty-card--active' : ''}`}
              >
                <input
                  type="radio"
                  id={inputId}
                  name="career_certainty"
                  value={value}
                  checked={isSelected}
                  onChange={() => onConstraintsChange('career_certainty', value)}
                  className="sr-only"
                  aria-invalid={missingFields.includes('career_certainty') || undefined}
                  aria-describedby={
                    missingFields.includes('career_certainty') ? 'certainty-required-note' : undefined
                  }
                />
                <div className="certainty-radio-indicator">
                  <div className="indicator-inner" />
                </div>
                <div className="certainty-content">
                  <h5 className="certainty-title">{title}</h5>
                  <p className="certainty-desc">{desc}</p>
                </div>
              </label>
            )
          })}
        </div>
      </section>
    </div>
  )
}
