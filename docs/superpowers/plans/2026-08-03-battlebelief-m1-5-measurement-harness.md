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
- concrete Selection, Power Pilot, or Release Holdout contents;
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
| 17 | Registration and arm-binding schemas | `schemas/manifests/`, `schemas/examples/`, `docs/contracts/manifest-schemas.md`, metric/statistical ID owners, schema-contract tests, and semantic validation tooling |
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
3. **Shared encoder port with Lab-owned hashing:** let Core emit a specified
   public projection and expose one versioned encoder port that Lab uses for
   hashing. This keeps the digest implementation out of the Core domain but
   requires the shared port, Runtime/Lab compatibility tests, and an explicit
   rule that no consumer may hash the projection independently. This option is
   not compatible with the Task 18 requirement that Core expose digest
   functions unless that requirement is changed before implementation.

Task 18 cannot start until Decision A is selected. Task 17 always extracts the
existing manifest JCS implementation into an installable Core module because
the semantic validator must work from an isolated Lab wheel. Its scope
therefore includes:

```text
packages/battlebelief-core/pyproject.toml
packages/battlebelief-lab/pyproject.toml
uv.lock
tools/smoke_packages.py
tools/canonicalize_manifest.py
tests/tooling/test_canonicalization.py
tests/tooling/test_pr_workflow.py
packages/battlebelief-lab/README.md
docs/architecture/dependency-matrix.md, when the Core runtime dependency is
listed there
```

The installable runtime dependencies are exactly `rfc8785` for Core and
`jsonschema` for Lab; the lockfile must not update unrelated dependencies.

The JCS implementation must be moved into one installable Core module and the
existing manifest tool must delegate to that module; two independent JCS
implementations are forbidden. If Option 1 is selected, Task 18 reuses this
module for Decision Records. Option 2 additionally includes a separately
versioned Core record encoder, its schema/byte-vector documentation, and its
cross-platform test vectors. Option 3 is not implementable under the current
Task 18 requirement for Core digest functions and must either be rejected or
be preceded by an explicit requirement change.

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

Decision B must be approved before Task 20 creates a clustering implementation.
The default recommendation is Option 1. Option 1 means a digest of a
canonical, complete team representation; Option 2 requires a separately
versioned distance, weights, threshold, clustering algorithm, and tie-break;
Option 3 introduces no local classifier and requires external provenance.

### Decision C: Budget calibration

**Question:** How is the pre-registered Search-work budget selected without
looking at action quality or battle results?

1. **Outcome-blind calibration grid (recommended):** freeze a finite ordered
   work grid and a calibration-state construction rule in a Calibration
   Specification. After the applicable Search implementation exists in M2,
   create separate Calibration Evidence by measuring only runtime and resource
   usage, then bind that evidence before quality evaluation. The calibration
   may never inspect action quality, wins, or holdout rows.
2. **Fixed budget value:** freeze an explicit number of transitions,
   simulations, or nodes before any calibration run. This is easiest to audit,
   but it may underuse the reference hardware or exceed the deployment limit.
3. **Hardware-normalized budget profile:** freeze a benchmark procedure and
   normalize work to a reference CPU profile. This is portable but adds a
   platform-normalization contract and must not become a post-result tuning
   loop.

The budget artifact is discriminated by profile mode. A `fixed` profile
registers its selected work value and requires no Calibration Evidence. A
`calibrated_grid` profile registers a Calibration Specification and receives
Calibration Evidence only later, after the applicable implementation exists.
A `hardware_normalized` profile registers a benchmark and normalization
specification and receives measured normalization evidence later. Runtime
observations from comparison runs never alter a registered budget identity.

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
- Create: `schemas/manifests/evaluation-run-binding.schema.json`
- Create: `schemas/manifests/budget-calibration-spec.schema.json`
- Create: `schemas/manifests/budget-calibration-evidence.schema.json`
- Create: `schemas/manifests/search-execution-spec.schema.json`
- Create: `schemas/manifests/synthetic-fixture-manifest.schema.json`
- Create: `schemas/examples/experiment-registration.example.json`
- Create: `schemas/examples/evaluation-arm-binding.example.json`
- Create: `schemas/examples/evaluation-run-binding.example.json`
- Create: `schemas/examples/budget-calibration-spec.example.json`
- Create: `schemas/examples/budget-calibration-evidence.example.json`
- Create: `schemas/examples/search-execution-spec.example.json`
- Create: `schemas/examples/synthetic-fixture-manifest.example.json`
- Modify: `docs/contracts/manifest-schemas.md` with a new version and entries
  for all seven manifest schemas, their `$id` values, validation order, and
  evolution rules
- Create: `docs/contracts/experiment-registration.md` as the normative owner
  of registration, implementation-binding, run-binding, freeze, supersession,
  and component-state lifecycle semantics
- Modify: `docs/contracts/provenance.md` with the versioned relationship
  between registration, binding, run, and evidence digests
- Modify: `docs/README.md` to index the new normative contract
- Modify: `docs/evaluation/metrics.md` with stable machine-readable metric IDs
  and unchanged human-readable definitions
- Modify: `docs/evaluation/statistical-analysis.md` with stable estimand and
  analysis-procedure IDs for the registered procedures
- Create: `tests/tooling/test_m15_registration_schemas.py`
- Create: `tools/validate_m15_registration.py`
- Create: `tests/tooling/test_m15_registration_validation.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/canonicalization.py`
- Modify: `packages/battlebelief-core/pyproject.toml` to add the runtime
  `rfc8785` dependency
- Create: `packages/battlebelief-lab/src/battlebelief_lab/registration_validation.py`
- Modify: `packages/battlebelief-lab/pyproject.toml` to add the runtime
  `jsonschema` dependency
- Create: `packages/battlebelief-lab/tests/test_registration_validation.py`
- Modify: `uv.lock` for only these internal runtime dependencies
- Modify: `tools/canonicalize_manifest.py` to delegate to the installable Core
  canonicalizer
