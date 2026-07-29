---
document_id: architecture-dependency-matrix
title: Dependencies und Installationsprofile
document_type: architecture
status: accepted
normative: true
version: 5
applies_to:
  - packaging
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Dependencies und Installationsprofile

## Pakete

```text
battlebelief-core
  Pure Domain- und Application-Logik.
  Keine Netzwerk-, Datenbank-, Engine-, ML- oder Oracle-Abhängigkeiten.

battlebelief-runtime
  base:
    Showdown-Client, Protocol-Adapter, Teamdateien, Legal-Fallback
  search:
    geprüftes Gen9-poke-engine-Artefakt
  onnx:
    CPU-Modellinferenz
  torch:
    PyTorch-Modellinferenz

battlebelief-lab
  DuckDB, Parquet/PyArrow, PyTorch-Training, Dataset-Ingestion,
  Node-/Showdown-Oracle, Teacher, Self-Play, Evaluation, Reporting
```

PyTorch ist keine Pflichtabhängigkeit der Runtime-Base.

## Betriebsmodi

| Modus | Python | `poke-engine` | Rust | Node/Showdown | PyTorch |
|---|---:|---:|---:|---:|---:|
| Client + Legal-Fallback | ja | nein | nein | nein | nein |
| Live Search | ja | ja | nein bei Wheel | nein | nur Modellmodus |
| Lokaler Oracle-Test | ja | optional | nein bei Wheel | ja | nein |
| Differentialtest | ja | ja | kontrollierter Build | ja | nein |
| Search-Entwicklung | ja | ja | meist ja | ja | optional |
| Training | ja | pipelineabhängig | optional | optional | ja |
| Release-Evaluation | ja | ja | kontrollierter Build | ja | modellabhängig |

## Versionierung während `0.x`

```text
battlebelief-core    X.Y.Z
battlebelief-runtime X.Y.Z  requires core == X.Y.Z
battlebelief-lab     X.Y.Z  requires core == X.Y.Z, runtime == X.Y.Z
```

Kompatible Versionsbereiche werden erst nach stabilen öffentlichen APIs und
Schemas eingeführt.

## Isolierte Smokes nach Phase

M0:

```text
install core only → import all core modules
install runtime base only → run `battlebelief --version` and
                            `battlebelief doctor`
install lab only → run `battlebelief-lab --version` and
                   `battlebelief-lab doctor`
```

Die beiden Runtime-Kommandos prüfen in M0 ausschließlich Paket-, Entry-Point-
und Kompositionsbereitschaft. Eine kampffähige Legal-/Heuristikpolicy wird
erst in M1 eingeführt.

Die Lab-Kommandos prüfen in M0 ausschließlich Paket- und Entry-Point-
Bereitschaft. Sie starten weder einen Oracle noch eine Dataset-Pipeline.

M2:

```text
install runtime[search] → run actual Gen9 poke-engine sentinel
install lab oracle dependencies → run local Showdown oracle smoke
```

Das `search`-Extra und sein echtes Engine-Artefakt werden erst in M2
eingeführt. M0 verwendet weder einen leeren Suchadapter noch einen
Schein-Sentinel.

M3:

```text
install lab dataset dependencies → run replay and dataset ingestion smoke
```
