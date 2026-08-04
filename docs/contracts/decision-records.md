---
document_id: contract-decision-records
title: Decision-Record- und öffentliche Projektion-Vertrag
document_type: contract
status: accepted
normative: true
version: 2
applies_to:
  - evaluation
  - measurement
  - runtime
effective_from: 2026-08-03
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-04
---

# Decision-Record- und öffentliche Projektion-Vertrag

Dieser Vertrag ist die einzige normative Quelle für die Bedeutung von
Decision Records. Das maschinenvalidierte Format ist in den drei registrierten
Schemas unter `schemas/records/` definiert.

## Bytevertrag und Digests

Decision Records verwenden das Repository-Kanonisierungsprofil v1:
validierte JSON-Werte werden mit RFC 8785 als UTF-8 ohne abschließenden
Zeilenumbruch serialisiert. Der Digest ist `sha256:` plus 64 kleingeschriebene
Hexzeichen. `record_digest` hasht `{record_id, payload}`; das Feld
`record_digest` selbst ist nicht Teil seines Inputs. `record_id` wird separat,
nicht zirkulär, aus Run-Kontext, Battle-ID, Entscheidungsindex und der
öffentlichen Request-Identity-Projektion abgeleitet.
Die Referenzvektoren liegen in
`schemas/canonicalization/decision-record-test-vectors.json`.

## Öffentliche Grenze

Die Projektionen enthalten keine Passwörter, Assertions, Packed Teams, rohen
Room-IDs, Konto- oder User-IDs, sichtbaren Displaynamen, privaten Requests,
gesampelten Hidden Worlds, absoluten Pfade, Hostnamen oder Wandzeitstempel.
Sie bewahren nur ausdrücklich dokumentierte beobachtete Felder. Nickname-
tragende Transformationsziele, freie Effekte und rohe Annotationen werden nicht
projiziert; eine Transformation wird nur als boolesches `transformed`-Merkmal
beziehungsweise als identitätsfreie Evidenz gemeldet. Der Gewinner wird als
`our_side`, `opponent_side` oder `tie` dargestellt, nie als Username. Ein nicht
auflösbarer Gewinner wird nicht als gegnerischer Sieg fehlklassifiziert.

Die Reihenfolge von `SafeSubmissionSet.submissions`, `BattleSubmission.team_order`
und sichtbaren Evidenzereignissen ist semantisch und bleibt erhalten.
Mapping-Schlüssel und echte mathematische Mengen werden kanonisch sortiert.

## Run-Kontext

Ein Measurement-Run verwendet die nichtzirkuläre Kette:

```text
RunScopePayload
→ run_scope_digest
→ {run_scope_digest, schedule_row_id, battle_ordinal}
→ battle_id_digest
→ RunContextPayload
→ run_context_digest
```

Der rohe Showdown-Raumname ist kein Bestandteil dieser Offline-Identität.
Ein Decision Record referenziert den Run-Kontext und verwendet einen
nullbasierten `decision_index`.

## Status und Kardinalität

Die zulässigen terminalen Status und ihre Feldinvarianten sind:

```text
submitted
wait_noop
policy_rejected
action_gate_rejected
command_encoding_failed
send_failed
session_aborted
superseded_before_selection
terminally_discarded
reconciliation_rejected
```

`submitted` erfordert eine ausgewählte Submission und passende Provenance,
aber keinen Fehlercode. `wait_noop` hat keine Submission, keine Provenance und
keinen Fehlercode. `policy_rejected`, `superseded_before_selection`,
`terminally_discarded` und `reconciliation_rejected` haben keine Submission,
keine Provenance und einen stabilen Fehlercode. `action_gate_rejected`,
`command_encoding_failed` und `send_failed` haben eine ausgewählte Submission,
passende Provenance und einen stabilen Fehlercode. `session_aborted` erfordert
einen stabilen Fehlercode; eine bereits erfolgte Auswahl darf erhalten bleiben.
Fehlercodes entsprechen ausschließlich der versionierten Record-Allowlist und
dem Muster `^[a-z][a-z0-9_]{0,63}$`; Punkte, Doppelpunkte, freie Texte und
Hostnamen sind ausgeschlossen. Die Submission-Felder entsprechen außerdem den
Invarianten von `BattleSubmission`: Move-Slots sind 1--4, Switch-/Revive-Slots
1--6, Team-Slots sind nichtleer und eindeutig, und Default-Aktionen tragen
ausschließlich `server_default`.

Jeder frische Request, der die Freshness-Prüfung passiert, eröffnet genau ein
Record und erhält genau eine terminale Disposition. Ein identischer Duplicate-
Request eröffnet kein Record. Ein Abbruch ohne frischen Request gehört in das
Run-/Battle-Resultat und erfindet keine Request-Identity. `command_encoding_failed`
ist von `send_failed` getrennt: Die Auswahl und Provenance sind vorhanden, aber
es gab keinen Socket-Send und keinen Submission-Counter-Zuwachs. `battle_id_digest`
ist Bestandteil des Payloads und wird damit sowohl von `record_id` als auch von
`record_digest` nachvollziehbar gebunden.

Fehlertexte werden nie serialisiert; `fallback_or_error_class` enthält nur
stabile Klassifikationscodes oder `null`.
