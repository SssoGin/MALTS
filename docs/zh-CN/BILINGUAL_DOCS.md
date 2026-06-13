# 双语文档与运行产物同步

语言：[English](../BILINGUAL_DOCS.md) | [简体中文](BILINGUAL_DOCS.md)

MALTS 默认使用英文运行文档作为 Agent 执行事实源。

中文公开文档和中文运行镜像不是独立事实源，但在中文用户可读输出或双语模式进入范围时，部分双语产物是规范要求。

## 规范产物对

当项目使用中文用户可读状态或双语模式时，以下文件必须成对创建并保持实质同步：

- `PROJECT_CONTROL.md` 和 `项目控制.md`
- `WORK_TASK_REPORT.md` 和 `工作任务报告.md`
- 需要中文交接镜像时，`PROJECT_HANDOFF.md` 和 `项目交接.md`

发布包中的运行模板和检查清单镜像维护在：

```text
runtime/EN/
runtime/CH/
```

## 规则

- 英文运行文档是 release source of truth。
- 中文文档和中文运行镜像是用户可读审阅镜像，不是独立事实源。
- Agent 普通执行时不应同时加载 EN 和 CH 文档。
- 当用户明确要求中文审阅、中文输出、对照或双语同步时，读取或更新 CH 文档。
- 当当前用户或项目使用中文时，不得把必需的双语运行产物降级为可选润色。
- 关键协议变更必须审阅语义，不能只做机械翻译。
- 如果 EN 和 CH 冲突，先修英文事实源，再重新同步中文审阅副本。
- 中文用户可读 docs、templates 和 reports 应是有效 UTF-8。Windows 下包含中文的 Markdown 默认优先 UTF-8 with BOM，除非项目既有约定冲突。

## 工具

`tools/agent_system_lint.py check-doc-sync` 默认不要求 CH 文档。
使用 `--require-ch` 时，它会检查配置好的文档对，并要求每份中文文档的标题数量和标题级别序列与英文一致。当 document root 是 `runtime` 时，即使不提供 manifest，也会检查内置 runtime EN/CH 产物对。它不能证明翻译质量或语义完全等价。

默认 runtime 检查保持英文优先：

```powershell
python tools\agent_system_lint.py check-doc-sync --output-root runtime
```

强制检查 runtime 中文镜像：

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
