---
document_id: team-contract
title: Teamvertrag
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - gen9ou
  - teams
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Teamvertrag

## MVP

Für den MVP werden starke kuratierte Teams verwendet. Das vollständige Team
ist vor Battlebeginn bekannt, legal geprüft, gehasht und versiegelt. Im Battle
findet weder Team-Generierung noch Setänderung statt.

Die Rotation der Hero-Teams wird vor Evaluation festgelegt. Manuelle
Teamwechsel nach Sichtung von Ergebnissen sind unzulässig.

## Trennung und Informationsfluss

Team-Building und Battle-Decision-Making sind getrennte Systeme. Sie dürfen
folgende versionierte Artefakte gemeinsam nutzen:

- Meta-Snapshots;
- Set- und Archetypstatistiken;
- Matchup- und Robustheitsberichte;
- Format-, Team- und Legalitätsschemas.

Der Battle-Entscheider darf keine Teamoptimierung aus laufenden
Release-Ergebnissen anstoßen. Der Team-Builder darf keinen Release-Holdout zur
Optimierung oder Kandidatenauswahl verwenden.

## Späterer Offline-Team-Builder

Ein Team-Builder:

- erzeugt Teams ausschließlich offline;
- bewertet Kandidaten bei unveränderter Battle-Policy;
- verwendet eigene Development-, Selection- und teamdisjunkte Holdouts;
- fördert ein Team nur, wenn es bei fester Policy den vorregistrierten
  Vergleich besteht;
- veröffentlicht Team-, Meta-, Policy- und Evaluationsdigests gemeinsam.

## Teammetriken

- gewichtete durchschnittliche Matchup-Winrate;
- schlechteste vorregistrierte Matchup-Familie;
- Archetypabdeckung;
- Rollenabdeckung und Redundanz;
- Format- und Setlegalität;
- Robustheit über mehrere Gegnerpolicies;
- Verbesserung gegenüber kuratierten Teams bei unveränderter Battle-Policy.

Ein Teamclaim ist kein Beweis einer besseren Battle-Policy. Ein Policyclaim ist
kein Beweis eines besseren Team-Builders.
