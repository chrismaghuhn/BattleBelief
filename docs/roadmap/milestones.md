---
document_id: roadmap-milestones
title: Projektroadmap und Meilensteine
document_type: roadmap
status: accepted
normative: false
version: 6
applies_to:
  - project
  - gen9ou
effective_from: 2026-08-03
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-03
---

# Projektroadmap und Meilensteine

Die Roadmap ordnet Arbeit. Verbindliche Schwellen und Bedeutungen stehen in den
verlinkten Contracts. Die experimentelle Reihenfolge, Evaluation-Arms und
Stop-/Pivot-Entscheidungen werden in der
[Forschungsstrategie](research-strategy-and-experiments.md) erklärt.

## M0 – Öffentliche Projektgrundlage

Lieferumfang:

- öffentliches Apache-2.0-Repository;
- aktuelle Contracts, ADRs, Schemas und Archivnachweis;
- GitHub-Rulesets, CI und Security;
- drei separat installierbare, gemeinsam versionierte Python-Pakete;
- öffentliche Core- und Runtime-Schnittstellen;
- Transfer-Audit-Inventar.

Gate:

- alle M0-Installations-Smokes aus
  [`architecture-dependency-matrix`](../architecture/dependency-matrix.md);
- alle Paketgrenzen aus
  [`architecture-code-boundaries`](../architecture/code-boundaries.md)
  maschinell erzwungen;
- `pr-gate` und Dokumentationsgates grün;
- keine ungeklärte Herkunft, Secrets oder großen Artefakte.

## M1 – Protocol-safe Prototype

Lieferumfang:

- Showdown-Verbindung und Authentifizierung;
- kanonische Events und Reducer;
- autoritative Legal Actions aus Request und `rqid`;
- Fixed-Team-Loader;
- kampffähige Legal-/Heuristikpolicy und entsprechender Runtime-Modus;
- klassifizierte Abbruchpfade.

Gate: Die Evidence- und Safety-Anforderungen aus
[`contract-protocol-state`](../contracts/protocol-state.md) und
[`contract-legal-action-safety`](../contracts/legal-action-safety.md) bestehen
in der lokalen Release-Smoke-Suite. Ein vollständiger direkter Battlepfad muss
kontrolliert wiederholbar sein; das erzeugt weiterhin keinen Strength-Claim.

## M1.5 – Measurement Harness and Baseline Registration

M1.5 ist ein kurzer Forschungs- und Evidenzcheckpoint zwischen dem sicheren
Runtimepfad und umfangreicher Search-Implementierung. Es ist kein zusätzliches
Runtime-Release und kein Strength-Claim. Doctor- und Statusausgaben bleiben bis
zum nächsten freigegebenen Runtime-Meilenstein bei Phase `M1` und der zu M1
gehörenden Paketversion.

Lieferumfang:

- vorab spezifizierte zentrale Hypothese und Kernvergleiche;
- ein versioniertes Experiment-Registration-/Evaluation-Arm-Schema mit
  validierendem Beispielmanifest;
- Evaluation-Arm-IDs und eine Ablationsreihenfolge, getrennt von Search-
  Algorithmus-IDs;
- vorab festgelegte Entwicklungs-, Selection- und spätere
  Holdout-Konstruktionsregeln;
- Near-Duplicate-, Partitionierungs-, Seiten- und Schedulelogik für spätere
  konkrete Team-, Replay-, Gegnerpolicy- und Seedcluster-Pools;
- getrennte Deployment- und Mechanismus-Budgetprofile;
- ein minimales versioniertes Decision-Record-Schema ohne Hidden-State-Leak;
- Verweise auf die normativen Metrik-, Statistik-, Zielpopulations-, Pool- und
  Determinismusquellen; und
- dokumentierte Stop-/Pivot-Kriterien für Search, Belief und optionale
  Modelle.

Gate: Die Mess-, Registrierungs- und Armdefinitionen sind maschinenprüfbar; aus
dem M1-Runtimepfad erzeugte Decision Records sind reproduzierbar; konkrete
noch nicht existierende Poolinhalte werden nicht vorgetäuscht; und kein
Selection- oder Release-Holdout wurde vorzeitig geöffnet. Konkrete Pool- und
Artefaktdigests werden erst nach Erzeugung und Validierung versiegelt. Der
lokale Showdown-Oracle bleibt der erste technische M2-Liefergegenstand.

