---
document_id: plan-poke-engine-legal-choice-binding
title: "poke-engine Legal-Choice Binding Implementation Plan"
document_type: roadmap
status: proposed
normative: false
version: 1
applies_to:
  - gen9ou
  - runtime
  - release
effective_from: 2026-08-07
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-07
---

# poke-engine Legal-Choice Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a verified downstream-patched `poke-engine==0.0.49` artifact that exposes native legal-choice enumeration while preserving Task-25 v1 and leaving Task 27 unimplemented.

**Architecture:** The exact Task-25 upstream checkout is verified first, then a repository-tracked downstream patch is verified by digest, applied exactly once, and checked against a complete post-patch source closure. The native binding maps `State::root_get_all_options()` through the existing canonical choice string helper; new v2 artifact manifests and verifiers bind the resulting source and six fresh wheel identities without modifying v1.

**Tech Stack:** Rust/PyO3, Python 3.12–3.14, Maturin 1.7.1, Rust 1.83.0, Git patch verification, JSON Schema, RFC 8785 JCS, uv, pytest, Ruff, mypy, GitHub Actions, GitHub CLI.

---

## File map

- Create `artifacts/gen9ou/m2/engine/downstream-patches/poke-engine-legal-choices-v1.patch` — exact downstream native binding and binding-test patch applied to the pinned upstream checkout.
- Create `schemas/manifests/engine-source-v2.schema.json` — schema for base-upstream plus downstream-patch provenance and post-patch closure.
- Create `schemas/manifests/engine-build-v2.schema.json` — schema for fresh `0.0.49` six-cell build manifests.
- Create `schemas/manifests/engine-artifact-index-v2.schema.json` — schema for the immutable v2 release closure.
- Create v2 schema examples and invalid examples under `schemas/examples/` — documentation and schema-gate fixtures.
- Create `artifacts/gen9ou/m2/engine-v2/engine-source.json`, six build manifests, and `engine-artifact-index.json` — verified v2 metadata only; v1 files remain unchanged.
- Create matching runtime sidecars under `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/data-v2/` — package-consumed v2 metadata.
- Modify `tools/build_poke_engine_wheel.py` — add an explicit v2 downstream-patch profile while retaining the existing v1 default behavior byte-for-byte at the manifest/API boundary.
- Create `tools/verify_published_engine_release_v2.py` and `tools/verify_published_wheel_manifest_v2.py` — v2-only release and wheel verification; v1 verifiers remain unchanged.
- Modify `tools/create_engine_artifact_index.py` only if shared index assembly is needed — preserve its v1 default and add a separate v2 profile.
- Create `tools/smoke_poke_engine_legal_choices.py` — actual installed-wheel binding smoke with deterministic state fixtures.
- Create `packages/battlebelief-runtime/tests/adapters/poke_engine/test_legal_choices.py` — runtime-side import and canonical-result contract checks that do not implement Task 27.
- Create `tests/tooling/test_poke_engine_legal_choice_binding.py` — patch application, closure, v2 manifest, and verifier regressions.
- Modify `tests/tooling/test_engine_artifact_schemas.py`, `tests/tooling/test_build_poke_engine_wheel.py`, and related tooling tests — v2 coverage while retaining all v1 assertions.
- Modify `.github/workflows/pr.yml` — add v2 candidate build/stage/verification jobs without changing the frozen v1 artifact job or release closure.
- Modify `packages/battlebelief-runtime/pyproject.toml` and `uv.lock` — consume the published `0.0.49` wheel only after v2 release verification is complete.
- Modify `docs/contracts/manifest-schemas.md`, `docs/README.md`, and the v2 artifact README — document the single v2 provenance owner and link, without duplicating v1 thresholds or editing the immutable archive.

## Task 1: Record and verify the exact native patch

**Files:**
- Create: `artifacts/gen9ou/m2/engine/downstream-patches/poke-engine-legal-choices-v1.patch`
- Test: `tests/tooling/test_poke_engine_legal_choice_binding.py`
- Modify: `tools/build_poke_engine_wheel.py`

- [ ] **Step 1: Add a failing patch-identity test**

Add a test that creates an exact clean checkout fixture from a small Git
repository, records the expected patch bytes and post-patch file closure, and
requires the v2 patch verifier to reject a changed patch digest, a missing
base identity, an extra patch file, or a dirty checkout.

- [ ] **Step 2: Run the focused test to confirm the missing verifier fails**

