# PathFinder v3 — Plan (Post Round-2-Brief Discovery)

**Status as of Aug 16, evening.** This revision folds in the actual Round 2 requirements (only just discovered today, six days into the build) — team size, real deliverables, judging weights, and the official problem brief. Effective working deadline is **Aug 25** (your exams start Aug 27), not the platform's Aug 31 cutoff.

## What changed today, and why

- Discovered the Round 2 dashboard requires **5 deliverables**, not 3. Two are entirely new: a Source Code ZIP, and a Solution Documentation PDF/PPT.
- Discovered **team size 3–5, same college** is a hard requirement. Currently solo.
- Discovered actual **judging weights** — Functionality 25%, AI/ML 20%, Problem Understanding 20%, Innovation 15%, UX 10%, Code Quality 10%. UX being only 10% confirms today's visual polish pass was enough; further design time isn't well spent.
- The official brief's "what to build" list includes a conversational intake and a query-answering assistant. Pathfinder's structured-assessment design deliberately doesn't do the former — decision: document that rationale rather than rebuild the intake. The latter (answering learner queries) is a real, addressable gap — decision: build a small, contained Q&A feature.
- **Cut:** résumé/GitHub enrichment (Aug 19 in prior plans). Two new hard-required deliverables plus teammate recruiting outweigh an optional feature that was never in the official brief.

## ✅ Already done (Aug 13–16)

- Skeleton, Supabase auth (email OTP), deployed live on Vercel + Railway from day one.
- Four curated roles, 18-question RIASEC assessment, skill taxonomy.
- Deterministic matching: cosine similarity (fixed from a magnitude-sensitive bug), 55/35/10 weighting, verified healthy score margins across four representative profiles.
- **Security incident fully resolved:** leaked legacy JWT secret found and rotated; backend migrated to JWKS-based asymmetric verification; all Supabase keys upgraded to the current publishable/secret key system; legacy keys disabled and the leaked secret revoked; every step re-verified live post-change. (This is genuinely strong material for the "challenges faced" section of the Solution Documentation — write it up honestly.)
- Assessment UI, results UI, `POST /profile`, `POST /match` — full core loop working live, cross-user isolation verified, confirmed_skills/missing_skills overlap bug caught and fixed.
- Roadmap + task system: `roadmaps`/`tasks` tables, `POST`/`GET /roadmaps/{role_id}`, `PATCH /tasks/{task_id}` with correct next-action progression — verified live.
- Career Path Dashboard UI, wired to real data.
- Full visual redesign: light theme, blue primary / green-for-success-only accent system, applied consistently across all pages. Login/Signup pages added. Committed and deployed.

## 🔴 Do this in parallel, starting now — not a calendar slot

**Find 2–4 teammates from CVR College of Engineering.** This is the single highest-risk open item — a hard compliance rule, not a feature. Best candidates: someone who can own the Solution Documentation deck or demo video, since those are entirely unstarted and don't require touching the codebase. Doesn't block the sequence below, but don't let it slide past Aug 18–19 — you'll need to divide remaining work once someone's in.

## Remaining Delivery Sequence (Aug 17 → Aug 25)

