---
document_id: operation-github-wiki-publication-design
title: GitHub Wiki Publication Design
document_type: operation
status: proposed
normative: false
version: 1
applies_to:
  - repository
effective_from: 2026-08-03
supersedes: []
superseded_by: null
owners:
  - maintainer
last_reviewed: 2026-08-03
---

# GitHub Wiki Publication Design

## Goal

Publish the reader-oriented English Markdown under [`wiki/`](../../../wiki/)
to the repository's actual GitHub Wiki. The accepted documentation under
[`docs/`](../../../docs/) remains authoritative.

This is a one-time publication. Automatic synchronization, changes to product
or runtime behavior, and changes to the prepared Wiki content are outside
scope.

## Published files

The publication copies these files without semantic changes:

- `Home.md`
- `Getting-Started.md`
- `Architecture.md`
- `Current-Status-and-Roadmap.md`
- `Development-and-Contributing.md`
- `Research-Scope-and-Safety.md`
- `_Sidebar.md`
- `_Footer.md`

`wiki/README.md` is a repository-side publishing note and is not copied to the
GitHub Wiki.

## Publication flow

1. Create the initial `Home` page through the authenticated GitHub web
   interface using the exact content of `wiki/Home.md`. This initializes the
   otherwise unavailable `.wiki.git` repository.
2. Clone the initialized Wiki repository into a dedicated temporary directory.
3. Copy the eight published files from the current repository checkout into
   the Wiki checkout, preserving their filenames and content.
4. Inspect the Wiki diff, stage only the intended path set, commit the files
   that differ from the initialized Wiki with the message
   `Create English project wiki`, detect the initialized Wiki branch, and push
   that branch without force.
5. Verify the public Wiki pages, navigation, footer, internal page links, and
   Mermaid rendering in GitHub.

## Safety and failure handling

- Do not modify or stage unrelated working-tree files.
- Do not publish `wiki/README.md`, credentials, packed teams, datasets, models,
  or local paths.
- Stop rather than guessing if GitHub initializes an unexpected repository or
  the target remote does not match `chrismaghuhn/BattleBelief.wiki.git`.
- Never force-push the Wiki.
- If initialization or publication fails, leave the prepared source unchanged
  and report the exact failed step.

## Validation

The publication is successful when:

- the GitHub Wiki Home page loads publicly;
- all six reader pages are reachable from `_Sidebar.md`;
- `_Footer.md` appears on Wiki pages;
- Wiki links do not lead to page-creation prompts;
- Mermaid diagrams render or, if GitHub does not support them in this context,
  the limitation is reported without changing the authoritative source; and
- the final Wiki Git tree contains exactly the eight intended Markdown files
  and does not contain `wiki/README.md`.
