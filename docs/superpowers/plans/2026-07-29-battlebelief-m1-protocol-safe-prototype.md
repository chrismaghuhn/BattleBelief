---
document_id: plan-m1-protocol-safe-prototype
title: BattleBelief M1 Protocol-safe Prototype Implementation Plan v3.1
document_type: roadmap
status: proposed
normative: false
version: 3
applies_to:
  - repository
  - runtime
  - gen9ou
effective_from: 2026-07-30
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-30
---

# BattleBelief M1 Protocol-safe Prototype Implementation Plan v3.1

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine kampffähige, rein heuristische Gen-9-OU-Runtime bauen, die
Pokémon-Showdown-Frames raumtreu verarbeitet, sichtbaren Zustand
deterministisch reduziert, ausschließlich Aktionen aus einem konservativen
request-abgeleiteten `SafeSubmissionSet` sendet und alle Abbrüche
klassifiziert.

**Architecture:** Runtime-Code dekodiert WebSocket-Frames in raumgebundene
Nachrichten, trennt `|request|` vom öffentlichen Battle-Eventstrom und
übersetzt beide Seiten in unveränderliche Core-Objekte. Jeder neue
entscheidungspflichtige Request löst sofort Reconciliation aus. Bei
`ACCEPT` folgen Policy, unabhängiges Safety-Gate und Versand; bei noch
fehlender öffentlicher Zustandsbasis wird ausschließlich dieser Request
begrenzt pending gehalten. `|turn|` ist niemals der Entscheidungstrigger. Der
Core kennt weder WebSocket-Zeilen, Showdown-JSON, Dateipfade noch
Credentials.

**Tech Stack:** Python 3.12–3.14, unveränderliche `dataclass`-Objekte,
`asyncio`, Standardbibliothek für HTTP-Login, `websockets==16.1.1` für den
sauberen Runtime-Adapter, bestehendes `pytest`/Ruff/mypy/uv-Tooling.

**Plan revision:** v3.1 ist eine gezielte Vor-Freeze-Korrektur des noch
unveröffentlichten vorgeschlagenen v3-Plans. Das ganzzahlige
Frontmatter-`version` bleibt deshalb 3.

---

## 0. Vertragsbasis und eingefrorener Scope

Dieser Plan operationalisiert ausschließlich:

- [`contract-protocol-state`](../../contracts/protocol-state.md);
- [`contract-legal-action-safety`](../../contracts/legal-action-safety.md);
- [`architecture-code-boundaries`](../../architecture/code-boundaries.md);
- [`architecture-dependency-matrix`](../../architecture/dependency-matrix.md);
- [`team-contract`](../../teams/team-contract.md);
- [`project-github-ci-security`](../../project/github-ci-security.md);
- [`transfer-audit`](../../transfer-audit/README.md);
- M1 aus [`roadmap-milestones`](../../roadmap/milestones.md).

Normative Schwellen werden hier nicht neu definiert. Bei Widerspruch gilt der
verlinkte akzeptierte Contract.

### M1 enthält

- einen sauberen Showdown-Client mit Login;
- einen einzelnen direkten Gen-9-OU-Challenge-Pfad, keine Ladder-Suche;
- raumerhaltende WebSocket-Frame-Dekodierung;
- explizite Klassifikation gemischter Room-, Chat- und Battle-Payloads;
- einen versionierten synthetischen Gen-9-OU-Protocol-Corpus;
- kanonische unveränderliche BattleEvents;
- einen deterministischen ObservationReducer;
- unveränderliche, normalisierte DecisionRequests;
- ein konservatives Submission Set einschließlich Tera-, Switch-, Revival-,
  Team-Preview- und `default`-Choices;
- eine deterministische Heuristikpolicy;
- ein unabhängiges Action-Safety-Gate;
- einen Fixed-Team-Loader für echtes Showdown-Packed-Format;
- klassifizierte Fehler und merge-blockierende Smokes.

### M1 enthält nicht

- `poke-engine`, lokale Showdown-Oracle-Prozesse oder Differentialtests;
- Belief, Search, DUCT/MCTS, Training, Replay- oder Dataset-Ingestion;
- PyTorch, ONNX, DuckDB, Parquet, CUDA oder Kaggle;
- Ladder-Automation, Parallelbattles oder Cross-Battle-Lernen;
- Export-zu-Packed-Konvertierung;
- vollständige lokale Smogon-Teamlegalitätsprüfung;
- alte Generationen, andere Tiers, Doubles oder VGC;
- Strength-, Parity-, Release- oder MVP-Claims.

### Externe Referenzrevision

Die M1-Fixtures und Protokollannahmen werden gegen diesen Showdown-Snapshot
entwickelt:

```text
repository: smogon/pokemon-showdown
branch: master
commit: 59da482eabc87245eb62313593e468e81ca537d9
captured_at: 2026-07-30
```

Verwendete Primärquellen:

- `PROTOCOL.md` für Raumframes, Room-/Battle-Multiplexing, Login,
  Challenge-State und Challenge-Kommandos;
- `sim/SIM-PROTOCOL.md` für Requests, Choices, `rqid` und Fehler;
- `sim/TEAMS.md` für Packed-Team-Syntax;
- `sim/side.ts` derselben Revision für die aktuellen Request-Felder
  `trapped`, `maybeTrapped`, `maybeDisabled`, `maybeLocked` und
  `canTerastallize`;
- `sim/pokemon.ts` derselben Revision für das `reviving`-Feld des
  Switch-Requests;
- `server/chat-commands/core.ts`, `server/ladders.ts` und
  `server/ladders-challenges.ts` derselben Revision für die vollständigen,
  expliziten Challenge-Setup-Antworten und den tatsächlich emittierten
  PM-Challenge-State;
- websockets-16.1.1-Dokumentation für `websockets.asyncio.client.connect`.

Tests greifen nicht auf `master` oder das öffentliche Netzwerk zu. Die
Revision steht im Corpus-Manifest und wird nur durch einen bewussten
Corpus-Update-PR geändert.

## 1. Vorabentscheidungen in v3

### 1.1 Client-Ansatz

v3 empfiehlt und plant **Option A: saubere Eigenimplementierung anhand der
offiziellen Spezifikation**. Die Zustimmung zu diesem Plan akzeptiert diese
reversible M1-Entscheidung.

| Weg | Gewinn | Preis |
|---|---|---|
| A – sauberer eigener Adapter | kleinste Runtime-Oberfläche, volle Kontrolle über Raum-, Request- und Safety-Semantik | Auth, Reconnect und Tests müssen selbst gepflegt werden |
| B – selektiver Transfer aus dem historischen VGC-Projekt | eventuell weniger Erstaufwand | Provenance-, Lizenz-, Bug- und Singles-Audit vor jeder Einheit; alte Annahmen können versteckt bleiben |
| C – Bot-Framework | schneller Funktionsumfang | zusätzliche Abhängigkeit und fremdes Zustandsmodell erschweren die eingefrorenen Core-Grenzen |

Selektiver Transfer bleibt später möglich, aber nicht als Voraussetzung für
M1. Ein späterer Transfer ersetzt nur einen Runtime-Leaf-Adapter und benötigt
den bestehenden Transfer-Audit.

### 1.2 Legalität unter absichtlich verborgener Information

Showdown kann `maybeTrapped`, `maybeDisabled` oder `maybeLocked` senden. Eine
versuchte Aktion kann erst danach mit `Unavailable choice` beantwortet und der
Request aktualisiert werden. M1 bezeichnet deshalb:

```text
request-derived domain
  = alle durch den aktuellen Request strukturell angebotenen Aktionen

explicit safe actions
  = konservative konkrete Teilmenge, die M1 ohne absichtliches Reveal-Risiko
    lokal validiert

server-delegated fallback
  = das für diesen Request zugelassene `default`-Kommando; Showdown bestimmt
    die dadurch ausgeführte konkrete Aktion

safe submission set
  = explizite sichere Aktionen plus optionaler server-delegierter Fallback
```

Regeln:

- bei `trapped` oder `maybeTrapped` keine freiwilligen Switch-Aktionen;
- bei `maybeDisabled` oder `maybeLocked` ausschließlich `default`;
- `default` ist bei jedem entscheidungspflichtigen Request die letzte sichere
  Fallback-Aktion;
- bei einem `reviving`-Request ausschließlich gefaintete, wiederbelebbare
  Team-Slots plus `default`;
- konkrete Moves kommen nur aus nicht deaktivierten Request-Moves;
- eine Tera-Variante wird nur erzeugt, wenn `canTerastallize` einen nicht
  leeren Tera-Typ enthält;
- serverseitige Zurückweisung wird sofort klassifiziert und beendet den
  M1-Battlepfad; sie wird nicht durch Retry-Zähler verborgen.

Jede Submission trägt `ActionProvenance.EXPLICIT_REQUEST` oder
`ActionProvenance.SERVER_DEFAULT`. Runtime-Evidence zählt
`default_submissions` getrennt. Für `default` behauptet BattleBelief nur die
lokale Zulässigkeit des Fallback-Kommandos, nicht lokale Validierung der von
Showdown intern gewählten konkreten Aktion.

Diese Konservativität kostet Spielstärke: Ein legaler Switch kann bei
`maybeTrapped` ungenutzt bleiben und `default` kann strategisch schwach sein.
M1 priorisiert das Safety-Gate; Search-Qualität beginnt erst in M2.

### 1.3 Request-ID-Profil

Das offizielle Simulatorprotokoll erlaubt Requests ohne `rqid`, insbesondere
bei direkter Simulatornutzung. M1 implementiert aber den WebSocket-
Serverpfad aus `contract-legal-action-safety` und verlangt dort ein
nichtnegatives ganzzahliges `rqid`.

Ein fehlendes oder falsch typisiertes Live-`rqid` führt fail-closed zu
`request_state_reconciliation_mismatch`. Der direkte lokale Simulatoradapter
kommt erst in M2 und erhält eine eigene typisierte Request-Identität; M1
erfindet dafür keine Wire-Semantik.

## 2. Bindender Datenfluss

```text
raw WebSocket frame
→ Runtime FrameDecoder
→ RoomLine(room_id, payload)
→ BattleCoordinator room routing
→ Runtime RoomPayloadClassifier
→ BattleSession

RoomPayloadClassifier
├─ battle_event
├─ decision_request
├─ battle_error
├─ timer_message
├─ room_control_or_chat
└─ unknown

ordinary battle line
→ Runtime ProtocolParser
→ immutable Core BattleEvent
→ Core ObservationReducer
→ immutable ObservedState

|request| JSON
→ Runtime RequestReader
→ immutable Core DecisionRequest + SafeSubmissionSet
→ Core RequestReconciler
→ Core HeuristicPolicy
→ Core ActionSafetyGate
→ Runtime CommandEncoder
→ room-prefixed /choose command
```

`|request|` ist eine parallele autoritative Eingabe für eigene Aktionen und
wird nicht als BattleEvent missbraucht. Der Request darf den sichtbaren
Battle-Zustand nicht mit privaten Feldern hydratisieren.

`room_control_or_chat` erreicht weder den `ProtocolParser` noch den Reducer.
Der Klassifikator betrachtet ausschließlich den äußeren Message-Type. Inhalt
aus Chat-, HTML- oder Plaintext-Nachrichten wird niemals erneut nach
eingebetteten `|request|`-, `|move|`- oder anderen Protokollfragmenten
durchsucht und standardmäßig nicht in Evidence-Logs geschrieben; lediglich
der aggregierte Zähler bleibt erhalten.

## 3. Fehlerzuordnung

Jeder Abbruch besitzt genau eine primäre Klasse.

| Beobachtung | Primärklasse |
|---|---|
| unbekannter nicht allowlisteter Battle-Wire-Typ | `unknown_protocol_event` |
| unbekannter room-scoped Payload-Typ | `unknown_protocol_event` |
| nicht allowlistete globale Setup-Antwort | `unknown_protocol_event` |
| kaputte Feldzahl, ungültige Zahl, ungültiges JSON/HP-Format | `malformed_protocol_message` |
| gültiges Event verletzt eine Reducer-Invariante | `reducer_invariant_failure` |
| Request passt nicht zu Raum, Side, Singles-Scope, State oder `rqid`-Profil | `request_state_reconciliation_mismatch` |
| Verbindungs-/Read-/Write-Deadline | `transport_timeout` |
| unerwarteter Socket-Abbruch oder Login-Abbruch | `disconnect` |
| terminale Timer-/Forfeit-Nachricht im Corpus | `timer_or_forfeit` |
| Policy-Submission fehlt im neuesten SafeSubmissionSet | `local_action_gate_rejection` |
| Kandidat gehört zu einer älteren RequestIdentity | `stale_rqid` |
| `|error|[Invalid choice]` | `server_invalid_choice` |
| `|error|[Unavailable choice]` | `server_unavailable_choice` |
| entscheidungspflichtiger Request hat selbst nach `default` keine Aktion | `no_legal_action_available` |
| eindeutig erkannte Teamvalidation vor Raumstart | `team_validation_error` |
| Challenge-Setup scheitert mit beobachtbarer Evidenz | `challenge_setup_error` plus Subcode |

