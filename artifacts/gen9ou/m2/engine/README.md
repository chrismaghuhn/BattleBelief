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

The release target is the immutable prerelease tag
`engine-poke-engine-v0.0.48-bcf13823-v1`. The exact release URL and final
digests are bound by `engine-artifact-index.json` after the Publication Gate.
