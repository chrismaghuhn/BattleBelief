---
document_id: plan-task-25-staging-and-runtime-hardening
title: Task 25 Staging Closure and Runtime Failure Hardening Implementation Plan
document_type: roadmap
status: accepted
normative: false
version: 1
applies_to:
  - repository
  - gen9ou
  - release
  - runtime
effective_from: 2026-08-06
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-06
---

# Task 25 Staging Closure and Runtime Failure Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two sanitized-runtime P2 gaps and add the exact fail-closed staging wheelhouse acceptance boundary approved for P3 without altering the immutable v1 release evidence.

**Architecture:** Runtime parsing, digesting, and expected-path resolution remain inside the existing `poke_engine` adapter and translate failures to the established stable `EngineFailureClass` values. The staging CLI gains one pre-manifest wheelhouse-closure guard based only on `--wheel`; the builder, frozen `artifact-build` job, and release-only verifier do not change. ADR-0005 and the PR body record that the new guard protects future staging runs but did not run retroactively during the original v1 build.

**Tech Stack:** Python 3.12-3.14, pathlib/lstat, JSON, pytest, uv, Ruff, mypy, GitHub Actions, GitHub CLI.

---

### Task 1: Sanitize sentinel fixture and native-import failures

**Files:**
- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/native_probe.py`
- Test: `packages/battlebelief-runtime/tests/adapters/poke_engine/test_native_probe.py`

- [ ] **Step 1: Add failing non-finite fixture tests**

Add `shutil`, import the `native_probe` module for monkeypatching, and add a helper that copies the three fixture files into `tmp_path`. Add this parametrized test:

```python
@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_fixture_nonfinite_constants_are_sentinel_failed(
    tmp_path: Path, constant: str
) -> None:
    fixture_root = _copied_fixtures(tmp_path)
    transition = fixture_root / "gen9_transition.json"
    transition.write_text(
        transition.read_text(encoding="utf-8").replace('"hp": 120', f'"hp": {constant}', 1),
        encoding="utf-8",
    )

    with pytest.raises(EngineArtifactError) as caught:
        load_fixture_bundle(fixture_root)

    assert caught.value.failure_class is EngineFailureClass.SENTINEL_FAILED
    assert str(caught.value) == "sentinel_failed"
    assert str(tmp_path) not in str(caught.value)
```

- [ ] **Step 2: Run the non-finite tests and verify the intended red failure**

Run:

```powershell
uv run pytest packages/battlebelief-runtime/tests/adapters/poke_engine/test_native_probe.py -q --basetemp=.tmp/pytest-native-red -p no:cacheprovider
```

Expected: the three new cases fail because `json.loads` accepts the constants and canonicalization raises a raw finite-domain `ValueError` subclass.

- [ ] **Step 3: Reject non-finite constants and guard fixture digest calculation**

Add a parser callback that calls `_fail(EngineFailureClass.SENTINEL_FAILED)` and pass it as `parse_constant`:

```python
def reject_nonfinite(_value: str) -> NoReturn:
    _fail(EngineFailureClass.SENTINEL_FAILED)

value = json.loads(
    path.read_bytes(),
    object_pairs_hook=reject_duplicates,
    parse_constant=reject_nonfinite,
)
```

Guard both digest calculations before constructing `FixtureBundle`:

```python
try:
    fixture_digest = manifest_digest(fixture_document)
    configuration_digest = manifest_digest(search)
except (TypeError, ValueError):
    _fail(EngineFailureClass.SENTINEL_FAILED)
