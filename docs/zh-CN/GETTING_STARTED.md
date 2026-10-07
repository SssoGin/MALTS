# MALTS 快速开始

本页帮助你安装 MALTS 并开始一个项目。当前版本为2.0.0。普通用户通过 Agent 的工作流使用系统；准确控制端协议另见[操作参考](V2_PREVIEW_USAGE.md)。

## 1. 准备工具与安装来源

MALTS 的已验证路径使用 Windows、Python3.11或更高版本及PowerShell，推荐PowerShell7。先确认你选择的Codex、Claude Code、OpenCode或DeepSeek Harness已能正常使用。

从[公开仓库](https://github.com/SssoGin/MALTS)取得准备使用的版本。安装与项目设置分开：安装让工具发现MALTS，项目设置保存你要完成的工作。

## 2. 安装并核实加载

在仓库根目录先生成计划：

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
```

阅读计划中的来源、写入位置、已有内容处理和恢复方式，再代入命令输出的实际值执行：

```powershell
.\scripts\Install-MALTS.ps1 -Apply -PlanPath '<计划路径>' -ExpectedPlanHash '<计划SHA-256>'
```

更多工具选择、明确根目录、离线安装和入口核查见[安装](INSTALL.md)。重新加载Agent工具后，确认MALTS工作流和相关工具实际可用；安装文件存在不证明当前对话已加载。

## 3. 给出一个有结束条件的目标

向Agent说明交付、范围和验收，例如：

> 使用MALTS管理这次模块迁移。先检查现状并保存目标与兼容性要求，按模块安排阶段，完成修改和验证后交付。只修改本项目，保留用户数据，提交与公开发布另行决定。

目标有重要歧义时使用`malts-grill-me-preflight`；基本多轮项目可用`malts-project-init`；需要跨阶段和中断恢复时选择`malts-long-project-workspace-init`。工作流不增加委派、费用或发布权限。

## 4. 建立有限的项目工作

新长期项目明确整体目标、首阶段、任务与完成条件。当前完整设置须报告`phase_ready=true`；只建立状态目录或运行`init`不足以证明长期设置完成。

已有MALTS项目先核当前进度、准确任务、已验证结果和未解决项，不重复初始化。任务工作流`malts-v2-task-workflow`帮助取得当前方法；用户不必把内部ID和协议字段复制进每次请求。

## 5. 执行并查看结果

Agent完成当前范围内工作，检查实际产物并说明结果。用户主要核对成果是否满足原目标、检查覆盖了什么、剩余限制是什么。文件生成、进程退出和状态“完成”不等于整体目标已验收。

有价值的决定和检查点保存以便继续；报告、交接和复盘按用途生成。技术上`task-verify`返回`CURRENT_EVIDENCE_VALID`证明当前任务的声明范围，业务要求仍需对应证据。

## 6. 中断或换窗口后继续

可以这样请求：

> 继续这个MALTS项目，先核已有任务和检查点，保留已验证结果，查清未决操作和相关执行者，再从下一步继续。

未知效果`UNKNOWN`先对账，不能解释为未执行而盲目重试。恢复不补充已消费预算。需要另一个执行者接续时，用会话交接保全手工内容和准确状态。见[交接](HANDOFF.md)和[生命周期](LIFECYCLE.md)。

## 7. 按需要分工或复盘

已有明确委派授权且职责可分离时使用多Agent调度；主Agent负责整合与验收。纠正、验证失败或有效方法可触发轻量成长，重要阶段或明确复盘请求可进入项目复盘。无信号成功回合不生成空报告，不直接改全局规则。

## 8. 可执行演示与进一步阅读

维护者可按[完整隔离文件演示](V2_PREVIEW_USAGE.md#v2-start)验证创建、接受和备份路径。它不调用模型、不安装、不证明一般业务收益，必须使用不存在的新演示目录；该演示是`TASK_ONLY`，不是完整长期工作区。

日常工作详见[使用指南](USAGE.md)，整体功能见[系统说明](SYSTEM_OVERVIEW.md)，机制与取舍见[设计](CORE_DESIGN.md)。
