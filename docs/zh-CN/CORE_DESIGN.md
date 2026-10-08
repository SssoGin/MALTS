# 多 Agent 长任务调度与成长系统

MALTS 帮助 AI Agent 完成有限的项目目标、跨中断接续、组织已授权工作并评估可复用经验。默认单 Agent，当前实现为 **2.0.0**。本文沿用产品设计的既有栏目，在其内补充当前机制，不把新版本当成另一个产品。

## 工作区权威、进入与并发

MALTS 围绕普通工作、长期项目与中断恢复维护同一套工作方式。已采用工作区的 v2 状态库保存可执行的项目、阶段、任务定义，以及版本、依赖、权限、操作和验收。早期版本生成的 Markdown 控制资料保留为原始来源或阅读视图，不作为另一套可写任务队列。

进入时先读取工具准确的 `MALTS_BOOT.md`，核实安装 discovery 和工作区 binding，再查询当前治理上下文、任务队列与所选任务。普通进入不重新初始化，也不按时间挑选最新历史 Session；不会自动创建 Project、Phase、Session、Agent 或 Artifact。

Project 说明整体目标；Phase 是包含计划、范围和退出条件的阶段；Task 对应可以检查的实际结果。定义与依赖绑定准确版本。目标或范围发生实质变化时修订受影响的定义和绑定；相关输入未变的有效证据可以复用。

并发通过声明资源、当前准入、租约和 fencing 管理，即受管接口拒绝持有过期执行资格的写者。不同目录不能单独证明编辑器、服务或设备互不影响；该机制也不排除任意外部程序。UNKNOWN 操作保留原身份，先对账再继续。参见[状态合同](V2_STATE_CONTRACT.md)。

## 设计基线

本文说明 MALTS 作为整体产品的设计。沿用交付、可恢复调度与经验改进的既有章节，将新增能力纳入相应栏目，必要时增设扩展章节。当前发布实现为 **2.0.0**。

设计基线包括：

- 跨执行轮次保留用户原始目标、约定边界与验收条件。
- 默认单 Agent；分工有实际价值且得到授权时，才采用独立调查、实施或验证。
- 保存接续所需的外部状态和实际证据，不能仅依赖聊天摘要。
- 区分执行、验证和验收；一个任务成功不等于整体项目完成。
- 报告与交接服务于交付或接续，保全用户手工内容。
- 经验是有来源、有适用范围、需要检验的候选方法，不自动变成永久规则。
- 复用同范围授权与有效证据，新增记录和检查必须解决具体问题。
- 支持没有 Git 的项目；Git 可加强恢复，但不成为项目状态权威。
- 四种工具适配围绕同一核心，分别说明真实宿主与配置的验证范围。

这些原则描述工作目标，不构成普遍提速、成功率或自治正确性的承诺。

## 概念模型

MALTS 将三条工作闭环相连：

```text
交付：目标 -> 验收条件 -> 有限任务 -> 执行 -> 验证 -> 交付
调度：当前状态 -> 下一有界轮次 -> 可选分工 -> 整合 -> 接续
成长：实际事实 -> 原因与适用性 -> 经审阅候选 -> 后续试用 -> 保留或撤回
```

| 问题 | 机制 | 用户可核查的内容 |
|---|---|---|
| 多轮工作中目标偏移 | 原始/当前目标与版本化定义 | 为何改变范围、哪些要求仍须完成 |
| 窗口结束但工作未完 | 当前任务、检查点和恢复证据 | 已发生什么、哪些效果未知、下一步是否具备条件 |
| 分工结果相互冲突 | 任务合同、资源范围和控制端验收 | 各产物边界、整合结果与验证 |
| 经验不断堆积为噪声 | 有来源候选、限定试用和撤回 | 方法适用于何处、后续证据是否支持 |

例如一次仓库迁移可以围绕一个交付目标，逐阶段检查兼容性，保留明确接续点，再在适合的后续工作中试用有价值的检查方法。它不需要被拆成相互独立的产品，也不要求固定人数的 Agent 团队。

## 系统定义与范围

### 定义

