# 维护者指南

语言：[English](../MAINTAINER_GUIDE.md) | [简体中文](MAINTAINER_GUIDE.md)

本文说明 MALTS 的 public-safe maintenance rules，面向需要在不依赖用户特定生成状态的情况下维护公开仓库的人类维护者和 coding agents。

## 维护目标

- 保持 `main` public-safe 且可安装。
- 保持英文 runtime docs 作为事实源。
- 当公开文档变化时，同步简体中文公开文档。
- 当 adapter 行为变化时，同步 Codex、Claude Code 和 OpenCode adapters。
- 优先 review-first change：在 apply 或 release 前运行 dry-run 和检查。

## 发布边界

允许进入公开包：

- public docs
- 根级 `skills/` 作为唯一公开 skill 实现 source
- English runtime templates 和 checklists
- optional adapters
- lightweight tools
- safe install scripts

不得同步：

- release-control files
- handoff outputs
- project-specific design notes
- trial-run logs
- real user tool configuration
- sessions
- memory dumps
- caches
- secrets
- machine-specific paths
- user-specific archives
- generated migration packages
- unrelated project references
- 根级 `skills/` 之外的额外公开 skill tree

简短规则：user-specific archives、generated migration packages 和 unrelated project references 不进入公开包。

公开文档中使用占位符：

```text
<PROJECT_ROOT>
<MALTS_ROOT>
<USER_HOME>
<HANDOFF_ARCHIVE_ROOT>
```

已忽略路径中可能存在生成的维护状态。这些文件不是公开 release package 的一部分。

## 更新策略

Agent 默认应 dry-run：

```text
show planned changes first
do not write files
do not commit
do not push
```

只有用户明确确认后才更新文件。

## 常规更新流程

1. 用最小改动解决当前维护任务。
2. 将相关 public docs、templates、checklists 和 adapters 一起更新。
3. 运行下方本地检查。
4. 使用聚焦的提交信息提交改动。
5. push 到 GitHub，并等待 CI 通过。
6. 只有当已检查的 commit 是目标公开快照时，才创建 release。

## 本地检查

push 公开改动前运行：

```powershell
$version = (Get-Content -Raw VERSION).Trim()
python tools\agent_system_lint.py check-semantic-freshness --malts-root . --version $version
python tools\agent_system_lint.py check-doc-sync --output-root . --manifest tools\doc_pairs.json --require-ch
python tools\agent_system_lint.py check-doc-sync --output-root .\runtime --require-ch
python tools\agent_system_lint.py check-adapter-parity --malts-root .
python tools\agent_system_lint.py check-encoding --malts-root . --require-ch-bom
python tools\agent_system_lint.py check-public-safety --malts-root .
```

对受支持工具运行安装预览：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool ClaudeCode
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool OpenCode
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool AllIncluded
```

安装脚本默认是 dry-run。不要把 `-Apply` 作为 release 检查。

发布 installer 或 runtime 改动前，运行一次真实临时安装 smoke test：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-MALTSInstall.ps1 -Tool AllIncluded
```

该 smoke test 只写入受保护的临时目录，验证安装布局后会删除临时目录。

## Continuous Integration

仓库使用 GitHub Actions 在以下事件上运行 release hygiene checks：

- push 到 `main`
- 指向 `main` 的 pull request
- 已发布的 release
- 手动 workflow dispatch

CI 运行在 Windows 上，因为安装脚本基于 PowerShell，并且 Windows execution-policy 行为是受支持安装路径的一部分。

## Skill Source Policy

MALTS public releases 维护一个 canonical skill source：

```text
<MALTS_ROOT>\skills\
```

安装器创建或更新一份共享 `MALTS_ROOT`，并通过 `MALTS_BOOT.md` 让每个选中的工具指向该 root。工具配置目录是薄 adapter target：可以接收发现型 skill bridge，但不得接收完整 `malts\` runtime 副本或完整 skill 实现重复源。

Public skills 保持在共享 root 中；adapter 目录只保存工具特定的指令模板、commands、agents 和配置。目标工具目录是安装目标，不是 release-package facts。

三份公开指令示例都必须且只能包含一对匹配的 MALTS managed markers。发布 installer 变更前，必须验证追加、区块内更新、旧格式迁移、幂等、BOM/换行保留、`Skip` 和显式 `Replace` 行为。

## 版本规则

使用 semantic versioning：

- Patch releases，例如 `v0.1.1`：文档修复、小型脚本修复或兼容性修复。
- Minor releases，例如 `v0.2.0`：新增 adapters、新 skills、新公开流程或行为补充。
- Major releases，例如 `v1.0.0`：项目成熟后形成稳定公开契约，或包含有意的 breaking changes。

创建新 release 前：

1. 更新 `VERSION`。
2. 更新 `CHANGELOG.md`。
3. 运行本地检查。
4. push 并确认 CI 通过。
5. 从已检查的 commit 创建 GitHub Release。

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

## 维护者 Agent Handoff

当未来 Agent 需要继续维护 MALTS 时，应在公开发布包之外提供 continuation context。handoff 应包含：

- generated time
- repository root
- source context reviewed
- completed work
- pending work
- known risks
- verification already performed
- next recommended steps

真实 handoff 文件应放在 release artifacts 之外。公开示例只能使用占位符内容。