Bekannte `room_control_or_chat`-Payloads sind kein Abbruch. Sie erhöhen nur
`room_control_or_chat_count`. Die beiden Setup-Klassen liegen vor
BattleSession-Start und ergänzen die zentralen Battle- und Action-Contracts;
sie werden nicht als Battle-Ausgang fortgeschrieben. Jede Runtime-Exception
trägt genau einen primären `code`; `ChallengeSetupError` trägt zusätzlich
genau einen beobachtbaren `subcode`.

Engine- und Modellfehlerklassen aus dem normativen Safety-Contract werden erst
mit den zugehörigen M2-/M4-Subsystemen konkret implementiert. M1 legt keine
unbenutzten Engine- oder Modelladapter an.

## 4. Datei- und Verantwortungslandkarte

```text
packages/battlebelief-core/src/battlebelief_core/
├─ domain/
│  ├─ events/
│  │  ├─ base.py                 # BattleEvent marker and shared annotations
│  │  ├─ metadata.py             # player, teamsize, gen, tier, rule, preview
│  │  ├─ progress.py             # start, turn, win, tie
│  │  ├─ pokemon.py              # move, switch, HP, status, item, ability, tera
│  │  ├─ field.py                # weather, field and side conditions
│  │  ├─ evidence.py             # visible nonpersistent decision evidence
│  │  └─ ignored.py              # explicit cosmetic/display allowlist result
│  ├─ state/
│  │  ├─ values.py               # HP, evidence intervals, effect counters
│  │  ├─ pokemon_view.py
│  │  ├─ side_view.py
│  │  └─ observed_state.py
│  ├─ actions/
│  │  ├─ submission.py
│  │  └─ decision_request.py
│  └─ teams/
│     └─ sealed_team.py           # digest and member count, no packed wire
├─ application/
│  ├─ observation/reducer.py
│  ├─ decision/heuristic_policy.py
│  └─ safety/
│     ├─ request_reconciler.py
│     └─ action_gate.py
└─ errors.py

packages/battlebelief-runtime/src/battlebelief_runtime/
├─ adapters/
│  ├─ showdown_protocol/
│  │  ├─ frame_decoder.py
│  │  ├─ room_payload_classifier.py
│  │  ├─ parser.py
│  │  ├─ challenge_state_reader.py
│  │  ├─ request_reader.py
│  │  └─ command_encoder.py
│  ├─ showdown_client/
│  │  ├─ types.py
│  │  ├─ auth.py
│  │  └─ connection.py
│  └─ team_files/
│     ├─ packed_team.py
│     └─ loader.py
├─ composition/
│  ├─ battle_session.py
│  └─ battle_coordinator.py
├─ errors/
│  ├─ protocol.py
│  ├─ actions.py
│  └─ setup.py
├─ public_api/status.py
└─ cli.py

packages/battlebelief-runtime/src/battlebelief_runtime/testing/
├─ fake_connection.py
└─ fixtures.py

tests/
├─ contracts/
│  ├─ test_protocol_contract.py
│  └─ test_action_safety_contract.py
├─ integration/
│  ├─ test_battle_session.py
│  └─ test_challenge_coordinator.py
├─ smokes/
│  ├─ test_protocol_smoke.py
│  └─ test_safety_smoke.py
└─ fixtures/
   ├─ protocol/
   │  ├─ corpus.json
   │  ├─ metadata-and-preview.txt
   │  ├─ state-transitions.txt
   │  └─ evidence-and-display.txt
   ├─ requests/
   │  ├─ move.json
   │  ├─ move-tera.json
   │  ├─ maybe-trapped.json
   │  ├─ forced-switch.json
   │  ├─ reviving.json
   │  ├─ team-preview.json
   │  └─ wait.json
   ├─ frames/
   │  ├─ login-and-battle.txt
   │  ├─ two-rooms.txt
   │  └─ battle-room-multiplex.txt
   └─ teams/
      └─ gen9ou-example-packed.txt
```

Jede Datei besitzt genau die oben angegebene Verantwortung. Insbesondere
parst weder `belief` noch `decision` Wire-Nachrichten; Runtime-Leaf-Adapter
konstruieren sich nicht gegenseitig.

## 5. PR-Topologie

M1 wird in fünf seriellen Pull Requests umgesetzt. Jeder PR basiert auf dem
jeweils gemergten `main`; es gibt keine gestapelten offenen PRs.

| PR | Branch | Aufgaben | Claim |
|---|---|---|---|
| 1 | `docs/m1-client-and-corpus` | 1 | Entscheidung und Corpus-Scope, kein Runtime-Claim |
| 2 | `feat/m1-core-protocol` | 2–5 | getestete Core-Typen, Reducer, Safety |
| 3 | `feat/m1-runtime-protocol` | 6–8 | Frame-, Parser-, Request-, Team-Adapter |
| 4 | `feat/m1-showdown-session` | 9–12 | Client, Session, Challenge-CLI |
| 5 | `test/m1-acceptance` | 13–15 | Smokes, CI, Status und M1-Evidence |

Innerhalb eines PRs folgen kleine TDD-Commits den Tasks. Squash-Merge bleibt
Repositorypolitik; keine Akzeptanzregel zählt Commits.

---

## Task 1 – Cliententscheidung und Protocol-Corpus verankern

**Files:**

- Create: `docs/adr/ADR-0004-clean-showdown-runtime-adapter.md`
- Modify: `docs/README.md`
- Create: `tests/fixtures/protocol/corpus.json`
- Modify: `docs/superpowers/plans/2026-07-29-battlebelief-m1-protocol-safe-prototype.md`

- [x] **Step 1: Decision-Issue aus dem vorhandenen Formular erstellen**

Titel:

```text
Decision: clean Showdown runtime adapter for M1
```

Die Entscheidung hält fest:

```text
chosen: clean implementation from official protocol
runtime dependency: websockets==16.1.1
historical VGC transfer: deferred; every transferred unit needs transfer audit
framework dependency: rejected for M1
scope: one authenticated Gen9 OU direct-challenge session
non-goals: ladder search, reconnect loop, multi-battle concurrency
```

- [x] **Step 2: ADR-0004 schreiben**

Der ADR erklärt Kontext, Entscheidung, die drei Alternativen, obige
Trade-offs und den Reversal-Punkt: Nur die Runtime-Connection hinter ihrer
öffentlichen Schnittstelle darf später ersetzt werden. Er definiert keine
zweite Importregelliste.

Frontmatter:

```yaml
document_id: adr-0004-clean-showdown-runtime-adapter
title: "ADR-0004: Sauberer Showdown-Runtime-Adapter"
document_type: adr
status: accepted
normative: false
version: 1
applies_to:
  - runtime
  - gen9ou
effective_from: 2026-07-30
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-30
```

- [x] **Step 3: Corpus-Manifest anlegen**

`tests/fixtures/protocol/corpus.json`:

```json
{
  "corpus_id": "gen9ou-protocol-m1-v1",
  "format": "gen9ou",
  "showdown_commit": "59da482eabc87245eb62313593e468e81ca537d9",
  "captured_at": "2026-07-30",
  "fixtures": [
    "metadata-and-preview.txt",
    "state-transitions.txt",
    "evidence-and-display.txt"
  ],
  "fixture_kind": "synthetic-minimized",
  "contains_private_replays": false
}
```

- [x] **Step 4: Dokumentindex aktualisieren**

`docs/README.md` verlinkt ADR-0004 und diesen M1-Plan unter nichtnormativer
Planung. Keine M1-Schwelle wird dort wiederholt.

- [x] **Step 5: Dokumentgates ausführen**

Run:

```powershell
uv run python tools/check_docs.py
uv run pytest tests/tooling/test_docs.py -v
```

Expected: beide Befehle enden mit Exitcode 0.

- [x] **Step 6: Commit**

```powershell
git add docs/adr/ADR-0004-clean-showdown-runtime-adapter.md docs/README.md tests/fixtures/protocol/corpus.json docs/superpowers/plans/2026-07-29-battlebelief-m1-protocol-safe-prototype.md
git commit -m "docs(m1): accept clean Showdown adapter and protocol corpus"
```

---

## Task 2 – Kanonische Core-Events und unveränderliche Zustandswerte

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/domain/events/base.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/events/metadata.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/events/progress.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/events/pokemon.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/events/field.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/events/evidence.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/events/ignored.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/events/__init__.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/state/values.py`
- Test: `packages/battlebelief-core/tests/domain/test_events.py`
- Test: `packages/battlebelief-core/tests/domain/test_state_values.py`

### Eventmodell

Alle Events sind `@dataclass(frozen=True, slots=True)` und tragen einen
monotonen `event_index`. Wire-Zeilen und Showdown-JSON kommen in keinem
Core-Typ vor.

State-bearing Eventklassen:

| Gruppe | Eventtypen |
|---|---|
| Metadaten | `BattleInit`, `PlayerDeclared`, `TeamSizeDeclared`, `GameTypeDeclared`, `GenerationDeclared`, `TierDeclared`, `BattleRated`, `RuleDeclared`, `PreviewPokemonDeclared`, `PreviewCleared`, `TeamPreviewStarted` |
| Verlauf | `BattleStarted`, `TurnStarted`, `BattleWon`, `BattleTied` |
| Pokémon | `PokemonSwitched`, `PokemonDragged`, `PokemonFainted`, `MoveUsed`, `MovePrevented`, `HealthChanged`, `StatusChanged`, `TeamStatusCured`, `BoostChanged`, `BoostsSwapped`, `BoostsCopied`, `BoostsCleared`, `BoostsInverted`, `ItemChanged`, `AbilityChanged`, `IdentityChanged`, `FormChanged`, `PokemonTransformed`, `Terastallized`, `VolatileChanged`, `TransientEffectObserved`, `RechargeChanged` |
| Feld | `WeatherChanged`, `FieldConditionChanged`, `SideConditionChanged`, `SideConditionsSwapped` |

Gemeinsame Felder:

| Typfamilie | kanonische Felder |
|---|---|
| Side-/Player-Metadaten | `event_index`, `side_id`, normalisierte ID, sichtbarer Displaywert |
| Preview/Identity | `event_index`, `side_id`, `nickname`, `details` |
| Pokémon-Ziel | `event_index`, `side_id`, `slot`, normalisierter sichtbarer Nickname |
| Move/Evidence | Actor, optionales Target, Effekt/Move-ID, sortierte Annotationen |
| Health | Pokémon-Ziel, `HpToken(current, maximum, status, fainted)` |
| Boost | Pokémon-Ziel, Stat-ID, Delta oder Zielwert |
| Item/Ability | Pokémon-Ziel, sichtbarer Wert oder `None`, Aktion `set|end` |
| Conditions | Scope/Ziel, normalisierte Effekt-ID, Aktion `start|upkeep|end` |

`HpToken` gehört zu den Eventwerten und behauptet noch keine Genauigkeit. Der
Reducer kennt nach `PlayerDeclared` die eigene Side und erzeugt daraus:

```text
own-side token       → HpPrecision.EXACT
opponent denominator 100 → HpPrecision.PERCENT
other visible opponent denominator → HpPrecision.PIXEL
```

Dadurch wird ein eigenes Pokémon mit tatsächlichen 100 Max-HP nicht
versehentlich als Prozentbeobachtung behandelt.

Nichtpersistente, aber für spätere Beliefs relevante Beobachtungen werden als
`VisibleEvidence` typisiert:

```text
crit, supereffective, resisted, immune, miss, fail, activate, block,
notarget, nothing, hitcount, prepare
```

Nur diese display-/transportbezogenen Battle-Zeilen ergeben
`IgnoredDisplayEvent`:

```text
spacer (exakter Payload |), upkeep, t:, -anim, -hint, -center, -combine,
-waiting, message, -message
```

`player`, `teamsize`, `gametype`, `gen`, `tier`, `rule`, `poke`,
`teampreview`, `inactive`, Boosts, Item, Ability, Tera, Volatiles und
Feldzustände sind ausdrücklich keine No-ops.

### Unveränderliche Werte

`values.py` definiert:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class HpPrecision(StrEnum):
    EXACT = "exact"
    PERCENT = "percent"
    PIXEL = "pixel"


@dataclass(frozen=True, slots=True)
class HpObservation:
    current: int
    maximum: int
    precision: HpPrecision
    fainted: bool = False

    def __post_init__(self) -> None:
        if self.maximum <= 0 or self.current < 0 or self.current > self.maximum:
            raise ValueError("invalid HP observation")
        if self.fainted and self.current != 0:
            raise ValueError("fainted HP observation must be zero")


@dataclass(frozen=True, slots=True)
class EvidenceInterval:
    value: str | None
    source_event_index: int
    valid_from: int
    valid_until: int | None = None


@dataclass(frozen=True, slots=True)
class EffectCounter:
    effect_id: str
    count: int
```

