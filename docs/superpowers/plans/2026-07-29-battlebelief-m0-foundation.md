---
document_id: plan-battlebelief-m0-foundation
title: BattleBelief M0 Repository Foundation Implementation Plan
document_type: roadmap
status: proposed
normative: false
version: 1
applies_to:
  - m0
  - repository
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# BattleBelief M0 Repository Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the public, secure, cross-platform M0 foundation for BattleBelief as a three-package Python monorepo without implementing battle, engine, oracle, dataset, training, or model behavior.

**Architecture:** A standard Python workspace contains `battlebelief-core`, `battlebelief-runtime`, and `battlebelief-lab` with exact lockstep versions during `0.x`. Small repository tools enforce package boundaries, documentation authority, schema validity, canonicalization, packaging, and provenance; one stable GitHub check named `pr-gate` aggregates the merge-blocking jobs.

**Tech Stack:** Python 3.12–3.14, uv 0.12.0, Hatchling 1.31.0, pytest 9.1.1, Ruff 0.16.0, mypy 2.3.0, jsonschema 4.26.0, PyYAML 6.0.3, rfc8785 0.1.4, GitHub Actions, GitHub CLI.

---

## Scope boundary

M0 proves only repository, package, CLI-entrypoint, schema, documentation,
architecture, security, and CI readiness.

Explicitly absent from M0:

- Showdown network connection and authentication;
- battle-capable legal or heuristic policy;
- `poke-engine`, Rust build, `runtime[search]`, and Gen9 sentinel;
- local Showdown oracle;
- Replay-, Dataset-, DuckDB-, Parquet-, PyTorch-, ONNX-, CUDA- or Kaggle code;
- strength, parity, ladder, release, or MVP claims.

The phase ownership is:

```text
M0  package imports + --version/doctor
M1  battle-capable legal/heuristic runtime
M2  runtime[search] + Gen9 sentinel + local Showdown oracle
M3  replay and dataset ingestion
```

## File map

```text
.
├─ .github/
│  ├─ ISSUE_TEMPLATE/
│  │  ├─ bug.yml
│  │  ├─ engine-divergence.yml
│  │  ├─ research-hypothesis.yml
│  │  └─ transfer-audit.yml
│  ├─ workflows/pr.yml
│  ├─ dependabot.yml
│  └─ pull_request_template.md
├─ config/
│  └─ docs-authority.json
├─ packages/
│  ├─ battlebelief-core/
│  │  ├─ pyproject.toml
│  │  ├─ README.md
│  │  ├─ src/battlebelief_core/__init__.py
│  │  ├─ src/battlebelief_core/py.typed
│  │  └─ tests/test_package.py
│  ├─ battlebelief-runtime/
│  │  ├─ pyproject.toml
│  │  ├─ README.md
│  │  ├─ src/battlebelief_runtime/__init__.py
│  │  ├─ src/battlebelief_runtime/__main__.py
│  │  ├─ src/battlebelief_runtime/cli.py
│  │  ├─ src/battlebelief_runtime/public_api/__init__.py
│  │  ├─ src/battlebelief_runtime/public_api/status.py
│  │  ├─ src/battlebelief_runtime/py.typed
│  │  └─ tests/test_cli.py
│  └─ battlebelief-lab/
│     ├─ pyproject.toml
│     ├─ README.md
│     ├─ src/battlebelief_lab/__init__.py
│     ├─ src/battlebelief_lab/__main__.py
│     ├─ src/battlebelief_lab/cli.py
│     ├─ src/battlebelief_lab/py.typed
│     └─ tests/test_cli.py
├─ schemas/
│  └─ canonicalization/test-vectors.json
├─ tests/tooling/
│  ├─ test_architecture.py
│  ├─ test_canonicalization.py
│  ├─ test_docs.py
│  └─ test_versions.py
├─ tools/
│  ├─ canonicalize_manifest.py
│  ├─ check_architecture.py
│  ├─ check_docs.py
│  ├─ check_schemas.py
│  ├─ check_versions.py
│  └─ smoke_packages.py
├─ .editorconfig
├─ .gitattributes
├─ .gitignore
├─ CITATION.cff
├─ CONTRIBUTING.md
├─ LICENSE
├─ README.md
├─ SECURITY.md
├─ pyproject.toml
└─ uv.lock
```

Existing `docs/` and `schemas/` files remain authoritative inputs. The
bit-identical design freeze is never edited.

### Task 1: Bootstrap the repository and public metadata

**Files:**

- Create: `.gitignore`
- Create: `.gitattributes`
- Create: `.editorconfig`
- Create: `README.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CITATION.cff`
- Create: `LICENSE`
- Include unchanged: `docs/**`
- Include unchanged: `schemas/**`

- [ ] **Step 1: Verify that the remote has no history before initializing**

Run:

```powershell
git ls-remote --symref https://github.com/chrismaghuhn/BattleBelief.git HEAD
git ls-remote --heads --tags https://github.com/chrismaghuhn/BattleBelief.git
```

Expected: no branch or tag refs. If any ref exists, stop this task and reconcile
the remote history without force-pushing or deleting either copy.

- [ ] **Step 2: Initialize the local repository and remote**

Run:

```powershell
git init -b main
git remote add origin https://github.com/chrismaghuhn/BattleBelief.git
git remote -v
```

Expected: `origin` fetch and push URLs both point to the BattleBelief
repository.

- [ ] **Step 3: Add the repository hygiene files**

`.gitignore`:

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.venv/
.venv-*/
dist/
build/
*.egg-info/
.idea/
.vscode/
.DS_Store
Thumbs.db
.env
.env.*
!.env.example
/data/
/artifacts/
/checkpoints/
/outputs/
```

`.gitattributes`:

```gitattributes
* text=auto
*.py text eol=lf
*.md text eol=lf
*.json text eol=lf
*.toml text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
*.ps1 text eol=crlf
```

`.editorconfig`:

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
indent_style = space
indent_size = 4

[{*.json,*.toml,*.yaml,*.yml,*.md}]
indent_style = space
indent_size = 2

[*.ps1]
end_of_line = crlf
indent_style = space
indent_size = 4
```

- [ ] **Step 4: Add the public project files**

`README.md`:

```markdown
# BattleBelief

An open-source Pokémon Singles research bot for decision-making under hidden
information.

> **Status:** M0 repository foundation in progress. Battle play, search,
> training, and strength claims are not implemented.

BattleBelief targets current Smogon Gen 9 OU first. Teams are fixed before a
battle; offline team-building and in-battle decision-making are separate
systems.

## Packages

- `battlebelief-core`: pure domain, belief, search, safety, and ports
- `battlebelief-runtime`: public live adapters and CLI
- `battlebelief-lab`: offline oracle, data, training, evaluation, and reporting

The current package boundaries are defined in
[`docs/architecture/code-boundaries.md`](docs/architecture/code-boundaries.md).

## Documentation

Start with [`docs/README.md`](docs/README.md). A green `main` is an integration
claim only; it is not a strength, parity, or MVP claim.

## License

Source code is licensed under Apache-2.0. Datasets and model artifacts may have
different licenses and are documented separately.

BattleBelief is an unofficial research project and is not affiliated with
Nintendo, Game Freak, Creatures Inc., Smogon, or Pokémon Showdown.
```

`CONTRIBUTING.md`:

````markdown
# Contributing

Read [`docs/README.md`](docs/README.md) and
[`docs/project/contribution-provenance.md`](docs/project/contribution-provenance.md)
before opening a pull request.

Use a short branch, keep one topic per pull request, add tests before behavior,
and run:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run python tools/check_docs.py
uv run python tools/check_schemas.py
uv run python tools/check_architecture.py
uv run python tools/check_versions.py
```

Do not submit credentials, ladder cookies, replay corpora, model weights,
incompatible code, or code whose provenance you cannot explain.
````

`SECURITY.md`:

```markdown
# Security Policy

## Supported versions

Before the first stable release, security fixes target `main` and the newest
published `0.x` release only.

## Reporting

Use GitHub Private Vulnerability Reporting for security-sensitive reports. Do
not open a public issue containing credentials, tokens, cookies, private
replays, or exploit details.

