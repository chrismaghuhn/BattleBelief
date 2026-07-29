---
document_id: contract-belief-open-world
title: Belief- und Open-World-Vertrag
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - belief
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Belief- und Open-World-Vertrag

## Vollständige Set-Hypothesen

```text
SetHypothesis:
  set_hash
  snapshot_id
  species
  ability
  item
  moves
  nature
  evs_or_feasible_region
  tera_type
  source_kind
  evidence_kind
  visibility
  weight
  uncertainty
```

Moves, Item, Ability, Spread und Tera werden nicht aus unabhängigen Marginalen
zu künstlichen Sets kombiniert.

## Evidenz

```text
evidence_kind:
  directly_observed
  mechanically_inferred
  dataset_imputed
  curated
  simulated

visibility:
  complete
  censored
  unknown
```

Imputierte Daten sind keine Ground Truth. Nicht revealed ist keine beobachtete
Abwesenheit.

## Open World

Ein abstrakter `OTHER`-Bucket besitzt von Initialisierung an kleine, auf dem
Development Pool kalibrierte positive Masse. Bekannte Hypothesen werden auf
`1 - epsilon` normiert.

Konkrete unbekannte Hypothesen werden lazy materialisiert, wenn:

- harte Evidenz alle gespeicherten Sets ausschließt;
- `OTHER`-Masse steigt;
- die effektive Hypothesenzahl kollabiert.

Verboten:

- unvereinbare Hypothese behalten;
- leere Verteilung normalisieren;
- still häufigstes Set einsetzen;
- Open-World-Ereignis nicht protokollieren.

## Späteres Cross-Battle-Gegnermemory

Cross-Battle-Gegnerprofile sind kein MVP-Bestandteil. Eine spätere Version:

- pseudonymisiert Gegnerkennungen;
- besitzt eine dokumentierte Aufbewahrungs- und Löschregel;
- verwendet Mindestbeobachtungen und Shrinkage zum Meta-Prior;
- konditioniert Stilmerkmale auf die jeweilige Spielsituation;
- wird im offiziellen Holdout deaktiviert oder als eigene
  Evaluationsbedingung ausgewiesen;
- liefert ausschließlich Priors und niemals direkte Aktionen.

Während einer offiziellen Evaluation werden Profile weder aktualisiert noch
zwischen Battles still weitergereicht.

## Metriken

Metrikdefinitionen und die Trennung vollständiger von zensierter Ground Truth
stehen ausschließlich in
[`evaluation-metrics`](../evaluation/metrics.md).
