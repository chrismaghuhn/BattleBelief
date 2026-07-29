---
document_id: evaluation-m5-strength-qualification
title: M5 Strength Qualification
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - gen9ou
  - release
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# M5 Strength Qualification

Nur ein bestandener M5-Release heißt MVP.

## Primärer Estimand

Die Bedeutung der metagame-gewichteten Proxy-Winrate und ihrer
Gegnerteam-/Policy-Verteilung steht in
[`evaluation-target-population`](target-population.md). Die Analyse folgt
[`evaluation-statistical-analysis`](statistical-analysis.md).

## Primäres Gate

```text
planning point estimate >= 72%
one-sided 95% cluster-CI lower bound >= 70%
```

Die bindende Bedingung ist die Cluster-Untergrenze. Die Battle- und
Clusterzahl stammt aus dem Power Pilot.

## Welche Battles zählen

Alle planmäßig gestarteten und regelkonform beendeten Battles zählen,
einschließlich Battles und Entscheidungen mit Fallback.

```text
bot_timeout / bot_crash / invalid_action:
  loss

independent oracle or infrastructure failure:
  void only under preregistered arm-blind definition

void:
  reschedule through precommitted replacement schedule
```

Search-Coverage, Fallbackgrund und Winrate mit oder ohne Fallback werden nur
diagnostisch berichtet.

## Robustheitsguardrails

- kein Hero-Team-Punktschätzer unter 60 Prozent;
- keine vorregistrierte Gegnerarchetyp-Familie unter 55 Prozent;
- unterstes Dezil vorregistrierter Matchup-Familien mindestens 50 Prozent;
- Mindestclusterzahl und Intervall für jede Subgruppe;
- Unterbesetzung bedeutet nicht bestanden.

## Safety und Laufzeit

- p95-End-to-End-Entscheidungszeit höchstens zwei Sekunden;
- harter Abbruch vor fünf Sekunden;
- Fallback-Entscheidungsrate unter 0,1 Prozent;
- vollständige Team-, Modell-, Search-, Engine- und Datenprovenienz.

Zusätzlich müssen die Evidenzgates aus
[`contract-protocol-state`](../contracts/protocol-state.md),
[`contract-legal-action-safety`](../contracts/legal-action-safety.md) und
[`contract-engine-capabilities`](../contracts/engine-capabilities.md) bestehen.
Ihre Null-Aussagen gelten nur im dort definierten Evidenzraum und behaupten
keine globale Fehlerfreiheit.

## Claim

Der Claim folgt
[`contract-provenance`](../contracts/provenance.md) und validiert gegen das
Evaluation-Claim-Schema. Fallback-Battles bleiben im Primärergebnis.
