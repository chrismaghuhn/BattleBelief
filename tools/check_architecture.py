from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

CORE_FORBIDDEN = frozenset(
    {
        "battlebelief_runtime",
        "battlebelief_lab",
        "torch",
        "onnxruntime",
        "duckdb",
        "pyarrow",
        "sqlite3",
        "websockets",
        "poke_engine",
        "subprocess",
    }
)
RUNTIME_FORBIDDEN = frozenset({"battlebelief_lab", "torch", "duckdb", "pyarrow", "subprocess"})
PROCESS_SPAWN_CALLS = frozenset(
    {
        ("asyncio", "create_subprocess_exec"),
        ("asyncio", "create_subprocess_shell"),
        ("os", "popen"),
        ("os", "spawnl"),
        ("os", "spawnle"),
        ("os", "spawnlp"),
        ("os", "spawnlpe"),
        ("os", "spawnv"),
        ("os", "spawnve"),
        ("os", "spawnvp"),
        ("os", "spawnvpe"),
        ("os", "startfile"),
        ("os", "system"),
    }
)
LAB_RUNTIME_ALLOWED = (
    "battlebelief_runtime.adapters",
    "battlebelief_runtime.testing",
    "battlebelief_runtime.public_api",
)


@dataclass(frozen=True, slots=True)
class ImportRule:
    forbidden_roots: frozenset[str]
    runtime_allowlist: tuple[str, ...] = ()
    forbidden_calls: frozenset[tuple[str, str]] = frozenset()

    @classmethod
    def core(cls) -> ImportRule:
        return cls(CORE_FORBIDDEN, forbidden_calls=PROCESS_SPAWN_CALLS)

    @classmethod
    def runtime(cls) -> ImportRule:
        return cls(RUNTIME_FORBIDDEN, forbidden_calls=PROCESS_SPAWN_CALLS)

    @classmethod
    def lab(cls) -> ImportRule:
        return cls(frozenset(), LAB_RUNTIME_ALLOWED)


def imported_modules(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append((node.lineno, node.module))
    return modules


def forbidden_process_calls(path: Path, rule: ImportRule) -> list[tuple[int, str]]:
    if not rule.forbidden_calls:
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_aliases: dict[str, str] = {}
    direct_aliases: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                direct_aliases[alias.asname or alias.name] = (node.module, alias.name)
    calls: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target: tuple[str, str] | None = None
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            module = module_aliases.get(node.func.value.id)
            if module is not None:
                target = (module, node.func.attr)
        elif isinstance(node.func, ast.Name):
            target = direct_aliases.get(node.func.id)
        if target in rule.forbidden_calls:
            calls.append((node.lineno, f"{target[0]}.{target[1]}"))
    return calls


def has_root(module: str, root: str) -> bool:
    return module == root or module.startswith(root + ".")


def scan_tree(root: Path, rule: ImportRule) -> list[str]:
    errors: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for line, module in imported_modules(path):
            if any(has_root(module, forbidden) for forbidden in rule.forbidden_roots):
                errors.append(f"{path.relative_to(root)}:{line}: forbidden import {module}")
            if (
                has_root(module, "battlebelief_runtime")
                and rule.runtime_allowlist
                and not any(has_root(module, allowed) for allowed in rule.runtime_allowlist)
            ):
                errors.append(f"{path.relative_to(root)}:{line}: forbidden import {module}")
        for line, call in forbidden_process_calls(path, rule):
            errors.append(f"{path.relative_to(root)}:{line}: forbidden process call {call}")
    return sorted(set(errors))


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    checks = (
        (repository / "packages/battlebelief-core/src", ImportRule.core()),
        (repository / "packages/battlebelief-runtime/src", ImportRule.runtime()),
        (repository / "packages/battlebelief-lab/src", ImportRule.lab()),
    )
    errors = [error for root, rule in checks for error in scan_tree(root, rule)]

    old_names = ("pokemonbot_core", "pokemonbot_runtime", "pokemonbot_lab", "urn:pokemonbot")
    for pattern in ("packages/**/*.py", "packages/**/pyproject.toml"):
        for path in repository.glob(pattern):
            text = path.read_text(encoding="utf-8")
            for old_name in old_names:
                if old_name in text:
                    errors.append(f"{path.relative_to(repository)}: old name {old_name}")

    if errors:
        print(*sorted(errors), sep="\n", file=sys.stderr)
        return 1
    print("PASS: package import and dependency boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
