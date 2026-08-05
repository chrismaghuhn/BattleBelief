---
document_id: research-adjacent-belief-search-directions
title: Adjacent Belief, Search, and Evaluation Directions
document_type: research
status: proposed
normative: false
version: 1
applies_to:
  - belief
  - search
  - evaluation
  - research
  - gen9ou
effective_from: 2026-08-05
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-05
---

# Adjacent Belief, Search, and Evaluation Directions

Diese Research Note sammelt angrenzende Forschungsrichtungen, die sich aus der
[Constraint-guided Open-World Set Materialization](constraint-guided-other-materialization.md)
und der bestehenden BattleBelief-Forschungsstrategie ergeben.

Sie ist keine normative Quelle, registriert keine Algorithmus- oder Arm-IDs und
ändert weder die M2-Reihenfolge noch akzeptierte Contracts, Registrierungen,
Budgets oder Gates. Bei einem Widerspruch gelten die Quellen im
[Dokumentationsindex](../README.md).

## Einordnung

Die Vorschläge gehören zu drei unterschiedlichen Schichten:

```text
Belief und Risiko
- Gegneraktionen als Belief-Evidenz
- Tail-Risk World Sampling

Evaluation und Erklärbarkeit
- Strategy-Fusion-Corpus
- Engine-Fragility-Analyse
- Robustheitszertifikate

Effizienz
- Decision-Equivalent Hypothesis Compression
- Battle Compute Bank und Early Stop
```

Sie sollen nicht gleichzeitig in die Roadmap gedrückt werden. Jede Richtung
benötigt vor einer Implementierung eine eigene Fragestellung, Ausführungs-
identität, Ablation und Stop-/Pivot-Regel.

## 1. Gegneraktionen als probabilistische Belief-Evidenz

Mechanische Reveals sind nicht die einzige Informationsquelle. Auch eine
freiwillig gewählte Gegneraktion kann Hinweise auf ein verborgenes Set oder
einen battle-lokalen Spielstil liefern.

Arbeitslabel:

```text
policy_likelihood_belief_update_v0
```

Ein möglicher Update-Schritt lautet:

```text
P(hidden set, style | public history, observed action)
∝
P(hidden set, style | public history)
× P(observed action | hidden set, style, public state)
```

Beispielsweise kann das Verbleiben eines gefährdeten Pokémon im Feld durch
einen unerwarteten Tera-Typ, Coverage, eine Switch-Erwartung, Risikopräferenz
oder einen Fehler erklärt werden. Das Modell darf eine schlechte Aktion nicht
automatisch als starke Set-Evidenz interpretieren.

Ein erster Prototyp sollte daher:

- ausschließlich innerhalb eines Battles lernen;
- eine explizite Noise-/Mistake-Komponente besitzen;
- zunächst ohne persistente Gegneridentität auskommen;
- Set- und Stilunsicherheit getrennt berichten;
- nur öffentliche Historie und eigene private Information verwenden;
- gegen mechanische Belief-Updates und einen no-policy-likelihood Arm abgetragen
  werden.

Die primäre Messfrage ist, ob die Aktionslikelihood Hidden-Set-Kalibrierung und
Entscheidungsnutzen verbessert, ohne überkonfident auf Fehler oder ungewöhnliche
Spielzüge zu reagieren.

## 2. Paired Information-Set Counterexample Corpus

BattleBeliefs Search-These benötigt gezielte Zustände, in denen getrennte
Determinization und Information-Set Search tatsächlich unterschiedliche
Eigenschaften zeigen.

Arbeitslabel:

```text
paired_information_set_counterexample_corpus_v0
```

Ein Corpus-Fall enthält mindestens:

```text
dieselbe öffentliche Historie
dieselbe autoritative Legal-Action-Menge
mehrere plausible vollständige Hidden Worlds
unterschiedliche weltabhängig optimale Aktionen
eine gemeinsame information-set-korrekte Root-Entscheidung
```

Eine Lab-Pipeline kann solche Zustände aus kontrollierten vollständigen Welten
suchen und anschließend als kleine, digestgebundene Puzzles versiegeln.

Mögliche diagnostische Größen:

```text
strategy_fusion_severity
hidden_world_action_flip_rate
clairvoyance_gap
world-conditioned plan inconsistency
information_set_recovery_rate
robust_action_regret
```

Der Corpus ist keine Ersatz-Winrate. Er soll erklären, wann Determinization
scheitert, wann sie ausreichend ist und ob Information-Set DUCT die beabsichtigte
Root-Semantik tatsächlich wiederherstellt.

Diese Richtung ist bereits während M2/M3 als Research-Vorbereitung sinnvoll,
darf aber den strikt seriellen M2-Implementierungsplan nicht erweitern.

