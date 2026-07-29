from __future__ import annotations

import sys
import tomllib
from pathlib import Path


PACKAGES = {
    "battlebelief-core": Path("packages/battlebelief-core/pyproject.toml"),
    "battlebelief-runtime": Path("packages/battlebelief-runtime/pyproject.toml"),
    "battlebelief-lab": Path("packages/battlebelief-lab/pyproject.toml"),
}


def collect_version_errors(root: Path) -> list[str]:
    metadata: dict[str, dict[str, object]] = {}
    for expected_name, relative_path in PACKAGES.items():
        project = tomllib.loads((root / relative_path).read_text(encoding="utf-8"))["project"]
        if project["name"] != expected_name:
            return [f"{relative_path}: expected name {expected_name!r}"]
        metadata[expected_name] = project

    versions = {str(project["version"]) for project in metadata.values()}
    if len(versions) != 1:
        return [f"package versions are not lockstep: {sorted(versions)}"]
    version = versions.pop()

    errors: list[str] = []
    requirements = {
        "battlebelief-runtime": {f"battlebelief-core=={version}"},
        "battlebelief-lab": {
            f"battlebelief-core=={version}",
            f"battlebelief-runtime=={version}",
        },
    }
    for package, required in requirements.items():
        actual = set(metadata[package].get("dependencies", []))
        missing = required - actual
        if missing:
            errors.append(f"{package}: missing exact dependencies {sorted(missing)}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = collect_version_errors(root)
    if errors:
        print(*errors, sep="\n", file=sys.stderr)
        return 1
    print("PASS: package versions and internal requirements are lockstep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
