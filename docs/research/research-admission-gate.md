---
document_id: research-admission-gate
title: Research Admission Gate
document_type: research
status: proposed
normative: false
version: 1
applies_to:
  - project
  - research
  - gen9ou
effective_from: 2026-08-05
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-05
---

# Research Admission Gate

Diese Research Note beschreibt einen allgemeinen Planungsfilter gegen
Overengineering. Sie ist keine normative Quelle und ändert weder Roadmap,
Contracts, Registrierungen noch den seriellen M2-Plan.

Eine technisch interessante Idee darf dokumentiert bleiben, ohne automatisch
zu einem Meilenstein-Liefergegenstand oder Implementierungstask zu werden.

## Vier Pflichtfragen

Eine neue Komponente wird erst in eine Implementierungsroadmap aufgenommen,
wenn vorab vier Fragen belastbar beantwortet sind:

1. **Hypothese:** Welche bereits benannte Forschungs- oder Systemhypothese
   testet die Komponente?
2. **Einfacher Vergleichsarm:** Gegen welchen möglichst einfachen bestehenden
   oder separat zu registrierenden Arm wird ihr Beitrag isoliert verglichen?
3. **Entscheidungsmetrik:** Welche vorab festgelegte Metrik und welche
   Stop-/Pivot-Regel entscheiden, ob die Komponente beibehalten, vereinfacht
   oder entfernt wird?
4. **Ressourcenbudget:** Welches Daten-, CPU-, Wandzeit-, Speicher- und
   Implementierungskomplexitätsbudget darf sie beanspruchen?

Kann eine dieser Fragen nicht belastbar beantwortet werden, bleibt die Idee
Research. Sie wird weder als Meilenstein-Liefergegenstand noch als
Implementierungstask eingeplant.

## Mindestinhalt einer Zulassung

Eine spätere Zulassungsentscheidung sollte mindestens binden:

```text
research_question
hypothesis_id oder eindeutige Hypothesenreferenz
simple_comparator_arm
mechanism_under_test
primary_decision_metric
required_guardrails
stop_or_pivot_rule
work_cpu_walltime_memory_budget
allowed_data_and_pool_scope
implementation_complexity_boundary
provenance_and_seed_identity
```

Arbeitslabels in Research Notes sind keine registrierten Algorithmus- oder
Evaluation-Arm-IDs. Eine Registrierung erfolgt erst in der dafür zuständigen
normativen oder manifestierten Quelle.

## Isolierbarkeit

Eine Komponente ist noch nicht zulassungsreif, wenn ihr Nutzen nur zusammen mit
mehreren gleichzeitig eingeführten Mechanismen gemessen werden kann.

Beispiel:

```text
nicht sauber isolierbar:
Materialization + neue Priors + neuer Search + neues Budget
gegen alte Heuristik

sauberer:
abstraktes OTHER
gegen
abstraktes OTHER + Materialization
bei gleicher Search-, Prior- und Budgetsemantik
```

Eine spätere Kombination darf erst geprüft werden, nachdem die einzelnen
Mechanismen eigene Ablationen und technische Guardrails besitzen.

## Entscheidungsmetrik und Guardrails

Eine neue Komponente benötigt genau eine vorab benannte primäre
Behalten-/Entfernen-Entscheidung. Diagnostische Metriken erklären das Ergebnis,
ersetzen diese Entscheidung aber nicht.

Eine Komponente wird nicht allein deshalb behalten, weil:

- ihre interne Metrik besser aussieht;
- sie mehr Code oder Architekturvollständigkeit erzeugt;
- ein einzelnes Beispiel beeindruckend ist;
- sie nur ohne gleiches Ressourcenbudget gewinnt;
- ihr negativer Effekt durch eine andere gleichzeitig geänderte Komponente
  verdeckt wird.

Safety-, Leakage-, Determinismus-, Provenienz- und Pool-Guardrails bleiben
harte Voraussetzungen. Ein positiver Primärwert darf einen verletzten Guardrail
nicht kompensieren.

## Budgetdisziplin

Das Budget umfasst nicht nur Search-Transitionen. Je nach Komponente gehören
mindestens dazu:

```text
CPU work
wall time
RAM und Artefaktgröße
Daten- und Labelbedarf
Start- und Ladezeit
Belief-, Materialization- und Orchestrierungsaufwand
Implementierungs- und Wartungskomplexität
zusätzliche CI- und Plattformkosten
```

