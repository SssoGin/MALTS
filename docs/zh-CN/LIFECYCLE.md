# MALTS 2.0.0 生命周期

## 1. 两类生命周期

安装生命周期管理不可变版本、工具投影、registry、计划和事务。项目生命周期管理 Project/Phase/Task、操作、证据和恢复。安装更新不会自动采用或重建项目；项目备份也不能替代安装快照。

## 2. 安装计划与正式归并

通常使用 Install/Update 的 review-first脚本。更完整控制入口是 `scripts/Invoke-MALTSLifecycle.ps1`：Plan、PreviewPlan、Execute、Recover、Inspect、Scan、Doctor、DoctorRepairPlan。operations 为 install、update、repair、finalize、uninstall；以当前 `--help`核参数。

`finalize`用于同版本正式归并，保全原目标快照并核精确输入；它不是任意覆盖。创建 Plan 不改变安装，Execute 必须传入已审阅 PlanPath和ExpectedPlanHash。preview 使用新隔离根核来源、投影与实际后置条件，再对正常目标执行。事务记录负责恢复，不能手改journal或删除锁绕过前置条件。

## 3. 发现与诊断

从工具 Boot 解析运行根，discovery交叉核 registry、active pointer、generation identity与VERSION。Doctor只读判断信任及漂移，不修复。Inspect列安装状态；Scan列残留，不表示可删除。比如：

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 -Command Doctor -LifecycleRoot '<existing-lifecycle-root>' -ToolRootCodex '<codex-config-root>'
```

共享三端传入全部实际工具根；Harness使用其独立lifecycle和 `-ToolRootDeepSeekDesktop`，该现有参数名对应当前 `deepseek-harness`，不表示宿主身份恢复为旧名称。

## 4. v2 项目恢复

普通暂停续接准确Task/Run；灾难恢复先核已采用binding/epoch、备份和原writer。verify-backup后对新的目标restore，保持隔离并对账后续修改、UNKNOWN、预算和资源。缺回执不证明无效果；恢复不复活旧Grant/Host/已消费额度，不回到legacy运行。

## 5. 保留与清理

保留活动代际、registry、当前状态库、binding/source-seal、原始验收、未决操作与必要恢复快照。过期时间、candidate目录名和终态均不足以证明可删；先查引用、归属、完整占用及替代恢复。按用户和宿主文件策略处理，可恢复失败保留原对象。

安装清理必须通过已审阅 lifecycle计划，不能直接清理当前不可变代际。持续保留恢复数据可能增长磁盘占用，当前没有无限期固定空间保证。见[状态合同](V2_STATE_CONTRACT.md)和[更新](UPDATE.md)。
