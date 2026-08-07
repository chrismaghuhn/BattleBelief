---
document_id: research-poke-engine-search-improvements-v3-1-battlebelief-review
title: "BattleBelief-Review: poke-engine Search Improvements v3.1"
document_type: research
status: proposed
normative: false
version: 1
applies_to:
  - search
  - runtime
  - gen9ou
effective_from: 2026-08-07
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-07
---

# BattleBelief-Review: poke-engine Search Improvements v3.1

## Quelle und Integrität

Dieses Dokument bewertet das unverändert beigefügte Research-Pack
[`poke-engine-search-improvements-v3.1.zip`](source-packs/poke-engine-search-improvements-v3.1.zip).

Der im Repository gespeicherte ZIP-Blob ist byte-identisch mit dem zur Review
bereitgestellten Archiv; nur der lokale Download-Suffix `(1)` wurde aus dem
Dateinamen entfernt.

```text
SHA-256: 94568aef264970ba55c575f383c88e60a40a5adda8c250b4903481e3b8af3054
size:    40236 bytes
```

Das Pack bleibt unverändert als externe Research-Eingabe erhalten. Dieses
Review ist ebenfalls `normative: false` und besitzt keine Autorität über
Contracts, ADRs, Schemas, Eligibility oder Release-/Strength-Aussagen.

## Gesamtbewertung

v3.1 ist als Search-Research-Roadmap stark. Besonders wertvoll ist, dass die
Semantik vor der Optimierung festgelegt wird. Das Pack trennt unter anderem:

- finite-horizon exactness von full-game exactness;
- Terminalwerte von Horizon-Evaluatoren;
- scalar utility von `terminal_distance`;
- `SearchStateKey`, `SearchContextId` und remaining-depth-Kompatibilität;
- exakte `ValueInterval`-Semantik von approximativen Verfahren;
- Chance-Backup von simultaner Player-Selection;
- `RootMixedStrategyHeuristic` von rekursivem `ZeroSumMatrixNash`;
- deterministische Correctness-Tests von statistischen Shared-Tree-Tests;
- konkrete Hidden-State-Hypothesen von der Information, auf die eine Policy
  tatsächlich konditionieren darf.

Der Anti-Strategy-Fusion-Grundsatz des Packs passt direkt zur bestehenden
BattleBelief-Search-Semantik: eine gesampelte Hidden-Hypothese ist keine
Erlaubnis, die eigene Aktion auf unbekannte Fakten zu konditionieren. Der
bestehende [`contract-search-v0`](../contracts/search-v0.md) schlüsselt
Statistiken bereits nach Informationszustand und verlangt, dass beide Spieler
ihre marginale Aktion wählen, bevor die Joint Action entsteht.

## Zentraler Architektur-Einwand

Das Pack ist als Technical Plan Pack für `pmariglia/poke-engine` formuliert.
Für BattleBelief sollte daraus **nicht** folgen, dass die Search-Policy in den
nativen Engine-Fork verschoben wird.

Die gewünschte BattleBelief-Grenze bleibt:

```text
BattleBelief Search
        |
        | engine-neutrale Search-/Port-Typen
        v
Core TransitionModel
        |
        v
Runtime poke_engine Adapter
        |
        v
geprüftes downstream poke-engine
        |
        v
Pokemon-Mechanics
```

Der eingefrorene
[`TransitionModel`](../../packages/battlebelief-core/src/battlebelief_core/ports/transition_model.py)
ist ausdrücklich die backend-neutrale Mechanics-Grenze, die Search konsumiert.
[`ADR-0006`](../adr/ADR-0006-poke-engine-runtime-mapping-boundary.md) hält die
konkrete `poke_engine`-Abbildung im Runtime-Adapter. Diese Trennung sollte auch
für spätere Search-Verbesserungen erhalten bleiben.

### Was in `poke-engine` gehört

Native Änderungen sind sinnvoll, wenn sie Mechanics effizienter und sauberer
zugänglich machen, zum Beispiel:

- native Legal-Choice-Enumeration wie `poke_engine.legal_choices(...)`;
- exakte Transition-/Outcome-Primitive;
- ein späterer, semantisch identischer Chance-Sampling-Primitive;
- Terminal Detection und terminale Mechanics-Werte;
- effiziente Clone-/Apply-/Undo- oder State-Fingerprint-Primitive, sofern sie
  die öffentliche BattleBelief-Grenze nicht durchbrechen.

