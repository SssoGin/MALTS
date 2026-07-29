# MALTS 语言模型

MALTS 提供英文和简体中文用户文档、模板与检查清单，同时保持项目状态单一、标准且精简。

## 用户文档

根目录和 `docs/` 下的英文文件是稳定技术参考；`README.zh-CN.md` 与 `docs/zh-CN/` 提供主题和标题结构等价的简体中文用户指南。

用户可以阅读任一语言。命令、路径、Schema 字段、ID、状态值和 Skill 名称在不同语言中保持不变。

## 运行模板

- `runtime/EN/` 包含英文模板和检查清单。
- `runtime/CH/` 包含简体中文模板和检查清单。

当 `NarrativeLanguage` 为简体中文时，Agent 可以把 CH 模板作为起草参考，同时保留 MALTS 要求的稳定 Schema 标记和机器可读值。

## 标准项目文件

MALTS 默认对每种运行职责只使用一个标准文件：

- `PROJECT_CONTROL.md`
- `WORK_TASK_REPORT.md`
- `PROJECT_HANDOFF.md`
- 每个显式开启的 Phase 或 Session 各自一个控制文件

叙述部分可以使用用户或项目主要语言。只有用户明确要求或其他工作流必须使用时，才创建完整翻译镜像。

## 不重复的内容

MALTS 不要求为每个生成计划、报告、交接、任务合同、registry 或 transaction record 同时创建英文和中文副本。重复可变状态会产生漂移，也会让恢复事实不明确。

生成的 JSON 合同保留稳定字段名。面向用户的解释可以使用首选语言，但不改变这些字段。

## Agent 行为

Agent 应当：

1. 使用用户指定语言编写解释和叙述部分
2. 保留精确代码、命令、路径、ID 和专有名词
3. 除非明确需要镜像，否则只创建标准运行文件
4. 存在镜像时说明哪一份文件是事实源
5. 不翻译机器可读状态值或合同 key

## 相关指南

- [快速开始](GETTING_STARTED.md)
- [使用](USAGE.md)
- [核心设计](CORE_DESIGN.md)
