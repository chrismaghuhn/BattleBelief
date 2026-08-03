---
document_id: plan-github-wiki-publication
title: GitHub Wiki Publication Implementation Plan
document_type: roadmap
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

# GitHub Wiki Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the eight prepared reader-facing Markdown files from
`wiki/` to the actual GitHub Wiki for `chrismaghuhn/BattleBelief` without
changing their meaning or publishing the repository-only `wiki/README.md`.

**Architecture:** Initialize the empty GitHub Wiki with `Home.md` through the
authenticated GitHub web interface, then use the resulting separate
`BattleBelief.wiki.git` repository for the complete publication. Validate the
source set before publication, push without force, and verify both the Wiki Git
tree and the rendered public pages afterward.

**Tech Stack:** GitHub Wiki, Git, GitHub CLI, authenticated browser, PowerShell

---

## File map

Repository files read without modification:

- `wiki/Home.md`
- `wiki/Getting-Started.md`
- `wiki/Architecture.md`
- `wiki/Current-Status-and-Roadmap.md`
- `wiki/Development-and-Contributing.md`
- `wiki/Research-Scope-and-Safety.md`
- `wiki/_Sidebar.md`
- `wiki/_Footer.md`

Repository file explicitly excluded from publication:

- `wiki/README.md`

External target files created or updated in the temporary Wiki checkout:

- `Home.md`
- `Getting-Started.md`
- `Architecture.md`
- `Current-Status-and-Roadmap.md`
- `Development-and-Contributing.md`
- `Research-Scope-and-Safety.md`
- `_Sidebar.md`
- `_Footer.md`

## Task 1: Validate source and target identity

**Files:**

- Read: `wiki/Home.md`
- Read: `wiki/Getting-Started.md`
- Read: `wiki/Architecture.md`
- Read: `wiki/Current-Status-and-Roadmap.md`
- Read: `wiki/Development-and-Contributing.md`
- Read: `wiki/Research-Scope-and-Safety.md`
- Read: `wiki/_Sidebar.md`
- Read: `wiki/_Footer.md`
- Exclude: `wiki/README.md`

- [ ] **Step 1: Confirm the local repository and remote**

Run:

```powershell
git rev-parse --show-toplevel
git remote get-url origin
git diff --exit-code origin/main -- wiki
git status --short -- wiki
```

Expected: the repository root is the BattleBelief checkout, the remote is
`https://github.com/chrismaghuhn/BattleBelief.git`, and the final two commands
produce no output.

- [ ] **Step 2: Assert the exact publication set**

Run:

```powershell
$wikiSourceFiles = @(
  'Home.md',
  'Getting-Started.md',
  'Architecture.md',
  'Current-Status-and-Roadmap.md',
  'Development-and-Contributing.md',
  'Research-Scope-and-Safety.md',
  '_Sidebar.md',
  '_Footer.md'
)
$actualWikiFiles = Get-ChildItem -LiteralPath 'wiki' -File |
  Where-Object Name -ne 'README.md' |
  ForEach-Object Name
$wikiFileDifference = Compare-Object $wikiSourceFiles $actualWikiFiles
if ($wikiFileDifference) {
  $wikiFileDifference | Format-Table
  throw 'The prepared Wiki source set differs from the approved publication set.'
}
```

Expected: no output and no exception.

- [ ] **Step 3: Run the repository's documentation gate**

Run:

```powershell
uv run python tools/check_docs.py
```

Expected: `PASS: documentation, authority, links, migration, and archive integrity`.

- [ ] **Step 4: Confirm the intended GitHub repository has Wiki enabled**

Run:

```powershell
gh api repos/chrismaghuhn/BattleBelief --jq '{html_url,has_wiki}'
```

Expected: `html_url` is `https://github.com/chrismaghuhn/BattleBelief` and
`has_wiki` is `true`.

## Task 2: Initialize the empty GitHub Wiki

**Files:**

- Read: `wiki/Home.md`
- Create externally: `Home.md` in `BattleBelief.wiki.git`

