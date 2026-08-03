---
document_id: evidence-m1-protocol-safe-prototype
title: M1 Protocol-safe Prototype Evidence
document_type: audit
status: accepted
normative: false
version: 1
applies_to:
  - runtime
  - gen9ou
effective_from: 2026-08-03
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-03
---

# M1 Protocol-safe Prototype Evidence

Dieses nichtnormative Audit verpackt die gemessene M1-Evidenz. Es definiert
keine Safety-Regeln, Paketgrenzen, Search-Verträge oder Evaluationsschwellen
neu. Dafür gelten weiterhin der
[`contract-protocol-state`](../contracts/protocol-state.md), der
[`contract-legal-action-safety`](../contracts/legal-action-safety.md) und die
im [Dokumentindex](../README.md) registrierten normativen Quellen.

## Validierter Quellstand

| Feld | Wert |
|---|---|
| `validated_source_commit` | [`952565a92efe24fa528b41b3426cab60b17f4e5b`](https://github.com/chrismaghuhn/BattleBelief/commit/952565a92efe24fa528b41b3426cab60b17f4e5b) |
| Paketversion | `0.2.0` für Workspace, Core, Runtime und Lab |
| Runtime-Status | Phase `M1`, `heuristic_direct_challenge` |
| Protocol-Corpus | [`gen9ou-protocol-m1-v1`](../../tests/fixtures/protocol/corpus.json) |
| Showdown-Referenz | `59da482eabc87245eb62313593e468e81ca537d9` |
| Validierter `main`-Workflow | [`pull-request` Run 30823102367](https://github.com/chrismaghuhn/BattleBelief/actions/runs/30823102367) |
| `pr-gate` im validierten Workflow | `success` |
| Erhebungsdatum | 2026-08-03 |

Der Quellcommit ist der gemergte Task-14-Code-under-Test. Der spätere
Task-15-Dokumentcommit enthält ausschließlich die Evidence-Verpackung und ist
nicht zirkulär als sein eigener validierter Quellstand angegeben.

## Lokale Verifikation

Die folgenden Befehle liefen am validierten Quellstand unter Windows mit
CPython 3.14.5. Jeder aufgeführte Befehl endete mit Exitcode 0.

| Befehl | Gemessenes Ergebnis |
|---|---|
| `uv lock --check` | Lockfile konsistent; 27 Pakete aufgelöst |
| `uv run ruff format --check .` | 122 Dateien bereits formatiert |
| `uv run ruff check .` | keine Lintfehler |
| `uv run mypy` | keine Fehler in 63 Source-Dateien |
| `uv run pytest` | 827 Tests bestanden |
| `uv run python tools/check_versions.py` | Workspace- und Paketversionen sowie interne Exact-Requirements lockstep |
| `uv run python tools/check_architecture.py` | Paketimport- und Abhängigkeitsgrenzen bestanden |
| `uv run python tools/check_docs.py` | Dokumentautorität, Links, Migration und Archivintegrität bestanden |
| `uv run python tools/check_schemas.py` | Schemas, Beispiele, IDs und Kanonisierung bestanden |
| `uv run python tools/smoke_packages.py` | isolierte Core-, Runtime- und Lab-Wheels gebaut, installiert und geprüft |
| `uv run battlebelief doctor` | `0.2.0`, Phase `M1`, Entry-Point ready, Capability `heuristic_direct_challenge` |
| `uv run pytest tests/smokes/test_protocol_smoke.py -v` | 2 Tests bestanden |
| `uv run pytest tests/smokes/test_safety_smoke.py -v` | 29 Tests bestanden |
| `uv run pytest tests/integration/test_challenge_coordinator.py -v` | 183 Tests bestanden |

Die negative Scope-Suche wurde mit diesem Befehl ausgeführt:

```powershell
rg -n "poke_engine|poke-engine|DUCT|MCTS|BeliefState|duckdb|pyarrow|torch|onnx|/search" packages tests .github
```

Sie fand genau einen Treffer. Dieser Treffer ist der Negativtest, der `/search`
und weitere nicht erlaubte Challenge-Kommandos ausdrücklich ausschließt; ein
ausführbarer M2+-Pfad wurde nicht gefunden.

## GitHub-Actions-Matrix

Der verlinkte Workflow lief für exakt `validated_source_commit`.

| Job | Betriebssystem | Python | Gemessenes Ergebnis |
|---|---|---:|---|
| `quality-py3.12` | Ubuntu 24.04 | 3.12 | 827 Tests und Repository-Gates bestanden |
| `quality-py3.13` | Ubuntu 24.04 | 3.13 | 827 Tests und Repository-Gates bestanden |
| `quality-py3.14` | Ubuntu 24.04 | 3.14 | 827 Tests und Repository-Gates bestanden |
| `protocol-smoke` | Ubuntu 24.04 | 3.14 | 2 Tests bestanden |
| `safety-smoke` | Ubuntu 24.04 | 3.14 | 29 Tests bestanden |
| `package-smoke-ubuntu-24.04` | Ubuntu 24.04 | 3.14 | isolierte Wheels bestanden |
| `package-smoke-windows-2025` | Windows 2025 | 3.14 | isolierte Wheels bestanden |
| `dependency-review` | — | — | beim `push`-Workflow bewusst übersprungen |
| `pr-gate` | Ubuntu 24.04 | — | `success` |

## Protocol-Corpus

Jede registrierte Fixture wurde zweimal aus einem frischen Zustand verarbeitet.
Endzustand, Eventtypenfolge, terminale Klassifikationen und Unknown-Zähler
waren zwischen beiden Läufen wertgleich.

| Fixture | Nichtleere Zeilen | Reduzierte Events | Terminalklassifikationen | Unknown | Fehler | `ignored_display_count` |
|---|---:|---:|---:|---:|---:|---:|
| `metadata-and-preview.txt` | 19 | 18 | 0 | 0 | 0 | 0 |
| `state-transitions.txt` | 57 | 56 | 0 | 0 | 0 | 0 |
| `evidence-and-display.txt` | 41 | 37 | 3 | 0 | 0 | 10 |

Die drei terminalen Beobachtungen wurden gezielt als `timer_or_forfeit`
klassifiziert und nicht als Parserfehler verschluckt.

## Action-Safety-Smoke

Der Safety-Smoke umfasst 29 voneinander isolierte Fälle. Die Summenzeile ist
deshalb ein Testfall-Aggregat mit Nenner 29 und keine Telemetrie eines einzelnen
Battles. Jede tatsächlich gesendete Submission wurde im Test gegen Raum,
aktuelle RequestIdentity, `rqid`, Provenance und das damalige SafeSubmissionSet
geprüft.

| Szenariogruppe | Fälle | Resultat je Fall | Explicit | Default | Room-Control | Ignored Display |
|---|---:|---|---:|---:|---:|---:|
| Move, Request-after-turn, Forced Switch, Revival, Tera, `maybeTrapped`, Team Preview, Pending-Reconciliation, neuester Pending-Request, Duplicate-Suppression und Raumisolation | 11 | Erfolg | 1 je Fall | 0 | 0 | 0 |
| Wait, Battle-Ende bei Pending-Request und `inactiveoff` | 3 | Erfolg ohne Send | 0 | 0 | 0 | 0 |
| explizite Submission, danach serverdelegiertes `default` | 1 | Erfolg | 1 | 1 | 0 | 0 |
| Room-Control/Chat vor Reconciliation | 1 | Erfolg | 1 | 0 | 4 | 0 |
| Chat nach erfolgreicher Submission | 1 | Erfolg, Duplicate unterdrückt | 1 | 0 | 1 | 0 |
| nackter Pipe-Spacer | 1 | Erfolg ohne Send | 0 | 0 | 0 | 1 |
| nichtterminale `-message`-Anzeige | 1 | Erfolg ohne Send | 0 | 0 | 0 | 1 |
| stale Request nach gültiger Submission | 1 | `stale_rqid` | 1 | 0 | 0 | 0 |
| Server Invalid/Unavailable nach gültiger Submission | 2 | klassifizierter Serverfehler | 1 je Fall | 0 | 0 | 0 |
| missing `rqid`, Policy außerhalb Safe Set, unknown, malformed und drei Timer-/Forfeit-Formen | 7 | klassifizierter Abbruch ohne Send | 0 | 0 | 0 | 0 |
| **Summe über 29 isolierte Fälle** | **29** | — | **17** | **1** | **5** | **2** |

Die Fehlerfälle bewahren gegebenenfalls eine bereits zuvor validierte
Submission, senden aber keine weitere Aktion nach dem primären Fehler.

## Challenge-Setup

Ein fokussierter Lauf mit 28 Fällen bestätigte die drei beobachtbaren
Challenge-Setup-Subcodes:

```powershell
uv run pytest tests/integration/test_challenge_coordinator.py -v -k "test_each_allowlisted_global_message_is_a_fully_matched_explicit_rejection or test_setup_deadline_classifies_only_the_observed_challenge_state or test_initial_not_pending_without_a_room_is_a_setup_timeout"
```

| Subcode | Gemessene Fälle | Beobachtung |
|---|---:|---|
| `challenge_command_rejected_explicit` | 24 | zwölf exakte allowlistete Nachrichten, jeweils als `popup` und `error` |
| `challenge_not_pending` | 1 | zuvor pending, zuletzt not pending, kein Zielraum bis zur Deadline |
| `challenge_setup_timeout` | 3 | pending oder initial/not-pending ohne rechtzeitig bewiesenen Zielraum |

Teamvalidation blieb die separate Primärklasse `team_validation_error` und
wurde nicht zusätzlich als Challenge-Subcode ausgegeben. Der vollständige
Coordinator-Integrationstest mit 183 Fällen prüfte außerdem Single-Reader-
Handoff, Fremdräume, Bootstrap-Grenze, Suchzustand, Close-Fehlerpriorität und
Packed-Team-Integrität.

## Abdeckungsstatus und Grenzen

```text
synthetic contract coverage: complete for the declared M1 mapping
observed live protocol coverage: not established
```

Es wurde kein öffentlicher Showdown-Login und keine öffentliche Challenge
ausgeführt. Es wurden keine realen Credentials verwendet oder aufgezeichnet. Der
Runtimepfad ist auf eine ausgehende direkte Gen-9-OU-Challenge begrenzt; der
Gegner muss sie annehmen. Die kontrollierte Wiederholbarkeit ist für den
synthetischen Corpus, Fake-Transport und die deklarierte M1-Zuordnung belegt,
nicht für das öffentliche Live-Protokoll.

M1 enthält keine Engine-Parity, kein Belief, keinen Searchpfad, kein Training,
keine Ladder-Automation und keinen Strength- oder MVP-Nachweis. Ein grüner
Workflow ist ausschließlich Integrations- und Contract-Evidenz.
