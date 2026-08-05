---
document_id: plan-m2-engine-qualified-search-prototype
title: BattleBelief M2 Engine-qualified Search Prototype Implementation Plan
document_type: roadmap
status: proposed
normative: false
version: 1
applies_to:
  - repository
  - gen9ou
  - research
effective_from: 2026-08-05
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-05
---

# BattleBelief M2 Engine-qualified Search Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task, with the review and approval checkpoints stated below.

**Goal:** Deliver an engine-qualified, fail-closed Gen 9 OU search prototype whose deterministic and live execution paths remain inside the accepted contracts and whose evaluation evidence is reproducible.

**Architecture:** `battlebelief-core` owns pure eligibility, closed-world evaluation types, engine-neutral transition ports, and search algorithms. `battlebelief-runtime` owns the optional `poke-engine` artifact, adapter, deadlines, composition, public runtime API, and telemetry bridging. `battlebelief-lab` owns the local Pokémon Showdown oracle, differential qualification, corpora, offline evaluation, calibration, reporting, and artifact verification. Pokémon Showdown remains authoritative; search may use `poke-engine` only when every required capability has exact, matching evidence.

**Tech Stack:** Python 3.12-3.14, `uv`, pytest, Ruff, mypy, JSON Schema, Node.js plus an exact Pokémon Showdown source revision for the Lab oracle, and a controlled `maturin`/Rust build of an exact `poke-engine` revision for qualified platform wheels.

---

## 1. Authority, interpretation, and scope

This document is a non-normative execution plan. It does not supersede, amend, or reinterpret an accepted contract. An implementation worker must resolve requirements in this order:

1. the maintainer instruction authorizing the particular task;
2. the normative index in `docs/README.md` and the accepted contract owning the subject;
3. accepted architecture decisions and registrations;
4. this plan.

The normative owners most relevant to M2 are:

- `docs/roadmap/milestones.md` for the milestone outcome and ordering;
- `docs/roadmap/research-strategy-and-experiments.md` for research sequencing;
- `docs/contracts/engine-capabilities.md` for engine qualification and fail-closed use;
- `docs/contracts/search-v0.md` for information-set DUCT semantics;
- `docs/contracts/determinism.md` for deterministic and live modes;
- `docs/contracts/legal-action-safety.md` for `SafeSubmissionSet` and the independent post-policy gate;
- `docs/contracts/decision-records.md`, `docs/contracts/provenance.md`, and `docs/contracts/manifest-schemas.md` for records, bindings, digests, and schema evolution;
- `docs/contracts/experiment-registration.md` and the frozen M1.5 registration for evaluation immutability;
- `docs/evaluation/metrics.md`, `docs/evaluation/statistical-analysis.md`, and `docs/evaluation/pool-separation.md` for metrics, inference, and pool access.

### M2 outcome

M2 produces a local, evidence-qualified prototype in which:

- a pinned local Pokémon Showdown process supplies the authoritative mechanics oracle;
- a pinned and artifact-verified `poke-engine` backend is eligible only for mechanics proven exact by versioned differential evidence;
- ineligible, unknown, unsupported, approximate, mismatched, unhealthy, or failed engine use returns the registered `heuristic_v0` decision through a stable, counted fallback path;
- `determinization_search_v0` and `information_set_duct_v0` operate on the same evaluation-only closed-world distribution;
- `deterministic_benchmark` is reproducible and single-threaded, while `live_anytime` is deadline-aware and never supplies teacher targets;
- the two already registered core comparisons can be evaluated on the development pool without opening protected pools or making strength claims.

### Explicit non-goals

M2 does not include:

- M3 open-world belief, `BeliefState`, `OTHER`, replay-derived priors, meta inference, belief updates, or hidden-set imputation presented as truth;
- training, models, policy/value learning, self-play, data ingestion, or teacher-target production from live-anytime search;
- ladder, parity, power-pilot, release-holdout, MVP, release, or strength claims;
- public Pokémon Showdown networking, authentication, or CI access to a public Showdown service;
- support for Doubles, VGC, another generation, or another tier;
- a claim that engine import, compilation, sentinel success, or a partial corpus establishes mechanics parity;
- changes to Runtime version `0.2.0`, Runtime phase `M1`, frozen M1.5 registrations, Task-21 bindings, registered decision gates, or existing artifact digests as part of Task 23;
- a single cross-cutting implementation pull request.

The protected selection, power-pilot, and release-holdout pools remain unopened. A later, separately authorized task may create or open them only under their registered rules.

## 2. Repository inventory at Task 23

The inventory below records the tree at commit `cfc526ca1558869e674769daf19b9aa09c00abf0`. “Missing” means that no implementation exists at this commit; it is not an instruction to create the item in Task 23.

### Existing foundations

| Area | Present at the baseline | M2 integration consequence |
|---|---|---|
| Core state and actions | Observed-state types, action/submission types, `SafeSubmissionSet`, request identity, canonical digests | Search candidates must remain members of the supplied safe set; sampled worlds never replace the observed root state. |
| Core application | Observation reducer, `HeuristicPolicy`, `ActionSafetyGate`, decision-record assembly | `heuristic_v0` is the mandatory incumbent and fallback; the safety gate stays after every search selection. |
| Core ports | `TraceSink` | Engine-neutral transition, random-source, and deadline/work-budget ports are absent and need deliberate public API design. |
| Records | Decision-record schemas and Python models through v2 | v2 cannot represent a successful searched decision with a distinct fallback reason or deterministic search summary without abusing its error field. |
| Runtime | Showdown protocol/client/team adapters; `BattleSession`, `BattleCoordinator`, `MeasurementSession`; telemetry sinks | Search composition must enter through runtime policy composition without moving engine or clock dependencies into Core. |
| Lab | Frozen-registration validation, evaluation/statistical helpers, measurement runner, reports | The runner can retain trace lifecycle ownership, but no oracle, differential runner, closed-world evaluation artifact, or calibration pipeline exists. |
| Schemas | Engine capability v1, search contract v1, implementation/run/calibration manifests and validation tooling | Existing schema versions must be preserved. Any incompatible M2 field set requires a new schema version and explicit migration tests. |
| Registrations | Frozen `m1-5-core-comparisons-v1.json`; active determinization and DUCT comparisons; determinization execution spec v4 | Registered arm IDs, metrics, thresholds, pool rules, and determinization values are immutable inputs to M2. |
| Tooling and CI | docs, architecture, schemas, versions, registration validation, package smoke, protocol/safety smoke, `pr-gate` | M2 adds isolated oracle, search-extra, sentinel, corpus, and deterministic-reproducibility gates without weakening existing gates. |

### Missing package areas and enforcement

| Package/tool | Missing baseline area | Intended owner |
|---|---|---|
| `battlebelief-core/domain` | `closed_world`, engine-capability domain representation, search state/action/value types | Core, with no files, engine imports, clocks, Node, or network |
| `battlebelief-core/application` | `engine_eligibility`, deterministic search orchestration, determinization, information-set DUCT, mode-independent result types | Core |
| `battlebelief-core/ports` | engine-neutral `TransitionModel`, injected random stream/factory, deterministic work-budget interface | Core protocols only |
| `battlebelief-runtime/adapters` | `poke_engine` artifact verifier, mapping, backend, sentinel; runtime clock/deadline; search telemetry adapter | Runtime |
| `battlebelief-runtime/composition` | search-policy assembly, engine qualification loading, live-anytime composition | Runtime |
| `battlebelief-runtime/public_api` | optional search configuration and decision API | Runtime; base imports must still work without the extra |
| `battlebelief-lab` | `oracle/showdown`, `differential`, closed-world artifact tooling, search evaluation, calibration, reporting extensions | Lab |
| Runtime packaging | `[search]` extra | Added only in the engine-artifact task after the exact distribution rule is approved |
| Architecture tooling | confinement of `poke_engine` imports to the Runtime adapter; new Core forbidden dependencies; Lab oracle boundary | `tools/check_architecture.py` and its tests |
| Package smoke/CI | isolated Runtime search-extra install, Lab oracle profile, Gen-9 sentinel, differential corpus validation, deterministic reproduction | `tools/smoke_packages.py`, dedicated tools, and `.github/workflows/pr.yml` |

### Concrete integration points

1. **`BattleSession`:** it currently calls a request-only policy and then the independent `ActionSafetyGate`. M2 needs a versioned, state-aware runtime policy boundary that receives the current `ObservedState`, the exact `SafeSubmissionSet`, and the request identity. Its result must carry a submission plus non-secret decision telemetry. `BattleSession` remains responsible for the final safety check and submission.
2. **`MeasurementSession`:** it remains a wrapper around a runtime session. It records decision and search measurements but must not obtain sampled worlds or opponent-private oracle data.
3. **Decision records:** existing v1/v2 readers and validation stay supported. A proposed v3 separates deterministic decision content from operational measurements and gives successful fallback its own field. The final shape requires Maintainer Decision MD-10 before a contract/schema task.
4. **`MeasurementRunner`:** Lab retains trace ownership and run finalization. It should depend on a small measured-session protocol so both runtime battles and local oracle evaluation sessions can be driven without importing a Lab adapter into Runtime.
5. **Bindings:** execution must resolve every digest before a run: runtime and contract sets, implementation, environment, Showdown source/build, engine source/build/wheel, capability manifest/evidence, differential corpus, ruleset, closed-world prior/distribution, and search configuration.

## 3. Verified upstream facts and binding policy

The facts in this section are a dated research snapshot, not selected BattleBelief pins. No upstream commit or artifact becomes qualified merely by being named here.

### Pokémon Showdown snapshot observed on 2026-08-05

- The observed upstream `master` revision was `6a1836dd71c0718e923206f3d089e61074410868`; BattleBelief has not selected it as the M2 pin.
- The package metadata reports version `0.11.11`, MIT licensing, `node >=16`, and a lockfile with `lockfileVersion: 2`.
- At that same revision, the official launcher and server entry point reject Node versions below 22, while the official test workflow still names Node 18.x. This conflict prevents Task 23 from selecting a supported Node version.
- The official simulator documentation defines newline-delimited standard-input operation and says each simulated battle uses its own subprocess. The direct simulator request form has no live-server `rqid`.

### `poke-engine` snapshot observed on 2026-08-05

- The observed `main` revision, also peeled from tag `v0.0.48`, was `bcf13823abc162a608e187b26bbf683f759f385e`; BattleBelief has not selected it as the M2 pin.
- The repository is MIT-licensed. Cargo exposes `gen9` and `terastallization` features, but the Python binding crate defaults to the engine's `gen4` feature. A qualified Gen 9 artifact therefore needs explicit, recorded features.
- The Python build metadata uses `maturin >=1,<2` and declares no Python version range. The repository requirements file pins `maturin==1.7.1` for its own helper flow.
- The upstream publish workflow builds an sdist. PyPI release `0.0.48` exposed only `poke_engine-0.0.48.tar.gz` when inspected, not platform wheels, and declared no `Requires-Python`. Its observed PyPI SHA-256 was `070010686f2aedff11e25137e696e301ccd80fd57c805d255464067fc905ca12`; this is an upstream sdist fact, not an approved BattleBelief artifact digest.
- The upstream project describes mechanics limitations; its Python API exposes state transition/reversal and Monte Carlo search with duration or exact iterations and thread controls. None of those interfaces is evidence of Gen 9 parity.

### Reproducible binding rule for future tasks

Every selected upstream must be captured in immutable manifests, never inferred at runtime from a version string:

- canonical repository URL, exact 40-character commit, declared license, license-file digest, and retrieval date;
- source tree or allowlisted source-file manifest with SHA-256 digests, submodule state, lockfile digest, and clean-tree assertion;
- exact compiler/interpreter/build-tool versions, target triple, Python tag/ABI/platform tag, build command, environment allowlist, and explicitly enabled Cargo/npm features;
- source-manifest digest, build-manifest digest, produced artifact or wheel SHA-256, size, and adapter version;
- supported Python/OS cells backed by actual isolated install and sentinel evidence, not upstream inference;
- local-build policy: an explicit developer/evidence command may build from the exact source manifest into an isolated directory; the public Runtime path must never trigger an implicit source build;
- prebuilt-wheel policy: only an exact digest from the approved artifact index may install in a qualified path; filename, package version, import version, embedded source identity, and sidecar manifest must agree.

An unavailable fact remains a Maintainer decision or an unqualified capability. A future task must not invent a revision, wheel, digest, support claim, or build result.

## 4. Maintainer decisions required before dependent implementation

No decision below is resolved by this plan. The recommendation is a review proposal. The approving task must record the Maintainer choice in an accepted authority before code relying on it merges.

### MD-01 — `poke-engine` artifact distribution

- **Options:** (A) publish BattleBelief-built wheels in GitHub Releases or another immutable project-controlled artifact store; (B) consume an upstream wheel when one exists; (C) require every user to build locally.
- **Advantages:** A gives exact digests and a testable support matrix; B minimizes project distribution work; C avoids distributing third-party binaries.
- **Disadvantages:** A adds release, retention, provenance, and license obligations; B is currently unavailable and would surrender feature/build control; C creates toolchain friction and makes the public install path depend on source builds.
- **Recommendation:** A, with a signed/immutable artifact index and source/build manifests, while retaining an explicit local evidence build command.
- **Consequences:** the Maintainer must choose hosting, retention, supported target cells, and release authority; Task 25 is blocked until approval.

