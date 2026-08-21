interface SectionGoalProps {
  goalText: string
  onGoalChange: (value: string) => void
  onPrefill: () => void
  onSkip: () => void
  isLoading: boolean
  error: string | null
}

const MIN_GOAL_LENGTH = 10
const MAX_GOAL_LENGTH = 2000

export function SectionGoal({
  goalText,
  onGoalChange,
  onPrefill,
  onSkip,
  isLoading,
  error,
}: SectionGoalProps) {
  const canSubmit = goalText.trim().length >= MIN_GOAL_LENGTH && !isLoading

  return (
    <div className="assessment-section" role="region" aria-labelledby="section-goal-heading">
      <div className="section-intro">
        <h3 id="section-goal-heading" className="section-title">
          Start With Your Goal
        </h3>
        <p className="section-subtitle">
          Describe what you want in your own words. Pathfinder turns your goal into a starting
          draft of this assessment — you review and edit every part before anything is scored.
        </p>
      </div>

      <div className="goal-intake-card">
        <label htmlFor="goal-textarea" className="input-label">
          Your goal, in your own words
        </label>
        <textarea
          id="goal-textarea"
          className="goal-textarea"
          value={goalText}
          onChange={(e) => onGoalChange(e.target.value)}
          maxLength={MAX_GOAL_LENGTH}
          rows={6}
          aria-describedby="goal-helper-text"
          placeholder="e.g. I'm a second-year student who enjoys building small web pages and digging through spreadsheet data. I have about 10 hours a week and want a job-ready path in six months — but I'm not sure which role suits me."
        />
        <p id="goal-helper-text" className="input-helper">
          Mention what you enjoy, what you have already tried, and how much time you have.
          Nothing is locked in — every answer stays editable on the next screens.
        </p>

        <div className="goal-meta-row">
          <span className="goal-char-count" aria-live="polite">
            {goalText.length} / {MAX_GOAL_LENGTH}
          </span>
        </div>

        {error && (
          <div className="validation-banner" role="alert">
            <span className="validation-icon">✕</span>
            <span className="validation-text">{error}</span>
          </div>
        )}

        <div className="goal-actions">
          <button type="button" className="btn-primary" onClick={onPrefill} disabled={!canSubmit}>
            {isLoading ? 'Reading your goal…' : 'Pre-fill my assessment →'}
          </button>
          <button type="button" className="btn-secondary" onClick={onSkip} disabled={isLoading}>
            Skip — I'll fill it in myself
          </button>
        </div>
      </div>
    </div>
  )
}
