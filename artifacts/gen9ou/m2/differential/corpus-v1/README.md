# Gen9 OU differential corpus v1

`gen9ou-differential` version `1` is the reviewed, data-only Task-28 corpus
freeze. Its canonical index digest is
`sha256:1f68c70b2a3310f2a735c7224a4eb7a017b647f19f9e228dfdbd4eb6033f7f2d`.

The corpus contains 13 project-authored synthetic fixtures. Each is an
RFC8785/JCS canonical JSON document with its own digest, and `index.json`
closes over every fixture file and all 13 Gen9 OU capability IDs from the
Task-26 catalog. Every coverage entry is a `reviewed_fixture`; there are no
preapproved known-divergence boundaries in v1.

The fixtures bind the project synthetic Gen9 OU ruleset identity from
`tests/fixtures/rulesets/gen9ou.json`, the Task-26 catalog identity, the
canonicalization profile, and the frozen differential classifier identity.
They are intentionally minimal mechanics scenarios, not replay data or
protected evaluation data.

This directory is a harness/corpus freeze only. No real Showdown-versus-
`poke-engine` differential qualification was run to create it. It makes no
capability-status, `exact`, or `bounded_approximation` claim. Task 29, after
this corpus is merged, is the separate data-only qualification task and must
not mutate corpus-v1.

Validate the complete closure without executing a backend:

```text
uv run python tools/validate_differential_corpus.py
```