- [ ] **Step 1: Failing Tests für Immutability und HP-Invarianten schreiben**

Tests versuchen eine Feldmutation, prüfen exakte/Prozent-HP getrennt und
verwerfen negative oder inkonsistente HP-Werte.

- [ ] **Step 2: Fokustests ausführen**

Run:

```powershell
uv run pytest packages/battlebelief-core/tests/domain/test_events.py packages/battlebelief-core/tests/domain/test_state_values.py -v
```

Expected: FAIL wegen fehlender Module.

- [ ] **Step 3: Events und Werte minimal vollständig implementieren**

Jede Tabellezeile erhält einen exportierten Typ. Generische
`VisibleEvidence(kind, actor, target, effect, annotations)` und
`IgnoredDisplayEvent(kind)` sind erlaubt; state-bearing Gruppen dürfen nicht
in diese beiden Typen umgeleitet werden.

- [ ] **Step 4: Fokustests erneut ausführen**

Expected: PASS.

- [ ] **Step 5: Core-Suite und Architekturcheck ausführen**

```powershell
uv run pytest packages/battlebelief-core/tests -v
uv run python tools/check_architecture.py
uv run mypy
```

Expected: alle Befehle enden mit Exitcode 0.

- [ ] **Step 6: Commit**

```powershell
git add packages/battlebelief-core
git commit -m "feat(core): add canonical M1 battle events"
```

---

## Task 3 – ObservedState und vollständiger ObservationReducer

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/domain/state/pokemon_view.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/state/side_view.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/state/observed_state.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/state/__init__.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/application/observation/reducer.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/errors.py`
- Test: `packages/battlebelief-core/tests/application/test_observation_reducer.py`
- Test: `packages/battlebelief-core/tests/application/test_hidden_information_boundary.py`

### Stateform

`ObservedState` enthält ausschließlich sichtbare Informationen:

```text
event_index
room_initialized
generation
game_type
tier
rules
turn
battle_started
winner / tied
our_side
p1 / p2 SideView
weather
field_conditions
visible_evidence
ignored_display_count
```

`ObservedState.initial(our_user_id: str)` erhält die normalisierte eigene
Showdown-ID explizit. Der Reducer setzt `our_side` erst, wenn ein passendes
`PlayerDeclared` eintrifft. Er greift weder auf globale Config noch auf
Runtime-Normalisierung zu.

`SideView` enthält Spielername, angekündigte Teamgröße, Preview-Roster,
aktiven Slot, Pokémon-Views und Side-Conditions mit Layerzahl.

`PokemonView` enthält:

```text
side + nickname identity
identity evidence intervals
preview details / current details
active
HP observation
status
fainted
revealed moves
item evidence intervals
ability evidence intervals
tera type if revealed
boost tuple
volatile tuple
recharge flag
transform target
```

Listen, Dicts und Sets werden an der Domain-Grenze in sortierte Tupel
normalisiert. `ObservedState` und alle Kindobjekte sind frozen.

### Reducer-Mutationsvertrag

| Event | verpflichtende Zustandsänderung |
|---|---|
| Metadaten | passendes Metadata-/Side-Feld setzen oder ergänzen |
| Preview clear/poke | sichtbaren Preview-Roster leeren/ergänzen |
| Switch/drag | bisher aktives Pokémon deaktivieren, Ziel aktivieren, Identität/Details/HP setzen |
| Move | Move zu `revealed_moves` ergänzen und Evidence anhängen |
| HP/status/faint | HP-, Status- und Faint-Felder konsistent aktualisieren |
| Boost | Stat-Stufe clampen auf `[-6, 6]` |
| Boost swap/copy/clear/invert | betroffene Stat-Tupel deterministisch ersetzen |
| Item/ability/identity | vorheriges offenes Evidenzintervall schließen, neues öffnen |
| Tera/form/transform | sichtbare Zielwerte aktualisieren und Evidence anhängen |
| Volatile/recharge | Start/End beziehungsweise booleschen Zustand aktualisieren |
| Single-turn/single-move | Turn-Effekt bis zum nächsten `TurnStarted` halten beziehungsweise Move-Effekt nur als transiente Evidence erfassen |
| Weather/field | aktuellen Effekt starten, upkeep erhalten oder beenden |
| Side condition | Layer bei `spikes` maximal 3, bei `toxicspikes` maximal 2, sonst 1; End entfernt |
| Side swap | Side-Condition-Tupel von p1 und p2 tauschen |
| VisibleEvidence | an sichtbare Evidence-Historie anhängen |
| IgnoredDisplayEvent | nur `ignored_display_count` erhöhen |

Kein state-bearing Event darf unverändert zurückgegeben werden. Ein Event, das
eine unmögliche Reihenfolge oder Form erzeugt, wirft
`ReducerInvariantError`; Runtime mappt dies später genau einmal.

- [ ] **Step 1: Failing Reducer-Tests schreiben**

Die Tests decken mindestens ab:

- Metadaten und Zuordnung des eigenen Users zu `p1` oder `p2`;
- Switch → Schaden → Status → Faint;
- Tera, Itemverlust, Ability-Reveal und Formwechsel;
- Boost, ClearBoost und SwapBoost;
- drei Spikes-Layer und deren Entfernung;
- Field-/Weather-Start und -End;
- sichtbare Evidence versus explizites Display-No-op;
- keine Mutation des Eingangszustands;
- kein gegnerisches Hidden Set, Stats oder unrevealed Moves im State.

- [ ] **Step 2: Tests rot ausführen**

```powershell
uv run pytest packages/battlebelief-core/tests/application/test_observation_reducer.py packages/battlebelief-core/tests/application/test_hidden_information_boundary.py -v
```

Expected: FAIL wegen fehlender State-/Reducer-Typen.

- [ ] **Step 3: State und Reducer implementieren**

Alle Update-Helfer sind pure Funktionen. Kein Helper liest Uhrzeit,
Umgebungsvariablen, globale Zufallsquellen oder Runtime-Module.

- [ ] **Step 4: Tests grün ausführen**

Expected: PASS.

- [ ] **Step 5: Gesamten Core prüfen und committen**

```powershell
uv run pytest packages/battlebelief-core/tests -v
uv run ruff check packages/battlebelief-core
uv run mypy
git add packages/battlebelief-core
git commit -m "feat(core): reduce visible Gen9 OU battle state"
```

---

## Task 4 – DecisionRequest und vollständiges SafeSubmissionSet

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/domain/actions/submission.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/actions/decision_request.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/actions/__init__.py`
- Test: `packages/battlebelief-core/tests/domain/test_submissions.py`

### Core-Typen

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActionKind(StrEnum):
    MOVE = "move"
    SWITCH = "switch"
    REVIVE = "revive"
    TEAM = "team"
    DEFAULT = "default"


class RequestKind(StrEnum):
    MOVE = "move"
    FORCED_SWITCH = "forced_switch"
    REVIVAL = "revival"
    TEAM_PREVIEW = "team_preview"
    WAIT = "wait"


class ActionProvenance(StrEnum):
    EXPLICIT_REQUEST = "explicit_request"
    SERVER_DEFAULT = "server_default"


@dataclass(frozen=True, slots=True)
class RequestIdentity:
    room_id: str
    rqid: int
    request_digest: str


@dataclass(frozen=True, slots=True)
class BattleSubmission:
    kind: ActionKind
    provenance: ActionProvenance
    slot: int | None = None
    move_id: str | None = None
    terastallize: bool = False
    team_order: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class SafeSubmissionSet:
    request_identity: RequestIdentity
    submissions: tuple[BattleSubmission, ...]

    def contains(self, submission: BattleSubmission) -> bool:
        return submission in self.submissions
```

`BattleSubmission` bezeichnet das an Showdown sendbare Choice-Kommando.
Konkrete Move-, Switch-, Revive- und Team-Submissions repräsentieren
request-validierte Aktionen. `DEFAULT` repräsentiert dagegen nur den lokal
zugelassenen serverdelegierten Fallback und behauptet keine konkrete, lokal
validierte Aktion.

`DecisionRequest` enthält nur normalisierte immutable DTOs:

```text
identity
kind
side_id
team_member_count
active_identity
safe_submissions
is_update
```

Es enthält weder einen Raw-Dict noch den ursprünglichen JSON-String,
vollständige eigene Stats, Dateipfade oder Wire-Nachrichten.

### Forminvarianten

- Move: Slot 1–4, `move_id` gesetzt, keine Teamorder;
- Switch: Slot 1–6, kein Move, kein Tera;
- Revive: gefainteter Zielslot 1–6, kein Move, kein Tera;
- Team: `team_order` ist eine vollständige Permutation `1..N`;
- Default: keine Slots, kein Move, kein Tera, keine Teamorder;
- Tera ist nur bei Move erlaubt;
- konkrete Move-, Switch-, Revive- und Team-Choices tragen
  `EXPLICIT_REQUEST`;
- nur Default trägt `SERVER_DEFAULT`;
- Submission-Tupel ist stabil sortiert und duplikatfrei;
- Wait hat exakt ein leeres Submission-Tupel.

Die Materialisierung aller Team-Preview-Permutationen ist ausschließlich eine
M1-Implementierungsentscheidung. Sie ist kein langfristiger Core-Vertrag.
`SafeSubmissionSet.contains()` darf in einer späteren, separat geprüften
Revision durch eine strukturelle `TeamOrderDomain`-Validierung ersetzt werden.

- [ ] **Step 1: Failing Tests für jede Forminvariante schreiben**
- [ ] **Step 2: Tests rot ausführen**

```powershell
uv run pytest packages/battlebelief-core/tests/domain/test_submissions.py -v
```

- [ ] **Step 3: Typen und Validierung implementieren**
- [ ] **Step 4: Tests grün ausführen**
- [ ] **Step 5: Commit**

```powershell
git add packages/battlebelief-core
git commit -m "feat(core): define immutable decision requests and submissions"
```

---

## Task 5 – Request-Reconciliation, Heuristikpolicy und unabhängiges Safety-Gate

**Files:**

- Create: `packages/battlebelief-core/src/battlebelief_core/application/safety/request_reconciler.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/application/safety/action_gate.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/application/safety/__init__.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/application/decision/heuristic_policy.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/application/decision/__init__.py`
- Modify: `packages/battlebelief-core/src/battlebelief_core/errors.py`
- Test: `packages/battlebelief-core/tests/application/test_request_reconciler.py`
- Test: `packages/battlebelief-core/tests/application/test_action_gate.py`
- Test: `packages/battlebelief-core/tests/application/test_heuristic_policy.py`

### RequestReconciler

Der Reconciler liefert ein typisiertes Ergebnis statt unbekannte und
widersprüchliche Zustände gleichzusetzen:

```python
from dataclasses import dataclass
from enum import StrEnum


class ReconciliationStatus(StrEnum):
    ACCEPT = "accept"
    PENDING_PUBLIC_STATE = "pending_public_state"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    status: ReconciliationStatus
    reason: str
