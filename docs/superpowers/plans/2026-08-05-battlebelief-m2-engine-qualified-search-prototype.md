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
| Lab | Frozen-registration validation, pool/schedule/seed helpers, measurement runner, reports | The runner can retain trace lifecycle ownership, but no oracle, differential runner, closed-world artifact, concrete Development inputs, registered analyzer, or calibration pipeline exists. `weighted_cluster_bootstrap_v1` is registered by ID but has no implementation or golden vectors. |
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
5. **Bindings:** execution must resolve every digest before a run: runtime and contract sets, implementation, environment, Showdown source/build, engine source/build/wheel, capability manifest/evidence, differential corpus, ruleset, closed-world prior/distribution, search configuration/specifications, analyzer, and concrete Development inputs. Existing run-binding v4 fixes `run_purpose` to `synthetic_acceptance`; it cannot bind a real Development run and must remain unchanged.

## 3. Verified upstream facts and binding policy

The facts in this section are a dated research snapshot, not selected BattleBelief pins. No upstream commit or artifact becomes qualified merely by being named here.

### Pokémon Showdown snapshot observed on 2026-08-05

- The observed upstream `master` revision was `6a1836dd71c0718e923206f3d089e61074410868`; BattleBelief has not selected it as the M2 pin.
- The package metadata reports version `0.11.11`, MIT licensing, `node >=16`, and a lockfile with `lockfileVersion: 2`.
- At that same revision, `package.json` declares `node >=16`. The launcher and server entry point do not compare versions: they test only whether the global `fetch` symbol exists, then emit a Node-22 error message when that feature test fails. The launcher comment says `fetch` was introduced in Node 18, and the official test workflow validates Node 18.x. The message therefore does not establish that every version below 22 is rejected or unsupported. BattleBelief has not selected a Node version.
- The official simulator documentation defines newline-delimited standard-input operation and says each simulated battle uses its own subprocess. The direct simulator request form has no live-server `rqid`.

### `poke-engine` snapshot observed on 2026-08-05

- The observed `main` revision, also peeled from tag `v0.0.48`, was `bcf13823abc162a608e187b26bbf683f759f385e`; BattleBelief has not selected it as the M2 pin.
- The repository is MIT-licensed. Cargo exposes `gen9` and `terastallization` features, but the Python binding crate defaults to the engine's `gen4` feature. A qualified Gen 9 artifact therefore needs explicit, recorded features.
- The Python build metadata uses `maturin >=1,<2` and declares no Python version range. The repository requirements file pins `maturin==1.7.1` for its own helper flow.
- The upstream publish workflow builds an sdist. PyPI release `0.0.48` exposed only `poke_engine-0.0.48.tar.gz` when inspected, not platform wheels, and declared no `Requires-Python`. Its observed PyPI SHA-256 was `070010686f2aedff11e25137e696e301ccd80fd57c805d255464067fc905ca12`; this is an upstream sdist fact, not an approved BattleBelief artifact digest.
- The Python binding is built as a native `cdylib`. Its inspected public search functions accept duration/iterations/thread controls but expose no cancellation token or kill interface. A Python-side monotonic clock therefore cannot by itself prove recovery from a blocking native call.
- The upstream project describes mechanics limitations; its Python API exposes state transition/reversal and Monte Carlo search with duration or exact iterations and thread controls. None of those interfaces is evidence of Gen 9 parity or a hard outer deadline.

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

- **Options:** (A) qualify an exact Node 22 LTS patch; (B) qualify an exact Node 20 LTS patch; (C) qualify an exact Node 18 patch matching upstream CI; (D) rely only on the declared package minimum Node 16.
- **Advantages:** A follows the launcher's stated recommendation; B tests the intervening LTS family; C follows the official workflow and satisfies the actual global-`fetch` feature test; D follows package metadata.
- **Disadvantages:** the upstream metadata, feature test/message, and CI do not define one coherent support floor. Node 18 is end-of-life according to the launcher's own comment; Node 16 does not normally supply the required global `fetch`; Node 20/22 still need exact Windows/Ubuntu proof for the selected commit.
- **Recommendation:** probe exact Node 18, 20, and 22 patch releases against the selected Showdown commit, including clean `npm ci`, build, stdio simulator, and loopback server lifecycle. Prefer a validated Node 22 LTS patch for BattleBelief after those results, but do not justify it as an upstream-enforced `<22` rejection.
- **Consequences:** the approval record must distinguish declared metadata, the actual `fetch` feature test, emitted message, upstream CI coverage, and BattleBelief's independently supported version. Task 24 may not claim support from any one signal alone.

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
- **Consequences:** approval is required before the dedicated Task-35 record/identity evolution; live M1 records remain readable and unchanged.

### MD-06 — engine-neutral `TransitionModel` port

- **Options:** (A) a typed Core protocol over opaque prepared worlds and engine-neutral search actions; (B) a generic callback bag; (C) expose `poke-engine` state strings to Core.
- **Advantages:** A keeps algorithms pure and testable; B is small; C closely mirrors the backend.
- **Disadvantages:** A requires deliberate state/action/view contracts; B weakens invariants and typing; C violates package boundaries and couples Core to backend serialization.
- **Recommendation:** A, with methods for root preparation, player information view/key, per-player legal actions, joint transition/chance resolution, terminal/value evaluation, health/identity, and deterministic transition-work accounting.
- **Consequences:** Task 26 freezes the Core protocol from documented engine requirements and test fakes before any public Runtime mapper exists. Task 25 may contain only a private artifact/sentinel probe and must not publish state/action mapping APIs. Backend-specific strings remain Runtime-private.

### MD-07 — observed-state, world, and action mapping

- **Options:** (A) one explicit canonical mapping layer with a lossless mapping report; (B) ad hoc conversion in every search algorithm; (C) make engine state the project domain model.
- **Advantages:** A centralizes validation and feature detection; B is initially fast; C removes conversion.
- **Disadvantages:** A needs exhaustive negative fixtures; B invites divergence; C makes a non-authoritative backend authoritative and risks hidden-information leakage.
- **Recommendation:** A in `battlebelief-runtime/adapters/poke_engine`, returning either a prepared world and required capability IDs or a typed mapping failure. Root submissions map only from `SafeSubmissionSet`; deeper actions use engine-neutral `SearchAction` IDs.
- **Consequences:** mapping mismatch is ineligible, never “best effort.” The mapping report records field/capability presence but no private world in a public decision record.
- **Decision record:** [ADR-0006 poke-engine Runtime-Mapping-Grenze](../../adr/ADR-0006-poke-engine-runtime-mapping-boundary.md) dokumentiert die erteilte Maintainer-Freigabe; MD-07 ist als Option A akzeptiert.

### MD-08 — capability-ID taxonomy and manifest evolution

- **Options:** (A) introduce versioned, namespaced atomic IDs and engine-capability schema v2 with `exact`, `bounded_approximation`, `unsupported`, and `unknown`; (B) encode only exact/unsupported in v1; (C) use free-form strings generated by the adapter.
- **Advantages:** A can express the accepted four-way semantics and evidence links; B avoids migration; C is flexible.
- **Disadvantages:** A requires a normative contract/schema decision and v1 compatibility; B cannot faithfully encode unknown and build/platform evidence; C makes eligibility unstable.
- **Recommendation:** A, using an immutable catalog such as `gen9.mechanic.terastallization.damage` and `gen9.transition.status.*`, with catalog version/digest and per-ID evidence. Preserve v1 readers; do not mutate v1.
- **Consequences:** this plan identifies a real expressiveness gap but does not amend the contract. Tasks 26-29 are blocked on Maintainer approval.

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
- **Consequences:** Task 35 owns versioned schemas/readers and migration tests before operating-mode or Runtime integration PRs; v1/v2 canonical vectors remain unchanged.

### MD-11 — evaluation-only closed-world prior artifact

- **Options:** (A) a small reviewed, licensed, manually sourced complete-team artifact dedicated to M2 evaluation; (B) derive from replays or current metagame data; (C) embed sets in Python tests.
- **Advantages:** A stays within M2 and is auditable; B is more representative; C is simple.
- **Disadvantages:** A is limited and cannot support external strength claims; B pulls M3 ingestion/meta work forward; C lacks independent provenance/versioning.
- **Recommendation:** A, with complete correlated opponent-team worlds, rational or exact decimal masses, source/license metadata, prior digest, distribution transform version, and no `OTHER`.
- **Consequences:** the Maintainer must approve source/license and scope. Task 30 cannot use protected-pool or replay information.

### MD-12 — composition of `deterministic_benchmark` and `live_anytime`

- **Options:** (A) one pure Core search kernel with distinct Runtime budget controllers; (B) two algorithm implementations; (C) simulate live time using fixed work.
- **Advantages:** A shares semantics but keeps clock out of Core; B isolates behavior; C simplifies testing.
- **Disadvantages:** A needs a careful interrupt protocol; B can drift; C does not implement an anytime deadline.
- **Recommendation:** A for algorithm semantics, conditional on MD-18 for backend-call isolation. Core advances explicit work units and exposes safe checkpoints. Runtime supplies fixed work or an injected monotonic deadline. The reference deterministic path is one thread.
- **Consequences:** live output is not deterministic evidence or a teacher target. A claim that timeout always returns the last independently safety-checked incumbent is permitted only for an execution boundary that can regain control by the deadline; otherwise the public contract must say soft deadline.

### MD-13 — calibration evidence and implementation/run binding

- **Options:** (A) introduce backward-compatible implementation/run binding versions that explicitly reference all M2 artifacts and reuse calibration-evidence v3 if sufficient; (B) pack digests into existing generic component fields; (C) mutate existing schema versions.
- **Advantages:** A is explicit and preserves history; B may avoid schemas; C minimizes filenames.
- **Disadvantages:** A adds versions and migration work; B can hide missing bindings; C breaks frozen evidence.
- **Recommendation:** A. First prove whether calibration-evidence v3 is sufficient; version it only if a required fact cannot be represented. Existing implementation/run versions remain valid and unchanged.
- **Consequences:** Task 40 must demonstrate closure from run binding to source bytes and artifacts before any registered evaluation.

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
- **Consequences:** Task 23 changes neither value. Task 42 is blocked on Maintainer acceptance and real evidence.

### MD-16 — outcome-blind algorithm specification and configuration ownership

- **Options:** (A) create separate versioned determinization and DUCT algorithm specifications before either implementation; (B) leave missing behavior to implementation defaults; (C) add fields to the frozen M1.5 execution artifact.
- **Advantages:** A binds all unregistered semantics without changing the freeze; B is quick; C makes one artifact appear complete.
- **Disadvantages:** A adds two specification schemas/artifacts and an explicit owner; B permits outcome-dependent or backend-dependent interpretation; C violates the frozen-artifact boundary.
- **Recommendation:** A. Task 32 must bind root-work allocation and remainder handling, opponent policy, simultaneous-action selection, leaf value, chance treatment, backup rule, exact depth counting, terminal handling, numeric/tie rules, and every algorithm parameter. It must also precommit the DUCT exploration/configuration and transition-work matching procedure. Neither Task 33 nor Task 34 starts before these artifacts merge.
- **Consequences:** the frozen M1.5 registration and execution manifest remain byte-identical. Task 40 later closes the new specification digests through implementation/run bindings and calibration evidence. No value may be invented in implementation or selected from evaluation outcomes.

### MD-17 — M2 evaluation result and evidence-index schemas

- **Options:** (A) add dedicated, minimal versioned M2 result/report and evidence-index schemas that reference existing metric/statistical authorities; (B) extend existing generic measurement-result schemas with a new version; (C) emit Markdown-only reports.
- **Advantages:** A makes both budget views and failure counts machine-checkable without changing old schemas; B may reduce schema count; C is easy to read.
- **Disadvantages:** A adds schema governance; B risks coupling synthetic M1.5 records to M2 semantics; C cannot enforce closure or prevent omitted failures.
- **Recommendation:** A, with no duplicated thresholds and with existing measurement records referenced by digest.
- **Consequences:** Task 38 creates result/report schemas using synthetic golden vectors; Task 42 creates the evidence-index schema. All earlier schemas stay valid and byte-identical.

### MD-18 — engine execution and deadline isolation

