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
}

export interface RolesCatalogData {
  schema_version: string
  roles: RoleDefinition[]
}

export interface AppCatalogBundle {
  assessment: AssessmentCatalogData
  roles: RolesCatalogData
}

/**
 * Fetch the assessment and roles reference catalogs from the backend API at runtime.
 * This ensures no backend file paths are imported across the deployment boundary.
 */
export async function fetchCatalogData(): Promise<AppCatalogBundle> {
  const [assessmentRes, rolesRes] = await Promise.all([
    fetch(`${config.apiUrl}/api/v1/catalog/assessment`),
    fetch(`${config.apiUrl}/api/v1/catalog/roles`),
  ])

  if (!assessmentRes.ok) {
    throw new Error(
      `Failed to load assessment catalog from backend (${assessmentRes.status} ${assessmentRes.statusText})`
    )
  }

  if (!rolesRes.ok) {
    throw new Error(
      `Failed to load roles catalog from backend (${rolesRes.status} ${rolesRes.statusText})`
    )
  }

  const assessment: AssessmentCatalogData = await assessmentRes.json()
  const roles: RolesCatalogData = await rolesRes.json()

  return { assessment, roles }
}