```

Prüfregeln:

- Raum-ID entspricht der Session;
- `rqid` ist nicht älter als der zuletzt akzeptierte Request;
- Request-Side entspricht dem durch `PlayerDeclared` ermittelten eigenen Side;
- Generation ist 9, Game Type `singles`, Tier normalisiert `gen9ou`;
- Teamgröße liegt 1–6 und stimmt mit der eigenen angekündigten Teamgröße
  überein, sobald diese bekannt ist;
- aktive Request-Identität stimmt mit dem sichtbaren eigenen Active überein,
  sobald beide bekannt sind;
- Wait-Request besitzt keine Aktionen;
- ein entscheidungspflichtiger Request besitzt mindestens `default`.

Ergebnisse:

- unbekannte Generation, Game Type, Tier oder eigene Side:
  `PENDING_PUBLIC_STATE`;
- für Move-/Forced-Switch-/Revival-Requests noch unbekannte eigene
  Active-Identität: `PENDING_PUBLIC_STATE`;
- bekannte, widersprüchliche Werte: `REJECT`;
- vollständige und konsistente Mindestbasis: `ACCEPT`.

Team Preview benötigt noch keine Active-Identität. Wait wird nach
Scope-/Side-Prüfung akzeptiert und löst keinen Versand aus.

Er liest keine privaten Gegnerdaten und verändert `ObservedState` nicht.

### HeuristicPolicy

Die M1-Reihenfolge ist deterministisch:

```text
1. erster normaler Move ohne Tera
2. erster Revival-Zielslot
3. erster erzwungener oder freiwilliger Switch
4. natürliche vollständige Teamorder
5. erster Tera-Move
6. default
```

Sie ist bewusst schwach. Kein Zufall, kein Tree Search und kein Hidden-State-
Guessing.

### ActionSafetyGate

```python
class ActionSafetyGate:
    @staticmethod
    def authorize(
        candidate: BattleSubmission,
        candidate_request: RequestIdentity,
        latest: SafeSubmissionSet,
    ) -> BattleSubmission:
        if candidate_request != latest.request_identity:
            raise StaleRequestIdentity
        if not latest.contains(candidate):
            raise LocalActionGateRejection
        return candidate
```

Das Gate läuft unabhängig nach der Policy. Es vertraut weder
`HeuristicPolicy` noch späterem Search-/Modellcode.

- [ ] **Step 1: Failing Contract-Tests schreiben**

Mindestens:

- alte RequestIdentity wird abgelehnt;
- fremde Submission wird abgelehnt;
- neu konstruierte, aber wertgleiche Submission aus dem Set wird akzeptiert;
- Policy mutiert weder State noch `SafeSubmissionSet`;
- gleiche Eingabe ergibt dieselbe Aktion;
- leeres entscheidungspflichtiges Set ergibt `NoLegalActionError`;
- unbekannte Side/Generation/Active-Identität ergibt Pending;
- bekannte Request-/State-Side- oder Scope-Mismatch ergibt Reject;
- Revival wird nicht als gewöhnlicher Forced Switch reconciliert.

- [ ] **Step 2: Tests rot ausführen**

```powershell
uv run pytest packages/battlebelief-core/tests/application/test_request_reconciler.py packages/battlebelief-core/tests/application/test_action_gate.py packages/battlebelief-core/tests/application/test_heuristic_policy.py -v
```

- [ ] **Step 3: Reconciler, Policy und Gate implementieren**
- [ ] **Step 4: Tests grün ausführen**
- [ ] **Step 5: PR-2-Gates ausführen**

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run python tools/check_architecture.py
```

Expected: alle Befehle enden mit Exitcode 0.

- [ ] **Step 6: Commit und PR 2 öffnen**

```powershell
git add packages/battlebelief-core
git commit -m "feat(core): add M1 request and action safety path"
```

---

## Task 6 – Raumtreue Frame-Dekodierung und Runtime-Fehler

**Files:**

- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/showdown_protocol/frame_decoder.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/errors/protocol.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/errors/actions.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/errors/setup.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/errors/__init__.py`
- Create: `tests/fixtures/frames/login-and-battle.txt`
- Create: `tests/fixtures/frames/two-rooms.txt`
- Test: `packages/battlebelief-runtime/tests/adapters/test_frame_decoder.py`
- Test: `packages/battlebelief-runtime/tests/test_error_taxonomy.py`

### Frameobjekt

```python
@dataclass(frozen=True, slots=True)
class RoomLine:
    room_id: str | None
    payload: str
```

`room_id=None` bedeutet global/lobby. Der Decoder:

- ignoriert leere Frames und leere Zeilen;
- erhält `>battle-gen9ou-...` als Kontext;
- ordnet jede Folgelinie bis zum nächsten Raummarker diesem Raum zu;
- darf mehrere Raumblöcke in einem Frame dekodieren;
- entfernt nur abschließendes `\r`, nicht Nutzdaten;
- verwirft niemals den Raumnamen;
- lehnt einen leeren `>`-Marker und binäre Frames klassifiziert ab.

Room-Chat und globale Loginzeilen bleiben `RoomLine`. Der Coordinator routet
nach Raum-ID; der in Task 7 definierte `RoomPayloadClassifier` entscheidet
danach, welche Payload den Battle-Parser erreicht.

### Fehlerobjekte

Jede Runtime-Exception besitzt ein unveränderliches `code`-Attribut mit exakt
einem Wert aus der zentralen Zuordnung in Abschnitt 3. BattleSession-Codes
stammen aus den normativen Protocol-/Action-Contracts; die beiden
vorangestellten Coordinator-Setup-Codes sind dort ausdrücklich als
M1-Ergänzung abgegrenzt. Serverfehler werden bereits beim ersten Auftreten
erzeugt. Es gibt keinen „drei Fehler“-Zähler.

`setup.py` definiert:

```python
class TeamValidationError(RuntimeError):
    code = "team_validation_error"


class ChallengeSetupError(RuntimeError):
    code = "challenge_setup_error"
    allowed_subcodes = frozenset(
        {
            "challenge_command_rejected_explicit",
            "challenge_not_pending",
            "challenge_setup_timeout",
        }
    )

    def __init__(self, *, subcode: str, message: str) -> None:
        if subcode not in self.allowed_subcodes:
            raise ValueError("unsupported challenge setup subcode")
        super().__init__(message)
        self.subcode = subcode
```

Der Konstruktor akzeptiert nur die drei in Task 11 festgelegten Subcodes.
Freitext `message` wird für Logs sanitiert; die Klassifikation hängt niemals
von einem nachträglich interpretierten Teilstring ab.

- [ ] **Step 1: Failing Frame- und Taxonomie-Tests schreiben**
- [ ] **Step 2: Tests rot ausführen**

```powershell
uv run pytest packages/battlebelief-runtime/tests/adapters/test_frame_decoder.py packages/battlebelief-runtime/tests/test_error_taxonomy.py -v
```

- [ ] **Step 3: Decoder und Fehler implementieren**
- [ ] **Step 4: Tests grün ausführen**
- [ ] **Step 5: Commit**

```powershell
git add packages/battlebelief-runtime tests/fixtures/frames
git commit -m "feat(runtime): preserve Showdown room framing"
```

---

## Task 7 – Strikter ProtocolParser und versionierte Fixtures

**Files:**

- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/showdown_protocol/parser.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/showdown_protocol/room_payload_classifier.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/showdown_protocol/__init__.py`
- Create: `tests/fixtures/protocol/metadata-and-preview.txt`
- Create: `tests/fixtures/protocol/state-transitions.txt`
- Create: `tests/fixtures/protocol/evidence-and-display.txt`
- Create: `tests/fixtures/frames/battle-room-multiplex.txt`
- Test: `packages/battlebelief-runtime/tests/adapters/test_protocol_parser.py`
- Test: `packages/battlebelief-runtime/tests/adapters/test_room_payload_classifier.py`
- Test: `tests/contracts/test_protocol_contract.py`

### RoomPayloadClassifier

Der Klassifikator arbeitet nach Raumrouting und vor der BattleSession:

```python
from dataclasses import dataclass
from enum import StrEnum


class RoomPayloadKind(StrEnum):
    BATTLE_EVENT = "battle_event"
    DECISION_REQUEST = "decision_request"
    BATTLE_ERROR = "battle_error"
    TIMER_MESSAGE = "timer_message"
    ROOM_CONTROL_OR_CHAT = "room_control_or_chat"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ClassifiedRoomPayload:
    kind: RoomPayloadKind
    payload: str
```

Bindende Reihenfolge:

1. exakt `|` ist `BATTLE_EVENT`, damit der dokumentierte Battle-Spacer den
   Parser erreicht;
2. nicht mit `|` beginnende Plaintext-Nachrichten und `||MESSAGE` sind
   `ROOM_CONTROL_OR_CHAT`;
3. `request` ist `DECISION_REQUEST`;
4. `error` ist `BATTLE_ERROR`;
5. `inactive` und `inactiveoff` sind `TIMER_MESSAGE`;
6. jeder in der Task-7-Wire-Zuordnung deklarierte Typ ist `BATTLE_EVENT`;
7. `title`, `users`, `join`, `j`, `J`, `leave`, `l`, `L`, `name`, `n`, `N`,
   `chat`, `c`, `c:`, `:`, `html`, `uhtml`, `uhtmlchange` und `notify` sind
   `ROOM_CONTROL_OR_CHAT`; die dokumentierten Raumhinweise `battle`, `b` und
   `B` gehören ebenfalls in diese Kategorie;
8. alles andere ist `UNKNOWN` und wird später zu
   `UnknownProtocolEvent(code="unknown_protocol_event")`.

Nur das erste, äußere Typfeld wird gelesen. Insbesondere bleibt bei
`|c:|TIMESTAMP|USER|MESSAGE` der gesamte Rest Payload; ein im Chattext
enthaltenes `|request|` oder `|move|` wird weder gesplittet noch rekursiv
klassifiziert. Die Menge der `BATTLE_EVENT`-Typen besitzt genau eine
Definition, die Klassifikator und Parser gemeinsam verwenden.

### Parserregeln

```python
def parse_battle_line(payload: str, event_index: int) -> BattleEvent:
    ...
```

- akzeptiert ausschließlich eine einzelne Battle-Payload;
- validiert Feldzahl und Feldtypen vor Konstruktion;
- normalisiert Side- und Pokémon-Identifikatoren ohne den sichtbaren
  Nickname zu verlieren;
- parst HP in einen `HpToken`; der Reducer bestimmt die Precision anhand der
  bereits sichtbaren eigenen Side;
- erhält `[from]`, `[of]`, `[silent]` und andere Suffixe als sortierte
  Annotationen;
- mappt jeden state-bearing Typ aus Task 2 auf den passenden Eventtyp;
- mappt nur die explizite Display-Allowlist auf `IgnoredDisplayEvent`;
- mappt Evidence-Typen auf `VisibleEvidence`;
- wirft `UnknownProtocolEvent` für alle anderen Typen;
- wirft `MalformedProtocolMessage` für bekannte, aber kaputte Zeilen;
- fängt `ValueError`, `IndexError` und `KeyError` an der
  Parsergrenze ab und mappt sie, statt Rohfehler durchsickern zu lassen.

`|request|`, `|error|`, `|inactive|`, `|inactiveoff|`, globale Login-,
Challenge- und Chatzeilen gehen nicht durch diese Funktion. Der
`RoomPayloadClassifier` erzwingt diese Grenze vor dem Aufruf.

`parse_inactive_line(payload, event_index)` ist eine getrennte Funktion im
gleichen Modul. Nichtterminale `inactive`-Warnungen ergeben
`VisibleEvidence(kind="timer_warning")`; `inactiveoff` ergibt
`VisibleEvidence(kind="timer_warning_cleared")`. Die im Corpus festgelegten
terminalen Inactivity-/Forfeit-Meldungen erzeugen `TimerOrForfeit`.

Der M1-Vertrag bleibt bewusst **ein kanonisches Event pro Battle-Wire-Zeile**.
Im gepinnten Showdown-Snapshot besitzt `|-sethp|POKEMON|HP` genau ein Ziel.
Pain Split emittiert dafür zwei aufeinanderfolgende `-sethp`-Zeilen, nicht eine
Mehrzielzeile. Erst reale Gegenbelege in einem späteren Snapshot rechtfertigen
eine Tuple-Rückgabe oder einen Multi-Event-Typ.

### Bindende Wire-Zuordnung für M1

| Wire-Typ | kanonisches Ergebnis |
|---|---|
| `init`, `player`, `teamsize`, `gametype`, `gen`, `tier`, `rated`, `rule` | passender Metadaten-Eventtyp |
| `clearpoke`, `poke`, `teampreview` | Preview-Event |
| `start`, `turn`, `win`, `tie` | Verlaufs-Event |
| `move`, `switch`, `drag`, `faint`, `cant`, `detailschange`, `replace` | passender Pokémon-/Evidence-Eventtyp |
| `-damage`, `-heal` | `HealthChanged` |
| `-sethp` | `HealthChanged` |
| `-status`, `-curestatus`, `-cureteam` | Status-Event |
| `-boost`, `-unboost`, `-setboost` | `BoostChanged` |
| `-swapboost`, `-copyboost` | Swap-/Copy-Event |
| `-clearboost`, `-clearallboost`, `-clearpositiveboost`, `-clearnegativeboost` | `BoostsCleared` mit explizitem Scope |
| `-invertboost` | `BoostsInverted` |
| `-weather` | `WeatherChanged` |
| `-fieldstart`, `-fieldend` | `FieldConditionChanged` |
| `-sidestart`, `-sideend`, `-swapsideconditions` | Side-Condition-Event |
| `-start`, `-end`, `-singleturn`, `-singlemove`, `-mustrecharge` | Volatile-/Recharge-Event |
| `-item`, `-enditem` | `ItemChanged` |
| `-ability`, `-endability` | `AbilityChanged` |
| `-transform`, `-formechange`, `-terastallize` | Transform-/Form-/Tera-Event |
| `-crit`, `-supereffective`, `-resisted`, `-immune`, `-miss`, `-fail`, `-activate`, `-block`, `-notarget`, `-nothing`, `-hitcount`, `-prepare`, `-fieldactivate` | `VisibleEvidence` |
| exakter Payload `|` | `IgnoredDisplayEvent(kind="spacer")` |
| `upkeep`, `t:`, `-anim`, `-hint`, `-center`, `-combine`, `-waiting`, `message`, `-message` | `IgnoredDisplayEvent` |