- **Options:** (A) execute native engine calls in a separate, killable worker process and treat its IPC protocol/artifact identity as part of Runtime; (B) keep the PyO3 extension in-process, promise only a soft deadline, and require qualified maximum call latency; (C) use an in-process path for deterministic fixed-work mode and a worker path for live hard-deadline mode.
- **Advantages:** A can recover control after a hung native call; B minimizes IPC and serialization overhead; C keeps benchmark overhead low while protecting live operation.
- **Disadvantages:** A adds worker startup, state transfer, crash cleanup, and cross-platform process semantics; B cannot guarantee a 2,000-ms return when native code blocks and needs a defensible latency bound; C adds two execution paths whose mapping and results need equivalence tests.
- **Recommendation:** C, subject to measured state-transfer overhead and deterministic equivalence. If the Maintainer rejects a worker, the public `live_anytime` guarantee must be explicitly soft and eligibility must bind a maximum single-call latency qualification; it must not claim hard deadline recovery.
- **Consequences:** Task 36 cannot implement or test hard-deadline return until this decision is approved. Worker source/protocol/version, process-tree termination, artifact digest, timeout class, and crash evidence become binding inputs. A Python monotonic clock alone is not cancellation.

### MD-19 — concrete M2 development inputs

- **Options:** (A) construct and seal a small M2-specific development set under the frozen pool/schedule rules; (B) reuse M1.5 synthetic fixtures as development evaluation; (C) defer all registered evaluation.
- **Advantages:** A supplies real team/policy/cluster/pool/schedule/seed bindings while keeping protected pools closed; B reuses existing artifacts; C avoids premature input selection.
- **Disadvantages:** A requires explicit team and opponent-policy source/license/selection approval; B is `synthetic_acceptance`, not a concrete registered development pool; C prevents Task 41.
- **Recommendation:** A in a dedicated Task 39 before run binding. Seal hero teams, opponent teams, opponent policies, exact-team clusters, base matchups, balanced side assignments, schedule blocks, and seed families under the frozen M1.5 construction IDs.
- **Consequences:** the Maintainer must approve the input sources and selection procedure before artifacts are viewed in registered outcomes. Selection, Power Pilot, and Release Holdout remain unopened and absent.

### MD-20 — differential harness versus qualification evidence

- **Options:** (A) merge a synthetic-only runner/corpus PR, then a separate data-only qualification PR; (B) implement the runner and produce exact claims in one PR; (C) keep all capabilities unknown in M2.
- **Advantages:** A prevents runner/classifier/schema edits after real divergences are visible; B is fewer PRs; C is maximally conservative.
- **Disadvantages:** A adds one serial boundary; B weakens preregistration of divergence handling; C prevents engine-qualified search.
- **Recommendation:** A. Task 28 freezes code, schemas, classifier, and reviewed corpus using synthetic/golden cases; Task 29 runs already-merged tooling against exact bound artifacts and changes only data/evidence manifests.
- **Consequences:** Task 29 may not change Python, schemas, classifier rules, corpus cases, or capability taxonomy. A discovered deficiency produces a failed/invalid qualification and a later separately reviewed successor, never an in-run edit.

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
| 25 (C) | `poke-engine` source/build/wheel verification, Runtime `[search]`, real Gen-9 sentinel | Proves only artifact identity and native health; it publishes no mapping or transition API before Core owns that contract. |
| 26 (D) | Core capability types, engine-neutral search foundations, `TransitionModel`, and `WorldDistributionIdentity` | Freezes the public Core vocabulary and port before a Runtime adapter implements it. |
| 27 (E) | Runtime `poke-engine` state/action mapping and port conformance | Reviews backend mapping against an already merged Core contract, with no eligibility or search algorithm. |
| 28 (F) | Differential corpus, classifier, and runner harness using synthetic/golden cases | Freezes comparison code and divergence semantics before real engine results are visible. |
| 29 (G) | Data-only differential qualification | Runs merged tooling against exact artifacts; changes evidence/manifests only and cannot edit code, schema, corpus, or classifier. |
| 30 (H) | Evaluation-only closed-world distribution | Reviews hidden-information semantics and provenance independently of eligibility and search. |
| 31 (I) | Pure Core eligibility and fail-closed heuristic policy | Consumes generic distribution identity and exact capability evidence only after both are defined. |
| 32 (J) | Outcome-blind determinization and DUCT algorithm specifications | Closes all unregistered selection, backup, value, chance, depth, allocation, and configuration semantics before implementation. |
| 33 (K) | `determinization_search_v0` | Implements one merged specification and the frozen registered values without DUCT or clocks. |
| 34 (L) | `information_set_duct_v0` | Implements the second merged specification and each Search-v0 invariant on the same distribution. |
| 35 (M) | Request identity, Decision Record v3, Search Decision/Measurement schema and contract evolution | Makes record/canonical-byte semantics reviewable before modes or Runtime composition use them. |
| 36 (N) | Deterministic/live operating modes and approved engine deadline isolation | Resolves fixed-work, checkpoints, worker/soft-deadline semantics, and canonical records before session integration. |
| 37 (O) | Runtime composition, public Search API, session and telemetry integration | Integrates only already versioned records, modes, adapter, and eligibility while preserving the final safety gate. |
| 38 (P) | Synthetic-only evaluation/statistical harness | Implements metrics, technical outcomes, `weighted_cluster_bootstrap_v1`, result/report schemas, and golden vectors without real registered outcomes. |
| 39 (Q) | Construct and seal concrete M2 development inputs | Creates team, opponent-policy, cluster, pool, schedule, side, and seed manifests without opening protected pools. |
| 40 (R) | Implementation/run bindings and calibration evidence | Closes real artifacts, algorithm specifications, development inputs, and outcome-blind calibration before a run. |
| 41 (S) | Data-only registered development run | Uses merged analyzer and closed bindings; permits only inputs, raw results, measurements, and generated reports. |
| 42 (T) | M2 acceptance/evidence report | Separates evidence and any status proposal from both analyzer implementation and outcome generation. |

No PR combines oracle, engine artifact, eligibility, both search algorithms, analyzer implementation, and registered outcomes. Tasks 24-42 are strictly serial: each starts from the merged predecessor. There is no “independently in time” exception. Work may be explored locally only when it is discarded or rebased after the owning predecessor merges; no dependent PR is mergeable out of order.

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

**Prerequisites:** baseline commit `cfc526ca1558869e674769daf19b9aa09c00abf0` with M1.5 complete and frozen. **Blocks:** every later task until the Maintainer selects or defers its blocking MD items. **Safe review boundary:** documentation-only scope makes accidental milestone expansion visible in one diff.

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

**Prerequisites:** Task 23 approval plus MD-03 and MD-04 disposition; MD-05 may remain pending until Task 35 because this task's oracle session uses its own typed Lab identity. **Blocks:** Tasks 28-29, 37, and 41. **Safe review boundary:** it proves only the authoritative oracle and its hermetic lifecycle; no non-authoritative decision path is present.

### Task 25 (C): Produce and verify the `poke-engine` artifact, Runtime `[search]`, and Gen-9 sentinel

**Purpose:** Provide a real, exactly identified Gen 9/Terastallization backend artifact and prove installation/health without qualifying mechanics.

**Files:**

- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/{__init__.py,artifact.py,errors.py,native_probe.py,sentinel.py}`. `native_probe.py` is private and sentinel-only; it is not the future `TransitionModel` adapter.
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/search_status.py` for extra availability and sanitized artifact identity.
- Create: `packages/battlebelief-runtime/tests/adapters/poke_engine/{test_artifact.py,test_import_boundary.py,test_native_probe.py,test_sentinel.py}`.
- Create: `packages/battlebelief-runtime/tests/fixtures/poke_engine/{gen9_transition.json,gen9_tera_transition.json,minimal_search.json}`.
- Create: `schemas/manifests/engine-source.schema.json`, `engine-build.schema.json`, and `engine-artifact-index.schema.json` **[NEW SCHEMAS v1]**, plus valid examples.
- Create: `tools/build_poke_engine_wheel.py`, `tools/verify_poke_engine_artifact.py`, and `tools/smoke_gen9_engine.py`.
- Create: `artifacts/gen9ou/m2/engine/README.md` documenting manifest layout and retrieval, but commit no wheel unless repository policy and MD-01 explicitly authorize it.
- Modify: `packages/battlebelief-runtime/pyproject.toml` to add `[project.optional-dependencies].search` with the exact approved wheel-install strategy; do not add `poke-engine` to base dependencies.
- Modify: root packaging/source configuration only if needed to include small manifest files, never binary output by accident.
- Modify: `tools/check_architecture.py` and tests to allow `poke_engine` imports only in `battlebelief_runtime.adapters.poke_engine` and forbid import-time loading elsewhere.
- Modify: `tools/check_schemas.py`, `tools/check_versions.py` if extra metadata is governed, `tools/smoke_packages.py`, their tests, and `.github/workflows/pr.yml` for isolated Runtime `[search]` cells and the sentinel.
- Delete: none.

**Public types and APIs:** only `EngineArtifactIdentity`, `EngineAvailability`, and `run_gen9_sentinel()` are **[PUBLIC RUNTIME API]** through curated exports. There is no public `PokeEngineAdapter`, state mapper, action mapper, transition backend, prepared world, or mapping failure in this task. `native_probe.py`, extension objects, and raw state strings are private and may be replaced after Task 26 freezes the Core port. Base `import battlebelief_runtime` and status inspection work without the extra.

**Allowed imports:** only `battlebelief_runtime.adapters.poke_engine` may import `poke_engine`; no Core or Lab module imports the extension directly. This task does not depend on a not-yet-defined Core transition port. Runtime must not import Lab.

**Artifact/build requirements:**

- Build from one approved exact commit in a clean verified tree. Explicitly enable the exact `gen9` and `terastallization` features; reject the upstream Python binding's Gen-4 default.
- Record Rust toolchain, Cargo lock digest, maturin version, build flags/features, target triple, Python ABI/tag, platform tag, source/build manifest digests, adapter version, wheel filename/size/SHA-256, and license/source origin.
- Build into an isolated output directory and install the finished wheel into a fresh environment for each supported Python/OS cell. Public Runtime never shells out to Cargo/maturin and never silently accepts the upstream sdist.
- Before backend creation, verify distribution name/version, import metadata, wheel/installed-files digest strategy, sidecar artifact manifest, selected features, target/environment compatibility, and adapter compatibility. Any disagreement fails closed.

**Real sentinel:** through the private probe, create a Gen 9 state; prove a normal transition and reversible/state-consistent result; exercise an actual Terastallization transition; enumerate native legal choices without asserting BattleBelief mapping semantics; run the native minimal search entry point with exact iterations, one thread, and a fixed seed if supported; assert a native result and stable artifact health. If upstream does not expose seed control adequate for a deterministic sentinel, record that as an unqualified or health-only property rather than faking determinism.

**Tests first:** absent extra; wrong distribution; source/build/wheel/feature/platform mismatch; corrupted sidecar; a fake import shadow; Gen-4 default artifact; Tera fixture; native transition apply/reverse; native minimal search; probe exception sanitization; no import on base package import; wheel installation into a clean environment; public-export test rejecting mapper/adapter symbols.

**Implementation checklist:**

- [ ] Add failing artifact-verification, no-extra import, private-probe, transition, Tera, minimal-search, public-export, and isolated-install tests.
- [ ] Implement the controlled source/build/wheel manifests and explicit Gen-9/Terastallization build command.
- [ ] Implement Runtime-only artifact verification, private native probing, artifact health, and sanitized failure types without a public mapping API.
- [ ] Implement the real sentinel and isolated base/`[search]` package smokes on approved cells.
- [ ] Run focused suites and full gates; retain manifests/results but no unapproved binary publication.

**Failure/fallback:** missing extra or artifact, wrong digest/features/platform, sentinel failure, import error, panic/exception, or native health failure returns an unavailable/unhealthy artifact identity. No BattleBelief search call is allowed. Runtime composition later maps it to `heuristic_v0`; this task does not yet add mapping or composition.

**Provenance/digests:** source, build, wheel, installed verification, adapter, Python, OS/architecture, and sentinel fixture/result digests are resolvable from the artifact index. No local path, hostname, compiler cache path, or secret enters the canonical manifest.

**CI/package smokes:** base Runtime without `[search]`; isolated `[search]` wheel install on every approved Python/OS cell; `tools/smoke_gen9_engine.py`; architecture import confinement; package build/sdist/wheel smoke. Unsupported matrix cells explicitly skip qualification and fail if marked supported.

