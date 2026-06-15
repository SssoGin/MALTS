# MALTS 核心设计

语言：[English](../CORE_DESIGN.md) | [简体中文](CORE_DESIGN.md)

MALTS 是一个面向 AI agents 参与或执行长时间 coding tasks 的 portable operating framework。它把可能超过单次 prompt、单个上下文窗口、一次不间断会话或单个 Agent 短期记忆的工作，形式化为可恢复、可验证、可交接的生命周期。

MALTS 默认 single-agent first。Multi-agent execution 是一种受控分工机制，只有在有明确操作价值时才启用；任何真实 sub-agent dispatch 前都必须先展示 launch review 并获得明确确认。即使 sub-agents 参与，main controller 仍然保留最终判断、合并、验证和交付责任。

从设计角度看，MALTS 是一个低开销的 Agent Project Operating System。它把任务交付、可恢复执行、受控委派、验证证据和复盘成长连接成一个闭环。核心目的不是制造更多流程，而是在 bounded execution rounds 之间保存意图、证据、恢复状态和可复用知识。

## 设计基线

本文定义 MALTS 的核心设计原则、操作模型和系统边界。MALTS 面向 AI agents 参与或执行的长时间 coding tasks，重点处理 goal drift、状态丢失、验证证据不足、跨窗口恢复和可复用学习。它说明 single-agent execution、受控 multi-agent 分工、恢复、交付验证和成长之间的关系。

设计不变量如下：

- 系统将 long-task scheduling 与 project retrospective growth 集成在同一个交付与成长闭环中。
- 系统是一个完整 workflow，不应拆成互不相关的产品。
- 普通工作默认保持 single-agent。
- 低开销 growth review 始终可用；写文件和 durable-memory 工作按价值和风险分层。
- Multi-agent scheduling 是可选项，只在 independent exploration、independent verification、降低上下文压力或无冲突并行 work 等场景有真实价值时启用。
- 真实 sub-agent dispatch 前，用户必须已经看到 launch review 并明确确认。
- Main controller 可以委派规划、探索、实现、验证或 memory curation，但不能委派最终责任。
- 长任务必须能从文件恢复，不能只依赖 chat memory。
- 用户原始目标和验收标准必须保持可见，不能被静默改写。
- 完成声明必须有验证证据。
- Growth candidates 进入 durable rules 或 memory 前必须过滤和去重。
- Token cost 是设计约束。更多 agents、documents 和 rules 只有在改善恢复、验证、交付或复用时才成立。
- Git 是可选恢复增强，不是硬依赖。MALTS 必须对没有 Git 的用户和项目仍然可用。
- 删除、依赖变更、权限变更、build 配置变更、credential 变更或 durable rule 变更等高风险动作需要确认或明确 safety controls。
- Codex、Claude Code 和 OpenCode 是围绕同一 core system 的 peer adapters。

## 概念模型

MALTS 把 Agent work 看作可审计的操作生命周期，而不是一次瞬时对话。模型由四类受控转换组成：

| 操作问题 | MALTS 控制机制 | 形成的系统属性 |
|---|---|---|
| 用户意图会在长对话中漂移。 | 原始目标捕获、完成定义和验收标准。 | 目标稳定且任务边界可审阅。 |
| 长执行可能超过单个 context 或 session。 | Bounded rounds、恢复文件、work reports 和 handoff records。 | 可以从外部证据继续。 |
| 并行 work 会产生协调风险。 | Launch review、task contracts、scoped permissions 和 dispatch evidence。 | 受控委派，责任可审阅。 |
| 经验可能积累成噪声。 | Retrospective analysis、memory-write filtering、deduplication 和 destination selection。 | 可复用能力增长，不产生无控制规则膨胀。 |

这个系统有意保持低 runtime 假设，但严格要求状态纪律。它不要求中央服务，但要求重要目标、决策、检查、风险和恢复点成为显式 artifacts。

## 系统定义与范围

### 定义

MALTS 是一个面向 AI-agent-assisted coding projects 的 portable operating workflow。它定义 Agent 如何捕获用户目标、把目标转化为可验证 work、为中断后的继续保存足够状态，并把可复用经验蒸馏为未来能力，同时避免 durable memory 无控制增长。

