# Pathfinder — Presentation for the Judge

Repo: `/Users/varun/Downloads/Varun/HCL` (GitHub `Varunsai1930/pathfinder`, last commit `c2a97e7`, 2026-08-21, 84 tracked files). Stack: React 19 + Vite + TypeScript (`frontend/`), FastAPI (`backend/`), Supabase Postgres + Auth OTP (`supabase/`). Backend test run on this machine (2026-08-21): **77 passed, 1 skipped** (`python3 -m pytest -q` in `backend/`, 0.16 s; the 1 skip is a live-OpenRouter test gated on `OPENROUTER_API_KEY`).

---

## 1. Pitch

Pathfinder is a career-path planning SaaS for tech students that answers "which tech role should I aim for, and what exactly do I do next?" with a **conversational front door and a deterministic engine**: the learner describes their goal in plain English, an LLM drafts their profile (interests, skills, constraints) as *editable suggestions*, a fully transparent scoring engine (55% RIASEC interest similarity / 35% tiered skill readiness / 10% work-style, all cosine-similarity based) ranks four entry-level roles with visible score math and exact skill gaps, and the chosen path becomes a five-milestone dashboard with weekly tasks, a prerequisite-aware 19-course catalog, time/quiz telemetry, a feedback loop that promotes demonstrated skills, and a grounded Q&A assistant. The architectural thesis: **"The AI explains. The math decides."** — the LLM is structurally incapable of inventing a role, milestone, or skill because every response is schema-validated and ID-checked against the learner's own computed data, with a deterministic fallback on every failure path.

---

## 2. Compliance matrix — the six required capabilities

| # | Required capability | Status | Evidence |
|---|---|---|---|
| 1 | **Conversational interface for goals in natural language** | **Built** | `POST /api/v1/intake` (`backend/app/api.py:74-86`) turns free text into reviewable pre-fill hints; LLM extraction + strict schema in `backend/app/personalization.py:584-676` (`GoalExtraction`, `generate_intake_prefill`); UI goal textarea + "Pre-fill my assessment" in `frontend/src/components/Assessment/SectionGoal.tsx`, wired in `AssessmentPage.tsx:283-367` (`handleIntakeSubmit` → editable draft + review notice banner). A second conversational surface, the global chat widget (`frontend/src/components/Chat/ChatWidget.tsx`, rendered app-wide in `App.tsx:145`), answers questions via `POST /api/v1/questions`. *Caveat:* intake is one-shot draft generation plus grounded Q&A chat — not an open-ended multi-turn planning conversation. |
| 2 | **Learner profiling engine (interests, experience level, completed work, objectives)** | **Built** | 18 RIASEC interest items + 19-skill confidence taxonomy (`none/aware/practised/project-ready`) + 5 work-style axes + hours/timeline/certainty constraints in `backend/app/catalog/assessment.v1.json`; persisted per user via `POST/GET /api/v1/profile` (`backend/app/api.py:89-112`, `backend/app/profile_store.py`) into the `profiles` table with RLS (`supabase/migrations/20260813000000_initial_schema.sql`); 4-step wizard UI in `frontend/src/components/Assessment/`. *Caveat:* there is no explicit "completed courses" list — prior experience is captured as per-skill confidence levels, and completed milestones auto-promote skill confidence in the feedback loop (`backend/app/task_store.py:99-180`). |
| 3 | **Recommendation engine (courses, projects, resources)** | **Built** | Deterministic role ranking: `POST /api/v1/match` (`backend/app/api.py:53-71`) → `backend/app/matching/service.py` (cosine similarity lines 52-59; confidence/tier weights 22-36; final weight `0.55*interest + 0.35*skill + 0.10*work_style` at line 143). Course recommendations: 19-course curated catalog mapped to the skill taxonomy at `backend/app/catalog/courses.v1.json`, exposed at `GET /api/v1/catalog/courses` (`backend/app/api.py:47-50`), filtered client-side to the learner's *missing* skills with prerequisite state (`frontend/src/components/Dashboard/DashboardPage.tsx:522-623`). Projects and resources come from each role's `portfolio_project` and per-milestone `resources` in `backend/app/catalog/roles.v1.json`. Scope note: recommendations rank 4 curated roles + the fixed catalog, not an external course-provider search. |
| 4 | **Learning path generator with prerequisites & milestones** | **Built (with one visual caveat)** | Every role has 5 ordered milestones (each with skills, practical task, portfolio deliverable, effort hours, resource links) in `roles.v1.json` (`sequence` field); per-user roadmap persistence via `POST/GET /api/v1/roadmaps/{role_id}` (`backend/app/api.py:115-132`, `backend/app/roadmap_store.py`) and task state via `PATCH /api/v1/tasks/{task_id}` (`backend/app/api.py:162-181`); tables `roadmaps` + `tasks` (`supabase/migrations/20260816000000_roadmaps.sql`, `20260816010000_tasks.sql`). **Prerequisites are modeled at course level** (`prerequisites` arrays in `courses.v1.json`) and rendered as a met/missing prerequisite chain per course (`DashboardPage.tsx:592-614`). Caveats: milestone order is the fixed catalog sequence (adaptivity is advisory — "suggested order adjustment" `DashboardPage.tsx:674-690`), and there is no single full-roadmap DAG graphic; the prerequisite visualization is per-course chips. |
| 5 | **AI assistant that explains recommendations and answers queries** | **Built** | Per-role 2-3 sentence `fit_explanation` (`personalize_match_response`, `personalization.py:211-256`); per-milestone `personalized_focus` + `adaptation_note` + roadmap-level fit explanation (`personalize_roadmap_response`, `personalization.py:381-516`); grounded Q&A over the caller's own match + owned roadmap at `POST /api/v1/questions` (`backend/app/api.py:135-159`, `answer_grounded_question` `personalization.py:535-565`). Two UIs: `ChatWidget.tsx` (floating, app-wide) and `AskAboutResults.tsx` (inline on Results and Dashboard). UI labels each answer `Personalized from your data` vs `Grounded Pathfinder guidance` (generation-mode transparency). |
| 6 | **Dashboard: progress, skill development, milestones, next actions** | **Built** | `frontend/src/components/Dashboard/DashboardPage.tsx` (801 lines): readiness % + milestones-complete counter (399-411), "NEXT BEST ACTION" banner (413-416), personalized pacing note (418-423), skill-development section confirmed vs to-develop core/supporting (444-520), recommended-courses grid with prerequisite graph (522-623), feedback-loop banner (625-630), learning-patterns telemetry stats — completion %, avg time on task, avg quiz score, pace ratio with insights (633-671), adaptive order suggestion (674-690), and the 5-milestone checklist with per-task time/quiz inputs (692-796). Progress persists in the `tasks` table; next action recomputed server-side (`task_store.py:285-310`). |

