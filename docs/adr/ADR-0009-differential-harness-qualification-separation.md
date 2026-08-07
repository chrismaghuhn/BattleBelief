---
document_id: adr-0009-differential-harness-qualification-separation
title: "ADR-0009: Differential-Harness- und Qualification-Trennung"
document_type: adr
status: accepted
normative: false
version: 1
applies_to:
  - evaluation
  - lab
  - gen9ou
effective_from: 2026-08-07
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-07
---

# ADR-0009: Differential-Harness- und Qualification-Trennung

## Kontext

Task 28 und Task 29 müssen eine harte Preregistration-Grenze bilden. Würden
Runner, Schemas, Classifier oder Corpus noch geändert, nachdem echte Showdown-
versus-`poke-engine`-Divergenzen sichtbar sind, könnten Vergleichs- und
Classification-Regeln unbewusst an die Ergebnisse angepasst werden.

Der M2-Plan beschreibt unter MD-20 drei Optionen, ist selbst jedoch
`status: proposed` und `normative: false` und besitzt keine
Entscheidungsautorität.

## Erwogene Optionen

### Option A – synthetic-only Harness-Freeze, danach data-only Qualification

Task 28 implementiert und friert Runner, Schemas, Classifier, Corpus und Golden-
Verhalten ausschließlich mit synthetischen/goldenen Fällen ein. Erst nach dem
Merge führt Task 29 die reale Matrix aus und verändert nur Daten-/Evidence-
Artefakte.

### Option B – Harness und Qualification in einem PR

Runner und reale Claims entstehen gemeinsam. Das reduziert PR-Anzahl, erlaubt
aber Änderungen an Vergleichsregeln, nachdem reale Divergenzen bereits sichtbar
sind.

### Option C – keine Qualification in M2

Alle Capabilities bleiben unknown. Das ist maximal konservativ, verhindert
aber den vorgesehenen engine-qualified Search-Prototyp.

## Entscheidung

Die Maintainer-Auswahl ist **Option A**. Die ausdrückliche Maintainer-Freigabe
wurde am 2026-08-07 erteilt; ADR-0009 ist damit akzeptiert. `normative: false`
bleibt bestehen.

### Task 28

Task 28 darf ausschließlich mit synthetischen/goldenen Doubles und Daten:

- Differential-Schemas erstellen und validieren;
- Corpus-v1 und dessen Fixture-Closure erstellen und einfrieren;
- Canonical-Mechanics-Observation und Vergleichsregeln implementieren;
- Runner und Classifier implementieren;
- Known-Divergence-Definitionen vorab binden;
- Evidence-Regeln implementieren und mit synthetischen incomplete/failure-
  Fällen beweisen, dass daraus keine `exact`-Claims entstehen;
- CI-/Package-Smokes für die synthetische/goldene Harness-Semantik ergänzen.

Task 28 darf **keinen realen Showdown-versus-`poke-engine`-Qualification-Run**
ausführen, weder lokal als Qualification-Evidence noch in normaler PR-CI.

Task 28 erzeugt keine reale Capability-Elevation und keine `exact`- oder
`bounded_approximation`-Claims.

### Task 29

Task 29 startet erst nach Merge von Task 28 und verwendet ausschließlich die
bereits gemergten, content-addressed Task-28-Bytes.

Der Task-29-PR ist data/evidence-only. Er darf insbesondere keine Änderungen an
folgenden Task-28-Grenzen enthalten:

- Python-Runner- oder Classifier-Code;
- Schemas oder deren Classification-Semantik;
- Corpus-v1-Index oder Fixtures;
- Known-Divergence-Regeln;
- Capability-Taxonomie;
- Normalisierungs- oder Vergleichsregeln.

Alle realen ersten Versuche, technische Fehlschläge, Timeouts, Crashes,
unclassified divergences und ausdrücklich autorisierte Retries bleiben in der
Run-Evidenz erhalten und werden nicht zugunsten günstiger Resultate ersetzt.

### Defekt nach dem Freeze

Wird durch Task 29 ein echter Defekt oder eine unzureichende Task-28-Regel
sichtbar, wird der laufende Qualification-Versuch nicht durch einen In-Run-Fix
repariert.

Stattdessen:

1. der betroffene Run bleibt failed/invalid oder nicht-exact;
2. ein separater Nachfolge-PR ändert Harness/Classifier/Schema oder erzeugt eine
   neue Corpus-Version;
3. danach wird eine neue Qualification-Version vollständig neu ausgeführt.

## Konsequenzen

Positiv:

- Reale Mechanics-Ergebnisse können die Bewertungsregeln nicht nachträglich
  beeinflussen.
- Task 29 bleibt auditierbar als reine Daten-/Evidence-Transformation.
- Unfavorable Ergebnisse bleiben sichtbar und reproduzierbar.

Kosten und Risiken:

- Ein Harness-Defekt erfordert einen neuen Review-/Run-Zyklus.
- Corpus-/Classifier-Versionen können nicht bequem in-place korrigiert werden.
- Die strikte Serialisierung verlängert den M2-Ablauf bewusst zugunsten der
  Evidenzintegrität.

## Nicht autorisiert

Dieser ADR autorisiert keine:

- reale Task-29-Qualification vor Merge von Task 28;
- Capability-Elevation in Task 28;
- Search, Eligibility oder Closed-World-Distribution;
- Änderung von Task-27 Runtime-Mapping oder Task-24 Oracle-Semantik;
- Strength-, Release- oder Parity-Claims.

MD-20 Option A is approved by the Maintainer.