系统保持低开销。它的主要操作基底是一组 file-backed runtime rules、templates、checklists、handoff records、work reports 和可选 tool adapters。因此它可以在现有 coding environments 中运行，不要求强制 server、daemon 或 database。

### 目标用户与使用场景

MALTS 面向：

- 需要 coding-agent work 跨窗口、跨 session、跨中断保持可恢复的用户。
- 在 corrections、failures 或 consequential decisions 后需要低开销 growth review 的 single-agent tasks。
- 需要显式 state、acceptance criteria、verification 和 handoff 的 long-running coding projects。
- independent exploration 或 verification 可能证明受控 multi-agent round 有价值的任务。
- 希望在 Codex、Claude Code 和 OpenCode 之间使用一个核心操作模型的团队或个人。

主要操作意图是完成任务，同时保存 goal definition、verification evidence、recovery state 和 reusable lessons。Multi-agent execution 是更大操作模型中的一个受控机制，不是系统的唯一或默认特征。

### 范围边界

MALTS 的范围是 Agent project operating workflow。Agent runtime behavior、source control、package management、editing、CI、secret management 和 human approval 仍是外部系统，并拥有独立权威。

设计边界如下：

- orchestration 采用 file-backed、workflow-driven model，而不是强制中央服务。
- Git 提升安全性，但只是可选 recovery mechanism。
- multi-agent scheduling 保持可选受控模式。
- durable memory writes 只作为 review 后的 filtered outcomes。
- high-risk actions 仍需用户确认或显式 safety controls。
- runtime state 和 project artifacts 位于 reusable MALTS system definition 之外。

### 规范性操作承诺与明确限制

在自身范围内，MALTS 定义以下可执行承诺和相应限制：

| 维度 | 规范性承诺 | 明确限制 |
|---|---|---|
| Recoverability | Project state 外部化到 `PROJECT_CONTROL.md`、`WORK_TASK_REPORT.md`、`PROJECT_HANDOFF.md` 等文件。 | Recovery 不能重建从未记录过的 work。 |
| Runtime continuity | 长 work 被拆成 bounded rounds，并有明确 stop、report 和 continuation points。 | Bounded rounds 不能扩展 runtime 的 context window、tool limits 或 uninterrupted session lifetime。 |
| Delegation control | 真实 sub-agent dispatch 前有 launch review、用户确认、task contracts 和后续 report recycling。 | 如果 runtime 不暴露 dispatch evidence，MALTS 不能认证 sub-agent work。 |
| Completion evidence | 完成按照 acceptance criteria 和验证证据评估。 | 已执行检查可以作证；跳过、阻塞或不可用的检查不能事后认证。 |
| Knowledge growth | Reusable lessons 进入 durable rules 或 memory 前必须过滤、去重并选择目的地。 | 偶然观察不会自动成为 durable policy。 |
| Risk governance | High-risk operations 需要用户确认或已记录 safety control。 | MALTS 不替代 source control、CI、permission models 或 human approval 等外部系统权威。 |

### 核心操作循环

系统保持三个循环连接：

```text
Delivery loop:
goal -> completion definition -> task queue -> execution -> verification -> delivery

Scheduling loop:
state -> bounded round -> optional delegation -> report recovery -> merge -> next round

Growth loop:
fact review -> cause analysis -> reusable lesson -> filtered candidate -> future use
```

Delivery loop 保存任务相关性。Scheduling loop 让长 work 可恢复。Growth loop 通过阻止未过滤观察进入 permanent memory，保持认识论纪律。

## 系统边界

MALTS 的核心职责：

- 通过 `PROJECT_CONTROL.md` 提供可恢复状态模型。
- 将 task queues、decisions、file ownership、verification 和 recovery notes 保存在 volatile chat context 之外。
- 支持普通 work 的低开销 single-agent growth。
- 在有清晰价值时支持受控 multi-agent scheduling。
- 提供 task contracts 和 sub-agent report templates。
- 提供 delivery、quality 和 memory-write checklists。
- 通过 `PROJECT_HANDOFF.md` 提供 Agent-facing handoff。
- 通过 `WORK_TASK_REPORT.md` 提供 work reports；中文用户可读输出或双语模式在范围内时，同步维护 `工作任务报告.md`。
- 为 Codex、Claude Code 和 OpenCode 提供可选 adapters。
- 提供低开销 linting 和 document-structure checks。