Alte Mechaniken wie `-mega`, `-zpower` oder Dynamax werden nicht vorauseilend
implementiert. Wenn sie im Gen-9-OU-Corpus auftauchen, ist das ein
Corpus-/Scope-Fehler und kein Anlass, sie still als No-op zu behandeln.

### Gültiger Corpus

Die drei Textfixtures starten jeweils mit vollständiger M1-Metadatenfolge.
Zusammen enthalten sie mindestens je ein Beispiel aller Task-2-Eventtypen.
Sie enthalten ausschließlich synthetische oder minimierte Zeilen, keine
Benutzernamen oder kopierten privaten Replays.

Ungültige Beispiele liegen nur in den Parser-Unit-Tests und gehören nicht zum
gültigen Corpus.

Diese Aussage bedeutet ausschließlich:

```text
synthetic contract coverage:
  complete for the declared M1 wire-to-event mapping

observed live protocol coverage:
  not established by the synthetic corpus
```

Sie ist kein Claim über die vollständige reale Gen-9-OU-Protokolloberfläche.

- [ ] **Step 1: Fixture- und Unit-Tests schreiben**

Unit-Tests prüfen mindestens:

- die Sequenz `title`, `J`, Chat mit eingebettetem `|request|`, `move`,
  echtem `request`, `L` bleibt korrekt klassifiziert und geordnet;
- `|b|ROOM|USER1|USER2` und `|B|ROOM|USER1|USER2` sind
  `ROOM_CONTROL_OR_CHAT`, während `|Bx|ROOM|USER1|USER2` `UNKNOWN` bleibt;
- Room-Control/Chat erreicht weder BattleParser noch RequestReader;
- unbekannter room-scoped Typ wird `UNKNOWN`, nicht kosmetisch ignoriert;
- malformed HP;
- fehlendes Feld;
- unbekannter state-bearing Typ;
- `player`, `teamsize`, `poke`, Tera, Item, Ability, Boost, Volatile,
  Field und SideCondition ergeben keine No-ops;
- `-crit` ergibt Evidence;
- `-anim` ergibt explizites Display-No-op;
- der nackte `|`-Spacer ergibt `IgnoredDisplayEvent(kind="spacer")` und
  erhöht `ignored_display_count` um eins;
- eine Initialisierungsfolge mit `|` direkt vor `|start|` wird vollständig
  klassifiziert, geparst und reduziert;
- `inactiveoff` ergibt `timer_warning_cleared`;
- zwei aufeinanderfolgende Pain-Split-`-sethp`-Zeilen erzeugen zwei Events
  mit stabiler Reihenfolge und aktualisieren beide HP-Zustände;
- derselbe Zwei-Zeilen-Input erzeugt wertgleiche Events und denselben
  Endzustand;
- parserfremdes `|request|` wird abgelehnt.

- [ ] **Step 2: Tests rot ausführen**

```powershell
uv run pytest packages/battlebelief-runtime/tests/adapters/test_room_payload_classifier.py packages/battlebelief-runtime/tests/adapters/test_protocol_parser.py tests/contracts/test_protocol_contract.py -v
```

- [ ] **Step 3: Parser implementieren**
- [ ] **Step 4: Tests grün ausführen**
- [ ] **Step 5: Commit**

```powershell
git add packages/battlebelief-runtime tests/fixtures/protocol tests/fixtures/frames/battle-room-multiplex.txt tests/contracts/test_protocol_contract.py
git commit -m "feat(runtime): parse the versioned Gen9 OU protocol corpus"
```

---

## Task 8 – RequestReader, CommandEncoder und Packed-Team-Loader

**Files:**

- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/showdown_protocol/request_reader.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/showdown_protocol/command_encoder.py`
- Create: `packages/battlebelief-core/src/battlebelief_core/domain/teams/sealed_team.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/team_files/packed_team.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/team_files/loader.py`
- Create: `tests/fixtures/requests/move.json`
- Create: `tests/fixtures/requests/move-tera.json`
- Create: `tests/fixtures/requests/maybe-trapped.json`
- Create: `tests/fixtures/requests/forced-switch.json`
- Create: `tests/fixtures/requests/reviving.json`
- Create: `tests/fixtures/requests/team-preview.json`
- Create: `tests/fixtures/requests/wait.json`
- Create: `tests/fixtures/teams/gen9ou-example-packed.txt`
- Test: `packages/battlebelief-runtime/tests/adapters/test_request_reader.py`
- Test: `packages/battlebelief-runtime/tests/adapters/test_command_encoder.py`
- Test: `packages/battlebelief-runtime/tests/adapters/test_team_loader.py`

### RequestReader

Der Reader erhält `room_id` und den rohen JSON-Payload der `|request|`-Line.
Er parst JSON innerhalb der Runtime-Grenze und validiert jede verschachtelte
Form selbst. JSON-Fehler werden `MalformedProtocolMessage`. Der
SHA-256-Digest wird aus einer kanonischen JSON-Darstellung mit sortierten Keys
und kompakten Separatoren gebildet.

Der Reader normalisiert jedes Element aus `side.pokemon` in ein immutable
Request-Teammitglied. `fainted` wird aus dem offiziellen `condition`-Feld
abgeleitet; der gepinnte Requesttyp besitzt kein separates
`pokemon[*].fainted`-Bool. `reviving` steht am aktiven Request-Teammitglied.

Die Erkennungsreihenfolge ist bindend:

```text
wait
→ teamPreview
→ active team member with reviving=true
→ forceSwitch
→ normal move request
```

Aktionsbildung:

| Request | SafeSubmissionSet |
|---|---|
| `wait` | leer |
| Team Preview | alle vollständigen Permutationen `1..N`, natürliche Reihenfolge zuerst, danach `default` |
| Forced Switch | jeder nichtaktive, nichtgefaintete Slot, danach `default` |
| Revival | jeder gefaintete, wiederbelebbare Slot als `ActionKind.REVIVE`, danach `default` |
| normal | nicht deaktivierte Moves; je Move zusätzlich Tera-Variante bei `canTerastallize`; erlaubte Switches; danach `default` |
| `trapped`/`maybeTrapped` | wie normal, aber ohne Switches |
| `maybeDisabled`/`maybeLocked` | nur `default` |

Alle konkreten Einträge tragen `EXPLICIT_REQUEST`; nur `default` trägt
`SERVER_DEFAULT`.

Für M1-Gen9-OU muss Team Preview alle vorhandenen Slots ordnen.
`maxChosenTeamSize`, das kleiner als die Teamgröße ist, wird als
`request_state_reconciliation_mismatch` abgelehnt, weil Bring-N-Formate nicht
im Scope liegen.

### Encoder

Exakte Ausgaben:

```text
move 1
move 1 terastallize
switch 3
team 123456
default
```

`BattleSubmission(kind=ActionKind.REVIVE,
provenance=ActionProvenance.EXPLICIT_REQUEST, slot=3)` wird wire-seitig
ebenfalls als `switch 3` encodiert, bleibt aber im Core semantisch von einem
Positionswechsel unterschieden.

Der Session-Layer ergänzt:

```text
/choose <choice>|<rqid>
<room_id>|/choose <choice>|<rqid>
```

`terastallize` ist die vom aktuellen Showdown-Code akzeptierte und selbst
ausgegebene Schreibweise. Der Encoder erfindet keine Targets, Mega-, Z- oder
Dynamax-Suffixe.

### Packed Team

Core:

```python
@dataclass(frozen=True, slots=True)
class SealedTeam:
    digest: str
    member_count: int
```

Runtime:

```python
@dataclass(frozen=True, slots=True)
class PackedTeam:
    sealed: SealedTeam
    packed: str
```

Der Loader akzeptiert genau eine nichtleere physische Zeile im offiziellen
Packed-Format. Er:

- entfernt nur eine abschließende Textdatei-Newline;
- lehnt innere `\r`/`\n` ab;
- teilt Pokémon an `]`;
- verlangt 1–6 nichtleere Einträge;
- verlangt pro Eintrag die Packed-Feldstruktur mit `|`;
- hasht exakt die normalisierten UTF-8-Bytes;
- konvertiert niemals menschliches Exportformat durch Zeilen-Joins.

Der Loader behauptet keine vollständige Teamlegalität. Der Challenge-
Coordinator behandelt spätere Showdown-Validierungsfehler als Startupfehler;
lokale Oracle-Validierung kommt in M2.

- [ ] **Step 1: Failing Request-, Encoder- und Loader-Tests schreiben**

Pflichtfälle:

- normale und Tera-Movevarianten;
- Tera-Feld ist String, nicht Bool;
- `maybeTrapped` entfernt Switches;
- `maybeDisabled` ergibt ausschließlich `default`;
- erzwungener Switch;
- Revival erkennt `side.pokemon[*].reviving`, enthält ausschließlich aus
  `condition` erkannte gefaintete Zielslots und encodiert sie als `switch N`;
- lebende und aktive Slots fehlen im Revival-Set, `default` bleibt letzter
  Fallback;
- 720 Permutationen bei sechs Teammitgliedern plus `default`;
- Wait ist leer;
- missing/negative/string `rqid` wird abgelehnt;
- Policy-Ausgabe kann exakt encoded werden;
- Exportformat und newline-joined Pseudopacked werden abgelehnt;
- Teamdigest ist stabil.

- [ ] **Step 2: Tests rot ausführen**

```powershell
uv run pytest packages/battlebelief-runtime/tests/adapters/test_request_reader.py packages/battlebelief-runtime/tests/adapters/test_command_encoder.py packages/battlebelief-runtime/tests/adapters/test_team_loader.py -v
```

- [ ] **Step 3: Reader, Encoder und Loader implementieren**
- [ ] **Step 4: Tests grün ausführen**
- [ ] **Step 5: PR-3-Gates ausführen und committen**

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run python tools/check_architecture.py
git add packages/battlebelief-core packages/battlebelief-runtime tests/fixtures
git commit -m "feat(runtime): derive and encode safe Showdown actions"
```

---

## Task 9 – Asynchroner Login und ShowdownConnection

**Files:**

- Modify: `packages/battlebelief-runtime/pyproject.toml`
- Modify: `uv.lock`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/showdown_client/types.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/showdown_client/auth.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/showdown_client/connection.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/showdown_client/__init__.py`
- Test: `packages/battlebelief-runtime/tests/adapters/test_showdown_auth.py`
- Test: `packages/battlebelief-runtime/tests/adapters/test_showdown_connection.py`

### Dependency

```toml
dependencies = [
  "battlebelief-core==0.1.0",
  "websockets==16.1.1"
]
```

Die interne Core-Version bleibt bis Task 14 bei `0.1.0`; der gemeinsame
Versionssprung erfolgt dort atomar.

### Auth

Runtime-interne Protokolle:

```python
class AssertionProvider(Protocol):
    async def assertion(
        self, username: str, password: str, challstr: str
    ) -> str: ...


class BattleConnection(Protocol):
    async def connect(self) -> None: ...
    def lines(self) -> AsyncIterator[RoomLine]: ...
    async def send_global(self, command: str) -> None: ...
    async def send_room(self, room_id: str, command: str) -> None: ...
    async def close(self) -> None: ...
