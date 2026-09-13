from __future__ import annotations

import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from easyprent_accounting.packaging import (
    assert_wheel_is_clean,
    build_clean_wheel,
    clean_build_artifacts,
    uninstall_legacy_distribution,
)


class PackagingTests(unittest.TestCase):
    def test_assert_wheel_is_clean_rejects_src_entries(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("src/easyprent_accounting/old.py", "print(1)")
            archive.writestr("easyprent_accounting/__init__.py", "")

        with tempfile.TemporaryDirectory() as temp_dir:
            wheel_path = Path(temp_dir) / "test.whl"
            wheel_path.write_bytes(buffer.getvalue())

            with self.assertRaises(ValueError) as ctx:
                assert_wheel_is_clean(wheel_path)
            self.assertIn("forbidden paths", str(ctx.exception))

    def test_build_clean_wheel_purges_dirty_build_artifacts_and_excludes_src(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        dirty_build = repo_root / "build" / "lib" / "src" / "easyprent_accounting"
        dirty_build.mkdir(parents=True, exist_ok=True)
        (dirty_build / "dirty_leak.py").write_text("# dirty", encoding="utf-8")

        dirty_egg = repo_root / "easy_rem.egg-info"
        dirty_egg.mkdir(exist_ok=True)
        (dirty_egg / "PKG-INFO").write_text("Name: easy-rem", encoding="utf-8")

        self.addCleanup(lambda: clean_build_artifacts(repo_root))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            wheel_path = build_clean_wheel(repo_root, output_dir, python_executable=sys.executable)

            self.assertTrue(wheel_path.exists())
            with zipfile.ZipFile(wheel_path) as archive:
                names = archive.namelist()
                forbidden_entries = [name for name in names if name.startswith("src/")]
                self.assertEqual(
                    forbidden_entries,
                    [],
                    f"Wheel contains forbidden entries: {forbidden_entries}",
                )
                self.assertIn("easyprent_accounting/__init__.py", names)
                self.assertIn("easyprent_accounting/cli.py", names)
                self.assertIn("easyprent_accounting/templates/utility_settlement.ods", names)

            self.assertFalse((repo_root / "build").exists())
            self.assertFalse((repo_root / "easy_rem.egg-info").exists())

    def test_uninstall_legacy_distribution_runs_pip_uninstall(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "show", "easy-rem"],
            capture_output=True,
            text=True,
        )
        # Verify easy-rem is not installed in the active environment
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn("Name: easy-rem", completed.stdout)

        uninstall_legacy_distribution(python_executable=sys.executable)

    def test_package_fallback_renders_ods_in_foreign_cwd(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as wheel_dir, \
             tempfile.TemporaryDirectory() as site_dir, \
             tempfile.TemporaryDirectory() as foreign_dir:
            wheel_path = build_clean_wheel(repo_root, Path(wheel_dir), sys.executable)
            with zipfile.ZipFile(wheel_path) as z:
                z.extractall(site_dir)

            script = """
from easyprent_accounting.ods_template import render_settlement_template
doc = render_settlement_template(
    template_path=None,
    tenant_name="Test Mieter",
    tenant_street="Musterweg 5",
    tenant_city_line="10115 Berlin",
    object_lines=["Wohnung 3"],
    created_on="01.01.2025",
    period_label="2025",
    line_items=[],
    allocated_costs="0.00",
    advances_paid="0.00",
    balance="0.00",
)
import zipfile, io
with zipfile.ZipFile(io.BytesIO(doc)) as z:
    assert "content.xml" in z.namelist()
print(len(doc))
"""
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=foreign_dir,
                env={"PYTHONPATH": site_dir},
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                completed.returncode,
                0,
                f"ODS fallback rendering failed in foreign CWD:\n{completed.stderr}",
            )
            self.assertGreater(int(completed.stdout.strip()), 0)


if __name__ == "__main__":
    unittest.main()