General bugs that do not create a security risk belong in the public bug form.
```

`CITATION.cff`:

```yaml
cff-version: 1.2.0
message: "If you use BattleBelief in research, cite the software and the exact release."
title: "BattleBelief"
type: software
license: Apache-2.0
repository-code: "https://github.com/chrismaghuhn/BattleBelief"
authors:
  - name: "BattleBelief contributors"
```

For `LICENSE`, add the exact, unmodified Apache License 2.0 text published at
<https://www.apache.org/licenses/LICENSE-2.0.txt>. Do not add a project-specific
copyright restriction.

- [ ] **Step 5: Verify text hygiene**

Run:

```powershell
rg -n "(Users[\\\\/]|file://|BEGIN .*PRIVATE KEY|password\\s*=|token\\s*=)" . `
  -g '!docs/archive/**' -g '!uv.lock'
```

Expected: no matches.

- [ ] **Step 6: Create and push the bootstrap commit**

Run:

```powershell
git add .editorconfig .gitattributes .gitignore README.md CONTRIBUTING.md SECURITY.md CITATION.cff LICENSE docs schemas
git commit -m "chore: bootstrap BattleBelief planning repository"
git push -u origin main
git switch -c feat/m0-foundation
```

Expected: the approved planning state exists on remote `main`, and all
remaining M0 work occurs on `feat/m0-foundation`. This initial push is the only
bootstrap exception before branch protection exists.

### Task 2: Create the uv workspace and package metadata

**Files:**

- Create: `pyproject.toml`
- Create: `packages/battlebelief-core/pyproject.toml`
- Create: `packages/battlebelief-runtime/pyproject.toml`
- Create: `packages/battlebelief-lab/pyproject.toml`
- Create: each package `README.md`
- Create: the three package-root `__init__.py` files shown in the file map
- Create: the three `py.typed` markers shown in the file map
- Create: `uv.lock`

- [ ] **Step 1: Add the root workspace configuration**

`pyproject.toml`:

```toml
[project]
name = "battlebelief-workspace"
version = "0.1.0"
description = "Development workspace for BattleBelief"
requires-python = ">=3.12,<3.15"
dependencies = []

[tool.uv]
package = false

[tool.uv.workspace]
members = [
  "packages/battlebelief-core",
  "packages/battlebelief-runtime",
  "packages/battlebelief-lab",
]

[dependency-groups]
dev = [
  "hatchling==1.31.0",
  "jsonschema==4.26.0",
  "mypy==2.3.0",
  "pytest==9.1.1",
  "PyYAML==6.0.3",
  "rfc8785==0.1.4",
  "ruff==0.16.0",
]

[tool.pytest.ini_options]
addopts = ["-ra", "--strict-config", "--strict-markers"]
testpaths = ["tests", "packages"]

[tool.ruff]
target-version = "py312"
line-length = 100
src = [
  "packages/battlebelief-core/src",
  "packages/battlebelief-runtime/src",
  "packages/battlebelief-lab/src",
  "tools",
  "tests",
]

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
mypy_path = [
  "packages/battlebelief-core/src",
  "packages/battlebelief-runtime/src",
  "packages/battlebelief-lab/src",
]
files = ["packages"]
```

- [ ] **Step 2: Add the three package manifests**

Use this common build configuration in all three package manifests:

```toml
[build-system]
requires = ["hatchling==1.31.0"]
build-backend = "hatchling.build"
```

`packages/battlebelief-core/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling==1.31.0"]
build-backend = "hatchling.build"

[project]
name = "battlebelief-core"
version = "0.1.0"
description = "Pure core contracts and application logic for BattleBelief"
readme = "README.md"
requires-python = ">=3.12,<3.15"
license = "Apache-2.0"
authors = [{ name = "BattleBelief contributors" }]
dependencies = []

[tool.hatch.build.targets.wheel]
packages = ["src/battlebelief_core"]
```

`packages/battlebelief-runtime/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling==1.31.0"]
build-backend = "hatchling.build"

[project]
name = "battlebelief-runtime"
version = "0.1.0"
description = "Public runtime adapters and CLI for BattleBelief"
readme = "README.md"
requires-python = ">=3.12,<3.15"
license = "Apache-2.0"
authors = [{ name = "BattleBelief contributors" }]
dependencies = ["battlebelief-core==0.1.0"]

[project.scripts]
battlebelief = "battlebelief_runtime.cli:main"

[tool.uv.sources]
battlebelief-core = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/battlebelief_runtime"]
```

`packages/battlebelief-lab/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling==1.31.0"]
build-backend = "hatchling.build"

[project]
name = "battlebelief-lab"
version = "0.1.0"
description = "Offline research and evaluation tools for BattleBelief"
readme = "README.md"
requires-python = ">=3.12,<3.15"
license = "Apache-2.0"
authors = [{ name = "BattleBelief contributors" }]
dependencies = [
  "battlebelief-core==0.1.0",
  "battlebelief-runtime==0.1.0",
]

[project.scripts]
battlebelief-lab = "battlebelief_lab.cli:main"

[tool.uv.sources]
battlebelief-core = { workspace = true }
battlebelief-runtime = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/battlebelief_lab"]
```

Package READMEs must state the package responsibility, link to
`../../docs/architecture/code-boundaries.md`, and explicitly state that M0
contains no battle, search, oracle, or dataset implementation.

Use these exact bodies:

`packages/battlebelief-core/README.md`:

```markdown
# battlebelief-core

Pure, dependency-light domain and application package for BattleBelief.
Current boundaries are defined in
[`docs/architecture/code-boundaries.md`](../../docs/architecture/code-boundaries.md).

M0 exposes package identity only. It contains no battle, engine, model, oracle,
or dataset behavior.
```

`packages/battlebelief-runtime/README.md`:

```markdown
# battlebelief-runtime

Public runtime package and CLI for BattleBelief. Current boundaries are
defined in
[`docs/architecture/code-boundaries.md`](../../docs/architecture/code-boundaries.md).

M0 provides only `--version` and `doctor`. It is not battle-capable and has no
search, engine, model, or network adapter.
```

`packages/battlebelief-lab/README.md`:

```markdown
# battlebelief-lab

Offline research package for BattleBelief. Current boundaries are defined in
[`docs/architecture/code-boundaries.md`](../../docs/architecture/code-boundaries.md).

M0 provides only `--version` and `doctor`. Oracle, dataset, training, and
evaluation behavior are absent.
```

- [ ] **Step 3: Add importable but behavior-free package roots**

Create empty UTF-8 `__init__.py` files and empty `py.typed` markers at the exact
paths in the file map. No domain, adapter, oracle, or dataset namespaces are
created in this task.

- [ ] **Step 4: Resolve and lock the workspace**

Run:

```powershell
python -m pip install uv==0.12.0
uv lock
uv lock --check
```

Expected: `uv.lock` is created and the lock check exits zero.

- [ ] **Step 5: Commit the packaging metadata**

Run:

```powershell
git add pyproject.toml uv.lock packages
git commit -m "build: define BattleBelief package workspace"
```

### Task 3: Define the minimal public core surface

**Files:**

- Modify: `packages/battlebelief-core/src/battlebelief_core/__init__.py`
- Create: `packages/battlebelief-core/tests/test_package.py`

- [ ] **Step 1: Write the failing core package test**

```python
from battlebelief_core import __version__


def test_core_version_is_lockstep_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the test and verify the failure**

Run:

```powershell
uv sync --all-packages --group dev
uv run pytest packages/battlebelief-core/tests/test_package.py -v
```

Expected: FAIL because `battlebelief_core.__version__` is absent.

- [ ] **Step 3: Add the minimal implementation**

```python
"""Pure BattleBelief core package."""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

- [ ] **Step 4: Run the test and static checks**

Run:

```powershell
uv run pytest packages/battlebelief-core/tests/test_package.py -v
uv run ruff check packages/battlebelief-core
uv run mypy packages/battlebelief-core
```

Expected: all commands exit zero.

- [ ] **Step 5: Commit**

```powershell
git add packages/battlebelief-core
git commit -m "feat(core): expose package identity"
```

### Task 4: Add the M0 runtime CLI and public status API

