# BattleBelief

An open-source Pokémon Singles research bot for decision-making under hidden
information.

> **Status:** M0 repository foundation complete. Battle play, search,
> training, and strength claims are not implemented.

BattleBelief targets current Smogon Gen 9 OU first. Teams are fixed before a
battle; offline team-building and in-battle decision-making are separate
systems.

## Packages

- `battlebelief-core`: pure domain, belief, search, safety, and ports
- `battlebelief-runtime`: public live adapters and CLI
- `battlebelief-lab`: offline oracle, data, training, evaluation, and reporting

The current package boundaries are defined in
[`docs/architecture/code-boundaries.md`](docs/architecture/code-boundaries.md).

## Documentation

Start with [`docs/README.md`](docs/README.md). A green `main` is an integration
claim only; it is not a strength, parity, or MVP claim.

## License

Source code is licensed under Apache-2.0. Datasets and model artifacts may have
different licenses and are documented separately.

BattleBelief is an unofficial research project and is not affiliated with
Nintendo, Game Freak, Creatures Inc., Smogon, or Pokémon Showdown.
