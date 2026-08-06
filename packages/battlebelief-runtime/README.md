# battlebelief-runtime

Public runtime package and CLI for BattleBelief. Its boundaries are defined in
[`docs/architecture/code-boundaries.md`](../../docs/architecture/code-boundaries.md).

The package status is version `0.2.0`, phase `M1`, with
`battle_capability: heuristic_direct_challenge`. This identifies the tested M1
runtime path; it is not a strength, engine-parity, ladder-readiness, release, or
MVP claim. Observed live public-protocol coverage is not established.

## Outgoing direct challenge

The `challenge` command starts one outgoing direct Gen 9 OU challenge. The
opponent must accept it before the battle starts:

```text
battlebelief challenge --username USER --opponent USER --team PATH [--server-url URL]
```

The Showdown password is read only when this command is invoked, exclusively
from `BATTLEBELIEF_SHOWDOWN_PASSWORD`. There is no password command-line
argument. Do not place credentials or packed-team content in command-line
arguments, logs, or captured output.

The frozen Task 12 defaults are:

```text
server URL: wss://sim3.psim.us/showdown/websocket
challenge setup timeout: 120.0 seconds
```

`--server-url` accepts only the official endpoint shown above, optionally with
the explicit TLS port `:443`. This trust binding prevents an official login
assertion from being sent to another WebSocket host. Private Showdown servers
aren't supported because authentication remains coupled to the official
Showdown assertion endpoint. The transport-pinned M1 path also ignores ambient
operating-system and environment proxy settings.

The team file must be UTF-8 and contain exactly one structurally valid Showdown
packed-team line. Showdown performs Gen 9 OU legality validation later during
challenge setup. Local argument, configuration, secret, and team-file failures
return exit code `2` before connection construction. Setup, transport, and
battle failures return `1`; an interrupted or nonterminal run returns `1`
without exposing a traceback or raw exception message. Any completed battle
outcome (win, loss, or tie) without a primary error returns `0`.

Public-network execution is not part of automated validation and requires
separate maintainer approval with a dedicated test account.

## Optional native search artifact

The `search` extra installs one digest-bound `poke-engine` wheel from the
project's immutable Task-25 artifact prerelease on a matching CPython 3.12,
3.13, or 3.14 Linux x86-64 or Windows AMD64 environment. It is not a base
dependency, and the Runtime never invokes Cargo, maturin, or another source
build fallback.

The qualified install smoke uses `pip --no-compile --only-binary=:all:`.
Disabling bytecode compilation prevents an installer-generated, unhashed
`.pyc` from entering the RECORD closure; the Runtime rejects such unverifiable
installation additions.

Package installation is not a support claim. Before importing the native
extension, the Runtime accepts only the six artifact-index cells: Ubuntu 24.04
x86-64 and Windows Server 2025 x86-64 for those three CPython versions. Other
Linux distributions fail closed as `unsupported_environment` even if their
packaging markers allowed the wheel to be installed.