**Summary: 6/6 capabilities are delivered in code; none is Missing.** Two honest nuances: #1 is one-shot intake + Q&A rather than free-form multi-turn dialogue, and #4's prerequisite DAG lives at course level rather than as one full-path diagram.

---

## 3. How the AI actually works

### Deterministic core (no LLM, fully reproducible)
- **Matching** (`backend/app/matching/service.py`): learner answers are normalized into a 6-dimension RIASEC vector and a 5-axis work-style vector; each of the 4 roles has a stored target profile; similarity is **cosine** (magnitude-invariant, lines 52-59 — an earlier magnitude-sensitive bug was found and fixed, see commit `bccfec3` and `test_matching_invariance.py`). Skill readiness = weighted coverage with `CONFIDENCE_WEIGHTS {none:0, aware:0.3, practised:0.7, project-ready:1.0}` and `TIER_WEIGHTS {core:1.0, supporting:0.5, optional:0.25}` (lines 22-36). Final fit = `0.55/0.35/0.10` blend (line 143). Confirmed vs missing core/supporting skills are derived from the same data (lines 126-142).
- **Timeline feasibility is computed in code, never by the model** (`_timeline_facts`, `personalization.py:284-291`): total milestone hours ÷ hours/week vs target weeks.

### LLM layer (optional, constrained, pinned)
- **Model:** `meta-llama/llama-3.1-8b-instruct:free` via OpenRouter, **pinned** for reproducibility (`backend/app/config.py:19-22`); called through the OpenAI SDK with `base_url=https://openrouter.ai/api/v1`, `temperature=0.1`, `max_tokens=4000`, 25 s timeout (`personalization.py:147-175`).
- **Structured output only:** every call uses `response_format json_schema strict` with Pydantic schemas that have `extra="forbid"` (`_StrictModel`, line 77).
- **Four constrained uses:** (1) intake extraction → dimension-level RIASEC hints 0-100 + skill hints + constraints, which deterministic code maps to the 1-5 answer scale (`_hint_to_response`, lines 615-617) — the model never touches individual answers; (2) match fit explanations; (3) roadmap personalization (`fit_explanation`, 5× `weekly_focus`, `adaptation_note`); (4) grounded Q&A.
- **Validation & grounding guardrails:** unknown/duplicate role or milestone IDs → fallback (lines 250-254, 463-466, 560-564); Q&A answers must cite only owned role/milestone IDs; intake skill hints outside the taxonomy are dropped (lines 656-662).
- **Honesty detectors (the standout engineering):** a regex-based **skill-attribution detector** (`_ATTRIBUTION_RE`, `personalization.py:41-64`, applied at 341-356) rejects prose that attributes skills/traits the learner never confirmed ("your analytical mindset" with no confirmed skills → whole response replaced by deterministic fallback); a **timeline-honesty check** (lines 316-323, 474-481) rejects LLM prose that asserts an infeasible plan fits when computed `weeks_needed > target_weeks`.
- **Fallbacks:** missing key, timeout, rate limit, malformed JSON, schema failure, or any validation miss → deterministic template content with `generation_mode: "fallback"` (`_structured_completion` catch-all lines 188-190; fallback builders at 193-208, 259-313, 359-378, 519-532). The README documents how to verify the live LLM path (`"generation_mode": "llm"` in the `/match` response).
- **Non-LLM adaptation loop:** completing a milestone persists optional telemetry (`time_spent_minutes`, `quiz_score`, validated 0-10080 / 0-100) and **promotes that milestone's skills to "practised" in the learner's profile** (`task_store.py:99-180`), so the next `/match` genuinely changes; `_telemetry_summary` (183-213) and the adaptive next-action hint (285-310) use the same data.

