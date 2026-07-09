import sys
import os
import json
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent)
sys.path.insert(0, PROJECT_ROOT)

from core.launcher import VersionParser, AccountManager, UnifiedLaunchCore
from core.manager import E4MCManager


def get_project_root():
    return PROJECT_ROOT


def scan_all_versions(game_root):
    versions_root = Path(game_root) / "versions"
    version_list = []
    if not versions_root.exists():
        return version_list
    for dir_item in versions_root.iterdir():
        if not dir_item.is_dir():
            continue
        if dir_item.name == "natives":
            continue
        json_files = [f for f in os.listdir(dir_item) if f.endswith(".json")]
        if len(json_files) != 1:
            continue
        version_list.append({
            "folder_name": dir_item.name,
            "json_name": json_files[0],
            "json_path": str(dir_item / json_files[0])
        })
    return version_list


def select_version(ver_list):
    print("\n检测到可用游戏版本")
    for idx, item in enumerate(ver_list, 1):
        print(f"  {idx}. {item['folder_name']}")
    while True:
        try:
            num = int(input("\n请选择版本序号: "))
            if 1 <= num <= len(ver_list):
                return ver_list[num - 1]
            print("超出范围，请重新输入")
        except ValueError:
            print("请输入数字")


def get_version_type(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    main_class = data.get("mainClass", "")
    if "BootstrapLauncher" in main_class:
        return "forge"
    elif "KnotClient" in main_class:
        return "fabric"
    else:
        return "vanilla"


def test_online(game_root, java_path):
    print("=" * 50)
    print("MCOpen 联机功能测试")
    print("=" * 50)

    vers = scan_all_versions(game_root)
    if not vers:
        print("未找到任何游戏版本，请先安装 Minecraft")
        return False

    sel = select_version(vers)
    folder = sel["folder_name"]
    json_full_path = sel["json_path"]

    base_ver = folder.split("-")[0]
    ver_type = get_version_type(json_full_path)
    print(f"\n目标版本: {folder}")
    print(f"模组加载器: {ver_type}")

    print("\n" + "-" * 50)
    print("【步骤 1】检查联机模组")
    print("-" * 50)

    e4mc = E4MCManager(game_root)
    mc_version = base_ver

    print(f"Minecraft 版本: {mc_version}")
    print(f"mods 目录: {e4mc.mods_dir}")

    print("\n" + "-" * 50)
    print("【步骤 2】联机模组状态")
    print("-" * 50)

    if e4mc.is_installed(mc_version):
        print(f"e4mc 模组已安装: {e4mc.get_local_path(mc_version)}")
        info = e4mc.get_connection_info(mc_version)
        print(f"公网地址格式: {info['public_address']}")
    else:
        print("e4mc 模组未安装")
        print("\n" + "=" * 50)
        print("【需要手动下载】")
        print("=" * 50)
        print(e4mc.get_manual_guide(mc_version))
        print("=" * 50)

    print("\n" + "-" * 50)
    print("【步骤 3】启动游戏")
    print("-" * 50)

    print(f"正在启动 Minecraft {folder} ...")
    if e4mc.is_installed(mc_version):
        print("   (进入游戏后，点击'对局域网开放'，e4mc 会自动生成公网地址)")
    else:
        print("   (联机模组未安装，仅启动原版游戏)")

    acc = AccountManager().create_offline("TestPlayer")
    parser = VersionParser(game_root)
    cfg = parser.parse(base_ver, ver_folder_name=folder, json_filename=sel["json_name"], ver_type=ver_type)
    core = UnifiedLaunchCore(game_root, java_path)
    core.launch("java", cfg, acc, 2048, 4096, ver_type)

    print("\n" + "=" * 50)
    print("游戏已启动")
    if e4mc.is_installed(mc_version):
        print("玩法提示:")
        print("   1. 进入游戏后点击 ESC → 对局域网开放")
        print("   2. e4mc 会自动生成公网地址（如 xxx.e4mc.com:xxxxx）")
        print("   3. 复制地址发给朋友，朋友在多人游戏输入该地址即可加入")
    else:
        print("联机模组未安装，如需联机请按照上方指引手动下载")
    print("=" * 50)

    return True


def main():
    GAME_DIR = os.path.join(get_project_root(), ".minecraft")
    JAVA = r"C:\Program Files\Zulu\zulu-17\bin\java.exe"

    if not os.path.exists(JAVA):
        print(f"未找到 Java: {JAVA}")
        alt = input("请输入 Java 17 的完整路径（直接回车使用默认）: ")
        if alt.strip():
            JAVA = alt.strip()

    if not os.path.exists(GAME_DIR):
        print(f"未找到 .minecraft 目录: {GAME_DIR}")
        alt = input("请输入 .minecraft 目录完整路径（直接回车使用默认）: ")
        if alt.strip():
            GAME_DIR = alt.strip()

    test_online(GAME_DIR, JAVA)


if __name__ == "__main__":
    main()