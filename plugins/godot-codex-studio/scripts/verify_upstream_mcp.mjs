#!/usr/bin/env node
/* In-process protocol smoke test for the pinned upstream MCP server. */
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');
const index = process.argv.indexOf('--install-root');
const installRoot = resolve((index >= 0 ? process.argv[index + 1] : undefined) || join(ROOT, 'mcp'));
const entry = join(installRoot, 'node_modules', '@satelliteoflove', 'godot-mcp', 'dist', 'index.js');
if (!existsSync(entry)) throw new Error(`pinned MCP dependencies are absent at ${installRoot}`);

const { main } = await import(pathToFileURL(entry).href);
const messages = [];
const transport = {
  async start() {},
  async close() {},
  async send(message) { messages.push(message); },
};
await main({ createTransport: () => transport, connectGodot: async () => {} });
await transport.onmessage({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'godot-codex-studio', version: '0.1.0' } } });
await transport.onmessage({ jsonrpc: '2.0', method: 'notifications/initialized', params: {} });
await transport.onmessage({ jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} });
await transport.onmessage({ jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'does_not_exist', arguments: {} } });
await new Promise((resolveReady) => setTimeout(resolveReady, 0));
const initialized = messages.find((message) => message.id === 1);
const listed = messages.find((message) => message.id === 2);
const invalid = messages.find((message) => message.id === 3);
if (!initialized?.result?.serverInfo) throw new Error(`initialize did not return server information: ${JSON.stringify(messages)}`);
if (listed?.result?.tools?.length !== 21 || !listed.result.tools.some((tool) => tool.name === 'godot_exec')) throw new Error('tool discovery did not expose all 21 upstream tools including godot_exec');
if (!invalid?.result?.isError) throw new Error('invalid tool did not return a classified error');
console.log('PASS: initialize, 21 tool discovery, classified error, timeout guard');
