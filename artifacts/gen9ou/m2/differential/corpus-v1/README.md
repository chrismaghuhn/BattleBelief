# Gen9 OU differential corpus v1

`gen9ou-differential` version `1` is the reviewed, data-only Task-28 corpus
freeze. Its canonical index digest is
`sha256:0630f696c0ff07210202356aecc51fc1bb447f2cb4c04199b82ea3802d5cc21a`.

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
