# MALTS 工作区管理与状态库重定位

MALTS 集中保存项目定义、任务状态、证据与恢复资料，并在业务成果的实际位置检查结果。当前版本为 **2.0.3**。本文说明默认管理布局、旧工作区的审阅采用，以及健康原生或已采用状态库的重定位。安装更新和项目状态迁移是不同操作。

## 1. 默认布局与所有权

```text
<workspace>/
  <业务文件和已有控制文档>
  runtime/v2_binding.json          # 仅已采用工作区
  .malts/
    management.json               # 管理目录的所属工作区
    native.json                   # 原生初始化时创建的状态库定位文件
    state/                        # 数据库、引用的证据内容和受管输入
    source-capsules/<adoption-id>/ # 所选原始来源字节
    recovery/<operation-id>/       # 重定位计划、备份与恢复记录
```

`state` 是长期保存的权威数据。来源封存保存所选原始控制文件及明确选中的载荷，不是全部业务资产的备份。恢复记录属于创建它的操作。这些私有目录应排除在公开导出之外；是否将 `.malts/` 加入版本控制忽略规则，应依据项目自身策略审阅，MALTS 不静默修改 SVN 或 Git 设置。

所有权标记说明 `.malts` 属于哪个工作区，不替代状态库，也不授予执行权限。已有目录缺少匹配标记、出现未知顶层内容、外来定位文件、非空目标或链接路径时，相关准备会停止。MALTS 不通过改名或覆盖认领用户文件。

普通新工作区默认采用根内布局，显式指定的外置状态库和来源封存仍受支持。安装、入口查询及更新不会搬动已有外置绑定；只有获准改变布局时才执行下文重定位流程。受支持的根内状态位置为 `.malts/state`，其他根内子目录不自动获得支持。

## 2. 初始化原生工作区

通过所选工具的 Boot 与生命周期 discovery 确定 `$MaltsRoot`、`$PythonExe` 和 `$ToolRoot`，将已有项目目录选为 `$Workspace`。使用已核实的运行时：

```powershell
$Cli = Join-Path $MaltsRoot 'tools/malts_v2.py'
& $PythonExe -B $Cli workspace-init --workspace $Workspace --project-id $ProjectId --goal $Goal
& $PythonExe -B $Cli workspace-init --workspace $Workspace --project-id $ProjectId --goal $Goal --apply
& $PythonExe -B $Cli workspace --workspace $Workspace
```

第一条命令检查并描述目标，不创建目录或数据库。正式应用创建所属管理目录与原生状态库；最后的查询核对定位文件、Project 身份、资源根和 epoch（恢复代次）。这些操作不创建 Phase、Session 或 Run。长期项目还须定义当前 Project 和 Phase，绑定实际计划与 Task，并明确激活应执行的 Phase，见[控制端操作](V2_PREVIEW_USAGE.md)。

有意使用外置原生库时增加 `--state-dir '<explicit-external-state>'`。底层 `init --state-dir` 继续供已有控制器使用，但不创建工作区定位文件。不得对导入库、已采用库或部分迁移现场运行原生初始化。

## 3. 在工作区内采用旧控制资料

持久准备前运行 `legacy-adoption-preflight --source-root $Workspace`。默认来源封存为 `.malts/source-capsules/adoption`，状态库为 `.malts/state`。需要按采用身份分目录时，以 `--capsule-root` 指定 `.malts/source-capsules/<adoption-id>`；高级外置布局则明确指定外部路径。

