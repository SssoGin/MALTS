# 能力与技能治理

Skill 描述方法，能力描述宿主或组件能提供什么，暴露决定哪些内容可被发现，授权决定哪些效果可以执行。MALTS 分别记录这些决定，避免将来源可见或路由建议当作扩大权限的依据。当前版本：**2.0.1**。

## 1. 状态与目的

能力治理解释工作流可使用什么、来源是否经审阅，以及原生暴露与执行权限的区别。适用于整个产品，当前 **2.0.1**，不承担第三方包管理。

不作这种区分时，目录可能成为第二套运行规则：复制的 Skill 与原文漂移，显示名被误当成已安装实现，或高分方法被视为已授权。治理保留来源身份，使审阅和暴露决定能够在产生效果前被核查。

Registry/router 工具与 v2 执行服务解决不同问题。元数据标识可复用内容及声明条件，Router 建议有资格的方法，任务服务约束当前版本、Grant、预算和效果/恢复边界。登记能力不创建 Task，也不产生 Grant。

对应实现见 [Registry Schema](../../tools/capability_registry.schema.json)、[Descriptor Schema](../../tools/capability_descriptor.schema.json)及 [Router](../../tools/capability_router.py)。这些证明 schema/元数据行为，原生模型执行另行验证。

## 2. 一个物理源，一个元数据视图

可移植 Skill 保持一份经审阅物理来源。Registry/catalog 引用身份、版本、哈希、兼容和暴露，不复制实现形成竞争仓库；轻量原生 MALTS 入口解析共享运行时。

物理来源是经审阅 Skill 目录及其实际文件。MALTS 所属内容的 descriptor 声明身份、触发条件、输入/输出、权限、依赖和工具元数据；生成 Catalog 将这些声明与来源哈希及暴露条件结合。它们不应另造 Skill 正文。

轻量发现桥是服务于宿主索引的派生内容，指向标准来源。目录/front-matter 使用 malts- 前缀，显示元数据描述用户工作流。来源和桥接身份均须核：descriptor 有效不能证明旧原生桥仍指向它。

第三方 sidecar 不修改作者 Skill，保留上游所属和可更新性，代价是兼容与审阅证据须独立维护。上游文件仍在时，sidecar 也可能已经过期。

## 3. 当前发布边界

分发提供标准工作流、元数据 schema、lint/router 工具、原生投影和当前任务服务。能力声明或配置不是实际宿主行为或用户授权。见[概览](SYSTEM_OVERVIEW.md)。

## 4. 目标治理层

分开物理来源、元数据、审阅/信任、宿主兼容、暴露和运行授权。v2 Grant 绑定主体/资源/效果，Skill 提供方法；路由器不能覆盖宿主策略或当前任务合同。

| 层次 | 所回答的问题 | 相关身份 |
|---|---|---|
| 来源 | 哪些字节实现方法？ | 来源版本、文件/树哈希 |
| Descriptor/sidecar | 声明什么、由谁拥有？ | capability_id、skill_id、来源 |
| 兼容 | 所选宿主能否使用该形式？ | 工具/平台/协议约束 |
| 审阅与风险 | 检查了什么、可能产生何种效果？ | 审阅状态、执行风险、证据引用 |
| 暴露 | 此处是否应发现该能力？ | 工具暴露策略和投影 |
| 执行 | 此主体现在能否执行该效果？ | 当前 Task/Grant/预算/准入 |

各层结论可以不同：可移植只读方法可能有 Catalog 资格，但未暴露给某宿主；可见更新工作流可能需要当前调查尚未允许的写权限。运行时必须使用实际当前授权，不能继承暴露标签。

## 5. Registry 数据合同

Descriptor 说明来源及声明的适用性/依赖；来源信任、审阅和执行风险分开。准确字段见 tools/capability_registry.schema.json、capability_descriptor.schema.json，不由叙述推出新字段或权限。

### 5.1 Capability Descriptor 与 External Sidecar

原生 descriptor 描述所属内容；external sidecar 记录第三方来源和兼容，不改其文件。合同见 tools/external_capability_sidecar.schema.json。

Registry 外层包含 schema_version、registry_version、design_status、registry_scope、generated_at 和 entries。条目分别描述身份、内容、接口、兼容、审阅、暴露、路由和生命周期。Schema 采用闭合字段，未知字段不能静默添加权限或含义。

| 字段组 | 用途 | 分开记录的原因 |
|---|---|---|
| id/skill_id/name/declared_name/aliases | 稳定身份与检索 | 显示别名不是另一份实现 |
| source/content/descriptor | 位置、版本与哈希 | 文件存在不检测内容变化 |
| interface/dependencies | 输入、输出及依赖 | 方法匹配仍须满足依赖 |
| compatibility/adapters/package_variants | 宿主、协议与分发范围 | 可移植不证明原生加载 |
| source_trust/review_status/execution_risk | 来源、检查与可能效果 | 可信来源不等于实际安全执行 |
| exposure_policy/routing | 可见性与建议匹配 | 排序不授权执行 |
| lifecycle/verification/evidence_refs/rollback | 更新、检查与恢复 | 须标识证据和撤回路径 |

历史设计的 Registry example 使用原 design_status 和占位哈希，属于维护参考，不包含在用户载荷中，也不是当前机器清单。实际 Catalog 应从所选包和经审阅外部 sidecar 生成，记录准确来源版本与生成时间。