- Modify: `tools/smoke_packages.py` to verify the isolated Core/Lab wheels
  can import and use their declared canonicalization/validation dependencies
- Modify: `tests/tooling/test_canonicalization.py`
- Modify: `tests/tooling/test_pr_workflow.py` to require the validator command
  in the Repository contracts step
- Modify: `docs/architecture/dependency-matrix.md` with the approved runtime
  dependency edges
- Modify: `packages/battlebelief-lab/README.md` to describe the new offline
  validation seam while keeping Search, Oracle, engine, and dataset
  capabilities absent
- Modify: `tools/check_schemas.py` to validate record schemas under
  `schemas/records/` as well as manifest schemas, while keeping the existing
  canonicalization checks unchanged
- Modify: `.github/workflows/pr.yml` so the semantic validator is executed by
  the Repository contracts job and contributes to the existing `pr-gate`
- The shared pure validation library is the Lab module above; the CLI wrapper,
  `battlebelief_lab.evaluation.registration`, and CI all call it. Neither
  caller may implement a second validator.

The semantic validator is required, not optional. JSON Schema validates each
document; it cannot calculate a digest of another file, resolve an external
arm ID, or enforce uniqueness of one property inside an array. The validator
must process inputs in this order:

```text
strict JSON loading
→ schema validation
→ semantic invariants
→ repository document and metric reference resolution
→ canonicalization
→ registration/binding digest comparison
```

The existing `quality` job's Repository contracts step must invoke
`uv run python tools/validate_m15_registration.py` after the schema checks.
Because `quality` is already a required input to the stable `pr-gate`, this
adds the semantic validator without creating a second full test matrix or
changing the five-result `success|skipped` gate semantics.

Its JSON loader must reject duplicate object keys, non-finite numbers, and
non-NFC strings before schema validation. It must report the relative path and
JSON path for each failure without echoing secret-like values. The validator
must support explicit schema-to-example mappings rather than assuming that
every `schemas/examples/NAME.example.json` maps to
`schemas/manifests/NAME.schema.json`; this is required for record schemas under
`schemas/records/`.

Task 17 has two explicit validation modes. `validate examples` processes the
seven explicit example-to-schema mappings listed in the contract. `validate
repository artifacts` additionally scans `registrations/` and any existing
bindings; a missing `registrations/` directory is a valid no-op until Task 21,
while every artifact that exists is fully validated. A missing
`schemas/records/` directory is likewise a valid no-op in Task 17. Task 18
creates that directory and activates record-schema scanning with negative
tests; Task 21 activates registration-artifact validation. The CI command must
run both modes without treating either preconditioned absence as success by
accident.

Before the schemas are frozen, the maintainer must approve stable IDs in the
normative metric and statistical documents. The initial candidate set is:

```text
decision_regret_teacher_v1
teacher_top1_agreement_v1
battle_outcome_weighted_v1
end_to_end_latency_ms_v1
fallback_rate_v1
```

The accepted list may use different names, but the chosen IDs, roles,
document versions, estimand IDs, direction of improvement, confidence
procedure, confidence level, technical-result treatment, and tie-break rule
must be written into the normative owners before the registration example is
accepted. A registration only references those IDs; it never copies their
definitions.

Adding these machine-readable IDs is a semantic contract change: the metric,
statistical-analysis, manifest-schema, and provenance document versions must
be incremented where their meaning or accepted schema list changes, and the
documentation index must be updated. The dedicated
`experiment-registration` contract owns the lifecycle of registration,
implementation binding, run binding, freeze, supersession, and the
`not_applicable`/`unbound`/`bound` component states.

The schemas must use Draft 2020-12 and project URNs. Every object rejects
unknown properties. Every manifest carries `schema_version`, a stable
`registration_id` or binding identity, and explicit contract references.

`experiment-registration` is the pre-experiment artifact. It contains:

- central hypothesis and named null hypotheses;
- a unique ordered list of Evaluation Arm IDs;
- policy kind, Search algorithm ID, and world-distribution/Belief mode per arm;
- a unique ordered comparison list whose arm references resolve exactly;
- metric IDs, metric-document versions, estimand IDs, and analysis-procedure
  IDs, without copying their definitions;
- deployment and mechanism budget profiles;
- a discriminated budget mode for each profile: `fixed`, `calibrated_grid`,
  or `hardware_normalized`;
- a selected work value for `fixed`, a Calibration Specification reference for
  `calibrated_grid`, or a benchmark/normalization Specification reference for
  `hardware_normalized`;
- no Calibration Evidence digest in the pre-experiment registration;
- pool construction, near-duplicate, side, and schedule rules;
- stop/pivot rules with the selected decision version; and
- a separate `pool_access` object with `development: "available"` and
  `selection`, `power_pilot`, and `release_holdout` all set to `"unopened"`;
- no concrete implementation, team, schedule, evaluation-pool, or later
  Calibration Evidence digests; those are resolved only by later bindings; and
- an explicit `registration_status: "frozen"`; the registration digest is
  recorded externally in the binding/evidence because inserting it into the
  bytes being hashed would be circular.

`evaluation-arm-binding` is the post-implementation implementation artifact.
It contains:

- the immutable `registration_id` and `registration_digest`;
- exactly one registered `arm_id`;
- implementation digests only: source commit, package or wheel, policy,
  fallback/safety, Search, engine, prior, Belief, model, Decision-Record
  schema, canonicalizer, and contract-set digests as applicable;
- a `binding_kind: "implementation"` marker; and
- a component-state object whose every component is explicitly one of
  `"not_applicable"`, `"unbound"`, or `"bound"`, with a digest present only
  for `"bound"`.

`evaluation-run-binding` is the later evaluation-context artifact. It refers to
an implementation binding and adds the concrete registration-controlled team,
opponent-policy, schedule, seed-family, budget, runtime, and environment
digests. It has `binding_kind: "run"`, and it cannot open a pool that the
registration marks `"unopened"`.

