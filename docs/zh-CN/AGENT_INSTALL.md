# Agent-Assisted 安装协议

语言：[English](../AGENT_INSTALL.md) | [简体中文](AGENT_INSTALL.md)

当 Agent 代用户安装 MALTS 时，必须先询问目标工具：

```text
Codex
Claude Code
OpenCode
AllIncluded
```

除非用户选择 `AllIncluded`，Agent 不得安装全部 adapters。

## 必需流程

1. 读取 `README.md`、`docs/INSTALL.md` 和本文。
2. 询问目标工具。
3. 说明根级 `skills/` 是共享支持文件；`AGENTS.md`、`CLAUDE.md` 等工具指令模板是可选增强项。
4. 询问是否安装或合并指令模板。
5. 说明 MALTS runtime root 和 boot pointer 是新机器正常安装的必需链路。除非用户已有另一条经过审阅的 `MALTS_ROOT` 发现路径，否则安装计划应包含 `<target>\malts\` 和 `<target>\MALTS_BOOT.md`。
6. 检查目标配置目录。
7. 展示计划写入文件和潜在冲突。
8. 默认 dry-run。
9. 未经明确确认，不覆盖已有文件。
10. 不读取或复制 secrets、sessions、memory dumps 或 user-specific generated state。
11. 询问是否启用双语文档同步；公开 docs 默认关闭，但中文用户可读输出进入范围时，双语运行产物对是必需的。
12. 安装后运行验证。
13. 准确报告实际改动。

## 共享 Skills

MALTS 只有一个公开 canonical skill source：

```text
skills/
```

Agent-assisted 安装会把它复制到所选目标工具目录：

```text
Codex      -> <target>\skills\
ClaudeCode -> <target>\skills\
OpenCode   -> <target>\skills\
```

Adapter 目录只提供工具特定的指令模板、commands、agents 和配置；不定义额外公开 skill 来源。

## Runtime 发现

项目初始化必须能找到 MALTS runtime root。因此正常安装应包含：

```text
<target>\malts\
<target>\MALTS_BOOT.md
```

`MALTS_BOOT.md` 记录已安装的 `MALTS_ROOT`。Agent 必须验证该 root 包含：

```text
README.md
skills/
runtime/EN/templates/
runtime/EN/checklists/
```

## 双语文档

如果用户启用双语文档同步，Agent 应遵循 [双语文档规则](BILINGUAL_DOCS.md)。中文文档是用户-facing 参考，不是默认 runtime context。当前用户或项目以中文运行时，`PROJECT_CONTROL.md` / `项目控制.md` 和 `WORK_TASK_REPORT.md` / `工作任务报告.md` 是规范产物对，不是可选润色。
