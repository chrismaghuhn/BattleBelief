"""Validate the data-only closure of a differential corpus."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

from battlebelief_core.domain.engine_capabilities import CapabilityCatalog
from battlebelief_lab.differential.corpus import CorpusValidationError, DifferentialCorpus
from battlebelief_lab.registration_validation import (
    RegistrationValidationError,
    load_json_strict,
)


def collect_errors(repository_root: Path) -> list[str]:
    """Return fail-closed corpus validation errors without running either backend."""

    catalog_path = repository_root / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json"
    if not catalog_path.is_file():
        return ["engine capability catalog is missing"]
    try:
        catalog = CapabilityCatalog.from_document(load_json_strict(catalog_path))
    except (OSError, RegistrationValidationError, TypeError, ValueError):
        return ["engine capability catalog is invalid"]
    corpus_directory = repository_root / "artifacts/gen9ou/m2/differential/corpus-v1"
    if not corpus_directory.is_dir():
        return ["differential corpus is missing"]
    try:
        corpus = DifferentialCorpus.load(corpus_directory, catalog)
    except (CorpusValidationError, OSError, OverflowError, RecursionError, TypeError, ValueError):
        return ["differential corpus is invalid"]
    if not isinstance(corpus, DifferentialCorpus):
        return ["differential corpus is invalid"]
    classifier_path = (
        repository_root
        / "packages/battlebelief-lab/src/battlebelief_lab/differential/classifier.py"
    )
    if not classifier_path.is_file():
        return ["differential classifier source is missing"]
    try:
        actual_digest = "sha256:" + sha256(classifier_path.read_bytes()).hexdigest()
    except OSError:
        return ["differential classifier source is unreadable"]
    if corpus.classifier_source_digest != actual_digest:
        return ["differential classifier source digest does not match the corpus index"]
    return []


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parsed = parser.parse_args(arguments)
    errors = collect_errors(parsed.root)
    if errors:
        print(*errors, sep="\n")
        return 1
    print("PASS: differential corpus closure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
