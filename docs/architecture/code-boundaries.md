---
document_id: architecture-code-boundaries
title: Code- und Paketgrenzen
document_type: architecture
status: accepted
normative: true
version: 2
applies_to:
  - repository
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# Code- und Paketgrenzen

## Pakete

```text
packages/
├─ battlebelief-core/
│  └─ src/battlebelief_core/
│     ├─ domain/
│     │  ├─ events/
│     │  ├─ state/
│     │  ├─ actions/
│     │  ├─ belief/
│     │  ├─ teams/
│     │  └─ schemas/
│     ├─ ports/
│     │  ├─ battle_transport
│     │  ├─ transition_model
│     │  ├─ meta_prior_provider
│     │  ├─ policy_value_evaluator
│     │  ├─ trace_sink
│     │  ├─ clock
│     │  └─ random_source
│     └─ application/
│        ├─ battle_session/
│        ├─ observation/
│        ├─ decision/
│        ├─ search/
│        ├─ engine_eligibility/
│        └─ safety/
│
├─ battlebelief-runtime/
│  └─ src/battlebelief_runtime/
│     ├─ adapters/
│     │  ├─ showdown_protocol/
│     │  ├─ showdown_client/
│     │  ├─ poke_engine/
│     │  ├─ sqlite_meta/
│     │  ├─ model_inference/
│     │  ├─ team_files/
│     │  └─ telemetry/
│     ├─ public_api/
│     ├─ testing/
│     ├─ composition/
│     └─ cli/
│
└─ battlebelief-lab/
   └─ src/battlebelief_lab/
      ├─ oracle/showdown/
      ├─ datasets/
      ├─ replay_mining/
      ├─ teacher/
      ├─ selfplay/
      ├─ training/
      ├─ evaluation/
      └─ reporting/
```

## Importkanten

Die Pfeile bedeuten „darf importieren“:

```text
battlebelief-runtime ──────► battlebelief-core
battlebelief-lab ──────────► battlebelief-core
battlebelief-lab ──────────► battlebelief-runtime
```

```text
core imports:    weder runtime noch lab
runtime imports: core, niemals lab
lab imports:     core und freigegebene Runtime-APIs
```

Freigegebene Lab-Zugriffe:

```text
battlebelief_runtime.adapters
battlebelief_runtime.testing
battlebelief_runtime.public_api
```

Nicht freigegeben sind private CLI-, Composition- und Implementierungsmodule.

## Core-Reinheit

Core darf kennen:

- Standardbibliothek;
- bewusst genehmigte kleine Typ-/Validierungsbibliotheken;
- unveränderliche Domainobjekte;
- Ports, Search, Belief, Reducer, Safety und Eligibility;
- kanonische Events und Schemas.

Core darf nicht kennen:

- WebSockets oder Showdown-Wire-Zeilen;
- Dateipfade und Umgebungsvariablen;
- SQLite, DuckDB, PyArrow;
- `poke-engine`;
- Node-Prozesse;
- PyTorch, ONNX Runtime oder CUDA;
- konkrete Logger oder Telemetrie;
- globale Zeit- oder Zufallsquellen.

```text
Showdown wire message       → Runtime
Canonical BattleEvent       → Core
ObservedState reducer       → Core
Showdown command encoding   → Runtime
```

## Ports

`MetaPriorProvider` lädt einen unveränderlichen `MetaPriorSnapshot`. Der Port
kennt keine Datenbank oder Querymethoden.

`PolicyValueEvaluator` beschreibt ausschließlich Inferenz. Download,
Checkpointladen, Gerätewahl, Training und Optimizerzustand liegen außerhalb.

## Adapter

Leaf-Adapter importieren oder konstruieren keine anderen Leaf-Adapter.
Decorators und zusammengesetzte Adapter sind zulässig, wenn der Composition
Root sie erzeugt und die Komposition einen Core-Port implementiert.

## Tests

| Bereich | Verantwortung |
|---|---|
| Pakettests | Unit- und Paketverträge |
| Contract-Tests | alle Adapter gegen dieselbe Port-Suite |
| Integration | Composition Root und reale Adapterkombinationen |
| Differential | Showdown gegen `poke-engine` |
| Release | versiegelte Evaluationspfade |

Die maschinelle Durchsetzung steht in
[GitHub, CI und Security](../project/github-ci-security.md).
