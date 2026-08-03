# battlebelief-core

Pure, dependency-light domain and application package for BattleBelief. Current
boundaries are defined in
[`docs/architecture/code-boundaries.md`](../../docs/architecture/code-boundaries.md).

Version `0.2.0` contains the M1 protocol-safe Core:

- immutable canonical battle events;
- deterministic observed-state reduction;
- normalized decision requests and reconciliation;
- authoritative safe submission sets;
- deterministic heuristic selection; and
- independent action and `rqid` safety validation.

WebSockets, files, environment access, concrete engines, belief, search,
oracles, datasets, training, and evaluation remain outside this package or
belong to later milestones.
