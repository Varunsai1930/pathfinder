# Pathfinder v1 — Build Plan

## Summary

Build a web SaaS for **Indian tech students** that recommends one of six career paths—**Frontend Developer, Backend Developer, Data Analyst, Cloud/DevOps Engineer, Security Analyst, Data Engineer**—then creates a grounded, actionable learning roadmap.

The recommender is deterministic and transparent. An LLM personalizes explanations and pacing, with a non-LLM fallback so the demo always works. Users sign in with email; an optional résumé and GitHub URL enrich their manually entered profile only after consent.

## Implementation

### 1. Stack and deployment

- Frontend: React, Vite, TypeScript, Tailwind CSS.
- Backend: Python FastAPI, Pydantic, pytest.
- Auth/database: Supabase Auth using email OTP plus Supabase Postgres.
- Deploy frontend to Vercel; deploy FastAPI to Railway; configure CORS only for the production and local frontend origins.
- Use an OpenAI API model capable of structured JSON output. Store the key only in backend environment variables.
- Use static, versioned JSON data in the backend for all role definitions. Do not call O*NET or roadmap.sh during user flows.

### 2. Grounded career data and matching

Create curated data for six roles (the four original paths plus Security Analyst and Data Engineer, added during the build). Each role includes:

- Role description and expected entry-level outcome.
- Six numeric interest weights aligned to RIASEC categories.
- Work-style weights: analytical, creative, collaborative, structured, systems-oriented.
- Required skills split into `core`, `supporting`, and `optional`.
- Five ordered milestones, each containing skills, one practical task, one portfolio deliverable, and curated resource links.
- A realistic student project brief.

Use O*NET only as a cited source for occupation structure and RIASEC interest profiles. Write original skill lists, milestone names, task descriptions, and project briefs. Use roadmap.sh only as an inspiration/reference source; do not copy its roadmap content.

The profile assessment contains:

- 18 original interest-exploration statements, three for each RIASEC dimension, scored on a five-point “not like me” to “very like me” scale.
- Skill confidence for a fixed tech-skill checklist: `none`, `aware`, `practised`, `project-ready`.
- Work-style preferences, weekly available hours, target timeline, and career certainty.

Call this an **interest exploration assessment**, not a validated psychometric test.

Calculate each role’s `PathFinder fit score` as:

- 55% normalized similarity between the user’s six-dimension interest vector and the role’s stored interest vector.
- 35% weighted skill readiness, with core skills weighted more heavily than supporting skills.
- 10% work-style alignment.

Show the breakdown and the exact missing core skills. Do not label scores as probabilities or claims of job eligibility.

### 3. User experience

Build five pages:

1. **Landing** — concise value proposition, supported roles, privacy statement, email sign-in.
2. **Assessment** — three short sections: interests, skills, constraints. Show progress and allow saving between sections.
3. **Results** — ranked cards for all six roles, top recommendation highlighted, with fit breakdown, three supporting reasons, two biggest gaps, and “Explore path.”
4. **Career path dashboard** — selected role, current readiness, five visual milestones, weekly plan, project brief, checklist, and next best action.
5. **Profile & evidence** — edit assessment, connect GitHub URL, upload résumé, view extracted skills, approve or reject each proposed skill before it affects the profile.

Persist selected role, profile, roadmap, and task progress for each signed-in user. Do not store anonymous profiles.

### 4. Optional evidence enrichment

Résumé upload accepts PDF or DOCX up to 5 MB. Extract text server-side, infer only skills from the fixed skill taxonomy, return proposed skills and confidence, then delete the uploaded file and extracted text immediately. Persist only user-approved skill values and an enrichment timestamp.

GitHub enrichment accepts only a public profile URL. Fetch public repositories and languages through GitHub’s API, infer skills only when backed by visible repository language or topic data, and present them for approval. If the GitHub API fails, the profile flow continues without error.

Manual assessment is always authoritative. Enrichment never alters recommendations until the user explicitly approves a proposed skill.

### 5. AI personalization and safe fallback

The backend first computes role results and skill gaps. It then sends the LLM only:

- Selected role and its approved milestone data.
- User interest summary, confirmed skills, missing skills, hours per week, and target timeline.

Require structured JSON with:

- `fit_explanation`: 2–3 sentences.
- `weekly_plan`: ordered weekly tasks referencing only supplied milestones/tasks.
- `adaptation_note`: one sentence based on completed tasks.