- [ ] **Step 1: Open the authenticated Wiki creation page**

Open `https://github.com/chrismaghuhn/BattleBelief/wiki/_new` in an
authenticated browser.

Expected: GitHub displays the form for the first Wiki page. Stop if the page is
not for `chrismaghuhn/BattleBelief` or the account cannot edit it.

- [ ] **Step 2: Create the initial Home page**

Set the page title to `Home`, copy the complete contents of `wiki/Home.md` into
the page body, and use GitHub's page-save action once.

Expected: GitHub opens
`https://github.com/chrismaghuhn/BattleBelief/wiki` and renders the BattleBelief
Home page.

- [ ] **Step 3: Confirm that initialization created the Wiki Git repository**

Run:

```powershell
git ls-remote https://github.com/chrismaghuhn/BattleBelief.wiki.git
```

Expected: at least one commit SHA and one branch reference are printed. Stop if
the repository still reports `Repository not found`.

## Task 3: Publish the complete page set through Git

**Files:**

- Read: the eight approved files under `wiki/`
- Create or update externally: the matching eight files in the temporary Wiki
  checkout

- [ ] **Step 1: Create a dedicated temporary target and clone the Wiki**

Run in the BattleBelief repository:

```powershell
$wikiPublishRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
  'battlebelief-wiki-' + [guid]::NewGuid().ToString('N')
)
New-Item -ItemType Directory -Path $wikiPublishRoot | Out-Null
git clone https://github.com/chrismaghuhn/BattleBelief.wiki.git $wikiPublishRoot
```

Expected: cloning succeeds into a new path whose final directory name starts
with `battlebelief-wiki-`.

- [ ] **Step 2: Validate the cloned target before copying**

Run:

```powershell
$wikiRemote = git -C $wikiPublishRoot remote get-url origin
$wikiBranch = git -C $wikiPublishRoot branch --show-current
if ($wikiRemote -ne 'https://github.com/chrismaghuhn/BattleBelief.wiki.git') {
  throw "Unexpected Wiki remote: $wikiRemote"
}
if ([string]::IsNullOrWhiteSpace($wikiBranch)) {
  throw 'The initialized Wiki has no current branch.'
}
```

Expected: no output and no exception.

- [ ] **Step 3: Copy only the approved publication files**

Run from the BattleBelief repository:

```powershell
foreach ($wikiFile in $wikiSourceFiles) {
  Copy-Item -LiteralPath (Join-Path 'wiki' $wikiFile) `
    -Destination (Join-Path $wikiPublishRoot $wikiFile) -Force
}
```

Expected: the command succeeds without creating `README.md` in the Wiki
checkout.

- [ ] **Step 4: Verify the final tracked path set and content**

Run:

```powershell
git -C $wikiPublishRoot add -- $wikiSourceFiles
$trackedWikiFiles = git -C $wikiPublishRoot ls-files
$trackedDifference = Compare-Object $wikiSourceFiles $trackedWikiFiles
if ($trackedDifference) {
  $trackedDifference | Format-Table
  throw 'The Wiki Git tree does not contain exactly the approved files.'
}
foreach ($wikiFile in $wikiSourceFiles) {
  $sourceText = (Get-Content -Raw (Join-Path 'wiki' $wikiFile)) -replace "`r`n", "`n"
  $targetText = (Get-Content -Raw (Join-Path $wikiPublishRoot $wikiFile)) -replace "`r`n", "`n"
  if ($sourceText -cne $targetText) {
    throw "Published content differs for $wikiFile"
  }
}
git -C $wikiPublishRoot diff --cached --check
git -C $wikiPublishRoot status --short
```

Expected: the tracked-file and content comparisons produce no exception,
`diff --cached --check` produces no output, and `status --short` lists only
approved Wiki files.

- [ ] **Step 5: Commit the files that differ from the initialized Wiki**

Run:

```powershell
$pendingWikiPaths = git -C $wikiPublishRoot diff --cached --name-only
if (-not $pendingWikiPaths) {
  throw 'The Wiki checkout has no publication changes to commit.'
}
$unexpectedWikiPaths = Compare-Object $wikiSourceFiles $pendingWikiPaths |
  Where-Object SideIndicator -eq '=>'
