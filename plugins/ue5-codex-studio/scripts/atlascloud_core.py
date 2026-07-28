"""Shared fail-closed AtlasCloud client and project artifact helpers."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from validate_atlascloud_lock import canonical_sha, load_and_validate


ASSET_ID = re.compile(r"asset_[a-z0-9_]+$")
PREDICTION_ID = re.compile(r"[A-Za-z0-9_-]{1,160}$")
TERMINAL_SUCCESS = {"completed", "succeeded"}
TERMINAL_FAILURE = {"failed"}
IN_PROGRESS = {"created", "processing", "starting", "queued"}


class AtlasError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: object, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        os.chmod(path, mode)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def project_path(project: Path, relative: str, *, must_exist: bool = False) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise AtlasError("project file must be a safe relative path")
    project = project.resolve()
    target = (project / relative).resolve()
    if target != project and project not in target.parents:
        raise AtlasError("project file escapes the project root")
    if must_exist and not target.is_file():
        raise AtlasError(f"project file does not exist: {relative}")
    return target


def validate_image_file(path: Path, maximum_bytes: int) -> None:
    if not path.is_file() or path.stat().st_size > maximum_bytes:
        raise AtlasError(f"input image is absent or exceeds {maximum_bytes} bytes")
    suffix = path.suffix.lower()
    with path.open("rb") as stream:
        head = stream.read(16)
    valid = (
        suffix == ".png" and head.startswith(b"\x89PNG\r\n\x1a\n")
        or suffix in {".jpg", ".jpeg"} and head.startswith(b"\xff\xd8\xff")
        or suffix == ".webp" and head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    )
    if not valid:
        raise AtlasError("input must be a valid PNG, JPEG, or WebP image")


def _unwrap(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AtlasError("AtlasCloud returned a non-object response")
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise AtlasError("AtlasCloud response data is invalid")
    return data


@dataclass(frozen=True)
class LockedModel:
    id: str
    tool: str
    capability_id: str
    effect: str
    output_kind: str
    required: tuple[str, ...]
    optional: tuple[str, ...]
    defaults: dict[str, Any]
    enums: dict[str, list[Any]]
    ranges: dict[str, dict[str, int]]


class Contract:
    def __init__(self, lock_path: Path):
        self.raw, self.sha256 = load_and_validate(lock_path)
        self.api_origin = self.raw["api_origin"]
        self.paths = self.raw["paths"]
        self.outputs = self.raw["outputs"]
        self.models: dict[str, LockedModel] = {}
        self.tools: dict[str, LockedModel] = {}
        for value in self.raw["models"]:
            model = LockedModel(
                id=value["id"], tool=value["tool"], capability_id=value["capability_id"],
                effect=value["effect"], output_kind=value["output_kind"],
                required=tuple(value["required"]), optional=tuple(value["optional"]),
                defaults=dict(value.get("defaults", {})), enums=dict(value.get("enums", {})),
                ranges=dict(value.get("ranges", {})),
            )
            self.models[model.id] = model
            self.tools[model.tool] = model

    def validate_arguments(self, tool: str, arguments: object) -> tuple[LockedModel, dict[str, Any]]:
        model = self.tools.get(tool)
        if model is None:
            raise AtlasError("tool is not in the reviewed AtlasCloud contract")
        if not isinstance(arguments, dict):
            raise AtlasError("arguments must be an object")
        allowed = set(model.required + model.optional)
        if set(arguments) - allowed:
            raise AtlasError(f"unknown model parameters: {sorted(set(arguments) - allowed)}")
        result = {**model.defaults, **arguments}
        for key in model.required:
            if key not in result or result[key] in (None, "", []):
                raise AtlasError(f"{key} is required")
        for key, values in model.enums.items():
            if key in result and result[key] not in values:
                raise AtlasError(f"{key} is outside the reviewed enum")
        for key, limits in model.ranges.items():
            value = result.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or not limits["minimum"] <= value <= limits["maximum"]:
                raise AtlasError(f"{key} is outside the reviewed range")
        if "prompt" in result and (not isinstance(result["prompt"], str) or not 1 <= len(result["prompt"]) <= 12000):
            raise AtlasError("prompt must contain 1 to 12000 characters")
        if "images" in result and (not isinstance(result["images"], list) or not result["images"] or not all(isinstance(item, str) for item in result["images"])):
            raise AtlasError("images must be a non-empty list of project files")
        if "image" in result and not isinstance(result["image"], str):
            raise AtlasError("image must be a project file")
        if "enable_pbr" in result and not isinstance(result["enable_pbr"], bool):
            raise AtlasError("enable_pbr must be boolean")
        return model, result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):  # type: ignore[no-untyped-def]
        raise AtlasError("AtlasCloud redirect was refused")


class AtlasClient:
    def __init__(self, contract: Contract, api_key: str, *, api_origin: str | None = None, allow_test_http: bool = False):
        if not api_key:
            raise AtlasError("AtlasCloud API key is required")
        self.contract = contract
        self.api_key = api_key
        self.origin = (api_origin or contract.api_origin).rstrip("/")
        parsed = urllib.parse.urlparse(self.origin)
        if parsed.scheme != "https" and not (allow_test_http and parsed.scheme == "http" and parsed.hostname == "127.0.0.1"):
            raise AtlasError("AtlasCloud origin must use HTTPS")
        if not allow_test_http and parsed.hostname != "api.atlascloud.ai":
            raise AtlasError("AtlasCloud origin is not approved")
        self.allow_test_http = allow_test_http
        self.opener = urllib.request.build_opener(NoRedirect())

    def _request(self, method: str, path: str, *, data: bytes | None = None, content_type: str = "application/json", timeout: int = 60) -> dict[str, Any]:
        request = urllib.request.Request(
            self.origin + path,
            method=method,
            data=data,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": content_type, "Accept": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
        except AtlasError:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            raise AtlasError(f"AtlasCloud {method} {path} failed without retry: {type(error).__name__}") from error
        if len(raw) > 8 * 1024 * 1024:
            raise AtlasError("AtlasCloud JSON response exceeded 8 MiB")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AtlasError("AtlasCloud returned invalid JSON") from error
        return _unwrap(payload)

    def upload(self, path: Path) -> str:
        if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
            raise AtlasError("upload input is absent or exceeds 64 MiB")
        boundary = "----ue5codex" + os.urandom(12).hex()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        filename = re.sub(r"[^A-Za-z0-9_.-]", "_", path.name)[:160] or "upload.bin"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        result = self._request("POST", self.contract.paths["upload"], data=body, content_type=f"multipart/form-data; boundary={boundary}", timeout=120)
        url = result.get("url") or result.get("download_url")
        if not isinstance(url, str):
            raise AtlasError("upload response lacks a URL")
        self._validate_remote_url(url)
        return url

    def submit(self, model: LockedModel, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {"model": model.id, **arguments}
        result = self._request("POST", self.contract.paths["submit"], data=json.dumps(payload, separators=(",", ":")).encode())
        identifier = result.get("id") or result.get("prediction_id")
        if not isinstance(identifier, str) or not PREDICTION_ID.fullmatch(identifier):
            raise AtlasError("submission response lacks a safe prediction ID")
        echoed = result.get("model")
        if echoed not in (None, "", model.id):
            raise AtlasError("AtlasCloud echoed a different model ID")
        return {"id": identifier, "status": str(result.get("status", "created")).lower()}

    def prediction(self, prediction_id: str) -> dict[str, Any]:
        if not PREDICTION_ID.fullmatch(prediction_id):
            raise AtlasError("prediction ID is invalid")
        path = self.contract.paths["prediction"].replace("{prediction_id}", prediction_id)
        result = self._request("GET", path)
        status = str(result.get("status", "")).lower()
        if status not in TERMINAL_SUCCESS | TERMINAL_FAILURE | IN_PROGRESS:
            raise AtlasError(f"unknown AtlasCloud prediction status: {status or 'missing'}")
        return result

    def _validate_remote_url(self, url: str) -> urllib.parse.ParseResult:
        parsed = urllib.parse.urlparse(url)
        if self.allow_test_http and parsed.scheme == "http" and parsed.hostname == "127.0.0.1":
            return parsed
        if parsed.scheme != "https" or not parsed.hostname or not (parsed.hostname == "atlascloud.ai" or parsed.hostname.endswith(".atlascloud.ai")):
            raise AtlasError("output URL is outside AtlasCloud HTTPS hosts")
        if parsed.username or parsed.password or parsed.port not in (None, 443):
            raise AtlasError("output URL contains disallowed authority fields")
        return parsed

    def download(self, url: str, destination: Path, maximum_bytes: int, allowed_content_types: set[str]) -> tuple[str, int, str]:
        self._validate_remote_url(url)
        request = urllib.request.Request(url, headers={"Accept": "*/*"})
        try:
            with self.opener.open(request, timeout=180) as response:
                content_type = response.headers.get_content_type()
                length = int(response.headers.get("Content-Length", "0") or 0)
                if length > maximum_bytes:
                    raise AtlasError("AtlasCloud artifact exceeds its size limit")
                raw = response.read(maximum_bytes + 1)
        except AtlasError:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as error:
            raise AtlasError(f"artifact download failed without retry: {type(error).__name__}") from error
        if len(raw) > maximum_bytes:
            raise AtlasError("AtlasCloud artifact exceeds its size limit")
        if content_type not in allowed_content_types:
            raise AtlasError(f"artifact content type is not allowed: {content_type}")
        suffix = destination.suffix.lower()
        if suffix == ".png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise AtlasError("downloaded PNG signature is invalid")
        if suffix in {".jpg", ".jpeg"} and not raw.startswith(b"\xff\xd8\xff"):
            raise AtlasError("downloaded JPEG signature is invalid")
        if suffix == ".glb" and not raw.startswith(b"glTF"):
            raise AtlasError("downloaded GLB signature is invalid")
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=destination.name + ".", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return sha256_bytes(raw), len(raw), content_type


def redacted_request_hash(model: str, arguments: dict[str, Any]) -> str:
    redacted = dict(arguments)
    if "prompt" in redacted:
        redacted["prompt"] = {"sha256": sha256_bytes(redacted["prompt"].encode()), "length": len(redacted["prompt"])}
    return canonical_sha({"model": model, "arguments": redacted})


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
