# MALTS 快速开始

本指南带领新用户从已验证的公开仓库进入第一个受 MALTS 控制的任务。

## 1. 先理解工作模型

MALTS 不是后台自治服务。它由 Skill、模板、合同、生命周期控制和 Agent 指令组成，用于让长期工作具备明确边界和可恢复状态。

主 Agent 对结果保持责任。子 Agent 是可选的，且只有用户确认完整启动审阅后才能真实派发。

## 2. 选择安装来源

公开仓库是正常安装来源。Agent 读取仓库、验证 `MALTS_RELEASE.json` 与 `VERSION`，然后只创建审阅计划。除非用户明确要求可选离线归档，否则不会下载 Release 资产。

可选 `MALTS-<version>.zip` 仅用于固定离线副本，或无法获得已验证仓库来源时。这个单一 ZIP 包含不可变 release package 及其包级验证材料。

## 3. 验证仓库来源

在仓库根目录确认 `MALTS_RELEASE.json` 中的 `version` 与 `VERSION` 一致。若 Git 元数据存在，还应确认当前 tag 与身份文件中的 `release_tag` 一致。

```powershell
Get-Content .\VERSION
Get-Content .\MALTS_RELEASE.json
git describe --exact-match --tags HEAD
```

没有 Git 检出不会阻止仓库安装；身份文件仍会绑定精确的用户源码树。

## 4. 创建安装计划

```powershell
.\scripts\Install-MALTS.ps1 `
  -RepositoryRoot (Get-Location).Path `
  -UseDefaultRoots `
  -Tool Codex
```

该命令会写入新计划并显示路径和精确 SHA-256；此时尚未安装 MALTS。

显式根目录用法见[安装](INSTALL.md)。让 Agent 协助审阅时见[Agent 协助安装](AGENT_INSTALL.md)。

## 5. 审阅并执行

检查计划中的选定工具根目录、用户修改分类、清理、回滚和后置验证动作。只执行审阅步骤输出的精确计划哈希。

## 6. 启动一个项目

安装后，让 Agent 使用已安装的 MALTS 入口：

| 需求 | 入口 |
|---|---|
| 普通项目控制 | `malts-project-init` |
| 带首个 Phase 的完整长期项目工作区 | `malts-long-project-workspace-init` |
| 实现前澄清 | `malts-grill-me-preflight` |
| 受控多 Agent 启动审阅 | `malts-multi-agent-long-task-scheduling` |
| 可恢复交接 | `malts-session-handoff` |

`malts-long-project-workspace-init` 与普通项目初始化刻意不同：全新长期项目工作区会一起创建根控制文件和首个活动 Phase。Session 仍需显式开启，不会由初始化隐式创建。

## 下一步阅读

- [安装](INSTALL.md)
- [更新](UPDATE.md)
- [使用](USAGE.md)
- [生命周期](LIFECYCLE.md)
- [发布产物](RELEASE_ARTIFACT.md)
