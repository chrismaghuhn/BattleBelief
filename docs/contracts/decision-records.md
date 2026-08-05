---
document_id: contract-decision-records
title: Decision-Record- und öffentliche Projektion-Vertrag
document_type: contract
status: accepted
normative: true
version: 7
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
freshness_invalidated
```

`submitted` erfordert eine ausgewählte Submission und passende Provenance,
aber keinen Fehlercode. `wait_noop` hat keine Submission, keine Provenance und
keinen Fehlercode. `policy_rejected` und `reconciliation_rejected` haben keine
Submission, keine Provenance und einen statusgebundenen stabilen Fehlercode.
`superseded_before_selection` und `terminally_discarded` haben keine
Submission, keine Provenance und `fallback_or_error_class: null`; sie sind
rein dispositionelle Zustände.
`freshness_invalidated` hat ebenfalls keine Submission, keine Provenance und
`fallback_or_error_class: null`; es markiert einen bereits eröffneten
wartenden Request, der durch einen später eingetroffenen, aber die Freshness-
Prüfung nicht bestehenden Request ungültig wurde. Der Fehlercode des späteren
Requests wird niemals dem älteren Record zugeschrieben.
`action_gate_rejected`,
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

## Measurement-Run-Ergebnis

Ein `measurement-run-result` ist das unveränderliche Ergebnisartefakt eines
synthetischen oder späteren Evaluationslaufs. Es referenziert den Run-Kontext,
ordnet die finalen Decision-Record-Digests in `decision_index`-Reihenfolge und
bewahrt auch Läufe ohne Request, technische Abbrüche und Trace-Fehler. Die
Submission-, Room-Control- und Ignored-Display-Zähler stammen jeweils aus
ihren autoritativen Quellen: finalisierte Records, `BattleSessionResult` und
der finale öffentliche State. Ein Measurement-Runner besitzt Flush und Close
eines injizierten Trace-Sinks; ein Sinkfehler wird als eigenes Trace-Ergebnis
sichtbar und überschreibt keinen früheren Battlefehler.

Die Record-Fehlercode-Taxonomie ist in Version 1 geschlossen und wird in den
beiden Versionen der Record-Payload-/Envelope-Schemas als Enum gespiegelt.
Die ursprünglichen `v1`-Schemas bleiben für bestehende Consumer und alte
Vektoren unverändert. Task-19-Records verwenden `v2`, weil diese Version den
neuen Status `freshness_invalidated` einführt:

```text
no_legal_action_available
local_action_gate_rejection
command_encoding_failed
send_failed
server_invalid_choice
server_unavailable_choice
request_state_reconciliation_mismatch
stale_rqid
disconnect
transport_timeout
timer_or_forfeit
unknown_protocol_event
malformed_protocol_message
reducer_invariant_failure
```

Die Codes sind statusgebunden: `policy_rejected` verwendet
`no_legal_action_available`, `action_gate_rejected` verwendet
`local_action_gate_rejection`, `command_encoding_failed` verwendet seinen
gleichnamigen Code, `send_failed` verwendet nur den Send-/Serverfehlerbereich,
`reconciliation_rejected` verwendet `request_state_reconciliation_mismatch`
oder `stale_rqid`, und `session_aborted` verwendet nur
klassifizierte Transport-, Timer- oder Protokollabbruchcodes. Die rein
dispositionellen Zustände `superseded_before_selection` und
`terminally_discarded` tragen `null`; sie benötigen keinen erfundenen
Fehlercode. `freshness_invalidated` trägt ebenfalls `null`. Setupfehler wie
Teamvalidierung und Challenge-Setup werden nicht
als Decision Record serialisiert.

Ein `measurement-run-result` verwendet dieselbe geschlossene Fehlercode-
Taxonomie sowie die beiden technischen Codes `trace_sink_failure` und
`decision_record_construction_failure`; unbekannte Exceptiontexte werden
vor der Serialisierung auf `runtime_error` reduziert. Ein Ergebnis mit
`completed` muss mindestens einen erfolgreich emittierten Record besitzen.
`no_request` besitzt keine Records und null Submission-Counter, während
`trace_failed` einen fehlgeschlagenen Sink-Lifecycle und den Code
`trace_sink_failure` verlangt. Submission-Counter werden ausschließlich aus
`submitted`-Records abgeleitet; abgelehnte oder fehlgeschlagene Sendpfade
erhöhen sie nicht.