MALTS（Multi-Agent Long-Task Scheduling and Growth System，多 Agent 长任务调度与成长系统）是面向 AI Agent 项目工作的运行框架。它帮助把目标转为可检查结果、跨中断接续、组织已授权分工，并评估方法能否用于未来工作。需要持久状态时，代码修改、工程迁移、调查和文档交付可使用同一工作方式。

### 目标用户与使用场景

面向跨多轮、阶段、窗口或执行者的工作，以及需要追溯验证和恢复的维护项目。独立调查或验证可能有分工价值；清晰的小任务仍可直接完成，不必建立工作区。

### 范围边界

模型解释需求、进行业务判断；宿主提供工具、身份、权限提示和进程能力；MALTS 管理持久状态，以及执行、证据与恢复之间的合同。编辑器、Git、CI、包管理器和用户决定保留各自权威。

当前已采用工作区使用本地 SQLite 状态库及 CLI/MCP 服务，不要求托管调度服务器或后台守护进程。早期以文件为主的设计说明产品来源，不能据此宣称当前 v2 运行时没有数据库。

### 运行约定与能力限制

| 约定 | 限制 |
|---|---|
| 持久保留接续所需状态 | 未记录的外部效果不能靠摘要还原 |
| 行为和证明绑定当前定义 | 版本号和历史 DONE 不证明当前验收 |
| 审阅分工并保留主控制端责任 | 配置存在不证明真实原生派发 |
| 保留经验来源与适用资格 | 有价值观察不自动授权全局长期修改 |
| 保护并对账不确定效果 | 不能对所有任意 OS 写者实施互斥 |

### 核心工作闭环

交付确保工作与目标相关，调度确保接续，成长评估方法复用。验证向三者提供事实；它们都不产生额外权限，也不改变用户的完成标准。

## 系统边界

工作流描述目标澄清、项目设置、长期管理、当前任务、交接、复盘、轻量成长和多 Agent调度。Skill封装对应方法，模板帮助起草记录，检查清单帮助核结果，工具执行可确定的状态与文件操作。它们围绕同一项目工作，不形成平行的状态体系。

Skill不是权限来源。工具可以验证字段和事务条件，但不能替代业务判断；模型可以解释目标并选择方法，但不能用自评产生完成证明；宿主提供实际工具、身份和进程能力，配置声明不等于真实调用已成功。

安装将公共载荷放入不可变运行代际，并向各Agent工具提供自己的入口与投影。工具适配保留原生加载和权限方式，共享核心承担共同状态与恢复机制；安装更新、项目采用和实际模型行为分别验证。

用户可读英文或简体中文指南，机器字段保持稳定，项目叙述与手工内容保持原语言。双语文档描述同一状态，不建立两份可写记录。

安全边界包含明确授权、保全重要前像、识别来源、限制受保护内容传播、拒绝陈旧输入以及核外部写者。当前保护使用Windows当前用户DPAPI（数据保护API），因此跨用户恢复另有条件。不可变包体不手改，历史证据不为当前文档一致而重写。

## 架构

MALTS 由三个相互配合的层次组成：

```text
核心：项目/阶段/任务定义，操作、证据、成果与恢复
工作流：标准 Skill、模板、检查清单、交付与成长方法
适配：Codex | Claude Code | OpenCode | DeepSeek Harness
```

核心提供共用合同，工作流说明怎样围绕所选目标使用合同，适配层接入宿主实际加载方式和工具。一个不可变 `MALTS_ROOT` 保存标准实现；工具本地 `malts-*` 发现入口指向该实现，不另存竞争的实现副本。

`runtime/EN` 保存 Agent 标准模板和清单，`runtime/CH` 保存中文对应资料。`tools/` 实现确定性的领域与生命周期服务，`scripts/` 提供用户生命周期入口，`docs/` 解释产品及操作。真实项目状态和交付物保留在其实际项目中。

### 能力治理边界

Capability Registry 是来源与工具覆盖层的元数据视图，不是另一份 Skill 仓库。可移植性、宿主兼容性、暴露、审阅和执行权限是不同决定；建议路由器不能执行 Skill、产生权限或改变发现状态。参见[能力与技能治理](CAPABILITY_AND_SKILL_GOVERNANCE.md)。

## 激活模型