**Acceptance criteria:** a real approved wheel—not a mock—passes isolated installation and the Gen-9/Tera/native-transition/minimal-search sentinel; the base package has no engine dependency; artifact mismatch is fail-closed; the public Runtime surface exposes no state/action mapper or transition adapter; no parity or capability-exact claim is made.

**Non-goals:** capability qualification, Showdown differential evidence, Core port/eligibility, algorithms, evaluation, or publishing an artifact without separate authorization.

**Prerequisites:** Tasks 23-24 and MD-01/02 approval. **Blocks:** Tasks 26-29 and 36-37. **Safe review boundary:** reviews binary provenance and native artifact health independently from Core API, mapping, mechanics claims, or deadline guarantees.

### Task 26 (D): Freeze Core capability and transition/search foundations

**Purpose:** Establish the capability vocabulary, engine-neutral search types, generic world-distribution identity, and `TransitionModel` port before Runtime publishes any mapping adapter.

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/domain/engine_capabilities.py`.
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/search.py`.
- Create: `packages/battlebelief-core/src/battlebelief_core/ports/transition_model.py` and `random_source.py`.
- Create: `packages/battlebelief-core/tests/domain/test_engine_capabilities.py`.
- Create: `packages/battlebelief-core/tests/domain/test_search_types.py` and `tests/ports/{test_transition_model_contract.py,test_random_source_contract.py}`.
- Create: `schemas/manifests/engine-capability-v2.schema.json` **[NEW SCHEMA v2]** and `engine-capability-evidence.schema.json` **[NEW SCHEMA v1]**.
- Create: `schemas/catalogs/engine-capability-catalog-v1.schema.json` **[NEW SCHEMA v1]**.
- Create: `artifacts/gen9ou/m2/engine-capability-catalog-v1.json` and schema examples after the Maintainer approves the exact taxonomy.
- Create: `docs/migrations/engine-capability-v1-to-v2.md` if the documentation governance contract requires a migration note.
- Modify: `docs/contracts/engine-capabilities.md`, its frontmatter, and `docs/README.md` **only under explicit normative-change approval for MD-08**; otherwise stop this task before implementation.
- Modify: `docs/contracts/manifest-schemas.md`, `tools/check_schemas.py`, schema tests, canonicalization tests, and architecture exports.
- Delete: none; preserve `schemas/manifests/engine-capability.schema.json` v1 and its examples.

**Public types and APIs:** `CapabilityId`, `CapabilityCatalog`, `CapabilityStatus`, `CapabilityClaim`, `EngineCapabilityManifest`, `CapabilityEvidenceRef`, `PreparedWorld`, `SearchAction`, `PlayerView`, `InformationStateKey`, `TransitionOutcome`, `TransitionWork`, `TransitionModel[WorldT, ActionT]`, `RandomStream`, and `WorldDistributionIdentity` are **[PUBLIC CORE API]** immutable values/protocols. `WorldDistributionIdentity` contains only algorithm-neutral identity/support fields—distribution ID/version/digest, generation/format/ruleset digest, public-evidence digest, support digest/count, and availability status—not a Task-30 concrete distribution class.

**Allowed imports:** Core standard library and existing Core canonicalization/types only. Manifest bytes, prepared worlds, and identities are supplied by callers; Core performs no file, environment, Runtime, Lab, engine, clock, process, or network import.

**Semantics:** each catalog ID has one status: `exact`, `bounded_approximation`, `unsupported`, or `unknown`. `exact` requires evidence refs bound to the engine artifact, oracle, ruleset, and corpus. `bounded_approximation` includes an explicit bound/condition but remains search-ineligible wherever exact is required. Missing catalog IDs are interpreted as unknown, not exact. Duplicate/overlapping claims, unknown free-form IDs, or evidence bound to another artifact are invalid.

The transition port defines root preparation, per-player information views/keys, per-player legal engine-neutral actions, joint transition/chance outcomes, terminal state/value access, backend health/identity, and explicit transition-work accounting. It exposes neither `poke-engine` strings nor a concrete closed-world type. Test fakes, not Task-25 probe internals, drive the public signature review.

**Tests first:** v1 remains valid under its existing schema; v2 round-trip/canonical digest; missing ID becomes unknown; all four statuses; duplicate and contradictory IDs; malformed namespaces; evidence/artifact mismatch; bounded approximation never parses as exact; catalog-digest mismatch; sorted canonical output; v1-to-v2 migration; protocol conformance fake; immutable prepared world/action/view/outcome values; generic distribution identity without Task-30 imports; deterministic transition-work counting; architecture negatives for engine/file/clock/process/network dependencies.

**Implementation checklist:**

- [ ] Obtain MD-08 and normative-change approval before editing a contract or schema index.
- [ ] Add failing v2/catalog/evidence examples, semantic tests, canonical vectors, and v1 compatibility tests.
- [ ] Implement immutable Core capability/search/distribution-identity types, transition/random protocols, and strict four-state/catalog/evidence validation.
- [ ] Add the approved catalog and an explicitly unqualified initial manifest; do not create exact claims.
- [ ] Run schema, docs, canonicalization, Core, package, and full repository gates.

**Negative/failure paths:** unrecognized schema/catalog version, missing evidence, stale corpus/ruleset/adapter/wheel digest, or unsupported platform invalidates the manifest for qualification. Parser errors are deterministic and contain JSON pointers, not local paths.

**Provenance/digests:** manifest v2 binds catalog, engine source/build/artifact, adapter, oracle source/build, ruleset, corpus, evidence set, supported environment matrix, generation/format, and canonicalization contract digests.

**CI/package smokes:** schema example validation, canonicalization vectors, v1 compatibility, manifest-closure tool smoke, Core-only import smoke, transition-port fake conformance, and forbidden-import fixtures.

**Acceptance criteria:** the four accepted statuses are unambiguous; v1 artifacts remain readable and unchanged; no capability is marked exact before Task 29 evidence; the complete engine-neutral port and generic distribution identity are public and tested before Runtime mapping; no Task-25 private probe type leaks into Core.

**Non-goals:** Runtime mapping, concrete closed-world filtering/sampling, eligibility decisions, algorithm semantics/implementation, engine calls, evidence generation, or changing registered gates.

**Prerequisites:** Tasks 23-25, MD-06/08 approval, and any approved normative amendment. **Blocks:** Tasks 27-42. **Safe review boundary:** all public Core foundations are reviewed before Runtime mapping, qualification, distribution, or eligibility can depend on them.

### Task 27 (E): Implement Runtime `poke-engine` mapping and Core-port conformance

**Purpose:** Map BattleBelief observations, complete hypothetical worlds, safe root submissions, deeper actions, and transition results to the already merged Core `TransitionModel` without adding eligibility or search.

**Files:**

- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/{state_mapper.py,action_mapper.py,transition_model.py,mapping_report.py}`.
- Create: `packages/battlebelief-runtime/tests/adapters/poke_engine/{test_state_mapper.py,test_action_mapper.py,test_transition_model.py,test_mapping_report.py,test_port_conformance.py}`.
- Create: `packages/battlebelief-runtime/tests/fixtures/poke_engine/{observed_root_mapping.json,complete_world_mapping.json,joint_transition_mapping.json,unsupported_mapping.json}`.
- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/__init__.py` to expose only the approved adapter surface.
- Modify: `tools/check_architecture.py`, `tests/tooling/test_architecture.py`, Runtime package smokes, and `.github/workflows/pr.yml` for import confinement and real port-conformance smoke.
- Delete: none; Task-25 private probe remains available only to its sentinel and is not the public adapter implementation.

**Public types and APIs:** `PokeEngineTransitionModel`, `PokeEngineMappingFailure`, `MappingReport`, and `RequiredCapabilities` are **[PUBLIC RUNTIME API]** and implement Task-26 types exactly. No Core signature changes are permitted in this task; a genuine port defect stops the task and becomes a Maintainer decision/successor Core PR.

**Allowed imports:** Runtime adapter code may import approved Core types and the verified optional extension. Only this adapter subtree imports `poke_engine`; Core and Lab never do. Runtime must not import Lab.

**Mapping contract:** root candidates originate only from the supplied `SafeSubmissionSet`; mapper output retains the stable safe-set index and request identity. Complete hypothetical worlds map through a separate type from `ObservedState`. Deeper native choices map to engine-neutral `SearchAction`. Every mapped mechanic produces catalog capability IDs. Player views are created separately for each side, joint actions are applied only after both choices exist, and raw engine strings never cross the Runtime public boundary.

**Tests first:** all Task-26 protocol methods; ordinary move/switch/Tera/forced-switch mappings; safe-root order preservation; observed versus complete-world type separation; both player views; simultaneous joint transition; chance outcome normalization; terminal/value mapping; unsupported/unknown fields; stale request/safe set; backend artifact mismatch; native exception; deterministic work count; no private data in `MappingReport`.

**Implementation checklist:**

- [ ] Add failing port-conformance, state/action/view, safe-root, joint-transition, and mapping-failure tests against the merged Core API.
- [ ] Implement state/action mapping and sanitized capability/mapping reports without changing Core.
- [ ] Implement `PokeEngineTransitionModel` over the verified Task-25 artifact and exact transition-work accounting.
- [ ] Add real bounded Gen-9/Tera port-conformance and architecture/package smokes.
- [ ] Run focused Runtime tests and every repository gate; audit that no Task-25 probe or raw native type is public.

**Failure/fallback:** any missing field, unsupported choice, capability ambiguity, request/safe-set mismatch, artifact/adapter mismatch, native exception, or work-accounting inconsistency returns a typed mapping/backend failure. This task has no eligibility policy and does not select an action.

**Provenance/digests:** adapter version/source digest, Task-26 port contract digest, engine source/build/wheel identity, fixture digest, required capability IDs, and sanitized mapping result bind conformance. Reports exclude hidden world contents, paths, hostnames, and raw exceptions.

**CI/package smokes:** base Runtime import remains engine-free; `[search]` installs the verified wheel; real adapter conformance runs on approved cells; architecture tests reject engine imports outside the adapter.

**Acceptance criteria:** the Runtime adapter implements the merged Core port without changing it; root mapping cannot create an action outside the safe set; all mapping failures are typed; no eligibility, algorithm, or exact-capability claim is added.

**Non-goals:** differential evidence, exact qualification, closed-world filtering, eligibility, algorithms, deadline isolation, Runtime session composition, or evaluation.

**Prerequisites:** Tasks 25-26 and MD-06/07 approval. **Blocks:** Tasks 28-42. **Safe review boundary:** the concrete backend mapping is reviewable against a stable Core contract before any decision policy can invoke it.

### Task 28 (F): Add the versioned Showdown-versus-`poke-engine` differential corpus and runner

**Purpose:** Freeze the differential corpus format, reviewed fixtures, comparison/classification code, schemas, and synthetic/golden behavior before any real qualification outcome is produced.

**Files:**

- Create: `packages/battlebelief-lab/src/battlebelief_lab/differential/{__init__.py,corpus.py,runner.py,classifier.py,evidence.py,report.py}`.
- Create: `packages/battlebelief-lab/tests/differential/{test_corpus.py,test_runner.py,test_classifier.py,test_evidence.py,test_report.py}`.
- Create: `schemas/evaluation/differential-corpus.schema.json`, `differential-fixture.schema.json`, `differential-result.schema.json`, and `capability-qualification.schema.json` **[NEW SCHEMAS v1]** with valid/invalid examples.
- Create: `artifacts/gen9ou/m2/differential/corpus-v1/{index.json,fixtures/*.json,README.md}` after MD-09 and fixture review; keep cases minimal and project-authored or properly licensed.
- Create: `tools/validate_differential_corpus.py` and `tools/run_engine_differential.py`.
- Modify: `tools/check_schemas.py`, `tools/smoke_packages.py`, their tests, and `.github/workflows/pr.yml` to validate the corpus and run only synthetic/golden runner smokes on ordinary PRs.
- Modify: Lab package exports and optional test/oracle profile metadata as needed; no Runtime-to-Lab edge.
- Delete: none; deprecated corpus versions remain immutable and addressable.

**Public types and APIs:** `DifferentialCorpus`, `DifferentialFixture`, `DifferentialRunner`, `CanonicalMechanicsObservation`, `DivergenceClass`, `FixtureResult`, and `CapabilityQualificationEvidence` are **[PUBLIC LAB API]**. The evidence builder defaults to unknown/non-exact and cannot emit exact when any required result is absent, synthetic, skipped, failed, or unclassified.

