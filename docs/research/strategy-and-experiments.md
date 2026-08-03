---
document_id: research-strategy-and-experiments
title: BattleBelief Forschungsstrategie und Experimentfolge
document_type: research
status: proposed
normative: false
version: 1
applies_to:
  - project
  - research
  - gen9ou
effective_from: 2026-08-03
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-03
---

# BattleBelief Forschungsstrategie und Experimentfolge

Dieses Dokument fokussiert die Forschungsarbeit nach M1. Es definiert keine
neuen Produkt-, Safety-, Search-, Determinismus- oder Strength-Verträge. Bei
Widerspruch gelten die akzeptierten normativen Quellen im
[Dokumentationsindex](../README.md).

## Zentrale Forschungsthese

BattleBelief untersucht, ob ein explizites Open-World-Belief über vollständige
verborgene Sets zusammen mit informationssatzkorrekter DUCT-Suche unter einem
autoritativen Showdown-Action-Safety-Gate bessere Gen-9-OU-Entscheidungen
liefert.

Die These wird unter festen, manifestierten CPU-, Daten-, Team-, Gegnerpolicy-
und Reproduzierbarkeitsbedingungen geprüft. Architekturvollständigkeit,
Codeumfang oder ein grüner `main` sind keine Evidenz für diese These.

## Forschungsgegenstand und Infrastruktur

Der eigene Showdown-Adapter, der kanonische Observed State, Request-
Reconciliation, Provenienz, CI und Manifestierung sind notwendige
Infrastruktur. Der primäre wissenschaftliche Differentiator liegt in:

- vollständigen Set-Hypothesen statt künstlich kombinierten Marginalen;
- expliziter Open-World-Masse und kontrollierter Hypothesenmaterialisierung;
- nach Informationszustand geschlüsselter Suche;
- sicherer Auswahl ausschließlich aus der aktuellen autoritativen
  Aktionsmenge; und
- reproduzierbaren Ablationen bei gleichem Ressourcenbudget.

Neue Infrastruktur wird nur erweitert, wenn sie eine konkrete Messung,
Ablation oder freigegebene Runtime-Fähigkeit ermöglicht. Breite
Multi-Format-Abstraktionen, eine eigene vollständige Mechanikengine und große
Modelle bleiben außerhalb der zentralen These.

## Experimentfolge

### M1 abschließen: korrekter und sicherer Battlepfad

M1 beweist ausschließlich den protocol-safe Runtimepfad. Vor der
Search-Forschung müssen vollständige kontrollierte Battles, klassifizierte
Abbrüche, Decision Traces und die vorhandenen Protocol- und Safety-Gates
stabil sein.

### M1.5: Measurement Harness and Baseline Freeze

M1.5 ist ein kurzer Evidenz- und Planungscheckpoint, kein neuer Strength-Claim.
Er friert vor umfangreicher Search- oder Belief-Implementierung ein:

- die zentrale Hypothese und die zugehörigen Nullhypothesen;
- Entwicklungs-, Selection- und spätere Holdout-Grenzen;
- Team-, Gegnerpolicy- und Seitenzuweisungspläne;
- CPU-/Arbeitsbudgets und Laufzeitprofile;
- Baseline-Identitäten, Manifestfelder und Decision-Trace-Ausgaben;
- primäre und diagnostische Metriken durch Verweis auf deren normative
  Eigentümer; und
- Stop-/Pivot-Entscheidungen für Search, Belief und optionale Modelle.

Der lokale Showdown-Oracle bleibt der erste technische M2-Liefergegenstand.
M1.5 legt vorher fest, welche Vergleiche er ermöglichen muss, damit die
Messinfrastruktur nicht nach Sichtung günstiger Ergebnisse angepasst wird.

### M2: Search muss die Heuristik schlagen

M2 beginnt mit Engine- und Oracle-Qualifikation. Danach wird zuerst die
kleinste reproduzierbare Search-Baseline gebaut. Search gilt nur dann als
wissenschaftlich nützlich, wenn sie bei gleichem manifestiertem Budget die
M1-Heuristik in der vorregistrierten Entwicklungsbewertung verbessert, ohne
Safety-, Determinismus- oder Runtime-Grenzen zu schwächen.

### M3: Belief muss Search messbar verbessern

M3 prüft nicht nur Belief-Kalibrierung, sondern auch Entscheidungsnutzen. Das
Open-World-Belief wird gegen eine geschlossene, geglättete Baseline und gegen
einfachere Set-Priors abgetragen. Verbesserte Belief-Metriken werden getrennt
von Verbesserungen in Search-Qualität oder Battle-Ergebnis berichtet.

### M4: Kandidat gegen starke reproduzierbare Baselines

Vor der Kandidatenauswahl müssen die stärksten intern reproduzierbaren
Varianten und mindestens eine starke externe oder öffentlich reproduzierbare
Baseline verglichen werden. Ein öffentlicher Wettbewerb oder ein externes
Leaderboard ist erwünscht, ersetzt aber nicht die manifestierte interne
Evaluation.

### M5 bleibt das Strength-Gate

M5 bleibt unverändert der einzige interne Strength-qualified-MVP-Claim. Die
Schwellen und Guardrails stehen ausschließlich in
[M5 Strength Qualification](../evaluation/m5-strength-qualification.md).

## Baseline-Leiter

Jede Stufe verändert möglichst nur eine zentrale Annahme:

| ID | Zweck |
|---|---|
| `heuristic_v0` | deterministische M1-Policy ohne Search oder Belief |
| `determinization_search_v0` | einfache Search über gesampelte vollständige Welten |
| `information_set_duct_closed_world_v0` | Information-Set DUCT mit geschlossenem Set-Prior |
| `information_set_duct_open_world_v0` | Information-Set DUCT mit explizitem Open-World-Belief |
| `model_or_hybrid_v0` | optionaler Kandidat nur nach positivem vorherigem Gate |

