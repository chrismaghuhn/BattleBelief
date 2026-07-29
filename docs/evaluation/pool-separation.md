---
document_id: evaluation-pool-separation
title: Trennung der Evaluationspools
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - evaluation
  - gen9ou
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Trennung der Evaluationspools

## Development Pool

Training, Debugging, Feature-, Belief- und Hyperparameterentwicklung. Keine
Releaseevidenz.

## Selection Pool

Formale Wahl genau eines Kandidaten. Kandidatenzahl, Metriken und
Auswahlverfahren werden vor Öffnung festgelegt. Adaptive Wiederverwendung
verbraucht den Pool.

## Power Pilot

Erst mit versiegeltem Kandidaten. Er schätzt ausschließlich:

- Varianz und Intracluster-Korrelation;
- Clustergrößen;
- Fallback-, Timeout- und Void-Raten;
- Tail-Latenz;
- notwendige Clusterzahl.

Der Pilot wählt keinen Kandidaten, bestimmt keine Marge und verwendet keine
Release-Holdout-Elemente.

## Release Holdout

- erst nach Kandidat und Stichprobenplan öffnen;
- genau eine präregistrierte Hauptauswertung;
- keine nachträgliche Architektur-, Kandidaten- oder Schwellenänderung;
- nach Öffnung für die nächste Releaseentscheidung verbraucht.

Physische Dateitrennung genügt nicht. Teams, Replays, Gegneridentitäten,
Policies, Near-Duplicate-Gruppen und Seedcluster müssen logisch getrennt sein.
Der finale Holdout darf weder für Entwicklung, Kandidatenauswahl noch
Power-Pilot verwendet werden.
