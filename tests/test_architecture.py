"""Keep delivery code thin and feature boundaries explicit after the cutover."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "easyprent_accounting"
FRONTEND = ROOT / "src"
DOMAIN_MODULES = {
    "asset_registry",
    "dashboard",
    "depreciation",
    "expense_pricer",
    "expenses",
    "linked_documents",
    "metering",
    "settings",
    "settlement_documents",
    "settlement_runs",
    "settlements",
    "tenancy",
}
DELIVERY_MODULES = {
    "asgi", "cli", "deployment", "openapi", "packaging", "server", "web"
}
RETIRED_FILES = (
    PACKAGE / "web.py",
    PACKAGE / "openapi.py",
    PACKAGE / "services.py",
    PACKAGE / "static" / "index.html",
)
IMPORT_SPECIFIER = re.compile(
    r"(?:\b(?:import|export)\s+(?:[^;]*?\s+from\s+)?|\bimport\s*\()"
    r"['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)


def local_imports(path: Path) -> set[str]:
    """Return first-party modules referenced by a Python module."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if node.level == 1 and node.module:
                names.add(node.module.split(".", 1)[0])
            elif node.module and node.module.startswith("easyprent_accounting."):
                names.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("easyprent_accounting."):
                    names.add(alias.name.split(".")[1])
    return names


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_retired_global_entry_points_and_browser_modules_are_absent(self) -> None:
        for path in RETIRED_FILES:
            with self.subTest(path=path):
                self.assertFalse(path.exists(), f"Retired aggregate remains: {path}")

        static_dir = PACKAGE / "static"
        self.assertEqual(list(static_dir.glob("app*.js")), [])
        self.assertFalse((static_dir / "vendor").exists())

    def test_domain_modules_do_not_import_delivery_layers(self) -> None:
        for module in sorted(DOMAIN_MODULES):
            with self.subTest(module=module):
                imported = local_imports(PACKAGE / f"{module}.py")
                self.assertFalse(
                    imported & DELIVERY_MODULES or any(name.startswith("http_") for name in imported),
                    f"{module} imports delivery code: {imported}",
                )

    def test_routers_do_not_reach_into_other_routers_or_manage_sql(self) -> None:
        for path in sorted(PACKAGE.glob("http_*.py")):
            if path.stem in {"http_db", "http_models"}:
                continue
            with self.subTest(router=path.name):
                imported = local_imports(path)
                self.assertFalse(
                    {name for name in imported if name.startswith("http_")}
                    - {"http_db", "http_models"},
                    f"{path.name} imports another HTTP router",
                )
                tree = ast.parse(path.read_text(encoding="utf-8"))
                forbidden_calls = {
                    node.func.attr
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"execute", "executemany", "executescript", "commit", "rollback"}
                }
                self.assertEqual(forbidden_calls, set(), f"{path.name} contains SQL or transaction logic")

    def test_frontend_features_import_siblings_through_public_entries(self) -> None:
        features = FRONTEND / "features"
        for path in sorted(features.glob("*/*")):
            if path.suffix not in {".ts", ".tsx"}:
                continue
            own_feature = path.parent.name
            for specifier in IMPORT_SPECIFIER.findall(path.read_text(encoding="utf-8")):
                if not specifier.startswith("../"):
                    continue
                parts = specifier.split("/")
                if len(parts) < 2 or parts[1] not in {p.name for p in features.iterdir() if p.is_dir()}:
                    continue
                if parts[1] != own_feature:
                    with self.subTest(path=path.name, imported=specifier):
                        self.assertEqual(
                            len(parts), 2,
                            f"{path.relative_to(ROOT)} bypasses {parts[1]}/index.ts",
                        )

    def test_app_shell_depends_only_on_navigation_and_message_components(self) -> None:
        shell = FRONTEND / "app" / "AppShell.tsx"
        specifiers = IMPORT_SPECIFIER.findall(shell.read_text(encoding="utf-8"))
        self.assertFalse(
            [name for name in specifiers if name.startswith("../features/") or name.startswith("../api/") or name.startswith("../models/")],
            "AppShell should only compose navigation, messages, and content supplied by App",
        )

    def test_installed_directories_are_not_versioned(self) -> None:
        tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
        forbidden = ("node_modules/", ".venv/", "venv/", "build/", "dist/", ".easyprent/")
        self.assertEqual(
            [name for name in tracked if name.startswith(forbidden) or ".egg-info/" in name],
            [],
        )


if __name__ == "__main__":
    unittest.main()