Run:

```powershell
uv run pytest tests/tooling/test_poke_engine_legal_choice_binding.py -q -p no:cacheprovider
```

Expected: the new verifier import or required v2 profile is absent, so the
test fails before any release metadata is generated.

- [ ] **Step 3: Implement exact downstream-patch application**

Add a v2 helper with this sequence:

```python
verify_source_checkout(checkout, base_source_manifest)
patch_bytes = patch_path.read_bytes()
if _sha256(patch_bytes) != source_manifest["downstream_patch"]["sha256"]:
    _fail("downstream patch digest differs")
_run(("git", "apply", "--check", "--unidiff-zero", "--whitespace=error", "--verbose", str(patch_path)), cwd=checkout)
_run(("git", "apply", "--unidiff-zero", "--whitespace=error", "--verbose", str(patch_path)), cwd=checkout)
verify_no_patch_offsets_or_fuzz(checkout)
verify_post_patch_source_closure(checkout, source_manifest["source_files"])
```

The helper must require the exact base commit/tree/tag before application,
reject patch paths outside the repository, reject non-UTF-8 or duplicate patch
metadata, reject any `offset` or `fuzz` diagnostic, reject an already-applied
or twice-applied patch, and reject every post-application file difference not
named by the patch. The post-patch closure must enumerate the complete tracked
source tree, hash bytes from the materialized checkout, and compare the
canonical record list and digest to the v2 source manifest.

- [ ] **Step 4: Run the focused patch tests**

Run the single test file again and require all patch identity, no-fuzz, exact
once, and closure cases to pass.

- [ ] **Step 5: Commit the patch and verifier foundation**

```powershell
git add artifacts/gen9ou/m2/engine/downstream-patches/poke-engine-legal-choices-v1.patch tools/build_poke_engine_wheel.py tests/tooling/test_poke_engine_legal_choice_binding.py
git commit -m "build: bind downstream poke-engine patch provenance"
```

## Task 2: Add the native read-only binding and native Python-binding tests

**Files:**
- Modify through: `artifacts/gen9ou/m2/engine/downstream-patches/poke-engine-legal-choices-v1.patch`
- Test through: the patched upstream `poke-engine-py/python/tests/test_poke_engine.py`
- Test: `tools/smoke_poke_engine_legal_choices.py`

- [ ] **Step 1: Add the failing native binding tests to the patch**

Extend the downstream-patched upstream test module with tests that construct
states for ordinary moves, disabled moves, zero-PP moves, legal switches,
trapped states, forced-switch states, caller-state serialization immutability,
and canonical choice strings. The zero-PP case must also call
`generate_instructions()` with the same parseable choice and record that the
existing instruction API accepts it while `legal_choices()` excludes it.

- [ ] **Step 2: Run the patched binding tests before implementation**

Run the upstream Python binding tests against the patched source checkout with
the native extension absent. Expected: the new tests fail because the Rust
function and Python stub/export do not yet exist.

- [ ] **Step 3: Add the minimal Rust binding**

The patch must add exactly this behavior to `poke-engine-py/src/lib.rs`:

```rust
#[pyfunction]
fn legal_choices(py_state: PyState) -> PyResult<(Vec<String>, Vec<String>)> {
    let state: State = py_state.into();
    let (side_one_options, side_two_options) = state.root_get_all_options();
    let side_one_choices = side_one_options
        .iter()
        .map(|choice| movechoice_to_string(&state.side_one, choice))
        .collect();
    let side_two_choices = side_two_options
        .iter()
        .map(|choice| movechoice_to_string(&state.side_two, choice))
        .collect();
    Ok((side_one_choices, side_two_choices))
}
```

Register it with `wrap_pyfunction!(legal_choices, m)` and add the matching
`legal_choices(py_state: State) -> Tuple[List[str], List[str]]` declaration to
`poke_engine.pyi`. Do not add a Python legality wrapper or a second choice
serializer.

- [ ] **Step 4: Run the native binding tests after implementation**

Build the patched native module with the established Maturin command and run
the patched `test_poke_engine.py`. Expected: all new cases pass, the function
calls native root enumeration once, and the caller's serialized state is byte-
identical before and after.

- [ ] **Step 5: Add actual-wheel smoke coverage**

