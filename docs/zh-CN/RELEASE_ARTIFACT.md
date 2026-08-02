# 可选 Release 归档

GitHub Release 可能为 MALTS 提供一个可选离线归档。它是固定离线副本的便利交付，不是普通 Agent 协助安装的必需条件。

## 一个可选 Release ZIP

每个 Release 最多上传一个 MALTS 资产：

```text
MALTS-<version>.zip
```

ZIP 是自包含的，内含：安装使用的不可变 release package、其 package 清单、`RELEASE_NOTES.md`，以及解出后所需的 runtime 模板、adapter、Skill 和用户工具。

不上传独立 checksum 或 transport 文件。归档 SHA-256 可以在 Release 正文中公布，作为额外的交付通道检查，但它不是第二个必需下载文件。

GitHub 还可能显示自动生成的 `Source code (zip)` 与 `Source code (tar.gz)` 链接。它们是平台生成的源码快照，不是这里定义的可选离线归档。

## 解压前验证

从与 ZIP 相同的已审阅来源或精确 source tag 取得 `scripts/Verify-MALTSBootstrap.ps1`，然后运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Verify-MALTSBootstrap.ps1 `
  -ArchivePath .\MALTS-1.1.0.zip
```

验证并解出到新位置：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Verify-MALTSBootstrap.ps1 `
  -ArchivePath .\MALTS-1.1.0.zip `
  -ExtractOutput <EXTRACTED_RELEASE_ROOT> `
  -Apply
```

验证器只接受预期的 `MALTS-<version>.zip` 名称。它会验证确定性 ZIP 结构、安全 Windows 路径、重复或大小写冲突成员、必需外层 release 文件、隔离解出，以及通过包内生命周期验证器验证闭合不可变 package。

## 从解出的归档安装

bootstrap 验证后，明确使用解出的 release root：

```powershell
<EXTRACTED_RELEASE_ROOT>\lifecycle_artifact\payload\scripts\Install-MALTS.ps1 `
  -ReleaseRoot <EXTRACTED_RELEASE_ROOT> `
  -UseDefaultRoots `
  -Tool Codex
```

这仍会先创建审阅计划。归档不会绕过计划哈希或用户授权边界。

## 归档内容

ZIP 只包含安装和使用 MALTS 所需的内容。本机状态、用户数据和项目文件绝不会被包含。

另见[安装](INSTALL.md)、[安全](SECURITY.md)和[Agent 协助安装](AGENT_INSTALL.md)。