```

Use the two local digest variables in the returned dataclass.

- [ ] **Step 4: Add and run a digest-conversion regression test**

Monkeypatch `native_probe.manifest_digest` to raise `ValueError` containing a private path, call `load_fixture_bundle(FIXTURE_ROOT)`, and assert only `sentinel_failed` escapes. Run the whole `test_native_probe.py` file and expect all cases to pass.

- [ ] **Step 5: Add a failing expected-native-path resolution test**

Create real expected package and extension files under `tmp_path`. Monkeypatch
`native_probe.importlib.import_module` to return objects whose `__file__`
attributes point at those files. Monkeypatch `Path.resolve` so the first
resolution of `package_root / "__init__.py"` succeeds and the second raises
`PermissionError("private native path")`. Add path-and-occurrence cases that
raise a path-bearing `RuntimeError` from the actual and expected package and
extension resolutions. Call `_import_verified_native(verified)` and assert:

```python
assert caught.value.failure_class is EngineFailureClass.IMPORT_FAILED
assert str(caught.value) == "import_failed"
assert "private" not in str(caught.value)
assert str(tmp_path) not in str(caught.value)
```

- [ ] **Step 6: Run the path test and verify the intended raw failure**

Run only the new test. Expected: raw `PermissionError` escapes from the second, expected-path `resolve(strict=True)`.

- [ ] **Step 7: Resolve actual and expected native paths in one guarded block**

Move both expected resolutions into the existing `try`:

```python
try:
    package_path = Path(package_origin).resolve(strict=True)
    extension_path = Path(extension_origin).resolve(strict=True)
    expected_package_path = (verified.package_root / "__init__.py").resolve(strict=True)
    expected_extension_path = verified.extension_path.resolve(strict=True)
except (OSError, RuntimeError, TypeError):
    _fail(EngineFailureClass.IMPORT_FAILED)
if package_path != expected_package_path or extension_path != expected_extension_path:
    _fail(EngineFailureClass.IMPORT_FAILED)
```

- [ ] **Step 8: Run the complete native-probe test file**

Run the command from Step 2 with a fresh basetemp. Expected: all native-probe tests pass.

### Task 2: Sanitize installed-artifact path resolution failures

**Files:**
- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/artifact.py`
- Test: `packages/battlebelief-runtime/tests/adapters/poke_engine/test_artifact.py`

- [ ] **Step 1: Add a failing second-resolution regression test**

Use `_installation(tmp_path)` and `monkeypatch.syspath_prepend(str(site))`.
Wrap `PathFinder.find_spec` to set a flag, then wrap `Path.resolve`; after the
spec lookup, allow the first resolution of
`site / "poke_engine" / "__init__.py"` and raise either
`PermissionError("private installed path")` or a path-bearing `RuntimeError`
for a CPython 3.12 symlink loop on the second. Call
`verify_installed_artifact(...)` and assert:

```python
assert caught.value.failure_class is EngineFailureClass.ARTIFACT_MISMATCH
assert str(caught.value) == "artifact_mismatch"
assert "private" not in str(caught.value)
assert str(tmp_path) not in str(caught.value)
```

- [ ] **Step 2: Run the new test and verify the intended red failure**

Run:

```powershell
uv run pytest packages/battlebelief-runtime/tests/adapters/poke_engine/test_artifact.py::test_expected_package_resolve_error_is_sanitized -q --basetemp=.tmp/pytest-artifact-red -p no:cacheprovider
```

Expected: raw `PermissionError` escapes from `expected_package.resolve(strict=True)`.

- [ ] **Step 3: Resolve the expected installed-package path inside the existing guard**

Change the final origin check to:

```python
try:
    origin = Path(spec.origin).resolve(strict=True)
    expected_origin = expected_package.resolve(strict=True)
except (OSError, RuntimeError):
    _fail(EngineFailureClass.ARTIFACT_MISMATCH)
if origin != expected_origin:
    _fail(EngineFailureClass.ARTIFACT_MISMATCH)
```

- [ ] **Step 4: Run the complete artifact test file**

Run the artifact test file with a fresh workspace-local basetemp. Expected: all artifact tests pass.

- [ ] **Step 5: Add failing RuntimeError regressions for the remaining Artifact paths**

Add one focused regression each for `_distribution_root_and_info`,
`_installed_path`, and the staged path branch of `_verify_direct_url`.
Monkeypatch `Path.resolve` to raise a path-bearing `RuntimeError` at the named
boundary. Each test must initially demonstrate the raw exception and then
require only `EngineArtifactError(ARTIFACT_MISMATCH)` with the exact public
message `artifact_mismatch`; neither the private exception text nor the
workspace path may escape.

