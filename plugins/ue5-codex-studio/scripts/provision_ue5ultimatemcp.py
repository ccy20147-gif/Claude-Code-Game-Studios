#!/usr/bin/env python3
"""Provision the patched UE5UltimateMCP as a project-local, controlled canary.

This Windows-only tool deliberately does not invoke the upstream Node bridge.
It accepts paths as individual argv values, never constructs a shell command,
and does not register Codex until an authenticated, schema-bound editor service
has been observed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "integrations" / "ue5ultimatemcp"
LOCK_PATH = ROOT / "templates" / "toolchain-lock.yaml"
STATE_RELATIVE = Path(".ue5-codex-studio") / "ue5ultimatemcp-local.json"
BACKUP_RELATIVE = Path(".ue5-codex-studio") / "ue5ultimatemcp-backups"
MCP_NAME = "ue5ultimatemcp-controlled"


class ProvisionError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def catalog_sha256(tools: Any) -> str:
    if not isinstance(tools, list):
        raise ProvisionError("UE /api/tools response has no tools list")
    return hashlib.sha256(canonical(tools).encode("ascii")).hexdigest()


def load_lock(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProvisionError(f"cannot read lock: {error}") from error
    mcp = value.get("unreal", {}).get("mcp", {}) if isinstance(value, dict) else {}
    required = ("upstream", "commit", "source_archive", "source_archive_sha256", "node_lockfile_sha256", "license")
    if any(not isinstance(mcp.get(key), str) or not mcp[key] for key in required):
        raise ProvisionError("toolchain lock lacks a complete UE5UltimateMCP source record")
    if mcp["upstream"] != "NodeNestor/UE5UltimateMCP" or len(mcp["commit"]) != 40:
        raise ProvisionError("toolchain lock does not identify the approved UE5UltimateMCP source")
    return value


def project_file(project: Path) -> Path:
    project = project.expanduser().resolve()
    if project.is_file() and project.suffix == ".uproject":
        return project
    if not project.is_dir():
        raise ProvisionError(f"project is not a directory or .uproject: {project}")
    choices = sorted(project.glob("*.uproject"))
    if len(choices) != 1:
        raise ProvisionError("project directory must contain exactly one .uproject file")
    return choices[0]


def ue_version(ue_root: Path) -> tuple[str, dict[str, Any]]:
    version_path = ue_root.expanduser().resolve() / "Engine" / "Build" / "Build.version"
    try:
        value = json.loads(version_path.read_text(encoding="utf-8"))
        version = f"{value['MajorVersion']}.{value['MinorVersion']}.{value['PatchVersion']}"
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ProvisionError(f"cannot read UE Build.version: {error}") from error
    if not version.startswith("5.7."):
        raise ProvisionError(f"only UE 5.7.x is supported, found {version}")
    return version, value


def tool_version(command: list[str]) -> dict[str, Any]:
    executable = shutil.which(command[0]) if len(command) == 1 else command[0]
    if executable is None or not Path(executable).exists() and shutil.which(executable) is None:
        return {"available": False, "detail": f"{command[0]} not found"}
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    except OSError as error:
        return {"available": False, "detail": str(error)}
    detail = (result.stdout or result.stderr).strip().splitlines()
    return {"available": result.returncode == 0, "detail": detail[0] if detail else f"exit {result.returncode}"}


def node_is_supported(detail: str) -> bool:
    version = detail.lstrip("v").split(".", 1)[0]
    return version.isdigit() and int(version) >= 20


def parse_uproject(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProvisionError(f"cannot safely parse .uproject: {error}") from error
    if not isinstance(value, dict):
        raise ProvisionError(".uproject root must be an object")
    plugins = value.get("Plugins", [])
    if not isinstance(plugins, list) or any(not isinstance(item, dict) for item in plugins):
        raise ProvisionError(".uproject Plugins must be an array of objects")
    return value


def require_windows() -> None:
    if platform.system() != "Windows":
        raise ProvisionError("UE5UltimateMCP provisioning is supported only on native Windows")


def endpoint(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ProvisionError("endpoint must be a plain http://127.0.0.1:PORT URL")
    if parsed.port is None or not 1024 <= parsed.port <= 65535:
        raise ProvisionError("endpoint port must be in 1024..65535")
    return parsed.geturl().rstrip("/")


def state_path(uproject: Path) -> Path:
    return uproject.parent / STATE_RELATIVE


def backup_root(uproject: Path) -> Path:
    return uproject.parent / BACKUP_RELATIVE


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, path)


def restrict_state_acl(path: Path) -> None:
    # The local state includes the generated token. The Windows user owns it;
    # failure to harden ACLs is fatal rather than leaving it broadly readable.
    username = os.environ.get("USERNAME")
    if not username:
        raise ProvisionError("USERNAME is required to protect the local state file")
    result = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:(R,W)"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ProvisionError(f"failed to restrict local-state ACL: {(result.stderr or result.stdout).strip()}")


def run(argv: list[str], cwd: Path | None = None, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProvisionError(f"command failed to start or timed out: {argv[0]}: {error}") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ProvisionError(f"command failed ({argv[0]}): {detail[-2000:]}")
    return result


def safe_extract(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        if not members or any(member.islnk() or member.issym() or Path(member.name).is_absolute() or ".." in Path(member.name).parts for member in members):
            raise ProvisionError("source archive has unsafe paths")
        top_levels = {Path(member.name).parts[0] for member in members if member.name}
        if len(top_levels) != 1:
            raise ProvisionError("source archive must have one top-level directory")
        tar.extractall(destination, members, filter="data")


def obtain_source(lock: dict[str, Any], destination: Path, source: Path | None, allow_download: bool) -> Path:
    mcp = lock["unreal"]["mcp"]
    archive = source.expanduser().resolve() if source else destination / "source.tar.gz"
    if source is None:
        if not allow_download:
            raise ProvisionError("a reviewed --source-archive is required unless --allow-download is supplied")
        destination.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(mcp["source_archive"], timeout=120) as response, archive.open("wb") as stream:
                shutil.copyfileobj(response, stream)
        except (OSError, urllib.error.URLError) as error:
            raise ProvisionError(f"source download failed: {error}") from error
    if not archive.is_file() or sha256(archive) != mcp["source_archive_sha256"]:
        raise ProvisionError("source archive checksum mismatch")
    return archive


def source_tree(archive: Path, staging: Path) -> Path:
    staging.mkdir(parents=True, exist_ok=True)
    extract = staging / "source"
    safe_extract(archive, extract)
    choices = [path for path in extract.iterdir() if path.is_dir()]
    if len(choices) != 1:
        raise ProvisionError("source archive layout is unexpected")
    source = choices[0]
    lockfile = source / "MCP" / "package-lock.json"
    if not lockfile.is_file():
        raise ProvisionError("locked upstream source lacks MCP/package-lock.json")
    return source


def patch_source(source: Path, ue_version_value: str) -> str:
    patch = INTEGRATION / "patches" / "0001-loopback-token-port.patch"
    git = shutil.which("git")
    if not git:
        raise ProvisionError("Git is required to apply the maintained security patch")
    run([git, "apply", "--whitespace=error", str(patch)], cwd=source)
    config_source = INTEGRATION / "loopback-DefaultEngine.ini"
    config_target = source / "Config" / "DefaultEngine.ini"
    config_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(config_source, config_target)
    descriptor = source / "UE5UltimateMCP.uplugin"
    plugin = json.loads(descriptor.read_text(encoding="utf-8"))
    plugin["EngineVersion"] = ue_version_value
    descriptor.write_text(json.dumps(plugin, indent=2) + "\n", encoding="utf-8")
    return sha256(patch)


def backup_project(uproject: Path) -> dict[str, str]:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    root = backup_root(uproject) / stamp
    root.mkdir(parents=True, exist_ok=False)
    plugin = uproject.parent / "Plugins" / "UE5UltimateMCP"
    plugin_backup = root / "UE5UltimateMCP"
    if plugin.exists():
        shutil.copytree(plugin, plugin_backup)
    uproject_backup = root / uproject.name
    shutil.copy2(uproject, uproject_backup)
    return {"root": str(root), "plugin": str(plugin_backup) if plugin.exists() else "", "uproject": str(uproject_backup)}


def restore_backup(uproject: Path, backup: dict[str, str]) -> None:
    plugin = uproject.parent / "Plugins" / "UE5UltimateMCP"
    if plugin.exists():
        shutil.rmtree(plugin)
    backup_plugin = Path(backup.get("plugin", "")) if backup.get("plugin") else None
    if backup_plugin and backup_plugin.exists():
        shutil.copytree(backup_plugin, plugin)
    uproject_backup = Path(backup["uproject"])
    if uproject_backup.is_file():
        shutil.copy2(uproject_backup, uproject)


def enable_plugin(uproject: Path) -> None:
    value = parse_uproject(uproject)
    plugins = value.setdefault("Plugins", [])
    found = False
    for item in plugins:
        if item.get("Name") == "UE5UltimateMCP":
            item["Enabled"] = True
            found = True
    if not found:
        plugins.append({"Name": "UE5UltimateMCP", "Enabled": True})
    uproject.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def compiler(ue_root: Path) -> Path:
    candidate = ue_root / "Engine" / "Build" / "BatchFiles" / "RunUAT.bat"
    if not candidate.is_file():
        raise ProvisionError(f"RunUAT.bat missing under {ue_root}")
    return candidate


def codex_config(name: str, codex: str) -> dict[str, Any] | None:
    result = subprocess.run([codex, "mcp", "get", name, "--json"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ProvisionError("Codex MCP readback was not JSON") from error
    if not isinstance(value, dict):
        raise ProvisionError("Codex MCP readback was not an object")
    return value


def http_json(url: str, token: str, path: str) -> tuple[int, Any]:
    request = urllib.request.Request(f"{url}{path}", headers={"X-UE5-Codex-Token": token, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(payload)
        except json.JSONDecodeError:
            return error.code, {"error": payload}
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as error:
        raise ProvisionError(f"cannot contact UE service: {error}") from error


def assert_loopback_listener(url: str) -> None:
    port = urlparse(url).port
    result = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ProvisionError("cannot inspect the Windows TCP listener")
    local_addresses = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and f":{port}" in fields[1]:
            local_addresses.append(fields[1])
    if not any(address.startswith(f"127.0.0.1:{port}") for address in local_addresses):
        raise ProvisionError("UE HTTP listener is not bound to 127.0.0.1")
    if any(address.startswith((f"0.0.0.0:{port}", f"[::]:{port}")) for address in local_addresses):
        raise ProvisionError("UE HTTP listener has a non-loopback binding")


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    uproject = project_file(args.project)
    project = parse_uproject(uproject)
    version, _ = ue_version(args.ue_root)
    node = tool_version(["node", "--version"])
    tools = {"node": node, "npm": tool_version(["npm", "--version"]), "git": tool_version(["git", "--version"]), "codex": tool_version([str(args.codex), "--version"]), "msbuild": tool_version(["where", "msbuild"]), "cl": tool_version(["where", "cl"]), "windows_sdk_rc": tool_version(["where", "rc"])}
    report = {
        "schema_version": 1,
        "status": "READY" if node["available"] and node_is_supported(str(node["detail"])) else "BLOCKED",
        "project": str(uproject),
        "ue_version": version,
        "project_is_cpp": (uproject.parent / "Source").is_dir(),
        "project_plugins": [item.get("Name") for item in project.get("Plugins", [])],
        "tools": tools,
        "platform": platform.system(),
    }
    if not all(bool(tools[name]["available"]) for name in ("npm", "git", "codex", "msbuild", "cl", "windows_sdk_rc")):
        report["status"] = "BLOCKED"
        report["reason"] = "Node, npm, Git, Codex CLI, Visual Studio C++ tools, and Windows SDK are required"
    if not report["project_is_cpp"]:
        report["status"] = "BLOCKED"
        report["reason"] = "only C++ projects are supported"
    if platform.system() != "Windows":
        report["status"] = "BLOCKED"
        report["reason"] = "native Windows is required"
    return report


def command_plan(args: argparse.Namespace) -> int:
    try:
        load_lock(args.lock)
        print(yaml.safe_dump(preflight(args), sort_keys=False), end="")
        return 0
    except (OSError, ProvisionError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


def command_install(args: argparse.Namespace) -> int:
    if not args.approve:
        print("FAIL: installation requires --approve", file=sys.stderr)
        return 1
    backup: dict[str, str] | None = None
    try:
        require_windows()
        lock = load_lock(args.lock)
        report = preflight(args)
        if report["status"] != "READY":
            raise ProvisionError(f"preflight blocked: {report.get('reason', 'required tool unavailable')}")
        uproject = project_file(args.project)
        version, _ = ue_version(args.ue_root)
        staging = uproject.parent / ".ue5-codex-studio" / "staging" / lock["unreal"]["mcp"]["commit"]
        if staging.exists():
            raise ProvisionError(f"refusing to reuse staging directory: {staging}")
        archive = obtain_source(lock, staging, args.source_archive, args.allow_download)
        source = source_tree(archive, staging)
        lockfile_hash = sha256(source / "MCP" / "package-lock.json")
        if lockfile_hash != lock["unreal"]["mcp"]["node_lockfile_sha256"]:
            raise ProvisionError("upstream Node package-lock checksum mismatch")
        patch_hash = patch_source(source, version)
        package = staging / "package"
        run([str(compiler(args.ue_root.resolve())), "BuildPlugin", f"-Plugin={source / 'UE5UltimateMCP.uplugin'}", f"-Package={package}", "-TargetPlatforms=Win64"], cwd=source)
        built_plugin = package
        if not (built_plugin / "UE5UltimateMCP.uplugin").is_file():
            raise ProvisionError("UE plugin build did not produce a deployable plugin")
        backup = backup_project(uproject)
        target = uproject.parent / "Plugins" / "UE5UltimateMCP"
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(built_plugin, target)
        enable_plugin(uproject)
        token = secrets.token_urlsafe(48)
        state = {
            "schema_version": 1,
            "automation_status": "DEPLOYED_PENDING_AUTHENTICATED_CANARY",
            "project": str(uproject),
            "project_sha256": sha256(uproject),
            "ue_version": version,
            "node_version": report["tools"]["node"]["detail"],
            "endpoint": endpoint(args.endpoint),
            "token": token,
            "source": {"commit": lock["unreal"]["mcp"]["commit"], "archive_sha256": lock["unreal"]["mcp"]["source_archive_sha256"], "node_lockfile_sha256": lockfile_hash, "license": lock["unreal"]["mcp"]["license"]},
            "patch_sha256": patch_hash,
            "backup": backup,
            "catalog": {"status": "PENDING", "sha256": None},
            "codex": {"name": MCP_NAME, "configuration_readback": "PENDING"},
            "canary": {"status": "PENDING"},
        }
        local_state = state_path(uproject)
        atomic_json(local_state, state)
        restrict_state_acl(local_state)
    except (OSError, ProvisionError) as error:
        if backup:
            try: restore_backup(project_file(args.project), backup)
            except (OSError, ProvisionError): pass
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: compiled and deployed project-local plugin. Start the editor with UE5ULTIMATEMCP_TOKEN set, then run doctor --accept-catalog. State: {state_path(project_file(args.project))}")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    try:
        require_windows()
        uproject = project_file(args.project)
        state_file = state_path(uproject)
        state = json.loads(state_file.read_text(encoding="utf-8"))
        url = endpoint(state["endpoint"])
        assert_loopback_listener(url)
        status, anonymous = http_json(url, "", "/api/health")
        if status != 401:
            raise ProvisionError("UE service accepted a missing token")
        status, health = http_json(url, state["token"], "/api/health")
        if status != 200 or health.get("status") != "ok":
            raise ProvisionError("authenticated health check failed")
        status, catalog = http_json(url, state["token"], "/api/tools")
        if status != 200:
            raise ProvisionError("authenticated tool discovery failed")
        names = {item.get("name") for item in catalog.get("tools", []) if isinstance(item, dict)}
        policy = json.loads((INTEGRATION / "policy.json").read_text(encoding="utf-8"))
        required = set(policy["required_upstream_tools"])
        if not required <= names:
            raise ProvisionError("UE tool discovery lacks a required controlled tool")
        if not names <= set(policy["known_upstream_tools"]):
            raise ProvisionError("UE tool discovery contains an unrecognized tool")
        fingerprint = catalog_sha256(catalog.get("tools"))
        if state["catalog"].get("sha256") and state["catalog"]["sha256"] != fingerprint:
            raise ProvisionError("UE catalog schema drift detected")
        if args.accept_catalog:
            if not args.approve:
                raise ProvisionError("accepting the catalog and registering Codex requires --approve")
            if codex_config(MCP_NAME, str(args.codex)) is not None:
                raise ProvisionError(f"Codex MCP configuration {MCP_NAME} already exists; refusing to overwrite")
            run([str(args.codex), "mcp", "add", MCP_NAME, "--", "node", str(INTEGRATION / "adapter.mjs"), "--state-file", str(state_file)])
            readback = codex_config(MCP_NAME, str(args.codex))
            if readback is None:
                raise ProvisionError("Codex MCP configuration readback failed")
            state["catalog"] = {"status": "APPROVED", "sha256": fingerprint, "tool_count": len(catalog["tools"])}
            state["codex"] = {"name": MCP_NAME, "configuration_readback": "PASS"}
            state["automation_status"] = "CATALOG_BOUND_PENDING_CANARY"
            try:
                atomic_json(state_file, state)
                restrict_state_acl(state_file)
            except (OSError, ProvisionError):
                try: run([str(args.codex), "mcp", "remove", MCP_NAME])
                except ProvisionError: pass
                raise
        print(json.dumps({"status": "PASS", "authenticated": True, "anonymous_status": anonymous.get("error", "rejected"), "catalog_sha256": fingerprint, "catalog_accepted": state["catalog"].get("status") == "APPROVED"}, indent=2))
        return 0
    except (OSError, KeyError, TypeError, json.JSONDecodeError, ProvisionError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


def command_remove(args: argparse.Namespace) -> int:
    if not args.approve:
        print("FAIL: removal requires --approve", file=sys.stderr)
        return 1
    try:
        require_windows()
        uproject = project_file(args.project)
        state_file = state_path(uproject)
        state = json.loads(state_file.read_text(encoding="utf-8"))
        restore_backup(uproject, state["backup"])
        existing = codex_config(MCP_NAME, str(args.codex))
        if existing is not None:
            run([str(args.codex), "mcp", "remove", MCP_NAME])
        state_file.unlink(missing_ok=True)
    except (OSError, KeyError, TypeError, json.JSONDecodeError, ProvisionError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: removed controlled MCP configuration and restored the project backup")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "install", "doctor", "remove"))
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--ue-root", type=Path, required=True)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    parser.add_argument("--endpoint", default="http://127.0.0.1:9847")
    parser.add_argument("--source-archive", type=Path)
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--accept-catalog", action="store_true")
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()
    if args.command == "plan": return command_plan(args)
    if args.command == "install": return command_install(args)
    if args.command == "doctor": return command_doctor(args)
    return command_remove(args)


if __name__ == "__main__":
    raise SystemExit(main())