### MD-02 — controlled local build versus wheel consumption

- **Options:** (A) qualified runtime consumes only approved wheels; local builds are separate, unqualified until attested; (B) runtime may fall back to a local build; (C) source-only installation.
- **Advantages:** A keeps runtime behavior reproducible and fail-closed; B improves convenience; C simplifies artifact publication.
- **Disadvantages:** A requires producing wheels; B can silently change mechanics and toolchains; C conflicts with a lightweight optional Runtime install.
- **Recommendation:** A. A local build can become qualified only after producing the same full manifest, wheel, digest, isolated install smoke, and differential evidence as a prebuilt wheel.
- **Consequences:** missing/mismatched wheels are stable `artifact_unavailable` or `artifact_mismatch` fallback reasons, never implicit compilation.

### MD-03 — Node version and Showdown lifecycle

- **Options:** (A) select the lowest Node 22 patch validated against the chosen Showdown commit; (B) use the package metadata minimum Node 16; (C) follow the upstream CI Node 18 cell.
- **Advantages:** A follows executable checks; B follows declared packaging metadata; C follows an official tested workflow.
- **Disadvantages:** the three upstream signals conflict; B and C are rejected by current entry-point checks, while A exceeds package/CI declarations and still needs Windows/Ubuntu proof.
- **Recommendation:** A only after a dedicated probe confirms build, simulator, server lifecycle, and both CI OS cells. Record the exact Node binary version and digest/source in the environment manifest.
- **Consequences:** the conflict must be cited in the approval record. Task 24 may not claim support from metadata alone.

### MD-04 — Oracle process boundary

- **Options:** (A) one `simulate-battle` stdio process per fixture/battle, plus a separate loopback-server lifecycle smoke; (B) one long-lived custom Node worker multiplexing battles; (C) a local Showdown server for all oracle operations.
- **Advantages:** A matches the official simulator contract and isolates crashes; B amortizes startup; C exercises server requests and live `rqid` behavior.
- **Disadvantages:** A costs process startup and has simulator identities unlike live requests; B adds a custom protocol and hidden mutable state; C adds networking/lifecycle complexity to mechanics tests.
- **Recommendation:** A for differential authority, with a minimal C smoke restricted to loopback and random free ports. Do not make server transport the mechanics oracle.
- **Consequences:** Task 24 needs process-tree shutdown, separate startup/per-command/fixture timeouts, and no public network access.

### MD-05 — Oracle request identity without `rqid`

- **Options:** (A) version `RequestIdentity` with `live_rqid` and `oracle_sequence` variants; (B) synthesize an integer `rqid`; (C) keep oracle decisions outside `BattleSession` entirely.
- **Advantages:** A preserves semantic honesty and lets the safety gate compare typed identities; B minimizes code changes; C avoids touching runtime identity types.
- **Disadvantages:** A requires backward-compatible schema/model evolution; B falsely equates two upstream protocols; C duplicates decision/safety/measurement orchestration.
- **Recommendation:** A: a per-battle monotonic oracle sequence plus canonical request digest, never a fabricated server `rqid`.
- **Consequences:** approval is required before Task 33; live M1 records remain readable and unchanged.

### MD-06 — engine-neutral `TransitionModel` port

- **Options:** (A) a typed Core protocol over opaque prepared worlds and engine-neutral search actions; (B) a generic callback bag; (C) expose `poke-engine` state strings to Core.
- **Advantages:** A keeps algorithms pure and testable; B is small; C closely mirrors the backend.
- **Disadvantages:** A requires deliberate state/action/view contracts; B weakens invariants and typing; C violates package boundaries and couples Core to backend serialization.
- **Recommendation:** A, with methods for root preparation, player information view/key, per-player legal actions, joint transition/chance resolution, terminal/value evaluation, health/identity, and deterministic transition-work accounting.
- **Consequences:** Task 27 freezes the public protocol only after adapter-spike evidence from Task 25; backend-specific strings remain Runtime-private.

### MD-07 — observed-state, world, and action mapping

- **Options:** (A) one explicit canonical mapping layer with a lossless mapping report; (B) ad hoc conversion in every search algorithm; (C) make engine state the project domain model.
- **Advantages:** A centralizes validation and feature detection; B is initially fast; C removes conversion.
- **Disadvantages:** A needs exhaustive negative fixtures; B invites divergence; C makes a non-authoritative backend authoritative and risks hidden-information leakage.
- **Recommendation:** A in `battlebelief-runtime/adapters/poke_engine`, returning either a prepared world and required capability IDs or a typed mapping failure. Root submissions map only from `SafeSubmissionSet`; deeper actions use engine-neutral `SearchAction` IDs.
- **Consequences:** mapping mismatch is ineligible, never “best effort.” The mapping report records field/capability presence but no private world in a public decision record.

### MD-08 — capability-ID taxonomy and manifest evolution

- **Options:** (A) introduce versioned, namespaced atomic IDs and engine-capability schema v2 with `exact`, `bounded_approximation`, `unsupported`, and `unknown`; (B) encode only exact/unsupported in v1; (C) use free-form strings generated by the adapter.
- **Advantages:** A can express the accepted four-way semantics and evidence links; B avoids migration; C is flexible.
- **Disadvantages:** A requires a normative contract/schema decision and v1 compatibility; B cannot faithfully encode unknown and build/platform evidence; C makes eligibility unstable.
- **Recommendation:** A, using an immutable catalog such as `gen9.mechanic.terastallization.damage` and `gen9.transition.status.*`, with catalog version/digest and per-ID evidence. Preserve v1 readers; do not mutate v1.
- **Consequences:** this plan identifies a real expressiveness gap but does not amend the contract. Tasks 26-28 are blocked on Maintainer approval.

### MD-09 — versioned differential corpus format

- **Options:** (A) canonical JSON fixture index plus one canonical JSON input/expected file per case; (B) a single monolithic JSON; (C) executable Python fixtures.
- **Advantages:** A permits small reviewable additions and independent file digests; B has one artifact; C is expressive.
- **Disadvantages:** A needs an index and closure validation; B creates noisy diffs; C is not a data-only reproducible corpus.
- **Recommendation:** A. Every case binds ruleset, seed, capability IDs, initial full state, action sequence, compared observations, expected divergence class, and immutable provenance. The index digest covers sorted file digests.
- **Consequences:** any classification change creates a new corpus version and explicit migration/evidence record; favorable and unfavorable results are never rewritten in place.

### MD-10 — search telemetry and Decision Record evolution

- **Options:** (A) Decision Record v3 stores only deterministic, non-secret search summary and a separate fallback reason; operational duration/counters live in a linked Search Measurement artifact; (B) put all telemetry in the decision row; (C) overload the v2 error field.
- **Advantages:** A permits byte-identical deterministic rows and full live telemetry; B is convenient for analysis; C avoids a new schema.
- **Disadvantages:** A adds a linked record/schema; B makes rows clock-dependent; C violates v2 status invariants and conflates successful fallback with failure.
- **Recommendation:** A. Search summary may include algorithm/mode/config digest, fixed work, worlds/simulations, chosen safe-set index, eligibility outcome, and stable fallback class. It excludes hidden worlds, opponent-private data, wall-clock timestamps, hostnames, and local paths.
- **Consequences:** Tasks 32-34 need versioned schemas/readers and migration tests; v1/v2 canonical vectors remain unchanged.

### MD-11 — evaluation-only closed-world prior artifact

- **Options:** (A) a small reviewed, licensed, manually sourced complete-team artifact dedicated to M2 evaluation; (B) derive from replays or current metagame data; (C) embed sets in Python tests.
- **Advantages:** A stays within M2 and is auditable; B is more representative; C is simple.
- **Disadvantages:** A is limited and cannot support external strength claims; B pulls M3 ingestion/meta work forward; C lacks independent provenance/versioning.
- **Recommendation:** A, with complete correlated opponent-team worlds, rational or exact decimal masses, source/license metadata, prior digest, distribution transform version, and no `OTHER`.
- **Consequences:** the Maintainer must approve source/license and scope. Task 29 cannot use protected-pool or replay information.

### MD-12 — composition of `deterministic_benchmark` and `live_anytime`

- **Options:** (A) one pure Core search kernel with distinct Runtime budget controllers; (B) two algorithm implementations; (C) simulate live time using fixed work.
- **Advantages:** A shares semantics but keeps clock out of Core; B isolates behavior; C simplifies testing.
- **Disadvantages:** A needs a careful interrupt protocol; B can drift; C does not implement an anytime deadline.
- **Recommendation:** A. Core advances explicit work units and exposes safe checkpoints. Runtime supplies fixed work or an injected monotonic deadline. The reference deterministic path is one thread.
- **Consequences:** live output is not deterministic evidence or a teacher target. Timeout returns the last independently safety-checkable incumbent.

### MD-13 — calibration evidence and implementation/run binding

- **Options:** (A) introduce backward-compatible implementation/run binding versions that explicitly reference all M2 artifacts and reuse calibration-evidence v3 if sufficient; (B) pack digests into existing generic component fields; (C) mutate existing schema versions.
- **Advantages:** A is explicit and preserves history; B may avoid schemas; C minimizes filenames.
- **Disadvantages:** A adds versions and migration work; B can hide missing bindings; C breaks frozen evidence.
- **Recommendation:** A. First prove whether calibration-evidence v3 is sufficient; version it only if a required fact cannot be represented. Existing implementation/run versions remain valid and unchanged.
- **Consequences:** Task 34 must demonstrate closure from run binding to source bytes and artifacts before any registered evaluation.

### MD-14 — failure and fallback classification

- **Options:** (A) a versioned stable public fallback taxonomy with private diagnostic details; (B) expose backend exceptions; (C) one generic failure.
- **Advantages:** A supports reproducible counting without leaking environment details; B is debuggable; C is compact.
- **Disadvantages:** A needs mapping and schema governance; B is unstable and may expose paths; C hides mechanism failures.
- **Recommendation:** A, separating at least missing extra/artifact, artifact mismatch, unknown/unsupported/approximate capability, state/action mismatch, unhealthy backend, backend error, no safe candidate, deadline, and safety rejection. Exact public labels require Maintainer approval.
- **Consequences:** every path selects `heuristic_v0`, remains counted in deployment and mechanism views, and retains sanitized diagnostics in Lab-only evidence.

### MD-15 — Runtime version and milestone phase

- **Options:** (A) leave `0.2.0`/`M1` through M2 implementation and make one separately approved acceptance change after evidence; (B) change them when the public search API lands; (C) change them in Task 23.
- **Advantages:** A avoids premature status claims; B aligns API availability; C signals intent early.
- **Disadvantages:** A temporarily understates feature presence; B may imply qualification before evidence; C contradicts this task's boundary.
- **Recommendation:** A. The evidence task proposes, but does not assume, the exact version/phase transition.
- **Consequences:** Task 23 changes neither value. Task 36 is blocked on Maintainer acceptance and real evidence.

### MD-16 — DUCT work budget and non-registered configuration values

- **Options:** (A) define and precommit one transition-work-matched DUCT configuration through a new calibration specification/binding before evaluation; (B) reuse a backend/default configuration; (C) tune DUCT after observing the registered comparison.
- **Advantages:** A makes mechanism budgets comparable and outcome-blind; B is quick; C may find a stronger configuration.
- **Disadvantages:** A requires an explicit parameter owner and calibration evidence; B is unbound and backend-dependent; C contaminates the registered comparison.
- **Recommendation:** A. Keep the accepted Search-v0 semantics fixed, calibrate only parameters the registration permits, bind the complete configuration and selection procedure before Task 35, and report both deployment and mechanism work.
- **Consequences:** Task 34 must stop if the accepted registration/contracts do not identify who owns a required parameter. No value may be invented by this plan or selected from evaluation outcomes.

### MD-17 — M2 evaluation result and evidence-index schemas

- **Options:** (A) add dedicated, minimal versioned M2 result/report and evidence-index schemas that reference existing metric/statistical authorities; (B) extend existing generic measurement-result schemas with a new version; (C) emit Markdown-only reports.
- **Advantages:** A makes both budget views and failure counts machine-checkable without changing old schemas; B may reduce schema count; C is easy to read.
- **Disadvantages:** A adds schema governance; B risks coupling synthetic M1.5 records to M2 semantics; C cannot enforce closure or prevent omitted failures.
- **Recommendation:** A, with no duplicated thresholds and with existing measurement records referenced by digest.
- **Consequences:** Tasks 35-36 create the exact schemas named below only after approval; all earlier schemas stay valid and byte-identical.

## 5. Target architecture and import boundaries

```text
Lab Showdown oracle ──authoritative fixtures──► Differential runner
        │                                            │
        │                                            ▼
        │                                  Capability evidence/manifest
        │                                            │
        ▼                                            ▼
Lab evaluation session ─► Runtime search composition ─► Core eligibility
                                      │                       │
                                      ▼                       ▼
                           Runtime poke-engine adapter ◄─ Core search kernels
                                      │
                                      ▼
                               verified wheel only
```

### Responsibility map

