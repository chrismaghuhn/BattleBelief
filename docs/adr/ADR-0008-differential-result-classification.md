---
document_id: adr-0008-differential-result-classification
title: "ADR-0008: Differential-Result-Klassifikation v1"
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

# ADR-0008: Differential-Result-Klassifikation v1

## Kontext

Task 28 muss Result- und Divergenzsemantik vor dem ersten realen Differential-
Run einfrieren. Der M2-Plan empfiehlt in MD-14 eine stabile versionierte
öffentliche Taxonomie mit privaten sanitisierten Diagnostics, legt für Task 28
aber noch keine konkreten Differential-Result-IDs autoritativ fest.

Die spätere Search-/Runtime-Fallback-Taxonomie und Decision-Record-Evolution
gehören weiterhin zu ihren eigenen späteren Tasks. Task 28 benötigt nur die
Klassifikation des Differential-Harness.

## Erwogene Optionen

### Option A – stabile öffentliche IDs plus private sanitisierten Diagnostics

Resultate verwenden eine kleine geschlossene Menge versionierter öffentlicher
Klassifikationen. Freitext, rohe Exceptions und Umgebungsdetails bleiben
außerhalb der öffentlichen Evidenz.

### Option B – Backend-Exceptions als Klassifikation

Native oder Oracle-Fehlertexte würden direkt erscheinen. Das ist instabil,
nicht reproduzierbar und kann Pfade, Hostnamen oder private Zustände leaken.

### Option C – eine generische Failure-Klasse

Alle technischen Fehlschläge würden gleich behandelt. Das ist kompakt, aber
für reproduzierbare Differential-Auswertung und spätere Evidence-Prüfung zu
wenig aussagekräftig.

## Entscheidung

Die Maintainer-Auswahl ist **Option A**. Die ausdrückliche Maintainer-Freigabe
wurde am 2026-08-07 erteilt; ADR-0008 ist damit akzeptiert. `normative: false`
bleibt bestehen.

Für Task 28 wird zusätzlich folgende **Differential-Result-Klassifikation v1**
freigegeben.

### `execution_status`

Zulässige Werte:

```text
completed
skipped
failed
```

### `divergence_class`

Zulässige Werte:

```text
match
known_divergence
unclassified
null
```

`null` ist nur zulässig, wenn `execution_status != completed`.

Ein abgeschlossenes Resultat besitzt genau eine der drei nicht-null
Divergenzklassen. Nur `match` ist ein Match. `known_divergence` und
`unclassified` sind ausdrücklich keine Matches.

### `failure_class`

Zulässige Werte:

```text
unavailable
artifact_mismatch
timeout
crash
malformed_output
mapping_failure
backend_error
null
```

### `failure_origin`

Zulässige Werte:

```text
oracle
engine
runtime_adapter
null
```

### Feldinvarianten

- `completed` verlangt `divergence_class` in
  `{match, known_divergence, unclassified}` und hat
  `failure_class = null`, `failure_origin = null`.
- `failed` verlangt `divergence_class = null`, eine nicht-null
  `failure_class` und eine nicht-null `failure_origin`.
- `skipped` verlangt `divergence_class = null`. Ein stabiler Skip-Grund darf
  über die freigegebenen Failure-Felder repräsentiert werden; falls kein
  technischer Failure-Grund vorliegt, sind beide Failure-Felder `null`.
- Ist `failure_class = null`, muss auch `failure_origin = null` sein.
- Ist `failure_class` nicht null, muss `failure_origin` nicht null sein.
- Timeout, Crash, malformed output, mapping failure, backend error,
  unavailable oder artifact mismatch dürfen niemals als `match`
  klassifiziert werden.

### Bekannte Divergenzen

`known_divergence` ist nur zulässig, wenn die betroffene Fixture bereits vor
dem ersten realen Task-29-Run an eine versionierte, stabile
`known_divergence_id` und die freigegebene Classification-Policy-Version
gebunden ist. Ein erstmals im realen Run beobachteter Unterschied ist
`unclassified`, nicht rückwirkend `known_divergence`.

Eine Umklassifizierung in derselben Corpus-/Classifier-Version ist verboten.
Sie benötigt eine separat reviewte Nachfolgeversion und anschließend einen
neuen Qualification-Run.

### Sanitization

Öffentliche Differential-Resultate und Reports enthalten keine:

- rohen Exceptions oder Tracebacks;
- absoluten lokalen Pfade oder Hostnamen;
- nativen State-Dumps;
- privaten Hidden-World-Inhalte;
- freien Failure-Text als Klassifikation.

Private Diagnostics dürfen intern existieren, autorisieren aber keine andere
öffentliche Klassifikation und sind nicht Teil einer Capability-Claim-
Entscheidung, sofern sie nicht durch eine separat genehmigte Evidence-Struktur
content-addressed gebunden werden.

## Abgrenzung zu Runtime-/Decision-Record-Fallbacks

Diese Entscheidung autorisiert **ausschließlich Task 28s Differential-Harness-
und Corpus-Freeze**. Sie ändert weder den bestehenden Decision-Record-Vertrag
noch dessen Fehlercode-Allowlist und definiert keine spätere öffentliche
Search-/Runtime-Fallback-Taxonomie.

Eine solche Evolution bleibt bei den dafür vorgesehenen späteren Maintainer-
Entscheidungen und Task 35/Runtime-Integrationsgrenzen.

## Nicht autorisiert

Dieser ADR autorisiert keine:

- reale Qualification;
- Capability-Status-Elevation;
- `exact`- oder `bounded_approximation`-Claims;
- Search-/Eligibility-/Runtime-Fallback-Evolution;
- Änderung bestehender Decision-Record-Schemas oder Contracts;
- Reclassification nach Sichtung realer Ergebnisse.

MD-14 Option A and the Task-28 differential result classification v1 are approved by the Maintainer.
