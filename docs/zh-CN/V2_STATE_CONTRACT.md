# MALTS 2.0.0 状态与服务合同

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

## 3. Task 与操作状态

Task 状态包括 READY、RUNNING、VERIFYING、WAITING、PAUSED、RECOVERY_REQUIRED、COMPLETED 和 CANCELLED。具体转换由服务前置条件决定，不靠标签推导可执行性。Task 修改只对可修订状态执行；未决效果先对账。

Operation 准备绑定 Grant、actor、resource、effect、parameters、request_hash、lease 和 epoch。提交 intent 后效果可能发生；observed 记录已知结果，UNKNOWN 保持不确定。prepared 操作不能作为已执行证据。重放要求相同身份与内容；不得用新 ID 重复未知效果。

## 4. 授权、预算与并发

MCP 的 project、actor、authority 等 Host-bound 字段由配置提供，客户端不能覆盖。只读 endpoint 不具有写动作；write-enabled endpoint 仍逐项执行服务检查。授权引用只是来源记录，不认证用户身份，也不自行扩大范围。

预算维护累计消费，恢复不补充额度。Host dispatch 还受能力、预算和资源准入约束。租约和 fencing 只约束受管消费者；任意外部编辑器/进程须另行核静止。

## 5. 文件适配器

`operation.create-file` 独占创建，不能覆盖现有文件。`operation.read-file` 需要 prepare parameters 的准确 `tool='read-file'` 和 granted relative `path`；读取也可产生控制记录，因此不等同普通只读上下文。

Windows `operation.update-file` 需要 `tool`、`path`、`content`、`expected_sha256` 和完整 `preimage_policy`。原文受保护保全；当前字节和写后结果均核查。冲突/UNKNOWN 通过 `operation.reconcile-update` 或经新范围授权的 repair plan 处理，不能盲目换 ID。

## 6. 验证与当前完成

criterion 必须是闭合字段 `criterion_id`、`description`、`hard`、`verification_method`、`minimum_evidence_level`。Evidence 绑定准确 Task revision、criterion、当前 epoch 的 OBSERVED 操作及描述符；方法和最低等级须匹配。

`verification.begin` 要求依赖、Host 和操作结清，进入 VERIFYING 后拒绝新执行。`verification.rework` 保留历史并使旧依据失效。`task.accept` 使用同一边界；`task-verify` 只读返回当前证明。Phase/Project 完成需各自验收与当前任务闭包，不能由一个任务或单元测试替代。

## 7. 证据、成果与 Growth

DPAPI 保护正文和敏感定义；blob 描述符声明 target、content_class、sensitivity、review、retention 与 access_scope。加密不证明脱敏，`verification`、`recovery`、`derivation`、Growth用途分别检查。派生内容须保留来源链，撤销/到期传播停止复用。

Artifact 关系图、回收前依赖、Shared 当前内容与 owner 独立检查。历史 SUPERSEDED/RETIRED 关系不自动指向新成果。Growth 使用提案与 trial 状态、未来可比证据和退役保护；neutral 保持 neutral，不把迟到正面记录复活为可用方法。

## 8. 交接与恢复

交接预览返回来源令牌、有界事实、部分页和所选手工原文。受控发布需现有且已审阅的目标、精确前像及来源一致；目标不存在需另行限定创建。交接不授权限、不成为第二事实源。

备份覆盖 DB、blob 和合同声明的资源，Host journal 与安装事务有独立保留责任。restore 使用已核验备份、新目录及新 epoch，保持隔离，核后续成果、外部效果和预算后才恢复。跨用户保护解密尚未认证。原库不可读的前向恢复也必须证明采用链和缺口，不能伪造 missing receipt 为无效果。

## 9. 保留与诊断

`blob-references`、`blob-inventory`、`blob-inspect` 和 retirement/recovery 查询帮助定位用途，均不证明可删除。终态、时间或哈希不能代替唯一恢复原文；保留未决操作、原始验收、来源封印和必要备份。空间不保证固定有界。

错误输出保持稳定 error_code；request 的成功结果在 `result` 内。例如 `result.request_hash`，不是顶层字段。`NOT_APPLIED` 不评估执行前置条件；`REQUIRES_REVIEW` 或错误退出不能标成成功。

## 10. 实现与资格范围

合同由 `v2_service.py` 与各领域模块执行。事务/权限/恢复、受管文件、代表性原生任务和安装验证各自建立证据。配置、模型自评、合成样例和历史完成不可相互替代；已知支持范围见[系统概览](SYSTEM_OVERVIEW.md)，控制端操作见[v2 使用说明](V2_PREVIEW_USAGE.md)。