Ein Vergleich muss klar angeben, ob er Deployment Utility oder eine
Mechanismus-Ablation misst. Nicht sichtbare Vorarbeit darf nicht aus dem Budget
verschwinden.

## Vorläufige Anwendung auf die aktuellen Research-Richtungen

Die folgende Tabelle ist eine Planungsorientierung, keine Registrierung:

| Richtung | Hypothese | Einfacher Arm | Primäre Entscheidung | Budgetgrenze |
|---|---|---|---|---|
| `OTHER`-Materialisierung | Konkrete neue Hypothesen verbessern Entscheidungen gegenüber abstraktem `OTHER`. | Open World mit abstraktem `OTHER`, ohne Materialisierung | Decision Regret oder Action Recovery bei bestandenen Belief-/Safety-Guardrails | festes Materialization- plus Search-Work-Budget |
| Action-Likelihood-Belief | Gegneraktionen liefern zusätzliche kalibrierte Set-Evidenz. | identisches Belief ohne Action Likelihood | Hidden-Set-Kalibrierung plus separat gemessener Entscheidungsnutzen | festes Update-/Inferenzbudget, battlelokal |
| Strategy-Fusion-Corpus | Information-Set DUCT behebt definierte Fehler getrennter Determinization. | Determinization Search | Information-Set Recovery oder Robust Action Regret | gleiche Search-Arbeit und identische Welten |
| Tail-Risk Sampling | Seltene Action-Flip-Welten werden bei gleichem Ziel effizienter erfasst. | reines Posterior-Sampling | Regret oder Action-Flip-Erkennung bei gleichem Work-Budget | gleiche Transitionen; Proposal und Objective getrennt |
| Decision-Equivalent Compression | Kompression erhält Entscheidungsqualität bei weniger Ressourcen. | unkomprimiertes Belief/Search | formale Nichtunterlegenheit plus Ressourcenreduktion | maximaler zulässiger Compression Regret |
| Battle Compute Bank | Adaptive Verteilung verbessert Utility bei gleichem Gesamtbudget. | fixes Turn-Budget | Battle Utility oder Decision Regret bei gleichem Battle-Gesamtbudget | vorab gebundenes Gesamtbudget |
| Engine-Fragility | Sensitivitätsanalyse erklärt simulatorabhängige Entscheidungen. | normale qualifizierte Search ohne Perturbationsanalyse | diagnostische Coverage und Fehlererklärung, kein Strength-Gate | begrenztes Lab-only Perturbationsbudget |
| Robustheitszertifikat | Zusammengefasste Sensitivitätsdaten verbessern Triage und Corpus-Aufbau. | bestehende Decision Records und Reports | messbarer diagnostischer Nutzen und reproduzierbare Failure Triage | begrenzter Lab-Overhead; keine privaten Daten öffentlich |

Vor einer tatsächlichen Implementierung müssen die Platzhalter durch exakte
registrierte Identitäten, Metrikdefinitionen, Schwellen und Budgets ersetzt
werden.

## Aufnahme, Vereinfachung und Entfernung

Mögliche Ergebnisse des Gates sind:

```text
admit:
Frage, Arm, Metrik und Budget sind geschlossen; ein serieller Task darf geplant
werden.

research-only:
Die Idee bleibt dokumentiert, aber mindestens eine Pflichtfrage ist offen.

simplify:
Die Hypothese ist prüfbar, benötigt aber einen kleineren Mechanismus oder einen
einfacheren Arm.

remove or pivot:
Die Komponente verfehlt die vorab festgelegte Entscheidung oder verletzt einen
Guardrail.
```

Negativbefunde sind gültige Forschungsergebnisse. Eine Komponente wird nach
einem negativen Gate nicht allein wegen bereits investierter Arbeit dauerhaft
im System behalten.

## M2-/M3-Grenze

Dieses Gate erweitert M2 nicht. Der akzeptierte serielle M2-Plan wird
unverändert ausgeführt.

Die in den angrenzenden Research Notes beschriebenen M3- und Phase-2-Ideen
bleiben außerhalb der Implementierungsroadmap, bis jede Richtung das Gate mit
konkreten, outcome-blind festgelegten Antworten besteht.
