# MALTS 快速开始

本指南带领新用户从已验证的仓库来源进入第一个受 MALTS 控制的任务。

## 1. 先理解工作模型

MALTS 不是后台自治服务。它由 Skill、模板、合同、生命周期控制和 Agent 指令组成，用于让长期工作具备明确边界和可恢复状态。

主 Agent 对结果保持责任。子 Agent 是可选的，且只有用户确认完整启动审阅后才能真实派发。

## 1.1 区分初始化与日常进入

`malts-project-init` 用于显式轻量初始化/指令修复；`malts-long-project-workspace-init` 用于首次长工作区初始化、结构恢复、显式迁移或重大 lifecycle/profile 变化。不要为每个普通任务重新执行完整 initializer。

已有长工作区先运行：

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py workspace-entry --workspace <WORKSPACE> --task-class LOW_RISK
```

只读取返回的 current-set 路径。只读任务用 `READ_ONLY`，已有/新写入范围用 `WRITE_EXISTING_SCOPE` 或 `NEW_WRITE_SCOPE`，安全敏感工作用 `HIGH_RISK`，窗口/上下文切换后用 `CONTEXT_RECOVERY`。只有 decision 要求时才升级到 boundary review、Plan Recheck、validation 或 cold recovery。重复、无变化的 entry 零写入、不加载历史，也不创建 Phase、Session、Agent、Artifact 或 coordination state。

全新长工作区默认使用 CURRENT contract `single_phase`。只有确实需要多个受资源治理的 `OPEN` Phase 时，才通过显式审阅的初始化/迁移启用 `resource_admission`；旧工作区在显式迁移前保持原 schema/profile。

## 2. 选择安装来源

仓库是正常安装来源。Agent 读取仓库、验证 `MALTS_RELEASE.json` 与 `VERSION`，然后只创建审阅计划。除非用户明确要求可选离线归档，否则不会下载 Release 资产。

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

## 7. 显式治理长项目

初始化后，普通工作保持在 active Phase boundary 内。范围可能变化时运行只读 `phase-boundary-review`；需要变化时使用显式 pause/resume 或 persisted hash-bound transition，不要静默改写 Phase goal。

Artifact lifecycle 在真实需求出现前保持 `NOT_ENROLLED`。先运行只读 `artifact audit`。Enrollment 与每个 mutation 都是独立的 dry-run/apply operation；不会创建 Session、移动/删除 payload、调用 VCS 或扫描整个 workspace。

有意义的 control 变更后运行 `validate` 与 `recover`。S3/S4 工作存在 active plan 时，在 write-scope、recovery、failure/rollback、verifier、final-delivery 边界运行匹配的只读 Plan Recheck trigger。

全新 long-project workspace 使用 CURRENT，默认 `single_phase`。受支持的旧 workspace 与 Result 布局保持可读，绝不静默重写。若 `validate` 报告需要重整，先审阅一次直接的 `reorganize-workspace` 或 `reorganize-result-contract` dry run，绑定所有报告的 hash/review/authorization precondition，复用同一固定 timestamp，并且只在当前 workspace authorization 内 apply。用户流程不暴露中间布局或降级链。

Current recovery authority 固定为：active Session checkpoint；否则 primary active Phase recovery；否则显式绑定的 terminal Phase；否则 Project recovery。历史 Session 不会仅因时间最新而被选择。Incomplete workspace/coordination transaction 会保留 lock/journal evidence，直到 exact-journal-hash `recover-workspace-transaction` 成功。

## 下一步阅读

- [安装](INSTALL.md)
- [更新](UPDATE.md)
- [使用](USAGE.md)
- [生命周期](LIFECYCLE.md)
- [发布产物](RELEASE_ARTIFACT.md)
