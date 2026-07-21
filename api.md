# MCOpen API 接口文档
## 架构说明
整体四层分层架构：资源解析层 -> 账号认证层 -> 下载引擎层 -> Java启动内核
顶层 `UnifiedLaunchCore` 统一分发调度，支持 Java 版完整游戏启动。

## 全局统一入口
### `launch_game(game_root, java_path, cfg, account, min_mem, max_mem, ver_type)`
| 参数 | 类型 | 说明 |
|------|------|------|
| `game_root` | str | .minecraft 目录路径 |
| `java_path` | str | Java 可执行文件路径 |
| `cfg` | dict | 版本配置（由 `parse_version` 返回） |
| `account` | dict | 账号信息（由 `create_offline_account` 或 `microsoft_authenticate` 返回） |
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
**返回**：`vanilla` / `forge` / `fabric` / `quilt` / `neoforge`

---
## 一、资源解析层（版本解析模块）
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

### 版本 JSON 继承链处理
`parse_version` 会自动处理 `inheritsFrom` 继承链，从父版本继承库文件、参数和资源配置。

---
## 二、账号认证层
### `create_offline_account(name)`
| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | str | 玩家名 |
**返回字段**：
{
    "name": "Player",
    "uuid": "70b24680c1b9498f8322c473484ef6a8",
    "accessToken": "0",
    "clientToken": "70b24680c1b9498f8322c473484ef6a8",
    "authType": "offline",
    "userType": "legacy"
}

### `microsoft_authenticate(client_id)`
| 参数 | 类型 | 说明 |
|------|------|------|
| `client_id` | str | Azure 应用程序（客户端）ID |
**返回字段**：
| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 玩家 Minecraft 用户名 |
| `uuid` | str | 玩家 UUID（无连字符，32位十六进制） |
| `access_token` | str | Minecraft 访问令牌（Bearer Token） |
| `refresh_token` | str | 刷新令牌（用于自动续期） |
| `authType` | str | 固定为 `"microsoft"` |
| `userType` | str | 固定为 `"msa"` |

**说明**：
- 采用设备码流程（Device Code Flow），用户通过 `https://www.microsoft.com/link` 输入代码完成授权。
- 首次登录成功后，`refresh_token` 自动保存到本地 `refresh_token.json` 文件。
- 后续调用时会自动尝试使用刷新令牌续期，无需重复授权。
- 应用需通过 `https://aka.ms/mce-reviewappid` 申请 Minecraft API 权限后方可使用。

**异常**：
| 异常 | 说明 |
|------|------|
| `requests.exceptions.RequestException` | 网络请求失败 |
| `PermissionError` | 刷新令牌文件权限不足 |
| `Exception` | 登录流程中其他错误（如应用未获 API 权限） |

### `refresh_microsoft_token(refresh_token)`
| 参数 | 类型 | 说明 |
|------|------|------|
| `refresh_token` | str | 保存的刷新令牌 |
**返回字段**：同 `microsoft_authenticate` 返回结构
**说明**：使用刷新令牌换取新的访问令牌，无需用户重新授权。

### `load_stored_refresh_token()`
无参数
**返回**：存储的刷新令牌（str），若不存在或无效则返回 `None`

### `clear_stored_refresh_token()`
无参数，无返回
**说明**：删除本地保存的刷新令牌文件，用于退出登录或切换账号。