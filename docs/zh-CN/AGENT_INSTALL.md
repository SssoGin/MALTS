# Agent 辅助安装

当 Agent 协助用户安装 MALTS 时，使用以下规则。

1. 阅读[安装](INSTALL.md)、[生命周期](LIFECYCLE.md)和[安全](SECURITY.md)。
2. 确认用户已选择一个或多个工具根，以及一个与它们分离的生命周期根。
3. 解包前先验证下载 package。
4. 生成 dry-run 生命周期计划，向用户展示目标、破坏性操作和 `plan_hash`。
5. 执行该计划前等待用户明确授权。
6. 执行后检查生命周期状态和所选 projection。

Agent 不得添加未选择的工具、猜测工具根、复用过期计划 hash，或向不可变用户 payload 写入 live project 文件。

安装后的普通项目工作应遵循已安装 MALTS boot pointer 与最近的项目指令。
