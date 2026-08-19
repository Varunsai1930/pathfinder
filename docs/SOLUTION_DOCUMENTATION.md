# Pathfinder — Solution Documentation Outline

Working outline for the Round 2 Solution Documentation (PDF/PPT). Fill each section with the final write-up; do not submit this markdown file as the deliverable.

## 1. Problem understanding

- Audience: Indian tech students choosing an entry-level path under time and information constraints.
- Core problem: students get generic “learn everything” advice instead of a grounded, role-specific next step.
- Scope: four roles only (Frontend, Backend, Data Analyst, Cloud/DevOps) so recommendations stay evidence-backed.
- Out of scope (and why): résumé/GitHub enrichment; replacing the structured assessment with open-ended chat intake.

## 2. Solution approach

- Structured interest-exploration assessment (18 RIASEC-aligned statements) plus skill confidence and work-style constraints.
- Deterministic matching: 55% interest similarity, 35% skill readiness, 10% work-style alignment.
- Transparent score breakdown, missing core skills, and ranked alternatives — not a single opaque “best job” claim.
- Selected-role dashboard: five milestones, weekly plan, project brief, task checklist, next action.
- Design choice to document: structured intake keeps scoring auditable; a later contained Q&A feature answers learner queries against already-computed results rather than inventing a chatbot intake.

## 3. System architecture

- Frontend: React + Vite + TypeScript, deployed on Vercel.
- Backend: FastAPI, deployed on Railway.
- Auth/data: Supabase Auth (email OTP) + Postgres with RLS.
- Static catalog: versioned JSON in `backend/app/catalog/` (roles, assessment, skills, milestones).
- Auth model: backend verifies Supabase JWTs (JWKS) and derives `user_id` from the token.
- Persistence: `profiles`, `recommendations`, `roadmaps`, `tasks`.
- Include a simple diagram: browser → FastAPI → Supabase; catalog files on the API host.

## 4. AI/ML techniques

- Current: deterministic vector similarity and weighted skill scoring (no black-box ranking).
- Planned/partial: constrained LLM personalization for `fit_explanation`, weekly pacing, and `adaptation_note`, with Pydantic validation and a deterministic fallback.
- Planned: contained Q&A over the user’s own match/roadmap payload — not an open-ended tutor.
- Be explicit about what is *not* ML: the four-role ranking itself.

## 5. Key features and workflows

1. Sign in → assessment (interests, skills, constraints) → persist profile.
2. Match → ranked cards with fit breakdown, reasons, and gaps.
3. Select a path → roadmap dashboard → complete tasks → next action updates.
4. Privacy: no anonymous profiles; enrichment sources (if ever added) would require explicit approval.

## 6. Challenges faced

- Security: leaked legacy JWT secret found during development; rotated keys, migrated to JWKS verification, disabled legacy secrets, and re-verified isolation live. Write this up honestly.
- Matching bug: magnitude-sensitive similarity replaced with cosine similarity; confirmed_skills / missing_skills overlap caught and fixed.
- Round 2 brief arrived mid-build (team size, five deliverables, judging weights); scope was cut (enrichment) so documentation and demo could finish.

## 7. Demo script hooks (for the video)

- Landing + privacy one-liner.
- Assessment in under a minute (pre-seeded answers if needed).
- Results: point at the score breakdown, not just the winner.
- Dashboard: complete one task, show next action changing.
- Mention fallback: the product still works if the LLM is unavailable.