```

Der konkrete AssertionProvider POSTet ausschließlich an:

```text
https://play.pokemonshowdown.com/api/login
```

Formfelder:

```text
name, pass, challstr
```

Der HTTP-Aufruf läuft über `asyncio.to_thread`, damit `urllib.request` den
Eventloop nicht blockiert. Es gibt keinen nicht dokumentierten
`action.php`-Fallback.

### Connection

Die Connection:

- verwendet `await connect(url, open_timeout=...)` und hält die
  `ClientConnection` bis `close`;
- sendet exakt `|/trn USERNAME,0,ASSERTION` auf dem Socket;
- akzeptiert Login erst bei exakt geparstem `|updateuser|USER|1|...`;
- vergleicht normalisierte User-IDs, nicht bloße Teilstrings;
- behandelt `|nametaken|` als `disconnect`;
- puffert jede beim Login konsumierte, aber nicht zum Login gehörende
  `RoomLine` in einer FIFO-Queue;
- liefert zuerst die Queue und danach weitere Socket-Frames;
- erhält Raumkontext über den FrameDecoder;
- mappt Open/Read/Write-Timeout auf `transport_timeout`;
- mappt unerwartetes Socket-Ende auf `disconnect`;
- fängt nicht pauschal jede Anwendungsexception als Disconnect.

Tests verwenden Fake-Socket und Fake-AssertionProvider. Keine Credentials und
kein Netzwerkzugriff.

- [ ] **Step 1: Dependency hinzufügen und Lockfile aktualisieren**

```powershell
uv add "websockets==16.1.1" --package battlebelief-runtime
```

Expected: Runtime-Paket und `uv.lock` ändern sich; Core/Lab erhalten keine
direkte websockets-Abhängigkeit.

- [ ] **Step 2: Failing Auth-/Connection-Tests schreiben**

Pflichtfälle:

- Challstr enthält `|` und bleibt vollständig;
- Login mit `NAMED=0` wird nicht akzeptiert;
- ähnlicher, aber falscher Username wird nicht akzeptiert;
- `nametaken`, HTTP-Fehler, Timeout und Socket-Close sind klassifiziert;
- während Login empfangene Battle-Room-Line geht nicht verloren;
- Raumpräfix bleibt beim Empfang erhalten;
- `send_room` erzeugt exakt `ROOMID|TEXT`.

- [ ] **Step 3: Tests rot ausführen**

```powershell
uv run pytest packages/battlebelief-runtime/tests/adapters/test_showdown_auth.py packages/battlebelief-runtime/tests/adapters/test_showdown_connection.py -v
```

- [ ] **Step 4: Auth und Connection implementieren**
- [ ] **Step 5: Tests grün ausführen**
- [ ] **Step 6: Commit**

```powershell
git add packages/battlebelief-runtime uv.lock
git commit -m "feat(runtime): add authenticated Showdown connection"
```

---

## Task 10 – BattleSession als request-getriebene Zustandsmaschine

**Files:**

- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/composition/battle_session.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/composition/__init__.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/testing/fake_connection.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/testing/__init__.py`
- Test: `tests/integration/test_battle_session.py`

### Session-Invarianten

Die Session verarbeitet ausschließlich `RoomLine` ihres `room_id`.

Jede Payload wird zuerst klassifiziert:

```text
battle_event
  → parse → reduce → replace current immutable state
decision_request
  → RequestReader und Request-Pfad
battle_error
  → klassifizierter Serverfehler
timer_message
  → parse_inactive_line und Timer-Pfad
room_control_or_chat
  → room_control_or_chat_count erhöhen, sonst keine Wirkung
unknown
  → UnknownProtocolEvent, kein Parser-Fallback
```

Der Session-Layer versucht niemals, Chat-, HTML- oder Plaintext-Inhalte
rekursiv zu interpretieren.

Für jeden neuen `|request|`:

```text
parse strict JSON
→ RequestReader
→ RequestReconciler
→ store as latest request
→ ACCEPT:
    if wait: no action
    else HeuristicPolicy.choose
      → ActionSafetyGate.authorize against latest set
      → encode
      → send_room
      → mark request identity submitted
→ PENDING_PUBLIC_STATE:
    store only the newest pending request
    → retry reconciliation after every relevant public event
→ REJECT:
    abort as RequestStateReconciliationMismatch
```

Ein Request löst selbst die Aktion aus. Die Session wartet weder auf
`TurnStarted` noch routinemäßig auf ein anderes Event. `PENDING_PUBLIC_STATE`
ist die einzige Ausnahme: Der Request bleibt der Entscheidungsauslöser, aber
die Session wartet fail-closed auf die minimale öffentliche Zustandsbasis,
die der Reconciler selbst verlangt. Ein späteres Event löst nur die erneute
Prüfung desselben Requests aus, keine eigenständige turn-basierte
Entscheidung.

### Pending-Reconciliation

- höchstens ein Pending-Request wird gespeichert;
- ein neuerer gültiger `rqid` ersetzt einen älteren Pending-Request;
- ein gleich alter oder älterer Request folgt weiterhin den Freshness-Regeln;
- nach `GenerationDeclared`, `GameTypeDeclared`, `TierDeclared`,
  `PlayerDeclared`, `BattleStarted`, `PokemonSwitched` und `PokemonDragged`
  wird der neueste Pending-Request erneut geprüft;
- `ACCEPT` führt genau einmal durch Policy, Gate und Versand;
- `REJECT` beendet die Session klassifiziert und ohne Versand;
- ein terminales Battle-Event verwirft den Pending-Request ohne Versand;
- war ein Request bereits vor `BattleStarted` pending, muss er beim
  Verarbeiten von `BattleStarted` vollständig `ACCEPT` oder `REJECT`
  erreichen; verbleibendes Pending führt fail-closed zum Abbruch;
- trifft ein Request erst nach `BattleStarted` ein und fehlt nur die eigene
  aktive Identität, darf er bis zum nächsten relevanten
  `PokemonSwitched`/`PokemonDragged` warten;
- erreicht die Session vorher `TurnStarted`, wird fail-closed mit
  `RequestStateReconciliationMismatch` abgebrochen;
- ein neuerer Request darf den alten Pending-Request gemäß newest-rqid-Regel
  ersetzen; der alte Request wird danach niemals versendet;
- ein Transport-Timeout bleibt die äußere zeitliche Grenze; M1 erfindet
  keinen zweiten beliebigen Pending-Timer.

### Freshness

- gleiche `rqid` + gleicher Digest nach erfolgreichem Submit:
  idempotent ignorieren;
- kleinere `rqid`: `stale_rqid`;
- gleiche `rqid` + anderer Digest ohne vorangegangenen klassifizierten
  Serverfehler: `request_state_reconciliation_mismatch`;
- größerer `rqid`: neuer Request und neue Entscheidung;
- fehlendes `rqid`: fail-closed gemäß Abschnitt 1.3.

Da M1 bei `Invalid`/`Unavailable` sofort abbricht, gibt es keinen
Retry-Zustand. Eine spätere Recovery darf in einem eigenen Plan eingeführt
werden, muss den ursprünglichen Fehler aber weiterhin zählen.

### Spezielle Lines

- `|error|[Invalid choice]` → sofort `ServerInvalidChoice`;
- `|error|[Unavailable choice]` → sofort `ServerUnavailableChoice`;
- andere `|error|` → `MalformedProtocolMessage`, sofern nicht separat
  spezifiziert;
- Corpus-terminales `|inactive|...lost due to inactivity...` oder
  Forfeit-Signal → `TimerOrForfeit`;
- nichtterminale Inactive-Warnung → typisierte Timer-Evidence, kein No-op;
- `|inactiveoff|` → `VisibleEvidence(kind="timer_warning_cleared")`;
- unbekannte Eventtypen werden vor dem Reducer klassifiziert;
- `ReducerInvariantError` wird genau einmal zu
  `ReducerInvariantFailure` gemappt.

Die Session zählt `explicit_request_submissions` und `default_submissions`
getrennt. Der zweite Zähler beweist nur die Nutzung des server-delegierten
Fallback-Kommandos, nicht die lokale Legalitätsprüfung der von Showdown
konkret ausgeführten Aktion.

- [ ] **Step 1: Failing Integrationstests schreiben**

Pflichtsequenzen:

1. `request` vor `turn` sendet genau eine Aktion;
2. `turn` vor `request` sendet nach dem Request genau eine Aktion;
3. Forced Switch innerhalb eines Turns sendet einen Switch;
4. Wait sendet nichts;
5. identischer Request wird nicht doppelt gesendet;
6. stale/missing `rqid` wird nicht gesendet;
7. Policy gibt absichtlich fremde Aktion zurück, Gate blockiert;
8. Tera-Action und Team-Preview-Action sind encodierbar;
9. `Invalid` und `Unavailable` brechen beim ersten Event ab;
10. unbekannt, malformed, Reconciliation, Reducer, Timer und Disconnect
    erzeugen jeweils genau eine Primärklasse;
11. Request vor `PlayerDeclared`, danach passende Metadaten: genau eine
    Aktion;
12. Request vor `PokemonSwitched`, danach passender Switch: genau eine
    Aktion;
13. Request vor anschließend widersprüchlicher Side: klassifizierter Abbruch
    ohne Versand;
14. zwei Pending-Requests: ausschließlich der neueste `rqid` wird ausgeführt;
15. Battle-Ende während Pending: kein Versand;
16. Revival-Request sendet ausschließlich einen gefainteten Zielslot oder
    den letzten `default`-Fallback;
17. explizite und `default`-Submissions werden getrennt gezählt;
18. `title`, Join, Chat mit eingebettetem `|request|`, Battle-Event, echter
    Request und Leave im selben Raum bleiben geordnet; nur der echte Request
    löst genau eine Entscheidung aus;
19. der nackte `|`-Spacer vor `BattleStarted` erhöht ausschließlich
    `ignored_display_count`.

- [ ] **Step 2: Tests rot ausführen**

```powershell
uv run pytest tests/integration/test_battle_session.py -v
```

- [ ] **Step 3: BattleSession und FakeConnection implementieren**
- [ ] **Step 4: Tests grün ausführen**
- [ ] **Step 5: Commit**

```powershell
git add packages/battlebelief-runtime tests/integration/test_battle_session.py
git commit -m "feat(runtime): act on fresh Showdown requests safely"
```

---

## Task 11 – Direkter Gen-9-OU-Challenge-Coordinator

**Files:**

- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/adapters/showdown_protocol/challenge_state_reader.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/composition/battle_coordinator.py`
- Test: `packages/battlebelief-runtime/tests/adapters/test_challenge_state_reader.py`
- Test: `tests/integration/test_challenge_coordinator.py`

### M1-Startpfad

M1 unterstützt **ausschließlich eine ausgehende direkte Challenge** und
startet genau einen solchen Battle. Der Gegner muss online sein, Challenges
akzeptieren, die Challenge annehmen und darf nicht bereits durch einen
inkompatiblen Zustand blockiert sein. Eingehende Challenges automatisch
anzunehmen ist nicht implementiert.

```text
connect and authenticate
→ socket |/utm PACKED_TEAM
→ socket |/challenge OPPONENT, gen9ou
→ observe global challenge state and room frames
→ detect new battle room through its preserved room_id
→ require |init|battle plus matching Gen9 OU metadata
→ hand room lines to one BattleSession
→ close after win, tie or classified abort
```

Keine `/search`-, `/cancelsearch`- oder Ladder-Kommandos werden implementiert.

### Challenge-State-Normalisierung

Der Coordinator konsumiert keine freien PM-Texte. Ein eigener
`ChallengeStateReader` normalisiert ausschließlich zwei am gepinnten Snapshot
nachgewiesene Darstellungen:

```text
PROTOCOL.md:
  |updatechallenges|JSON

server/ladders-challenges.ts:
  |pm|SENDER|RECEIVER|/challenge FORMAT|TEAMBUILDER_FORMAT|MESSAGE|ACCEPT|REJECT
  |pm|SENDER|RECEIVER|/challenge
```

Er erzeugt immutable Zustandsbeobachtungen:

```python
from dataclasses import dataclass
from enum import StrEnum


class OutgoingChallengeStatus(StrEnum):
    PENDING = "pending"
    NOT_PENDING = "not_pending"


@dataclass(frozen=True, slots=True)
class OutgoingChallengeObservation:
    status: OutgoingChallengeStatus
    target_user_id: str
    format_id: str | None
    source_kind: str