Die Engine beantwortet damit Fragen wie „welche Aktion ist mechanisch legal?“
oder „welche Nachfolger erzeugt diese Joint Action?“, aber nicht „welche Aktion
soll BattleBelief auswählen?“.

### Was BattleBelief-seitig bleiben soll

Folgende v3.1-Themen sind Search-/Decision-Policy und gehören nicht als
BattleBelief-spezifische Policy in `poke-engine`:

- Information-Set DUCT;
- Move ordering als Search-Heuristik;
- SearchContext-/TT-Policy;
- Star1/Star2-Orchestrierung;
- Sparse Sampling, Chance Progressive Widening und ChanceProbCut;
- MCTS-Solver-Policy;
- Belief- und Information-State-Policy;
- Root Matrix/Nash;
- SM-MCTS, Regret Matching/RM+ oder Exp3;
- UCB-Ablationen;
- Opponent-/Policy-Guidance;
- Learned Value/Policy;
- Search Eligibility, Deadline- und Fallback-Policy.

Der Grund ist nicht nur Austauschbarkeit des Backends. Die Grenze schützt auch
Hidden Information, Capability-Qualification, reproduzierbare Search-Semantik
und verhindert, dass native Backendtypen oder Backend-Policy heimlich zu
BattleBelief-Domainsemantik werden.

## BattleBelief-Ownership der v3.1-Roadmap

| v3.1-Bereich | Primärer BattleBelief-Owner | Rolle von `poke-engine` |
| --- | --- | --- |
| P0 Benchmarking / Profiling | Lab / Tooling | Benchmark-Target |
| P0.5 Search Semantics & Contracts | Core/Search-Contracts und Research | keine Decision-Policy |
| P1 Move Ordering | Search-Implementierung | kanonische Actions liefern |
| P2 Fast Chance Sampling | Runtime-/Engine-Primitive plus Search-Consumer | Mechanik-Sampler |
| P3/P5 Star1/Star2 | Search-Implementierung | exakte Chance-Outcomes liefern |
| P4 TT / Zobrist / Context | Search-Implementierung | optional semantischer State-Fingerprint |
| P6-P8 approximative Chance-Verfahren | Search / Lab-Experiment | Transition-Backend |
| P9 MCTS-Solver | Search | Transition-Backend |
| P10 Belief / Information State | Core Belief + Search | keine Hidden-State-Policy |
| P11 Root Matrix / Nash | Search, zuerst Lab-validiert | Mechanics only |
| P12 SM-MCTS / Regret Matching | Search, zuerst Lab-validiert | Mechanics only |
| P13 UCB1-Tuned | Lab-Ablation | keine Policy |
| P14/P15 Policy/Value Learning | Lab/Modelle + Search-Integration | keine Model-/Policy-Logik |

## Anpassung des TransitionModel-Vorschlags

v3.1 empfiehlt einen gemeinsamen `TransitionModel::{enumerate,sample}`-Pfad.
Die Grundidee, Enumeration und Sampling auf denselben Mechanics aufzubauen, ist
richtig. BattleBelief besitzt jedoch bereits einen eingefrorenen Port mit
`transition(...) -> TransitionOutcome`, `legal_actions(...)`, Player Views und
Terminal-Methoden.

`TransitionOutcome` modelliert Chance-Outcomes derzeit mit ganzzahligen
Numeratoren und einem gemeinsamen Nenner. Für BattleBelief ist das eine gute
Grenze: exakte rationale Wahrscheinlichkeiten können bis zur Search-/Solver-
Grenze erhalten bleiben und dort, wenn ein Algorithmus es benötigt, kontrolliert
in `f64` überführt werden.

Daraus folgt für die aktuelle M2-Sequenz:

1. Task 27 implementiert den gemergten Core-Port **ohne Signaturänderung**.
2. Exakte Enumeration bleibt die Referenz für Mapping- und Conformance-Tests.
3. Ein zusätzlicher `sample_transition`-/Sampling-Port wird nur in einem
   separaten, ausdrücklich genehmigten Core-Contract-Task eingeführt, falls
   Messdaten zeigen, dass er für Sampled Search erforderlich ist.
