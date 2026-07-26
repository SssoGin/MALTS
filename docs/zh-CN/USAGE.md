# 在项目中使用 MALTS

生命周期安装后，从工具的 MALTS boot pointer 开始工作。它会解析当前不可变 generation；不要手工把 runtime 文件复制到项目中。

## 启动项目

对于非平凡任务，在 `PROJECT_CONTROL.md` 中定义目标、验收标准、任务队列和恢复点；在 `WORK_TASK_REPORT.md` 中记录执行证据；当另一个 Agent 需要继续工作时创建 `PROJECT_HANDOFF.md`。

使用 `runtime/EN/` 或 `runtime/CH/` 中对应模板作为起草参考。除非用户明确要求翻译镜像，否则只保留一份规范的控制、报告和交接文件。

## 选择合适的工作流

- 只需要轻量根项目控制时，使用 `malts-project-init`。
- 项目会跨 Phase、跨窗口、经历中断或需要恢复边界时，使用 `malts-long-project-workspace-init`。选择该入口就代表选择长期项目工作区：初始化会同时创建根控制文件和首个 active Phase，不会静默停在最小骨架。
- 当目标、假设、取舍或验收标准需要澄清时，使用 Grill-Me Preflight。
- 简单工作保持单 Agent。
- 对用户已批准的长任务或多 Agent 任务，派发前展示 launch review。
- 当交接上下文必须跨会话保存时，使用 handoff Skill。

长期项目初始化必须提供首个 Phase ID 和目标。Dry run 必须列出首个 `PHASE_CONTROL.md`；缺少 Phase 输入时零写入失败。Apply 后应核对 `initialization_status=READY` 和 active Phase。初始化不会创建 Session；只有明确存在 bounded work-session 边界时才开启。

如果旧工作区已有根控制文件但没有登记任何 Phase，验证会报告 `WS_INITIAL_PHASE_MISSING`。通过 initializer 补充首个 Phase，或显式开启第一个 Phase；现有用户文件必须保留。

## 验证项目控制

用户工具会验证稳定的项目控制结构；提供 MALTS 根时，也会验证当前版本引用：

```powershell
python -B <MALTS_ROOT>\tools\malts_user_tools.py check-project-control `
  --project-control <PROJECT_CONTROL_PATH> `
  --malts-root <MALTS_ROOT>
```

## 默认安全行为

写入前先计划。工具根改动必须留在用户已批准的范围内。报告完成前先验证；没有用户明确授权的目标、限额、停止条件和恢复行为时，不要启用无人值守继续执行。
