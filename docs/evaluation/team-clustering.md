---
document_id: evaluation-team-clustering
title: Kanonische Teamcluster für M1.5
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - evaluation
  - gen9ou
effective_from: 2026-08-04
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-04
---

# Kanonische Teamcluster

M1.5 verwendet die Exact-Team-Clusterregel `canonical_exact_team_cluster_v1`.
Sie gruppiert nur vollständige, strukturell gültige Sechserteams mit derselben
kanonischen Darstellung. Diese Regel ist keine semantische Ähnlichkeitsmetrik.

Die Darstellung enthält ausschließlich `species`, `form`, `item`, `ability`,
`nature`, vier Moves, EVs, IVs, `level`, `happiness`, `gender`, `shiny`,
`pokeball`, `hidden_power_type` und `tera_type`. Die Defaults sind: leere
Form, Item, Ability, Nature, Hidden-Power- und Tera-Type-Werte, vier
explizite Moves, EVs null, IVs 31, Level 100, Happiness 255, Gender null,
Shiny false und Pokéball `poke ball`. Unbekannte Felder,
duplizierte Moves, falsche Wertebereiche und Teams mit nicht genau sechs
Mitgliedern werden fail-closed abgelehnt. Pokémon-Identifier werden nach
Showdowns ASCII-`toID`-Regel normalisiert, bevor sie kanonisiert werden.

Die sechs Mitglieder werden in der kanonischen Darstellung unabhängig von
ihrer Teamposition sortiert. Move-Slots werden für diese Clusterregel als
sortierte Menge dargestellt; die Reihenfolge der Submission-Aktionen bleibt
davon unberührt. Die Feld- und Memberreihenfolge ist versioniert und Teil des
Cluster-Digests. Der Cluster-Identifier ist der RFC-8785-SHA-256-Digest der
vollständigen Darstellung.

M1.5 erstellt keine konkreten Evaluation-Pools. Die Clusterregel darf daher
keinen Selection-, Power-Pilot- oder Release-Holdout-Pool öffnen.
