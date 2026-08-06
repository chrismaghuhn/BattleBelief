---
document_id: plan-task-25-v1-verifier-provenance
title: Task 25 v1 Verifier and Provenance Boundary Implementation Plan
document_type: roadmap
status: accepted
normative: false
version: 1
applies_to:
  - repository
  - gen9ou
  - release
effective_from: 2026-08-06
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-06
---

# Task 25 v1 Verifier and Provenance Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make staged source verification unskippable, add a release-only wheel-manifest verifier, and document the honest Windows provenance boundary of the immutable v1 artifacts.

**Architecture:** The staging CLI keeps ownership of checkout closure and makes `--checkout` mandatory. A new release-only CLI reuses the manifest-and-wheel comparison logic but exposes no checkout option or source-verification claim; the immutable-release workflow calls it for each published wheel. ADR-0005 records the v1 evidence boundary without changing the published release or existing schemas.

**Tech Stack:** Python 3.12+, `argparse`, JSON Schema 2020-12, BattleBelief canonicalization, wheel ZIP/RECORD inspection, pytest, GitHub Actions YAML, Markdown governance.

---

### Task 1: Lock the staged verifier to a real checkout

**Files:**
- Modify: `tests/tooling/test_verify_poke_engine_artifact.py`
- Modify: `tools/verify_poke_engine_artifact.py`

- [ ] **Step 1: Add a missing-checkout regression test**

Add a test that calls `main` with the three manifest/wheel arguments but no
`--checkout` and asserts `argparse` raises `SystemExit` with code `2`:

```python
def test_staging_cli_requires_checkout() -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--source-manifest", "source.json",
                "--build-manifest", "build.json",
                "--wheel", "wheel.whl",
            ]
        )
    assert error.value.code == 2
```

- [ ] **Step 2: Add a wrong-checkout regression test**

Use the committed source and Windows CPython 3.14 build manifests with an
empty temporary checkout. Pass an unused wheel path because checkout closure
must fail before wheel inspection, then assert `main(...) == 1` and stderr
contains the stable source-checkout failure.

- [ ] **Step 3: Run the focused tests and observe the missing-checkout failure**

Run:

```powershell
uv run pytest tests/tooling/test_verify_poke_engine_artifact.py -q
```

Expected: the missing-checkout test fails because `--checkout` is still
optional; the malformed-input tests and wrong-checkout test pass.

- [ ] **Step 4: Require and always verify `--checkout`**

Change the parser declaration and conditional call to:

```python
parser.add_argument("--checkout", type=Path, required=True)
...
verify_source_checkout(args.checkout, source)
```

Keep source checkout verification before wheel inspection.

- [ ] **Step 5: Run the focused tests**

Run:

```powershell
uv run pytest tests/tooling/test_verify_poke_engine_artifact.py -q
```

Expected: all tests pass.

### Task 2: Add the published-wheel-manifest evidence path

**Files:**
- Create: `tools/verify_published_wheel_manifest.py`
- Create: `tests/tooling/test_verify_published_wheel_manifest.py`
- Modify: `tools/verify_poke_engine_artifact.py`

- [ ] **Step 1: Add valid published-wheel fixture construction**

Create a minimal valid Windows CPython 3.14 wheel ZIP with `METADATA`,
`WHEEL`, and a closed `RECORD`. Load the committed v1 source and corresponding
build manifests, replace only the build manifest's `wheel` object with the
result of `inspect_wheel`, and write the build manifest in canonical form.

- [ ] **Step 2: Add three release-verifier regression tests**

Test the future `verify_published_wheel_manifest` function for:

```python
verify_published_wheel_manifest(
    source_manifest_path=source_path,
    build_manifest_path=build_path,
    wheel_path=wheel_path,
)
```

The valid fixture must pass without any checkout. Flipping a wheel byte must
raise the release verifier's stable exception. Replacing the canonical build
manifest wheel digest with `sha256:` plus 64 zeroes must also raise.

- [ ] **Step 3: Run the new tests and observe the absent module**

Run:

```powershell
uv run pytest tests/tooling/test_verify_published_wheel_manifest.py -q
```

Expected: collection fails because
`tools.verify_published_wheel_manifest` does not exist.

- [ ] **Step 4: Extract the shared manifested-wheel comparison**

In `tools/verify_poke_engine_artifact.py`, expose a function that accepts
already loaded source/build mappings plus a wheel path, validates the pinned
source manifest and source-manifest digest, derives expected Python/ABI/
platform tags, calls `inspect_wheel`, and requires exact equality with the
manifest's `wheel` object. Keep checkout verification exclusively in the
staging `main` function.

- [ ] **Step 5: Implement the release-only verifier**

Create a CLI with exactly these required arguments:

```python
parser.add_argument("--source-manifest", type=Path, required=True)
parser.add_argument("--build-manifest", type=Path, required=True)
parser.add_argument("--wheel", type=Path, required=True)
```

Load both canonical schema-valid manifests, call the shared manifested-wheel
comparison, and print only release-manifest-scoped success fields such as:

```text
published_wheel_manifest_digest=<digest>
published_wheel_sha256=<digest>
```

Do not accept a checkout parameter and do not print source-checkout or build-
environment verification claims.

- [ ] **Step 6: Run both verifier suites**

Run:

```powershell
uv run pytest tests/tooling/test_verify_poke_engine_artifact.py tests/tooling/test_verify_published_wheel_manifest.py -q
```

Expected: all tests pass.

### Task 3: Route release closure through the distinct verifier

**Files:**
- Modify: `.github/workflows/pr.yml`
- Modify: `tests/tooling/test_pr_workflow.py`

- [ ] **Step 1: Add workflow boundary assertions**

Extend the artifact-index workflow test to assert that its per-wheel step
contains `tools/verify_published_wheel_manifest.py`, does not contain
`tools/verify_poke_engine_artifact.py`, and does not contain `--checkout`.
Also assert the artifact-build staging step continues to invoke
`tools/verify_poke_engine_artifact.py` with `--checkout`.

- [ ] **Step 2: Run the focused workflow test and observe failure**

Run:

```powershell
uv run pytest tests/tooling/test_pr_workflow.py -q
```

Expected: the release-boundary assertion fails because CI still invokes the
staging verifier for published wheels.

- [ ] **Step 3: Replace the release-loop command**

Rename the per-wheel step to `Verify every published wheel manifest without
native import` and replace only its tool path with
`tools/verify_published_wheel_manifest.py`. Preserve the source manifest,
build manifest, and wheel arguments; do not add a checkout.

- [ ] **Step 4: Run workflow tests**

Run:

```powershell
uv run pytest tests/tooling/test_pr_workflow.py -q
```

Expected: all tests pass.

### Task 4: Record the accepted v1 Windows provenance boundary

**Files:**
- Create: `docs/adr/ADR-0005-task-25-v1-windows-provenance-boundary.md`
- Modify: `docs/README.md`
- Modify: `artifacts/gen9ou/m2/engine/README.md`

- [ ] **Step 1: Write accepted ADR-0005**

Use accepted, non-normative ADR frontmatter. State that v1 guarantees
immutable artifact identity, digest binding, the v1-manifested controlled
inputs, and behavioral six-cell rebuild evidence. State that v1 does not bind
the complete original Windows environment, including exact Visual Studio/MSVC
toolset, Windows SDK, `link.exe`, and runner image.

Clarify that "no ambient build overrides" means no override of explicitly
controlled build parameters, not fully pinned native Windows discovery.
Reject retrospective reconstruction and defer full toolchain binding to a
future v2 schema and regular artifact generation.

- [ ] **Step 2: Link the single decision owner**

Add ADR-0005 to the explanatory-decision list in `docs/README.md`. Update the
artifact README with a concise v1 limitation and a link to ADR-0005 instead of
duplicating the full decision.

- [ ] **Step 3: Run documentation governance checks**

Run the repository's documented documentation commands from the PR workflow,
including frontmatter validation, link checking, and prohibited-placeholder
checking.

Expected: all checks pass and the immutable archive remains unchanged.

### Task 5: Validate and publish the PR-head correction

**Files:**
- Modify externally: PR #36 description

- [ ] **Step 1: Run focused tooling validation**

Run Ruff on the modified Python files and tests, then run the four focused
tooling suites:

```powershell
uv run ruff check tools/verify_poke_engine_artifact.py tools/verify_published_wheel_manifest.py tests/tooling/test_verify_poke_engine_artifact.py tests/tooling/test_verify_published_wheel_manifest.py tests/tooling/test_pr_workflow.py
uv run pytest tests/tooling/test_verify_poke_engine_artifact.py tests/tooling/test_verify_published_wheel_manifest.py tests/tooling/test_verify_published_engine_release.py tests/tooling/test_pr_workflow.py -q
```

Expected: Ruff and all focused tests pass.

- [ ] **Step 2: Run every repository gate defined by the current PR workflow**

Execute the repository's formatting, linting, typing, unit/package,
architecture, documentation, schema, canonicalization, packaging, version,
security, and dependency checks exactly as defined by current configuration.
Record any platform-only checks that cannot run locally.

- [ ] **Step 3: Inspect the complete diff and immutable-release boundary**

Confirm no file under the release bundle was changed, no wheel was added, the
artifact build job and `tools/build_poke_engine_wheel.py` remain unchanged,
and the diff contains no secrets, local paths, generated artifacts, or
unrelated edits.

- [ ] **Step 4: Commit and push the focused changes**

Create focused commits describing the verifier split and provenance decision,
then push the existing feature branch without force.

- [ ] **Step 5: Correct the PR description**

Replace the broad "no ambient build overrides" claim with the ADR-0005
boundary: controlled manifest parameters have no ambient overrides, while v1
does not claim a completely pinned or reconstructible MSVC/SDK/linker/runner
environment. Keep PR #36 Draft.

- [ ] **Step 6: Re-run and inspect hosted checks**

Wait for the complete PR workflow and CodeQL on the new head. Report exact run
results, keep the PR Draft, and do not merge it.
