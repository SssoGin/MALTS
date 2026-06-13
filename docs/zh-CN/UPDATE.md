# 更新 MALTS

语言：[English](../UPDATE.md) | [简体中文](UPDATE.md)

MALTS 有两条更新路径：

- 用户更新：拉取新版公开包，并把 MALTS 管理文件重新安装到工具目录。
- 维护者更新：修改 release repository，并准备新的公开快照。

## 用户更新

使用公开 MALTS 仓库的 git clone。更新脚本是 review-first，默认 dry-run：

```powershell
.\scripts\Update-MALTS.ps1 -Tool Codex
.\scripts\Update-MALTS.ps1 -Tool Codex -Apply
.\scripts\Update-MALTS.ps1 -Tool AllIncluded -Strategy MergeSafe
.\scripts\Update-MALTS.review.cmd -Tool Codex
```

模式：

- `PullAndInstall`：检查远端分支，有更新时拉取，然后安装。
- `PullOnly`：只更新仓库 clone。
- `InstallOnly`：从已经下载的 package 安装。

策略：

- `MergeSafe`：更新 MALTS 管理的 runtime、skills、docs、tools 和 adapter 支持文件，但不替换用户顶层指令文件。
- `Overwrite`：更新 MALTS 管理文件，并在用户明确需要时替换工具指令模板。

如果远端分支已经是最新，脚本会输出 `Already up to date`。如果 working tree 有本地改动，`-Apply` 会拒绝 pull；只有审阅后提供 `-AllowDirty` 才继续。

## 安装验证

维护者可以测试一次真实临时安装：

```powershell
.\scripts\Test-MALTSInstall.ps1 -Tool AllIncluded
```

该脚本安装到受保护的临时目录，验证 `MALTS_BOOT.md`、`malts/runtime`、`malts/skills`、工具 scaffold 文件和 `malts/tools/agent_system_lint.py`，然后删除临时目录；提供 `-KeepTemp` 时保留。

也可以直接运行安装布局检查：

```powershell
python tools\agent_system_lint.py check-install-layout --install-root <TARGET> --tool Codex
```

## 维护者更新流程

1. 从 dry-run 开始。
2. 比较源 MALTS runtime assets 与 release repository。
3. 只同步已批准的公开发布内容。
4. 保持根级 `skills/` 作为唯一公开 skill 来源。
5. 不同步 handoff output、release-control state、project-specific design notes、trial runs、caches、sessions、真实 tool configs、user-specific archives、generated migration packages 或 unrelated project references。
6. 当 reusable Agent guidance 变化时，只把稳定的 MALTS-relevant public guidance 同步到 adapter examples。保留 public-safe confirmation 和 skill-recommendation rules；排除 personal language defaults、machine-specific paths、user-specific archive paths、package-maintenance-only rules 和 environment-specific wording。
7. 如果公开 guidance 受到上游项目启发或改写，保持 third-party attribution 当前有效。
8. 更新 `VERSION` 和 `CHANGELOG.md`。
9. 运行敏感内容扫描。
10. 运行 lint checks。
11. commit 前审阅 diff。
12. 使用 GitHub Desktop 或 Git CLI commit 和 push。

release repository 在任何 visibility change 前都应保持可公开。
