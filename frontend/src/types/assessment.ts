export type SkillConfidence = 'none' | 'aware' | 'practised' | 'project-ready'

export interface WorkStyleResponses {
  analytical: number
  creative: number
  collaborative: number
  structured: number
  systems_oriented: number
}

export type CareerCertainty = 'exploring' | 'deciding' | 'committed'

export interface ConstraintsState {
  hours_per_week: number | ''
  target_timeline_weeks: number | ''
  career_certainty: CareerCertainty | ''
}

export interface AssessmentState {
  interest_responses: Record<string, number>
  skill_confidence: Record<string, SkillConfidence>
  work_style_responses: Record<keyof WorkStyleResponses, number | undefined>
  constraints: ConstraintsState
}

export interface AssessmentPayload {
  interest_responses: Record<string, number>
  skill_confidence: Record<string, SkillConfidence>
  work_style_responses: WorkStyleResponses
  constraints: {
    hours_per_week: number
    target_timeline_weeks: number
    career_certainty: CareerCertainty
  }
}