- [ ] **Step 6: Close all three RuntimeError exception boundaries**

Extend only the existing exception tuples:

```python
# _distribution_root_and_info
except (OSError, RuntimeError):

# _installed_path
except (OSError, RuntimeError, ValueError):

# staged _verify_direct_url
except (OSError, RuntimeError):
```

Run the three focused regressions and then the complete artifact test file.
Expected: every case passes with stable, path-free `artifact_mismatch` output.

### Task 3: Enforce exact staged wheelhouse closure

**Files:**
- Modify: `tools/verify_poke_engine_artifact.py`
- Test: `tests/tooling/test_verify_poke_engine_artifact.py`
- Must not modify: `tools/build_poke_engine_wheel.py`
- Must not modify: `tools/verify_published_wheel_manifest.py`
- Must not modify: `.github/workflows/pr.yml`

- [ ] **Step 1: Add failing direct closure tests**

Import the new `verify_staged_wheelhouse` helper. Add a success test with one regular wheel, then parametrized failures for an extra regular file and an extra directory. Every failure must match exactly `staged wheelhouse closure differs`.

```python
def test_staged_wheelhouse_accepts_only_expected_regular_wheel(tmp_path: Path) -> None:
    wheel = tmp_path / "poke_engine-0.0.48-cp314-none-win_amd64.whl"
    wheel.write_bytes(b"wheel")
    verify_staged_wheelhouse(wheel)

@pytest.mark.parametrize("extra_kind", ["file", "directory"])
def test_staged_wheelhouse_rejects_extra_entry(tmp_path: Path, extra_kind: str) -> None:
    wheel = tmp_path / "poke_engine-0.0.48-cp314-none-win_amd64.whl"
    wheel.write_bytes(b"wheel")
    extra = tmp_path / "extra"
    extra.write_bytes(b"extra") if extra_kind == "file" else extra.mkdir()
    with pytest.raises(ArtifactVerificationError, match="^staged wheelhouse closure differs$"):
        verify_staged_wheelhouse(wheel)
```

- [ ] **Step 2: Add link, reparse, containment, and ordering tests**

Add real-symlink tests for an expected wheel pointing outside, an additional symlink, and a linked wheelhouse. If Windows does not permit symlink creation, skip only that filesystem-specific case. Add simulated reparse tests by monkeypatching the classifier for the wheel and wheelhouse so junction/reparse rejection is covered without privileges.

Add a CLI ordering test that creates a wheelhouse with an extra file, monkeypatches `_canonical_document`, `verify_source_checkout`, and `inspect_wheel` to fail if called, invokes `main`, and asserts the sole stderr line is `staged wheelhouse closure differs`.

Update existing CLI tests so their wheelhouse contains exactly the supplied wheel before they exercise checkout or manifest-binding behavior.

- [ ] **Step 3: Run the tooling tests and verify the intended red failures**

Run:

```powershell
uv run pytest tests/tooling/test_verify_poke_engine_artifact.py -q --basetemp=.tmp/pytest-staging-red -p no:cacheprovider
```

Expected: new tests fail because no wheelhouse guard exists and the CLI reaches later verification stages.

- [ ] **Step 4: Implement non-following link/reparse classification**

Import `os` and `stat`. Implement a helper that treats a non-following `lstat` symlink mode, `FILE_ATTRIBUTE_REPARSE_POINT`, or `Path.is_junction()` as linked/reparse state. Any `OSError` from metadata or junction inspection must be caught by the closure boundary.

```python
def _is_link_or_reparse(path: Path, metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    if bool(reparse_flag and attributes & reparse_flag):
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())
```

- [ ] **Step 5: Implement the exact immediate closure guard**

Implement `verify_staged_wheelhouse(wheel_path: Path) -> None` using `wheel_path.parent`, `lstat`, `iterdir`, lexical `os.path.abspath` plus `os.path.normcase` comparison, and regular-file mode checks. Wrap all filesystem operations in `try/except OSError`; every negative branch calls `_fail("staged wheelhouse closure differs")`.

