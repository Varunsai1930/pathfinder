# Pathfinder — Demo Video Script (3:45)

For the Round 2 demo video (requirement: 3–5 minutes covering core functionality, key features, and overall workflow/UX). Written to be delivered by any teammate as-is. Total runtime target: 3 minutes 45 seconds. Rehearse twice before recording.

**The one message to land:** *Every other tool tells you what to learn. Pathfinder shows you the math, then explains it in plain language — the AI can persuade, but it can't decide.*

---

## Before you record — prep checklist

- [ ] Seeded demo account already signed in (email OTP verified) — never do OTP live on camera.
- [ ] Write the demo goal text (below) into a notes window to copy-paste — don't type it fresh.
- [ ] Confirm the backend has a live `OPENROUTER_API_KEY` (test once: results card should show a natural-language explanation).
- [ ] A second browser profile with an account that has **one completed roadmap task** (Week 1 checked) and telemetry filled — used in Segment 5 so progress state is real.
- [ ] Browser: 1440p or higher, zoom 110%, clean profile (no extensions/bookmarks bar), light theme.
- [ ] Close all other tabs and notifications (macOS: Do Not Disturb).
- [ ] Record a dry run first; check audio levels and that cursor focus is visible.

**Demo goal text (copy-paste in Segment 2):**

> I'm a second-year student who enjoys building small web pages and digging through spreadsheet data. I've used HTML a bit and played with Python in class. I have about 10 hours a week and want to be job-ready in six months — but honestly, I'm not sure which role suits me.

---

## SEGMENT 1 — Hook + problem (0:00 – 0:25)

**On screen:** Landing page. Scroll slowly to show hero, then stop.

**Say:**

> "Every student asking 'which tech role is right for me?' gets the same answer: a wall of courses and a generic roadmap. Every learning platform recommends… more of itself.
>
> We built Pathfinder on one principle: **the AI explains, the math decides.** Let me show you what that means."

**Do:** Point at the hero headline — *"The AI can persuade. It can't decide."* — and the example fit-score card with its visible breakdown.

---

## SEGMENT 2 — Conversational goal intake, our front door (0:25 – 1:05)

**On screen:** Click **Start Assessment**. Step 1: "Start With Your Goal."

**Say:**

> "You start with a conversation, not a form. Describe your goal in your own words."

**Do:** Paste the demo goal text into the textarea. Click **Pre-fill my assessment →**. Wait for the draft (2–4 seconds).

**Say:**

> "The AI reads your goal and drafts the entire assessment — your interest leanings, the skills you mentioned, your weekly hours, your timeline. But here's the important part: **it's only a draft.** The language model never touches your actual answers — it produces dimension-level hints, and deterministic code maps them to suggestions that you review and edit."

**Do:** On the next screen, point at the blue notice banner: *"We drafted your assessment from your goal — review and edit anything."* Deliberately **change one interest slider** on camera.

**Say:**

> "I'm changing this answer — because the learner, not the model, has the final word."

---

## SEGMENT 3 — Assessment → transparent match (1:05 – 1:50)

**On screen:** Click through skills (pre-filled where the goal mentioned them) and constraints (hours: 10/week, timeline: 24 weeks, certainty: "Deciding" — all pre-filled). Submit.

**Say:**

> "Under the hood, scoring is fully deterministic: fifty-five percent interest similarity, thirty-five percent skill readiness, ten percent work-style alignment — cosine similarity against four entry-level roles. No black box, no vibes."

**On screen:** Results page. Point at the ranked role cards.

**Say:**

> "And because it's deterministic, every number on this screen is **auditable**. Data Analyst ranks first for this learner — and look, we don't just show the winner: every role shows its score breakdown, confirmed strengths, and the exact core skills still missing."

**Do:** Expand the top card's fit explanation.

**Say:**

> "The AI's only job is to explain the result in plain language — and if it ever fails, times out, or invents something, a deterministic fallback takes over. The product never breaks."

---

## SEGMENT 4 — Ask your own results (1:50 – 2:15)

**On screen:** Open the Q&A widget (bottom-right). Type: **"Why is Data Analyst my top match and Frontend second?"**

