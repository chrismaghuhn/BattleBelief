---
document_id: plan-task-27-runtime-observation-predecessor
title: Task 27 Runtime Observation Predecessor Implementation Plan
document_type: roadmap
status: proposed
normative: false
version: 1
applies_to:
  - task-27
  - task-28
effective_from: 2026-08-08
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-08
---

# Task-27 Runtime Observation Predecessor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add a Runtime-owned, engine-neutral, read-only mechanics-observation surface required by the future differential binder.

**Architecture:** A frozen Runtime DTO exposes only public mechanics retained while worlds are prepared or transitioned. PokeEngineTransitionModel projects that DTO without a native call, a new work unit, or a backend-health mutation. Lab maps it to its own observation type; Runtime never imports Lab.

**Tech Stack:** Python 3.12-3.14, dataclasses, BattleBelief Core transition port, verified poke-engine Runtime adapter, pytest, ruff, mypy.

---

### Task 1: Define and export the public Runtime DTO

**Files:**

- Create: packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/mechanics_observation.py
- Modify: packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/__init__.py
- Test: packages/battlebelief-runtime/tests/adapters/poke_engine/test_mechanics_observation.py

- [ ] **Step 1: Write failing DTO validation tests**

~~~python
def test_public_mechanics_observation_is_immutable_and_canonical() -> None:
    observation = RuntimeMechanicsObservation(
        active_slots=("p1:0", "p2:0"),
        effective_types=(("electric", "typeless"), ("water", "typeless")),
        terastallized=(False, False),
        public_hp=((100, 100), (80, 100)),
        statuses=("none", "brn"),
        action_order=("p1", "p2"),
    )
    assert observation.to_dict()["active_slots"] == ["p1:0", "p2:0"]
    with pytest.raises((AttributeError, TypeError)):
        observation.active_slots[0] = "p1:1"  # type: ignore[index]


def test_public_mechanics_observation_rejects_operational_data() -> None:
    with pytest.raises(ValueError, match="public mechanics observation"):
        RuntimeMechanicsObservation(
            active_slots=("unsafe://local", "p2:0"),
            effective_types=(("electric",), ("water",)),
            terastallized=(False, False),
            public_hp=((100, 100), (100, 100)),
            statuses=("none", "none"),
            action_order=None,
        )
~~~

- [ ] **Step 2: Run red test**

Run: uv run pytest packages/battlebelief-runtime/tests/adapters/poke_engine/test_mechanics_observation.py -q

Expected: collection fails because RuntimeMechanicsObservation is not exported.

- [ ] **Step 3: Implement the DTO and export**

~~~python
@dataclass(frozen=True, slots=True)
class RuntimeMechanicsObservation:
    active_slots: tuple[str, str]
    effective_types: tuple[tuple[str, ...], tuple[str, ...]]
    terastallized: tuple[bool, bool]
    public_hp: tuple[tuple[int, int], tuple[int, int]]
    statuses: tuple[str, str]
    action_order: tuple[Literal["p1", "p2"], Literal["p1", "p2"]] | None

    def to_dict(self) -> dict[str, object]: ...
~~~

Validate canonical tokens, HP bounds, two-side ordering, and public-safe strings. Export only the DTO through the public adapter package.

- [ ] **Step 4: Run focused green checks**

Run: uv run pytest packages/battlebelief-runtime/tests/adapters/poke_engine/test_mechanics_observation.py -q; uv run ruff check packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/mechanics_observation.py; uv run mypy packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine

Expected: all pass.

- [ ] **Step 5: Commit**

~~~powershell
git add packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/mechanics_observation.py packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/__init__.py packages/battlebelief-runtime/tests/adapters/poke_engine/test_mechanics_observation.py
git commit -m "feat(runtime): expose canonical mechanics observations"
~~~

### Task 2: Retain and project mechanics without re-running the engine

**Files:**

- Modify: packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/state_mapper.py
- Modify: packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/transition_model.py
- Test: packages/battlebelief-runtime/tests/adapters/poke_engine/test_transition_model.py
- Test: packages/battlebelief-runtime/tests/adapters/poke_engine/test_mechanics_observation.py

- [ ] **Step 1: Write failing projection and no-extra-work tests**

