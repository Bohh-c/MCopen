# MCOpen API 接口文档
## 架构说明
整体四层分层架构：资源解析层 -> 账号认证层 -> 下载引擎层 -> Java启动内核
顶层 UnifiedLaunchCore 统一分发调度；
Java版为完整游戏启动内核；BedrockEngine仅作为**基岩第三方启动器辅助工具模块**，不内置游戏运行二进制，仅提供配置、文件管理、外部进程调用能力，两者代码完全隔离，新增BE辅助逻辑不修改上层任何代码。

## 全局统一入口（GUI唯一调用）
launch(edition, cfg, account, min_mem, max_mem)
edition 枚举：java / bedrock
- java：完整拉起Java游戏进程
- bedrock：仅辅助基岩版启动 **不内置任何基岩版启动器**

---
## 一、Java版完整API（已全部实现，核心主力）
### VersionParser 版本解析模块
parse_version(ver_id: str) -> dict
读取versions版本json，自动过滤条件参数，分离普通jar与natives原生库，解压LWJGL动态链接库，输出完整运行配置。
返回字段：mainClass, raw_args, libraries, natives, assets_id, jar_path

### AssetChecker 资源完整性校验
scan_missing(asset_id: str) -> list
读取assets索引哈希，扫描本地缺失材质、音效、语言文件，返回缺失资源哈希列表，直接传入下载引擎。

### AccountManager 认证模块
create_offline(name: str) -> dict
生成MC标准Yggdrasil离线账号，包含name、uuid、accessToken、clientToken，兼容1.17+全部新版本认证协议。
microsoft_oauth()
预留微软OAuth2正版登录接口，未实现。

### DownloadEngine 异步下载引擎
batch_download(url_list, root_path)
多线程后台批量下载，Qt信号槽返回进度百分比，不阻塞UI线程，自动递归创建目录。
single_download(url, out_path)
底层单文件流式下载。

### JavaLaunchEngine Java启动内核
launch(cfg, account, min_mem, max_mem)
拼接完整ClassPath、JVM参数、游戏强制环境变量，注入natives dll路径，拉起Java游戏进程。

---
## 二、Bedrock基岩辅助工具API（接口定型，仅做外部调用辅助，无内置运行程序）
### BedrockEngine 基岩工具模块（仅辅助，不含内置启动器）
scan_install()
扫描本地BE自定义目录，读取pak资源包、options配置、存档/附加包路径。
xbox_authenticate()
完整OAuth2 → XBL → XSTS 微软Xbox认证链路，仅用于正版账号信息读取（不强制启动）。
set_xsts(token: str)
外部注入XSTS身份令牌，GUI账号面板调用。
generate_launch_args()
【新增接口】根据用户填写的离线昵称、游戏目录，生成mcpelauncher离线启动命令行参数，返回参数列表供外部进程调用。
launch()
基岩工具入口：读取本地用户选择的mcpelauncher二进制路径，拼接参数拉起外部第三方程序；**本项目不自带任何基岩版启动相关内容，仅做辅助工具**。

## 数据结构体标准（永久固定）
### VersionConfig
{
    mainClass: str,
    raw_args: list,
    libraries: list,
    natives: list,
    assets_id: str,
    jar_path: str
}
### PlayerAccount
{
    name: str,
    uuid: str,
    accessToken: str,
    clientToken: str,
    authType: str
}

## 开发规范
1. GUI禁止直接import底层Engine，只能通过UnifiedLaunchCore调用
2. 所有Java游戏底层逻辑修改只允许在JavaLaunchEngine类内部
3. BE所有工具代码仅写入BedrockEngine，禁止侵入Java内核逻辑
4. 顶层对外接口定稿永久不再修改