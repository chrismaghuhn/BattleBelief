---
document_id: contract-protocol-state
title: Protocol- und State-Vertrag
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - runtime
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Protocol- und State-Vertrag

## Datenfluss

```text
Showdown wire
→ Runtime parser
→ canonical immutable BattleEvent
→ Core ObservationReducer
→ ObservedState
```

Belief und Decision dürfen keine Wire-Nachrichten interpretieren. Der
deterministische Reducer ist die einzige Quelle des sichtbaren Zustands.
Kanonische Events gehören zum Core; Parsing und Command-Encoding bleiben in
der Runtime.

## Eventbehandlung

- State-bearing Events sind vollständig typisiert.
- Bekannte irrelevante Events liegen in einer expliziten No-op-Allowlist.
- Ein unbekanntes state-bearing Event führt fail-closed zu klassifiziertem
  Abbruch oder nachweisbarer Resynchronisation.
- „Nicht gesehen“ bedeutet niemals beobachtetes `None`.
- Item-, Ability- und Identitätswerte tragen Evidenzereignis und
  Gültigkeitsintervall.
- Unvollständige, widersprüchliche oder unbekannte Nachrichten dürfen den
  Zustand nicht still fortschreiben.

## Evidenzraum

Die Aussage über vollständige Protokollabdeckung gilt ausschließlich für:

1. alle gültigen Fixtures des versionierten Protocol-Corpus und
2. alle während einer konkreten Release-Evaluation beobachteten Events.

Sie ist kein Beweis über alle theoretisch möglichen Showdown-Ereignisse.

Im versionierten Protocol-Corpus und während der konkreten
Release-Evaluation gelten:

- null unbekannte state-bearing Events;
- null Parserfehler;
- null Reducer-Invariant-Fehler;
- null erkannte Request-/State-Reconciliation-Mismatches.

## Protocol-Fehlerklassen

```text
unknown_protocol_event
malformed_protocol_message
reducer_invariant_failure
request_state_reconciliation_mismatch
transport_timeout
disconnect
timer_or_forfeit
```

Jeder Abbruch besitzt genau eine primäre Klasse und darf nicht still als
gewöhnlicher Battle-Ausgang fortgeschrieben werden. Action-Safety und
serverseitige Zurückweisungen regelt
[`contract-legal-action-safety`](legal-action-safety.md).
