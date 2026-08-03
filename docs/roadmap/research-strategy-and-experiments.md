---
document_id: roadmap-research-strategy-and-experiments
title: BattleBelief Forschungsstrategie und Experimentfolge
document_type: roadmap
status: accepted
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

Dieses Planungsdokument fokussiert die Forschungsarbeit nach M1. Es definiert
keine neuen Produkt-, Safety-, Search-, Belief-, Determinismus- oder
Strength-Verträge. Bei Widerspruch gelten die akzeptierten normativen Quellen
im [Dokumentationsindex](../README.md).

## Zentrale Forschungsthese

BattleBelief untersucht, ob ein explizites Open-World-Belief über vollständige
verborgene Sets zusammen mit informationssatzkorrekter DUCT-Suche unter einem
autoritativen Showdown-Action-Safety-Gate bessere Gen-9-OU-Entscheidungen als
vorab festgelegte Heuristik-, Determinization- und Closed-World-Baselines
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
- reproduzierbaren Ablationen bei kontrolliertem Ressourcenbudget.

Neue Infrastruktur wird nur erweitert, wenn sie eine konkrete Messung,
Ablation oder freigegebene Runtime-Fähigkeit ermöglicht. Breite
Multi-Format-Abstraktionen, eine eigene vollständige Mechanikengine und große
Modelle bleiben außerhalb der zentralen These.

## Experimentfolge

### M1 abschließen: korrekter und sicherer Battlepfad

M1 beweist ausschließlich den protocol-safe Runtimepfad. Vor der
Search-Forschung müssen vollständige kontrollierte Battles, klassifizierte
Abbrüche sowie die vorhandenen Protocol- und Safety-Gates stabil sein.

M1 muss noch kein endgültiges Forschungs-Traceformat besitzen. M1.5 definiert
ein minimales versioniertes Decision-Record-Schema und erzeugt daraus
reproduzierbare Traces des bereits vorhandenen M1-Runtimepfads.

### M1.5: Measurement Harness and Baseline Registration

M1.5 ist ein kurzer Evidenz- und Planungscheckpoint, kein eigener
Runtime-Release und kein Strength-Claim. Öffentliche Doctor- und Statusangaben
bleiben bis zum nächsten freigegebenen Runtime-Meilenstein bei Phase `M1` und
der zu M1 gehörenden Paketversion.

M1.5 trennt zwei Zeitpunkte ausdrücklich:

1. **Vorab spezifizieren und registrieren:** Hypothesen, Vergleichsarme,
   Metrikverweise, Budgetprofile, Pool-Konstruktionsregeln,
   Seitenzuweisung, Schedulelogik und Stop-/Pivot-Entscheidungen werden vor
   Sichtung der zugehörigen Ergebnisse festgelegt.
2. **Nach Implementierung versiegeln:** Konkrete Code-, Daten-, Team-, Engine-,
   Prior-, Modell- und Policy-Artefakte werden validiert, gehasht und an die
   zuvor registrierten Vergleichsarme gebunden.

Damit die Bezeichnung „präregistriert“ maschinenprüfbar ist, erstellt M1.5 vor
der ersten bindenden Auswertung ein versioniertes
Experiment-Registration-/Evaluation-Arm-Schema samt validierendem
Beispielmanifest. Bis dieses Artefakt existiert, gelten Beschreibungen nur als
**vorab spezifiziert**, nicht als formal präregistriert.

M1.5 legt fest:

- die zentrale Hypothese und zugehörige Nullhypothesen;
- Evaluation-Arm-IDs und ihre zulässigen Komponenten;
- Entwicklungs-, Selection- und spätere Holdout-Konstruktionsregeln;
- Near-Duplicate-, Partitionierungs- und Öffnungsregeln für spätere konkrete
  Team-, Replay-, Gegnerpolicy- und Seedcluster-Pools;
- Deployment- und Mechanismus-Budgetprofile;
- ein minimales Decision-Record-Schema ohne Hidden-State-Leak;
- primäre und diagnostische Metriken ausschließlich durch Verweis auf deren
  normative Eigentümer; und
- Stop-/Pivot-Entscheidungen für Search, Belief und optionale Modelle.

Konkrete Poolinhalte und ihre Digests werden erst versiegelt, nachdem sie in
M3 beziehungsweise M4 erzeugt und validiert wurden. M1.5 friert deren
Konstruktions- und Trennungsregeln ein, nicht noch nicht existierende Elemente.

Der lokale Showdown-Oracle bleibt der erste technische M2-Liefergegenstand.
M1.5 legt vorher fest, welche Vergleiche er ermöglichen muss, damit die
Messinfrastruktur nicht nach Sichtung günstiger Ergebnisse angepasst wird.

### M2: Search muss die Heuristik schlagen

M2 beginnt mit Engine- und Oracle-Qualifikation. Danach wird zuerst die
kleinste reproduzierbare Determinization-Search-Baseline gebaut.

