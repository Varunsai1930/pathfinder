# PathFinder v2 — Build Plan (Revised)

**Status as of Aug 15:** Aug 13–14 complete (skeleton, auth flow, role data, assessment taxonomy). This revision folds in fixes identified during review. Changes from v1 are marked with `[FIX]`.

## Summary

Build a web SaaS for **Indian tech students** that recommends one of four career paths — **Frontend Developer, Backend Developer, Data Analyst, Cloud/DevOps Engineer** — then creates a grounded, actionable learning roadmap.

The recommender is deterministic and transparent. An LLM personalizes explanations and pacing, with a non-LLM fallback so the demo always works. Users sign in with email; an optional résumé and GitHub URL enrich their manually entered profile only after consent.

## Implementation

### 1. Stack and deployment

- Frontend: React, Vite, TypeScript, Tailwind CSS.
- Backend: Python FastAPI, Pydantic, pytest.
- Auth/database: Supabase Auth using email OTP plus Supabase Postgres.
- **`[FIX]` Deploy the empty skeleton (auth flow only) to Vercel + Railway on day 1, not after the build is complete.** Every subsequent day's feature ships to the same live environment, not just locally. This surfaces CORS/env-var/free-tier issues while they're cheap to fix, not on Aug 21 with two days left.
- Configure CORS only for the production and local frontend origins.
- Pin one specific LLM model now, in config, not "a model capable of structured JSON output." Document the exact model string in the README the day it's chosen. Store the key only in backend environment variables.
- Use static, versioned JSON data in the backend for all role definitions. Do not call O*NET or roadmap.sh during user flows.

### 2. Grounded career data and matching

Create curated data for exactly four roles. Each role includes:

- Role description and expected entry-level outcome.
- Six numeric interest weights aligned to RIASEC categories.
- Work-style weights: analytical, creative, collaborative, structured, systems-oriented.
- Required skills split into `core`, `supporting`, and `optional`.
- Five ordered milestones, each containing skills, one practical task, one portfolio deliverable, and curated resource links.
- A realistic student project brief.

**`[FIX]` Before matching logic is written, verify:** all four roles' interest vectors are on the same scale, and core/supporting skill-list lengths don't silently bias the skill-readiness term (normalize by max possible weighted score per role, not a raw sum — the skill term is not scale-invariant across roles unless you do this).

Use O*NET only as a cited source for occupation structure and RIASEC interest profiles. Write original skill lists, milestone names, task descriptions, and project briefs. Use roadmap.sh only as an inspiration/reference source; do not copy its roadmap content. Do not claim this reproduces O*NET's documented matching algorithm — it's inspired by, not identical to, that approach.

The profile assessment contains:

- 18 original interest-exploration statements, three for each RIASEC dimension, scored on a five-point "not like me" to "very like me" scale.
- Skill confidence for a fixed tech-skill checklist: `none`, `aware`, `practised`, `project-ready`.
- Work-style preferences, weekly available hours, target timeline, and career certainty.

Call this an **interest exploration assessment**, not a validated psychometric test.

Calculate each role's `PathFinder fit score` as:

- 55% normalized similarity between the user's six-dimension interest vector and the role's stored interest vector.
- 35% weighted skill readiness, with core skills weighted more heavily than supporting skills.
- 10% work-style alignment.

Show the breakdown and the exact missing core skills. Do not label scores as probabilities or claims of job eligibility.

### 3. User experience

Build five pages:

1. **Landing** — concise value proposition, supported roles, privacy statement, email sign-in.
2. **Assessment** — three short sections: interests, skills, constraints. Show progress and allow saving between sections.
3. **Results** — ranked cards for all four roles, top recommendation highlighted, with fit breakdown, three supporting reasons, two biggest gaps, and "Explore path."
4. **Career path dashboard** — selected role, current readiness, five visual milestones, weekly plan, project brief, checklist, and next best action.
5. **Profile & evidence** — edit assessment, connect GitHub URL, upload résumé, view extracted skills, approve or reject each proposed skill before it affects the profile.

Persist selected role, profile, roadmap, and task progress for each signed-in user. Do not store anonymous profiles.

### 4. Optional evidence enrichment — `[FIX]` explicit cut-line

This section is **the first thing to drop if Aug 17's checkpoint (below) isn't met.** Résumé/GitHub enrichment is not part of the scored core loop; don't let it consume guaranteed calendar time it wasn't earning in v1.

Résumé upload accepts PDF or DOCX up to 5 MB. Extract text server-side, infer only skills from the fixed skill taxonomy, return proposed skills and confidence, then delete the uploaded file and extracted text immediately. Persist only user-approved skill values and an enrichment timestamp.

GitHub enrichment accepts only a public profile URL. Fetch public repositories and languages through GitHub's API, infer skills only when backed by visible repository language or topic data, and present them for approval. If the GitHub API fails, the profile flow continues without error.

Manual assessment is always authoritative. Enrichment never alters recommendations until the user explicitly approves a proposed skill.

### 5. AI personalization and safe fallback

The backend first computes role results and skill gaps. It then sends the LLM only:

- Selected role and its approved milestone data.
- User interest summary, confirmed skills, missing skills, hours per week, and target timeline.

Require structured JSON with:

- `fit_explanation`: 2–3 sentences.
- `weekly_plan`: ordered weekly tasks referencing only supplied milestones/tasks.
- `adaptation_note`: one sentence based on completed tasks.

Validate output against Pydantic schemas. Reject unknown skills, resources, roles, statistics, certifications, salary claims, and milestones. On API, validation, rate-limit, or network failure, use deterministic template explanations and milestone-based pacing. The dashboard must never show an AI error to the user. Do not claim the system carries "zero hallucination risk" anywhere — the validation layer reduces risk, it doesn't eliminate it; the LLM explanation text itself is unconstrained prose.

