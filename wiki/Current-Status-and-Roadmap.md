# Current Status and Roadmap

BattleBelief is developed through explicit milestones. Each milestone separates implementation progress from evidence, capability, strength, release, and MVP claims.

## Current status

**Active milestone: M1 — Protocol-safe Prototype**

Implemented on `main`:

- immutable canonical battle events;
- deterministic visible-state reduction;
- normalized decision requests;
- conservative safe submission sets;
- request reconciliation and freshness checks;
- deterministic heuristic action selection;
- independent action and `rqid` safety validation;
- room-preserving Showdown frame decoding;
- strict protocol parsing;
- request reading and command encoding;
- packed-team loading;
- authenticated Showdown WebSocket connectivity;
- request-driven single-room `BattleSession` execution;
- direct Gen 9 OU challenge coordination;
- a secrets-safe outgoing challenge CLI.

Still incomplete for M1:

- acceptance smoke tests;
- atomic version and capability activation;
- final milestone evidence;
- controlled repeatability evidence for the complete direct-battle path.

The repository therefore does **not** currently claim:

- public ladder readiness;
- battle strength or parity with strong agents;
- belief-system completion;
- information-set search completion;
- training-system completion;
- a stable release;
- MVP status.

## Milestone overview

### M0 — Public project foundation

Establish the public Apache-2.0 repository, documentation governance, contracts, schemas, CI, security controls, package boundaries, and separately installable Python packages.

### M1 — Protocol-safe prototype

Deliver a safe heuristic Gen 9 OU runtime with Showdown authentication, canonical events, deterministic state, authoritative legal actions, fixed teams, classified failures, and a controlled direct-battle path.

A completed M1 demonstrates protocol and safety behavior. It does not demonstrate playing strength.

### M1.5 — Measurement harness and baseline registration

Freeze the research questions, evaluation arms, budget profiles, pool-construction rules, decision-record schema, reproducibility requirements, and stop-or-pivot criteria before major search implementation.

This milestone exists to prevent retrospective metric selection and uncontrolled experimental expansion.

### M2 — Engine-qualified search prototype

Planned work includes:

- a local Pokémon Showdown oracle;
- a qualified Gen 9 simulation engine;
- capability manifests and fail-closed eligibility;
- differential testing;
- deterministic benchmark and live-anytime modes;
- a minimal determinization-search baseline;
- an evaluation-only closed-world world distribution;
- `information_set_duct_v0` search.

Search must be compared against the M1 heuristic and simpler baselines under registered CPU and wall-time budgets.

### M3 — Open-world belief and research baseline

Planned work includes:

- a versioned meta snapshot;
- replay and dataset ingestion;
- complete hidden-set hypotheses;
- positive open-world `OTHER` mass;
- controlled hypothesis materialization;
- calibration and coverage evaluation;
- open-world search arms;
- optional simple model baselines only after intermediate gates pass.

Belief quality and battle utility are evaluated separately. Better calibration alone does not automatically justify more complexity.

### M4 — MVP candidate selection

Potential components include replay behavior cloning, search teachers, population self-play, hybrid models, and external baseline comparisons.

Exactly one candidate must be selected through the predefined evaluation process before the release holdout is opened.

### M5 — Strength-qualified MVP

Only M5 may be called the BattleBelief MVP. It requires a sealed evaluation, fixed ruleset snapshot, sealed teams, qualified safety fallback, public CPU runtime, and the complete strength-qualification gate.

### M6 — External human validation

A separate post-MVP phase for human or ladder validation. M6 does not retroactively form part of M5.

## Later phases

### Phase 2 — Optimization

Possible work includes larger models, broader self-play, alternate bandit or regret methods, deeper or more selective search, cross-battle priors, inference optimization, and wheel distribution.

Each additional layer must improve strength or reduce a predefined resource while preserving non-inferiority.

### Phase 3 — Offline team-building

A separate team-generation system with team-disjoint evaluation. Team improvement and battle-policy improvement must not be mixed into one claim.

### Phase 4 — Additional Singles formats

Formats may be added one at a time with new ruleset, target-population, capability, and strength artifacts. Doubles and VGC remain outside scope.

## How to interpret project claims

| Statement | What it means |
|---|---|
| CI is green | Repository integration and contract checks passed |
| M1 is complete | The protocol-safe heuristic runtime passed its evidence gates |
| Search is implemented | Search code exists; this alone says nothing about benefit or qualification |
| M5 is complete | The sealed strength-qualification process passed and an MVP claim is permitted |

Implementation, qualification, evaluation, release, and strength are deliberately separate concepts in this project.
