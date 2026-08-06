---
document_id: contract-engine-capabilities
title: Engine-Capability-Vertrag
document_type: contract
status: accepted
normative: true
version: 2
applies_to:
  - search
  - gen9ou
effective_from: 2026-08-06
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-06
---

# Engine-Capability-Vertrag

## Engine capability contract

### Roles

- [Pokemon Showdown](https://github.com/smogon/pokemon-showdown) is the oracle.
- [`poke-engine`](https://github.com/pmariglia/poke-engine) is a controlled
  surrogate simulator.
- Legal/heuristic fallback is the live path whenever eligibility is absent.

### Catalog, manifest, and evidence

The v1 structure remains available, byte-identically, at
[`engine-capability.schema.json`](../../schemas/manifests/engine-capability.schema.json).
All new capability claims use v2:

- [`engine-capability-catalog-v1.schema.json`](../../schemas/catalogs/engine-capability-catalog-v1.schema.json)
  is the sole authority for capability IDs;
- [`engine-capability-v2.schema.json`](../../schemas/manifests/engine-capability-v2.schema.json)
  binds a catalog, engine provenance, and claims; and
- [`engine-capability-evidence.schema.json`](../../schemas/manifests/engine-capability-evidence.schema.json)
  binds one claim/catalog/evidence identity.

A capability ID is lowercase ASCII, at most 128 characters, and matches
`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*){2,7}$`.
It begins with `gen9.` for this catalog. A free ID in a manifest, evidence
file, code, or migration is not claim authority.

The machine-readable
[`engine-capability-catalog-v1.json`](../../artifacts/gen9ou/m2/engine-capability-catalog-v1.json)
is the sole Gen 9 OU taxonomy, including its complete approved ID set and
normative descriptions. Other documents and code must not duplicate that list.

The only statuses are `exact`, `bounded_approximation`, `unsupported`, and
`unknown`. A missing claim is effectively `unknown`. `unsupported` and
`unknown` carry neither evidence nor an approximation. `exact` requires a
complete evidence matrix over every bound environment cell.
`bounded_approximation` requires the same closure and a nonempty `bound` and
`condition`; it must never be interpreted as `exact`.

Qualifying claims bind the engine source, artifact index, every build/wheel
cell, all five `transition_adapter_*` identities, oracle source/build, ruleset,
corpus, result schema, and result digest. The five adapter fields are either
all `null` or all present. They name the later BattleBelief transition adapter.

The Task 25 artifact/sentinel probe is not that adapter binding. It supports
private build and health properties only: it does not establish transition
mapping, oracle parity, search eligibility, or strength. The initial v2
artifact is explicitly unqualified: every catalog ID is effectively `unknown`,
and there is no `exact` or `bounded_approximation` evidence.

### Eligibility before each search

1. Check artifact identity, version, build features, and adapter provenance.
2. Form required capabilities from state, belief support, legal set, and
   end-of-turn mechanics.
3. Start search only with a completely `exact` classified set.
4. Admit `bounded_approximation` only with a named tested bound and explicit
   approval.
5. `unknown`, `unsupported`, mismatch, or backend failure use fallback.

### Prepared root and backend identities

`PreparedRootIdentity` contains exactly `request_identity_digest`,
`safe_submission_set_digest`, `observed_state_digest`, `root_player`,
`ruleset_digest`, `backend_identity_digest`, and `capability_catalog_digest`.
`prepared_root_digest` is the canonical digest of exactly those seven inputs.
Changes to a private prepared world do not alter that root digest.

`backend_identity_digest` is the canonical closure over the engine source
manifest, selected engine build manifest, artifact index, selected environment
cell and wheel, plus all five `transition_adapter_*` fields. It is not the
Task25 sentinel adapter identity: the Task25 sentinel remains only a private
artifact health probe and cannot supply a transition adapter binding.

### Required capabilities before search

`PreparedWorld`, `SearchAction`, and `TransitionOutcome` each carry their
required capabilities. Before starting search, validate that every value is a
catalog-bound `CapabilityId` from the same `capability_catalog_digest`; reject
foreign IDs. Deduplicate the values and sort them lexicographically by
capability value, then take the deterministic union across the prepared world,
candidate search actions, and transition outcomes. If this validation or union
cannot be formed, no search starts and the fallback path applies.

### Differential gates

- no unclassified divergences in the versioned corpus;
- no unclassified divergences observed during release evaluation; and
- every `exact` capability passes its own evidence suite.

### Fallback and strength

Fallback-battle accounting is defined only in
[`evaluation-m5-strength-qualification`](../evaluation/m5-strength-qualification.md).
Report search coverage, eligibility, and fallback reason separately. A fallback
battle must not be called a search battle.