Its implementation-facing fields are limited to
`implementation_binding_digest`, `team_pool_digest`,
`opponent_policy_pool_digest`, `schedule_digest`, `seed_family_digest`,
`budget_profile_digest`, `calibration_evidence_digest`,
`runtime_environment_digest`, `ruleset_digest`, and
`synthetic_fixture_manifest_digest`. The corresponding
`ArmImplementationBinding` does not contain those run-specific pool, schedule,
budget, or environment values.

The Run Binding is discriminated by `run_purpose`. For `evaluation`,
`team_pool_digest` and `opponent_policy_pool_digest` are required and the
registered pool-access rules apply. For `synthetic_acceptance`,
`synthetic_fixture_manifest_digest` is required, both pool-digest fields are
forbidden, and no pool is opened. The validator resolves that digest to an
existing `synthetic-fixture-manifest` and recomputes its canonical digest; a
syntactically valid digest without a resolvable artifact is rejected.

The synthetic fixture manifest embeds or references canonical objects for the
synthetic team fixtures, opponent-policy fixture, schedule rows, SeedFamily,
budget profile, runtime environment, and ruleset snapshot. Every referenced
object must exist and its digest must recompute before the Run Binding is
accepted.

The two budget-calibration schemas separate specification from later evidence.
`budget-calibration-spec` contains the reference environment specification,
calibration-state construction rule, ordered work grid, selection-rule ID,
allowed runtime/resource measurements, and forbidden quality measurements.
`budget-calibration-evidence` is created only after the applicable M2
implementation exists and contains the specification digest, actual
environment and calibration-state digests, measured runtime/resource values,
and the selected grid value. A fixed profile has no evidence artifact; a
calibrated-grid or hardware-normalized profile receives its evidence in a
later run binding, never by rewriting the registration.

`search-execution-spec` is likewise declarative only. It freezes the future
`determinization_search_v0` world-sampling, lookahead, aggregation, tie-break,
budget, and fallback choices; it contains no Search implementation or engine
artifact.

Digest meanings are versioned and explicit: a policy digest covers the named
policy source manifest or wheel contents; a runtime digest covers the exact
runtime wheel/source artifact and lock metadata selected by the binding; a
contract-set digest covers the sorted `(document_id, version, file_digest)`
tuples; and a fallback/safety digest covers the exact declared source-file
set. A digest shape alone is not accepted as provenance.

The schemas and semantic validator must reject:

- duplicate arm IDs or duplicate comparison IDs, including duplicates whose
  other object fields differ;
- unknown arm IDs in comparisons;
- an `information_set_duct_*` arm whose Search ID is not
  `information_set_duct_v0`;
- concrete implementation or pool digests in an unsealed registration;
- any Selection, Power Pilot, or Release Holdout status other than `unopened`;
- missing contract, metric, estimand, or analysis-procedure references;
- empty digests, invalid digest shapes, and free placeholder strings;
- a binding without a matching registration digest; and
- a binding whose arm, component state, registration digest, or referenced
  implementation does not match the external registration.

TDD sequence:

- [ ] Add invalid instances for each rejection and run the focused test to
  prove the validator rejects them.
- [ ] Add the seven valid examples and run the explicit example-to-schema
  validation.
- [ ] Add metric, estimand, and analysis-procedure IDs to their normative
  owners without changing the meaning of an existing metric or procedure.
- [ ] Implement the strict loader, semantic validator, explicit schema mapping,
  reference resolver, and digest comparison needed by those tests.
- [ ] Add a unit suite for the shared pure validation library and make the
  CLI wrapper expose only sanitized diagnostics.
- [ ] Run `uv run python tools/check_schemas.py` and
  `uv run python tools/validate_m15_registration.py` and
  `uv run pytest tests/tooling/test_m15_registration_schemas.py tests/tooling/test_m15_registration_validation.py -v`.
- [ ] Run the same semantic validation through the repository `pr-gate`, not
  only as a local/manual command.
- [ ] Run `uv run python tools/check_docs.py` after the contract version and
  links are updated.
- [ ] Run `uv lock --check`, `uv run python tools/smoke_packages.py`,
  `uv run pytest tests/tooling/test_pr_workflow.py -v`,
  `uv run python tools/check_architecture.py`, and `uv run mypy` after the
  dependency and workflow changes.

**Acceptance criteria:** All seven manifest artifacts and examples validate
through the repository schema gate; preconditioned missing directories are
explicit no-ops and existing artifacts are fully checked; cross-field identity
and arm rules are tested; the contract is the only
normative owner of the new schema list; and no concrete pool or implementation
artifact is represented as already existing.

## Task 18: Decision Record schema and canonical public projections

**Files:**

- Create: `schemas/records/decision-record.schema.json`
- Create: `schemas/records/decision-record-payload.schema.json`
- Create: `schemas/records/measurement-run.schema.json`
- Create: `schemas/examples/decision-record.example.json`
- Create: `schemas/examples/decision-record-payload.example.json`
- Create: `schemas/examples/measurement-run.example.json`
- Create: `docs/contracts/decision-records.md` as the normative owner of
  Decision-Record semantics, public/private boundaries, cardinality, and
  terminal dispositions
- Modify: `docs/contracts/manifest-schemas.md` to register the payload,
  envelope, and measurement-run record schemas and their evolution rules
