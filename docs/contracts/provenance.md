---
document_id: contract-provenance
title: Provenance-, Snapshot- und Claim-Vertrag
document_type: contract
status: accepted
normative: true
version: 3
applies_to:
  - release
  - evaluation
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Provenance-, Snapshot- und Claim-Vertrag

## Lokaler Showdown-Holdout

Ein lokaler Lauf zeichnet mindestens auf:

- Pokémon-Showdown-Git-SHA;
- Startseed;
- Formatdefinition und Banlist-Digest;
- Node-Version;
- vollständige Simulator-Inputs und -Outputs;
- Bot-, Search-, Engine-, Modell- und Team-Digests.

## Öffentliche Human- oder Ladder-Evaluation

Ein externer Lauf zeichnet mindestens auf:

- Replay- oder Battle-ID;
- UTC-Zeit;
- Formatname und sichtbare Regelmeldungen;
- vollständiges Clientprotokoll;
- Bot-, Modell-, Search- und Team-Digest;
- lokale Clientversion;
- Server-Deploy-Commit nur, wenn er tatsächlich verfügbar ist.

Ein interner Serverseed oder unbekannter Deploy-Commit darf nicht erfunden oder
als vorhanden vorausgesetzt werden.

## Release-Fenster

Jeder Strength-Claim ist an einen unveränderlichen Ruleset-Snapshot und ein
Evaluationsfenster gebunden. Das konkrete Manifest validiert gegen
[`evaluation-claim.schema.json`](../../schemas/manifests/evaluation-claim.schema.json).

Eine Mechanik-, Format- oder Banliständerung verändert keinen alten Holdout.
Der alte Claim wird `stale` oder `superseded`; ein neuer Snapshot und ein neuer
versiegelter Pool erzeugen einen neuen Claim.

## Claim-Integrität

Der Claim bindet mindestens:

- Source-Commit;
- Paketversionen;
- Ruleset- und Format-Snapshot;
- Holdout-, Schedule- und Seed-Digests;
- Team-, Gegnerpolicy-, Modell-, Engine- und Search-Digests;
- Zielpopulation, Schätzer und Analyseprotokoll;
- Fehlerklassifikation und vollständige Resultatzeilen.

Ein Release- oder Claim-Tag verweist auf einen Commit auf `main`, in dem das
Claim-Manifest bereits enthalten ist. Ein Claim darf nicht nachträglich passend
zu einem Tag geschrieben werden.

Canonicalization und Hashbildung folgen
[`contract-manifest-schemas`](manifest-schemas.md).

Experimentregistrierungen, Implementierungsbindungen und Laufbindungen sind
unveränderliche Provenienzartefakte. Ihre Lebenszyklus- und
Supersessionsregeln stehen ausschließlich im
[`experiment-registration`](experiment-registration.md)-Contract.