| 方式 | 适用情况 | 行为 |
|---|---|---|
| 普通单 Agent | 清晰的小任务 | 按项目规则完成并验证，不自动初始化 MALTS |
| 可恢复 MALTS 项目 | 工作跨多轮或阶段 | 保留目标、当前任务、检查和恢复；按需报告或交接 |
| 已授权协作 | 职责和资源可以分离 | 审阅任务合同与宿主能力，整合真实结果 |

安装、项目初始化、旧工作区采用和进入已有工作分别管理。选择 Skill 提供方法，不自动授权迁移或委派。

### 长项目初始化的完成条件

`malts-project-init` 负责轻量项目设置，`malts-long-project-workspace-init` 建立具有可执行阶段的长期工作区。首次设置须绑定经审阅的 Project、计划和首个活动 Phase，并报告 `phase_ready=true`。只有根文件、空库或 TASK_ONLY 都不算完成长项目初始化。Session 是独立、有界的明确操作；普通轮次和进入不会自动创建。

## 任务分级

分级帮助选择投入和恢复方式，不是审批等级，也不自动启用 MALTS、分工或无人值守。

| 级别 | 工作形态 | 建议方式 |
|---|---|---|
| S0 简单 | 一条命令、简短回答、文字修正 | 单 Agent 直接完成 |
| S1 有界 | 单文件/单行为，验证明确 | 单 Agent；有实际信号时轻量判断 |
| S2 中等 | 多文件或原因不明确，仍可一轮完成 | 单 Agent 优先，必要时调查/验证 |
| S3 复杂 | 多阶段、多模块或容易中断 | 保存 MALTS 状态；有价值且已授权时分工 |
| S4 高风险或不明确 | 删除、权限、凭据、依赖、长期规则，或目标/验收关键不清楚 | 先查事实并解决缺少的实质授权或决定 |

同范围必要步骤复用已有授权。判断多 Agent 时，说明是否降低不确定性、验证风险或整合成本，不以复杂度直接推导委派。

## 项目状态模型

项目定义整体目标和跨阶段接受条件；阶段限定一段工作及其交付；任务描述具体可执行结果。每个层次只接受其范围内的完成证明，任务成功不自动完成阶段，阶段结束也不自动关闭仍需维护的项目。

任务包含目标、相关输入、修改范围、依赖、验收和结果。分解质量取决于输出能否检查，而不是子任务数量。强依赖任务顺序执行；独立任务可以评估并行。新增需求与已经批准范围区分，必要的本地修正不被拆成重复审批。

当前实现使用版本化定义，把任务与准确阶段计划和前置结果相连。其目的在于识别陈旧输入和实际修订，而不是让用户记住内部编号。普通工作通过当前队列和上下文继续；历史材料按明确问题定位。

当前可执行状态由所选服务持久维护，不直接编辑数据库。Project 保留原始/当前目标，Phase 和 Task 使用版本化定义及验收。操作、授权、预算、检查点和证据保留准确身份。Markdown 可保存叙述计划和原始输入，但不能覆盖状态库。

### 长工作区跨控制一致性

采用前遵循经验证的历史合同；采用明确将原始定义和历史映射至 v2 权威，并保留 binding/source-seal。采用后不运行旧 Markdown 写入命令，也不恢复旧运行权威。绑定缺失应走当前恢复，不能静默重建。

## 产物矩阵

以下既有模板继续用于起草和审阅。已采用工作区的执行状态以当前服务记录为准；模板文件名不能使生成的 Markdown 自动获得运行权威。

