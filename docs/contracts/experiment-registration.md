---
document_id: experiment-registration
title: Experimentregistrierung und Artefaktbindungen
document_type: contract
status: accepted
normative: true
version: 5
applies_to:
  - research
  - evaluation
  - manifests
effective_from: 2026-08-03
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-03
---

# Experimentregistrierung und Artefaktbindungen

## Unveränderliche Artefakte

Eine Experimentregistrierung wird vor der Auswertung eingefroren. Sie enthält
Hypothesen, Nullhypothesen, registrierte Arme, Vergleichsreihenfolge,
Metrik- und Contractverweise, Budgets, Poolzugriff sowie Stop-/Pivotregeln.
Ihre kanonische Struktur ist in
[`experiment-registration.schema.json`](../../schemas/manifests/experiment-registration.schema.json)
definiert.

Eine Arm-Implementierungsbindung versiegelt später die konkrete Implementierung
eines registrierten Arms. Eine Evaluationslauf-Bindung versiegelt zusätzlich
Schedule, Seeds, Budgets, Pools oder synthetische Fixtures und die
Laufumgebung. Keine dieser Dateien wird nach Ergebnissichtung passend verändert;
eine Änderung erzeugt ein neues versioniertes Artefakt mit Verweis auf den
Vorgänger.

Jedes dieser drei Artefakte trägt `artifact_version` und
`supersedes_digest`. Die erste Version hat `artifact_version: 1` und keinen
Vorgänger. Ein Nachfolger muss denselben Artefakttyp und dieselbe Identität
besitzen, einen auflösbaren Vorgängerdigest referenzieren und eine höhere
Version tragen. Selbstreferenzen und Supersessionszyklen sind ungültig.

## Versionierte Registrierungsregeln

Die folgenden IDs sind die für M1.5 zulässigen, versionierten Regelreferenzen:

| Reference field | Allowed ID | Normative meaning |
|---|---|---|
| `construction_rule_id` | `registered_pool_construction_v1` | Constructs disjoint registered evaluation pools. |
| `near_duplicate_rule_id` | `canonical_exact_team_cluster_v1` | Groups semantically identical complete teams by canonical representation. |
| `side_assignment_rule_id` | `alternating_balanced_sides_v1` | Assigns sides deterministically and balances even repetitions. |
| `schedule_rule_id` | `registered_schedule_v1` | Produces schedule rows from the frozen matchup, seed, and side order. |
| `tie_break_rule_id` | `prefer_lower_runtime_v1` | Resolves a registered tie in favor of the lower runtime. |
| `stop_rule_id` | `no_effect_stop_v1` | Stops a comparison at the preregistered null-effect criterion. |
| `pivot_rule_id` | `uncertain_effect_pivot_v1` | Routes an uncertain effect through the preregistered pivot path. |

Eine Registrierung darf keine freie oder unbekannte Regel-ID verwenden. Diese
versionierte Tabelle ist der normative Eigentümer der zulässigen IDs und ihrer
Minimalbedeutung; spezialisierte Verträge dürfen die Verfahren operationalisieren,
aber keine abweichende Identität einführen.

## Komponentenstatus

Jede Komponente einer Implementierungsbindung besitzt genau einen Status:

- `not_applicable`: Der Arm verwendet diese Komponente grundsätzlich nicht.
- `unbound`: Die Komponente ist für einen späteren Lauf relevant, aber in dieser
  Bindung noch nicht festgelegt.
- `bound`: Die Komponente besitzt einen validierten Artefaktdigest.

`null`, freie Platzhalter und leere Digests sind keine Ersatzwerte für diese
Status.

## Holdout-Schutz

Registrierungen halten `selection`, `power_pilot` und `release_holdout` bis zu
den jeweils akzeptierten Freigabekriterien geschlossen. Ein synthetischer
Acceptance-Lauf verwendet ausschließlich deklarierte Fixture-Manifeste und
öffnet oder simuliert keinen Evaluationspool.

Schema-Version 2 aktiviert nur synthetische Acceptance-Bindings. Evaluation-
Bindings bleiben geschlossen, solange keine auflösbaren Poolartefakte und
Poolrollen existieren; ein solcher Lauf darf keinen geschützten Pool nur über
einen freien Digest öffnen.

## Validierung und Supersession

JSON Schema definiert die lokale Struktur. Der gemeinsame Validator prüft
zusätzlich Duplikate, Referenzen, Registrierungsdigests, Arm- und
Vergleichsidentitäten sowie die Konsistenz der Bindungen. Die Reihenfolge ist:

```text
striktes JSON-Laden
→ Schema-Validierung
→ semantische Invarianten
→ Referenzauflösung
→ Canonicalization
→ Digestvergleich
```

Die normative Canonicalization steht in
[`contract-manifest-schemas`](manifest-schemas.md); diese Datei definiert keine
zweite Digest-Spezifikation.
