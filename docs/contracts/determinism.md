---
document_id: contract-determinism
title: Determinismus- und Reproduzierbarkeitsvertrag
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - search
  - training
  - evaluation
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Determinismus- und Reproduzierbarkeitsvertrag

## Zwei Betriebsmodi

| Modus | Abbruch | Zweck | Reproduzierbarkeit |
|---|---|---|---|
| `deterministic_benchmark` | feste Zahl von Simulationen, Transitionen oder Knoten | Teacher, Holdout, Ablationen | unter der Referenzumgebung aktionsidentisch und zeilenstabil |
| `live_anytime` | manifestiertes Wandzeitbudget | öffentliche Nutzung | statistisch, nicht bit- oder aktionsidentisch |

Teacher-Daten und bindende Search-Ablationen werden ausschließlich im
`deterministic_benchmark` erzeugt. Eine wandzeitbasierte Suche darf keine
Teacher-Targets produzieren.

## Deterministic Benchmark

Der erste freigegebene Referenzpfad ist single-threaded. Ein paralleler Pfad
darf erst als deterministisch bezeichnet werden, wenn feste Work-Zuweisung,
workerlokale Seeds und eine stabile Reduktionsreihenfolge durch Contract-Tests
nachgewiesen sind.

Gleiche Resultate setzen dieselben manifestierten Eingaben voraus:

- kanonischer Observed State und Belief-Snapshot;
- Aktionsreihenfolge;
- Algorithmus- und Contract-Version;
- Budgettyp und Budgetwert;
- Search-, Welt-, Policy- und Simulatorseeds;
- Workerzahl und Parallelmodus;
- Engine-, Modell- und Prior-Digests;
- Runtime-, Bibliotheks- und Hardwareprofil.

Ein Referenzlauf muss mindestens aktionsidentisch sein und identische
kanonische Decision Rows erzeugen. Float-Zwischenwerte außerhalb der
kanonischen Ausgabe dürfen innerhalb einer separat versionierten
Plattformtoleranz abweichen; eine solche Toleranz darf niemals nach Sichtung
eines Holdout-Ergebnisses erweitert werden.

## Live Anytime

Die Suche liefert zu jedem Abbruchzeitpunkt die beste bereits legal geprüfte
Aktion. CPU-Auslastung, Scheduling und Cacheverhalten können die Zahl
abgeschlossener Iterationen und damit die gewählte Aktion verändern.

Die konkrete Deadline und das Release-Gate gehören zum
[`evaluation-m5-strength-qualification`](../evaluation/m5-strength-qualification.md),
nicht zu diesem Reproduzierbarkeitsvertrag.

## Seed-Semantik

Gleiche Startseeds sind kontrollierte Wiederholungs-IDs. Sie garantieren nicht,
dass unterschiedliche Policies dieselben Zufallsereignisse erleben, weil
abweichende Aktionspfade unterschiedlich viele PRNG-Aufrufe verbrauchen können.
Search-, Welt-, Policy- und Simulatorzufall werden getrennt abgeleitet und
protokolliert.

Gepaarte statistische Auswertung ist nur zulässig, wenn die relevante
PRNG-Konsumstruktur nachweislich vergleichbar bleibt. Seitenzuweisung ist ein
eigener Blockfaktor.

## Manifest und Nachweis

Das Search-Manifest folgt
[`search-contract.schema.json`](../../schemas/manifests/search-contract.schema.json).
Jeder Lauf zeichnet Budgettyp, Budgetwert, Workerzahl, CPU-Modell, Seeds und
abgeschlossene Iterationen auf. Canonicalization und Hashbildung folgen
[`contract-manifest-schemas`](manifest-schemas.md).
