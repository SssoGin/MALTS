# MALTS 状态与服务合同

状态合同将目标、任务版本、权限、操作、证据和恢复绑定所选工作区。CLI 与 MCP 经不同宿主权限界面调用同一领域服务。当前实现：**2.0.1**。

## 1. 格式、入口与权威

当前 Core application ID 为 1296125012，只读写 Schema69；CLI interface 为 1，MCP application interface 为 7。`runtime-contract --root` 核对包内声明与静态代码常量，`capabilities` 返回加载的合同。声明一致不证明运行行为。跨版本开发库不自动升级。

原生 v2 状态根需显式选择；已采用工作区通过 `runtime/v2_binding.json` 验证 store、epoch 和来源封印。binding 无效或缺失不能回到旧写权。状态查询只读，控制端 request 默认 dry-run。实际能力合同以当前 `capabilities` 与服务实现为准。

## 2. 实体和版本

| 实体 | 责任 |
|---|---|
| Project | 原始目标、当前版本化目标和全局验收 |
| Phase | 阶段目标、in_scope/out_of_scope、criterion 与精确计划哈希 |
| Task | 可验收目标、scope、revision、依赖、执行状态 |
| Run / Host | 检查点和一次执行/派发身份；与传输会话分开 |
| Grant / Budget | 已有授权的资源/效果/主体和累计额度 |
| Operation | 请求哈希、租约、epoch、intent 与 observed/UNKNOWN 效果 |
| Evidence / Artifact | 验收依据、原文/派生来源、owner 与成果关系 |
| Growth | 提案、试用、未来结果与撤销/退役 |

Phase 定义绑定当前 Project revision、实际 plan_ref/plan_sha256。Task scope 是 Phase in_scope 的子集；每份 Task revision 绑定准确 Phase revision。计划或验收语义变化须通过正式 revision 和相关依赖重绑定，不能直接编辑数据库。

定义和观察具有不同生命周期。修订任务改变意图与条件，旧操作仍记录原版本下请求/执行的工作。不能仅改标签将证据转给新含义。

阶段所属将任务版本绑定当前阶段版本和计划，依赖绑定准确前置版本。发生变化时，先核受影响绑定和剩余工作，再准入新效果。与总读最新行的平面队列不同，该关系使结果实际使用的版本可检查。

叙述内容可在机器库外，例如真实计划文件，但适用版本绑定其字节。哈希核身份，不核业务充分性；控制端须分别审阅计划/条件与服务字段验证。

## 3. Task 与操作状态

Task 状态包括 READY、RUNNING、VERIFYING、WAITING、PAUSED、RECOVERY_REQUIRED、COMPLETED 和 CANCELLED。具体转换由服务前置条件决定，不靠标签推导可执行性。Task 修改只对可修订状态执行；未决效果先对账。

Operation 准备绑定 Grant、actor、resource、effect、parameters、request_hash、lease 和 epoch。提交 intent 后效果可能发生；observed 记录已知结果，UNKNOWN 保持不确定。prepared 操作不能作为已执行证据。重放要求相同身份与内容；不得用新 ID 重复未知效果。

操作次序区分准备与允许产生效果：

```text
PREPARED -> INTENT_RECORDED -> OBSERVED  （已知成功观察）
                            -> FAILED   （已知报告失败）
                            -> UNKNOWN  （效果仍不确定）
```

仅保持 PREPARED 的请求可取消为未执行。提交意图后，取消不能消除效果发生可能。已知失败仍需实际观察，不是普遍回滚证明。UNKNOWN 保留原操作，并使受管 lease/资源保持隔离直至对账。

相同重放可返回历史判断而不再执行效果，应核请求身份与预期哈希，不能换主体/参数或新 operation ID 作为重试捷径。受管 create/read/update 适配器自行处理意图与观察，调用者不应先为其提交不相关手工意图。

## 4. 授权、预算与并发

MCP 的 project、actor、authority 等 Host-bound 字段由配置提供，客户端不能覆盖。只读 endpoint 不具有写动作；write-enabled endpoint 仍逐项执行服务检查。授权引用只是来源记录，不认证用户身份，也不自行扩大范围。

预算维护累计消费，恢复不补充额度。Host dispatch 还受能力、预算和资源准入约束。租约和 fencing 只约束受管消费者；任意外部编辑器/进程须另行核静止。

准入将身份与效果相连：当前任务版本、主体准确 Grant、资源/效果、依赖、操作预算和当前资源身份。提交意图产生 epoch/fence lease，执行适配器使用前重新核 token 与真实资源；传输连接本身不提供这些事实。

预算统计已提交意图并保留累计使用。新 Run、改呈现或恢复备份都不能清零；额度修订是具有当前前置的明确审阅策略变化，也不能抹去已有消耗。

Lease 绑定所属、epoch、fence、到期，续租是明确动作。到期阻止旧受管执行，却不证明外部进程停止或效果撤销。共享编辑器/服务/设备须另有实际写者边界。

## 5. 文件适配器

`operation.create-file` 独占创建，不能覆盖现有文件。`operation.read-file` 需要 prepare parameters 的准确 `tool='read-file'` 和 granted relative `path`；读取也可产生控制记录，因此不等同普通只读上下文。

Windows `operation.update-file` 需要 `tool`、`path`、`content`、`expected_sha256` 和完整 `preimage_policy`。原文受保护保全；当前字节和写后结果均核查。冲突/UNKNOWN 通过 `operation.reconcile-update` 或经新范围授权的 repair plan 处理，不能盲目换 ID。

| 适配器 | 目标规则 | 准备/结果边界 |
|---|---|---|
| create-file | 准确相对新文件 | 独占新建，已有目标拒绝 |
| read-file | 已存在且被授权的相对文件 | Prepare 含 tool/path，结果为观察字节/哈希 |
| update-file | 已存在的准确相对文件 | 当前 SHA-256、UTF-8 新正文及受保护前像策略 |

