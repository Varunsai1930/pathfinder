# Pathfinder — Solution Documentation Outline

Working outline for the Round 2 Solution Documentation (PDF/PPT). Fill each section with the final write-up; do not submit this markdown file as the deliverable.

Positioning statement (use verbatim in the deck and demo): **"Every other tool tells you what to learn. Pathfinder shows you the math, then explains it in plain language — the AI can persuade, but it can't decide."** Short form: *The AI explains. The math decides.*

## 1. Problem understanding

- Audience: Indian tech students choosing an entry-level path under time and information constraints.
- Core problem: students get generic “learn everything” advice instead of a grounded, role-specific next step.
- Scope: six entry-level roles (Frontend, Backend, Data Analyst, Cloud/DevOps, Security Analyst, Data Engineer) so recommendations stay evidence-backed.
- Out of scope (and why): résumé/GitHub enrichment.

## 2. Solution approach

- Conversational front door: the learner describes their goal in natural language (`POST /api/v1/intake`); the LLM returns dimension-level hints that deterministic code maps into editable assessment pre-fill — the learner reviews and edits every answer before anything is scored.
- Structured interest-exploration assessment (18 RIASEC-aligned statements) plus skill confidence and work-style constraints.
- Deterministic matching: 55% interest similarity, 35% skill readiness, 10% work-style alignment.
- Transparent score breakdown, missing core skills, and ranked alternatives — not a single opaque “best job” claim.
- Selected-role dashboard: five milestones, weekly plan, project brief, task checklist, next action.
- Contained Q&A feature answers learner queries against already-computed results rather than an open-ended chatbot.
- Design rationale: conversation for understanding, structure for auditability — the LLM drafts, the learner confirms, the deterministic engine decides.

## 3. System architecture

- Frontend: React + Vite + TypeScript, deployed on Vercel.
- Backend: FastAPI, deployed on Railway.
- Auth/data: Supabase Auth (email OTP) + Postgres with RLS.
- Static catalog: versioned JSON in `backend/app/catalog/` (roles, assessment, skills, milestones, courses).
- Auth model: backend verifies Supabase JWTs (JWKS) and derives `user_id` from the token.
- Persistence: `profiles`, `recommendations`, `roadmaps`, `tasks`.
- Include a simple diagram: browser → FastAPI → Supabase; catalog files on the API host.

## 4. AI/ML techniques

- Deterministic vector similarity and weighted skill scoring (no black-box ranking).
- Constrained LLM personalization for assessment pre-fill hints (`/intake`), `fit_explanation`, weekly pacing, and `adaptation_note`, with strict Pydantic validation, ID/subset checks, and a deterministic fallback on every failure path.
- Contained Q&A over the user’s own match/roadmap payload — not an open-ended tutor.
- Be explicit about what is *not* ML: the four-role ranking itself.

## 5. Key features and workflows

1. Sign in → describe your goal in plain words (or skip) → review the pre-filled assessment (interests, skills, constraints) → persist profile.
2. Match → ranked cards with fit breakdown, reasons, and gaps.
3. Select a path → roadmap dashboard → complete tasks → next action updates.
4. Privacy: no anonymous profiles; enrichment sources (if ever added) would require explicit approval.

## 6. Challenges faced

- Security: leaked legacy JWT secret found during development; rotated keys, migrated to JWKS verification, disabled legacy secrets, and re-verified isolation live. Write this up honestly.
- Matching bug: magnitude-sensitive similarity replaced with cosine similarity; confirmed_skills / missing_skills overlap caught and fixed.
- Round 2 brief arrived mid-build (team size, five deliverables, judging weights); scope was cut (enrichment) so documentation and demo could finish.
- LLM honesty engineering: attribution and timeline-mismatch detectors in `personalization.py` that reject generated prose which claims unconfirmed skills or ignores an infeasible schedule.

## 7. Demo script hooks (for the video)

Full script: `docs/demo_video_script.md`.
- Landing + the positioning one-liner.
- Conversational goal → pre-filled assessment draft → edit one answer on camera.
- Results: point at the score breakdown, not just the winner.
- Dashboard: complete one task, show next action changing.
- Mention fallback: the product still works if the LLM is unavailable.
