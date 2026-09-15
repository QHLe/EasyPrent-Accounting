from __future__ import annotations

import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

from easyprent_accounting.packaging import (
    assert_wheel_is_clean,
    build_clean_wheel,
    install_checkout,
    main,
    uninstall_legacy_distribution,
    validate_install_target_writable,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def _copy_project_source(self) -> Path:
        temp_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        project_root = temp_dir / "project"
        project_root.mkdir()
        for filename in ("pyproject.toml", "README.md"):
            shutil.copy2(REPOSITORY_ROOT / filename, project_root / filename)
        shutil.copytree(
            REPOSITORY_ROOT / "easyprent_accounting",
            project_root / "easyprent_accounting",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        return project_root

    def _minimal_project(self, name: str, *, stale: bool) -> Path:
        root = Path(self.enterContext(tempfile.TemporaryDirectory())) / name
        package = root / "easyprent_accounting"
        template_dir = package / "templates"
        template_dir.mkdir(parents=True)
        (root / "README.md").write_text("temporary packaging fixture", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "easyprent-accounting"
version = "0.1.0"
dependencies = []

[tool.setuptools.packages.find]
where = ["."]
include = ["easyprent_accounting*"]

[tool.setuptools.package-data]
"easyprent_accounting" = ["templates/*.ods"]
""",
            encoding="utf-8",
        )
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "config.py").write_text(
            "VERSION_MARKER = 'stale'\n" if stale else "VERSION_MARKER = 'clean'\n",
            encoding="utf-8",
        )
        (template_dir / "utility_settlement.ods").write_bytes(
            b"stale template" if stale else b"clean template"
        )
        if stale:
            (package / "old_marker.py").write_text("OLD = True\n", encoding="utf-8")
        return root

    def _legacy_wheel(self, directory: Path) -> Path:
        wheel_path = directory / "easy_rem-0.1.0-py3-none-any.whl"
        info = "easy_rem-0.1.0.dist-info"
        entries = {
            "src/__init__.py": b"",
            "src/easyprent_accounting/__init__.py": b"",
            "src/easyprent_accounting/old.py": b"LEGACY = True\n",
            f"{info}/METADATA": b"Metadata-Version: 2.1\nName: easy-rem\nVersion: 0.1.0\n",
            f"{info}/WHEEL": b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        }
        entries[f"{info}/RECORD"] = (
            "\n".join(f"{name},," for name in (*entries, f"{info}/RECORD")) + "\n"
        ).encode("utf-8")
        with zipfile.ZipFile(wheel_path, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        return wheel_path

    def _dirty_canonical_wheel(self, clean_wheel: Path, directory: Path) -> Path:
        """Model the old canonical RECORD that still owned legacy src files."""
        dirty_wheel = directory / clean_wheel.name
        directory.mkdir()
        with zipfile.ZipFile(clean_wheel) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        record_name = next(name for name in entries if name.endswith(".dist-info/RECORD"))
        old_paths = {
            "src/__init__.py": b"",
            "src/easyprent_accounting/__init__.py": b"",
            "src/easyprent_accounting/old.py": b"LEGACY = True\n",
        }
        entries.update(old_paths)
        entries[record_name] += "".join(f"{name},,\n" for name in old_paths).encode("utf-8")
        with zipfile.ZipFile(dirty_wheel, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        return dirty_wheel

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

    def test_build_clean_wheel_isolates_dirty_artifacts_without_deleting_them(self) -> None:
        project_root = self._copy_project_source()
        dirty_build = project_root / "build" / "lib" / "src" / "easyprent_accounting"
        dirty_build.mkdir(parents=True, exist_ok=True)
        dirty_build_marker = dirty_build / "dirty_leak.py"
        dirty_build_marker.write_text("# dirty", encoding="utf-8")

        dirty_egg = project_root / "easy_rem.egg-info"
        dirty_egg.mkdir(exist_ok=True)
        dirty_egg_marker = dirty_egg / "PKG-INFO"
        dirty_egg_marker.write_text("Name: easy-rem", encoding="utf-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            wheel_path = build_clean_wheel(project_root, output_dir, python_executable=sys.executable)

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

            self.assertTrue(dirty_build_marker.is_file())
            self.assertTrue(dirty_egg_marker.is_file())

    def test_uninstall_legacy_distribution_propagates_pip_failure(self) -> None:
        with self.assertRaises(subprocess.CalledProcessError):
            uninstall_legacy_distribution(python_executable="/bin/false")

    def test_packaging_command_uses_install_interface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch(
            "easyprent_accounting.packaging.install_checkout"
        ) as install_mock:
            result = main(["install", temp_dir])

        self.assertEqual(result, 0)
        install_mock.assert_called_once_with(Path(temp_dir))

    def test_packaging_preflight_command_checks_target(self) -> None:
        with mock.patch(
            "easyprent_accounting.packaging.validate_install_target_writable"
        ) as validate_mock:
            result = main(["preflight-install"])

        self.assertEqual(result, 0)
        validate_mock.assert_called_once_with()

    def test_preflight_rejects_nonwritable_existing_package_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            site_packages = root / "lib" / "site-packages"
            protected = site_packages / "easyprent_accounting" / "templates"
            protected.mkdir(parents=True)
            (root / "bin").mkdir()
            protected.chmod(0o555)
            try:
                with mock.patch(
                    "easyprent_accounting.packaging.sysconfig.get_path",
                    return_value=str(site_packages),
                ), mock.patch(
                    "easyprent_accounting.packaging.sys.executable",
                    str(root / "bin" / "python"),
                ):
                    with self.assertRaises(PermissionError) as ctx:
                        validate_install_target_writable()
            finally:
                protected.chmod(0o755)

        self.assertIn(str(protected), str(ctx.exception))
        self.assertIn("no automatic chown", str(ctx.exception))

    def test_install_aborts_before_build_if_existing_venv_is_unwritable(self) -> None:
        with mock.patch(
            "easyprent_accounting.packaging.validate_install_target_writable",
            side_effect=PermissionError("mixed-owner venv"),
        ), mock.patch("easyprent_accounting.packaging.build_clean_wheel") as build_mock:
            with self.assertRaises(PermissionError):
                install_checkout(Path("/unused"))

        build_mock.assert_not_called()

    def test_fresh_venv_can_build_with_pyproject_build_isolation(self) -> None:
        project_root = self._copy_project_source()
        temp_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        venv_dir = temp_dir / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        venv_python = venv_dir / "bin" / "python"
        no_backend = subprocess.run(
            [str(venv_python), "-I", "-c", "import setuptools"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(no_backend.returncode, 0)

        wheel_path = build_clean_wheel(
            project_root,
            temp_dir / "wheels",
            python_executable=str(venv_python),
        )
        self.assertTrue(wheel_path.is_file())

    def test_same_version_install_activates_clean_wheel_and_retires_legacy(self) -> None:
        stale_root = self._minimal_project("stale", stale=True)
        clean_root = self._minimal_project("clean", stale=False)
        temp_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        venv_dir = temp_dir / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        venv_python = str(venv_dir / "bin" / "python")
        stale_wheel = build_clean_wheel(stale_root, temp_dir / "stale-wheels", venv_python)
        stale_wheel = self._dirty_canonical_wheel(stale_wheel, temp_dir / "dirty-wheels")
        legacy_wheel = self._legacy_wheel(temp_dir)
        subprocess.run(
            [venv_python, "-m", "pip", "install", "--no-deps", str(stale_wheel), str(legacy_wheel)],
            check=True,
            capture_output=True,
            text=True,
        )

        install_checkout(clean_root, python_executable=venv_python)
        with tempfile.TemporaryDirectory() as foreign_dir:
            rollback_check = subprocess.run(
                [
                    venv_python,
                    "-I",
                    "-c",
                    "import src.easyprent_accounting.old as old; assert old.LEGACY",
                ],
                cwd=foreign_dir,
                capture_output=True,
                text=True,
            )
        self.assertEqual(
            rollback_check.returncode,
            0,
            f"legacy unit could not restart before cutover: {rollback_check.stderr}",
        )
        uninstall_legacy_distribution(python_executable=venv_python)

        script = """
from importlib import metadata, util
import easyprent_accounting.config as config
assert config.VERSION_MARKER == 'clean'
assert util.find_spec('easyprent_accounting.old_marker') is None
assert metadata.distribution('easyprent-accounting').version == '0.1.0'
try:
    metadata.distribution('easy-rem')
except metadata.PackageNotFoundError:
    pass
else:
    raise AssertionError('easy-rem still installed')
try:
    legacy = util.find_spec('src.easyprent_accounting')
except ModuleNotFoundError:
    legacy = None
assert legacy is None
"""
        with tempfile.TemporaryDirectory() as foreign_dir:
            completed = subprocess.run(
                [venv_python, "-I", "-c", script],
                cwd=foreign_dir,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_package_fallback_renders_ods_in_foreign_cwd(self) -> None:
        project_root = self._copy_project_source()
        with tempfile.TemporaryDirectory() as wheel_dir, \
             tempfile.TemporaryDirectory() as site_dir, \
             tempfile.TemporaryDirectory() as foreign_dir:
            wheel_path = build_clean_wheel(project_root, Path(wheel_dir), sys.executable)
            with zipfile.ZipFile(wheel_path) as z:
                z.extractall(site_dir)

            bogus_template = Path(foreign_dir) / "templates" / "utility_settlement.ods"
            bogus_template.parent.mkdir()
            bogus_template.write_bytes(b"not an ods file")

            script = """
from pathlib import Path
from easyprent_accounting.config import load_config
from easyprent_accounting.ods_template import render_settlement_template
cfg = load_config({})
assert cfg.project_root == Path.cwd().resolve()
assert cfg.settlement_template is None
doc = render_settlement_template(
    template_path=cfg.settlement_template,
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