准确布局已有授权后，预览并应用 `management-init --workspace $Workspace`，再按返回的路径执行[来源封存、映射、语义评审与采用](V2_PREVIEW_USAGE.md#v2-migration)。来源封存和状态库仍须互不包含；只有所属管理目录中的位置可以包含在来源工作区之下。

来源清单只读取索引控制文件和显式选择。其参与哈希的 `source_selection` 合同将 `.malts` 排除在迁移输入之外，因此管理写入不改变所选来源哈希，来源封存也不会收集自身。其他目录中的隐藏业务文件仍可被显式选中。实际位于 `.malts` 下的控制文件或所选载荷会构成待处理冲突，不会从迁移中静默丢弃。缺少此合同的历史来源封存仍可用于原有外置采用；新的根内准备须使用已审阅的来源选择合同。

`archive-only` 表示仅保留已验证、非活动且已终结的 Phase/Session 控制资料，不导入其可执行定义。只有 `DONE`、`CANCELLED` 和 `FAILED` 符合条件；`SUPERSEDED`、`BLOCKED`、活动控制及未核实身份均不符合。封存预览在复制前报告选中身份和不支持的状态，不改写历史控制来满足条件。

Windows 采用交接冻结审阅来源文件并保护目录身份，同时允许候选数据库提交。即使管理数据物理上位于工作区内，也不属于普通业务文件操作的资源范围；逻辑权威隔离不依赖相邻目录布局，也不赋予任意应用访问状态文件的权限。

## 4. 重定位健康的状态库

### 4.1 范围与前提

正式控制器支持同机、同用户、Windows 固定本地卷上可读且健康的已采用库。目标必须不存在；旧状态、新状态和操作记录目录须互不包含。目标与操作记录目录须同卷，以便原子发布恢复后的目录；旧库可以位于另一个固定本地卷。默认目标和操作记录目录分别为 `.malts/state` 与 `.malts/recovery/<operation-id>`。

规划前处理活动 Run、未知操作效果和未静默的 Host 派发。Run 列表为空不能证明外部 Editor、脚本或业务写入者已停止。恢复库在切换权威前须完成当前 epoch 的资源与效果审查；不得为了完成迁移而将未知覆盖改成已协调。

网络路径、重解析链接、不支持的根内布局、跨用户或跨机器搬迁，以及非本地或云同步存储不属于此流程的已验证范围。固定本地路径本身不能证明第三方同步客户端不存在，操作者须排除同步目录。容量和访问检查是前置检查；后续磁盘或访问失败会保留部分现场。



原生库不需要伪装成旧工作区或重新导入。预检自动识别已有原生定位文件；通过底层 `init --state-dir` 建立、尚无定位文件的库须另外传入 `--old-state-dir $OldState`，其中 `$Workspace` 是 Project 的实际业务资源根，`$OldState` 是现有数据库的父目录，二者不可混用。返回的 `source_kind` 分别为 `NATIVE_EXPLICIT`、`NATIVE_LOCATOR` 或 `ADOPTED`。已有库迁址不能使用 `workspace-init`：该命令只创建新库，不复制现有 Task、依赖、历史或预算。

### 4.2 只读计划与准备

选定唯一 `$OperationId`、已有授权引用 `$AuthorityRef` 以及新的 `$PlanPath`，将返回 JSON 原样保存为 UTF-8：

```powershell
& $PythonExe -B $Cli store-relocation-preflight --workspace $Workspace --operation-id $OperationId --authority-ref $AuthorityRef |
    Out-File -LiteralPath $PlanPath -Encoding utf8NoBOM
$Plan = Get-Content -LiteralPath $PlanPath -Raw -Encoding utf8 | ConvertFrom-Json
& $PythonExe -B $Cli store-relocation-prepare --plan-file $PlanPath --expected-plan-sha256 $Plan.plan_sha256 --tool-root $ToolRoot
& $PythonExe -B $Cli store-relocation-prepare --plan-file $PlanPath --expected-plan-sha256 $Plan.plan_sha256 --tool-root $ToolRoot --apply
& $PythonExe -B $Cli store-relocation-status --journal-root $Plan.journal_root
```

使用显式外置目标时，在预检增加 `--target-state-dir`，必要时指定 `--journal-root`。计划绑定规范化路径、用户与机器身份、来源协议哈希、当前状态哈希及文件闭包。预览后旧库产生新工作，会拒绝准备。正式准备取得真实 SQLite 排他锁，生成并核验备份，在隔离状态下恢复新 epoch，再原子发布恢复目录；此时旧权威仍保留。

闭包通过既有备份合同复制数据库引用的证据内容、STATE 范围计划、所选旧来源、映射和受保护操作输入。PROJECT 范围文件继续使用项目位置。未被数据库引用的历史文件，以及 Host 和证据中的绝对引用，保留原路径，并列为 `RETAIN_EXTERNAL_HISTORY`；相关旧目录须继续可用。流程不替换历史字符串，也不授权删除旧库或独立来源封存。

### 4.3 恢复审查

状态查询返回 `recovery_inventory` 和 `recovery_review_template`。模板有意保留 `UNKNOWN` 覆盖及未决效果占位项。将其另存为新的审查文件，依据现状逐项核查每个 Project 根、历史 Task 范围、真实写入者与效果，填写实际授权和证据引用以及 Task 处置。只有处理完成后才能移除未决效果；保留终结历史，后续动作尚未审阅的任务继续暂停。

```powershell
& $PythonExe -B $Cli recovery-review --state-dir $Plan.state_dir --review-file $ReviewPath
# 读取返回的 plan_sha256，再应用完全相同、已经审阅的报告：
& $PythonExe -B $Cli recovery-review --state-dir $Plan.state_dir --review-file $ReviewPath --expected-plan-sha256 $ReviewHash --apply
```

审查由操作者依据事实作证，不是系统独立证明任意外部写入者已隔离。它绑定准确的恢复 epoch 和清单。过期报告、UNKNOWN 覆盖、未决效果或缺失写入者覆盖均阻止协调通过。

### 4.4 前向切换与核验

将原操作记录中的 `target.backup_root` 读为 `$BackupRoot`，再保存准确的前向计划：

```powershell
& $PythonExe -B $Cli store-relocation-plan --journal-root $Plan.journal_root |
    Out-File -LiteralPath $ForwardPath -Encoding utf8NoBOM
$Forward = Get-Content -LiteralPath $ForwardPath -Raw -Encoding utf8 | ConvertFrom-Json
& $PythonExe -B $Cli store-relocation-apply --plan-file $ForwardPath --expected-plan-sha256 $Forward.plan_sha256 --journal-root $Plan.journal_root --tool-root $ToolRoot
& $PythonExe -B $Cli store-relocation-apply --plan-file $ForwardPath --expected-plan-sha256 $Forward.plan_sha256 --journal-root $Plan.journal_root --tool-root $ToolRoot --apply
& $PythonExe -B $Cli workspace --workspace $Workspace
& $PythonExe -B $Cli store-relocation-status --journal-root $Plan.journal_root
```

控制器在前向事务之间持续持有两个 SQLite 排他锁，保护受管输入及目录身份，并重核备份、旧库、已协调目标和采用谱系。旧权威先被取代，新绑定才变为活动。部分切换时两库可能均拒绝执行，但不会同时获得活动权威。真实数据库锁阻止遵循 SQLite 协议的写入者；该模式不隔离任意原始文件写入，外部资源事实仍由操作者审查负责。SQLite 锁的保留语义见其[排他锁合同](https://www.sqlite.org/pragma.html#pragma_locking_mode)。

新 epoch 撤销旧 Grant、使验收失效、隔离租约与 Host，并防止恢复预算被重新补足。恢复会暂停原活动或已完成的 Phase。切换成功后核对当前治理状态，再明确激活应接续的 Phase；不能复制旧令牌或重复已完成效果来恢复运行。



### 4.5 原生库权威与长路径

原生迁址使用相同的备份、恢复审查和真实交接锁，随后在现有执行审计中追加原生生命周期事实，并原子切换 `.malts/native.json`。目标依次为恢复隔离、准备和活动状态；旧库持久记录被取代后，服务拒绝其执行及普通写入，包括新增 Task。它不生成旧来源、采用记录或第二份空项目。活动事实绑定状态路径、epoch、所属工作区、原操作记录和回执哈希。定位前像及未完成尝试仍用于原身份接续。

Windows 受管文件复制、哈希、备份核验、恢复及交接文件句柄采用内部扩展路径表示；对外计划、引用和定位文件保留普通规范化路径。这样可处理完整路径超过260字符的合法受管文件，不要求修改 `LongPathsEnabled`。路径组件仍须符合文件系统限制；链接、重解析、硬链接和受管引用校验没有放宽。数据库和协议控制根仍采用有界路径：新预检按派生控制文件最长路径240字符的保守预算拒绝过深布局，返回 `RELOCATION_CONTROL_PATH_TOO_LONG`。这与受管相对文件较长是两种情况。文件复制失败返回不含私人文件名的 `MANAGED_FILE_IO_FAILED`、操作类别、字符数和系统错误码，不宣称准备完成。

## 5. 中断、保留与验证边界

保留原操作 ID、计划、操作记录、备份和目标。`store-relocation-status` 只读。准备中断后重新应用原准备计划；不完整的备份与恢复尝试保留供核查，重试发布完整尝试而不覆盖它们。前向中断后，读取状态返回的 `forward.plan` （已采用库仍可使用 `forward-status`），再应用准确的原计划。部分协议替换保留前像，沿原身份接续。ACTIVE 重复调用核验绑定后返回原回执，不重新切换，也不声称重新核验 Host。

备份后旧库产生新工作时，前向规划或应用会拒绝过期快照。应处理分歧，不能强改哈希或删除新工作。旧库不可读及灾难恢复须使用既有独立恢复合同；健康重定位控制器不静默切换到该流程。

验证覆盖隔离原生初始化、根内采用、外置兼容、真实 SQLite 争用、输入保护、漂移拒绝、原身份接续及权威切换，不代表某个用户项目已经迁移，也不证明任意 Editor 隔离、跨用户 DPAPI 恢复、模型行为或性能收益。项目专属验证和另行授权的保留或清理决定完成前，应保留原始资料。

已有2.0.2的版本1重定位计划及 `PREPARING` 操作记录继续有效：更新运行时后读取原 `store-relocation-status`，用原计划文件、原 `plan_sha256`、原操作 ID 和原目录重新执行 `store-relocation-prepare`。不删除失败尝试、不编辑操作记录、不另起 ID 掩盖未决状态。后续仍须完成新 epoch 的资源与效果审查，再由统一的 `store-relocation-plan`／`store-relocation-apply` 接续；原 `legacy-forward-*` 已采用库接口继续兼容。长路径验证使用自有 Windows 夹具，不能据此外推特定用户工程已迁移。
