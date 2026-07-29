# Capability 与 Skill 治理

本文定义 MALTS v1.0 Capability Registry 和 Workflow Router 的治理契约，同时固定此前 Skill 整理工作的安全边界。

## 1. 状态与目的

Registry 和 advisory Router 是已实现的 v1.0 组件。W3 引入 deterministic Catalog 生成、advisory Resolver、collision/dependency 检查，以及只能在明确 isolation root 内 plan/apply 的 native projection。事务 lifecycle 现已激活经过验证的 MALTS-owned runtime 内容与工具原生薄发现 projection；它不会使用这些组件移动、安装、更新、隐藏或删除第三方 Skill。

W3 component evidence 仍只覆盖 static 与 isolated 行为；后续 lifecycle 和真实工具 qualification evidence 是独立且带日期的证据。Router 始终只提供建议，MALTS 不是第三方 Skill package manager。

## 2. 一个物理源，一个元数据视图

一个 portable Skill 只能有一份经过审阅的物理事实源。Capability Registry 可以描述该事实源，但不能变成另一个保存 Skill 正文副本的目录。

Registry 可以引用：

- canonical source locator 和 revision
- normalized hash 和完整目录树 hash
- 工具兼容性与 adapter projection
- typed dependencies 和 conflicts
- provenance、review evidence 和 rollback reference
- lifecycle 与每工具 exposure policy

工具专属 overlay 继续使用由对应工具或安装器管理的实体目录。禁止把多个工具的整个 Skill 根目录互相链接；只有目标 runtime 确实需要时，才可以为审阅通过的单个 Skill 建立 projection。

## 3. 当前 Release 边界

在当前 v1.0 release 边界内：

- `skills/` 继续作为 MALTS 自有 Skill 的 canonical source。
- `adapters/skill-bridges/` 继续作为 MALTS 自有原生发现 bridge 的 source。
- 事务 lifecycle 只管理经过验证的 MALTS 内容与 MALTS-owned 薄 projection。
- 第三方 Skill 的发现和 lifecycle 继续由用户的 Agent 工具及其现有安装机制负责。
- 用户 payload 包含验证所需的 Registry Schema；生成后的 Registry 与本地验证 example 属于用户或项目本地状态，不属于安装 package 内容。

只有完整 installation metadata 与已验证 lifecycle evidence 绑定时，文档才可描述 MALTS-owned projection 已激活；不得暗示生成式 external Catalog state 或 Resolver 会执行 Skill，也不得暗示 MALTS 管理第三方 Skill lifecycle。

## 4. 目标治理分层

v1.0 目标把五类职责分开：

1. Physical source：一份经过审阅的 Skill 正文。
2. Registry metadata：identity、provenance、compatibility、risk、exposure 和 lifecycle。
3. Tool projection：目标工具原生发现需要的 entry 或 overlay。
4. Advisory Router：基于已登记 capability 给出可解释建议。
5. Transactional manager：针对已验证 MALTS release 内容、另行门禁的 journaled install、update、repair 和 uninstall 层。

这些层已按顺序交付。W3 实现 Registry/Resolver source component 和 isolated native-projection precondition；W6/G3 随后为 MALTS-owned 内容激活经过验证的 transactional lifecycle。Router 始终只提供建议，两个层都不授权第三方 Skill lifecycle 管理。

## 5. Registry 数据契约

机器可读契约是 `tools/capability_registry.schema.json`。每个 Registry entry 必须能够回答：

- 这是什么 capability，由谁拥有？
- 内容来自哪里、哪个 revision、对应哪个 tree hash？
- 兼容哪些工具和平台？
- 需要哪些 adapters 和 dependencies？
- 已经完成什么审阅或验证，时间是什么？
- 每个工具可以向 catalog 暴露什么？
- 如何恢复上一个状态？

应优先使用中央元数据，不应向每个第三方 Skill 强制注入 `skill.yaml`、`VERSION`、`CHANGELOG` 或其他 MALTS 管理文件。除非上游 owner 明确采用该契约，否则上游内容应保持 byte-stable。

### 5.1 Capability Descriptor 与 External Sidecar

MALTS-owned Skill 使用一组相邻文件自描述：`skills/<skill-id>/SKILL.md` 继续作为 canonical body，`skills/<skill-id>/capability.json` 提供 typed metadata。Descriptor 不得替代或复制 Skill 正文。

