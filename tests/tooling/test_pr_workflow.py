from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

_CHECKOUT_ACTION = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
_SETUP_PYTHON_ACTION = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"


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
        "dependency-review",
        "protocol-smoke",
        "safety-smoke",
    ]
    assert "permissions" not in gate
    assert all("uses" not in step for step in gate["steps"])
    gate_step = gate["steps"][0]
    assert gate_step["env"]["PROTOCOL_SMOKE"] == ("${{ needs['protocol-smoke'].result }}")
    assert gate_step["env"]["SAFETY_SMOKE"] == ("${{ needs['safety-smoke'].result }}")
    assert '"$PROTOCOL_SMOKE"' in gate_step["run"]
    assert '"$SAFETY_SMOKE"' in gate_step["run"]
    assert "success|skipped" in gate_step["run"]


def test_repository_contracts_run_m15_semantic_validation() -> None:
    workflow = _load_workflow()
    contracts_step = next(
        step
        for step in workflow["jobs"]["quality"]["steps"]
        if step.get("name") == "Repository contracts"
    )
    assert "uv run python tools/validate_m15_registration.py" in contracts_step["run"]
