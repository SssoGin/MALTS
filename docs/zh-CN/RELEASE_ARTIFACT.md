# MALTS 2.0.0 发布归档

## 1. 仓库与可选 ZIP

正常安装和更新来自已审阅的[公开仓库](https://github.com/SssoGin/MALTS)。正式Release提供一个MALTS上传文件 `MALTS-2.0.0.zip`；平台自动生成的源码归档是另外的链接。离线、存档或仓库不可用时才需要该ZIP，安装器不自动下载。

## 2. 内容和验证

ZIP包括不可变lifecycle artifact、精确清单/manifest和用户发布说明。repository-only文件不进入安装payload。闭合清单、内容哈希、路径/碰撞检查和安全解压用于发现新增、缺失或改动。

从同一可信来源取得Verify-MALTSBootstrap.ps1，先只读核验，再用不存在的ExtractOutput和Apply解出。安装使用ReleaseRoot和审阅计划哈希；不要直接覆盖代际。命令见[安装](INSTALL.md)。

## 3. 判断边界

包体验证证明内容/身份，不证明实际模型任务或整体业务效果。安装、宿主和项目验收有各自依据。同版本归并用准确artifact身份区分；历史包和回执保持原时间/版本，不为新发布改写。见[生命周期](LIFECYCLE.md)。

## 一个可选 Release ZIP

闭合包包含 RELEASE_NOTES.md、release/artifact manifest 和精确文件清单。核验后以实际条目定位文件，不假设平台生成源码归档具有相同结构。

### 从解出的归档安装

使用解出的 payload 安装器及 ReleaseRoot。归档不会绕过计划哈希、用户内容合并检查或实际安装后验证。
