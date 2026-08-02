# Agent 协助安装

本策略适用于 AI Agent 帮助用户验证、安装、更新、修复、恢复或卸载 MALTS 的情形。

## 来源选择

仓库是主要来源。Agent 不能仅因可选 Release ZIP 存在就自动下载它。

仓库安装或更新前，Agent 必须：

1. 从选定仓库根目录读取 `MALTS_RELEASE.json` 与 `VERSION`。
2. 验证其中的版本、release ID、源码树哈希和文件数量是否内部一致。
3. Git 元数据可用时，报告当前检出 tag 是否与 `release_tag` 一致。
4. 仓库有意外文件、缓存、`.malts` 残留、reparse point 或身份不匹配时停止。

可选单一 ZIP 只在用户明确选择离线/固定归档路径，或已验证仓库来源不可用时使用。解包前必须用精确来源中的 `Verify-MALTSBootstrap.ps1` 验证。

## 必需顺序

1. 阅读[安装](INSTALL.md)、[生命周期](LIFECYCLE.md)、[安全](SECURITY.md)及与所选来源相关的说明。
2. 确认来源：已验证仓库，或用户明确要求的已验证 ZIP。
3. 询问哪些工具和根目录在范围内；不要推定未说明目标。
4. 创建新计划，但不执行。
5. 展示计划路径、精确哈希、选定根目录、破坏性动作、用户修改、清理、回滚和停止条件。
6. 等待用户明确授权该精确计划。
7. 使用已审阅计划路径和精确哈希执行。
8. 执行后检查 registry、活动版本、选定投影、boot pointer 和残留。如果 lifecycle root 旁已有本地 `GLOBAL_BOOT.md`，已审阅计划必须绑定、刷新并验证其中唯一的活动版本指针（或写入明确的未安装状态）；该本地发现文件只属于本机状态。

## 授权边界

读取仓库、验证身份、检查 ZIP 或创建审阅计划都不是安装授权。安装、更新、修复、恢复、卸载、删除、配置变更、Git 变更和远端发布分别需要用户授权范围内的具体动作。

计划展示后不得替换为更新的仓库或 Release package。来源漂移会使计划失效，必须重新审阅。

## 隐私与纯净度

不得把本地路径、凭据、令牌、用户配置、transaction journal、计划、交接、测试数据或缓存放入仓库或已安装版本。它们只能作为用户本地状态存在。

## Discovery 验证

Apply 后，把所选工具相邻的 `MALTS_BOOT.md` 作为普通启动权威。运行 `python -B <MALTS_ROOT>\tools\malts_lifecycle.py discover --tool-root <TOOL_ROOT> --lifecycle-root <LIFECYCLE_ROOT>`，并要求它与 registry、`active_generation.json`、active `VERSION` 及已配置的 `GLOBAL_BOOT.md` 精确一致。`GLOBAL_BOOT.md` 是独立的机器全局 / 恢复 schema，不能代替 tool boot。证据缺失或冲突必须 fail closed。