---

## 4. Feature tour beyond the minimum

- **Conversational intake with human-in-the-loop draft** — goal text → pre-filled, fully editable assessment; the review notice states "you stay in control" (`AssessmentPage.tsx:354-358`).
- **Transparent score math on every card** — weighted breakdown bars labeled with their exact weights (55%/35%/10%) plus skill gaps (`ResultsPage.tsx:204-220`).
- **Prerequisite-aware course recommendations** — 19 curated courses (MDN, React, FastAPI, W3C WAI, GitHub Skills…), each with `prerequisites` rendered as a met/missing chain against the learner's confirmed skills (`DashboardPage.tsx:592-614`).
- **Closed feedback loop** — task completion → telemetry → skill promotion → updated readiness → learning-pattern insights → suggested order adjustment when quiz average < 60% or pace deviates >30% (`DashboardPage.tsx:625-690`, `task_store.py`).
- **Grounded Q&A in two surfaces** — floating chat widget on every page + inline "Ask about your results" on Results and Dashboard; the Dashboard version scopes answers to that roadmap by passing `role_id`.
- **Generation-mode transparency** — every AI text carries an honest badge: `Personalized from your data` vs `Grounded Pathfinder guidance`.
- **Auth & multi-tenancy** — Supabase email OTP; backend verifies Supabase JWTs via **JWKS (RS256/ES256)** with HS256 transition fallback (`backend/app/auth.py`); user id always from the token `sub`, never the request body; RLS policies on all five tables.
- **Ops** — deploys configured for Vercel (`frontend/vercel.json`) and Railway (`backend/railway.toml`); backend runs without Supabase creds using in-memory stores for tests.

---

## 5. Innovation & differentiation

Positioning (from `docs/uniqueness_report.md`, which includes a competitor scan of CareerExplorer, Coursera, LinkedIn Learning, roadmap.sh, Khan/Khanmigo, Degreed):

1. **Auditable match math.** Every learner sees the actual component scores and weights; no surveyed competitor exposes its scoring (`matching/service.py`, `ResultsPage.tsx`).
2. **Hybrid deterministic-core + validated-LLM architecture.** The LLM can only explain and personalize prose; it cannot create or alter a course, milestone, or skill — schema + ID checks + honesty detectors + deterministic fallback. The team's one-liner: *"The AI explains. The math decides."*
3. **Grounded Q&A over the learner's own results**, unlike open chatbots — the system prompt forbids outside knowledge and instructs the model to say when the data cannot answer.
4. **Honesty engineering as a feature** — attribution and timeline-mismatch detectors (`personalization.py:41-74, 316-356, 474-481`) that reject flattering-but-ungrounded prose are rare even in production LLM apps.
5. **Closed adaptation loop** — telemetry → skill promotion → changed recommendations; most roadmap products are static artifacts.
6. **Scope discipline** — 4 deeply curated roles (RIASEC profile, O*NET-referenced `onet_soc_code`/`onet_reference_url` fields in `roles.v1.json`) instead of 1000 shallow ones; the unused résumé/GitHub enrichment idea was deliberately cut (documented in `PLAN.md` and `uniqueness_report.md` §6).

---

## 6. UX & interface highlights

