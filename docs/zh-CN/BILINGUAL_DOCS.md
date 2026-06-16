# 双语文档与运行产物语言策略

语言：[English](../BILINGUAL_DOCS.md) | [简体中文](BILINGUAL_DOCS.md)

MALTS 公开发布文档和 Agent 执行文档默认以英文源文档为事实源。

项目运行产物默认是单 canonical 文件。`PROJECT_CONTROL.md`、`WORK_TASK_REPORT.md`、`PROJECT_HANDOFF.md` 的叙述正文可以使用用户或项目主要语言，但标题、字段、状态值、ID、路径、命令和证据等级应保持稳定，便于 Agent 读取。

## Canonical 运行产物

默认使用这些文件：

- `PROJECT_CONTROL.md`
- `WORK_TASK_REPORT.md`
- `PROJECT_HANDOFF.md`

默认不生成完整翻译镜像。`项目控制.md`、`工作任务报告.md`、`项目交接.md` 等可选翻译镜像，只在用户明确要求单独翻译文件，或外部流程强制要求时创建。如果镜像与 canonical 文件冲突，以 canonical 文件为准。

## 公开文档镜像

公开文档仍可维护英文和简体中文对照：

```text
docs/
docs/zh-CN/
```

运行模板和检查清单参考文件维护在：

```text
runtime/EN/
runtime/CH/
```

这些 CH 文件是本地化参考，不代表项目运行产物必须生成重复文件。

## 规则

- 英文公开文档和 runtime EN 文档是 release source of truth。
- 中文文档和 runtime CH 文件是用户可读审阅/参考镜像，不是独立事实源。
- Agent 普通执行时不应同时加载 EN 和 CH 文档。
- 当用户明确要求中文审阅、中文编辑、对照或公开文档同步时，读取或更新 CH 文档。
- 项目运行产物默认保持单一事实源；需要中文叙述时，写入 canonical 文件正文，而不是默认生成重复镜像。
- 关键协议变更必须审阅语义，不能只做机械翻译。
- 如果 EN 和 CH 公开文档冲突，先修英文事实源，再重新同步中文审阅副本。
- 中文用户可读 docs、templates 和可选镜像应是有效 UTF-8。Windows 下包含中文的 Markdown 默认优先 UTF-8 with BOM，除非项目既有约定冲突。

## 工具

`tools/agent_system_lint.py check-doc-sync` 默认不要求 CH 文档。
使用 `--require-ch` 时，它会检查配置的公开文档对和 runtime 参考文件对。它不能证明翻译质量或语义完全等价。

默认 runtime 检查：

```powershell
python tools\agent_system_lint.py check-doc-sync --output-root runtime
```

检查 runtime 本地化参考：

```powershell
python tools\agent_system_lint.py check-doc-sync --output-root runtime --require-ch
```

检查公开双语文档时使用仓库 manifest：

```powershell
python tools\agent_system_lint.py check-doc-sync --output-root . --manifest tools\doc_pairs.json --require-ch
```

检查编码：

```powershell
python tools\agent_system_lint.py check-encoding --malts-root . --require-ch-bom
```
