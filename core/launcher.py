import os
import json
import subprocess
import threading
import requests
import zipfile
import uuid
from pathlib import Path
from abc import ABC, abstractmethod

from core.multi_downloader import MultiDownloader
from core.basher import check_and_create_mco

try:
    from PyQt5.QtCore import QObject, pyqtSignal
except ImportError:
    from PyQt6.QtCore import QObject, pyqtSignal

def _resolve_mojang_libs(lib_list, game_root):
    cp = []
    natives = []
    for lib in lib_list:
        if "downloads" in lib:
            if "artifact" in lib["downloads"]:
                artifact = lib["downloads"]["artifact"]
                lib_path = os.path.join(game_root, "libraries", artifact["path"])
                cp.append(lib_path)
            if "classifiers" in lib["downloads"]:
                classifiers = lib["downloads"]["classifiers"]
                for classifier_name, classifier_info in classifiers.items():
                    if "natives" in classifier_name.lower():
                        native_path = os.path.join(game_root, "libraries", classifier_info["path"])
                        natives.append(native_path)
        elif "name" in lib:
            name = lib["name"]
            parts = name.split(":")
            if len(parts) >= 3:
                group, artifact_name, version = parts[0], parts[1], parts[2]
                classifier = None
                if len(parts) >= 4:
                    classifier = parts[3]
                group_path = group.replace(".", os.sep)
                if classifier and "natives" in classifier.lower():
                    jar_filename = f"{artifact_name}-{version}-{classifier}.jar"
                    natives.append(os.path.join(game_root, "libraries", group_path, artifact_name, version, jar_filename))
                else:
                    jar_filename = f"{artifact_name}-{version}.jar"
                    cp.append(os.path.join(game_root, "libraries", group_path, artifact_name, version, jar_filename))
    return cp, natives

def _resolve_fabric_libs(lib_list, game_root):
    cp = []
    natives = []
    for lib in lib_list:
        if "downloads" in lib:
            artifact = lib["downloads"]["artifact"]
            lib_path = os.path.join(game_root, "libraries", artifact["path"])
            if "classifier" in artifact:
                natives.append(lib_path)
            else:
                cp.append(lib_path)
        elif "name" in lib:
            name = lib["name"]
            parts = name.split(":")
            if len(parts) >= 3:
                group, artifact, version = parts[0], parts[1], parts[2]
                group_path = group.replace(".", os.sep)
                jar_filename = f"{artifact}-{version}.jar"
                lib_path = os.path.join(game_root, "libraries", group_path, artifact, version, jar_filename)
                cp.append(lib_path)
    return cp, natives

def _build_jvm_args_common(base_jvm, json_jvm, full_cp):
    merged = base_jvm + json_jvm
    filtered = []
    skip = False
    for i, arg in enumerate(merged):
        if skip:
            skip = False
            continue
        if arg in ("-cp", "-classpath", "--module-path"):
            if i + 1 < len(merged):
                skip = True
            continue
        filtered.append(arg)
    filtered.extend(["-cp", full_cp])
    return filtered

def _build_game_args_common(raw_args):
    return raw_args

class BaseLoader(ABC):
    @abstractmethod
    def resolve_libraries(self, lib_list, game_root):
        pass

    @abstractmethod
    def build_jvm_args(self, base_jvm, json_jvm, full_cp):
        pass

    @abstractmethod
    def build_game_args(self, raw_args):
        pass

class VanillaLoader(BaseLoader):
    def resolve_libraries(self, lib_list, game_root):
        return _resolve_mojang_libs(lib_list, game_root)

    def build_jvm_args(self, base_jvm, json_jvm, full_cp):
        return _build_jvm_args_common(base_jvm, json_jvm, full_cp)

    def build_game_args(self, raw_args):
        return _build_game_args_common(raw_args)

