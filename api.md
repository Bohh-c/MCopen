# MCOpen API 接口文档

## 架构说明

整体四层分层架构：资源解析层 -> 账号认证层 -> 下载引擎层 -> Java启动内核

顶层 `UnifiedLaunchCore` 统一分发调度，支持 Java 版完整游戏启动。

---

## 全局统一入口

### `launch_game(game_root, java_path, cfg, account, min_mem, max_mem, ver_type)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `game_root` | str | .minecraft 目录路径 |
| `java_path` | str | Java 可执行文件路径 |
| `cfg` | dict | 版本配置（由 `parse_version` 返回） |
| `account` | dict | 账号信息（由 `create_offline_account` 返回） |
| `min_mem` | int | 最小内存（MB），默认 1024 |
| `max_mem` | int | 最大内存（MB），默认 4096 |
| `ver_type` | str | 加载器类型：`vanilla` / `forge` / `neoforge` / `fabric` / `quilt`，默认 `vanilla` |

**返回**：`subprocess.Popen` 进程对象


### `launch_selected_version(game_root, java_path, selected_version, mem_min, mem_max, player_name, progress_callback)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `game_root` | str | .minecraft 目录路径 |
| `java_path` | str | Java 可执行文件路径 |
| `selected_version` | dict | 由 `scan_all_versions` 返回的版本项 |
| `mem_min` | int | 最小内存（MB），默认 1024 |
| `mem_max` | int | 最大内存（MB），默认 4096 |
| `player_name` | str | 玩家名，默认 `"Player"` |
| `progress_callback` | callable | 进度回调 `(pct, msg)` |

**返回**：`subprocess.Popen` 进程对象


### `scan_all_versions(game_root)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `game_root` | str | .minecraft 目录路径 |

**返回**：版本列表 `[{folder_name, json_name, json_path}]`


### `get_version_type(json_path, folder_name)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `json_path` | str | 版本 JSON 文件路径 |
| `folder_name` | str | 版本文件夹名 |

**返回**：`vanilla` / `forge` / `fabric` / `quilt`


## 一、版本解析模块

### `parse_version(game_root, version_id, ver_folder_name, json_filename, ver_type, progress_callback)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `game_root` | str | .minecraft 目录路径 |
| `version_id` | str | 版本 ID（如 `1.20.1`） |
| `ver_folder_name` | str | 版本文件夹名（如 `1.20.1-Forge_47.1.106`） |
| `json_filename` | str | 版本 JSON 文件名 |
| `ver_type` | str | 加载器类型，默认 `vanilla` |
| `progress_callback` | callable | 进度回调函数 `(pct, msg)` |

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | 版本 ID |
| `mainClass` | str | 主类名 |
| `raw_args` | list | 游戏启动参数 |
| `jvm_args` | list | JVM 参数 |
| `libraries` | list | 库文件路径列表 |
| `natives` | list | Native 库路径列表 |
| `loader` | object | 加载器处理器实例 |
| `assets_id` | str | 资源索引 ID |
| `jar_path` | str | 版本 JAR 文件路径 |
| `ver_type` | str | 加载器类型 |


### 支持的加载器类型

| 类型 | 说明 |
|------|------|
| `vanilla` | 原版 |
| `forge` | Forge（使用官方 Maven 源） |
| `neoforge` | NeoForge |
| `fabric` | Fabric |
| `quilt` | Quilt |


## 二、账号认证模块

### `create_offline_account(name)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | str | 玩家名 |

**返回字段**：

```json
{
    "name": "Player",
    "uuid": "70b24680c1b9498f8322c473484ef6a8",
    "accessToken": "0",
    "clientToken": "70b24680c1b9498f8322c473484ef6a8",
    "authType": "offline",
    "userType": "legacy"
}