```

Bei der PM-Form werden Sender, Empfänger und der eigene normalisierte User-ID
gegeneinander geprüft; beliebiger PM-Chat mit `/challenge` im Nachrichtentext
ist keine Zustandsnachricht. Bei der JSON-Form werden `challengeTo.to` und
`challengeTo.format` strikt validiert. Beide Formen beweisen nur
`PENDING`/`NOT_PENDING`, niemals Annahme, Ablehnung, Abbruch oder Ablauf.
Annahme beweist ausschließlich die passende `|init|battle`-
Rauminitialisierung.

Vor Raumstart:

- `|popup|` mit Teamvalidation wird `TeamValidationError`;
- andere fehlgeschlagene Setups werden `ChallengeSetupError` mit einem der
  drei nachfolgend definierten Subcodes;
- fremde Battle-Räume werden nicht an die Session weitergereicht;
- während Raumaufbau bereits gelieferte Ziellines bleiben in Reihenfolge
  gepuffert.

Die maschinenlesbaren `ChallengeSetupError`-Subcodes lauten:

```text
challenge_command_rejected_explicit
challenge_not_pending
challenge_setup_timeout
```

Die Evidenz ist bindend:

| Subcode | Autoritative M1-Evidenz |
|---|---|
| `challenge_command_rejected_explicit` | globale `popup`-/Fehlernachricht passt vollständig zu einer versionierten, challenge-spezifischen Pattern-ID aus dem gepinnten Servercode |
| `challenge_not_pending` | die eigene Challenge war im dokumentierten Challenge-State nachweislich pending, verschwindet wieder, und bis zur Coordinator-Deadline erscheint keine passende Battle-Room-Initialisierung |
| `challenge_setup_timeout` | die injizierte Coordinator-Deadline endet ohne passende Battle-Room-Initialisierung und ohne stärkere klassifizierte Evidenz |

Die versionierte Pattern-Allowlist für
`challenge_command_rejected_explicit` enthält in M1 ausschließlich die
challenge-spezifischen vollständigen Servertexte aus dem gepinnten Commit.
`requested_username`, `target_display` und `format_id` werden nicht frei
akzeptiert, sondern müssen mit dem aktuellen Coordinator-Auftrag
übereinstimmen:

| Pattern-ID | Vollständige Nachrichtenform |
|---|---|
| `challenge-user-not-found` | `The user '{requested_username}' was not found.` |
| `challenge-self` | `You can't battle yourself. The best you can do is open PS in Private Browsing (or another browser) and log into a different username, and battle that username.` |
| `challenge-already-outgoing` | `You are already challenging someone. Cancel that challenge before challenging someone else.` |
| `challenge-target-blocking` | `The user '{target_display}' is not accepting challenges right now.` |
| `challenge-throttled` | `You challenged less than 10 seconds after your last challenge! It's cancelled in case it's a misclick.` |
| `challenge-target-capacity` | `This user already has 3 pending challenges.\nYou must be autoconfirmed to challenge them.` |
| `challenge-user-locked` | `You are locked and cannot challenge unlocked users. If this user is your friend, ask them to challenge you instead.` |
| `challenge-user-battle-banned` | `You are banned from battling and cannot challenge users.` |
| `challenge-username-required` | `You must choose a username before you challenge someone.` |
| `challenge-existing-between-users` | `There's already a challenge ({format_id}) between you and {target_display}!` |
| `challenge-server-restarting` | `The server is restarting. Battles will be available again in a few minutes.` |
| `challenge-server-under-attack` | `The server is under attack. Battles cannot be started at this time.` |

Die Tests übernehmen diese vollständigen Formen aus
`server/chat-commands/core.ts` beziehungsweise `server/ladders.ts`. Freier
Teilstringvergleich ist verboten. Nicht passende Popups werden nicht als
Challenge-Ursache erfunden, sondern als unbekannte Setup-Antwort mit
`unknown_protocol_event` abgebrochen.

Teamvalidation bleibt die spezifischere Primärklasse
`team_validation_error`; sie erhält keinen doppelten Challenge-Subcode.
Beide durch den `ChallengeStateReader` normalisierten Wire-Formen beweisen nur
den Challenge-Zustand, nie die Ursache seines Verschwindens.
`challenge_rejected`, `challenge_cancelled` und `challenge_expired` sind daher
keine M1-Subcodes. M1 sendet weder `/cancelchallenge` noch `/reject`.

Der Coordinator loggt Teamdigest und Gegner-ID, niemals Passwort oder
Assertion.

- [ ] **Step 1: Failing Coordinator-Tests schreiben**

Tests prüfen exakte `|/utm`-/`|/challenge`-Socket-Kommandos, Room-Discovery,
Fremdraumfilter, Pufferreihenfolge, Teamvalidation, alle drei beobachtbaren
Setup-Subcodes und sauberes Close. Weitere Tests beweisen:

- dokumentiertes `updatechallenges` und die gepinnte PM-`/challenge`-Form
  ergeben wertgleiche Pending-/Not-Pending-Beobachtungen;
- gewöhnlicher PM-Chat mit `/challenge` im Inhalt wird nicht als Zustand
  akzeptiert;
- jede Pattern-ID akzeptiert ausschließlich ihre vollständige
  parametrisierte Form; Präfix-, Suffix- und falscher-Ziel-Near-Miss werden
  abgelehnt;
- das bloße Verschwinden einer pending Challenge wird nie als Ablehnung,
  Abbruch oder Ablauf bezeichnet;
- Annahme wird ausschließlich durch passende Battle-Room-Initialisierung
  bestätigt;
- ein nicht allowlistetes Popup erhält keinen erfundenen Subcode;
- `/cancelchallenge`, `/reject` und Incoming-Challenge-Acceptance sind nicht
  implementiert.

- [ ] **Step 2: Tests rot ausführen**

```powershell
uv run pytest packages/battlebelief-runtime/tests/adapters/test_challenge_state_reader.py tests/integration/test_challenge_coordinator.py -v
```

- [ ] **Step 3: ChallengeStateReader und Coordinator implementieren**
- [ ] **Step 4: Tests grün ausführen**
- [ ] **Step 5: Commit**

```powershell
git add packages/battlebelief-runtime tests/integration/test_challenge_coordinator.py
git commit -m "feat(runtime): coordinate one direct Gen9 OU challenge"
```

---

## Task 12 – CLI und secretsicheres Runtime-Profil

**Files:**

- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/cli.py`
- Create: `packages/battlebelief-runtime/src/battlebelief_runtime/config.py`
- Modify: `packages/battlebelief-runtime/tests/test_cli.py`
- Modify: `packages/battlebelief-runtime/README.md`

### CLI

M1 ergänzt:

```text
battlebelief challenge
  --username USER
  --opponent USER
  --team PATH
  [--server-url URL]
```

`challenge` bedeutet in M1 ausschließlich „ausgehende direkte Challenge“.
Die Hilfe nennt diese Einschränkung sowie die notwendige Annahme durch den
Gegner ausdrücklich.

Das Passwort kommt ausschließlich aus:

```text
BATTLEBELIEF_SHOWDOWN_PASSWORD
```

Es gibt kein `--password`-Argument. Fehlende Variable, ungültiger Teampfad
oder leere User-ID beendet vor Netzwerkzugriff mit Exitcode 2. Fehlerausgaben
enthalten weder Passwort, Assertion noch Packed Team.

`doctor` meldet nach M1:

```json
{
  "battle_capability": "heuristic_direct_challenge",
  "entrypoint": "ready",
  "package": "battlebelief-runtime",
  "phase": "M1",
  "version": "0.2.0"
}
```

Der Versionswert wird in Task 14 atomar aktiviert; während der Entwicklung
prüfen CLI-Tests den gemeinsamen Versionsprovider statt doppelte Konstanten.

- [ ] **Step 1: Failing CLI-Tests schreiben**

Tests injizieren Config und Coordinator; sie öffnen kein Netzwerk.
Pflichtfälle: fehlendes Secret, fehlendes Team, korrektes Gen9-OU-Profil,
sanitisierte Fehlermeldung, `doctor`.

- [ ] **Step 2: Tests rot ausführen**

```powershell
uv run pytest packages/battlebelief-runtime/tests/test_cli.py -v
```

- [ ] **Step 3: Config und CLI implementieren**
- [ ] **Step 4: Tests grün ausführen**
- [ ] **Step 5: PR-4-Gates ausführen und committen**

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run python tools/check_architecture.py
git add packages/battlebelief-runtime
git commit -m "feat(runtime): expose the M1 challenge CLI"
```

Ein echter öffentlicher Login/Challenge-Lauf ist kein CI-Schritt und darf nur
nach Prüfung der zum Laufzeitpunkt geltenden Serverregeln mit einem
dedizierten Testkonto erfolgen.

---

## Task 13 – Protocol- und Safety-Smokes

**Files:**

- Create: `tests/smokes/test_protocol_smoke.py`
- Create: `tests/smokes/test_safety_smoke.py`
- Create: `tests/contracts/test_action_safety_contract.py`
- Modify: `tests/contracts/test_protocol_contract.py`

Es wird kein `pytest-asyncio` hinzugefügt. Async-Smokes werden in normalen
Pytest-Tests mit `asyncio.run()` ausgeführt; für zwei kleine Smokes ist eine
weitere Dev-Abhängigkeit nicht nötig.

### Protocol-Smoke

Für jede im `corpus.json` registrierte Fixture:

1. alle Zeilen parsen;
2. alle Events reduzieren;
3. null unbekannte Events;
4. null Parserfehler;
5. null Reducer-Invariantfehler;
6. Endzustand zweimal berechnen und auf Wertgleichheit prüfen.

Die Fehlermeldung listet alle Datei-/Zeilennummern gesammelt.

### Safety-Smoke

Mit FakeConnection werden mindestens diese vollständigen Abläufe ausgeführt:

- normaler Move;
- Request-after-turn;
- Forced Switch;
- Revival;
- Tera Request;
- `maybeTrapped`;
- Team Preview;
- Wait;
- Request vor Metadaten beziehungsweise eigener Active-Identität mit späterer
  erfolgreicher Reconciliation;
- zwei Pending-Requests, von denen nur der neueste ausgeführt wird;
- Battle-Ende bei Pending-Request ohne Versand;
- stale und missing `rqid`;
- Policy-Out-of-Set;
- Server Invalid/Unavailable;
- unbekanntes/malformed Event;
- `inactiveoff` als sichtbare Timer-Cleared-Evidence;
- nackter `|`-Spacer in der Battle-Initialisierung;
- Room-Control/Chat gemischt mit Battle-Events, einschließlich Chattext mit
  eingebettetem `|request|`;
- terminale Timer-/Forfeit-Line;
- zwei parallele Raumpräfixe bei weiterhin nur einer Session.

Für alle erfolgreichen Abläufe gilt:

- jeder Versand gehört zum richtigen Raum;
- jede Submission ist Mitglied des neuesten `SafeSubmissionSet`;
- jeder Versand enthält den aktuellen `rqid`;
- kein Request wird doppelt beantwortet;
- Room-Control/Chat verändert weder `ObservedState` noch Request-Freshness;
- `room_control_or_chat_count` und `ignored_display_count` entsprechen dem
  Fixture;
- `ActionProvenance.EXPLICIT_REQUEST` und
  `ActionProvenance.SERVER_DEFAULT` bleiben unterscheidbar;
- `default_submissions` stimmt mit den tatsächlich gesendeten
  Server-Fallbacks überein.

Für alle Fehlerabläufe gilt:

- kein unvalidierter Versand;
- genau eine primäre Fehlerklasse;
- der Fehler bleibt im Testresultat sichtbar.

- [ ] **Step 1: Smokes und Contract-Tests schreiben**
- [ ] **Step 2: Gezielte Smokes ausführen**

```powershell
uv run pytest tests/smokes/test_protocol_smoke.py tests/smokes/test_safety_smoke.py tests/contracts -v
```

Expected: PASS.

- [ ] **Step 3: Gesamte Suite ausführen**

```powershell
uv run pytest
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add tests
git commit -m "test(m1): prove protocol and action safety contracts"
```

---

## Task 14 – CI, Lockstep-Version und Status

**Files:**

