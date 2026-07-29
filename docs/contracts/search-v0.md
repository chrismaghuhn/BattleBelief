---
document_id: contract-search-v0
title: Search-v0
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

# Search-v0: Information-Set DUCT

```text
algorithm_id: information_set_duct_v0
search_adr: ADR-0001-information-set-duct-v0
```

## Vertrag

1. Jede Simulation zieht eine Welt aus dem aktuellen Posterior.
2. Die Welt ist auf eigene private Information und öffentliche Historie
   konditioniert.
3. Knotenstatistiken sind nach Informationszustand, nicht vollständigem Hidden
   State, geschlüsselt.
4. Der Gegner kennt in seiner Ansicht sein eigenes gesampeltes Set, aber keine
   unveröffentlichten Informationen unserer Seite.
5. Beide Spieler wählen ihre marginale Aktion unabhängig, ohne die
   gleichzeitige gegnerische Aktion zu kennen.
6. Erst danach entsteht die gemeinsame Aktion und der Chance-/Transition-Step.
7. Root-Entscheidung und Teacher-Target aggregieren eigene Aktionsstatistiken
   über alle Welten.
8. Kein weltabhängiger Joint-Action-Argmax bestimmt die Root-Aktion.

DUCT besitzt hier keine Nash- oder allgemeine Konvergenzgarantie. Regret
Matching/Exp3 ist eine spätere Ablation.

## Betriebsmodi und Maschinenidentität

Deterministic Benchmark, Live Anytime, Seed-Semantik und
Parallelreproduzierbarkeit werden ausschließlich durch
[`contract-determinism`](determinism.md) definiert.

Struktur, Canonicalization und Hashbildung des Search-Manifests werden durch
[`contract-manifest-schemas`](manifest-schemas.md) und das
[`search-contract.schema.json`](../../schemas/manifests/search-contract.schema.json)
festgelegt. Jede Decision Row trägt den `search_contract_hash`.

Die Release-Laufzeitgrenzen stehen ausschließlich in
[`evaluation-m5-strength-qualification`](../evaluation/m5-strength-qualification.md).
