---
document_id: project-contribution-provenance
title: Contribution- und Herkunftsvertrag
document_type: operation
status: accepted
normative: true
version: 1
applies_to:
  - contributions
  - repository
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Contribution- und Herkunftsvertrag

## Pull-Request-Nachweis

Jeder Beitrag beantwortet:

```text
Source provenance:
  kein kopierter GPL- oder inkompatibel lizenzierter Code
  übernommene Algorithmen, Snippets und Ideen genannt
  Drittanbieter-Code mit Lizenznachweis
  KI-generierter Code vollständig geprüft
  Trainingsdaten und Modellartefakte mit Provenance-Manifest
```

„Ideas only“ erlaubt das Studium einer Architektur, nicht das Übernehmen
lizenzpflichtiger Implementierungsdetails. Foul-Play-Code wird nicht in den
Apache-2.0-Codebestand kopiert.

## Daten und Modelle

- Jede externe Datenquelle besitzt URL, Revision, Lizenz und
  Dataset-Manifest.
- Rekonstruierte oder imputierte Labels werden als solche markiert.
- Modellartefakte nennen alle Trainingsdatenklassen und ihre Lizenzen.
- NC-basierte Checkpoints bleiben getrennte, nichtkommerzielle
  Forschungsartefakte.
- Große Datensätze, Gewichte und Trainingsoutputs werden nicht in das
  Core-Repository eingecheckt.

## Historischer Code

Historische Komponenten benötigen den
[`transfer-audit`](../transfer-audit/README.md). Unklare Herkunft,
inkompatible Lizenz oder nicht isolierbare VGC-Annahmen führen zu einer
sauberen Neuimplementierung auf Basis zulässiger Spezifikationen.

## Sicherheits- und Datenschutzprüfung

Vor Veröffentlichung werden mindestens geprüft:

- Secrets, Tokens, Cookies und Credentials;
- Benutzernamen und personenbezogene Replaydaten;
- lokale Laufwerks- und Benutzerpfade;
- private Serveradressen;
- nicht freigegebene Datensätze;
- unzulässige Drittanbieterartefakte.

Ein bestandener technischer Test ersetzt keinen Herkunfts- oder Lizenznachweis.