**Allowed imports:** Lab may import Core capability/types and the approved Runtime `PokeEngineTransitionModel` public surface. It calls the Lab oracle internally. It must not import private extension objects, and Runtime/Core must not import Lab.

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
- [ ] Run synthetic/golden oracle/engine doubles through every outcome class and prove the evidence builder rejects incomplete qualification.
- [ ] Run corpus/differential harness smokes and all repository gates; freeze code, schemas, classifier, and corpus before Task 29.

**Failure/fallback:** any unavailable oracle/engine artifact, mismatch, timeout, crash, mapping failure, incomplete corpus, or unclassified divergence makes affected capabilities non-exact and therefore search-ineligible. The report counts every fixture outcome; retries are recorded and cannot replace the original result silently.

**Provenance/digests:** a Merkle-like index digest covers sorted fixture file digests and schema/classifier versions. Evidence references immutable raw result digests. A corpus change creates `corpus-v2` (or a semantically versioned successor), never edits v1 after evidence registration.

**CI/package smokes:** fast data-only corpus validator and synthetic/golden oracle/adapter doubles on every PR. Task 28 runs no real Showdown-versus-engine comparison; the first real matrix is Task 29 after this code merges. Network denial remains active.

**Acceptance criteria:** runner, classifier, corpus, schemas, golden vectors, and evidence rules are merged and immutable for the subsequent run; no real capability is elevated; synthetic incomplete/failure cases cannot yield exact.

**Non-goals:** executing the qualification matrix, creating exact claims, broad parity, search, closed-world distribution, protected evaluation, or reclassification after results.

**Prerequisites:** Tasks 24-27 and MD-09/14/20 approval. **Blocks:** Tasks 29-42. **Safe review boundary:** all code and classification rules merge before real divergences are visible.

### Task 29 (G): Run data-only engine capability qualification

**Purpose:** Execute the already merged differential tooling and corpus against the exact Showdown and `poke-engine` artifacts, preserving every outcome before any exact capability is usable.

**Files:**

- Create: `artifacts/gen9ou/m2/differential/runs/qualification-v1/{run-binding.json,raw-results.jsonl,result-index.json,report.json}`.
- Create: `artifacts/gen9ou/m2/engine-capabilities/engine-capability-v2-qualified.json`, one deterministic `evidence/<evidence-id>.json` document per qualifying claimed capability and environment cell, and the repository-relative `artifacts/gen9ou/m2/differential/runs/qualification-v1/provenance/index.json` plus its referenced immutable closure bytes, only from complete retained results. `unknown` and `unsupported` capabilities produce no capability-evidence documents; their complete unfavorable, aborted, or divergent outcomes remain retained in the differential run artifacts. The evidence directory is the exact union of documents referenced by qualifying claims across discovered manifests; an unchanged document may be reused by multiple manifests, and no evidence files are written outside that directory.
- Modify: `artifacts/gen9ou/m2/differential/README.md` to link immutable run/evidence digests and scope.
- Modify: no Python, schema, contract, corpus fixture/index, classifier, catalog, Runtime adapter, or CI file.
- Delete: none; failed, crashed, timed-out, and unfavorable rows remain immutable.

**Public APIs:** none.

**Allowed imports:** none are added. This is a data/evidence-only PR invoking merged Lab public tools and creates no package import edge.

**Qualification procedure:** resolve exact oracle source/build, engine source/build/wheel/adapter, ruleset, catalog, corpus/classifier, runner, environment, and seed digests before execution. Run the complete approved matrix once. Retain raw first-attempt results and any explicitly authorized retries as additional rows. Generate claims mechanically: exact requires every applicable fixture/environment cell, zero skipped/failed/known-affecting/unclassified divergence, and matching identities; anything else remains bounded, unsupported, or unknown under the premerged classifier.

**Tests and validation first:** validate binding closure before the run; reject dirty/mismatched artifacts; prove the generated evidence reproduces from raw rows; ensure one missing/unclassified/crashed fixture rejects exact; compare corpus/classifier/tool source digests with Task 28; assert the diff contains only the named data/evidence paths.

**Implementation checklist:**

- [ ] Obtain explicit qualification-run authorization and close every input digest without changing Task-28 tooling.
- [ ] Execute the complete matrix, retain all raw outcomes, and classify only through the merged classifier.
- [ ] Generate the result index, report, capability evidence, and successor manifest mechanically.
- [ ] Re-run evidence generation from raw rows and byte-compare canonical outputs.
- [ ] Run artifact/schema/full repository gates and perform a data-only diff audit.

**Failure/fallback:** unavailable/mismatched artifacts, runner failure, timeout, crash, incomplete matrix, or unclassified divergence prevents affected exact claims. It does not trigger code/schema/corpus edits inside this PR. A tooling defect marks the run invalid and requires a separately reviewed successor harness/corpus task followed by a new qualification version.

**Provenance/digests:** raw/result/evidence closure includes all oracle, engine, adapter, catalog, corpus, classifier, runner, ruleset, environment, seed, and schema digests. No result is deleted or overwritten.

**CI/package smokes:** data/evidence schema and closure validation; raw-to-report reproducibility; frozen Task-28 source/corpus digest assertion; ordinary package smokes remain unchanged.

**Acceptance criteria:** the diff is data/evidence-only; every real outcome is retained; each exact claim has complete artifact-matched evidence and zero unclassified/affecting divergence; missing evidence remains non-exact.

**Non-goals:** changing qualification semantics, adding fixtures after results, search, distribution, eligibility, evaluation pools, or parity claims.

**Prerequisites:** Tasks 24-28, MD-20 approval, and explicit Maintainer run authorization. **Blocks:** Tasks 30-42. **Safe review boundary:** real mechanics outcomes cannot influence the already merged runner, schema, classifier, or corpus.

### Task 30 (H): Add the evaluation-only closed-world distribution

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

**Public types and APIs:** `ClosedWorld`, `ClosedWorldPrior`, `PublicEvidence`, `ClosedWorldDistribution`, `ClosedWorldDistributionSummary`, and `ClosedWorldSampler` are **[PUBLIC CORE API]** but explicitly evaluation-only. `ClosedWorldDistributionSummary.to_identity()` returns the Task-26 generic `WorldDistributionIdentity`; eligibility never depends on this concrete class. No symbol contains or aliases `BeliefState`, and Runtime's general public API must not re-export them as production belief.

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

**Prerequisites:** Tasks 23-29, MD-11 approval, and source/license review. **Blocks:** Tasks 31-42. **Safe review boundary:** hidden-information and prior semantics are reviewed after qualification but before eligibility/search, with no exception to strict serial merge order.

### Task 31 (I): Add pure Core eligibility and fail-closed heuristic policy

**Purpose:** Decide, without backend imports or I/O, whether engine-backed search may start for the exact observed decision, using the already merged generic distribution identity and qualified capability evidence.

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/application/engine_eligibility.py` and `search_policy.py`.
- Create: `packages/battlebelief-core/tests/application/{test_engine_eligibility.py,test_search_policy_fallback.py}`.
- Create: `packages/battlebelief-core/tests/fakes/{transition_model.py,random_source.py}` with deterministic Task-26 protocol fakes.
- Modify: Core curated exports and `tools/check_architecture.py`/tests for pure application restrictions.
- Modify: no decision-record schema; Task 35 owns record/fallback representation.
- Delete: none.

**Public types and APIs:** `SearchEligibilityInput`, `SearchEligibilityDecision`, `EligibilityReason`, `SearchCandidate`, `SearchDecision`, and `EngineQualifiedSearchPolicy` are **[PUBLIC CORE API]**. `SearchEligibilityInput` accepts Task-26 `WorldDistributionIdentity`, never `ClosedWorldDistributionSummary`; Task 30 converts to the generic identity at the composition edge.

**Allowed imports:** Core domain/ports/application code and standard library only. No concrete distribution class is required by eligibility. No adapter, engine, filesystem, environment, random global, clock, process, or network import is allowed.

**Pure decision:** inputs are observed state, authoritative `SafeSubmissionSet`, required capability IDs from Task-27 mapping, generic world-distribution identity, Task-29 capability manifest/evidence, and backend/artifact health identity. Eligible requires a nonempty unchanged safe set; matching observed/request/prepared-root identity; matching distribution generation/format/ruleset/public-evidence/support identity; matching backend source/build/wheel/adapter/platform; exact evidence for every required capability; and no mapping/health failure. Unknown, unsupported, bounded approximation, missing evidence, mismatch, or backend failure is ineligible.

**Tests first:** exhaustive reason/precedence table; empty/mutated/stale safe set; every capability status; missing catalog item/evidence; manifest/artifact/ruleset/distribution/adapter mismatch; unavailable distribution; unhealthy backend; mapping error; deterministic reason order; no backend call when ineligible; injected search called once when eligible; search error/invalid candidate/no result returns the identical injected `heuristic_v0` result.

**Implementation checklist:**

- [ ] Add failing generic-identity and exhaustive eligibility/fallback tests before application code.
- [ ] Implement deterministic eligibility with no concrete Task-30 type dependency.
- [ ] Implement precomputed heuristic-incumbent orchestration and typed internal reasons.
- [ ] Add architecture and fake-model tests proving no I/O/backend call on denial.
- [ ] Run focused Core, architecture, package, frozen-artifact, and full repository gates.

**Failure/fallback:** eligibility denial or subsequent search/backend failure returns the unchanged precomputed heuristic submission and stable internal reason. If heuristic cannot return a safe member, existing safe failure/forfeit behavior governs; search never invents an action.

**Provenance/digests:** decision includes input identity digests, required capability IDs, generic distribution identity, outcome/reason, config/work identity when applicable, and selected safe-set index; it excludes concrete worlds, hidden data, raw exception, clock, path, and host.

**CI/package smokes:** Core-only import; architecture negative fixtures; deterministic fake transition/distribution identity; no real engine dependency.

**Acceptance criteria:** the truth table is exhaustive; search cannot start unless all required mechanics are exact and all identities match; every denial/error returns `heuristic_v0`; no later concrete-distribution API change is needed.

**Non-goals:** algorithm semantics/implementation, record schemas, deadlines, Runtime composition, evaluation, or capability elevation.

**Prerequisites:** Tasks 23-30 and MD-06/08/14 approval. **Blocks:** Tasks 32-42. **Safe review boundary:** safety policy consumes stable prior APIs and evidence, so it requires no provisional distribution or adapter type.

### Task 32 (J): Bind outcome-blind determinization and DUCT algorithm specifications

**Purpose:** Resolve every search behavior not fixed by the frozen M1.5 artifacts before either algorithm is implemented or any evaluation outcome exists.

**Files:**

- Create: `schemas/manifests/determinization-algorithm-spec-v1.schema.json` and `information-set-duct-config-v1.schema.json` **[NEW SCHEMAS v1]** with valid/invalid examples.
- Create: `artifacts/gen9ou/m2/search-specs/determinization-search-v0-algorithm-v1.json` and `information-set-duct-v0-config-v1.json` after explicit MD-16 approval.
- Create: `packages/battlebelief-lab/src/battlebelief_lab/search_specs/{__init__.py,validator.py}` and tests for semantic cross-validation against the frozen registration/execution spec and accepted Search-v0 contract.
- Create: `tools/validate_m2_search_specs.py`.
- Modify: `docs/contracts/manifest-schemas.md`, schema tooling/tests, package smoke, and CI only for approved new manifest types; do not change accepted Search-v0 semantics.
- Modify: no frozen registration, determinization execution manifest, calibration spec/evidence, metric, gate, or Task-21 binding.
- Delete: none.

**Public types and APIs:** `DeterminizationAlgorithmSpec`, `InformationSetDuctConfig`, and `validate_m2_search_specs(...)` are **[PUBLIC LAB API]** manifest values/validation. Core algorithms later receive validated immutable config values; this task adds no algorithm code.

**Allowed imports:** Lab validation may import Core manifest/config value types and read the accepted/frozen artifacts through Lab file adapters. Core and Runtime do not import Lab; no engine, search execution, clock, or result data enters this task.

**Required determinization fields:** exact depth-counting convention; terminal-before/at-depth handling; root safe-action enumeration; deterministic per-root work allocation and remainder rule for every grid point/candidate count; opponent policy and its information view; simultaneous own/opponent action-selection order without clairvoyance; chance enumeration/sampling/seed policy; leaf/terminal value function and perspective/range; backup rule; action/world aggregation order; numeric precision/non-finite handling; all tie orders; and failure semantics. It incorporates, but never changes, 16 worlds, depth 2, grid 64/128/256/512, one transition per work unit, arithmetic world mean, safe-order tie, and heuristic fallback.

**Required DUCT fields:** exploration formula/constant; unvisited initialization; value perspective/range; visit/value backup; terminal/leaf evaluation; chance handling; exact information-state key contract; per-player marginal selection/ties; joint-transition timing; root aggregation; simulation/work accounting and work-matching rule; every seed domain; tree reset/reuse policy; numeric/failure behavior; and fixed single-thread reference configuration. All fields preserve the accepted Search-v0 invariants.

**Tests first:** every required field absent/invalid; frozen value mismatch; ambiguous depth/work/remainder; backend/default sentinel values rejected; unknown policy/value/chance/backup IDs; DUCT config missing exploration/work rule; deterministic canonical digest; implementation-source test proving Tasks 33/34 config loaders reject unbound/default values.

**Implementation checklist:**

- [ ] Obtain MD-16 decisions for every enumerated semantic/parameter field before writing artifacts.
- [ ] Add failing schemas, semantic cross-validation, frozen-value, completeness, and canonicalization tests.
- [ ] Create and validate both outcome-blind specifications with explicit named policy/value/chance/backup IDs.
- [ ] Bind their digests in a pre-implementation search-spec index without touching frozen artifacts.
- [ ] Run schema/docs/frozen-artifact/package/full gates and audit that no result data informed the choices.

**Failure/fallback:** any omitted, ambiguous, defaulted, or conflicting field blocks Tasks 33/34. A conflict with an accepted contract becomes a Maintainer decision before contract change; it is not resolved in code.

**Provenance/digests:** each spec binds registration/execution/Search-v0/canonicalization/capability/distribution contract digests, authorizing decision record, schema, and complete canonical bytes. It contains no evaluation result or calibration outcome.

**CI/package smokes:** schema/example/canonicalization; semantic validator against frozen artifacts; negative default/missing-field fixtures; immutable registration/arm-spec check.

**Acceptance criteria:** both specs are complete, outcome-blind, versioned, canonical, and merged; every previously unspecified behavior named in MD-16 is resolved; later implementations require the exact spec digest and have no semantic defaults.

**Non-goals:** algorithm code, calibration selection, performance tuning, evaluation, or frozen-artifact modification.

**Prerequisites:** Tasks 23-31 and explicit MD-16 approval. **Blocks:** Tasks 33-42. **Safe review boundary:** specification choices are reviewed before implementation or outcomes can influence them.

### Task 33 (K): Implement the registered `determinization_search_v0`

**Purpose:** Implement the determinization baseline from the immutable M1.5 execution values plus the complete, outcome-blind Task-32 algorithm specification, using only qualified transitions and the Task-30 distribution.

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/application/search/__init__.py`.
- Create: `packages/battlebelief-core/src/battlebelief_core/application/search/determinization_v0.py` and `work_accounting.py`.
- Create: `packages/battlebelief-core/tests/application/search/{test_determinization_v0.py,test_work_accounting.py,test_determinization_registration_conformance.py,test_determinization_algorithm_spec_conformance.py}`.
- Create: `packages/battlebelief-core/tests/fixtures/search/determinization_v0_vectors.json` with canonical project-authored fake-tree vectors.
- Modify: Core curated exports.
- Modify: `tools/check_architecture.py` and tests for pure-algorithm restrictions.
- Modify: no registration or arm-spec file.
- Delete: none.

