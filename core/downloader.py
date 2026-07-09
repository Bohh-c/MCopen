"""MC版本下载核心 - 支持客户端和服务端，带SHA1校验"""

import os
import hashlib
import requests


MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
MOJANG_BASE = "https://piston-data.mojang.com/v1/objects"


def calc_sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def fetch_version_manifest(timeout=20):
    try:
        resp = requests.get(MANIFEST_URL, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"网络请求失败: {e}")
    except ValueError as e:
        raise Exception(f"JSON解析失败: {e}, 响应内容: {resp.text[:500]}")


def find_version(manifest, version_id):
    for v in manifest["versions"]:
        if v["id"] == version_id:
            return v
    return None


def get_version_meta(version_info, timeout=15):
    try:
        url = version_info["url"]
        url = url.replace("https://launchermeta.mojang.com/", "https://bmclapi2.bangbang93.com/")
        url = url.replace("https://launcher.mojang.com/", "https://bmclapi2.bangbang93.com/")
        resp = requests.get(url, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"获取版本信息失败: {e}")
    except ValueError as e:
        raise Exception(f"版本信息JSON解析失败: {e}")


def download_file(url, save_path, progress_callback=None, timeout=30):
    try:
        resp = requests.get(url, stream=True, timeout=timeout, verify=False)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    pct = int(100 * downloaded / total)
                    progress_callback(pct, downloaded)
        return downloaded
    except requests.exceptions.RequestException as e:
        raise Exception(f"下载文件失败: {e}")


def download_client(version_id, save_dir, progress_callback=None):
    versions_dir = os.path.join(save_dir, "versions", version_id)
    os.makedirs(versions_dir, exist_ok=True)
    try:
        manifest = fetch_version_manifest()
        target_ver = find_version(manifest, version_id)
        if not target_ver:
            return False, f"不存在版本 {version_id}"

        ver_meta = get_version_meta(target_ver)
        downloads = ver_meta.get("downloads", {})
        if "client" not in downloads:
            return False, f"{version_id} 无官方客户端"

        json_path = os.path.join(versions_dir, f"{version_id}.json")
        jar_path = os.path.join(versions_dir, f"{version_id}.jar")

        if progress_callback:
            progress_callback(5, "正在保存版本信息...")
        with open(json_path, "w", encoding="utf-8") as f:
            import json
            json.dump(ver_meta, f, indent=2)

        client = downloads["client"]
        url = client["url"]
        expect_sha = client["sha1"]

        if os.path.exists(jar_path):
            local_sha = calc_sha1(jar_path)
            if local_sha == expect_sha:
                return True, f"已存在且校验通过：{jar_path}"
            os.remove(jar_path)

        if progress_callback:
            progress_callback(10, "开始下载客户端...")
        download_file(url, jar_path, progress_callback)

        final_sha = calc_sha1(jar_path)
        if final_sha == expect_sha:
            return True, f"下载完成，校验通过 SHA1={final_sha}\n目录: {versions_dir}"
        os.remove(jar_path)
        return False, "哈希校验失败，文件已删除"
    except Exception as e:
        return False, str(e)


def download_server(version_id, save_dir, progress_callback=None):
    os.makedirs(save_dir, exist_ok=True)
    try:
        manifest = fetch_version_manifest()
        target_ver = find_version(manifest, version_id)
        if not target_ver:
            return False, f"不存在版本 {version_id}"

        ver_meta = get_version_meta(target_ver)
        downloads = ver_meta.get("downloads", {})
        if "server" not in downloads:
            return False, f"{version_id} 无官方 server.jar"

        server = downloads["server"]
        url = server["url"]
        expect_sha = server["sha1"]
        save_path = os.path.join(save_dir, f"{version_id}-server.jar")

        if os.path.exists(save_path):
            local_sha = calc_sha1(save_path)
            if local_sha == expect_sha:
                return True, f"已存在且校验通过：{save_path}"
            os.remove(save_path)

        if progress_callback:
            progress_callback(0, "开始下载服务端...")
        download_file(url, save_path, progress_callback)

        final_sha = calc_sha1(save_path)
        if final_sha == expect_sha:
            return True, f"下载完成，校验通过 SHA1={final_sha}"
        os.remove(save_path)
        return False, "哈希校验失败，文件已删除"
    except Exception as e:
        return False, str(e)