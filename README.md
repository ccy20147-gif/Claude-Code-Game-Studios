# Codex Game Studios

面向 Codex 的可追溯游戏开发工作流。仓库同时提供独立安装的 UE5 与 Godot 4 插件；它们共享稳定的设计契约，但不存在运行时跨插件依赖。

## 插件

| 引擎 | 插件 | 入口 |
| --- | --- | --- |
| Unreal Engine 5 | `ue5-codex-studio` | `$ue5-start-project` |
| Godot 4 | `godot-codex-studio` | `$godot-start-project` |

两者各有 39 个 skills，覆盖项目启动、GDD 协调、故事改编、设计、制作、QA、发布与运营。外部文档中的“已通过”仅是待核验声明，必须先经 GDD 协调与用户确认才能接受基线。UE5 当前完整的新项目闭环止于 `ACCEPTED baseline + READY work item`；编辑器/DCC 自动化和游戏发行必须以 capability catalog 的运行时可用性为准。

UE5 当前入口与恢复流程见 [UE5 Codex Studio Workflow](docs/UE5-CODEX-WORKFLOW.md)。

## 安装

```bash
git clone https://github.com/ccy20147-gif/codex-ue5-game-studio.git
cd codex-ue5-game-studio
codex plugin marketplace add . --json
codex plugin add godot-codex-studio@donchitos-game-studios --json
# 或：codex plugin add ue5-codex-studio@donchitos-game-studios --json
```

安装后开启新的 Codex 对话线程，以加载最新 skills。

## Godot MCP

Godot 的设计工作流不依赖 MCP。需要编辑器自动化时，调用 `$godot-setup-toolchain`。它先做只读预检，展示变更计划，并只在一次明确批准后安装固定的 `@satelliteoflove/godot-mcp@4.1.0`、部署 addon、写入 Codex stdio 配置、读回配置并执行编辑器 canary。

正式接受范围为原生 Windows/Linux、Node.js 20+ 与 Godot `>=4.5,<4.8`；Godot 4.7.1 是已验证基线。C# 项目还需要 Godot .NET 编辑器及 .NET SDK 8+。WSL2、macOS、移动端和 Web 导出不在首版验收范围。

## 验证

```bash
python3 -m unittest discover -s plugins/ue5-codex-studio/tests -v
python3 -m unittest discover -s plugins/godot-codex-studio/tests -v
python3 plugins/ue5-codex-studio/scripts/validate_studio.py
python3 plugins/godot-codex-studio/scripts/validate_studio.py
python3 plugins/godot-codex-studio/scripts/sync_shared_contracts.py plugins/ue5-codex-studio --check
python3 plugins/godot-codex-studio/scripts/sync_shared_contracts.py plugins/godot-codex-studio --check
git diff --check
```

这些静态测试不替代真实 Godot 编辑器中的保存、重载、输入、截图、`godot_exec`、停止运行和错误日志 canary。

## 许可证

[MIT](LICENSE)