External-owned Skill 只能由 operator-state sidecar 表示，记录 identity、source hash、tool scope、risk、evidence 和 user alias。External sidecar 可以授权 discover-and-route，但不能授权 MALTS-managed install、update、projection 或 delete。

Capability Catalog 必须从这些输入与 source hash 生成，不能手工维护，也不能形成第二个可编辑 source tree。

## 6. 来源信任、审阅状态与执行风险

以下字段彼此独立：

- `source_trust`：对来源和 provenance 的可信程度。
- `review_status`：真正完成了哪些静态或 runtime 审阅。
- `execution_risk`：脚本、写入、网络、凭据、destructive 操作或自修改造成的影响。

第一方 source 仍可能有高 execution risk。低风险的纯文本 Skill 仍可能来源不明。不得用单一 `trusted` Boolean 替代这三个维度。

## 7. 暴露与 Catalog 门禁

物理可移植不等于允许向所有工具显示。每项 capability 都必须有每工具 exposure 决策。

修改共享 Skill source 或 projection 前，维护者必须记录每个受影响工具的预期可见集合，并与修改后的实际 catalog 对比。出现以下情况时必须阻断：

- 未经审阅的 catalog 新增或移除
- 存在优先级不明确的重复语义 capability
- 暴露 protected、incompatible 或 rejected entry
- catalog 扩张超过已审阅预算或范围
- 变化无法追溯到 Registry entry 和 winner decision

只比较 catalog 数量不构成证据。验证必须检查名称、来源、projection 和实际 precedence。

## 8. Advisory Router 契约

第一阶段 Router 是只读且可解释的。输出包括：

- 推荐 operating mode
- 候选 capabilities 及其匹配原因
- 所需授权和 verification gate
- 影响建议的 evidence 或 uncertainty
- 未选择更重 workflow 的原因

Router 不移动目录、不修改 discovery setting、不隐藏 Skill、不安装 package、不派发 Agent，也不绕过用户确认。主控的最终责任保持不变。

### 8.1 生成式 Catalog 与 Resolver

`tools/capability_router.py` 在生成 operator-state Catalog 前验证 descriptor、required file、capability dependency、package variant、name、alias 和 projection target。生成输出的目标位于 MALTS package root 内时必须拒绝。

Collision review 覆盖 exact/declared/alias name、target path、nested-suite exposure、plugin-cache exposure，以及可识别的 MALTS-owned bridge migration candidate。未知工具 inventory 必须保留为 unclassified，不能据此声称 clean。

Resolver 的选择必须 deterministic 且 advisory。它按 tool support、exposure、installed/effective inventory、collision block、permission、risk、dependency、task intent/type、mode 和显式 user override 过滤。输出必须记录 `execution_performed: false`；native invocation 与 authorization 继续独立。

### 8.2 隔离 Native Projection

`tools/native_skill_projection.py` 从 canonical body 生成 tool-native `SKILL.md`，只修改 projection front-matter name，并只为 Codex 生成 `agents/openai.yaml` metadata。每份 ProjectionManifest 绑定 source revision、source/descriptor hash、package variant、target tool/version、adapter version、generated hash、dependency、ownership 和 creator。

只有 target root 被明确 isolation root 包含时才允许 apply。只有 name、marker、capability binding 与允许文件集合全部吻合的 MALTS bridge 才能替换。复制到隔离环境内的旧 bridge 在 postvalidation 成功前保留用于 rollback，成功后立即删除。未知、已修改或含额外文件的 target 必须 fail closed。

该直接 component apply 路径仍只允许 isolation root。生产工具 projection 由 journaled lifecycle 从已验证的闭合 release 执行，并且只有 active-generation、installation-registry、projection 与 ownership metadata 完整一致绑定时才通过验收。

### 8.3 W3 验证边界

W3 evidence 本身只覆盖 schema/static validation 与 isolated filesystem behavior；它关闭 G2 Resolver component slice，并只证明 G3 precondition。后续 W6/G3 evidence 已激活并完成 lifecycle fault testing，另行授权的 G4 rows 记录了带日期的真实工具行为。后续结果不会把 W3 wrapper 变成 runtime proof；任何当前 discovery、invocation、behavior 或 effective-model 声明都必须引用准确的带日期 evidence 与绑定 installation metadata。

