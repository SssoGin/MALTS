# OpenCode Adapter

语言：[English](README.md) | [简体中文](README.zh-CN.md)

此 adapter 包含 MALTS 的 OpenCode scaffold 文件。

## 安装

先 dry-run：

```powershell
.\scripts\Install-MALTS.ps1 -Tool OpenCode
```

审阅后应用：

```powershell
.\scripts\Install-MALTS.ps1 -Tool OpenCode -Apply
```

## 内容

- `AGENTS.example.md`：安装为 `AGENTS.md`。
- `opencode.json`
- `.opencode/agents/`
- 安装器生成的 `MALTS_BOOT.md`，指向共享 `MALTS_ROOT`。

安装会复制 OpenCode scaffold，安装一份共享 `MALTS_ROOT`，并生成 `MALTS_BOOT.md`。默认不会在工具目录下创建完整 `malts/` runtime 副本。

## Runtime 规则

默认读取英文 runtime 文档。中文 runtime 镜像只在中文用户可读输出或双语同步进入范围时使用。

中文用户场景的必需 MALTS 产物对：

```text
PROJECT_CONTROL.md / 项目控制.md
WORK_TASK_REPORT.md / 工作任务报告.md
```

中文用户可读 Markdown 应为有效 UTF-8。Windows 下优先 UTF-8 with BOM，除非本地项目约定冲突。

## 多 Agent 门禁

只有在 MALTS launch review 之后，并且用户明确回复 `确认运行` 后，才能使用 OpenCode agents。模型策略、dispatch evidence 和 report recycling 必须记录到 `PROJECT_CONTROL.md`。

## Handoff

默认 Agent-facing handoff：

```text
PROJECT_HANDOFF.md
```
