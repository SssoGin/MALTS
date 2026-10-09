# MALTS 2.0.0 与 DeepSeek Harness

## 入口与职责

本适配提供宿主原生指令与工作流发现。共享v2服务拥有Task状态、授权范围、证据和恢复；.dsh/MALTS_BOOT.md定位安装根，discovery交叉核registry、active pointer、identity与VERSION。

## 安装与使用

按[安装](../../docs/zh-CN/INSTALL.md)和[使用](../../docs/zh-CN/USAGE.md)操作。重载宿主验证实际Skill/MCP；标记区外个人内容保留。新长期工作区需Phase-ready，已采用工作区沿当前binding和Task服务继续。

Harness 使用 `Install-MALTS.ps1 -Tool DeepSeekHarness`；`AllIncluded` 选择四端，默认共享安装生命周期。各端仍有自己的配置根和 Boot。`ToolRootDeepSeekHarness` 指定实际工具根，旧参数名保留为别名。已有双安装按[生命周期合并流程](../../docs/zh-CN/LIFECYCLE.md#合并已有安装)显式迁移。完整安装和更新步骤见[安装](../../docs/zh-CN/INSTALL.md#deepseek-harness-安装)、[更新](../../docs/zh-CN/UPDATE.md#deepseek-harness-更新)。Desktop入口仍为profiles/desktop，CLI/Web不代证Desktop。

## 验证范围与限制

Windows Desktop0.2.0-rc.2覆盖任务、会话重开、目录终端与关联后端；GUI模型取消和任意writer隔离未认证。配置、安装、实际执行身份和业务验收分别判断。默认单Agent，委派、费用和发布按对应授权；未知效果及暂停/取消Host在续接前对账。
