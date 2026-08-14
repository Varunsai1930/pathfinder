interface ProgressBarProps {
  currentStep: number
  totalSteps: number
  stepTitles: string[]
  completedCount?: number
  totalCount?: number
}

export function ProgressBar({
  currentStep,
  totalSteps,
  stepTitles,
  completedCount,
  totalCount,
}: ProgressBarProps) {
  const currentTitle = stepTitles[currentStep - 1]
  const progressPercent = Math.round(((currentStep - 1) / totalSteps) * 100)
  const itemPercent =
    completedCount !== undefined && totalCount !== undefined && totalCount > 0
      ? Math.round((completedCount / totalCount) * 100)
      : null

  return (
    <div className="assessment-progress-container" aria-label="Assessment progress">
      <div className="assessment-progress-header">
        <div>
          <span className="eyebrow">
            SECTION {currentStep} OF {totalSteps}
          </span>
          <h2 className="progress-title">{currentTitle}</h2>
        </div>

        <div className="progress-stats">
          {itemPercent !== null ? (
            <span className="progress-counter">
              <b>{completedCount}</b> / {totalCount} answered ({itemPercent}%)
            </span>
          ) : (
            <span className="progress-counter">
              Step {currentStep} of {totalSteps}
            </span>
          )}
        </div>
      </div>

      <div className="progress-track" role="progressbar" aria-valuenow={currentStep} aria-valuemin={1} aria-valuemax={totalSteps}>
        <div
          className="progress-fill"
          style={{ width: `${Math.max(8, progressPercent + (itemPercent !== null ? (itemPercent / totalSteps) : 0))}%` }}
        />
      </div>

      <div className="step-pills">
        {stepTitles.map((title, idx) => {
          const stepNum = idx + 1
          const isDone = stepNum < currentStep
          const isCurrent = stepNum === currentStep
          return (
            <div
              key={title}
              className={`step-pill ${isCurrent ? 'active' : ''} ${isDone ? 'done' : ''}`}
            >
              <span className="pill-num">{isDone ? '✓' : `0${stepNum}`}</span>
              <span className="pill-title">{title}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