The accepted sequence is:

```python
wheelhouse = wheel_path.parent
wheelhouse_metadata = wheelhouse.lstat()
if not stat.S_ISDIR(wheelhouse_metadata.st_mode) or _is_link_or_reparse(
    wheelhouse, wheelhouse_metadata
):
    _fail("staged wheelhouse closure differs")
entries = list(wheelhouse.iterdir())
if len(entries) != 1:
    _fail("staged wheelhouse closure differs")
entry = entries[0]
if os.path.normcase(os.path.abspath(entry)) != os.path.normcase(os.path.abspath(wheel_path)):
    _fail("staged wheelhouse closure differs")
entry_metadata = entry.lstat()
if not stat.S_ISREG(entry_metadata.st_mode) or _is_link_or_reparse(entry, entry_metadata):
    _fail("staged wheelhouse closure differs")
```

- [ ] **Step 6: Make closure the first staging acceptance operation**

Inside `main`, call `verify_staged_wheelhouse(args.wheel)` as the first statement in the verification `try`, before `_canonical_document` for either manifest. Do not add any call to the release-only verifier.

- [ ] **Step 7: Run the complete staging-verifier test file**

Run the command from Step 3 with a fresh basetemp. Expected: all tests pass with stable, path-free errors.

### Task 4: Record the non-retroactive staging boundary

**Files:**
- Modify: `docs/adr/ADR-0005-task-25-v1-windows-provenance-boundary.md`
- Existing design: `docs/superpowers/specs/2026-08-06-task-25-staging-and-runtime-hardening-design.md`
- Create this plan: `docs/superpowers/plans/2026-08-06-task-25-staging-and-runtime-hardening.md`
- External metadata after push: PR #36 description

- [ ] **Step 1: Extend ADR-0005 without changing its Windows decision**

Add a paragraph to `## Verifier-Grenze` stating that the staging verifier now rejects a wheelhouse unless its immediate closure contains only the non-linked regular wheel supplied by `--wheel`, before manifest and wheel binding. State explicitly that the guard applies to future staging/CI acceptance and does not prove it ran during the original immutable v1 build. Link to the new accepted hardening design.

- [ ] **Step 2: Run documentation governance and diff checks**

Run:

```powershell
uv run python tools/check_docs.py
git diff --check
```

Expected: both pass.

- [ ] **Step 3: Run focused joint validation**

Run all three changed test files together, Ruff on the six changed Python files, and mypy using the repository command. Use workspace-local pytest basetemp and disable only pytest's local cache provider when the sandbox requires it.

- [ ] **Step 4: Run every repository gate from the current configuration**

Execute the formatting, linting, typing, architecture, documentation, schema, package-build/install-smoke, security/dependency, and full pytest commands defined by `pyproject.toml`, repository tooling, and `.github/workflows/pr.yml`. Inspect the complete diff and verify that the builder, release verifier, frozen `artifact-build` job, schemas, release assets, and archived documents have no changes.

- [ ] **Step 5: Commit and push the coherent fix**

Stage only the approved runtime, staging-verifier, tests, ADR, design, and plan files. Commit with a focused message such as `fix: harden engine staging and runtime failures`, then push the existing feature branch without force.

- [ ] **Step 6: Update PR #36 while keeping it Draft**

Append a concise PR-body note stating:

```text
The staged-artifact verifier now enforces an exact, non-linked immediate
wheelhouse closure before manifest and wheel binding. This guard protects
future staging and CI acceptance runs; it does not retroactively expand the
evidence of the original immutable v1 build. The builder, frozen
artifact-build job, release-only verifier, and v1 release assets remain
unchanged.
```

Verify `isDraft=true`, the expected head SHA, and that the PR is not merged.

- [ ] **Step 7: Wait for hosted PR and CodeQL checks on the final head**

Require the full PR workflow and CodeQL to pass on exactly the pushed head. Keep PR #36 Draft even after green checks; do not merge and do not begin Task 26.
