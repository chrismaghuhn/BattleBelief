---
document_id: operation-release-evaluation
title: Durchführung einer Release-Evaluation
document_type: operation
status: accepted
normative: true
version: 1
applies_to:
  - release
  - evaluation
  - gen9ou
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Durchführung einer Release-Evaluation

Dieses Runbook operationalisiert die Contracts, verändert aber keine ihrer
Schwellen oder Bedeutungen.

## 1. Kandidat versiegeln

- Selection Pool nach
  [`training-pipeline-and-selection`](../training/pipeline-and-selection.md)
  auswerten.
- Genau einen Kandidaten auswählen.
- Code, Pakete, Teams, Modell, Search, Engine, Priors und Fallbackpolicy
  hashen.
- Danach keine Gewichte, Parameter, Teamrotation oder Heuristiken ändern.

## 2. Ziel und Ruleset versiegeln

- Zielpopulation nach
  [`evaluation-target-population`](../evaluation/target-population.md)
  manifestieren.
- Ruleset-Snapshot gegen das reale Schema validieren.
- Gegnerteams, Gegnerpolicies, Seiten- und Seed-Schedule hashen.
- Development-, Selection-, Pilot- und Holdout-Trennung nach
  [`evaluation-pool-separation`](../evaluation/pool-separation.md) prüfen.

## 3. Power Pilot

- Nur den versiegelten Kandidaten verwenden.
- Varianz, Clusterabhängigkeit, technische Raten und Tail-Latenz schätzen.
- Stichprobenplan mit dem Verfahren aus
  [`evaluation-statistical-analysis`](../evaluation/statistical-analysis.md)
  festschreiben.
- Release-Holdout weiterhin ungeöffnet lassen.

## 4. Präregistrieren

Vor dem ersten Holdout-Battle werden veröffentlicht oder unveränderlich
gespeichert:

- Claim- und Ruleset-Manifeste;
- Zielpopulation und Analyseprotokoll;
- primärer Schedule und Ersatzschedule;
- Fehler-, Loss- und Void-Regeln;
- Subgruppendefinitionen und Mindestcluster;
- alle Artefaktdigests;
- Search-Modus und Referenzumgebung.

## 5. Holdout ausführen

- Exakt den präregistrierten Schedule abarbeiten.
- Keine manuelle Battle-Intervention.
- Jede Decision Row und jedes Battle klassifiziert protokollieren.
- Botfehler gemäß M5-Vertrag als Loss zählen.
- Unabhängige Infrastrukturfehler nur nach der vorregistrierten,
  ergebnisblinden Regel voiden und über den festen Ersatzschedule nachholen.
- Fallback-Battles im Primärergebnis belassen.

## 6. Analysieren und claimen

- Eine präregistrierte Hauptanalyse ausführen.
- Ergebnis gegen
  [`evaluation-m5-strength-qualification`](../evaluation/m5-strength-qualification.md)
  entscheiden.
- Claim-Manifest gegen
  [`evaluation-claim.schema.json`](../../schemas/manifests/evaluation-claim.schema.json)
  validieren und kanonisch hashen.
- Ergebnis unabhängig von `pass` oder `fail` vollständig berichten.
- Nur ein bestandenes Ergebnis darf einen M5-/MVP-Claim tragen.

## 7. Release und Tag

- Claim-Manifest vor Tag-Erzeugung auf `main` integrieren.
- Archivhash, Schemas, Digests und Attestations prüfen.
- Geschützten `eval-*`, `claim-*` oder `v*`-Tag über den autorisierten
  Releaseprozess erzeugen.
- Ruleset- oder Metaänderungen erzeugen einen neuen Zyklus; alte Claims werden
  nicht umgeschrieben.
