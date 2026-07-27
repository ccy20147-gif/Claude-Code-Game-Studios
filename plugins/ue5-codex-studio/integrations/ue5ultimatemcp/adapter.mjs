#!/usr/bin/env node
/* Controlled stdio MCP adapter for the patched UE5UltimateMCP REST service. */

import crypto from "node:crypto";
import fs from "node:fs";
import readline from "node:readline";
import process from "node:process";

const ROOT = new URL(".", import.meta.url);
const policy = JSON.parse(fs.readFileSync(new URL("policy.json", ROOT), "utf8"));
const MAX_RESPONSE_BYTES = 8 * 1024 * 1024;

function argument(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

function fail(message) {
  throw new Error(message);
}

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function sha256(value) {
  return crypto.createHash("sha256").update(canonical(value)).digest("hex");
}

function loadState() {
  const statePath = argument("--state-file");
  if (!statePath) fail("--state-file is required");
  const state = JSON.parse(fs.readFileSync(statePath, "utf8"));
  if (state.schema_version !== 1 || typeof state.token !== "string" || state.token.length < 32) {
    fail("local state is invalid or lacks a capability token");
  }
  if (typeof state.endpoint !== "string") fail("local state lacks endpoint");
  const endpoint = new URL(state.endpoint);
  if (endpoint.protocol !== "http:" || endpoint.hostname !== "127.0.0.1") {
    fail("only an HTTP 127.0.0.1 endpoint is permitted");
  }
  if (!state.catalog || !/^[a-f0-9]{64}$/.test(state.catalog.sha256 || "")) {
    fail("local state lacks an approved upstream schema hash");
  }
  return { state, endpoint: endpoint.origin };
}

const runtime = loadState();

async function rest(path, options = {}) {
  const response = await fetch(`${runtime.endpoint}${path}`, {
    ...options,
    headers: { "X-UE5-Codex-Token": runtime.state.token, "Content-Type": "application/json", ...(options.headers || {}) },
    signal: AbortSignal.timeout(30_000),
  });
  const contentLength = Number(response.headers.get("content-length") || 0);
  if (contentLength > MAX_RESPONSE_BYTES) fail("UE response exceeds controlled adapter limit");
  const body = await response.text();
  if (body.length > MAX_RESPONSE_BYTES) fail("UE response exceeds controlled adapter limit");
  let payload;
  try { payload = JSON.parse(body); } catch { fail(`UE returned invalid JSON (${response.status})`); }
  if (!response.ok) fail(`UE HTTP ${response.status}: ${payload.error || "request rejected"}`);
  return payload;
}

let catalogPromise;
async function verifiedCatalog() {
  if (!catalogPromise) {
    catalogPromise = (async () => {
      const payload = await rest("/api/tools");
      if (!Array.isArray(payload.tools)) fail("UE tool discovery response is invalid");
      const names = new Set();
      for (const tool of payload.tools) {
        if (!tool || typeof tool.name !== "string" || !policy.known_upstream_tools.includes(tool.name)) {
          fail("UE tool catalog contains an unrecognized tool; refusing to expose automation");
        }
        if (names.has(tool.name)) fail("UE tool catalog contains a duplicate tool name");
        names.add(tool.name);
      }
      for (const required of policy.required_upstream_tools) {
        if (!names.has(required)) fail(`UE tool catalog lacks required tool ${required}`);
      }
      const fingerprint = sha256(payload.tools);
      if (fingerprint !== runtime.state.catalog.sha256) {
        fail("UE tool catalog schema drift detected; refusing to expose automation");
      }
      return { tools: payload.tools, fingerprint };
    })();
  }
  return catalogPromise;
}

function text(value) {
  return { content: [{ type: "text", text: JSON.stringify(value, null, 2) }] };
}

function requireString(args, key) {
  if (!args || typeof args[key] !== "string" || !args[key]) fail(`${key} is required`);
  return args[key];
}

function checkCanaryMap(map) {
  if (!map.startsWith(policy.canary_map_prefix) || map.includes("..") || /[^A-Za-z0-9_/.]/.test(map)) {
    fail(`canary_map must start with ${policy.canary_map_prefix}`);
  }
}

async function requireActiveCanary(map) {
  checkCanaryMap(map);
  const level = await execute("get_level_info", {});
  const basename = map.slice(map.lastIndexOf("/") + 1);
  if (typeof level.map_name !== "string" || (level.map_name !== basename && level.map_name !== map)) {
    fail("the requested canary map is not the active editor map");
  }
}

async function execute(tool, args) {
  await verifiedCatalog();
  const result = await rest("/api/tool", { method: "POST", body: JSON.stringify({ tool, ...args }) });
  if (result.success !== true) fail(result.error || `UE tool ${tool} failed`);
  return result.result || {};
}

const tools = [
  ["ue_health", "Verify the patched local UE service and its approved catalog.", { type: "object", properties: {}, additionalProperties: false }, async () => {
    const health = await rest("/api/health"); const catalog = await verifiedCatalog(); return text({ health, schema_hash: catalog.fingerprint });
  }, { readOnlyHint: true }],
  ["ue_discover", "List the controlled UE capabilities. This does not expose upstream dynamic tools.", { type: "object", properties: {}, additionalProperties: false }, async () => {
    const catalog = await verifiedCatalog(); return text({ schema_hash: catalog.fingerprint, allowed: tools.map(([name]) => name) });
  }, { readOnlyHint: true }],
  ["ue_get_level", "Read the active editor level summary.", { type: "object", properties: {}, additionalProperties: false }, async () => text(await execute("get_level_info", {})), { readOnlyHint: true }],
  ["ue_list_actors", "Read actors in the active editor level.", { type: "object", properties: {}, additionalProperties: false }, async () => text(await execute("get_actors_in_level", {})), { readOnlyHint: true }],
  ["ue_find_actors", "Find actors by a name substring in the active editor level.", { type: "object", properties: { pattern: { type: "string", minLength: 1, maxLength: 128 } }, required: ["pattern"], additionalProperties: false }, async (args) => text(await execute("find_actors_by_name", { pattern: requireString(args, "pattern") })), { readOnlyHint: true }],
  ["ue_capture_viewport", "Capture the active editor viewport for canary inspection.", { type: "object", properties: { width: { type: "integer", minimum: 64, maximum: 1920 }, height: { type: "integer", minimum: 64, maximum: 1080 } }, additionalProperties: false }, async (args) => text(await execute("capture_viewport", args || {})), { readOnlyHint: true }],
  ["ue_canary_create_actor", "Approval-required: create an actor only in the active __CodexCanary_ map with a __CodexCanary_ name.", { type: "object", properties: { canary_map: { type: "string" }, name: { type: "string" }, type: { type: "string", enum: ["StaticMeshActor", "PointLight", "SpotLight", "DirectionalLight", "CameraActor"] }, location: { type: "array", items: { type: "number" }, minItems: 3, maxItems: 3 } }, required: ["canary_map", "name", "type"], additionalProperties: false }, async (args) => {
    const name = requireString(args, "name"); if (!name.startsWith(policy.actor_prefix)) fail(`name must start with ${policy.actor_prefix}`);
    await requireActiveCanary(requireString(args, "canary_map"));
    return text(await execute("spawn_actor", { name, type: requireString(args, "type"), ...(Array.isArray(args.location) ? { location: args.location } : {}) }));
  }, { readOnlyHint: false, destructiveHint: true }],
  ["ue_canary_delete_actor", "Approval-required: delete a __CodexCanary_ actor only from the active __CodexCanary_ map.", { type: "object", properties: { canary_map: { type: "string" }, name: { type: "string" } }, required: ["canary_map", "name"], additionalProperties: false }, async (args) => {
    const name = requireString(args, "name"); if (!name.startsWith(policy.actor_prefix)) fail(`name must start with ${policy.actor_prefix}`);
    await requireActiveCanary(requireString(args, "canary_map")); return text(await execute("delete_actor", { name }));
  }, { readOnlyHint: false, destructiveHint: true }],
];

function response(id, result) { return { jsonrpc: "2.0", id, result }; }
function error(id, message) { return { jsonrpc: "2.0", id, error: { code: -32000, message } }; }

async function dispatch(request) {
  if (!request || request.jsonrpc !== "2.0" || typeof request.method !== "string") return null;
  if (request.method === "notifications/initialized") return null;
  if (request.method === "initialize") return response(request.id, { protocolVersion: "2025-03-26", capabilities: { tools: {} }, serverInfo: { name: "ue5ultimatemcp-controlled", version: "1.0.0" } });
  if (request.method === "tools/list") return response(request.id, { tools: tools.map(([name, description, inputSchema, , annotations]) => ({ name, description, inputSchema, annotations })) });
  if (request.method === "tools/call") {
    const target = tools.find(([name]) => name === request.params?.name);
    if (!target) return error(request.id, "tool is not exposed by the controlled adapter");
    try { return response(request.id, await target[3](request.params?.arguments || {})); }
    catch (cause) { return error(request.id, cause instanceof Error ? cause.message : "controlled adapter failed"); }
  }
  return error(request.id, "method is not supported by the controlled adapter");
}

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  try { const result = await dispatch(JSON.parse(line)); if (result) process.stdout.write(`${JSON.stringify(result)}\n`); }
  catch (cause) { process.stdout.write(`${JSON.stringify(error(null, cause instanceof Error ? cause.message : "invalid request"))}\n`); }
}
