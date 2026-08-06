---
document_id: task-25-v1-verifier-provenance-design
title: Task 25 v1 Verifier and Windows Provenance Boundary Design
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

# Task 25 v1 Verifier and Windows Provenance Boundary Design

## Goal

Close the Task-25 source-verification bypass while preserving the already
published immutable v1 release, and record the exact boundary of the Windows
provenance evidence that v1 actually contains.

## Accepted decision

The staged-artifact verifier and published-wheel verifier are separate
evidence paths:

- staged verification requires a real source checkout and verifies its full
  tree closure against the canonical source manifest before accepting the
  manifested wheel;
- published-wheel-manifest verification revalidates canonical manifests,
  manifest digests, expected Python/platform tags, wheel bytes, metadata, and
  `RECORD`, but does not evaluate a source checkout or reconstruct a build
  environment.

The existing release
`engine-poke-engine-v0.0.48-bcf13823-v1` and every asset attached to it remain
unchanged.

## Command boundaries

`tools/verify_poke_engine_artifact.py` remains the staging command. Its
`--checkout` argument is required by the command-line parser. A missing
argument fails before verification begins, and a checkout whose Git identity
or complete file closure differs fails before wheel acceptance.

`tools/verify_published_wheel_manifest.py` is the release-only command. It
accepts a canonical source manifest, one canonical build manifest, and the
corresponding downloaded wheel. It checks:

- both manifests against their existing v1 schemas and canonical byte form;
- the pinned source-manifest identity and the build-to-source manifest digest;
- the Python, ABI, and platform tags declared by the build manifest;
- the complete wheel identity already returned by `inspect_wheel`, including
  filename, size, SHA-256, distribution metadata, wheel metadata, `RECORD`,
  and normalized `RECORD` entries.

The release-only command has no checkout parameter. Its name, description,
and success output describe only published-wheel-manifest verification.

The immutable-release closure command continues to verify GitHub release
metadata, asset closure, asset API digests, `SHA256SUMS`, committed manifest
identity, license identity, and the six indexed cells. CI then invokes the new
release-only command for every downloaded wheel.

## Windows v1 provenance boundary

An accepted ADR records the maintainer decision for v1. The evidence
guarantees immutable released bytes, digest binding across release metadata,
checksums and manifests, the controlled build parameters recorded by the v1
schema, and behavioral rebuild evidence from all six qualified cells.

It does not guarantee complete reconstruction of the original Windows build
environment. In particular, v1 did not bind the exact Visual Studio/MSVC
toolset, Windows SDK, `link.exe` binary, or runner-image identity. The phrase
"no ambient build overrides" therefore applies only to the explicitly
controlled build parameters. It is not a claim that all native Windows
toolchain discovery inputs were pinned.

Retrofitting unrecorded values into v1 would create unsupported evidence. A
future regular v2 artifact generation may introduce a new manifest schema and
release criterion that binds those values before building.

## Testing

Regression coverage proves that:

- staging verification without `--checkout` is rejected by argument parsing;
- staging verification with a non-matching checkout returns failure;
- published-wheel-manifest verification succeeds without a checkout;
- changed wheel bytes or a changed canonical build manifest are rejected;
- the PR workflow invokes the staging verifier only with `--checkout` and uses
  the distinctly named release verifier for downloaded release wheels.

Focused tests run before implementation to demonstrate the missing behavior,
then again after the smallest implementation. Repository formatting, linting,
typing, documentation, schema, package, and test gates run before completion.

## Non-goals

- changing the v1 source, build, or artifact-index schemas;
- rebuilding or republishing any v1 wheel;
- changing the v1 tag or release assets;
- claiming byte-reproducible Windows rebuilds;
- collecting or guessing historical MSVC, SDK, linker, or runner identities;
- implementing the future v2 Windows toolchain-provenance schema.
