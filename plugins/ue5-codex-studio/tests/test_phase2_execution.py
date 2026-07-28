from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class Phase2ExecutionTests(unittest.TestCase):
    def run_script(self, script: str, *args: str, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if environment:
            env.update(environment)
        return subprocess.run([sys.executable, str(ROOT / script), *args], cwd=ROOT, env=env, capture_output=True, text=True, check=False)

    def fake_ue(self, root: Path, body: str) -> tuple[Path, Path]:
        root.mkdir(parents=True, exist_ok=True)
        project = root / "Game.uproject"
        project.write_text("{}", encoding="utf-8")
        build = root / "UE" / "Engine" / "Build"
        build.mkdir(parents=True)
        (build / "Build.version").write_text('{"MajorVersion": 5, "MinorVersion": 7, "PatchVersion": 4}', encoding="utf-8")
        editor = root / "UE" / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
        editor.parent.mkdir(parents=True)
        editor.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        editor.chmod(0o755)
        return project, root / "UE"

    def fake_uat(self, root: Path, body: str) -> tuple[Path, Path]:
        project, ue_root = self.fake_ue(root, "exit 0\n")
        uat = ue_root / "Engine" / "Build" / "BatchFiles" / "RunUAT.bat"
        uat.parent.mkdir(parents=True)
        uat.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        uat.chmod(0o755)
        return project, ue_root

    def automation_args(self, project: Path, ue_root: Path, evidence: Path, execute: bool = False, timeout: str = "2") -> list[str]:
        values = [str(project), "--ue-root", str(ue_root), "--test-filter", "Project.Smoke.Menu", "--operation-id", "operation_smoke_menu", "--subject-ref", "work_smoke", "--evidence", str(evidence), "--timeout-seconds", timeout]
        return values + (["--execute"] if execute else [])

    def test_automation_dry_run_does_not_start_editor_and_rejects_raw_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            called = root / "called.txt"
            project, ue_root = self.fake_ue(root, 'echo called > "$FAKE_CALLED"\n')
            evidence = root / "evidence.yaml"
            result = self.run_script("scripts/run_ue_automation.py", *self.automation_args(project, ue_root, evidence), environment={"FAKE_CALLED": str(called)})
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("PLANNED", result.stdout)
            self.assertFalse(called.exists())
            self.assertFalse(evidence.exists())
            bad = self.run_script("scripts/run_ue_automation.py", str(project), "--ue-root", str(ue_root), "--test-filter", "Project.Smoke.Menu; quit", "--operation-id", "operation_bad", "--subject-ref", "work_smoke", "--evidence", str(evidence))
        self.assertEqual(bad.returncode, 1)
        self.assertIn("allowlisted", bad.stderr)

    def test_automation_execution_records_fixed_command_and_timeout_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args_path = root / "editor-args.txt"
            project, ue_root = self.fake_ue(root, 'printf "%s\\n" "$@" > "$FAKE_ARGS"\nexit 0\n')
            evidence = root / "success.yaml"
            result = self.run_script("scripts/run_ue_automation.py", *self.automation_args(project, ue_root, evidence, execute=True), environment={"FAKE_ARGS": str(args_path)})
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            command = args_path.read_text(encoding="utf-8")
            self.assertIn("-ExecCmds=Automation RunTests Project.Smoke.Menu; Quit", command)
            self.assertIn("-NullRHI", command)
            record = yaml.safe_load(evidence.read_text(encoding="utf-8"))
            self.assertEqual((record["result"], record["state"]), ("PASS", "SUCCEEDED"))
            self.assertEqual(self.run_script("scripts/validate_evidence.py", str(evidence)).returncode, 0)

            slow_project, slow_root = self.fake_ue(root / "slow", "sleep 2\n")
            timed = root / "timeout.yaml"
            result = self.run_script("scripts/run_ue_automation.py", *self.automation_args(slow_project, slow_root, timed, execute=True, timeout="1"))
            self.assertEqual(result.returncode, 1)
            record = yaml.safe_load(timed.read_text(encoding="utf-8"))
        self.assertEqual((record["result"], record["state"]), ("UNKNOWN", "UNKNOWN"))
        self.assertFalse(record["automatic_retry"])

    def test_package_is_win64_shipping_only_and_never_clears_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, ue_root = self.fake_uat(root, 'for arg in "$@"; do case "$arg" in -archivedirectory=*) out="${arg#-archivedirectory=}";; esac; done\nmkdir -p "$out"\necho package > "$out/Game-Win64-Shipping.pak"\nprintf "%s\\n" "$@" > "$FAKE_ARGS"\n')
            staging = root / "staging"
            evidence = root / "package-evidence.yaml"
            args = [str(project), "--ue-root", str(ue_root), "--staging-dir", str(staging), "--operation-id", "operation_package_win64", "--subject-ref", "work_package", "--evidence", str(evidence)]
            called = root / "uat-args.txt"
            plan = self.run_script("scripts/build_ue_package.py", *args, environment={"FAKE_ARGS": str(called)})
            self.assertEqual(plan.returncode, 0, plan.stderr + plan.stdout)
            self.assertFalse(called.exists())
            built = self.run_script("scripts/build_ue_package.py", *args, "--execute", environment={"FAKE_ARGS": str(called)})
            self.assertEqual(built.returncode, 0, built.stderr + built.stdout)
            self.assertIn("-platform=Win64", called.read_text(encoding="utf-8"))
            self.assertIn("-clientconfig=Shipping", called.read_text(encoding="utf-8"))
            manifest = staging / "package-manifest.yaml"
            self.assertEqual(self.run_script("scripts/validate_package_manifest.py", str(manifest), "--staging-dir", str(staging)).returncode, 0)
            self.assertEqual(self.run_script("scripts/validate_evidence.py", str(evidence)).returncode, 0)
            blocked = self.run_script("scripts/build_ue_package.py", *args)
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("never clears", blocked.stderr)

    def test_blueprint_and_dcc_contracts_reject_unapproved_or_unavailable_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            blueprint = root / "blueprint.yaml"
            blueprint.write_text((ROOT / "templates/blueprint-operation.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            passed = self.run_script("scripts/validate_blueprint_operation.py", str(blueprint))
            self.assertEqual(passed.returncode, 0, passed.stderr + passed.stdout)
            value = yaml.safe_load(blueprint.read_text(encoding="utf-8"))
            value.update({"action": "apply_allowlisted_graph_patch", "capability_id": "ue.blueprint.apply_allowlisted_graph_patch", "graph_patch_id": "graph_patch_interact", "status": "READY"})
            value.pop("template_id")
            blueprint.write_text(yaml.safe_dump(value), encoding="utf-8")
            rejected = self.run_script("scripts/validate_blueprint_operation.py", str(blueprint))
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("approval", rejected.stderr)
            value["approval_record"] = "approval_graph_patch"
            blueprint.write_text(yaml.safe_dump(value), encoding="utf-8")
            unavailable = self.run_script("scripts/validate_blueprint_operation.py", str(blueprint))
            self.assertEqual(unavailable.returncode, 1)
            self.assertIn("remain BLOCKED", unavailable.stderr)

            dcc = root / "dcc.yaml"
            dcc.write_text((ROOT / "templates/dcc-operation.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            self.assertEqual(self.run_script("scripts/validate_dcc_operation.py", str(dcc)).returncode, 0)
            dcc_value = yaml.safe_load(dcc.read_text(encoding="utf-8"))
            dcc_value.update({"action": "edit_existing_mesh", "capability_id": "dcc.model.modify_existing", "effect": "MODIFY", "target_path": "../escape.blend"})
            dcc.write_text(yaml.safe_dump(dcc_value), encoding="utf-8")
            rejected = self.run_script("scripts/validate_dcc_operation.py", str(dcc))
        self.assertEqual(rejected.returncode, 1)
        self.assertTrue("approval" in rejected.stderr or "project-relative" in rejected.stderr)


if __name__ == "__main__":
    unittest.main()
