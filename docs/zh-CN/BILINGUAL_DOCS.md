# 可选双语文档同步

语言：[English](../BILINGUAL_DOCS.md) | [简体中文](BILINGUAL_DOCS.md)

MALTS 默认以英文文档和根级 `skills/` 作为 Agent 执行事实源。中文文档是公开入口、用户审阅材料和可选译本。

## 为什么是可选项

收益：

- 方便中文用户审阅
- 提升人类可读 onboarding
- 便于关键流程文档做双语对照

成本：

- 文件数量更多
- 审阅成本更高
- 如果 Agent 错误同时加载 EN 和 CH，会增加 token 使用
- 可能出现翻译漂移

## 规则

- 英文 docs 和根级 `skills/` 是 release source of truth。
- 中文 docs 是用户-facing 公开译本或审阅镜像，不是独立事实源。
- Agent 正常执行时不应同时加载 EN 和 CH docs。
- 只有用户明确要求中文审阅、中文输出、对照或双语同步时，才读取或更新 CH docs。
- 关键协议变更必须审查语义，不只是机械翻译。
- 如果 EN 和 CH 冲突，先修英文事实源，再同步中文。

## 工具

默认 `check-doc-sync` 不强制要求中文文档：

```powershell
python tools\agent_system_lint.py check-doc-sync --output-root runtime
```

公开中文文档需要强制检查时，使用 manifest：

```powershell
python tools\agent_system_lint.py check-doc-sync --output-root . --manifest tools\doc_pairs.json --require-ch
```

该检查确认配置的文档对存在，不证明翻译质量或语义完全等价。