Eine Variante darf erst als neue Baseline eingefroren werden, wenn Code,
Manifest, Daten-, Engine- und Teamdigests sowie die zugehörige
Validierung vollständig reproduzierbar sind.

## Kernvergleiche

### Search-Nutzen

```text
heuristic_v0
gegen
determinization_search_v0
```

Dieser Vergleich prüft, ob zusätzliche Planung unter demselben kontrollierten
Battle- und Ressourcenprofil überhaupt einen messbaren Nutzen erzeugt.

### Information-Set-Nutzen

```text
determinization_search_v0
gegen
information_set_duct_closed_world_v0
```

Dieser Vergleich isoliert die Informationssatzbehandlung von der bloßen
Verwendung gesampelter vollständiger Welten.

### Open-World-Nutzen

```text
information_set_duct_closed_world_v0
gegen
information_set_duct_open_world_v0
```

Dieser Vergleich prüft Kalibrierung, Coverage, Open-World-Ereignisse,
Search-Qualität, Laufzeit und Battle-Ergebnis getrennt.

### Modellnutzen

Ein Modell- oder Hybridkandidat wird erst eingeführt, nachdem Search und
Belief stabile Baselines besitzen. Das Modell muss entweder messbar bessere
Entscheidungen liefern oder bei formaler Nichtunterlegenheit eine
vorregistrierte Ressource reduzieren.

## Mess- und Vergleichsdisziplin

Jeder bindende Vergleich verwendet:

- vorab fixierte Team- und Gegnerpolicy-Pools;
- manifestierte Seitenzuweisung und Scheduleblöcke;
- identische Legal-Action- und Abbruchregeln;
- getrennte Search-, Welt-, Policy- und Simulatorseeds;
- dasselbe Budgetprofil innerhalb eines Paarvergleichs;
- vollständige Fallzahlen einschließlich Fallback, Timeout und Crash gemäß
  den zuständigen Contracts;
- Decision Rows und Artefaktdigests; und
- eine vorab festgelegte Auswertung ohne nachträgliche Auswahl günstiger
  Matchups.

Die konkrete Bedeutung der Metriken, Zielpopulation, Pooltrennung,
Statistik, Laufzeit und Strength-Schwellen wird hier nicht wiederholt. Sie
bleibt in den jeweils akzeptierten normativen Dokumenten.

## Stop- und Pivot-Kriterien

### Search vereinfachen oder neu ausrichten, wenn

- die vorregistrierte Search-Variante die Heuristik bei gleichem Budget nicht
  reproduzierbar verbessert;
- Engine-Bias oder Zustandsfragmentierung den Vergleich dominiert;
- das öffentliche CPU-Laufzeitprofil trotz gezielter Optimierung nicht
  erreichbar ist; oder
- eine einfachere Root-Sampling- oder Determinization-Methode praktisch
  gleichwertig ist.

### Open-World-Belief vereinfachen oder neu ausrichten, wenn

- es die vorregistrierten Belief-Metriken nicht verbessert;
- es Kalibrierung verbessert, aber keinen nachweisbaren Entscheidungsnutzen
  erzeugt;
- seine Rechenkosten die Search-Tiefe stärker reduzieren als der zusätzliche
  Informationsgewinn kompensiert; oder
- eine einfachere geglättete Closed-World-Baseline gleichwertig bleibt.

### Modelle verschieben oder verwerfen, wenn

- Search und Belief noch keine stabilen Baselines besitzen;
- der Modellgewinn nach kontrollierter Ablation verschwindet;
- Provenienz, Reproduzierbarkeit oder öffentliche CPU-Nutzung nicht
  gewährleistet werden kann; oder
- derselbe Nutzen mit einer einfacheren Komponente erreicht wird.

Ein Pivot ist kein negativer Projektausgang. Ein sauberer, reproduzierbarer
Nullbefund ist verwertbare Forschung und wird ohne nachträgliche Änderung der
Fragestellung berichtet.

## Öffentliche Positionierung

Die angestrebte Positionierung lautet:

> A protocol-safe, reproducible, open-world information-set search agent for
> competitive Pokémon Singles.

Öffentliche Kommunikation trennt strikt:

- implementierte technische Fähigkeiten;
- interne Forschungsresultate;
- externe Benchmarkresultate;
- methodische Beiträge;
- Effizienz- oder Safety-Claims; und
- einen vollständigen Strength-Claim.

Ein State-of-the-Art-Claim benötigt einen klar benannten Vergleichsbereich,
starke relevante Baselines, gleiche Ressourcen- und Evaluationsbedingungen
sowie veröffentlichte Evidenz. Eine einzigartige Architektur oder einzelne
erfolgreiche Battles reichen dafür nicht aus.

## Ergebnisdarstellung

Sobald Search- und Belief-Experimente vorliegen, soll die öffentliche
Dokumentation mindestens eine kompakte Ablationstabelle enthalten:

| Variante | Battle-Metrik | Belief-Metrik | p95-Zeit | Fallback/Safety |
|---|---:|---:|---:|---:|
| Heuristik | aus Manifest | nicht anwendbar | aus Manifest | aus Manifest |
| Determinization | aus Manifest | aus Manifest | aus Manifest | aus Manifest |
| IS-DUCT Closed World | aus Manifest | aus Manifest | aus Manifest | aus Manifest |
| IS-DUCT Open World | aus Manifest | aus Manifest | aus Manifest | aus Manifest |

Bis belastbare Resultate existieren, bleiben diese Felder unbefüllt und es
wird kein Leistungs- oder State-of-the-Art-Claim formuliert.
