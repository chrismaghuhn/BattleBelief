---
document_id: evaluation-metrics
title: Forschungs- und Betriebsmetriken
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - research
  - evaluation
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Forschungs- und Betriebsmetriken

Öffentliche Nutzung priorisiert regelkonform beendete Battles und Siege.
Forschung benötigt zusätzlich Messungen der Entscheidungsqualität unter
unvollständiger Information. Keine einzelne Metrik ersetzt die andere.

## Belief

Primär:

- Set-NLL auf vollständig bekannter Ground Truth.

Guardrails und Diagnostik:

- Brier Score;
- Reliability/Calibration Error;
- Top-k-Coverage des tatsächlichen Sets;
- Open-World-Rate und Posterior-Kollapsrate;
- eventbasierte Reveal-Likelihood auf zensierten Human-Replays.

Rekonstruierte oder imputierte Gegnersets gelten nicht als beobachtete Ground
Truth. Vollständige Set-NLL wird nur auf synthetischen oder tatsächlich
vollständig bekannten Fällen berechnet.

## Decision Quality

- Regret gegenüber einem vorregistrierten Search Teacher;
- Top-k-Agreement und Rank Correlation mit Teacher-Aktionen;
- Policy-Entropy und Sensitivität gegenüber plausiblen Hidden Worlds;
- Value-Calibration gegen realisierte Outcomes;
- Verbesserung gegenüber Legal-, Heuristik- und Search-only-Baselines.

Teacher-Qualität wird über unabhängige Ablationen geprüft; Teacher-Agreement
allein ist kein Strength-Claim.

## Engine

- Capability-Kategorie pro Entscheidung;
- Search-Coverage pro Entscheidung und Battle;
- klassifizierte Divergenzen im Differential-Corpus;
- Transitionen, CPU-Zeit und Speicher pro Entscheidung;
- Runtime-Fallbackgrund.

`exact` bedeutet nur „innerhalb des manifestierten
Anwendungsprädikats geprüft“, nicht globale Vollständigkeit.

## Protocol und Betrieb

- unbekannte state-bearing Events im versionierten Evidenzraum;
- Parser- und Reducerfehler;
- Reconciliation-Mismatches;
- stale-`rqid`-Submissions;
- serverseitig zurückgewiesene Aktionen;
- Timeouts, Crashes, Disconnects und Voids nach Fehlerklasse;
- End-to-End-, Search- und Inferenzlatenz als Verteilungen.

Die konkreten M5-Schwellen stehen ausschließlich in
[`evaluation-m5-strength-qualification`](m5-strength-qualification.md).
