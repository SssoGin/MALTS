# Claude Code Adapter

语言：[English](README.md) | [简体中文](README.zh-CN.md)

此 adapter 包含 MALTS 的 Claude Code scaffold 文件。

## 安装

先 dry-run：

```powershell
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode
```

审阅后应用：

```powershell
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode -Apply
```

## 内容

- `CLAUDE.example.md`：Claude Code 指令起点模板，包含回答质量规则。
- `.claude/agents/`：Claude Code agents。
- `.claude/commands/`：Claude Code commands。
- 安装器生成的 `MALTS_BOOT.md`，指向共享 `MALTS_ROOT`。
- `skills/<name>/SKILL.md`：路由到共享实现的轻量发现 bridge。

安装会把 `CLAUDE.example.md` 映射为 `CLAUDE.md`，安装 Claude Code scaffold，安装一份共享 `MALTS_ROOT`，生成 `MALTS_BOOT.md`，并安装发现 bridge。工具目录不会包含完整 runtime 或 skill 实现副本。

默认 `ManagedMerge` 只更新 `CLAUDE.md` 中带标记的 MALTS 指令区块，并保留区块外用户规则。需要完全不改时使用 `InstructionMode Skip`；整份 `Replace` 必须显式搭配 `Overwrite`。

## Runtime 规则

默认读取英文 runtime 文档。中文 runtime 镜像只在中文用户可读输出或双语同步进入范围时使用。

Canonical MALTS 产物：

```text
PROJECT_CONTROL.md
WORK_TASK_REPORT.md
PROJECT_HANDOFF.md
```

`项目控制.md`、`工作任务报告.md`、`项目交接.md` 等翻译镜像是可选项；只在用户明确要求或外部流程要求完整翻译镜像时生成。中文用户可读 Markdown 应为有效 UTF-8。Windows 下优先 UTF-8 with BOM，除非本地项目约定冲突。

## 多 Agent 门禁

只有在 MALTS launch review 之后，并且用户明确回复 `确认运行` 后，才能使用 Claude Code subagents。模型策略、dispatch evidence 和 report recycling 必须记录到 `PROJECT_CONTROL.md`。

## Handoff

默认 Agent-facing handoff：

```text
PROJECT_HANDOFF.md
```