外部 sidecar 包含 sidecar_id、capability_id、declared_name、ownership、skill_path、source_hash、capability_tags、tool_scope、risk_class、verified_at、evidence_refs、user_aliases、lifecycle_policy。其来源位置属于本地操作状态，不应将机器路径公开为可复用包元数据。

## 6. 来源信任、审阅状态与执行风险

可信来源不证明行为安全，审阅方法不授权效果。保留当前来源身份和允许用途；敏感证据需要经审阅来源链，不能重新贴成公开或 Growth 标签。

审阅证据应说明检查对象：解析/schema、来源哈希、静态合同、原生发现或实际任务行为。static-reviewed 不能仅因安装成功提升为 runtime-verified。内容或相关宿主配置变化时，重核依赖该输入的检查。

风险描述可能效果，而非发布者声誉。第一方安装器可调整配置，因此需要计划/前像检查；第三方参考资料可能只读。按所选路径核真实所需权限和禁忌条件；凭据与受保护证据进入 Prompt/Catalog 前须核用途及范围。

来源撤回、审阅失效或兼容失败会排除受影响复用。保留条目解释历史与保持资格不同，旧来源或较高建议分不能恢复已撤销决定。

## 7. 暴露与 Catalog 门禁

只暴露当前有资格且兼容的内容。禁用、撤销或不兼容内容继续排除；排序不能使其获得资格、安装或执行授权。

## 8. Advisory Router 契约

Router 对有资格候选排序并解释，不调用 Skill、不改发现、不授权或验收。当前任务工作流选择 task/phase/artifact/recovery 专题，只读相关合同。

### 8.1 生成式 Catalog 与 Resolver

生成元数据是来源视图，解析准确当前身份和哈希。

### 8.2 隔离 Native Projection

声明所属与输入身份，在所选隔离配置中核原生发现。

### 8.3 W3 验证边界

静态组件/投影、安装和真实原生任务各自支持自己的范围；历史 W3 不扩写成完整宿主资格。

路由请求说明 tool、task_intent、task_type 和 mode，也可提供 authorized_permissions、required_capabilities、installed_capability_ids、exposed_capability_ids、blocked_capability_ids、max_risk、user_override。这些是建议资格与匹配的输入，不是新授权记录。

Resolver 检查兼容、生命周期/审阅条件、风险、权限、依赖和禁忌。被排除条目保留 missing-dependency、task-mismatch 等原因，再按任务、触发词和模式匹配对有资格候选排序。user_override 仅表示资格范围内偏好；指定候选仍不合格时，不强行选择。

结果包含 selected、no_skill_needed、candidates、authorization_preserved、execution_performed=false。score 是排序量，不是成功概率、独立审阅或安全评分。消费者在产生效果前仍须解析真实来源并通过相应执行准入。

生成 Catalog 使用 capability_router.py generate，传 --malts-root、--source-revision、--package-variant、--generated-at、--out；resolve 使用 --catalog、--request 及可选 --out。生成文件属于包外操作状态。生成命令写输出，不安装 Skill，也不调用 Provider。

## 9. 第三方 Skill 安装位置判断

例如，经审阅的 Codex 可移植来源可位于 `~/.agents/skills/<skill-name>`，兼容和加载仍须核验。根据实际宿主加载规则和明确用户意图选择，不将可移植来源静默复制到所有工具。MALTS 生命周期仅拥有自己的投影。

### 既有 Skill 归并

迁移/移除前核身份、用户修改、引用及恢复；catalog 成员身份不产生清理权。

放置前先分类真实内容：可移植方法、工具原生命令、插件工作流或生成桥。核所选宿主的加载方式，以及已有安装是否拥有同名对象。同名不同正文需要明确来源决定；随意改名可能破坏原生元数据或依赖。

归并前保留本地修改、权威来源身份和旧位置引用，再决定是否移除重复内容。哈希相同仅证明观察时字节一致，不证明不存在后续更新所属。插件会重新生成文件时，再复制到手工维护根可能造成长期分叉。

MALTS 投影/生命周期管理声明所属文件，不接管其他插件或用户 Skill。第三方安装和删除独立遵循宿主及用户授权，不由路由建议推出。

## 10. 更新与生命周期安全

保全标记块外个人内容，使用核验来源、审阅计划和事务更新；重载宿主并核实际发现。Codex、Claude Code、OpenCode、DeepSeek Harness 保持各自加载约定。见[生命周期](LIFECYCLE.md)。

## 11. 公开投影与私有状态

仅发布有资格的可复用内容，不包含凭据、用户配置、任务库、journal 和原证据；暴露不授权复制私有状态。

## 12. 采用次序

核实际安装/工作区，选择所需工作流，检查当前来源和宿主能力，在已有权限内准备审阅动作，验证实际结果。不因建议自动采用、安装插件或派发 Agent。

## 13. 验收条件

分别核来源身份/schema、依赖闭包、当前资格、所需原生暴露和实际操作；说明缺失/不可用检查。请求模型/effort 不等于实际执行身份。全局 Skill/规则修改另有范围；中性/有害 Growth 结果仍保留。

可审阅能力结果应说明来源版本/哈希、声明接口、所选工具/配置、暴露结果、已做检查及不可用检查。确认可用前核冲突或缺失依赖；Schema 解析或桥接发现只验收合同的相应部分。

运行能力证据另区分不支持、Provider 未配置、配置未验证、继承/静态绑定及实际有效观察。分类器读取已有证据，不产生 Provider 调用或多 Agent 行为结果；即使满足前置，g4_status 仍为 NOT_RUN。有效并发上限来自观察配置，不能由目录数量或请求模型名推断。
