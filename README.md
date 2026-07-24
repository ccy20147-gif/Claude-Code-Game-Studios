# Codex UE Game Studios

面向 Codex 的 Unreal Engine 5 游戏开发插件。它将零想法、小说或剧本、
已有游戏方案、以及已有 UE 工程，统一转为可追溯的设计、制作、验证、发布和运营工作流。

核心工作流不依赖 MCP。可以先完成创意、叙事、系统、关卡、音频、UX、架构和工作计划；
只有需要让 Codex 自动操作 Unreal Editor 或 Blender 时，才进入 MCP 配置与实机验证阶段。

## 能做什么

- 38 个 Codex skills，覆盖项目启动、剧本改编、设计、资产、制作、QA、发布与运营。
- 将小说、剧本或设定转为带来源定位的剧情、角色、叙事节点、游戏需求和核心玩法循环。
- 接收已有 GDD、原型或 UE 工程；二进制 UE 资产会被标记为需要编辑器验证，不会按文件名臆测其语义。
- 支持叙事冒险、侦探推理、Kenshi 类沙盒，以及 2D、2.5D、3D 项目的条件化交付门槛。
- 在文案改动后追踪受影响的本地化、字幕、配音、过场、线索、关卡触发、测试和证据。
- 以供应商无关的方式规划并制作音乐、音效和配音。

## 前置条件

### 仅使用设计与工作流

以下是安装和运行核心插件所需的全部条件：

- Codex CLI，已验证范围为 `>=0.145.0,<0.146.0`
- Git
- Python 3 与 PyYAML

不需要安装 Unreal Engine、Blender、任何 MCP 服务或 MCP 源码仓库。没有编辑器的环境也可以完成剧本改编、GDD、系统规格、资产规格、工作拆解和静态验证。

### 需要实际开发 UE 项目

在需要编译、运行、打包或实机验证时，另行准备目标项目所需的 Unreal Engine。当前工具链锁定文件以 UE `5.7.4` 为验证目标；不同版本必须记录差异并重新验证，不能直接视为等价。

### 需要自动操作 Unreal 或 Blender

MCP 是可选的本地加速层，目前默认拒绝所有编辑器写操作。启用前必须同时具备：

- 对应的本地 Unreal/Blender 安装，以及匹配版本的 MCP 服务。
- 受你控制的 MCP 源码或维护分支，用于实现服务端令牌校验和动作白名单。仅在 Codex 客户端配置 `disabled_tools` 不是安全边界。
- 锁定的服务构件与 SHA-256；`plugins/ue5-codex-studio/templates/toolchain-lock.yaml` 中未填写的哈希必须先审查并补齐。
- 仅监听回环地址的服务、未提交到仓库的本地策略文件，以及通过环境变量注入的能力令牌。
- 缺失令牌、错误令牌、危险操作、绕过网关、schema 漂移、多实例、超时、保存/重载和运行时 canary 的实测证据。

当前锁定的候选上游为 `ChiR24/Unreal_mcp` 和 `dcc-mcp/dcc-mcp-blender`。插件不打包它们，也不会替你下载或启动服务。未完成上述条件时，保持 MCP 关闭，使用技能提供的人工/脚本回退路径。

详细的安全边界、构件配置和剩余实机验证项见 [Handoff](plugins/ue5-codex-studio/HANDOFF.md)。

## 安装

当前 GitHub 远程仍使用历史仓库名，以下命令可直接使用；完成仓库重命名后，将 URL 替换为 `codex-ue-game-studios` 即可。

```bash
git clone https://github.com/ccy20147-gif/Claude-Code-Game-Studios.git codex-ue-game-studios
cd codex-ue-game-studios
codex plugin marketplace add . --json
codex plugin add ue5-codex-studio@donchitos-game-studios --json
codex plugin list --json
```

最后一条命令应显示插件 `installed` 且 `enabled`。安装或更新后新开一个 Codex 对话线程，以加载最新 skill 内容。

## 从哪里开始

在 Codex 中按项目起点调用对应 skill：

| 起点 | 调用 | 结果 |
| --- | --- | --- |
| 还没有明确创意 | `$ue5-start-project` 或 `$ue5-conceive-game` | 有范围的概念与可验证体验契约 |
| 小说、剧本或设定 | `$ue5-adapt-story` | 可追溯的叙事注册表、角色/剧情节点、需求与核心玩法循环 |
| 已有 GDD、设计包或原型资料 | `$ue5-ingest-project` | 标准化 intake bundle 与缺口清单 |
| 已有 Unreal 工程 | `$ue5-ingest-project` | 只读工程盘点、能力状态与后续路线 |

`$ue5-start-project` 可根据起点自动路由。设计产出默认写入 `intake/`、`design/`、`docs/architecture/` 和 `production/`；这些目录是新工作流的项目空间，应保留在游戏项目中。

## 推荐流程

```text
启动/导入 -> 接受基线 -> 系统映射 -> 叙事、系统、关卡、艺术、音频、UX、架构设计
-> 工作计划 -> 原型或垂直切片 -> 制作 -> 测试与实机证据 -> 发布
```

剧本改编后的常用路径是：`$ue5-adapt-story`、`$ue5-accept-baseline`、`$ue5-map-systems`、`$ue5-design-narrative`、`$ue5-design-system`、`$ue5-plan-work`。设计变更使用 `$ue5-change-design`，避免文本、配音、线索和测试状态脱节。

## 验证插件

在仓库根目录运行：

```bash
python3 -m unittest discover -s plugins/ue5-codex-studio/tests -v
python3 plugins/ue5-codex-studio/scripts/validate_studio.py
python3 plugins/ue5-codex-studio/scripts/validate_mcp_security_policy.py \
  plugins/ue5-codex-studio/templates/mcp-security-policy.yaml
python3 "$CODEX_HOME/skills/.system/plugin-creator/scripts/validate_plugin.py" \
  plugins/ue5-codex-studio
git diff --check
```

这些检查验证插件结构、工作流契约和默认拒绝的 MCP 策略；它们不能替代真实 UE/Blender 环境中的保存、重载和运行时 canary。

## 目录说明

```text
.agents/plugins/marketplace.json    仓库内 Codex marketplace 定义
plugins/ue5-codex-studio/           插件、skills、契约、脚本和测试
design/                             新插件的游戏设计产出
docs/architecture/                  新插件的架构决策与架构产出
production/                         工作项、证据、构建与发布产出
.claude/                            原 Claude Code 模板的历史参考，不是 Codex 运行时
```

旧 Claude 会话状态目录与旧技能测试框架已移除。`.claude/` 保留为来源和历史资料，不应再被视为本插件的可运行依赖。

## 许可证

[MIT](LICENSE)
