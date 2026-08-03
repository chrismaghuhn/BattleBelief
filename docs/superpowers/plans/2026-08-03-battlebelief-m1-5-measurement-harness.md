---
document_id: plan-m1-5-measurement-harness
title: BattleBelief M1.5 Measurement Harness and Baseline Registration Implementation Plan
document_type: roadmap
status: proposed
normative: false
version: 1
applies_to:
  - repository
  - gen9ou
  - research
effective_from: 2026-08-03
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-03
---

# M1.5 Measurement Harness and Baseline Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze a machine-checkable, reproducible measurement harness and a
formal baseline-registration boundary for the M1 protocol-safe runtime without
implementing Search, Belief, an Oracle, an engine adapter, training, or a new
runtime release.

**Architecture:** Registration is an immutable pre-experiment specification;
an Evaluation Arm Binding is a later, separately versioned attachment of
validated implementation and environment digests. Public Decision Records are
created in the Core from explicit projections, emitted through a Core
`TraceSink`, and consumed by Runtime telemetry or Lab evaluation code without
exposing private opponent information. The Lab harness generates identities,
budgets, seeds, pool partitions, and schedules, but it does not execute
Search or create concrete evaluation pools.

**Tech Stack:** Python 3.12–3.14, immutable dataclasses, JSON Schema
Draft 2020-12, the repository's RFC 8785 canonicalization profile, SHA-256,
`pytest`, Ruff, mypy, and the existing repository contract tools.

---

## Authority and non-goals

This plan operationalizes, but does not redefine, the following accepted
sources:

- [M1.5 in the roadmap](../../roadmap/milestones.md);
- [research strategy and experiment sequence](../../roadmap/research-strategy-and-experiments.md);
- [manifest schema and canonicalization contract](../../contracts/manifest-schemas.md);
- [determinism contract](../../contracts/determinism.md);
- [provenance contract](../../contracts/provenance.md);
- [evaluation metrics](../../evaluation/metrics.md);
- [target population](../../evaluation/target-population.md);
- [pool separation](../../evaluation/pool-separation.md); and
- [statistical analysis](../../evaluation/statistical-analysis.md).

The following remain explicitly outside every M1.5 task and PR:

- Determinization Search, Information-Set DUCT, or any other Search execution;
- productive or evaluation-only Belief implementation;
- local Pokémon Showdown Oracle or `poke-engine` integration;
- replay ingestion, dataset generation, training, self-play, or model inference;
- concrete Selection or Release Holdout contents;
- public Ladder automation or a public-network smoke;
- changing Runtime version `0.2.0`, Runtime phase `M1`, or the M1 Doctor output;
- new format, generation, Doubles, or VGC abstractions; and
- strength, parity, MVP, release, or ladder claims.

The normative owner of each definition remains singular. New documents link to
the owner instead of copying metric definitions, statistical thresholds,
package boundaries, safety rules, or M5 gates.

## PR and task boundaries

Each task starts from the merged `main` of its predecessor. The first task is
the present plan-only PR. Later tasks are intended to be separate, focused PRs
with the following maximum write scopes:

| Task | Purpose | Primary write scope |
| --- | --- | --- |
| 16 | This implementation plan | `docs/superpowers/plans/2026-08-03-battlebelief-m1-5-measurement-harness.md` |
| 17 | Registration and arm-binding schemas | `schemas/manifests/`, `schemas/examples/`, `docs/contracts/manifest-schemas.md`, schema-contract tests and validation tooling |
| 18 | Decision Records and public projections | `schemas/records/`, `schemas/examples/`, Core records/projections and Core tests |
| 19 | TraceSink and M1 runtime integration | Core trace port, Runtime telemetry/testing adapters, `BattleSession`, and focused Runtime tests |
| 20 | Deterministic Lab harness | Lab evaluation modules and Lab tests |
| 21 | Formal registration and heuristic binding | `registrations/gen9ou/` and registration validation tests |
| 22 | M1.5 acceptance evidence | M1.5 audit, relevant documentation links, evidence tests, and measured repository output |

No task may silently absorb a file from a later task. If an integration
discovery requires a scope change, stop, record the reason in the PR, and
obtain maintainer approval before editing another task's area.

## Maintainer decisions required before implementation

