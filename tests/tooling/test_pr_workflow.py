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
        "runtime-search-smoke",
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
    assert '"$RUNTIME_SEARCH_SMOKE"' in gate_step["run"]
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
    assert diagnostic["if"] == "failure() && steps.engine_build.outcome == 'failure'"
    assert diagnostic["shell"] == "pwsh"
    assert diagnostic["env"] == {
        "CARGO_HOME": "${{ runner.temp }}/battlebelief-engine-cargo-home",
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
    for job_name in ("artifact-stage-sentinel", "runtime-search-smoke"):
        steps = workflow["jobs"][job_name]["steps"]
        install = next(
            step
            for step in steps
            if step.get("name")
            in {
                "Create isolated sentinel environment",
                "Create isolated Runtime search environment",
            }
        )
        command = install["run"]
        assert "battlebelief_core-0.2.0" not in command
        assert "battlebelief_runtime-0.2.0" not in command
        assert "Get-ChildItem" in command
        assert "battlebelief_core-*.whl" in command
        assert "battlebelief_runtime-*.whl" in command


def test_runtime_search_smoke_installs_only_published_binary_wheels() -> None:
    workflow = _load_workflow()
    job = workflow["jobs"]["runtime-search-smoke"]

    assert job["name"] == "runtime-search-smoke-${{ matrix.os }}-py${{ matrix.python }}"
    assert job["needs"] == ["artifact-index"]
    assert job["strategy"]["fail-fast"] == "false"
    assert job["strategy"]["matrix"]["include"] == [
        {"os": os_name, "python": python_version}
        for os_name in ("ubuntu-24.04", "windows-2025")
        for python_version in ("3.12", "3.13", "3.14")
    ]

    steps = job["steps"]
    install = next(
        step for step in steps if step.get("name") == "Create isolated Runtime search environment"
    )
    assert install["shell"] == "pwsh"
    assert "-m pip install" in install["run"]
    assert "--only-binary=:all:" in install["run"]
    assert "--no-compile" in install["run"]
    assert "--no-deps" not in install["run"]
    assert "+ '[search]'" in install["run"]
    assert "poke_engine-0.0.48" not in install["run"]

    sentinel = next(
        step for step in steps if step.get("name") == "Run published Runtime search sentinel twice"
    )
    assert "run_gen9_sentinel" in sentinel["run"]
    assert "status == 'available'" in sentinel["run"]
    assert "--staged-wheel" not in sentinel["run"]
    assert "engine-publication-bundle" not in str(job)


def test_artifact_index_closes_the_immutable_published_release() -> None:
    workflow = _load_workflow()
    job = workflow["jobs"]["artifact-index"]

    assert job["needs"] == ["artifact-build", "artifact-stage-sentinel"]
    assert job["permissions"] == {"contents": "read"}
    assert job["env"] == {
        "ENGINE_RELEASE_TAG": "engine-poke-engine-v0.0.48-bcf13823-v1",
        "ENGINE_RELEASE_COMMIT": "78ec24dec65582bafb5cb89f00ecb4f8b8a23d8c",
    }

    steps = job["steps"]
    release = next(
        step for step in steps if step.get("name") == "Download immutable release closure"
    )
    assert release["env"] == {"GH_TOKEN": "${{ github.token }}"}
    assert "X-GitHub-Api-Version: 2026-03-10" in release["run"]
    assert "gh release download" in release["run"]

    verify = next(step for step in steps if step.get("name") == "Verify immutable release closure")
    assert "tools/verify_published_engine_release.py" in verify["run"]
    assert "--release-metadata" in verify["run"]
    assert "--bundle-root" in verify["run"]
    assert "--manifest-root artifacts/gen9ou/m2/engine" in verify["run"]
    assert '--expected-tag "${{ env.ENGINE_RELEASE_TAG }}"' in verify["run"]
    schema = next(step for step in steps if step.get("name") == "Validate published index schema")
    assert "engine-artifact-index.schema.json" in schema["run"]
    assert "publication/engine-artifact-index.json" in schema["run"]

    published_wheels = next(
        step for step in steps if "publication/engine-build-*.json" in step.get("run", "")
    )
    assert published_wheels["name"] == (
        "Verify every published wheel manifest without native import"
    )
    assert "tools/verify_published_wheel_manifest.py" in published_wheels["run"]
    assert "tools/verify_poke_engine_artifact.py" not in published_wheels["run"]
    assert "--checkout" not in published_wheels["run"]

    staged_wheel = next(
        step
        for step in workflow["jobs"]["artifact-build"]["steps"]
        if step.get("name") == "Verify the staged wheel without import"
    )
    assert "tools/verify_poke_engine_artifact.py" in staged_wheel["run"]
    assert "--checkout" in staged_wheel["run"]

    commands = "\n".join(step.get("run", "") for step in steps)
    assert "git rev-parse" in commands
    assert "ENGINE_RELEASE_COMMIT" in commands
    assert (
        'test "$(git rev-parse "${ENGINE_RELEASE_TAG}^{commit}")" = "$ENGINE_RELEASE_COMMIT"'
        in commands
    )
    assert (
        'git diff --exit-code "$ENGINE_RELEASE_COMMIT" -- tools/build_poke_engine_wheel.py'
        not in (commands)
    )
    assert 'git show "${ENGINE_RELEASE_COMMIT}:.github/workflows/pr.yml"' in commands
    assert "current['jobs']['artifact-build'] == released['jobs']['artifact-build']" in commands
    assert "Create available artifact index" not in commands
    assert 'cmp "$committed"' not in commands


def test_engine_build_fetches_the_complete_lockfile_for_offline_metadata() -> None:
    workflow = _load_workflow()
    steps = workflow["jobs"]["artifact-build"]["steps"]
    linux_resolution = next(
        step for step in steps if step.get("name") == "Resolve controlled executables on Linux"
    )
    windows_resolution = next(
        step for step in steps if step.get("name") == "Resolve controlled executables on Windows"
    )
    assert "rustup which --toolchain 1.83.0 rustc" in linux_resolution["run"]
    assert "rustup which --toolchain 1.83.0 cargo" in linux_resolution["run"]
    assert "rustup which --toolchain 1.83.0 rustc" in windows_resolution["run"]
    assert "rustup which --toolchain 1.83.0 cargo" in windows_resolution["run"]
    fetch = next(
        step
        for step in steps
        if step.get("name") == "Fetch locked Cargo dependencies before the offline build"
    )
    assert fetch["shell"] == "pwsh"
    assert fetch["env"] == {"CARGO_HOME": "${{ runner.temp }}/battlebelief-engine-cargo-home"}
    assert fetch["run"] == (
        '& "${{ env.ENGINE_CARGO }}" fetch --locked --manifest-path '
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