**Say:**

> "Learners have questions, so we answer them — grounded strictly in this learner's own computed results. The model can't bring in outside facts; if the data isn't there, it says so."

**Do:** Show the answer appearing. Read one sentence of it aloud.

---

## SEGMENT 5 — Roadmap that reacts to progress (2:15 – 3:05)

**On screen:** Switch to the seeded account with progress. Open the career-path dashboard.

**Say:**

> "Choosing a path is the beginning. Each role becomes five milestones with weekly tasks, a portfolio project, and a next action that updates as you work."

**Do:** Check one task's completion; enter time spent (e.g., 180 minutes) and a quiz score (e.g., 70). Show the **next-action banner** changing.

**Say:**

> "This is the feedback loop: we capture time spent and quiz scores as telemetry, surface your learning patterns, suggest order adjustments when you struggle, and promote skills you've actually demonstrated. The plan adapts to the person — that's the 'understand, plan, achieve' loop the problem statement asks for."

**Do:** Scroll to the **Courses for your gaps** section; point at one course's prerequisite chips.

**Say:**

> "Course recommendations come from our prerequisite-aware catalog — targeted at this learner's specific skill gaps, in dependency order."

---

## SEGMENT 6 — What makes us different (3:05 – 3:45)

**On screen:** Return to the landing page (or a simple slide with the three competitor names).

**Say:**

> "roadmap.sh gives every learner the same map — you pick it yourself. Coursera's quiz recommends courses Coursera sells. CareerExplorer matches you with a proprietary black box.
>
> Pathfinder is the only one where the learner can audit every number on screen: a conversational front door, a deterministic engine, and an AI that is structurally incapable of inventing a course, a milestone, or a skill — every LLM response is schema-validated against the learner's own data, with a deterministic fallback behind it.
>
> **The AI explains. The math decides. That's Pathfinder.**"

**On screen:** Logo / tagline end card. Stop recording.

---

## Map to the problem statement (know this for Q&A)

| Brief requirement | Where it appears in the video |
|---|---|
| 1. Conversational interface for goals | Segment 2 — goal intake |
| 2. Learner profiling engine | Segments 2–3 — drafted, reviewed, persisted profile |
| 3. Recommendation engine | Segment 3 — transparent weighted matching + Segment 5 course catalog |
| 4. Learning path with prerequisites & milestones | Segment 5 — five milestones, prerequisite-aware courses |
| 5. AI assistant explaining recommendations | Segments 3–4 — fit explanations + grounded Q&A |
| 6. Progress & skills dashboard with next actions | Segment 5 — telemetry, adaptation, next-action banner |

## Likely judge questions — one-line answers

- **"Why six roles?"** — Six entry-level paths cover the majority of tech-student intent while every role keeps a validated interest profile, skill taxonomy, milestones, and course set. Depth beats a thousand shallow matches.
- **"What if the LLM hallucinates?"** — It can't reach the data layer: strict Pydantic schemas, ID/subset checks against the learner's real data, skill-attribution and timeline-honesty detectors, deterministic fallback on every failure path. 107 backend tests cover these.
- **"Why not let the LLM generate the whole roadmap?"** — That's exactly what competitors do, and it's unauditable. We split responsibilities: conversation for understanding, deterministic code for decisions, LLM for explanation.
- **"How do recommendations adapt?"** — Task telemetry (time, quiz scores) drives learning-pattern analysis, suggested order adjustments, and skill promotion; the adaptation note recomputes from real task state.
- **"What's the RIASEC grounding?"** — An 18-item Holland-code-aligned interest instrument, normalized per dimension and matched by cosine similarity against each role's validated target profile.

## Delivery notes for the presenter

- Slow down on the two bolded lines — they are the differentiator and the judges' takeaway.
- If the LLM is slow on camera: keep talking about the deterministic core; the wait itself demonstrates the fallback design ("and if this takes too long, we don't block the learner").
- If the pre-fill returns the fallback draft (empty): say "the AI layer is optional by design — watch the assessment work perfectly without it," continue manually, and re-record the segment later.
- Never apologize on camera; every degraded state in this product is a designed, speakable feature.
