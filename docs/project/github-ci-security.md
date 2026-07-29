---
document_id: project-github-ci-security
title: GitHub, CI und Security
document_type: operation
status: accepted
normative: true
version: 1
applies_to:
  - repository
  - github
effective_from: 2026-07-29
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-07-29
---

# GitHub, CI und Security

## Entwicklungsworkflow

- `main` ist die kanonische Integrationsbasis.
- Änderungen laufen über kurze `feat/`, `fix/` oder `docs/`-Branches.
- Ein Pull Request behandelt ein zusammenhängendes Thema.
- Draft-PRs dienen frühem Feedback.
- Erfolgreiche PRs werden per Squash gemergt.
- Gemergte Feature-Branches werden automatisch gelöscht.
- Bei niedrigem PR-Volumen gibt es weder `develop`, Gitflow noch Merge Queue.

Ein grüner `main` bedeutet nur: installierbar, startfähig und alle
merge-blockierenden Correctness-, Contract-, Schema- und Safety-Smokes
bestanden. Er ist kein Strength-, vollständiger Paritäts- oder Release-Claim.

## Schutz von `main`

- Pull Request erforderlich;
- Diskussionen aufgelöst;
- lineare Historie;
- keine Force-Pushes oder Löschung von `main`;
- zunächst keine Pflichtfreigabe für den Solo-Maintainer;
- ab einem zweiten aktiven Maintainer eine Freigabe für relevante Änderungen;
- kein Bypass in normaler Entwicklung.

Ein eng begrenzter PR-only-Break-Glass-Weg ist nur zur Repository- oder
Sicherheitswiederherstellung erlaubt. Er benötigt Issue, Begründung, exakten
Commit und unmittelbar folgenden Reparatur-PR. Er darf niemals einen Release-,
Evaluation- oder Strength-Claim erzeugen.

## Stabiler Required Check

Das Ruleset verlangt genau einen stabilen Status:

```text
pr-gate
```

Der Workflow:

- läuft bei jedem Pull Request;
- besitzt keine Workflow-Level-Pfadfilter;
- darf Jobs auf Job-Ebene bewusst überspringen;
- führt den Abschlussjob mit `if: always()` aus;
- prüft alle `needs.*.result`-Werte explizit;
- akzeptiert nur Erfolg oder bewusstes Überspringen;
- benötigt im Abschlussjob weder Checkout noch Netzwerk;
- hält den Checknamen stabil.

Merge-blockierende Jobs prüfen:

- Lint, Format und Typen;
- Unit-, Contract-, Protocol- und Reducertests;
- Schemas und Beispielmanifeste;
- Paket- und Architekturgrenzen;
- kleine Differential- und Gen9-Build-Smokes;
- Dependency Review und akzeptierte Lizenzregeln;
- die Dokumentationsgates aus
  [`documentation-governance`](../documentation-governance.md).

Die einzige normative Importregelliste steht in
[`architecture-code-boundaries`](../architecture/code-boundaries.md). CI
erzwingt diese Liste, definiert hier aber keine zweite Fassung. Die isolierten
Installationsprofile stehen in
[`architecture-dependency-matrix`](../architecture/dependency-matrix.md).

GPU-, Kaggle-, Ladder-, große Holdout- und vollständige Differentialläufe sind
nicht merge-blockierend. Sie erzeugen gesonderte Evidenz und Claims.

## Actions-Sicherheit

Standard:

```yaml
permissions:
  contents: read
```

Schreibrechte existieren nur im konkreten Release- oder Attestation-Job.
Fork-PRs erhalten keine Secrets oder Schreibrechte. Nicht vertrauenswürdiger
PR-Code, Caches oder Artefakte werden niemals in einem privilegierten
`pull_request_target`- oder `workflow_run`-Kontext ausgeführt.

Actions werden auf vollständige Commit-SHAs gepinnt. Dependabot pflegt Actions-
und Dependency-Pins; automatische Merges bleiben deaktiviert.

## Repository Security

Aktiviert werden:

- Secret Scanning;
- Push Protection;
- Private Vulnerability Reporting;
- Dependabot Alerts und Security Updates;
- wöchentliche, begrenzte Versions-PRs;
- `SECURITY.md`.

CodeQL Default Setup startet beratend. Nach Einführung von Rust- oder
Node-Quellcode wird geprüft, ob Python, JavaScript/TypeScript, Rust und Actions
tatsächlich erfasst werden. Bei Lücken folgt Advanced Setup. CodeQL ersetzt
weder Differentialtests noch den Gen9-Build-Sentinel.

## Geschützte Tags

Geschützte Muster:

```text
v*
eval-*
claim-*
```

Geschichtete Rulesets erlauben die Erzeugung nur durch den autorisierten,
getesteten Releaseprozess und verbieten Updates, Löschung und Force-Updates.
Der Tag verweist auf `main`; das Manifest liegt bereits im referenzierten
Commit. Tag-Schutz ersetzt keine Digests oder Attestations.

## Issues und Community-Dateien

Minimale Labelachsen:

```text
type: bug | feature | research | documentation
area: protocol | belief | engine | search | training | evaluation | teams
priority: blocking | high | normal
status: needs-decision | blocked-external
good-first-issue
```

Issueformulare: Bug, Engine-Divergenz, Forschungshypothese und Transfer-Audit.

Von Beginn an: `README.md`, `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`,
`CITATION.cff` und die verlinkte Architektur-, Evaluations-,
Reproduzierbarkeits- und Lizenzdokumentation. Ein `CODE_OF_CONDUCT.md` folgt
vor aktiver Werbung um Beiträge; Governance, CODEOWNERS und Supportkanäle erst
bei realen Zuständigkeiten.