- **Core:** public protocols and immutable types; eligibility; evaluation-only closed-world filtering/sampling; deterministic work accounting; determinization and information-set DUCT; orchestration that accepts all clocks/randomness/data through inputs or ports. No filesystem, environment, Node, network, `poke_engine`, global clock, or global random source.
- **Runtime:** exact artifact verification before import/use; all `poke_engine` imports under one adapter subtree; state/action conversion; backend health; monotonic clock/deadline; optional-extra composition; public search API; conversion from Core results into stable telemetry; final Runtime use of `ActionSafetyGate`.
- **Lab:** source acquisition/build verification for local Showdown; oracle process lifecycle; full-state fixtures; differential corpus and runner; prior artifact construction; offline paired evaluation; calibration and report generation; binding and artifact closure validation.

Allowed new dependency edges are Core-internal, Runtime to approved Core APIs, Lab to Core, and Lab to approved Runtime public/testing APIs. Runtime never imports Lab. Core never imports either outer package. Lab oracle full states never enter a player observation except through an authoritative player-view reduction with leakage tests.

## 6. Strict serial Task/PR sequence

Every implementation task starts only from the merged predecessor. Each PR has one reviewable authority boundary and may not absorb a later task because it appears small.

| Task | Scope | Why the boundary is independently reviewable |
|---|---|---|
| 23 (A) | This plan only | Establishes decisions and file-level work without code or contract mutation. |
| 24 (B) | Local Showdown oracle and Lab oracle smoke | Establishes the authoritative side before introducing the non-authoritative engine. |
| 25 (C) | `poke-engine` artifact, Runtime `[search]`, real Gen-9 sentinel | Proves an installable backend artifact without claiming mechanics eligibility. |
| 26 (D) | Capability catalog and manifest/schema evolution | Makes the qualification vocabulary reviewable before decision logic or favorable evidence exists. |
| 27 (E) | Core eligibility, transition port, fail-closed heuristic fallback | Reviews the safety boundary against synthetic fakes before differential qualification. |
| 28 (F) | Versioned differential corpus and runner | Produces evidence and qualified manifests without adding search algorithms. |
| 29 (G) | Evaluation-only closed-world distribution | Reviews hidden-information semantics and provenance independently of search. |
| 30 (H) | `determinization_search_v0` | Implements only the already registered deterministic baseline. |
| 31 (I) | `information_set_duct_v0` | Reviews every information-set invariant against the same distribution. |
| 32 (J) | Deterministic and live-anytime operating modes | Adds work/deadline control after algorithm semantics are stable. |
| 33 (K) | Runtime composition, public Search API, session integration | Integrates qualified pieces while preserving the post-search safety gate. |
| 34 (L) | Implementation/run bindings and calibration evidence | Closes provenance before evaluation produces decision evidence. |
| 35 (M1) | Registered development evaluation | Runs the two frozen comparisons without changing their gates or opening pools. |
| 36 (M2) | M2 acceptance/evidence report | Separates evidence review and any status proposal from experiment execution. |

No PR combines oracle, engine artifact, eligibility, both search algorithms, and evaluation. Tasks 24-36 may be renumbered by the Maintainer if repository scheduling requires it, but their dependency order and scopes remain serial unless a revised accepted plan says otherwise.

## 7. Detailed implementation tasks

Paths below are repository-relative. “Delete: none” is intentional: existing schema versions, fixtures, registrations, and bindings are retained for compatibility.

### Task 23 (A): Approve the plan-only boundary

**Purpose:** Review M2 sequencing and decide which Maintainer decisions may advance to normative or implementation work. This task creates no implementation authority by itself.

**Files:**

- Create: `docs/superpowers/plans/2026-08-05-battlebelief-m2-engine-qualified-search-prototype.md`.
- Modify: none.
- Delete: none.

**Public APIs, imports, schemas, and artifacts:** none. The plan is non-normative and must not be registered as a contract.

**Allowed imports:** none; this is tracked Markdown only.

**Tests and negative review first:**

1. Confirm the base commit and clean tree before writing.
2. Run documentation governance/link checks and whitespace checks.
3. Scan the complete diff for code, dependency, lockfile, frozen-registration, Task-21 binding/digest, Runtime version/phase, archive, pool, and status-claim changes.
4. Scan for secrets, absolute local paths in tracked content, invented pins/digests/results, and prohibited placeholder markers.

**Implementation checklist:**

- [ ] Reconfirm HEAD, `origin/main`, and the clean starting tree.
- [ ] Validate frontmatter, repository-relative links, headings, and every required plan section.
- [ ] Run the applicable documentation/schema/architecture/version/frozen-artifact checks and whitespace scan.
- [ ] Inspect the complete diff and report unexecuted PR-only checks without committing, pushing, or opening a PR.

**Failure/fallback and provenance:** a failed check blocks approval; it does not justify weakening a gate. The frontmatter identifies this file as proposed, non-normative, versioned, dated, and M2-scoped.

**Acceptance criteria:** exactly this plan file is changed; all applicable plan-only gates pass; every unresolved technical issue is an MD item with options, trade-offs, recommendation, consequences, and required approval.

**Non-goals:** all production code, dependencies, schemas, manifests, registrations, evidence, version changes, commits, pushes, and PR creation.

**Prerequisite:** baseline commit `cfc526ca1558869e674769daf19b9aa09c00abf0` with M1.5 complete and frozen. **Blocks:** every later task until the Maintainer selects or defers its blocking MD items. **Safe review boundary:** documentation-only scope makes accidental milestone expansion visible in one diff.

### Task 24 (B): Add the local Pokémon Showdown oracle and Lab oracle smoke

**Purpose:** Establish a hermetic, authoritative Gen 9 mechanics oracle before integrating `poke-engine`.

**Files:**

- Create: `packages/battlebelief-lab/src/battlebelief_lab/oracle/__init__.py`.
- Create: `packages/battlebelief-lab/src/battlebelief_lab/oracle/showdown/{__init__.py,errors.py,manifests.py,process.py,protocol.py,session.py}`.
- Create: `packages/battlebelief-lab/tests/oracle/showdown/{test_manifests.py,test_process.py,test_protocol.py,test_session.py,test_no_network.py}`.
- Create: `packages/battlebelief-lab/tests/fixtures/showdown_oracle/{minimal_gen9ou_input.json,tera_transition_input.json}` containing only deterministic project-authored fixtures.
- Create: `schemas/manifests/showdown-oracle-source.schema.json` and `schemas/manifests/showdown-oracle-build.schema.json` **[NEW SCHEMA v1]**.
- Create: `schemas/examples/manifests/showdown-oracle-source.valid.json` and `showdown-oracle-build.valid.json`.
- Create: `tools/build_showdown_oracle.py` and `tools/smoke_lab_oracle.py`.
- Modify: `packages/battlebelief-lab/pyproject.toml` to add an explicit `oracle` extra only if approved by MD-03/04 and required by the chosen launcher; preserve the base Lab install.
- Modify: `tools/check_schemas.py`, `tools/smoke_packages.py`, `tests/tooling/test_schema_examples.py`, `tests/tooling/test_package_smoke_tool.py`, and `.github/workflows/pr.yml` for schema registration and isolated Ubuntu/Windows oracle-profile smoke.
- Modify: `tools/check_architecture.py` and `tests/tooling/test_architecture.py` to confine Node/process imports and oracle full-state types to Lab.
- Delete: none; do not vendor or commit the Showdown source tree or its build output.

**Public types and APIs:** `ShowdownSourceManifest`, `ShowdownBuildManifest`, `ShowdownOracleConfig`, `ShowdownOracleSession`, `OracleRequestIdentity`, `OracleResult`, and the stable `OracleFailureClass` are **[PUBLIC LAB API]**. `ShowdownOracleSession` is evaluation-only and must not appear in Runtime's public API.

**Allowed imports:** Lab oracle code may import the standard-library process/network primitives and Lab/Core value types. It may use only approved Runtime public/testing APIs when session integration is later required. Core and Runtime must not import this package.

**Process and binding design:**

- Bind an exact Maintainer-approved Showdown commit, canonical upstream URL, MIT license file/digest, package-lock digest, source-manifest digest, exact Node/npm versions, build command, build-output digest, OS/architecture, and Lab oracle adapter version.
- Treat the selected upstream `package-lock.json` as immutable input. Use `npm ci` with the approved flags in a clean verified checkout, prohibit `npm install` and lock regeneration in the evidence path, fail if the lock changes, and bind the lockfile, npm configuration, dependency tree/build output, and command to the build manifest.
- Checkout/build into an ignored temporary or cache directory verified against the source manifest. Reject a dirty or mismatched tree. Never write the local checkout path or hostname into canonical artifacts.
- Use one `simulate-battle` stdio subprocess per fixture or battle. Encode and decode newline-delimited commands with strict message size, JSON shape, and state-machine checks.
- Seed every fixture explicitly. Record seed-domain labels separately from evaluation/search seeds.
- Apply separate startup, input/write, response, battle, and graceful-shutdown timeouts. On exit, close stdin, wait briefly, then terminate the verified child process tree; test both normal and forced shutdown on Windows and Ubuntu.
- The server-lifecycle smoke binds only `127.0.0.1`/`::1`. It reserves an OS-assigned free port, starts and stops the server, and records only the invariant profile—not the ephemeral port—in digests. A test denies non-loopback destinations and monkeypatches network resolution/connect calls.
- CI never contacts a public Showdown host and never downloads an unpinned branch during the test phase. Source acquisition, if CI performs it, verifies the approved commit and source manifest before build; a project-controlled immutable cache is acceptable only when its digest is checked.

**Tests first:** manifest canonicalization and mismatch cases; split/partial/malformed protocol lines; deterministic fixture replay; stable request sequence/digest; process crash and stderr truncation; all timeout stages; orphan cleanup; occupied/raced port retry; loopback enforcement; source/build/Node mismatch; Windows quoting/path-with-spaces; source/build digest repeatability.

**Implementation checklist:**

- [ ] Add failing schema/canonicalization, protocol-state-machine, no-network, timeout, and process-cleanup tests.
- [ ] Implement source/build manifest parsing and strict verified `npm ci`/build orchestration.
- [ ] Implement the per-battle stdio session, typed oracle identity, timeout taxonomy, and cross-platform shutdown.
- [ ] Add deterministic fixtures, the Lab oracle profile, loopback lifecycle smoke, package smoke, architecture rules, and CI cells.
- [ ] Run focused tests twice, then all repository gates, and audit build/cache outputs before handoff.

**Negative and failure paths:** missing Node, disallowed Node, missing source, source or lock mismatch, build failure, startup timeout, malformed oracle message, protocol desynchronization, ruleset rejection, process crash, result timeout, nonzero exit, shutdown failure, or attempted external networking return a stable `OracleFailureClass`. Raw stderr is sanitized and size-bounded. None is silently retried with a different revision.

**Provenance/digests:** the oracle result references source and build manifest digests, ruleset snapshot digest, fixture digest, seed digest, adapter version, and sanitized failure class. Ephemeral port, PID, absolute path, hostname, and wall-clock time are operational logs only and excluded from canonical evidence.

**CI/package smokes:** isolated Lab base install remains green; isolated `battlebelief-lab[oracle]` install; `tools/smoke_lab_oracle.py` on Ubuntu and Windows; schema examples; architecture check; a no-public-network CI assertion.

**Acceptance criteria:** the same deterministic fixtures yield canonically identical results on repeated executions; lifecycle tests leave no child; source/build manifests close; local server smoke uses only loopback; all failures are classified; no public network is required.

**Non-goals:** `poke-engine`, differential comparison, search, eligibility, closed-world prior, Runtime integration, public battle networking, or any parity claim.

**Prerequisites:** Task 23 approval plus MD-03, MD-04, and MD-05 disposition. **Blocks:** Tasks 28 and 35. **Safe review boundary:** it proves only the authoritative oracle and its hermetic lifecycle; no non-authoritative decision path is present.

### Task 25 (C): Produce and verify the `poke-engine` artifact, Runtime `[search]`, and Gen-9 sentinel

**Purpose:** Provide a real, exactly identified Gen 9/Terastallization backend artifact and prove installation/health without qualifying mechanics.

**Files:**

- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/{__init__.py,artifact.py,errors.py,state_mapper.py,action_mapper.py,backend.py,sentinel.py}`.
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/search_status.py` for extra availability and sanitized artifact identity.
- Create: `packages/battlebelief-runtime/tests/adapters/poke_engine/{test_artifact.py,test_import_boundary.py,test_state_mapper.py,test_action_mapper.py,test_backend.py,test_sentinel.py}`.
- Create: `packages/battlebelief-runtime/tests/fixtures/poke_engine/{gen9_transition.json,gen9_tera_transition.json,minimal_search.json}`.
- Create: `schemas/manifests/engine-source.schema.json`, `engine-build.schema.json`, and `engine-artifact-index.schema.json` **[NEW SCHEMAS v1]**, plus valid examples.
- Create: `tools/build_poke_engine_wheel.py`, `tools/verify_poke_engine_artifact.py`, and `tools/smoke_gen9_engine.py`.
- Create: `artifacts/gen9ou/m2/engine/README.md` documenting manifest layout and retrieval, but commit no wheel unless repository policy and MD-01 explicitly authorize it.
- Modify: `packages/battlebelief-runtime/pyproject.toml` to add `[project.optional-dependencies].search` with the exact approved wheel-install strategy; do not add `poke-engine` to base dependencies.
- Modify: root packaging/source configuration only if needed to include small manifest files, never binary output by accident.
- Modify: `tools/check_architecture.py` and tests to allow `poke_engine` imports only in `battlebelief_runtime.adapters.poke_engine` and forbid import-time loading elsewhere.
- Modify: `tools/check_schemas.py`, `tools/check_versions.py` if extra metadata is governed, `tools/smoke_packages.py`, their tests, and `.github/workflows/pr.yml` for isolated Runtime `[search]` cells and the sentinel.
- Delete: none.

