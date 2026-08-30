import { config } from '../lib/config'

export interface InterestQuestion {
  id: string
  dimension: string
  prompt: string
}

export interface SkillDefinition {
  id: string
  name: string
  domain: string
  profile_prompt: string
}

export interface AssessmentCatalogData {
  schema_version: string
  purpose_note: string
  response_scale: string[]
  interest_questions: InterestQuestion[]
  skills: SkillDefinition[]
}

export interface RoleSkill {
  id: string
  name: string
  tier: 'core' | 'supporting' | 'optional'
}

export interface RoleDefinition {
  id: string
  title: string
  summary: string
  skills: RoleSkill[]
  portfolio_project: {
    title: string
    brief: string
    evidence_of_readiness: string[]
  }
}

export interface RolesCatalogData {
  schema_version: string
  roles: RoleDefinition[]
}

export interface AppCatalogBundle {
  assessment: AssessmentCatalogData
  roles: RolesCatalogData
}

export interface CoursesCatalogData {
  courses: {
    id: string
    title: string
    provider: string
    url: string
    skill_ids: string[]
    prerequisites: string[]
    level: string
    duration_hours: number
    description: string
  }[]
}

async function fetchJson<T>(path: string, label: string): Promise<T> {
  const response = await fetch(`${config.apiUrl}${path}`)
  if (!response.ok) {
    throw new Error(`Failed to load ${label} (${response.status} ${response.statusText})`)
  }
  return (await response.json()) as T
}

// The catalogs are immutable reference data served from static files, so each
// is fetched once per session and shared by every consumer. Caches hold the
// in-flight promise (deduplicating concurrent callers) and are cleared on
// failure so a transient error can never poison later loads. Consumers must
// treat returned objects as read-only.
let assessmentCache: Promise<AssessmentCatalogData> | null = null
let rolesCache: Promise<RolesCatalogData> | null = null
let coursesCache: Promise<CoursesCatalogData> | null = null

export function fetchAssessmentCatalog(): Promise<AssessmentCatalogData> {
  if (!assessmentCache) {
    assessmentCache = fetchJson<AssessmentCatalogData>(
      '/api/v1/catalog/assessment',
      'assessment catalog from backend',
    ).catch((err: unknown) => {
      assessmentCache = null
      throw err
    })
  }
  return assessmentCache
}

export function fetchRolesCatalog(): Promise<RolesCatalogData> {
  if (!rolesCache) {
    rolesCache = fetchJson<RolesCatalogData>(
      '/api/v1/catalog/roles',
      'roles catalog from backend',
    ).catch((err: unknown) => {
      rolesCache = null
      throw err
    })
  }
  return rolesCache
}

export function fetchCoursesCatalog(): Promise<CoursesCatalogData> {
  if (!coursesCache) {
    coursesCache = fetchJson<CoursesCatalogData>(
      '/api/v1/catalog/courses',
      'courses catalog',
    ).catch((err: unknown) => {
      coursesCache = null
      throw err
    })
  }
  return coursesCache
}

/** Test-only: clear the module caches so each test starts uncached. */
export function resetCatalogCacheForTests(): void {
  assessmentCache = null
  rolesCache = null
  coursesCache = null
}

/**
 * Fetch the assessment and roles reference catalogs from the backend API at runtime.
 * This ensures no backend file paths are imported across the deployment boundary.
 * Both catalogs are session-cached; see fetchAssessmentCatalog/fetchRolesCatalog.
 */
export async function fetchCatalogData(): Promise<AppCatalogBundle> {
  const [assessment, roles] = await Promise.all([fetchAssessmentCatalog(), fetchRolesCatalog()])
  return { assessment, roles }
}