- Modify: `docs/architecture/code-boundaries.md` to register the Core records
  directory and its allowed dependencies
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/records/__init__.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/records/decision_record.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/records/public_projection.py`
- Modify: `packages/battlebelief-core/src/battlebelief_core/domain/__init__.py`
  only for the public record exports
- Create: `packages/battlebelief-core/tests/domain/records/test_decision_record.py`
- Create: `packages/battlebelief-core/tests/domain/records/test_public_projection.py`
- Create: `tests/contracts/test_decision_record_contract.py`

Task 18 changes the previously valid no-op state: it creates
`schemas/records/`, registers the explicit payload/envelope/measurement-run
example mappings, and adds negative tests proving malformed record schemas are
reported. It must not weaken the Task 17 example validator or silently skip
records once the directory exists.

The new `docs/contracts/decision-records.md` is the sole normative owner for
the durable meaning of these records. It must receive a document ID, version,
frontmatter, and an entry in `docs/README.md`. The plan, examples, Runtime
README, and evidence may link to it but may not define a competing status,
privacy, cardinality, or digest rule.

The selected byte contract from Decision A must be recorded before coding. The
payload schema is versioned and contains exactly the public fields required by
the research strategy:

```text
record_schema_version
record_status
run_context_digest
decision_index
request_identity
observed_state_digest
safe_submission_set_digest
selected_submission
submission_provenance
fallback_or_error_class
policy_or_arm_id
runtime_and_contract_digests
```

The envelope schema adds `record_id` and `record_digest` around the validated
payload. `record_digest` is the SHA-256 digest of canonical bytes for
`{record_id, payload}`; only `record_digest` itself remains outside the hashed
value. The payload and envelope are separate schema levels so the digest can
never hash itself, while a changed record identity is still detected.

The status enum is:

```text
submitted
wait_noop
policy_rejected
action_gate_rejected
command_encoding_failed
send_failed
session_aborted
superseded_before_selection
terminally_discarded
reconciliation_rejected
```

`selected_submission` is nullable and is populated only after a candidate has
been selected. `fallback_or_error_class` is a stable code or null; exception
messages are never serialized. The record has no password, assertion,
packed-team content, raw room ID, account ID, user ID, display name, private
opponent request, sampled hidden world, absolute path, hostname, wall-clock
timestamp, or unbounded free-form payload.

`command_encoding_failed` is distinct from both `action_gate_rejected` and
`send_failed`: the candidate passed the independent safety gate, encoding
failed, and no socket send was attempted. In that terminal record,
`selected_submission` and `submission_provenance` are set,
`fallback_or_error_class` is a stable sanitized code, and submission counters
remain unchanged.

`session_aborted` finalizes a fresh record when a classified session error
(such as `disconnect`, `transport_timeout`, `timer_or_forfeit`,
`unknown_protocol_event`, `malformed_protocol_message`, or a reducer invariant
failure) ends the session before another terminal disposition. Its
`fallback_or_error_class` is the stable existing error code;
`selected_submission` is retained if selection already occurred, otherwise it
is null. It never invents an action or performs an additional send. A record
already finalized as `submitted` is never rewritten by a later abort.

The record is bound to an `EvaluationRunBinding` through a
`measurement-run` context. The public context carries these primary
references:

```text
evaluation_run_binding_digest
run_scope_digest
battle_id_digest
```

The validator resolves the Run Binding and verifies that its implementation
binding and registration, schedule, seed family, budget, runtime environment,
ruleset, and pool-access state agree with the registered run. The resolved
non-circular `RunScopePayload` contains those fields and is hashed as
`run_scope_digest`. A synthetic harness then derives `battle_id_digest` from
`{run_scope_digest, schedule_row_id, battle_ordinal}`. The final
`RunContextPayload` contains `evaluation_run_binding_digest`, the scope
references, `battle_ordinal`, and `battle_id_digest`; its digest is
`run_context_digest`. The raw Showdown room ID is never an input or
serialized field in this offline identity scheme. The bot and opponent
identities are not projected. Tests must use concrete room IDs and usernames
to prove that they do not appear in canonical bytes or JSONL.

The same resolution is mandatory for every record: `policy_or_arm_id` must
equal the resolved implementation binding's `arm_id`; the record's
`runtime_and_contract_digests.runtime_digest` must equal the Run Binding's
runtime digest; and its `contract_set_digest` must equal the resolved
implementation binding's contract-set digest. Policy and fallback/safety
digests, when represented in public provenance, are likewise derived from the
resolved binding rather than accepted as caller-supplied alternatives.

`record_id` is non-circular. It is derived from the run-context digest,
`battle_id_digest`, a zero-based `decision_index`, and the public
request-identity projection. `record_digest` is then computed over the
canonical envelope payload `{record_id, payload}`, with only the digest field
excluded; neither digest is an input to its own derivation. A run, schedule row,
repetition, and request can therefore be resolved without relying on an
implicit process or timestamp.

The cardinality rule is exact:

```text
fresh request passes Freshness
→ exactly one in-progress record
→ intermediate boundaries update that record
→ exactly one terminal disposition is emitted
```

An identical duplicate request creates no record. A newer request can
terminate an older pending record as `superseded_before_selection`; `win`,
`tie`, or another terminal battle result can terminate a pending record as
`terminally_discarded`. A request that fails reconciliation after passing the
freshness boundary uses `reconciliation_rejected` with its stable error code.
An abort that occurs before any fresh request exists is a separate run/battle
disposition and must not invent a request identity or Decision Record.

`public_projection.py` must expose explicit, immutable projections for:

- `ObservedState`;
- `RequestIdentity`;
- `SafeSubmissionSet`; and
- `BattleSubmission`.

Projection rules are explicit: sort mapping keys and mathematical sets, but
preserve semantically meaningful sequences. In particular, preserve
`SafeSubmissionSet.submissions`, `BattleSubmission.team_order`, and visible
evidence/event order. Use normalized scalar values and encode only documented
fields. `room_id`, `our_user_id`, side user IDs, and display names are omitted
or replaced by the run-scoped pseudonyms specified by the normative contract.
Digest functions must never call `hash()`,
`repr()`, `str(dataclass)`, UUID generation, or the current clock. They must
return stable bytes and `sha256:` digests under Python 3.12, 3.13, and 3.14.

TDD sequence:

- [ ] Add cross-version fixture vectors and a leakage test that fails if any
  forbidden secret, hidden-state, path, or host token appears.
- [ ] Add tests proving equivalent public objects produce identical bytes and
  digest, while changes to each public field change the digest.
- [ ] Add tests proving set-order and mapping-order variations canonicalize
  identically where the contract declares them unordered.
- [ ] Add a regression showing that reordering `SafeSubmissionSet.submissions`
  changes its digest and can change a same-priority heuristic choice, while
  mapping keys and true mathematical sets remain order-independent.
- [ ] Add tests proving the record is immutable and rejects unknown or
  non-public fields.
- [ ] Add tests for run-context binding, non-circular `record_id`, decision
  index uniqueness, and the exact fresh-request cardinality/terminal-state
  matrix.
- [ ] Add the command-encoding failure to that matrix and prove it emits one
  terminal record without a socket send or counter increment.
- [ ] Add pending-request abort cases for disconnect, transport timeout,
  timer/forfeit, unknown protocol, and malformed protocol classifications, and
  prove a submitted record remains immutable after a later abort.
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
- Create: `packages/battlebelief-core/src/battlebelief_core/ports/__init__.py`
  for the public port and null implementation
- Modify: `packages/battlebelief-core/src/battlebelief_core/errors.py` with the
  stable `trace_sink_failure` classification and its contract test
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/telemetry/__init__.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/telemetry/jsonl_decision_trace.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/testing/in_memory_trace_sink.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/testing/measurement_session.py`
- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/testing/__init__.py`
  to expose the narrow measurement seam allowed to Lab
- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/composition/battle_session.py`
  to accept an injected sink with a no-op default
