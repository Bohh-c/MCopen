# MCOpen(MCO)
## Important Repository Statement
This is an independent open-source desktop launcher for Minecraft Java Edition, released under the GNU GPL v3.0 license.
It is not created, endorsed, or affiliated with Mojang AB or Microsoft Corporation.

- Primary mode: Official Xbox authentication for users with valid legitimate Minecraft Java Edition accounts
- Offline mode: Only for local single-player gameplay, used solely by users who already own official Minecraft accounts. It cannot bypass official authentication on public servers.
- This project fully complies with the Minecraft EULA and official usage guidelines. No global authentication bypass or public server crack functionality is included.
- The main repository is hosted on Gitee; this GitHub repository is a read-only mirror.

---
---
## 仓库重要说明
Gitee 为本项目唯一主线开发仓库，保存完整原始提交开发记录。
GitHub 仓库仅为从 Gitee 自动同步的只读镜像仓库。

本项目是独立第三方 Minecraft Java 版启动器，**与 Mojang、Microsoft 无官方隶属关系**。
项目采用 GNU GPL v3.0 开源协议，完整条款详见 LICENSE 文件。
本软件仅供持有正版 Minecraft Java 账号的用户使用。
离线模式仅用于本地单人单机游玩，不可用于绕过公共服务器正版验证。

## 开发说明
本项目2026年6月由核心开发者 Bohh 独立开发底层内核完成前期预研，7月组建四人开发团队协同开发；整体底层架构、四层分层设计、接口规范、核心业务逻辑均由团队独立设计落地。
开发过程中借助AI完成代码梳理、结构重构、GUI界面初稿生成，所有经AI处理的代码均经过团队人工逐行核对、改写、调试，完全适配自研底层框架，底层核心逻辑无AI生成内容。
完整开发迭代历程可查阅 CHANGELOG.md 与仓库提交记录，标准化接口定义详见 api.md。
本项目永久免费开源，**不含任何付费、充值、广告、捆绑推广相关功能**。
纯自研 Minecraft Java版 启动内核，原生解析版本JSON协议，无第三方闭源二进制捆绑。

## 项目介绍
整体四层分层架构：资源解析层 -> 账号认证层 -> 下载引擎层 -> Java启动内核
顶层 UnifiedLaunchCore 统一调度入口，预留基岩版辅助工具模块，仅做本地文件管理、第三方启动器调用辅助，**不内置任何基岩版游戏/启动器二进制程序**。
GUI仅调用全局统一顶层接口，Java游戏内核与基岩辅助工具代码完全隔离，新增基岩辅助逻辑无需修改Java底层核心代码。

## 核心（Java版）
1. Java版全版本完整支持，兼容1.12~最新快照，修复1.17+新版聊天公钥认证参数冲突问题
2. 内置多线程异步下载引擎，支持断点续传、文件哈希校验，下载逻辑不阻塞UI主线程
3. 完整标准离线账号随机UUID生成逻辑，预留微软OAuth正版登录接口
4. 原生兼容Forge/Fabric/Quilt/NeoForge所有主流模组加载器，规避多加载器参数冲突崩溃问题
5. 联机方案：基于 ZeroTier 虚拟局域网，用户自行安装 ZeroTier 客户端后，输入 Network ID 即可组网联机，支持好友直连
6. PyQt5图形可视化界面：集成版本下载、本地服务器管理、账号管理、模组开关管理全套功能，打包后开箱即用

## 附加辅助能力（基岩版，仅工具，不内置启动器）
仅提供本地文件管理、第三方mcpelauncher调用辅助功能，所有基岩运行二进制、游戏资源均由用户自行下载存放：
1. 扫描本地基岩目录、管理附加包/材质包/存档文件夹
2. 可视化配置离线昵称、自定义游戏路径，自动拼接mcpelauncher离线启动参数
3. 托管第三方进程、捕获运行日志，快捷打开各类资源目录
4. 不打包、不内置mcpelauncher、基岩游戏本体，无强制分发第三方程序

## 开发文档
完整接口参数、结构体、函数定义详见：[api.md](./api.md)

## 开发规范
1. GUI禁止直接import底层Engine，只能通过UnifiedLaunchCore统一调用
2. Java游戏底层逻辑修改只允许在JavaLaunchEngine类内部完成
3. BE所有工具代码仅写入BedrockEngine，禁止侵入Java内核逻辑
4. 顶层对外接口定稿后永久不再修改

## 当前版本状态（v1.4.3 Beta测试版）
1. UI 全面重构为列表式布局，所有页面风格统一
2. 联机方案已迁移至 ZeroTier，移除 EasyTier P2P
3. 加载器已迁移至官方 Maven 源，支持最新 Forge/NeoForge 版本
4. 打包输出 exe 文件名版本号同步问题待修复

## 温馨提示
UI随便胡乱折腾，底层代码别去乱碰
乱改结构全盘作废，老老实实调用接口
偷来抄去没啥意思，抄袭老冯原地爆炸

## 后续版本规划
1. v1.4.x Beta分支：仅修复联机、账号、打包相关bug，不新增大型功能；
2. Beta稳定后：全界面人工重构美化，统一全局UI样式、间距、配色；
3. 中长期计划：完善1.20.2+ authlib-injector正版验证支持，评估EasyTier联机是否恢复为外置插件。

## 开源协议
本项目永久采用 **GNU GPL v3.0** 开源协议，详情查看根目录 LICENSE 文件
本项目接入微软OAuth仅用于已有正版Minecraft账号的用户完成登录鉴权，不用于任何违规场景；本项目内Azure客户端ID严格绑定本仓库项目，绝不对外公开、泄露、搬运至其他程序使用

### GPLv3 分发说明
1. 仅个人本地修改、不对外分发exe/安装包，不受协议约束；
2. 若向他人分发修改后的程序二进制文件，必须同步完整开源全部修改源码，且衍生项目同样采用GPLv3协议；
3. 仓库开源时同步附带 AI_NOTICE.md，明确AI辅助范围、项目完整著作权归属；
4. 项目整合的 authlib-injector、ZeroTier 等第三方组件版权归其原作者所有，本项目仅作整合调用，不侵占第三方著作权益。