---
document_id: poke-engine-legal-choice-binding-design
title: Downstream poke-engine Legal-Choice Binding Design
document_type: operation
status: accepted
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

# Downstream `poke-engine` Legal-Choice Binding Design

## Goal

Publish a new verified `poke-engine` artifact that exposes native legal-choice
enumeration for a future runtime adapter, while leaving Task 25's `0.0.48`
release and Task 27's runtime mapping untouched.

## Context and constraints

The accepted Task-25 artifact is `poke-engine==0.0.48`, built from upstream
commit `bcf13823abc162a608e187b26bbf683f759f385e` and its clean source tree.
That artifact and every v1 manifest, wheel, checksum, release asset, and
runtime identity remain immutable.

The pinned upstream Python module calls `State::root_get_all_options()` from
MCTS and iterative-deepening search but does not export it. The native Gen 9
implementation already owns disabled-move, PP, switching, trapping, and
forced-switch legality. The binding must expose that result without adding
legality logic or search behavior.

The new release is therefore a downstream-patched artifact. The base upstream
commit remains a base identity only; the resulting source is not represented as
an upstream commit or tag.

## Decision

Create a new v2 artifact/provenance profile for `poke-engine==0.0.49`.

The tracked downstream patch modifies only the native Python binding's public
surface and its binding-level tests. The v2 source manifest binds:

1. the complete immutable v1 base source manifest digest;
2. the exact upstream base commit, tag, and tree identity;
3. the patch's repository-relative path, byte size, SHA-256 digest, and exact
   downstream-patch role; and
4. the complete resulting source-file closure and its canonical digest.

The controlled builder verifies the clean base checkout, verifies the patch
bytes, applies the patch exactly once with no offset or fuzz tolerance, and
then verifies the complete post-patch closure before invoking the existing
locked Maturin build settings. New v2 source, build, and artifact-index
schemas are additive; v1 schemas and artifacts are not edited.

## Public binding API

The native Python binding adds:

```python
def legal_choices(state: State) -> tuple[list[str], list[str]]: ...
```

Its complete data flow is:

```text
PyState
  -> native State conversion
  -> State::root_get_all_options() exactly once
  -> existing movechoice_to_string(&side, &choice)
  -> (side_one_choices, side_two_choices)
```

The binding takes ownership of a converted native state, does not mutate the
caller-visible `PyState`, performs no MCTS, iterative deepening,
expectiminimax, sampling, evaluation, filtering, or Python legality
reconstruction, and returns only the two native option vectors rendered by the
existing canonical search stringification helper.

## Verification and tests

Native Python-binding tests run against the downstream-patched source and
cover ordinary moves, disabled and zero-PP moves, legal switches, trapped
states, forced-switch states, caller-state serialization immutability, and
canonical choice strings. The disabled zero-PP case explicitly preserves the
known counterexample where `generate_instructions()` accepts a parseable but
illegal choice.

Repository tooling tests cover exact patch identity, fail-closed application,
base identity, no-fuzz application, complete post-patch closure, v2 manifest
canonicalization, and old v1 immutability. The staged-artifact smoke imports
the new wheel and exercises representative legal-choice results.

The release verifier accepts only the new v2 release closure: six distinct
wheel identities, six fresh wheel digests, matching build manifests, matching
source/patch closure, immutable release metadata, checksums, and canonical
artifact index. Runtime dependency metadata is updated only after those
published bytes are verified by the v2 verifier.

## Architectural boundary

The native backend defines legality. The Python binding exposes it. A future
Task-27 runtime adapter will map the returned native strings into the frozen
engine-neutral core port. This change does not implement
`TransitionModel.legal_actions()`, modify any core port, expose native states
or choices through core, or add search behavior to the future adapter.

## Non-goals

- changing or rebuilding the immutable Task-25 `0.0.48` artifact;
- changing `codex/task-27-runtime-poke-engine-mapping`;
- implementing Task 27 or any `TransitionModel.legal_actions()` method;
- changing the frozen core port or its contracts;
- reimplementing native legality in Python or runtime code;
- using `generate_instructions()` or search to discover legal choices;
- claiming mechanics parity, search eligibility, or strength qualification;
- adding new target cells outside the established six-cell matrix.