class ForgeLoader(BaseLoader):
    def resolve_libraries(self, lib_list, game_root):
        return _resolve_mojang_libs(lib_list, game_root)

    def build_jvm_args(self, base_jvm, json_jvm, full_cp):
        return _build_jvm_args_common(base_jvm, json_jvm, full_cp)

    def build_game_args(self, raw_args):
        return _build_game_args_common(raw_args)

class NeoForgeLoader(BaseLoader):
    def resolve_libraries(self, lib_list, game_root):
        return _resolve_mojang_libs(lib_list, game_root)

    def build_jvm_args(self, base_jvm, json_jvm, full_cp):
        return _build_jvm_args_common(base_jvm, json_jvm, full_cp)

    def build_game_args(self, raw_args):
        return _build_game_args_common(raw_args)

class FabricLoader(BaseLoader):
    def resolve_libraries(self, lib_list, game_root):
        return _resolve_fabric_libs(lib_list, game_root)

    def build_jvm_args(self, base_jvm, json_jvm, full_cp):
        return _build_jvm_args_common(base_jvm, json_jvm, full_cp)

    def build_game_args(self, raw_args):
        return _build_game_args_common(raw_args)

class QuiltLoader(BaseLoader):
    def resolve_libraries(self, lib_list, game_root):
        return _resolve_fabric_libs(lib_list, game_root)

    def build_jvm_args(self, base_jvm, json_jvm, full_cp):
        return _build_jvm_args_common(base_jvm, json_jvm, full_cp)

    def build_game_args(self, raw_args):
        return _build_game_args_common(raw_args)

def get_loader(ver_type):
    if ver_type == "forge":
        return ForgeLoader()
    elif ver_type == "neoforge":
        return NeoForgeLoader()
    elif ver_type == "fabric":
        return FabricLoader()
    elif ver_type == "quilt":
        return QuiltLoader()
    else:
        return VanillaLoader()

