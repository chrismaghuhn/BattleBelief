---
document_id: task-25-staging-and-runtime-hardening-design
title: Task 25 Staging Closure and Runtime Failure Hardening Design
document_type: operation
status: accepted
normative: false
version: 1
applies_to:
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

# Task 25 Staging Closure and Runtime Failure Hardening Design

## Goal

Close the two remaining sanitized-runtime failure gaps and make the staged
wheelhouse acceptance boundary exact, without changing the immutable v1
release, its original builder, or the release-only verification claim.

## Accepted decisions

### Sentinel fixture failures

Sentinel fixture loading rejects the non-standard JSON constants `NaN`,
`Infinity`, and `-Infinity` while parsing. The rejection is represented only
as `EngineArtifactError(SENTINEL_FAILED)` at the public runtime boundary.

Fixture and search-configuration digest calculation is also a guarded
boundary. Canonicalization failures caused by invalid fixture values, including
`TypeError` and `ValueError` subclasses, are converted to the same stable
`SENTINEL_FAILED` status. Raw parser or canonicalization exceptions and fixture
contents do not escape.

### Artifact and native-path resolution failures

Every `resolve(strict=True)` operation used to compare an actual installed or
imported native path with its expected path belongs to the same guarded block
as the corresponding actual-path resolution.

- Artifact installation verification converts distribution-root, installed-
  file containment, staged `direct_url.json`, and expected-package origin
  resolution failures, including `RuntimeError` from symlink loops, to
  `EngineArtifactError(ARTIFACT_MISMATCH)`.
- Native import verification converts an expected-path resolution failure to
  `EngineArtifactError(IMPORT_FAILED)`.

The conversion exposes only the stable status. It does not include an absolute
path or the original operating-system exception message.

### Staged wheelhouse closure

`tools/verify_poke_engine_artifact.py` derives the wheelhouse only from the
required `--wheel` argument as `wheel_path.parent`. Before reading or binding
either manifest, inspecting the wheel, verifying the checkout, or producing
success output, the staging verifier validates this immediate output closure.

The wheelhouse is accepted only when all of the following are true:

- it exists;
- its own filesystem entry is a directory;
- its own filesystem entry is not a symbolic link, junction, mount-style
  reparse entry, or any other reparse point reported by the host filesystem;
- enumerating its immediate children succeeds;
- the immediate closure contains exactly one entry;
- that entry is exactly the path supplied by `--wheel`;
- the entry is a regular file;
- the entry is not a symbolic link, junction, or other reparse point.

Filesystem classification uses non-following metadata where available. Path
comparison normalizes absolute lexical paths without accepting a different
target reached through a link. Resolution, metadata, and enumeration errors
all fail closed.

Every failure in this closure check emits the single stable staging message
`staged wheelhouse closure differs`. The message contains no local path and no
raw operating-system error. Extra regular files, directories, links, and
reparse entries are therefore indistinguishable at the public CLI boundary but
are all rejected.

After the closure succeeds, the existing staging sequence continues with
canonical manifest loading, pinned-source validation, complete checkout
verification, and manifest-to-wheel binding.

## Frozen v1 boundaries

The following remain unchanged:

- `tools/build_poke_engine_wheel.py` and the original builder behavior;
- the frozen `artifact-build` job definition in `.github/workflows/pr.yml`;
- `tools/verify_published_wheel_manifest.py` and its release-only claim;
- all source, build, and artifact-index schemas;
- the tag, assets, manifests, checksums, licenses, and metadata of
  `engine-poke-engine-v0.0.48-bcf13823-v1`.

The new wheelhouse guard protects future staging and CI acceptance runs. It is
not evidence that the original immutable v1 build run applied this check, and
it does not retroactively expand the provenance or output-closure guarantees
recorded for that run.

ADR-0005 and the PR description state this temporal boundary explicitly. The
existing Windows provenance decision remains unchanged.

## Regression coverage

Tests first demonstrate each missing behavior, then the smallest production
change makes them pass.

Sentinel fixture tests cover `NaN`, `Infinity`, and `-Infinity` in
`gen9_transition.json` and require only `sentinel_failed` to escape. A digest
canonicalization failure is separately converted to `sentinel_failed`.

Path-resolution tests force expected-path resolution, after successful
actual-path resolution, to raise `PermissionError` or `FileNotFoundError`.
They also cover the path-bearing `RuntimeError` used for symlink loops by
supported CPython 3.12, including all four actual and expected native paths.
Separate Artifact regressions raise a path-bearing `RuntimeError` while
resolving the distribution root, validating installed-file containment, and
binding a staged `direct_url.json` path.
The tests require `artifact_mismatch` for installation verification and
`import_failed` for native import verification, and assert that neither the
exception text nor an absolute path appears in the public result.

Staging-verifier tests cover:

- only the expected regular wheel succeeds;
- an additional regular file fails;
- an additional directory fails;
- the expected wheel as a symbolic link or reparse point fails;
- an additional symbolic link or reparse point fails;
- a wheel reached outside the immediate closure through a link fails;
- a wheel under a linked or reparse-point wheelhouse fails;
- closure failure occurs before manifest loading, checkout verification, and
  wheel inspection.

Platform-specific link and reparse tests use real filesystem entries when the
host permits their creation. Unit-level classification tests simulate Windows
reparse metadata so the fail-closed rule remains covered on hosts without
junction privileges.

Focused runtime and tooling tests run first. The complete repository test and
quality gates, followed by the unchanged PR workflow and CodeQL on the final
head, are required before PR #36 may leave Draft.

## Non-goals

- modifying or republishing the immutable v1 release;
- changing the release-only verifier or giving it a wheelhouse claim;
- changing the builder or the frozen `artifact-build` job;
- claiming the new staging guard ran during the original v1 build;
- adding historical Windows toolchain evidence;
- implementing the future v2 Windows provenance model;
- making PR #36 ready or merging it before all required checks pass.
