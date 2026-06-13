# MALTS 安装说明

语言：[English](../INSTALL.md) | [简体中文](INSTALL.md)

MALTS 的安装方式是选择一个或多个 Agent 工具 adapter，并把经过审阅的 scaffold 文件复制到对应工具的配置目录。共享 skills 只在公开仓库根级 `skills/` 维护一份，安装时复制到目标工具的本地 `skills/` 目录。

安装器还必须让新机器上的 MALTS runtime 可发现。它会规划安装到目标工具目录的 `malts/` runtime 副本，并生成 `MALTS_BOOT.md` 指针，使项目初始化能找到 `README.md`、`skills/`、`runtime/EN/templates` 和 `runtime/EN/checklists`。

## 推荐流程

第一步始终先 dry-run：

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
```

如果 Windows PowerShell 阻止脚本执行，可使用进程级执行策略覆盖：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
```

Windows 下需要双击审阅时，使用会保留窗口的 wrapper：

```powershell
.\scripts\Install-MALTS.review.cmd -Tool Codex
```

不提供 `-Apply` 时不会写入文件。确认计划后再应用：

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
```

## 安装 Smoke Test

维护者可以在不触碰正常工具目录的情况下验证真实临时安装：

```powershell
.\scripts\Test-MALTSInstall.ps1 -Tool AllIncluded
```

该 smoke test 会创建临时安装目标，对临时目标运行 `Install-MALTS.ps1 -Apply -Overwrite`，验证生成的 `MALTS_BOOT.md`、runtime templates、checklists、工具 scaffold 和 `malts/tools/agent_system_lint.py`，然后删除临时目录；提供 `-KeepTemp` 时保留临时目录。

指令模板是可选增强项。它们帮助工具记住 MALTS 的任务模式、Grill-Me Preflight、项目控制、交接和验证规则。应用前应先审阅并与已有用户或项目指令合并。

跳过指令模板但安装支持文件和共享 skills：

```powershell
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode -SkipInstructionTemplate
```

## 支持工具

```text
Codex
ClaudeCode
OpenCode
AllIncluded
```

## 默认行为

- 根级 `skills/` 的共享 skills 默认纳入安装计划。
- 默认在 `<target>\malts\` 下安装 MALTS runtime 副本。
- 默认生成 `MALTS_BOOT.md`，指向已安装的 runtime root。
- `runtime/EN` 和 `runtime/CH` 作为运行模板和检查清单来源。
- 双语文档同步默认关闭。
- Codex 可安装 `AGENTS.md` 和 Codex-native `.codex` subagent scaffold；Claude Code 可安装 `CLAUDE.md` 和 `.claude` agents/commands；OpenCode 可把 `AGENTS.example.md` 安装为 `AGENTS.md`，并安装 `opencode.json` 和 `.opencode` agents。
- `-SkipInstructionTemplate` 只跳过工具指令模板，不跳过共享 skills。
- 只有在已有经过审阅的 MALTS runtime root 和 boot pointer 时，才使用 `-SkipRuntime`。
- 只有在工具已有其他经过审阅的 `MALTS_ROOT` 解析方式时，才使用 `-SkipBoot`。
- 除非用户明确允许，安装脚本不会覆盖已有文件。
- 安装脚本会先打印计划。

## Skill 安装路径

公开仓库只有一个 canonical skill source：

```text
skills/
```

安装脚本会复制到目标工具发现目录：

```text
Codex      -> <target>\skills\
ClaudeCode -> <target>\skills\
OpenCode   -> <target>\skills\
```

Adapter 目录只提供工具特定的指令模板、commands、agents 和配置。共享 MALTS skills 始终从仓库根级 `skills/` 安装。

安装后的 runtime root：

```text
<target>\malts\
```

生成的 boot pointer：

```text
<target>\MALTS_BOOT.md
```

Agent 运行 MALTS project initialization 前，必须从 `MALTS_BOOT.md` 或其他配置好的 global boot 文件解析 `MALTS_ROOT`。

## 手动安装

1. 阅读 `README.md` 或 `README.zh-CN.md`。
2. 选择目标工具 adapter。
3. 审阅 `adapters/` 下对应目录。
4. 只复制该工具需要的文件。
5. 把根级 `skills/` 复制到该工具目标 `skills/` 目录。
6. 保持 `runtime/EN/templates`、`runtime/EN/checklists` 和生成的 `MALTS_BOOT.md` 可被 Agent 读取。
7. 运行 dry-run 或 lint 检查。

Agent-assisted 安装规则见 [Agent 安装协议](AGENT_INSTALL.md)。
