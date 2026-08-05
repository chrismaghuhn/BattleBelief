---
document_id: architecture-memory-hierarchy
title: Memory-Hierarchie und battle-lokale Working Sets
document_type: architecture
status: accepted
normative: false
version: 1
applies_to:
  - architecture
  - belief
  - m3
effective_from: 2026-08-05
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-05
---

# Memory-Hierarchie und battle-lokale Working Sets

Dieses Dokument erklärt die vorgesehene Speicherarchitektur für M3 und spätere
Belief-, Trainings- und Opponent-Modeling-Arbeit. Es definiert keine neue
normative API und ändert den M2-Scope nicht. Bei Widerspruch gelten die
akzeptierten Contracts und der normative Dokumentindex.

## Kerninvariante

> **Unveränderliches Wissen wird geteilt; pro Battle werden nur veränderliche
> Zustände gespeichert.**

Langzeitwissen wird offline gespeichert, geprüft und in einen versionierten
Snapshot kompiliert. Die Runtime validiert und öffnet das Artefakt. Der Core
sieht ausschließlich eine speicherneutrale semantische Sicht. Belief und Search
arbeiten auf kleinen battle- beziehungsweise entscheidungslokalen Strukturen.

## Verantwortungsverteilung

```text
battlebelief-lab
├─ Replays und Rohdaten
├─ DuckDB / Parquet
├─ Aggregation und Kalibrierung
└─ erzeugt content-addressed Meta-Snapshot

battlebelief-runtime
├─ validiert Manifest, Schema und Digests
├─ besitzt Datei-, Mapping- und Handle-Lebensdauer
├─ öffnet SQLite, Arrow oder alternatives Snapshot-Artefakt
└─ implementiert die semantische Core-Sicht

battlebelief-core
├─ MetaPriorSnapshot als speicherneutraler Vertrag
├─ snapshotgebundene Hypothesen-IDs
├─ BattleWorkingSet
├─ BeliefState
└─ DecisionWorkingSet

Search / Engine
├─ kompakte IDs und Arrays
├─ keine SQL-Abfragen
├─ keine Dateisystemzugriffe
└─ keine unnötigen Objektallokationen im Hot Path
```

Die verbindlichen Paket- und Importgrenzen bleiben in
[Code- und Paketgrenzen](code-boundaries.md). Insbesondere kennt der Core weder
SQLite noch DuckDB, Arrow, Dateipfade oder konkrete Mapping-Handles.

## Semantische Sicht statt Speicherformat

`MetaPriorProvider` liefert dem Core einen unveränderlichen
`MetaPriorSnapshot`. Der Begriff bezeichnet eine semantische Sicht, nicht die
vollständige Materialisierung sämtlicher Sets als Python-Objekte.

Eine mögliche, nicht eingefrorene Skizze ist:

```python
from typing import Protocol, Sequence


class SetHypothesisView(Protocol):
    @property
    def snapshot_digest(self) -> str: ...

    def hypotheses_for_species(
        self,
        species_id: int,
    ) -> Sequence[int]:
        """Return snapshot-local hypothesis row IDs."""
```

Die konkrete Runtime-Implementierung darf intern zum Beispiel heißen:

```text
SnapshotArtifactHandle
MemoryMappedSetTable
ArrowSnapshotReader
```

Diese Namen, das Dateiformat und die konkrete Rückgabestruktur sind nicht durch
dieses Dokument festgelegt. Der Core-Vertrag beschreibt ausschließlich
Bedeutung, Identität und Lebensdauer der Sicht.

## Statische und veränderliche Daten

### Geteiltes Snapshot-Wissen

Statische Informationen werden nach Veröffentlichung nicht verändert:

```text
Species
Item
Ability
Moves
Nature
EV- oder Feasible-Region
Tera-Typ
Quelle und Evidenzstatus
ursprünglicher Prior
Team- und Archetyp-Korrelationen
```

Diese Daten werden nicht für jeden Battle kopiert. Battle-lokale Strukturen
verweisen über snapshotgebundene IDs oder Zeilenidentitäten auf den Snapshot.

### Battle-lokaler Zustand

Ein `BattleWorkingSet` enthält nur veränderliche oder battle-spezifische Daten,
beispielsweise:

```text
snapshot_digest
hypothesis_ids
Log-Gewichte
Kompatibilitätsmasken
Reveal- und Evidenzstatus
Speed-Grenzen
OTHER- und Tail-Masse
battle-lokale Caches
```

Die konkrete Repräsentation als Listen, Arrays, Bitsets oder Rust-Strukturen
bleibt eine Implementierungs- und Benchmarkentscheidung.

### Entscheidungslokaler Zustand

Ein `DecisionWorkingSet` wird für einen konkreten Entscheidungszeitpunkt aus dem
Battle Working Set abgeleitet. Es darf enthalten:

```text
aktuell relevante Hypothesen
Top-K plus repräsentative Tail-Samples
aktuelle SafeSubmissionSet-Identität
enginefertige vollständige Welten
entscheidungslokale Damage- und Speed-Caches
Search-Konfiguration und Seed-Identitäten
```

Abgeschnittene Posterior-Masse darf nicht still verschwinden. Sie bleibt als
Tail-Masse, `OTHER`-Masse oder durch ein vorab spezifiziertes Samplingverfahren
repräsentiert.

## Lebenszyklus

```text
Rohdaten
  ↓ offline verarbeiten
versionierter Meta-Snapshot
  ↓ content-addressed veröffentlichen
Runtime validiert und öffnet Artefakt
  ↓ Battle startet
Battle bindet exakt einen Snapshot
  ↓ öffentliche Evidenz
BattleWorkingSet wird aktualisiert
  ↓ Entscheidung
DecisionWorkingSet wird deterministisch projiziert
  ↓
Belief und Search ohne SQL- oder Dateizugriff
```

