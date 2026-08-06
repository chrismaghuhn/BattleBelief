"""Focused malformed-input tests for the staged artifact verifier."""

from pathlib import Path

import pytest
from tools.verify_poke_engine_artifact import ArtifactVerificationError, _canonical_document


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_canonical_document_rejects_nonfinite_json_as_unreadable(
    tmp_path: Path, constant: str
) -> None:
    document = tmp_path / "manifest.json"
    document.write_text('{"value":' + constant + "}\n", encoding="utf-8")

    with pytest.raises(ArtifactVerificationError, match="artifact input is unreadable"):
        _canonical_document(document, "engine-source.schema.json")
