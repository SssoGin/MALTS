# MALTS 能力与 Skill 治理

本页属于MALTS整体系统说明，当前版本与实现为2.0.0。工作过程见[系统说明](SYSTEM_OVERVIEW.md)和[使用指南](USAGE.md)，本页只展开对应主题。

## 1. 区分方法、能力与权限

Skill说明如何工作；capability说明宿主实际能执行什么；Grant记录已有授权允许谁对哪项资源做什么。安装Skill、工具广告、配置或模型升级都不自动增加执行权限，也不能证明实际调用有效。

## 2. 按目标选择工作流

先解析当前项目规则、运行根与所选工作区。当前 v2 router按 task、phase、artifact、recovery选一项专题，避免为了一个问题加载整套历史。Task执行只读当前上下文，必要时载入执行参考；复杂度或多文件本身不触发委派、无人值守或迁移。

## 3. 指令与宿主适配

共享核心生成MALTS受管指令，工具自己的Boot提供真实运行定位。Codex、Claude Code、OpenCode和DeepSeek Harness保持各自配置与加载规则。用户手工区、最近适用项目指令与明确本轮要求保留。不同工具的参考文件不自动成为当前入口。

MCP只广告Host允许的动作；只读端不能mint Grant，write端也不能越过服务前置条件。实际模型/effort需要可观察证据；请求标签和真实身份分开。

## 4. Growth 与全局变更

经验以有来源提案、限定trial、未来可比结果、反证停用与退役管理。加密原文不等于可用于成长，需明确用途及经审阅的派生来源。neutral保持中性，不自动推广；DEPRECATED/REMOVED/REJECTED不得由迟到记录复活。

全局Skill、长期规则或插件修改仍须对应授权；项目范围内建议不产生这种权限。方法变更先用当前行为和实际收益判断，不为每次错误追加永久Prompt。验证机制与限制见[核心设计](CORE_DESIGN.md)，操作见[v2说明](V2_PREVIEW_USAGE.md#v2-growth)。

## 一个物理源，一个元数据视图

经审阅的可移植 Skill 保持一个物理正文来源；registry 记录来源、revision、hash 与兼容性，不复制第二份正文。

## Capability Descriptor 与 External Sidecar

descriptor 描述原生内容身份；external sidecar 在不改第三方文件的前提下记录来源、依赖与暴露声明。两者不能自动授予执行资格。

## 来源信任、审阅状态与执行风险

三者分别记录。可信来源不证明行为安全，方法通过审阅也不授权实际效果。

## 暴露与 Catalog 门禁

目录暴露仍须当前资格检查；可见不等于可执行。disabled、revoked 或 incompatible 不能由路由分数变成可用。

## Advisory Router 契约

capability router 只排序当前合格候选并给出理由，不接受 Task、不执行工具、不修改授权或覆盖 Host policy。

## 生成式 Catalog 与 Resolver

生成元数据是已审阅内容的视图；解析时核当前身份和 hash。过期目录需重新生成/验证，不能手改资格绕过。

## 隔离 Native Projection

原生投影是工具专属派生物，声明归属与输入身份；在选定隔离 profile 核发现。配置通过不等于真实工具行为通过。

## W3 验证边界

历史 W3 只覆盖静态组件与隔离投影；后续安装和原生任务证据保持各自时间/输入，不追溯扩大旧范围。

## 第三方 Skill 安装位置判断

遵循宿主加载规则并保留唯一正文；Codex portable Skill 可位于 ~/.agents/skills/<skill-name>，工具派生视图不制造相冲突正文。MALTS 不是第三方包管理器。

## 公开投影与私有状态

只共享合格可移植内容；项目凭据、journal、证据正文和用户配置不进入目录或分发。暴露不授权复制私有状态。

工具专属原生根包括 ~/.codex/skills/<skill-name>、~/.claude/skills/<skill-name> 和 ~/.config/opencode/skills/<skill-name>。按实际宿主加载规则及明确用户目标选择，不静默复制可移植正文。