## M2 – Engine-qualified Search Prototype

Lieferumfang:

- lokaler Showdown-Oracle;
- Lab-Oracle-Profil und lokaler Oracle-Smoke;
- geprüftes Gen9-`poke-engine`-Artefakt;
- installierbares Runtime-`search`-Extra und echter Gen9-Sentinel;
- Capability-Manifest und Eligibility-Gate;
- Differentialtests;
- kleinste reproduzierbare Determinization-Search-Baseline als eigener
  Evaluation-Arm;
- Evaluation-only Closed-World-Weltverteilung mit eingefrorenem vollständigem
  Set-Prior, harter öffentlicher Evidenzfilterung und normalisierter
  Verteilung;
- `information_set_duct_v0` auf dieser Closed-World-Weltverteilung;
- deterministic-benchmark- und live-anytime-Betriebsmodus.

Die M2-Weltverteilung ist keine Implementierung des produktiven
BattleBelief-Belief-Subsystems und beansprucht keine Erfüllung des
Open-World-Belief-Vertrags. Sie besitzt keinen `OTHER`-Bucket, keine
Open-World-Materialisierung und keine still als Ground Truth behandelten
imputierten Informationen. Sie stellt ausschließlich die vollständige
Weltverteilung für kontrollierte Search-Baselines bereit. Das vertragliche
Open-World-Belief folgt in M3.

Gate: Engine-, Search- und Determinismus-Contracts bestehen im definierten
Corpus; unbekannte oder nicht unterstützte Capabilities führen fail-closed zum
Fallback. Search wird gegen die M1-Heuristik und die Determinization-Baseline
unter den registrierten Budgetansichten geprüft:

- gleiches maximales End-to-End-Wandzeit- und CPU-Budget für Deployment
  Utility; und
- soweit anwendbar gleiche Search-Arbeit mit separat berichtetem
  Weltverteilungs-/Belief- und Gesamtaufwand für Mechanismus-Ablationen.

Ein ausbleibender reproduzierbarer Nutzen führt zu dem vorab festgelegten
Forschungsbefund und Pivot-Prozess statt zur automatischen Erweiterung der
Search-Komplexität. Ein Pivot, der dem akzeptierten Search-Vertrag
widerspricht, erfordert vor einer Produktionsänderung eine neue Decision-/ADR-
Prüfung und eine versionierte Contract-Änderung. Die Runtime-Grenzen aus
[`evaluation-m5-strength-qualification`](../evaluation/m5-strength-qualification.md)
werden auf der Referenzhardware geprüft; dies erzeugt noch keinen
Strength-Claim.

## M3 – Belief- und Forschungsbaseline

Lieferumfang:

- versionierter Meta-Snapshot;
- Lab-Dataset-Profil und Replay-/Dataset-Ingestion-Smoke;
- produktives, vertraglich konformes Belief über vollständige Set-Hypothesen
  mit kalibrierten Priors;
- positive Open-World-Masse, kontrollierte Hypothesenmaterialisierung und
  Ereignisprotokollierung;
- Replaypipeline;
- Heuristik-, Determinization-, Evaluation-only-Closed-World- und
  Open-World-Search-Arms;
- optionale einfache Modellbaseline ausschließlich nach bestandenem Search-
  und Belief-Zwischengate;
- getrennte Entwicklungs- und Evaluationsartefakte;
- nach den in M1.5 registrierten Regeln erzeugte und logisch getrennte Team-,
  Replay-, Gegnerpolicy- und Seedcluster-Pools;
- versiegelbare Hero-Teams und Gegnerpolicy-Mischung.

Gate: Hidden-Set-NLL verbessert sich auf evidenzgesicherten
Ground-Truth-Fällen; Reveal-Likelihood verbessert sich separat auf zensierten
Replays; Kalibrierung, Coverage und Open-World-Verhalten bestehen ihre
vorregistrierten Guardrails. Zusätzlich werden die M2-Evaluation-only-
Closed-World-Weltverteilung gegen das M3-Open-World-Belief und Belief-Metrik
gegen tatsächlichen Entscheidungsnutzen getrennt abgetragen. Die Deployment-
und Mechanismus-Budgetansichten verhindern, dass Belief-Aufwand und geringere
Search-Tiefe still vermischt werden.

