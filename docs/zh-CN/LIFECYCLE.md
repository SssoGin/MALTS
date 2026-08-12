# MALTS 生命周期

生命周期引擎把已验证的 MALTS 来源转换为不可变安装版本。一个本地 registry 标识活动版本；每个选定 Agent 工具只接收自己的投影和 boot pointer。

## 核心不变量

- 版本来自一个已验证仓库来源，或一个明确验证后解出的 release package。
- 激活后安装 payload 字节保持不可变。
- 版本来源信息只保存来源类型和哈希绑定身份；绝不保存 package、仓库或机器路径。
- 安装或更新成功后恰好有一个活动版本。
- 计划会被持久化、可审阅，并绑定精确 SHA-256。
- 执行只接受精确已审阅计划和已观察到的前置条件。
- 未被选定的工具根目录不会被修改。
- 未知或用户拥有的文件会保留或阻塞，不会被静默移除。

## 来源模式

| 来源 | 正常用途 | 验证 |
|---|---|---|
| 仓库 | 默认安装和更新路径 | `MALTS_RELEASE.json`、`VERSION`、精确源码树清单、必需用户入口和安全仓库拓扑。 |
| 已解出的 release package | 明确的离线/固定归档路径 | 闭合 `release_manifest.json`、release inventory、内部 lifecycle artifact 和 package identity。 |

可选 ZIP 只是归档交付方式，不是第三种 lifecycle 来源。bootstrap 验证会把它解出为第二种来源模式。

## 语义化版本身份与迁移

稳定版本使用 `malts-v<version>`，隔离预览版本使用
`malts-v<version>-preview.<positive-sequence>`。release builder 与 lifecycle engine
调用同一身份函数。已安装稳定身份精确一致时为显式 `NO_OP`；同一 ID 对应不同内容，
或存在未绑定同名目录时，会在创建 transaction 或 lock 状态前失败。

`malts-1.0.0-<hash>` 等 legacy ID 只作为已识别迁移输入。先 stage 并 prevalidate
新的语义版本，再以 transaction 切换 registry、active pointer、global boot 和已选工具投影。
只有 post-validation 证明旧权威引用为零后才移除旧版本。任一状态发生 crash 时，恢复到唯一
committed 或 rolled-back 终态。

## 操作

| 操作 | 用途 | 所需来源 |
|---|---|---|
| `install` | 创建并激活首个版本。 | 仓库或已解出 package |
| `update` | 暂存并激活更新的已验证版本。 | 仓库或已解出 package |
| `repair` | 用活动版本协调选定投影。 | 仓库或已解出 package |
| `uninstall` | 在已审阅计划下移除 MALTS 拥有投影和 registry 状态。 | 仅已有安装状态 |
| `recover` | 继续或回滚中断的 transaction。 | 已有 lifecycle 状态 |

## 先审阅计划

用户生命周期脚本先创建计划。计划包含来源身份、选定根目录、目标版本身份、写入、移除、用户修改分类、旧版迁移或残留动作、回滚和后置验证。

执行需要相同计划文件及其精确 `plan_hash`。来源或环境漂移会在变更前失败。

## 预览验证

影响 runtime 的新版本必须在显式绝对 preview root 中验证，之后才可考虑真实安装。该 root 不能是磁盘根、reparse point、source/runtime root，也不能与任何 protected root 互为祖先或后代。Preview lifecycle、registry、global boot，以及每个已选工具的 config、home、cache 和 temp 根都必须留在该边界下。

先创建零写入 preview plan，审阅后再只持久化并执行其精确 hash：

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command PreviewPlan `
  -PreviewRoot <ABSOLUTE_PREVIEW_ROOT> `
  -ReleaseRoot <PREVIEW_RELEASE_ROOT> `
  -ProtectedRoot <REAL_LIFECYCLE_ROOT> `
  -Tool codex,claude-code,opencode `
  -OutPath <NEW_PREVIEW_PLAN_PATH> `
  -Apply