Implement `tools/smoke_poke_engine_legal_choices.py` so it imports
`poke_engine.legal_choices`, loads deterministic fixture states, asserts the
disabled/zero-PP, switch, trap, forced-switch, and canonical-string cases, and
emits only canonical JSON with the fixture/configuration digests. It must not
import BattleBelief runtime mapping code or invoke any search function.

## Task 3: Define additive v2 source/build/index schemas and manifests

**Files:**
- Create: `schemas/manifests/engine-source-v2.schema.json`
- Create: `schemas/manifests/engine-build-v2.schema.json`
- Create: `schemas/manifests/engine-artifact-index-v2.schema.json`
- Create: v2 examples and invalid examples under `schemas/examples/`
- Create: v2 manifests under `artifacts/gen9ou/m2/engine-v2/`
- Test: `tests/tooling/test_engine_artifact_schemas.py`

- [ ] **Step 1: Add failing schema fixtures**

Add a valid v2 source manifest with `source_scope` equal to
`full_git_tree_with_downstream_patch`, `base_source_manifest_digest`,
`base_commit`, `base_tag`, `base_git_tree_oid`, a `downstream_patch` object
whose role is `legal-choice-binding` and application is
`git-apply-exact-v1`, and a complete post-patch `source_files` closure. Add
valid v2 build/index examples with distribution `0.0.49`, new release tag,
fresh wheel identity fields, and the unchanged six target cells. Add invalid
examples for a missing patch digest, a post-patch closure mismatch, a v1
release tag, and a repeated wheel digest.

- [ ] **Step 2: Run schema tests and observe the intended red result**

Run:

```powershell
uv run pytest tests/tooling/test_engine_artifact_schemas.py -q -p no:cacheprovider
```

Expected: the new v2 schema IDs and examples are not yet registered by the
schema checker.

- [ ] **Step 3: Implement additive v2 schemas**

Use `additionalProperties: false`, canonical v2 schema IDs, exact `0.0.49`
distribution constants, exact new release-tag patterns, six-cell closure
constraints, unique wheel filenames/digests, and explicit downstream patch
fields. Do not edit any v1 schema or v1 artifact file.

- [ ] **Step 4: Generate canonical v2 source and build manifests**

Run the v2 builder/profile to create the source manifest and six build
manifests. Verify every source manifest contains the base v1 digest, patch
digest, post-patch source-file digest, and exact base commit; verify every
build manifest contains the v2 source digest and a distinct `0.0.49` wheel
identity.

- [ ] **Step 5: Create and validate the v2 artifact index**

Assemble the six-cell v2 index only from the six verified build manifests and
the actual staged sentinel results. Require unique wheel SHA-256 values and
fresh release asset URLs. Run the schema tests and repository schema checker.

## Task 4: Build, verify, and smoke the new six-cell artifact

**Files:**
- Modify: `tools/build_poke_engine_wheel.py`
- Create: `tools/verify_published_engine_release_v2.py`
- Create: `tools/verify_published_wheel_manifest_v2.py`
- Modify: `tests/tooling/test_build_poke_engine_wheel.py`
- Create: `tests/tooling/test_verify_poke_engine_legal_choice_release.py`
- Create: runtime v2 sidecars under `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/data-v2/`

- [ ] **Step 1: Add failing v2 builder/verifier tests**

Require the v2 builder to reject the old version, old release tag, old source
manifest schema, patch digest mismatch, incomplete post-patch closure, and
duplicate wheel bytes. Require the v2 published-wheel verifier to reject
changed wheel bytes, changed wheel metadata, changed build manifests, missing
v2 sidecars, and any reuse of a `0.0.48` filename or digest.

- [ ] **Step 2: Implement the isolated v2 build profile**

Keep all v1 constants, defaults, and command behavior intact. Add an explicit
v2 profile that applies the verified patch before Maturin, changes only the
distribution/release identity to `0.0.49` and the v2 adapter identity, retains
Rust 1.83.0, Maturin 1.7.1, locked Cargo, disabled default features, Gen 9
and terastallization features, and the existing six target cells.

- [ ] **Step 3: Build the available local cell and verify its bytes**

Use the established controlled build command with the exact pinned tools. Run
the staged verifier, wheel manifest verifier, source closure verifier, and
`smoke_poke_engine_legal_choices.py` against the actual wheel. Record the
wheel filename, size, SHA-256, metadata digests, `RECORD` digest, source
manifest digest, and build manifest digest without adding the wheel to Git.

- [ ] **Step 4: Run the six-cell hosted build and collect all fresh identities**

