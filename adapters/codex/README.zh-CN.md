# Codex Adapter

语言：[English](README.md) | [简体中文](README.zh-CN.md)

此 adapter 提供 Codex 使用 MALTS 的指令模板、Codex-native subagent scaffold 和 workflow prompts。

## 安装

先 dry-run：

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
```

审阅后应用：

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
```

## 内容

- `AGENTS.example.md`：Codex 指令起点模板。
- `config.toml`：安装到 Codex 配置 root 的 subagent scaffold 配置。
- `agents/*.toml`：Codex-native custom subagent roles。
- `workflows/*.md`：普通 workflow prompts，不是 Codex custom slash commands。
- 安装器生成的 `MALTS_BOOT.md`，指向共享 `MALTS_ROOT`。

安装会把 `AGENTS.example.md` 映射为 `AGENTS.md`，把 Codex scaffold 复制到 Codex 配置 root，安装一份共享 `MALTS_ROOT`，并生成 `MALTS_BOOT.md`。默认不会在工具目录下创建完整 `malts/` runtime 副本。

## Runtime 规则

默认读取英文 runtime 文档。中文 runtime 镜像只在中文用户可读输出或双语同步进入范围时使用。

中文用户场景的必需 MALTS 产物对：

```text
PROJECT_CONTROL.md / 项目控制.md
WORK_TASK_REPORT.md / 工作任务报告.md
```

中文用户可读 Markdown 应为有效 UTF-8。Windows 下优先 UTF-8 with BOM，除非本地项目约定冲突。

## 多 Agent 门禁

只有在 MALTS launch review 之后，并且用户明确回复 `确认运行` 后，才能使用 Codex subagents。模型策略、dispatch evidence 和 report recycling 必须记录到 `PROJECT_CONTROL.md`。

Codex 支持通过 `.codex/config.toml` 和 `.codex/agents/*.toml` 配置 project-scoped custom subagents。不要把 `workflows/*.md` 说成 Codex custom slash commands。

## Handoff

默认 Agent-facing handoff 文件：

```text
PROJECT_HANDOFF.md
```

可选中文镜像：

```text
项目交接.md
```
