---
document_id: product-scope-and-success
title: Scope und Erfolg
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - project
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Scope und Erfolg

## Scope

- ausschließlich Pokémon Singles;
- initial aktuelles Smogon Gen 9 OU;
- feste, vor Battlebeginn versiegelte Teams;
- Entscheidungen unter unvollständiger Information;
- lokale Adaption an Reveals und Verhalten im laufenden Battle;
- offene Entwicklung unter Apache-2.0;
- öffentliche CPU-Runtime;
- spätere Singles-Formate nur mit eigenem Claim.

## Nicht im MVP

- Doubles oder VGC;
- Team-Erzeugung im Battle;
- globale Online-Gewichtsänderung während Evaluation;
- Cross-Battle-Gegnerprofile als Pflicht;
- Ladder-Massentraining;
- LLM-Komponenten;
- eigene vollständige Mechanikengine.

## Erfolgshierarchie

| Stufe | Bedeutung |
|---|---|
| grüner `main` | integrierbar; kein Strength-Claim |
| Prototyp | technische Teilfunktion |
| MVP-Kandidat | versiegelt, aber finaler Holdout ungeöffnet |
| M5 MVP | interne Strength Qualification bestanden |
| M6 | getrennte Human-/Ladder-Validierung |

Die vollständigen M5-Schwellen stehen ausschließlich in
[M5 Strength Qualification](../evaluation/m5-strength-qualification.md).

M6 ist weder Voraussetzung noch rückwirkender Bestandteil des M5-Claims.