The coding agents must not choose these values from experiment outcomes. The
maintainer selects one option for each item before Task 17, Task 18, Task 20,
or Task 21 freezes an artifact. The selected option, rationale, and version are
then recorded in the applicable registration or contract change; the original
registration cannot be rewritten after results are observed.

### Decision A: Decision-Record byte contract

**Question:** Which bytes are hashed for public Decision Records?

1. **Reuse JCS profile v1 (recommended):** validate the record, serialize with
   the existing RFC 8785 implementation, hash UTF-8 bytes without a trailing
   newline, and publish the same `sha256:<64 lowercase hex>` form. This gives
   one canonicalization rule and reuses existing cross-platform vectors.
2. **Separate versioned encoder:** define a Decision-Record encoder with its
   own `$id`, byte vectors, and digest prefix. This can reduce dependency
   coupling but creates a second canonicalization contract that must be
   maintained independently.
3. **Canonical bytes without a digest in Core:** let Core emit a specified
   public projection and let Lab hash it. This keeps Core smaller but weakens
   the guarantee that every producer uses the same digest boundary and is
   therefore acceptable only if a single shared encoder port is added first.

### Decision B: Near-Duplicate team rule

**Question:** When do complete teams belong to one logical cluster?

1. **Canonical exact-team cluster (recommended for M1.5):** canonicalize the
   complete six-member packed-team structure, including order-independent
   member identity and explicitly defined moves/items/abilities, and assign
   identical canonical forms to one cluster. This is deterministic and avoids
   an unvalidated similarity metric, but it does not group semantically close
   teams.
2. **Ruleset-aware similarity cluster:** define a versioned distance over
   species, items, abilities, moves, EVs, and tera types, then apply a fixed
   threshold and deterministic clustering algorithm. This captures near
   duplicates but requires a stronger domain rule and more test vectors.
3. **Maintainer-supplied cluster labels:** accept precomputed cluster IDs only
   when a versioned classifier digest and complete input manifest accompany
   them. This separates classification from the harness but requires a future
   classifier artifact before concrete pools exist.

### Decision C: Budget calibration

**Question:** How is the pre-registered Search-work budget selected without
looking at action quality or battle results?

1. **Outcome-blind calibration grid (recommended):** freeze a finite ordered
   work grid and a calibration-state digest; choose the largest value whose
   measured runtime remains inside the deployment budget on the reference
   environment. The calibration may inspect only runtime and resource
   measurements, never action quality, wins, or holdout rows.
2. **Fixed budget value:** freeze an explicit number of transitions,
   simulations, or nodes before any calibration run. This is easiest to audit,
   but it may underuse the reference hardware or exceed the deployment limit.
3. **Hardware-normalized budget profile:** freeze a benchmark procedure and
   normalize work to a reference CPU profile. This is portable but adds a
   platform-normalization contract and must not become a post-result tuning
   loop.

Deployment Utility always uses the same maximum end-to-end wall-time and CPU
budget for the compared arms. Mechanism Ablation uses the selected Search-work
rule and reports world-distribution, Belief, orchestration, and total costs
separately. The M5 two-second p95 and five-second hard-cutoff values are only
referenced as future targets; M1.5 does not claim to satisfy M5.

### Decision D: Stop and pivot gates

**Question:** What quantitative result permits additional complexity?

1. **Effect-size plus uncertainty gate (recommended):** require a
   pre-specified minimum improvement in the primary registered metric and a
   pre-specified confidence bound, with technical failure rates reported as
   full outcomes. This supports a clear go/no-go rule but requires the
   maintainer to choose estimands and margins before the comparison.
2. **Non-inferiority/resource gate:** permit a more complex arm only if it is
   non-inferior within a fixed margin and improves a pre-registered resource
   metric. This is suitable when a method trades quality for speed, but the
   non-inferiority margin must be frozen before results.
3. **Sequential evidence gate:** require a fixed number of independent
   matchup clusters and then apply a single pre-registered decision rule. This
   is easy to schedule, but its power and uncertainty must be established by
   the statistical-analysis contract and cannot be adjusted after inspection.

The chosen gate must distinguish Search utility, Belief calibration, and model
utility. A null result is recorded as evidence and does not authorize silently
changing the hypothesis, pool, metric, or threshold.

## Task 16: publish this plan as a plan-only PR

**Files:**

- Create: `docs/superpowers/plans/2026-08-03-battlebelief-m1-5-measurement-harness.md`
- Do not modify: schemas, manifests, package source, Runtime status, or tests

