# Task 28 qualification-freeze repair design

## Status

Approved maintainer design for the Task-27 and Task-24 predecessors and the
subsequent Task-28 repair. This document is implementation guidance, not a
normative mechanics or qualification contract.

## Goal

Freeze all code, corpus bindings, and qualification semantics needed for Task
29 to execute a real differential matrix without modifying Python code,
schemas, classifier logic, or corpus-v1.

The work is split into three pull requests, in dependency order:

1. a Task-27 public Runtime observation predecessor;
2. a Task-24 Windows Node-22 oracle-lifecycle predecessor; and
3. the repaired Task-28 differential corpus and runner.

None of the three pull requests performs a real Showdown-versus-poke-engine
qualification run or elevates a capability.

## Task-27 public observation predecessor

The Runtime-owned adapter surface gains an engine-neutral, sanitised public
observation DTO and a projection method on `PokeEngineTransitionModel`. The
DTO contains only values required by declared differential comparison fields:
legal actions, active slot, effective types, Terastallized state, public HP,
status, action order, terminal state/value, and chance-branch probabilities.

It contains no native `poke_engine` object, native state string, private world,
hidden-world value, path, hostname, exception, or search/eligibility status.
The Runtime does not import the Lab. The Lab later maps this DTO onto its own
`CanonicalMechanicsObservation`.

Existing Runtime action, transition, terminal, mapping-report, capability, and
health semantics remain unchanged. The predecessor is limited to the public
projection of already-calculated mechanics state.

## Task-24 oracle-lifecycle predecessor

Issue #44 is fixed independently. The Windows-2025/Node-22 oracle smoke gains
a bounded, fail-closed completion path while retaining the existing hermetic
oracle API, network denial, pinning, and sanitized diagnostics. It changes no
Runtime, differential, capability, corpus, or qualification logic.

## Task-28 execution freeze repair

After both predecessors merge, corpus-v1 adds a versioned, closed execution
binding for each fixture. The binding holds:

* an exact Task-24 oracle fixture input;
* a Runtime root input sufficient to call only public Runtime APIs;
* canonical action bindings for the fixture's joint intent; and
* a declared mapping from each backend result to the fixture's declared
  mechanics fields.

The corpus validator proves that each execution binding agrees with its
fixture's ruleset identity, authoritative state, public views, action intent,
and declared fields. The binder invokes the public `ShowdownOracleSession` and
`PokeEngineTransitionModel` surfaces, converts their public outputs to Lab
canonical observations, and delegates comparison and classification to
`DifferentialRunner`. Task-28 tests use injected doubles only; no real oracle
or engine is run by the test suite, smoke tooling, or CI.

The corpus ruleset binding changes from the synthetic replacement identity to
the reviewed Task-24 Gen9OU ruleset snapshot identity. Every fixture, index,
and corpus digest is regenerated canonically.

## Qualification evidence repair

Qualification expectations bind expected result provenance per environment
cell, rather than reusing one wheel/build provenance across every cell. A
complete non-synthetic matrix can produce `exact_eligible=true` only when all
fixture, environment, result, artifact, ruleset, corpus, runner, classifier,
and canonicalization identities match and no result is skipped, failed,
timed-out, crashed, malformed, unclassified, or an affecting known divergence.

Synthetic, partial, mismatched, skipped, failed, timeout, crash, malformed,
unclassified, or known-divergent matrices remain non-exact. Task-28 tests use
golden documents to exercise the positive eligibility branch without emitting
a real evidence artifact or a real capability claim.

## Validation and release boundary

Each predecessor receives focused tests, its normal package gates, and an
independent draft pull request. Task-28 then rebases onto both merged
predecessors, regenerates deterministic corpus/schema vectors twice, runs the
full repository gates, and remains a Draft PR.

Task 29 is then data-only: it binds approved real artifacts and environment
cells, executes the pre-frozen matrix, and emits reproducible qualification
artifacts. It does not modify code, schemas, corpus-v1, adapters, classifier,
or evidence rules.