| Artifact | 默认位置 | 受众 | 目的 |
|---|---|---|---|
| Project/Phase/Task 服务记录 | 所选工作区状态库 | Agent/控制端 | 当前可执行目标、计划、依赖、效果与验收 |
| `PROJECT_CONTROL.md` | 项目根 | 叙述来源 | 原始目标/背景或采用前控制，不是第二套 v2 可写队列 |
| `WORK_TASK_REPORT.md` | Project root | User/Agent-facing derived view | 按需 Phase/最终交付摘要；阅读视图，不是 v2 执行权威 |
| `PROJECT_HANDOFF.md` | Project root | Agent-facing derived view | 按需 continuation 摘要；阅读视图，不是 v2 执行权威 |
| `TASK_CONTRACT.template.en.md` | `runtime/EN/templates/` | Agent-facing | 真实 sub-agent task 的 contract |
| `SUB_AGENT_REPORT.template.en.md` | `runtime/EN/templates/` | Agent-facing | sub-agent 返回的结构化结果 |
| `PROJECT_HANDOFF.template.en.md` | `runtime/EN/templates/` | Agent-facing | 固定 recovery handoff 模板 |
| `WORK_TASK_REPORT.template.en.md` | `runtime/EN/templates/` | Agent-facing structure, user-facing output | 可用用户语言撰写的 report 结构 |
| `WORK_TASK_REPORT.template.zh-CN.md` | `runtime/CH/templates/` | 本地化参考 | 用于按需 report view 的中文措辞参考，或明确要求时的翻译 view |
| `DELIVERY_CHECKLIST.en.md` | `runtime/EN/checklists/` | Agent-facing | Final 或 phase delivery self-check |
| `MEMORY_WRITE_CHECKLIST.en.md` | `runtime/EN/checklists/` | Agent-facing | durable memory 或 rule writes 前的过滤 |
| `QUALITY_GATE.en.md` | `runtime/EN/checklists/` | Agent-facing | 通用 completion gate |

Release templates 是起点。真实 project artifacts 属于用户项目 workspace，不属于本 release repository。

当前状态库另记录 Project/Phase/Task 定义、操作与证据。业务交付物不同于报告和控制记录；成果所属、版本与复用资格由所选 Artifact 服务维护。项目实际产物不能存入安装代际。

## 有界运行流程

1. 读取当前用户目标、适用指令和实际目标对象。
2. 选择足够简单的工作方式，仅在明确需要时初始化。
3. 已有 MALTS 工作先核 discovery、binding 和当前任务。
4. 读取所选目标、计划、依赖、所需证据和不确定效果。
5. 解决实质不明确项，复用同范围必要步骤的既有授权。
6. 完成下一项有界结果，检查相应行为或内容。
7. 保存重要决定、检查点和实际结果，按需派生报告与交接。
8. 对照原始验收条件，保留失败、跳过和未知事项。
9. 判断实际经验信号，不自动写长期规则。
10. 持续完成必要工作，直到目标达到或出现实际停止条件。

MALTS 提供可恢复轮次，不延长上下文窗口，也不自动监视和保存每次对话。持久记录应对应实际效果与检查点。

## 上下文与连续性

在上下文耗尽、压缩、中断、执行者变化或未结协作可能丢失事实前，保留重要进度。接续须识别当前目标、准确任务版本、相关产物、失败检查、未知效果、写者及下一项具备条件的动作。

重新从 discovery、binding 和当前任务上下文进入。仅在确实相关时读取交接，不默认加载全历史，也不按时间选择历史 Session。聊天和当前证据不一致时核查实际状态；摘要不能证明未执行，也不能修复未结效果。

## 可选 Multi-Agent Scheduling

多 Agent 是可选择的职责分工，默认执行者仍是主 Agent。按工作价值、资源独立性与实际宿主能力选择零个、一个或多个协作者，不建立固定的角色流水线。

| 职责 | 参与方式 | 范围 | 责任 |
|---|---|---|---|
| 主控制端（Main Controller） | 必需 | 计划、协调、整合和最终判断 | 用户沟通、整体目标、资源与验收 |
| 规划者（Planner） | 可选 | 只读建议 | 拆分成果、依赖与优先次序 |
| 调查者（Explorer） | 可选 | 只读调查 | 结构、日志、模块或根因 |
| 执行者（Worker） | 可选 | 明确范围内修改 | 按合同完成实现 |
| 验证者（Verifier） | 可选 | 按授权检查 | 检验真实产物与交付声明 |
| 经验整理者（Memory Curator） | 可选 | 仅允许的候选记录 | 来源、适用条件和可检验方法 |

实际分工前形成可以审阅的目标、必要性、角色、输入、允许/禁止对象、资源、顺序、预算、模型约束、输出和验收合同。复用已经批准的同范围批次，不逐项再确认；缺少实质授权时仅暂停依赖动作。

角色不是模型能力或推理强度，遵循用户已经指定的模型和 effort。无法观察的实际身份如实说明，不能用配置标签冒充真实派发。协作者返回产物、检查和未解决项，主控制端在效果和宿主结清后负责整合与验收。