## 3. Decision-Equivalent Hypothesis Compression

Ein Open-World-Belief kann Hunderte vollständige Hypothesen enthalten. Viele
Unterschiede sind für eine konkrete Entscheidung möglicherweise irrelevant.

Arbeitslabel:

```text
decision_equivalent_world_compression_v0
```

Die Idee gruppiert Welten nicht primär nach struktureller Ähnlichkeit, sondern
nach ähnlichen entscheidungsrelevanten Konsequenzen, etwa:

- gleichen Legal Actions;
- gleichen relevanten Speed-Relationen;
- gleichen terminalen Gefahren;
- gleichen Damage-Bändern;
- stabiler Root-Action-Reihenfolge unter einem begrenzten Probe-Budget.

Search verwendet Repräsentanten und gebundene Klassenmassen. Eine Klasse muss
wieder aufgeteilt werden, sobald neue Evidenz, ein neuer Zustand oder ein
Fehlerindikator einen zuvor irrelevanten Unterschied entscheidungsrelevant
macht.

Ein Prototyp benötigt mindestens:

```text
mass_per_class
representative identity
compression error estimate
split trigger
uncompressed audit sample
compression regret measurement
```

Exakte Entscheidungsäquivalenz darf nicht vorausgesetzt werden, wenn ihr
Nachweis bereits dieselbe vollständige Search erfordern würde, die eingespart
werden soll. Diese Richtung gehört nach eine funktionierende, unkomprimierte
M3-Baseline.

## 4. Battle Compute Bank und confidence-bounded Early Stop

Nicht jeder Turn ist gleich schwierig. Ein Gesamtbudget pro Battle könnte
Search-Arbeit von offensichtlichen Entscheidungen zu kritischen Zuständen
verschieben.

Arbeitslabel:

```text
confidence_bounded_compute_scheduler_v0
```

Mögliche ausschließlich öffentlich ableitbare Signale sind:

- Root-Value-Gap;
- Stabilität der Root-Rangfolge;
- Posterior-Entropie;
- Hidden-World-Action-Flip-Rate;
- Anzahl legaler Aktionen;
- unmittelbares Terminalrisiko;
- erwarteter Nutzen zusätzlicher Simulationen.

Für eine saubere Evaluation müssen Gesamtbudget, Zähler und Scheduler-Regeln
vorab gebunden sein. Im deterministischen Benchmark darf keine Wandzeit- oder
Hostlastentscheidung in die Work-Verteilung eingehen. Im Livepfad bleiben
Timeouts, Fallbacks und nicht verbrauchtes Budget sichtbar.

Verglichen wird gegen dasselbe Battle-Gesamtbudget, nicht nur gegen dasselbe
Budget eines einzelnen Turns. Diese Richtung ist eine spätere Effizienz-
optimierung nach einer stabilen Search-Baseline.

## 5. Tail-Risk World Sampling

Reines Posterior-Sampling untersucht häufige Welten oft und seltene Welten
selten. Eine geringe Weltmasse kann dennoch die Root-Entscheidung umdrehen oder
einen katastrophalen Verlust verursachen.

Arbeitslabel:

```text
tail_risk_world_sampler_v0
```

Zu trennen sind drei verschiedene Objekte:

```text
Posterior-Verteilung
Proposal-Sampling-Verteilung
Risk Objective
```

Eine Stichprobeneffizienz-Ablation darf seltene, wirkungsstarke Welten über ein
Proposal häufiger ziehen, muss aber korrekte Importance-Weights verwenden,
wenn weiterhin der Posterior-Erwartungswert geschätzt werden soll.

Eine echte risk-aware Ablation, etwa CVaR oder Worst-Tail-Regret, verändert
dagegen bewusst das Entscheidungsziel und benötigt eine eigene registrierte
Semantik.

Vorgeschlagener Vergleich:

```text
Posterior-Sampling
vs. impact-basiertes Proposal mit Importance-Weights
vs. explizites risk-aware Root Objective
```

Diese Richtung passt zu `OTHER` und Off-Meta-Sets, gehört aber erst nach einem
kalibrierten M3-Posterior in eine bindende Evaluation.

## 6. Lab-only Engine-Fragility-Analyse

Production Eligibility bleibt fail-closed: Eine nicht exakt qualifizierte
Capability erlaubt keine Search. Unabhängig davon kann das Lab messen, wie
empfindlich eine Entscheidung gegenüber kleinen Modellabweichungen wäre.

Arbeitslabel:

```text
mechanics_fragility_analysis_v0
```

Eine Analyse kann bekannte oder kontrolliert perturbierte Übergangsvarianten
verwenden und prüfen, ob sich dadurch Root-Rangfolge oder ausgewählte Aktion
ändern.