v1 Registry、Descriptor、Sidecar 与 ProjectionManifest contract 必须在首份 active operator state 之前冻结。因为当前不存在 live prior Catalog 或 ProjectionManifest，W3 不虚构 v1-to-v2 live migration。

## 9. 第三方 Skill 安装位置判断

安装位置判断是轻量的安装前决策，不是新的 Skill、Registry service 或 installer。安装前，当前 Agent 检查候选 `SKILL.md` 和附带文件，并按以下顺序判断：

1. 用户明确指定的位置或工具范围优先。
2. 通用可移植 Skill 默认使用 `~/.agents/skills/<skill-name>`。
3. 工具专属 Skill 默认使用对应工具自己的 root：`~/.codex/skills/<skill-name>`、`~/.claude/skills/<skill-name>` 或 `~/.config/opencode/skills/<skill-name>`。
4. 兼容性仍不确定时，使用当前工具自己的 Skill root，不假设它可以共享。
5. 说明判断结果，等待写入授权，再使用现有安装器。

安装位置判断不授权跨工具暴露、重复复制、更新、删除或无人值守 lifecycle management。

### 存量 Skill 整理

整理已经安装的 Skill 时，必须先为每个发现项确定归属，再修改位置。最终决策账本中的未分类项必须为零。

- 只有在 `SKILL.md`、附带文件、引用、依赖和工具假设都已审阅并确认可移植后，通用 Skill 才能共享。
- 工具产品自身管理或随工具安装的 Skill 必须保留在产品管理的 root，避免未来产品升级形成重复所有权。
- 工具专属、兼容性不确定、引用损坏、存在依赖风险或同名冲突尚未解决的 Skill，保留在原工具 root。
- 审阅通过的共享 Skill 在 `~/.agents/skills/<skill-name>` 只保留一份 physical canonical source。只有当某个工具不会发现该 root 时，才为单个 Skill 增加所需 projection；禁止链接整个 root。
- 被替换的副本必须进入可逆 quarantine，记录 source hash 和 rollback action，并在修改后检查 Codex、Claude Code、OpenCode 的 catalog 和代表性实际调用。

内容 byte-identical 是有价值的证据，但不能单独证明跨工具兼容；审阅还必须明确预期 exposure set。

## 10. 更新与 Lifecycle 安全

第三方更新默认只检查。Apply flow 必须具备：

1. 解析 source 与 revision
2. 隔离 staging
3. content 与 metadata diff
4. compatibility、dependency 和 risk 检查
5. 明确 apply 授权
6. 修改前 snapshot
7. 修改后 discovery 与 invocation 验证
8. 已测试 rollback reference

第三方 Skill 无人值守更新不属于 v1.0 初始范围。Quarantine 必须可逆；永久删除需要单独授权和观察证据。

## 11. 公开投影与私有状态

公开 MALTS artifacts 可以包含：

- 本通用契约
- Registry Schema
- 占位示例
- 通用 lint 和 regression rules
- canonical MALTS capability descriptor 与 isolated projection source/test

公开 artifacts 不得包含生成后的 inventory、用户路径、工具 catalog、conflict table、source lock、环境 hash、backup location、quarantine record 或生成后的 Registry state。公开 example 只能使用 package-relative locator 和不可执行占位值。

## 12. 采用顺序

稳定顺序是：

1. 完成可逆的物理源稳定化
2. 观察 discovery 与 invocation 行为
3. 引入 Schema 和 lint 契约
4. 从已验证证据生成私有只读 Registry projection
5. 增加 source lock 与 compatibility lock
6. 增加 advisory Router
7. 评估 false positive、catalog drift 和操作成本
8. 另行决定是否需要 transactional manager

任何阶段都不引入第二个物理 Registry tree。

## 13. 验收标准

治理层只有满足以下条件才可验收：

- 一项 capability 的正文只有一个 canonical physical source
- Registry entry 可以从 evidence 重建并通过 Schema validation
- source trust、review status 和 execution risk 始终分离
- 每个工具的实际 catalog 与已审阅 exposure set 一致
- Router 输出保持 advisory、可解释且不绕过授权
- update 和 rollback 操作经过 staging 且可恢复
- 公开发布检查会拒绝生成后的操作环境状态和机器专用数据
- 英文和简体中文治理文档保持结构同步