```

全新 Codex、Claude Code 和 OpenCode 进程必须通过 process-local 隔离根发现预览版本。无法证明隔离时，操作被阻断，绝不回退真实根。未用真实工具集成验证的预览会被如实记录，不能视为完整合格。

## Doctor 与 Repair 信任

`Doctor` 返回闭合 `lifecycle-doctor-report`，包含精确 locator、expected/observed 证据、严重度、core trust 与建议命令；它始终只读。派生 boot 或投影漂移可由本地一致活动版本限定；payload、manifest、registry 或 pointer 被篡改时，必须提供与 installed binding 精确一致的外部已验证来源。

`DoctorRepairPlan` 是独立审阅步骤。来自本地活动版本的建议不可执行。精确已验证来源可以生成普通 hash-bound repair plan，但仍须使用 `Execute -Apply` 和已审阅 plan hash 执行，并保留正常 snapshot、rollback 与 post-validation 行为。

## 版本与 Boot Pointer

lifecycle root 包含不可变版本目录、registry 状态、transaction journal、审计证据和残留记录。每个选定工具接收一个小型投影以及 `MALTS_BOOT.md`，它在使用时解析活动版本。

不要把物理版本路径复制进项目控制文件。需要当前 runtime 信息时，先解析 boot pointer，再读取活动 `VERSION`。

公开 Python CLI entrypoint 会在导入 MALTS 本地模块前抑制 bytecode 写入，因此普通只读启动也不会在 immutable installed generation 中创建 `__pycache__` 或 `.pyc`。示例仍使用 `python -B` 作为纵深防护；installed-generation purity 与 Doctor 检查会对任何生成缓存残留 fail closed。

如果旧的长项目工作区在生成的 `PROJECT_CONTROL.md` 中保留了物理版本路径，先检查迁移计划：

```powershell
python -B .\tools\long_workspace.py refresh-runtime-references --workspace <PROJECT_WORKSPACE>
```

仅在审阅返回计划后再应用：

```powershell
python -B .\tools\long_workspace.py refresh-runtime-references --workspace <PROJECT_WORKSPACE> --apply
```

该命令只改写生成的版本来源元数据行。静态版本引用会使 `validate` 以
`WS_STALE_RUNTIME_REFERENCE` 失败；必须刷新或人工审阅，不能被静默忽略，也不能在该生成行之外被静默改写。

旧版本可能保留 legacy 绝对来源 locator，仅用于让已验证更新替换它。它仍可被读取以完成迁移，但在更新生成不含路径的当前记录前，安装纯净度检查会关闭式失败。

## 有界 Audit 保留

Lifecycle audit state 使用闭合 schema 与固定 ownership 规则，保留：

- 一份 current active-binding receipt；uninstall 后不保留 current binding
- 最近 20 份 compact success-operation receipt
- 最近 10 组完整 failure/recovery plan-and-journal bundle
- 最近 12 个日历月各一份 compact summary

未完成且可恢复的 transaction 永不 prune。新 record 会先安全写入，再按精确名称和 hash-bound 清单 prune。未知名称、hash drift、reparse point、被禁止的版本/package/ZIP/payload 副本或 cleanup failure 都会被保留，并阻断 stable 或 zero-residue 结果。Audit write 与 prune recovery 保持幂等。

对于早于该保留契约的唯一旧 Audit 布局，迁移只识别精确闭合的 v1 envelope、plan、context 和 terminal journal 形状。它会验证原始 plan/context hash 以及 operation / artifact / journal binding，然后在 `state/audit/legacy-pre-retention/<operation_id>/` 保留源文件的原始字节；绝不伪造较新的版本身份。缺字段、多字段、hash drift、reparse point、不能匹配的 archive 内容和任何未识别文件都继续阻断。

可识别的标准 legacy plan/journal pair 会使用其 `release_identity` 已绑定的版本身份压缩为当前 receipt；缺少派生 plan 字段绝不被当作新的身份。若普通失败发生在 `COMMIT` 之后，journaled snapshot rollback 仍是显式恢复路径。恢复后只要 registry 回到 stable active，严格 audit 校验前也会先补齐对应的 current binding receipt。

## 恢复与残留

中断操作会写入 journal。恢复会检查 journal、registry、活动 pointer、版本、选定投影和受管残留，之后才会宣称状态稳定。

引擎区分 MALTS 拥有路径与用户拥有或不确定路径。它只会在已审阅计划下移除有确凿归属证据的 MALTS 残留；不明确路径会保留或等待明确用户决定。

## Workspace Phase And Artifact Lifecycle

### Phase boundary 与状态

每个 current Phase 都记录 milestone、in-scope/out-of-scope、exit criteria、carry-over policy 和 boundary-review triggers。`phase-boundary-review` 只读，只对候选 goal/touch set 分类，不授予写权限。其 compatibility `status` 与 `operation_status` 只描述 command execution；必须分别读取 `review_outcome`、`candidate_mapping`、`recommendation` 与 `persisted`。只有 `record-phase-boundary-review` 会持久化 structured review，该记录并不是后续工作授权。`PAUSED` 保留 ownership 与 recovery evidence；`resume-phase` 需要新的 boundary、plan、精确 hash 与 authorization reference。跨 Phase 工作先生成 persisted `plan-phase-transition`，再执行 hash-bound `apply-phase-transition`；旧 Phase 进入终态 `SUPERSEDED`，新 Phase 成为唯一 `ACTIVE` owner，carry-over provenance 在两端双向记录。

### Cross-control consistency 与 recovery authority

全新 long-project workspace 使用精确 schema v3。精确 schema v1/v2 input 作为可读 compatibility contract 保留，`validate`、`recover`、maintenance、installation update 或 active-generation switch 绝不会静默重写。Active v2 workspace 缺少 required current projection 时会被分类为需要显式迁移，而不是猜测修复。

Active `PHASE_CONTROL.md` 拥有 Boundary Review 与 Phase recovery record；active Session 拥有 checkpoint。schema v3 要求 current `WORK_TASK_REPORT.md` binding。`PROJECT_HANDOFF.md` 仍然可选，但存在时必须绑定同一组精确 Phase-control、normalized boundary/review 与 normalized recovery hashes。Runtime JSON 是 typed non-canonical projection。Validation 分层报告 structural、binding、deterministic-consistency 与 advisory-semantic finding；deterministic drift 会阻断 cold recovery 和普通 lifecycle mutation。

Migration、review recording 与 reconciliation 分别使用 `migrate-consistency-records`、`record-phase-boundary-review`、`reconcile-consistency-records`。三者均 dry-run-first，并绑定显式 authority、operation ID 与精确 expected hash。Workspace-control 写入使用独立 `runtime/workspace_transaction.lock.json`、`runtime/workspace_transactions/` 和 `WS_TRANSACTION_*` domain。Incomplete journal 会保留到 exact-hash `recover-workspace-transaction` 成功；失败 recovery 继续保留证据。Artifact transaction path 与 `ART_TRANSACTION_*` code 不变。

Canonical recovery selection 固定为 active Session checkpoint；否则 active Phase recovery；否则显式绑定的 terminal Phase；否则 Project recovery。禁止按 timestamp 或 registry order 选择最新历史 Session。

### Artifact enrollment 与 ownership

Artifact lifecycle 是可选能力。Project 只拥有 `NOT_ENROLLED`/`ENROLLED` 状态以及紧凑 Shared/Archive pointer。Phase 或显式有界 Session 拥有本地 Artifact rows；Shared 拥有 current reusable authority，Archive 拥有 cold/superseded history。Runtime snapshot 只能缓存 locator 与 count，绝不能覆盖 canonical Markdown。

`artifact audit` 只读，范围只包含当前已声明 control。`artifact enrollment-preview` 提出精确 enrollment/index 变更；只有携带唯一 operation ID 且显式 `--apply` 的 `artifact enrollment-apply` 才会 enrollment workspace。Legacy directory 只是 observation，不是 authority；已声明 index 缺失时 fail closed，绝不隐式重建。

### Mutation、close 与 recovery

Register、promote、supersede、reconcile 默认 dry-run。Apply 时持有唯一 workspace lock、写入 persisted hash-bound journal、重读 full-state precondition、stage 精确 replacement，并且要么提交全部已声明 control，要么恢复原始精确 bytes。相同重试是 no-op success；竞争 writer、stale lock/journal、bytes 变化、duplicate authority、cycle 或 incomplete reference 均安全失败。

Artifact mutation 绝不移动/删除 payload 或调用 VCS，也绝不创建 Session。含 `UNRESOLVED` row 的 enrolled Phase/Session 无法关闭。`recover` 报告精确 stale transaction 人工审阅动作，只沿当前 recovery chain 所需的 owner/Shared/Archive pointer 读取，不递归扫描大型 payload tree。

### Compatibility 与 non-goals

Schema-v1 与 schema-v2 workspace 保持可读。全新工作区使用 schema v3；migration 必须显式执行，安全 duplicate-marker cleanup 仅限空重复 section，non-empty duplicate 或 ambiguous legacy review semantics 必须 fail closed 并人工 reconciliation。Workspace consistency 不增加自动 update check、background watcher、project-wide payload hashing、目录整理、Unity 默认规则或远端 publication。G4 仍需真实 Codex、Claude Code、OpenCode invocation；component/projection test 不能冒充 G4。

## 普通启动 Discovery

每个工具从自身相邻的 `MALTS_BOOT.md` 启动，其 schema 只允许一条绝对 `MALTS_ROOT:` 行。MALTS v1.1.1 起不再使用或创建机器全局 `GLOBAL_BOOT.md`。只读 `discover` 命令验证 tool boot、stable registry 状态、唯一 active record、精确 `active_generation.json`、active `VERSION` 与版本身份。普通启动不计算完整树 hash，也不写入。权威面缺失、畸形、陈旧或冲突时全部 fail closed。

另见[安装](INSTALL.md)、[更新](UPDATE.md)和[安全](SECURITY.md)。