以下职责不在当前 MALTS 范围内：

- 运行强制 scheduling service 或 database。
- 要求 Git、特定 IDE 或特定 agent runtime。
- 为每个小任务创建 MALTS files。
- 默认大规模 sub-agent launch。
- 把每个 lesson 都当作 permanent rule。
- 覆盖用户对 high-risk actions 的判断。
- 延长 runtime 的 uninterrupted session duration。
- 在没有 visible dispatch evidence 时认证 sub-agent work。

## 架构

MALTS 使用一个 core system 和三层结构：

```text
MALTS
|
|- Core layer
|  |- PROJECT_CONTROL.md
|  |- WORK_TASK_REPORT.md
|  |- PROJECT_HANDOFF.md
|  |- templates
|  |- checklists
|  `- durable growth candidates
|
|- Runtime layer
|  |- canonical skills
|  |- execution modes
|  |- recovery and continuity
|  |- delivery verification
|  `- memory pipeline
|
`- Adapter layer
   |- Codex
   |- Claude Code
   `- OpenCode
```

Core layer 存储通用操作模型和持久 project artifacts。Runtime layer 通过根级 `skills/`、execution modes、recovery、verification、templates、checklists 和 memory pipeline 把模型变成可执行 Agent workflows。Adapter layer 把同一模型映射到每个受支持 agent tool，而不让 tool-specific details 污染核心设计。

公开包只有一个 canonical skill 和 runtime source：共享 `MALTS_ROOT`，并以该 root 下的 `skills/` 为准。目标工具目录是薄 adapter target，不是独立 MALTS runtime 或 skill source。`runtime/EN` 包含 MALTS workflows 使用的 Agent-facing templates 和 checklists。`runtime/CH` 包含简体中文运行镜像，用于用户可读审阅和双语产物生成。

## 激活模型

MALTS 有三种实际模式：

| 模式 | 使用时机 | 需要文件 | 行为 |
|---|---|---|---|
| Normal single-agent work | 小、明确、低风险任务 | 默认无 | 直接完成，验证相关 completion criteria，必要时做低开销 growth judgment |
| MALTS single-agent mode | Work 需要可恢复状态或阶段报告 | `PROJECT_CONTROL.md`；通常根据需要使用 `WORK_TASK_REPORT.md` 和 `PROJECT_HANDOFF.md` | Main controller 默认仍然执行，但状态和验证持久化 |
| MALTS multi-agent mode | Delegation 明确降低风险或成本 | MALTS files、task contracts 和 sub-agent reports | Dispatch 前需要 launch review 和明确确认 |

Single-agent first 表示启用 MALTS 后 main controller 仍是默认执行者。这个原则有两个边界：它既不要求每个任务都启用 MALTS，也不会在 MALTS 已启用后删除状态文件。

## 任务分级

每个任务都应在增加流程开销前做 fit-for-process assessment。

| Level | 形态 | 默认选择 |
|---|---|---|
| S0 trivial | 一个命令、一个短回答、typo、简单查询、小格式修改 | Single Agent only |
| S1 bounded | 单文件或单行为，验证路径清晰 | Single Agent；必要时做低开销 growth judgment |
| S2 medium | 多文件或原因不清，但仍能在一个 bounded round 中处理 | Single Agent first；只有 Explorer 或 Verifier 能降低风险时才考虑 |
| S3 complex | 多阶段、多模块、易中断或可能超过舒适 context | 使用 MALTS state；如果 multi-agent work 有价值，准备 launch review |
| S4 high-risk or unclear | 删除、权限、依赖、build config、credentials、durable rules、目标或验证不清 | 先澄清或获取批准；写入前使用只读规划或验证 |

Agent 应在推荐 multi-agent work 前说明预期操作价值。如果价值不清楚，应保持 single-agent execution。

## 项目状态模型

启用 MALTS 时，`PROJECT_CONTROL.md` 是主要状态文件。它让下一个窗口、下一个 Agent 或同一 Agent 在 context compaction 后，可以从外部证据继续。

核心 sections：