1. **Aug 17 — LLM personalization layer.** `fit_explanation` (2-3 sentences), LLM-personalized weekly plan referencing only real milestones, `adaptation_note`. Strict Pydantic validation; automatic fallback to the existing deterministic plan on any malformed/invented/timeout/error case. Pin a specific cheap, fast, structured-output-capable model (check OpenAI's current model docs directly, not aggregator sites — confirm before wiring in). Deploy, verify live with a real curl showing `generation_mode: "llm"`.

2. **Aug 18 — Small Q&A feature.** A contained "Ask about your results" input on the Results or Dashboard page. Backend endpoint that answers a free-text question using only the user's already-computed match/roadmap data — same validation-and-fallback discipline as the personalization layer, not an open-ended chatbot. This directly satisfies the brief's "answers learner queries" requirement using infrastructure already built the day before.

3. **Aug 19 — Repository cleanup + ZIP prep.** Remove stray Round 1 ML-challenge files from the repo root (mask_signature.py, tfidf_param_signature.py, etc. — flagged earlier, never cleaned up). `.gitignore` and untrack `node_modules`. Confirm README has real setup/execution instructions. Prepare the Source Code ZIP deliverable directly from the cleaned repo. Start outlining Solution Documentation structure.

4. **Aug 20 — Final polish + start Solution Documentation.** Audit empty/loading/error states across all pages (per original test plan, never explicitly re-verified after the theme change). Accessibility pass. Theme toggle only if genuinely low-risk time remains — not a priority given UX is 10% of judging. Draft Solution Documentation: problem understanding, solution approach, system architecture, AI/ML techniques used, key features/workflows, and challenges faced (the JWT incident belongs here).

5. **Aug 21 — Production hardening + full test plan execution.** Re-run the original test plan explicitly: signed-out API calls fail, cross-user isolation on every table (re-verify post key-rotation), RLS policies confirmed on all tables, CORS locked to production origins only, seeded demo account works end-to-end, mobile + desktop pass on the live deployed app.

6. **Aug 22 — Finish Solution Documentation; write demo video script.** Finalize the PDF/PPT. Write a script covering the 3-5 minute demo requirement (core functionality, key features, overall workflow/UX) — script first, don't improvise the recording.

7. **Aug 23 — Record and edit the demo video.**

8. **Aug 24 — Buffer.** Fix anything found during a full rehearsal walkthrough. Package all five deliverables together and check each against the platform's literal checklist. Confirm teammate access/contributions are reflected if a team was formed.

9. **Aug 25 — Submit.** All five deliverables: Source Code ZIP, GitHub repo link, Solution Documentation, demo video, live application URL. Do not wait for Aug 31.

## Explicitly cut / not building

- **Résumé and GitHub profile enrichment** (previously Aug 19). Optional in the original PathFinder design, not required by the official brief, and outweighed by two new hard-required deliverables plus team recruiting.
- **Conversational/natural-language intake** replacing the structured assessment. Deliberately not built — document the rationale in Solution Documentation: structured input keeps scoring transparent, auditable, and free of hallucination risk, which is core to the "evidence, not guesswork" positioning.

## Judging weights — what this means for remaining time

| Category | Weight | Where this shows up |
|---|---|---|
| Functionality & Feature Completeness | 25% | Core loop (done), roadmap/tasks (done), Q&A (Aug 18) |
| AI/ML Implementation | 20% | LLM personalization (Aug 17) + Q&A (Aug 18) — real weight, prioritize accordingly |
| Problem Understanding & Solution Design | 20% | Solution Documentation must clearly justify design choices, including the intake/Q&A tradeoff |
| Innovation & Creativity | 15% | Transparent scoring breakdown, deterministic fallback design |
| User Experience & Interface | 10% | Already solid post-redesign — don't over-invest further |
| Performance & Code Quality | 10% | Aug 21 hardening pass, clean repo for the ZIP |

## Required deliverables (confirmed from Round 2 dashboard)

1. **Source Code (ZIP file)** — complete source, no venvs/build artifacts/large dependency folders, README with setup + execution instructions.
2. **Source Code Repository** — GitHub link, accessible to evaluators, commit history reflecting real development process (already true).
3. **Solution Documentation** — PDF/PPT: problem understanding, solution approach, system architecture, AI/ML techniques, key features/workflows, challenges faced.
4. **Demo Video** — 3–5 minutes: core functionality, key features, overall workflow and UX.
5. **Application Access** — deployed URL (have this) or clear local setup instructions if not deployed.

## Assumptions (updated)

- Effective working deadline is **Aug 25**, driven by the person's exam schedule starting Aug 27 — not the platform's Aug 31 cutoff, which offers no real benefit given the exam constraint.
- Team formation is in progress; this plan assumes solo execution continues unless/until teammates join, at which point work should be redivided toward the two currently-unowned deliverables (documentation, video).
- Codex/AI coding budget remains the binding constraint on remaining scope, not calendar time — decisions above are made accordingly.
