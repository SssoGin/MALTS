# 更新 MALTS

MALTS 默认从经过独立审阅的当前仓库 checkout 更新。更新器不会执行 Git 拉取、后台发现更新或下载 Release 归档。在任何安装状态变更前，它先创建只供审阅的计划。

安装更新不会重整项目 workspace 或 Result Contract。激活后，旧 workspace 仍保持既有兼容行为，直到单独审阅并显式 apply 一次 `reorganize-workspace` 或 `reorganize-result-contract` dry run。重整会绑定精确 source hash、review/authorization reference、同一固定 timestamp 与可恢复 journal；绝不在普通 `workspace-entry`、`validate`、`recover` 或 generation 切换中运行。

不要为了获得 CURRENT workspace contract 而原位修改 active generation。应修改并验证 maintenance source，再分别经过 candidate、activation、Git、tag 与公开 Release 门。默认 single-profile workspace 不需要 concurrency profile，也不产生 coordination state。

## 更新前

1. 完成或恢复所有未完成 lifecycle transaction。
2. 取得目标版本的当前仓库来源。
3. 验证 `MALTS_RELEASE.json`、`VERSION`，以及可用时的当前 Git tag。
4. 确认已有 lifecycle root 和每个已选工具根目录。
5. 需要时按工具自身正常流程备份用户拥有的配置。

不要从未验证文件夹更新。仓库身份不匹配、意外文件、缓存或 `.malts` 残留都会在计划阶段停止。

## 仓库更新审阅

在已审阅仓库来源中运行：

```powershell
.\scripts\Update-MALTS.ps1 `
  -RepositoryRoot (Get-Location).Path `
  -UseDefaultRoots `
  -Tool Codex
```

使用显式根目录：

```powershell
.\scripts\Update-MALTS.ps1 `
  -RepositoryRoot <REPOSITORY_ROOT> `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -Tool Codex `
  -ToolRootCodex <CODEX_ROOT> `
  -PlanPath <NEW_UPDATE_PLAN_PATH>
```

执行前审阅计划。它会显示活动与目标版本身份、选定投影、用户修改分类、迁移或清理动作、回滚动作和后置验证。

```powershell
.\scripts\Update-MALTS.ps1 `
  -Apply `
  -PlanPath <REVIEWED_UPDATE_PLAN_PATH> `
  -ExpectedPlanHash <REVIEWED_UPDATE_PLAN_SHA256>
```

## 版本迁移与冲突处理

稳定版本使用 `malts-v<version>`，隔离预览使用
`malts-v<version>-preview.<sequence>`。`malts-1.0.0-<hash>` 等已识别 legacy ID
只作为迁移输入；MALTS 不会原地改名，也不会把其物理路径当作当前 pointer。

更新会先 stage 并 prevalidate 目标，再把 registry、active pointer、各工具本地 Boot 与投影作为一个 transaction unit 切换。安装后的受管指令记录安装时生成的精确 `MALTS_BOOT_PATH`，不得相对于 `cwd` 或项目文件重新解释。只有 post-validation 证明所有权威引用都不再指向旧版本后，才会清理旧版本。相同版本且精确一致时为 no-op；相同版本内容冲突或未绑定同名目录会在写入前失败。进程中断通过 transaction journal 继续或回滚。

## 可选离线归档更新

当更新来源必须是固定离线归档时，先明确验证并解出单一 `MALTS-<version>.zip`。随后以 `-ReleaseRoot <EXTRACTED_RELEASE_ROOT>` 调用解出内容中的更新器。该归档是明确选择的来源，不是普通更新器的依赖。

## 用户修改与清理

MALTS 会在变更前分类已有投影文件：

| 类别 | 含义 | 默认结果 |
|---|---|---|
| U0 | 缺失或与 MALTS 拥有内容完全一致 | 按计划替换或移除。 |
| U1 | 可合并的受管指令块 | 合并受管区块。 |
| U2 | 具有确定性证据的合并 | 仅在记录验证后合并。 |
| U3 | 用户拥有或归属不明确的修改 | 停止并等待明确用户决定。 |
| U4 | 敏感或不安全冲突 | 关闭式失败。 |

已知旧布局只在归属证据充分时迁移。未知、用户拥有或不明确的文件会保留或阻塞更新，不会被静默删除。

已验证更新还会把旧版来源中的绝对路径记录替换为当前无路径记录。不要手动编辑已安装版本。

## Repair 前先诊断

尝试 repair 前，用 lifecycle root 和全部已选工具根运行 `Invoke-MALTSLifecycle.ps1 -Command Doctor`。Doctor 只读，并会区分派生 boot/投影漂移与无效 core payload、manifest、registry 或 pointer 状态。

core 状态本地一致时，`DoctorRepairPlan` 可从活动版本限定派生 repair 目标，但该建议本身不是可执行变更。只有与已安装绑定精确一致的已验证来源才能生成可持久化的 executable repair plan；随后必须审阅其 hash，并作为独立授权 transaction 执行。

## 更新 Workspace Control

更新 MALTS 会安装新 runtime behavior，但不会重写项目 controls。受支持的旧 long-project 布局保持可读；全新 workspace 使用 CURRENT，默认 `single_phase`；Artifact lifecycle 仍为 `NOT_ENROLLED`。Resource profile 与每项重整都保持显式 workspace operation。

先运行 `validate` 并保留精确 state hash/classification。若它报告受支持的旧布局，审阅一次 `reorganize-workspace` dry run，明确分类每个保留、移动、归档或派生 section，并直接以 CURRENT 为目标。只有当前 workspace authorization 覆盖时，才 apply 同一个 hash-bound plan。旧 parser 与 consistency repair 细节只在内部兼容层保留；validation/recovery 不会自动重整。

考虑 enrollment 前先运行 `artifact audit`。Legacy `shared/` 类目录只是 candidate observation，绝不会被静默接管。如果确实需要 enrollment，运行 `artifact enrollment-preview`，审阅精确 index path 与 finding，然后使用唯一 operation ID 和显式 `--apply` 运行 `artifact enrollment-apply`。

若重整后的 Boundary Review 仍 unresolved，只能通过携带精确 Phase SHA-256 的 `record-phase-boundary-review` 持久化 structured result；记录并不是后续 mutation authorization。Ambiguous non-empty duplicate marker 或 legacy prose semantics 必须 fail closed，不做推断。

Interrupted workspace/coordination authority write 使用共享 `runtime/workspace_transaction.lock.json` 与 `runtime/workspace_transactions/`，并与 Artifact transaction 分离。添加 `--apply` 前，用精确 journal SHA-256 审阅 `recover-workspace-transaction`；失败 recovery 保留 evidence。

任何 update path 都不会移动/删除 payload、调用 VCS、创建 Session、把最新历史 Session 选作 recovery authority，或启动自动/后台 workspace scan。已安装 MALTS generation 的回滚应通过 lifecycle plan 完成；绝不能把旧 template 复制覆盖 canonical workspace control。Workspace 重整中断时恢复原始字节，或使用显式 reconcile 证据。

## 恢复

更新中断时，先检查或恢复 lifecycle transaction，再创建新的计划。registry、journal、回滚和残留行为见[生命周期](LIFECYCLE.md)。

## 更新后 Discovery

更新成功后，对每个已选 tool root 运行只读发现命令。安装时生成的精确 `MALTS_BOOT_PATH` 必须全部解析到同一个新活动版本，并与 registry、active pointer、`VERSION` 一致；MALTS 的普通发现不使用机器全局 Boot。不得继续使用陈旧 tool boot 或猜测版本路径；repair 必须进入单独审阅的 lifecycle transaction。
