---
document_id: contract-manifest-schemas
title: Manifest-Schemas, Canonicalization und Evolution
document_type: contract
status: accepted
normative: true
version: 2
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
| Search-Ausführung | [`search-contract.schema.json`](../../schemas/manifests/search-contract.schema.json) |
| Engine-Capabilities | [`engine-capability.schema.json`](../../schemas/manifests/engine-capability.schema.json) |
| Evaluation-Claim | [`evaluation-claim.schema.json`](../../schemas/manifests/evaluation-claim.schema.json) |
| Ruleset-Snapshot | [`ruleset-snapshot.schema.json`](../../schemas/manifests/ruleset-snapshot.schema.json) |
| Dataset-Provenance | [`dataset-manifest.schema.json`](../../schemas/manifests/dataset-manifest.schema.json) |

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
