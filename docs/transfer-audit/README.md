---
document_id: transfer-audit
title: Transfer-Audit historischer Bot-Komponenten
document_type: audit
status: accepted
normative: true
version: 1
applies_to:
  - historical-code
  - contributions
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Transfer-Audit historischer Bot-Komponenten

Das historische VGC-Projekt ist nur eine Kandidatenquelle. Kein Bestandteil
wird allein wegen funktionaler Ähnlichkeit übernommen.

## Mögliche formatneutrale Kandidaten

- Verbindung und Lifecycle;
- Authentifizierung;
- formatneutrales Protokollparsing;
- Teamimport und -hashing;
- Logging und Provenance-Hilfen.

## Nicht blind übertragen

- Battle-State und Decision-Core;
- Annahmen über zwei aktive Slots;
- Partner-Targeting und Spread-Moves;
- Joint-Action-Tupel;
- Bring-4 und Lead-Paare;
- VGC-spezifische Protect-Priors.

Protect und Slots sind nicht pauschal problematisch; ausgeschlossen sind
Doubles-spezifische Partner-, Target- und Zwei-Active-Slot-Annahmen.

## Auditdatensatz

Jede übertragene Einheit dokumentiert:

```text
source repository, file and commit
target package and file
responsibility
provenance:
  copied | modified | ideas-only | clean-implementation
license evidence
removed VGC assumptions
known bugs
new OU tests
differential or integration evidence
review status
```

## Freigaberegel

Vor Veröffentlichung erfolgen:

- Secret-, Credential-, Username-, Replay- und lokale Pfadprüfung;
- Herkunftsvergleich mit bekannten Clients und Frameworks;
- Lizenzprüfung jedes Snippets und jeder Abhängigkeit;
- Bugprüfung auch für unverändert übernommene Komponenten;
- Singles-/OU-spezifische Contract- und Integrationstests.

Bei unklarer Herkunft, inkompatibler Lizenz oder nicht sauber entfernbaren
VGC-Annahmen wird die Komponente auf Basis zulässiger Spezifikationen neu
implementiert.
