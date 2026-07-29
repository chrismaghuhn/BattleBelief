---
document_id: evaluation-target-population
title: Zielpopulation und Metagame-Gewichtung
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - gen9ou
  - evaluation
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Zielpopulation und Metagame-Gewichtung

## Estimand-Bedeutung

Die interne Zielgröße verwendet eine **metagame-weighted proxy
distribution**. Sie ist eine vorregistrierte, ladder-inspirierte Verteilung
vollständiger Gegnerteams und Gegnerpolicies. Sie ist keine Behauptung über die
tatsächliche Winrate gegen alle Ladder-Spieler.

Smogon-Usage-Statistiken liefern Pokémon- und Moveset-Häufigkeiten, aber nicht
automatisch eine Verteilung vollständiger Teams oder menschlicher
Spielstrategien. Jede Ableitung von Archetyp- oder Teamgewichten ist deshalb
eine explizite Modellierungsentscheidung.

## Erforderlicher Snapshot

Vor Öffnung des Selection Pools werden festgelegt:

```text
format
date_window
rating_or_glicko_band
replay_source
replay_deduplication
complete_team_corpus_digest
team_archetype_classifier_version
near_duplicate_team_rule
archetype_weights
opponent_policy_mixture
weight_normalization
```

## Team- und Policy-Mischung

- Gegnerteams sind vollständig und vor Battlebeginn versiegelt.
- Teamgewichte und Gegnerpolicy-Gewichte werden getrennt modelliert.
- Dieselbe Teamliste darf mit mehreren vorregistrierten Policies auftreten.
- Gegnerteam, Gegnerpolicy-Checkpoint, Seitenzuweisung und Scheduleblock sind
  Bestandteile der Matchup-Identität.
- Near-Duplicate-Teams werden nach einer vorregistrierten Regel gruppiert.
- Gewichte werden vor Evaluation normalisiert und gehasht.

## Gültigkeitsfenster

Eine Meta-, Ruleset- oder wesentliche Policy-Verteilungsänderung überschreibt
keinen bestehenden Snapshot. Sie erzeugt eine neue Zielpopulation und einen
neuen Claim-Zyklus nach
[`contract-provenance`](../contracts/provenance.md).