The Task 16 PR must contain only this plan. Before opening it:

- [ ] Verify the branch starts at the current merged `main`.
- [ ] Verify the plan has valid document frontmatter and repository-relative
  links.
- [ ] Search the plan for placeholder markers and remove every unresolved
  marker before committing.
- [ ] Confirm the plan names all seven task boundaries, all required files,
  all four maintainer decisions, M2 exclusions, and the final gate list.
- [ ] Run `uv run python tools/check_docs.py`.
- [ ] Run `uv run python tools/check_architecture.py`.
- [ ] Run `uv run python tools/check_schemas.py`.
- [ ] Inspect `git diff --check` and the complete staged diff.
- [ ] Open a Draft PR; do not mark it Ready for review or merge it in this
  task.

**Acceptance criteria:** The document is the only changed tracked file; its
frontmatter is accepted by the documentation checker; every later task has a
concrete file/test/acceptance boundary; and no M1.5 implementation artifact or
M2 code exists in the PR.

## Task 17: registration and evaluation-arm schemas

**Files:**

- Create: `schemas/manifests/experiment-registration.schema.json`
- Create: `schemas/manifests/evaluation-arm-binding.schema.json`
- Create: `schemas/examples/experiment-registration.example.json`
- Create: `schemas/examples/evaluation-arm-binding.example.json`
- Modify: `docs/contracts/manifest-schemas.md` with a new version and entries
  for both schemas, their `$id` values, validation order, and evolution rules
- Create: `tests/tooling/test_m15_registration_schemas.py`
- Modify: `tools/check_schemas.py` only if cross-schema example validation needs
  a named check; keep the existing canonicalization checks unchanged

The schemas must use Draft 2020-12 and project URNs. Every object rejects
unknown properties. Every manifest carries `schema_version`, a stable
`registration_id` or binding identity, and explicit contract references.

`experiment-registration` is the pre-experiment artifact. It contains:

- central hypothesis and named null hypotheses;
- a unique ordered list of Evaluation Arm IDs;
- policy kind, Search algorithm ID, and world-distribution/Belief mode per arm;
- a unique ordered comparison list whose arm references resolve exactly;
- metric IDs and document versions, without copying metric definitions;
- deployment and mechanism budget profiles;
- pool construction, near-duplicate, side, and schedule rules;
- stop/pivot rules with the selected decision version; and
- `holdout_status: "unopened"` with no concrete artifact digests.

`evaluation-arm-binding` is the post-implementation artifact. It contains:

- the immutable `registration_id` and `registration_digest`;
- exactly one registered `arm_id`;
- source, policy, Search, engine, prior, Belief, model, fallback, team-pool,
  opponent-pool, budget, runtime, and contract digests as applicable;
- explicit nulls only for components that the registered arm declares
  inapplicable; and
- a binding status that cannot claim an unimplemented Search or Belief arm.

Schema conditionals and tests must reject:

- duplicate arm IDs or duplicate comparison IDs;
- unknown arm IDs in comparisons;
- an `information_set_duct_*` arm whose Search ID is not
  `information_set_duct_v0`;
- concrete implementation or pool digests in an unsealed registration;
- any Selection or Release Holdout status other than `unopened`;
- missing contract or metric references;
- empty digests, invalid digest shapes, and free placeholder strings;
- a binding without a matching registration digest; and
- a binding that supplies a non-null artifact for an arm that declares it
  inapplicable.

TDD sequence:

- [ ] Add invalid instances for each rejection and run the focused test to
  prove the validator rejects them.
- [ ] Add the two valid examples and run JSON Schema validation.
- [ ] Implement only the schema constraints needed by those tests.
- [ ] Run `uv run python tools/check_schemas.py` and
  `uv run pytest tests/tooling/test_m15_registration_schemas.py -v`.
- [ ] Run `uv run python tools/check_docs.py` after the contract version and
  links are updated.

**Acceptance criteria:** Both artifacts validate through the repository schema
gate; cross-field identity and arm rules are tested; the contract is the only
normative owner of the new schema list; and no concrete pool or implementation
artifact is represented as already existing.

## Task 18: Decision Record schema and canonical public projections

**Files:**

