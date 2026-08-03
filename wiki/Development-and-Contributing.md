# Development and Contributing

BattleBelief treats architecture, documentation, provenance, safety, and reproducibility as repository contracts rather than optional conventions.

## Before contributing

Read these repository documents first:

- `README.md`
- `docs/README.md`
- `docs/architecture/code-boundaries.md`
- `docs/project/contribution-provenance.md`
- the relevant normative contract for the area being changed

The repository documentation is the authoritative technical source. The wiki is an accessible overview and should not silently replace normative contracts.

## Development setup

```bash
git clone https://github.com/chrismaghuhn/BattleBelief.git
cd BattleBelief
python -m pip install uv==0.12.0
uv sync --frozen --all-packages --group dev
```

Supported CI Python versions are 3.12, 3.13, and 3.14.

## Branches and pull requests

- Use a short, descriptive branch name.
- Keep one topic per pull request.
- Add or update tests before changing behavior where practical.
- Explain the affected contract and package boundary.
- Do not combine research-result claims with unrelated implementation changes.
- Keep generated artifacts and large datasets out of the core repository.

## Required checks

Run the repository checks before opening a pull request:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run python tools/check_docs.py
uv run python tools/check_schemas.py
uv run python tools/check_architecture.py
uv run python tools/check_versions.py
```

CI also runs isolated package-wheel smoke tests and dependency review.

## Architecture rules

### Core

`battlebelief-core` contains deterministic domain and application logic. It must not depend on runtime or lab code and must not directly access WebSockets, files, environment variables, databases, concrete engines, GPU frameworks, or global time and randomness.

### Runtime

`battlebelief-runtime` may depend on core. It owns live adapters, CLI composition, protocol translation, authentication, team loading, telemetry adapters, and external command encoding. It must not depend on lab.

### Lab

`battlebelief-lab` may depend on core and approved runtime APIs. It owns offline datasets, oracles, training, evaluation, replay mining, and reporting. Live runtime operation must not depend on lab internals.

### Import direction

```text
battlebelief-runtime → battlebelief-core
battlebelief-lab     → battlebelief-core
battlebelief-lab     → approved battlebelief-runtime APIs
```

Changes that violate these directions should fail the architecture checks.

## Testing responsibilities

| Test area | Responsibility |
|---|---|
| Package tests | Unit behavior and package-local contracts |
| Contract tests | Every adapter against the same port expectations |
| Integration tests | Composition roots and real adapter combinations |
| Differential tests | Pokémon Showdown behavior compared with the qualified simulation engine |
| Release tests | Sealed evaluation and release-specific evidence |

Do not interpret ordinary unit or CI success as release or strength evidence.

## Source provenance

Every contribution must be explainable. Pull requests should make clear that:

- no GPL or otherwise incompatible implementation was copied into the Apache-2.0 codebase;
- borrowed algorithms, ideas, and snippets are identified;
- third-party code has an understood and compatible license;
- AI-generated code has been fully reviewed by the contributor;
- datasets and model artifacts have explicit provenance manifests.

Studying an architecture does not grant permission to copy license-restricted implementation details. Unclear historical code should be reimplemented from permitted specifications rather than transferred blindly.

## Data and model contributions

External data should record:

- source URL;
- exact revision or snapshot;
- license;
- dataset manifest;
- whether labels are observed, reconstructed, or imputed.

Model artifacts should identify their training-data classes and licenses. Large datasets, model weights, checkpoints, and training outputs must not be committed to the core source repository.

## Security and privacy review

Before publishing a change, check for:

- secrets, access tokens, cookies, and credentials;
- usernames and personal replay information;
- local user or drive paths;
- private server addresses;
- non-public datasets;
- unapproved third-party artifacts;
- packed-team content accidentally captured in logs or command histories.

Passing tests does not replace provenance, licensing, privacy, or security review.

## Documentation changes

Normative documents use repository governance, versioning, and validation rules. When behavior changes, update the single authoritative contract rather than creating a conflicting description elsewhere.

Wiki pages should summarize and link to repository documentation. They should not introduce new normative behavior.