- Modify: `.github/workflows/pr.yml`
- Modify: `pyproject.toml`
- Modify: `packages/battlebelief-core/pyproject.toml`
- Modify: `packages/battlebelief-runtime/pyproject.toml`
- Modify: `packages/battlebelief-lab/pyproject.toml`
- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/public_api/status.py`
- Modify: `packages/battlebelief-runtime/tests/test_cli.py`
- Modify: `packages/battlebelief-core/src/battlebelief_core/__init__.py`
- Modify: `packages/battlebelief-runtime/src/battlebelief_runtime/__init__.py`
- Modify: `packages/battlebelief-lab/src/battlebelief_lab/__init__.py`
- Modify: `packages/battlebelief-core/tests/test_package.py`
- Modify: `packages/battlebelief-lab/src/battlebelief_lab/cli.py`
- Modify: `packages/battlebelief-lab/tests/test_cli.py`
- Modify: `tools/smoke_packages.py`
- Modify: `uv.lock`

### Version

Alle drei Pakete wechseln gemeinsam:

```text
0.1.0 → 0.2.0
```

Runtime verlangt `battlebelief-core==0.2.0`; Lab verlangt Core und Runtime
jeweils `==0.2.0`. Die websockets-Pin bleibt Runtime-only.

Die Workspace-Version, Paket-`__version__`-Werte, CLI-/Doctor-Ausgaben,
Pakettests und `tools/smoke_packages.py` werden im selben Commit auf `0.2.0`
umgestellt. Es darf kein ausführbarer `0.1.0`-Restwert bleiben.

### CI

`pr.yml` erhält zwei sichtbare Jobs:

```text
protocol-smoke
safety-smoke
```

Beide:

- verwenden dieselben gepinnten Checkout-/Setup-Python-Actions wie bestehende
  Jobs;
- installieren mit `uv sync --frozen --all-packages --group dev`;
- führen nur ihren gezielten Smoke aus;
- besitzen keine Secrets und nur `contents: read`;
- haben keine Workflow-Level-Pfadfilter.

`pr-gate`:

- nimmt beide Jobs in `needs` auf;
- exportiert beide Results;
- akzeptiert weiterhin nur `success|skipped`;
- behält exakt den Namen `pr-gate`.

- [ ] **Step 1: CI-Datei ändern**
- [ ] **Step 2: Lockstep-Version atomar ändern**
- [ ] **Step 3: Lockfile aktualisieren**

```powershell
uv lock
```

- [ ] **Step 4: Versions- und Paket-Smokes ausführen**

```powershell
uv run python tools/check_versions.py
uv run python tools/check_architecture.py
uv run python tools/smoke_packages.py
```

Expected: alle Befehle enden mit Exitcode 0; Runtime-Doctor zeigt M1 und
`heuristic_direct_challenge`.

- [ ] **Step 5: Workflow-Semantik lokal prüfen**

```powershell
uv run pytest tests/smokes/test_protocol_smoke.py -v
uv run pytest tests/smokes/test_safety_smoke.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add .github/workflows/pr.yml pyproject.toml packages uv.lock
git commit -m "ci(m1): gate protocol and action safety smokes"
```

---

## Task 15 – M1-Akzeptanz, Dokumentation und Proof-PR

**Files:**

- Modify: `README.md`
- Modify: `packages/battlebelief-runtime/README.md`
- Create: `docs/operations/m1-protocol-safe-evidence.md`
- Modify: `docs/README.md`

### Ehrlicher Status

README:

```markdown
> **Status:** M1 protocol-safe prototype complete. The runtime can execute one
> direct Gen 9 OU challenge with a deterministic heuristic policy. Search,
> belief, training, ladder automation, engine parity, strength, and MVP claims
> are not implemented.
```

Das Evidence-Dokument zeichnet auf:

- BattleBelief-Commit und Paketversion;
- Protocol-Corpus-ID und Showdown-Referenzcommit;
- ausgeführte lokale Befehle mit Exitcode;
- Python-/OS-Matrix aus GitHub Actions;
- geprüfte Success- und Failure-Flows;
- getrennte Zähler für explizite und server-delegierte
  `default`-Submissions;
- `room_control_or_chat_count` und `ignored_display_count`;
- Challenge-Setup-Ergebnisse nach maschinenlesbarem Subcode;
- nicht ausgeführte öffentliche Login-/Challenge-Prüfung;
- `synthetic contract coverage: complete for declared M1 mapping`;
- `observed live protocol coverage: not established`, solange kein
  freigegebener Live-Lauf genau diese Evidenz erhoben hat;
- Einschränkung auf ausgehende direkte Challenges und notwendige
  Gegnerannahme;
- verbleibende M1-Limits;
- Link auf den grünen `pr-gate`.

Frontmatter:

```yaml
document_id: evidence-m1-protocol-safe-prototype
title: M1 Protocol-safe Prototype Evidence
document_type: audit
status: accepted
normative: false
version: 1
applies_to:
  - runtime
  - gen9ou
effective_from: 2026-07-30
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-30
```

Die Roadmap bleibt unverändert; sie definiert bereits Lieferumfang und Gate.
Der Docs-Index verlinkt ausschließlich das neue Evidence-Dokument.

- [ ] **Step 1: Vollständige lokale Gates ausführen**

```powershell
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run python tools/check_versions.py
uv run python tools/check_architecture.py
uv run python tools/check_docs.py
uv run python tools/check_schemas.py
uv run python tools/smoke_packages.py
uv run battlebelief doctor
```

Expected: alle Befehle enden mit Exitcode 0; Doctor meldet Version `0.2.0`,
Phase `M1` und `heuristic_direct_challenge`.

- [ ] **Step 2: Negative Scope-Prüfung ausführen**

```powershell
rg -n "poke_engine|poke-engine|DUCT|MCTS|BeliefState|duckdb|pyarrow|torch|onnx|/search" packages tests .github
```

Expected:

- keine M2+-Implementierungen;
- `/search` kommt in keinem ausführbaren Runtime-Pfad vor;
- zulässige Treffer sind ausschließlich Dokument-/Negativtesttexte und
  werden im PR erklärt.

- [ ] **Step 3: Diff- und Artefaktprüfung**

```powershell
git status --short
git diff --check
git diff --stat origin/main...HEAD
git diff --name-only origin/main...HEAD
```

Prüfen:

- keine Credentials, Cookies, Assertions oder lokale Pfade;
- keine Replays, Datasets, Modelle oder große Outputs;
- keine Änderung am unveränderlichen Design-Freeze;
- kein historischer VGC-Code ohne Transfer-Audit;
- keine Hidden-Information-Felder im Core-ObservedState;
- keine Wire-/JSON-Dicts in Core-Typen.

- [ ] **Step 4: Evidence und READMEs mit tatsächlich gemessenen Ergebnissen schreiben**

Keine grüne Behauptung wird vor den ausgeführten Befehlen eingetragen.

- [ ] **Step 5: Dokumentgates erneut ausführen**

```powershell
uv run python tools/check_docs.py
uv run pytest tests/tooling/test_docs.py -v
```

Expected: PASS.

- [ ] **Step 6: Finalen Commit erstellen**

```powershell
git add README.md packages/battlebelief-runtime/README.md docs
git commit -m "docs(m1): record protocol-safe prototype evidence"
```

- [ ] **Step 7: Proof-PR öffnen**

Der PR-Body enthält:

```text
Scope:
- protocol-safe direct Gen9 OU challenge prototype

Evidence:
- local full gate outputs
- protocol corpus id and Showdown reference commit
- GitHub pr-gate URL

Explicit non-claims:
- no engine parity
- no search or belief
- no ladder automation
- no strength or MVP claim

External validation:
- public login/challenge smoke run or explicitly not run
```

- [ ] **Step 8: Erst nach grünem `pr-gate` und Maintainerfreigabe mergen**

Kein Tag und kein GitHub Release wird für M1 erzeugt.

## 6. M1-Abnahmematrix

| Vertragsbereich | Nachweis |
|---|---|
| Raumtreue | Multi-Room-Frame- und Coordinator-Tests |
| Room-Multiplexing | äußerer Payload-Klassifikator trennt Chat/Control, Battle, Request, Error und Timer ohne rekursive Inhaltsinterpretation |
| Parserabdeckung | versionierter gültiger Corpus ohne Unknown/Malformed |
| Display-Spacer | nackter `|`-Payload wird bewusst als `IgnoredDisplayEvent(kind="spacer")` gezählt |
| Reducer | jeder state-bearing Eventtyp verändert passenden State oder bricht klassifiziert ab |
| Hidden Information | eigener Leakage-Grenztest; Request hydratisiert State nicht |
| Request-Trigger | Request-before/after-turn, Forced-Switch- und Revival-Smokes |
| Pending State | Accept/Pending/Reject, spätere Reconciliation, newest-rqid-only und terminal-no-send |
| Legalität | vollständige Requestvarianten plus konservative Unsicherheitsregeln |
| Default-Evidenz | server-delegierter Fallback ist von expliziten Actions getrennt und separat gezählt |
| Tera | `canTerastallize`-String → normaler und Tera-Move; exaktes Encoding |
| Team Preview | M1-materialisierte Permutationsdomäne, natürliche Heuristikorder |
| Freshness | duplicate, stale, missing und changed-same-rqid getestet |
| Safety | unabhängiger Membership-/Shape-/Identity-Gate |
| Serverfehler | erste Invalid-/Unavailable-Line bricht klassifiziert ab |
| Teamformat | nur echtes einzeiliges Packed-Format; stabiler Digest |
| Auth | `/api/login`, exaktes `updateuser NAMED=1`, Queue-Erhalt |
| Battlefähigkeit | ausgehender direkter Challenge-Koordinator mit ausschließlich beobachtbaren Setup-Subcodes, keine Incoming-Annahme, keine Ladder |
| Coverage-Claim | synthetische Contract-Abdeckung getrennt von nicht etablierter Live-Abdeckung |
| CI | sichtbare Smokes im stabilen `pr-gate` |
| Claimgrenze | M1-Status ohne Search-, Strength-, Parity- oder MVP-Claim |

## 7. Bewusst akzeptierte M1-Kosten

- Ein eigener Client erhöht Wartungsaufwand, hält aber fremde Zustandsmodelle
  aus dem Core.
- Die konservative `maybeTrapped`-/`maybeDisabled`-Behandlung verschenkt
  spielerische Optionen, schützt aber das Null-Error-Safety-Ziel.
- Vollständige Team-Preview-Permutationen erzeugen bei sechs Pokémon 720
  Kandidaten; das ist für M1 klein genug und vermeidet eine unvollständige
  Pseudo-Aktionsmenge. Die Materialisierung ist ausdrücklich kein
  langfristiger Core-Vertrag; ein späterer `TeamOrderDomain`-Typ darf sie
  ersetzen.
- Packed-only schließt Nutzer mit reinem Exporttext zunächst aus; dafür
  erfindet M1 keinen fehlerhaften Konverter.
- Der direkte, ausgehende Challenge-Pfad benötigt die explizite
  Gegnerannahme und beweist keine öffentliche Ladder-Tauglichkeit.
- Explizite Challenge-Popup-Muster sind an den gepinnten englischen
  Server-Snapshot gebunden. Abweichende oder übersetzte Texte brechen in M1
  fail-closed ab, statt eine Ursache zu erraten.
- Der versionierte synthetische Corpus beweist nur die deklarierte
  M1-Mapping-Abdeckung in seinem Evidenzraum. Beobachtete Live-Abdeckung ist
  damit nicht etabliert.

Diese Kosten sind absichtlich sichtbar. M2 darf sie nur mit eigenen Tests und
Contracts ändern, nicht still in M1 umgehen.

## 8. Verifizierte Primärquellen

- [Pokémon Showdown Client-/Server-Protokoll, Commit
  `59da482`](https://github.com/smogon/pokemon-showdown/blob/59da482eabc87245eb62313593e468e81ca537d9/PROTOCOL.md)
- [Pokémon Showdown Simulator-Protokoll, Commit
  `59da482`](https://github.com/smogon/pokemon-showdown/blob/59da482eabc87245eb62313593e468e81ca537d9/sim/SIM-PROTOCOL.md)
- [Pokémon Showdown Teamformate, Commit
  `59da482`](https://github.com/smogon/pokemon-showdown/blob/59da482eabc87245eb62313593e468e81ca537d9/sim/TEAMS.md)
- [Aktuelle Request- und Choice-Typen in `sim/side.ts`, Commit
  `59da482`](https://github.com/smogon/pokemon-showdown/blob/59da482eabc87245eb62313593e468e81ca537d9/sim/side.ts)
- [`reviving`-Feld im Switch-Request in `sim/pokemon.ts`, Commit
  `59da482`](https://github.com/smogon/pokemon-showdown/blob/59da482eabc87245eb62313593e468e81ca537d9/sim/pokemon.ts)
- [Challenge-Command-Antworten in `server/chat-commands/core.ts`, Commit
  `59da482`](https://github.com/smogon/pokemon-showdown/blob/59da482eabc87245eb62313593e468e81ca537d9/server/chat-commands/core.ts)
- [Challenge-Setup-Antworten in `server/ladders.ts`, Commit
  `59da482`](https://github.com/smogon/pokemon-showdown/blob/59da482eabc87245eb62313593e468e81ca537d9/server/ladders.ts)
- [Challenge-State-Emission in `server/ladders-challenges.ts`, Commit
  `59da482`](https://github.com/smogon/pokemon-showdown/blob/59da482eabc87245eb62313593e468e81ca537d9/server/ladders-challenges.ts)
- [`websockets` asyncio client
  API](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html)
- [`websockets` 16.1.1 auf
  PyPI](https://pypi.org/project/websockets/16.1.1/)
