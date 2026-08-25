# 在项目中使用 MALTS

生命周期安装后，从工具的 MALTS boot pointer 开始工作。它会解析当前不可变 generation；不要手工把 runtime 文件复制到项目中。

## 进入已有工作区

普通任务不要重新运行 initializer。先分类任务并运行一次只读 entry：

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py workspace-entry --workspace <WORKSPACE> --task-class LOW_RISK
```

可用类别为 `READ_ONLY`、`LOW_RISK`、`WRITE_EXISTING_SCOPE`、`NEW_WRITE_SCOPE`、`HIGH_RISK`、`CONTEXT_RECOVERY`。只读取返回的 current-set 路径。新 scope/Phase 变化触发 boundary review 与 Plan Recheck；真实 canonical/transaction/Admission drift 触发 reconcile 或 recovery。普通 entry 不加载 report/handoff/history，也不写 maintenance view。

如果从未登记过 Phase，entry 返回 `INITIALIZATION_REQUIRED`；如果工作区已初始化但只剩 terminal Phase，则返回 `PHASE_REQUIRED`，要求显式打开新 Phase。两条路径都不会创建 Phase、Session、Agent 或 Artifact。

全新长工作区默认使用 CURRENT contract `single_phase`。要显式启用按资源治理的并行 Phase，应审阅带 `resource_admission` 的初始化或显式 `reorganize-workspace`，再创建绑定 typed locator/capability、精确 Phase bytes、actor、expiry、authorization 与 fencing token 的 Admission request。所有 mutation 默认 dry run，必须显式 `--apply`；没有 daemon 自动续租。

## 启动项目

对于新的非平凡项目，在 `PROJECT_CONTROL.md` 中定义 Project 目标与全局验收；长工作区的 Phase queue/evidence/recovery 放在所属 `PHASE_CONTROL.md`，显式 Session checkpoint 放在 `SESSION_CONTROL.md`。只有需要 durable report/handoff 时才按需刷新 `WORK_TASK_REPORT.md` 或创建 `PROJECT_HANDOFF.md`；CURRENT contract 中二者都是 derived/non-authoritative view。

使用 `runtime/EN/` 或 `runtime/CH/` 中对应模板作为起草参考。除非用户明确要求翻译镜像，否则只保留一份规范的控制、报告和交接文件。

## 选择合适的工作流

- 只需要轻量根项目控制时，使用 `malts-project-init`。
- 项目会跨 Phase、跨窗口、经历中断或需要恢复边界时，使用 `malts-long-project-workspace-init`。选择该入口就代表选择长期项目工作区：初始化会同时创建根控制文件和首个 active Phase，不会静默停在最小骨架。
- 当目标、假设、取舍或验收标准需要澄清时，使用 Grill-Me Preflight。
- 简单工作保持单 Agent。
- 验证后，普通单 Agent 工作会自动进行一次无写入 Growth Routing Gate。琐碎且无 signal 的工作保持静默；非琐碎工作或纠正/失败/恢复会得到简短、可见的成长结果。重复或高影响证据只建议 Standard/Major retrospective，不会自动执行；L2/L3 写入仍需独立授权。
- 对用户已批准的长任务或多 Agent 任务，派发前展示 launch review。
- 当交接上下文必须跨会话保存时，使用 handoff Skill。

长期项目初始化必须提供首个 Phase ID 和目标。Dry run 必须列出首个 `PHASE_CONTROL.md`；缺少 Phase 输入时零写入失败。Apply 后应核对 `initialization_status=READY` 和 active Phase。初始化不会创建 Session；只有明确存在 bounded work-session 边界时才开启。

如果旧工作区已有根控制文件但没有登记任何 Phase，验证会报告 `WS_INITIAL_PHASE_MISSING`。通过 initializer 补充首个 Phase，或显式开启第一个 Phase；现有用户文件必须保留。

## MALTS 何时要求隔离 Preview

候选可能改变 runtime、boot、registry 或工具发现时，Agent 应展示 preview 范围、显式
绝对根、验证与清理边界，并等待确认。用户无需猜测何时需要沙箱：release prep 会返回
`PREVIEW_REQUIRED`，Agent 必须在运行前主动说明该状态。

preview 会为 Codex、Claude Code 和 OpenCode 启动使用 process-local 隔离配置的全新
进程。任何工具无法隔离时都报告 `BLOCKED`，不得回退到真实工具根。用户可以显式
waive preview，但结果会把真实工具集成记录为 `NOT RUN`，且不具备完整 release
qualification。

## 验证项目控制

用户工具会验证稳定的项目控制结构；提供 MALTS 根时，也会验证当前版本引用：

```powershell
python -B <MALTS_ROOT>\tools\malts_user_tools.py check-project-control `
  --project-control <PROJECT_CONTROL_PATH> `
  --malts-root <MALTS_ROOT>
