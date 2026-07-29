# MALTS 生命周期

生命周期引擎把已验证的 MALTS 来源转换为不可变安装代。一个本地 registry 标识活动安装代；每个选定 Agent 工具只接收自己的投影和 boot pointer。

## 核心不变量

- 安装代来自一个已验证仓库来源，或一个明确验证后解出的 release package。
- 激活后安装 payload 字节保持不可变。
- 安装代的来源信息只保存来源类型和哈希绑定身份；绝不保存 package、仓库或机器路径。
- 安装或更新成功后恰好有一个活动安装代。
- 计划会被持久化、可审阅，并绑定精确 SHA-256。
- 执行只接受精确已审阅计划和已观察到的前置条件。
- 未被选定的工具根目录不会被修改。
- 未知或用户拥有的文件会保留或阻塞，不会被静默移除。

## 来源模式

| 来源 | 正常用途 | 验证 |
|---|---|---|
| 公开仓库 | 默认安装和更新路径 | `MALTS_RELEASE.json`、`VERSION`、精确源码树清单、必需用户入口和安全仓库拓扑。 |
| 已解出的 release package | 明确的离线/固定归档路径 | 闭合 `release_manifest.json`、release inventory、内部 lifecycle artifact 和 package identity。 |

可选 ZIP 只是归档交付方式，不是第三种 lifecycle 来源。bootstrap 验证会把它解出为第二种来源模式。

## 操作

| 操作 | 用途 | 所需来源 |
|---|---|---|
| `install` | 创建并激活首个安装代。 | 仓库或已解出 package |
| `update` | 暂存并激活更新的已验证安装代。 | 仓库或已解出 package |
| `repair` | 用活动安装代协调选定投影。 | 仓库或已解出 package |
| `uninstall` | 在已审阅计划下移除 MALTS 拥有投影和 registry 状态。 | 仅已有安装状态 |
| `recover` | 继续或回滚中断的 transaction。 | 已有 lifecycle 状态 |

## 先审阅计划

用户生命周期脚本先创建计划。计划包含来源身份、选定根目录、目标安装代身份、写入、移除、用户修改分类、旧版迁移或残留动作、回滚和后置验证。

执行需要相同计划文件及其精确 `plan_hash`。来源或环境漂移会在变更前失败。

## 安装代与 Boot Pointer

lifecycle root 包含不可变安装代目录、registry 状态、transaction journal、审计证据和残留记录。每个选定工具接收一个小型投影以及 `MALTS_BOOT.md`，它在使用时解析活动安装代。

不要把物理 generation 路径复制进项目控制文件。需要当前 runtime 信息时，先解析 boot pointer，再读取活动 `VERSION`。

如果旧的长项目工作区在生成的 `PROJECT_CONTROL.md` 中保留了物理 generation 路径，先检查迁移计划：

```powershell
python .\tools\long_workspace.py refresh-runtime-references --workspace <PROJECT_WORKSPACE>
```

仅在审阅返回计划后再应用：

```powershell
python .\tools\long_workspace.py refresh-runtime-references --workspace <PROJECT_WORKSPACE> --apply
```

该命令只改写生成的版本来源元数据行。静态 generation 引用会使 `validate` 以
`WS_STALE_RUNTIME_REFERENCE` 失败；必须刷新或人工审阅，不能被静默忽略，也不能在该生成行之外被静默改写。

旧安装代可能保留 legacy 绝对来源 locator，仅用于让已验证更新替换它。它仍可被读取以完成迁移，但在更新生成不含路径的当前 envelope 前，安装代用户纯净度门禁会关闭式失败。

## 恢复与残留

中断操作会写入 journal。恢复会检查 journal、registry、活动 pointer、安装代、选定投影和受管残留，之后才会宣称状态稳定。

引擎区分 MALTS 拥有路径与用户拥有或不确定路径。它只会在已审阅计划下移除有确凿归属证据的 MALTS 残留；不明确路径会保留或等待明确用户决定。

另见[安装](INSTALL.md)、[更新](UPDATE.md)和[安全](SECURITY.md)。