**Public types and APIs:** `EngineArtifactIdentity`, `EngineAvailability`, `PokeEngineAdapter`, `PokeEngineMappingFailure`, and `run_gen9_sentinel()` are **[PUBLIC RUNTIME API]** only through curated exports. Backend module objects and raw state strings are private. Base `import battlebelief_runtime` and status inspection work without the extra.

**Allowed imports:** Runtime may import Core ports/types. Only `battlebelief_runtime.adapters.poke_engine` may import `poke_engine`; no Core or Lab module imports the extension directly. Runtime must not import Lab.

**Artifact/build requirements:**

- Build from one approved exact commit in a clean verified tree. Explicitly enable the exact `gen9` and `terastallization` features; reject the upstream Python binding's Gen-4 default.
- Record Rust toolchain, Cargo lock digest, maturin version, build flags/features, target triple, Python ABI/tag, platform tag, source/build manifest digests, adapter version, wheel filename/size/SHA-256, and license/source origin.
- Build into an isolated output directory and install the finished wheel into a fresh environment for each supported Python/OS cell. Public Runtime never shells out to Cargo/maturin and never silently accepts the upstream sdist.
- Before backend creation, verify distribution name/version, import metadata, wheel/installed-files digest strategy, sidecar artifact manifest, selected features, target/environment compatibility, and adapter compatibility. Any disagreement fails closed.

**Real sentinel:** create a Gen 9 state; prove a normal transition and reversible/state-consistent result; exercise an actual Terastallization transition; enumerate/map legal actions; run the minimal search entry point with exact iterations, one thread, and a fixed seed if supported; assert a legal returned action and stable backend health. If upstream does not expose seed control adequate for a deterministic sentinel, record that as an unqualified or health-only property rather than faking determinism.

**Tests first:** absent extra; wrong distribution; source/build/wheel/feature/platform/adapter mismatch; corrupted sidecar; a fake import shadow; Gen-4 default artifact; mapper rejects unsupported fields/actions; Tera fixture; transition apply/reverse; minimal search; backend exception sanitization; no import on base package import; wheel installation into a clean environment.

**Implementation checklist:**

- [ ] Add failing artifact-verification, no-extra import, mapping, transition, Tera, minimal-search, and isolated-install tests.
- [ ] Implement the controlled source/build/wheel manifests and explicit Gen-9/Terastallization build command.
- [ ] Implement Runtime-only artifact verification, mapping, backend health, and sanitized failure types.
- [ ] Implement the real sentinel and isolated base/`[search]` package smokes on approved cells.
- [ ] Run focused suites and full gates; retain manifests/results but no unapproved binary publication.

**Failure/fallback:** missing extra or artifact, wrong digest/features/platform, mapping mismatch, sentinel failure, import error, panic/exception, or backend health failure returns an unavailable/unhealthy adapter identity. No search call is allowed. Runtime composition later maps it to `heuristic_v0`; this task does not yet add composition.

**Provenance/digests:** source, build, wheel, installed verification, adapter, Python, OS/architecture, and sentinel fixture/result digests are resolvable from the artifact index. No local path, hostname, compiler cache path, or secret enters the canonical manifest.

**CI/package smokes:** base Runtime without `[search]`; isolated `[search]` wheel install on every approved Python/OS cell; `tools/smoke_gen9_engine.py`; architecture import confinement; package build/sdist/wheel smoke. Unsupported matrix cells explicitly skip qualification and fail if marked supported.

**Acceptance criteria:** a real approved wheel—not a mock—passes isolated installation and the Gen-9/Tera/transition/minimal-search sentinel; the base package has no engine dependency; artifact mismatch is fail-closed; no parity or capability-exact claim is made.

**Non-goals:** capability qualification, Showdown differential evidence, Core port/eligibility, algorithms, evaluation, or publishing an artifact without separate authorization.

**Prerequisites:** Task 23 and MD-01/02 approval. The adapter spike may inspect Task 24 interfaces but does not depend on oracle code. **Blocks:** Tasks 26-28 and 33. **Safe review boundary:** reviews binary provenance and backend health independently from mechanics claims.

### Task 26 (D): Version the capability catalog and Engine Capability Manifest

