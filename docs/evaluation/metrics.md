---
document_id: evaluation-metrics
title: Forschungs- und Betriebsmetriken
document_type: contract
status: accepted
normative: true
version: 4
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

## Maschinenlesbare Metrik-IDs und Definitionen

Registrierungen referenzieren die folgenden stabilen IDs; die Bedeutung der
Metriken bleibt in den Abschnitten dieses Contracts:

| ID | Rolle |
|---|---|
| `decision_regret_teacher_v1` | primärer Decision-Regret |
| `teacher_top1_agreement_v1` | Teacher-Agreement-Diagnostik |
| `battle_outcome_weighted_v1` | gewichtetes Battle-Ergebnis |
| `end_to_end_latency_ms_v1` | End-to-End-Latenzverteilung |
| `fallback_rate_v1` | Fallback-Rate |

### Feste Berechnung, Nenner und Richtung

| ID | Berechnung und Nenner | Richtung | Zulässige Rollen |
|---|---|---|---|
| `decision_regret_teacher_v1` | Teacher-Wert minus ausgewählter Wert je vergleichbarer legaler Entscheidung; Mittelwert über den registrierten Zielpopulations-Nenner | niedriger ist besser | primary, secondary |
| `teacher_top1_agreement_v1` | Anteil vergleichbarer Entscheidungen mit derselben Top-1-Aktion wie der vorregistrierte Teacher | höher ist besser | secondary, diagnostic |
| `battle_outcome_weighted_v1` | Zielpopulationsgewichteter Mittelwert mit Win=1, Tie=0.5 und Loss=0; technische Klassen bleiben sichtbar | höher ist besser | primary, secondary |
| `end_to_end_latency_ms_v1` | Millisekunden vom akzeptierten frischen Request bis zum erfolgreichen Wire-Dispatch, als Verteilung | niedriger ist besser | diagnostic |
| `fallback_rate_v1` | Klassifizierte Fallback-Entscheidungen geteilt durch frische Requests mit erreichter Policy-Auswahl | niedriger ist besser | diagnostic |

Die Nenner umfassen keine still verworfenen Fehler- oder Timeoutfälle. Jeder
technische Ausgang wird mit seiner Fehlerklasse berichtet; ein Vergleich darf
ihn nur nach dem referenzierten technischen Behandlungsschema aggregieren.
Die Metrikversion ist Teil der Registrierungsreferenz und darf nach Öffnung
eines Vergleichs nicht passend zu einem Ergebnis geändert werden.