Use the new v2 CI profile for Ubuntu 24.04 and Windows 2025 with CPython
3.12–3.14. The candidate index must be generated only from the six successful
build manifests and six actual-wheel smoke results. Any failed, missing, or
duplicated cell stops the release candidate.

- [ ] **Step 5: Verify the published release closure**

After the six wheels and sidecars are published under the new immutable release
tag, run the v2 release verifier over the downloaded release bundle. Require
release metadata, asset URLs, API digests, `SHA256SUMS`, canonical source/build
manifests, v2 index, licenses, and all six wheel manifests to agree. Do not
update runtime pins before this verification succeeds.

## Task 5: Integrate only the verified v2 artifact

**Files:**
- Modify: `packages/battlebelief-runtime/pyproject.toml`
- Modify: `uv.lock`
- Modify: runtime v2 artifact data and verifier selection
- Modify: `.github/workflows/pr.yml`
- Modify: `docs/contracts/manifest-schemas.md`, `docs/README.md`, and v2 artifact README
- Test: runtime artifact and import-boundary tests

- [ ] **Step 1: Add failing runtime metadata tests**

Require runtime installation metadata to resolve only the new v2 release URL,
v2 wheel hashes, v2 source/build/index manifests, and the new adapter identity,
while asserting the historical v1 data remains unchanged. Require no import or
symbol for `TransitionModel.legal_actions()`.

- [ ] **Step 2: Update runtime consumption metadata**

Replace only the active optional-search dependency references with the six
verified `0.0.49` wheel URLs and SHA-256 fragments, regenerate `uv.lock`, and
point artifact verification at the v2 sidecars. Retain the old v1 bundle in
its original directory and leave all Task-25 release identity tests passing.

- [ ] **Step 3: Add v2 CI jobs without changing the frozen v1 job**

Add v2 candidate build, stage-smoke, index, and published-release verification
jobs with the same six-cell matrix and fail-closed checks. Preserve the existing
v1 `artifact-build` job definition and v1 release-closure comparison exactly;
the v2 jobs must not replace or mutate that historical evidence path.

- [ ] **Step 4: Run focused integration checks**

Run:

```powershell
uv run pytest tests/tooling/test_poke_engine_legal_choice_binding.py tests/tooling/test_engine_artifact_schemas.py tests/tooling/test_build_poke_engine_wheel.py packages/battlebelief-runtime/tests/adapters/poke_engine -q -p no:cacheprovider
uv run python tools/check_schemas.py
uv run python tools/check_docs.py
```

Expected: v2 checks pass and all v1 artifact tests remain green.

## Task 6: Final validation, scope review, commit, push, and draft PR

**Files:**
- All files from Tasks 1–5; no Task-27 branch or core-port files.

- [ ] **Step 1: Run the repository gates**

Run the exact commands from `.github/workflows/pr.yml` and repository
configuration:

```powershell
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run python tools/check_versions.py
uv run python tools/check_architecture.py
uv run python tools/check_docs.py
uv run python tools/check_schemas.py
uv run python tools/validate_m15_registration.py
git diff --check
```

Record platform-only hosted checks separately; do not call a local subset the
full CI gate.

- [ ] **Step 2: Inspect immutability and scope**

Confirm the v1 source/build/index files, v1 runtime sidecars, v1 release
metadata, immutable archive, `packages/battlebelief-core`, and
`TransitionModel.legal_actions()` are unchanged. Confirm no wheel, checkout,
secret, local path, dataset, model, or Task-27 implementation is committed.

- [ ] **Step 3: Commit intentionally**

```powershell
git add artifacts schemas tools packages .github docs uv.lock
git commit -m "feat: expose native poke-engine legal choices"
```

- [ ] **Step 4: Push the predecessor branch**

```powershell
git push -u origin codex/poke-engine-legal-choice-binding
```

- [ ] **Step 5: Open a draft PR**

Create a draft PR targeting `main` with a body that states the exact base
commit, downstream patch identity, native delegation, new version/release
identity, six-cell verification status, and explicit Task-27 non-goal. Keep it
Draft and do not merge it.

- [ ] **Step 6: Report exact evidence**

Report branch, base SHA, commit SHA, PR URL/number, changed files, public API,
native function, version, every wheel identity and SHA-256, verifier output,
test counts, Task-27 immutability, and residual risks. If publication cannot
be completed without a release-side external action, stop and report that
precise blocker rather than fabricating wheel or provenance data.
