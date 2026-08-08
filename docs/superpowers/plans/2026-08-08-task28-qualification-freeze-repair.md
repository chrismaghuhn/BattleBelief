---
document_id: plan-task-28-qualification-freeze-repair
title: Task 28 Qualification Freeze Repair Implementation Plan
document_type: roadmap
status: proposed
normative: false
version: 1
applies_to:
  - task-28
  - task-29
effective_from: 2026-08-08
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-08
---

# Task-28 Qualification Freeze Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Freeze the real Task-29 execution, provenance, evidence, corpus, and CLI path after the Task-27 observation and Task-24 scripted-Oracle predecessors merge.

**Architecture:** A Lab-owned binder consumes only public Task-24 and Task-27 APIs and maps them onto Lab canonical observations. Corpus-v1 holds closed backend inputs that agree with the declared mechanics fixture. A qualification run-binding closes over execution identities; the CLI writes sanitized result records, result index, report, and evidence. Task-28 tests use doubles and golden documents only.

**Tech Stack:** Python asyncio, dataclasses, JSON Schema Draft 2020-12, RFC8785/JCS, BattleBelief Lab/Core/Runtime public APIs, pytest, ruff, mypy.

---

### Task 1: Add closed execution and run-binding schemas

**Files:**

- Modify: schemas/evaluation/differential-fixture.schema.json
- Modify: schemas/evaluation/differential-corpus.schema.json
- Create: schemas/evaluation/differential-run-binding.schema.json
- Modify: schemas/evaluation/differential-result.schema.json
- Modify: schemas/evaluation/capability-qualification.schema.json
- Modify: schemas/examples/differential-fixture.example.json
- Create: schemas/examples/differential-run-binding.example.json
- Create: schemas/examples/invalid/differential-run-binding.invalid.json
- Modify: tools/check_schemas.py
- Test: packages/battlebelief-lab/tests/differential/test_corpus.py
- Test: tests/tooling/test_schema_checker_robustness.py

- [ ] **Step 1: Write failing schema and corpus tests**

~~~python
def test_fixture_requires_closed_execution_binding() -> None:
    document = _valid_fixture_document()
    document.pop("execution")
    with pytest.raises(CorpusValidationError, match="execution"):
        DifferentialFixture.from_document(document)


def test_run_binding_requires_environment_specific_artifacts() -> None:
    binding = _valid_run_binding()
    binding["environment_cells"][1]["engine"]["wheel_digest"] = binding["environment_cells"][0]["engine"]["wheel_digest"]
    assert _schema_errors("differential-run-binding", binding)
~~~

- [ ] **Step 2: Run red tests**

Run: uv run pytest packages/battlebelief-lab/tests/differential/test_corpus.py tests/tooling/test_schema_checker_robustness.py -q

Expected: a fixture without execution is accepted and the run-binding schema is absent.

- [ ] **Step 3: Define execution and qualification closure**

Add execution to every fixture with exact closed subdocuments:

~~~json
{
  "oracle_script": {"script_version": 2, "document": {}},
  "runtime_root": {
    "observed_state": {},
    "safe_submissions": {},
    "complete_world": {},
    "root_player": "p1"
  },
  "joint_action_binding": {"p1": {}, "p2": {}},
  "observation_projection": {"fields": ["hp", "status"]}
}
~~~

The run-binding schema closes over binding ID/digest, corpus/index digest, ruleset/catalog/canonicalization identities, runner/classifier identities, Oracle source/build identities, and a sorted environment-cell list. Every cell carries its own environment, engine build, and wheel digest. Reject paths, hostnames, noncanonical IDs, unknown fields, and mismatched fixture IDs.

- [ ] **Step 4: Run green schema and vector checks twice**

Run: uv run python tools/check_schemas.py; uv run pytest packages/battlebelief-lab/tests/differential/test_corpus.py -q; uv run python tools/check_schemas.py

Expected: both schema passes are byte-identical and focused corpus tests pass.

- [ ] **Step 5: Commit**

~~~powershell
git add schemas packages/battlebelief-lab/tests/differential/test_corpus.py tests/tooling tools/check_schemas.py
git commit -m "feat(lab): bind differential execution inputs"
~~~

### Task 2: Implement the public-API execution binder

**Files:**

- Create: packages/battlebelief-lab/src/battlebelief_lab/differential/binder.py
- Modify: packages/battlebelief-lab/src/battlebelief_lab/differential/__init__.py
- Modify: packages/battlebelief-lab/src/battlebelief_lab/differential/runner.py
- Create: packages/battlebelief-lab/tests/differential/test_binder.py
- Modify: packages/battlebelief-lab/tests/differential/test_runner.py

- [ ] **Step 1: Write failing double-only binder tests**

~~~python
async def test_binder_calls_public_oracle_and_runtime_once_per_fixture() -> None:
    oracle = FakeShowdownOracleSession(_oracle_result())
    runtime = FakePokeEngineTransitionModel(_runtime_outcome())
    binder = ShowdownPokeEngineExecutionBinder(oracle=oracle, runtime=runtime)
    execution = await binder.execute(_fixture())
    assert oracle.script_calls == 1
    assert runtime.transition_calls == 1
    assert execution.oracle.observation.to_dict()["hp"] == execution.engine.observation.to_dict()["hp"]


