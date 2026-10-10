# 可选发布归档

仓库是 MALTS 常规安装/更新来源，可选固定归档服务于离线或归档使用；当前发布版本 **2.0.2**。

## 一个可选 Release ZIP

正式 Release 有一个 MALTS 上传附件 MALTS-2.0.2.zip。GitHub 自动源码归档是平台另行链接；安装器不自动下载 ZIP。

## 解压前核验

从匹配审阅来源取得 Verify-MALTSBootstrap.ps1，解压前核验：

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.2.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.2.zip -ExtractOutput '<new-extraction-root>' -Apply
```

检查闭合清单、哈希、安全路径/碰撞和包体身份。完整性证明这些字节，不证明原生模型或业务结果。

## 从解出的归档安装

归档不会绕过计划哈希、所属合并或后置检查。使用载荷生命周期入口和解压包 ReleaseRoot，再审阅/执行准确计划哈希。Harness 使用共享生命周期及实际 ToolRootDeepSeekHarness，并提供其他已注册工具根。不能直接复制至活动代际。见[安装](INSTALL.md)。

## 归档内容

读取经核验 manifest：闭合包包含公开 RELEASE_NOTES.md、manifest/清单和不可变生命周期载荷。仓库专用 Git/CI/identity 文件不进入安装用户载荷。

外层 release manifest 与清单绑定完整包，包括 RELEASE_NOTES.md 和内层 lifecycle_artifact；内层 manifest/清单绑定实际用户载荷与代际身份。两层均核，单个内层文件相同不能证明外层无增加或缺失。

安装将解压 release root 作为固定核验来源，只安装声明用户载荷；Git/CI 与仓库 identity 留在仓库专用范围。安全解压在最终输出前核路径和碰撞，新目标避免静默混入无关已有文件。

包不可用或核验失败时不能换同名目录冒充，应经正规核验选其他来源。包有效证明内容身份，不证明模型任务或完整用户项目结果。

## 归档不包含的内容

排除项目数据库、用户配置、凭据、原会话、私有控制、缓存、测试及本地验收正文。同版本线上 ZIP 更新对应按来源提交核验的新不可变包。旧包、回执及原标签对象保留作历史，发布当前校验值和回执。明确授权同版本对齐时，现行标签及 GitHub 自动源码 ZIP/TAR 须与 MALTS ZIP 标识同一核验提交。源码归档包含仓库树，MALTS ZIP 另有分发 manifest 与生命周期布局。

排除项是分发合同的一部分。维护 checkout 中的控制和测试可在本地有用，但不属于安装/公开载荷。公开投影使用准确分类，不作整个目录复制。

发布后生成的更新/恢复证据仍属于其工作区，应标识公共载荷，而不是塞入旧 ZIP。这保留发布时包体与之后安装/项目观察结果的区别。
