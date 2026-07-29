---
document_id: adr-0002-three-package-monorepo
title: "ADR-0002: Drei-Pakete-Monorepo"
document_type: adr
status: superseded
normative: false
version: 1
applies_to:
  - repository
effective_from: 2026-07-29
supersedes: []
superseded_by: adr-0003-battlebelief-naming
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# ADR-0002: Drei-Pakete-Monorepo

## Kontext

Der Bot benötigt drei deutlich verschiedene Abhängigkeitsprofile:

- reine Domain-, Belief-, Search- und Application-Logik;
- öffentliche Live-Runtime mit Showdown-Client und optionalen Engine- oder
  Modelladaptern;
- schwere Offline-Werkzeuge für Oracle, Daten, Training und Evaluation.

Ein einziges Python-Paket würde die Regel „Runtime importiert weder Training
noch Research“ hauptsächlich als Konvention ausdrücken. Mehrere Repositories
würden dagegen Versions-, Release- und Koordinationsaufwand erzeugen, der für
ein Solo- oder Kleinteamprojekt nicht gerechtfertigt ist.

## Entscheidung

Das Repository enthält drei separat installierbare Python-Pakete:

```text
pokemonbot-core
pokemonbot-runtime
pokemonbot-lab
```

Die aktuelle normative Liste erlaubter Importkanten, öffentlicher
Runtime-APIs und verbotener Abhängigkeiten steht ausschließlich in
[`architecture-code-boundaries`](../architecture/code-boundaries.md). Dieses
ADR begründet die Paketentscheidung, ersetzt diese veränderbare Liste aber
nicht.

### `pokemonbot-core`

Enthält:

- unveränderliche Domainobjekte und kanonische Events;
- Observation-Reducer;
- Belief- und Open-World-Logik;
- Search und Safety;
- Engine-Eligibility als reine Entscheidung;
- Ports und kanonische Schemas.

Kennt keine Netzwerk-, Datei-, Datenbank-, Engine-, Node-, ML-, CUDA-,
Telemetrie- oder globale Zeit-/Zufallsimplementierung.

### `pokemonbot-runtime`

Enthält:

- Showdown-Wire-Protokoll und Client;
- Teamdatei- und SQLite-Meta-Adapter;
- Legal-/Heuristikfallback;
- optionalen `poke-engine`-Search-Adapter;
- optionale ONNX- und PyTorch-Inferenzadapter;
- Composition Root und CLI.

Runtime hängt ausschließlich vom Core ab.

### `pokemonbot-lab`

Enthält:

- lokalen Showdown-Oracle;
- Replay-Ingestion und Meta-Mining;
- Search Teacher und Self-Play;
- Training, Evaluation und Reporting.

Lab verwendet die in `architecture-code-boundaries` freigegebenen Core- und
Runtime-Oberflächen.

## Ports

Der Core-Port für Meta-Wissen heißt `MetaPriorProvider`. Er lädt einen
unveränderlichen `MetaPriorSnapshot` und besitzt keine SQL-artige
Abfragesemantik.

Der Modellport heißt `PolicyValueEvaluator` und beschreibt ausschließlich
Inferenz. Modellladen, Download, Gerätewahl, Training und Optimizerzustand
gehören nicht zu diesem Port.

## Adapterkomposition

Leaf-Adapter importieren oder konstruieren keine anderen Leaf-Adapter.
Decorators, zusammengesetzte Adapter und Fallback-Ketten sind zulässig, wenn
der Composition Root sie erzeugt und die Komposition einen Core-Port
implementiert.

## Packaging

```text
pokemonbot-runtime:
  base
  search
  onnx
  torch

pokemonbot-lab:
  Oracle-, Daten-, Training- und Evaluationsabhängigkeiten
```

PyTorch ist keine Pflichtabhängigkeit der Runtime-Base.

Während `0.x` werden alle Pakete im Lockstep versioniert. Runtime verlangt die
exakt gleiche Core-Version; Lab verlangt die exakt gleiche Core- und
Runtime-Version.

## Durchsetzung

Merge-blockierend:

- verbotene Importkanten;
- verbotene Heavy-Dependency-Imports;
- Lab-Zugriff nur auf freigegebene Runtime-Module;
- wiederverwendbare Contract-Suites für Adapter;
- isolierte Installations-Smokes für Core, Runtime-Base, Runtime-Search und
  Lab.

## Verworfene Alternativen

### Ein Python-Paket

Weniger Packagingaufwand, aber schwächere Isolation und höheres Risiko, schwere
oder interne Abhängigkeiten versehentlich in die öffentliche Runtime zu ziehen.

### Mehrere Repositories

Stärkere organisatorische Isolation, aber unnötiger Release-, Versions- und
Cross-Repository-Koordinationsaufwand.

## Konsequenzen

Vorteile:

- installierbare Abhängigkeitsprofile;
- maschinell prüfbare Grenzen;
- wiederverwendbare Runtime-Adapter im Lab;
- kein Training-/Research-Zwang für öffentliche Nutzer.

Kosten:

- drei Buildkonfigurationen;
- gemeinsame Releasekoordination;
- bewusst gepflegte öffentliche Runtime-APIs.

## Kriterien für eine spätere Aufspaltung

Eine Trennung in mehrere Repositories wird erst neu bewertet, wenn mindestens
eines gilt:

- Pakete besitzen unabhängig veröffentlichte Maintainerteams;
- Releasezyklen müssen nachweislich unabhängig werden;
- Zugriffs- oder Compliancegrenzen lassen sich im Monorepo nicht ausreichend
  durchsetzen;
- externe Nutzer benötigen ein Paket unabhängig vom restlichen Projekt und
  Lockstep-Versionierung verursacht reale Blockaden.