- Create or modify: focused Core port, Runtime adapter, and BattleSession tests
  under the existing package test trees

The Core port accepts a `DecisionRecord` and has no filesystem, WebSocket,
environment, logging, clock, or random dependency. The Runtime JSONL adapter
serializes only the validated public record projection. The in-memory sink is
for deterministic tests and preserves record order without changing records.
The measurement seam is exported from `battlebelief_runtime.testing`, so Lab
does not import the private `composition` module. It may internally compose the
existing `BattleSession` but exposes only synthetic, dependency-injected input
and output types.

The BattleSession integration opens one in-progress record immediately after a
request passes the Freshness check, before reconciliation or policy selection.
It updates that record at these boundaries:

```text
fresh request reconciled
→ policy candidate
→ independent ActionSafetyGate
→ command encoding
→ successful socket send
→ submission counters
→ one terminal Decision Record
```

The record for an encoding failure is `command_encoding_failed`: the selected
candidate and provenance are present, no socket send occurs, and submission
counters do not change. A send failure is `send_failed` and never claims a
successful dispatch. Duplicate requests are suppressed before selection and do
not create a second record. A pending public-state request creates `wait_noop` only when
that is the declared decision outcome, not for every ignored wire line. A
superseded pending request uses `superseded_before_selection`; a request
discarded by `win`/`tie` uses `terminally_discarded`; and reconciliation failure
after the freshness boundary uses `reconciliation_rejected`. Aborts before
any fresh request remain in the existing run/battle result and are not wrapped
in a fabricated Decision Record. Once a fresh record exists, a classified
Disconnect, TransportTimeout, TimerOrForfeit, UnknownProtocolEvent,
MalformedProtocolMessage, or reducer invariant failure finalizes it as
`session_aborted` unless a more specific terminal disposition already exists.

Trace failures are surfaced through the stable `trace_sink_failure` class and
are never silently discarded. Each fresh request produces exactly one
finalized record object and exactly one emit attempt. A successful sink
persists one record; a sink failure makes the run invalid with
`trace_sink_failure`, performs no automatic retry, and cannot cause another
socket send or change the selected action. The implementation must explicitly
preserve the primary battle/send error if a trace failure occurs during cleanup
or terminal emission, and must report the trace failure when no earlier primary
error exists. `BattleSession` never closes an injected sink. The Measurement
Runner owns flush/close and classifies failures from those operations.

The JSONL adapter writes UTF-8 bytes using `\n` exactly once per record:
`canonical_record_bytes + b"\n"`. It must not use platform newline
translation, must define flush and close behavior, and must test identical
bytes on Windows and Linux. No raw JSON request, secret, host, or path is
written.

TDD sequence:

- [ ] Add a failing integration test showing the same synthetic M1 session
  emits one record per fresh accepted request and no record for a duplicate.
- [ ] Add a failing test for a rejected action, a send failure, a wait/no-op,
  and terminal battle abort, checking the exact status and nullability rules.
- [ ] Add a failing command-encoding test after a successful safety gate,
  proving no send or submission-counter increment occurs.
- [ ] Add pending-request session-abort tests for disconnect, transport
  timeout, timer/forfeit, unknown protocol, malformed protocol, and reducer
  invariant failure, including preservation of already submitted records.
- [ ] Add a failing test for a trace-sink failure before and after a primary
  battle/send failure, checking `trace_sink_failure` classification and error
  precedence.
- [ ] Add a leakage test over JSONL and in-memory output for secrets, private
  opponent data, sampled hidden worlds, paths, and hostnames.
- [ ] Add a two-run test with identical input, policy, and digest inputs that
  compares actions, records, canonical bytes, and digests byte-for-byte.
- [ ] Implement the Core port, Runtime adapters, and narrow BattleSession
  injection.
- [ ] Run focused Core/Runtime integration tests and the existing BattleSession
  suite; then run architecture and package boundary checks.

**Acceptance criteria:** The default public CLI behavior remains unchanged;
the Lab-approved testing API can inject a strict sink; no second stream reader
is created; no unvalidated submission is traced as sent; duplicate suppression
and error priority are preserved; trace failures are classified; and trace
output is safe, newline-stable, and deterministic.

## Task 20: deterministic Lab measurement harness

**Files:**

