---
document_id: contract-engine-capabilities
title: Engine-Capability-Vertrag
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - search
  - gen9ou
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Engine-Capability-Vertrag

## Rollen

- [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) ist Oracle.
- [`poke-engine`](https://github.com/pmariglia/poke-engine) ist kontrollierter
  Surrogat-Simulator.
- Legal-/Heuristikfallback ist der Livepfad bei fehlender Eligibility.

## Manifest

Die maschinenvalidierte Struktur steht ausschließlich in
[`engine-capability.schema.json`](../../schemas/manifests/engine-capability.schema.json).

`exact` ist immer an `applies_when` und Evidenzhashes gebunden. Upstream-
Approximationen ohne nachgewiesene Fehlergrenze gelten als `unsupported`.

## Eligibility vor jeder Suche

1. Artefakthash, Version, Buildfeatures und Adapter prüfen.
2. Benötigte Capabilities aus Zustand, Belief-Support, Legal Set und
   End-of-Turn-Mechaniken bilden.
3. Search nur bei vollständig `exact` klassifizierter Menge starten.
4. `bounded` nur mit benannter getesteter Grenze und expliziter Freigabe.
5. `unknown`, `unsupported`, Mismatch oder Backendfehler führen zum Fallback.

## Gen9-Sentinel

Der Sentinel prüft das tatsächliche Python-Artefakt:

- gepinnter Upstream-Commit;
- Produktionsfeatures;
- Gen 9;
- Terastallisierung;
- minimaler Search- und Transition-Smoke;
- Artefaktdigest.

Ein erfolgreicher Import reicht nicht.

## Differentialgates

- null unklassifizierte Divergenzen im versionierten Corpus;
- null während der Release-Evaluation beobachtete unklassifizierte
  Divergenzen;
- jede `exact`-Capability besteht ihre eigene Evidenzsuite.

## Fallback und Strength

Zählregeln für Fallback-Battles stehen ausschließlich in
[`evaluation-m5-strength-qualification`](../evaluation/m5-strength-qualification.md).
Search-Coverage, Eligibility und Fallbackgrund werden separat berichtet. Ein
Fallback-Battle darf nicht als Search-Battle bezeichnet werden.
