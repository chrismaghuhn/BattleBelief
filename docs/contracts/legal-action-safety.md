---
document_id: contract-legal-action-safety
title: Legal-Action- und Fallback-Safety-Vertrag
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - runtime
  - gen9ou
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Legal-Action- und Fallback-Safety-Vertrag

## Autoritative Aktionsmenge

```text
latest Showdown request + rqid
→ authoritative legal action set
```

Vor jedem Versand:

1. vorgeschlagene Aktion gegen das neueste autoritative Legal Set prüfen;
2. aktuelles `rqid` prüfen;
3. Team-, Slot-, Switch- und Tera-Bezug prüfen;
4. bei Mismatch die Entscheidung verwerfen;
5. eine sichere Aktion ausschließlich aus dem aktuellen Legal Set wählen.

Ein Search-, Modell- oder Adapterergebnis darf die autoritative Aktionsmenge
nicht erweitern.

## Fallback-Kette

Die Composition Root erzeugt eine versionierte Fallback-Kette. Jede Stufe
liefert entweder eine legal geprüfte Aktion oder einen klassifizierten Fehler.
Unbekannte Capability, Engine-Fehler, Deadline oder Modellfehler dürfen niemals
zu einer unvalidierten Aktion führen.

Fallback-Entscheidungen bleiben Bestandteil des primären Battle-Ergebnisses.
Ihre Zähl- und Release-Regeln stehen ausschließlich in
[`evaluation-m5-strength-qualification`](../evaluation/m5-strength-qualification.md).

## Fehlerklassen

```text
capability_unsupported
engine_manifest_mismatch
engine_runtime_failure
model_runtime_failure
decision_deadline
local_action_gate_rejection
stale_rqid
server_invalid_choice
server_unavailable_choice
no_legal_action_available
```

## Nachweis

Contract-Tests prüfen mindestens:

- keine Mutation der Eingabeobjekte;
- Auswahl nur aus der übergebenen Aktionsmenge;
- Ablehnung eines veralteten `rqid`;
- deterministische Fallback-Reihenfolge bei gleicher Eingabe;
- klassifizierte Fehler statt stiller Approximation;
- Erhalt von Entscheidungs- und Provenance-IDs.

Im versionierten Safety-Corpus und während der konkreten Release-Evaluation
gelten:

- null stale-`rqid`-Submissions;
- null `Invalid choice`;
- null `Unavailable choice`.
