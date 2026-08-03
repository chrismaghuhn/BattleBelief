# Research, Scope, and Safety

BattleBelief is a research project, not a finished competitive bot. Its central goal is to test a specific decision-making thesis under controlled resource and reproducibility constraints.

## Research thesis

The project investigates whether all three of the following improve Gen 9 OU decisions over simpler registered baselines:

1. an explicit **open-world belief** over complete hidden Pokémon sets;
2. **information-set DUCT** search over uncertain worlds;
3. an authoritative, independent **Showdown action-safety gate**.

The comparison is intended to use fixed CPU, wall-time, data, seed, and reproducibility budgets. Additional complexity is not considered successful merely because it is technically sophisticated.

## Experimental discipline

BattleBelief separates:

- implementation from qualification;
- qualification from measured benefit;
- development pools from selection pools;
- selection evidence from release holdouts;
- mechanism analysis from deployment utility;
- belief quality from battle strength;
- internal resource-controlled comparisons from external context comparisons.

Hypotheses, evaluation arms, metrics, budget profiles, and stop-or-pivot criteria are intended to be registered before expensive search or training experiments.

A negative result is a valid research outcome. Search, belief, or models should be simplified or redirected when they fail their predefined gates.

## Supported battle scope

Current target:

- Pokémon Singles;
- Smogon Gen 9 OU;
- fixed teams selected before each battle;
- public CPU runtime as the eventual M5 target.

Outside current scope:

- Doubles;
- VGC;
- changing teams during a battle;
- claiming a universal battle abstraction from one format;
- unqualified private-server authentication;
- unrestricted autonomous public-ladder deployment.

Additional Singles formats require their own ruleset, target-population, capability, and strength artifacts.

## Open-world belief

A closed-world system assumes the hidden opponent set must belong to a finite known catalogue. BattleBelief instead plans to reserve probability mass for unknown or unsupported possibilities through an `OTHER` component.

The open-world design is intended to avoid silently treating imputed or catalogue-limited hidden information as ground truth. Hypotheses should be materialized under explicit controls and evaluated for calibration, coverage, and downstream decision utility.

The complete open-world belief system is a later milestone and is not currently implemented as a finished production capability.

## Search and eligibility

Information-set search may run only when the required engine capabilities, state support, legal actions, budgets, and safety conditions are qualified.

Unsupported or uncertain capabilities must fail closed to the deterministic legal heuristic fallback. The fallback is part of the evaluated system, not an exceptional path that may be omitted from reported results.

## Action safety

The final action gate is intentionally independent from the policy or search procedure. Before dispatch, it verifies that the candidate action:

- belongs to the latest authoritative safe submission set;
- answers the current request;
- uses the matching `rqid`;
- is compatible with pending-state reconciliation;
- can be encoded as a valid Showdown command.

A strong policy does not bypass this gate.

## Credential safety

The current challenge CLI reads the Showdown password exclusively from:

```text
BATTLEBELIEF_SHOWDOWN_PASSWORD
```

Passwords must not appear in:

- command-line arguments;
- source files;
- Git history;
- logs;
- screenshots;
- issue or pull-request text;
- test fixtures;
- captured terminal output.

Use a dedicated test account for approved public-network testing. Remove the environment variable after use.

## Team and replay privacy

Packed teams, usernames, replay corpora, and battle traces may contain private or identifying information.

Before publishing an artifact:

- remove credentials and cookies;
- review usernames and replay metadata;
- remove local paths and private server addresses;
- confirm that the dataset is permitted for redistribution;
- document whether data is observed, reconstructed, generated, or imputed;
- avoid emitting hidden-state information into public decision records.

## Data and model licensing

Source code is Apache-2.0, but datasets, checkpoints, and model artifacts may require separate licenses.

Every external dataset should record its source, revision, license, and manifest. Model artifacts should identify the classes of training data used and their licenses. Non-commercial or otherwise restricted checkpoints must remain separate from the Apache-2.0 source distribution.

## Claims policy

BattleBelief uses narrow claims:

- green CI means integration checks passed;
- a completed milestone means its specific gate passed;
- implemented code is not automatically qualified;
- better offline metrics do not automatically imply stronger battle decisions;
- only M5 permits an MVP and strength-qualified claim;
- later human or ladder validation remains a separate M6 claim.

## Affiliation

BattleBelief is unofficial and is not affiliated with Nintendo, Game Freak, Creatures Inc., Smogon, or Pokémon Showdown.
