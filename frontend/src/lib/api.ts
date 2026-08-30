import { config } from './config'

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
  fit_explanation: string
}

export interface MatchResponse {
  normalized_interest_profile: Record<string, number>
  normalized_work_style_profile: Record<string, number>
  recommendations: CareerRecommendation[]
  generation_mode: 'fallback' | 'llm'
}

/* ------------------------------------------------------------------ */
/*  Shared match loading                                               */
/* ------------------------------------------------------------------ */

/** Thrown by loadMatch when the signed-in user has no profile yet. */
export class ProfileMissingError extends Error {
  constructor() {
    super('No completed assessment found — start the assessment to compute your matches.')
  }
}

async function detailFrom(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json()
    if (body?.detail) return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  } catch { /* response was not JSON */ }
  return fallback
}

/**
 * Load the user's match from the single shared code path: GET the persisted
 * result first; POST (compute) only when nothing is persisted for the current
 * profile version (404) or the backend build predates GET /match (405).
 * Every surface that reads match data uses this, so no page silently
 * recomputes and overwrites the stored match behind the others' backs.
 * `fallback` seeds the error message when the backend sends no usable detail.
 *
 * `opts.explain` (default false) applies to the recompute leg only: the POST
 * gets `?explain=false`, which returns deterministic template explanations
 * without the OpenRouter round-trip and without writing the cache — right for
 * surfaces that only read scores/role ids (Progress, Dashboard, Landing).
 * Results omits it so a recompute there stays personalized and cached.
 */
export async function loadMatch(
  headers: HeadersInit,
  fallback = 'Failed to load results',
  opts: { explain?: boolean } = {},
): Promise<MatchResponse> {
  let res = await fetch(`${config.apiUrl}/api/v1/match`, { headers })
  if (res.status === 404 || res.status === 405) {
    const profileRes = await fetch(`${config.apiUrl}/api/v1/profile`, { headers })
    if (profileRes.status === 404) throw new ProfileMissingError()
    const suffix = opts.explain ? '?explain=false' : ''
    res = await fetch(`${config.apiUrl}/api/v1/match${suffix}`, { method: 'POST', headers })
  }
  if (!res.ok) {
    throw new Error(await detailFrom(res, `${fallback} (${res.status})`))
  }
  return res.json() as Promise<MatchResponse>
}