**Public types and APIs:** `DeterminizationSearchV0`, `DeterminizationConfigV0`, `DeterminizationResult`, `RootActionScore`, and `TransitionWorkCounter` are **[PUBLIC CORE API]**. Configuration construction requires both the frozen execution-spec digest and Task-32 algorithm-spec digest; there are no backend/default values.

**Allowed imports:** Core search imports Core ports/domain/application only. Real engine and artifact access enter through `TransitionModel`; no Runtime, Lab, file, clock, network, or global-random dependency is permitted.

**Exact registered execution:**

- sample exactly 16 worlds from `evaluation_closed_world_v0` using the dedicated world seed;
- search to registered lookahead depth 2 using Task-32's exact depth-counting and terminal convention;
- execute each registered `per_world_work` point in the ordered grid `64`, `128`, `256`, `512` as a separate calibrated configuration;
- define one work unit as one call that advances one world transition, including terminal-producing transitions; bookkeeping, mapping, scoring, and sampling are not transition work;
- allocate exactly `per_world_work` units to each of the 16 worlds and report total work as `16 * per_world_work`, distributing root/remainder work only by the Task-32 rule;
- apply Task-32 opponent, simultaneous-action, chance, leaf-value, backup, and numeric rules, then use the frozen arithmetic mean across all 16 worlds; no backend policy/default or optimistic world selection is introduced;
- select the maximal mean, breaking exact score ties by stable `SafeSubmissionSet` order;
- return the existing `heuristic_v0` result on eligibility denial, invalid/empty result, work mismatch, or transition/backend failure.

The implementation must validate frozen values against `registrations/gen9ou/arm-specs/determinization-search-v0-v4.json` and every remaining behavior against Task-32's specification. It must not edit either artifact or choose an allocation, opponent policy, chance, value, depth, backup, or remainder interpretation in code.

**Tests first:** conformance loads both specs; exactly 16 sampler calls; exactly 64/128/256/512 transitions per world and totals; exact depth/terminal boundary; every candidate-count remainder vector; opponent/simultaneous/chance/leaf/backup golden vectors; arithmetic mean versus max/weight; safe-order tie; exact safe candidate set; seed separation; iteration/map-order independence; terminal accounting; short/extra work; missing/wrong spec digest; backend errors; hidden-world exclusion; heuristic fallback identity.

**Implementation checklist:**

- [ ] Add failing registration-conformance and fake-tree vectors for every frozen value and failure path.
- [ ] Implement transition-work accounting and the depth-2 per-world kernel without Runtime dependencies.
- [ ] Implement 16-world aggregation, arithmetic mean, stable safe-order tie, and heuristic fallback.
- [ ] Add qualified-adapter integration smoke while keeping unit tests engine-free.
- [ ] Run all work-grid vectors, focused Core tests, frozen-artifact checks, and full repository gates.

**Failure/fallback:** any Task-31 ineligibility, world sampling failure, transition/model failure, non-finite value, candidate/action mapping mismatch, work-budget violation, or no score for every safe root candidate returns the precomputed `heuristic_v0` incumbent with the stable class. Partial search does not override it in deterministic mode.

**Provenance/digests:** result binds algorithm/version, frozen execution-spec digest, Task-32 algorithm-spec digest, search config/work point, 16-world distribution/support digest, all named seed identities, transition-model artifact identity, capability evidence, and deterministic score summary. It never includes sampled world content.

**CI/package smokes:** Core vector/conformance tests, architecture test, deterministic repeat smoke on fake transitions; no real engine dependency in Core tests.

**Acceptance criteria:** every frozen and Task-32 semantic field has a direct conformance/golden test; all work points use exact transition counts and specified allocation; repeated pure executions match; no registered/spec artifact changes.

**Non-goals:** DUCT, live deadlines, parallelism, adaptive worlds/depth/work, alternate averaging, tuning, engine qualification, or evaluation outcomes.

**Prerequisites:** Tasks 23-32. **Blocks:** Tasks 34-42. **Safe review boundary:** implements one fully specified algorithm with fakes and qualified-adapter conformance, no DUCT, records, clocks, or evaluation.

### Task 34 (L): Implement `information_set_duct_v0` on the same closed world

**Purpose:** Implement the accepted Search-v0 information-set DUCT semantics and the complete Task-32 configuration without allowing hidden-state nodes, backend defaults, or world-dependent joint-action optimization.

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/application/search/information_set_duct_v0.py`, `information_tree.py`, and `simultaneous_selection.py`.
- Create: `packages/battlebelief-core/tests/application/search/{test_information_set_duct_v0.py,test_information_tree.py,test_simultaneous_selection.py,test_search_v0_contract.py}`.
- Create: `packages/battlebelief-core/tests/fixtures/search/information_set_duct_v0_vectors.json` with adversarial information-set trees.
- Modify: Core curated exports.
- Modify: `tools/check_architecture.py` and tests to forbid raw hidden-world keys/serialization in tree node APIs.
- Modify: no accepted Search-v0 contract unless an actual contradiction is first recorded and separately approved as a Maintainer decision.
- Delete: none.

**Public types and APIs:** `InformationSetDuctV0`, `InformationSetDuctConfigV0`, `InformationSetDuctResult`, `InformationNodeKey`, `MarginalActionStats`, and `RootAggregate` are **[PUBLIC CORE API]**. Config construction requires the exact Task-32 DUCT-spec digest and exposes no defaults. Mutable tree/node implementation classes remain private.

**Allowed imports:** Core domain/application plus Task-26 injected ports and Task-32 validated configuration only. Neither the tree nor tests may import a Runtime hidden-state/backend type.

**Tests first — contract invariants and direct tests:**

1. **New world per simulation:** the distribution sampler is called once at the start of every simulation; a test fails implementations that reuse one world for a batch.
2. **Information-state nodes:** node keys derive solely from the acting player's `PlayerView` plus public history/config identity, never from a hidden world ID or private set; two worlds with the same view share a node, and one world with different player views does not.
3. **Correct view for both players:** own selection receives the bot-visible information view; opponent selection receives the opponent-visible view supplied by the transition port. Adversarial fixtures reveal different private facts to each and assert no cross-view access.
4. **Independent marginal action choice:** each player's node stores/selects only its marginal legal-action statistics. Tests distinguish this from a joint-action table.
5. **Joint transition afterward:** only after both marginal choices are fixed does the model receive the pair for one joint transition/chance resolution. Tests assert call order and that neither selector observes the other sampled action before selection.
6. **Root aggregation across worlds:** root submission values/visits aggregate over every sampled world by safe submission, not by hidden-state root node. Tests use worlds that reverse local preferences.
7. **No world-dependent joint-action argmax:** an adversarial payoff matrix makes a clairvoyant joint argmax attractive; expected output follows marginal information-set selection instead.

Additional tests cover every Task-32 exploration/configuration field, visit/value initialization and backup, deterministic ties, terminal/leaf values, chance outcomes, legal-action changes, fixed-work matching, seed separation, numeric rules, model errors, wrong/missing spec digest, and absence of hidden worlds from outputs. All randomness comes from injected streams. The first reference execution is single-threaded.

**Implementation checklist:**

- [ ] Add one failing adversarial test for each of the seven accepted Search-v0 invariants before tree code.
- [ ] Add failing fixed-work, seed, tie, terminal, chance, failure, and hidden-output tests.
- [ ] Implement information-view keys, independent marginal selectors, joint transition ordering, and tree updates.
- [ ] Implement cross-world root aggregation and fail-closed result handling; add qualified-adapter smoke.
- [ ] Run the contract suite, deterministic vectors, architecture/leakage checks, and all repository gates.

**Failure/fallback:** eligibility denial, distribution failure, invalid information view/key, missing marginal legal action, joint-transition mismatch, work violation, backend error, or invalid root aggregation returns the precomputed `heuristic_v0` incumbent. No node from a failed simulation is published as evidence unless rollback semantics are explicitly tested.

**Provenance/digests:** result binds the accepted Search-v0 contract digest, Task-32 DUCT-spec digest, algorithm/config/work identity, the same Task-30 prior/distribution identity used by determinization, separate world/own-selection/opponent-selection/chance/tie seeds, model/capability identities, and root aggregate summary. Tree dumps and hidden worlds are not decision-record fields.

**CI/package smokes:** contract-invariant suite with fake transition model; deterministic one-thread vector smoke; architecture/leakage negative tests; qualified-adapter bounded integration smoke.

**Acceptance criteria:** all seven invariants and every Task-32 configuration field have positive/adversarial/golden tests; it uses the same distribution; no hidden-state node, joint-action argmax, or unbound default is possible; failure is fail-closed.

**Non-goals:** open-world belief, learned priors/value/policy, multi-thread reference path, live timing, tree persistence across decisions, or registered evaluation.

**Prerequisites:** Tasks 23-33 and MD-06/07/12/16 decisions. **Blocks:** Tasks 35-42. **Safe review boundary:** isolates the second fully specified algorithm from records, clocks, Runtime composition, and evaluation.

### Task 35 (M): Version request identity, Decision Record, and Search Measurement

**Purpose:** Define backward-compatible, leakage-safe canonical records before deterministic/live executors or Runtime session composition depend on them.

**Files:**

- Create: `schemas/records/request-identity-v2.schema.json`, `decision-record-v3.schema.json`, and `search-measurement-v1.schema.json` **[NEW VERSIONED SCHEMAS]** with valid/invalid and migration examples.
- Create: `schemas/canonicalization/decision-record-v3-test-vectors.json` and `search-decision-test-vectors.json`.
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/records/search.py` and corresponding Core tests.
- Modify: `packages/battlebelief-core/src/battlebelief_core/domain/actions/decision_request.py`, `domain/records/decision_record.py`, and curated exports for approved v2/v3 dual-read models.
- Modify: `docs/contracts/decision-records.md`, `legal-action-safety.md`, `manifest-schemas.md`, `provenance.md`, frontmatter/index, and migration docs only under explicit MD-05/10/14 normative approval.
- Modify: schema/canonicalization/docs tools/tests and package smokes.
- Modify: no Runtime composition/session file.
- Delete: none; v1/v2 records, vectors, and readers remain byte-identical.