class VersionParser:
    def __init__(self, game_root):
        self.game_root = game_root
        self.ver_dir = os.path.join(game_root, "versions")
        self.natives_dir = os.path.join(self.ver_dir, "natives")
        self.libraries_dir = os.path.join(game_root, "libraries")
        self.versions_root = Path(game_root) / "versions"
        os.makedirs(self.natives_dir, exist_ok=True)
        os.makedirs(self.libraries_dir, exist_ok=True)

    def download_libraries(self, lib_list, progress_callback=None):
        download_items = []
        existing_count = 0
        for lib in lib_list:
            if "downloads" in lib:
                if "artifact" in lib["downloads"]:
                    artifact = lib["downloads"]["artifact"]
                    lib_path = os.path.join(self.game_root, "libraries", artifact["path"])
                    if os.path.exists(lib_path):
                        existing_count += 1
                        continue
                    if "url" in artifact:
                        lib_url = artifact["url"]
                    else:
                        lib_url = f"https://libraries.minecraft.net/{artifact['path']}"
                    download_items.append((lib_url, lib_path))
                if "classifiers" in lib["downloads"]:
                    classifiers = lib["downloads"]["classifiers"]
                    for classifier_name, classifier_info in classifiers.items():
                        if "natives" in classifier_name.lower():
                            native_path = os.path.join(self.game_root, "libraries", classifier_info["path"])
                            if os.path.exists(native_path):
                                existing_count += 1
                                continue
                            if "url" in classifier_info:
                                native_url = classifier_info["url"]
                            else:
                                native_url = f"https://libraries.minecraft.net/{classifier_info['path']}"
                            download_items.append((native_url, native_path))
            elif "name" in lib:
                name = lib["name"]
                parts = name.split(":")
                if len(parts) >= 3:
                    group, artifact_name, version = parts[0], parts[1], parts[2]
                    classifier = None
                    if len(parts) >= 4:
                        classifier = parts[3]
                    group_path = group.replace(".", "/")
                    if classifier and "natives" in classifier.lower():
                        jar_filename = f"{artifact_name}-{version}-{classifier}.jar"
                        lib_path = os.path.join(self.game_root, "libraries", group_path.replace("/", os.sep), artifact_name, version, jar_filename)
                        if os.path.exists(lib_path):
                            existing_count += 1
                            continue
                        lib_url = f"https://libraries.minecraft.net/{group_path}/{artifact_name}/{version}/{jar_filename}"
                        download_items.append((lib_url, lib_path))
                    else:
                        jar_filename = f"{artifact_name}-{version}.jar"
                        lib_path = os.path.join(self.game_root, "libraries", group_path.replace("/", os.sep), artifact_name, version, jar_filename)
                        if os.path.exists(lib_path):
                            existing_count += 1
                            continue
                        lib_url = f"https://libraries.minecraft.net/{group_path}/{artifact_name}/{version}/{jar_filename}"
                        download_items.append((lib_url, lib_path))

        if download_items:
            if progress_callback:
                progress_callback(0, f"开始下载 {len(download_items)} 个库文件（{existing_count} 个已存在）...")
            downloader = MultiDownloader(max_workers=8)
            downloader.download_files(download_items, progress_callback)
        else:
            if progress_callback:
                progress_callback(0, f"库文件已全部就绪（{existing_count} 个）")
        return len(download_items)

    def download_assets(self, asset_id, asset_url=None, progress_callback=None):
        index_dir = os.path.join(self.game_root, "assets", "indexes")
        objects_dir = os.path.join(self.game_root, "assets", "objects")
        os.makedirs(index_dir, exist_ok=True)
        os.makedirs(objects_dir, exist_ok=True)

        index_path = os.path.join(index_dir, f"{asset_id}.json")
        if not os.path.exists(index_path):
            if asset_url:
                index_url = asset_url
            else:
                index_url = f"https://piston-meta.mojang.com/mc/assets/indexes/{asset_id}.json"
            try:
                if progress_callback:
                    progress_callback(0, "正在下载资源索引...")
                resp = requests.get(index_url, timeout=30, verify=False)
                resp.raise_for_status()
                with open(index_path, "w", encoding="utf-8") as f:
                    f.write(resp.text)
            except Exception as e:
                if progress_callback:
                    progress_callback(0, f"下载资源索引失败: {e}")
                return 0

        if not os.path.exists(index_path):
            return 0

        with open(index_path, "r", encoding="utf-8") as f:
            idx = json.load(f)

        objects = idx.get("objects", {})
        total = len(objects)

        download_items = []
        existing_count = 0
        mirrors = [
            "https://resources.download.minecraft.net",
            "https://bmclapi2.bangbang93.com/assets/objects",
        ]

        for name, meta in objects.items():
            hash_str = meta.get('hash', '')
            if not hash_str:
                continue
            prefix = hash_str[:2]
            obj_path = os.path.join(objects_dir, prefix, hash_str)
            if os.path.exists(obj_path):
                existing_count += 1
            else:
                for mirror in mirrors:
                    obj_url = f"{mirror}/{prefix}/{hash_str}"
                    download_items.append((obj_url, obj_path))
                    break

        if download_items:
            if progress_callback:
                progress_callback(0, f"开始下载 {len(download_items)} 个资源文件（{existing_count} 个已存在）...")
            downloader = MultiDownloader(max_workers=16)
            downloader.download_files(download_items, progress_callback)
            return len(download_items)
        else:
            if progress_callback:
                progress_callback(0, f"资源文件已全部就绪（{existing_count} 个）")
            return total

    def parse(self, ver_id, ver_folder_name=None, json_filename=None, ver_type="vanilla", progress_callback=None):
        target_version = ver_id
        ver_json_path = None

        if ver_folder_name is not None and json_filename is not None:
            custom_dir = os.path.join(self.game_root, "versions", ver_folder_name)
            ver_json_path = os.path.join(custom_dir, json_filename)
        else:
            if self.versions_root.exists():
                for dir_full in self.versions_root.iterdir():
                    if not dir_full.is_dir():
                        continue
                    if dir_full.name == "natives":
                        continue
                    json_list = [f for f in os.listdir(dir_full) if f.endswith(".json")]
                    if len(json_list) != 1:
                        continue
                    json_file = dir_full / json_list[0]
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            jdata = json.load(f)
                        if jdata.get("inheritsFrom") == target_version or jdata.get("id") == target_version:
                            ver_json_path = str(json_file)
                            break
                    except Exception:
                        continue
            if ver_json_path is None:
                old_ver_folder = os.path.join(self.game_root, "versions", target_version)
                ver_json_path = os.path.join(old_ver_folder, f"{target_version}.json")

        with open(ver_json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if progress_callback:
            progress_callback(10, "正在分析版本信息...")

        real_ver_id = raw.get("id", target_version)
        cfg = {}
        cfg["id"] = real_ver_id
        cfg["mainClass"] = raw["mainClass"]

        if "arguments" in raw:
            cfg["raw_args"] = self.filter_valid_args(raw["arguments"]["game"])
            cfg["jvm_args"] = self.filter_valid_args(raw.get("arguments", {}).get("jvm", []))
        else:
            mc_args = raw.get("minecraftArguments", "")
            cfg["raw_args"] = mc_args.split(" ") if mc_args else []
            cfg["jvm_args"] = []

        loader = get_loader(ver_type)
        cfg["libraries"], cfg["natives"] = loader.resolve_libraries(raw["libraries"], self.game_root)
        cfg["loader"] = loader

        asset_index = raw.get("assetIndex", {})
        cfg["assets_id"] = asset_index.get("id", "")
        asset_url = asset_index.get("url", "")
        cfg["jar_path"] = os.path.join(self.ver_dir, real_ver_id, f"{real_ver_id}.jar")
        cfg["ver_type"] = ver_type

        mco_exists = check_and_create_mco(real_ver_id, self.game_root)

        if not mco_exists:
            if progress_callback:
                progress_callback(20, "首次启动，正在下载依赖库...")
            self.download_libraries(raw["libraries"], progress_callback)

            if progress_callback:
                progress_callback(60, "正在下载资源文件...")
            self.download_assets(cfg["assets_id"], asset_url, progress_callback)
        else:
            if progress_callback:
                progress_callback(30, "已缓存，跳过资源下载...")

        if progress_callback:
            progress_callback(80, "正在提取原生库...")
        self.extract_natives(cfg["natives"])

        if progress_callback:
            progress_callback(100, "准备完成")
        return cfg

    def extract_natives(self, native_list):
        for path in native_list:
            if not os.path.exists(path):
                continue
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(self.natives_dir)

    def filter_valid_args(self, arg_list):
        clean = []
        for item in arg_list:
            if isinstance(item, str):
                clean.append(item)
        return clean

class AssetChecker:
    def __init__(self, game_root):
        self.game_root = game_root
        self.index_dir = os.path.join(game_root, "assets", "indexes")
        self.objects_dir = os.path.join(game_root, "assets", "objects")

    def scan_missing(self, asset_id):
        index_path = os.path.join(self.index_dir, f"{asset_id}.json")
        with open(index_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
        missing = []
        for name, meta in idx["objects"].items():
            hash_str = meta.get('hash', '')
            if not hash_str:
                continue
            prefix = hash_str[:2]
            obj_full = os.path.join(self.objects_dir, prefix, hash_str)
            if not os.path.exists(obj_full):
                missing.append(hash_str)
        return missing

class AccountManager:
    def create_offline(self, name):
        import uuid as uuid_module
        return {
            "name": name,
            "uuid": str(uuid_module.uuid4()).replace("-", ""),
            "accessToken": str(uuid_module.uuid4()),
            "clientToken": str(uuid_module.uuid4()),
            "authType": "offline",
            "userType": "offline"
        }

    def microsoft_oauth(self):
        pass

class DownloadEngine(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal()

    def batch_download(self, url_list, root):
        def worker():
            total = len(url_list)
            for idx, url in enumerate(url_list):
                self.single_download(url, root)
                self.progress.emit(int(100 * (idx + 1) / total))
            self.finished.emit()
        threading.Thread(target=worker, daemon=True).start()

    def single_download(self, url, out_root):
        resp = requests.get(url, stream=True, timeout=15)
        filename = url.split("/")[-1]
        full_path = os.path.join(out_root, filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)

class JavaLaunchEngine:
    def __init__(self, java_exe, game_root):
        self.java = java_exe
        self.root = game_root
        self.natives_path = os.path.join(game_root, "versions", "natives")

    def _replace_vars(self, arg, cfg, account):
        replacements = {
            "${natives_directory}": self.natives_path,
            "${library_directory}": os.path.join(self.root, "libraries"),
            "${classpath_separator}": os.pathsep,
            "${game_directory}": self.root,
            "${assets_root}": os.path.join(self.root, "assets"),
            "${assets_index_name}": cfg["assets_id"],
            "${version_name}": cfg["id"],
            "${auth_player_name}": account["name"],
            "${auth_uuid}": account["uuid"],
            "${auth_access_token}": account["accessToken"],
            "${auth_session}": account["accessToken"],
            "${user_type}": account["authType"],
            "${user_properties}": "{}",
        }
        for key, value in replacements.items():
            arg = arg.replace(key, value)
        return arg

    def launch(self, cfg, account, min_mem=1024, max_mem=4096, ver_type="vanilla"):
        libs = cfg["libraries"]
        game_jar = cfg["jar_path"]
        full_cp_list = libs + [game_jar]
        full_cp = os.pathsep.join(full_cp_list)

        env = os.environ.copy()
        env["PATH"] = self.natives_path + os.pathsep + env["PATH"]

        base_jvm = [
            f"-Xms{min_mem}M",
            f"-Xmx{max_mem}M",
            f"-Djava.library.path={self.natives_path}",
            "-Djava.net.preferIPv6Addresses=false",
            "-Djava.net.preferIPv4Stack=true",
            "-Dminecraft.launcher.brand=MCOpen",
            "-Dminecraft.launcher.version=1.0.0",
            "-Daccessibility.screen_reader=false",
            "-Dawt.accessibility=false",
            "-Djavax.accessibility.assistive_technologies=",
            "--add-opens", "java.base/java.lang=ALL-UNNAMED",
            "--add-opens", "java.base/java.lang.invoke=ALL-UNNAMED",
            "--add-opens", "java.base/java.util=ALL-UNNAMED",
            "--add-opens", "java.base/java.io=ALL-UNNAMED",
            "--add-opens", "java.base/java.lang.reflect=ALL-UNNAMED",
        ]

        json_jvm = cfg.get("jvm_args", [])
        json_jvm = [self._replace_vars(arg, cfg, account) for arg in json_jvm]

        loader = cfg.get("loader", VanillaLoader())
        final_jvm = loader.build_jvm_args(base_jvm, json_jvm, full_cp)

        raw_args = cfg["raw_args"]
        raw_args = [self._replace_vars(arg, cfg, account) for arg in raw_args]
        final_game_args = loader.build_game_args(raw_args)

        args = [self.java] + final_jvm + [cfg["mainClass"]] + final_game_args
        proc = subprocess.Popen(args, cwd=self.root, env=env)
        return proc

class UnifiedLaunchCore:
    def __init__(self, game_root, java_path):
        self.java_engine = JavaLaunchEngine(java_path, game_root)

    def launch(self, edition, cfg, account, min_mem, max_mem, ver_type):
        if edition == "java":
            return self.java_engine.launch(cfg, account, min_mem, max_mem, ver_type)