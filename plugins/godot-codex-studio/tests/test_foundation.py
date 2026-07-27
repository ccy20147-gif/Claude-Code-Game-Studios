from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
CLI = ROOT / "scripts" / "godot-mcp-cli.mjs"


class GodotStudioTests(unittest.TestCase):
    def command(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, cwd=cwd or REPO, text=True, capture_output=True, check=False)

    def test_plugin_contract_and_shared_drift(self) -> None:
        result = self.command("python3", str(ROOT / "scripts" / "validate_studio.py"))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        for plugin in (ROOT, REPO / "plugins" / "ue5-codex-studio"):
            result = self.command("python3", str(ROOT / "scripts" / "sync_shared_contracts.py"), str(plugin), "--check")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_cli_syntax_and_unapproved_install(self) -> None:
        result = self.command("node", "--check", str(CLI))
        self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.godot").write_text("[application]\nconfig/name=\"Fixture\"\n", encoding="utf-8")
            result = self.command("node", str(CLI), "install", "--project", str(project))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--approve", result.stderr)

    def test_approved_install_requires_a_godot_executable_for_canary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.godot").write_text("[application]\nconfig/name=\"Fixture\"\n", encoding="utf-8")
            result = self.command("node", str(CLI), "install", "--approve", "--project", str(project))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --godot", result.stderr)

    def test_plan_detects_project_and_csharp_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.godot").write_text("[application]\nconfig/name=\"Fixture\"\n", encoding="utf-8")
            result = self.command("node", str(CLI), "plan", "--project", str(project))
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertTrue(plan["observed"]["project_exists"])
            self.assertEqual(plan["observed"]["tools"], 21)
            (project / "Fixture.csproj").write_text("<Project />", encoding="utf-8")
            result = self.command("node", str(CLI), "plan", "--project", str(project))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["observed"]["csharp"])

    def test_project_intake_preserves_resource_uncertainty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project, output = Path(temporary), Path(temporary) / "intake.yaml"
            (project / "project.godot").write_text("[application]\nconfig/name=\"Fixture\"\n", encoding="utf-8")
            (project / "main.gd").write_text("extends Node\n", encoding="utf-8")
            (project / "level.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")
            result = self.command("python3", str(ROOT / "scripts" / "inspect_project_intake.py"), str(project), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            bundle = yaml.safe_load(output.read_text(encoding="utf-8"))
        self.assertTrue(bundle["godot"]["detected"])
        self.assertEqual(bundle["godot"]["resources_requiring_editor_validation"], ["level.tscn"])

    @unittest.skipUnless(shutil.which("godot") or shutil.which("godot4"), "Godot editor is not installed")
    def test_gdscript_fixture_headless_imports(self) -> None:
        godot = shutil.which("godot") or shutil.which("godot4")
        result = self.command("python3", str(ROOT / "scripts" / "validate_godot_project.py"), str(ROOT / "tests" / "fixtures" / "gdscript"), "--godot", godot)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