**Public types and APIs:** `RequestIdentityV2` with `live_rqid`/`oracle_sequence` variants, Task-31 `SearchDecision` canonical projection, `SearchDecisionSummary`, `SearchFallbackReason`, `DecisionRecordV3`, `SearchMeasurement`, and `SearchTermination` are **[PUBLIC CORE RECORD API]**. Operational timing is absent from deterministic decision bytes and present only in the linked measurement.

**Allowed imports:** Core record/canonicalization code only. No engine, clock read, filesystem, Runtime, or Lab import. Callers pass operational measurements explicitly.

**Record semantics:** v3 stores algorithm/mode/spec/config identities, fixed work/world/simulation counts, selected safe-set index, eligibility outcome, stable successful fallback reason, and linked measurement ID. It excludes sampled worlds, opponent-private data, absolute time, duration, host/path/PID, and raw exceptions. Submitted fallback is not encoded as a v2 error. Oracle identity uses sequence plus request digest, never fake `rqid`.

**Tests first:** v1/v2 parse/canonical bytes unchanged; both identity variants; identity mismatch; v3 searched success, successful fallback, error, timeout, and safety rejection; deterministic SearchDecision/row repeated bytes; measurement linkage; duration changes measurement but not decision row; unknown fallback; hidden/private/path/host/raw-exception leakage; canonical set/order vectors and migrations.

**Implementation checklist:**

- [ ] Obtain MD-05/10/14 approval and add failing schema, migration, canonical-byte, fallback, and leakage tests.
- [ ] Implement typed dual-read identities/records and deterministic SearchDecision projection.
- [ ] Implement linked operational measurement without reading a clock in Core.
- [ ] Update approved normative owners, examples, canonical vectors, docs/schema tooling, and smokes.
- [ ] Run focused contract/Core tests, immutable-old-vector checks, and every repository gate.

**Failure/fallback:** invalid identity, unknown schema/reason, mismatched safe-set index, noncanonical data, forbidden private field, or bad measurement link rejects the record deterministically. It cannot change action selection.

**Provenance/digests:** v3 binds runtime/contract/spec/config/distribution/capability/engine identities through references. Search Measurement binds its decision-record ID and operational taxonomy. Neither stores local paths, hostnames, or hidden worlds.

**CI/package smokes:** cross-version schema/canonicalization, old-vector immutability, leakage negative fixtures, Core-only record import, docs/schema checks.

**Acceptance criteria:** record and identity schemas merge before executors/integration; v1/v2 remain unchanged; deterministic SearchDecision and Decision Record v3 bytes are canonical; successful fallback and operational timing are represented without v2-error abuse or leakage.

**Non-goals:** running algorithms, reading clocks, deadline isolation, Runtime composition, telemetry backend, or evaluation.

**Prerequisites:** Tasks 23-34 and MD-05/10/14 approval. **Blocks:** Tasks 36-42. **Safe review boundary:** normative/schema/canonical-record evolution is independent from Runtime behavior.

### Task 36 (N): Add `deterministic_benchmark`, `live_anytime`, and deadline isolation

**Purpose:** Compose the two fully specified kernels under deterministic and live semantics and implement the Maintainer-approved native-call isolation/deadline contract without contaminating Core with a clock.

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/application/search/executor.py` and `checkpoint.py`.
- Create: `packages/battlebelief-core/tests/application/search/{test_executor.py,test_checkpoint.py,test_deterministic_reproducibility.py}`.
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/clock.py` and `search_budget.py`.
- Create: `packages/battlebelief-runtime/tests/{test_clock.py,test_search_budget.py,test_live_anytime.py}`.
- Create under recommended MD-18 option C: `packages/battlebelief-runtime/src/battlebelief_runtime/search_worker/{__init__.py,protocol.py,client.py,server.py,lifecycle.py}` and `tests/search_worker/{test_protocol.py,test_client.py,test_lifecycle.py,test_equivalence.py}`. If the Maintainer selects A or B instead, revise these exact files/acceptance claims before Task 36 starts.
- Create: `tools/smoke_deterministic_search.py`.
- Modify: search-contract validation tests/examples only as needed to exercise the already accepted modes; do not change `schemas/manifests/search-contract.schema.json`. If implementation exposes an actual inconsistency, stop and raise a new Maintainer decision before a successor schema.
- Modify: Runtime/Core exports, schema tooling, package smoke, and `.github/workflows/pr.yml` for deterministic reproduction.
- Delete: none.

**Public types and APIs:** `SearchExecutor`, `DeterministicBenchmarkBudget`, `SearchCheckpoint`, `LiveAnytimeBudget`, `MonotonicClock`, `EngineExecutionMode`, and—under option C—`SearchWorkerClient`/`SearchWorkerFailure` are **[PUBLIC APIs]** in their owning package. Task-35 `SearchMeasurement`/`SearchTermination` are consumed unchanged. Core sees fixed work and an injected checkpoint/stop signal, not a clock or duration.

**Allowed imports:** Core executor imports Core only; Runtime budget/clock/worker imports Core executor/record protocols, the Task-27 adapter, and standard-library time/process/IPC primitives. Runtime does not import Lab, and Core never imports Runtime clock/worker code. The worker is the only live-hard-deadline process loading the native extension under option C.

**`deterministic_benchmark`:** exactly one thread; fixed configured transition work; separate named random streams for worlds, own actions, opponent actions, chance, and ties; no wall-clock branch; stable iteration and serialization order; identical environment/artifacts/config/inputs/seeds yield action-identical results and byte-identical canonical Decision Rows. Operational measurements may differ and are stored separately.

**`live_anytime`:** Runtime uses an injected monotonic clock and an explicit wall-time budget. Before native work it holds a safety-checked `heuristic_v0` incumbent. Core proposes replacements only at completed checkpoints; Runtime accepts one only after independent `ActionSafetyGate` validation. Under MD-18 A/C, potentially blocking native work runs in a killable worker, the parent owns the incumbent/deadline, and deadline expiry terminates the verified worker tree before returning the incumbent and applying the final safety check. Under B, the API is explicitly a soft deadline and can return only after the native call regains control; eligibility requires a bound maximum call-latency qualification. The mode is never a teacher-target source.

**Tests first:** deterministic repeated Task-35 Decision Record v3 byte vector across processes; random-stream separation; one-thread/exact-work; no Core clock; fake-clock deadline before start/mid-transition/between checkpoints/after completion; clock regression; native worker hangs/ignores cancellation; parent kills worker tree and returns incumbent under A/C; hard-deadline claim rejected under B; qualified max-call-latency mismatch under B; worker crash/partial/malformed IPC; deterministic in-process/worker equivalence under C; timing only in Search Measurement; no teacher target; complete counters.

**Implementation checklist:**

- [ ] Add failing deterministic two-process byte vectors and seed-domain/one-thread/exact-work tests.
- [ ] Obtain MD-18 approval and add fake-clock plus real killable-worker (or explicit soft-deadline) tests before promising timeout behavior.
- [ ] Implement Core checkpoints/fixed-work executor and Runtime monotonic controller with the approved worker/latency boundary.
- [ ] Populate Task-35 Search Measurement records and implement deterministic/worker-equivalence smokes.
- [ ] Run focused Core/Runtime suites, repeatability smoke, package smokes, and all repository gates.

**Failure/fallback:** invalid mode/config, attempted deterministic parallelism, clock regression, deadline, worker protocol/start/kill failure, checkpoint corruption, work mismatch, backend error, or unsafe candidate follows MD-14. Under A/C the parent returns the last safe incumbent only after regaining control/terminating the worker; under B a hung native call cannot truthfully guarantee deadline return. Every crash/timeout is counted.

**Provenance/digests:** deterministic record contains fixed-work/spec/seed identities. Live measurement additionally binds execution-mode/worker protocol/source/artifact or maximum-call-latency evidence, requested/effective duration, elapsed duration, completed work, termination/fallback, engine health, and incumbent source. PID/path/host/hidden worlds are excluded.

**CI/package smokes:** deterministic two-run Decision Record v3 byte comparison; fake-clock live smoke; worker hang/kill/process-tree cleanup and in-process equivalence on Ubuntu/Windows under A/C, or max-latency qualification under B; Core clock ban; one-thread; Runtime `[search]` cell.

**Acceptance criteria:** deterministic mode is action- and Decision-Record-byte reproducible. Under A/C, a deliberately hung native worker is terminated and the parent returns the last safety-checked incumbent within the approved outer tolerance; under B, every API/schema/document says soft deadline and no hard-return claim exists. Telemetry is complete; no live result is a teacher target.

**Non-goals:** Runtime battle-session integration, telemetry storage backend, multi-thread deterministic support, live action-quality guarantees, or evaluation.

**Prerequisites:** Tasks 23-35 and MD-10/12/14/18 approval. **Blocks:** Tasks 37-42. **Safe review boundary:** operating/deadline semantics and native isolation are proven before session/public composition.

### Task 37 (O): Integrate Runtime composition, sessions, telemetry, and the public Search API

**Purpose:** Make qualified search usable through Runtime while preserving request identity, safe submissions, the independent action-safety gate, and optional-extra behavior.

**Files:**

- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/composition/search.py`.
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/public_api/search.py`.
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/telemetry/search.py`.
- Create: `packages/battlebelief-runtime/tests/composition/test_search.py`, `tests/public_api/test_search.py`, `tests/telemetry/test_search.py`, and `tests/test_battle_session_search.py`.
- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/composition/battle_session.py`, `composition/battle_coordinator.py`, `testing/measurement_session.py`, and curated public exports.
- Modify: corresponding Runtime tests and smokes.
- Modify: `tools/check_architecture.py`, `tools/smoke_packages.py`, protocol/safety smokes, and `.github/workflows/pr.yml`.
- Modify: no Core record/identity model, record schema, or normative contract; Task 35 owns those merged inputs.
- Delete: none.

**Public types and APIs:** `SearchRuntimeConfig`, `SearchPolicyFactory`, `RuntimeSearchPolicy`, and `decide_with_search(...)` are **[PUBLIC RUNTIME API]**. A `RuntimeDecisionPolicy` consumes observed state, Task-35 request identity, and safe set; a compatibility adapter keeps `HeuristicPolicy` usable. Search summaries/fallbacks/records are imported unchanged from Task 35.

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

**Tests first:** no-extra import/call; qualified composition; each eligibility/fallback; artifact changes after check; stale safe set/request; unsafe/not-member search result; checkpoint and final safety gates; heuristic compatibility; live/oracle identities; Task-35 record/measurement integration without schema change; no hidden/private/exception/path/host data; worker/soft-deadline outcome propagation; BattleCoordinator reconnect/idempotence; MeasurementSession captures every outcome.

**Implementation checklist:**

- [ ] Add failing public API, no-extra, fallback, Task-35 record-consumption, deadline-mode, and leakage tests without modifying Core/schema contracts.
- [ ] Implement the state-aware policy compatibility boundary using merged Task-35 types.
- [ ] Implement artifact resolution, Core eligibility/search composition, checkpoint safety checks, and final safety recheck.
- [ ] Integrate BattleSession, BattleCoordinator, MeasurementSession, telemetry, public API, smokes, and CI.
- [ ] Run Protocol/Safety and base/`[search]` package smokes plus every repository gate; inspect canonical rows manually.

