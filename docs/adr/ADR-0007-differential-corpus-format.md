---
document_id: adr-0007-differential-corpus-format
title: "ADR-0007: Versioniertes Differential-Corpus-Format"
document_type: adr
status: accepted
normative: false
version: 1
applies_to:
  - evaluation
  - lab
  - gen9ou
effective_from: 2026-08-07
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-07
---

# ADR-0007: Versioniertes Differential-Corpus-Format

## Kontext

Task 28 friert den Showdown-versus-`poke-engine`-Differential-Harness ein, bevor
Task 29 echte Qualification-Ergebnisse erzeugt. Der M2-Plan beschreibt unter
MD-09 drei Corpus-Formate, ist selbst aber `status: proposed` und
`normative: false` und besitzt daher keine Entscheidungsautorität.

Ein Differential-Corpus muss kleine Änderungen reviewbar halten, jede Fixture
unabhängig adressierbar machen und verhindern, dass nach Sichtung realer
Ergebnisse günstige Fälle still verändert oder ersetzt werden.

## Erwogene Optionen

### Option A – kanonischer Index plus einzelne kanonische JSON-Fixtures

Ein versionierter Index referenziert eine kanonische JSON-Datei pro Fall. Jede
Fixture besitzt eine eigene Identität und einen eigenen Digest; der Corpus-
Digest bindet die sortierte Fixture-Closure.

### Option B – monolithisches JSON

Alle Fälle liegen in einem Dokument. Das reduziert die Zahl der Dateien, macht
kleine Änderungen jedoch diff-noisy und erschwert unabhängige Fixture-Digests.

### Option C – ausführbare Python-Fixtures

Fixture-Semantik wird in Python ausgedrückt. Das ist flexibel, vermischt aber
Daten und Ausführung und ist für eine preregistrierte, content-addressed Corpus-
Quelle ungeeignet.

## Entscheidung

Die Maintainer-Auswahl ist **Option A**. Die ausdrückliche Maintainer-Freigabe
wurde am 2026-08-07 erteilt; ADR-0007 ist damit akzeptiert. `normative: false`
bleibt bestehen.

Task 28 verwendet daher einen versionierten Corpus mit:

- einem kanonischen JSON-Index;
- genau einer kanonischen JSON-Fixture-Datei je Fall;
- eindeutigen Fixture-IDs und Fixture-Digests;
- einem Corpus-Digest über die deterministisch sortierte vollständige Fixture-
  Closure;
- expliziten Bindungen je Fixture an Generation, Format, Ruleset, Seed,
  Capability-IDs, initialen autoritativen Full State, deklarierte öffentliche
  Ansichten, geordnete Joint-Action-/Chance-Inputs, Observation-Checkpoints,
  Vergleichsfelder, Classification-Policy-Version und Provenienz;
- fail-closed Validierung für fehlende, doppelte, unbekannte oder nicht
  referenzierte Fixture-Dateien und Capability-IDs.

Sobald eine Corpus-Version in Qualification-Evidenz referenziert wurde, bleiben
Index und Fixtures dieser Version unverändert. Eine semantische oder inhaltliche
Änderung erzeugt eine neue Corpus-Version; bestehende favorable oder unfavorable
Ergebnisse werden nicht in-place umgeschrieben.

## Konsequenzen

Positiv:

- Kleine Mechanics-Fälle bleiben separat reviewbar.
- Jeder Fall und die gesamte Corpus-Closure sind content-addressed.
- Coverage über den Capability-Katalog ist maschinenprüfbar.
- Task 29 kann exakt an die vorab gemergten Corpus-Bytes gebunden werden.

Kosten und Risiken:

- Der Index benötigt Closure- und Ordering-Validierung.
- Änderungen nach dem Freeze erfordern eine neue Corpus-Version und später eine
  neue Qualification-Version.
- Fixtures müssen minimal und projekt-authored oder sauber lizenziert bleiben.

## Nicht autorisiert

Dieser ADR autorisiert keine:

- reale Showdown-versus-`poke-engine`-Qualification;
- Capability-Elevation oder `exact`-/`bounded_approximation`-Claims;
- Änderung des Task-27-Runtime-Adapters;
- Search-, Eligibility-, Closed-World- oder Strength-Implementierung;
- nachträgliche Anpassung von Corpus-v1 an reale Task-29-Ergebnisse.

MD-09 Option A is approved by the Maintainer.
