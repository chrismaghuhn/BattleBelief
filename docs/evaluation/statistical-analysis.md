---
document_id: evaluation-statistical-analysis
title: Statistischer Analysevertrag
document_type: contract
status: accepted
normative: true
version: 4
applies_to:
  - evaluation
  - gen9ou
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Statistischer Analysevertrag

## Primäre Analyse

Der primäre Schätzer verwendet die Gewichte aus
[`evaluation-target-population`](target-population.md). Vor Öffnung des
Release-Holdouts werden Schätzer, Cluster-Einheit, Bootstrap-Verfahren,
Konfidenzniveau, Seitenblöcke und Behandlung technischer Ergebnisse
festgeschrieben.

Ein Matchup-Block enthält mindestens:

```text
hero_team
opponent_team
opponent_archetype
opponent_policy_checkpoint
side_assignment
schedule_block
seed_family
```

Die rohe Battle-Anzahl ist nicht die effektive Stichprobengröße.

## Power-Simulation

Die Simulation bildet den späteren Ablauf und Schätzer vollständig nach:

- Cluster und variable Clustergrößen;
- Paarung und Seitenzuweisung;
- gemessene Intracluster-Korrelation;
- Fallbacks, Timeouts und Voids;
- identischen gewichteten Schätzer und Cluster-Bootstrap;
- einseitige Konfidenzgrenze;
- Releaseentscheidung und Sensitivitätsgitter;
- Monte-Carlo-Fehler.

Die endgültige Battle- und Clusterzahl stammt aus dieser Simulation, nicht aus
einer pauschalen Annahme unabhängiger Battles.

## Subgruppen

M5 verwendet vorregistrierte Punktwert-Guardrails. Jede Subgruppe benötigt:

- feste Definition und Nenner;
- per Präzisions- oder Power-Simulation bestimmte Mindestzahl unabhängiger
  Cluster;
- berichtetes Intervall;
- Ergebnis `nicht bestanden`, wenn sie unterbesetzt ist.

Formale Subgruppenclaims benötigen eigene Konfidenzgrenzen,
Interaktionstests und Multiplizitätskontrolle.

## Seeds

Die statistische Bedeutung gleicher Seeds folgt
[`contract-determinism`](../contracts/determinism.md). Ein gleicher Seed allein
rechtfertigt keine gepaarte kausale Analyse.

## Maschinenlesbare Analyse-IDs und feste Prozeduren

| Referenzfeld | ID | Bedeutung |
|---|---|---|
| `analysis_procedure_id` | `weighted_cluster_bootstrap_v1` | Resampling ganzer registrierter Matchup-Cluster mit Zielpopulationsgewichten; Cluster werden nicht in einzelne Battles aufgeteilt |
| `estimand_id` | `paired_mean_difference_v1` | Arithmetischer Mittelwert der zeilenweise definierten rechten minus linken Armwerte innerhalb der vorregistrierten Vergleichspaare |
| `technical_outcome_treatment_id` | `technical_outcomes_full_v1` | Win, Loss, Tie, Void, Timeout, Disconnect, Invalid, Fallback und sonstige technische Klassen bleiben getrennt sichtbar; keine Klasse wird still entfernt |
