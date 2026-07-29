# Contributing

Read [`docs/README.md`](docs/README.md) and
[`docs/project/contribution-provenance.md`](docs/project/contribution-provenance.md)
before opening a pull request.

Use a short branch, keep one topic per pull request, add tests before behavior,
and run:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run python tools/check_docs.py
uv run python tools/check_schemas.py
uv run python tools/check_architecture.py
uv run python tools/check_versions.py
```

Do not submit credentials, ladder cookies, replay corpora, model weights,
incompatible code, or code whose provenance you cannot explain.