- Create: `schemas/records/decision-record.schema.json`
- Create: `schemas/examples/decision-record.example.json`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/records/__init__.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/records/decision_record.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/records/public_projection.py`
- Modify: `packages/battlebelief-core/src/battlebelief_core/domain/__init__.py`
  only for the public record exports
- Create: `packages/battlebelief-core/tests/domain/records/test_decision_record.py`
- Create: `packages/battlebelief-core/tests/domain/records/test_public_projection.py`
- Create: `tests/contracts/test_decision_record_contract.py`

The selected byte contract from Decision A must be recorded before coding. The
record schema is versioned and contains exactly the public fields required by
the research strategy:

```text
record_schema_version
record_id
record_status
request_identity
observed_state_digest
safe_submission_set_digest
selected_submission
submission_provenance
fallback_or_error_class
policy_or_arm_id
runtime_and_contract_digests
```

The status enum is:

```text
submitted
wait_noop
policy_rejected
action_gate_rejected
send_failed
aborted_before_selection
```

`selected_submission` is nullable and is populated only after a candidate has
been selected. `fallback_or_error_class` is a stable code or null; exception
messages are never serialized. The record has no password, assertion,
packed-team content, room secret, private opponent request, sampled hidden
world, absolute path, hostname, wall-clock timestamp, or unbounded free-form
payload.

`public_projection.py` must expose explicit, immutable projections for:

- `ObservedState`;
- `RequestIdentity`;
- `SafeSubmissionSet`; and
- `BattleSubmission`.

Projection rules are explicit: sort all sets and mapping keys, preserve list
order only where it is semantically public, use normalized scalar values, and
encode only documented fields. Digest functions must never call `hash()`,
`repr()`, `str(dataclass)`, UUID generation, or the current clock. They must
return stable bytes and `sha256:` digests under Python 3.12, 3.13, and 3.14.

TDD sequence:

- [ ] Add cross-version fixture vectors and a leakage test that fails if any
  forbidden secret, hidden-state, path, or host token appears.
- [ ] Add tests proving equivalent public objects produce identical bytes and
  digest, while changes to each public field change the digest.
- [ ] Add tests proving set-order and mapping-order variations canonicalize
  identically where the contract declares them unordered.
- [ ] Add tests proving the record is immutable and rejects unknown or
  non-public fields.
- [ ] Implement the record dataclass, projections, canonical bytes, and digest
  helpers against the selected byte contract.
- [ ] Run the focused Core and contract tests, then `uv run python
  tools/check_schemas.py`.

**Acceptance criteria:** The Decision Record is schema-valid, public-only,
immutable, deterministic across the supported Python versions, and compatible
with the repository digest format. No Search, Belief, engine, or data system
is introduced.

## Task 19: TraceSink and M1 runtime integration

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/ports/trace_sink.py`
- Modify: `packages/battlebelief-core/src/battlebelief_core/ports/__init__.py`
  for the public port and null implementation
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/telemetry/__init__.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/telemetry/jsonl_decision_trace.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/testing/in_memory_trace_sink.py`
- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/composition/battle_session.py`
  to accept an injected sink with a no-op default
- Create or modify: focused Core port, Runtime adapter, and BattleSession tests
  under the existing package test trees

The Core port accepts a `DecisionRecord` and has no filesystem, WebSocket,
environment, logging, clock, or random dependency. The Runtime JSONL adapter
serializes only the validated public record projection. The in-memory sink is
for deterministic tests and preserves record order without changing records.

The BattleSession integration must record at these boundaries:

```text
fresh request reconciled
→ policy candidate
→ independent ActionSafetyGate
→ command encoding
→ successful socket send
→ submission counters
→ final Decision Record
```

The record for a send failure is `send_failed` and never claims a successful
dispatch. Duplicate requests are suppressed before selection and do not create
a second record. A pending public-state request creates `wait_noop` only when
that is the declared decision outcome, not for every ignored wire line.
Trace failures are surfaced through a typed, classified path and are never
silently discarded; they cannot cause another socket send or change the
selected action.

TDD sequence:

- [ ] Add a failing integration test showing the same synthetic M1 session
  emits one record per fresh accepted request and no record for a duplicate.
- [ ] Add a failing test for a rejected action, a send failure, a wait/no-op,
  and terminal battle abort, checking the exact status and nullability rules.
- [ ] Add a leakage test over JSONL and in-memory output for secrets, private
  opponent data, sampled hidden worlds, paths, and hostnames.
- [ ] Add a two-run test with identical input, policy, and digest inputs that
  compares actions, records, canonical bytes, and digests byte-for-byte.