**Purpose:** Establish a stable, evidence-addressable vocabulary for exact, bounded, unsupported, and unknown mechanics before eligibility can trust it.

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/domain/engine_capabilities.py`.
- Create: `packages/battlebelief-core/tests/domain/test_engine_capabilities.py`.
- Create: `schemas/manifests/engine-capability-v2.schema.json` **[NEW SCHEMA v2]** and `engine-capability-evidence.schema.json` **[NEW SCHEMA v1]**.
- Create: `schemas/catalogs/engine-capability-catalog-v1.schema.json` **[NEW SCHEMA v1]**.
- Create: `artifacts/gen9ou/m2/engine-capability-catalog-v1.json` and schema examples after the Maintainer approves the exact taxonomy.
- Create: `docs/migrations/engine-capability-v1-to-v2.md` if the documentation governance contract requires a migration note.
- Modify: `docs/contracts/engine-capabilities.md`, its frontmatter, and `docs/README.md` **only under explicit normative-change approval for MD-08**; otherwise stop this task before implementation.
- Modify: `docs/contracts/manifest-schemas.md`, `tools/check_schemas.py`, schema tests, canonicalization tests, and architecture exports.
- Delete: none; preserve `schemas/manifests/engine-capability.schema.json` v1 and its examples.

**Public types and APIs:** `CapabilityId`, `CapabilityCatalog`, `CapabilityStatus`, `CapabilityClaim`, `EngineCapabilityManifest`, and `CapabilityEvidenceRef` are **[PUBLIC CORE API]** immutable value types. They parse canonical manifests without filesystem access.

**Allowed imports:** Core standard library and existing Core canonicalization/types only. Manifest bytes are supplied by callers; Core performs no file, environment, Runtime, Lab, or engine import.

**Semantics:** each catalog ID has one status: `exact`, `bounded_approximation`, `unsupported`, or `unknown`. `exact` requires evidence refs bound to the engine artifact, oracle, ruleset, and corpus. `bounded_approximation` includes an explicit bound/condition but remains search-ineligible wherever exact is required. Missing catalog IDs are interpreted as unknown, not exact. Duplicate/overlapping claims, unknown free-form IDs, or evidence bound to another artifact are invalid.

**Tests first:** v1 remains valid under its existing schema; v2 round-trip/canonical digest; missing ID becomes unknown; all four statuses; duplicate and contradictory IDs; malformed namespaces; evidence/artifact mismatch; bounded approximation never parses as exact; catalog-digest mismatch; sorted canonical output; v1-to-v2 migration keeps original facts without elevating claims.

**Implementation checklist:**

- [ ] Obtain MD-08 and normative-change approval before editing a contract or schema index.
- [ ] Add failing v2/catalog/evidence examples, semantic tests, canonical vectors, and v1 compatibility tests.
- [ ] Implement immutable Core value types and strict four-state/catalog/evidence validation.
- [ ] Add the approved catalog and an explicitly unqualified initial manifest; do not create exact claims.
- [ ] Run schema, docs, canonicalization, Core, package, and full repository gates.

**Negative/failure paths:** unrecognized schema/catalog version, missing evidence, stale corpus/ruleset/adapter/wheel digest, or unsupported platform invalidates the manifest for qualification. Parser errors are deterministic and contain JSON pointers, not local paths.

**Provenance/digests:** manifest v2 binds catalog, engine source/build/artifact, adapter, oracle source/build, ruleset, corpus, evidence set, supported environment matrix, generation/format, and canonicalization contract digests.

**CI/package smokes:** schema example validation, canonicalization vectors, v1 compatibility, manifest-closure tool smoke, Core-only import smoke.

**Acceptance criteria:** the four accepted statuses are unambiguous; v1 artifacts remain readable and unchanged; no capability is marked exact in the initial catalog/manifest without Task 28 evidence; schema and Core types agree byte-for-byte on canonicalization.

**Non-goals:** evidence generation, eligibility decisions, engine calls, search, or changing registered gates.

**Prerequisites:** Tasks 23 and 25, MD-08 approval, and any approved normative amendment. **Blocks:** Tasks 27 and 28. **Safe review boundary:** vocabulary and validation are reviewed before any algorithm can benefit from an exact claim.

### Task 27 (E): Add the pure Core eligibility gate and fail-closed heuristic fallback

**Purpose:** Decide, without backend imports or I/O, whether an engine-backed search may start for the exact observed decision.

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/ports/transition_model.py` and `random_source.py`.
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/search.py`.
- Create: `packages/battlebelief-core/src/battlebelief_core/application/engine_eligibility.py` and `search_policy.py`.
- Create: `packages/battlebelief-core/tests/ports/test_transition_model_contract.py`.
- Create: `packages/battlebelief-core/tests/application/{test_engine_eligibility.py,test_search_policy_fallback.py}`.
- Create: `packages/battlebelief-core/tests/fakes/{transition_model.py,random_source.py}` with deterministic test-only fakes.
- Modify: Core `__init__.py` export surfaces for approved public types.
- Modify: `tools/check_architecture.py` and tests to forbid engine, filesystem, environment, network, process, global clock, and global randomness in the new Core areas.
- Modify: decision-record error/fallback enum only in a later version approved by MD-10/14; this task keeps its internal result taxonomy separate.
- Delete: none.

**Public types and APIs:** `TransitionModel[WorldT, ActionT]`, `PreparedWorld`, `SearchAction`, `PlayerView`, `InformationStateKey`, `TransitionOutcome`, `TransitionWork`, `RandomStream`, `SearchEligibilityInput`, `SearchEligibilityDecision`, `EligibilityReason`, `SearchCandidate`, `SearchDecision`, and `EngineQualifiedSearchPolicy` are **[PUBLIC CORE API]**. Exact signatures are frozen by tests after Task-25 adapter evidence and MD-06/07 approval.

**Allowed imports:** the new modules import only Core domain/ports/application code and the standard library. Test fakes stay under Core tests. No adapter, filesystem, environment, global random, clock, process, or network import is allowed.

**Pure decision:** the function consumes exactly the observed state, authoritative `SafeSubmissionSet`, required capability IDs produced by validated mapping, closed-world distribution identity/support summary, capability manifest, and backend/artifact health identity. It returns eligible only when:

- the safe set is non-empty and every root candidate is an exact member;
- observed state/request identity and prepared-root identity agree;
- distribution generation/format/ruleset and public-evidence digest agree;
- backend source/build/wheel/adapter/platform identities match the manifest;
- every required capability exists in the approved catalog, is `exact`, and has applicable evidence;
- no mapping or health failure is present.

Unknown, unsupported, bounded approximation, missing evidence, any mismatch, or backend failure is ineligible. There is no precedence that can convert a bounded approximation into exact.

**Tests first:** table-test every reason and precedence; empty/mutated/stale safe set; each capability status; missing catalog item; manifest/artifact/ruleset/prior/distribution/adapter mismatch; unhealthy backend; mapping error; deterministic reason ordering; no backend method called when ineligible; eligible boundary calls the injected search function once; any search exception/invalid candidate/no result returns the exact injected `heuristic_v0` result.

**Implementation checklist:**

- [ ] Freeze the approved TransitionModel and mapping evidence as protocol contract tests before implementation.
- [ ] Add failing exhaustive eligibility truth-table and heuristic-identity fallback tests.
- [ ] Implement the pure protocols/types, eligibility decision, and precomputed-incumbent orchestration.
- [ ] Add architecture negative fixtures and fake model/random conformance tests.
- [ ] Run Core-focused, architecture, package, and full repository gates.

**Failure/fallback:** the policy obtains `heuristic_v0` first as the safe incumbent. Eligibility denial or subsequent backend/search failure returns that unchanged submission with a stable internal fallback class. If heuristic selection itself cannot return a member of the safe set, the existing safety/forfeit behavior remains authoritative; search never invents an action.

**Provenance/digests:** decision includes only input identity digests, required capability IDs, eligibility outcome, stable reason, fixed search config/work identity when applicable, and selected safe-set index. It contains no prepared world, hidden set, raw backend exception, time, path, or host.

**CI/package smokes:** Core import smoke without Runtime; architecture negative fixtures attempting `poke_engine`, file, Node, clock, or network imports; deterministic fake transition conformance.

**Acceptance criteria:** the truth table is exhaustive and deterministic; search cannot start unless all mechanics are exact and identities match; every denial/error returns registered `heuristic_v0`; the post-policy Runtime safety gate remains required.

**Non-goals:** real engine evidence, differential corpus, final record schema, either search algorithm, Runtime composition, or capability elevation.

**Prerequisites:** Tasks 25-26 and MD-06/07/08/14 decisions. **Blocks:** Tasks 28-33. **Safe review boundary:** safety policy is proven with fakes before real qualification or algorithm complexity can mask it.

### Task 28 (F): Add the versioned Showdown-versus-`poke-engine` differential corpus and runner

**Purpose:** Generate reproducible, reviewable evidence for each capability claimed exact.

**Files:**

- Create: `packages/battlebelief-lab/src/battlebelief_lab/differential/{__init__.py,corpus.py,runner.py,classifier.py,evidence.py,report.py}`.
- Create: `packages/battlebelief-lab/tests/differential/{test_corpus.py,test_runner.py,test_classifier.py,test_evidence.py,test_report.py}`.
- Create: `schemas/evaluation/differential-corpus.schema.json`, `differential-fixture.schema.json`, `differential-result.schema.json`, and `capability-qualification.schema.json` **[NEW SCHEMAS v1]** with valid/invalid examples.
- Create: `artifacts/gen9ou/m2/differential/corpus-v1/{index.json,fixtures/*.json,README.md}` after MD-09 and fixture review; keep cases minimal and project-authored or properly licensed.
- Create: `tools/validate_differential_corpus.py` and `tools/run_engine_differential.py`.
- Modify: capability manifest/evidence artifacts from Task 26 by creating a new evidence-qualified version; never rewrite an earlier digest in place.
- Modify: `tools/check_schemas.py`, `tools/smoke_packages.py`, their tests, and `.github/workflows/pr.yml` to validate the corpus on all PRs and run the bounded differential profile on approved engine/oracle cells.
- Modify: Lab package exports and optional test/oracle profile metadata as needed; no Runtime-to-Lab edge.
- Delete: none; deprecated corpus versions remain immutable and addressable.

**Public types and APIs:** `DifferentialCorpus`, `DifferentialFixture`, `DifferentialRunner`, `CanonicalMechanicsObservation`, `DivergenceClass`, `FixtureResult`, and `CapabilityQualificationEvidence` are **[PUBLIC LAB API]**.

**Allowed imports:** Lab may import Core capability/types and the approved Runtime `PokeEngineAdapter` public surface. It calls the Lab oracle internally. It must not import private extension objects, and Runtime/Core must not import Lab.

**Corpus and runner contract:**

- Each fixture binds corpus version/digest, fixture ID/digest, generation/format/ruleset snapshot, deterministic seed, initial authoritative full state, explicit public views, ordered joint actions/chance inputs, capability IDs exercised, observation checkpoints, and expected classification policy version.
- The runner executes the same canonical transition intent against the exact local Showdown oracle and Runtime adapter artifact, converts both outputs to a common mechanics observation, and compares only declared fields with exact or explicitly approved normalization.
- Result binds oracle commit/source/build digest, engine commit/source/build/wheel/adapter digest, ruleset snapshot, corpus/fixture digest, environment, and runner/classifier versions.
- Divergences are `match`, an approved stable known class tied to a non-exact capability, or `unclassified`. A runtime crash/timeout/malformed output is never a match.
- An `exact` capability requires all applicable fixtures to run, zero unclassified divergences, zero known divergence affecting that capability, and the approved environment matrix. Missing cases/evidence remain unknown.

**Tests first:** corpus closure and digest vectors; minimal one-field mutation changes digest; duplicate IDs; missing referenced fixture; undeclared capability; state/action mapping mismatch; oracle/engine timeout/crash; field-order normalization; invalid numeric/speed/damage/status comparisons; classifier version mismatch; evidence bound to wrong artifact/ruleset; expected known divergence cannot be reclassified in place; exact claim rejected with one skipped/unclassified/failed case.

**Implementation checklist:**

- [ ] Add failing corpus/schema/closure/classification/evidence tests, including skipped and crashed fixtures.
- [ ] Implement canonical corpus loading, common observation conversion, runner, immutable raw results, and classifier.
- [ ] Add reviewed minimal fixtures covering every proposed exact capability and known non-exact boundaries.
- [ ] Run the real oracle-versus-engine matrix, create a new evidence-qualified manifest, and preserve all unfavorable results.
- [ ] Run corpus/differential smokes and all repository gates; review every exact claim against raw evidence.

**Failure/fallback:** any unavailable oracle/engine artifact, mismatch, timeout, crash, mapping failure, incomplete corpus, or unclassified divergence makes affected capabilities non-exact and therefore search-ineligible. The report counts every fixture outcome; retries are recorded and cannot replace the original result silently.

**Provenance/digests:** a Merkle-like index digest covers sorted fixture file digests and schema/classifier versions. Evidence references immutable raw result digests. A corpus change creates `corpus-v2` (or a semantically versioned successor), never edits v1 after evidence registration.

**CI/package smokes:** fast data-only corpus validator on every PR; small real differential smoke on Ubuntu and Windows approved cells; full qualification profile as an explicit evidence job with retained artifacts. Network denial remains active.

**Acceptance criteria:** all exact claims have complete, artifact-matched evidence and zero unclassified divergence; all failures are counted; reports reproduce from bound raw results; capability manifests default to unknown/non-exact when evidence is absent.

**Non-goals:** broad parity, engine qualification outside the exercised catalog/environment, search, closed-world distribution, protected evaluation, or reclassification to improve results.

**Prerequisites:** Tasks 24-27 and MD-09/14 approval. **Blocks:** exact-eligible Tasks 30-35. **Safe review boundary:** qualification evidence is reviewed before any search benefit or registered result exists.

### Task 29 (G): Add the evaluation-only closed-world distribution

**Purpose:** Supply both registered search prototypes with the same frozen, deterministic distribution over complete opponent-team worlds, without introducing M3 belief semantics.

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/domain/closed_world.py`.
- Create: `packages/battlebelief-core/src/battlebelief_core/application/closed_world_distribution.py`.
- Create: `packages/battlebelief-core/tests/domain/test_closed_world.py`.
- Create: `packages/battlebelief-core/tests/application/test_closed_world_distribution.py`.
- Create: `schemas/evaluation/closed-world-prior.schema.json` and `closed-world-distribution.schema.json` **[NEW SCHEMAS v1]**, with valid/invalid examples.
- Create: `artifacts/gen9ou/m2/closed-world/prior-v1.json`, `distribution-config-v1.json`, and `README.md` only after MD-11 source/license approval.
- Create: `packages/battlebelief-lab/src/battlebelief_lab/closed_world/{__init__.py,artifacts.py,validator.py}` and corresponding tests for file/digest/provenance handling; the filtering/sampling semantics stay in Core.
- Create: `tools/validate_closed_world_artifacts.py`.
- Modify: `tools/check_schemas.py`, `tools/check_architecture.py`, `tools/smoke_packages.py`, their tests, and `.github/workflows/pr.yml` for validation and hidden-information import/serialization restrictions.
- Delete: none; prior versions become immutable once bound.

**Public types and APIs:** `ClosedWorld`, `ClosedWorldPrior`, `PublicEvidence`, `ClosedWorldDistribution`, `ClosedWorldDistributionSummary`, and `ClosedWorldSampler` are **[PUBLIC CORE API]** but explicitly evaluation-only. No symbol contains or aliases `BeliefState`, and Runtime's general public API must not re-export them as production belief.

**Allowed imports:** filtering/sampling imports only Core types and injected random ports. Lab artifact loaders may import Core. Core must not import Lab/file adapters, and Runtime may consume the Core distribution API only through explicitly configured evaluation/search composition.

**Distribution semantics:**

1. A prior row contains one complete, internally coherent opponent-team/set world and a positive frozen mass. It preserves correlations; it is not rebuilt from independent marginals.
2. Convert the observed state into hard `PublicEvidence` using only facts legally visible to that player.
3. Remove worlds inconsistent with hard evidence. Do not fill an unrevealed move, item, ability, EV, Tera type, or set field into the observation.
4. Reweight retained prior mass using the frozen distribution transform. Normalize with exact rational arithmetic or a specified canonical decimal procedure; reject zero remaining mass.
5. Sample deterministically from a dedicated injected world-sampling seed/stream using canonical world order. A world is resampled for each DUCT simulation as required later.
6. Bind prior digest, distribution transform/config digest, public-evidence digest, retained support digest/count, normalization result, sampler version, and seed-domain label.

There is no `OTHER`, open-world materialization, replay/meta pipeline, posterior learning, or claim that a sampled world is truth.

**Tests first:** complete-set validation; positive/frozen mass; duplicate world IDs; correlated-set preservation; hard evidence for revealed species/move/item/ability/Tera and negative inconsistent cases; unrevealed facts do not filter; zero-mass failure; exact renormalization vector; canonical ordering independent of input map order; repeated samples identical under the same seed and distribution; separate seeds diverge; no serialization into public observation/decision record; no omniscient/private evidence accepted; artifact/license/source/digest mismatch.

**Implementation checklist:**

- [ ] Obtain MD-11 source/license approval and add failing schema, correlation, filtering, normalization, sampling, and leakage tests.
- [ ] Implement pure Core complete-world/prior/evidence/distribution/sampler types and semantics.
- [ ] Implement Lab-only artifact loading/validation and create the reviewed prior/config artifacts.
- [ ] Add schema, artifact, architecture, and deterministic sampling smokes.
- [ ] Run focused tests and full gates; audit that no protected, replay, or open-world data entered the artifacts.

**Failure/fallback:** invalid/mismatched prior, unsupported public evidence, zero retained mass, normalization failure, sampler/config mismatch, or source/license closure failure makes the distribution unavailable and search ineligible. It never substitutes a uniform or invented world silently.

**Provenance/digests:** prior rows reference reviewed source/license provenance without protected-pool data. Canonical artifacts exclude local paths, hostnames, and evaluation truth. Distribution digest is distinct from the prior digest and changes when filtering/sampling semantics or config changes.

**CI/package smokes:** Core pure sampling smoke; Lab artifact validation; schema/canonical vectors; leakage test; architecture assertion that production observation code does not import Lab artifacts.

**Acceptance criteria:** complete worlds are filtered only by hard public evidence, retained mass is deterministically normalized and sampled, the prior and derived distribution have separate resolvable digests, and the same distribution can be passed to both algorithms.

**Non-goals:** M3 belief, open world, `OTHER`, imputation-as-truth, replay/meta ingestion, runtime opponent modeling, or protected-pool construction.

**Prerequisites:** Task 27, MD-11 approval, and source/license review. Task 28 evidence may proceed independently in time but must be merged earlier under the serial sequence. **Blocks:** Tasks 30-35. **Safe review boundary:** hidden-information and prior semantics are reviewable without search code.

### Task 30 (H): Implement the registered `determinization_search_v0`

**Purpose:** Implement the frozen determinization baseline exactly as registered, using only qualified transitions and the Task-29 distribution.

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/application/search/__init__.py`.
- Create: `packages/battlebelief-core/src/battlebelief_core/application/search/determinization_v0.py` and `work_accounting.py`.
- Create: `packages/battlebelief-core/tests/application/search/{test_determinization_v0.py,test_work_accounting.py,test_determinization_registration_conformance.py}`.
- Create: `packages/battlebelief-core/tests/fixtures/search/determinization_v0_vectors.json` with canonical project-authored fake-tree vectors.
- Modify: Core curated exports.
- Modify: `tools/check_architecture.py` and tests for pure-algorithm restrictions.
- Modify: no registration or arm-spec file.
- Delete: none.

**Public types and APIs:** `DeterminizationSearchV0`, `DeterminizationConfigV0`, `DeterminizationResult`, `RootActionScore`, and `TransitionWorkCounter` are **[PUBLIC CORE API]**. The config parser accepts only the registered algorithm/execution values for the registered arm; generalization is not part of v0.

**Allowed imports:** Core search imports Core ports/domain/application only. Real engine and artifact access enter through `TransitionModel`; no Runtime, Lab, file, clock, network, or global-random dependency is permitted.

**Exact registered execution:**

- sample exactly 16 worlds from `evaluation_closed_world_v0` using the dedicated world seed;
- search to lookahead depth 2;
- execute each registered `per_world_work` point in the ordered grid `64`, `128`, `256`, `512` as a separate calibrated configuration;
- define one work unit as one call that advances one world transition, including terminal-producing transitions; bookkeeping, mapping, scoring, and sampling are not transition work;
- allocate exactly `per_world_work` units to each of the 16 worlds and report total work as `16 * per_world_work`;
- compute one value per safe root submission per world, then use the arithmetic mean across all 16 worlds; no weighting or optimistic selection is introduced;
- select the maximal mean, breaking exact score ties by stable `SafeSubmissionSet` order;
- return the existing `heuristic_v0` result on eligibility denial, invalid/empty result, work mismatch, or transition/backend failure.

The implementation task must extract these values from or validate them against `registrations/gen9ou/arm-specs/determinization-search-v0-v4.json`; it must not edit that file or silently choose a different allocation interpretation.

**Tests first:** registration conformance loads the frozen spec; exactly 16 sampler calls; exactly 64/128/256/512 transitions per world and the corresponding totals; depth never exceeds 2; arithmetic mean vector distinguishing mean from max/weighted selection; equal-score safe-order tie; candidate set is exactly the safe set; seed-domain separation; iteration/map-order independence; terminal transition accounting; short/extra work raises a typed failure; backend error at each phase; sampled hidden world absent from result/record serialization; heuristic fallback identity.

**Implementation checklist:**

- [ ] Add failing registration-conformance and fake-tree vectors for every frozen value and failure path.
- [ ] Implement transition-work accounting and the depth-2 per-world kernel without Runtime dependencies.
- [ ] Implement 16-world aggregation, arithmetic mean, stable safe-order tie, and heuristic fallback.
- [ ] Add qualified-adapter integration smoke while keeping unit tests engine-free.
- [ ] Run all work-grid vectors, focused Core tests, frozen-artifact checks, and full repository gates.

**Failure/fallback:** any Task-27 ineligibility, world sampling failure, transition/model failure, non-finite value, candidate/action mapping mismatch, work-budget violation, or no score for every safe root candidate returns the precomputed `heuristic_v0` incumbent with the stable class. Partial search does not override it in deterministic mode.

**Provenance/digests:** result binds algorithm/version, frozen arm spec digest, search config/work point, 16-world distribution/support digest, distinct world/search/tie seed identities, transition-model artifact identity, capability manifest/evidence digest, and deterministic score summary. It never includes sampled world content.

**CI/package smokes:** Core vector/conformance tests, architecture test, deterministic repeat smoke on fake transitions; no real engine dependency in Core tests.

**Acceptance criteria:** every frozen value and tie/fallback rule has a direct test; all work points use exact transition counts; repeated pure executions match; no registered artifact changes.

**Non-goals:** DUCT, live deadlines, parallelism, adaptive worlds/depth/work, alternate averaging, tuning, engine qualification, or evaluation outcomes.

**Prerequisites:** Tasks 27-29 with an exact-qualified engine available for integration smoke. **Blocks:** Tasks 31-35. **Safe review boundary:** implements one already registered baseline with artificial and then qualified-adapter conformance, no second algorithm.

### Task 31 (I): Implement `information_set_duct_v0` on the same closed world

**Purpose:** Implement the accepted Search-v0 information-set DUCT semantics without allowing hidden-state nodes or world-dependent joint-action optimization.

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/application/search/information_set_duct_v0.py`, `information_tree.py`, and `simultaneous_selection.py`.
- Create: `packages/battlebelief-core/tests/application/search/{test_information_set_duct_v0.py,test_information_tree.py,test_simultaneous_selection.py,test_search_v0_contract.py}`.
- Create: `packages/battlebelief-core/tests/fixtures/search/information_set_duct_v0_vectors.json` with adversarial information-set trees.
- Modify: Core curated exports.
- Modify: `tools/check_architecture.py` and tests to forbid raw hidden-world keys/serialization in tree node APIs.
- Modify: no accepted Search-v0 contract unless an actual contradiction is first recorded and separately approved as a Maintainer decision.
- Delete: none.

**Public types and APIs:** `InformationSetDuctV0`, `InformationSetDuctConfigV0`, `InformationSetDuctResult`, `InformationNodeKey`, `MarginalActionStats`, and `RootAggregate` are **[PUBLIC CORE API]**. Mutable tree/node implementation classes remain private.

**Allowed imports:** identical to Task 30: Core-only dependencies plus injected ports. Neither the tree nor tests may import a Runtime hidden-state/backend type.

**Contract invariants and direct tests:**

1. **New world per simulation:** the distribution sampler is called once at the start of every simulation; a test fails implementations that reuse one world for a batch.
2. **Information-state nodes:** node keys derive solely from the acting player's `PlayerView` plus public history/config identity, never from a hidden world ID or private set; two worlds with the same view share a node, and one world with different player views does not.
3. **Correct view for both players:** own selection receives the bot-visible information view; opponent selection receives the opponent-visible view supplied by the transition port. Adversarial fixtures reveal different private facts to each and assert no cross-view access.
4. **Independent marginal action choice:** each player's node stores/selects only its marginal legal-action statistics. Tests distinguish this from a joint-action table.
5. **Joint transition afterward:** only after both marginal choices are fixed does the model receive the pair for one joint transition/chance resolution. Tests assert call order and that neither selector observes the other sampled action before selection.
6. **Root aggregation across worlds:** root submission values/visits aggregate over every sampled world by safe submission, not by hidden-state root node. Tests use worlds that reverse local preferences.
7. **No world-dependent joint-action argmax:** an adversarial payoff matrix makes a clairvoyant joint argmax attractive; expected output follows marginal information-set selection instead.

Additional tests cover exploration/visit initialization, deterministic tie order, terminal values, chance outcomes, legal-action changes, fixed-work accounting, seed-domain separation, non-finite values, model errors, and absence of hidden worlds from outputs. All randomness comes from injected streams. The first reference execution is single-threaded.

**Implementation checklist:**

- [ ] Add one failing adversarial test for each of the seven accepted Search-v0 invariants before tree code.
- [ ] Add failing fixed-work, seed, tie, terminal, chance, failure, and hidden-output tests.
- [ ] Implement information-view keys, independent marginal selectors, joint transition ordering, and tree updates.
- [ ] Implement cross-world root aggregation and fail-closed result handling; add qualified-adapter smoke.
- [ ] Run the contract suite, deterministic vectors, architecture/leakage checks, and all repository gates.

**Failure/fallback:** eligibility denial, distribution failure, invalid information view/key, missing marginal legal action, joint-transition mismatch, work violation, backend error, or invalid root aggregation returns the precomputed `heuristic_v0` incumbent. No node from a failed simulation is published as evidence unless rollback semantics are explicitly tested.

**Provenance/digests:** result binds the accepted Search-v0 contract digest, algorithm/config/work identity, the same Task-29 prior/distribution identity used by determinization, separate world/own-selection/opponent-selection/chance/tie seed identities, model/capability identities, and root aggregate summary. Tree dumps and hidden worlds are not decision-record fields.

**CI/package smokes:** contract-invariant suite with fake transition model; deterministic one-thread vector smoke; architecture/leakage negative tests; qualified-adapter bounded integration smoke.

**Acceptance criteria:** all seven invariants above have positive and adversarial negative tests; it uses the same closed-world distribution contract; no hidden-state node or joint-action argmax is possible through public APIs; failure is fail-closed.

**Non-goals:** open-world belief, learned priors/value/policy, multi-thread reference path, live timing, tree persistence across decisions, or registered evaluation.

**Prerequisites:** Tasks 29-30 and MD-06/07/12 decisions. **Blocks:** Tasks 32-35. **Safe review boundary:** isolates information-set correctness from clocks, Runtime composition, and evaluation.

### Task 32 (J): Add `deterministic_benchmark` and `live_anytime` execution modes

**Purpose:** Compose the two search kernels under the accepted deterministic and live operating semantics without contaminating Core with a clock.

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/application/search/executor.py` and `checkpoint.py`.
- Create: `packages/battlebelief-core/tests/application/search/{test_executor.py,test_checkpoint.py,test_deterministic_reproducibility.py}`.
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/clock.py` and `search_budget.py`.
- Create: `packages/battlebelief-runtime/tests/{test_clock.py,test_search_budget.py,test_live_anytime.py}`.
- Create: `schemas/records/search-measurement.schema.json` **[NEW SCHEMA v1]** plus valid/invalid examples after MD-10 approval.
- Create: `tools/smoke_deterministic_search.py`.
- Modify: search-contract validation tests/examples only as needed to exercise the already accepted modes; do not change `schemas/manifests/search-contract.schema.json`. If implementation exposes an actual inconsistency, stop and raise a new Maintainer decision before a successor schema.
- Modify: Runtime/Core exports, schema tooling, package smoke, and `.github/workflows/pr.yml` for deterministic reproduction.
- Delete: none.

**Public types and APIs:** `SearchExecutor`, `DeterministicBenchmarkBudget`, `SearchCheckpoint`, `LiveAnytimeBudget`, `MonotonicClock`, `SearchMeasurement`, and `SearchTermination` are **[PUBLIC APIs]** in their owning package. Core sees fixed work and an injected checkpoint/stop signal, not a clock object or duration.

**Allowed imports:** Core executor imports Core only; Runtime budget/clock imports Core executor protocols and standard-library monotonic-time primitives. Runtime does not import Lab, and Core never imports Runtime clock code.

**`deterministic_benchmark`:** exactly one thread; fixed configured transition work; separate named random streams for worlds, own actions, opponent actions, chance, and ties; no wall-clock branch; stable iteration and serialization order; identical environment/artifacts/config/inputs/seeds yield action-identical results and byte-identical canonical Decision Rows. Operational measurements may differ and are stored separately.

**`live_anytime`:** Runtime uses an injected monotonic clock and an explicit wall-time budget. Before search starts it holds the already safety-checked `heuristic_v0` incumbent. Core proposes a replacement only at a completed checkpoint with a member of the exact root safe set; Runtime accepts it as the incumbent only after an independent `ActionSafetyGate` check against the unchanged request/safe-set identity. On deadline, cancellation, or recoverable backend failure, Runtime returns the best completed and safety-checked incumbent, then applies the ordinary final pre-submission safety check again. If no searched candidate completed, it returns heuristic. The mode is never a teacher-target source.

**Tests first:** deterministic repeated byte vector across processes; random-stream separation (changing one seed cannot consume another); one-thread enforcement; exact work; no clock access in Core; fake-clock deadline before start/mid-transition/between checkpoints/after completion; deadline monotonicity; backend ignores cancellation; incumbent remains safe; partial invalid candidate ignored; time measurement outside canonical decision row; live result tagged ineligible for teacher target; all timeout/fallback/crash counters retained.

**Implementation checklist:**

- [ ] Add failing deterministic two-process byte vectors and seed-domain/one-thread/exact-work tests.
- [ ] Add fake-clock deadline/cancellation/incumbent-safety and no-teacher-target tests.
- [ ] Implement Core checkpoints/fixed-work executor and Runtime monotonic deadline controller.
- [ ] Implement separate Search Measurement records and the repeatability smoke.
- [ ] Run focused Core/Runtime suites, repeatability smoke, package smokes, and all repository gates.

**Failure/fallback:** invalid mode/config, attempted deterministic parallelism, clock regression, deadline exhaustion, checkpoint corruption, work mismatch, backend cancellation/error, or unsafe candidate follows MD-14 and retains the last safe incumbent. A hard process/backend crash is counted, not excluded from evaluation.

**Provenance/digests:** deterministic record contains fixed-work and seed identities; live measurement contains requested/effective duration, monotonic elapsed duration, completed work/simulations, termination/fallback class, engine health transition, and chosen incumbent source. Absolute time, hostname, PID, local path, and hidden worlds are excluded from canonical decision content.

**CI/package smokes:** `tools/smoke_deterministic_search.py` runs twice and byte-compares canonical rows; fake-clock live smoke; Core architecture clock ban; one-thread assertion; supported Runtime search-extra cell.

**Acceptance criteria:** deterministic mode is action- and byte-reproducible under bound inputs; live mode always returns a completed safe incumbent on timeout; telemetry is complete and separate; no live result can be labeled a teacher target.

**Non-goals:** Runtime battle-session integration, telemetry storage backend, multi-thread deterministic support, live action-quality guarantees, or evaluation.

**Prerequisites:** Tasks 30-31, MD-10/12/14 approval. **Blocks:** Tasks 33-35. **Safe review boundary:** operating semantics are tested around stable kernels before public composition.

### Task 33 (K): Integrate Runtime composition, sessions, records, and the public Search API

**Purpose:** Make qualified search usable through Runtime while preserving request identity, safe submissions, the independent action-safety gate, and optional-extra behavior.

**Files:**

- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/composition/search.py`.
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/public_api/search.py`.
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/telemetry/search.py`.
- Create: `packages/battlebelief-runtime/tests/composition/test_search.py`, `tests/public_api/test_search.py`, `tests/telemetry/test_search.py`, and `tests/test_battle_session_search.py`.
- Create: `schemas/records/decision-record-v3.schema.json` and, if approved, `request-identity-v2.schema.json` **[NEW VERSIONED SCHEMAS]**, with canonical vectors and migration examples.
- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/composition/battle_session.py`, `composition/battle_coordinator.py`, `testing/measurement_session.py`, and curated public exports.
- Modify: corresponding Runtime tests and smokes.
- Modify: `packages/battlebelief-core/src/battlebelief_core/domain/records/decision_record.py` and `domain/actions/decision_request.py` only for approved backward-compatible v3/v2 models from MD-05/10/14; preserve v1/v2 readers and canonical vectors.
- Modify: `docs/contracts/decision-records.md`, `legal-action-safety.md`, `manifest-schemas.md`, and `provenance.md` only under explicit normative approval; record migration and update the normative index if required.
- Modify: `tools/check_schemas.py`, `tools/check_architecture.py`, `tools/smoke_packages.py`, protocol/safety smokes, and `.github/workflows/pr.yml`.
- Delete: none.

**Public types and APIs:** `SearchRuntimeConfig`, `SearchPolicyFactory`, `RuntimeSearchPolicy`, `SearchDecisionSummary`, `SearchFallbackReason`, and `decide_with_search(...)` are **[PUBLIC RUNTIME API]**. A versioned `RuntimeDecisionPolicy` consumes observed state, request identity, and safe set; a compatibility adapter keeps `HeuristicPolicy` usable. `DecisionRecordV3` and typed oracle request identity are **[PUBLIC CORE RECORD API]** if approved.

**Allowed imports:** Runtime composition/public API imports approved Core and Runtime adapter APIs. `poke_engine` remains confined to its adapter. Measurement testing code may expose approved protocols to Lab, but Runtime never imports Lab.

**Composition sequence:**

1. Runtime derives the observation and authoritative `SafeSubmissionSet` through existing code.
2. It computes `heuristic_v0` and retains that safe incumbent.
3. It resolves and verifies all configured artifacts/manifests and calls pure Core eligibility.
4. Only if eligible, it maps the closed worlds/observed root through the verified Runtime adapter and runs the selected mode/algorithm.
5. It accepts only a returned root candidate whose request identity and canonical submission are still in the original safe set.
6. Existing `ActionSafetyGate` independently revalidates after search and before wire submission. A safety rejection follows existing registered safe failure behavior and is counted.
7. Decision Record v3 stores only stable summary/fallback data; `SearchMeasurement` stores timing/backend counters keyed by decision-record ID.

The optional extra is fail-closed: importing Runtime, using heuristic mode, and M1 protocol/safety paths work without `[search]`; requesting search without it yields heuristic plus `artifact_unavailable`, not an import-time crash.

**Tests first:** no-extra import and call; correct qualified composition; each eligibility/fallback class; artifact changes after initial check; stale safe set/request; search returns an unsafe/not-member action; action-safety gate is still invoked and can reject; heuristic compatibility; live and oracle identity variants; v1/v2 records still parse/canonicalize unchanged; v3 successful fallback distinct from error; measurement linkage; deterministic rows exclude duration; record contains no sampled world/private opponent data/raw exception/path/hostname; BattleCoordinator reconnect/idempotence; MeasurementSession captures every outcome.

**Implementation checklist:**

- [ ] Obtain MD-05/10/14 and normative record approval; add failing API, migration, no-extra, fallback, and leakage tests.
- [ ] Implement versioned request/record models and the state-aware policy compatibility boundary.
- [ ] Implement artifact resolution, Core eligibility/search composition, checkpoint safety checks, and final safety recheck.
- [ ] Integrate BattleSession, BattleCoordinator, MeasurementSession, telemetry, public API, smokes, and CI.
- [ ] Run Protocol/Safety and base/`[search]` package smokes plus every repository gate; inspect canonical rows manually.

**Failure/fallback:** resolution, manifest, mapping, eligibility, model, algorithm, deadline, telemetry, or backend failures never bypass heuristic/safety. Telemetry-sink failure follows the accepted Runtime telemetry policy and cannot authorize an unsafe action. Failures and fallback successes are separately counted.

**Provenance/digests:** every decision resolves runtime/contract/environment/implementation, engine source/build/wheel/adapter, capability/evidence, ruleset, prior/distribution, search config, and arm spec digests. The record includes references, not local artifact paths.

**CI/package smokes:** base and `[search]` Runtime wheels in isolated environments; protocol and safety smokes with search absent/present; Gen-9 sentinel; deterministic row smoke; schema backward-compatibility vectors; architecture confinement.

**Acceptance criteria:** public search can run only through verified qualification; all denied/error paths return `heuristic_v0`; final safety gate remains active; base install is unaffected; records are backward compatible and leakage-free.

**Non-goals:** Lab evaluation, calibration/evidence binding, changing Runtime version/phase, public Showdown networking, or status/strength claims.

**Prerequisites:** Tasks 25-32 and MD-05/10/13/14 approval plus any normative record changes. **Blocks:** Tasks 34-35. **Safe review boundary:** integration happens only after component semantics are independently tested.

### Task 34 (L): Close implementation/run bindings and calibration evidence

**Purpose:** Make every evaluation-relevant byte and environment fact resolvable before a registered run starts.

**Files:**

- Create: new versioned schemas such as `schemas/manifests/evaluation-arm-binding-v5.schema.json` and `evaluation-run-binding-v5.schema.json` **only if MD-13 approves and existing versions cannot express M2 closure**.
- Create: valid/invalid M2 binding examples and canonical vectors.
- Create: `packages/battlebelief-lab/src/battlebelief_lab/bindings/{__init__.py,m2.py,closure.py}` and tests.
- Create: `packages/battlebelief-lab/src/battlebelief_lab/calibration/{__init__.py,search.py,evidence.py}` and tests.
- Create: `tools/validate_m2_bindings.py` and `tools/calibrate_search_work.py`.
- Create: `artifacts/gen9ou/m2/bindings/README.md` and immutable generated bindings/evidence only after real inputs exist.
- Modify: `docs/contracts/manifest-schemas.md`, `provenance.md`, and schema frontmatter/index only under explicit schema-version approval.
- Modify: existing calibration-evidence schema only by adding a successor if a demonstrated missing fact exists; never mutate v3.
- Modify: `tools/check_schemas.py`, `tools/smoke_packages.py`, their tests, and `.github/workflows/pr.yml` for binding closure.
- Delete: none; Task-21 bindings/digests and existing schema versions remain byte-identical.

**Public types and APIs:** `M2ImplementationBinding`, `M2RunBinding`, `BindingClosure`, `SearchCalibrationPlan`, and `SearchCalibrationEvidence` are **[PUBLIC LAB API]**. They resolve content-addressed artifacts through injected stores; no Core filesystem API is introduced.

**Allowed imports:** Lab binding/calibration modules may import Core manifest value types and approved Runtime public/testing identity APIs. All artifact-store and filesystem access stays in Lab; Core/Runtime do not import these modules.

**Required closure:**

- repository commit and exact source bytes for Core/Runtime/Lab implementation;
- package versions and runtime/contract-set/schema canonicalization digests;
- Showdown commit/source/build/license/adapter and ruleset snapshot;
- engine commit/source/build/wheel/features/platform/adapter and capability/evidence manifest;
- differential corpus/classifier/results;
- closed-world source/prior/distribution;
- search algorithm/accepted contract/frozen arm spec/config/work point/mode;
- environment OS/architecture/Python/Node/Rust/build-tool identities as applicable;
- team and pool bindings, registration digest, metric/statistical configuration references, and seed plan;
- fallback/timeout/crash taxonomy version and telemetry/record schema versions.

Calibration chooses among only the registered determinization work grid `64/128/256/512`; it does not tune worlds, depth, metric threshold, or DUCT semantics. Calibration inputs and output selection are bound before evaluation. If DUCT needs a work-matched configuration not fully owned by an accepted artifact, stop and record a new Maintainer decision rather than inventing it.

**Tests first:** complete valid closure; one missing/unknown/mismatched digest at every edge; wrong engine/oracle/ruleset/prior/environment; circular/unresolvable ref; local path or hostname; Task-21 immutable fixture byte check; calibration grid rejects other values; calibration run cannot use evaluation result; run binding cannot name unopened pool; v3 evidence compatibility; repeated binding canonical bytes.

**Implementation checklist:**

- [ ] Obtain MD-13/16 approval; add failing schema, closure, immutable-old-artifact, and outcome-blind calibration tests.
- [ ] Implement content-addressed binding resolution and complete M2 closure validation.
- [ ] Implement calibration specifications/evidence restricted to registered choices and precommit the DUCT configuration.
- [ ] Generate bindings only from real verified inputs and validate every reference from a clean checkout.
- [ ] Run focused schema/binding/calibration tests, frozen-artifact checks, package smokes, and all repository gates.

**Failure/fallback:** incomplete closure blocks run creation—there is no fallback run with partial provenance. Calibration crash/timeout/failure remains in calibration evidence and cannot be dropped. Artifact retrieval never follows an unverified mutable URL.

**CI/package smokes:** schema/canonicalization and closure validation; synthetic M2 binding smoke; immutable Task-21 artifact test; `uv lock --check`; no network needed to verify local retained artifacts.

**Acceptance criteria:** a run binding resolves every required digest to verified bytes and is rejected on any mismatch; calibration is reproducible and restricted to registered values; no frozen artifact changes.

**Non-goals:** running registered comparisons, altering arm/metric/gate values, selecting favorable results after evaluation, opening pools, version/phase change, or strength claims.

**Prerequisites:** Tasks 28-33 and MD-13 approval. **Blocks:** Task 35. **Safe review boundary:** provenance completeness is approved before outcome data exists.

### Task 35 (M1): Run the registered development evaluation and create M2 run evidence

**Purpose:** Execute the two frozen M2 core comparisons exactly as registered on authorized development inputs, with complete deployment and mechanism accounting.

**Files:**

- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/search/{__init__.py,session.py,runner.py,metrics.py,report.py}`.
- Create: `packages/battlebelief-lab/tests/evaluation/search/{test_session.py,test_runner.py,test_metrics.py,test_report.py,test_pool_guard.py}`.
- Create: `schemas/evaluation/m2-evaluation-result-v1.schema.json` and `m2-evaluation-report-v1.schema.json` **[NEW SCHEMAS v1]** after MD-17 approval; they reference existing metric/statistical IDs instead of restating thresholds.
- Create: `tools/run_m2_evaluation.py` and `tools/validate_m2_evidence.py`.
- Create: content-addressed `artifacts/gen9ou/m2/evaluation/...` run bindings, raw decision/measurement rows, summaries, and reports generated by the authorized run.
- Modify: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/measurement_runner.py` to depend on a measured-session protocol if needed; preserve existing `MeasurementRunner` clients.
- Modify: Lab registration validator/reporting exports, schema tooling, package smoke, and CI evidence validator.
- Modify: no frozen registration, arm spec, gate, pool manifest, or Task-21 binding.
- Delete: none; failed/aborted runs remain retained under provenance rules.

**Public types and APIs:** `MeasuredDecisionSession`, `SearchEvaluationSession`, `M2EvaluationRunner`, `DeploymentBudgetView`, `MechanismBudgetView`, and `M2EvaluationReport` are **[PUBLIC LAB API]**. The oracle session creates separate authoritative player views; it never passes full truth into a Runtime decision policy.

**Allowed imports:** Lab evaluation may import Core evaluation types and approved Runtime public/testing APIs, plus its own oracle/binding modules. It does not import private Runtime adapter internals; Runtime/Core never import the runner.

**Frozen comparisons:**

1. `heuristic_v0` versus `determinization_search_v0`.
2. `determinization_search_v0` versus `information_set_duct_closed_world_v0`.

For both, preserve `battle_outcome_weighted_v1`, one-sided 95% confidence, minimum effect `0.05`, and Go only when the lower confidence bound is at least `0.05`. `end_to_end_latency_ms_v1` is tie-break-only. Do not restate these as a new authority in generated prose; reference the frozen registration and record its digest.

**Run procedure:** validate binding closure and development-pool authorization before starting; precommit seeds/pairings/side allocation; run through the local oracle and public Runtime composition; retain every decision and battle; compute paired/weighted metric exactly through existing evaluation code; produce both deployment-budget (all fallbacks/timeouts/crashes as deployed) and mechanism-budget (qualified completed search mechanism with denominator disclosures) views; make the registered inference once; render raw counts, rates, confidence bounds, effect, latency tie-break, artifact identities, and failure taxonomy.

Protected selection, power-pilot, and release-holdout pools are rejected by the runner unless a later independent authorization and binding explicitly opens them. This task does not create them.

**Tests first:** measured-session protocol compatibility with existing BattleSession/MeasurementSession; distinct player observations and adversarial leakage test; full truth unavailable to policy; registration digest/arm order/gate checks; wrong pool blocked; seed/pairing precommit; failure/timeout/crash retained in denominators; fallback counted in both declared views; no double counting; weighted metric and one-sided confidence vectors; exact 0.05 boundary; latency cannot override failed primary gate; interrupted run resumability without selective deletion; report regenerates byte-stable canonical data from raw evidence.

**Implementation checklist:**

- [ ] Obtain explicit development-run and MD-17 approval; add failing session, pool, leakage, accounting, metric, inference, and report tests.
- [ ] Implement the measured-session adapter, local-oracle evaluator, immutable raw-result writer, and resume rules.
- [ ] Implement deployment/mechanism views and reports by referencing the frozen registration and accepted metric/statistical code.
- [ ] Validate closure, precommit run inputs, execute the authorized comparisons, and retain every result/failure.
- [ ] Rebuild reports from raw evidence, run evidence validators and full repository gates, and audit protected-pool access logs.

**Failure/fallback:** individual decision failures use the registered Runtime fallback and remain in the battle. Battle/oracle/backend crashes and timeouts are classified and counted; an invalid run is reported invalid, not removed. Binding, leakage, pool, or registration mismatch aborts before evaluation and produces no gate result.

**Provenance/digests:** each row/run resolves the Task-34 closure plus pairing, seeds, teams, development pool, oracle session, Decision Record/Search Measurement, outcome, fallback/timeout/crash, metric, statistical-analysis, and report-renderer digests. No secret, host, path, or hidden world appears in public decision evidence.

**CI/package smokes:** synthetic miniature runner/report test in CI; M2 evidence validator for retained authorized artifacts; local oracle/search-extra/sentinel/differential/prior checks as prerequisites. The full registered run is an explicit retained-evidence workflow, not an unbounded ordinary PR test.

**Acceptance criteria:** both comparisons are executed unchanged on an authorized development pool; all outcomes/failures are retained; reports show both budget views and the registered inference; no protected pool is touched; evidence is reproducible from bindings and raw rows.

**Non-goals:** changing a gate after results, selection/power/release evaluation, ladder play, publishing strength/parity/MVP claims, opening pools, or changing Runtime phase/version.

**Prerequisites:** Tasks 24-34, real exact capability evidence, full binding closure, and explicit Maintainer authorization to run the registered development evaluation. **Blocks:** Task 36. **Safe review boundary:** evaluation cannot redefine implementation, qualification, or gates and produces evidence without status changes.

### Task 36 (M2): Review M2 acceptance evidence and propose any status transition

**Purpose:** Decide whether the implemented prototype meets the M2 milestone using real retained evidence, without converting development results into a strength claim.

**Files:**

- Create: `docs/evidence/m2-engine-qualified-search-prototype.md` or the repository's approved evidence location, containing digest references rather than duplicated normative thresholds.
- Create: `schemas/manifests/m2-evidence-index-v1.schema.json` **[NEW SCHEMA v1]** and its valid/invalid examples after MD-17 approval.
- Modify: `docs/roadmap/milestones.md`, Runtime status/version metadata, README, Wiki, or release notes only after the Maintainer explicitly accepts the evidence and separately authorizes the exact status/version edits.
- Modify: evidence validation tooling/CI if a new index is approved.
- Modify: no frozen M1.5 registration, Task-21 binding, registered gate, or protected pool.
- Delete: none.

**Public APIs and schemas:** none unless the Maintainer approves a new evidence-index schema. A version/phase change is a separate reviewed compatibility decision under MD-15.

**Allowed imports:** documentation and evidence-validation tooling only; any new tool follows existing tool-to-package boundaries and does not create a product import edge.

**Evidence review:** verify oracle hermeticity, engine artifact identity and support matrix, sentinel, exact differential claims, eligibility fail-closed vectors, closed-world safety, both algorithms' invariant suites, deterministic reproduction, live timeout safety, binding closure, registered evaluation accounting, and all repository gates. Distinguish clearly:

- engine-qualified only for enumerated exact capabilities/artifact/environment/corpus;
- M2 prototype acceptance;
- development-pool comparison outcomes;
- unmade parity, strength, ladder, MVP, and release claims.

**Tests and negative review first:** evidence index rejects missing/unresolvable/stale digests; no report language broadens capability scope; no hidden/protected data; no failed-run deletion; no local path/host/secret; no status change before approval; documentation links and migration rules; complete diff review.

**Implementation checklist:**

- [ ] Obtain MD-15/17 disposition and add failing evidence-closure and claim-scope checks.
- [ ] Build the evidence index/report exclusively from verified Task-35 artifacts and full gate results.
- [ ] Review exact capability/environment scope, failures, protected-pool state, and all unmade claims.
- [ ] Request explicit Maintainer acceptance and exact version/phase/documentation authority before any status edit.
- [ ] Run complete local and PR gates, inspect the entire diff, and record every limitation or unexecuted external check.

**Failure/fallback:** insufficient or contradictory evidence leaves the project at its current status. Record the missing evidence or Maintainer decision; do not edit results, loosen a gate, broaden an exact claim, or infer qualification.

**CI/package smokes:** full repository gates and evidence closure. Any GitHub `pr-gate` must pass on the actual PR before merge; local checks are not a substitute.

**Acceptance criteria:** the evidence report is digest-resolved and scope-accurate; the Maintainer makes an explicit M2 acceptance/status/version decision; no strength claim or protected-pool access occurs.

**Non-goals:** new implementation, new evaluation, gate changes, M3 work, or automatic release.

**Prerequisites:** Task 35 and all retained evidence. **Blocks:** any claim that M2 is complete and any subsequent milestone transition. **Safe review boundary:** acceptance/status is not bundled with implementation or result generation.

## 8. Cross-task safety, determinism, and compatibility rules

### Safe action authority

- `SafeSubmissionSet` remains authoritative at the observed root. Search enumerates only its candidates and returns a member with the same request identity.
- Sampled-world legality may prune or score deeper engine-neutral actions, but it cannot add a root submission.
- `ActionSafetyGate` remains a separate check after search and before submission. Its rejection is not overwritten by search confidence or engine health.
- `heuristic_v0` is computed before engine-backed work and is the stable fallback for all ineligible/error/timeout paths. If it cannot produce a safe action, existing safe failure/forfeit behavior governs.

### Hidden-information boundary

- Authoritative full state exists only inside the Lab oracle/evaluation boundary.
- Player observations are produced separately for each side by an authoritative visibility rule; they are not informal field-deleted copies of full state.
- A closed-world sample is a hypothesis used inside a single evaluation/search simulation. It cannot update public observed state or become truth.
- Decision records, public telemetry, logs, errors, bindings, and reports exclude sampled team/set contents, private requests, unrevealed moves/items/abilities/Tera information, oracle-only seeds, and opponent-private views.
- Leakage tests use adversarial paired full states that share the same public view and require identical public decisions/records under fixed public inputs, except for legitimate sampled-random aggregate behavior bound by the distribution.

### Determinism and seed domains

At minimum, bind independent seed domains for oracle battle generation, evaluation pairing, side allocation, closed-world sampling, own marginal selection, opponent marginal selection, chance resolution, and tie-breaking. A component receives only its stream. No global Python, NumPy, engine, or process random state is accepted without an adapter that demonstrates explicit seeding and records it.

Canonical iteration orders are schema-defined or explicitly sorted. Fixed work—not elapsed time—is the deterministic benchmark budget. The first reference implementation is single-threaded, and deterministic Decision Rows exclude operational time.

### Provenance closure

An evaluation-relevant digest must resolve to canonical bytes through an approved artifact store or repository path at the bound commit. The closure includes source, build, artifact, adapter, capability/evidence, corpus, ruleset, prior/distribution, search, runtime/contracts, environment, teams/pool, registration, and run artifacts. A name, semantic version, branch, mutable URL, or successful import alone is insufficient.

Canonical artifacts contain no credentials, cookies, tokens, private data, absolute local paths, usernames, hostnames, PIDs, ephemeral ports, or unbounded raw exception output. License/origin metadata remains attached to third-party source and binary artifacts.

### Migration and backward compatibility

- Never edit an accepted schema version in place when new required fields or semantics are incompatible. Add a successor `$id`, examples, parser/model, canonical vectors, migration note, and dual-read tests.
- Preserve Decision Record v1/v2, engine-capability v1, Task-21 implementation/run bindings, calibration-evidence v3, and all frozen registration/arm-spec bytes and digests.
- Runtime base installation and M1 public APIs continue to work without `[search]`. Search exports are additive and availability-inspectable.
- Any normative inconsistency discovered during implementation stops the dependent task and becomes a new Maintainer decision before contract edits.

## 9. Validation plan

### Focused validation by task

| Task | Focused commands or gate categories |
|---|---|
| 23 | documentation/link governance; placeholder/secret/path scan; `git diff --check`; frozen-artifact and full-diff audit |
| 24 | Lab oracle unit tests; manifest schemas; deterministic oracle and lifecycle smoke on Ubuntu/Windows; no-network test |
| 25 | Runtime artifact/mapper/sentinel tests; base and `[search]` isolated package installs; Gen-9 sentinel on supported cells |
| 26 | capability schema/examples/canonicalization; v1 compatibility; catalog/manifest closure |
| 27 | Core eligibility/fallback truth table; fake transition port conformance; architecture negative tests |
| 28 | corpus validator; classifier/evidence tests; real bounded differential smoke on Ubuntu/Windows |
| 29 | closed-world schema, filtering, normalization, sampler, provenance, and leakage tests |
| 30 | registration conformance; exact work/depth/world/mean/tie/fallback vectors |
| 31 | all seven Search-v0 invariants; adversarial information/view/joint-argmax vectors |
| 32 | deterministic two-run byte comparison; seed separation; fake-clock live timeout/incumbent tests |
| 33 | no-extra/extra Runtime composition; BattleSession/MeasurementSession; records migration; Protocol and Safety smokes |
| 34 | implementation/run/calibration schema closure; immutable Task-21 bindings; registered grid restriction |
| 35 | measured-session/leakage/pool guards; metric/statistical vectors; synthetic report/evidence validation |
| 36 | full evidence closure, claim-language review, status/version approval, full repository/PR gates |

Use the actual commands exposed by the repository at the task's baseline. Do not invent a command name when tooling has not yet been added; adding each named new tool and its tests is part of its owning task.

### Required repository gates before every implementation PR handoff

Run focused tests first, then all applicable configured gates:

```powershell
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run python tools/check_architecture.py
uv run python tools/check_docs.py
uv run python tools/check_schemas.py
uv run python tools/check_versions.py
uv run python tools/smoke_packages.py
uv run pytest tests/smokes/test_protocol_smoke.py -v
uv run pytest tests/smokes/test_safety_smoke.py -v
uv lock --check
git diff --check
```

Also run the registration/frozen-artifact validators present at that baseline. The CI `pr-gate` must pass on the actual pull request; no local command or green `main` run substitutes for it.

As their owning tasks land, add these isolated gates and keep them independent:

- Runtime `[search]` build/install/import smoke without implicit source build;
- Lab oracle profile build/lifecycle/no-network smoke;
- real Gen-9/Terastallization/transition/minimal-search sentinel;
- differential corpus closure and bounded real runner smoke;
- deterministic benchmark two-run canonical-row byte comparison.

Full validation must inspect retained artifacts and the complete diff for generated binaries, secrets, local state, absolute paths, hostnames, unlicensed data, unexpected dependency/lock changes, frozen registration/binding changes, premature M2 status, and parity/strength/release claims.

## 10. Official primary sources used for Task-23 research

These links identify the inspected snapshot. They do not select BattleBelief's future pins.

### Pokémon Showdown

- [Package metadata at the observed revision](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/package.json)
- [Official package lock at the observed revision](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/package-lock.json)
- [Official MIT license](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/LICENSE)
- [Official launcher with its Node version check](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/pokemon-showdown)
- [Official simulator documentation](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/sim/SIMULATOR.md)
- [Official simulator protocol documentation](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/sim/SIM-PROTOCOL.md)
- [Official test workflow at the observed revision](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/.github/workflows/test.yml)

### `poke-engine`

- [Engine Cargo features at the observed revision](https://github.com/pmariglia/poke-engine/blob/bcf13823abc162a608e187b26bbf683f759f385e/Cargo.toml)
- [Python binding Cargo defaults](https://github.com/pmariglia/poke-engine/blob/bcf13823abc162a608e187b26bbf683f759f385e/poke-engine-py/Cargo.toml)
- [Official Python build metadata](https://github.com/pmariglia/poke-engine/blob/bcf13823abc162a608e187b26bbf683f759f385e/poke-engine-py/pyproject.toml)
- [Official build targets](https://github.com/pmariglia/poke-engine/blob/bcf13823abc162a608e187b26bbf683f759f385e/Makefile)
- [Official publish workflow](https://github.com/pmariglia/poke-engine/blob/bcf13823abc162a608e187b26bbf683f759f385e/.github/workflows/publish.yml)
- [Official Python publish helper](https://github.com/pmariglia/poke-engine/blob/bcf13823abc162a608e187b26bbf683f759f385e/poke-engine-py/build_and_publish)
- [Official MIT license](https://github.com/pmariglia/poke-engine/blob/bcf13823abc162a608e187b26bbf683f759f385e/LICENSE)
- [Official Python API surface](https://github.com/pmariglia/poke-engine/blob/bcf13823abc162a608e187b26bbf683f759f385e/poke-engine-py/python/poke_engine/__init__.py)
- [Official PyPI release metadata for 0.0.48](https://pypi.org/project/poke-engine/0.0.48/)

## 11. Plan review checklist

Before approving this plan, verify that it:

- keeps Task 23 documentation-only and leaves the current Runtime version/phase and M1.5/Task-21 artifacts unchanged;
- assigns every new port, adapter, schema, artifact, test, smoke, and CI/tool change to exactly one serial task;
- treats Pokémon Showdown as authoritative and `poke-engine` as non-authoritative and artifact-qualified;
- requires exact capability evidence and rejects unknown, unsupported, bounded approximation, mismatch, and backend failure;
- treats the closed-world distribution as evaluation-only and never as M3 belief;
- reproduces every frozen determinization value without modification;
- maps every Search-v0 invariant to an adversarial test;
- separates deterministic canonical rows from live operational measurement;
- retains all fallbacks, timeouts, crashes, invalid actions, and failed runs in evaluation accounting;
- keeps protected pools closed and makes no strength, parity, ladder, MVP, or release claim;
- presents every discovered inconsistency or proposed improvement as a Maintainer decision rather than an implicit change;
- binds real future revisions and digests only after they have been selected and generated, never through plausible placeholders.