Validate output against Pydantic schemas. Reject unknown skills, resources, roles, statistics, certifications, salary claims, and milestones. On API, validation, rate-limit, or network failure, use deterministic template explanations and milestone-based pacing. The dashboard must never show an AI error to the user.

### 6. Backend interfaces

Implement these authenticated FastAPI endpoints:

- `POST /profile` — save assessment, skills, preferences, and constraints.
- `GET /profile` — return the persisted user profile.
- `POST /match` — calculate and persist all six role scores and return their score breakdowns.
- `POST /roadmaps/{role_id}` — create or refresh the selected role’s personalized weekly plan.
- `GET /roadmaps/{role_id}` — return roadmap, milestones, and task completion state.
- `PATCH /tasks/{task_id}` — update a task’s completion state and return the recalculated next action.
- `POST /enrichment/resume` — extract and return proposed skills; never persist the source document.
- `POST /enrichment/github` — return proposed skills from a public GitHub profile.
- `POST /enrichment/approve` — persist only approved inferred skills.

FastAPI verifies Supabase JWTs on every API call and derives the user ID from the verified token, never from request body data.

### 7. Data model

Use these tables:

- `profiles`: user ID, assessment vectors, skill confidence map, work preferences, hours/week, timeline, selected role.
- `recommendations`: user ID, role ID, total score, score breakdown, generated timestamp.
- `roadmaps`: user ID, role ID, weekly-plan JSON, generation mode (`llm` or `fallback`), generated timestamp.
- `tasks`: roadmap ID, milestone ID, task ID, completion state, completed timestamp.
- `enrichment_events`: user ID, source type, success/failure state, timestamp; store no résumé content or GitHub response body.

Keep role definitions in backend static JSON, not the database.

## Delivery Sequence

1. **Aug 13:** Create the React/FastAPI/Supabase skeleton, auth flow, environment configuration, and static role-data schema.
2. **Aug 14:** Curate and test the four role definitions, original assessment prompts, skills taxonomy, milestones, projects, and resources.
3. **Aug 15:** Implement and unit-test deterministic matching with representative profiles for each intended top role.
4. **Aug 16:** Build assessment and results UI; integrate profile persistence and score breakdowns.
5. **Aug 17:** Build roadmap dashboard, task persistence, next-action logic, and deterministic weekly-plan fallback.
6. **Aug 18:** Add structured LLM explanations/pacing, schema validation, and failure fallback.
7. **Aug 19:** Add optional résumé extraction, GitHub enrichment, approval UI, deletion behavior, and graceful failure states.
8. **Aug 20:** Polish responsive UI, empty/loading/error states, accessibility, and demo-specific seeded test accounts.
9. **Aug 21:** Deploy frontend, backend, and Supabase production configuration; conduct end-to-end testing on mobile and desktop.
10. **Aug 22:** Record the walkthrough, write README, architecture diagram, source acknowledgements, and privacy note.
11. **Aug 23:** Submit the hosted URL, repository, and video/write-up. Keep Aug 24 as contingency; do not wait for the Aug 25 deadline.

## Test Plan

- Unit-test scoring so four representative profiles rank their intended role first, and verify score-breakdown totals equal 100%.
- Test every assessment answer scale, missing skill value, and empty optional-enrichment path.
- Test LLM output validation with malformed JSON, invented skills, invented resources, timeouts, and rate limits; confirm fallback is shown.
- Test résumé formats, invalid uploads, oversized uploads, failed extraction, private/invalid GitHub URLs, and GitHub API failure.
- Test authentication: signed-out API calls fail; a user cannot read or update another user’s profile, roadmap, or tasks.
- Run one complete demo journey: sign in → assessment → results → approve enrichment → select path → complete task → receive adapted next action.
- Verify deployed app loads, signs in, generates paths, and falls back correctly with the LLM key temporarily disabled.

## Assumptions

- The dashboard deadline of **Aug 25, 5:29 AM IST** governs submission; submission occurs by Aug 23.
- Users are advised that Pathfinder is a career-exploration tool, not a guarantee of employment or professional counselling.
- A live LLM key and Supabase/Vercel/Railway accounts are available before implementation begins.
- Deeply curated roles are preferable to broad but weak career coverage for this prototype — the plan started with four and expanded to six (Security Analyst, Data Engineer).