```

## 不改变状态的诊断

使用 lifecycle root 和每个已选工具根运行
`scripts\Invoke-MALTSLifecycle.ps1 -Command Doctor` 检查安装。Doctor 以
`writes_performed=false` 报告精确漂移与 trust evidence，不执行 repair、update、
cleanup 或后台检查。任何建议 repair 都必须进入独立的 review-only plan 与精确 plan
hash 授权流程。

## 治理 Phase 与 Artifact Lifecycle

### 审阅和改变 Phase

候选 goal 或 touch set 可能离开 active boundary 时，先运行 `phase-boundary-review`。它只读，不授予实施权限。`status`/`operation_status` 只表示 command execution；必须分别检查 `review_outcome`、mapping、recommendation 与 `persisted`。用 `record-phase-boundary-review` 持久化 structured result；该记录仍不授予实施权限。需要保留 ownership 但停止工作时用 `pause-phase`。Pause/resume 必须传稳定的 Review ID（例如 `review:phase-030:001`），不得把文件路径当 ID；证据路径保存在独立字段。恢复前可对显式选中的 PAUSED Phase 运行只读 `plan-recheck`，但 PASS 只证明绑定有效，不授予执行权限。只有具备当前 boundary/plan/authorization 证据时才用 `resume-phase`。跨 Phase 交接分两步：先生成 hash-bound `plan-phase-transition`，再用显式 carry-over 与 disposition file 执行 `apply-phase-transition`。

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py phase-boundary-review --workspace <workspace> --candidate-goal <goal> --candidate-touch-set <paths> --candidate-mapping UNCLEAR --recommendation USER_DECISION_REQUIRED
python -B <MALTS_ROOT>\tools\long_workspace.py pause-phase --workspace <workspace> --reason <reason> --boundary-review-ref <review-id> --authorization-ref <ref>
python -B <MALTS_ROOT>\tools\long_workspace.py plan-recheck --workspace <workspace> --phase-id <paused-phase-id> --trigger CONTEXT_RECOVERY --require-active-plan
python -B <MALTS_ROOT>\tools\long_workspace.py resume-phase --workspace <workspace> --phase-id <id> --boundary-review-ref <review-id> --plan-review-ref <ref> --expected-plan-sha256 <sha256> --authorization-ref <ref>
```

先审阅 dry-run output，再添加 `--apply`。`SUPERSEDED` 是终态；`active_phase_id` 保持单值 primary Phase。只有 `resource_admission` 可同时登记额外 `OPEN` Phase，且其写入必须取得 Admission。

### 重整与一致性恢复

