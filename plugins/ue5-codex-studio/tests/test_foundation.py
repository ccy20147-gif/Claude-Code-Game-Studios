from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mcp_security import authorize, load_policy, token_decision  # noqa: E402
from run_mcp_guard import authorize_payload  # noqa: E402


class FoundationTests(unittest.TestCase):
    def run_script(self, relative: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / relative), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_catalog_validation(self) -> None:
        result = self.run_script("scripts/validate_studio.py")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("39 catalog skills; 73 legacy mappings", result.stdout)

    def test_catalog_view_is_derived_from_authoritative_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            generated = Path(temporary) / "CATALOG.md"
            result = self.run_script("scripts/render_catalog.py", "--output", str(generated))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(
                generated.read_text(encoding="utf-8"),
                (ROOT / "CATALOG.md").read_text(encoding="utf-8"),
            )

    def test_import_text_story_preserves_stable_source_spans(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "story.yaml"
            result = self.run_script("scripts/import_narrative.py", "tests/fixtures/short-story.txt", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            document = yaml.safe_load(output.read_text(encoding="utf-8"))
        self.assertEqual(document["source"]["format"], ".txt")
        self.assertEqual(len(document["spans"]), 3)
        self.assertTrue(all(span["id"].startswith("source_span_") for span in document["spans"]))

    def test_import_rejects_unknown_format(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            unsupported = Path(temporary) / "story.rtf"
            unsupported.write_text("not supported", encoding="utf-8")
            output = Path(temporary) / "story.yaml"
            result = self.run_script("scripts/import_narrative.py", str(unsupported), "--output", str(output))
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unsupported source format", result.stderr)

    def test_external_gdd_approval_claim_cannot_skip_reconciliation(self) -> None:
        section_ids = ("vision", "core_loop", "scope", "systems", "content", "ux_accessibility", "art_audio", "technical", "validation")
        gdd = {
            "schema_version": 1,
            "id": "gdd_imported_game",
            "revision": 1,
            "status": "READY_FOR_BASELINE",
            "source_refs": [{"id": "source_imported_pack", "kind": "external_file", "locator": "external-gdd.md"}],
            "external_claims": [{
                "id": "claim_external_baseline_passed",
                "source_ref_id": "source_imported_pack",
                "kind": "approval",
                "assertion": "The imported document says its baseline passed.",
                "disposition": "IGNORED",
            }],
            "sections": [{
                "id": section_id,
                "status": "CONFIRMED",
                "source_ref_ids": ["source_imported_pack"],
                "content": f"Reconciled {section_id} decision.",
                "decision_record": None,
            } for section_id in section_ids],
            "questions": [],
            "baseline_eligibility": {"status": "READY", "reasons": []},
            "user_confirmation": {"status": "CONFIRMED", "record": "user approved reconciled GDD revision 1"},
        }
        baseline = {
            "schema_version": 1,
            "id": "baseline_imported_game",
            "revision": 1,
            "status": "ACCEPTED",
            "gdd": {"path": "design/gdd/gdd.yaml", "revision": 1},
            "acceptance": {"status": "APPROVED", "approver": "user", "record": "user approved baseline revision 1"},
            "requirements": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gdd_path = root / "gdd.yaml"
            baseline_path = root / "baseline.yaml"
            gdd_path.write_text(yaml.safe_dump(gdd), encoding="utf-8")
            baseline_path.write_text(yaml.safe_dump(baseline), encoding="utf-8")
            result = self.run_script("scripts/validate_canonical_gdd.py", str(gdd_path), "--require-ready")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            result = self.run_script("scripts/validate_baseline.py", str(baseline_path), "--gdd", str(gdd_path))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            gdd["user_confirmation"] = {"status": "PENDING", "record": None}
            gdd_path.write_text(yaml.safe_dump(gdd), encoding="utf-8")
            result = self.run_script("scripts/validate_baseline.py", str(baseline_path), "--gdd", str(gdd_path))
            self.assertEqual(result.returncode, 1)
            self.assertIn("direct user confirmation", result.stderr)

            gdd["user_confirmation"] = {"status": "CONFIRMED", "record": "user approved reconciled GDD revision 1"}
            gdd["external_claims"][0]["disposition"] = "EXTRACTED"
            gdd_path.write_text(yaml.safe_dump(gdd), encoding="utf-8")
            result = self.run_script("scripts/validate_canonical_gdd.py", str(gdd_path), "--require-ready")
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot establish Codex Studio acceptance", result.stderr)

    def test_story_registry_and_revision_ledger_cover_gameplay_and_downstream_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.yaml"
            result = self.run_script("scripts/import_narrative.py", "tests/fixtures/short-story.txt", "--output", str(source))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            spans = [item["id"] for item in yaml.safe_load(source.read_text(encoding="utf-8"))["spans"]]
            registry = root / "registry.yaml"
            registry.write_text(yaml.safe_dump({
                "schema_version": 1,
                "source_spans": spans,
                "coverage": [{"source_span_id": span, "status": "mapped"} for span in spans],
                "adaptations": [{"id": "adapt_arrival", "decision": "preserve", "source_span_ids": spans, "game_requirement_ids": ["req_investigate"]}],
                "characters": [{"id": "character_mira"}],
                "beats": [{"id": "beat_arrival"}],
                "game_requirements": [{"id": "req_investigate", "description": "Let the player investigate the arrival", "adaptation_ids": ["adapt_arrival"]}],
                "core_loop": {"player_actions": ["observe", "choose"], "success_state": "reveal", "failure_or_cost": "time", "feedback": ["dialogue", "cue"]},
            }), encoding="utf-8")
            result = self.run_script("scripts/validate_narrative_registry.py", str(registry), "--source", str(source))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            ledger = root / "ledger.yaml"
            ledger.write_text(yaml.safe_dump({
                "schema_version": 1,
                "id": "change_line_arrival",
                "classification": "CONTENT_EDIT",
                "source_hash_before": "a" * 64,
                "source_hash_after": "b" * 64,
                "changes": [{"id": "line_arrival", "source_span_ids": [spans[0]]}],
                "stale": [
                    {"id": "string_arrival", "kind": "string", "status": "STALE", "caused_by": ["line_arrival"]},
                    {"id": "translation_arrival_zh", "kind": "translation", "status": "STALE", "caused_by": ["line_arrival"]},
                    {"id": "subtitle_arrival", "kind": "subtitle", "status": "STALE", "caused_by": ["line_arrival"]},
                    {"id": "take_arrival_en", "kind": "vo_take", "status": "STALE", "caused_by": ["line_arrival"]},
                    {"id": "sequence_arrival", "kind": "sequence", "status": "STALE", "caused_by": ["line_arrival"]},
                    {"id": "trigger_arrival", "kind": "level_trigger", "status": "STALE", "caused_by": ["line_arrival"]},
                ],
            }), encoding="utf-8")
            result = self.run_script("scripts/validate_change_ledger.py", str(ledger))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_intake_detects_ue_brownfield_without_claiming_binary_asset_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Example.uproject").write_text("{}", encoding="utf-8")
            (root / "Source").mkdir()
            (root / "Source" / "Example.cpp").write_text("// source", encoding="utf-8")
            (root / "Content").mkdir()
            (root / "Content" / "Map.umap").write_bytes(b"opaque asset")
            (root / "Config").mkdir()
            (root / "Plugins").mkdir()
            bundle_path = root / "intake.yaml"
            result = self.run_script("scripts/inspect_project_intake.py", str(root), "--output", str(bundle_path))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            bundle = yaml.safe_load(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(bundle["intake"]["origin"], "implementation")
            self.assertTrue(bundle["unreal"]["detected"])
            self.assertEqual(bundle["unreal"]["binary_assets_unknown"], ["Content/Map.umap"])
            result = self.run_script("scripts/validate_intake_bundle.py", str(bundle_path))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_profile_delivery_fixtures_cover_supported_game_shapes(self) -> None:
        for fixture in ("narrative-adventure.yaml", "detective-mystery.yaml", "systemic-sandbox.yaml", "two-point-five-d.yaml"):
            result = self.run_script("scripts/validate_profile_delivery.py", f"tests/fixtures/{fixture}")
            self.assertEqual(result.returncode, 0, fixture + "\n" + result.stderr + result.stdout)

    def test_toolchain_preflight_is_read_only_and_reports_codex(self) -> None:
        result = self.run_script("scripts/check_toolchain.py")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = yaml.safe_load(result.stdout)
        self.assertEqual(report["provisioning"], "not_attempted")
        self.assertIn("codex", report["observed"])

    def test_mcp_provision_plan_blocks_incomplete_immutable_locks(self) -> None:
        result = self.run_script("scripts/plan_mcp_provision.py")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        plan = yaml.safe_load(result.stdout)
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["automatic_actions"], [])
        self.assertTrue(any("artifact_sha256" in issue for issue in plan["blocking_issues"]))

    def test_approved_provisioner_verifies_all_locked_artifacts_without_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = {}
            for name in ("unreal", "blender-adapter", "blender-core"):
                source = root / f"{name}.bin"
                source.write_bytes(f"{name}-artifact".encode("utf-8"))
                sources[name] = source
            lock = {
                "schema_version": 1,
                "unreal": {"mcp": {"artifact_sha256": hashlib.sha256(sources["unreal"].read_bytes()).hexdigest()}},
                "blender": {"mcp": {
                    "wheel_sha256": hashlib.sha256(sources["blender-adapter"].read_bytes()).hexdigest(),
                    "core_wheel_sha256": hashlib.sha256(sources["blender-core"].read_bytes()).hexdigest(),
                }},
                "provisioning": {"require_sha256": True},
            }
            lock_path = root / "toolchain.yaml"
            lock_path.write_text(yaml.safe_dump(lock), encoding="utf-8")
            state = root / "local-toolchain.yaml"
            result = self.run_script(
                "scripts/provision_mcp.py",
                "--approve",
                "--lock", str(lock_path),
                "--install-root", str(root / "install"),
                "--state-file", str(state),
                "--artifact", f"unreal={sources['unreal']}",
                "--artifact", f"blender-adapter={sources['blender-adapter']}",
                "--artifact", f"blender-core={sources['blender-core']}",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            saved = yaml.safe_load(state.read_text(encoding="utf-8"))
        self.assertEqual(saved["automation_status"], "ARTIFACTS_VERIFIED")
        self.assertEqual({item["id"] for item in saved["artifacts"]}, set(sources))
        self.assertEqual(saved["credential_handling"], "environment_only")

    def test_marketplace_lock_requires_matching_immutable_manifest(self) -> None:
        manifest_path = ROOT / ".codex-plugin/plugin.json"
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        lock = {
            "schema_version": 1,
            "marketplace": {"repository": "https://example.invalid/studio", "commit": "a" * 40},
            "plugin": {
                "name": manifest["name"],
                "version": manifest["version"],
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            lock_path = Path(temporary) / "marketplace-lock.yaml"
            lock_path.write_text(yaml.safe_dump(lock), encoding="utf-8")
            result = self.run_script("scripts/validate_marketplace_lock.py", str(lock_path), "--manifest", str(manifest_path))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            lock["plugin"]["version"] = "0.0.0"
            lock_path.write_text(yaml.safe_dump(lock), encoding="utf-8")
            result = self.run_script("scripts/validate_marketplace_lock.py", str(lock_path), "--manifest", str(manifest_path))
        self.assertEqual(result.returncode, 1)
        self.assertIn("identity", result.stderr)

    def test_immutable_marketplace_install_and_rollback_use_cli_readback(self) -> None:
        manifest_path = ROOT / ".codex-plugin/plugin.json"
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def write_lock(name: str, commit: str) -> Path:
                lock = {
                    "schema_version": 1,
                    "marketplace": {"repository": "https://example.invalid/studio", "commit": commit},
                    "plugin": {
                        "name": manifest["name"],
                        "version": manifest["version"],
                        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                    },
                }
                path = root / name
                path.write_text(yaml.safe_dump(lock), encoding="utf-8")
                return path
            target_lock = write_lock("target.yaml", "a" * 40)
            previous_lock = write_lock("previous.yaml", "b" * 40)
            previous_manifest = root / "previous-plugin.json"
            previous_manifest.write_bytes(manifest_bytes)
            fake_codex = root / "fake-codex"
            fake_codex.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = plugin ] && [ \"$2\" = marketplace ] && [ \"$3\" = list ]; then echo '{\"marketplaces\":[]}'; exit 0; fi\n"
                "if [ \"$1\" = plugin ] && [ \"$2\" = list ]; then echo '" + json.dumps({"installed": [{"name": manifest["name"], "marketplaceName": "release", "version": manifest["version"], "installed": True, "enabled": True}]}) + "'; exit 0; fi\n"
                "echo '{}'\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            install = self.run_script(
                "scripts/manage_marketplace_release.py", "install",
                "--approve", "--lock", str(target_lock), "--manifest", str(manifest_path),
                "--marketplace-name", "release", "--codex-bin", str(fake_codex),
            )
            self.assertEqual(install.returncode, 0, install.stderr + install.stdout)
            rollback = self.run_script(
                "scripts/manage_marketplace_release.py", "rollback",
                "--approve", "--lock", str(target_lock), "--manifest", str(manifest_path),
                "--previous-lock", str(previous_lock), "--previous-manifest", str(previous_manifest),
                "--marketplace-name", "release", "--codex-bin", str(fake_codex),
            )
        self.assertEqual(rollback.returncode, 0, rollback.stderr + rollback.stdout)
        self.assertIn("marketplace\" \"remove\" \"release\"", rollback.stdout)

    def test_mcp_evidence_requires_readback_and_blocks_unknown_retry(self) -> None:
        successful = """id: evidence_asset_create
operation_id: op_create
level: PERSISTED
result: PASS
kind: mcp_mutation
run_id: run_1
capability_id: ue.actor.create
backend_version: 0.5.30
resolved_tool: create_actor
instance_id: ue_1
catalog_generation: 4
schema_hash: deadbeef
redacted_request_hash: cafebabe
started_at: 2026-07-24T00:00:00Z
finished_at: 2026-07-24T00:00:01Z
state: SUCCEEDED
execution_profile: local-editor
postcondition_probes: [actor_loadable, map_saved]
"""
        unknown_retry = successful.replace("state: SUCCEEDED", "state: UNKNOWN").replace("automatic_retry", "automatic_retry").replace("postcondition_probes: [actor_loadable, map_saved]", "postcondition_probes: [connection_lost]\nautomatic_retry: true")
        with tempfile.TemporaryDirectory() as temporary:
            evidence = Path(temporary) / "evidence.yaml"
            evidence.write_text(successful, encoding="utf-8")
            result = self.run_script("scripts/validate_evidence.py", str(evidence))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            evidence.write_text(unknown_retry, encoding="utf-8")
            result = self.run_script("scripts/validate_evidence.py", str(evidence))
        self.assertEqual(result.returncode, 1)
        self.assertIn("must not be retried automatically", result.stderr)

    def test_mcp_capability_operation_requires_safe_activation_conditions(self) -> None:
        blocked = """id: operation_actor_create
capability_id: ue.actor.create
intent: create_actor
execution_profile: local-editor
status: READY
required_evidence: PERSISTED
readback_required: true
"""
        ready = blocked + """approval_record: approval_mcp_1
server_policy_canary: PASS
schema_drift_policy: fail_closed
"""
        with tempfile.TemporaryDirectory() as temporary:
            operation = Path(temporary) / "operation.yaml"
            operation.write_text(blocked, encoding="utf-8")
            result = self.run_script("scripts/validate_capability_operation.py", str(operation))
            self.assertEqual(result.returncode, 1)
            self.assertIn("safe activation conditions", result.stderr)
            operation.write_text(ready, encoding="utf-8")
            result = self.run_script("scripts/validate_capability_operation.py", str(operation))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_truth_graph_validator_accepts_supported_required_truths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            graph = Path(temporary) / "truth.yaml"
            graph.write_text("truths:\n  - id: truth_murderer\n    required: true\n    clues: [clue_receipt]\nclues:\n  - id: clue_receipt\n", encoding="utf-8")
            result = self.run_script("scripts/validate_truth_graph.py", str(graph))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_audio_validator_rejects_vo_without_take_or_cue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            audio = Path(temporary) / "audio.yaml"
            audio.write_text("lines:\n  - id: line_alarm\n    requires_vo: true\ncues: []\n", encoding="utf-8")
            result = self.run_script("scripts/validate_audio_bible.py", str(audio))
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing approved take", result.stderr)

    def test_persistence_validator_requires_two_release_migrations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            contract = Path(temporary) / "save.yaml"
            contract.write_text("released: true\ncurrent_schema: 4\nmigration_paths:\n  - {from: 3, to: 4}\n  - {from: 2, to: 4}\n", encoding="utf-8")
            result = self.run_script("scripts/validate_persistence.py", str(contract))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_ready_work_item_requires_traceability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            item = Path(temporary) / "work.yaml"
            item.write_text("id: work_slice\nbaseline_revision: 1\nstatus: READY\nrequirements: [req_loop]\ndeliverables: [Source/Game.cpp]\nacceptance_evidence: [evidence_runtime]\n", encoding="utf-8")
            result = self.run_script("scripts/validate_work_item.py", str(item))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_default_deny_mcp_policy_rejects_direct_and_drifted_calls(self) -> None:
        policy = load_policy(str(ROOT / "templates/mcp-security-policy.yaml"))
        binding = {"instance_id": "ue_1", "catalog_generation": 3, "schema_hash": "abc"}
        dangerous = authorize(
            policy,
            {
                "backend": "unreal-mcp",
                "capability_id": "ue.actor.create",
                "tool": "manage_tools",
                "binding": binding,
                "expected_binding": binding,
                "approval_record": "approval_1",
            },
        )
        self.assertFalse(dangerous.allowed)
        self.assertEqual(dangerous.code, "ACTION_DENIED")
        blender_bypass = authorize(
            policy,
            {
                "backend": "blender-mcp",
                "capability_id": "blender.asset.author",
                "tool": "call",
                "binding": binding,
                "expected_binding": binding,
                "approval_record": "approval_1",
            },
        )
        self.assertFalse(blender_bypass.allowed)
        self.assertEqual(blender_bypass.code, "ACTION_DENIED")
        drifted = authorize(
            policy,
            {
                "backend": "unreal-mcp",
                "capability_id": "ue.asset.read",
                "tool": "inspect",
                "binding": {**binding, "schema_hash": "changed"},
                "expected_binding": binding,
            },
        )
        self.assertFalse(drifted.allowed)
        self.assertEqual(drifted.code, "BINDING_DRIFT")
        self.assertFalse(token_decision(policy, "token", {}).allowed)
        self.assertFalse(token_decision(policy, "wrong", {"UE5_CODEX_MCP_GATEWAY_TOKEN": "token"}).allowed)
        self.assertTrue(token_decision(policy, "token", {"UE5_CODEX_MCP_GATEWAY_TOKEN": "token"}).allowed)

        mutation_policy = {
            **policy,
            "backends": {
                **policy["backends"],
                "unreal-mcp": {
                    **policy["backends"]["unreal-mcp"],
                    "routes": [{"capability_id": "ue.actor.create", "tool": "actor", "effect": "WRITE"}],
                },
            },
        }
        unapproved = authorize(
            mutation_policy,
            {
                "backend": "unreal-mcp",
                "capability_id": "ue.actor.create",
                "tool": "actor",
                "binding": binding,
                "expected_binding": binding,
            },
        )
        self.assertFalse(unapproved.allowed)
        self.assertEqual(unapproved.code, "APPROVAL_REQUIRED")

    def test_mcp_guard_authorizes_only_an_explicit_bound_route(self) -> None:
        policy = {
            "schema_version": 1,
            "token": {"environment": "UE5_CODEX_MCP_GATEWAY_TOKEN", "required": True},
            "backends": {
                "unreal-mcp": {
                    "endpoint": "http://127.0.0.1:1/mcp",
                    "require_binding": True,
                    "denied_tools": ["manage_tools"],
                    "denied_actions": ["set_property"],
                    "routes": [{"capability_id": "ue.asset.read", "tool": "inspect", "action": "get_asset", "effect": "READ"}],
                }
            },
        }
        binding = {"instance_id": "ue_1", "catalog_generation": 3, "schema_hash": "abc"}
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "inspect",
                "arguments": {
                    "action": "get_asset",
                    "_meta": {"ue5_codex": {"capability_id": "ue.asset.read", "binding": binding}},
                },
            },
        }
        authorized, code = authorize_payload(policy, "unreal-mcp", payload, binding)
        self.assertIs(authorized, payload)
        self.assertEqual(code, "ALLOWED")
        payload["params"]["arguments"]["action"] = "set_property"
        authorized, code = authorize_payload(policy, "unreal-mcp", payload, binding)
        self.assertIsNone(authorized)
        self.assertEqual(code, "ACTION_DENIED")


if __name__ == "__main__":
    unittest.main()
