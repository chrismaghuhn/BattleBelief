---
document_id: adr-0003-battlebelief-naming
title: "ADR-0003: BattleBelief-Naming und Paketidentität"
document_type: adr
status: accepted
normative: false
version: 1
applies_to:
  - repository
  - packaging
  - schemas
effective_from: 2026-07-29
supersedes:
  - adr-0002-three-package-monorepo
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# ADR-0003: BattleBelief-Naming und Paketidentität

## Kontext

ADR-0002 legte ein Drei-Pakete-Monorepo unter dem vorläufigen Namen
`pokemonbot` fest. Vor dem ersten Code und vor einer Paketveröffentlichung
wurde **BattleBelief** als öffentlicher Projektname gewählt. Ein reines
Repository-Rebranding bei unveränderten `pokemonbot-*`-Paketen würde zwei
dauerhafte Identitäten erzeugen.

## Entscheidung

Die öffentliche Projektidentität lautet:

```text
display name: BattleBelief
repository: chrismaghuhn/BattleBelief
subtitle: An open-source Pokémon Singles research bot for
          decision-making under hidden information
```

Repository:

[`chrismaghuhn/BattleBelief`](https://github.com/chrismaghuhn/BattleBelief)

Die drei Distributionspakete heißen:

```text
battlebelief-core
battlebelief-runtime
battlebelief-lab
```

Die Python-Importnames heißen:

```text
battlebelief_core
battlebelief_runtime
battlebelief_lab
```

Projektkontrollierte Schema-IDs verwenden:

```text
urn:battlebelief:...
```

Die aktuelle normative Liste der Paketgrenzen und öffentlichen Runtime-APIs
steht ausschließlich in
[`architecture-code-boundaries`](../architecture/code-boundaries.md).

## Beibehaltener Architekturentscheid

Die Drei-Pakete-Struktur, ihre Isolation und die Lockstep-Versionierung während
`0.x` bleiben bestehen. ADR-0003 ersetzt ADR-0002 als aktuelle Entscheidung,
weil es dessen Architektur mit der endgültigen Paketidentität vollständig
neu festhält.

## Verworfene Alternativen

### Nur das Repository umbenennen

`BattleBelief` außen und `pokemonbot-*` innen hätte kurzfristig weniger
Dokumentänderungen benötigt, aber langfristig Suche, Installation,
Fehlermeldungen und Paketprovenienz unnötig getrennt.

### Pokémon im Markennamen behalten

Ein rein beschreibender Name wäre leichter sofort einzuordnen, aber weniger
eigenständig. Der Untertitel stellt die Pokémon-Singles-Ausrichtung her, ohne
den Projektnamen an ein einzelnes Format, eine Generation oder einen
Search-Algorithmus zu binden.

### Algorithmus im Namen

Ein DUCT-, MCTS- oder ISMCTS-Name würde die Forschungsrichtung sichtbar machen,
aber spätere Search-Ablationen und hybride Policies unnötig als
Namensänderungen erscheinen lassen.

## Konsequenzen

Vorteile:

- eine Identität in GitHub, Distributionen, Imports, Logs und Manifests;
- der Name bleibt bei weiteren Singles-Formaten und Search-Varianten gültig;
- technische Artefakte sind eindeutig dem Projekt zuzuordnen.

Kosten:

- der Name erklärt Pokémon nicht ohne Untertitel oder README;
- bestehende Planungsdokumente und Schema-IDs müssen vor M0 umgestellt werden;
- der historische Design-Freeze behält absichtlich die damaligen
  `pokemonbot-*`-Bezeichnungen.