- Create: `schemas/records/measurement-run-result.schema.json`
- Create: `schemas/examples/measurement-run-result.example.json`
- Modify: `docs/contracts/manifest-schemas.md` to register the run-result
  schema and its evolution rules
- Modify: `docs/contracts/decision-records.md` to define the run-result
  relationship, pre-request dispositions, trace status, and sink lifecycle
- Create: `docs/evaluation/team-clustering.md` as the normative owner of the
  selected Decision B canonicalization rule
- Modify: `docs/README.md` to index the team-clustering contract
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/__init__.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/budget_profiles.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/seed_families.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/pool_partitioning.py`
- Create conditionally for Decision B option 1 or 2:
  `packages/battlebelief-lab/src/battlebelief_lab/evaluation/team_clustering.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/schedule.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/matchup_blocks.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/registration.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/measurement_runner.py`
- Create: `packages/battlebelief-lab/tests/evaluation/test_budget_profiles.py`
- Create: `packages/battlebelief-lab/tests/evaluation/test_seed_families.py`
- Create: `packages/battlebelief-lab/tests/evaluation/test_pool_partitioning.py`
- Create: `packages/battlebelief-lab/tests/evaluation/test_schedule.py`
- Create: `packages/battlebelief-lab/tests/evaluation/test_registration.py`
- Create: `packages/battlebelief-lab/tests/evaluation/test_measurement_runner.py`

The harness produces deterministic plans and identities only. It accepts no
Search implementation, engine transition model, Belief state, replay loader,
model, or network adapter.

`evaluation.registration` is only a Lab facade over the shared pure validator
from Task 17. It must not reimplement schema, reference, or digest checks.

Seed namespaces are a closed enum:

```text
search, world, policy, simulator, schedule, side_assignment
```

Seed derivation uses a registered `seed_derivation_id`, a fixed-width hex
`master_seed`, specified UTF-8 encoding with unambiguous field boundaries, and
SHA-256 over `master_seed`, namespace, `base_matchup_id`, `side_assignment`,
and repetition index. Python's process-randomized `hash()` is forbidden. The
function returns a fixed-width, documented seed representation and identical
inputs produce identical outputs independent of input-list order. A
`SeedFamily` is an object, not one ambiguous scalar, with
`search_seed`, `world_seed`, `policy_seed`, `simulator_seed`, `schedule_seed`,
and `side_assignment_seed`.

The schedule avoids seed and side-assignment circularity. First construct a
`BaseMatchupKey` without side or seed fields:

```text
hero_team
opponent_team
opponent_archetype
opponent_policy_checkpoint
schedule_block
```

`base_matchup_id` is the canonical digest of that key. Derive the initial side
bit from the low bit of SHA-256 over the registration digest and base matchup
ID, then define the side for repetition `i` as
`(initial_side_bit + i) mod 2`. Even repetition counts are exactly balanced;
odd counts differ by at most one, and an exact-balance profile rejects odd
counts. Then derive the complete `SeedFamily` from the registered master seed,
namespace, base matchup ID, side assignment, and repetition index. Finally
create the complete `ScheduleRow`:

```text
base_matchup_id
side_assignment
schedule_block
seed_family
repetition_index
```

`schedule_row_id` is the digest of the complete ScheduleRow. Fixed test
vectors cover field boundaries, namespace separation, side balance, and the
selected `seed_derivation_id`. The statistical
contract's matchup block is represented by this fully materialized row; side
balance is checked across the group of rows sharing one base matchup ID, not
inside a row that is already side-bound.

Pool partitioning accepts logical cluster IDs and emits disjoint Development,
Selection, Power Pilot, and Release Holdout labels. In M1.5 no concrete pool
elements are supplied. The API rejects duplicate cluster ownership, cross-pool
near-duplicate membership, and every attempt to open Selection, Power Pilot,
or Release Holdout before the later permitted milestone.

The pool state is explicit: Development is `available`, while Selection,
Power Pilot, and Release Holdout are all `unopened`. The harness does not
generate concrete members. If Decision B option 1 is selected,
`team_clustering.py` canonicalizes the complete six-member team and emits a
cluster ID equal to the digest of that canonical representation. Member order
is not semantic; the contract explicitly decides move-slot order and includes
species/form, moves, item, ability, nature, EVs/IVs, level, tera type, gender,
and exactly the closed field/default rules in
`docs/evaluation/team-clustering.md`. If Option 2 is selected, the same module
additionally requires a versioned distance, field
weights, threshold, deterministic clustering algorithm, and tie-break rule;
those values receive their own contract and vectors. If Option 3 is selected,
no local clustering algorithm is introduced; the harness accepts only a
versioned external classifier digest and complete input manifest, and all
evaluation pools remain unopened until that artifact is validated.

`docs/evaluation/team-clustering.md` must define a closed canonical field set
before implementation. For Option 1 that set is: species, form, item,
ability, nature, all four move slots, EVs, IVs, level, happiness, gender,
shiny, Pokéball, Hidden-Power type, and Tera type. No other field is included.
It must define
Showdown ID and Unicode normalization, missing/implicit defaults, whether move
slot order is preserved or sorted for clustering, canonical field order,
order-independent six-member ordering, and fail-closed behavior for duplicate
or structurally invalid members. Unowned fields and defaults are rejected. The
cluster ID is the SHA-256 digest of this
exact versioned canonical team representation. Option 2 owns a separate
distance/weight/threshold contract; Option 3 owns only external classifier
provenance.

Schedule generation sorts canonical identities, records balanced side
assignments within each registered block, derives all schedule seeds from the
registered registration digest, and returns a schedule digest. Reordering
input collections without changing their identities cannot silently alter the
schedule.

Budget profiles contain separate Deployment Utility and Mechanism Ablation
views. M1.5 creates only a Calibration Specification with
`reference_environment_specification`, `calibration_state_construction_rule`,
`ordered_work_grid`, `selection_rule_id`, `allowed_runtime_measurements`, and
`forbidden_quality_measurements`. It creates no measured Calibration Evidence
because Search, engine, and Oracle implementations are out of scope. A later
M2 implementation creates Calibration Evidence with the specification digest,
actual environment and calibration-state digests, runtime measurements, and
selected work value, then attaches it to an EvaluationRunBinding. A fixed
budget needs neither a Calibration Specification nor Evidence; a
`calibrated_grid` or `hardware_normalized` profile gets its later evidence
only after the applicable implementation exists. No calibration artifact may
inspect actions, wins, quality metrics, or holdout rows.

`measurement_runner.py` begins at the Battle-Room Handoff, after challenge
setup has succeeded. It composes an already validated `EvaluationRunBinding`,
a `ScheduleRow`, Run Context, the approved Runtime testing seam, and Decision
Records into one immutable
`measurement-run-result` artifact. Its schema records at minimum:

```text
run_context_digest
run_status
battle_outcome
primary_error_class
decision_record_digests
explicit_submission_count
default_submission_count
room_control_or_chat_count
ignored_display_count
final_observed_state_digest
trace_status
```

It preserves setup/transport failures before the first request, timer/forfeit,
unknown wire events, a battle with no Decision Record, and trace-sink failure
as explicit result states. Challenge-Coordinator setup errors remain in the
Coordinator seam and are not misrepresented as a BattleSession run result. It
owns sink flush and close; the Runtime session does not close an injected sink.
A close failure is classified without rewriting an earlier primary battle
error.

The result validator requires every listed Decision Record to exist, to share
the run context, and to have unique IDs in `decision_index` order. It checks
that explicit/default counters are derivable from finalized Decision Records.
`room_control_or_chat_count` must equal the `BattleSessionResult` value, and
`ignored_display_count` must equal the final `ObservedState` value. The
`final_observed_state_digest` must equal the digest of the final public State
projection. It also checks that `trace_status` matches the actual emit outcome
and that `battle_outcome` is one of `our_win`, `opponent_win`, `tie`, `void`, or
`incomplete`. Winner values are side labels, never usernames.

TDD sequence:

- [ ] Add tests for stable seed vectors, namespace separation, field-boundary
  separation, and order-independent plan identities.
- [ ] Add tests for disjoint pool partitions, duplicate cluster rejection,
  unopened Selection/Power Pilot/Release Holdout, and immutable registration
  digests.
- [ ] Add tests for base-matchup construction, balanced side assignments over
  row groups, circularity-free seed derivation, and stable schedule digests.
- [ ] Add the Decision B option 1 canonical-team clustering tests if that
  option is selected; for option 2 add distance, weight, threshold,
  deterministic-clustering, and tie-break tests; for option 3 add the
  external-classifier provenance and unopened-pool rejection tests.
- [ ] Add tests for both budget views and outcome-blind calibration inputs.
- [ ] Add tests that the Calibration Specification is stable in M1.5, that
  fixed profiles require no evidence, and that later Calibration Evidence
  changes a run-binding identity without rewriting the registration.
- [ ] Add result-validation tests for Run Binding resolution, record existence
  and shared context, decision ordering, duplicate IDs, counter agreement,
  trace status, side-based outcomes, and pre-request dispositions.
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
- Create: `registrations/gen9ou/bindings/heuristic_v0-implementation.json`
- Create: `registrations/gen9ou/bindings/heuristic_v0-m15-synthetic-run.json`
- Create: `registrations/gen9ou/synthetic/m15-acceptance-inputs-v1.json`
- Create: `registrations/gen9ou/arm-specs/determinization-search-v0.json`
- Create conditionally for Decision C `calibrated_grid` or
  `hardware_normalized`: `registrations/gen9ou/budgets/m15-search-work-calibration-v1.json`
- Create: `tests/tooling/test_m15_registration_artifacts.py`
- Modify: `tools/validate_m15_registration.py` only for artifact-specific
  checks that are not already covered by Task 17

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
```