### 6. Backend interfaces

Implement these authenticated FastAPI endpoints:

- `POST /profile` — save assessment, skills, preferences, and constraints.
- `GET /profile` — return the persisted user profile.
- `POST /match` — calculate and persist all four role scores and return their score breakdowns. **`[FIX]` If the assessment is incomplete, return a 4xx with which sections are missing rather than scoring against partial/default data.**
- `POST /roadmaps/{role_id}` — create or refresh the selected role's personalized weekly plan.
- `GET /roadmaps/{role_id}` — return roadmap, milestones, and task completion state.
- `PATCH /tasks/{task_id}` — update a task's completion state and return the recalculated next action.
- `POST /enrichment/resume` — extract and return proposed skills; never persist the source document.
- `POST /enrichment/github` — return proposed skills from a public GitHub profile.
- `POST /enrichment/approve` — persist only approved inferred skills.

FastAPI verifies Supabase JWTs on every API call and derives the user ID from the verified token, never from request body data. **`[FIX]` Enable Row-Level Security policies on `profiles`, `recommendations`, `roadmaps`, and `tasks` in Supabase Postgres as defense-in-depth** — JWT-derived user ID in FastAPI is necessary but not sufficient; a query bug shouldn't be able to leak cross-user rows.

### 7. Data model

Use these tables:

- `profiles`: user ID, assessment vectors, skill confidence map, work preferences, hours/week, timeline, selected role.
- `recommendations`: user ID, role ID, total score, score breakdown, generated timestamp.
- `roadmaps`: user ID, role ID, weekly-plan JSON, generation mode (`llm` or `fallback`), generated timestamp.
- `tasks`: roadmap ID, milestone ID, task ID, completion state, completed timestamp.
- `enrichment_events`: user ID, source type, success/failure state, timestamp; store no résumé content or GitHub response body.

Keep role definitions in backend static JSON, not the database. RLS policies apply to every table above except the static role JSON.

## Delivery Sequence

1. ~~**Aug 13:** React/FastAPI/Supabase skeleton, auth flow, env config, static role-data schema.~~ ✅ Done — **`[FIX]`** skeleton deployed live, not just local.
2. ~~**Aug 14:** Four role definitions, original assessment prompts, skills taxonomy, milestones, projects, resources.~~ ✅ Done
3. **Aug 15 (current):** Deterministic matching, unit-tested with representative profiles per intended top role, **plus the flat/generalist-profile edge case** — confirm no role wins by default due to skill-list length or weight asymmetry. Ship to live environment same day.
4. **Aug 16:** Assessment and results UI; profile persistence; score breakdowns. Ship to live.
5. **Aug 17 — checkpoint:** Roadmap dashboard, task persistence, next-action logic, deterministic weekly-plan fallback. **If the core loop (assessment → match → roadmap → fallback explanation) isn't working end-to-end today, drop Section 4 (enrichment) entirely and move to step 8.**
6. **Aug 18:** Structured LLM explanations/pacing, schema validation, failure fallback. Pinned model confirmed working live with key temporarily disabled to verify fallback path.
7. **Aug 19:** Only if Aug 17 checkpoint passed — résumé extraction, GitHub enrichment, approval UI, deletion behavior, graceful failure states.
8. **Aug 20:** Polish responsive UI, empty/loading/error states, accessibility, demo-specific seeded test accounts.
9. **Aug 21:** Production config hardening (RLS verified, CORS locked down); end-to-end testing on mobile and desktop.
10. **Aug 22:** Record walkthrough, finalize README/architecture diagram/source acknowledgements/privacy note — **`[FIX]` these should already be ~80% written incrementally from days 15–21, not started fresh today.**
11. **Aug 23:** Submit hosted URL, repository, video/write-up. Aug 24 stays contingency; do not wait for the Aug 25, 5:29 AM IST deadline.

**`[FIX]` Running doc habit:** after each day's session, add 3–5 lines to README/architecture notes covering what was built and any decision made. This replaces the single Aug 22 doc-writing task with incremental capture.

## Test Plan

- Unit-test scoring so four representative profiles rank their intended role first, verify score-breakdown totals equal 100% (real assertion, not eyeballed), **and test a flat/generalist profile for default-role bias.**
- Test every assessment answer scale, missing skill value, and empty optional-enrichment path.
- Test LLM output validation with malformed JSON, invented skills, invented resources, timeouts, and rate limits; confirm fallback is shown.
- Test résumé formats, invalid uploads, oversized uploads, failed extraction, private/invalid GitHub URLs, and GitHub API failure.
- Test authentication: signed-out API calls fail; a user cannot read or update another user's profile, roadmap, or tasks (verify this against RLS policies directly, not just application-layer checks).
- Test `/match` against an incomplete profile returns a clear 4xx, not a partial/default score.
- Run one complete demo journey: sign in → assessment → results → approve enrichment → select path → complete task → receive adapted next action.
- Verify deployed app loads, signs in, generates paths, and falls back correctly with the LLM key temporarily disabled.

## Assumptions

- The dashboard deadline of **Aug 25, 5:29 AM IST** governs submission; submission occurs by Aug 23.
- Users are advised that PathFinder is a career-exploration tool, not a guarantee of employment or professional counselling.
- A live LLM key and Supabase/Vercel/Railway accounts are available before implementation begins.
- Four deeply curated roles are preferable to broad but weak career coverage for this prototype.
- Section 4 (résumé/GitHub enrichment) is explicitly disposable scope, gated on the Aug 17 checkpoint.
