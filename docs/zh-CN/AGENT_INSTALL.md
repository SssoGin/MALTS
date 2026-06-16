# Agent 辅助安装协议

当 Agent 为用户安装 MALTS 时，必须先询问目标工具：

```text
Codex
Claude Code
OpenCode
AllIncluded
```

除非用户选择 `AllIncluded`，Agent 不得安装全部 adapters。

## 必需流程

1. 阅读 `README.md`、`docs/INSTALL.md` 和本文。
2. 询问要安装哪个目标工具。
3. 说明 MALTS 使用一份共享 `MALTS_ROOT` 加工具薄适配层。
4. 说明共享 `MALTS_ROOT` 下的 `skills/` 是唯一安装的 skill source。不要安装工具本地 `skills/`。
5. 说明 `AGENTS.md`、`CLAUDE.md` 等工具指令模板是可选 MALTS 增强项，并询问是否安装或合并到目标工具真实指令文件。
6. 说明每个工具需要 `MALTS_BOOT.md`，但它应指向共享 `MALTS_ROOT`；默认安装计划不应包含完整 `<target>\malts\` runtime 副本。
7. 检查目标配置目录。
8. 展示计划写入文件、共享 root 位置和可能冲突。
9. 默认 dry-run。
10. 未经明确确认，不覆盖已有文件。
11. 不读取或复制 secrets、sessions、memory dumps 或用户特定生成状态。
12. 询问是否启用公开 docs 的双语文档同步；默认 runtime 项目产物保持单 canonical 文件，完整翻译镜像只在明确要求时生成。
13. 安装后运行验证。
14. 准确报告改动。

## 共享 Root

MALTS 每次安装只有一条 canonical public skill 和 runtime root：

```text
MALTS_ROOT
```

共享 root 必须包含：

```text
README.md
skills/
runtime/EN/templates/
runtime/EN/checklists/
tools/
scripts/
```

使用 `Install-MALTS.ps1` 时，默认共享 root 是 `%USERPROFILE%\.malts`。提供 `-TargetRoot` 时，默认共享 root 是 `<TargetRoot>\MALTS_ROOT`。用户选择其他经过审阅的位置时，使用 `-SharedRoot`。

## 工具适配层

Adapter 目录只提供工具特定指令模板、commands、agents 和配置。它们不定义独立公开 skill source。

正常安装布局：

```text
<tool-config-root>\MALTS_BOOT.md
<tool-config-root>\<tool adapter files>
```

无效布局：

```text
<tool-config-root>\malts\
<tool-config-root>\skills\
```

如果安装计划里出现上述任一路径，先停止并修正计划，再 apply。

## Runtime Discovery

项目初始化必须能找到共享 MALTS runtime root。因此正常安装应包含：

```text
<tool-config-root>\MALTS_BOOT.md
```

`MALTS_BOOT.md` 记录共享 `MALTS_ROOT`。Agent 必须验证该 root 包含：

```text
README.md
skills/
runtime/EN/templates/
runtime/EN/checklists/
```

## 编码

Windows 环境下不要依赖系统默认编码。脚本读写文本、命令行输出、文档校验应显式使用 UTF-8。Python 脚本优先写 `encoding='utf-8'`；必要时设置 `PYTHONUTF8=1`，或对 `stdout` / `stderr` 显式 `reconfigure(encoding='utf-8')`。

## 双语文档

如果用户启用双语文档同步，Agent 应遵循 [双语文档规则](BILINGUAL_DOCS.md)。中文文档是 user-facing 参考，不是默认 runtime context。项目运行产物默认是单 canonical 文件：中文叙述直接写入 `PROJECT_CONTROL.md`、`WORK_TASK_REPORT.md`、`PROJECT_HANDOFF.md`，完整翻译镜像只在明确要求时生成。
