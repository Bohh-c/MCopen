import sys
import os
import json
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)

try:
    from core.launcher import VersionParser, AccountManager, UnifiedLaunchCore
except ImportError:
    from launcher import VersionParser, AccountManager, UnifiedLaunchCore


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
    print("检测到可用游戏版本")
    for idx, item in enumerate(ver_list, 1):
        print(f"{idx}. {item['folder_name']}")
    while True:
        try:
            num = int(input("请输入版本序号："))
            if 1 <= num <= len(ver_list):
                return ver_list[num - 1]
            print("超出范围")
        except ValueError:
            print("请输入数字")

def get_version_type(json_path, folder_name=""):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    main_class = data.get("mainClass", "")
    if "BootstrapLauncher" in main_class:
        return "forge"
    elif "KnotClient" in main_class:
        if "quilt" in folder_name.lower():
            return "quilt"
        return "fabric"
    else:
        return "vanilla"

def launch_selected_version(game_root, java_path, selected_version, mem_min=1024, mem_max=4096, player_name="Player", progress_callback=None):
    folder = selected_version["folder_name"]
    json_file = selected_version["json_name"]
    json_full_path = selected_version["json_path"]
    base_ver = folder.split("-")[0]
    ver_type = get_version_type(json_full_path, folder)

    acc = AccountManager().create_offline(player_name)
    parser = VersionParser(game_root)
    cfg = parser.parse(base_ver, ver_folder_name=folder, json_filename=json_file, ver_type=ver_type, progress_callback=progress_callback)
    core = UnifiedLaunchCore(game_root, java_path)
    proc = core.launch("java", cfg, acc, mem_min, mem_max, ver_type)
    return proc

def quick_launch(game_root, java_path, mem_min=1024, mem_max=4096, player_name="Player"):
    vers = scan_all_versions(game_root)
    if not vers:
        print("无可用版本")
        return False
    sel = select_version(vers)
    launched = launch_selected_version(game_root, java_path, sel, mem_min, mem_max, player_name)
    if launched:
        print("游戏启动中")
    return launched

if __name__ == "__main__":
    GAME_DIR = os.path.join(get_project_root(), ".minecraft")
    JAVA = r"C:\Program Files\Zulu\zulu-17\bin\java.exe"
    quick_launch(GAME_DIR, JAVA, 2048, 4096, "TestPlayer")