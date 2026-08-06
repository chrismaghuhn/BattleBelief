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
        "os",
        "pathlib",
        "shutil",
        "tempfile",
        "glob",
        "time",
        "socket",
        "urllib",
        "http",
        "requests",
        "httpx",
        "aiohttp",
        "random",
        "secrets",
    }
)
RUNTIME_FORBIDDEN = frozenset({"battlebelief_lab", "torch", "duckdb", "pyarrow", "subprocess"})
CORE_FORBIDDEN_BUILTIN_CALLS = frozenset({"open"})
CORE_FORBIDDEN_PRIVATE_ATTRIBUTES = frozenset({"_opaque"})
PROCESS_SPAWN_CALLS = frozenset(
    {
        ("asyncio", "create_subprocess_exec"),
        ("asyncio", "create_subprocess_shell"),
        ("os", "popen"),
        ("os", "posix_spawn"),
        ("os", "posix_spawnp"),
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
CORE_FORBIDDEN_IO_AND_CLOCK_CALLS = frozenset(
    {
        ("io", "open"),
        ("datetime", "datetime.now"),
        ("datetime", "datetime.utcnow"),
        ("datetime", "date.today"),
    }
)
CORE_FORBIDDEN_PROJECTION_CALLS = frozenset({("dataclasses", "asdict"), ("dataclasses", "astuple")})
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
    forbidden_builtin_calls: frozenset[str] = frozenset()
    native_import_prefix: str | None = None
    forbidden_private_attributes: frozenset[str] = frozenset()
    private_attribute_scope_allowlist: tuple[tuple[str, str, str], ...] = ()

    @classmethod
    def core(cls) -> ImportRule:
        return cls(
            CORE_FORBIDDEN,
            forbidden_calls=(
                PROCESS_SPAWN_CALLS
                | CORE_FORBIDDEN_IO_AND_CLOCK_CALLS
                | CORE_FORBIDDEN_PROJECTION_CALLS
            ),
            forbidden_builtin_calls=CORE_FORBIDDEN_BUILTIN_CALLS,
            forbidden_private_attributes=CORE_FORBIDDEN_PRIVATE_ATTRIBUTES,
            private_attribute_scope_allowlist=(
                ("battlebelief_core/domain/search.py", "PreparedWorld", "__post_init__"),
            ),
        )

    @classmethod
    def runtime(cls) -> ImportRule:
        return cls(
            RUNTIME_FORBIDDEN,
            forbidden_calls=PROCESS_SPAWN_CALLS,
            native_import_prefix="battlebelief_runtime/adapters/poke_engine/",
        )

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


def dynamically_imported_modules(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_aliases: set[str] = set()
    function_aliases: set[str] = {"__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib":
                    module_aliases.add(alias.asname or "importlib")
                elif alias.name.startswith("importlib.") and alias.asname is None:
                    module_aliases.add("importlib")
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            for alias in node.names:
                if alias.name == "import_module":
                    function_aliases.add(alias.asname or alias.name)
    modules: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        argument = node.args[0]
        if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
            continue
        is_dynamic_import = (
            isinstance(node.func, ast.Name) and node.func.id in function_aliases
        ) or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in module_aliases
        )
        if is_dynamic_import:
            modules.append((node.lineno, argument.value))
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

    def resolve_call_target(node: ast.expr) -> tuple[str, str] | None:
        if isinstance(node, ast.Name):
            if node.id in module_aliases:
                return (module_aliases[node.id], "")
            return direct_aliases.get(node.id)
        if not isinstance(node, ast.Attribute):
            return None
        resolved = resolve_call_target(node.value)
        if resolved is None:
            return None
        module, prefix = resolved
        return (module, f"{prefix}.{node.attr}" if prefix else node.attr)

    calls: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = resolve_call_target(node.func)
        if target in rule.forbidden_calls:
            calls.append((node.lineno, f"{target[0]}.{target[1]}"))
    return calls


def forbidden_builtin_calls(path: Path, rule: ImportRule) -> list[tuple[int, str]]:
    if not rule.forbidden_builtin_calls:
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    builtins_modules: set[str] = {"builtins"}
    direct_aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "builtins":
                    builtins_modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "builtins":
            for alias in node.names:
                direct_aliases[alias.asname or alias.name] = alias.name

    calls: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target: str | None = None
        if isinstance(node.func, ast.Name):
            target = direct_aliases.get(node.func.id, node.func.id)
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in builtins_modules
        ):
            target = node.func.attr
        if target in rule.forbidden_builtin_calls:
            calls.append((node.lineno, target))
    return calls


def forbidden_private_attribute_accesses(
    path: Path, root: Path, rule: ImportRule
) -> list[tuple[int, str]]:
    if not rule.forbidden_private_attributes:
        return []
    relative_path = path.relative_to(root).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    accesses: list[tuple[int, str]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.class_name = ""
            self.function_name = ""

        def _allowed(self) -> bool:
            return (
                relative_path,
                self.class_name,
                self.function_name,
            ) in rule.private_attribute_scope_allowlist

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            previous = self.class_name
            self.class_name = node.name
            self.generic_visit(node)
            self.class_name = previous

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            previous = self.function_name
            self.function_name = node.name
            self.generic_visit(node)
            self.function_name = previous

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Attribute(self, node: ast.Attribute) -> None:
            if node.attr in rule.forbidden_private_attributes and not self._allowed():
                accesses.append((node.lineno, node.attr))
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            direct_getattr = (
                isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value in rule.forbidden_private_attributes
            )
            reflective_getattribute = (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "__getattribute__"
                and any(
                    isinstance(argument, ast.Constant)
                    and argument.value in rule.forbidden_private_attributes
                    for argument in node.args
                )
            )
            if (direct_getattr or reflective_getattribute) and not self._allowed():
                attribute = next(
                    str(argument.value)
                    for argument in node.args
                    if isinstance(argument, ast.Constant)
                    and argument.value in rule.forbidden_private_attributes
                )
                accesses.append((node.lineno, attribute))
            self.generic_visit(node)

    Visitor().visit(tree)
    return accesses


def has_root(module: str, root: str) -> bool:
    return module == root or module.startswith(root + ".")


def scan_tree(root: Path, rule: ImportRule) -> list[str]:
    errors: list[str] = []
    for path in sorted(root.rglob("*.py")):
        relative_path = path.relative_to(root).as_posix()
        modules = [*imported_modules(path), *dynamically_imported_modules(path)]
        for line, module in modules:
            if any(has_root(module, forbidden) for forbidden in rule.forbidden_roots):
                errors.append(f"{path.relative_to(root)}:{line}: forbidden import {module}")
            if has_root(module, "poke_engine") and (
                rule.native_import_prefix is None
                or not relative_path.startswith(rule.native_import_prefix)
            ):
                errors.append(f"{path.relative_to(root)}:{line}: forbidden native import {module}")
            if (
                has_root(module, "battlebelief_runtime")
                and rule.runtime_allowlist
                and not any(has_root(module, allowed) for allowed in rule.runtime_allowlist)
            ):
                errors.append(f"{path.relative_to(root)}:{line}: forbidden import {module}")
        for line, call in forbidden_process_calls(path, rule):
            errors.append(f"{path.relative_to(root)}:{line}: forbidden call {call}")
        for line, call in forbidden_builtin_calls(path, rule):
            errors.append(f"{path.relative_to(root)}:{line}: forbidden builtin call {call}")
        for line, attribute in forbidden_private_attribute_accesses(path, root, rule):
            errors.append(
                f"{path.relative_to(root)}:{line}: forbidden private attribute {attribute}"
            )
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