Both Information-Set arms use `information_set_duct_v0`; their distinction is
the registered world-distribution or Belief mode. The registration references
the accepted metric, target-population, pool, statistical, determinism, and
provenance documents by ID and version. It contains no concrete team,
opponent, Search, engine, model, or holdout digest. The
`model_or_hybrid_v0` arm may be present as `lifecycle: "deferred"`, but it is
not part of a comparison in this first registration. A later model experiment
requires a new immutable registration with a concrete baseline arm selected
before its results are observed. The registration includes the digest and
version of `determinization-search-v0.json`, which freezes world-sampling
count/distribution, lookahead, value/action aggregation, tie-break, budget
consumption, and fail-closed fallback without implementing Search. Decision C
uses a fixed selected work value directly, or references the concrete budget
Calibration Specification artifact when `calibrated_grid` or
`hardware_normalized` is selected; measured evidence is still deferred.

The first binding is an `ArmImplementationBinding` for `heuristic_v0`, not an
evaluation-run binding. It records the actual source commit selected for the
post-Task-20 `main`, the heuristic policy digest, Safety/Fallback digest,
Decision-Record schema and canonicalizer digests, Runtime and contract
digests, and component states for Search, engine, Belief, and model. For this
arm, policy and fallback/safety are `bound`; Search, engine, prior, Belief, and
model are `not_applicable`. Team pools, opponent-policy pools, schedules,
seeds, budgets, calibration evidence, runtime environment, and ruleset belong
only to a later `EvaluationRunBinding`, where they may be `unbound` until a
concrete run is sealed. No component is represented as a false null digest.
The registration digest is computed before the binding and must match exactly;
the registration file is never edited to accommodate the binding or any
observed result.

