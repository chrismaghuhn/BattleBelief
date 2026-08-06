---
document_id: migration-engine-capability-v1-to-v2
title: Engine capability v1 to v2 migration
document_type: guide
status: accepted
normative: false
version: 1
applies_to:
  - engine-capabilities
effective_from: 2026-08-06
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-06
---

# Engine capability v1 to v2 migration

The pure `tools/migrate_engine_capability.py` migrator accepts a v1 JSON
document, a valid v2 catalog, and an explicit unqualified target binding. The
binding supplies the engine-source and artifact-index digests, canonical sorted
environment bindings, and the catalog-matching canonicalization digest. It
returns a Core-valid v2 migration target plus a deterministic report. The v1
schema and fixture remain byte-identical.

The migration is deliberately lossy and fail-closed:

- no free v1 capability is copied into the catalog;
- no v1 classification is promoted to a v2 claim;
- `claims` is empty, so every catalog ID remains effectively `unknown`; and
- the transition adapter, oracle, ruleset, corpus, runner, classifier, and evidence bindings remain
  explicitly `null`.

The target has a `migration` closure with `source_schema_id`, source digest,
migrator ID/version, sorted loss codes, and `loss_report_digest`. The digest is
computed over a deterministic report projection excluding `target_digest`; the
final report repeats that projection and binds the resulting target digest. This
is acyclic while preventing either report projection or target from being
substituted independently. The report contains deterministic per-section loss
counts for `exact`, `approximated`, `unsupported`, and `known_divergences`. It
contains no path, hostname, or time. The explicit source/index/environment
binding prevents a migration from guessing provenance; it remains unqualified
because it has no claims or evidence.
