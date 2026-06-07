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
5. 检查目标配置目录。
6. 展示计划写入文件和潜在冲突。
7. 默认 dry-run。
8. 未经明确确认，不覆盖已有文件。
9. 不读取或复制 secrets、sessions、memory dumps 或 private local state。
10. 询问是否启用双语文档同步；默认关闭。
11. 安装后运行验证。
12. 准确报告实际改动。

## 共享 Skills

MALTS 只有一个公开 canonical skill source：

```text
skills/
```

Agent-assisted 安装会把它复制到所选工具本地目录：

```text
Codex      -> <target>\skills\
ClaudeCode -> <target>\skills\
OpenCode   -> <target>\skills\
```

Adapter 目录只提供工具特定的指令模板、commands、agents 和配置；不定义额外公开 skill 来源。

## 双语文档

如果用户启用双语文档同步，Agent 应遵循 [双语文档规则](BILINGUAL_DOCS.md)。中文文档是用户-facing 参考，不是默认 runtime context。