- [ ] Implement the Core port, Runtime adapters, and narrow BattleSession
  injection.
- [ ] Run focused Core/Runtime integration tests and the existing BattleSession
  suite; then run architecture and package boundary checks.

**Acceptance criteria:** The default public CLI behavior remains unchanged;
the measurement harness can inject a strict sink; no second stream reader is
created; no unvalidated submission is traced as sent; duplicate suppression and
error priority are preserved; and trace output is safe and deterministic.

## Task 20: deterministic Lab measurement harness

**Files:**

- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/__init__.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/budget_profiles.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/seed_families.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/pool_partitioning.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/schedule.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/matchup_blocks.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/registration.py`
- Create: `packages/battlebelief-lab/tests/evaluation/test_budget_profiles.py`
- Create: `packages/battlebelief-lab/tests/evaluation/test_seed_families.py`
- Create: `packages/battlebelief-lab/tests/evaluation/test_pool_partitioning.py`
- Create: `packages/battlebelief-lab/tests/evaluation/test_schedule.py`
- Create: `packages/battlebelief-lab/tests/evaluation/test_registration.py`

The harness produces deterministic plans and identities only. It accepts no
Search implementation, engine transition model, Belief state, replay loader,
model, or network adapter.

Seed namespaces are a closed enum:

```text
search, world, policy, simulator, schedule, side_assignment
```

Seed derivation uses a specified UTF-8 encoding with unambiguous field
boundaries and SHA-256 over `master_seed`, namespace,
`matchup_block_id`, and repetition index. Python's process-randomized
`hash()` is forbidden. The function returns a fixed-width, documented seed
representation and identical inputs produce identical outputs independent of
input-list order.

Matchup block identities contain:

```text
hero_team
opponent_team
opponent_archetype
opponent_policy_checkpoint
side_assignment
schedule_block
seed_family
```

Pool partitioning accepts logical cluster IDs and emits disjoint Development,
Selection, Power Pilot, and Release Holdout labels. In M1.5 no concrete pool
elements are supplied. The API rejects duplicate cluster ownership, cross-pool
near-duplicate membership, and every attempt to open Selection or Release
Holdout before the later permitted milestone.

Schedule generation sorts canonical identities, records balanced side
assignments within each registered block, derives all schedule seeds from the
registered registration digest, and returns a schedule digest. Reordering
input collections without changing their identities cannot silently alter the
schedule.

Budget profiles contain separate Deployment Utility and Mechanism Ablation
views. Calibration can select only from a pre-registered work grid using
runtime/resource observations; it cannot inspect actions, wins, quality
metrics, or holdout rows.

TDD sequence:

- [ ] Add tests for stable seed vectors, namespace separation, field-boundary
  separation, and order-independent plan identities.
- [ ] Add tests for disjoint pool partitions, duplicate cluster rejection,
  unopened Selection/Release Holdout, and immutable registration digests.
- [ ] Add tests for balanced side assignments and stable schedule digests.
- [ ] Add tests for both budget views and outcome-blind calibration inputs.
- [ ] Implement the pure Lab modules with immutable return values.
- [ ] Run focused Lab tests, architecture checks, and the isolated Lab package
  smoke; no public network access is permitted.

**Acceptance criteria:** Identical registered inputs produce identical seed,
block, partition, schedule, and budget identities; pool rules are disjoint and
fail closed; no concrete holdout is opened; and the Lab package remains an
offline M1.5 harness rather than a Search or Oracle package.

## Task 21: formal M1.5 registration and heuristic binding

**Files:**

- Create: `registrations/gen9ou/m1-5-core-comparisons-v1.json`
- Create: `registrations/gen9ou/bindings/heuristic_v0.json`
- Create: `tests/tooling/test_m15_registration_artifacts.py`
- Modify: `tools/check_schemas.py` or add a narrowly scoped registration
  validator only if the completed artifact needs checks beyond JSON Schema

The registration freezes these Evaluation Arm IDs in this order:

```text
heuristic_v0
determinization_search_v0
information_set_duct_closed_world_v0
information_set_duct_open_world_v0
model_or_hybrid_v0
```

The comparison order is:

```text
heuristic_v0
  vs determinization_search_v0
determinization_search_v0
  vs information_set_duct_closed_world_v0
information_set_duct_closed_world_v0
  vs information_set_duct_open_world_v0