if ($unexpectedWikiPaths) {
  $unexpectedWikiPaths | Format-Table
  throw 'The pending Wiki commit contains an unapproved path.'
}
git -C $wikiPublishRoot commit -m 'Create English project wiki'
```

Expected: Git creates one commit containing only the approved paths that differ
from the initialized `Home.md` commit.

- [ ] **Step 6: Push the detected Wiki branch without force**

Run:

```powershell
git -C $wikiPublishRoot push origin $wikiBranch
```

Expected: Git reports a successful update to the detected branch. Do not retry
with `--force` if the push is rejected.

## Task 4: Verify the published Wiki

**Files:**

- Inspect externally: all eight tracked Wiki files and six rendered pages

- [ ] **Step 1: Verify the remote commit and exact final tree**

Run:

```powershell
$wikiHead = git -C $wikiPublishRoot rev-parse HEAD
$remoteWikiHead = git -C $wikiPublishRoot ls-remote origin "refs/heads/$wikiBranch" |
  ForEach-Object { ($_ -split "`t")[0] }
if ($wikiHead -ne $remoteWikiHead) {
  throw 'The remote Wiki branch does not match the verified local commit.'
}
$finalWikiFiles = git -C $wikiPublishRoot ls-tree -r --name-only HEAD
$finalTreeDifference = Compare-Object $wikiSourceFiles $finalWikiFiles
if ($finalTreeDifference) {
  $finalTreeDifference | Format-Table
  throw 'The published Wiki tree differs from the approved eight-file set.'
}
git -C $wikiPublishRoot show --stat --oneline HEAD
```

Expected: local and remote SHAs match, the tree comparison produces no output,
and the commit summary names only approved Wiki paths.

- [ ] **Step 2: Check every public page URL**

Open each URL in the browser:

```text
https://github.com/chrismaghuhn/BattleBelief/wiki
https://github.com/chrismaghuhn/BattleBelief/wiki/Getting-Started
https://github.com/chrismaghuhn/BattleBelief/wiki/Architecture
https://github.com/chrismaghuhn/BattleBelief/wiki/Current-Status-and-Roadmap
https://github.com/chrismaghuhn/BattleBelief/wiki/Development-and-Contributing
https://github.com/chrismaghuhn/BattleBelief/wiki/Research-Scope-and-Safety
```

Expected: every URL renders an existing Wiki page rather than a page-creation
prompt or an error.

- [ ] **Step 3: Check navigation and rendering**

On the rendered pages, verify that the sidebar lists all six pages, every
sidebar and Home-page Wiki link resolves, the affiliation footer is visible,
and the Mermaid diagrams on `Home` and `Architecture` render as diagrams.

Expected: navigation and footer are present throughout the Wiki, no internal
link offers to create a missing page, and both Mermaid diagrams are visible.
If GitHub displays Mermaid source instead, record that rendering limitation and
leave the authoritative source unchanged.

- [ ] **Step 4: Confirm the source repository remains untouched by publication**

Run from the BattleBelief repository:

```powershell
git diff --exit-code origin/main -- wiki
git status -sb
```

Expected: the Wiki source diff produces no output. Repository status lists only
the intentional planning commits and the pre-existing untracked Canvas files.

## Task 5: Report the publication evidence

**Files:**

- No file changes

- [ ] **Step 1: Record the evidence in the handoff**

Report:

- the public Wiki Home URL;
- the pushed Wiki branch and commit SHA;
- the eight-file final-tree verification;
- the rendered navigation, footer, internal-link, and Mermaid results;
- `tools/check_docs.py` output; and
- confirmation that `wiki/README.md` and the two untracked Canvas files were
  not published or modified.

Expected: the handoff distinguishes successful checks from any rendering or
access limitation and does not claim unperformed validation.
