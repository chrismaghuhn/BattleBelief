---
document_id: plan-task-24-bounded-scripted-oracle-predecessor
title: Task 24 Bounded Scripted Oracle Predecessor Implementation Plan
document_type: roadmap
status: proposed
normative: false
version: 1
applies_to:
  - task-24
  - task-28
effective_from: 2026-08-08
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-08
---

# Task-24 Bounded Scripted Oracle Predecessor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Bound the Windows Node-22 Oracle lifecycle and add a pinned public script-v2 Oracle surface sufficient for later differential fixtures.

**Architecture:** Task-24 remains the sole owner of Showdown interaction. Fixture-v1 remains supported unchanged; script-v2 is an additive contract for ordered moves, Tera, switches, forced-switches, natural terminal states, and controlled chance execution. Public results remain sanitized and content-addressed, with no differential or poke-engine dependency.

**Tech Stack:** Python asyncio/subprocess lifecycle control, pinned local Pokémon Showdown/Node, RFC8785/JCS, pytest, Windows process jobs, GitHub Actions.

---

### Task 1: Reproduce and bound the Windows Node-22 lifecycle failure

**Files:**

- Modify: packages/battlebelief-lab/src/battlebelief_lab/oracle/showdown/process.py
- Test: packages/battlebelief-lab/tests/oracle/showdown/test_process.py
- Test: tools/smoke_lab_oracle.py

- [ ] **Step 1: Write a failing Windows-process-double test**

~~~python
def test_windows_process_timeout_terminates_job_and_returns_sanitized_timeout() -> None:
    runner = ShowdownProcessRunner(process_factory=HangingWindowsProcessFactory())
    with pytest.raises(OracleProcessError, match="timeout") as failure:
        runner.run(_spec(), ShowdownProcessLimits(startup_seconds=1, step_seconds=1))
    assert failure.value.failure_class is OracleFailureClass.TIMEOUT
    assert HangingWindowsProcessFactory.active_process_count == 0
~~~

- [ ] **Step 2: Run red test**

Run: uv run pytest packages/battlebelief-lab/tests/oracle/showdown/test_process.py::test_windows_process_timeout_terminates_job_and_returns_sanitized_timeout -q

Expected: the fake child remains active or the execution does not return a bounded sanitized failure.

- [ ] **Step 3: Implement bounded cleanup on every exit path**

Execute Windows Job Object termination and close in finally after startup, interaction-step, drain, cancellation, and timeout paths. Preserve current failure semantics; translate cleanup failure to the existing sanitized orphaned-child-process class without PID, host, path, or exception text.

- [ ] **Step 4: Run lifecycle tests twice**

Run: uv run pytest packages/battlebelief-lab/tests/oracle/showdown/test_process.py -q; uv run pytest packages/battlebelief-lab/tests/oracle/showdown/test_process.py -q

Expected: both pass; fake active child count is zero.

- [ ] **Step 5: Commit**

~~~powershell
git add packages/battlebelief-lab/src/battlebelief_lab/oracle/showdown/process.py packages/battlebelief-lab/tests/oracle/showdown/test_process.py tools/smoke_lab_oracle.py
git commit -m "fix(oracle): bound Windows Node process cleanup"
~~~

### Task 2: Add the additive script-v2 public contract

**Files:**

- Create: packages/battlebelief-lab/src/battlebelief_lab/oracle/showdown/script.py
- Modify: packages/battlebelief-lab/src/battlebelief_lab/oracle/showdown/session.py
- Modify: packages/battlebelief-lab/src/battlebelief_lab/oracle/showdown/__init__.py
- Create: packages/battlebelief-lab/tests/oracle/showdown/test_script.py
- Test: packages/battlebelief-lab/tests/oracle/showdown/test_session.py

- [ ] **Step 1: Write failing v2 parsing and command-order tests**

~~~python
def test_script_v2_preserves_move_tera_switch_and_natural_end() -> None:
    script = OracleScriptV2.from_document(_script_document())
    assert [step.kind for step in script.steps] == ["start", "move", "switch", "move"]
    assert script.requires_forced_tie is False


def test_script_v2_rejects_unbound_forced_switch() -> None:
    document = _script_document()
    document["steps"][2]["required_request_sides"] = []
    with pytest.raises(ValueError, match="forced switch"):
        OracleScriptV2.from_document(document)
~~~