async def test_binder_rejects_private_or_undeclared_projection_fields() -> None:
    with pytest.raises(BindingError, match="declared mechanics fields"):
        await _binder().execute(_fixture_with_projection("native_state"))
~~~

- [ ] **Step 2: Run red tests**

Run: uv run pytest packages/battlebelief-lab/tests/differential/test_binder.py -q

Expected: collection fails because ShowdownPokeEngineExecutionBinder is absent.

- [ ] **Step 3: Implement binder protocols and projection**

~~~python
class ShowdownPokeEngineExecutionBinder:
    def __init__(self, *, oracle: ShowdownOracleSession, runtime: PokeEngineTransitionModel) -> None: ...

    async def execute(self, fixture: DifferentialFixture) -> BoundFixtureExecution: ...
~~~

Call only ShowdownOracleSession.run_script, PokeEngineTransitionModel.safe_submissions_from_document, prepare_battle_root, legal_actions, transition, is_terminal, terminal_value, and mechanics_observation. Convert public outputs into Lab CanonicalMechanicsObservation. Never inspect _opaque, native state, or private exceptions. Map chance fields only from complete Oracle controlled-chance output and Runtime TransitionOutcome; fail closed if a declared field is unavailable.

- [ ] **Step 4: Integrate with DifferentialRunner**

Add async run_bound_fixture that accepts a binder result, calls the existing declared-field comparison/classifier, and emits FixtureResult. Preserve injected callable run_fixture for existing synthetic tests.

- [ ] **Step 5: Run focused checks**

Run: uv run pytest packages/battlebelief-lab/tests/differential/test_binder.py packages/battlebelief-lab/tests/differential/test_runner.py -q; uv run python tools/check_architecture.py

Expected: all pass; import tests prove Runtime does not import Lab and the binder imports no private Runtime symbol.

- [ ] **Step 6: Commit**

~~~powershell
git add packages/battlebelief-lab/src/battlebelief_lab/differential packages/battlebelief-lab/tests/differential
git commit -m "feat(lab): bind public oracle and runtime execution"
~~~

### Task 3: Make qualification evidence binding-based and per-cell

**Files:**

- Modify: packages/battlebelief-lab/src/battlebelief_lab/differential/evidence.py
- Modify: packages/battlebelief-lab/tests/differential/test_evidence.py
- Modify: schemas/evaluation/capability-qualification.schema.json
- Modify: schemas/examples/capability-qualification.example.json
- Modify: schemas/examples/invalid/capability-qualification.invalid.json

- [ ] **Step 1: Write failing multi-environment and positive-golden tests**

~~~python
def test_complete_real_binding_with_distinct_cell_artifacts_is_exact_eligible() -> None:
    evidence = CapabilityQualificationEvidence.assess(
        expectation=_expectation_for_cells("cp312", "cp313", "cp314"),
        results=_completed_results_for_distinct_cells(),
        qualification_run_binding=_golden_real_run_binding(),
    )
    assert evidence.exact_eligible is True
    assert evidence.capability_status == "exact"


def test_caller_non_synthetic_boolean_cannot_bypass_binding() -> None:
    evidence = CapabilityQualificationEvidence.assess(
        expectation=_expectation_for_cells("cp312"),
        results=(_result(synthetic=False),),
        qualification_run_binding=None,
    )
    assert evidence.exact_eligible is False
~~~

- [ ] **Step 2: Run red tests**

Run: uv run pytest packages/battlebelief-lab/tests/differential/test_evidence.py -q

Expected: the current model cannot represent exact eligibility and accepts one shared provenance expectation.

- [ ] **Step 3: Implement per-cell expectation and run-binding validation**

Replace the single FixtureResultProvenance expectation with a sorted mapping from environment-cell ID to expected provenance. Add a validated QualificationRunBinding whose digest closes over pre-run identities. Return capability_status exact only when every expected fixture/cell result matches its own provenance and binding and every no-exact condition is absent. Treat synthetic only as diagnostic, never as the authority for a real execution.

- [ ] **Step 4: Run evidence green tests**

Run: uv run pytest packages/battlebelief-lab/tests/differential/test_evidence.py -q

Expected: a complete matching golden binding permits exact eligibility; synthetic, missing, skipped, failed, timeout, crash, malformed, unclassified, known-affecting, and per-cell mismatch cases remain false.

- [ ] **Step 5: Commit**

~~~powershell
git add packages/battlebelief-lab/src/battlebelief_lab/differential/evidence.py packages/battlebelief-lab/tests/differential/test_evidence.py schemas/evaluation/capability-qualification.schema.json schemas/examples
git commit -m "feat(lab): bind qualification evidence per environment"
~~~

### Task 4: Freeze the actual Task-29 CLI path

**Files:**

- Modify: tools/run_engine_differential.py
- Create: packages/battlebelief-lab/src/battlebelief_lab/differential/run_binding.py
- Create: packages/battlebelief-lab/src/battlebelief_lab/differential/result_store.py
- Create: packages/battlebelief-lab/tests/differential/test_run_binding.py
- Modify: tests/tooling/test_pr_workflow.py

