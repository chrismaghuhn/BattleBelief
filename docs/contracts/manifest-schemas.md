---
document_id: contract-manifest-schemas
title: Manifest-Schemas, Canonicalization und Evolution
document_type: contract
status: accepted
normative: true
version: 6
applies_to:
  - manifests
  - release
  - evaluation
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Manifest-Schemas, Canonicalization und Evolution

## Autoritative Schemas

Die Markdown-Dokumentation erklärt Bedeutung und Verantwortlichkeit. Nur die
folgenden Dateien definieren die maschinenvalidierte Struktur:

| Manifest | Schema |
|---|---|
| Dokument-Frontmatter | [`frontmatter.schema.json`](../../schemas/documents/frontmatter.schema.json) |
| Contract-Snapshot-Metadaten | [`contract-snapshot-metadata.schema.json`](../../schemas/documents/contract-snapshot-metadata.schema.json) |
| Search-Ausführung | [`search-contract.schema.json`](../../schemas/manifests/search-contract.schema.json) |
| Engine-Capabilities | [`engine-capability.schema.json`](../../schemas/manifests/engine-capability.schema.json) |
| Evaluation-Claim | [`evaluation-claim.schema.json`](../../schemas/manifests/evaluation-claim.schema.json) |
| Ruleset-Snapshot | [`ruleset-snapshot.schema.json`](../../schemas/manifests/ruleset-snapshot.schema.json) |
| Dataset-Provenance | [`dataset-manifest.schema.json`](../../schemas/manifests/dataset-manifest.schema.json) |
| Experiment-Registrierung | [`experiment-registration.schema.json`](../../schemas/manifests/experiment-registration.schema.json) |
| Arm-Implementierungsbindung | [`evaluation-arm-binding.schema.json`](../../schemas/manifests/evaluation-arm-binding.schema.json) |
| Evaluationslauf-Bindung | [`evaluation-run-binding.schema.json`](../../schemas/manifests/evaluation-run-binding.schema.json) |
| Budget-Kalibrierungsspezifikation | [`budget-calibration-spec.schema.json`](../../schemas/manifests/budget-calibration-spec.schema.json) |
| Budget-Kalibrierungsevidenz | [`budget-calibration-evidence.schema.json`](../../schemas/manifests/budget-calibration-evidence.schema.json) |
| Deklarative Search-Ausführungsspezifikation | [`search-execution-spec.schema.json`](../../schemas/manifests/search-execution-spec.schema.json) |
| Synthetisches Fixture-Manifest | [`synthetic-fixture-manifest.schema.json`](../../schemas/manifests/synthetic-fixture-manifest.schema.json) |

Beispieldateien unter `/schemas/examples` sind Test-Fixtures und müssen im
`pr-gate` gegen das zugehörige Schema validieren.

## Canonicalization und Hashbildung

Der verbindliche Bytevertrag steht in
[`schemas/canonicalization/README.md`](../../schemas/canonicalization/README.md).
Ein Manifest-Digest besitzt die Form:

```text
sha256:<64 lowercase hexadecimal characters>
```

Ein Hash wird erst nach erfolgreicher Schema-Validierung gebildet. Eingaben mit
unbekannten Feldern, nicht endlichen Zahlen, mehrfachen JSON-Schlüsseln oder
mehrdeutigen YAML-Typen werden abgelehnt.

## Schema-Evolution

- Jedes Manifest trägt `schema_version`.
- Rückwärtskompatible Ergänzungen erfordern trotzdem eine neue
  Schema-Dateiversion, wenn sie die kanonische Repräsentation verändern.
- Ein bestehendes Schema und seine `$id` werden nach Verwendung in einem Claim
  nicht semantisch umgeschrieben.
- Inkompatible Änderungen benötigen neue `$id`, neue `schema_version` und
  einen expliziten Migrator.
- Ein Migrator bewahrt die alte Datei und zeichnet Quellhash, Zielhash,
  Migratorversion und Verlustinformation auf.
- Ein Release-Claim referenziert die konkreten Schema- und
  Canonicalizer-Versionen.

## Kompatibilität

Ein Leser darf ein Manifest nur akzeptieren, wenn:

1. Schema-ID und Version unterstützt werden;
2. Validierung vollständig besteht;
3. referenzierte Contract-Dokument-ID und -Version vorhanden sind;
4. Hash nach erneuter Canonicalization übereinstimmt;
5. alle referenzierten Artefakte auflösbar und lizenzrechtlich zulässig sind.

Unbekannte Schema-Versionen werden fail-closed abgelehnt, nicht heuristisch
interpretiert.

Document references bind the document ID and version to the SHA-256 digest of
the exact UTF-8 file. Older frozen references resolve through sidecar metadata
and byte-identical files under `docs/archive/contract-snapshots/`; changing the
current Markdown file must not retroactively change an existing document
digest. Archived snapshot bytes are not revalidated as current documents.

Beispieldateien unter `/schemas/examples` werden im `pr-gate` über eine
explizite Beispiel-zu-Schema-Zuordnung geprüft; die Zuordnung wird nicht aus
Dateinamenheuristik abgeleitet. Die Verzeichnisse `schemas/records/` und
`registrations/` werden von späteren M1.5-Tasks aktiviert. Solange sie fehlen,
ist die Artefaktprüfung ein gültiger No-op; vorhandene Artefakte werden
vollständig und semantisch fail-closed geprüft.