读取的 max_bytes/max_characters 属执行限制，不是准备参数。缺 tool/path 时不能猜宽泛资源。更新应读取宿主提供的完整当前 preimage policy 模板，摘要标签不是完整描述符。

更新保护比较独占打开文件与 expected_sha256，保全前像、写入并检查新字节。当前内容改变时保留原操作，使用对应对账/修复合同。受管字节结果不证明构建通过，也不证明编辑器/网络操作发生。

## 6. 验证与当前完成

criterion 必须是闭合字段 `criterion_id`、`description`、`hard`、`verification_method`、`minimum_evidence_level`。Evidence 绑定准确 Task revision、criterion、当前 epoch 的 OBSERVED 操作及描述符；方法和最低等级须匹配。

`verification.begin` 要求依赖、Host 和操作结清，进入 VERIFYING 后拒绝新执行。`verification.rework` 保留历史并使旧依据失效。`task.accept` 使用同一边界；`task-verify` 只读返回当前证明。Phase/Project 完成需各自验收与当前任务闭包，不能由一个任务或单元测试替代。

所有硬条件须有满足方法/等级的证据。调用者声明的 review 不能仅因 JSON 写 PASS 成为独立验证。verification.managed-files 提供固定有界文件完整性方法/等级，任务业务行为需另有证据。

验证模式在验收前结清依赖、操作和受管宿主，检查期间拒绝新效果。Rework 返回可执行工作并使之前当前依据失效，不抹历史。小任务可通过同一边界原子验收。

阶段完成核当前计划、硬条件、任务所属/当前验收及成果引用闭包；项目完成聚合自身要求。空阶段或单个文件验收不完成更大范围。当前证明查询须区分历史重放和 CURRENT_EVIDENCE_VALID。

## 7. 证据、成果与 Growth

DPAPI 保护正文和敏感定义；blob 描述符声明 target、content_class、sensitivity、review、retention 与 access_scope。加密不证明脱敏，`verification`、`recovery`、`derivation`、Growth用途分别检查。派生内容须保留来源链，撤销/到期传播停止复用。

Artifact 关系图、回收前依赖、Shared 当前内容与 owner 独立检查。历史 SUPERSEDED/RETIRED 关系不自动指向新成果。Growth 使用提案与 trial 状态、未来可比证据和退役保护；neutral 保持 neutral，不把迟到正面记录复活为可用方法。

## 8. 交接与恢复

交接预览返回来源令牌、有界事实、部分页和所选手工原文。受控发布需现有且已审阅的目标、精确前像及来源一致；目标不存在需另行限定创建。交接不授权限、不成为第二事实源。

备份覆盖 DB、blob 和合同声明的资源，Host journal 与安装事务有独立保留责任。restore 使用已核验备份、新目录及新 epoch，保持隔离，核后续成果、外部效果和预算后才恢复。跨用户保护解密尚未认证。原库不可读的前向恢复也必须证明采用链和缺口，不能伪造 missing receipt 为无效果。

source_token 检测交接快照呈现的所属事实，不是全部业务依赖哈希或文件 compare-and-swap token。选定备注保留审阅来源身份，但预览不重新验证所有原文件；发布因此同时需要当前 token 检查及准确目标前像保护。

备份验证核声明数据/资源；恢复写新的所选目标和 epoch，之后对账备份后的工作。记录缺失不能证明 Provider 调用或宿主启动未发生，填补缺口时保留原回执、隔离和消耗。

Host journal 和安装快照具有不同所属，恢复任务库不能代替它们。准入后继前另核对应关系和真实进程状态。

## 9. 保留与诊断

`blob-references`、`blob-inventory`、`blob-inspect` 和 retirement/recovery 查询帮助定位用途，均不证明可删除。终态、时间或哈希不能代替唯一恢复原文；保留未决操作、原始验收、来源封印和必要备份。空间不保证固定有界。

错误输出保持稳定 error_code；request 的成功结果在 `result` 内。例如 `result.request_hash`，不是顶层字段。`NOT_APPLIED` 不评估执行前置条件；`REQUIRES_REVIEW` 或错误退出不能标成成功。

## 10. 实现与资格范围

合同由 `v2_service.py` 与各领域模块执行。事务/权限/恢复、受管文件、代表性原生任务和安装验证各自建立证据。配置、模型自评、合成样例和历史完成不可相互替代；已知支持范围见[系统概览](SYSTEM_OVERVIEW.md)，控制端操作见[v2 使用说明](V2_PREVIEW_USAGE.md)。

## 受管采用边界

`legacy-adoption-preflight` 在持久准备前检查 source/capsule/state 互不包含及 Windows 控制输入支持范围；目录关系有效不产生写入权限。`legacy-adoption-apply` 默认只预览，正式应用绑定准确计划哈希及当前运行时，并使用真实来源封印、Windows 文件保护与 SQLite 定义重验。内置模式只覆盖审阅的 MALTS 控制输入和旧事务准入，不隔离任意外部应用或接管业务根。

失败时保留原采用 ID、计划、所属封印和私有交接证据；不能换 ID 重放或删除 binding 来恢复旧权威。`workspace` 对旧来源、未绑定导入库和封印恢复现场分别给出迁移、采用与恢复诊断；已采用入口重核 Project/计划/Task/依赖并报告 `LONG_PROJECT`、`phase_ready` 和阻塞原因。该就绪仅为治理条件，不签发 Grant、不证明业务验收。跨根业务效果须另行核准资源与适配器。完整步骤见[采用与升级](V2_PREVIEW_USAGE.md#v2-migration)。