```text
User Original Goal
Current Interpreted Goal
Completion Definition
Acceptance Criteria
Current Mode
Current Stage
Task Queue
File Ownership
Decisions
Verification Records
Deliverables
Risks And Blockers
Exception Handling
User Checkpoints
Termination Status
Planner Evaluation
Cost And Efficiency
Growth Candidates
Next Round Plan
Recovery Notes
```

最小恢复状态：

- current goal
- completion definition
- active task and next task
- completed work
- changed files
- verification evidence
- open risks or blockers
- user decisions still needed
- next shortest recovery path

对于小型 MALTS-enabled work，该文件可以保持紧凑。目标是可恢复状态，而不是为了文档体积而增加文档。

## 产物矩阵

| Artifact | 默认位置 | 受众 | 目的 |
|---|---|---|---|
| `PROJECT_CONTROL.md` | Project root | Agent-facing | 当前目标、队列、决策、ownership、verification、risks、recovery state |
| `项目控制.md` | Project root | 中文用户可读镜像 | 中文用户可读状态在范围内时，作为 `PROJECT_CONTROL.md` 的实质镜像 |
| `WORK_TASK_REPORT.md` | Project root | Agent-facing structure and report source | 阶段或最终交付报告结构与证据记录 |
| `工作任务报告.md` | Project root | 中文用户可读镜像 | 中文输出或双语模式在范围内时，作为 `WORK_TASK_REPORT.md` 的实质镜像 |
| `PROJECT_HANDOFF.md` | Project root | Agent-facing | 面向未来窗口、工具或 Agents 的 continuation source |
| `项目交接.md` | Project root | 中文用户可读镜像 | 用户请求或项目语言要求时的 handoff mirror |
| `TASK_CONTRACT.template.en.md` | `runtime/EN/templates/` | Agent-facing | 真实 sub-agent task 的 contract |
| `SUB_AGENT_REPORT.template.en.md` | `runtime/EN/templates/` | Agent-facing | sub-agent 返回的结构化结果 |
| `PROJECT_HANDOFF.template.en.md` | `runtime/EN/templates/` | Agent-facing | 固定 recovery handoff 模板 |
| `WORK_TASK_REPORT.template.en.md` | `runtime/EN/templates/` | Agent-facing structure, user-facing output | 可用用户语言撰写的 report 结构 |
| `WORK_TASK_REPORT.template.zh-CN.md` | `runtime/CH/templates/` | 中文用户可读镜像 | `工作任务报告.md` 的结构 |
| `DELIVERY_CHECKLIST.en.md` | `runtime/EN/checklists/` | Agent-facing | Final 或 phase delivery self-check |
| `MEMORY_WRITE_CHECKLIST.en.md` | `runtime/EN/checklists/` | Agent-facing | durable memory 或 rule writes 前的过滤 |
| `QUALITY_GATE.en.md` | `runtime/EN/checklists/` | Agent-facing | 通用 completion gate |

Release templates 是起点。真实 project artifacts 属于用户项目 workspace，不属于本 release repository。

## 有界运行流程

标准 MALTS execution protocol 是 round-based：

1. 读取用户目标和项目指令。
2. 判断是否需要 MALTS。
3. 如果启用 MALTS，创建或复用 `PROJECT_CONTROL.md`。
4. 捕获 original goal、completion definition、acceptance criteria、task queue、file ownership 和 risks。
5. 对非琐碎或不清楚的开始提供 MALTS-native Grill-Me Preflight，除非明显 N/A。
6. 执行下一轮 bounded round。
7. 标记任务完成前先验证。
8. 每个 MALTS phase 或最终交付后写入或追加 `WORK_TASK_REPORT.md`；中文输出或双语模式在范围内时，同步写入或追加 `工作任务报告.md`。
9. 进入 handoff、context-risk handling 或 cross-window continuation 时，更新 `PROJECT_HANDOFF.md`。
10. 将 reusable lessons 送入 MALTS Memory Pipeline。

Long work 被建模为带明确 stop、report 和 continuation points 的 bounded rounds 序列。这个设计让连续性不依赖任何单一 uninterrupted chat window。

MALTS 不是会自动观察 context windows 或自动写 handoff files 的 background service。Recoverability 取决于 Agent 在相关 checkpoint 执行协议。

## 上下文与连续性

当 context 变得有风险时，main controller 必须先持久化 recovery state，再继续做更多非琐碎 work。Context risk 包括：