- [ ] **Step 1: Write failing command-path tests with injected doubles**

~~~python
def test_qualification_command_writes_sanitized_result_closure(tmp_path: Path) -> None:
    exit_code = main(
        ["--run-binding", str(_binding_file(tmp_path)), "--output-dir", str(tmp_path / "out")],
        dependencies=_double_dependencies(),
    )
    assert exit_code == 0
    assert (tmp_path / "out" / "raw-results.jsonl").is_file()
    assert (tmp_path / "out" / "result-index.json").is_file()
    assert (tmp_path / "out" / "report.json").is_file()


def test_qualification_command_refuses_unbound_default() -> None:
    assert main([], dependencies=_double_dependencies()) == 2
~~~

- [ ] **Step 2: Run red tests**

Run: uv run pytest packages/battlebelief-lab/tests/differential/test_run_binding.py tests/tooling/test_pr_workflow.py -q

Expected: the current tool only supports --synthetic-smoke.

- [ ] **Step 3: Implement binding loader, store, and explicit CLI modes**

Keep --synthetic-smoke. Add only an explicit --run-binding mode requiring an output directory and injected Oracle/Runtime dependencies. Validate binding before execution and write canonical sanitized result JSONL, sorted result index, report, and evidence. Paths may be CLI inputs but cannot appear in persisted documents. No public-network, unpinned-build, or inferred-identity fallback is permitted.

- [ ] **Step 4: Run CLI and CI guard coverage**

Run: uv run python tools/run_engine_differential.py --synthetic-smoke; uv run pytest packages/battlebelief-lab/tests/differential/test_run_binding.py tests/tooling/test_pr_workflow.py -q

Expected: smoke uses doubles only; the workflow contains no real qualification command or run-binding artifact.

- [ ] **Step 5: Commit**

~~~powershell
git add tools/run_engine_differential.py packages/battlebelief-lab/src/battlebelief_lab/differential packages/battlebelief-lab/tests/differential tests/tooling
git commit -m "feat(lab): freeze qualification execution command"
~~~

### Task 5: Rebind corpus-v1 and validate the freeze

**Files:**

- Modify: artifacts/gen9ou/m2/differential/corpus-v1/index.json
- Modify: artifacts/gen9ou/m2/differential/corpus-v1/fixtures/*.json
- Modify: artifacts/gen9ou/m2/differential/corpus-v1/README.md
- Modify: tools/validate_differential_corpus.py
- Test: packages/battlebelief-lab/tests/differential/test_corpus.py
- Test: packages/battlebelief-lab/tests/differential/test_report.py

- [ ] **Step 1: Write failing real-identity and chance-boundary tests**

~~~python
def test_corpus_binds_task24_ruleset_and_execution_scripts() -> None:
    corpus = DifferentialCorpus.load(_corpus_root())
    assert corpus.ruleset_digest == TASK24_RULESET_DIGEST
    assert all(fixture.execution.oracle_script["script_version"] == 2 for fixture in corpus.fixtures)


def test_unavailable_authoritative_chance_is_non_exact() -> None:
    evidence = _evidence_for_complete_matrix_with_chance_unavailable()
    assert evidence_for("gen9.transition.chance.damage-roll").exact_eligible is False
~~~

- [ ] **Step 2: Run red tests**

Run: uv run pytest packages/battlebelief-lab/tests/differential/test_corpus.py packages/battlebelief-lab/tests/differential/test_report.py -q

Expected: synthetic ruleset identity and current fixture closure fail the new binding assertions.

- [ ] **Step 3: Update every fixture before the v1 merge**

Replace the synthetic ruleset identity with the reviewed Task-24 Gen9OU snapshot identity. Add every closed execution binding, regenerate fixture/index/corpus bytes in RFC8785/JCS form, and update the README. If authoritative Oracle chance is unavailable, bind the reviewed damage-roll boundary and keep it non-exact rather than writing an invented distribution.

- [ ] **Step 4: Run deterministic and full repository gates**

Run: uv run python tools/validate_differential_corpus.py; uv run python tools/validate_differential_corpus.py; uv run pytest -q; uv run ruff format --check .; uv run ruff check .; uv run mypy; uv run python tools/check_architecture.py; uv run python tools/check_docs.py; uv run python tools/check_schemas.py; uv run python tools/check_versions.py; uv run python tools/validate_m15_registration.py; uv run python tools/smoke_packages.py; uv lock --check; git diff --check

Expected: both corpus validations are byte-identical and all gates pass.

- [ ] **Step 5: Commit, rebase, push, and update Draft PR 43**

~~~powershell
git add -f artifacts/gen9ou/m2/differential/corpus-v1
git add packages schemas tools tests docs
git commit -m "feat(lab): freeze qualified differential execution"
git fetch origin
git rebase origin/main
git push
~~~

Update PR 43 with predecessor links, final corpus/binder/evidence/schema digests, data-only Task-29 command contract, test evidence, and the explicit statement that no real qualification run or capability claim was created. Keep it Draft.
