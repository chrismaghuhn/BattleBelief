from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_core.domain.engine_capabilities import (
    CapabilityApproximation,
    CapabilityCatalog,
    CapabilityClaim,
    CapabilityDefinition,
    CapabilityEvidenceRef,
    CapabilityId,
    CapabilityStatus,
    EngineCapabilityManifest,
    EngineEnvironmentBinding,
)

ROOT = Path(__file__).resolve().parents[4]


def _document(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


def _catalog(digest: str = _digest("a")) -> CapabilityCatalog:
    catalog = CapabilityCatalog.create(
        catalog_id="gen9-ou-v1",
        catalog_version="1",
        capability_contract_digest=_digest("0"),
        canonicalization_contract_digest=_digest("e"),
        definitions=(
            CapabilityDefinition(value="gen9.battle.damage", description="Damage resolution."),
            CapabilityDefinition(value="gen9.battle.turn", description="Turn progression."),
        ),
    )
    if digest == _digest("a"):
        return catalog
    return CapabilityCatalog.create(
        catalog_id=catalog.catalog_id,
        catalog_version="2",
        capability_contract_digest=catalog.capability_contract_digest,
        canonicalization_contract_digest=catalog.canonicalization_contract_digest,
        definitions=catalog.definitions,
    )


def _binding() -> EngineEnvironmentBinding:
    return EngineEnvironmentBinding(
        environment_cell_id="cp312-win-amd64",
        engine_build_manifest_digest=_digest("2"),
        wheel_digest=_digest("4"),
    )


def _evidence(capability_value: str = "gen9.battle.damage") -> CapabilityEvidenceRef:
    binding = _binding()
    catalog = _catalog()
    return CapabilityEvidenceRef(
        evidence_id=("fixture-evidence" if capability_value.endswith("damage") else "fixture-turn"),
        evidence_digest=_digest("f" if capability_value.endswith("damage") else "0"),
        catalog_id=catalog.catalog_id,
        catalog_version=catalog.catalog_version,
        capability_id=catalog.id_for(capability_value),
        catalog_digest=catalog.catalog_digest,
        canonicalization_contract_digest=catalog.canonicalization_contract_digest,
        environment_cell_id=binding.environment_cell_id,
        engine_source_manifest_digest=_digest("1"),
        engine_build_manifest_digest=binding.engine_build_manifest_digest,
        artifact_index_digest=_digest("3"),
        wheel_digest=binding.wheel_digest,
        transition_adapter_id="poke-engine-transition",
        transition_adapter_version="1.0.0",
        transition_adapter_source_digest=_digest("5"),
        transition_model_contract_digest=_digest("6"),
        transition_adapter_conformance_digest=_digest("7"),
        oracle_source_manifest_digest=_digest("8"),
        oracle_build_manifest_digest=_digest("9"),
        ruleset_digest=_digest("b"),
        corpus_digest=_digest("c"),
        runner_source_digest=_digest("e"),
        classifier_source_digest=_digest("a"),
        qualification_result_schema_id="urn:battlebelief:schema:fixture-result:v1",
        qualification_result_digest=_digest("d"),
    )


def _manifest(
    *claims: CapabilityClaim, evidence_set_digest: str | None = None
) -> EngineCapabilityManifest:
    evidence_refs = tuple(dict.fromkeys(ref for claim in claims for ref in claim.evidence_refs))
    return EngineCapabilityManifest(
        manifest_id="gen9-ou-engine-v2",
        catalog=_catalog(),
        generation=9,
        format="gen9ou",
        engine_source_manifest_digest=_digest("1"),
        artifact_index_digest=_digest("3"),
        environment_bindings=(_binding(),),
        transition_adapter_id="poke-engine-transition",
        transition_adapter_version="1.0.0",
        transition_adapter_source_digest=_digest("5"),
        transition_model_contract_digest=_digest("6"),
        transition_adapter_conformance_digest=_digest("7"),
        oracle_source_manifest_digest=_digest("8"),
        oracle_build_manifest_digest=_digest("9"),
        ruleset_digest=_digest("b"),
        corpus_digest=_digest("c"),
        runner_source_digest=_digest("e"),
        classifier_source_digest=_digest("a"),
        evidence_set_digest=(
            EngineCapabilityManifest.evidence_set_digest_for(evidence_refs)
            if evidence_set_digest is None
            else evidence_set_digest
        ),
        canonicalization_contract_digest=_digest("e"),
        claims=claims,
    )


class TestCapabilityCatalog:
    def test_issues_catalog_bound_ids_without_public_constructor(self) -> None:
        catalog = _catalog()
        capability = catalog.id_for("gen9.battle.damage")

        assert capability.value == "gen9.battle.damage"
        assert capability.catalog_digest == catalog.catalog_digest
        assert "catalog_digest" not in repr(capability)
        with pytest.raises(TypeError):
            type(capability)("gen9.battle.damage", catalog.catalog_digest)

    @pytest.mark.parametrize(
        "value",
        [
            "Gen9.battle.damage",
            "gen9.battle",
            "gen9..damage",
            "gen9.battle.damage!",
            "gen9.battle." + "a" * 117,
        ],
    )
    def test_rejects_noncanonical_capability_ids(self, value: str) -> None:
        with pytest.raises(ValueError):
            CapabilityDefinition(value=value, description="valid test definition")

    def test_rejects_foreign_ids_and_treats_missing_claim_as_unknown(self) -> None:
        catalog = _catalog()
        foreign = _catalog(_digest("d")).id_for("gen9.battle.damage")
        manifest = EngineCapabilityManifest.create_unqualified(
            manifest_id="initial-unqualified",
            catalog=catalog,
            generation=9,
            format="gen9ou",
            engine_source_manifest_digest=_digest("1"),
            artifact_index_digest=_digest("3"),
            environment_bindings=(),
            canonicalization_contract_digest=_digest("e"),
        )

        with pytest.raises(ValueError):
            catalog.require(foreign)
        assert manifest.status_for(catalog.id_for("gen9.battle.damage")) is CapabilityStatus.UNKNOWN

    def test_catalog_requires_canonical_definition_order(self) -> None:
        with pytest.raises(ValueError):
            CapabilityCatalog.create(
                catalog_id="gen9-ou-v1",
                catalog_version="1",
                capability_contract_digest=_digest("0"),
                canonicalization_contract_digest=_digest("e"),
                definitions=(
                    CapabilityDefinition(value="gen9.battle.turn", description="Turn progression."),
                    CapabilityDefinition(
                        value="gen9.battle.damage", description="Damage resolution."
                    ),
                ),
            )

    def test_named_public_identity_values_match_schema_grammar(self) -> None:
        with pytest.raises(ValueError):
            EngineEnvironmentBinding(
                environment_cell_id="Private Host Cell",
                engine_build_manifest_digest=_digest("2"),
                wheel_digest=_digest("4"),
            )
        with pytest.raises(ValueError):
            dataclasses.replace(_evidence(), transition_adapter_id="Private Adapter")
        with pytest.raises(ValueError):
            dataclasses.replace(_evidence(), environment_cell_id="Private Host Cell")
        with pytest.raises(ValueError):
            dataclasses.replace(
                _evidence(), qualification_result_schema_id="engine-capability-evidence-v1"
            )
        with pytest.raises(ValueError):
            dataclasses.replace(_manifest(), manifest_id="Private Manifest")

    def test_evidence_document_rejects_non_integer_schema_version(self) -> None:
        document: dict[str, object] = _evidence().document()
        document.pop("evidence_digest")
        document["schema_version"] = True

        with pytest.raises(ValueError, match="schema version 1"):
            CapabilityEvidenceRef.from_document(document, _catalog())


class TestCapabilityClaims:
    def test_status_requirements_and_evidence_binding(self) -> None:
        catalog = _catalog()
        capability = catalog.id_for("gen9.battle.damage")
        evidence = _evidence()
        exact = CapabilityClaim(capability, CapabilityStatus.EXACT, evidence_refs=(evidence,))
        bounded = CapabilityClaim(
            catalog.id_for("gen9.battle.turn"),
            CapabilityStatus.BOUNDED_APPROXIMATION,
            evidence_refs=(_evidence("gen9.battle.turn"),),
            approximation=CapabilityApproximation(
                metric_id="absolute-error",
                maximum="1",
                unit_id="hp",
                condition_id="fixed-corpus",
            ),
        )
        manifest = _manifest(exact, bounded)

        assert manifest.status_for(capability) is CapabilityStatus.EXACT
        assert manifest.status_for(bounded.capability_id) is CapabilityStatus.BOUNDED_APPROXIMATION
        assert "sha256:" not in repr(evidence)
        with pytest.raises(ValueError):
            CapabilityClaim(capability, CapabilityStatus.EXACT, evidence_refs=())
        with pytest.raises(ValueError):
            CapabilityClaim(capability, CapabilityStatus.UNSUPPORTED, evidence_refs=(evidence,))

    def test_bounded_claim_rejects_a_non_approximation_object(self) -> None:
        catalog = _catalog()

        with pytest.raises(ValueError, match="CapabilityApproximation"):
            CapabilityClaim(
                catalog.id_for("gen9.battle.damage"),
                CapabilityStatus.BOUNDED_APPROXIMATION,
                evidence_refs=(_evidence(),),
                approximation=object(),  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("metric_id", "Free prose"),
            ("maximum", "01"),
            ("maximum", "1.0"),
            ("maximum", "-1"),
            ("unit_id", "HP points"),
            ("condition_id", "fixed corpus"),
        ],
    )
    def test_approximation_requires_machine_readable_metric_maximum_unit_and_condition(
        self, field: str, value: str
    ) -> None:
        values = {
            "metric_id": "absolute-error",
            "maximum": "1",
            "unit_id": "hp",
            "condition_id": "fixed-corpus",
        }
        values[field] = value

        with pytest.raises(ValueError):
            CapabilityApproximation(**values)

    @pytest.mark.parametrize("maximum", ["0", "0.5", "0.25", "1", "1.5", "10.01"])
    def test_approximation_accepts_canonical_nonnegative_decimals(self, maximum: str) -> None:
        CapabilityApproximation(
            metric_id="absolute-error",
            maximum=maximum,
            unit_id="hp",
            condition_id="fixed-corpus",
        )
        schema = _document(ROOT / "schemas/manifests/engine-capability-v2.schema.json")
        assert (
            list(
                Draft202012Validator(
                    schema["$defs"]["approximation"]["properties"]["maximum"]
                ).iter_errors(maximum)
            )
            == []
        )

    @pytest.mark.parametrize(
        "maximum",
        ["00", ".5", "00.5", "0.0", "0.50", "1.0", "-0.5", "1e-3"],
    )
    def test_approximation_rejects_noncanonical_decimals_in_core_and_schema(
        self, maximum: str
    ) -> None:
        values = {
            "metric_id": "absolute-error",
            "maximum": maximum,
            "unit_id": "hp",
            "condition_id": "fixed-corpus",
        }
        with pytest.raises(ValueError, match="canonical non-negative decimal"):
            CapabilityApproximation(**values)

        schema = _document(
            Path(__file__).resolve().parents[4]
            / "schemas/manifests/engine-capability-v2.schema.json"
        )
        assert list(
            Draft202012Validator(
                schema["$defs"]["approximation"]["properties"]["maximum"]
            ).iter_errors(maximum)
        )

    def test_rejects_evidence_for_another_engine_environment(self) -> None:
        catalog = _catalog()
        evidence = dataclasses.replace(_evidence(), wheel_digest=_digest("e"))
        claim = CapabilityClaim(
            catalog.id_for("gen9.battle.damage"), CapabilityStatus.EXACT, evidence_refs=(evidence,)
        )

        with pytest.raises(ValueError):
            _manifest(claim)

    def test_catalog_digest_is_derived_and_ids_remain_digest_bound(self) -> None:
        catalog = _catalog()
        same_value_foreign = _catalog(_digest("f")).id_for("gen9.battle.damage")
        local = catalog.id_for("gen9.battle.damage")

        assert local != same_value_foreign
        assert len({local, same_value_foreign}) == 2
        with pytest.raises(ValueError):
            catalog.require(same_value_foreign)

    def test_catalog_document_round_trip_and_undefined_id_issuance_fail_closed(self) -> None:
        catalog = _catalog()
        document = catalog.document()

        assert document["schema_version"] == 1
        assert document["generation"] == 9
        assert document["format"] == "gen9ou"
        assert document["definitions"] == [
            {"value": "gen9.battle.damage", "description": "Damage resolution."},
            {"value": "gen9.battle.turn", "description": "Turn progression."},
        ]
        assert CapabilityCatalog.from_document(document) == catalog
        assert catalog.catalog_digest == manifest_digest(catalog.document())
        with pytest.raises(ValueError):
            CapabilityId._issue(catalog, "gen9.battle.undefined")
        invalid_schema_version = dict(document)
        invalid_schema_version["schema_version"] = True
        with pytest.raises(ValueError):
            CapabilityCatalog.from_document(invalid_schema_version)

    @pytest.mark.parametrize(
        "field",
        [
            "transition_adapter_id",
            "transition_adapter_version",
            "transition_adapter_source_digest",
            "transition_model_contract_digest",
            "transition_adapter_conformance_digest",
            "qualification_result_schema_id",
            "qualification_result_digest",
            "environment_cell_id",
            "oracle_source_manifest_digest",
            "engine_source_manifest_digest",
            "engine_build_manifest_digest",
            "artifact_index_digest",
            "wheel_digest",
            "oracle_build_manifest_digest",
            "ruleset_digest",
            "corpus_digest",
            "runner_source_digest",
            "classifier_source_digest",
        ],
    )
    def test_qualifying_evidence_mismatch_fails_closed(self, field: str) -> None:
        catalog = _catalog()
        evidence = _evidence()
        changed = "other" if field.endswith(("id", "version")) else _digest("f")
        if field == "qualification_result_schema_id":
            changed = "urn:battlebelief:schema:other-result:v1"
        mismatched = dataclasses.replace(evidence, **{field: changed})
        claim = CapabilityClaim(
            catalog.id_for("gen9.battle.damage"),
            CapabilityStatus.EXACT,
            evidence_refs=(mismatched,),
        )

        if field.startswith("qualification_result"):
            with pytest.raises(ValueError):
                _manifest(
                    claim,
                    evidence_set_digest=EngineCapabilityManifest.evidence_set_digest_for(
                        (_evidence(),)
                    ),
                )
        else:
            with pytest.raises(ValueError):
                _manifest(claim)

    def test_qualification_results_are_retained_in_evidence_set_identity(self) -> None:
        evidence = _evidence()
        changed = dataclasses.replace(evidence, qualification_result_digest=_digest("f"))

        assert evidence != changed
        assert EngineCapabilityManifest.evidence_set_digest_for((evidence,)) != (
            EngineCapabilityManifest.evidence_set_digest_for((changed,))
        )

    def test_evidence_set_identity_is_permutation_invariant_and_rejects_duplicates(self) -> None:
        first = _evidence()
        second = dataclasses.replace(first, environment_cell_id="cp313-win-amd64")

        assert EngineCapabilityManifest.evidence_set_digest_for((first, second)) == (
            EngineCapabilityManifest.evidence_set_digest_for((second, first))
        )
        with pytest.raises(ValueError):
            EngineCapabilityManifest.evidence_set_digest_for((first, first))

    def test_unknown_and_unsupported_are_explicit_and_duplicate_claims_fail_closed(self) -> None:
        catalog = _catalog()
        unknown = CapabilityClaim(catalog.id_for("gen9.battle.damage"), CapabilityStatus.UNKNOWN)
        unsupported = CapabilityClaim(
            catalog.id_for("gen9.battle.turn"), CapabilityStatus.UNSUPPORTED
        )

        manifest = EngineCapabilityManifest.create_unqualified(
            manifest_id="initial-unqualified",
            catalog=catalog,
            generation=9,
            format="gen9ou",
            engine_source_manifest_digest=_digest("1"),
            artifact_index_digest=_digest("3"),
            environment_bindings=(),
            canonicalization_contract_digest=_digest("e"),
        )
        assert unknown.status is CapabilityStatus.UNKNOWN
        assert unsupported.status is CapabilityStatus.UNSUPPORTED
        with pytest.raises(ValueError):
            dataclasses.replace(manifest, claims=(unknown, unknown))

    @pytest.mark.parametrize(
        "field",
        [
            "engine_source_manifest_digest",
            "artifact_index_digest",
            "transition_adapter_id",
            "transition_adapter_version",
            "transition_adapter_source_digest",
            "transition_model_contract_digest",
            "transition_adapter_conformance_digest",
        ],
    )
    def test_backend_identity_binds_every_backend_component(self, field: str) -> None:
        claim = CapabilityClaim(
            _catalog().id_for("gen9.battle.damage"),
            CapabilityStatus.EXACT,
            evidence_refs=(_evidence(),),
        )
        manifest = dataclasses.replace(_manifest(claim), claims=(), evidence_set_digest=None)
        replacement = "other-adapter" if field.endswith(("id", "version")) else _digest("f")
        changed = dataclasses.replace(manifest, **{field: replacement})

        assert changed.backend_identity_digest(
            "cp312-win-amd64"
        ) != manifest.backend_identity_digest("cp312-win-amd64")