- 接近 context limits
- compaction 或 summarization
- tool/runtime interruption
- handoff 到另一个窗口
- 未解决的 sub-agent work
- 多个 active branches of work

继续前，future Agent 应按以下顺序读取：

1. `PROJECT_HANDOFF.md`
2. `PROJECT_CONTROL.md`
3. `WORK_TASK_REPORT.md`
4. 当前 next task 所需的 project files

如果 chat memory 与 file state 冲突，在验证前以当前 file state 为准。

## 可选 Multi-Agent Scheduling

Multi-agent work 是受控分工机制，并且不属于默认 runtime path。

支持角色：

| Role | 默认权限 | 责任 |
|---|---|---|
| Main Controller | Coordination, merge, final judgment | 负责用户沟通、状态、launch review、merge、verification、delivery |
| Planner | Read-only advice | 分解 tasks、dependencies、priorities 和 batches |
| Explorer | Read-only | 调查 project structure、logs、modules 或 root cause |
| Worker | Scoped write access | 在声明的 file 或 task boundary 内实现 |
| Verifier | Read-only by default; may run checks | 测试、构建、扫描并验证 delivery claims |
| Memory Curator | Candidate writes only | 提取 reusable lessons 并准备 filtered growth candidates |

可以以后增加高级角色，但 MVP 应避免无边界 role proliferation。

任何真实 sub-agent dispatch 前，main controller 必须展示 launch review packet，包含：

- overall goal and plan
- 本任务使用 multi-agent work 的预期操作价值
- 每个将被 dispatch 的 role
- 每个 task boundary
- allowed files or directories
- prohibited areas
- model name 或 model policy（runtime 可用时）
- dispatch order 或 parallel batches
- verification requirement
- expected output format
- 明确说明 dispatch 等待用户确认

如果用户指定 sub-agent models，main controller 应询问 model preferences 并在 dispatch 前记录结果。如果 runtime 不暴露 exact model selection 或 exact inherited model names，必须把该限制记录为 execution evidence 的一部分。

没有 runtime-visible dispatch evidence 时，不得声称发生了 sub-agent work。证据可以是 tool call、thread ID、agent ID、transcript 或等价记录。

## 任务契约与恢复

一个 task 只有在具备以下内容时才 ready for dispatch：

- clear goal
- available context
- allowed read/write scope
- prohibited scope
- dependencies satisfied
- file ownership or conflict boundary
- expected output format
- verification method
- model policy when relevant

Sub-agent reports 必须在 merge 前回收并审阅。偏离 scope、不可验证、不完整或与 task contract 不一致的 reports，应被拒绝、以更小任务重试，或升级给用户。

Failures 应被记录为 failures。Partial 或 failed sub-agent output 必须保持 incomplete work 分类，而不是完成进度。

## 验证与交付

Completion 是 evidentiary claim，必须由 verification records 支撑，而不是主观信心。

Phase 或 final delivery 前，Agent 应审阅 `DELIVERY_CHECKLIST.en.md`，并在 `WORK_TASK_REPORT.md` 或最终 user-facing report 中记录审阅。

Report 应包含：

- result
- changed files or artifacts
- verification performed
- skipped or failed checks
- known risks
- recovery point
- next step
- growth review and memory-write decision when applicable

Termination 有三种实际状态：

| State | 含义 | Delivery behavior |
|---|---|---|
| Ideal | 所有 acceptance criteria 通过，risks 已关闭或接受 | 正常交付 |
| Pragmatic | 核心目标已满足，但存在透明残余风险 | 带 risk list 交付 |
| Forced | 用户停止、预算耗尽、环境阻塞或方向不确定 | 保存 state 和 recovery path |

如果 verification 不完整，delivery record 必须明确说明限制。部分验证的结果不是完全验证的交付。

## 成长系统

Growth 是 operational change process，不只是 retrospective summary。

| Output | Purpose |
|---|---|
| Summary | 发生了什么 |
| Retrospective | 为什么发生、流程在哪里漂移 |
| Distillation | 下次应改变什么，并包含 trigger、action、check、boundary |
| Skill or rule | 可在未来正确时机调用的 reusable behavior |

Growth tiers：