- [ ] **Step 2: Run red test**

Run: uv run pytest packages/battlebelief-lab/tests/oracle/showdown/test_script.py -q

Expected: collection fails because OracleScriptV2 is absent.

- [ ] **Step 3: Implement closed script values and public execution**

~~~python
@dataclass(frozen=True, slots=True)
class OracleScriptStep:
    kind: Literal["start", "team", "move", "switch", "forcetie"]
    commands: tuple[str, ...]
    barrier: ScriptBarrier


class ShowdownOracleSession:
    async def run_script(self, script_document: Mapping[str, object]) -> OracleResult: ...
~~~

Validate exact keys, canonical order, p1/p2 command pairing, legal barriers, and natural end. Reuse existing pinned build verification, guarded environment, limits, transcript canonicalization, and sanitized failure handling. Do not change run_fixture or fixture-v1 behavior.

- [ ] **Step 4: Run focused green tests**

Run: uv run pytest packages/battlebelief-lab/tests/oracle/showdown/test_script.py packages/battlebelief-lab/tests/oracle/showdown/test_session.py -q

Expected: ordered switch, forced-switch barrier, natural terminal, and v1 compatibility pass with fake process runners.

- [ ] **Step 5: Commit**

~~~powershell
git add packages/battlebelief-lab/src/battlebelief_lab/oracle/showdown packages/battlebelief-lab/tests/oracle/showdown
git commit -m "feat(oracle): add bounded scripted fixture v2"
~~~

### Task 3: Freeze controlled chance semantics

**Files:**

- Modify: packages/battlebelief-lab/src/battlebelief_lab/oracle/showdown/script.py
- Modify: packages/battlebelief-lab/src/battlebelief_lab/oracle/showdown/session.py
- Modify: packages/battlebelief-lab/src/battlebelief_lab/oracle/showdown/protocol.py if a new sanitized failure enum is required
- Test: packages/battlebelief-lab/tests/oracle/showdown/test_script.py
- Test: packages/battlebelief-lab/tests/oracle/showdown/test_session.py

- [ ] **Step 1: Write failing chance completeness tests**

~~~python
def test_controlled_chance_requires_closed_preregistered_branch_space() -> None:
    with pytest.raises(ValueError, match="complete finite chance structure"):
        OracleChancePlan.from_document({"branches": [{"seed": [1, 2, 3, 4]}]})


async def test_session_fails_closed_without_authoritative_branch_mass() -> None:
    result = await ShowdownOracleSession(_config(), runner=FakeRunner()).run_script(_chance_script())
    assert result.status == "failure"
    assert result.failure_class is OracleFailureClass.CHANCE_STRUCTURE_UNAVAILABLE
~~~

- [ ] **Step 2: Run red tests**

Run: uv run pytest packages/battlebelief-lab/tests/oracle/showdown/test_script.py packages/battlebelief-lab/tests/oracle/showdown/test_session.py -q

Expected: chance-plan types and the failure class are absent.

- [ ] **Step 3: Implement authoritative-or-unavailable chance result**

OracleChancePlan binds a versioned controlled-RNG method, a complete finite branch enumeration identity, every executed branch, and canonical probability mass produced by that method. OracleResult exposes a sanitized chance_observation only for successful complete plans. If the pinned Oracle cannot expose complete authoritative branch mass, return CHANCE_STRUCTURE_UNAVAILABLE rather than a guessed probability.

- [ ] **Step 4: Run chance and compatibility tests**

Run: uv run pytest packages/battlebelief-lab/tests/oracle/showdown/test_script.py packages/battlebelief-lab/tests/oracle/showdown/test_session.py -q

Expected: exact fake controlled-RNG vector passes; incomplete plan fails closed; fixture-v1 remains unchanged.

- [ ] **Step 5: Commit and validate**

~~~powershell
git add packages/battlebelief-lab/src/battlebelief_lab/oracle/showdown packages/battlebelief-lab/tests/oracle/showdown
git commit -m "feat(oracle): freeze controlled chance observations"
~~~

Run: uv run pytest packages/battlebelief-lab/tests/oracle -q; uv run ruff format --check .; uv run ruff check .; uv run mypy; uv run python tools/check_architecture.py; uv run python tools/check_schemas.py; git diff --check

Expected: all pass. Open a Draft PR for Issue #44 that explicitly excludes Runtime, Differential, Capability, and Task-28 logic.
