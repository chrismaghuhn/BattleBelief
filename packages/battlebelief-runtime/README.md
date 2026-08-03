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
