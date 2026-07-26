# 安装 MALTS v1.0

## 前置条件

- Windows 10 或更高版本
- PowerShell 5.1 或更高版本
- Python 3.11 或更高版本
- 至少选择一个工具：Codex、Claude Code 或 OpenCode

生命周期根必须位于所有已选工具根之外。生命周期根保存 MALTS generation 与 registry；工具根只接收对应工具的 projection。

## 1. 验证下载内容

把四个文件放在同一目录：ZIP、其 checksum、transport manifest 和公开说明。使用匹配用户源码中的 bootstrap verifier：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-MALTSBootstrap.ps1 `
  -ArchivePath <ASSET_ROOT>\MALTS-1.0.0.zip
```

如需在验证成功后才解包，提供一个最终名为 `MALTS-1.0.0` 的空输出目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-MALTSBootstrap.ps1 `
  -ArchivePath <ASSET_ROOT>\MALTS-1.0.0.zip `
  -ExtractOutput <EXTRACT_PARENT>\MALTS-1.0.0 `
  -Apply
```

## 2. 创建可审阅的计划

把 `$releaseRoot` 指向已验证解包后的外层 package，把 `$payloadRoot` 指向其中的用户 payload。

```powershell
$releaseRoot = '<EXTRACT_PARENT>\MALTS-1.0.0'
$payloadRoot = Join-Path $releaseRoot 'lifecycle_artifact\payload'

powershell -NoProfile -ExecutionPolicy Bypass -File "$payloadRoot\scripts\Invoke-MALTSLifecycle.ps1" `
  -Command Plan `
  -Operation install `
  -ReleaseRoot $releaseRoot `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -ToolRootCodex <CODEX_ROOT> `
  -OutPath <PLAN_PATH> `
  -Apply
```

只选择自己要使用的工具根。可按需把 `-ToolRootCodex` 改为或增加 `-ToolRootClaudeCode`、`-ToolRootOpenCode`。在执行前阅读写出的计划及其 `plan_hash`。

## 3. 执行精确审阅过的计划

```powershell
python -B "$payloadRoot\tools\malts_lifecycle.py" execute `
  --plan <PLAN_PATH> `
  --expected-plan-hash <PLAN_HASH> `
  --apply
```

如果选中的 package、路径或计划 hash 已变化，engine 会 fail closed。它不会覆盖无关的工具根。

## 下一步

项目工作见[使用](USAGE.md)；更新、修复、恢复和卸载操作见[生命周期](LIFECYCLE.md)。
