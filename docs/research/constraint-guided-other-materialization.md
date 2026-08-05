---
document_id: research-constraint-guided-other-materialization
title: Constraint-guided Open-World Set Materialization
document_type: research
status: proposed
normative: false
version: 1
applies_to:
  - belief
  - research
  - gen9ou
effective_from: 2026-08-05
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-05
---

# Constraint-guided Open-World Set Materialization

Diese Research Note beschreibt eine mögliche M3-Erweiterung für das
Open-World-Belief. Sie ist keine normative Quelle, registriert keine
Algorithmus-ID und ändert weder den
[Belief- und Open-World-Vertrag](../contracts/belief-open-world.md) noch die
M2-Reihenfolge.

Bei einem Widerspruch gelten die akzeptierten Contracts, Registrierungen und
Manifeste im [Dokumentationsindex](../README.md).

## Forschungsfrage

Der aktuelle Open-World-Vertrag reserviert positive Masse für `OTHER` und
fordert kontrollierte Hypothesenmaterialisierung. Offen ist, wie aus dieser
abstrakten Masse neue vollständige, legale und evidenzkompatible
Set-Hypothesen entstehen sollen.

Die zu prüfende Idee lautet:

> Wenn bekannte vollständige Sets die öffentliche Battle-Evidenz nicht mehr
> ausreichend erklären, erzeugt ein begrenzter, mechanisch validierter
> Materializer eine kleine diverse Menge neuer vollständiger Hypothesen und
> überträgt ausschließlich einen Teil der `OTHER`-Masse auf sie.

Arbeitsname:

```text
constraint_guided_other_materialization_v0
```

Dieser Name ist ausschließlich ein Research-Label. Eine spätere
`algorithm_id` benötigt einen separat geprüften Contract, ein Schema, eine
Ausführungsidentität und Evidenz.

## Vorgeschlagener Ablauf

```text
bekannte vollständige Set-Hypothesen
        ↓
neue öffentliche Battle-Evidenz
        ↓
Support-Kollaps, steigendes OTHER oder kalibrierte Surprise
        ↓
Evidenz wird in Constraints und Likelihoods übersetzt
        ↓
begrenzte Kandidatensynthese
        ↓
Showdown-basierte Legalitäts- und Mechanikprüfung
        ↓
Plausibilitätsgewichtung und Diversitätsauswahl
        ↓
Teilmasse von OTHER auf neue Hypothesen übertragen
        ↓
Belief und Search verwenden die erweiterte Weltverteilung
```

Die genaue Triggerfunktion, Solver-Klasse, Kandidatenzahl, Massenregel und
Search-Integration bleiben offene Forschungsentscheidungen.

## Informationsgrenze

Der Materializer darf ausschließlich verwenden:

- die eigene private Battle-Information;
- die für den Bot öffentlich beobachtbare Gegnerinformation;
- den an das Battle gebundenen Meta-Snapshot;
- rulesetgebundene Mechanik- und Legalitätsdaten;
- explizit gebundene Priors und Solver-Konfigurationen.

Er darf nicht verwenden:

- den vollständigen Oracle-Zustand des Gegners;
- unrevealed Gegnerdaten aus Evaluation-Harness oder Replay-Ground-Truth;
- spätere Battle-Ereignisse für frühere Entscheidungen;
- Cross-Battle-Daten, die nicht als eigener Evaluationsarm autorisiert sind;
- ungeprüfte externe LLM-Ausgaben als mechanische Wahrheit.

Adversarielle Leakage-Tests müssen zwei vollständige Wahrheiten mit derselben
öffentlichen Sicht verwenden und identische Materialization-Inputs verlangen.

## Harte Constraints

Ein Kandidat darf keine nachgewiesene mechanische oder rechtliche
Unmöglichkeit verletzen. Mögliche harte Constraints sind:

```text
Species und Form
bereits gezeigte Moves
enthülltes Item
enthüllte Ability
enthüllter Tera-Typ
Format- und Generation-Regeln
Learnset und Move-Kombinationen
Ability-, Item- und Formlegalität
EV-/IV-Grenzen
mechanisch ausgeschlossene Zustände
```

Pokémon Showdown bleibt die autoritative Legalitäts- und Mechanikquelle. Ein
lokaler Solver oder Datensatz darf keine eigene abweichende Legalitätswahrheit
definieren.

## Stochastische mechanische Evidenz

Nicht jede Beobachtung beweist eine Unmöglichkeit. Insbesondere Damage,
Speed-Reihenfolge oder Aktivierungseffekte können von Zustand, Zufallsroll,
Rundung oder noch unbekannten Variablen abhängen.

Solche Evidenz sollte grundsätzlich als Likelihood behandelt werden:

```text
P(observation | candidate hypothesis, public state)
```

Mögliche Quellen:

- beobachteter Damage-Bereich;
- Speed Order und bekannte Priority;
- Weather-, Terrain- und Field-Interaktionen;
- Move Lock;
- Recovery-Menge;
- Status- oder Ability-Aktivierung;
- verbleibende PP, soweit zuverlässig beobachtbar.

Ein harter Ausschluss ist nur zulässig, wenn die gebundene Mechanikprüfung die
Beobachtung unter dem Kandidaten tatsächlich unmöglich macht.

## Plausibilitäts-Priors

Mechanische Möglichkeit ist nicht gleich strategische Plausibilität. Nach der
Feasibility-Prüfung kann eine getrennte Prior-Schicht Kandidaten gewichten:

- aktuelle Meta-Häufigkeit;
- Team-Archetyp und Partnerkorrelationen;
- typische Rollen;
- bekannte EV-Benchmarks;
- Ähnlichkeit zu historischen vollständigen Sets;
- Quellenqualität und Zensierungsstatus.

Die Prior-Schicht darf keinen mechanisch unmöglichen Kandidaten retten. Die
Constraint-Schicht darf umgekehrt keine Meta-Häufigkeit als Legalität
behandeln.

Ein deterministischer Referenzmaterializer verwendet kein LLM. Ein gelerntes
Proposal-Modell wäre später ein eigener Arm und müsste jeden Vorschlag erneut
mechanisch validieren.

## Vollständige Hypothesen und Regionen

Ein materialisierter Kandidat beschreibt eine kohärente vollständige
Set-Erklärung, mindestens über:

```text
Species/Form
Item
Ability
Moves
Nature
EVs oder eine klar definierte feasible Region
Tera-Typ
Quelle und Evidence-Klasse
```

Moves, Item, Ability, Spread und Tera werden nicht unabhängig zu künstlichen
Sets zusammengesetzt.

Bei starker Unterbestimmtheit sind entscheidungsrelevante Regionen oft besser
als tausende nahezu identische EV-Varianten, zum Beispiel:

```text
langsamer als Benchmark A
zwischen Benchmark A und B
schneller als Benchmark B

fällt sicher
möglicher Damage Roll
überlebt sicher
```

Jede Region benötigt eine eindeutige Semantik und eine reproduzierbare
Materialisierung in Search-Welten.

## Massenerhaltung

Neue Kandidaten erhalten ausschließlich Masse aus `OTHER`.

Die Materialisierung muss nicht die gesamte unbekannte Masse konkretisieren:

```text
OTHER vorher: 0.30

Kandidat A:    0.08
Kandidat B:    0.05
Kandidat C:    0.03
OTHER danach:  0.14
```

Vorgeschlagene Invarianten für eine spätere Contract-Prüfung:

1. Die gesamte Wahrscheinlichkeitsmasse bleibt erhalten.
2. Bekannte Hypothesen verlieren nicht still Masse zugunsten eines neuen
   Kandidaten, sofern dies nicht eine getrennte Belief-Update-Regel bestimmt.