M2 enthält außerdem ein minimales Closed-World-Belief, damit der normative
Search-Vertrag einen definierten Posterior besitzt:

- ein eingefrorener Prior über vollständige Set-Hypothesen;
- Filterung und Gewichtsanpassung anhand harter öffentlicher Evidenz;
- ein normalisierter Closed-World-Posterior;
- kein `OTHER`-Bucket und keine Open-World-Hypothesenmaterialisierung; und
- keine still als Ground Truth behandelten imputierten Informationen.

Dieses minimale Belief ist Infrastruktur für den M2-Vergleich, nicht der
vollständige M3-Forschungsbeitrag. M3 erweitert es um kalibrierte Priors,
zensierte Replay-Evidenz, positive Open-World-Masse und kontrollierte
Hypothesenmaterialisierung.

Search gilt nur dann als wissenschaftlich nützlich, wenn sie die M1-Heuristik
in der registrierten Entwicklungsbewertung verbessert, ohne Safety-,
Determinismus- oder Runtime-Grenzen zu schwächen.

### M3: Open-World-Belief muss Search messbar verbessern

M3 prüft nicht nur Belief-Kalibrierung, sondern auch Entscheidungsnutzen. Das
Open-World-Belief wird gegen das minimale M2-Closed-World-Belief und gegen
einfachere vollständige Set-Priors abgetragen. Verbesserte Belief-Metriken
werden getrennt von Verbesserungen in Search-Qualität oder Battle-Ergebnis
berichtet.

Eine einfache Modellbaseline ist in M3 optional und darf erst nach einem
bestandenen Search- und Belief-Zwischengate eingeführt werden. Sie ist kein
Pflichtliefergegenstand des Belief-Gates.

### M4: Kandidat gegen starke reproduzierbare Baselines

Vor der Kandidatenauswahl müssen die stärksten intern reproduzierbaren
Varianten und mindestens eine starke externe oder öffentlich reproduzierbare
Baseline verglichen werden. Ein öffentlicher Wettbewerb oder ein externes
Leaderboard ist erwünscht, ersetzt aber nicht die manifestierte interne
Evaluation. Externe Ergebnisse werden nur als gleichermaßen kontrollierter
Vergleich bezeichnet, wenn Ressourcen, Teams, Regeln und Harness tatsächlich
vergleichbar sind.

### M5 bleibt das Strength-Gate

M5 bleibt unverändert der einzige interne Strength-qualified-MVP-Claim. Die
Schwellen und Guardrails stehen ausschließlich in
[M5 Strength Qualification](../evaluation/m5-strength-qualification.md).

## Evaluation-Arms und Maschinenidentität

Die folgenden Namen sind **Evaluation-Arm-IDs**, nicht automatisch
`algorithm_id`-Werte eines Search-Manifests:

| Arm-ID | Zweck |
|---|---|
| `heuristic_v0` | deterministische M1-Policy ohne Search oder Belief |
| `determinization_search_v0` | einfache Evaluation-only Search über gesampelte vollständige Welten |
| `information_set_duct_closed_world_v0` | `information_set_duct_v0` mit minimalem Closed-World-Belief |
| `information_set_duct_open_world_v0` | `information_set_duct_v0` mit explizitem Open-World-Belief |
| `model_or_hybrid_v0` | optionaler Kandidat nur nach positivem vorherigem Gate |

Für beide Information-Set-Arms bleibt die Search-Algorithmus-ID
`information_set_duct_v0`. Der Unterschied liegt in `belief_mode`, Prior- und
Belief-Digests sowie den weiteren Evaluation-Arm-Feldern.

`determinization_search_v0` ist zunächst ausschließlich eine
Evaluation-Baseline. Vor ihrer bindenden Verwendung benötigt sie eine klar
versionierte Algorithmusbeschreibung und eine passende maschinenlesbare
Ausführungsidentität; sie ersetzt nicht still den akzeptierten Search-v0-
Produktionsvertrag.

Das in M1.5 einzuführende Evaluation-Arm-Manifest bindet mindestens:

```text
arm_id
policy_kind
search_algorithm_id
belief_mode
search_manifest_digest
prior_digest
model_digest
fallback_policy_digest
team_pool_digest
opponent_pool_digest
budget_profile_digest
```

Nicht anwendbare Felder werden durch das zukünftige Schema explizit als
nullable oder armabhängig geregelt; freie, mehrdeutige Platzhalter sind nicht
zulässig.

## Kernvergleiche

### Search-Nutzen

```text
heuristic_v0
gegen
determinization_search_v0
```

Dieser Vergleich prüft, ob zusätzliche Planung im kontrollierten Battleprofil
überhaupt einen messbaren Nutzen erzeugt.

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
vorab spezifizierte Ressource reduzieren.

## Zwei Budgetansichten pro Kernvergleich

