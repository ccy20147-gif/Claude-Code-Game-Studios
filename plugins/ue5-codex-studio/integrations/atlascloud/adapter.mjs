#!/usr/bin/env node
/* Controlled stdio MCP adapter for the in-memory AtlasCloud session broker. */

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

function fail(message) { throw new Error(message); }

function loadState() {
  const path = argument("--state-file");
  if (!path) fail("--state-file is required");
  const state = JSON.parse(fs.readFileSync(path, "utf8"));
  if (state.schema_version !== 1 || typeof state.token !== "string" || state.token.length < 32) {
    fail("AtlasCloud session state is invalid or lacks a session token");
  }
  if (state.contract_sha256 !== policy.contract_sha256) {
    fail("AtlasCloud model contract drift detected");
  }
  const endpoint = new URL(state.endpoint);
  if (endpoint.protocol !== "http:" || endpoint.hostname !== "127.0.0.1") {
    fail("AtlasCloud session must bind HTTP loopback");
  }
  return { state, endpoint: endpoint.origin };
}

const runtime = loadState();

async function broker(path, options = {}) {
  const response = await fetch(`${runtime.endpoint}${path}`, {
    ...options,
    headers: {
      "X-Atlas-Session-Token": runtime.state.token,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    signal: AbortSignal.timeout(45_000),
  });
  const contentLength = Number(response.headers.get("content-length") || 0);
  if (contentLength > MAX_RESPONSE_BYTES) fail("AtlasCloud session response exceeds 8 MiB");
  const body = await response.text();
  if (body.length > MAX_RESPONSE_BYTES) fail("AtlasCloud session response exceeds 8 MiB");
  let payload;
  try { payload = JSON.parse(body); } catch { fail(`AtlasCloud session returned invalid JSON (${response.status})`); }
  if (!response.ok) fail(payload.error || `AtlasCloud session rejected request (${response.status})`);
  return payload;
}

async function verifiedHealth() {
  const health = await broker("/health");
  if (health.contract_sha256 !== policy.contract_sha256 || health.provider !== "atlascloud") {
    fail("AtlasCloud session contract binding drifted");
  }
  return health;
}

function text(value) {
  return { content: [{ type: "text", text: JSON.stringify(value, null, 2) }] };
}

function string(args, key) {
  if (!args || typeof args[key] !== "string" || !args[key]) fail(`${key} is required`);
  return args[key];
}

function common(args) {
  return {
    asset_id: string(args, "asset_id"),
    rights_record: string(args, "rights_record"),
    target_destination: string(args, "target_destination"),
    source_asset_ids: Array.isArray(args.source_asset_ids) ? args.source_asset_ids : [],
  };
}

async function generate(tool, envelope, parameters) {
  await verifiedHealth();
  const expected = policy.tools[tool];
  if (!expected) fail("tool is outside the controlled AtlasCloud policy");
  return text(await broker("/generate", {
    method: "POST",
    body: JSON.stringify({ tool, ...envelope, parameters }),
  }));
}

const assetId = { type: "string", pattern: "^asset_[a-z0-9_]+$" };
const commonProperties = {
  asset_id: assetId,
  rights_record: { type: "string", minLength: 1, maxLength: 512 },
  target_destination: { type: "string", pattern: "^/Game/[A-Za-z0-9_/]+$" },
};
const imageOptions = {
  size: { type: "string", enum: ["1024x1024", "1024x768", "768x1024", "1024x1536", "1536x1024", "2048x2048", "2048x1152", "1152x2048", "2560x1088", "1088x2560", "2880x2160", "2160x2880", "3840x2160", "2160x3840"] },
  quality: { type: "string", enum: ["low", "medium", "high"] },
  output_format: { type: "string", enum: ["jpeg", "png"] },
};

const tools = [
  ["atlas_health", "Verify the local AtlasCloud credential session and locked model contract.", { type: "object", properties: {}, additionalProperties: false }, async () => text(await verifiedHealth()), { readOnlyHint: true }],
  ["atlas_models", "List only the three model IDs in the reviewed asset-generation contract.", { type: "object", properties: {}, additionalProperties: false }, async () => {
    await verifiedHealth(); return text(await broker("/models"));
  }, { readOnlyHint: true }],
  ["atlas_generate_concept", "Create a new concept-art candidate with locked GPT Image 2 text-to-image. This never overwrites an asset.", {
    type: "object",
    properties: { ...commonProperties, prompt: { type: "string", minLength: 1, maxLength: 12000 }, ...imageOptions },
    required: ["asset_id", "rights_record", "target_destination", "prompt"],
    additionalProperties: false,
  }, async (args) => generate("atlas_generate_concept", common(args), {
    prompt: string(args, "prompt"),
    ...(args.size ? { size: args.size } : {}), ...(args.quality ? { quality: args.quality } : {}),
    ...(args.output_format ? { output_format: args.output_format } : {}),
  }), { readOnlyHint: false, destructiveHint: false, openWorldHint: true }],
  ["atlas_edit_concept", "Approval-required: derive a new concept from registered existing assets with locked GPT Image 2 Edit. Source files remain unchanged.", {
    type: "object",
    properties: {
      ...commonProperties,
      source_asset_ids: { type: "array", items: assetId, minItems: 1, maxItems: 16 },
      images: { type: "array", items: { type: "string", minLength: 1 }, minItems: 1, maxItems: 16 },
      prompt: { type: "string", minLength: 1, maxLength: 12000 },
      approval_record: { type: "string", pattern: "^approval_[a-z0-9_.-]{1,200}$" },
      ...imageOptions,
    },
    required: ["asset_id", "rights_record", "target_destination", "source_asset_ids", "images", "prompt", "approval_record"],
    additionalProperties: false,
  }, async (args) => {
    const approval = string(args, "approval_record");
    return generate("atlas_edit_concept", { ...common(args), approval_record: approval }, {
      prompt: string(args, "prompt"), images: args.images,
      ...(args.size ? { size: args.size } : {}), ...(args.quality ? { quality: args.quality } : {}),
      ...(args.output_format ? { output_format: args.output_format } : {}),
    });
  }, { readOnlyHint: false, destructiveHint: true, openWorldHint: true }],
  ["atlas_generate_mesh", "Create a new Hunyuan 3D Pro mesh candidate from a project-local image. This never overwrites an asset.", {
    type: "object",
    properties: {
      ...commonProperties,
      source_asset_ids: { type: "array", items: assetId, maxItems: 16 },
      image: { type: "string", minLength: 1 },
      generate_type: { type: "string", enum: ["Normal", "Geometry"] },
      enable_pbr: { type: "boolean" },
      face_count: { type: "integer", minimum: 40000, maximum: 1500000 },
    },
    required: ["asset_id", "rights_record", "target_destination", "image"],
    additionalProperties: false,
  }, async (args) => generate("atlas_generate_mesh", common(args), {
    image: string(args, "image"),
    ...(args.generate_type ? { generate_type: args.generate_type } : {}),
    ...(typeof args.enable_pbr === "boolean" ? { enable_pbr: args.enable_pbr } : {}),
    ...(Number.isInteger(args.face_count) ? { face_count: args.face_count } : {}),
  }), { readOnlyHint: false, destructiveHint: false, openWorldHint: true }],
  ["atlas_collect_job", "Poll one submitted AtlasCloud job and collect completed outputs into immutable project paths.", {
    type: "object",
    properties: { prediction_id: { type: "string", pattern: "^[A-Za-z0-9_-]{1,160}$" }, wait_seconds: { type: "integer", minimum: 0, maximum: 30 } },
    required: ["prediction_id"], additionalProperties: false,
  }, async (args) => {
    await verifiedHealth();
    return text(await broker("/collect", { method: "POST", body: JSON.stringify({ prediction_id: string(args, "prediction_id"), wait_seconds: args.wait_seconds || 0 }) }));
  }, { readOnlyHint: false, destructiveHint: false, openWorldHint: true }],
  ["atlas_get_job", "Read a local AtlasCloud job record without polling or spending credits.", {
    type: "object", properties: { prediction_id: { type: "string", pattern: "^[A-Za-z0-9_-]{1,160}$" } }, required: ["prediction_id"], additionalProperties: false,
  }, async (args) => {
    await verifiedHealth(); return text(await broker(`/jobs/${encodeURIComponent(string(args, "prediction_id"))}`));
  }, { readOnlyHint: true }],
];

function response(id, result) { return { jsonrpc: "2.0", id, result }; }
function error(id, message) { return { jsonrpc: "2.0", id, error: { code: -32000, message } }; }

async function dispatch(request) {
  if (!request || request.jsonrpc !== "2.0" || typeof request.method !== "string") return null;
  if (request.method === "notifications/initialized") return null;
  if (request.method === "initialize") return response(request.id, { protocolVersion: "2025-03-26", capabilities: { tools: {} }, serverInfo: { name: policy.name, version: "1.0.0" } });
  if (request.method === "tools/list") return response(request.id, { tools: tools.map(([name, description, inputSchema, , annotations]) => ({ name, description, inputSchema, annotations })) });
  if (request.method === "tools/call") {
    const target = tools.find(([name]) => name === request.params?.name);
    if (!target) return error(request.id, "tool is not exposed by the controlled AtlasCloud adapter");
    try { return response(request.id, await target[3](request.params?.arguments || {})); }
    catch (cause) { return error(request.id, cause instanceof Error ? cause.message : "controlled AtlasCloud adapter failed"); }
  }
  return error(request.id, "method is not supported by the controlled AtlasCloud adapter");
}

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  try { const result = await dispatch(JSON.parse(line)); if (result) process.stdout.write(`${JSON.stringify(result)}\n`); }
  catch (cause) { process.stdout.write(`${JSON.stringify(error(null, cause instanceof Error ? cause.message : "invalid request"))}\n`); }
}