**Files:**

- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/__init__.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/__main__.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/cli.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/public_api/__init__.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/public_api/status.py`
- Create: `packages/battlebelief-runtime/tests/test_cli.py`

- [ ] **Step 1: Write failing runtime tests**

```python
import json

import pytest

from battlebelief_runtime.cli import main
from battlebelief_runtime.public_api import runtime_status


def test_runtime_status_is_m0_entrypoint_only() -> None:
    assert runtime_status() == {
        "package": "battlebelief-runtime",
        "version": "0.1.0",
        "phase": "M0",
        "entrypoint": "ready",
        "battle_capability": "absent",
    }


def test_doctor_prints_canonical_status(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output) == runtime_status()


def test_version_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "0.1.0"
```

- [ ] **Step 2: Run the tests and verify the failure**

Run:

```powershell
uv run pytest packages/battlebelief-runtime/tests/test_cli.py -v
```

Expected: FAIL because `cli` and `public_api` do not exist.

- [ ] **Step 3: Implement the status API**

`public_api/status.py`:

```python
from typing import Final, TypedDict


class RuntimeStatus(TypedDict):
    package: str
    version: str
    phase: str
    entrypoint: str
    battle_capability: str


_STATUS: Final[RuntimeStatus] = {
    "package": "battlebelief-runtime",
    "version": "0.1.0",
    "phase": "M0",
    "entrypoint": "ready",
    "battle_capability": "absent",
}


def runtime_status() -> RuntimeStatus:
    return _STATUS.copy()
```

`public_api/__init__.py`:

```python
from .status import RuntimeStatus, runtime_status

__all__ = ["RuntimeStatus", "runtime_status"]
```

- [ ] **Step 4: Implement the CLI**

`cli.py`:

```python
import argparse
import json
from collections.abc import Sequence

from .public_api import runtime_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="battlebelief")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="report M0 package readiness")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(runtime_status()["version"])
        return 0
    if args.command == "doctor":
        print(json.dumps(runtime_status(), sort_keys=True, separators=(",", ":")))
        return 0
    build_parser().print_help()
    return 0
```

`__main__.py`:

```python
from .cli import main

raise SystemExit(main())
```

`__init__.py`:

```python
"""Public BattleBelief runtime package."""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

- [ ] **Step 5: Run runtime verification**

Run:

```powershell
uv run pytest packages/battlebelief-runtime/tests/test_cli.py -v
uv run battlebelief --version
uv run battlebelief doctor
uv run ruff check packages/battlebelief-runtime
uv run mypy packages/battlebelief-runtime
```

Expected:

```text
0.1.0
{"battle_capability":"absent","entrypoint":"ready","package":"battlebelief-runtime","phase":"M0","version":"0.1.0"}
```

All tests and checks exit zero.

- [ ] **Step 6: Commit**

```powershell
git add packages/battlebelief-runtime
git commit -m "feat(runtime): add M0 status CLI"
```

### Task 5: Add the M0 lab CLI without research dependencies

**Files:**

- Modify: `packages/battlebelief-lab/src/battlebelief_lab/__init__.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/__main__.py`
- Create: `packages/battlebelief-lab/src/battlebelief_lab/cli.py`
- Create: `packages/battlebelief-lab/tests/test_cli.py`

- [ ] **Step 1: Write failing lab tests**

```python
import json

import pytest

from battlebelief_lab.cli import lab_status, main


def test_lab_status_has_no_oracle_or_dataset_capability() -> None:
    assert lab_status() == {
        "package": "battlebelief-lab",
        "version": "0.1.0",
        "phase": "M0",
        "entrypoint": "ready",
        "oracle_capability": "absent",
        "dataset_capability": "absent",
    }


def test_lab_doctor(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor"]) == 0
    assert json.loads(capsys.readouterr().out) == lab_status()
```

- [ ] **Step 2: Run the tests and verify the failure**

Run:

```powershell
uv run pytest packages/battlebelief-lab/tests/test_cli.py -v
```

Expected: FAIL because `battlebelief_lab.cli` does not exist.

- [ ] **Step 3: Implement the lab CLI**

`cli.py`:

```python
import argparse
import json
from collections.abc import Sequence
from typing import TypedDict

from battlebelief_runtime.public_api import runtime_status


class LabStatus(TypedDict):
    package: str
    version: str
    phase: str
    entrypoint: str
    oracle_capability: str
    dataset_capability: str


def lab_status() -> LabStatus:
    runtime = runtime_status()
    if runtime["entrypoint"] != "ready":
        raise RuntimeError("battlebelief-runtime entrypoint is not ready")
    return {
        "package": "battlebelief-lab",
        "version": "0.1.0",
        "phase": "M0",
        "entrypoint": "ready",
        "oracle_capability": "absent",
        "dataset_capability": "absent",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="battlebelief-lab")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="report M0 lab package readiness")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(lab_status()["version"])
        return 0
    if args.command == "doctor":
        print(json.dumps(lab_status(), sort_keys=True, separators=(",", ":")))
        return 0
    build_parser().print_help()
    return 0
```

`__main__.py`:

```python
from .cli import main

raise SystemExit(main())
```

`__init__.py`:

```python
"""Offline BattleBelief research package."""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

- [ ] **Step 4: Run lab verification**

Run:

```powershell
uv run pytest packages/battlebelief-lab/tests/test_cli.py -v
uv run battlebelief-lab --version
uv run battlebelief-lab doctor
uv run ruff check packages/battlebelief-lab
uv run mypy packages/battlebelief-lab
```

Expected: version `0.1.0`, a JSON doctor report with both capabilities
`"absent"`, and zero test/static-check failures.

- [ ] **Step 5: Commit**

```powershell
git add packages/battlebelief-lab
git commit -m "feat(lab): add dependency-light M0 CLI"
```

### Task 6: Enforce lockstep versions and isolated installation smokes

**Files:**

- Create: `tools/__init__.py`
- Create: `tools/check_versions.py`
- Create: `tools/smoke_packages.py`
- Create: `tests/tooling/test_versions.py`

- [ ] **Step 1: Write the failing version test**

```python
from pathlib import Path

from tools.check_versions import collect_version_errors


ROOT = Path(__file__).resolve().parents[2]


def test_workspace_versions_are_exactly_locked() -> None:
    assert collect_version_errors(ROOT) == []
```

- [ ] **Step 2: Run it and verify the failure**

Run:

```powershell
uv run pytest tests/tooling/test_versions.py -v
```

Expected: FAIL because `tools.check_versions` does not exist.

- [ ] **Step 3: Implement the lockstep checker**

`tools/check_versions.py`:

```python
from __future__ import annotations

import sys
import tomllib
from pathlib import Path


PACKAGES = {
    "battlebelief-core": Path("packages/battlebelief-core/pyproject.toml"),
    "battlebelief-runtime": Path("packages/battlebelief-runtime/pyproject.toml"),
    "battlebelief-lab": Path("packages/battlebelief-lab/pyproject.toml"),
}