strongest stable baseline
  vs model_or_hybrid_v0, only when the optional arm is enabled by the frozen rule
```

Both Information-Set arms use `information_set_duct_v0`; their distinction is
the registered world-distribution or Belief mode. The registration references
the accepted metric, target-population, pool, statistical, determinism, and
provenance documents by ID and version. It contains no concrete team,
opponent, Search, engine, model, or holdout digest.

The binding is created only for `heuristic_v0`. It records the actual source
commit selected for the post-Task-20 `main`, the heuristic policy digest,
Safety/Fallback digest, Decision-Record schema and canonicalizer digests,
Runtime and contract digests, and null values for Search, engine, Belief, and
model artifacts that do not exist for this arm. The registration digest is
computed before the binding and must match exactly; the registration file is
never edited to accommodate the binding or any observed result.

TDD sequence:

- [ ] Add a test that validates the registration and records its canonical
  digest twice with identical bytes.
- [ ] Add tests that all five arm IDs and the three mandatory comparisons are
  present, Information-Set IDs are correct, and the optional model comparison
  is disabled unless its pre-registered condition is met.
- [ ] Add tests that the heuristic binding resolves to the registration
  digest, binds only an implemented arm, and leaves non-existent arms
  unsealed.
- [ ] Add tests that Selection and Release Holdout remain unopened and no
  concrete pool digest appears in the registration.
- [ ] Generate the two artifacts from the already accepted rules and validate
  them without changing their meaning after digest calculation.

**Acceptance criteria:** The registration is formally frozen and digestable;
the heuristic is the only bound arm; all other future arms are visibly
unsealed; no holdout is opened; and no Search, Belief, Oracle, engine, or model
artifact is claimed to exist.

## Task 22: M1.5 acceptance and evidence

**Files:**

- Create: `docs/operations/m1-5-measurement-harness-evidence.md`
- Modify: `docs/README.md` under `## Evidenz und Audits` to link the new audit
- Create: `tests/tooling/test_m15_evidence.py` if machine-checkable evidence
  assertions are not already covered by the existing tooling tests

The audit has `document_type: audit`, `normative: false`, a real completion
date, and links to the validated source commit, registration digest, schema
versions, Decision-Record byte vectors, and the successful workflow run. It
reports measured values rather than copying old PR descriptions. At minimum it
records:

- schema and example validation results;
- registration and heuristic-binding digest checks;
- two identical synthetic M1 runs with byte-identical Decision Records;
- seed, schedule, and budget reproducibility;
- pool partition and near-duplicate disjointness checks;
- unopened Selection and Release Holdout status;
- secret and hidden-state leakage checks;
- Python and OS validation matrix;
- complete test and gate counts from the actual run; and
- explicit negative scope evidence showing no Search, Oracle, engine, Belief,
  replay, dataset, training, or model implementation was introduced.

The status language must remain:

```text
M1.5 Measurement Harness and Baseline Registration complete
Next milestone: M2 Engine-qualified Search Prototype
Runtime remains version 0.2.0, phase M1
Observed live measurement coverage: not established unless separately authorized
No strength, parity, release, or MVP claim
```

The evidence document may summarize results and link to normative owners, but
it may not duplicate metric definitions, statistical thresholds, pool meaning,
Safety rules, package boundaries, or M5 gates. Any numeric total must include
the command, commit, environment, and denominator from which it was measured.

TDD and evidence sequence:

- [ ] Add a failing evidence check for an unlinked registration digest, an
  opened holdout, and a secret or hidden-state field.
- [ ] Run the full M1.5 synthetic harness twice from a clean checkout and
  capture the actual outputs and counts.
- [ ] Write the audit from those outputs, preserving the existing M1 status
  and avoiding claims about public live coverage.
- [ ] Run the focused evidence/documentation checks.
- [ ] Run every repository gate from the current workflow, including Ruff,
  mypy, full tests, architecture, docs, schemas, versions, package smokes,
  Protocol/Safety smokes, and `pr-gate`.
- [ ] Inspect the complete diff for generated artifacts, credentials, local
  paths, private data, accidental pools, and M2 code before merging.

**Acceptance criteria:** The M1.5 audit is reproducible from the frozen
registration and binding, every reported number has measured provenance,
holdouts remain unopened, the runtime status remains M1/0.2.0, no M2
implementation is present, and all required repository checks are green.