| Tier | Trigger | Output |
|---|---|---|
| Light | 普通小任务 | 通常不写文件；只有有价值时做短判断 |
| Standard | Phase delivery、user correction、轻微 rework、consequential decision | Candidate lesson、checklist item 或 report note |
| Major | Significant failure、direction drift、重复 rework、long-task completion | Full retrospective 和 durable rule/skill candidate |

这个 tiering 让普通工作保持低操作成本，同时在经验预期复用价值足够时保存 lessons。

## MALTS Memory Pipeline

MALTS Memory Pipeline 是 reusable lessons 的 durable growth path，独立于任何单一 external memory tool。

Pipeline：

1. 从 delivery、failure、user correction、verification 或 process friction 中观察 reusable lesson。
2. 先在 `PROJECT_CONTROL.md`、`WORK_TASK_REPORT.md` 或 local retrospective 中本地记录。
3. 使用 `MEMORY_WRITE_CHECKLIST.en.md` 过滤。
4. 与已有 rules、skills 和 instruction files 去重。
5. 选择最窄 durable destination：project skill、global skill、`GLOBAL_MEMORY.md`、`AGENTS.md`、`CLAUDE.md` 或等价 tool instruction entry。
6. 只有在 external memory system 已配置、可写且适合时才使用它。
7. 如果 durable destination 不可用，保留 local candidate 并报告没有发生 long-term write。

一个经验只有在真实、可重复、有边界、可检查，并且预期复用价值高于维护成本时，才应成为 durable memory。

## Token 与成本控制

MALTS 将 process cost 视为一等设计约束：coordination 和 documentation 只有在回报高于操作成本时才合理。

成本控制：

- S0/S1 work 保持 single-agent。
- 只读取当前决策需要的文档。
- 正常执行时避免同时加载 English 和 Chinese runtime docs。
- 不把长模板塞进全局 instruction files。
- 使用 bounded rounds，避免开放式 progress。
- 只给 sub-agents task-relevant context packets。
- 合并或丢弃低价值 tasks，而不是把它们独立调度。
- 保持 growth review tiered。
- Durable rules 写入前先过滤。
- 当 multi-agent parallelism 产生的 coordination cost 大于 delivery value 时，降低并行度。

评估 multi-agent round 时，应看 uncertainty 是否下降、verification 是否改善、conflicts 是否受控、task queue 是否向完成推进。

## 安全与权限

Task contracts 应标明 permission level：

| Level | Permission |
|---|---|
| 0 | Read-only analysis |
| 1 | Modify specified files only |
| 2 | Add files, but do not delete files |
| 3 | Directory restructuring only after main-controller approval |
| 4 | High-risk operation requiring user confirmation |

High-risk operations 包括：

- deleting files
- modifying permissions
- changing dependency versions
- changing build configuration
- changing authentication, credentials, or authorization behavior
- overwriting existing configuration
- cleaning caches, logs, history, or archives
- modifying durable global instructions, skills, or long-term rules

如果项目有 Git，meaningful edits 前检查当前状态，并且绝不在没有明确批准时丢弃用户改动。如果项目没有 Git，使用更轻量 recovery mechanisms，例如 scoped backups、smaller patches 和 clear recovery notes。

## Unattended Continuation

Unattended continuation 不属于默认 long-task scheduling semantics。它需要明确用户授权，并且必须记录在 `PROJECT_CONTROL.md`。

Authorization record 应包含：

- authorized goal
- allowed files, directories, commands, and actions
- prohibited actions
- 是否允许 multi-agent dispatch
- model policy for any allowed sub-agent work
- maximum rounds or time limit
- stop conditions
- report and recovery-state requirements
- continuation mechanism, if any

没有该记录时，MALTS 应停在正常 user checkpoints。

## Adapter 策略

MALTS 保持 core portable，并把 tool-specific details 放入 adapters。

Codex：

- 使用 `AGENTS.md` 作为 instruction entry。
- 安装时在 Codex 配置 root 中使用 `config.toml` 和 `agents/*.toml` 提供 Codex-native custom subagent scaffold。
- 通过 `MALTS_BOOT.md` 和共享 `MALTS_ROOT` 解析 MALTS skills 与 runtime files。
- 除非 Codex 官方文档明确支持，否则不得声称 Codex 支持 Claude Code 或 OpenCode 风格的文件式自定义 slash commands。
- 使用 `PROJECT_CONTROL.md` 作为 recoverable state。
- 实际使用 sub-agents 时，使用 visible tool calls 或 thread tools 作为 dispatch evidence。
- 可用时记录 agent IDs、roles、task IDs、model policy 和 report summaries。

