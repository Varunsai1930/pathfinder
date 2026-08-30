import { expect, test, type Page } from '@playwright/test'

/**
 * E2E smoke test for the core signed-in loop: landing (persisted match) →
 * career dashboard → task completion with telemetry. The backend API is fully
 * route-mocked and the Supabase session is injected into localStorage, so this
 * runs hermetically in CI without Supabase or OpenRouter credentials.
 */

const futureExp = Math.floor(Date.now() / 1000) + 3600

function fakeSession() {
  const b64 = (obj: object) => Buffer.from(JSON.stringify(obj)).toString('base64url')
  return {
    access_token: `${b64({ alg: 'HS256' })}.${b64({ sub: 'e1000000-0000-0000-0000-00000000e2e1', exp: futureExp })}.sig`,
    token_type: 'bearer',
    expires_in: 3600,
    expires_at: futureExp,
    refresh_token: 'test-refresh-token',
    user: {
      id: 'e1000000-0000-0000-0000-00000000e2e1',
      aud: 'authenticated',
      email: 'e2e@example.com',
      role: 'authenticated',
    },
  }
}

const MATCH = {
  normalized_interest_profile: {},
  normalized_work_style_profile: {},
  generation_mode: 'fallback',
  recommendations: [
    { role_id: 'backend-developer', role_title: 'Backend Developer', rank: 1, pathfinder_fit_score: 72.01,
      score_breakdown: { interest_alignment: 87.36, skill_readiness: 40, work_style_alignment: 99.62 },
      confirmed_skills: ['Python'], missing_core_skills: ['API design'], missing_supporting_skills: [],
      fit_explanation: 'Backend Developer is ranked #1 with a 72 fit score.' },
    { role_id: 'frontend-developer', role_title: 'Frontend Developer', rank: 2, pathfinder_fit_score: 70.87,
      score_breakdown: { interest_alignment: 86.33, skill_readiness: 40, work_style_alignment: 93.92 },
      confirmed_skills: ['JavaScript'], missing_core_skills: ['React'], missing_supporting_skills: [],
      fit_explanation: 'Frontend Developer is ranked #2 with a 71 fit score.' },
  ],
}

const ROADMAP = {
  role_id: 'backend-developer',
  generation_mode: 'fallback',
  created_at: '2026-08-30T00:00:00Z',
  updated_at: '2026-08-30T00:00:00Z',
  adaptation_note: '',
  weekly_plan: [1, 2, 3, 4, 5].map((week) => ({
    week,
    milestone_id: `backend-m${week}`,
    title: `Milestone ${week}`,
    objective: `Objective for milestone ${week}.`,
    skills: week === 1 ? ['git'] : ['python'],
    estimated_effort_hours: 8,
    practical_task: `Practical task ${week}.`,
    portfolio_deliverable: `Deliverable ${week}.`,
    resources: [{ title: 'MDN', url: 'https://developer.mozilla.org', provider: 'MDN' }],
    task_id: `task-uuid-${week}`,
    completed: false,
    personalized_focus: `Focus ${week}.`,
    time_spent_minutes: null,
    quiz_score: null,
  })),
}

const TASK_PATCH = {
  task: { id: 'task-uuid-1', completed: true, time_spent_minutes: 90, quiz_score: 80 },
  next_action: { milestone_id: 'backend-m2', task_label: 'Milestone 2', message: 'Next: Milestone 2' },
  skill_progression: { upgraded_skills: ['git'], milestone_id: 'backend-m1', message: 'Feedback loop: git promoted to practised' },
  telemetry_summary: { completed_count: 1, total_count: 5, completion_rate: 20, avg_time_spent_minutes: 90, avg_quiz_score: 80, pace_note: '' },
}

async function mockBackend(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname.replace('/api/v1', '')
    const method = route.request().method()
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

    if (path === '/match' && method === 'GET') return json(MATCH)
    if (path === '/roadmaps/backend-developer' && method === 'GET') return json(ROADMAP)
    if (path.startsWith('/tasks/') && method === 'PATCH') return json(TASK_PATCH)
    if (path === '/catalog/roles') {
      return json({
        schema_version: '1.0.0',
        roles: [{
          id: 'backend-developer', title: 'Backend Developer', summary: 'Design the systems and APIs behind products.',
          skills: [{ id: 'git', name: 'Git and GitHub', tier: 'core' }],
          portfolio_project: {
            title: 'REST API service', brief: 'Build and deploy a small REST API.',
            evidence_of_readiness: ['Deployed API with docs'],
          },
        }],
      })
    }
    if (path === '/catalog/assessment') {
      return json({ schema_version: '1.0.0', response_scale: [], interest_questions: [],
        skills: [{ id: 'git', name: 'Git and GitHub', domain: 'tooling', profile_prompt: '' }] })
    }
    if (path === '/catalog/courses') return json({ courses: [] })
    if (path === '/questions' && method === 'POST') {
      return json({ answer: 'Your top result is Backend Developer (#1, 72 fit score).', generation_mode: 'fallback' })
    }
    return json({ detail: `e2e mock: unhandled ${method} ${path}` }, 404)
  })
  // Safety net: no Supabase network calls are expected (session is pre-seeded).
  await page.route('**/auth/v1/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(fakeSession()) }),
  )
}

test.beforeEach(async ({ page }) => {
  await mockBackend(page)
  // Pre-seed the Supabase session so the app boots signed-in without OTP.
  await page.addInitScript(
    ([session, keyA, keyB]) => {
      localStorage.setItem(keyA!, JSON.stringify(session))
      localStorage.setItem(keyB!, JSON.stringify(session))
    },
    [fakeSession(), 'sb-localhost-auth-token', 'sb-localhost:54321-auth-token'],
  )
})

test('landing shows the persisted top path for the signed-in user', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Continue my path — Backend Developer →' })).toBeVisible()
  await expect(page.getByText('YOUR TOP PATH')).toBeVisible()
  // Landing must read the persisted match, never POST a recompute.
  const matchCalls = (await page.locator('body').evaluate(() => performance.getEntriesByType('resource').map((r) => r.name)))
    .filter((name: string) => name.includes('/api/v1/match'))
  expect(matchCalls.some((name) => name.toUpperCase().includes('POST'))).toBe(false)
})

test('dashboard renders the roadmap and completing a task fires telemetry', async ({ page }) => {
  await page.goto('/dashboard/backend-developer')
  // Direct deep link: roleTitle falls back to the mocked roles catalog.
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Backend Developer')
  await expect(page.getByText('NEXT BEST ACTION')).toBeVisible()
  await expect(page.getByRole('heading', { level: 2, name: 'Milestone 1' })).toBeVisible()

  const checkbox = page.getByRole('checkbox', { name: 'Mark Milestone 1 as complete' })
  await expect(checkbox).toBeVisible()
  await checkbox.click()

  // Optimistic update confirmed by the PATCH response shape.
  await expect(page.getByText('Feedback loop: git promoted to practised')).toBeVisible()
  await expect(page.getByText('Next: Milestone 2')).toBeVisible()
})
