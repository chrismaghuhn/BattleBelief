# Getting Started

This page describes the current development setup and the available outgoing direct-challenge command. BattleBelief is still under active development; the current CLI path is not a strength, release, or MVP claim.

## Requirements

- Git
- Python **3.12, 3.13, or 3.14**
- `uv` **0.12.0** for the repository's locked development workflow
- A dedicated Pokémon Showdown test account for approved public-network testing

## Clone and install

```bash
git clone https://github.com/chrismaghuhn/BattleBelief.git
cd BattleBelief
python -m pip install uv==0.12.0
uv sync --frozen --all-packages --group dev
```

The workspace contains three packages:

- `battlebelief-core`
- `battlebelief-runtime`
- `battlebelief-lab`

The command-line entry point is named `battlebelief` and is provided by `battlebelief-runtime`.

## Run the repository checks

Run the same principal checks used by pull-request CI:

```bash
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run python tools/check_versions.py
uv run python tools/check_architecture.py
uv run python tools/check_docs.py
uv run python tools/check_schemas.py
```

An isolated package-wheel smoke test is also available:

```bash
python tools/smoke_packages.py
```

## Outgoing direct challenge

The current CLI can start one outgoing direct Gen 9 OU challenge:

```text
battlebelief challenge --username USER --opponent USER --team PATH [--server-url URL]
```

Run it through the workspace environment:

```bash
uv run battlebelief challenge \
  --username YOUR_USERNAME \
  --opponent OPPONENT_USERNAME \
  --team path/to/team.txt
```

The opponent must accept the challenge before the battle begins.

## Configure the password safely

The Showdown password is read only from `BATTLEBELIEF_SHOWDOWN_PASSWORD`. There is intentionally no password command-line option.

### PowerShell

```powershell
$env:BATTLEBELIEF_SHOWDOWN_PASSWORD = "your-password"
uv run battlebelief challenge --username YOUR_USERNAME --opponent OPPONENT_USERNAME --team .\team.txt
```

Remove it from the current PowerShell session afterward:

```powershell
Remove-Item Env:BATTLEBELIEF_SHOWDOWN_PASSWORD
```

### Bash

```bash
export BATTLEBELIEF_SHOWDOWN_PASSWORD='your-password'
uv run battlebelief challenge --username YOUR_USERNAME --opponent OPPONENT_USERNAME --team ./team.txt
unset BATTLEBELIEF_SHOWDOWN_PASSWORD
```

Never put credentials or packed-team contents in command-line arguments, logs, screenshots, issues, or commits.

## Team file requirements

The team file must:

- be UTF-8 encoded;
- contain exactly one structurally valid Pokémon Showdown packed-team line;
- avoid extra lines or unrelated text.

Pokémon Showdown performs Gen 9 OU legality validation during challenge setup.

## Network restrictions

The default and currently trusted WebSocket endpoint is:

```text
wss://sim3.psim.us/showdown/websocket
```

The optional `--server-url` argument accepts only that official endpoint, with an optional explicit `:443` TLS port. Private Showdown servers are not supported by the current authentication path.

Public-network execution is intentionally excluded from automated validation and requires maintainer approval with a dedicated test account.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | A battle completed with a win, loss, or tie and no primary runtime error |
| `1` | Setup, transport, battle, interruption, or nonterminal runtime failure |
| `2` | Local argument, configuration, secret, or team-file validation failure before connection construction |

## Troubleshooting

### `battlebelief` is not found

Use the workspace runner:

```bash
uv run battlebelief --help
```

Then verify that the locked workspace was installed:

```bash
uv sync --frozen --all-packages --group dev
```

### Authentication fails

Confirm that:

- the username is correct;
- `BATTLEBELIEF_SHOWDOWN_PASSWORD` exists in the same shell session;
- the official server endpoint is being used;
- the account is a dedicated test account approved for this work.

### The challenge does not start

The opponent must be online and must accept the direct challenge before the setup timeout expires.
