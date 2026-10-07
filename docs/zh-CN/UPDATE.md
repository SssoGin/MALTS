# 更新到 MALTS 2.0.0

## 1. 升级前检查

分别核实当前安装、待更新来源和工作区绑定。保存现有恢复资料，结清相关 Host/操作，检查是否存在用户修改。更新器不执行 Git pull、不自动下载 ZIP，也不迁移任意项目。

2.0.0 以所选 v2 store 管理执行。既有未采用工作区按自己的有效合同读取；采用 v2 必须显式审阅来源映射、原写者、未知效果和备份。当前 Core 只读写 Schema69，不能隐式升级早期开发库或恢复旧运行写权。

## 2. 审阅更新

从已审阅的 2.0.0 仓库根运行：

```powershell
.\scripts\Update-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool AllIncluded
```

使用明确根时传入现有 `-LifecycleRoot` 和工具根。阅读生成的来源身份、个人内容分类、代际变更、快照和后置检查，再使用真实输出值：

```powershell
.\scripts\Update-MALTS.ps1 -Apply -PlanPath '<reviewed-plan-path>' -ExpectedPlanHash '<reviewed-plan-sha256>'
```

同版本完全相同来源可返回 `NO_OP`；同版本内容不同需要先使用 lifecycle 的 `finalize` 归并合同，保全旧前像并绑定精确源。不要自行改成 2.0.1，不要清空或手改正在使用的代际。执行方法见[生命周期](LIFECYCLE.md)。

## 3. 指令和宿主加载

安装只维护拥有标记的 MALTS 区块，保留区块外个人内容。区块使用安装时生成的精确 `MALTS_BOOT_PATH`；指令文件与 Boot 不在同一目录时也遵循该准确指针。用户的 `AGENTS.override.md` 不由安装器创建或移除；它可能改变 Codex 实际加载的指令。更新后重载宿主，核对 Boot/discovery、原生 Skill 和 MCP，而不是推断本轮已切换运行代码。

## 4. 工作区、恢复与限制

已采用工作区继续核对 `workspace` 与 `entry-status`，使用当前 Task 服务；不运行旧 Markdown 初始化或双写。恢复到新 epoch 后，旧 Grant/Host/验收不会自动有效，消耗也不清零。发生不确定效果，沿原操作对账。

未经认证的跨用户 DPAPI 恢复、任意外部写者互斥和 GUI 模型取消仍不承诺。历史验收必须匹配相关输入；文档变化不自动否定未变的代码行为，但影响其命令和阅读验证。见[状态合同](V2_STATE_CONTRACT.md)。

## 仓库更新审阅

更新器不会执行 Git 拉取；先独立审阅取得的 checkout，再检查修改分类：

| 分类 | 含义 | 处理 |
|---|---|---|
| U0 | 缺失或准确属于 MALTS | 仅按计划替换/移除 |
| U1 | 可合并的受管指令块 | 保留块外内容并合并 |
| U2 | 有证据的确定性合并 | 使用已记录验证 |
| U3 | 用户修改或归属不明 | 保留，等待明确决定 |
| U4 | 敏感或不安全冲突 | 拒绝执行 |

## 可选离线归档更新

先验证解出同版本归档，再用 ReleaseRoot 和同一更新计划/哈希流程；不降低漂移与归属检查。

## 历史工作区采用

安装更新不采用现有项目。显式 v2 采用核原有事实、writer静止、未知效果与备份；保留历史来源与seal，恢复只围绕 v2。旧重整命令不拥有已采用工作区状态。