- Multi-step assessment with progress bar, per-step validation, scroll-to-first-error, and a "Set unrated to 'None'" bulk action (`AssessmentPage.tsx:122-255`).
- Optimistic task toggling with rollback on failure (`DashboardPage.tsx:253-341`).
- Accessibility throughout: `aria-live` regions, `role="alert"` errors, `aria-label`s, sr-only labels in chat, Escape-to-close chat, focus management (`ChatWidget.tsx:30-50`).
- Loading/error states with retry everywhere; `ErrorBoundary` + `Skeleton` components isolate dashboard sections so one failing widget never blanks the page (`frontend/src/components/ErrorBoundary.tsx`, used at `DashboardPage.tsx:443, 522, 632`).
- Roadmap GET-with-auto-POST-on-404 pattern so deep links to `/dashboard/:roleId` just work (`DashboardPage.tsx:139-167`, `DashboardRoute.tsx`).
- Catalog-driven portfolio project brief and resources; all external links curated, no ads.

---

## 7. Engineering quality (honest)

**Strengths**
- **Tests: 77 passed, 1 skipped** in `backend/tests/` (verified by running them; 0.16 s). Coverage includes catalog validation, representative-profile ranking (each of 4 intended roles ranks first for its profile), cosine invariance, profile/match/roadmap/task endpoints, intake mapping + fallbacks, LLM personalization incl. mocked malformed/fabricated outputs, and a regression suite proving Supabase-mode writes never mirror into in-memory stores (`test_store_supabase_isolation.py`).
- **Typing & validation:** strict TypeScript (`tsconfig.app.json` `"strict": true`, `tsc -b` in build), Pydantic models with `extra="forbid"` for all LLM I/O, typed FastAPI responses, 422 details that list missing/unknown question/skill IDs.
- **Security:** JWKS JWT verification, token-derived user ids, RLS on every table, CORS restricted to configured origins, only `.env.example` committed (repo tree is clean; no dist/node_modules tracked).
- **Structure:** clean separation (catalog/matching/stores/personalization), versioned static catalogs, compatibility route aliases, honest commit history (including a documented leaked-JWT-secret → rotation → JWKS migration incident, referenced in `docs/SOLUTION_DOCUMENTATION.md` §6).

**Known gaps / limitations (flagging proactively)**
- `frontend/package.json` declares `"test": "vitest run"` but there are **no frontend test files and vitest is not a dependency** — the script would fail; all automated tests are backend.
- The `recommendations` and `enrichment_events` tables (`20260813000000_initial_schema.sql`) are **unused by current code** — `/match` computes on demand rather than persisting to `recommendations`; enrichment was descoped.
- `docs/SOLUTION_DOCUMENTATION.md` is still an outline, not the final PDF deliverable; `deliverables/Pathfinder-Source-Code.zip` is dated Aug 18 and predates the last ~7 commits; `docs/uniqueness_report.md` and `docs/demo_video_script.md` are untracked in git.
- LLM layer depends on one pinned free-tier model (Llama 3.1 8B); quality of prose is bounded by it — mitigated by validators/fallbacks.
- No vector search/RAG over course content; recommendations are filtered from a 19-course static catalog — deliberate for grounding, but it caps variety.
- `ChatWidget` does not pass `role_id` (only `AskAboutResults` does), so floating-chat answers are scoped to the whole match rather than the open roadmap.
- Four roles only (deliberate, documented); no mobile app.

---

## 8. Suggested demo flow (5 steps)

1. **Landing → conversational intake.** Sign in (seeded OTP-verified account), start the assessment, paste a natural-language goal ("second-year student, enjoys web pages and spreadsheets, 10 hrs/week, job-ready in six months"), click *Pre-fill my assessment* — show the drafted assessment and **edit one answer on camera** ("the learner, not the model, has the final word").
2. **Results with visible math.** Submit; point at the ranked role cards, the 55/35/10 breakdown bars, skill gaps, and the LLM's fit explanation. Kill-switch beat (optional): note every AI text has a fallback badge.
3. **Grounded Q&A.** Open the floating chat; ask "Why is Data Analyst my top match and Frontend second?" — answer cites only this learner's data.
4. **Dashboard + feedback loop.** Explore the top path; check a milestone complete with time=180 min and quiz=70%; show the NEXT BEST ACTION banner change, the skill-promotion toast, and learning-pattern stats; scroll to *Courses for your gaps* and the prerequisite met/missing chain.
5. **Close on the differentiator.** Return to landing: "Every other tool tells you what to learn. Pathfinder shows you the math, then explains it in plain language — the AI can persuade, but it can't decide."

*(A full 3:45 scripted walkthrough with timing, prep checklist, and judge-Q&A one-liners already exists at `docs/demo_video_script.md`.)*
