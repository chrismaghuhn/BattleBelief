---
document_id: data-splits-and-meta-snapshot
title: Splits, Leakage und Meta-Snapshot
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - data
  - gen9ou
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Splits, Leakage und Meta-Snapshot

## Splitregeln

- beide POV-Dateien desselben Battles im selben Split;
- chronologische ganze Zeitblöcke;
- zusätzlicher spielerdisjunkter Generalisierungstest;
- Replay-ID-Dedup;
- exakte Teamhash-Dedup;
- Near-Duplicate-Team-Erkennung;
- Teamstatistiken nur auf Training fitten und anschließend einfrieren;
- end-of-battle bekannte Daten niemals als frühere Features;
- Imputation niemals als beobachtete Wahrheit;
- Elo nur für Stratifizierung und Reporting.

Development-, Selection-, Power- und Releaseartefakte sind auch auf Ebene
unabhängiger Teams, Replaylinien, Gegner, Policies und Seedcluster getrennt.

## Speicherarchitektur

```text
Replays / Self-Play / kuratierte Quellen
→ Parquet
→ DuckDB
→ versionierter Meta-Snapshot
→ read-only SQLite-Runtime-Artefakt
→ MetaPriorProvider
→ MetaPriorSnapshot im RAM
```

Search führt keine SQL-Abfragen aus.

## Relationale Kernfelder

IDs, Snapshot, Species, Set-Hash, Quelle, Gewicht, Evidenzstatus und häufig
abgefragte Attribute werden normalisiert und indexiert. JSON bleibt für
erweiterbare Rohpayloads, nicht als Ersatz für Schlüssel und Constraints.

## Zielpopulation

Die Ableitung von Team- und Policy-Gewichten aus diesem Snapshot wird
ausschließlich in
[Zielpopulation und Metagame-Gewichtung](../evaluation/target-population.md)
definiert. Smogon-Marginalen bleiben Kalibrierungs- und Plausibilitätsquelle,
keine vollständige Teamverteilung.
