import os
import json
import requests
import shutil
import zipfile
import xml.etree.ElementTree as ET
import re
from pathlib import Path

FABRIC_META = "https://meta.fabricmc.net/v2"
QUILT_META = "https://meta.quiltmc.org/v3"
FORGE_MAVEN = "https://maven.minecraftforge.net"
NEOFORGE_MAVEN = "https://maven.neoforged.net/releases"
MINECRAFT_LIBRARIES = "https://libraries.minecraft.net"
MOJANG_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest.json"


def fetch_fabric_versions(game_version=None):
    try:
        if game_version:
            url = f"{FABRIC_META}/versions/loader/{game_version}"
        else:
            url = f"{FABRIC_META}/versions/game"
        resp = requests.get(url, timeout=15, verify=False)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def fetch_quilt_versions(game_version=None):
    try:
        if game_version:
            url = f"{QUILT_META}/versions/loader/{game_version}"
        else:
            url = f"{QUILT_META}/versions/game"
        resp = requests.get(url, timeout=15, verify=False)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def fetch_forge_versions(game_version):
    try:
        url = f"{FORGE_MAVEN}/net/minecraftforge/forge/maven-metadata.xml"
        resp = requests.get(url, timeout=15, verify=False)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        versions = []
        for version in root.findall(".//version"):
            ver_text = version.text
            if ver_text and ver_text.startswith(f"{game_version}-"):
                forge_ver = ver_text.split("-", 1)[1]
                versions.append({"version": forge_ver})
        return versions
    except Exception:
        return []


def fetch_neoforge_versions(game_version):
    try:
        major = ".".join(game_version.split(".")[:2])
        url = f"{NEOFORGE_MAVEN}/net/neoforged/neoforge/maven-metadata.xml"
        resp = requests.get(url, timeout=15, verify=False)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        versions = []
        for version in root.findall(".//version"):
            ver_text = version.text
            if ver_text and ver_text.startswith(major):
                versions.append({"version": ver_text})
        return versions
    except Exception:
        return []


def fetch_all_mc_versions():
    try:
        url = MOJANG_MANIFEST
        resp = requests.get(url, timeout=20, verify=False)
        resp.raise_for_status()
        data = resp.json()
        versions = [v["id"] for v in data.get("versions", []) if v.get("type") == "release"]
        return versions[:50]
    except Exception:
        return ["1.21.4", "1.21.3", "1.21.1", "1.21", "1.20.6", "1.20.4", "1.20.1",
                "1.19.4", "1.19.2", "1.18.2", "1.17.1", "1.16.5", "1.12.2"]


