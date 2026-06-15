# 更新 MALTS

MALTS 有两条更新路径：

- 用户更新：拉取新的公开包，然后把 MALTS 管理文件重新安装到共享 `MALTS_ROOT` 和选中的工具薄适配层。
- 维护者更新：修改此 release repository 并准备新的公开 snapshot。

## 用户更新

使用公开 MALTS 仓库的 git clone。更新脚本 review-first，默认 dry-run：

```powershell
.\scripts\Update-MALTS.ps1 -Tool Codex
.\scripts\Update-MALTS.ps1 -Tool Codex -Apply
.\scripts\Update-MALTS.ps1 -Tool AllIncluded -Strategy MergeSafe
.\scripts\Update-MALTS.review.cmd -Tool Codex
```

如果已安装共享 root 不在默认位置，使用 `-SharedRoot <path>`：

```powershell
.\scripts\Update-MALTS.ps1 -Tool AllIncluded -SharedRoot <MALTS_ROOT>
```

Modes：

- `PullAndInstall`：检查远端分支，有更新时拉取，然后安装。
- `PullOnly`：只更新 repository clone。
- `InstallOnly`：从已经下载的 package 安装。

Strategies：

- `MergeSafe`：更新共享 MALTS root 和 adapter 支持文件，但不替换用户顶层指令文件。
- `Overwrite`：更新 MALTS 管理文件，并在用户明确需要时替换工具指令模板。

如果远端分支已经是最新，脚本会打印 `Already up to date`。如果 working tree 有本地改动，`-Apply` 会拒绝 pull，除非审阅后提供 `-AllowDirty`。

## 布局规则

当前更新应保持这个布局：

```text
<MALTS_ROOT>\README.md
<MALTS_ROOT>\skills\
<MALTS_ROOT>\runtime\
<MALTS_ROOT>\tools\
<MALTS_ROOT>\scripts\
<tool-config-root>\MALTS_BOOT.md
<tool-config-root>\<adapter files only>
```

更新器不得创建完整 `<tool-config-root>\malts\` 副本或工具本地 `skills\` 重复源。

## 安装验证

维护者可以测试真实临时安装：

```powershell
.\scripts\Test-MALTSInstall.ps1 -Tool AllIncluded
```

该脚本安装到受保护的临时目录，验证共享 `MALTS_ROOT`、每个选中工具的 `MALTS_BOOT.md` 和 adapter scaffold，确认工具 target 下没有 `<tool>\malts` 或工具本地 `skills\`，然后删除临时目录；提供 `-KeepTemp` 时保留。

也可以直接运行同一个安装布局检查：

```powershell
python tools\agent_system_lint.py check-install-layout --install-root <TOOL_TARGET> --tool Codex
```

## 维护者更新流程

1. 从 dry-run 开始。
2. 比较源 MALTS runtime assets 与 release repository。
3. 只同步经过批准的 release content。
4. 保持共享 `MALTS_ROOT` 作为默认唯一 runtime 和 skill source。
5. 不同步 handoff output、release-control state、project-specific design notes、trial runs、caches、sessions、真实工具配置、用户特定 archives、生成的 migration packages 或无关项目 references。
6. 当 reusable Agent guidance 改动时，只把稳定的 MALTS-relevant public guidance 同步到 adapter examples。保留 public-safe confirmation 和 skill-recommendation rules。排除个人语言默认值、机器特定路径、用户特定 archive 路径、package-maintenance-only rules 和环境特定措辞。
7. 当 public guidance 借鉴或改编 upstream projects 时，保持 third-party attribution 最新。
8. 准备新公开 release 时更新 `VERSION` 和 `CHANGELOG.md`。
9. 运行 sensitive scans。
10. 运行 lint checks。
11. commit 前审阅 diff。
12. 使用 GitHub Desktop 或 Git CLI commit 和 push。

任何 visibility change 之前，仓库都应保持 public-safe。
