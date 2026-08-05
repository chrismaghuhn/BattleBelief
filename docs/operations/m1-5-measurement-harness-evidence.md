---
document_id: evidence-m1-5-measurement-harness
title: M1.5 Measurement Harness and Baseline Registration Evidence
document_type: audit
status: accepted
normative: false
version: 1
applies_to:
  - evaluation
  - gen9ou
effective_from: 2026-08-05
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-05
---

# M1.5 Measurement Harness and Baseline Registration Evidence

This non-normative audit records measured acceptance evidence for M1.5. It
does not define metrics, estimands, statistical procedures, pool meaning,
Safety rules, package boundaries, or M5 gates. Those definitions remain in the
normative owners linked from the [documentation index](../README.md).

## Validated source and frozen artifacts

Task 21 was merged before this audit was started. The validated source is the
Task-21 merge commit, not this later documentation commit.

| Artifact or check | Measured value |
|---|---|
| `validated_source_commit` | [`eeb608e6d2f897665b6d01c97e56010ff7f73d56`](https://github.com/chrismaghuhn/BattleBelief/commit/eeb608e6d2f897665b6d01c97e56010ff7f73d56) |
| `evidence_execution_commit` | [`11bb983bb39f0e48a9e6b27ea2771e7b3b39e0e6`](https://github.com/chrismaghuhn/BattleBelief/commit/11bb983bb39f0e48a9e6b27ea2771e7b3b39e0e6) |
| Task-21 PR workflow (`pull_request`, PR #30) | [`31003761078`](https://github.com/chrismaghuhn/BattleBelief/actions/runs/31003761078) |
| Task-21 main validation workflow (`push`, validated source) | [`31005007421`](https://github.com/chrismaghuhn/BattleBelief/actions/runs/31005007421) |
| Task-21 CodeQL workflow (`push`, validated source) | [`31005007415`](https://github.com/chrismaghuhn/BattleBelief/actions/runs/31005007415) |
| Task-22 PR workflow (`pull_request`, evidence execution commit) | [`31006644403`](https://github.com/chrismaghuhn/BattleBelief/actions/runs/31006644403) |
| Registration | [`m1-5-core-comparisons-v1`](https://github.com/chrismaghuhn/BattleBelief/blob/eeb608e6d2f897665b6d01c97e56010ff7f73d56/registrations/gen9ou/m1-5-core-comparisons-v1.json) |
| Registration digest | `sha256:c05cbeb123bcc797d325807a739402266ccdaf0c8e4de9691764af012a3ad03b` |
| Heuristic implementation binding | [`heuristic_v0-implementation-v2`](https://github.com/chrismaghuhn/BattleBelief/blob/eeb608e6d2f897665b6d01c97e56010ff7f73d56/registrations/gen9ou/bindings/heuristic_v0-implementation-v2.json) |
| Heuristic implementation-binding digest | `sha256:56db0a62df44fe708397c5e55f3cff1f17b599f6067bf9ec54846aba4b90ec78` |
| Synthetic fixture manifest digest | `sha256:10c90ba770cb6b6b4e8c631727463c4356ae20169db796d6f47ed05e4bcb7ce8` |
| Calibration Specification digest | `sha256:d071164c46fc88e76dd7a5481bcd39757bb6c28b0d101020a53793da7874bcd8` |
| Calibration Evidence | Not present; deferred to the later M2 implementation binding |

The two row-specific synthetic Acceptance Run Bindings are:

| Binding | Digest | Schedule row | Seed-family digest |
|---|---|---|---|
| [`heuristic_v0-m15-synthetic-run-p1`](https://github.com/chrismaghuhn/BattleBelief/blob/eeb608e6d2f897665b6d01c97e56010ff7f73d56/registrations/gen9ou/bindings/heuristic_v0-m15-synthetic-run-p1.json) | `sha256:7a548f890527f9e03cf9b4b2279aa97f3dcdb52eb10bb9c101662ea753fef30c` | `sha256:998ad3d52772d251c89dd65ae07b5aae73078b0570e80cefb68eb09af17f5e3c` | `sha256:d179b65a12dda5442e375b0fb3475d2738f8795d06bc07429819b8ad8e35814b` |
| [`heuristic_v0-m15-synthetic-run-p2`](https://github.com/chrismaghuhn/BattleBelief/blob/eeb608e6d2f897665b6d01c97e56010ff7f73d56/registrations/gen9ou/bindings/heuristic_v0-m15-synthetic-run-p2.json) | `sha256:2be21c771b7cfce0cc601f056e9ff98b324c544aa7f4acdf8b34af0105d0b9d1` | `sha256:078f2ea940144047f6b079882b5b6cc5b3c41088f05f4ad0599507cd2c6b24af` | `sha256:da534c7a2f1ae6b7861db21224b5a360a2669b9690a1181d6c394f949ed26c4e` |

The registration is frozen, and both Run Bindings resolve to the same frozen
registration and the same heuristic Implementation Binding. Selection,
Power Pilot, and Release Holdout access are all `unopened`; only the
Development scope is available for this synthetic acceptance check.

```yaml
pool_access:
  development: available
  selection: unopened
  power_pilot: unopened
  release_holdout: unopened
```

## Reproducibility and Decision Records

The acceptance test runs each of the two row-specific bindings twice through
the approved Runtime `MeasurementSession` seam and the Lab
`MeasurementRunner`. That is four offline synthetic sessions in total, with
one submitted Decision Record per session. The test compares:

- the resolved Run Context digest;
- the `MeasurementRunResult` projection;
- each canonical Decision-Record envelope; and
- the JSONL bytes emitted by the UTF-8 sink.

All four sessions completed with `trace_status: emitted`; the two executions
for each row produced byte-identical Decision Records and byte-identical
JSONL output. The reproducibility command was:

```powershell
uv run pytest tests/tooling/test_m15_evidence.py -v
```

The same test resolves the registration, Implementation Binding, Run Binding,
Schedule Row, SeedFamily, Run Scope, Run Context, and Measurement Runner. It
therefore checks the complete provenance chain rather than comparing isolated
placeholder digests.

The Decision-Record schemas use the existing JCS-v1 byte profile. The
canonicalization vector file is
[`decision-record-test-vectors.json`](../../schemas/canonicalization/decision-record-test-vectors.json);
it contains 2 vectors and has file digest
`sha256:7de7dc105aca46f0c0992dee5694d5268613155f0655d61f9953066ac5294735`.
The registered machine-readable schema IDs include Decision Record v2,
Measurement Run v1, Measurement Run Result v1, Evaluation Run Binding v4,
Calibration Specification v4, Calibration State Manifest v2, and Calibration
Environment Manifest v2.

The JSONL byte contract is checked by the Runtime integration tests and the
Task-22 acceptance test: each line is exactly canonical record bytes followed
by `b"\n"`, encoded as UTF-8, with no platform-dependent `\r\n`. The sink
requires a complete write, flushes after each emit, and exposes explicit
flush/close lifecycle methods. The runner owns lifecycle calls for the
MeasurementSession; the injected sink is not closed by the Core domain.

## Determinism, budgets, and pools

The existing Task-20 evaluation tests and the Task-22 end-to-end test verify
that seed-family, schedule-row, Run Context, and budget identities are
reproducible from their canonical inputs. The relevant commands are:

```powershell
uv run pytest packages/battlebelief-lab/tests/evaluation/test_seed_families.py packages/battlebelief-lab/tests/evaluation/test_schedule.py packages/battlebelief-lab/tests/evaluation/test_pool_partitioning.py packages/battlebelief-lab/tests/evaluation/test_team_clustering.py -q
uv run pytest tests/tooling/test_m15_registration_artifacts.py -q
```

The generic pool-partitioning and team-clustering contract tests are green.
The Task-21 synthetic team fixtures are identity fixtures rather than complete
team objects; this audit makes no concrete near-duplicate classification claim
for them. No concrete Selection, Power Pilot, or Release Holdout pool is
created or opened by this audit. The registered budget mode is
`calibrated_grid`: `per_world_work` uses the frozen grid `[64, 128, 256, 512]`
and 16 worlds, while deployment limits are recorded in the registration.
Measured Calibration Evidence is intentionally deferred until the applicable
M2 Search implementation exists; no quality or battle result was used to
select a work value here.

## Leakage and scope checks

The Decision-Record and public-projection tests use synthetic identifiers and
assert that credential-like values, private opponent data, absolute local
paths, sampled hidden state, and raw Pokémon identifiers do not occur in
public record bytes. No real credentials or live public account were used.

The exact negative scope command was:

```powershell
rg -n "poke_engine|poke-engine|DUCT|MCTS|BeliefState|duckdb|pyarrow|torch|onnx|/search" packages tools tests .github
```

It found 13 matching lines: 6 are explicit prohibited-dependency declarations
in `tools/check_architecture.py`; 6 are schema and registration tests or test
fixtures that exercise the deferred Search-spec contract; and 1 is the
negative challenge-command test that excludes `/search` and related commands.
These hits are contract guards and test references, not implementations. No
Search, Belief, Oracle, engine, replay, dataset-ingestion, training, or model
implementation is present in the searched executable repository paths.

## Measured validation matrix

All numbers below were measured from the Task-22 branch after the evidence
test was added, from the validated source lineage above, on Windows with
CPython 3.14.5 unless a GitHub matrix entry is stated. The denominator for the
full suite is the repository's collected pytest test set.

| Command or workflow | Result |
|---|---|
| `uv run pytest -q` | 1,065 tests passed |
| `uv run pytest tests/tooling/test_m15_evidence.py -v` | 5 tests passed |
| `uv run pytest packages/battlebelief-lab/tests/evaluation/test_seed_families.py packages/battlebelief-lab/tests/evaluation/test_schedule.py packages/battlebelief-lab/tests/evaluation/test_pool_partitioning.py packages/battlebelief-lab/tests/evaluation/test_team_clustering.py -q` | 17 tests passed |
| `uv run pytest tests/tooling/test_m15_registration_artifacts.py -q` | 27 tests passed |
| `uv run pytest tests/smokes/test_protocol_smoke.py -v` | 2 tests passed |
| `uv run pytest tests/smokes/test_safety_smoke.py -v` | 29 tests passed |
| `uv run ruff format --check .` | exit code 0; 162 files already formatted |
| `uv run ruff check .` | exit code 0; no lint errors |
| `uv run mypy` | exit code 0; no type errors |
| `uv run python tools/check_architecture.py` | exit code 0 |
| `uv run python tools/check_docs.py` | exit code 0 |
| `uv run python tools/check_schemas.py` | exit code 0 |
| `uv run python tools/check_versions.py` | exit code 0 |
| `uv run python tools/validate_m15_registration.py` | exit code 0 |
| `uv run python tools/smoke_packages.py` | exit code 0; isolated package smokes passed |
| `uv lock --check` | exit code 0; lockfile consistent |
| `git diff --check` | exit code 0; no whitespace errors |
| GitHub quality matrix | Python 3.12, 3.13, and 3.14 successful |
| GitHub package matrix | Ubuntu and Windows successful |
| GitHub protocol/safety and `pr-gate` | successful |

The full local and GitHub checks establish repository and synthetic acceptance
health only. They do not establish observed live measurement coverage, battle
strength, engine parity, ladder readiness, release readiness, or MVP status.

## Status

M1.5 Measurement Harness and Baseline Registration complete.

Next milestone: M2 Engine-qualified Search Prototype.

Runtime remains version `0.2.0`, phase `M1`. Observed live measurement coverage: not established. No strength, parity, release, or MVP claim is made.