Eine Kalibrierungsverbesserung ohne Search- oder Battle-Nutzen wird als solche
berichtet und löst den festgelegten Pivot-Prozess aus. Eine Änderung des
normativen `OTHER`-Vertrags benötigt zuvor eine Decision-/ADR-Prüfung und eine
versionierte Contract-Änderung. Die normativen Definitionen und
Entscheidungsregeln stehen ausschließlich in
[`evaluation-metrics`](../evaluation/metrics.md). Engine-Bias,
Search-Stabilität und Clusterstruktur sind messbar. Das ist keine
Releaseevidenz.

Großes GPU-Training beginnt erst nach diesem Gate.

## M4 – MVP-Kandidat

Lieferumfang:

- optional Replay-BC, Search Teacher, Population Self-Play und Hybridmodell;
- Pflichtablation Heuristik, Determinization Search, Information-Set Search,
  Evaluation-only Closed World und vertragliches Open World sowie Model und
  Hybrid nur soweit tatsächlich implementiert;
- Vergleich mit mindestens einer starken externen oder öffentlich
  reproduzierbaren Baseline;
- klare Trennung zwischen externem Kontextvergleich und internem
  ressourcenkontrolliertem Harness-Vergleich;
- formale Auswahl genau eines Kandidaten;
- anschließend Power Pilot und endgültiger Stichprobenplan.

Gate: Einer der in
[`training-pipeline-and-selection`](../training/pipeline-and-selection.md)
definierten Auswahlwege besteht; alle Artefakte sind versiegelt und der
Release-Holdout bleibt ungeöffnet. Ein öffentliches Leaderboard oder ein
Wettbewerb ist erwünscht, ersetzt jedoch nicht die manifestierte interne
Evaluation.

## M5 – Strength-qualified MVP

Lieferumfang:

- aktuelles Gen9 OU auf festem Ruleset-Snapshot;
- versiegelte Hero-Teams;
- Information-Set DUCT;
- optional evidenzbasiertes Modell;
- Capability-/Safety-Fallback;
- öffentlicher CPU-Runtime-Pfad.

Gate: Der vollständige
[`evaluation-m5-strength-qualification`](../evaluation/m5-strength-qualification.md)
ist bestanden und der unveränderliche Claim wurde nach dem Release-Runbook
erstellt. Nur M5 heißt MVP.

## M6 – Externe Human-Validierung

Lieferumfang und Gate stehen in
[`evaluation-m6-human-validation`](../evaluation/m6-human-validation.md). M6
ist kein rückwirkender Bestandteil von M5.

## Phase 2 – Optimierung

- größere Modelle;
- breiteres Population Self-Play;
- Regret-Matching-/Exp3-Ablation;
- selektiverer oder tieferer Search;
- optionale Cross-Battle-Priors;
- Inferenzoptimierung und Wheels.

Jede zusätzliche Schicht muss Stärke erhöhen oder bei formaler
Nichtunterlegenheit die vorab definierte Ressource senken. Komponenten, die
die Stop-/Pivot-Kriterien der Forschungsstrategie auslösen, werden zuerst
vereinfacht oder neu ausgerichtet, statt parallel weiter ausgebaut zu werden.
Normative Produktionsentscheidungen werden dabei nicht ohne versionierte
Decision- und Contract-Änderung ersetzt.

## Phase 3 – Offline-Team-Building

Eigener Generator und teamdisjunkter Holdout bei fester Battle-Policy nach
[`team-contract`](../teams/team-contract.md). Kein Teamwechsel innerhalb eines
Battles und keine Vermischung von Team- und Policyverbesserung.

## Phase 4 – Weitere Singles-Formate

Ein Format nach dem anderen, jeweils mit neuem Ruleset-, Zielpopulations-,
Capability- und Strength-Claim. Doubles und VGC bleiben ausgeschlossen.