## Cross-task integration rules

1. **Immutable registration:** after Task 21 computes the registration digest,
   no later task may rewrite the registration to match an outcome, platform,
   artifact, or favorable analysis.
2. **Registration before binding:** a binding must reference an already frozen
   registration digest. It cannot create or modify an arm specification.
3. **Public/private boundary:** Core projections and records contain only
   public observed state and current legal-action evidence. Full hidden worlds,
   private requests, secrets, local paths, and raw Showdown payloads stay out.
4. **Single trace path:** the Runtime owns concrete telemetry; Core owns only
   the port and immutable public record types; Lab consumes approved public
   Runtime APIs and does not import private CLI or Composition modules.
5. **No outcome-dependent tuning:** calibration, pool construction, schedule,
   seed families, and pivot gates are fixed before the relevant results are
   inspected.
6. **Failure preservation:** rejected actions, send failures, fallbacks,
   timeouts, disconnects, and voids remain visible result classes and are not
   removed from totals.
7. **No ambient state:** no global clock, process-randomized hash, unrecorded
   randomness, current hostname, absolute path, or environment-dependent
   decision enters a digest or schedule.
8. **No public-network work:** all M1.5 tests use synthetic inputs, fake
   connections, in-memory sinks, or offline fixtures. A live Showdown run
   requires a separate maintainer authorization and is not part of the gate.

## Final validation matrix

The exact command names remain the repository's current commands. The final
Task 22 PR must run, at minimum:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run python tools/check_architecture.py
uv run python tools/check_docs.py
uv run python tools/check_schemas.py
uv run python tools/check_versions.py
uv run python tools/smoke_packages.py
```

Focused checks additionally cover:

```text
uv run pytest tests/tooling/test_m15_registration_schemas.py -v
uv run pytest tests/contracts/test_decision_record_contract.py -v
uv run pytest packages/battlebelief-core/tests/domain/records -v
uv run pytest packages/battlebelief-runtime/tests -v
uv run pytest packages/battlebelief-lab/tests/evaluation -v
uv run pytest tests/tooling/test_m15_registration_artifacts.py -v
uv run pytest tests/tooling/test_m15_evidence.py -v
```

If a focused path is renamed during a later task, the PR must record the
replacement path rather than silently omitting the check. The GitHub workflow
must keep the stable required status `pr-gate`, use `if: always()`, accept only
`success` or intentional `skipped` results, retain `contents: read`, and add
no public-network or secret-dependent job.

## Risks and review checkpoints

- **Canonicalization drift:** Decision Records must not accidentally use a
  second JSON encoder or Python object representation. Review byte vectors and
  cross-version output before accepting Task 18.
- **Trace timing drift:** a record emitted before the independent Safety Gate
  or after a failed send is invalid evidence. Review ordering with a fake
  connection in Task 19.
- **Boundary leakage:** the Lab may use only approved Runtime public/testing
  adapters. Review import scans and package smokes after Task 20.
- **Pool contamination:** logical clusters, policy identities, and seed
  families must not cross future pool boundaries. Review partition rejection
  tests before Task 21.
- **Registration hindsight:** no concrete digest, chosen budget, or favorable
  comparison may be inserted after inspecting a result. Review the git history
  and registration digest in Task 21 and Task 22.
- **Status inflation:** M1.5 does not change Runtime Doctor, package version,
  or the meaning of a green `main`; review README and audit wording for
  strength or release claims.

## Plan self-review

The plan covers the requested sequence as follows:

| Requirement | Plan location |
| --- | --- |
| Seven serial PR boundaries | PR and task boundaries |
| Registration/binding separation | Authority, Task 17, Task 21, integration rules |
| Decision Record fields and projections | Task 18 |
| TraceSink and M1 integration | Task 19 |
| Deterministic budgets, seeds, pools, schedules | Task 20 |
| Formal arms and heuristic binding | Task 21 |
| Measured M1.5 evidence | Task 22 |
| Four maintainer decisions | Decision A–D |
| Existing normative owners preserved | Authority and non-goals |
| M2 implementation excluded | Authority, task acceptance criteria, integration rules |
| Fresh repository gates | Final validation matrix |

No implementation schema, registration artifact, production adapter, Search
module, Belief module, engine module, or concrete pool is introduced by Task
16. The plan is therefore suitable for a plan-only Draft PR from the merged
M1/main base.