Mögliche Ausgaben:

```text
mechanics_fragility_score
root_action_flip_rate
minimal_transition_perturbation
capabilities_on_decision_path
fragile differential fixtures
```

Der Score ist ein Diagnoseinstrument für Differential-Corpus-Priorisierung,
Fehlererklärung und robuste Entscheidungsanalyse. Er darf niemals eine fehlende
Exact-Qualification überschreiben oder eine Produktionsausnahme erzeugen.

## 7. Robustheitszertifikat pro Entscheidung

Mehrere der vorherigen Analysen können in einem maschinenlesbaren Lab-Artefakt
zusammenlaufen.

Arbeitslabel:

```text
belief_search_robustness_certificate_v0
```

Ein Zertifikat könnte enthalten:

```text
selected safe submission
posterior mass supporting the action
root value gap
worlds or classes causing an action flip
OTHER-mass sensitivity
search stability
compression sensitivity
engine fragility
minimal public evidence needed to flip
```

Das Zertifikat verbessert nicht automatisch die Spielstärke. Es unterstützt:

- Debugging und Failure Triage;
- Strategy-Fusion-Corpus-Erzeugung;
- Vergleich von Determinization und Information-Set Search;
- Identifikation schlechter Priors und fragiler Capabilities;
- Aufbau von Belief- und Search-Puzzles;
- nachvollziehbare wissenschaftliche Berichte.

Vollständige Weltlisten und private Informationen bleiben Lab-intern. Ein
öffentlicher Decision Record dürfte später nur eine leakage-sichere Projektion
mit Digests und zusammengefassten Zählern referenzieren.

## Zusammenspiel mit OTHER-Materialisierung

Die Richtungen bilden eine mögliche Kette:

```text
ungewöhnliche mechanische oder freiwillige Aktion
→ Surprise oder Policy-Likelihood verändert das Belief
→ OTHER steigt oder bekannte Unterstützung kollabiert
→ Materializer erzeugt begrenzte neue vollständige Hypothesen
→ Tail-Risk- und Posterior-Sampling prüfen Entscheidungsfolgen
→ Robustheitszertifikat erklärt Stabilität und Action Flips
```

Diese Kette ist keine geplante monolithische Implementierung. Jeder Pfeil muss
separat abgetragen werden, damit Kalibrierungs-, Materialization-, Search- und
Effizienzgewinne nicht miteinander verwechselt werden.

## Empfohlene Forschungsreihenfolge

```text
M2:
  bestehenden seriellen Plan unverändert ausführen
  Strategy-Fusion-Corpus nur als spätere Research-Vorbereitung spezifizieren

M3:
  abstraktes Open-World OTHER
  constraint-guided Materialization als eigener Arm
  Action-Likelihood-Belief als separater Arm
  Tail-Risk-Sampling erst auf kalibriertem Posterior

nach positiver M3-Evidenz:
  Decision-Equivalent Compression
  Robustheitszertifikate und Engine-Fragility gemeinsam nutzen

Phase 2:
  Battle Compute Bank und weitere Search-Effizienzoptimierung
```

## Neuheitsdisziplin

Bayesian inverse planning, Belief Compression, adaptive MCTS, Importance
Sampling, risk-sensitive Planung, Strategy Fusion und Modellunsicherheit sind
bekannte Konzepte.

Ein möglicher BattleBelief-Beitrag läge in der kontrollierten Pokémon-
Kombination aus vollständigen Hidden Sets, explizitem `OTHER`, aktionsbasierter
Belief-Evidenz, mechanisch validierter Materialisierung,
Information-Set Search, gezielten Strategy-Fusion-Gegenbeispielen und
reproduzierbaren Robustheitsnachweisen.

Diese Note erhebt keinen First-System- oder Novelty-Claim. Ein späterer Claim
erfordert eine erneute systematische Literatur- und öffentliche Code-Suche.

## Verwandte Grundlagen

- [Finding Approximate POMDP Solutions Through Belief Compression](https://auld.aaai.org/Library/JAIR/Vol23/jair23-001.php)
- [Learning to Stop: Dynamic Simulation Monte-Carlo Tree Search](https://ojs.aaai.org/index.php/AAAI/article/view/16100)
- [Understanding the Success of Perfect Information Monte Carlo Sampling in Game Tree Search](https://ojs.aaai.org/index.php/AAAI/article/view/7562)
- [Monte Carlo Tree Search in the Presence of Transition Uncertainty](https://ojs.aaai.org/index.php/AAAI/article/view/29994)
- [Foul Play Architecture Report](https://pmariglia.github.io/posts/foul-play/)