**Failure/fallback:** resolution, manifest, mapping, eligibility, model, algorithm, deadline, telemetry, or backend failures never bypass heuristic/safety. Telemetry-sink failure follows the accepted Runtime telemetry policy and cannot authorize an unsafe action. Failures and fallback successes are separately counted.

**Provenance/digests:** every decision resolves runtime/contract/environment/implementation, engine source/build/wheel/adapter, capability/evidence, ruleset, prior/distribution, search config, and arm spec digests. The record includes references, not local artifact paths.

**CI/package smokes:** base and `[search]` Runtime wheels; protocol/safety smokes with search absent/present; Gen-9 sentinel; Task-36 deterministic/deadline smoke; Task-35 record vectors; architecture confinement.

**Acceptance criteria:** public search can run only through verified qualification; all denied/error paths return `heuristic_v0`; final safety gate remains active; base install is unaffected; records are backward compatible and leakage-free.

**Non-goals:** Lab evaluation, calibration/evidence binding, changing Runtime version/phase, public Showdown networking, or status/strength claims.

**Prerequisites:** Tasks 23-36 and approved record/deadline decisions. **Blocks:** Tasks 38-42. **Safe review boundary:** Runtime integration changes no public Core contract or record schema because those are already merged.

### Task 38 (P): Implement the synthetic-only evaluation and statistical harness

**Purpose:** Implement and freeze all metric, technical-outcome, estimand, bootstrap, result-schema, and report behavior using synthetic golden data before registered battle outcomes exist.

**Files:**

- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/search/{__init__.py,session.py,technical_outcomes.py,metrics.py,statistics.py,report.py}`.
- Create: `packages/battlebelief-lab/tests/evaluation/search/{test_session.py,test_technical_outcomes.py,test_metrics.py,test_statistics.py,test_report.py,test_golden_vectors.py}`.
- Create: `packages/battlebelief-lab/tests/fixtures/evaluation/m2/{paired-outcomes.json,technical-outcomes.json,bootstrap-golden-vectors.json,report-golden.json}` with synthetic labels only.
- Create: `schemas/evaluation/m2-evaluation-result-v1.schema.json` and `m2-evaluation-report-v1.schema.json` **[NEW SCHEMAS v1]** plus synthetic valid/invalid examples after MD-17 approval.
- Create: `tools/run_m2_evaluation.py`, `tools/validate_m2_evaluation.py`, and `tools/smoke_m2_evaluation_harness.py`; the generic runner is exercised only with synthetic fixtures in this task.
- Modify: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/measurement_runner.py` only to depend on a general measured-session protocol while preserving existing clients.
- Modify: schema/docs/architecture/package-smoke tooling and CI for synthetic harness/golden validation.
- Modify: no registration, threshold, development-pool artifact, run binding, real raw result, or evidence report.
- Delete: none.

**Public types and APIs:** `MeasuredDecisionSession`, `TechnicalOutcomeTreatmentV1`, `BattleOutcomeWeightedV1`, `PairedMeanDifferenceV1`, `WeightedClusterBootstrapV1`, `DeploymentBudgetView`, `MechanismBudgetView`, `M2EvaluationResult`, and `M2EvaluationReport` are **[PUBLIC LAB API]**. IDs and semantics must match accepted owners; the implementation cannot redefine thresholds.

**Allowed imports:** Lab may import Core record/value types and approved Runtime public/testing protocols. Statistical code is pure over supplied rows/seeds. No Oracle, engine, development pool, or protected data is required by tests.

**Harness contract:** implement `battle_outcome_weighted_v1`, `paired_mean_difference_v1`, `weighted_cluster_bootstrap_v1`, `technical_outcomes_full_v1`, one-sided 95% interval handling, lower-bound comparison, and latency tie-break eligibility exactly from accepted contracts/registration references. Produce deployment and mechanism views with explicit denominators. Count all fallbacks/timeouts/crashes/invalid actions; never filter them to improve the metric.

**Tests first:** exact synthetic weighted outcome vectors; paired side/block/cluster handling; deterministic bootstrap seed/resample indices and golden quantiles; one-sided interval and exact 0.05 boundary; technical outcomes retained; missing/duplicate pair; zero/invalid weights; nonfinite data; deployment/mechanism denominators; latency cannot override primary failure; report schema/canonical bytes; measured-session compatibility; no real artifact path accepted in fixtures.

**Implementation checklist:**

- [ ] Obtain MD-17 approval and add failing metric/estimand/bootstrap/technical-outcome/schema golden vectors.
- [ ] Implement pure analyzer components and measured-session protocol with no real run inputs.
- [ ] Implement both budget views and deterministic report generation from synthetic rows.
- [ ] Add schema, golden-vector, package, and CI harness smokes.
- [ ] Run focused Lab/statistical tests twice, full gates, and audit that no real result or threshold change entered the PR.

**Failure/fallback:** malformed/incomplete pairs, missing clusters, invalid weights, unbound analysis ID, nonfinite estimates, or missing technical outcomes make the synthetic/result validation fail. Analyzer exceptions are not converted into favorable estimates.

**Provenance/digests:** result/report schemas reference registration, metric, estimand, analysis, technical-treatment, input-row, seed, analyzer-source, and canonicalizer digests. Golden fixtures are explicitly synthetic.

**CI/package smokes:** synthetic analyzer/report smoke; deterministic golden bootstrap; schema validation; existing MeasurementRunner clients; no network/engine/oracle dependency.

**Acceptance criteria:** `weighted_cluster_bootstrap_v1` and all dependent analysis/report code are merged with fixed golden vectors before real registered outcomes; the PR contains synthetic inputs only and changes no gate.

**Non-goals:** constructing development inputs, calibrating, binding, running registered battles, viewing real outcomes, or evidence/status claims.

**Prerequisites:** Tasks 23-37 and MD-17 approval. **Blocks:** Tasks 39-42. **Safe review boundary:** analysis code and schemas cannot be adapted after seeing registered outcomes.

### Task 39 (Q): Construct and seal concrete M2 development inputs

**Purpose:** Create the complete authorized Development-pool inputs required by the frozen M1.5 pool/schedule rules, without creating or opening protected pools.

**Files:**

- Create: `schemas/manifests/m2-development-pool-v1.schema.json` and `m2-development-schedule-v1.schema.json` **[NEW SCHEMAS v1]** with valid/invalid examples.
- Create after MD-19 approval: `registrations/gen9ou/development/m2-development-inputs-v1/{README.md,team-sources.json,hero-teams/*.txt,opponent-teams/*.txt,opponent-policies/*.json,team-clusters.json,pool-manifest.json,schedule.json,seed-families.json}`.
- Create: `packages/battlebelief-lab/src/battlebelief_lab/evaluation/development_inputs.py` and `tests/evaluation/test_development_inputs.py` for construction/closure validation using existing pool/schedule/seed modules.
- Create: `tools/validate_m2_development_inputs.py`.
- Modify: Lab exports, schema/docs/package-smoke tooling, and CI data validator.
- Modify: no Selection, Power Pilot, Release Holdout, frozen registration, Task-21 binding, analysis code, algorithm code, or outcome file.
- Delete: none; sealed input versions are immutable.

**Public types and APIs:** `DevelopmentInputManifest`, `DevelopmentPoolManifest`, `DevelopmentScheduleManifest`, and `validate_m2_development_inputs(...)` are **[PUBLIC LAB API]**. Existing team-cluster, matchup, schedule, side, and seed types remain authoritative where already implemented.

**Allowed imports:** Lab data construction may import existing Core sealed-team and Lab pool/schedule/seed modules. It does not import private Runtime adapters or execute battles/search.

**Construction requirements:** bind each hero/opponent team's source/license/content hash and legality/ruleset validation; bind every opponent-policy implementation/config/source digest; compute canonical exact-team clusters/near-duplicate rejection under the frozen rule ID; enumerate base matchups and schedule blocks; create alternating balanced p1/p2 assignments; derive all named seed families outcome-blind; bind development pool ID/version/digest and complete schedule digest. Inputs are selected and sealed before Task 41 outcomes.

**Tests first:** missing/duplicate/illegal team; missing source/license; secret/local path; duplicate exact-team cluster across partitions; unbound opponent policy; absent hero/opponent/policy; unbalanced sides; schedule row/seed collision; wrong frozen construction/cluster/side/schedule rule ID; unstable ordering/digest; protected-pool path/name; mutation changes digest; full closure/reproduction from source bytes.

**Implementation checklist:**

- [ ] Obtain MD-19 approval for source/license, selection procedure, sizes, policies, and development-only access.
- [ ] Add failing schema/closure/cluster/schedule/seed/protected-pool tests.
- [ ] Materialize reviewed teams/policies and generate cluster, pool, schedule, and seed artifacts mechanically.
- [ ] Seal canonical digests and reproduce the complete input set from approved source bytes.
- [ ] Run legality/data/schema/frozen-rule/full gates and audit that protected pools remain absent/unopened.

**Failure/fallback:** any missing provenance, illegality, duplicate/contamination, unbound policy, schedule imbalance, seed collision, or digest mismatch prevents sealing. No input is replaced after outcomes in the same version.

**Provenance/digests:** source/license, team/policy bytes, ruleset/legality tool, clusters, pool, matchups, schedule blocks/rows, side assignments, seed families, construction code, and schema digests close transitively.

**CI/package smokes:** data-only development-input closure and deterministic regeneration; no battle run; explicit assertion that Selection/Power Pilot/Release Holdout artifacts do not exist or remain unopened under registered state.

**Acceptance criteria:** concrete hero teams, opponent teams/policies, clusters, pool manifest, all schedule rows/blocks/sides, and seed families are sealed and digest-resolvable under frozen rules; no protected pool is created/opened.

**Non-goals:** closed-world prior, analysis changes, calibration, bindings, battle execution, result viewing, or strength claims.

**Prerequisites:** Tasks 23-38 and MD-19 approval. **Blocks:** Tasks 40-42. **Safe review boundary:** evaluation inputs are selected and immutable before run bindings and outcomes.

### Task 40 (R): Close implementation/run bindings and calibration evidence

**Purpose:** Make every evaluation-relevant byte and environment fact resolvable before a registered run starts.

**Files:**

- Create after MD-13 approval: `schemas/manifests/evaluation-arm-binding-v5.schema.json` and `evaluation-run-binding-v5.schema.json` **[NEW SCHEMAS v5]**; v4 cannot represent a real development run because it fixes `run_purpose` to `synthetic_acceptance`.
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
- search algorithm/accepted contract/frozen execution spec/Task-32 algorithm specifications/config/work point/mode;
- Task-35 identity/record/measurement schemas and Task-36 execution-isolation/worker-or-latency evidence;
- environment OS/architecture/Python/Node/Rust/build-tool identities as applicable;
- Task-39 hero/opponent teams, opponent policies, clusters, development-pool/schedule/side/seed bindings;
- registration digest and Task-38 metric/estimand/bootstrap/technical-outcome/analyzer/report source and golden-vector digests;
- fallback/timeout/crash taxonomy version and telemetry/record schema versions.

Calibration chooses among only the registered determinization work grid `64/128/256/512` and applies Task-32's precommitted DUCT work-matching procedure. It does not tune worlds, depth, algorithm semantics, metric threshold, or any Task-32 configuration field. Calibration inputs, outcome-blind selection rule, and complete outputs are bound before Task 41.

**Tests first:** complete valid closure; one missing/unknown/mismatched digest at every edge; wrong engine/oracle/ruleset/prior/spec/record/worker-or-latency/analyzer/development-input/environment; circular/unresolvable ref; path/host; Task-21 immutable bytes; v4 stays synthetic-only; v5 development closure; calibration rejects off-grid or Task-32 config change; calibration cannot use registered outcomes; unopened pool rejected; v3 evidence compatibility; repeated canonical bytes.

**Implementation checklist:**

- [ ] Obtain MD-13/16 approval; add failing schema, closure, immutable-old-artifact, and outcome-blind calibration tests.
- [ ] Implement content-addressed binding resolution and complete M2 closure validation.
- [ ] Implement calibration evidence restricted to registered choices and the already precommitted Task-32 DUCT configuration/work-matching rule.
- [ ] Generate bindings only from real verified inputs and validate every reference from a clean checkout.
- [ ] Run focused schema/binding/calibration tests, frozen-artifact checks, package smokes, and all repository gates.

