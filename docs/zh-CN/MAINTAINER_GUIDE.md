# 维护者指南

语言：[English](../MAINTAINER_GUIDE.md) | [简体中文](MAINTAINER_GUIDE.md)

本文说明 public-safe release maintenance rules。

## 发布边界

允许进入公开包：

- public docs
- 根级 `skills/` 作为唯一公开 skill source
- English runtime templates 和 checklists
- optional adapters
- lightweight tools
- safe install scripts

不得同步：

- local release-control files
- local handoff outputs
- old private design notes
- trial-run logs
- real user tool configuration
- sessions
- memory dumps
- caches
- secrets
- machine-specific paths
- local archives
- generated migration packages
- non-public companion project references
- 根级 `skills/` 之外的额外公开 skill tree

简短规则：local archives、generated migration packages 和 non-public companion project references 不进入公开包。

## 更新策略

Agent 默认应 dry-run：

```text
show planned changes first
do not write files
do not commit
do not push
```

只有用户明确确认后才更新文件。

## Skill Source Policy

MALTS public releases 维护一个 canonical skill source：

```text
skills/
```

安装脚本会把该目录分发到受支持 Agent 工具。Public skills 保持在这个根级目录中；adapter 目录只保存工具特定的指令模板、commands、agents 和配置。工具本地 skill 目录是安装目标，不是 release-package facts。

## 公开发布前

- 审阅 `README.md` 和 `README.zh-CN.md`。
- 审阅 `LICENSE`。
- 审阅 `CONTRIBUTING.md`。
- 运行敏感信息扫描。
- 仅在需要时添加 community files：
  - `CODE_OF_CONDUCT.md`
  - `.github/PULL_REQUEST_TEMPLATE.md`
  - `.github/ISSUE_TEMPLATE/`
- 明确确认 repository visibility change。
