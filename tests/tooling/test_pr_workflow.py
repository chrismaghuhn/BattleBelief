from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

_CHECKOUT_ACTION = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
_SETUP_PYTHON_ACTION = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
_SETUP_NODE_ACTION = "actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"


def _load_workflow() -> dict[str, object]:
    loaded = yaml.load(
        (ROOT / ".github/workflows/pr.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert isinstance(loaded, dict)
    return loaded


def test_pr_gate_requires_focused_protocol_and_safety_smokes() -> None:
    workflow = _load_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    assert "pull_request" in triggers
    pull_request = triggers["pull_request"]
    assert pull_request == "" or (
        "paths" not in pull_request and "paths-ignore" not in pull_request
    )

    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    expected_smokes = {
        "protocol-smoke": "uv run pytest tests/smokes/test_protocol_smoke.py -v",
        "safety-smoke": "uv run pytest tests/smokes/test_safety_smoke.py -v",
    }
    for job_id, smoke_command in expected_smokes.items():
        job = jobs[job_id]
        assert job["name"] == job_id
        assert job["runs-on"] == "ubuntu-24.04"
        assert "permissions" not in job
        steps = job["steps"]
        assert [step.get("uses") for step in steps if "uses" in step] == [
            _CHECKOUT_ACTION,
            _SETUP_PYTHON_ACTION,
        ]
        assert steps[1]["with"] == {"python-version": "3.14"}
        assert [step.get("run") for step in steps if "run" in step] == [
            "python -m pip install uv==0.12.0",
            "uv sync --frozen --all-packages --group dev",
            smoke_command,
        ]

    gate = jobs["pr-gate"]
    assert gate["name"] == "pr-gate"
    assert gate["if"] == "always()"
    assert gate["needs"] == [
        "quality",
        "package-smoke",
        "oracle-smoke",
        "dependency-review",
        "protocol-smoke",
        "safety-smoke",
        "artifact-build",
        "artifact-candidate-index",
        "artifact-stage-sentinel",
        "artifact-index",
        "artifact-final-sentinel",
    ]
    assert "permissions" not in gate
    assert all("uses" not in step for step in gate["steps"])
    gate_step = gate["steps"][0]
    assert gate_step["env"]["ORACLE_SMOKE"] == "${{ needs['oracle-smoke'].result }}"
    assert gate_step["env"]["PROTOCOL_SMOKE"] == ("${{ needs['protocol-smoke'].result }}")
    assert gate_step["env"]["SAFETY_SMOKE"] == ("${{ needs['safety-smoke'].result }}")
    assert '"$PROTOCOL_SMOKE"' in gate_step["run"]
    assert '"$SAFETY_SMOKE"' in gate_step["run"]
    assert '"$ORACLE_SMOKE"' in gate_step["run"]
    assert '"$ARTIFACT_BUILD"' in gate_step["run"]
    assert '"$ARTIFACT_CANDIDATE_INDEX"' in gate_step["run"]
    assert '"$ARTIFACT_STAGE_SENTINEL"' in gate_step["run"]
    assert '"$ARTIFACT_INDEX"' in gate_step["run"]
    assert '"$ARTIFACT_FINAL_SENTINEL"' in gate_step["run"]
    assert "success|skipped" in gate_step["run"]


def test_repository_contracts_run_m15_semantic_validation() -> None:
    workflow = _load_workflow()
    contracts_step = next(
        step
        for step in workflow["jobs"]["quality"]["steps"]
        if step.get("name") == "Repository contracts"
    )
    assert "uv run python tools/validate_m15_registration.py" in contracts_step["run"]


def test_engine_build_failure_has_a_controlled_maturin_diagnostic() -> None:
    workflow = _load_workflow()
    steps = workflow["jobs"]["artifact-build"]["steps"]
    diagnostic = next(
        step for step in steps if step.get("name") == "Diagnose a failed Maturin build"
    )
    assert diagnostic["if"] == "steps.engine_build.outcome == 'failure'"
    assert diagnostic["shell"] == "pwsh"
    assert diagnostic["env"] == {
        "CARGO_INCREMENTAL": "false",
        "CARGO_NET_OFFLINE": "true",
        "CARGO_PROFILE_RELEASE_DEBUG": "0",
        "PYTHONUTF8": "1",
        "SOURCE_DATE_EPOCH": "1784471591",
    }
    command = diagnostic["run"]
    assert (
        '"--manifest-path", "${{ runner.temp }}/poke-engine/poke-engine-py/Cargo.toml"' in command
    )
    assert '"--interpreter", "${{ env.ENGINE_PYTHON }}"' in command
    assert '"--target", "${{ env.ENGINE_TARGET }}"' in command
    assert "--no-default-features" in command
    assert "poke-engine/gen9,poke-engine/terastallization" in command
    assert "Get-ChildItem Env:" not in command


def test_engine_sentinel_install_resolves_battlebelief_wheels_without_version_literals() -> None:
    workflow = _load_workflow()
    for job_name in ("artifact-stage-sentinel", "artifact-final-sentinel"):
        steps = workflow["jobs"][job_name]["steps"]
        install = next(
            step
            for step in steps
            if step.get("name")
            in {
                "Create isolated sentinel environment",
                "Create isolated final sentinel environment",
            }
        )
        command = install["run"]
        assert "battlebelief_core-0.2.0" not in command
        assert "battlebelief_runtime-0.2.0" not in command
        assert "Get-ChildItem" in command
        assert "battlebelief_core-*.whl" in command
        assert "battlebelief_runtime-*.whl" in command


def test_engine_build_fetches_the_complete_lockfile_for_offline_metadata() -> None:
    workflow = _load_workflow()
    steps = workflow["jobs"]["artifact-build"]["steps"]
    fetch = next(
        step
        for step in steps
        if step.get("name") == "Fetch locked Cargo dependencies before the offline build"
    )
    assert fetch["run"] == (
        "cargo fetch --locked --manifest-path "
        '"${{ runner.temp }}/poke-engine/poke-engine-py/Cargo.toml"'
    )
    assert "--target" not in fetch["run"]


def test_oracle_smoke_uses_exact_cross_platform_node_matrix() -> None:
    workflow = _load_workflow()
    job = workflow["jobs"]["oracle-smoke"]
    assert job["name"] == "oracle-smoke-${{ matrix.os }}-node${{ matrix.node }}"
    assert job["strategy"]["fail-fast"] == "false"
    assert job["strategy"]["matrix"]["include"] == [
        {
            "os": "ubuntu-24.04",
            "node": "18.20.8",
            "npm": "10.8.2",
            "role": "comparison",
        },
        {
            "os": "windows-2025",
            "node": "18.20.8",
            "npm": "10.8.2",
            "role": "comparison",
        },
        {
            "os": "ubuntu-24.04",
            "node": "20.20.2",
            "npm": "10.8.2",
            "role": "comparison",
        },
        {
            "os": "windows-2025",
            "node": "20.20.2",
            "npm": "10.8.2",
            "role": "comparison",
        },
        {
            "os": "ubuntu-24.04",
            "node": "22.23.2",
            "npm": "10.9.8",
            "role": "candidate",
        },
        {
            "os": "windows-2025",
            "node": "22.23.2",
            "npm": "10.9.8",
            "role": "candidate",
        },
    ]

    steps = job["steps"]
    uses = [step["uses"] for step in steps if "uses" in step]
    assert uses == [_CHECKOUT_ACTION, _SETUP_PYTHON_ACTION, _SETUP_NODE_ACTION]
    node_setup = next(step for step in steps if step.get("uses") == _SETUP_NODE_ACTION)
    assert node_setup["with"] == {"node-version": "${{ matrix.node }}"}
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "npm ci" not in commands
    assert "tools/build_showdown_oracle.py" in commands
    assert "tools/smoke_lab_oracle.py" in commands
    assert '--probe-role "${{ matrix.role }}"' in commands
    assert '--checkout "${{ runner.temp }}/pokemon-showdown"' in commands
    assert "--verify-only" in commands
    assert "schemas/examples/showdown-oracle-source.example.json" in commands
    assert "packages/battlebelief-lab/tests/fixtures/showdown_oracle" in commands
    diagnostic = next(
        step for step in steps if step.get("name") == "Diagnose a rejected Linux oracle checkout"
    )
    assert diagnostic["if"] == "failure() && runner.os != 'Windows'"
    assert diagnostic["shell"] == "bash"
    assert diagnostic["env"] == {"ORACLE_CHECKOUT": "${{ runner.temp }}/pokemon-showdown"}
    assert 'git -C "$ORACLE_CHECKOUT" diff --name-status --no-ext-diff' in diagnostic["run"]
    assert 'GIT_INDEX_FILE="$ORACLE_CHECKOUT/logs/.gitindex"' in diagnostic["run"]
    assert "diff --cached --name-status HEAD" in diagnostic["run"]
    assert "cat " not in diagnostic["run"]


def test_pr_gate_requires_oracle_smoke() -> None:
    workflow = _load_workflow()
    gate = workflow["jobs"]["pr-gate"]
    assert "oracle-smoke" in gate["needs"]
    gate_step = gate["steps"][0]
    assert gate_step["env"]["ORACLE_SMOKE"] == "${{ needs['oracle-smoke'].result }}"
    assert '"$ORACLE_SMOKE"' in gate_step["run"]
