# MALTS 安全与隐私

本页属于MALTS整体系统说明，当前版本与实现为2.0.0。工作过程见[系统说明](SYSTEM_OVERVIEW.md)和[使用指南](USAGE.md)，本页只展开对应主题。

## 1. 来源与身份

安装前核repository/tag、VERSION、发布身份与完整清单；离线ZIP先验后解。discovery核工具Boot、registry、active pointer和代际身份。不要把目录名、哈希文本或历史回执当当前完整性验证。

## 2. 最小授权与保护内容

Grant限定主体/资源/效果；服务检查依赖、预算、epoch和准入。MCP客户端不替换Host-bound字段。不要在命令行放密钥；参数错误输出的去值保护不覆盖shell历史或OS进程参数。

当前敏感正文与定义使用Windows当前用户DPAPI；保护描述符限定允许用途和保留范围。加密不证明脱敏、来源合法或跨用户可恢复。公开仓库/ZIP不包含工作区库、会话、凭据和机器私有路径。

## 3. 变更、未知效果与恢复

受管更新保留原文并绑定精确字节；UNKNOWN不自动重试。新epoch恢复必须对账后续成果、外部效果、预算和writer。fencing只约束已接入接口，不能替代外部编辑器锁或实际进程静止证明。

## 4. 保留和报告

清理前核依赖与恢复价值；保留原始验收、binding/seal、必要备份和未决操作。发现安全问题时向[仓库](https://github.com/SssoGin/MALTS)报告可公开的最小复现，不公开密钥、原生会话或私有证据正文。见[状态合同](V2_STATE_CONTRACT.md)。