3. Nicht materialisierte Ungewissheit verbleibt in `OTHER`.
4. Kann kein gültiger Kandidat erzeugt werden, bleibt die Masse in `OTHER`.
5. Ein Fehler darf niemals still das häufigste bekannte Set einsetzen.
6. Rundung, Quantisierung und Canonicalization müssen manifestiert sein.

Diese Regeln sind in dieser Research Note noch nicht normativ.

## Determinismus und Provenienz

Unter identischen gebundenen Eingaben soll eine Referenzausführung dieselben
kanonischen Kandidaten und Massen erzeugen. Mindestens zu binden sind:

```text
snapshot_digest
ruleset_digest
id_catalog_digest
evidence_digest
materializer_label und source_digest
solver/config digest
seed domains
work/time budget
candidate/diversity policy
numeric and canonicalization contract
```

Ein späteres auditierbares Ereignis könnte folgende Informationen tragen:

```text
HypothesisMaterializationEvent
  event_id
  decision_identity
  snapshot_digest
  ruleset_digest
  evidence_digest
  trigger_reason
  known_support_before
  other_mass_before
  materializer/config identity
  seeds and budget
  generated_hypothesis_hashes
  mass_transfers
  other_mass_after
  termination_reason
```

Öffentliche Decision Records und Telemetrie dürfen keine vollständigen
materialisierten Gegnerwelten oder andere Hidden-State-Inhalte enthalten.
Sie referenzieren ausschließlich sichere Digests und zusammengefasste Zähler.

## Begrenzung der kombinatorischen Suche

Die größte technische Gefahr ist die kombinatorische Explosion über Moves,
Item, Ability, Tera, Nature und EVs.

Ein erster Prototyp sollte deshalb streng begrenzt sein:

```text
kleines max_candidates
festes Work- oder Solverbudget
nur entscheidungsrelevante Species
Top-K plus diverse Randlösungen
Cache nach Snapshot-, Evidence- und Config-Digest
keine ungebundene globale Zufallsquelle
```

Nach jeder Lösung kann eine Diversitätsbedingung nahezu identische Varianten
blockieren, etwa durch eine andere Rolle, ein anderes Item, einen anderen
relevanten Speed-Bereich oder eine andere Coverage-Eigenschaft.

Ein Timeout oder unvollständiger Solverlauf ist ein technisches Ergebnis und
muss in Evaluation und Deployment-Ansicht gezählt werden.

## Vorgeschlagene Evaluation

Der sauberste erste Test ist ein versiegeltes held-out Off-Meta-Set-Corpus:

1. Bestimmte vollständige Sets werden outcome-blind aus dem Meta-Snapshot
   entfernt.
2. Der Gegner verwendet genau diese Sets in kontrollierten Battles oder
   Belief-Puzzles.
3. Der Bot erhält nur die zulässige öffentliche Battle-Evidenz.
4. Detection und `OTHER`-Verhalten werden gemessen.
5. Der Materializer erzeugt begrenzte Kandidaten.
6. Belief- und Search-Nutzen werden getrennt ausgewertet.

Geeignete Kategorien sind:

- unbekannter Move auf bekannter Species;
- ungewöhnliches Item;
- ungewöhnlicher Speed- oder Bulk-Benchmark;
- defensive statt offensive Rolle;
- neue Tera-Tech;
- Ruleset- oder Meta-Shift.

### Forschungsarme

Die folgenden Bezeichnungen sind nur Arbeitslabels und keine registrierten
Arm-IDs:

```text
A  Closed World ohne OTHER
B  Open World mit abstraktem OTHER, ohne Materialisierung
C  B plus constraint-guided Materialisierung
D  C plus Team-Archetyp- und Partner-Priors
```

Dadurch lässt sich unterscheiden, ob ein Nutzen aus besserer
Unsicherheitskalibrierung, konkreter Hypothesenerzeugung oder strukturellen
Priors stammt.

### Metrikgruppen

Open-World Detection:

```text
unknown-set detection quality
false materialization rate
surprise calibration
OTHER mass before contradiction
```

Materialization:

```text
legal-set rate
evidence-consistency rate
true-set or decision-relevant coverage@K
time and work to materialization
candidate count and diversity
solver timeout/failure rate
```

Entscheidungsnutzen:

```text
decision regret before/after materialization
action recovery rate
battle utility against held-out sets
utility per additional CPU/work budget
```

Der primäre Forschungsnutzen ist nicht das exakte Erraten jedes privaten
Details, sondern die rechtzeitige Erzeugung einer Erklärung, die eine bessere
Entscheidung ermöglicht.

## M2-/M3-Grenze

M2 bleibt unverändert. Der lokale Oracle, Engine-Qualifikation,
Determinization und Closed-World Information-Set DUCT werden nicht um diese
Idee erweitert.

Vorgeschlagene M3-Reihenfolge:

```text
1. Open-World-Belief mit abstraktem OTHER
2. synthetischer Materializer-Prototyp ohne Produktionsintegration
3. held-out Detection-, Materialization- und Belief-Evaluation
4. eigener Search-Evaluation-Arm
5. Contract-/Schema-Vorschlag nur nach positiver Evidenz
```

Eine produktive Runtime-Integration ist kein automatisches Ergebnis eines
guten Offline-Materialization-Scores.

## Spätere Search-Forschung

Branch-lokale kontrafaktische Belief-Updates innerhalb der Search könnten
simulierte Beobachtungen verwenden, um Informationswert zu bewerten. Diese
Idee verändert Knotenzustand, Transpositionen und Search-Semantik erheblich und
gehört frühestens in einen späteren `search-v1`-Entwurf nach einer stabilen
M3-Baseline.

Sie ist kein Bestandteil des hier vorgeschlagenen Referenzmaterializers.

## Offene Entscheidungen

Vor einer Implementierung müssen mindestens geklärt werden:

- Surprise- und Triggerdefinition;
- Solver- oder Enumerator-Klasse;
- Repräsentation von EV-/IV-Regionen;
- mechanische Likelihoods und deren Kalibrierung;
- Kandidaten-Diversität und Dominanzregeln;
- exakte Massenübertragung und verbleibendes `OTHER`;
- Work-, CPU- und Deadline-Budget;
- Cache-Identität und Lebensdauer;
- Search-Weltmaterialisierung;
- sichere Record-/Telemetry-Projektion;
- Evaluationskorpus, Pools und statistische Analyse.

Keine dieser Entscheidungen wird durch diese Research Note vorweggenommen.

## Neuheitsdisziplin

Open-Set Recognition, Constraint Solving, abduktive Inferenz und
beliefbasierte Monte-Carlo-Planung sind etablierte Konzepte. Ein möglicher
BattleBelief-Beitrag läge in der überprüfbaren Kombination aus:

```text
explizitem OTHER
mechanischer Surprise-Erkennung
vollständiger legaler Set-Synthese
Massenerhaltung
auditierbarer Provenienz
Information-State Search
kontrollierter Pokémon-Evaluation
```

Diese Note erhebt keinen First-System- oder Novelty-Claim. Ein späterer Claim
erfordert eine systematische Literatur- und öffentliche Code-Suche zum dann
aktuellen Stand.

## Primärquellen und verwandte Grundlagen

- [Pokémon Showdown Team Validator](https://github.com/smogon/pokemon-showdown/blob/master/sim/team-validator.ts)
- [Toward Open Set Recognition](https://pubmed.ncbi.nlm.nih.gov/23682001/)
- [Monte-Carlo Planning in Large POMDPs](https://papers.nips.cc/paper_files/paper/2010/hash/edfbe1afcf9246bb0d40eb4d8027d90f-Abstract.html)
- [Information Set MCTS](https://eprints.whiterose.ac.uk/id/eprint/75048/1/CowlingPowleyWhitehouse2012.pdf)
