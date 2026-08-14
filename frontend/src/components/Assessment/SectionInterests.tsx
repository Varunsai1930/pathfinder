import type { AssessmentCatalogData, InterestQuestion } from '../../data/assessmentCatalog'

interface SectionInterestsProps {
  catalog: AssessmentCatalogData
  responses: Record<string, number>
  onChange: (questionId: string, value: number) => void
  missingQuestionIds: string[]
}

const DIMENSION_LABELS: Record<string, string> = {
  realistic: 'Realistic (Practical & Systems)',
  investigative: 'Investigative (Analysis & Research)',
  artistic: 'Artistic (Design & Expression)',
  social: 'Social (Helping & Collaboration)',
  enterprising: 'Enterprising (Leadership & Action)',
  conventional: 'Conventional (Structure & Detail)',
}

export function SectionInterests({
  catalog,
  responses,
  onChange,
  missingQuestionIds,
}: SectionInterestsProps) {
  const { purpose_note, response_scale, interest_questions } = catalog

  return (
    <div className="assessment-section" role="region" aria-labelledby="section-interests-heading">
      <div className="section-intro">
        <h3 id="section-interests-heading" className="section-title">
          Interest Exploration
        </h3>
        <p className="section-subtitle">
          Rate how accurately each statement describes the kind of work and problems you naturally gravitate toward.
        </p>
        <aside className="purpose-banner" role="note">
          <span className="purpose-tag">NOTE</span>
          <p>{purpose_note}</p>
        </aside>
      </div>

      <div className="questions-list">
        {interest_questions.map((q: InterestQuestion, index: number) => {
          const isMissing = missingQuestionIds.includes(q.id)
          const currentValue = responses[q.id]

          return (
            <article
              key={q.id}
              id={`question-${q.id}`}
              className={`question-card ${isMissing ? 'question-card--missing' : ''} ${
                currentValue ? 'question-card--answered' : ''
              }`}
            >
              <header className="question-header">
                <span className="question-index">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span className="question-dimension-tag" title={DIMENSION_LABELS[q.dimension] ?? q.dimension}>
                  {q.dimension.toUpperCase()}
                </span>
                {isMissing && <span className="missing-badge">Response required</span>}
              </header>

              <p className="question-prompt">{q.prompt}</p>

              <fieldset className="segmented-scale" aria-label={`Response for question ${index + 1}`}>
                <legend className="sr-only">{q.prompt}</legend>
                <div className="scale-options-grid">
                  {response_scale.map((label: string, scaleIdx: number) => {
                    const value = scaleIdx + 1
                    const isSelected = currentValue === value
                    const inputId = `${q.id}-option-${value}`

                    return (
                      <label
                        key={value}
                        htmlFor={inputId}
                        className={`scale-option ${isSelected ? 'scale-option--active' : ''}`}
                      >
                        <input
                          type="radio"
                          id={inputId}
                          name={q.id}
                          value={value}
                          checked={isSelected}
                          onChange={() => onChange(q.id, value)}
                          className="sr-only"
                        />
                        <span className="scale-value-num">{value}</span>
                        <span className="scale-label-text">{label}</span>
                      </label>
                    )
                  })}
                </div>
              </fieldset>
            </article>
          )
        })}
      </div>
    </div>
  )
}
