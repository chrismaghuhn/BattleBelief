---
document_id: docs-index
title: BattleBelief-Dokumentation
document_type: guide
status: accepted
normative: false
version: 6
applies_to:
  - repository
effective_from: 2026-08-03
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-05
---

# BattleBelief-Dokumentation

Diese Seite ist der Einstiegspunkt. Sie enthält keine eigenen Systemverträge,
sondern verweist auf deren jeweils einzige normative Quelle.

## Autorität

Autoritätsordnung, Frontmatter, Versionierung, Migration und CI-Gates stehen in
[Documentation Governance](documentation-governance.md).

## Lesereihenfolge

1. [Scope und Erfolg](product/scope-and-success.md)
2. [Systemüberblick](architecture/overview.md)
3. [Code- und Paketgrenzen](architecture/code-boundaries.md)
4. [Protocol und State](contracts/protocol-state.md)
5. [Legal-Action und Fallback-Safety](contracts/legal-action-safety.md)
6. [Engine-Capabilities](contracts/engine-capabilities.md)
7. [Belief und Open World](contracts/belief-open-world.md)
8. [Search-v0](contracts/search-v0.md)
9. [Determinismus](contracts/determinism.md)
10. [Evaluationsstruktur](evaluation/pool-separation.md)
11. [Forschungsstrategie und Experimentfolge](roadmap/research-strategy-and-experiments.md)
12. [Roadmap](roadmap/milestones.md)

## Aktuelle akzeptierte normative Quellen

Dieser Abschnitt ist der normative Dokumentindex. Er registriert alle
Dokumente mit `status: accepted` und `normative: true`.

### Governance, Produkt und Architektur

- [`documentation-governance`](documentation-governance.md)
- [`glossary`](glossary.md)
- [`product-scope-and-success`](product/scope-and-success.md)
- [`architecture-code-boundaries`](architecture/code-boundaries.md)
- [`architecture-dependency-matrix`](architecture/dependency-matrix.md)

### Runtime- und Search-Contracts

- [`contract-protocol-state`](contracts/protocol-state.md)
- [`contract-legal-action-safety`](contracts/legal-action-safety.md)
- [`contract-engine-capabilities`](contracts/engine-capabilities.md)
- [`contract-belief-open-world`](contracts/belief-open-world.md)
- [`contract-search-v0`](contracts/search-v0.md)
- [`contract-determinism`](contracts/determinism.md)
- [`contract-provenance`](contracts/provenance.md)
- [`contract-manifest-schemas`](contracts/manifest-schemas.md)
- [`experiment-registration`](contracts/experiment-registration.md)
- [`contract-decision-records`](contracts/decision-records.md)

### Daten, Training und Teams

- [`data-sources-and-licensing`](data/data-and-licensing.md)
- [`data-splits-and-meta-snapshot`](data/splits-and-meta-snapshot.md)
- [`training-pipeline-and-selection`](training/pipeline-and-selection.md)
- [`team-contract`](teams/team-contract.md)

### Evaluation

- [`evaluation-metrics`](evaluation/metrics.md)
- [`evaluation-target-population`](evaluation/target-population.md)
- [`evaluation-pool-separation`](evaluation/pool-separation.md)
- [`evaluation-team-clustering`](evaluation/team-clustering.md)
- [`evaluation-statistical-analysis`](evaluation/statistical-analysis.md)
- [`evaluation-m5-strength-qualification`](evaluation/m5-strength-qualification.md)
- [`evaluation-m6-human-validation`](evaluation/m6-human-validation.md)

### Betrieb und Beiträge

- [`operation-release-evaluation`](operations/release-evaluation.md)
- [`project-github-ci-security`](project/github-ci-security.md)
- [`project-contribution-provenance`](project/contribution-provenance.md)
- [`transfer-audit`](transfer-audit/README.md)

## Erklärungen, Entscheidungen und Planung

- [Systemüberblick](architecture/overview.md)
- [Memory-Hierarchie und battle-lokale Working Sets](architecture/memory-hierarchy.md)
- [ADR-0001 Information-Set DUCT](adr/ADR-0001-information-set-duct-v0.md)
- [ADR-0003 BattleBelief-Naming und Drei-Pakete-Monorepo](adr/ADR-0003-battlebelief-naming.md)
- [ADR-0004 Sauberer Showdown-Runtime-Adapter](adr/ADR-0004-clean-showdown-runtime-adapter.md)
- [ADR-0005 Task-25-v1-Windows-Provenienzgrenze](adr/ADR-0005-task-25-v1-windows-provenance-boundary.md)
- [Forschungsstrategie und Experimentfolge](roadmap/research-strategy-and-experiments.md)
- [Roadmap](roadmap/milestones.md)
- [M0-Implementierungsplan](superpowers/plans/2026-07-29-battlebelief-m0-foundation.md)
- [M1-Implementierungsplan](superpowers/plans/2026-07-29-battlebelief-m1-protocol-safe-prototype.md)
- [Quellenbasis](research/sources.md)

## Evidenz und Audits

- [M1 Protocol-safe Prototype Evidence](operations/m1-protocol-safe-evidence.md)
- [M1.5 Measurement Harness and Baseline Registration Evidence](operations/m1-5-measurement-harness-evidence.md)
- [Decision-Record-Contract](contracts/decision-records.md)

## Migrationen

- [Engine-Capability-v1-to-v2 migration](migrations/engine-capability-v1-to-v2.md)

## Archiv

- [Unveränderlicher Design-Freeze](archive/2026-07-29-design-freeze.md)
- [Freeze-Metadaten und SHA-256](archive/2026-07-29-design-freeze.metadata.yaml)
- [Migrationsmatrix](archive/2026-07-29-design-freeze.migration.csv)
