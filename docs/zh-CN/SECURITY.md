# 安全

## 使用前验证

解包下载 package 前使用 bootstrap verifier。它会检查 ZIP、checksum、transport manifest、公开说明、精确 inventory、安全 Windows 路径和内部 lifecycle artifact。

## 保持本地数据只在本地

不要把凭据、token、session data、用户 profile 路径、私有项目文件、缓存目录或生成的 runtime state 放进 MALTS 用户 payload 或工具 projection。

凭据应通过环境变量或所选工具通常的安全配置机制提供。不要把 secret value 写入 `PROJECT_CONTROL.md`、`WORK_TASK_REPORT.md`、交接文件、prompt 或命令历史。

## 生命周期安全

应用前审阅每一个生命周期计划。计划会标识精确根、操作和 generation 身份。如果目标不符合预期、包含链接或 reparse point，或不再匹配已审阅计划，应立即停止。

## 报告漏洞

只分享描述问题所需的最少可复现信息。发送报告前移除 secret 和私有机器细节。
