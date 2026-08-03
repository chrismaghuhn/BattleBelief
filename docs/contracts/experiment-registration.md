---
document_id: experiment-registration
title: Experimentregistrierung und Artefaktbindungen
document_type: contract
status: accepted
normative: true
version: 1
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