def download_file(url, path, progress_cb=None, timeout=(10, 30)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    resp = requests.get(url, stream=True, timeout=timeout, verify=False)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            downloaded += len(chunk)
            if progress_cb and total > 0:
                pct = int(100 * downloaded / total)
                progress_cb(pct, f"下载中 {downloaded//1024} KB")
    return downloaded


def install_fabric(game_root, game_version, loader_version, progress_cb=None):
    if progress_cb:
        progress_cb(0, "准备安装 Fabric...")
    versions_dir = os.path.join(game_root, "versions")
    version_name = f"fabric-loader-{loader_version}-{game_version}"
    version_dir = os.path.join(versions_dir, version_name)
    os.makedirs(version_dir, exist_ok=True)

    try:
        if progress_cb:
            progress_cb(5, "获取 Fabric 版本信息...")
        profile_url = f"{FABRIC_META}/versions/loader/{game_version}/{loader_version}/profile/json"
        resp = requests.get(profile_url, timeout=30, verify=False)
        resp.raise_for_status()
        profile_json = resp.json()

        json_path = os.path.join(version_dir, f"{version_name}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(profile_json, f, indent=2)

        if progress_cb:
            progress_cb(20, "下载 Fabric 库文件...")
        _download_loader_libraries(game_root, profile_json.get("libraries", []), progress_cb, start_pct=20, end_pct=90)

        jar_path = os.path.join(versions_dir, game_version, f"{game_version}.jar")
        if os.path.exists(jar_path):
            target_jar = os.path.join(version_dir, f"{version_name}.jar")
            if not os.path.exists(target_jar):
                shutil.copy2(jar_path, target_jar)

        if progress_cb:
            progress_cb(100, "Fabric 装好了")
        return True, version_name
    except Exception as e:
        return False, str(e)


def install_quilt(game_root, game_version, loader_version, progress_cb=None):
    if progress_cb:
        progress_cb(0, "准备安装 Quilt...")
    versions_dir = os.path.join(game_root, "versions")
    version_name = f"quilt-loader-{loader_version}-{game_version}"
    version_dir = os.path.join(versions_dir, version_name)
    os.makedirs(version_dir, exist_ok=True)

    try:
        if progress_cb:
            progress_cb(5, "获取 Quilt 版本信息...")
        profile_url = f"{QUILT_META}/versions/loader/{game_version}/{loader_version}/profile/json"
        resp = requests.get(profile_url, timeout=30, verify=False)
        resp.raise_for_status()
        profile_json = resp.json()

        json_path = os.path.join(version_dir, f"{version_name}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(profile_json, f, indent=2)

        if progress_cb:
            progress_cb(20, "下载 Quilt 库文件...")
        _download_loader_libraries(game_root, profile_json.get("libraries", []), progress_cb, start_pct=20, end_pct=90)

        jar_path = os.path.join(versions_dir, game_version, f"{game_version}.jar")
        if os.path.exists(jar_path):
            target_jar = os.path.join(version_dir, f"{version_name}.jar")
            if not os.path.exists(target_jar):
                shutil.copy2(jar_path, target_jar)

        if progress_cb:
            progress_cb(100, "Quilt 装好了")
        return True, version_name
    except Exception as e:
        return False, str(e)


def install_forge(game_root, game_version, forge_version, progress_cb=None):
    if progress_cb:
        progress_cb(0, "下载 Forge 安装器...")

    versions_dir = os.path.join(game_root, "versions")
    version_name = f"{game_version}-forge-{forge_version}"
    version_dir = os.path.join(versions_dir, version_name)

    if os.path.exists(version_dir):
        shutil.rmtree(version_dir)
    os.makedirs(version_dir, exist_ok=True)

    installer_path = os.path.join(version_dir, "forge-installer.jar")

    url = f"{FORGE_MAVEN}/net/minecraftforge/forge/{game_version}-{forge_version}/forge-{game_version}-{forge_version}-installer.jar"

    try:
        if progress_cb:
            progress_cb(5, "下载安装器...")
        download_file(url, installer_path, progress_cb, timeout=(10, 30))

        if not os.path.exists(installer_path) or os.path.getsize(installer_path) < 10240:
            return False, f"Forge {forge_version} 下载失败"

        if progress_cb:
            progress_cb(40, "解压安装器...")

        success, err = _extract_forge_installer(game_root, installer_path, version_dir, version_name, game_version, forge_version, progress_cb)
        if not success:
            return False, err

        try:
            os.remove(installer_path)
        except Exception:
            pass

        json_path = os.path.join(version_dir, f"{version_name}.json")
        if not os.path.exists(json_path):
            return False, f"安装失败：未生成 {version_name}.json"

        jar_path = os.path.join(version_dir, f"{version_name}.jar")
        if not os.path.exists(jar_path):
            client_jar = os.path.join(versions_dir, game_version, f"{game_version}.jar")
            if os.path.exists(client_jar):
                shutil.copy2(client_jar, jar_path)

        if not os.path.exists(jar_path):
            return False, f"缺少 {version_name}.jar，请先下载 {game_version} 客户端"

        if progress_cb:
            progress_cb(100, "Forge 装好了")
        return True, version_name
    except Exception as e:
        return False, f"安装失败: {e}"


def install_neoforge(game_root, game_version, neoforge_version, progress_cb=None):
    if progress_cb:
        progress_cb(0, "下载 NeoForge 安装器...")

    versions_dir = os.path.join(game_root, "versions")
    version_name = f"{game_version}-neoforge-{neoforge_version}"
    version_dir = os.path.join(versions_dir, version_name)

    if os.path.exists(version_dir):
        shutil.rmtree(version_dir)
    os.makedirs(version_dir, exist_ok=True)

    installer_path = os.path.join(version_dir, "neoforge-installer.jar")

    url = f"{NEOFORGE_MAVEN}/net/neoforged/neoforge/{neoforge_version}/neoforge-{neoforge_version}-installer.jar"

    try:
        if progress_cb:
            progress_cb(5, "下载安装器...")
        download_file(url, installer_path, progress_cb, timeout=(10, 30))

        if not os.path.exists(installer_path) or os.path.getsize(installer_path) < 10240:
            return False, f"NeoForge {neoforge_version} 下载失败"

        if progress_cb:
            progress_cb(40, "解压安装器...")

        success, err = _extract_forge_installer(game_root, installer_path, version_dir, version_name, game_version, neoforge_version, progress_cb, is_neoforge=True)
        if not success:
            return False, err

        try:
            os.remove(installer_path)
        except Exception:
            pass

        json_path = os.path.join(version_dir, f"{version_name}.json")
        if not os.path.exists(json_path):
            return False, f"安装失败：未生成 {version_name}.json"

        jar_path = os.path.join(version_dir, f"{version_name}.jar")
        if not os.path.exists(jar_path):
            client_jar = os.path.join(versions_dir, game_version, f"{game_version}.jar")
            if os.path.exists(client_jar):
                shutil.copy2(client_jar, jar_path)

        if not os.path.exists(jar_path):
            return False, f"缺少 {version_name}.jar，请先下载 {game_version} 客户端"

        if progress_cb:
            progress_cb(100, "NeoForge 装好了")
        return True, version_name
    except Exception as e:
        return False, f"安装失败: {e}"


def _detect_main_class_from_installer(zf, loader_version, is_neoforge):
    try:
        manifest_path = "META-INF/MANIFEST.MF"
        if manifest_path in zf.namelist():
            with zf.open(manifest_path) as f:
                content = f.read().decode("utf-8", errors="ignore")
                for line in content.splitlines():
                    if "Main-Class:" in line:
                        main_class = line.split(":", 1)[1].strip()
                        return main_class
    except:
        pass

    if is_neoforge:
        return "cpw.mods.bootstraplauncher.BootstrapLauncher"

    try:
        ver_num = int(loader_version.split('.')[0]) if loader_version and loader_version.split('.')[0].isdigit() else 0
        if ver_num >= 36:
            return "net.minecraftforge.fml.loading.FMLClientLaunchProvider"
    except:
        pass

    return "net.minecraft.launchwrapper.Launch"


def _extract_forge_installer(game_root, installer_path, version_dir, version_name, game_version, loader_version, progress_cb=None, is_neoforge=False):
    libs_dir = os.path.join(game_root, "libraries")
    os.makedirs(libs_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(installer_path, "r") as zf:
            version_json_name = None
            for name in zf.namelist():
                if name.startswith("versions/") and name.endswith(".json"):
                    version_json_name = name
                    break

            if version_json_name:
                if progress_cb:
                    progress_cb(45, "提取 JSON...")
                zf.extract(version_json_name, version_dir)
                src_json = os.path.join(version_dir, version_json_name)
                dst_json = os.path.join(version_dir, f"{version_name}.json")
                with open(src_json, "r", encoding="utf-8") as f:
                    profile = json.load(f)
                with open(dst_json, "w", encoding="utf-8") as f:
                    json.dump(profile, f, indent=2)
                shutil.rmtree(os.path.join(version_dir, "versions"), ignore_errors=True)

                if progress_cb:
                    progress_cb(50, "下载库文件...")
                _download_loader_libraries(game_root, profile.get("libraries", []), progress_cb, start_pct=50, end_pct=90)
            else:
                if progress_cb:
                    progress_cb(45, "生成 JSON...")
                main_class = _detect_main_class_from_installer(zf, loader_version, is_neoforge)
                profile = _generate_forge_profile(game_root, game_version, loader_version, main_class, is_neoforge)
                dst_json = os.path.join(version_dir, f"{version_name}.json")
                with open(dst_json, "w", encoding="utf-8") as f:
                    json.dump(profile, f, indent=2)

                if progress_cb:
                    progress_cb(50, "下载库文件...")
                _download_loader_libraries(game_root, profile.get("libraries", []), progress_cb, start_pct=50, end_pct=90)

            maven_files = []
            for name in zf.namelist():
                if name.startswith("maven/") and name.endswith(".jar"):
                    maven_files.append(name)

            if progress_cb:
                progress_cb(90, "提取 Maven 文件...")
            for name in maven_files:
                try:
                    rel_path = name[len("maven/"):]
                    target_path = os.path.join(libs_dir, rel_path.replace("/", os.sep))
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    if not os.path.exists(target_path):
                        with zf.open(name) as src, open(target_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                except Exception:
                    pass

            client_jar = os.path.join(game_root, "versions", game_version, f"{game_version}.jar")
            target_jar = os.path.join(version_dir, f"{version_name}.jar")
            if os.path.exists(client_jar) and not os.path.exists(target_jar):
                if progress_cb:
                    progress_cb(95, "复制客户端核心...")
                shutil.copy2(client_jar, target_jar)

            return True, None
    except Exception as e:
        return False, f"解压失败: {e}"


def _generate_forge_profile(game_root, game_version, loader_version, main_class, is_neoforge=False):
    if is_neoforge:
        profile = {
            "id": f"{game_version}-neoforge-{loader_version}",
            "inheritsFrom": game_version,
            "releaseTime": "2026-07-09T21:53:00+00:00",
            "type": "release",
            "mainClass": main_class,
            "arguments": {
                "game": [],
                "jvm": [
                    "-DignoreList=bootstraplauncher,securejarhandler,asm-commons,asm-util,asm-analysis,asm-tree,asm,client-extra,forge",
                    "-DmergeModules=jna-5.10.0.jar,jna-platform-5.10.0.jar",
                    "-DlibraryDirectory=${library_directory}",
                    "-p", "${classpath_separator}",
                    "--add-modules", "ALL-MODULE-PATH"
                ]
            },
            "libraries": [],
            "logging": {}
        }
        maven_group = "net.neoforged"
        artifact_id = "neoforge"
    else:
        profile = {
            "id": f"{game_version}-forge-{loader_version}",
            "inheritsFrom": game_version,
            "releaseTime": "2026-07-09T21:53:00+00:00",
            "type": "release",
            "mainClass": main_class,
            "arguments": {
                "game": [],
                "jvm": []
            },
            "libraries": [],
            "logging": {}
        }
        maven_group = "net.minecraftforge"
        artifact_id = "forge"

        try:
            ver_num = int(loader_version.split('.')[0]) if loader_version and loader_version.split('.')[0].isdigit() else 0
            if ver_num >= 36:
                profile["arguments"]["jvm"] = [
                    "-DignoreList=bootstraplauncher,securejarhandler,asm-commons,asm-util,asm-analysis,asm-tree,asm,client-extra,forge",
                    "-DmergeModules=jna-5.10.0.jar,jna-platform-5.10.0.jar",
                    "-DlibraryDirectory=${library_directory}",
                    "-p", "${classpath_separator}",
                    "--add-modules", "ALL-MODULE-PATH",
                    "--add-opens", "java.base/java.util.jar=ALL-UNNAMED",
                    "--add-opens", "java.base/java.lang.invoke=ALL-UNNAMED",
                    "--add-opens", "java.base/java.lang=ALL-UNNAMED",
                    "--add-opens", "java.base/java.nio=ALL-UNNAMED",
                    "--add-opens", "java.base/java.io=ALL-UNNAMED",
                    "--add-opens", "java.base/java.net=ALL-UNNAMED",
                    "--add-opens", "java.base/java.util=ALL-UNNAMED",
                    "--add-opens", "java.base/java.util.concurrent=ALL-UNNAMED",
                    "--add-opens", "java.base/java.util.concurrent.atomic=ALL-UNNAMED",
                    "--add-opens", "java.base/java.text=ALL-UNNAMED",
                    "--add-opens", "java.base/java.time=ALL-UNNAMED",
                    "--add-opens", "java.base/java.time.format=ALL-UNNAMED",
                    "--add-opens", "java.base/java.util.regex=ALL-UNNAMED",
                    "--add-opens", "java.base/java.util.zip=ALL-UNNAMED",
                    "--add-opens", "java.base/java.util.function=ALL-UNNAMED",
                    "--add-opens", "java.base/java.util.stream=ALL-UNNAMED",
                    "--add-opens", "java.base/java.util.random=ALL-UNNAMED",
                    "--add-opens", "java.base/java.util.logging=ALL-UNNAMED",
                    "--add-opens", "java.base/jdk.internal.loader=ALL-UNNAMED",
                    "--add-opens", "java.base/jdk.internal.ref=ALL-UNNAMED",
                    "--add-opens", "java.base/jdk.internal.misc=ALL-UNNAMED",
                    "--add-opens", "java.base/jdk.internal.module=ALL-UNNAMED",
                    "--add-opens", "java.base/sun.nio.ch=ALL-UNNAMED",
                    "--add-opens", "java.base/sun.util.calendar=ALL-UNNAMED",
                    "--add-opens", "java.management/sun.management=ALL-UNNAMED",
                    "--add-opens", "jdk.crypto.ec/sun.security.ec=ALL-UNNAMED",
                    "--add-opens", "jdk.unsupported/sun.misc=ALL-UNNAMED"
                ]
            else:
                profile["arguments"]["jvm"] = [
                    "-Djava.library.path=${natives_directory}",
                    "-Dminecraft.launcher.brand=${launcher_name}",
                    "-Dminecraft.launcher.version=${launcher_version}"
                ]
                if game_version and game_version.startswith("1.17"):
                    profile["arguments"]["jvm"].append("--add-exports=java.base/sun.security.util=ALL-UNNAMED")
                    profile["arguments"]["jvm"].append("--add-opens=java.base/java.util.jar=ALL-UNNAMED")
        except:
            profile["arguments"]["jvm"] = [
                "-Djava.library.path=${natives_directory}",
                "-Dminecraft.launcher.brand=${launcher_name}",
                "-Dminecraft.launcher.version=${launcher_version}"
            ]

    artifact_path = f"{maven_group.replace('.', '/')}/{artifact_id}/{loader_version}/{artifact_id}-{loader_version}.jar"
    artifact_url = f"{FORGE_MAVEN if not is_neoforge else NEOFORGE_MAVEN}/{artifact_path}"

    profile["libraries"].append({
        "name": f"{maven_group}:{artifact_id}:{loader_version}",
        "downloads": {
            "artifact": {
                "path": artifact_path,
                "url": artifact_url
            }
        }
    })

    if not is_neoforge:
        try:
            ver_num = int(loader_version.split('.')[0]) if loader_version and loader_version.split('.')[0].isdigit() else 0
            if ver_num >= 36:
                profile["libraries"].extend([
                    {"name": "net.minecraftforge:securejarhandler:2.1.24", "downloads": {"artifact": {"path": "net/minecraftforge/securejarhandler/2.1.24/securejarhandler-2.1.24.jar", "url": f"{MINECRAFT_LIBRARIES}/net/minecraftforge/securejarhandler/2.1.24/securejarhandler-2.1.24.jar"}}},
                    {"name": "org.ow2.asm:asm:9.5", "downloads": {"artifact": {"path": "org/ow2/asm/asm/9.5/asm-9.5.jar", "url": f"{MINECRAFT_LIBRARIES}/org/ow2/asm/asm/9.5/asm-9.5.jar"}}},
                ])
        except:
            pass

    return profile


def _download_loader_libraries(game_root, libraries, progress_cb=None, start_pct=0, end_pct=100):
    libs_dir = os.path.join(game_root, "libraries")
    os.makedirs(libs_dir, exist_ok=True)

    download_list = []
    for lib in libraries:
        url = None
        path = None
        if "downloads" in lib and "artifact" in lib["downloads"]:
            artifact = lib["downloads"]["artifact"]
            url = artifact.get("url")
            path = artifact.get("path")
        elif "name" in lib and "url" in lib:
            parts = lib["name"].split(":")
            if len(parts) >= 3:
                group, artifact_name, version = parts[0], parts[1], parts[2]
                group_path = group.replace(".", "/")
                jar_name = f"{artifact_name}-{version}.jar"
                path = f"{group_path}/{artifact_name}/{version}/{jar_name}"
                base_url = lib.get("url", "").rstrip("/")
                url = f"{base_url}/{path}"
        elif "name" in lib:
            parts = lib["name"].split(":")
            if len(parts) >= 3:
                group, artifact_name, version = parts[0], parts[1], parts[2]
                group_path = group.replace(".", "/")
                jar_name = f"{artifact_name}-{version}.jar"
                path = f"{group_path}/{artifact_name}/{version}/{jar_name}"
                url = f"{MINECRAFT_LIBRARIES}/{path}"

        if url and path:
            full_path = os.path.join(libs_dir, path.replace("/", os.sep))
            if not os.path.exists(full_path):
                download_list.append((url, full_path))

    total = len(download_list)
    for i, (url, path) in enumerate(download_list):
        try:
            if not os.path.exists(path):
                r = requests.get(url, stream=True, timeout=20, verify=False)
                if r.status_code == 200:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as f:
                        for chunk in r.iter_content(65536):
                            f.write(chunk)
        except Exception:
            pass
        if progress_cb and total > 0:
            pct = start_pct + int((end_pct - start_pct) * (i + 1) / total)
            progress_cb(min(pct, end_pct), f"库文件 ({i+1}/{total})")


def get_installed_loaders(game_root):
    versions_dir = os.path.join(game_root, "versions")
    installed = []
    if not os.path.isdir(versions_dir):
        return installed

    for dir_item in Path(versions_dir).iterdir():
        if not dir_item.is_dir():
            continue
        if dir_item.name == "natives":
            continue
        name = dir_item.name
        loader_type = None
        mc_ver = None
        loader_ver = None

        if "forge" in name.lower():
            loader_type = "forge"
            parts = name.split("-forge-")
            if len(parts) == 2:
                mc_ver = parts[0]
                loader_ver = parts[1]
        elif "neoforge" in name.lower():
            loader_type = "neoforge"
            parts = name.split("-neoforge-")
            if len(parts) == 2:
                mc_ver = parts[0]
                loader_ver = parts[1]
        elif "fabric" in name.lower():
            loader_type = "fabric"
            parts = name.split("-")
            for i, p in enumerate(parts):
                if p == "loader" and i + 1 < len(parts):
                    loader_ver = parts[i + 1]
                elif i == len(parts) - 1 and not loader_ver:
                    mc_ver = p
            if not mc_ver:
                for p in parts[2:]:
                    if p[0].isdigit() and "." in p:
                        mc_ver = p
                        break
        elif "quilt" in name.lower():
            loader_type = "quilt"
            parts = name.split("-")
            for i, p in enumerate(parts):
                if p == "loader" and i + 1 < len(parts):
                    loader_ver = parts[i + 1]
                elif i == len(parts) - 1 and not loader_ver:
                    mc_ver = p
            if not mc_ver:
                for p in parts[2:]:
                    if p[0].isdigit() and "." in p:
                        mc_ver = p
                        break

        if loader_type:
            json_files = list(dir_item.glob("*.json"))
            if json_files:
                installed.append({
                    "name": name,
                    "loader_type": loader_type,
                    "mc_version": mc_ver or "",
                    "loader_version": loader_ver or "",
                    "path": str(dir_item),
                })

    return installed


def uninstall_loader(version_path):
    try:
        if os.path.isdir(version_path):
            shutil.rmtree(version_path)
        return True, "卸载成功"
    except Exception as e:
        return False, str(e)


def scan_modrinth_mods(query="", game_version=None, loader=None, limit=20):
    try:
        params = {
            "query": query,
            "facets": [["project_type:mod"]],
            "limit": limit,
        }
        facets = [["project_type:mod"]]
        if game_version:
            facets.append([f"versions:{game_version}"])
        if loader and loader != "all":
            facets.append([f"categories:{loader}"])
        params["facets"] = json.dumps(facets)

        url = "https://api.modrinth.com/v2/search"
        resp = requests.get(url, params=params, timeout=15, verify=False)
        resp.raise_for_status()
        data = resp.json()
        return data.get("hits", [])
    except Exception:
        return []


def get_modrinth_versions(mod_id, game_version=None, loader=None):
    try:
        url = f"https://api.modrinth.com/v2/project/{mod_id}/version"
        params = {}
        if game_version:
            params["game_versions"] = json.dumps([game_version])
        if loader and loader != "all":
            params["loaders"] = json.dumps([loader])
        resp = requests.get(url, params=params, timeout=15, verify=False)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def download_mod_file(url, save_path, progress_cb=None):
    try:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        resp = requests.get(url, stream=True, timeout=60, verify=False)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total > 0:
                    pct = int(100 * downloaded / total)
                    progress_cb(pct, downloaded)
        return True, save_path
    except Exception as e:
        return False, str(e)