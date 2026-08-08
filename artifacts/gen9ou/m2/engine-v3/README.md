# Downstream `poke-engine` resolved-action-order artifact

This directory contains the additive v3 source provenance for the planned
`poke-engine==0.0.50` artifact. The immutable v1 `0.0.48` and v2 `0.0.49`
artifact records remain unchanged.

The v3 source manifest binds the accepted upstream `v0.0.48` base, followed
by an explicit ordered patch chain: first the existing legal-choice binding,
then the resolved-action-order binding. The latter adds the read-only
`StateInstructions.resolved_action_order` Python property. Each returned
branch carries the two already selected sides in the native resolution order
as `("p1", "p2")` or `("p2", "p1")`; no Python priority, speed, switch, or
tie calculation is introduced.

The six-cell candidate workflow builds CPython 3.12, 3.13, and 3.14 wheels for
Ubuntu 24.04 x86-64 and Windows Server 2025 x86-64, runs the upstream native
binding tests and the staged-wheel smoke, and creates both a candidate index
and an available-index publication candidate that binds each cell's sentinel.
The immutable prerelease tag is created only after merge from `main`, after all
six wheel and sentinel records are available and the v3 release verifier
accepts the complete closure.

The native Speed-Tie audit deliberately retains branch-local action-order
metadata even where two branches have the same resulting serialized state.
Consequently, the Task-27 Runtime observation successor is blocked until a
separate Runtime transition-metadata/coalescing predecessor can retain this
branch-local distinction without changing transition semantics. This artifact
does not modify Runtime coalescing, expose a Runtime observation surface,
qualify any capability, or make a mechanics-parity claim.
