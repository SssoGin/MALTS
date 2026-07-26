# Codex 适配器

此适配器从已验证的 MALTS 用户包使用，提供 Codex 在运行时需要的项目指令模板、角色定义和工作流。

## 通过生命周期安装

1. 先验证下载包，再解包。
2. 为 Codex 工具根创建并审阅生命周期计划。
3. 只执行已审阅计划的精确 hash。

生命周期会把 Codex 投影写入所选工具根，并记录精确 generation 身份。不要手工复制这些文件。

## 包含的运行时材料

- `AGENTS.example.md`：项目使用的 MALTS managed instruction block。
- `.codex/agents/`：可选的 MALTS 角色定义。
- `.codex/config.toml`：Codex 适配器配置。
- `workflows/`：启动、验证、复盘和 smoke check 指引。

参见[用户安装指南](../../docs/INSTALL.md)与[用户使用指南](../../docs/USAGE.md)。
