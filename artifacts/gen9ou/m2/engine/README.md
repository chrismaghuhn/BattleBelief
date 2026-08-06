# Task 25 `poke-engine` artifacts

This directory contains the small, canonical provenance records for the
Task-25 Gen-9/Terastallization native artifact. Wheel files are release assets
and are never committed to Git.

The accepted upstream identity is:

- repository: `https://github.com/pmariglia/poke-engine`;
- annotated tag: `v0.0.48`;
- peeled commit: `bcf13823abc162a608e187b26bbf683f759f385e`;
- Git tree: `74d10964d7470b2b9d92ba734550825388178d2d`;
- license: MIT, bound by the source manifest;
- Cargo features: `poke-engine/gen9` and
  `poke-engine/terastallization`, with default features disabled.

The required matrix is CPython 3.12, 3.13, and 3.14 on Ubuntu 24.04 x86-64
and Windows Server 2025 x86-64. Each cell has its own build manifest. The
artifact index becomes `available` only after an isolated install and the real
native sentinel succeed for all six cells.

The sentinel checks artifact identity, native choice enumeration, a normal
transition and reverse round-trip, a real Terastallization transition, and a
small one-thread native MCTS health call. These records do not qualify
Pokémon Showdown mechanics parity, BattleBelief mapping, search eligibility,
deadline safety, or search strength.

The six-cell bundle is published as the immutable prerelease
[`engine-poke-engine-v0.0.48-bcf13823-v1`](https://github.com/chrismaghuhn/BattleBelief/releases/tag/engine-poke-engine-v0.0.48-bcf13823-v1).
The exact asset URLs and final digests are bound by
`engine-artifact-index.json`, whose canonical manifest digest is
`sha256:5b4f59849ff01c6024b7b5f78f95f5457f3f69030bf46822d9f323c911908d98`.

Linux wheel markers can identify CPython, `linux`, and `x86_64`, but not
Ubuntu 24.04. Installation on another x86-64 Linux distribution therefore
does not imply support. The Runtime verifies the actual OS release before any
native import and returns `unsupported_environment` outside the six indexed
cells, without a search call or local build fallback.
