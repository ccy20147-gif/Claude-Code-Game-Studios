#!/usr/bin/env node
/* Approval-gated installer and stdio launcher for the pinned Godot MCP. */
import { createHash, randomUUID } from 'node:crypto';
import { cp, mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { existsSync, readdirSync } from 'node:fs';
import { homedir, platform } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { get } from 'node:https';

const HERE = dirname(fileURLToPath(import.meta.url));
const PLUGIN = resolve(HERE, '..');
const MCP = '@satelliteoflove/godot-mcp';
const VERSION = '4.1.0';
const SHA256 = '3f6df8842219ba6ca763cb310019147dbb16cd695a48d7316a727de2d38705a9';
const TARBALL = 'https://registry.npmjs.org/@satelliteoflove/godot-mcp/-/godot-mcp-4.1.0.tgz';
const TOOLS = ['godot_scene', 'godot_node_read', 'godot_node_edit', 'godot_editor_read', 'godot_editor_edit', 'godot_project', 'godot_animation_read', 'godot_animation_edit', 'godot_tilemap_read', 'godot_tilemap_edit', 'godot_gridmap_read', 'godot_gridmap_edit', 'godot_resource', 'godot_scene3d', 'godot_docs', 'godot_input', 'godot_profiler', 'godot_runtime_state', 'godot_game_time', 'godot_exec', 'godot_validate_meshes'];

function fail(message) { throw new Error(message); }
function usage() { return 'Usage: godot-mcp-cli.mjs <plan|install|doctor|update|remove|serve|canary> [--project PATH] [--godot PATH] [--codex PATH] [--approve]'; }
function arg(name, args) { const i = args.indexOf(`--${name}`); return i >= 0 ? args[i + 1] : undefined; }
function has(name, args) { return args.includes(`--${name}`); }
function baseDir() {
  if (process.platform === 'win32') return join(process.env.LOCALAPPDATA || join(homedir(), 'AppData', 'Local'), 'CodexGameStudios', 'godot-mcp', VERSION);
  return join(process.env.XDG_DATA_HOME || join(homedir(), '.local', 'share'), 'codex-game-studios', 'godot-mcp', VERSION);
}
function statePath(project) { return join(project, '.godot-codex-studio', 'toolchain-lock.yaml'); }
function command(bin, args, options = {}) {
  const result = spawnSync(bin, args, { encoding: 'utf8', ...options });
  if (result.error) fail(`${bin}: ${result.error.message}`);
  if (result.status !== 0) fail(`${bin} ${args.join(' ')} failed: ${(result.stderr || result.stdout).trim()}`);
  return result.stdout.trim();
}
function versionAtLeast(actual, major) { return /^v?(\d+)/.test(actual) && Number(RegExp.$1) >= major; }
function godotVersion(actual) {
  const match = /(4)\.(\d+)\.(\d+)/.exec(actual);
  return match ? { major: Number(match[1]), minor: Number(match[2]), patch: Number(match[3]), raw: match[0] } : null;
}
function acceptedGodot(actual) { const value = godotVersion(actual); return value && value.major === 4 && value.minor >= 5 && value.minor < 8; }
function isGodotProject(project) { return existsSync(join(project, 'project.godot')); }
function isCSharpProject(project) { return ['.csproj', '.sln', '.cs'].some((suffix) => scan(project, suffix)); }
function scan(root, suffix) {
  try { return readdirSync(root, { withFileTypes: true }).some((entry) => entry.isFile() && entry.name.endsWith(suffix)); } catch { return false; }
}
function inspect(project, godot, codex) {
  const observed = { host: process.platform, node: process.version, project, project_exists: isGodotProject(project), csharp: isCSharpProject(project), tools: TOOLS.length };
  const issues = [];
  if (!['linux', 'win32'].includes(process.platform)) issues.push('unsupported host: only native Windows and Linux are accepted');
  if (process.env.WSL_DISTRO_NAME) issues.push('WSL2 is outside the accepted host matrix');
  if (!versionAtLeast(process.version, 20)) issues.push('Node.js 20+ is required');
  if (!observed.project_exists) issues.push('project.godot is required');
  if (godot) { try { observed.godot = command(godot, ['--version']); if (!acceptedGodot(observed.godot)) issues.push('Godot version must be >=4.5,<4.8'); observed.godot_verification = godotVersion(observed.godot)?.raw === '4.7.1' ? 'VERIFIED_VERSION' : 'UNVERIFIED_VERSION'; } catch (error) { issues.push(error.message); } }
  if (observed.csharp) { try { observed.dotnet = command('dotnet', ['--version']); if (!versionAtLeast(observed.dotnet, 8)) issues.push('.NET SDK 8+ is required for C# projects'); } catch (error) { issues.push(error.message); } }
  if (codex) { try { observed.codex = command(codex, ['--version']); } catch (error) { issues.push(error.message); } }
  return { status: issues.length ? 'BLOCKED' : 'READY', observed, blocking_issues: issues, install_root: baseDir(), package: `${MCP}@${VERSION}`, tarball_sha256: SHA256, approval_required: true };
}
async function download(url, target) {
  await new Promise((resolveDownload, reject) => get(url, (response) => {
    if (response.statusCode !== 200) return reject(new Error(`download failed with HTTP ${response.statusCode}`));
    const parts = []; response.on('data', (part) => parts.push(part)); response.on('end', async () => { try { await writeFile(target, Buffer.concat(parts)); resolveDownload(); } catch (error) { reject(error); } });
  }).on('error', reject));
}
async function sha(path) { return createHash('sha256').update(await readFile(path)).digest('hex'); }
async function editProjectConfig(project) {
  const path = join(project, 'project.godot'); const original = await readFile(path, 'utf8'); const plugin = 'res://addons/godot_mcp/plugin.cfg';
  const section = /^\[editor_plugins\]\r?\n([\s\S]*?)(?=^\[|\Z)/m;
  let updated;
  if (!section.test(original)) updated = `${original.trimEnd()}\n\n[editor_plugins]\nenabled=PackedStringArray("${plugin}")\n`;
  else {
    const match = original.match(section); const body = match[1];
    if (/^enabled\s*=/.test(body) && !/^enabled\s*=PackedStringArray\([^\n]*\)\s*$/m.test(body)) fail('project.godot editor_plugins is not a safely editable PackedStringArray');
    if (body.includes(plugin)) return { original, updated: original };
    const nextBody = /^enabled\s*=/m.test(body) ? body.replace(/^(enabled\s*=PackedStringArray\()([^)]*)(\)\s*)$/m, `$1$2${body.match(/PackedStringArray\(\s*\)/) ? '' : ', '}"${plugin}"$3`) : `${body}enabled=PackedStringArray("${plugin}")\n`;
    updated = original.slice(0, match.index) + `[editor_plugins]\n${nextBody}` + original.slice(match.index + match[0].length);
  }
  await writeFile(path, updated); return { original, updated };
}
async function writeState(project, data) {
  const destination = statePath(project); await mkdir(dirname(destination), { recursive: true });
  const safe = Object.entries(data).map(([key, value]) => `${key}: ${JSON.stringify(value)}`).join('\n'); await writeFile(destination, `${safe}\n`);
}
function managedConfig(value, cliPath, root) {
  const text = JSON.stringify(value);
  const loopback = text.includes('GODOT_HOST=127.0.0.1') || text.includes('"GODOT_HOST":"127.0.0.1"');
  const port = text.includes('GODOT_PORT=6550') || text.includes('"GODOT_PORT":"6550"');
  return text.includes(cliPath) && text.includes('"serve"') && text.includes('"--install-root"') && text.includes(root) && loopback && port;
}
function getMcp(codex) {
  try { return JSON.parse(command(codex, ['mcp', 'get', 'godot-codex-studio', '--json'])); } catch { return null; }
}
function codexConfigPath() { return join(process.env.CODEX_HOME || join(homedir(), '.codex'), 'config.toml'); }
async function setApprovalMode() {
  const path = codexConfigPath(); const original = existsSync(path) ? await readFile(path, 'utf8') : null;
  const next = original === null ? 'default_tools_approval_mode = "writes"\n' : (/^default_tools_approval_mode\s*=/m.test(original) ? original.replace(/^default_tools_approval_mode\s*=.*$/m, 'default_tools_approval_mode = "writes"') : `${original.trimEnd()}\ndefault_tools_approval_mode = "writes"\n`);
  await mkdir(dirname(path), { recursive: true }); await writeFile(path, next);
  if (!(await readFile(path, 'utf8')).match(/^default_tools_approval_mode\s*=\s*"writes"\s*$/m)) fail('Codex approval mode readback failed');
  return { path, original };
}
async function restoreApprovalMode(snapshot) {
  if (!snapshot) return;
  if (snapshot.original === null) await rm(snapshot.path, { force: true }); else await writeFile(snapshot.path, snapshot.original);
}
async function install(args) {
  if (!has('approve', args)) fail('install is read-only until --approve is supplied');
  const project = resolve(arg('project', args) || process.cwd()); const godot = arg('godot', args); const codex = arg('codex', args) || 'codex';
  if (!godot) fail('install requires --godot <absolute Godot executable> so the required editor canary can run');
  const plan = inspect(project, godot, codex); if (plan.status !== 'READY') fail(plan.blocking_issues.join('; '));
  const installRoot = baseDir(); const staging = `${installRoot}.staging-${randomUUID()}`; const backup = `${installRoot}.previous-${Date.now()}`; const projectAddon = join(project, 'addons', 'godot_mcp'); const addonBackup = `${projectAddon}.godot-codex-studio-backup-${Date.now()}`; const cliPath = resolve(HERE, 'godot-mcp-cli.mjs');
  let projectBackup; let approvalBackup; let codexAdded = false;
  try {
    await mkdir(staging, { recursive: true }); await cp(join(PLUGIN, 'mcp', 'package.json'), join(staging, 'package.json')); await cp(join(PLUGIN, 'mcp', 'package-lock.json'), join(staging, 'package-lock.json'));
    const tarball = join(staging, 'godot-mcp.tgz'); await download(TARBALL, tarball); if (await sha(tarball) !== SHA256) fail('tarball SHA-256 mismatch');
    command('npm', ['cache', 'add', tarball]); command('npm', ['ci', '--omit=dev', '--ignore-scripts', '--offline'], { cwd: staging });
    const addon = join(staging, 'node_modules', '@satelliteoflove', 'godot-mcp', 'addon'); if (!existsSync(addon)) fail('verified package did not contain addon');
    if (existsSync(installRoot)) await rename(installRoot, backup); await rename(staging, installRoot);
    if (existsSync(projectAddon)) await rename(projectAddon, addonBackup); await mkdir(dirname(projectAddon), { recursive: true }); await cp(join(installRoot, 'node_modules', '@satelliteoflove', 'godot-mcp', 'addon'), projectAddon, { recursive: true }); await hardenAddon(projectAddon);
    projectBackup = await editProjectConfig(project); const projectBackupPath = join(project, '.godot-codex-studio', 'backup-project.godot'); await mkdir(dirname(projectBackupPath), { recursive: true }); await writeFile(projectBackupPath, projectBackup.original);
    const current = getMcp(codex); if (current && !managedConfig(current, cliPath, installRoot)) fail('existing godot-codex-studio MCP is not managed by this plugin; refusing to overwrite');
    command(codex, ['mcp', 'add', 'godot-codex-studio', '--env', 'GODOT_HOST=127.0.0.1', '--env', 'GODOT_PORT=6550', '--env', 'GODOT_MCP_USAGE_LOG=0', '--', 'node', cliPath, 'serve', '--install-root', installRoot]); codexAdded = true;
    const readback = getMcp(codex); if (!readback || !managedConfig(readback, cliPath, installRoot)) fail('Codex MCP configuration readback did not match managed launcher');
    approvalBackup = await setApprovalMode();
    const canary = await runCanary(project, godot, installRoot);
    await writeState(project, { version: VERSION, tarball_sha256: SHA256, install_root: installRoot, project, godot, godot_verification: plan.observed.godot_verification, node: process.version, codex_configuration: 'verified', approval_mode: 'writes', project_backup: projectBackupPath, addon_backup: existsSync(addonBackup) ? addonBackup : '', canary });
    return { status: 'READY', install_root: installRoot, addon_backup: existsSync(addonBackup) ? addonBackup : null, canary };
  } catch (error) {
    if (projectBackup) await writeFile(join(project, 'project.godot'), projectBackup.original);
    if (existsSync(projectAddon)) await rm(projectAddon, { recursive: true, force: true }); if (existsSync(addonBackup)) await rename(addonBackup, projectAddon);
    if (codexAdded) { try { command(codex, ['mcp', 'remove', 'godot-codex-studio']); } catch {} }
    await restoreApprovalMode(approvalBackup);
    if (existsSync(installRoot)) await rm(installRoot, { recursive: true, force: true }); if (existsSync(backup)) await rename(backup, installRoot);
    await rm(staging, { recursive: true, force: true }); throw error;
  }
}
function serve(args) {
  const root = resolve(arg('install-root', args) || baseDir()); const entry = join(root, 'node_modules', '@satelliteoflove', 'godot-mcp', 'dist', 'cli.js'); if (!existsSync(entry)) fail(`MCP package is not installed at ${root}`);
  const child = spawn(process.execPath, [entry], { stdio: 'inherit', env: { ...process.env, GODOT_HOST: '127.0.0.1', GODOT_PORT: '6550', GODOT_MCP_USAGE_LOG: '0' } }); child.on('exit', (code) => process.exit(code ?? 1));
}
async function hardenAddon(addon) {
  const plugin = join(addon, 'plugin.gd'); const source = await readFile(plugin, 'utf8');
  const hardened = source
    .replace(/func _get_listen_port\(\) -> int:[\s\S]*?\n\nfunc _resolve_bind_address/, 'func _get_listen_port() -> int:\n\treturn 6550\n\nfunc _resolve_bind_address')
    .replace(/func _resolve_bind_address\(\) -> String:[\s\S]*?\n\nfunc _is_valid_bind_address/, 'func _resolve_bind_address() -> String:\n\treturn MCPConstants.LOCALHOST_BIND_ADDRESS\n\nfunc _is_valid_bind_address');
  if (hardened === source || hardened.includes('BindMode.WSL')) fail('cannot safely harden pinned addon loopback policy');
  await writeFile(plugin, hardened);
}
async function runCanary(project, godot, installRoot) {
  const editor = spawn(godot, ['--editor', '--path', project], { detached: true, stdio: 'ignore' }); editor.unref();
  await new Promise((resolveReady) => setTimeout(resolveReady, 5000));
  const probe = spawnSync(process.execPath, [join(HERE, 'verify_upstream_mcp.mjs'), '--install-root', installRoot, '--bridge'], { encoding: 'utf8', timeout: 30000 });
  if (probe.status !== 0) fail(`editor canary failed: ${(probe.stderr || probe.stdout).trim()}`);
  return 'PASS';
}
async function remove(args) {
  if (!has('approve', args)) fail('remove is read-only until --approve is supplied');
  const project = resolve(arg('project', args) || process.cwd()); const codex = arg('codex', args) || 'codex'; const addon = join(project, 'addons', 'godot_mcp');
  const lock = existsSync(statePath(project)) ? await readFile(statePath(project), 'utf8') : ''; if (!lock.includes(`version: ${JSON.stringify(VERSION)}`)) fail('refusing to remove addon without a matching Godot Codex Studio lock');
  const current = getMcp(codex); if (current && !managedConfig(current, resolve(HERE, 'godot-mcp-cli.mjs'), baseDir())) fail('refusing to remove an unmanaged MCP configuration');
  const quoted = (key) => { const match = new RegExp(`^${key}:\\s*(.+)$`, 'm').exec(lock); try { return match ? JSON.parse(match[1]) : ''; } catch { return ''; } };
  const projectBackup = quoted('project_backup'); const addonBackup = quoted('addon_backup');
  command(codex, ['mcp', 'remove', 'godot-codex-studio']); await rm(addon, { recursive: true, force: true }); if (addonBackup && existsSync(addonBackup)) await rename(addonBackup, addon); if (projectBackup && existsSync(projectBackup)) await rename(projectBackup, join(project, 'project.godot')); await rm(statePath(project), { force: true }); return { status: 'REMOVED', project };
}
async function main() {
  const [action = 'doctor', ...args] = process.argv.slice(2); if (has('help', args)) return console.log(usage());
  if (action === 'serve') return serve(args); if (action === 'install' || action === 'update') return console.log(JSON.stringify(await install(args), null, 2)); if (action === 'remove') return console.log(JSON.stringify(await remove(args), null, 2)); if (action === 'canary') { if (!has('approve', args)) fail('canary requires --approve'); const project = resolve(arg('project', args) || process.cwd()); const godot = arg('godot', args); if (!godot) fail('canary requires --godot'); return console.log(JSON.stringify({ canary: await runCanary(project, godot, resolve(arg('install-root', args) || baseDir())) }, null, 2)); }
  const project = resolve(arg('project', args) || process.cwd()); const result = inspect(project, arg('godot', args), arg('codex', args)); if (action === 'plan' || action === 'doctor') return console.log(JSON.stringify(result, null, 2));
  fail(`unknown command: ${action}\n${usage()}`);
}
main().catch((error) => { console.error(`godot-codex-studio: ${error.message}`); process.exitCode = 1; });