全新 workspace 使用 CURRENT，默认 `single_phase`。受支持的旧 workspace 与 Result 布局保持可读且不会静默升级。先运行 `validate`；若它将输入分类为需要重整，使用报告的精确 hash，并先在不带 `--apply` 的情况下审阅一个匹配命令。公开流程始终直接生成 CURRENT，不要求用户经过中间版本或降级链。

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py record-phase-boundary-review --workspace <workspace> --phase-id <id> --review-id <id> --candidate-mapping SAME_PHASE --recommendation KEEP --evidence-ref <ref> --expected-phase-sha256 <sha256> --operation-id <id>
python -B <MALTS_ROOT>\tools\long_workspace.py recover-workspace-transaction --workspace <workspace> --operation-id <id> --expected-journal-sha256 <sha256>
python -B <MALTS_ROOT>\tools\long_workspace.py reorganize-workspace --workspace <workspace> --operation-id <id> --expected-state-sha256 <sha256> --expected-project-control-sha256 <sha256> [--project-control-candidate <workspace-relative-path> --expected-candidate-sha256 <sha256>] --profile <single_phase-or-resource_admission> --review-ref <ref> --authorization-ref <ref> [--expected-plan-sha256 <sha256>]
python -B <MALTS_ROOT>\tools\long_workspace.py reorganize-result-contract --workspace <workspace> --contract <legacy-or-current-contract> --expected-contract-sha256 <sha256> --expected-phase-control-sha256 <sha256> --expected-phase-boundary-sha256 <sha256> --operation-id <id> --revision-reason <reason> --review-ref <ref> --authorization-ref <ref> [--task-id <tid> --lineage-id <lid> --phase-id <pid> --event-id <eid> --expected-plan-sha256 <sha256>]
```

Applied workspace/coordination authority 写入共享 unique-writer lock/journal，并在获锁后复核精确 preimage。禁止删除 incomplete journal；先运行匹配的 exact-journal-hash recovery dry run，再添加 `--apply`。Current recovery authority 固定为 active Session checkpoint、primary active Phase recovery、显式绑定 terminal Phase、Project recovery——绝不选择最新历史 Session。

### 协调 resource-profile 写入

`workspace_coordination.py` 负责 typed locator/capability Admission、lease renew/release、fencing verify、expired grant reap，以及 `UNKNOWN` record/reconcile。所有 mutation 默认 dry run，直到显式 `--apply`；续租是显式操作，不创建 daemon。Request JSON 遵循 `workspace_coordination.schema.json`。Non-fenceable exclusive capability 必须串行，`ISOLATE_REQUIRED` 必须使用不同 isolation key。

### Audit、enroll 与 mutate Artifact

从 `artifact audit` 开始，不要手工创建 index file。如果结果为 `LEGACY_UNDECLARED`，workspace 仍兼容，但没有 enrollment。只有在 owner、Shared、Archive boundary 都已理解后，才使用 enrollment preview/apply。

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py artifact audit --workspace <workspace> --captured-at <timestamp>
python -B <MALTS_ROOT>\tools\long_workspace.py artifact enrollment-preview --workspace <workspace> --captured-at <timestamp>
python -B <MALTS_ROOT>\tools\long_workspace.py artifact enrollment-apply --workspace <workspace> --operation-id <id> --captured-at <timestamp> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py artifact register --workspace <workspace> --owner phase:<phase-id> --role WORKING --locator <path> --authority WORKSPACE --vcs LOCAL_ONLY --verification UNVERIFIED --retention <contract> --disposition KEEP_OWNED --operation-id <id> --apply
```

Promotion 需要 verified source evidence。Supersession 会保留旧 payload/history，并且要么 atomic 更新所有已审阅 active reference，要么 fail closed。Reconcile 只 apply 显式 owner disposition。所有 mutation 默认 dry-run，绝不移动/删除 payload、调用 VCS、递归扫描未声明目录或创建 Session。

## 默认安全行为

写入前先计划。工具根改动必须留在用户已批准的范围内。报告完成前先验证；没有用户明确授权的目标、限额、停止条件和恢复行为时，不要启用无人值守继续执行。

## Plan Recheck 与 Codex Peer Task

Active S3/S4 长项目 Phase 在 `PHASE_CONTROL.md` 中绑定 active plan path、revision 与 raw-byte SHA-256。在新写入范围、launch review、verifier、recovery/rollback 或 final delivery 前，按事件运行只读 `long_workspace.py plan-recheck`。Root control 只保存索引，Session 只继承绑定。`BLOCKED` 必须停止；该命令不会编辑 control 或创建授权。

当原生子 Agent 无法满足已批准的 hard model / effort 契约，而官方 Codex task/thread 接口能够满足时，可使用受治理的 peer task。它使用当前项目工作区，记录为 `codex-peer-task` / `peer-task`，禁止静默 fallback，返工复用同一个 task，并只在 Main Controller 接受或终止闭合后归档。它属于现有 multi-agent Skill，不是新 Skill，也不是隐藏 child Agent。

## 当前 Workspace 命令

- `workspace-entry` / `refresh-maintenance-views`：有界只读日常进入，以及从当前 canonical control 按需重建 non-authoritative view；不保留旧投影正文。
- `record-result-events` / `rebuild-result-lineage`：typed Result event append 与投影重建（默认 dry-run）；resource execution 使用 CURRENT Result authority。
- `reorganize-workspace` / `reorganize-result-contract`：把任意受支持旧输入一步显式、hash-bound 地重整为 CURRENT，并要求满足对应静止与恢复条件。
- `workspace_coordination.py`：Admission、queue、lease、fencing、quarantine 与 reconcile；不创建 heartbeat daemon。
- `plan-phase-boundary-amendment` / `apply-phase-boundary-amendment`：不可变 Phase boundary revision。
- `transfer-session-lease`：哈希绑定的 Session lease owner 转移。
- `scoped-readiness`：只读 S0/S1/S2/ESCALATE 路由建议；绝不授权或写入。
- `refresh-project-instructions`：只按精确审阅计划重写 `MALTS-PROJECT:` 拥有的 block。
