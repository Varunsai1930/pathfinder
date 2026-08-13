# Pathfinder role catalog

`roles.v1.json` is the versioned source of truth for Pathfinder's four supported student career paths.

## What is grounded

Each path points to a closest O*NET occupation and its current O*NET OnLine summary page. O*NET is used for occupational framing and the RIASEC interest model—not for Indian salary, hiring, or placement claims.

| Pathfinder path | O*NET reference |
| --- | --- |
| Frontend Developer | Web Developers (`15-1254.00`) |
| Backend Developer | Software Developers (`15-1252.00`) |
| Data Analyst | Business Intelligence Analysts (`15-2051.01`) |
| Cloud/DevOps Engineer | Network and Computer Systems Administrators (`15-1244.00`) |

## What Pathfinder curates

- The four student-facing role labels.
- Normalised RIASEC and work-style target vectors used by the future matching engine.
- Skills, five ordered milestones, practical tasks, portfolio projects, and resources.

These fields are original product curation. They must not be presented as official O*NET scores, a validated assessment, Indian labour-market data, or a guarantee of job readiness.

## Assessment contract

`assessment.v1.json` contains the profile questions and the one shared skill taxonomy. It supplies exactly 18 original interest-exploration prompts—three per RIASEC dimension—and a five-point agreement scale. The UI will send answers as one-to-five integers; a later matching service will aggregate each dimension before it compares the profile with a role's curated target vector.

Every skill required by a role must exist in this taxonomy. The user-facing skill confidence choices will be added with the profile endpoint, so the labels and scoring semantics remain in one place rather than being duplicated in the UI.

## Roadmap contract

Each role has exactly five original milestones. They are ordered with `sequence`, each carries a bounded effort estimate, and the first four milestones introduce every core skill before the fifth portfolio stage asks the learner to demonstrate it. The future pacing service will convert these fixed estimates into calendar weeks using the user's available hours; it must never invent a sixth milestone or a resource outside the catalog.

## Update rule

When changing role content, keep the schema validation passing, review each linked source, record the source year in `grounding.source_updated`, and increment `schema_version` only for a breaking shape change.
