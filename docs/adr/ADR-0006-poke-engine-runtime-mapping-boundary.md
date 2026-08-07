---
document_id: adr-0006-poke-engine-runtime-mapping-boundary
title: "ADR-0006: poke-engine Runtime-Mapping-Grenze"
document_type: adr
status: accepted
normative: false
version: 1
applies_to:
  - runtime
  - search
  - gen9ou
effective_from: 2026-08-07
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-07
---

# ADR-0006: poke-engine Runtime-Mapping-Grenze

## Kontext

Task 25 liefert ausschließlich verifizierte native Artifact- und Sentinel-
Grundlagen. Die Task-25-Evidenz autorisiert weder ein öffentliches Mapping-
API noch eine Mechanics-, Eligibility- oder Strength-Aussage. Die bestehende
Provenienzgrenze steht in [ADR-0005](ADR-0005-task-25-v1-windows-provenance-boundary.md).

Task 26 hat den engine-neutralen Core-Port für vorbereitete Welten, Aktionen,
Ansichten und Transitionen eingefroren. Dieser ADR nimmt diesen Port als
gegeben und ändert keine Core-API.

Task 27 benötigt nun eine konkrete Runtime-Abbildung zwischen BattleBelief-
Objekten und dem optionalen `poke-engine`-Backend. Der M2-Plan nennt dafür drei
Optionen und empfiehlt Option A, besitzt als `status: proposed` und
`normative: false` jedoch keine Entscheidungsautorität.

## Erwogene Optionen

### Option A – zentrale kanonische Mapping-Schicht

Eine einzige explizite Mapping-Schicht zentralisiert Validierung und
Feature-Erkennung. Sie erfordert vollständige negative Fixtures und zentrale
Conformance-Tests.

### Option B – ad-hoc Mapping in jedem Search-Algorithmus

Jeder spätere Search-Algorithmus konvertiert die benötigten Zustände und
Aktionen selbst. Das ist anfänglich schnell, lädt aber zu divergierendem
Mapping- und Fehlerverhalten ein.

### Option C – native `poke-engine`-States als Projekt-Domainmodell

Das native Zustandsmodell beseitigt die Konvertierung. Es würde jedoch ein
nicht-autoritativer Backend-Zustand zum Projekt-Domainmodell machen und die
Hidden-Information-Grenze gefährden.

## Entscheidung

Die Maintainer-Auswahl ist **Option A**. Die ausdrückliche Maintainer-
Freigabe wurde am 2026-08-07 erteilt; ADR-0006 ist damit akzeptiert.
`normative: false` bleibt bestehen.

Die Mapping-Schicht liegt konzeptionell im bestehenden Runtime-Adapterbereich
`battlebelief-runtime/adapters/poke_engine`. Sie implementiert den bereits
eingefrorenen engine-neutralen Core-Port und verändert keine Core-Signatur.
Die Entscheidung umfasst:

- `ObservedState` und vollständige hypothetische Welten werden über getrennte,
  explizite Abbildungspfade gemappt;
- Root-Aktionen stammen ausschließlich aus dem autoritativen
  `SafeSubmissionSet`;
- tiefere Backend-Aktionen werden auf den engine-neutralen `SearchAction`-
  Vertrag abgebildet;
- eine erfolgreiche Abbildung liefert eine vorbereitete Backend-Welt samt
  kataloggebundenen Required-Capabilities, andernfalls einen typisierten
  Mapping-Fehler;
- Backend-native States, Choices, Results, Strings und Exceptions bleiben
  Runtime-intern und überqueren keine öffentlichen Core-Grenzen;
- der Mapping-Report ist sanitisiert und enthält keine private Welt;
- Mapping-Verhalten wird zentral mit deterministischen Fixtures und
  Port-Conformance-Tests geprüft, statt in späteren Search-Algorithmen
  dupliziert zu werden.

Normative Details bleiben bei ihren bestehenden Owners:

- [architecture-code-boundaries](../architecture/code-boundaries.md) besitzt
  Paket- und Importgrenzen;
- [contract-protocol-state](../contracts/protocol-state.md) und
  [contract-belief-open-world](../contracts/belief-open-world.md) besitzen die
  State-, Beobachtungs- und Hidden-Information-Semantik;
- [contract-legal-action-safety](../contracts/legal-action-safety.md) besitzt
  die Autorität des `SafeSubmissionSet` und die Action-Safety;
- [contract-engine-capabilities](../contracts/engine-capabilities.md) besitzt
  Capability-Katalog, Required-Capabilities und fail-closed Capability-
  Semantik;
- [contract-search-v0](../contracts/search-v0.md) besitzt die Search- und
  Information-Set-Semantik.

Dieser ADR verlinkt diese Regeln und begründet die Mapping-Entscheidung; er
definiert keine zweite normative Quelle für sie.

## Konsequenzen

Positiv:

- Es gibt eine einzige überprüfbare Mapping-Implementierung.
- Search-Algorithmen benötigen kein algorithmusspezifisches Mapping.
- Die Grenze zwischen beobachtetem Zustand, vollständiger hypothetischer Welt
  und Backend-Zustand bleibt explizit.
- Deterministische Fixtures und Port-Conformance werden an einer Stelle
  möglich.
- Das Backend kann später ersetzt werden, ohne das Core-Domainmodell
  umzubauen.

Kosten und Risiken:

- Die Runtime benötigt mehr explizite Mapper und negative Fixtures.
- Native Backend-Felder müssen vollständig klassifiziert werden.
- Unsupported- oder mehrdeutige Backendzustände müssen fail closed behandelt
  werden; sie dürfen nicht als best-effort Mapping fortschreiten.
- Task 27 kann einen echten Defekt im Core-Port sichtbar machen. In diesem
  Fall muss Task 27 stoppen und darf den Port nicht durch eine Backend-
  Sonderlösung umgehen.

## Nicht autorisiert

Dieser ADR allein begründet keine:

- Mechanics-Parity oder Differential Runs;
- Search-Eligibility oder Runtime-Search-Nutzung;
- Capability-Qualification oder `exact`-Einstufung;
- Closed-World-Distribution;
- Runtime-Session-Composition;
- Strength-, Evaluation- oder Release-Aussage;
- Änderung des bereits gemergten Task-26-Core-Ports oder anderer Core-APIs.

MD-07 Option A is approved by the Maintainer.