Claude Code：

- 使用 `CLAUDE.md` 作为 instruction entry。
- 将 commands 和 agents 放在 Claude Code 预期的 adapter directories。
- 通过 `MALTS_BOOT.md` 和共享 `MALTS_ROOT` 解析 MALTS skills 与 runtime files。
- 不安装工具本地 skill 重复源。
- 记录 installed version 可用的 runtime-visible agent 或 transcript evidence。
- 当 explicit model selection 不可用或未验证时，记录限制。

OpenCode：

- 使用 `AGENTS.md` 和 OpenCode-specific config 作为 instruction 和 tool entry。
- 将 OpenCode-specific files 保持在 adapter layer。
- 通过 `MALTS_BOOT.md` 和共享 `MALTS_ROOT` 解析 MALTS skills 与 runtime files。
- 不安装工具本地 skill 重复源。
- 在声称透明 multi-agent execution 前，验证目标 OpenCode version 如何暴露 sub-agent dispatch evidence。

除非变更明确 scoped to one tool，否则 adapter docs 和 templates 应在 Codex、Claude Code 和 OpenCode 之间保持同步。

## 双语文档

English runtime documents 是 release source of truth。Chinese documentation 是面向用户审阅和 bilingual maintenance 的可选 mirror。

Agents 正常执行时应避免同时加载 EN 和 CH documents。Doc sync tooling 检查配置结构和路径；它不是 translation quality 或 semantic equivalence 的证据。关键协议 wording 需要 human 或 main-controller review。

如果 English 和 Chinese docs 冲突，先修英文事实源，再重新同步 Chinese review copy。

## 系统发布边界

MALTS 作为 Agent work 的 portable operating system 发布：runtime rules、templates、checklists、adapter guidance、installation helpers 和 design documentation。Distribution package 应包含 reusable system definition，以及在 project environment 中安装或运行该系统所需的材料。

Project-specific state 有意位于 system distribution 之外。真实 project control files、work reports、handoff records、local retrospectives、generated packages、caches 和 runtime history 是具体项目创建的 execution artifacts，由产生它们的项目治理，而不是由 MALTS system definition 治理。

这个边界让系统能够跨机器、团队和 Agent runtimes 复用，同时清楚区分 MALTS operating model 和应用该模型到具体项目时产生的 records。

## MVP 实施阶段

MVP sequence：

1. Design and templates：project control、task contract、sub-agent report、delivery checklist、quality gate。
2. Core skills：Grill-Me Preflight、long-task scheduling、project retrospective growth、session handoff、project initialization，以及 root `skills/` 下的 single-agent low-overhead growth。
3. Tool adapters：Codex、Claude Code、OpenCode。
4. Lightweight automation：task ID generation、project-control checks、doc sync checks、semantic freshness checks、installer dry-runs。
5. Trial and retrospective：分别验证 actual single-agent growth 和 actual multi-agent dispatch。Multi-agent validation claims 需要真实 dispatch evidence。

## 验收标准

第一个完整 MALTS release 可接受的条件：

- ordinary tasks 能保持低开销 single-agent。
- non-trivial starts 能通过 Grill-Me Preflight 暴露 assumptions。
- long tasks 能创建或复用 `PROJECT_CONTROL.md`。
- state 能跨 windows 或 Agents 恢复。
- multi-agent work 需要 launch review 和明确确认。
- sub-agent contracts 包含 scope、output 和 verification。
- completion claims 包含 evidence。
- `WORK_TASK_REPORT.md` 能向用户说明 results、verification、risk 和 recovery。
- `PROJECT_HANDOFF.md` 能指导下一个 Agent。
- growth candidates 在 durable writes 前通过 memory-write checklist。
- Codex、Claude Code 和 OpenCode 有 adapter entry points。
- 启用 bilingual docs 时，结构保持同步。
- no-Git projects 仍然有 basic recovery insurance。
- token 和 coordination cost controls 已记录并应用。
