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

如果旧的长项目工作区在生成的 `PROJECT_CONTROL.md` 中保留了物理版本路径，先检查迁移计划：

```powershell
python .\tools\long_workspace.py refresh-runtime-references --workspace <PROJECT_WORKSPACE>
```

仅在审阅返回计划后再应用：

```powershell
python .\tools\long_workspace.py refresh-runtime-references --workspace <PROJECT_WORKSPACE> --apply
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

## 普通启动 Discovery

每个工具从自身相邻的 `MALTS_BOOT.md` 启动，其 schema 只允许一条绝对 `MALTS_ROOT:` 行。`GLOBAL_BOOT.md` 使用独立 fenced-block schema，仅作为可选机器全局 / 恢复交叉核对。只读 `discover` 命令验证 tool boot、stable registry 状态、唯一 active record、精确 `active_generation.json`、active `VERSION`、版本身份与可选 global boot。普通启动不计算完整树 hash，也不写入。权威面缺失、畸形、陈旧或冲突时全部 fail closed。

另见[安装](INSTALL.md)、[更新](UPDATE.md)和[安全](SECURITY.md)。
