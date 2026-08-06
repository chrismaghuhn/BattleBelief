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

- [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) is the oracle.
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
The catalog binds both the capability contract and canonicalization profile by
explicit contract ID, version, and exact UTF-8 digest. Repository validation
resolves the declared ID/version to the authoritative bytes and rejects a
missing, substituted, or digest-mismatched contract.

The only statuses are `exact`, `bounded_approximation`, `unsupported`, and
`unknown`. A missing claim is effectively `unknown`. `unsupported` and
`unknown` carry neither evidence nor an approximation. `exact` requires a
complete evidence matrix over every bound environment cell.
`bounded_approximation` requires the same closure and a machine-readable
`metric_id`, canonical decimal `maximum`, `unit_id`, and `condition_id`; it
must never be interpreted as `exact`.

Qualifying claims bind the engine source, artifact index, every build/wheel
cell, `transition_adapter_id`, `transition_adapter_version`,
`transition_adapter_source_digest`, `transition_model_contract_digest`, and
`transition_adapter_conformance_digest`, plus oracle source/build, ruleset,
corpus, runner and classifier source, result schema, and result digest. An
inline evidence reference additionally binds its `evidence_id`, canonical
complete-document `evidence_digest`, capability ID, catalog ID/version/digest,
and canonicalization-contract digest. The repository validator loads the
referenced document from
`artifacts/gen9ou/m2/engine-capabilities/evidence/<evidence-id>.json`,
recomputes its canonical digest, and rejects any closure mismatch. The
directory contains exactly one document per qualifying claimed capability and
bound environment cell; no evidence file may exist outside it. `unknown` and
`unsupported` capabilities produce no capability-evidence documents; their
complete unfavorable, aborted, or divergent outcomes remain retained in the
differential run artifacts. Evidence IDs and digests are unique within a
manifest. The five adapter fields are either all `null` or all present. They
name the later BattleBelief transition adapter.

The Task 25 artifact/sentinel probe is not that adapter binding. It supports
private build and health properties only: it does not establish transition
mapping, oracle parity, search eligibility, or strength. The initial v2
artifact is explicitly unqualified: every catalog ID is effectively `unknown`,
and there is no `exact` or `bounded_approximation` evidence.

A migrated v2 document binds an optional `migration` closure containing source
schema/document identity and digest, migrator ID/version, deterministic loss
codes, loss-report identity, and the digest of a deterministic loss-report
projection. Source v1 documents resolve as
`artifacts/gen9ou/m2/engine-capabilities/migration-sources/<source-document-id>.json`;
loss reports resolve as
`artifacts/gen9ou/m2/engine-capabilities/migration-reports/<loss-report-id>.json`
under the versioned
`urn:battlebelief:schema:manifest:engine-capability-migration-loss-report:v1`
schema. Repository validation loads both documents, recomputes the source and
loss-report digests, checks migrator/loss-code identity, and compares the
report's target digest with the manifest digest. This acyclic pair prevents a
loose source, report, or target from being substituted; an ordinary
unqualified initial manifest has `migration: null`.

### Eligibility before each search

1. Check artifact identity, version, build features, and adapter provenance.
2. Form the conservative static preflight set defined in
   [Required capabilities before search](#required-capabilities-before-search).
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
cell and wheel, plus `transition_adapter_id`, `transition_adapter_version`,
`transition_adapter_source_digest`, `transition_model_contract_digest`, and
`transition_adapter_conformance_digest`. It is not the
Task25 sentinel adapter identity: the Task25 sentinel remains only a private
artifact health probe and cannot supply a transition adapter binding.

### Required capabilities before search

Before starting search, form a conservative static preflight set from prepared
worlds, authoritative root actions, statically enumerated deep-action kinds,
and potentially reachable ordering, chance, transition, end-of-turn, and
terminal handlers. Validate that every value is a catalog-bound `CapabilityId`
from the same `capability_catalog_digest`; reject foreign IDs, deduplicate, and
sort by capability value. No `TransitionOutcome` is produced to determine this
preflight set. `TransitionOutcome.required_capabilities` is runtime
conformance evidence: every actual outcome capability must be a subset of the
prequalified set. A new or catalog-foreign outcome capability ends that search
path fail closed. If the static set cannot be formed, no search starts and the
fallback path applies.

### Differential gates

- no unclassified divergences in the versioned corpus;
- no unclassified divergences observed during release evaluation; and
- every `exact` capability passes its own evidence suite.

### Fallback and strength

Fallback-battle accounting is defined only in
[`evaluation-m5-strength-qualification`](../evaluation/m5-strength-qualification.md).
Report search coverage, eligibility, and fallback reason separately. A fallback
battle must not be called a search battle.