**Failure/fallback:** incomplete closure blocks run creation—there is no fallback run with partial provenance. Calibration crash/timeout/failure remains in calibration evidence and cannot be dropped. Artifact retrieval never follows an unverified mutable URL.

**CI/package smokes:** schema/canonicalization and closure validation; synthetic M2 binding smoke; immutable Task-21 artifact test; `uv lock --check`; no network needed to verify local retained artifacts.

**Acceptance criteria:** a run binding resolves every required digest to verified bytes and is rejected on any mismatch; calibration is reproducible and restricted to registered values; no frozen artifact changes.

**Non-goals:** running registered comparisons, altering arm/metric/gate values, selecting favorable results after evaluation, opening pools, version/phase change, or strength claims.

**Prerequisites:** Tasks 23-39 and MD-13/16/19 approval. **Blocks:** Tasks 41-42. **Safe review boundary:** provenance and calibration close only merged code/specs/inputs before registered outcomes exist.

### Task 41 (S): Execute the data-only registered development run

**Purpose:** Execute the two frozen comparisons with already merged Runtime/analyzer code and closed bindings, allowing only immutable run inputs, raw outcomes, measurements, and mechanically generated reports in the PR.

**Files:**

- Create: `artifacts/gen9ou/m2/evaluation/development-run-v1/{run-index.json,raw-battles.jsonl,decision-records.jsonl,search-measurements.jsonl,technical-outcomes.jsonl,evaluation-result.json,evaluation-report.json}`.
- Modify: `artifacts/gen9ou/m2/evaluation/README.md` to link the closed Task-40 run binding and immutable output digests.
- Modify: no Python, schema, contract, registration, algorithm specification, threshold, analyzer/golden vector, Runtime code, pool/schedule/seed input, binding/calibration artifact, or Task-21 file.
- Delete: none; failed/aborted runs remain retained under provenance rules.

**Public types and APIs:** none. The PR invokes Task-38 `run_m2_evaluation.py`/public analyzer and Task-37 Runtime APIs without changing them.

**Allowed imports:** none are added. The merged Lab runner may import approved Core/Runtime APIs and its own oracle/binding modules; the data-only diff creates no import edge.

**Frozen comparisons:**

1. `heuristic_v0` versus `determinization_search_v0`.
2. `determinization_search_v0` versus `information_set_duct_closed_world_v0`.

For both, preserve `battle_outcome_weighted_v1`, one-sided 95% confidence, minimum effect `0.05`, and Go only when the lower confidence bound is at least `0.05`. `end_to_end_latency_ms_v1` is tie-break-only. Do not restate these as a new authority in generated prose; reference the frozen registration and record its digest.

**Run procedure:** validate Task-40 binding closure and Task-39 development-pool authorization before starting; use the already sealed seeds/pairings/sides; run through the local oracle and public Runtime composition; retain every decision and battle; compute paired/weighted metrics exclusively through the merged Task-38 analyzer; produce deployment-budget (all fallbacks/timeouts/crashes as deployed) and mechanism-budget (qualified completed mechanism with disclosed denominators) views; make the registered inference once; render raw counts, rates, confidence bounds, effect, latency tie-break, artifact identities, and failure taxonomy.

Protected selection, power-pilot, and release-holdout pools are rejected by the runner unless a later independent authorization and binding explicitly opens them. This task does not create them.

**Tests and validation first:** Task-40 binding closure; exact Task-39 development pool/schedule/seed authorization; frozen registration/arm/spec/gate digests; merged Task-38 analyzer/golden digests; no protected pool; distinct-player leakage smoke; resume/idempotence dry run; raw-output destination empty; generated report reproduces byte-identically from retained rows; all failures/timeouts/crashes remain in denominators; diff allowlist is data-only.

**Implementation checklist:**

- [ ] Obtain explicit development-run authorization and validate every closed input/code/spec/analyzer digest before starting.
- [ ] Execute the precommitted schedule through the merged local oracle and Runtime; retain every battle/decision/measurement/technical outcome.
- [ ] Generate both budget views, registered inference, and report only with the merged Task-38 analyzer.
- [ ] Rebuild result/report from immutable raw rows and byte-compare canonical outputs.
- [ ] Run evidence/schema/full gates and enforce a data-only diff plus protected-pool access audit.

**Failure/fallback:** individual decision failures use the registered Runtime fallback and remain in the battle. Battle/oracle/backend crashes and timeouts are classified and counted; an invalid run is reported invalid, not removed. Binding, leakage, pool, or registration mismatch aborts before evaluation and produces no gate result.

**Provenance/digests:** each row/run resolves Task-40 closure plus Task-39 pairing/seeds/teams/policies/pool/schedule, oracle session, Decision Record/Search Measurement, outcome, fallback/timeout/crash, Task-38 analyzer, and report-renderer digests. No secret, host, path, or hidden world appears in public decision evidence.

**CI/package smokes:** validate retained authorized artifacts and raw-to-report reproduction; rerun existing synthetic analyzer smoke and oracle/search/qualification/prior prerequisites. CI does not rerun the full registered schedule automatically.

**Acceptance criteria:** both comparisons are executed unchanged on an authorized development pool; all outcomes/failures are retained; reports show both budget views and the registered inference; no protected pool is touched; evidence is reproducible from bindings and raw rows.

**Non-goals:** any code/schema/spec/analyzer/golden/pool/schedule/binding/calibration/threshold change, selection/power/release evaluation, ladder play, strength/parity/MVP claims, or Runtime phase/version change.

**Prerequisites:** Tasks 23-40, real exact capability evidence, full binding closure, and explicit Maintainer authorization. **Blocks:** Task 42. **Safe review boundary:** real outcomes arrive in a data-only PR that cannot redefine analyzer, implementation, inputs, qualification, or gates.

### Task 42 (T): Review M2 acceptance evidence and propose any status transition

**Purpose:** Decide whether the implemented prototype meets the M2 milestone using real retained evidence, without converting development results into a strength claim.

**Files:**

- Create: `docs/operations/m2-engine-qualified-search-prototype-evidence.md`, following the repository's existing evidence/operations location and containing digest references rather than duplicated normative thresholds.
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
- [ ] Build the evidence index/report exclusively from verified Task-41 artifacts and full gate results.
- [ ] Review exact capability/environment scope, failures, protected-pool state, and all unmade claims.
- [ ] Request explicit Maintainer acceptance and exact version/phase/documentation authority before any status edit.
- [ ] Run complete local and PR gates, inspect the entire diff, and record every limitation or unexecuted external check.

**Failure/fallback:** insufficient or contradictory evidence leaves the project at its current status. Record the missing evidence or Maintainer decision; do not edit results, loosen a gate, broaden an exact claim, or infer qualification.

**CI/package smokes:** full repository gates and evidence closure. Any GitHub `pr-gate` must pass on the actual PR before merge; local checks are not a substitute.

**Acceptance criteria:** the evidence report is digest-resolved and scope-accurate; the Maintainer makes an explicit M2 acceptance/status/version decision; no strength claim or protected-pool access occurs.

**Non-goals:** new implementation, new evaluation, gate changes, M3 work, or automatic release.

**Prerequisites:** Task 41 and all retained evidence. **Blocks:** any claim that M2 is complete and any subsequent milestone transition. **Safe review boundary:** acceptance/status is not bundled with analyzer implementation or result generation.

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
| 25 | Runtime artifact/private-probe/sentinel tests; no public mapper export; base and `[search]` isolated installs; Gen-9 sentinel |
| 26 | capability/schema/canonicalization/v1 compatibility; Core transition/random port fake conformance; generic distribution identity |
| 27 | Runtime state/action/view/joint-transition mapping; safe-root preservation; real Core-port conformance; import confinement |
| 28 | corpus/classifier/evidence-builder schemas and synthetic/golden differential harness; no real exact claim |
| 29 | data-only real matrix; frozen Task-28 digests; raw-to-evidence reproduction; zero unclassified/affecting divergence for exact |
| 30 | closed-world filtering, normalization, sampler, generic-identity conversion, provenance, and leakage tests |
| 31 | Core eligibility/fallback truth table over generic identity; no backend call on denial; architecture negatives |
| 32 | both algorithm-spec schemas/completeness/canonicalization; frozen-value cross-validation; no semantic defaults |
| 33 | determinization conformance to frozen plus Task-32 specs; allocation/remainder/opponent/chance/value/backup/depth/work vectors |
| 34 | seven Search-v0 invariants plus Task-32 DUCT config/work/backup golden vectors and adversarial joint-argmax tests |
| 35 | request/record/measurement schemas, migrations, canonical bytes, v1/v2 immutability, and leakage tests |
| 36 | deterministic Decision Record byte comparison; seed separation; fake-clock plus worker hang/kill or soft-deadline qualification |
| 37 | no-extra/extra Runtime composition; BattleSession/Coordinator/MeasurementSession; Task-35 records; Protocol/Safety smokes |
| 38 | synthetic metric/estimand/technical-outcome/bootstrap/report golden vectors and schemas; no real outcomes |
| 39 | team/policy/source/license/cluster/pool/schedule/side/seed closure; protected-pool absence; deterministic regeneration |
| 40 | arm/run/calibration binding closure across specs, analyzer, development inputs, isolation evidence, and immutable Task-21 artifacts |
| 41 | data-only run allowlist; pre-run closure; complete outcome retention; raw-to-report reproduction; protected-pool access audit |
| 42 | full evidence closure, claim-language review, status/version approval, and complete repository/PR gates |

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
- differential corpus/classifier synthetic golden smoke, followed by a separately authorized data-only qualification validator;
- deterministic benchmark two-run Decision Record v3 byte comparison;
- native worker hang/kill/process-tree cleanup smoke under a hard-deadline option, or explicit soft-deadline/max-call-latency qualification;
- synthetic `weighted_cluster_bootstrap_v1`/technical-outcome golden-vector smoke;
- M2 development-input pool/schedule/seed closure and protected-pool absence smoke.

Full validation must inspect retained artifacts and the complete diff for generated binaries, secrets, local state, absolute paths, hostnames, unlicensed data, unexpected dependency/lock changes, frozen registration/binding changes, premature M2 status, and parity/strength/release claims.

## 10. Official primary sources used for Task-23 research

These links identify the inspected snapshot. They do not select BattleBelief's future pins.

### Pokémon Showdown

- [Package metadata at the observed revision](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/package.json)
- [Official package lock at the observed revision](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/package-lock.json)
- [Official MIT license](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/LICENSE)
- [Official launcher with its global-`fetch` feature test and Node-22 message](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/pokemon-showdown)
- [Official server entry point with the same feature test/message](https://github.com/smogon/pokemon-showdown/blob/6a1836dd71c0718e923206f3d089e61074410868/server/index.ts)
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
- publishes no Runtime state/action mapper before the Core port and generic distribution identity merge;
- treats Pokémon Showdown as authoritative and `poke-engine` as non-authoritative and artifact-qualified;
- distinguishes Showdown's declared Node >=16 metadata, actual global-`fetch` feature test, Node-22 message, and Node-18 CI coverage;
- requires exact capability evidence and rejects unknown, unsupported, bounded approximation, mismatch, and backend failure;
- freezes differential code/classifier/corpus before a separate data-only qualification run;
- treats the closed-world distribution as evaluation-only and never as M3 belief;
- reproduces every frozen determinization value without modification;
- binds all otherwise unspecified determinization and DUCT semantics outcome-blind before either implementation;
- maps every Search-v0 invariant to an adversarial test;
- versions record/canonical-byte semantics before modes and Runtime integration, and separates deterministic rows from live measurement;
- makes hard native-call deadlines depend on killable isolation, or explicitly narrows the API to a qualified soft deadline;
- seals concrete Development teams, policies, clusters, pool, schedule, sides, and seeds before bindings and outcomes;
- merges the synthetic-only statistical analyzer and golden vectors before a data-only registered run;
- retains all fallbacks, timeouts, crashes, invalid actions, and failed runs in evaluation accounting;
- keeps protected pools closed and makes no strength, parity, ladder, MVP, or release claim;
- presents every discovered inconsistency or proposed improvement as a Maintainer decision rather than an implicit change;
- binds real future revisions and digests only after they have been selected and generated, never through plausible placeholders.
