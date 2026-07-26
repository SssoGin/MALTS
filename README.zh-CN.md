# MALTS v1.0

MALTS 是面向 Agent 工作的可移植运行层：它提供项目控制模板、工作清单、可复用 Skill，以及 Codex、Claude Code 和 OpenCode 适配器。

此仓库是用户发行内容，只保留在项目中安装、运行、更新和理解 MALTS 所需的材料。

## 从这里开始

1. 向任何工具根写入前，先阅读[安装](docs/zh-CN/INSTALL.md)。
2. 验证下载包，并审阅生命周期计划。
3. 只执行自己已审阅过的精确计划 hash。
4. 阅读[使用](docs/zh-CN/USAGE.md)，开始一个由 MALTS 管理的项目。

如果工作会跨 Phase 或跨窗口，使用 `malts-long-project-workspace-init`。它会在同一次已审阅的初始化中创建根控制文件和首个 active Phase；Session 仍保持显式按需，不会自动创建。

同一份 payload 支持选择一个、两个或三个工具。它不会自行启动网络访问、provider 调用、后台轮询或自动更新。

## 包含的内容

- `runtime/`：规范的项目控制模板和检查清单。
- `skills/`：轻量项目初始化、Phase-ready 长期项目初始化、预检、长任务协作、复盘成长和交接所需的 MALTS 原生工作流。
- `adapters/`：Codex、Claude Code 和 OpenCode 的投影输入。
- `scripts/` 与 `tools/`：生命周期计划、执行、完整性检查和轻量项目控制工具。

## 用户文档

- [安装](docs/zh-CN/INSTALL.md)
- [Agent 辅助安装](docs/zh-CN/AGENT_INSTALL.md)
- [生命周期](docs/zh-CN/LIFECYCLE.md)
- [使用](docs/zh-CN/USAGE.md)
- [安全](docs/zh-CN/SECURITY.md)

英文文档见 [README.md](README.md) 和 `docs/`。

## 完整性

解包前先验证下载包。Bootstrap verifier 会检查 ZIP、checksum、transport manifest、公开说明、精确 inventory 和内部 lifecycle artifact，之后才会写入解包目标。

归属信息见 [LICENSE](LICENSE) 与 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
