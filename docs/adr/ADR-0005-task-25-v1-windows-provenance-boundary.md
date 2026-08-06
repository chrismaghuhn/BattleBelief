---
document_id: adr-0005-task-25-v1-windows-provenance-boundary
title: "ADR-0005: Task-25-v1-Windows-Provenienzgrenze"
document_type: adr
status: accepted
normative: false
version: 1
applies_to:
  - gen9ou
  - manifests
  - release
effective_from: 2026-08-06
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-06
---

# ADR-0005: Task-25-v1-Windows-Provenienzgrenze

## Kontext

Task 25 veröffentlichte sechs `poke-engine`-Wheels als unveränderlichen
Prerelease
`engine-poke-engine-v0.0.48-bcf13823-v1`. Release-API-Digests,
`SHA256SUMS`, Quell-, Build- und Artifact-Index-Manifeste binden die
veröffentlichten Bytes. Alle sechs Zellen durchliefen außerdem isolierte
Installations- und native Health-Sentinels; spätere CI-Läufe bauen dieselbe
Quelle mit denselben manifestierten Parametern erneut und prüfen das Verhalten.

Der Windows-Build übernahm jedoch die Host-Discovery für Visual Studio, MSVC,
Windows SDK und Linker. Das v1-Build-Manifest erfasst weder die genaue
MSVC-Toolset- und SDK-Version noch Version und Digest der tatsächlich
verwendeten `link.exe` oder die vollständige Runner-Image-Identität. Diese
Werte wurden beim ursprünglichen Build nicht als Evidenz aufgezeichnet und
können nach Veröffentlichung nicht zuverlässig rekonstruiert werden.

Der normative Schema- und Evolutionsvertrag steht in
[Manifest-Schemas, Canonicalization und Evolution](../contracts/manifest-schemas.md).
Das vorhandene v1-Schema und die veröffentlichten v1-Artefakte werden nicht
rückwirkend verändert.

## Entscheidung

Task 25 v1 garantiert:

- die unveränderliche Identität der veröffentlichten Release-Assets und des
  zugehörigen Tags;
- die Digestbindung zwischen Release-Metadaten, `SHA256SUMS`, Quellmanifest,
  sechs Build-Manifesten, Artifact-Index, Lizenz und Wheels;
- die im v1-Build-Manifest erfassten kontrollierten Buildparameter,
  einschließlich Rust-, Cargo-, Maturin- und Python-Identität, Ziel-Tripel,
  Features und expliziter Buildargumente;
- verhaltensbezogene Rebuild-Evidenz für die sechs qualifizierten
  Ubuntu-/Windows-Zellen.

Task 25 v1 garantiert nicht:

- die vollständige Rekonstruktion der ursprünglichen Windows-Buildumgebung;
- eine vollständig gepinnte Visual-Studio-/MSVC-/Windows-SDK-Toolchain;
- Identität oder Digest der ursprünglich aufgelösten `link.exe`;
- vollständige Runner-Image-Identität oder byteidentische Windows-Rebuilds.

Die Formulierung „no ambient build overrides“ bedeutet für v1 ausschließlich,
dass die ausdrücklich kontrollierten und manifestierten Buildparameter nicht
durch Umgebungs-Overrides ersetzt werden. Sie bedeutet nicht, dass die
Windows-Discovery-Umgebung oder jede native Toolchain-Komponente vollständig
gepinnt war.

## Verifier-Grenze

Staging und veröffentlichte Artefakte liefern unterschiedliche Evidenz:

- Der Staging-Verifier benötigt zwingend einen realen Checkout und prüft
  dessen vollständige Tree-Closure gegen das Quellmanifest, bevor er ein Wheel
  akzeptiert.
- Als gegenüber dem Builder nachgelagerte, im Staging-Verifier jedoch erste
  Akzeptanzbedingung verwirft der Staging-Verifier einen Lauf, sofern die
  unmittelbare Closure des Wheelhouse nicht exakt aus dem einen regulären Wheel
  besteht. Das Wheelhouse ist das Elternverzeichnis des mit `--wheel`
  übergebenen Pfads. Weder Wheelhouse noch Wheel dürfen symbolische Links,
  Junctions oder sonstige Reparse Points sein. Diese Prüfung erfolgt vor dem
  Laden eines Manifests, der Checkout-Verifikation, der Wheel-Inspektion und
  der Manifest-/Wheel-Bindung.
- Der Release-Manifest-Verifier prüft heruntergeladene Wheel-Bytes, Digests,
  kanonische Manifestkonsistenz sowie Python-, ABI- und Plattform-Tags. Er
  prüft keinen Source-Checkout und keine Buildumgebung und erhebt diesen
  Anspruch weder im Namen noch in Erfolgsmeldungen.

Der neue Guard schützt Staging- und CI-Akzeptanzläufe, die nach seiner
Einführung ausgeführt werden. Er ist keine Evidenz dafür, dass der
ursprüngliche v1-Build-Lauf diese Prüfung anwendete, und erweitert dessen
Evidenz oder Output-Closure-Garantie nicht rückwirkend. Builder, eingefrorener
`artifact-build`-Job, Release-only-Verifier und das unveränderliche v1-Release
bleiben unverändert.

Die vollständige technische Ausgestaltung steht in den beiden akzeptierten
Designs:
[Task-25-v1-Verifier-Design](../superpowers/specs/2026-08-06-task-25-v1-verifier-provenance-design.md)
und
[Task-25-Staging- und Runtime-Hardening-Design](../superpowers/specs/2026-08-06-task-25-staging-and-runtime-hardening-design.md).

## Konsequenzen

Die veröffentlichte v1-Identität bleibt unverändert und ihre vorhandene
Evidenz wird nicht überinterpretiert. Die bereits beobachtete Variation von
PE/COFF-Zeitstempeln und CodeView-GUIDs in späteren Windows-Builds ist mit
dieser begrenzten Rebuild-Garantie vereinbar; solche Builds ersetzen nie die
digestgebundenen Release-Wheels.

Falls vollständige Windows-Toolchain-Provenienz künftig Release-Kriterium
wird, benötigt eine reguläre v2-Artefaktgeneration vor dem Build ein neues
Schema. Dieses muss mindestens Visual-Studio-/MSVC-Toolset, Windows-SDK,
Version und vorzugsweise Digest von `link.exe` sowie eine relevante
Runner-Image-Identität binden. Die daraus entstehenden Artefakte erhalten eine
neue Release-Identität; v1 bleibt erhalten.

## Verworfene Alternativen

### Retrospektive v1-Attestation

Abgelehnt, weil die entscheidenden Windows-Werte im ursprünglichen Lauf nicht
vollständig erfasst wurden. Eine spätere Schätzung würde keine belastbare
Provenienz für die veröffentlichten Bytes schaffen.

### Sofortige v2-Neuveröffentlichung

Für diese Korrektur abgelehnt. Die v1-Wheels sind bereits unveränderlich,
digestgebunden und verhaltensbezogen geprüft. Eine neue Artefaktgeneration ist
erst gerechtfertigt, wenn die vollständige Windows-Toolchainbindung ein
ausdrückliches zukünftiges Release-Kriterium ist.
