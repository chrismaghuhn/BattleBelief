from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from tools.canonicalize_manifest import manifest_digest
from tools.check_schemas import collect_schema_errors

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
V1_SCHEMA = SCHEMAS / "manifests" / "engine-capability.schema.json"
V1_EXAMPLE = SCHEMAS / "examples" / "engine-capability.example.json"
CATALOG = ROOT / "artifacts" / "gen9ou" / "m2" / "engine-capability-catalog-v1.json"
MANIFEST = (
    ROOT
    / "artifacts"
    / "gen9ou"
    / "m2"
    / "engine-capabilities"
    / "engine-capability-v2-unqualified.json"
)


def _document(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v1_engine_capability_schema_and_fixture_bytes_are_preserved() -> None:
    assert len(V1_SCHEMA.read_bytes()) == 5109
    assert hashlib.sha256(V1_SCHEMA.read_bytes()).hexdigest() == (
        "800dd53a40970fe1273ce01dbe13b9b306c5b600a0cd797f2eba5ec3df1814e6"
    )
    assert len(V1_EXAMPLE.read_bytes()) == 1190
    assert hashlib.sha256(V1_EXAMPLE.read_bytes()).hexdigest() == (
        "3f2aa796d17d028cd0135847f93401692ddc1417782ccd1c40be0f3f6a6daf76"
    )


def test_v2_catalog_and_unqualified_manifest_are_explicitly_registered_and_valid() -> None:
    catalog_schema = _document(SCHEMAS / "catalogs" / "engine-capability-catalog-v1.schema.json")
    manifest_schema = _document(SCHEMAS / "manifests" / "engine-capability-v2.schema.json")
    catalog = _document(CATALOG)
    manifest = _document(MANIFEST)

    assert list(Draft202012Validator(catalog_schema).iter_errors(catalog)) == []
    assert list(Draft202012Validator(manifest_schema).iter_errors(manifest)) == []
    assert manifest["claims"] == []
    assert all(
        manifest[name] is None
        for name in (
            "transition_adapter_id",
            "transition_adapter_version",
            "transition_adapter_source_digest",
            "transition_model_contract_digest",
            "transition_adapter_conformance_digest",
            "oracle_source_manifest_digest",
            "oracle_build_manifest_digest",
            "ruleset_digest",
            "corpus_digest",
            "runner_source_digest",
            "classifier_source_digest",
            "evidence_set_digest",
        )
    )
    assert collect_schema_errors(ROOT) == []


def test_v2_manifest_and_evidence_digest_freeze_is_key_order_independent() -> None:
    manifest = _document(MANIFEST)
    evidence = _document(SCHEMAS / "examples" / "engine-capability-evidence.example.json")

    manifest_round_trip = json.loads(json.dumps(manifest, sort_keys=True))
    evidence_round_trip = json.loads(json.dumps(evidence, sort_keys=True))

    assert manifest_digest(manifest_round_trip) == (
        "sha256:bab26386f675e9224539c1c695e84c950b46f866a3dd370828536c2916cb80bf"
    )
    assert manifest_digest(evidence_round_trip) == (
        "sha256:7a11f3e724a4bfffbbdf01b2e70f08d906a6e857a0bded978241047edeeaaf5d"
    )


def test_v2_catalog_is_the_only_capability_id_authority() -> None:
    catalog = _document(CATALOG)
    values = [definition["value"] for definition in catalog["definitions"]]
    assert values == sorted(values)
    assert len(values) == 13
    assert manifest_digest(catalog) == (
        "sha256:ee1d5db2d489035440602acb8decd87c727dfa04ddad832cdb9e208d8fb0d258"
    )
