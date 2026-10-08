# MALTS 生命周期

生命周期引擎安装经核验的 MALTS 内容并保留恢复边界。本文沿用安装、诊断、预览和工作区的既有栏目，依据当前 **2.0.0** 实现修订。

## 核心不变量

安装与项目工作有不同生命周期。安装负责不可变代际、所选投影、注册表、审阅计划和事务；项目服务负责目标、阶段/任务、成果、证据与恢复。安装不静默采用或重建项目。

- 准确安装载荷来自一份经核验来源。
- 注册表/活动指针及所选工具 Boot 标识当前版本。
- 计划绑定来源/目标事实与 SHA-256，执行拒绝漂移。
- 未选工具根和用户所属内容保留。
- 活动代际是运行输入，不是编辑工作区。
- 快照与未结事务保留恢复用途。

当前版本 **2.0.0**；同版本文档修订仍有独立内容身份。

## 来源模式

| 来源 | 用途 | 核验 |
|---|---|---|
| 已审阅仓库 | 常规安装/更新 | VERSION、MALTS_RELEASE.json、准确清单、源树身份及拓扑 |
| 已核验解压包 | 明确固定/离线输入 | 闭合 release/artifact manifest、清单与哈希 |

ZIP 是第二种来源的交付形式，不自动下载，也不免除核验。后续 main 文档修订和原标签 ZIP 可以同为 2.0.0，但准确树身份不同。

## 语义化版本身份与迁移

稳定身份使用 `malts-v<version>`，预览身份使用合同声明的预览后缀。封包器与生命周期使用同一身份合同；已安装字节完全相同时可返回 `NO_OP`。相同版本的不同字节不能手动覆盖。

明确的同版本修正通过当前 v2 `finalize` 保全目标前像并事务安装经核验的新身份。这是经审阅归并，不是自动清理，也不是自行添加补丁版本的理由。历史身份和回执保持真实。

## 操作

| 操作 | 用途 |
|---|---|
| install | 从核验来源首次激活 |
| update | 激活所选核验更新 |
| repair | 使用适当可信来源修复所选投影 |
| finalize | 保留前像的明确同版本归并 |
| uninstall | 仅移除计划内 MALTS 所属适配/状态 |
| recover | 检查并结清中断生命周期事务 |

`Invoke-MALTSLifecycle.ps1` 提供 Plan、PreviewPlan、Execute、Recover、Inspect、Scan、Doctor、DoctorRepairPlan。构建计划前查看当前帮助；这些操作不产生发布或项目迁移授权。

## 先审阅计划

Install/Update 在激活前保存计划，说明来源、所选根、代际、写入/移除、所属分类、快照及后置检查。Execute 必须提供准确计划路径和输出哈希。

通用入口 `Plan -Apply` 仅保存计划，`Execute -Apply` 执行审阅事务；PreviewPlan 同样区分计划与执行。保留事务 journal，删锁或改计划不是恢复。

四端流程见[安装](INSTALL.md)和[更新](UPDATE.md)。AllIncluded 仅选择三端；Harness 使用独立生命周期/工具根以及保留参数 `ToolRootDeepSeekDesktop`。

## 预览验证

预览使用新的明确根，与源码、活动安装、正式生命周期/工具根及保护对象分离。执行前审阅计划路径和隔离宿主根；隔离失败不能退回生产根。

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 -Command PreviewPlan `
  -PreviewRoot '<new-absolute-preview-root>' -RepositoryRoot (Get-Location).Path `
  -ProtectedRoot '<real-lifecycle-root>' -Tool codex,claude-code,opencode `
  -OutPath '<new-preview-plan-path>' -Apply
```

Harness 单独预览使用 `-Tool deepseek-harness`。保存计划不执行预览；原生工具调用、投影检查和模型行为属于不同证据，分别说明实际观察层。

## Doctor 与 Repair 信任

Doctor 只读评估信任与漂移，报告期望/观察位置、严重度和核心信任，不修复、不删除、不调用模型。派生投影漂移与载荷/注册身份被改变需要不同信任处理。

DoctorRepairPlan 是独立审阅准备；建议不是可执行权限。Repair 使用准确可信来源，仍走哈希绑定执行、快照及后置检查。

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 -Command Doctor `
  -LifecycleRoot '<existing-lifecycle-root>' -ToolRootCodex '<codex-config-root>'
```

提供共享该生命周期的全部实际根。Harness 使用独立生命周期和 `-ToolRootDeepSeekDesktop`，见[安装](INSTALL.md)。

## 版本与 Boot Pointer

各工具读取相邻或指令声明的准确 `MALTS_BOOT.md`，MALTS_ROOT 指向不可变代际。解析 Boot 和 discovery 返回的权威路径，不能猜活动指针或依赖历史绝对路径。

公共入口抑制字节码写入，示例仍用 `python -B`。代际中不生成缓存或业务输出。安装后重载宿主并核真实 Skill/MCP 发现，不能假设旧进程已经加载新字节。

## 有界 Audit 保留

生命周期审计保存当前活动绑定、有界近期成功、失败/恢复包及月度汇总，未结恢复事务保留。准确名称/哈希绑定的保留规则拒绝未知内容、reparse 和输入变化。

该策略不限制全部项目证据或安装备份。另行审阅证明无用途之前，恢复快照可能持续占用空间；不能改删历史字节来迎合新说明。

## 恢复与残留

核原事务以及实际 registry、pointer、代际、投影和快照，遵循引擎当前恢复结论。当前 v2 激活恢复保持在 v2 中，不恢复旧运行写入权威。

UNKNOWN 表示效果不确定，依赖执行前沿原操作对账。

Scan 只盘点残留，不产生删除权限。保留活动安装、状态/binding/seal、未知效果、原验收及必要备份。依宿主/用户策略核所属、引用和替代恢复方式；可恢复处置失败不能升级删除。

## Workspace Phase And Artifact Lifecycle

### Phase 边界与状态

阶段定义有限目标、排除项、验收和实际计划引用；任务绑定准确阶段/版本与依赖。实质修订更新受影响合同和绑定；审阅本身不是执行权限或业务验收。关闭任务不完成整个项目。

### 跨控制一致性与恢复权威

已采用工作区使用有效 v2 状态库。历史 Markdown 保留来源，不是第二套可写控制。查询 workspace、governance-context、task-queue 和准确 context。保留未知效果和外部写者证据；PAUSED 本身不证明进程停止。

### Artifact 登记与所属

成果的所属、版本、内容身份、来源和保留规则与路径分开。当前共享核内容/资格和依赖；替代或退役记录解释历史，不自动指向新内容。

### 修改、关闭与恢复

使用当前服务与经审阅版本。验收前结清注册效果和受管宿主，仍需独立业务检查。恢复产生新 epoch，对账后续工作、预算、资源与效果，不复活旧 Grant 或 Host。

### 兼容与非目标

采用前保持原经验证合同。采用是保留原数据/source-seal 的明确操作；旧重组命令不拥有已采用状态。普通进入不初始化、迁移、起守护进程或扫描全历史。见[状态合同](V2_STATE_CONTRACT.md)。

## 普通启动 Discovery

```powershell
$runtime = '<MALTS_ROOT-from-selected-tool-boot>'
python -B "$runtime/tools/malts_lifecycle.py" discover --tool-root '<selected-tool-root>'
```

核 registry、active pointer、generation identity 和 VERSION 一致。Discovery 只读，不使用机器级 GLOBAL_BOOT.md。随后核所选工作区绑定和任务上下文。见[快速开始](GETTING_STARTED.md)。
