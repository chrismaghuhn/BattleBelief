# Downstream `poke-engine` legal-choice artifact

This directory contains the additive v2 provenance records for
`poke-engine==0.0.49`. The v1 `0.0.48` records under `../engine/` remain
immutable and are not replaced by this release.

The v2 source manifest binds the exact upstream base commit
`bcf13823abc162a608e187b26bbf683f759f385e`, the complete v1 source-manifest
digest, the repository-tracked downstream patch and its SHA-256 digest, and
the complete post-patch source closure. The patched source is not represented
as an upstream commit or tag.

The patch adds the read-only Python API
`poke_engine.legal_choices(state) -> (side_one_choices, side_two_choices)`.
Its only native legality call is `State::root_get_all_options()`, followed by
the existing `movechoice_to_string` conversion. It does not invoke MCTS,
expectiminimax, sampling, evaluation, or Python-side legality reconstruction.

The required target matrix remains CPython 3.12, 3.13, and 3.14 on Ubuntu
24.04 x86-64 and Windows Server 2025 x86-64. The six wheels are published as
the immutable prerelease
`engine-poke-engine-v0.0.49-bcf13823-v2-legal-choices` only after the v2
release verifier accepts the complete release bundle.

This artifact enables a future Task-27 runtime mapping. It does not implement
`TransitionModel.legal_actions()`, change the frozen core port, or claim
mechanics parity, search eligibility, or search strength.
