# 安装 MALTS

MALTS 的安装模型是一份共享系统 root 加工具薄适配层。

共享 root 是当前机器上唯一默认的 MALTS runtime 和 skill 事实源。工具目录只应包含工具特定指令、scaffold 文件和指向共享 root 的 `MALTS_BOOT.md`。安装器默认不得在每个工具目录下创建完整 `malts/` 副本。

## 推荐流程

第一步先 dry-run：

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
```

如果 Windows PowerShell 阻止脚本执行，使用进程内 execution policy 覆盖：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
```

Windows 双击审阅可以使用会保留窗口的 wrapper：

```powershell
.\scripts\Install-MALTS.review.cmd -Tool Codex
```

除非提供 `-Apply`，否则不会写文件：

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
```

## 共享 Root

默认共享 root：

```text
%USERPROFILE%\.malts
```

提供 `-TargetRoot` 时，默认共享 root：

```text
<TargetRoot>\MALTS_ROOT
```

使用 `-SharedRoot <path>` 可以选择另一条经过审阅的位置。

`MALTS_ROOT` 必须包含：

```text
README.md
skills/
runtime/EN/templates/
runtime/EN/checklists/
tools/
scripts/
```

## 工具薄适配层

每个选中的工具只接收自己的 adapter 文件和 `MALTS_BOOT.md`。

```text
Codex      -> AGENTS.md, config.toml, agents/*.toml, MALTS_BOOT.md
ClaudeCode -> CLAUDE.md, agents/*.md, commands/*.md, MALTS_BOOT.md
OpenCode   -> AGENTS.md, opencode.json, .opencode/agents/*.md, MALTS_BOOT.md
```

`MALTS_BOOT.md` 记录共享 `MALTS_ROOT`。Agent 运行 MALTS project initialization 前，必须从该文件或另一条经过审阅的 global boot 路径解析 `MALTS_ROOT`。

工具 target 不得接收本地 `skills/` 副本。共享 `MALTS_ROOT\skills\` 是唯一安装的 skill source。

## 安装 Smoke Test

维护者可以在不触碰正常工具目录的情况下验证真实临时安装：

```powershell
.\scripts\Test-MALTSInstall.ps1 -Tool AllIncluded
```

该 smoke test 会创建受保护的临时目录，安装一份共享 `MALTS_ROOT`，为选中工具安装薄适配层，验证 `MALTS_BOOT.md`、共享 runtime root，并确认工具目录下没有本地 `malts/` runtime 副本或 `skills/` 重复源，然后删除临时目录；提供 `-KeepTemp` 时保留临时目录。

也可以直接运行安装布局检查：

```powershell
python tools\agent_system_lint.py check-install-layout --install-root <TOOL_TARGET> --tool Codex
```

## 支持的工具

```text
Codex
ClaudeCode
OpenCode
AllIncluded
```

## 默认行为

- 每组安装目标只安装一份共享 MALTS root。
- 工具目录只接收薄 adapter 文件和 `MALTS_BOOT.md`。
- `MALTS_BOOT.md` 指向共享 `MALTS_ROOT`。
- `MALTS_ROOT` 下的根级 `skills/` 是 canonical skill source。
- 不安装工具本地 `skills/` 重复源。
- 不安装每个工具目录下的 `<target>\malts\` runtime 副本。
- `runtime/EN` 和 `runtime/CH` 作为运行模板和检查清单来源。
- 双语文档同步默认关闭。
- Codex 安装到 Codex 配置 root；Claude Code 安装到 Claude Code 配置 root；OpenCode 安装到 OpenCode 配置 root。
- `-SkipInstructionTemplate` 用于安装 adapter 支持文件但不修改 Agent 指令文件。
- 除非用户明确允许，安装脚本不会覆盖已有文件。
- 安装脚本会先打印计划。

## 手动安装

1. 阅读 `README.md`。
2. 选择一条共享 `MALTS_ROOT`。
3. 将仓库 runtime 文件复制到共享 root。
4. 选择目标工具 adapter。
5. 审阅 `adapters/` 下的对应 adapter 目录。
6. 只复制该工具需要的文件到工具配置 root。
7. 在工具指令文件旁写入 `MALTS_BOOT.md`，并指向共享 `MALTS_ROOT`。
8. 不要把完整 `malts/` 目录复制到每个工具 target。
9. 运行对应 smoke test 或 lint 命令。

Agent 辅助安装规则见 [Agent 安装协议](AGENT_INSTALL.md)。