4. Ein Sampling-Primitive muss dieselbe Mechanics-Distribution repräsentieren;
   es darf keine zweite Battle-Engine oder Python-seitige Mechanics-Logik
   erzeugen.

Damit wird der v3.1-Grundsatz „enumeration and sampling share mechanics
primitives“ übernommen, ohne Task 27 oder den eingefrorenen Port still zu
verändern.

## Empfohlene Übernahmereihenfolge

### 1. Runtime-Konformität vor Search-Ausbau

Zuerst muss die Runtime-Abbildung zuverlässig sein: getrennte Observed-State-
und Complete-World-Pfade, kanonische Actions, beide Player Views, Joint
Transition, Chance-Outcomes, Terminalwerte, Capability-Anforderungen und
fail-closed Mapping-Failures.

### 2. Bestehenden DUCT-Baseline-Pfad funktionsfähig machen

Der erste produktive Search-Pfad bleibt engine-neutral und erfüllt
[`contract-search-v0`](../contracts/search-v0.md). v3.1 wird zunächst als
Research-Eingabe genutzt, nicht als Ersatz für den bestehenden Vertrag.

### 3. P0/P0.5 als eigene Search-vNext-Entscheidung ausarbeiten

Die stärksten Semantikideen aus v3.1 sollten später in einer separaten
Search-vNext-Designrunde geprüft werden: Exactness-Terminologie,
`SearchContextId`, Horizon-Kompatibilität, `ValueInterval`, Numerical Semantics
und Policy-/Information-State-Cache-Identität.

### 4. Exakten Referenzpfad vor aggressiven Approximationen bauen

Move ordering, TT, Star1/Star2 und ein kleiner finite-horizon Referenzsolver
sind besonders wertvoll, weil sie einen kontrollierten Vergleichspunkt für
spätere sampled/no-regret Verfahren schaffen.

### 5. Matrix- und No-Regret-Verfahren getrennt evaluieren

`RootMixedStrategyHeuristic`, rekursives `ZeroSumMatrixNash` und SM-MCTS/RM+
sind unterschiedliche Semantiken. Sie dürfen weder im Code noch in Strength-
oder Exactness-Berichten zusammengezogen werden.

### 6. Approximation und Learned Search zuletzt

Sparse Sampling, Progressive Widening, ChanceProbCut, Policy Guidance und
Learned Value sollten erst auf einem gemessenen, semantisch stabilen Baseline-
Pfad bewertet werden.

## Review-Blocker für spätere Umsetzung

Eine spätere Implementierung aus diesem Pack ist nur dann mit BattleBelief
kompatibel, wenn mindestens folgende Grenzen erhalten bleiben:

- Search-Policy sieht keine Hidden Information, die der handelnde Spieler nicht
  besitzt;
- Root-Submissions bleiben an den autoritativen Safe-Submission-Satz gebunden;
- Backend-native Strings/States/Exceptions bleiben Runtime-intern;
- Search-/TT-Caches werden nicht über inkompatible Context-/Horizon-Semantik
  wiederverwendet;
- Exact- und Approximation-Modi bleiben explizit getrennt;
- Solver-/Search-Code begründet keine Engine-Capability-Qualification;
- Search-Ergebnisse begründen ohne separate Evaluation keine Strength-Aussage;
- neue native `poke-engine`-Bindings bleiben Mechanics-Primitive und werden wie
  andere Engine-Artefakte provenance- und conformance-seitig gebunden.

## Nicht autorisiert durch diesen PR

Dieser Research-PR autorisiert insbesondere keine:

- Änderung von `contract-search-v0`;
- Änderung des eingefrorenen Core-`TransitionModel`;
- Task-27-Implementierung oder Scope-Erweiterung;
- neue Search-Eligibility;
- Capability-Claims wie `exact` oder `bounded_approximation`;
- Search-Algorithmus-Aktivierung im Live-Runtime-Pfad;
- Strength-/Release-Aussage;
- automatische Übernahme der v3.1-Roadmap in `poke-engine`.

Das Pack wird als hochwertige Research-Eingabe übernommen. Die BattleBelief-
Architekturentscheidung bleibt: **Mechanics nach unten, Search-Policy nach oben.**