~~~python
def test_projection_reads_transitioned_mechanics_without_native_call(monkeypatch) -> None:
    model, prepared = _model_and_world()
    outcome = model.transition(prepared, _p1_action(prepared), _p2_action(model, prepared))
    calls_before = _native_call_count(monkeypatch)
    observation = model.mechanics_observation(outcome.successors[0].world)
    assert observation.terastallized[0] is True
    assert _native_call_count(monkeypatch) == calls_before
    assert model.mapping_report(outcome.successors[0].world).work_units == 1


def test_projection_agrees_with_public_terminal_authority() -> None:
    model, prepared = _model_and_world()
    outcome = model.transition(prepared, _p1_action(prepared), _p2_action(model, prepared))
    world = outcome.successors[0].world
    observation = model.mechanics_observation(world)
    assert model.is_terminal(world) is (model.terminal_value(world, "p1") is not None)
    assert observation.action_order == ("p1", "p2")
~~~

- [ ] **Step 2: Run red tests**

Run: uv run pytest packages/battlebelief-runtime/tests/adapters/poke_engine/test_mechanics_observation.py packages/battlebelief-runtime/tests/adapters/poke_engine/test_transition_model.py -q

Expected: PokeEngineTransitionModel has no mechanics_observation method.

- [ ] **Step 3: Extend retained mapped state and add the projection**

Extend _MappedNativeState and _PokeEngineWorld with active slot IDs, active status, exact public active HP, and retained action order. Map state values while map_native_state already reads a native state. Derive action order while transition already has generated instructions, then copy it to successor payloads.

~~~python
def mechanics_observation(
    self, world: PreparedWorld[_PokeEngineWorld]
) -> RuntimeMechanicsObservation:
    payload = self._require_runtime_world(world)
    return RuntimeMechanicsObservation(
        active_slots=payload.active_slots,
        effective_types=payload.active_types,
        terastallized=payload.terastallized,
        public_hp=payload.active_hp,
        statuses=payload.active_statuses,
        action_order=payload.last_action_order,
    )
~~~

The method must not call _state_from_string, _legal_choice_values, or _generate_instructions.

- [ ] **Step 4: Run focused green tests**

Run: uv run pytest packages/battlebelief-runtime/tests/adapters/poke_engine/test_mechanics_observation.py packages/battlebelief-runtime/tests/adapters/poke_engine/test_transition_model.py -q

Expected: all pass; tests prove no second native call, zero extra work, stable backend health, and no native-state or hidden-world material in to_dict.

- [ ] **Step 5: Commit**

~~~powershell
git add packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/state_mapper.py packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/transition_model.py packages/battlebelief-runtime/tests/adapters/poke_engine/test_transition_model.py packages/battlebelief-runtime/tests/adapters/poke_engine/test_mechanics_observation.py
git commit -m "feat(runtime): project retained mechanics state"
~~~

### Task 3: Freeze the public and architecture boundary

**Files:**

- Create: packages/battlebelief-runtime/tests/adapters/poke_engine/test_public_api.py
- Modify: tests/tooling/test_architecture.py only if existing boundary coverage needs a new assertion

- [ ] **Step 1: Write failing boundary tests**

~~~python
def test_runtime_public_observation_does_not_import_lab() -> None:
    source = Path(mechanics_observation.__file__).read_text(encoding="utf-8")
    assert "battlebelief_lab" not in source


def test_runtime_public_observation_has_only_canonical_fields() -> None:
    assert set(RuntimeMechanicsObservation.__dataclass_fields__) == {
        "active_slots", "effective_types", "terastallized", "public_hp", "statuses", "action_order"
    }
~~~

- [ ] **Step 2: Run red then green boundary test**

Run: uv run pytest packages/battlebelief-runtime/tests/adapters/poke_engine/test_public_api.py -q

Expected before the export adjustment: import/export assertion failure. Expected after adjustment: pass.

- [ ] **Step 3: Run predecessor gates**

Run: uv run pytest packages/battlebelief-runtime/tests -q; uv run ruff format --check .; uv run ruff check .; uv run mypy; uv run python tools/check_architecture.py; git diff --check

Expected: all pass.

- [ ] **Step 4: Commit and open a Draft PR**

~~~powershell
git add packages/battlebelief-runtime tests
git commit -m "test(runtime): freeze observation projection boundary"
git push -u origin codex/task-27-runtime-observation
~~~

The Draft PR must state: no Lab import, no new transition, no work unit, no health change, no capability elevation, and no Task-29 work.