目录不同不能证明编辑器、服务、环境或设备资源独立。暂停、取消和进程退出分别核查，保留未知效果与累计消耗；新轮次不能视为免费重启。

## 任务契约与恢复

可执行任务应说明目标、输入、允许/禁止范围、依赖、资源所属、预期结果、验证方法、预算，以及实际适用的宿主或模型硬约束。控制端核当前定义版本和真实文件是否符合合同。

返回说明应包含实际产物、检查、失败与限制。超范围或没有依据的完成声明不能直接验收；先整合真实成果再判定。报告的正面措辞不是验收。

暂停任务只有在检查点、依赖、未决效果、宿主状态和预算允许时，才沿准确 Task/Run 接续。中断操作使用原身份对账。恢复产生新的 epoch 并保留已消耗额度，不复活旧 Grant、Host 或验收，也不恢复旧运行权威。

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

成果的内容、所属阶段、版本、来源和依赖分别记录。跨任务共享前核当前内容和资格；替代、失效或退役的成果保留历史解释，不能由旧链接自动升级为另一份当前成果。

报告面向阅读和交付，说明做了什么及其证据；交接面向接续，说明当前状态、未决项与下一步。它们按需从事实生成，保全用户手工内容。发布阅读视图时比较当前来源和目标前像，避免旧报告覆盖新状态。阅读副本修改后，旧hash不能认证新正文。

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

### Growth Routing Gate

验证完成、最终交付前，每个普通任务都评估一次无写入 L1 Growth Routing Gate。没有 signal 的琐碎工作保持静默（`NO_OUTPUT`）。非琐碎工作，或出现用户纠正、验证反转、恢复、失败、可复用方法时，输出简短且可见的 `LIGHT_REPORT`。重复/高影响证据、Phase 交付、长任务完成和交付失败返回 `RETROSPECTIVE_RECOMMENDED`；它只建议 Standard/Major review，不会自动执行。用户明确请求或已授权的 review 返回 `RETROSPECTIVE_AUTHORIZED`。

L1 只在当前上下文判断，不能创建 ledger、Phase、Session、Artifact、后台服务或 durable control 更新。L2 项目维护和 L3 系统晋升仍各自独立授权。仅写入报告不能替代面向用户的交付结果。适用的 Plan/Boundary/transaction/unknown-effect gate 必须先执行并可返回 `BLOCKED`；Growth 不能绕过它们。

成长从实际纠正、验证失败、恢复、反复问题或有效方法开始。轻量检查判断是否有必要深入；标准或重大复盘分析原因、适用边界与可改进的做法。普通成功且没有信号时保持静默。

经验候选包含事实来源、适用条件、建议动作、检查方式和停止使用条件。原事件可以支持提出候选，但不能同时充当“未来使用有效”的证明。后续任务需要符合条件、有可比结果和来源；失败、中性和不确定样本保留，反证或来源撤回会停止受影响的复用。

项目记录、经验试用和全局Skill/规则修改有不同授权范围。加密的原始证据不因此变得可公开或可用于成长；传播前需要用途检查和经审阅的派生来源。设计支持受控改进，不预设任何方法都必然有效。

## MALTS Memory Pipeline

MALTS Memory Pipeline 是 reusable lessons 的 durable growth path，独立于任何单一 external memory tool。

Pipeline：

1. 从 delivery、failure、user correction、verification 或 process friction 中观察 reusable lesson。
2. L1 分析保持临时；只有具备对应 L2 项目授权后才在本地记录。
3. 使用 `MEMORY_WRITE_CHECKLIST.en.md` 过滤。
4. 与已有 rules、skills 和 instruction files 去重。
5. 选择最窄 durable destination：project skill、global skill、`GLOBAL_MEMORY.md`、`AGENTS.md`、`CLAUDE.md` 或等价 tool instruction entry。
6. 只有在 external memory system 已配置、可写且适合时才使用它。
7. 如果 durable destination 不可用，保留 local candidate 并报告没有发生 long-term write。

一个经验只有在真实、可重复、有边界、可检查，并且预期复用价值高于维护成本时，才应成为 durable memory。