def collect_version_errors(root: Path) -> list[str]:
    metadata: dict[str, dict[str, object]] = {}
    for expected_name, relative_path in PACKAGES.items():
        project = tomllib.loads((root / relative_path).read_text(encoding="utf-8"))["project"]
        if project["name"] != expected_name:
            return [f"{relative_path}: expected name {expected_name!r}"]
        metadata[expected_name] = project

    versions = {str(project["version"]) for project in metadata.values()}
    if len(versions) != 1:
        return [f"package versions are not lockstep: {sorted(versions)}"]
    version = versions.pop()

    errors: list[str] = []
    requirements = {
        "battlebelief-runtime": {f"battlebelief-core=={version}"},
        "battlebelief-lab": {
            f"battlebelief-core=={version}",
            f"battlebelief-runtime=={version}",
        },
    }
    for package, required in requirements.items():
        actual = set(metadata[package].get("dependencies", []))
        missing = required - actual
        if missing:
            errors.append(f"{package}: missing exact dependencies {sorted(missing)}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = collect_version_errors(root)
    if errors:
        print(*errors, sep="\n", file=sys.stderr)
        return 1
    print("PASS: package versions and internal requirements are lockstep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Implement the cross-platform isolated smoke**

Create an empty `tools/__init__.py`, then add `tools/smoke_packages.py`:

```python
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
PACKAGE_DIRS = (
    ROOT / "packages/battlebelief-core",
    ROOT / "packages/battlebelief-runtime",
    ROOT / "packages/battlebelief-lab",
)


def run(arguments: list[str]) -> None:
    subprocess.run(arguments, cwd=ROOT, check=True)


def environment_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts/python.exe"
    return venv_dir / "bin/python"


def entrypoint(venv_dir: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    directory = "Scripts" if sys.platform == "win32" else "bin"
    return venv_dir / directory / f"{name}{suffix}"


def install_profile(
    root: Path,
    dist: Path,
    requirement: str,
    commands: list[list[str]],
) -> None:
    venv.EnvBuilder(with_pip=True, clear=True).create(root)
    python = environment_python(root)
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-index",
            "--find-links",
            str(dist),
            requirement,
        ]
    )
    for command in commands:
        run(command)


def main() -> int:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv executable is required")

    with tempfile.TemporaryDirectory(prefix="battlebelief-smoke-") as temporary:
        temp = Path(temporary)
        dist = temp / "dist"
        dist.mkdir()
        for package_dir in PACKAGE_DIRS:
            run([uv, "build", str(package_dir), "--out-dir", str(dist)])

        core_env = temp / "core"
        install_profile(
            core_env,
            dist,
            f"battlebelief-core=={VERSION}",
            [
                [
                    str(environment_python(core_env)),
                    "-c",
                    "import battlebelief_core; "
                    "assert battlebelief_core.__version__ == '0.1.0'",
                ]
            ],
        )
        print("PASS: core")

        runtime_env = temp / "runtime"
        install_profile(
            runtime_env,
            dist,
            f"battlebelief-runtime=={VERSION}",
            [
                [str(entrypoint(runtime_env, "battlebelief")), "--version"],
                [str(entrypoint(runtime_env, "battlebelief")), "doctor"],
            ],
        )
        print("PASS: runtime")

        lab_env = temp / "lab"
        install_profile(
            lab_env,
            dist,
            f"battlebelief-lab=={VERSION}",
            [
                [str(entrypoint(lab_env, "battlebelief-lab")), "--version"],
                [str(entrypoint(lab_env, "battlebelief-lab")), "doctor"],
            ],
        )
        print("PASS: lab")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run all packaging checks**

Run:

```powershell
uv run pytest tests/tooling/test_versions.py -v
uv run python tools/check_versions.py
uv run python tools/smoke_packages.py
```

Expected:

```text
PASS: package versions and internal requirements are lockstep
PASS: core
PASS: runtime
PASS: lab
```

- [ ] **Step 6: Commit**

```powershell
git add tools/check_versions.py tools/smoke_packages.py tests/tooling/test_versions.py
git commit -m "test: enforce package and installation contracts"
```

### Task 7: Enforce architecture and dependency boundaries

**Files:**

- Create: `tools/check_architecture.py`
- Create: `tests/tooling/test_architecture.py`

- [ ] **Step 1: Write focused failing tests**

```python
from pathlib import Path

from tools.check_architecture import ImportRule, scan_tree


def write_module(root: Path, package: str, body: str) -> Path:
    path = root / package / "module.py"
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_core_cannot_import_runtime(tmp_path: Path) -> None:
    write_module(tmp_path, "battlebelief_core", "import battlebelief_runtime\n")
    errors = scan_tree(tmp_path, ImportRule.core())
    assert any("battlebelief_runtime" in error for error in errors)


def test_lab_can_import_only_public_runtime_api(tmp_path: Path) -> None:
    write_module(tmp_path, "battlebelief_lab", "import battlebelief_runtime.cli\n")
    errors = scan_tree(tmp_path, ImportRule.lab())
    assert any("battlebelief_runtime.cli" in error for error in errors)


def test_lab_public_runtime_import_is_allowed(tmp_path: Path) -> None:
    write_module(
        tmp_path,
        "battlebelief_lab",
        "from battlebelief_runtime.public_api import runtime_status\n",
    )
    assert scan_tree(tmp_path, ImportRule.lab()) == []
```

- [ ] **Step 2: Run the tests and verify the failure**

Run:

```powershell
uv run pytest tests/tooling/test_architecture.py -v
```

Expected: FAIL because `tools.check_architecture` does not exist.

- [ ] **Step 3: Implement AST-based import checks**

The implementation uses `ast.walk` over every `*.py` file and normalizes both
`import x` and `from x import y` to their absolute module roots.

The exact policies are:

```python
CORE_FORBIDDEN = {
    "battlebelief_runtime",
    "battlebelief_lab",
    "torch",
    "onnxruntime",
    "duckdb",
    "pyarrow",
    "sqlite3",
    "websockets",
    "poke_engine",
}

RUNTIME_FORBIDDEN = {
    "battlebelief_lab",
    "torch",
    "duckdb",
    "pyarrow",
}

LAB_RUNTIME_ALLOWED = (
    "battlebelief_runtime.adapters",
    "battlebelief_runtime.testing",
    "battlebelief_runtime.public_api",
)
```

`ImportRule.core()`, `.runtime()`, and `.lab()` return immutable rule objects.
`scan_tree(root, rule)` returns sorted diagnostics containing the
repository-relative file, line number, and forbidden import, for example:

```text
packages/battlebelief-core/src/battlebelief_core/bad_adapter.py:1: forbidden import websockets
```

The repository entrypoint scans:

```text
packages/battlebelief-core/src       with core rule
packages/battlebelief-runtime/src    with runtime rule
packages/battlebelief-lab/src        with lab rule
```

Implement `tools/check_architecture.py`:

```python
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


CORE_FORBIDDEN = frozenset(
    {
        "battlebelief_runtime",
        "battlebelief_lab",
        "torch",
        "onnxruntime",
        "duckdb",
        "pyarrow",
        "sqlite3",
        "websockets",
        "poke_engine",
    }
)
RUNTIME_FORBIDDEN = frozenset(
    {"battlebelief_lab", "torch", "duckdb", "pyarrow"}
)
LAB_RUNTIME_ALLOWED = (
    "battlebelief_runtime.adapters",
    "battlebelief_runtime.testing",
    "battlebelief_runtime.public_api",
)


@dataclass(frozen=True, slots=True)
class ImportRule:
    forbidden_roots: frozenset[str]
    runtime_allowlist: tuple[str, ...] = ()

    @classmethod
    def core(cls) -> ImportRule:
        return cls(CORE_FORBIDDEN)

    @classmethod
    def runtime(cls) -> ImportRule:
        return cls(RUNTIME_FORBIDDEN)

    @classmethod
    def lab(cls) -> ImportRule:
        return cls(frozenset(), LAB_RUNTIME_ALLOWED)


def imported_modules(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append((node.lineno, node.module))
    return modules


def has_root(module: str, root: str) -> bool:
    return module == root or module.startswith(root + ".")


def scan_tree(root: Path, rule: ImportRule) -> list[str]:
    errors: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for line, module in imported_modules(path):
            if any(has_root(module, forbidden) for forbidden in rule.forbidden_roots):
                errors.append(
                    f"{path.relative_to(root)}:{line}: forbidden import {module}"
                )
            if has_root(module, "battlebelief_runtime") and rule.runtime_allowlist:
                if not any(has_root(module, allowed) for allowed in rule.runtime_allowlist):
                    errors.append(
                        f"{path.relative_to(root)}:{line}: forbidden import {module}"
                    )
    return sorted(set(errors))


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    checks = (
        (repository / "packages/battlebelief-core/src", ImportRule.core()),
        (repository / "packages/battlebelief-runtime/src", ImportRule.runtime()),
        (repository / "packages/battlebelief-lab/src", ImportRule.lab()),
    )
    errors = [error for root, rule in checks for error in scan_tree(root, rule)]

    old_names = ("pokemonbot_core", "pokemonbot_runtime", "pokemonbot_lab", "urn:pokemonbot")
    for pattern in ("packages/**/*.py", "packages/**/pyproject.toml"):
        for path in repository.glob(pattern):
            text = path.read_text(encoding="utf-8")
            for old_name in old_names:
                if old_name in text:
                    errors.append(f"{path.relative_to(repository)}: old name {old_name}")

    if errors:
        print(*sorted(errors), sep="\n", file=sys.stderr)
        return 1
    print("PASS: package import and dependency boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and the repository scan**

Run:

```powershell
uv run pytest tests/tooling/test_architecture.py -v
uv run python tools/check_architecture.py
```

Expected: tests pass and the script prints:

```text
PASS: package import and dependency boundaries
```

- [ ] **Step 5: Commit**

```powershell
git add tools/check_architecture.py tests/tooling/test_architecture.py
git commit -m "test: enforce package architecture boundaries"
```

### Task 8: Turn documentation and archive checks into repository tooling

**Files:**

- Create: `config/docs-authority.json`
- Create: `tools/check_docs.py`
- Create: `tests/tooling/test_docs.py`

- [ ] **Step 1: Write the repository acceptance test**

```python
from pathlib import Path

from tools.check_docs import collect_doc_errors


ROOT = Path(__file__).resolve().parents[2]


def test_repository_documentation_contracts() -> None:
    assert collect_doc_errors(ROOT) == []
```

- [ ] **Step 2: Run it and verify the failure**

Run:

```powershell
uv run pytest tests/tooling/test_docs.py -v
```

Expected: FAIL because `tools.check_docs` does not exist.

- [ ] **Step 3: Add the protected-definition registry**

`config/docs-authority.json`:

```json
{
  "definitions": [
    {
      "id": "m5-planning-estimate",
      "owner": "docs/evaluation/m5-strength-qualification.md",
      "parts": ["planning point estimate ", ">= 72%"]
    },
    {
      "id": "m5-cluster-lower-bound",
      "owner": "docs/evaluation/m5-strength-qualification.md",
      "parts": ["one-sided 95% cluster-CI ", "lower bound >= 70%"]
    },
    {
      "id": "m5-runtime-p95",
      "owner": "docs/evaluation/m5-strength-qualification.md",
      "parts": ["p95-End-to-End-Entscheidungszeit ", "höchstens zwei Sekunden"]
    },
    {
      "id": "m5-fallback-rate",
      "owner": "docs/evaluation/m5-strength-qualification.md",
      "parts": ["Fallback-Entscheidungsrate ", "unter 0,1 Prozent"]
    },
    {
      "id": "package-edge-runtime-core",
      "owner": "docs/architecture/code-boundaries.md",
      "parts": ["battlebelief-runtime ", "──────► battlebelief-core"]
    }
  ]
}
```

- [ ] **Step 4: Implement all documentation gates**

`tools/check_docs.py`:

```python
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
FENCED_CODE = re.compile(r"(?ms)^(`{3,})[^\n]*\n.*?^\1[ \t]*$")
LOCAL_PATH = re.compile(
    r"(?i)(?<![a-z])[a-z]:[\\/]|file://|%3a(?:%2f|/)"
)
OLD_NAMES = re.compile(
    r"(?i)urn:pokemonbot|pokemonbot[-_](?:core|runtime|lab)"
)


def jsonable(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    return value


def has_unclosed_fence(text: str) -> bool:
    opening_length: int | None = None
    for line in text.splitlines():
        match = re.match(r"^(`{3,})", line)
        if match is None:
            continue
        fence_length = len(match.group(1))
        if opening_length is None:
            opening_length = fence_length
        elif fence_length >= opening_length:
            opening_length = None
    return opening_length is not None


def collect_doc_errors(root: Path) -> list[str]:
    errors: list[str] = []
    docs_root = root / "docs"
    schema = json.loads(
        (root / "schemas/documents/frontmatter.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    paths = sorted(
        path
        for path in docs_root.rglob("*.md")
        if "archive" not in path.relative_to(docs_root).parts
    )

    documents: dict[str, tuple[Path, dict[str, Any]]] = {}
    texts: dict[Path, str] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        texts[path] = text
        match = FRONTMATTER.match(text)
        if match is None:
            errors.append(f"{path.relative_to(root)}: missing frontmatter")
            continue
        frontmatter = jsonable(yaml.safe_load(match.group(1)))
        errors.extend(
            f"{path.relative_to(root)} {issue.json_path}: {issue.message}"
            for issue in validator.iter_errors(frontmatter)
        )
        document_id = frontmatter.get("document_id")
        if document_id in documents:
            errors.append(f"duplicate document_id: {document_id}")
        else:
            documents[document_id] = (path, frontmatter)

        if has_unclosed_fence(text):
            errors.append(f"{path.relative_to(root)}: unbalanced code fences")
        prose = FENCED_CODE.sub("", text)
        if LOCAL_PATH.search(prose):
            errors.append(f"{path.relative_to(root)}: local path")
        for link in MARKDOWN_LINK.findall(prose):
            target = link.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"{path.relative_to(root)}: broken link {link}")

    known_ids = set(documents)
    index = (docs_root / "README.md").read_text(encoding="utf-8")
    for document_id, (path, frontmatter) in documents.items():
        for predecessor in frontmatter["supersedes"]:
            if predecessor not in known_ids:
                errors.append(f"{document_id}: unresolved supersedes {predecessor}")
        successor = frontmatter["superseded_by"]
        if successor is not None and successor not in known_ids:
            errors.append(f"{document_id}: unresolved superseded_by {successor}")
        marker = f"[`{document_id}`]"
        if (
            frontmatter["status"] == "accepted"
            and frontmatter["normative"]
            and marker not in index
        ):
            errors.append(f"{document_id}: accepted normative document not indexed")
        if frontmatter["status"] in {"superseded", "archived"} and marker in index:
            errors.append(f"{document_id}: noncurrent document listed as current")
        if (
            frontmatter["status"] == "accepted"
            and frontmatter["normative"]
            and OLD_NAMES.search(texts[path])
        ):
            errors.append(f"{document_id}: old namespace in current normative document")

    authority = json.loads(
        (root / "config/docs-authority.json").read_text(encoding="utf-8")
    )
    for definition in authority["definitions"]:
        literal = "".join(definition["parts"])
        hits = [
            path.relative_to(root).as_posix()
            for path, text in texts.items()
            if literal in text
        ]
        if hits != [definition["owner"]]:
            errors.append(
                f"{definition['id']}: expected {definition['owner']}, got {hits}"
            )

    metadata_path = docs_root / "archive/2026-07-29-design-freeze.metadata.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    snapshot = metadata_path.parent / metadata["snapshot_path"]
    digest = "sha256:" + hashlib.sha256(snapshot.read_bytes()).hexdigest()
    if digest != metadata["source_hash"]:
        errors.append(f"archive hash mismatch: {digest}")

    matrix_path = metadata_path.parent / metadata["migration_matrix"]
    with matrix_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    coverage: list[int] = []
    for row in rows:
        start, end = map(int, row["source_lines"].split("-"))
        coverage.extend(range(start, end + 1))
        target = root / row["target_document"]
        if not target.exists():
            errors.append(f"{row['old_section']}: missing migration target")
        elif f"# {row['target_heading']}" not in target.read_text(
            encoding="utf-8"
        ).splitlines():
            errors.append(f"{row['old_section']}: missing target H1")
        if row["normative_owner"] not in known_ids:
            errors.append(f"{row['old_section']}: missing migration owner")

    expected_coverage = list(
        range(1, len(snapshot.read_text(encoding="utf-8").splitlines()) + 1)
    )
    if coverage != expected_coverage:
        errors.append("migration matrix has gaps, overlaps, or wrong order")
    return sorted(errors)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = collect_doc_errors(root)
    if errors:
        print(*errors, sep="\n", file=sys.stderr)
        return 1
    print("PASS: documentation, authority, links, migration, and archive integrity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

The CLI prints every failure to stderr and returns `1`; otherwise it prints:

```text
PASS: documentation, authority, links, migration, and archive integrity
```

- [ ] **Step 5: Run the acceptance test and CLI**

Run:

```powershell
uv run pytest tests/tooling/test_docs.py -v
uv run python tools/check_docs.py
```

Expected: both exit zero.

- [ ] **Step 6: Commit**

```powershell
git add config/docs-authority.json tools/check_docs.py tests/tooling/test_docs.py
git commit -m "test: automate documentation governance"
```

### Task 9: Validate schemas and canonical manifest hashes

**Files:**

- Create: `tools/canonicalize_manifest.py`
- Create: `tools/check_schemas.py`
- Create: `schemas/canonicalization/test-vectors.json`
- Create: `tests/tooling/test_canonicalization.py`

- [ ] **Step 1: Write the failing canonicalization test**

```python
from tools.canonicalize_manifest import canonicalize, manifest_digest


def test_object_key_order_is_canonical() -> None:
    value = {"b": 1, "a": 2}
    assert canonicalize(value) == b'{"a":2,"b":1}'
    assert manifest_digest(value) == (
        "sha256:d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772"
    )
```

- [ ] **Step 2: Run it and verify the failure**

Run:

```powershell
uv run pytest tests/tooling/test_canonicalization.py -v
```

Expected: FAIL because `tools.canonicalize_manifest` does not exist.

- [ ] **Step 3: Implement canonicalization**

`tools/canonicalize_manifest.py`:

```python
from __future__ import annotations

import hashlib
from typing import Any, cast

import rfc8785


def canonicalize(value: Any) -> bytes:
    return cast(bytes, rfc8785.dumps(value))


def manifest_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonicalize(value)).hexdigest()
```

`schemas/canonicalization/test-vectors.json`:

```json
[
  {
    "name": "object-key-order",
    "value": {"b": 1, "a": 2},
    "canonical_utf8": "{\"a\":2,\"b\":1}",
    "sha256": "d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772"
  }
]
```

- [ ] **Step 4: Implement schema and vector validation**

`tools/check_schemas.py`:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from tools.canonicalize_manifest import canonicalize, manifest_digest


def collect_schema_errors(root: Path) -> list[str]:
    errors: list[str] = []
    schema_root = root / "schemas"
    ids: dict[str, Path] = {}

    for path in sorted(schema_root.rglob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as error:
            errors.append(f"{path.relative_to(root)}: invalid schema: {error}")
            continue
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id.startswith(
            "urn:battlebelief:"
        ):
            errors.append(f"{path.relative_to(root)}: invalid project schema ID")
        elif schema_id in ids:
            errors.append(
                f"{path.relative_to(root)}: duplicate schema ID also in "
                f"{ids[schema_id].relative_to(root)}"
            )
        else:
            ids[schema_id] = path

    for example_path in sorted((schema_root / "examples").glob("*.example.json")):
        name = example_path.name.removesuffix(".example.json")
        schema_path = schema_root / "manifests" / f"{name}.schema.json"
        if not schema_path.exists():
            errors.append(f"{example_path.relative_to(root)}: schema missing")
            continue
        instance = json.loads(example_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors.extend(
            f"{example_path.relative_to(root)} {issue.json_path}: {issue.message}"
            for issue in validator.iter_errors(instance)
        )

    vectors: list[dict[str, Any]] = json.loads(
        (schema_root / "canonicalization/test-vectors.json").read_text(
            encoding="utf-8"
        )
    )
    for vector in vectors:
        actual_bytes = canonicalize(vector["value"])
        expected_bytes = vector["canonical_utf8"].encode("utf-8")
        if actual_bytes != expected_bytes:
            errors.append(f"{vector['name']}: canonical bytes differ")
        actual_digest = manifest_digest(vector["value"])
        if actual_digest != "sha256:" + vector["sha256"]:
            errors.append(f"{vector['name']}: digest differs")
    return sorted(errors)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = collect_schema_errors(root)
    if errors:
        print(*errors, sep="\n", file=sys.stderr)
        return 1
    print("PASS: schemas, examples, IDs, and canonicalization vectors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run schema verification**

Run:

```powershell
uv run pytest tests/tooling/test_canonicalization.py -v
uv run python tools/check_schemas.py
```

Expected: both commands exit zero.

- [ ] **Step 6: Commit**

```powershell
git add tools/canonicalize_manifest.py tools/check_schemas.py schemas/canonicalization/test-vectors.json tests/tooling/test_canonicalization.py
git commit -m "test: validate schemas and canonical hashes"
```

### Task 10: Add contribution and issue provenance forms

**Files:**

- Create: `.github/pull_request_template.md`
- Create: `.github/ISSUE_TEMPLATE/bug.yml`
- Create: `.github/ISSUE_TEMPLATE/engine-divergence.yml`
- Create: `.github/ISSUE_TEMPLATE/research-hypothesis.yml`
- Create: `.github/ISSUE_TEMPLATE/transfer-audit.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`

- [ ] **Step 1: Add the pull-request checklist**

`.github/pull_request_template.md`:

```markdown
## Summary

Describe one coherent change and the contract or issue it implements.

## Verification

- [ ] I ran the focused tests for this change.
- [ ] I ran the repository checks affected by this change.
- [ ] New behavior has a failing-before/passing-after test.

## Source provenance

- [ ] No copied GPL or otherwise incompatible code is included.
- [ ] Algorithms, snippets, and third-party code are identified with licenses.
- [ ] AI-generated code was fully reviewed and tested by the contributor.
- [ ] Data and model artifacts have a provenance manifest.
- [ ] No credentials, cookies, private replays, local user paths, or large artifacts are included.

## Claims

- [ ] This pull request does not describe green CI as a strength, parity, release, or MVP claim.
```

- [ ] **Step 2: Add the bug form**

`.github/ISSUE_TEMPLATE/bug.yml`:

```yaml
name: Bug
description: Report a reproducible correctness or runtime defect
title: "[Bug] "
labels: ["type: bug", "priority: normal"]
body:
  - type: textarea
    id: behavior
    attributes:
      label: Observed behavior
      description: State what happened without including credentials or private replay data.
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected behavior
    validations:
      required: true
  - type: textarea
    id: reproduction
    attributes:
      label: Minimal reproduction
    validations:
      required: true
  - type: input
    id: revision
    attributes:
      label: BattleBelief commit or version
    validations:
      required: true
  - type: dropdown
    id: area
    attributes:
      label: Area
      options: [protocol, belief, engine, search, training, evaluation, teams, packaging]
    validations:
      required: true
```

- [ ] **Step 3: Add the engine-divergence form**

`.github/ISSUE_TEMPLATE/engine-divergence.yml`:

```yaml
name: Engine divergence
description: Record a classified Showdown versus surrogate-engine difference
title: "[Engine divergence] "
labels: ["type: bug", "area: engine", "priority: high"]
body:
  - type: input
    id: showdown
    attributes:
      label: Pokémon Showdown commit
    validations:
      required: true
  - type: input
    id: surrogate
    attributes:
      label: Surrogate engine artifact digest
    validations:
      required: true
  - type: textarea
    id: state
    attributes:
      label: Minimal public fixture or state digest
    validations:
      required: true
  - type: textarea
    id: difference
    attributes:
      label: Observed difference
    validations:
      required: true
  - type: dropdown
    id: classification
    attributes:
      label: Proposed classification
      options: [unclassified, bounded_approximation, unsupported]
    validations:
      required: true
```

- [ ] **Step 4: Add the research and transfer forms**

`.github/ISSUE_TEMPLATE/research-hypothesis.yml`:

```yaml
name: Research hypothesis
description: Propose a falsifiable experiment without changing a sealed holdout
title: "[Research] "
labels: ["type: research", "status: needs-decision"]
body:
  - type: textarea
    id: hypothesis
    attributes:
      label: Falsifiable hypothesis
    validations:
      required: true
  - type: textarea
    id: estimand
    attributes:
      label: Estimand and comparison
    validations:
      required: true
  - type: textarea
    id: data
    attributes:
      label: Development or selection data
      description: A release holdout cannot be proposed as development data.
    validations:
      required: true
  - type: textarea
    id: decision
    attributes:
      label: Precommitted decision rule
    validations:
      required: true
```

`.github/ISSUE_TEMPLATE/transfer-audit.yml`:

```yaml
name: Transfer audit
description: Audit a historical component before any reuse
title: "[Transfer audit] "
labels: ["type: research", "status: needs-decision"]
body:
  - type: input
    id: source
    attributes:
      label: Source repository, file, and commit
    validations:
      required: true
  - type: dropdown
    id: provenance
    attributes:
      label: Intended provenance classification
      options: [copied, modified, ideas-only, clean-implementation]
    validations:
      required: true
  - type: textarea
    id: license
    attributes:
      label: License evidence
    validations:
      required: true
  - type: textarea
    id: assumptions
    attributes:
      label: Removed VGC or Doubles assumptions
    validations:
      required: true
  - type: textarea
    id: tests
    attributes:
      label: New Singles and OU verification
    validations:
      required: true
```

`.github/ISSUE_TEMPLATE/config.yml`:

```yaml
blank_issues_enabled: false
contact_links:
  - name: Private security report
    url: https://github.com/chrismaghuhn/BattleBelief/security/advisories/new
    about: Report credentials or security-sensitive defects privately
```

- [ ] **Step 5: Validate YAML and provenance wording**

Run:

```powershell
uv run python -c "from pathlib import Path; import yaml; [yaml.safe_load(p.read_text(encoding='utf-8')) for p in Path('.github/ISSUE_TEMPLATE').glob('*.yml')]"
rg -n "Source provenance|strength, parity, release, or MVP" .github
```

Expected: YAML loading exits zero and both provenance/claim checks match their
intended templates.

- [ ] **Step 6: Commit**

```powershell
git add .github/ISSUE_TEMPLATE .github/pull_request_template.md
git commit -m "chore: add contribution provenance forms"
```

### Task 11: Add the stable merge-blocking CI workflow

**Files:**

- Create: `.github/workflows/pr.yml`

- [ ] **Step 1: Add the pinned workflow**

`.github/workflows/pr.yml`:

```yaml
name: pull-request

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  quality:
    name: quality-py${{ matrix.python }}
    runs-on: ubuntu-24.04
    strategy:
      fail-fast: false
      matrix:
        python: ["3.12", "3.13", "3.14"]
    steps:
      - name: Check out source
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - name: Set up Python
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: ${{ matrix.python }}
      - name: Install uv
        run: python -m pip install uv==0.12.0
      - name: Sync locked workspace
        run: uv sync --frozen --all-packages --group dev
      - name: Test
        run: uv run pytest
      - name: Ruff format
        run: uv run ruff format --check .
      - name: Ruff lint
        run: uv run ruff check .
      - name: Mypy
        run: uv run mypy
      - name: Repository contracts
        run: |
          uv run python tools/check_versions.py
          uv run python tools/check_architecture.py
          uv run python tools/check_docs.py
          uv run python tools/check_schemas.py

  package-smoke:
    name: package-smoke-${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: ubuntu-24.04
            python: "3.14"
          - os: windows-2025
            python: "3.14"
    runs-on: ${{ matrix.os }}
    steps:
      - name: Check out source
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - name: Set up Python
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: ${{ matrix.python }}
      - name: Install uv
        run: python -m pip install uv==0.12.0
      - name: Run isolated wheel smokes
        run: python tools/smoke_packages.py

  dependency-review:
    name: dependency-review
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-24.04
    steps:
      - name: Review dependency changes
        uses: actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0
        with:
          fail-on-severity: moderate
          deny-licenses: GPL-2.0, GPL-3.0, AGPL-3.0

  pr-gate:
    name: pr-gate
    if: always()
    needs: [quality, package-smoke, dependency-review]
    runs-on: ubuntu-24.04
    steps:
      - name: Evaluate required jobs
        env:
          QUALITY: ${{ needs.quality.result }}
          PACKAGE_SMOKE: ${{ needs.package-smoke.result }}
          DEPENDENCY_REVIEW: ${{ needs.dependency-review.result }}
        shell: bash
        run: |
          for result in "$QUALITY" "$PACKAGE_SMOKE" "$DEPENDENCY_REVIEW"; do
            case "$result" in
              success|skipped) ;;
              *) echo "Required job result: $result"; exit 1 ;;
            esac
          done
```

- [ ] **Step 2: Validate local equivalents before pushing**

Run:

```powershell
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run python tools/check_versions.py
uv run python tools/check_architecture.py
uv run python tools/check_docs.py
uv run python tools/check_schemas.py
uv run python tools/smoke_packages.py
```

Expected: every command exits zero.

- [ ] **Step 3: Commit and push the feature branch**

Run:

```powershell
git add .github/workflows/pr.yml
git commit -m "ci: add stable pull request gate"
git push -u origin feat/m0-foundation
```

- [ ] **Step 4: Open the first M0 pull request**

Run:

```powershell
gh pr create --base main --head feat/m0-foundation --draft `
  --title "chore: establish BattleBelief M0 foundation" `
  --body "Implements the approved M0 package, validation, provenance, and CI foundation. This PR makes no battle, engine, strength, parity, release, or MVP claim."
```

Expected: a draft pull request whose `quality`, `package-smoke`,
`dependency-review`, and `pr-gate` checks all execute. Do not configure
`pr-gate` as required until this workflow has produced the exact check context
at least once.

### Task 12: Configure dependency updates, repository security, and protection

**Files:**

- Create: `.github/dependabot.yml`
- Create: `.github/repository-settings.json`
- Create: `.github/codeql-default-setup.json`
- Create: `.github/rulesets/protected-tags-creation.json`
- Create: `.github/rulesets/protected-tags-immutable.json`

- [ ] **Step 1: Add Dependabot for the uv workspace and GitHub Actions**

`.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    schedule:
      interval: weekly
      day: monday
      time: "06:00"
      timezone: Europe/Berlin
    open-pull-requests-limit: 5
    labels: ["type: dependencies"]
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
      day: monday
      time: "06:30"
      timezone: Europe/Berlin
    open-pull-requests-limit: 5
    labels: ["type: dependencies"]
```

- [ ] **Step 2: Add auditable GitHub configuration payloads**

`.github/repository-settings.json`:

```json
{
  "allow_merge_commit": false,
  "allow_rebase_merge": true,
  "allow_squash_merge": true,
  "delete_branch_on_merge": true,
  "security_and_analysis": {
    "secret_scanning": {"status": "enabled"},
    "secret_scanning_push_protection": {"status": "enabled"}
  }
}
```

`.github/codeql-default-setup.json`:

```json
{
  "state": "configured",
  "runner_type": "standard",
  "query_suite": "default",
  "threat_model": "remote",
  "languages": ["python"]
}
```

`.github/rulesets/protected-tags-creation.json`:

```json
{
  "name": "protected-tags-creation-gate",
  "target": "tag",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": [
        "refs/tags/v*",
        "refs/tags/eval-*",
        "refs/tags/claim-*"
      ],
      "exclude": []
    }
  },
  "rules": [{"type": "creation"}]
}
```

`.github/rulesets/protected-tags-immutable.json`:

```json
{
  "name": "protected-tags-immutable",
  "target": "tag",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": [
        "refs/tags/v*",
        "refs/tags/eval-*",
        "refs/tags/claim-*"
      ],
      "exclude": []
    }
  },
  "rules": [
    {"type": "update"},
    {"type": "deletion"},
    {"type": "non_fast_forward"}
  ]
}
```

The creation gate intentionally blocks every protected tag during M0 because
no release actor exists yet. A later release ADR may add a narrowly scoped
release actor to that gate. The immutable ruleset remains without bypass.
Repository administrators can still edit repository rulesets; the contract
therefore promises audited protection, not protection against a malicious
repository administrator.

- [ ] **Step 3: Validate and commit the configuration**

Run:

```powershell
uv run python -c "from pathlib import Path; import json, yaml; [json.loads(p.read_text(encoding='utf-8')) for p in Path('.github').rglob('*.json')]; yaml.safe_load(Path('.github/dependabot.yml').read_text(encoding='utf-8'))"
git add .github/dependabot.yml .github/repository-settings.json .github/codeql-default-setup.json .github/rulesets
git commit -m "chore: define repository protection settings"
git push
gh pr checks --watch
```

Expected: all JSON and YAML parse, the commit is included in the open M0 pull
request, and `pr-gate` completes successfully. Do not continue until the exact
`pr-gate` context has appeared on that pull request.

- [ ] **Step 4: Verify public visibility and create the referenced labels**

Run:

```powershell
gh repo view chrismaghuhn/BattleBelief --json visibility,nameWithOwner
gh label create "type: bug" --color D73A4A --description "Correctness or runtime defect" --force
gh label create "type: research" --color 5319E7 --description "Research question or experiment" --force
gh label create "type: dependencies" --color 0366D6 --description "Dependency update" --force
gh label create "priority: normal" --color C5DEF5 --description "Normal project priority" --force
gh label create "priority: high" --color B60205 --description "High project priority" --force
gh label create "area: engine" --color F9D0C4 --description "Battle-engine compatibility" --force
gh label create "status: needs-decision" --color FBCA04 --description "Maintainer decision required" --force
```

Expected: visibility is `PUBLIC`, and every label used by an issue form or
Dependabot exists. If visibility is not public, stop and obtain explicit
approval before changing it.

- [ ] **Step 5: Apply repository and security settings**

Run:

```powershell
gh api --method PATCH repos/chrismaghuhn/BattleBelief `
  --input .github/repository-settings.json --silent
gh api --method PUT `
  repos/chrismaghuhn/BattleBelief/private-vulnerability-reporting --silent
gh api repos/chrismaghuhn/BattleBelief `
  --jq '{allow_merge_commit,allow_rebase_merge,allow_squash_merge,delete_branch_on_merge,security_and_analysis}'
```

Expected: the first two requests return successfully; the final response shows
squash and rebase enabled, merge commits disabled, merged-branch deletion
enabled, and both secret-scanning controls enabled. Verify in the repository
Security settings that the dependency graph is enabled before relying on the
dependency-review job.

- [ ] **Step 6: Configure the default-branch ruleset in the GitHub UI**

Open repository **Settings → Rules → Rulesets → New branch ruleset** and use
these exact settings:

```text
Name: default-branch-pr-gate
Enforcement: Active
Target: Default branch
Bypass list: Repository administrators — For pull requests only

Rules:
- Restrict deletions
- Block force pushes
- Require linear history
- Require a pull request before merging
  - Required approvals: 0
  - Require conversation resolution: enabled
  - Allowed merge methods: squash, rebase
- Require status checks to pass
  - Required check: pr-gate
  - Require branches to be up to date before merging: enabled
```

Do not enter a hard-coded API `actor_id` for repository administrators. GitHub
does not document that role ID as a stable public constant. The pull-request-
only bypass is the audited break-glass recovery path and is not used for normal
development or any release or strength claim.

Verify the saved ruleset:

```powershell
$battleBeliefRulesetId = gh api repos/chrismaghuhn/BattleBelief/rulesets `
  --jq '.[] | select(.name=="default-branch-pr-gate") | .id'
gh api "repos/chrismaghuhn/BattleBelief/rulesets/$battleBeliefRulesetId"
```

Expected: exactly one active default-branch ruleset exists, it requires the
observed `pr-gate` context, and its bypass entry is pull-request-only.

- [ ] **Step 7: Apply the two protected-tag rulesets**

Run:

```powershell
gh api --method POST repos/chrismaghuhn/BattleBelief/rulesets `
  --input .github/rulesets/protected-tags-creation.json --silent
gh api --method POST repos/chrismaghuhn/BattleBelief/rulesets `
  --input .github/rulesets/protected-tags-immutable.json --silent
gh api repos/chrismaghuhn/BattleBelief/rulesets `
  --jq '.[] | select(.target=="tag") | {name,enforcement,target}'
```

Expected: both active tag rulesets are listed. Do not create a release,
evaluation, or claim tag in M0 merely to test the block.

- [ ] **Step 8: Make the M0 pull request ready and merge normally**

Run:

```powershell
gh pr ready
gh pr checks --watch
gh pr merge --squash --delete-branch
git switch main
git pull --ff-only
```

Expected: the PR merges only after `pr-gate` succeeds, `main` advances by a
squash commit, and the feature branch is deleted. Do not use the break-glass
bypass.

- [ ] **Step 9: Enable and verify CodeQL Default Setup on merged M0 code**

Run:

```powershell
gh api --method PATCH `
  repos/chrismaghuhn/BattleBelief/code-scanning/default-setup `
  --input .github/codeql-default-setup.json --silent
gh api repos/chrismaghuhn/BattleBelief/code-scanning/default-setup
```

Expected: state is `configured`, the query suite is `default`, and Python is
listed. Re-audit language coverage when Rust, Node, generated code, or new
GitHub Actions behavior enters the repository; M0 claims Python coverage only.

### Task 13: Prove the protected-main workflow and close M0

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Create the proof branch and write the failing status assertion**

Run:

```powershell
git switch -c docs/m0-proof
rg -n "M0 repository foundation complete" README.md
```

Expected: no match because the bootstrap README still says the foundation is
in progress.

- [ ] **Step 2: Update only the root README status**

Replace the root README status block with:

```markdown
> **Status:** M0 repository foundation complete. Battle play, search,
> training, and strength claims are not implemented.
```

Do not describe this as an MVP, strength, parity, engine, or release claim.

- [ ] **Step 3: Run the complete local M0 acceptance suite**

Run:

```powershell
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run python tools/check_versions.py
uv run python tools/check_architecture.py
uv run python tools/check_docs.py
uv run python tools/check_schemas.py
uv run python tools/smoke_packages.py
rg -n "M0 repository foundation complete" README.md
```

Expected: every command exits zero and the final command finds exactly the new
status block.

- [ ] **Step 4: Commit, open the proof PR, and merge through `pr-gate`**

Run:

```powershell
git add README.md
git commit -m "docs: record M0 foundation proof"
git push -u origin docs/m0-proof
gh pr create --base main --head docs/m0-proof `
  --title "docs: record M0 foundation proof" `
  --body "Records repository-foundation completion after the protected pull-request path was exercised. This is not a battle, engine, strength, parity, release, or MVP claim."
gh pr checks --watch
gh pr merge --squash --delete-branch
git switch main
git pull --ff-only
```

Expected: direct integration is not used; the second PR passes the required
check and merges normally.

- [ ] **Step 5: Verify the final M0 evidence and absence of claims**

Run:

```powershell
git status --short
git log -3 --oneline
gh api repos/chrismaghuhn/BattleBelief/rulesets `
  --jq '.[] | {name,target,enforcement}'
gh api repos/chrismaghuhn/BattleBelief/code-scanning/default-setup `
  --jq '{state,languages,query_suite}'
git ls-remote --tags origin
gh release list
```

Expected:

- the worktree is clean;
- the two M0 pull-request squash commits are on `main`;
- the active branch and two tag rulesets are present;
- CodeQL Default Setup is configured for Python;
- no tag and no GitHub release exists;
- no package or model artifact has been published.

- [ ] **Step 6: Record the evidence in the M0 pull requests**

Add a short comment to each merged M0 PR containing only:

```text
M0 repository-foundation evidence:
- required pr-gate passed
- package and documentation contracts passed
- protected-main workflow verified
- no battle, engine, strength, parity, release, or MVP claim
```

This is operational evidence, not a normative document and not a release
manifest.

## Verified implementation references

- [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/)
- [uv in Dependabot](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference#package-ecosystem-)
- [Repository rulesets API](https://docs.github.com/en/rest/repos/rules)
- [Ruleset bypass permissions](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository#granting-bypass-permissions-for-your-branch-or-tag-ruleset)
- [Required status-check behavior](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)
- [`GITHUB_TOKEN` permissions](https://docs.github.com/actions/security-for-github-actions/security-guides/automatic-token-authentication)
- [Secure use of GitHub Actions](https://docs.github.com/en/actions/reference/security/secure-use)
- [Secret scanning and push protection](https://docs.github.com/code-security/secret-scanning/about-secret-scanning)
- [Private vulnerability reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository)
- [CodeQL Default Setup API](https://docs.github.com/en/rest/code-scanning/code-scanning)
- [Dependency review action](https://github.com/actions/dependency-review-action)
- [Checkout action releases](https://github.com/actions/checkout/releases)
- [Setup Python action releases](https://github.com/actions/setup-python/releases)
