---
document_id: data-sources-and-licensing
title: Datenquellen, Lizenzen und Artefakte
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - data
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Datenquellen, Lizenzen und Artefakte

## Metamon-Bootstrap

```text
dataset: jakegrigsby/metamon-parsed-replays
format: gen9ou
tag: v6
revision: 7d82b873647dee35a62e7b63cd253e5d273cbe87
license: CC BY-NC 4.0
```

Quelle:
[`jakegrigsby/metamon-parsed-replays`](https://huggingface.co/datasets/jakegrigsby/metamon-parsed-replays).

`actions["missing"] == true` wird aus Action-Supervision und -Evaluation
maskiert. Rekonstruierte Sets sind kompatible Kandidaten, keine Ground Truth.

## Smogon Usage

Veröffentlichte Smogon-Stats sind Pokémon-/Setattribut-Marginalen und teilweise
Teamkollegenstatistiken. Sie sind keine vollständige Teamverteilung und keine
Gegneraktionspolicy.

Die daraus modellierte Zielpopulation wird ausschließlich in
[Zielpopulation und Metagame-Gewichtung](../evaluation/target-population.md)
definiert.

## Lizenzmatrix

| Artefakt | Vertrag |
|---|---|
| Core/Runtime/Lab-Code | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| Self-Play-Checkpoint ohne NC-Daten | separate permissive Modelllizenz |
| eigener Checkpoint mit Metamon-NC-Daten | getrenntes NC-Forschungsartefakt |
| Metamon-Splits/Manifeste | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en) und Attribution |
| offizielle Metamon-Weights | exakte Apache-2.0-Provenienz |
| [`poke-engine`](https://github.com/pmariglia/poke-engine) | MIT-Notice |
| [Pokémon Showdown Server](https://github.com/smogon/pokemon-showdown) | MIT-Notice |
| [Foul Play](https://github.com/pmariglia/foul-play) | GPL-3.0; kein Copy/Paste in permissiven Core |
| [Pokémon Showdown Client](https://github.com/smogon/pokemon-showdown-client) | AGPL-3.0; keine ungeklärte Übernahme |

Die Rechtslage eigener Gewichte aus NC-Daten wird nicht als abschließend geklärt
behauptet. Das Projekt trennt sie konservativ.

„Open Source“ bezeichnet den Apache-2.0-Codebestand. Eine Distribution mit
NC-basierten Checkpoints ist nicht automatisch eine vollständig
OSI-konforme Open-Source-Distribution; deshalb werden Code und Modellartefakte
getrennt veröffentlicht und bezeichnet.

## Nicht im Core-Repository

- Replaykorpora;
- Parquet-Datensätze;
- Modellgewichte;
- vollständige Trainingsoutputs;
- Credentials und Ladder-Cookies;
- große Differentialfixtures ohne bewusstes Review.

Im Repository liegen nur kleine Fixtures, Manifeste, URLs, Digests und
Reproduktionswerkzeuge.