列举长期落点表示可能的审阅结果，不表示自动实现写入或授权。当前受保护证据在复用前核允许用途与经审阅派生来源；试用保留中性、有害和未知结果。

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

成本包括准备、执行、等待、整合、验证与修复，不能只计模型响应时间。多Agent分工的收益需要扣除协调和集成开销；读取范围变小也不能单由配置推断模型节省了多少token。

控制方法是读取当前所需材料、复用仍有效的证据、按风险选择检查和保持有限范围。预算记录累计消耗，不因恢复而补充。每轮以实际交付、必要决定、检查点或故障停止条件结束；整个目标完成后及时交付，不无限追加旁支。

## 安全与权限

授权取决于当前用户请求和实际动作。只读工作不修改项目；已有授权覆盖必要的同范围实施与验证。发布、真实 Provider 调用、委派或难以恢复的动作缺少权限时，在该依赖步骤前解决。

任务合同可区分只读调查、限定修改、新建、结构调整和破坏性效果；这些描述不是运行时 Grant 等级。实际 Grant 绑定主体、资源、效果、任务版本和预算。

有 Git 时核当前状态，保留用户修改和重要前像；没有 Git 时采用限定备份和可恢复补丁。凭据与私有证据不能进入公开输出。清理遵循宿主准确删除策略；盘点、旧候选名称和有利的完成标签都不产生删除权限。

## Unattended Continuation

无人值守或周期运行是单独授权的方式。记录目标、允许对象和效果、禁止行为、委派/模型约束、时间或轮次限制、停止条件、报告与恢复要求，以及实际接续机制。

长期项目存在不意味着 MALTS 自动安装定时器、监视上下文或授权未来工作。调度器及自动化宿主保留自己的权限与实际进程行为。新轮次不能补充已消耗预算；达到约定边界时停止，或提出必要的实质决定。

## Adapter 策略

| 宿主 | 入口与加载关系 | 安装选择 |
|---|---|---|
| Codex | 受管 `AGENTS.md`、原生 Skill 入口与可选 MCP | Install/Update `-Tool Codex` |
| Claude Code | 受管 `CLAUDE.md`、原生命令/Agent/Skill | Install/Update `-Tool ClaudeCode` |
| OpenCode | 受管 `AGENTS.md` 与原生配置/Skill | Install/Update `-Tool OpenCode` |
| DeepSeek Harness | `.dsh/MALTS_BOOT.md`、Harness 原生工作流/配置入口 | 独立生命周期，`-ToolRootDeepSeekDesktop` |

四端使用同一核心合同。Install/Update 的 `AllIncluded` 只选择前三端，不是四端快捷方式。沿用的 DeepSeek 参数名对应当前 `deepseek-harness` 身份；[安装说明](INSTALL.md)提供可执行选择示例。

MALTS 仅拥有标记区块，区块外属于用户。合并需幂等，保留个人内容，所属不明确时停止。各宿主重载后检查实际原生发现；CLI、Web 和 Desktop 验证不能相互替代。当前 DeepSeek 证据限 Windows Desktop 0.2.0-rc.2；GUI 模型取消仍未认证。

## 双语文档

英文与简体中文产品指南描述同一产品与同一状态，章节用途、命令参数、路径和限制保持对应。Agent 运行模板保留稳定机器字段，项目叙述保持原语言。

日常读取使用一种适用语言。结构同步仅检查标题和路径，不证明翻译语义质量。关键差异以实际实现为依据修正，并审阅两种语言。参见[语言模型](BILINGUAL_DOCS.md)。

## 系统发布边界

MALTS 作为 Agent work 的 portable operating system 发布：runtime rules、templates、checklists、adapter guidance、installation helpers 和 design documentation。Distribution package 应包含 reusable system definition，以及在 project environment 中安装或运行该系统所需的材料。

Project-specific state 有意位于 system distribution 之外。真实 project control files、work reports、handoff records、local retrospectives、generated packages、caches 和 runtime history 是具体项目创建的 execution artifacts，由产生它们的项目治理，而不是由 MALTS system definition 治理。

这个边界让系统能够跨机器、团队和 Agent runtimes 复用，同时清楚区分 MALTS operating model 和应用该模型到具体项目时产生的 records。

