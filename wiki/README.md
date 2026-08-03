# BattleBelief Wiki Source

This directory contains the English Markdown source prepared for the GitHub Wiki.

## Pages

- `Home.md`
- `Getting-Started.md`
- `Architecture.md`
- `Current-Status-and-Roadmap.md`
- `Development-and-Contributing.md`
- `Research-Scope-and-Safety.md`
- `_Sidebar.md`
- `_Footer.md`

`README.md` is a publishing note and should not be copied into the Wiki repository.

## Publish through the GitHub web interface

For an empty Wiki:

1. Open `https://github.com/chrismaghuhn/BattleBelief/wiki/_new`.
2. Create the first page with title `Home` and copy the contents of `Home.md`.
3. Create the remaining pages with titles matching their filenames, without the `.md` extension.
4. Add `_Sidebar.md` and `_Footer.md` through the Wiki Git repository after the first page initializes it, or create equivalent navigation manually.

## Publish through Git

After the Wiki has been initialized with its first page:

```bash
git clone https://github.com/chrismaghuhn/BattleBelief.wiki.git
cd BattleBelief.wiki
```

Copy the page files from this directory into the Wiki checkout, excluding this `README.md`, then commit and push:

```bash
git add Home.md Getting-Started.md Architecture.md \
  Current-Status-and-Roadmap.md Development-and-Contributing.md \
  Research-Scope-and-Safety.md _Sidebar.md _Footer.md
git commit -m "Create English project wiki"
git push origin master
```

Depending on how GitHub initializes the Wiki repository, the default Wiki branch may be `master`. Check `git branch --show-current` before pushing and use that branch name.

## Maintenance rule

The repository documentation under `docs/` remains authoritative. Wiki pages are an English reader-oriented overview. When behavior or milestone status changes:

1. update the authoritative repository document first;
2. update the corresponding Wiki source page in the same or a follow-up pull request;
3. publish the updated page to the GitHub Wiki.
