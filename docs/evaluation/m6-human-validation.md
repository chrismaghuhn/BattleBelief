---
document_id: evaluation-m6-human-validation
title: M6 Human- und Ladder-Validierung
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - gen9ou
  - human-validation
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# M6 Human- und Ladder-Validierung

M6 ist getrennt von M5 und kein rückwirkender Bestandteil des MVP-Claims.

## Plattformabhängigkeit

Öffentliche Ladder-Evaluation findet nur unter den zum Evaluationszeitpunkt
geltenden Pokémon-Showdown-Regeln und, falls erforderlich, nach Abstimmung mit
dem Serverteam statt. Ist automatisiertes Laddering nicht zulässig oder nicht
erwünscht, wird das externe Human-Gate auf einem genehmigten Server, in einer
Challenge-Queue oder in einem dedizierten Evaluationsturnier durchgeführt.

## Vorregistriertes Protokoll

Vor dem ersten gültigen Spiel werden festgelegt:

- Plattform und Genehmigungsgrundlage;
- feste Modell-, Search-, Client- und Team-Digests;
- Teamrotation;
- Spielzahl und kein optionales Stoppen;
- Umgang mit Disconnect, Timer, Forfeit und Serverfehler;
- Rating-, GXE-, Glicko-, RD- und Ergebnisfelder;
- Ratingfenster und Stabilitätsformel;
- Ausschluss manueller Battle-Intervention.

GXE ist nicht identisch mit der tatsächlich beobachteten Match-Winrate.
Rating- und Ergebnismaße werden getrennt berichtet.

## Claims

M6 darf als externe Human-Validierung berichtet werden. Es darf weder die
interne Zielpopulation umdefinieren noch ein nicht bestandenes M5-Gate
ersetzen. Provenance folgt
[`contract-provenance`](../contracts/provenance.md).
