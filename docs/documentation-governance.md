---
document_id: documentation-governance
title: Documentation Governance
document_type: guide
status: accepted
normative: true
version: 1
applies_to:
  - repository
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Documentation Governance

Dieses Dokument regelt Autorität, Versionierung und Migration der
Projektdokumentation. Fachliche Anforderungen bleiben in ihren jeweiligen
Contracts.

## Autoritätsordnung

```text
Validiertes Manifest
    ↓ instanziiert
Normativer Contract
    ↓ wird erklärt durch
ADR und Architecture
    ↓ wird operationalisiert durch
Operations
    ↓ wird eingeplant durch
Roadmap
```

Bei einem Widerspruch gilt:

1. Ein validiertes Manifest bestimmt die konkrete Ausführung.
2. Der zugehörige Contract bestimmt die zulässige Bedeutung des Manifests.
3. Ein Manifest, das seinem Contract widerspricht, ist ungültig.
4. ADR, Architektur, Operations und Roadmap dürfen einen Contract nicht
   überschreiben.
5. Archiv- und Research-Dokumente sind Evidenz oder Historie, aber niemals
   operative Quellen. Ein als normativ markiertes Audit darf ausschließlich
   Freigabekriterien für den von ihm geprüften Transfergegenstand setzen.

Ein ADR begründet eine Entscheidung. Es besitzt nicht die aktuelle Liste
erlaubter Importkanten oder aktuelle Strength-Schwellen. Diese stehen
ausschließlich in der jeweils ausgewiesenen normativen Quelle.

## Dokumenttypen und Status

Zulässige `document_type`-Werte:

```text
contract | architecture | operation | adr | roadmap |
research | audit | archive | guide
```

Zulässige `status`-Werte:

```text
draft | proposed | accepted | deprecated | superseded | archived
```

Alle aktuellen Markdown-Dokumente außer bitidentischen Archiv-Snapshots
besitzen Frontmatter, das gegen
[`frontmatter.schema.json`](../schemas/documents/frontmatter.schema.json)
validiert. Archiv-Snapshots besitzen stattdessen eine separate Metadatendatei,
damit ihre Bytes unverändert bleiben.

## Frontmatter-Vertrag

Jedes aktuelle Dokument enthält:

```yaml
document_id: contract-search-v0
title: Search v0 Contract
document_type: contract
status: accepted
normative: true
version: 1
applies_to:
  - gen9ou
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
```

Regeln:

- `document_id` ist repositoryweit eindeutig und bleibt bei Dateiumbenennung
  stabil.
- `applies_to` und `supersedes` sind immer Listen.
- Bei einer semantischen Änderung an einem normativen Dokument steigt
  `version`.
- Eine reine Review-Bestätigung darf `last_reviewed` ändern, ohne `version`
  zu erhöhen.
- `supersedes` und `superseded_by` müssen auf existierende Dokument-IDs
  zeigen.
- Dokumente mit Status `superseded` oder `archived` dürfen im aktuellen Index
  nicht als geltende Quelle erscheinen.

## Eine normative Quelle je Definition

Der [Docs-Index](README.md) registriert jedes aktuelle, akzeptierte normative
Dokument. README, Roadmap, ADRs und Paket-READMEs verlinken auf normative
Definitionen, statt Schwellen, Importkanten oder Sicherheitsregeln neu zu
definieren.

Insbesondere:

- Importkanten gehören nur in
  [`architecture-code-boundaries`](architecture/code-boundaries.md).
- M5-Strength-Schwellen gehören nur in
  [`evaluation-m5-strength-qualification`](evaluation/m5-strength-qualification.md).
- Laufzeit- und Determinismusregeln gehören in ihre ausgewiesenen Contracts.
- Die Zielpopulation gehört nur in
  [`evaluation-target-population`](evaluation/target-population.md).

## Schema- und Hash-Vertrag

Die erklärende Dokumentation steht in
[`contract-manifest-schemas`](contracts/manifest-schemas.md). Die tatsächlich
validierten JSON-Schemas liegen unter `/schemas`. Hashbildung und
Canonicalization sind in
[`schemas/canonicalization/README.md`](../schemas/canonicalization/README.md)
festgelegt.

## Migration und Archiv

Eine Aufteilung eines Freeze-Dokuments erfolgt in zwei prüfbaren Pässen:

1. **Verlustfreie Sicherung:** bytegleicher Snapshot, SHA-256-Metadaten und
   eine Migrationsmatrix, die jeden Quellzeilenbereich genau einem
   Zieldokument zuordnet.
2. **Entduplizierung:** eine normative Quelle je Definition; andere Dokumente
   werden zu Zusammenfassungen und Links.

Eine Quellpassage gilt nur dann als migriert, wenn sie übernommen, ausdrücklich
als überholt markiert oder durch einen benannten ADR ersetzt wurde.

Der Freeze vom 29. Juli 2026 ist in
[`2026-07-29-design-freeze.metadata.yaml`](archive/2026-07-29-design-freeze.metadata.yaml)
registriert. Der Markdown-Snapshot selbst wird nicht mit einem Hinweis oder
Frontmatter verändert.

## Merge-blockierende Dokumentprüfungen

Der spätere `pr-gate` prüft:

```text
docs-frontmatter:
  aktuelles Markdown besitzt gültiges Frontmatter

docs-ids:
  document_id eindeutig
  supersedes und superseded_by auflösbar

docs-links:
  interne Links gültig
  keine operativen Links auf lokale Laufwerks- oder Benutzerpfade

docs-normative-index:
  jedes accepted normative Dokument im Index
  kein verwaister Contract

docs-authority:
  README, Roadmap und ADRs definieren keine geschützten Schwellen
  oder Importkanten erneut

schema-validation:
  Beispielmanifeste validieren gegen die echten JSON-Schemas

archive-integrity:
  archivierter Snapshot stimmt mit seinem SHA-256-Hash überein
```

Semantische Duplikate können nicht vollständig automatisch erkannt werden.
CI darf deshalb zusätzlich bekannte Schlüsselformulierungen und numerische
Gates außerhalb ihrer normativen Eigentümerdatei verbieten.
