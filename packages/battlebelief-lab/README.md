# battlebelief-lab

Offline research package for BattleBelief. Current boundaries are defined in
[`docs/architecture/code-boundaries.md`](../../docs/architecture/code-boundaries.md).

Version `0.2.0` remains a runtime `M1` package boundary, while the lab now
contains the deterministic M1.5 measurement-planning harness, registration
validation, team clustering, schedule and budget identities, and synthetic
run-result validation. It does not provide an Oracle, dataset ingestion,
training, Search, Belief, engine integration, or public evaluation pools.
