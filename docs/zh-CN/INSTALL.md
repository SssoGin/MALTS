# MALTS 安装说明

语言：[English](../INSTALL.md) | [简体中文](INSTALL.md)

MALTS 的安装方式是选择一个或多个 Agent 工具 adapter，并把经过审阅的 scaffold 文件复制到对应工具的配置目录。共享 skills 只在公开仓库根级 `skills/` 维护一份，安装时复制到目标工具的本地 `skills/` 目录。

## 推荐流程

第一步始终先 dry-run：

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
```

如果 Windows PowerShell 阻止脚本执行，可使用进程级执行策略覆盖：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
```

不提供 `-Apply` 时不会写入文件。确认计划后再应用：

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
```

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
- `runtime/EN/templates` 和 `runtime/EN/checklists` 继续作为模板和检查清单来源。
- 双语文档同步默认关闭。
- Codex 可安装 `AGENTS.md`；Claude Code 可安装 `CLAUDE.md`；OpenCode 可把 `AGENTS.example.md` 安装为 `AGENTS.md`，并安装 `opencode.json`。
- `-SkipInstructionTemplate` 只跳过工具指令模板，不跳过共享 skills。
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

## 手动安装

1. 阅读 `README.md` 或 `README.zh-CN.md`。
2. 选择目标工具 adapter。
3. 审阅 `adapters/` 下对应目录。
4. 只复制该工具需要的文件。
5. 把根级 `skills/` 复制到该工具本地 `skills/` 目录。
6. 保持 `runtime/EN/templates` 和 `runtime/EN/checklists` 可被 Agent 读取。
7. 运行 dry-run 或 lint 检查。

Agent-assisted 安装规则见 [Agent 安装协议](AGENT_INSTALL.md)。
