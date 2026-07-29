---
document_id: training-pipeline-and-selection
title: Training und Kandidatenauswahl
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - training
  - gen9ou
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Training und Kandidatenauswahl

## Reihenfolge

1. Human-Replays als Bootstrap;
2. deterministischer Search Teacher;
3. diverse Population Self-Play;
4. optional Policy-Prior und Value-Modell;
5. Pflichtablation gegen Heuristik-, Search- und Model-only.

Lokale GPU und Kaggle dienen ausschließlich Offline-Training. Öffentliche
Runtime benötigt keine GPU.

## Keine Onlineänderung

Während offizieller Evaluation ändern sich weder:

- Modellgewichte;
- Heuristikskalare;
- Meta-Priors;
- Gegnerprofile;
- Teamrotation;
- Searchparameter.

Decision Traces dürfen offline Diagnose- und Trainingsfälle erzeugen.
Teacher-Regret ist eine modellabhängige Gegenfaktualschätzung, kein wahres
Spielregret.

## Kandidatenwege

### Strength-Superiority

```text
lower one-sided cluster-CI bound(Hybrid - SearchOnly) > 0
```

Zusätzlich bleiben Safety- und Latenzgates bestanden.

### Efficiency-Noninferiority

```text
lower one-sided cluster-CI bound(Hybrid - SearchOnly) > -0.01

upper one-sided cluster-bootstrap CI bound(
  p95_walltime_hybrid / p95_walltime_search_only
) < 0.80
```

Primär ist p95-End-to-End-Wandzeit pro Entscheidung auf fester Hardware und mit
identischen Parallelitätsgrenzen. Timeouts bleiben enthalten.

Sekundär werden CPU-Core-Sekunden, GPU-Sekunden, Transitionen, Simulationen,
Modellaufrufe, RAM, Timeout- und Fallbackrate berichtet.

Kandidatenzahl, Versiegelung und Öffnungsreihenfolge folgen ausschließlich
[`evaluation-pool-separation`](../evaluation/pool-separation.md).