„Dasselbe Budget“ besitzt je nach Forschungsfrage zwei getrennte Bedeutungen.
Bindende Vergleiche berichten beide Ansichten, soweit sie für die beteiligten
Arms anwendbar sind.

### Deployment Utility

```text
gleiches maximales End-to-End-Wandzeit- und CPU-Budget
```

Diese Ansicht misst den Nutzen des vollständigen Systems im öffentlichen
Runtimeprofil. Eine schnelle Heuristik muss ungenutzte Zeit nicht künstlich
verbrauchen. Timeouts, Fallbacks und Belief-Aufwand bleiben enthalten.

### Mechanism Ablation

```text
gleiche Search-Arbeit, etwa Transitionen, Simulationen oder Knoten
+ separat berichteter Belief-, Orchestrierungs- und Gesamtaufwand
```

Diese Ansicht prüft, ob eine Methode bessere Entscheidungen pro Search-Arbeit
erzeugt. Beim Closed-/Open-World-Vergleich verhindert sie, dass eine geringere
Search-Tiefe unbemerkt mit der Belief-Methode vermischt wird.

Für eine Heuristik ohne Search-Arbeit ist die Mechanismusansicht nicht als
„gleiche Simulationen“ interpretierbar; dort bleibt die Deployment-Ansicht der
primäre direkte Systemvergleich.

## Mess- und Vergleichsdisziplin

Jeder bindende Vergleich verwendet:

- nach den vorab spezifizierten Regeln erzeugte Team- und Gegnerpolicy-Pools;
- manifestierte Seitenzuweisung und Scheduleblöcke;
- identische Legal-Action- und Abbruchregeln;
- getrennte Search-, Welt-, Policy- und Simulatorseeds;
- die registrierte Deployment- und, soweit anwendbar, Mechanismus-
  Budgetansicht;
- vollständige Fallzahlen einschließlich Fallback, Timeout und Crash gemäß
  den zuständigen Contracts;
- Decision Rows und Artefaktdigests; und
- eine vorab festgelegte Auswertung ohne nachträgliche Auswahl günstiger
  Matchups.

Die konkrete Bedeutung der Metriken, Zielpopulation, Pooltrennung, Statistik,
Laufzeit und Strength-Schwellen wird hier nicht wiederholt. Sie bleibt in den
jeweils akzeptierten normativen Dokumenten.

## Minimales Decision Record aus M1.5

Das M1.5-Schema zeichnet mindestens auf:

```text
request_identity
observed_state_digest
safe_submission_set_digest
selected_submission
submission_provenance
fallback_or_error_class
policy_or_arm_id
runtime_and_contract_digests
```

Es enthält keine privaten Gegnerfelder aus Showdown-Requests und keinen
vollständigen gesampelten Hidden State. Eine spätere Search-Decision-Row kann
dieses Format versioniert erweitern, darf seine öffentliche/private Grenze
aber nicht still verändern.

## Stop- und Pivot-Kriterien

### Search vereinfachen oder neu ausrichten, wenn

- die registrierte Search-Variante die Heuristik in keiner passenden
  Budgetansicht reproduzierbar verbessert;
- Engine-Bias oder Zustandsfragmentierung den Vergleich dominiert;
- das öffentliche CPU-Laufzeitprofil trotz gezielter Optimierung nicht
  erreichbar ist; oder
- eine einfachere Root-Sampling- oder Determinization-Methode praktisch
  gleichwertig ist.

### Open-World-Belief vereinfachen oder neu ausrichten, wenn

- es die registrierten Belief-Metriken nicht verbessert;
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

Ein Pivot, der einer akzeptierten ADR oder einem normativen Contract
widerspricht, ist zunächst ausschließlich ein Forschungsbefund. Bevor er den
Produktionspfad oder eine verbindliche Bedeutung ändert, benötigt er eine
explizite Decision-/ADR-Prüfung sowie eine versionierte Änderung aller
betroffenen normativen Contracts. Die ursprüngliche Registrierung und die
negative Evidenz bleiben erhalten.

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

| Variante | Budgetansicht | Battle-Metrik | Belief-Metrik | p95-Zeit | Fallback/Safety |
|---|---|---:|---:|---:|---:|
| Heuristik | Deployment | aus Manifest | nicht anwendbar | aus Manifest | aus Manifest |
| Determinization | Deployment/Mechanism | aus Manifest | aus Manifest | aus Manifest | aus Manifest |
| IS-DUCT Closed World | Deployment/Mechanism | aus Manifest | aus Manifest | aus Manifest | aus Manifest |
| IS-DUCT Open World | Deployment/Mechanism | aus Manifest | aus Manifest | aus Manifest | aus Manifest |

Bis belastbare Resultate existieren, bleiben diese Felder unbefüllt und es
wird kein Leistungs- oder State-of-the-Art-Claim formuliert.
