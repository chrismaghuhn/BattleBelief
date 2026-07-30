---
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
---

# ADR-0004: Sauberer Showdown-Runtime-Adapter

## Kontext und Entscheidungsproblem

M1 benötigt eine Showdown-Runtime-Verbindung für eine authentifizierte
Gen-9-OU-Direktherausforderungssession. Drei Ansätze standen zur Auswahl:
Ein sauberer eigener Adapter, ein selektiver Transfer aus einem historischen
VGC-Projekt und die Integration eines bestehenden Bot-Frameworks.

Die Entscheidung bestimmt die Provenienz der Runtime-Connection, die
Abhängigkeiten des `battlebelief-runtime`-Pakets und den Grad der Kontrolle
über Raumframing-, Request- und Safety-Semantik.

Die eingefrorenen Architektur- und Grenzregeln stehen ausschließlich in
[`architecture-code-boundaries`](../architecture/code-boundaries.md) und
[`architecture-dependency-matrix`](../architecture/dependency-matrix.md).
Dieser ADR definiert keine neuen Importregeln oder Abhängigkeitsmatrizen.

## Entscheidung

**Option A: Saubere Eigenimplementierung** auf Basis der offiziellen
Showdown-Protokollspezifikation.

Runtime-Abhängigkeit: `websockets==16.1.1`.

Scope: eine authentifizierte Gen-9-OU-Direktherausforderungssession.

Non-Goals für M1:
- Ladder-Suche
- Reconnect-Schleife
- gleichzeitige Mehrfachbattles

Primärquellen am gepinnten Showdown-Commit
`59da482eabc87245eb62313593e468e81ca537d9`:

- [PROTOCOL.md](https://github.com/smogon/pokemon-showdown/blob/59da482eabc87245eb62313593e468e81ca537d9/PROTOCOL.md)
- [sim/SIM-PROTOCOL.md](https://github.com/smogon/pokemon-showdown/blob/59da482eabc87245eb62313593e468e81ca537d9/sim/SIM-PROTOCOL.md)
- [sim/TEAMS.md](https://github.com/smogon/pokemon-showdown/blob/59da482eabc87245eb62313593e468e81ca537d9/sim/TEAMS.md)

Der gepinnte Commit steht im Corpus-Manifest
`tests/fixtures/protocol/corpus.json`. Tests greifen nicht auf `master` oder
das öffentliche Netzwerk zu.

## Geprüfte Alternativen

### Option B – Selektiver Transfer aus dem historischen VGC-Projekt

Das historische Projekt enthält möglicherweise wiederverwendbare Teile. Jede
übertragene Einheit benötigt jedoch vor dem Merge einen vollständigen
Provenienz-, Lizenz-, Bug- und Singles-Scope-Audit gemäß
[`transfer-audit`](../transfer-audit/README.md). Alte Doubles/VGC-Annahmen
können versteckt bleiben und die Singles-Safety-Grenze verletzen.

**Gewinn:** potenziell weniger Erstaufwand bei einzelnen Modulen.

**Preis:** jede Einheit erfordert einen separaten Transfer-Audit vor dem Merge;
Lizenz- und Provenienzkette muss neu dokumentiert werden; Zeitpunkt und Umfang
sind vor M1 unklar.

**Disposition:** deferred. Ein späterer selektiver Transfer bleibt möglich und
ersetzt ausschließlich einen Runtime-Leaf-Adapter hinter seiner öffentlichen
Schnittstelle. Der bestehende Transfer-Audit-Prozess greift unverändert.

### Option C – Bot-Framework (z. B. poke-env oder Metamon)

Ein fertiges Framework bietet schneller Funktionsumfang und übernimmt
Login-Logik und Verbindungsmanagement.

**Gewinn:** kürzere Implementierungszeit für die erste funktionierende Session.

**Preis:** zusätzliche externe Abhängigkeit; das fremde Zustandsmodell
widerspricht den eingefrorenen Core-Grenzen; Protokoll- und Safety-Semantik
liegen im Framework, nicht im kontrollierten `battlebelief-runtime`-Code.

**Disposition:** für M1 abgelehnt. Framework-Abhängigkeiten werden erst
eingeführt, wenn eine konkrete Notwendigkeit die Kontrollverluste rechtfertigt.

## Sicherheits- und Provenienzgrenze

Alle Protokoll-Fixtures und -Annahmen leiten sich aus dem gepinnten
Showdown-Commit ab. Es wird kein Drittcode kopiert. Credentials gelangen
ausschließlich über injizierte `AssertionProvider`-Ports in die Runtime;
`battlebelief-core` kennt weder Credentials noch WebSocket-Zeilen.

## Reversal-Punkt

Dieser ADR ist eine M1-Implementierungsentscheidung und reversibel im
folgenden Sinne: Später darf **ausschließlich** die Runtime-Connection hinter
ihrer öffentlichen `BattleConnection`-Protokollschnittstelle ersetzt werden.
Core-Objekte, Protokoll-Parser, Request-Reader und Safety-Gate bleiben
stabil; sie werden nicht durch den Ersatz des Verbindungsadapters berührt.

## M1-Scope und Non-Goals

Dieser ADR gilt ausschließlich für M1 und den Umfang, den
[`plan-m1-protocol-safe-prototype`](../superpowers/plans/2026-07-29-battlebelief-m1-protocol-safe-prototype.md)
festlegt. Engine, Belief, Search, Training, Ladder und VGC liegen außerhalb
dieses Scopes.

## GitHub-Decision-Issue

[Decision: clean Showdown runtime adapter for M1 (#6)](https://github.com/chrismaghuhn/BattleBelief/issues/6)
