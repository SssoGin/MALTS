# 可选发布归档

仓库是 MALTS 常规安装/更新来源，可选固定归档服务于离线或归档使用；当前发布版本 **2.0.0**。

## 一个可选 Release ZIP

正式 Release 有一个 MALTS 上传附件 MALTS-2.0.0.zip。GitHub 自动源码归档是平台另行链接；安装器不自动下载 ZIP。

## 解压前核验

从匹配审阅来源取得 Verify-MALTSBootstrap.ps1，解压前核验：

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip -ExtractOutput '<new-extraction-root>' -Apply
```

检查闭合清单、哈希、安全路径/碰撞和包体身份。完整性证明这些字节，不证明原生模型或业务结果。

## 从解出的归档安装

归档不会绕过计划哈希、所属合并或后置检查。使用载荷生命周期入口和解压包 ReleaseRoot，再审阅/执行准确计划哈希。Harness 选择独立生命周期及 ToolRootDeepSeekDesktop。不能直接复制至活动代际。见[安装](INSTALL.md)。

## 归档内容

读取经核验 manifest：闭合包包含公开 RELEASE_NOTES.md、manifest/清单和不可变生命周期载荷。仓库专用 Git/CI/identity 文件不进入安装用户载荷。

## 归档不包含的内容

排除项目数据库、用户配置、凭据、原会话、私有控制、缓存、测试及本地验收正文。后续同版本 main 指南修订不替换原归档/标签；其历史身份保持明确。