## MVP 实施阶段

此栏目保留历史实施次序，不作为当前待办队列：先明确目标、模板和清单，再封装共同工作流、接入原生工具、自动检查结构和安装，最后观察真实交付、恢复与经验使用。

后续版本增加生命周期事务、明确阶段/成果治理和当前任务服务；DeepSeek Harness 将工具适配扩展为四端。当前要求和完成由所选 Project/Phase/Task 及有效证据判定，不能由历史次序推出。版本历史见 [CHANGELOG](../../CHANGELOG.md)。

## 验收标准

验收判断约定结果是否在声明范围内可用：

- 目标、排除项、交付物和当前计划可追溯。
- 所选任务与依赖对应实际工作。
- 产物通过相关业务检查，失败和跳过检查明确说明。
- 中断/恢复保留当前状态、后续工作与不确定效果。
- 已授权分工具有真实宿主证据及控制端整合。
- 报告/交接保全手工内容，解释剩余工作但不成为权威。
- 经验复用具备允许来源、适用试用与撤回路径。
- 分别说明安装、工作区采用、实际宿主行为和整体计划验收。
- 四端具有安装入口，并明确真实资格限制。

安装成功、版本号、组件测试或旧回执不能同时证明上述内容。当前任务/阶段验证仅支持其声明范围；验收不能推出普遍提速或节省。

## Plan Recheck、Peer Task 与 Discovery Authority

当前 Phase 绑定实际计划及 SHA-256，任务绑定准确阶段/依赖版本。计划复核检查改变的目标、边界、输入与恢复条件，不提供权限，也不验收业务结果。已采用 v2 的工作使用阶段/任务服务；旧 `plan-recheck` 命令仅适用于其经验证的采用前合同。

原生 Peer Task 是宿主执行能力，不是新的 MALTS 项目层次。实际派发、模型/effort、结清和结果须符合审阅合同；原生 spawn、另一会话和受管 Worker 不能被当作同一种证据。

Discovery 使用工具准确 Boot 及返回的 registry/active-pointer 路径。机器级 `GLOBAL_BOOT.md` 不是当前发现输入；身份缺失或冲突阻断受影响运行操作。

## 当前任务服务机制

以下机制说明当前系统怎样落实前述原则；它们属于实现参考，日常使用从工作流进入。

### 职责划分与权威

模型解释目标、作业务判断并选择方法；宿主提供工具、权限、进程与身份能力；MALTS 维护状态、依赖、准入、预算、证据和恢复合同。三者各自的声明不能替代其他层的实际结果。

所选 v2 store 是执行事实的单一来源。CLI 和 MCP 经 `v2_service.py` 调用相同领域服务。Project/Phase/Task 定义使用 revision；Phase 绑定实际计划的 SHA-256；Task 依赖指定前置版本。旧 Markdown、报告和交接保持可解释，但不创建第二套可写队列。

Core Schema69 是当前精确读写格式，接口声明位于 `runtime/v2_runtime_contract.json`。早期开发库不能靠修改版本字段升级。已采用工作区的 binding 与 source-seal 用于识别采用边界，不能删除它们来恢复旧运行权威。

### 执行、并发与恢复机制

Grant 声明已有授权对应的主体、资源和效果。预算记录累计消耗；新 Run 或恢复不是新的额度。资源准入、lease 和 fencing 用于拒绝受管接口中的陈旧执行者。fencing 指执行者必须持有当前有效的代际或租约标识；它不对未接入这些接口的外部工具提供全局互斥。

操作先准备并绑定请求哈希，再持久保存 intent（即将执行的意图），最后 observe（观察真实结果）。回执缺失时保留 UNKNOWN。UNKNOWN 表示效果不确定，不能解释为失败、未执行或可重试。对账沿原操作身份继续，避免为了重试创建新 ID 造成重复效果。

受管 `create-file` 使用独占创建。Windows `update-file` 比较打开后的当前字节哈希，保全原文，写入后验证；冲突或不确定结果通过原身份处理。文件适配器证明其声明的文件结果，不证明无关网络请求或编辑器保存。

