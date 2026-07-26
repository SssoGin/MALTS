# MALTS 生命周期

生命周期 engine 一次安装并管理一个不可变的 MALTS generation。它消费已验证的外层 package，在 registry 中保存 generation 身份，并且只向选定的工具根写入 projection。

## 操作

| 操作 | 用途 | 是否需要已验证 package |
|---|---|---|
| `install` | 创建第一个受管理 generation。 | 是 |
| `update` | 激活更新的已验证 generation。 | 是 |
| `repair` | 受管理文件漂移时，重新应用当前 generation。 | 是 |
| `uninstall` | 从生命周期根和已选工具根移除 MALTS 受管理材料。 | 否 |

## 安全模型

- `plan` 可审阅且绑定 hash。
- `execute` 只接受已审阅的精确 `plan_hash`。
- 路径必须是绝对路径、彼此分离，并且没有链接或 reparse point。
- engine 会记录变更，因此中断后的工作可以恢复。
- 选定集合之外的工具根不会被修改。

## 常用命令

engine 路径使用用户 payload 根。

```powershell
python -B <PAYLOAD_ROOT>\tools\malts_lifecycle.py verify-release `
  --release-root <VERIFIED_OUTER_PACKAGE>
```

```powershell
python -B <PAYLOAD_ROOT>\tools\malts_lifecycle.py plan `
  --operation update `
  --lifecycle-root <LIFECYCLE_ROOT> `
  --tool-root codex=<CODEX_ROOT> `
  --release-root <VERIFIED_OUTER_PACKAGE> `
  --out <PLAN_PATH> `
  --apply
```

```powershell
python -B <PAYLOAD_ROOT>\tools\malts_lifecycle.py execute `
  --plan <PLAN_PATH> `
  --expected-plan-hash <PLAN_HASH> `
  --apply
```

中断后恢复时，先检查生命周期根，再针对同一根运行 `recover`。不要手工删除 transaction state。

参见[安装](INSTALL.md)和[使用](USAGE.md)。
