import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  fetchAssessmentCatalog,
  fetchCatalogData,
  fetchCoursesCatalog,
  fetchRolesCatalog,
  resetCatalogCacheForTests,
} from './assessmentCatalog'

const assessmentPayload = { schema_version: 'assessment.v1', skills: [], interest_questions: [] }
const rolesPayload = { schema_version: 'roles.v1', roles: [] }
const coursesPayload = { courses: [] }

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubCatalogFetch() {
  return vi.fn((url: RequestInfo | URL) => {
    const path = String(url)
    if (path.endsWith('/catalog/assessment')) return Promise.resolve(jsonResponse(assessmentPayload))
    if (path.endsWith('/catalog/roles')) return Promise.resolve(jsonResponse(rolesPayload))
    if (path.endsWith('/catalog/courses')) return Promise.resolve(jsonResponse(coursesPayload))
    return Promise.resolve(jsonResponse({}, 404))
  })
}

describe('catalog fetch caching', () => {
  afterEach(() => {
    resetCatalogCacheForTests()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('deduplicates concurrent and repeated loads into one fetch per catalog', async () => {
    const fetchMock = stubCatalogFetch()
    vi.stubGlobal('fetch', fetchMock)

    const [a1, a2] = await Promise.all([fetchAssessmentCatalog(), fetchAssessmentCatalog()])
    expect(a1).toBe(a2)
    await fetchRolesCatalog()
    const bundle = await fetchCatalogData()
    expect(bundle.assessment).toEqual(assessmentPayload)
    expect(bundle.roles).toEqual(rolesPayload)
    await fetchCoursesCatalog()

    expect(fetchMock).toHaveBeenCalledTimes(3)
    for (const path of ['/catalog/assessment', '/catalog/roles', '/catalog/courses']) {
      expect(fetchMock.mock.calls.filter(([url]) => String(url).includes(path))).toHaveLength(1)
    }
  })

  it('refetches after a failure instead of caching the rejection', async () => {
    let assessmentCalls = 0
    let rolesCalls = 0
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      const path = String(url)
      if (path.endsWith('/catalog/assessment')) {
        assessmentCalls += 1
        return Promise.resolve(
          assessmentCalls === 1 ? jsonResponse({}, 500) : jsonResponse(assessmentPayload),
        )
      }
      if (path.endsWith('/catalog/roles')) {
        rolesCalls += 1
        return Promise.resolve(rolesCalls === 1 ? jsonResponse({}, 503) : jsonResponse(rolesPayload))
      }
      if (path.endsWith('/catalog/courses')) return Promise.resolve(jsonResponse(coursesPayload))
      return Promise.resolve(jsonResponse({}, 404))
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchAssessmentCatalog()).rejects.toThrow(
      'Failed to load assessment catalog from backend (500',
    )
    await expect(fetchAssessmentCatalog()).resolves.toEqual(assessmentPayload)
    expect(assessmentCalls).toBe(2)

    // A transient roles failure must not break fetchCatalogData once recovered.
    await expect(fetchRolesCatalog()).rejects.toThrow()
    const bundle = await fetchCatalogData()
    expect(bundle.roles).toEqual(rolesPayload)
    expect(rolesCalls).toBe(2)
  })
})