暂停、取消与进程静止分别记录。PAUSED、取消确认、空操作列表和 lease 到期都不能证明外部写者已退出。接替之前核对 Host、未决操作、检查点、epoch 和预算。备份恢复产生新的 epoch（恢复代际）；恢复后的隔离和对账防止旧 Grant、Host 与验收被自动复活。

### 完成判定与证据

每项验收 criterion 指定 description、hard、verification_method 和 minimum_evidence_level。`verification.begin` 在操作和 Host 结清后进入 VERIFYING，并阻止新执行。需要修改时用 `verification.rework` 保留旧证据但撤销其当前依据；小任务的 `task.accept` 使用同一检查边界。

证据必须绑定当前 Task 版本、当前 epoch 下已观察的操作、准确 criterion 与来源。证据等级 A–D 按合同比较：较低等级不得冒充独立验证或更高等级。`task-verify` 复核当前证明并保留历史；`NO_LONGER_PROVEN` 表示现在不能继续援引旧完成。

受保护正文存于 blob，描述符限定 owner、目标、敏感性、允许用途与保留规则。当前保护依赖 Windows 当前用户 DPAPI。加密不意味着脱敏，也不自动允许把原始内容用于 Growth。派生证据必须经明确审阅并保留来源链；来源撤销或到期停止后续复用。

### 协作、成果与经验

默认单 Agent。需要协作时，控制端分离职责、资源和验收，绑定真实 Host adapter、累计预算与可观察身份；Worker 交付结果，控制端在 Host 结清后验收。传输会话 ID 不是业务 Task、授权或 Run。并行产物存在不表示整合已经完成。

Artifact 的 owner、来源版本、关系和保留用途与文件路径分开。Shared 指经治理允许跨任务复用的成果；当前内容、资格和依赖闭包仍须验证。SUPERSEDED 或 RETIRED 成果可以解释历史，但不能被旧引用自动重定向为新成果或重新启用。

Growth 管理有来源的经验提案、限定试用、未来结果与撤销/退役。正面自评不构成有效方法；中性或有害结果保留。修改全局 Skill 或规则属于另一种授权范围，不能由试用 PASS 推导。

### 安装与接口取舍

工具自己的 `MALTS_BOOT.md` 指向不可变代际；discovery 核对 registry、active pointer、identity 和 VERSION。安装计划绑定精确来源与目标前像，隔离 preview 验证后再激活；原位补丁会破坏身份链。公共仓库是通常来源，可选 ZIP 用于离线交付。

精确 Schema 和哈希绑定提高可核查性，代价是升级、旧库采用和恢复必须显式进行。受保护证据减少意外传播，代价是当前跨用户恢复能力有限。持续保留恢复原文可支持解释和修复，但不保证磁盘空间固定有界；诊断清单不产生删除权限。

Skill 用有界路由及 `task`、`phase`、`artifact`、`recovery` 专题组织内容。按需读取降低一次进入所需的材料范围，但不能由配置推断模型实际只读取了该内容或节省了多少 token。

## 验证范围与限制

对应实现见 `tools/v2_state_store.py`、`v2_governance.py`、`v2_operations.py`、`v2_local_host.py`、`v2_acceptance.py`、`v2_evidence_derivation.py`、`v2_artifacts.py`、`v2_growth.py`、`v2_handoff.py` 和 `malts_lifecycle.py`。这些文件解释机制，不能单独替代执行证据。

已记录的验证包括领域/事务/权限/恢复检查、受管文件结果、原生任务与冷恢复、限定串行/并行配对、Growth 未来试用及安装/采用/备份恢复。不同层只支持自己的范围。一个完整的固定 A/C 配对记录了较低自动耗时和输入/输出量，同时工具项更多；B1 原观察 profile 失败仍保留，不能作为完整比较样本。Growth 的真实配对为中性，证明受控试用和停用，不能证明自动收益。

当前不认证总体成功率、普遍或跨宿主因果提速、真实费用/人工节省、Provider 内部请求总量、GUI 模型取消、任意 OS 写者的 fencing、跨用户 DPAPI 恢复或自治发布。对这些限制的保留是对证据适用范围的说明，不改变 Task 的实际验收标准。

操作方法见[使用指南](USAGE.md)；精确状态和错误合同见[状态合同](V2_STATE_CONTRACT.md)。
