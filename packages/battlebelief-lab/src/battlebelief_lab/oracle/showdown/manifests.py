"""Strict, canonical provenance manifests for a local Showdown oracle."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Any, ClassVar

from battlebelief_core.canonicalization import canonicalize, manifest_digest

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MANIFEST_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
_SAFE_PATH_RE = re.compile(
    r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9._@+~=-]+(?:/[A-Za-z0-9._@+~=-]+)*$"
)
_SOURCE_SCHEMA_ID = "urn:battlebelief:schema:manifest:showdown-oracle-source:v1"
_BUILD_SCHEMA_ID = "urn:battlebelief:schema:manifest:showdown-oracle-build:v1"
_CANONICALIZATION_PROFILE = "rfc8785-jcs-v1"
_ADAPTER_VERSION = "showdown-oracle-v1"
_REPOSITORY_URL = "https://github.com/smogon/pokemon-showdown"
_SHOWDOWN_COMMIT = "6a1836dd71c0718e923206f3d089e61074410868"
_SOURCE_TREE_OID = "b0404c1084b81b68d48102b6ba17b455199668db"
_SOURCE_FILE_COUNT = 984
_SOURCE_TREE_DIGEST = "sha256:1b4a43fbd5ce2357f04554143a61012dd3fd032d529ae94ab4fa65476f3bef75"
_LICENSE_DIGEST = "sha256:b2002a9fd52ba8db3783a05fbdebfb09c34fd09513b90f6b390a2c0dfbc93ed0"
_PACKAGE_LOCK_DIGEST = "sha256:f207748a1ef4e549160defbbb688de0f35889f3038939edebb5a956cf41b9d0a"
_PACKAGE_JSON_DIGEST = "sha256:561152e07c4a0f4a8ddb0ab60bc3f4c3225bac24b207a70545f528d5bc4727e9"
_CANDIDATE_NODE_NPM = ("22.23.2", "10.9.8")
_COMPARISON_NODE_NPM = frozenset({("18.20.8", "10.8.2"), ("20.20.2", "10.8.2")})
_NPM_CONFIG_KEYS = frozenset({"audit", "fund", "ignore-scripts", "package-lock", "update-notifier"})
_RULESET_EXTRACTOR_DIGEST = (
    "sha256:82ae637f73a81aa9bafeab27fc0bc057d1fc281660985898a9c0006159e56f58"
)


def _require_exact_keys(value: Mapping[str, Any], expected: frozenset[str]) -> None:
    if frozenset(value) != expected:
        missing = sorted(expected - frozenset(value))
        unknown = sorted(frozenset(value) - expected)
        raise ValueError(f"manifest fields differ: missing={missing}, unknown={unknown}")


def _require_string(value: object, field: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_manifest_id(value: object) -> str:
    value = _require_string(value, "manifest_id")
    if not _MANIFEST_ID_RE.fullmatch(value):
        raise ValueError("manifest_id must match the schema identifier pattern")
    return value


def _require_digest(value: object, field: str) -> str:
    value = _require_string(value, field)
    if not _DIGEST_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase sha256 digest")
    return value


def _require_safe_path(value: object, field: str) -> str:
    value = _require_string(value, field)
    if not _SAFE_PATH_RE.fullmatch(value):
        raise ValueError(f"{field} must be a safe relative POSIX path")
    return value


def _require_version(value: object, field: str) -> str:
    value = _require_string(value, field)
    if not _VERSION_RE.fullmatch(value):
        raise ValueError(f"{field} must be an exact version without a v-prefix or range")
    return value


def _normalize_records(value: object, field: str) -> tuple[tuple[str, str, int], ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    records: list[tuple[str, str, int]] = []
    for record in value:
        if not isinstance(record, Mapping):
            raise ValueError(f"{field} records must be objects")
        _require_exact_keys(record, frozenset({"path", "digest", "size"}))
        path = _require_safe_path(record["path"], f"{field}.path")
        digest = _require_digest(record["digest"], f"{field}.digest")
        size = record["size"]
        if type(size) is not int or size < 0:
            raise ValueError(f"{field}.size must be a non-negative integer")
        records.append((path, digest, size))
    if records != sorted(records, key=lambda record: record[0]):
        raise ValueError(f"{field} must be sorted by path")
    if len({record[0] for record in records}) != len(records):
        raise ValueError(f"{field} must not contain duplicate paths")
    return tuple(records)


def _records_document(records: tuple[tuple[str, str, int], ...]) -> list[dict[str, object]]:
    return [{"path": path, "digest": digest, "size": size} for path, digest, size in records]


def _record_digest(records: tuple[tuple[str, str, int], ...]) -> str:
    return manifest_digest(_records_document(records))


@dataclass(frozen=True, slots=True)
class _DependencyFileRecord:
    """One regular runtime file or POSIX-style link below ``node_modules``."""

    kind: str
    path: str
    digest: str | None = None
    size: int | None = None
    target: str | None = None

    def to_dict(self) -> dict[str, object]:
        if self.kind == "file":
            assert self.digest is not None and self.size is not None
            return {
                "kind": "file",
                "path": self.path,
                "digest": self.digest,
                "size": self.size,
            }
        assert self.target is not None
        return {"kind": "symlink", "path": self.path, "target": self.target}


def _require_dependency_path(value: object, field: str) -> str:
    path = _require_safe_path(value, field)
    if not path.startswith("node_modules/"):
        raise ValueError(f"{field} must be below node_modules")
    return path


def _require_relative_link_target(value: object, path: str) -> str:
    target = _require_string(value, "dependency_files.target")
    if "\\" in target or target.startswith("/") or re.match(r"^[A-Za-z]:", target):
        raise ValueError("dependency_files.target must be a relative POSIX path")
    parts = target.split("/")
    if any(part in {"", "."} for part in parts):
        raise ValueError("dependency_files.target must be normalized")
    resolved_parts = path.split("/")[:-1]
    for part in PurePosixPath(target).parts:
        if part == "..":
            if len(resolved_parts) <= 1:
                raise ValueError("dependency_files.target must stay within node_modules")
            resolved_parts.pop()
        else:
            resolved_parts.append(part)
    if not resolved_parts or resolved_parts[0] != "node_modules":
        raise ValueError("dependency_files.target must stay within node_modules")
    return target


def _normalize_dependency_files(value: object) -> tuple[_DependencyFileRecord, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("dependency_files must be a non-empty list")
    records: list[_DependencyFileRecord] = []
    for raw_record in value:
        if not isinstance(raw_record, Mapping):
            raise ValueError("dependency_files records must be objects")
        kind = raw_record.get("kind")
        if kind == "file":
            _require_exact_keys(raw_record, frozenset({"kind", "path", "digest", "size"}))
            path = _require_dependency_path(raw_record["path"], "dependency_files.path")
            digest = _require_digest(raw_record["digest"], "dependency_files.digest")
            size = raw_record["size"]
            if type(size) is not int or size < 0:
                raise ValueError("dependency_files.size must be a non-negative integer")
            records.append(_DependencyFileRecord("file", path, digest=digest, size=size))
        elif kind == "symlink":
            _require_exact_keys(raw_record, frozenset({"kind", "path", "target"}))
            path = _require_dependency_path(raw_record["path"], "dependency_files.path")
            target = _require_relative_link_target(raw_record["target"], path)
            records.append(_DependencyFileRecord("symlink", path, target=target))
        else:
            raise ValueError("dependency_files.kind is unsupported")
    if records != sorted(records, key=lambda record: record.path):
        raise ValueError("dependency_files must be sorted by path")
    if len({record.path for record in records}) != len(records):
        raise ValueError("dependency_files must not contain duplicate paths")
    return tuple(records)


def _dependency_files_document(
    records: tuple[_DependencyFileRecord, ...],
) -> list[dict[str, object]]:
    return [record.to_dict() for record in records]


def _require_record_binding(
    records: tuple[tuple[str, str, int], ...], path: str, digest: str, field: str
) -> None:
    if not any(
        record_path == path and record_digest == digest for record_path, record_digest, _ in records
    ):
        raise ValueError(f"{field} must bind a matching file record")


def _normalize_argv(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty argument list")
    argv = tuple(_require_string(token, f"{field} token") for token in value)
    for token in argv:
        normalized = token.replace("\\", "/")
        if (
            normalized.startswith("/")
            or re.match(r"^[A-Za-z]:/", normalized)
            or "/../" in f"/{normalized}/"
        ):
            raise ValueError(f"{field} must not contain local absolute or parent paths")
    return argv


def _normalize_npm_config(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("npm_config must be a non-empty allowlisted object")
    if not set(value).issubset(_NPM_CONFIG_KEYS):
        raise ValueError("npm_config contains a non-allowlisted key")
    normalized: list[tuple[str, str]] = []
    for key, setting in value.items():
        if type(key) is not str or type(setting) is not str or setting not in {"true", "false"}:
            raise ValueError("npm_config values must be explicit true or false strings")
        normalized.append((key, setting))
    return tuple(sorted(normalized))


def _normalize_sorted_strings(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or any(type(item) is not str or not item for item in value):
        raise ValueError(f"{field} must be a non-empty-string list")
    values = list(value)
    if values != sorted(values) or len(values) != len(set(values)):
        raise ValueError(f"{field} must be sorted and unique")
    return values


def _normalize_ruleset_entries(value: object, field: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result: list[dict[str, str]] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            raise ValueError(f"{field} entries must be objects")
        _require_exact_keys(entry, frozenset({"key", "value"}))
        result.append(
            {
                "key": _require_string(entry["key"], f"{field}.key"),
                "value": entry["value"]
                if type(entry["value"]) is str
                else _require_string(entry["value"], f"{field}.value"),
            }
        )
    if result != sorted(result, key=lambda item: (item["key"], item["value"])):
        raise ValueError(f"{field} must be sorted")
    if len({(item["key"], item["value"]) for item in result}) != len(result):
        raise ValueError(f"{field} must not contain duplicate entries")
    return result


def _normalize_complex_bans(value: object, field: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result: list[dict[str, object]] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            raise ValueError(f"{field} entries must be objects")
        _require_exact_keys(entry, frozenset({"limit", "rules", "source"}))
        limit = entry["limit"]
        if type(limit) is not int or limit < 1:
            raise ValueError(f"{field}.limit must be a positive integer")
        result.append(
            {
                "limit": limit,
                "rules": _normalize_sorted_strings(entry["rules"], f"{field}.rules"),
                "source": _require_string(entry["source"], f"{field}.source"),
            }
        )
    if result != sorted(result, key=lambda item: canonicalize(item)):
        raise ValueError(f"{field} must be sorted")
    return result


def _normalize_tag_rules(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("ruleset_snapshot tag_rules must be a list")
    result: list[dict[str, str]] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            raise ValueError("ruleset_snapshot tag_rules entries must be objects")
        _require_exact_keys(entry, frozenset({"prefix", "tag"}))
        result.append(
            {
                "prefix": _require_string(entry["prefix"], "ruleset_snapshot tag prefix"),
                "tag": _require_string(entry["tag"], "ruleset_snapshot tag"),
            }
        )
    if result != sorted(result, key=lambda item: (item["prefix"], item["tag"])):
        raise ValueError("ruleset_snapshot tag_rules must be sorted")
    if len({(item["prefix"], item["tag"]) for item in result}) != len(result):
        raise ValueError("ruleset_snapshot tag_rules must not contain duplicates")
    return result


def _normalize_ruleset_snapshot(value: object) -> dict[str, object]:
    """Validate the complete build-derived Gen 9 OU format/rule closure."""

    if not isinstance(value, Mapping):
        raise ValueError("ruleset_snapshot must be an object")
    _require_exact_keys(
        value,
        frozenset(
            {"schema_version", "extractor_id", "extractor_digest", "format", "resolved_rule_table"}
        ),
    )
    if value["schema_version"] != 1:
        raise ValueError("ruleset_snapshot schema version is unsupported")
    if value["extractor_id"] != "battlebelief-showdown-ruleset-extractor-v1":
        raise ValueError("ruleset_snapshot extractor identity is unsupported")
    extractor_digest = _require_digest(
        value["extractor_digest"], "ruleset_snapshot extractor digest"
    )
    if extractor_digest != _RULESET_EXTRACTOR_DIGEST:
        raise ValueError("ruleset_snapshot extractor digest is not the bound extractor")
    format_value = value["format"]
    if not isinstance(format_value, Mapping):
        raise ValueError("ruleset_snapshot format must be an object")
    _require_exact_keys(
        format_value,
        frozenset(
            {
                "id",
                "name",
                "mod",
                "game_type",
                "gen",
                "rated",
                "ruleset",
                "base_ruleset",
                "banlist",
                "restricted",
                "unbanlist",
            }
        ),
    )
    if (
        format_value["id"] != "gen9ou"
        or format_value["mod"] != "gen9"
        or format_value["game_type"] != "singles"
        or format_value["gen"] != 9
        or type(format_value["rated"]) is not bool
    ):
        raise ValueError("ruleset_snapshot must bind the resolved Gen 9 OU Singles format")
    normalized_format: dict[str, object] = {
        "id": "gen9ou",
        "name": _require_string(format_value["name"], "ruleset_snapshot format name"),
        "mod": "gen9",
        "game_type": "singles",
        "gen": 9,
        "rated": format_value["rated"],
        "ruleset": _normalize_sorted_strings(format_value["ruleset"], "ruleset_snapshot ruleset"),
        "base_ruleset": _normalize_sorted_strings(
            format_value["base_ruleset"], "ruleset_snapshot base_ruleset"
        ),
        "banlist": _normalize_sorted_strings(format_value["banlist"], "ruleset_snapshot banlist"),
        "restricted": _normalize_sorted_strings(
            format_value["restricted"], "ruleset_snapshot restricted"
        ),
        "unbanlist": _normalize_sorted_strings(
            format_value["unbanlist"], "ruleset_snapshot unbanlist"
        ),
    }
    table_value = value["resolved_rule_table"]
    if not isinstance(table_value, Mapping):
        raise ValueError("ruleset_snapshot resolved_rule_table must be an object")
    _require_exact_keys(
        table_value,
        frozenset(
            {
                "entries",
                "value_rules",
                "complex_bans",
                "complex_team_bans",
                "tag_rules",
                "team_constraints",
            }
        ),
    )
    constraints = table_value["team_constraints"]
    if not isinstance(constraints, Mapping):
        raise ValueError("ruleset_snapshot team_constraints must be an object")
    constraint_keys = frozenset(
        {
            "ev_limit",
            "max_level",
            "max_move_count",
            "max_team_size",
            "min_level",
            "min_source_gen",
            "min_team_size",
        }
    )
    _require_exact_keys(constraints, constraint_keys)
    normalized_constraints: dict[str, int] = {}
    for key in sorted(constraint_keys):
        numeric = constraints[key]
        if type(numeric) is not int or numeric < 0:
            raise ValueError(
                f"ruleset_snapshot team constraint {key} must be a non-negative integer"
            )
        normalized_constraints[key] = numeric
    normalized_table: dict[str, object] = {
        "entries": _normalize_ruleset_entries(table_value["entries"], "ruleset_snapshot entries"),
        "value_rules": _normalize_ruleset_entries(
            table_value["value_rules"], "ruleset_snapshot value_rules"
        ),
        "complex_bans": _normalize_complex_bans(
            table_value["complex_bans"], "ruleset_snapshot complex_bans"
        ),
        "complex_team_bans": _normalize_complex_bans(
            table_value["complex_team_bans"], "ruleset_snapshot complex_team_bans"
        ),
        "tag_rules": _normalize_tag_rules(table_value["tag_rules"]),
        "team_constraints": normalized_constraints,
    }
    return {
        "schema_version": 1,
        "extractor_id": "battlebelief-showdown-ruleset-extractor-v1",
        "extractor_digest": extractor_digest,
        "format": normalized_format,
        "resolved_rule_table": normalized_table,
    }


@dataclass(frozen=True, slots=True)
class ShowdownSourceManifest:
    """Source bytes and metadata bound to one exact Showdown commit."""

    schema_version: int
    manifest_id: str
    repository_url: str
    commit: str
    package_name: str
    package_version: str
    declared_node_version: str
    license_path: str
    license_digest: str
    package_lock_path: str
    lockfile_version: int
    package_lock_digest: str
    package_json_path: str
    package_json_digest: str
    source_scope: str
    source_files: tuple[tuple[str, str, int], ...]
    source_tree_digest: str
    git_tree_oid: str
    source_file_count: int
    adapter_version: str
    canonicalization_profile: str
    schema_id: str

    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "manifest_id",
            "repository_url",
            "commit",
            "package_name",
            "package_version",
            "declared_node_version",
            "license_path",
            "license_digest",
            "package_lock_path",
            "lockfile_version",
            "package_lock_digest",
            "package_json_path",
            "package_json_digest",
            "source_scope",
            "source_files",
            "source_tree_digest",
            "git_tree_oid",
            "source_file_count",
            "adapter_version",
            "canonicalization_profile",
            "schema_id",
        }
    )

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported source manifest schema version")
        _require_manifest_id(self.manifest_id)
        if self.repository_url != _REPOSITORY_URL:
            raise ValueError("repository_url must be the canonical upstream URL")
        if not _COMMIT_RE.fullmatch(self.commit):
            raise ValueError("commit must be 40 lowercase hexadecimal characters")
        if self.commit != _SHOWDOWN_COMMIT:
            raise ValueError("commit must bind the selected Showdown revision")
        for field in ("package_name", "package_version", "declared_node_version"):
            _require_string(getattr(self, field), field)
        if self.package_name != "pokemon-showdown":
            raise ValueError("package_name must bind pokemon-showdown")
        if self.package_version != "0.11.11" or self.declared_node_version != ">=16.0.0":
            raise ValueError("package metadata must bind the selected Showdown revision")
        _require_safe_path(self.license_path, "license_path")
        _require_digest(self.license_digest, "license_digest")
        _require_safe_path(self.package_lock_path, "package_lock_path")
        _require_digest(self.package_lock_digest, "package_lock_digest")
        if type(self.lockfile_version) is not int or self.lockfile_version < 1:
            raise ValueError("lockfile_version must be a positive integer")
        _require_safe_path(self.package_json_path, "package_json_path")
        _require_digest(self.package_json_digest, "package_json_digest")
        if (
            self.license_path != "LICENSE"
            or self.license_digest != _LICENSE_DIGEST
            or self.package_lock_path != "package-lock.json"
            or self.package_lock_digest != _PACKAGE_LOCK_DIGEST
            or self.lockfile_version != 2
            or self.package_json_path != "package.json"
            or self.package_json_digest != _PACKAGE_JSON_DIGEST
        ):
            raise ValueError("source artifact metadata must bind historical Git blob facts")
        if self.source_scope != "full_git_tree":
            raise ValueError("source_scope must bind the full tracked Git tree")
        records = _normalize_records(_records_document(self.source_files), "source_files")
        object.__setattr__(self, "source_files", records)
        if type(self.source_file_count) is not int or self.source_file_count != _SOURCE_FILE_COUNT:
            raise ValueError("source_file_count must bind the full tracked tree")
        if len(records) != self.source_file_count:
            raise ValueError("source_files must contain the complete tracked tree")
        if self.git_tree_oid != _SOURCE_TREE_OID:
            raise ValueError("git_tree_oid must bind the selected Showdown tree")
        _require_record_binding(records, self.license_path, self.license_digest, "license")
        _require_record_binding(
            records, self.package_lock_path, self.package_lock_digest, "package lock"
        )
        _require_record_binding(
            records, self.package_json_path, self.package_json_digest, "package metadata"
        )
        if self.source_tree_digest != _record_digest(records):
            raise ValueError("source_tree_digest does not match source_files")
        if self.source_tree_digest != _SOURCE_TREE_DIGEST:
            raise ValueError("source_tree_digest must bind the selected Showdown tree")
        if self.adapter_version != _ADAPTER_VERSION:
            raise ValueError("adapter_version is unsupported")
        if self.canonicalization_profile != _CANONICALIZATION_PROFILE:
            raise ValueError("canonicalization profile is unsupported")
        if self.schema_id != _SOURCE_SCHEMA_ID:
            raise ValueError("source schema identity is unsupported")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ShowdownSourceManifest:
        if not isinstance(value, Mapping):
            raise ValueError("source manifest must be an object")
        _require_exact_keys(value, cls._FIELDS)
        records = _normalize_records(value["source_files"], "source_files")
        return cls(
            schema_version=value["schema_version"],  # type: ignore[arg-type]
            manifest_id=value["manifest_id"],  # type: ignore[arg-type]
            repository_url=value["repository_url"],  # type: ignore[arg-type]
            commit=value["commit"],  # type: ignore[arg-type]
            package_name=value["package_name"],  # type: ignore[arg-type]
            package_version=value["package_version"],  # type: ignore[arg-type]
            declared_node_version=value["declared_node_version"],  # type: ignore[arg-type]
            license_path=value["license_path"],  # type: ignore[arg-type]
            license_digest=value["license_digest"],  # type: ignore[arg-type]
            package_lock_path=value["package_lock_path"],  # type: ignore[arg-type]
            lockfile_version=value["lockfile_version"],  # type: ignore[arg-type]
            package_lock_digest=value["package_lock_digest"],  # type: ignore[arg-type]
            package_json_path=value["package_json_path"],  # type: ignore[arg-type]
            package_json_digest=value["package_json_digest"],  # type: ignore[arg-type]
            source_scope=value["source_scope"],  # type: ignore[arg-type]
            source_files=records,
            source_tree_digest=value["source_tree_digest"],  # type: ignore[arg-type]
            git_tree_oid=value["git_tree_oid"],  # type: ignore[arg-type]
            source_file_count=value["source_file_count"],  # type: ignore[arg-type]
            adapter_version=value["adapter_version"],  # type: ignore[arg-type]
            canonicalization_profile=value["canonicalization_profile"],  # type: ignore[arg-type]
            schema_id=value["schema_id"],  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "repository_url": self.repository_url,
            "commit": self.commit,
            "package_name": self.package_name,
            "package_version": self.package_version,
            "declared_node_version": self.declared_node_version,
            "license_path": self.license_path,
            "license_digest": self.license_digest,
            "package_lock_path": self.package_lock_path,
            "lockfile_version": self.lockfile_version,
            "package_lock_digest": self.package_lock_digest,
            "package_json_path": self.package_json_path,
            "package_json_digest": self.package_json_digest,
            "source_scope": self.source_scope,
            "source_files": _records_document(self.source_files),
            "source_tree_digest": self.source_tree_digest,
            "git_tree_oid": self.git_tree_oid,
            "source_file_count": self.source_file_count,
            "adapter_version": self.adapter_version,
            "canonicalization_profile": self.canonicalization_profile,
            "schema_id": self.schema_id,
        }

    def canonical_bytes(self) -> bytes:
        return canonicalize(self.to_dict())

    @property
    def digest(self) -> str:
        return manifest_digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class ShowdownBuildManifest:
    """Hermetic build inputs and output bytes for one local oracle profile."""

    schema_version: int
    manifest_id: str
    source_manifest_digest: str
    commit: str
    node_version: str
    npm_version: str
    probe_role: str
    os: str
    architecture: str
    npm_ci_argv: tuple[str, ...]
    npm_build_argv: tuple[str, ...]
    simulator_argv: tuple[str, ...]
    npm_config: tuple[tuple[str, str], ...]
    dependency_tree_digest: str
    dependency_files: tuple[_DependencyFileRecord, ...]
    dependency_files_digest: str
    dist_files: tuple[tuple[str, str, int], ...]
    dist_tree_digest: str
    format_id: str
    ruleset_snapshot: Mapping[str, object]
    ruleset_snapshot_digest: str
    format_identity_digest: str
    adapter_version: str
    canonicalization_profile: str
    schema_id: str

    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "manifest_id",
            "source_manifest_digest",
            "commit",
            "node_version",
            "npm_version",
            "probe_role",
            "os",
            "architecture",
            "npm_ci_argv",
            "npm_build_argv",
            "simulator_argv",
            "npm_config",
            "dependency_tree_digest",
            "dependency_files",
            "dependency_files_digest",
            "dist_files",
            "dist_tree_digest",
            "format_id",
            "ruleset_snapshot",
            "ruleset_snapshot_digest",
            "format_identity_digest",
            "adapter_version",
            "canonicalization_profile",
            "schema_id",
        }
    )

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported build manifest schema version")
        _require_manifest_id(self.manifest_id)
        _require_digest(self.source_manifest_digest, "source_manifest_digest")
        if not _COMMIT_RE.fullmatch(self.commit):
            raise ValueError("commit must be 40 lowercase hexadecimal characters")
        _require_version(self.node_version, "node_version")
        _require_version(self.npm_version, "npm_version")
        if self.probe_role not in {"candidate", "comparison"}:
            raise ValueError("probe_role is unsupported")
        if self.commit != _SHOWDOWN_COMMIT:
            raise ValueError("commit must bind the selected Showdown revision")
        if (
            self.probe_role == "candidate"
            and (self.node_version, self.npm_version) != _CANDIDATE_NODE_NPM
        ):
            raise ValueError("candidate must bind the approved Node and npm versions")
        if (
            self.probe_role == "comparison"
            and (
                self.node_version,
                self.npm_version,
            )
            not in _COMPARISON_NODE_NPM
        ):
            raise ValueError("comparison must bind an approved Node and npm version pair")
        if self.os not in {"linux", "windows"}:
            raise ValueError("os is unsupported")
        if self.architecture not in {"x86_64", "arm64"}:
            raise ValueError("architecture is unsupported")
        ci = _normalize_argv(list(self.npm_ci_argv), "npm_ci_argv")
        build = _normalize_argv(list(self.npm_build_argv), "npm_build_argv")
        simulator = _normalize_argv(list(self.simulator_argv), "simulator_argv")
        object.__setattr__(self, "npm_ci_argv", ci)
        object.__setattr__(self, "npm_build_argv", build)
        object.__setattr__(self, "simulator_argv", simulator)
        if ci != ("npm", "ci", "--no-audit", "--no-fund"):
            raise ValueError("npm_ci_argv must bind npm ci --no-audit --no-fund")
        if build != ("npm", "run", "build"):
            raise ValueError("npm_build_argv must bind the approved build command")
        if simulator != ("node", "pokemon-showdown", "--skip-build", "simulate-battle"):
            raise ValueError("simulator_argv must bind the approved simulator command")
        config = _normalize_npm_config(dict(self.npm_config))
        object.__setattr__(self, "npm_config", config)
        _require_digest(self.dependency_tree_digest, "dependency_tree_digest")
        dependency_files = _normalize_dependency_files(
            _dependency_files_document(self.dependency_files)
        )
        object.__setattr__(self, "dependency_files", dependency_files)
        _require_digest(self.dependency_files_digest, "dependency_files_digest")
        if self.dependency_files_digest != manifest_digest(
            _dependency_files_document(dependency_files)
        ):
            raise ValueError("dependency_files_digest does not match dependency_files")
        records = _normalize_records(_records_document(self.dist_files), "dist_files")
        object.__setattr__(self, "dist_files", records)
        if self.dist_tree_digest != _record_digest(records):
            raise ValueError("dist_tree_digest does not match dist_files")
        if self.format_id != "gen9ou":
            raise ValueError("format_id must bind gen9ou")
        snapshot = _normalize_ruleset_snapshot(self.ruleset_snapshot)
        object.__setattr__(self, "ruleset_snapshot", MappingProxyType(snapshot))
        _require_digest(self.ruleset_snapshot_digest, "ruleset_snapshot_digest")
        _require_digest(self.format_identity_digest, "format_identity_digest")
        if self.ruleset_snapshot_digest != manifest_digest(snapshot):
            raise ValueError("ruleset_snapshot_digest does not match ruleset_snapshot")
        if self.format_identity_digest != manifest_digest(snapshot["format"]):
            raise ValueError("format_identity_digest does not match ruleset_snapshot format")
        if self.adapter_version != _ADAPTER_VERSION:
            raise ValueError("adapter_version is unsupported")
        if self.canonicalization_profile != _CANONICALIZATION_PROFILE:
            raise ValueError("canonicalization profile is unsupported")
        if self.schema_id != _BUILD_SCHEMA_ID:
            raise ValueError("build schema identity is unsupported")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ShowdownBuildManifest:
        if not isinstance(value, Mapping):
            raise ValueError("build manifest must be an object")
        _require_exact_keys(value, cls._FIELDS)
        return cls(
            schema_version=value["schema_version"],  # type: ignore[arg-type]
            manifest_id=value["manifest_id"],  # type: ignore[arg-type]
            source_manifest_digest=value["source_manifest_digest"],  # type: ignore[arg-type]
            commit=value["commit"],  # type: ignore[arg-type]
            node_version=value["node_version"],  # type: ignore[arg-type]
            npm_version=value["npm_version"],  # type: ignore[arg-type]
            probe_role=value["probe_role"],  # type: ignore[arg-type]
            os=value["os"],  # type: ignore[arg-type]
            architecture=value["architecture"],  # type: ignore[arg-type]
            npm_ci_argv=_normalize_argv(value["npm_ci_argv"], "npm_ci_argv"),
            npm_build_argv=_normalize_argv(value["npm_build_argv"], "npm_build_argv"),
            simulator_argv=_normalize_argv(value["simulator_argv"], "simulator_argv"),
            npm_config=_normalize_npm_config(value["npm_config"]),
            dependency_tree_digest=value["dependency_tree_digest"],  # type: ignore[arg-type]
            dependency_files=_normalize_dependency_files(value["dependency_files"]),
            dependency_files_digest=value["dependency_files_digest"],  # type: ignore[arg-type]
            dist_files=_normalize_records(value["dist_files"], "dist_files"),
            dist_tree_digest=value["dist_tree_digest"],  # type: ignore[arg-type]
            format_id=value["format_id"],  # type: ignore[arg-type]
            ruleset_snapshot=_normalize_ruleset_snapshot(value["ruleset_snapshot"]),
            ruleset_snapshot_digest=value["ruleset_snapshot_digest"],  # type: ignore[arg-type]
            format_identity_digest=value["format_identity_digest"],  # type: ignore[arg-type]
            adapter_version=value["adapter_version"],  # type: ignore[arg-type]
            canonicalization_profile=value["canonicalization_profile"],  # type: ignore[arg-type]
            schema_id=value["schema_id"],  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "source_manifest_digest": self.source_manifest_digest,
            "commit": self.commit,
            "node_version": self.node_version,
            "npm_version": self.npm_version,
            "probe_role": self.probe_role,
            "os": self.os,
            "architecture": self.architecture,
            "npm_ci_argv": list(self.npm_ci_argv),
            "npm_build_argv": list(self.npm_build_argv),
            "simulator_argv": list(self.simulator_argv),
            "npm_config": dict(self.npm_config),
            "dependency_tree_digest": self.dependency_tree_digest,
            "dependency_files": _dependency_files_document(self.dependency_files),
            "dependency_files_digest": self.dependency_files_digest,
            "dist_files": _records_document(self.dist_files),
            "dist_tree_digest": self.dist_tree_digest,
            "format_id": self.format_id,
            "ruleset_snapshot": _normalize_ruleset_snapshot(self.ruleset_snapshot),
            "ruleset_snapshot_digest": self.ruleset_snapshot_digest,
            "format_identity_digest": self.format_identity_digest,
            "adapter_version": self.adapter_version,
            "canonicalization_profile": self.canonicalization_profile,
            "schema_id": self.schema_id,
        }

    def canonical_bytes(self) -> bytes:
        return canonicalize(self.to_dict())

    @property
    def digest(self) -> str:
        return manifest_digest(self.to_dict())


__all__ = ["ShowdownBuildManifest", "ShowdownSourceManifest"]
