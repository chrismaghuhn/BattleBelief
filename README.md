# BattleBelief

An open-source Pokémon Singles research bot for decision-making under hidden
information.

> **Status:** M1 is in progress. `main` contains immutable protocol and
> observed-state modeling, request-derived action safety, Showdown protocol and
> request adapters, packed-team loading, authenticated room-preserving
> connectivity, and a request-driven single-room `BattleSession`. Direct
> challenge coordination, CLI integration, acceptance smokes, version
> activation, and final M1 evidence are not yet finished. Live public battle,
> belief, search, training, strength, parity, release, and MVP claims are not
> made.

BattleBelief targets current Smogon Gen 9 OU first. Teams are fixed before a
battle; offline team-building and in-battle decision-making are separate
systems.

## Research thesis

BattleBelief investigates whether an explicit open-world belief over complete
hidden sets, combined with information-set DUCT and an authoritative Showdown
action-safety gate, improves Gen 9 OU decisions over pre-specified heuristic,
determinization, and closed-world baselines under fixed CPU and
reproducibility budgets.

The project develops and measures one layer at a time. Runtime infrastructure,
search, belief, and optional models must each earn further complexity through
pre-specified comparisons and controlled ablations. Formal preregistration
begins only after M1.5 introduces the corresponding versioned registration
artifact. See the
[research strategy and experiment sequence](docs/roadmap/research-strategy-and-experiments.md).

## Current milestone

M1 is building a protocol-safe, heuristic Gen 9 OU prototype. The current
implementation on `main` includes:

- immutable battle events, visible state, and deterministic reduction;
- normalized decision requests and conservative safe submission sets;
- request reconciliation, deterministic heuristic selection, and an
  independent action-safety gate;
- room-preserving frame decoding and strict Showdown protocol parsing;
- request reading, command encoding, and packed-team loading;
- authenticated Showdown WebSocket connectivity with classified transport
  failures; and
- request-driven `BattleSession` execution with freshness checks, pending-state
  reconciliation, and `rqid`-bound `/choose` dispatch.

Direct challenge coordination and the remaining M1 CLI, smoke, version, and
evidence work are still in progress. See the
[M1 protocol-safe prototype plan](docs/superpowers/plans/2026-07-29-battlebelief-m1-protocol-safe-prototype.md)
for the detailed scope and task sequence.

## Packages

- `battlebelief-core`: pure immutable domain and application logic; currently
  includes protocol-state reduction, decision requests, reconciliation,
  deterministic policy, and action safety
- `battlebelief-runtime`: public live adapters and CLI; currently includes
  Showdown framing, parsing, requests, command encoding, packed teams,
  authenticated connectivity, and the single-room BattleSession
- `battlebelief-lab`: offline oracle, data, training, evaluation, and reporting
  work for later milestones

The package boundaries are defined in
[`docs/architecture/code-boundaries.md`](docs/architecture/code-boundaries.md).

## Documentation

Start with [`docs/README.md`](docs/README.md). A green `main` is an integration
claim only; it is not a strength, parity, release, or MVP claim.

## License

Source code is licensed under Apache-2.0. Datasets and model artifacts may have
different licenses and are documented separately.

BattleBelief is an unofficial research project and is not affiliated with
Nintendo, Game Freak, Creatures Inc., Smogon, or Pokémon Showdown.
