---
document_id: adr-0001-information-set-duct-v0
title: "ADR-0001: Information-Set DUCT als Search-v0"
document_type: adr
status: accepted
normative: false
version: 1
applies_to:
  - search
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# ADR-0001: Information-Set DUCT als Search-v0

## Kontext

Pokémon Singles besitzt simultane Aktionswahl, Chance-Events und versteckte
Moves, Items, Abilities, Spreads und Tera-Typen. Gewöhnliches alternierendes
UCT oder ein separater perfekter Baum je vollständiger Welt kann die
gegnerische Aktion fälschlich nach Kenntnis unserer Aktion wählen oder
Strategy Fusion erzeugen.

## Entscheidung

Search-v0 verwendet Information-Set DUCT:

- neue Posteriorwelt pro Simulation;
- Knoten nach Informationszustand;
- getrennte Spieleransichten;
- unabhängige simultane marginale Aktionswahl;
- Root-Statistiken über alle Welten;
- kein weltabhängiger Root-Argmax.

Der normative Algorithmusvertrag steht in
[Search-v0](../contracts/search-v0.md).

## Verworfene Ausgangsalternativen

### Gewöhnliches alternierendes UCT

Modelliert simultane Commitments falsch.

### Separater perfekter Baum je Welt

Einfacher zu implementieren, aber hohes Strategy-Fusion-Risiko.

### Regret Matching/Exp3 als erste Version

Theoretisch sauberer für simultane perfekte Informationsspiele, aber höhere
Komplexität und keine vollständige Hidden-Information-Garantie für Pokémon.
Bleibt präregistrierte spätere Ablation.

## Konsequenzen

- praktische Search-first-Basis;
- keine Nash-/allgemeine Konvergenzbehauptung;
- Informationsansichten, Welt-Sampling und Root-Aggregation werden Teil der
  gehashten Maschinenidentität;
- deterministischer Benchmark und Live-Anytime benötigen getrennte Modi.

## Quellen

- [Information Set Monte Carlo Tree Search](https://eprints.whiterose.ac.uk/id/eprint/75048/1/CowlingPowleyWhitehouse2012.pdf)
- [Monte Carlo Tree Search in Simultaneous Move Games](https://proceedings.neurips.cc/paper_files/paper/2013/file/1579779b98ce9edb98dd85606f2c119d-Paper.pdf)
- [Foul Play: Pokémon Search Architecture](https://pmariglia.github.io/posts/foul-play/)