Ein bereits laufender Battle bleibt für seine gesamte Lebensdauer an denselben
Snapshot gebunden. Die Veröffentlichung eines neuen Snapshots beeinflusst nur
neu gestartete Battles. Runtime-Handles müssen so lange leben wie jede daraus
abgeleitete semantische Sicht.

Content-addressed, unveränderliche Dateinamen vermeiden insbesondere auf
Windows den Austausch oder das Löschen eines noch gemappten Artefakts:

```text
meta-snapshot-<sha256>.artifact
```

## Kandidaten für spätere normative Festschreibung

Die folgenden Regeln sollten vor der produktiven M3-Implementierung in den
zuständigen versionierten Contracts beziehungsweise Manifesten festgeschrieben
werden. Dieses Architekturpapier nimmt diese Contract-Änderung nicht vor.

- Ein veröffentlichter Snapshot ist unveränderlich.
- Jede interne ID ist ausschließlich innerhalb ihres Snapshots gültig.
- Snapshot-, Ruleset-, Schema- und ID-Katalog-Digests werden mitgeführt.
- Ein Battle bleibt während seiner gesamten Laufzeit an denselben Snapshot
  gebunden.
- Neue Snapshots verändern bereits laufende Battles nicht.
- Die Projektion vom Snapshot zum Working Set ist deterministisch.
- Der Search-Hot-Path führt keine SQL- oder Dateisystemzugriffe aus.
- Abgeschnittene Posterior-Masse verschwindet nicht still.
- Offizielle Evaluationen aktualisieren globale Priors nicht während eines
  Battles oder zwischen Battles eines versiegelten Runs.

Normative Eigentümer bleiben insbesondere:

- [Splits, Leakage und Meta-Snapshot](../data/splits-and-meta-snapshot.md)
- [Belief- und Open-World-Vertrag](../contracts/belief-open-world.md)
- [Provenienzvertrag](../contracts/provenance.md)
- [Determinismusvertrag](../contracts/determinism.md)
- [Code- und Paketgrenzen](code-boundaries.md)

## Offene Technologieentscheidung

Das fachliche Design schreibt kein Runtime-Dateiformat vor. Mindestens diese
Varianten bleiben offen:

```text
read-only SQLite-Snapshot
Arrow-IPC-Snapshot
gepacktes Array-Artefakt
```

Arrow ist ein plausibler erster Kandidat, aber keine akzeptierte fachliche
Abhängigkeit. Memory Mapping, `float32`, Bitsets, Rust-Arenen, FlatBuffers und
ein eigenes Binärformat sind ebenfalls nicht festgelegt.

## Benchmark-Gate

Die Speichertechnik wird anhand eines reproduzierbaren Prototyps ausgewählt.
Der Vergleich misst mindestens:

```text
Cold Start
Warm Start
Team-Preview-Projektion
Evidenzfilterung
RAM pro Battle
RAM bei parallelen Prozessen
Python-Rust-Übergabe
Artefaktgröße
Windows-Datei- und Handle-Lebensdauer
Determinismus der Working-Set-Projektion
```

Zusätzlich müssen alle Kandidaten dieselben Snapshot-, Ruleset-, Schema- und
Katalogidentitäten validieren und dieselbe semantische Core-Sicht erzeugen.
Eine schnellere Variante ist nicht zulässig, wenn sie Provenienz,
Reproduzierbarkeit, Leakage-Schutz oder Plattformstabilität schwächt.

## Meilensteingrenze

### M2

M2 bleibt unverändert. Die Evaluation-only Closed-World-Verteilung ist ein
kleines, eingefrorenes Search-Artefakt und keine Implementierung dieser
produktiven Memory-Hierarchie.

### M3

M3 ist der erste sinnvolle Lieferzeitpunkt für:

```text
versionierten Meta-Snapshot
Runtime-Snapshot-Loader
battle-lokales Working Set
Open-World-Belief
entscheidungslokale Search-Projektion
```

Low-Level-Optimierungen folgen erst nach Profiling. Ein eigenes Binärformat,
manuelle SIMD-Kernel, GPU-Belief-Updates oder ein verteilter Meta-Store sind
keine M3-Voraussetzung.

## Forschungs- und Claim-Grenze

Die Memory-Hierarchie selbst ist etablierte Infrastruktur und kein
Neuheitsclaim. Der mögliche Forschungsbeitrag liegt in ihrer Verbindung mit:

```text
kohärenten vollständigen Set-Hypothesen
+ kalibriertem Open-World-OTHER
+ battle-lokalem Posterior
+ informationszustandsbasierter Search
+ leakage-freien Decision Records
```

## Nichtziele

Dieses Dokument:

- friert keine öffentliche Python- oder Rust-API ein;
- wählt weder Arrow noch SQLite als endgültiges Runtime-Format;
- erweitert M2 nicht;
- autorisiert kein Cross-Battle-Lernen während offizieller Evaluationen;
- erlaubt keine SQL-Abfrage in einer Search-Simulation;
- erzeugt keinen Performance-, Strength- oder Neuheitsclaim.

## Zugehörige Dokumente

- [Systemüberblick](overview.md)
- [Code- und Paketgrenzen](code-boundaries.md)
- [Splits, Leakage und Meta-Snapshot](../data/splits-and-meta-snapshot.md)
- [Belief- und Open-World-Vertrag](../contracts/belief-open-world.md)
- [Forschungsstrategie](../roadmap/research-strategy-and-experiments.md)
- [Projektroadmap](../roadmap/milestones.md)