The second binding is a synthetic acceptance `EvaluationRunBinding` with
`run_purpose: "synthetic_acceptance"`. It uses small fixture digests only;
those fixtures are not Selection, Power Pilot, Release Holdout, or any other
evaluation pool. The `synthetic-fixture-manifest` above is a concrete,
schema-valid artifact containing the synthetic team fixtures,
opponent-policy fixture, schedule rows, SeedFamily, budget profile, runtime
environment, and ruleset snapshot. The binding references its recomputed
`synthetic_fixture_manifest_digest`, forbids both pool-digest fields, and binds
the implementation binding without opening a pool. Task 22 therefore cannot
bypass the formal Run Binding layer.

Before any future binding of `determinization_search_v0`, the registration
must also reference a versioned execution specification covering world
sampling count and distribution, search/lookahead per world, value and action
aggregation, tie-break, budget consumption, and fail-closed fallback. An
implementation agent may not infer these choices from later results.

TDD sequence:

- [ ] Add a test that validates the registration and records its canonical
  digest twice with identical bytes.
- [ ] Add tests that all five arm IDs and the three mandatory comparisons are
  present, Information-Set IDs are correct, and the optional model comparison
  is disabled unless its pre-registered condition is met.
- [ ] Add tests that the heuristic binding resolves to the registration
  digest, binds only an implemented arm, and leaves non-existent arms
  unsealed.
- [ ] Add tests that the synthetic run binding resolves through the
  implementation binding and registration, uses only fixture digests, and
  cannot open any protected pool.
- [ ] Add tests that Selection, Power Pilot, and Release Holdout remain
  unopened and no concrete pool digest appears in the registration.
- [ ] Add tests that `model_or_hybrid_v0` is deferred and has no comparison in
  the first registration, and that every comparison reference is a concrete
  registered arm ID.
- [ ] Add tests for `not_applicable`, `unbound`, and `bound` component states
  in the implementation binding.
- [ ] Generate and validate all required artifacts from the already accepted
  rules without changing their meaning after digest calculation.

**Acceptance criteria:** The registration is formally frozen and
digest-verifiable;
the heuristic is the only bound arm; all other future arms are visibly
unsealed; no holdout is opened; and no Search, Belief, Oracle, engine, or model
artifact is claimed to exist.

## Task 22: M1.5 acceptance and evidence

**Files:**

- Create: `docs/operations/m1-5-measurement-harness-evidence.md`
- Modify: `docs/README.md` under `## Evidenz und Audits` to link the new audit
- Modify: `README.md` to change the M1.5 status without changing Runtime
  version, Runtime phase, or strength language
- Modify: `wiki/Home.md` and `wiki/Current-Status-and-Roadmap.md` to keep the
  repository's published status sources consistent
- Create: `tests/tooling/test_m15_evidence.py` if machine-checkable evidence
  assertions are not already covered by the existing tooling tests

Task 22 starts only after Task 21 has been merged and its main push workflow
is green. The validated-source sequence is non-circular:

```text
Task 21 merge
→ green main workflow for the Task 21 merge commit
→ that merge commit is validated_source_commit
→ Task 22 starts from exactly that main commit
→ the audit records the source commit and its workflow URL
```

The audit has `document_type: audit`, `normative: false`, a real completion
date, and links to the validated source commit, registration digest, schema
versions, Decision-Record byte vectors, and the successful workflow run. It
reports measured values rather than copying old PR descriptions. At minimum it
records:

- schema and example validation results;
- registration and heuristic-binding digest checks;
- the synthetic `EvaluationRunBinding` digest and its resolution to the
  implementation binding and frozen registration;
- two identical synthetic M1 runs with byte-identical Decision Records;
- seed, schedule, and budget reproducibility;
- budget-profile reproducibility; for Decision C `fixed`, report the selected
  work value and no Calibration Specification or Evidence; for
  `calibrated_grid` or `hardware_normalized`, report the concrete Calibration
  Specification and explicitly report that measured Calibration Evidence is
  deferred to the later M2 implementation binding;
- pool partition and near-duplicate disjointness checks;
- unopened Selection, Power Pilot, and Release Holdout status;
- secret and hidden-state leakage checks;
- Python and OS validation matrix;
- complete test and gate counts from the actual run; and
- explicit negative scope evidence showing no Search, Oracle, engine, Belief,
  replay, dataset, training, or model implementation was introduced.

The audit must also record the exact `uv lock --check` and `git diff --check`
results, and the JSONL byte contract: UTF-8, canonical record bytes followed
by exactly `b"\n"`, no platform-dependent `\r\n`, and explicit flush/close
behavior. Any measured count is tied to the actual command, source commit,
Python version, operating system, and denominator.

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
  capture the actual outputs and counts through the synthetic Run Binding;
- [ ] Write the audit from those outputs, preserving the existing M1 status
  and avoiding claims about public live coverage.
- [ ] Run the focused evidence/documentation checks.
- [ ] Run every repository gate from the current workflow, including Ruff,
  mypy, full tests, architecture, docs, schemas, versions, package smokes,
  Protocol/Safety smokes, `uv lock --check`, `git diff --check`, and `pr-gate`.
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
5. **One registration validator:** the pure semantic validation library is
   shared by the CLI tool, the Lab registration facade, and the repository
   schema/`pr-gate` path. No caller may provide a weaker duplicate validator.
6. **No outcome-dependent tuning:** calibration, pool construction, schedule,
   seed families, and pivot gates are fixed before the relevant results are
   inspected.
7. **Failure preservation:** rejected actions, send failures, fallbacks,
   timeouts, disconnects, and voids remain visible result classes and are not
   removed from totals.
8. **No ambient state:** no global clock, process-randomized hash, unrecorded
   randomness, current hostname, absolute path, or environment-dependent
   decision enters a digest or schedule.
9. **No public-network work:** all M1.5 tests use synthetic inputs, fake
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
uv lock --check
uv run python tools/validate_m15_registration.py
git diff --check
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

No implementation, schema, registration artifact, production adapter, Search
module, Belief module, engine module, or concrete pool is introduced by Task
16. The plan is therefore suitable for a plan-only Draft PR from the merged
M1/main base.
