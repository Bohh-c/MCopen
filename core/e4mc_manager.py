import os
import re
import requests
import threading
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal


class E4MCManager(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, game_root):
        super().__init__()
        self.game_root = Path(game_root)
        self.mods_dir = self.game_root / "mods"
        self.mods_dir.mkdir(parents=True, exist_ok=True)
        self.downloading = False
        self.cancel_flag = False

    def get_local_path(self, mc_version):
        return self.mods_dir / f"e4mc-{mc_version}.jar"

    def is_installed(self, mc_version):
        return self.get_local_path(mc_version).exists()

    def _extract_base_version(self, version_id):
        match = re.match(r'^(\d+\.\d+(?:\.\d+)?)', version_id)
        if match:
            return match.group(1)
        return version_id

    def _get_download_url_from_modrinth(self, mc_version, loader_type):
        base_version = self._extract_base_version(mc_version)
        api_url = "https://api.modrinth.com/v2/project/e4mc/version"
        try:
            resp = requests.get(api_url, timeout=10)
            if resp.status_code != 200:
                return None
            versions = resp.json()
            candidates = []
            for v in versions:
                game_versions = v.get("game_versions", [])
                if base_version in game_versions:
                    candidates.append(v)
            if not candidates:
                major_minor = ".".join(base_version.split(".")[:2])
                for v in versions:
                    game_versions = v.get("game_versions", [])
                    if major_minor in game_versions:
                        candidates.append(v)
            for v in candidates:
                loaders = v.get("loaders", [])
                if loader_type == "fabric" and "fabric" not in loaders:
                    continue
                if loader_type == "quilt" and "quilt" not in loaders:
                    continue
                if loader_type == "forge" and "forge" not in loaders:
                    continue
                if loader_type == "neoforge" and "neoforge" not in loaders:
                    continue
                for file in v.get("files", []):
                    if file.get("primary", False) or file.get("file_type") == "primary":
                        return file.get("url")
            return None
        except Exception:
            return None

    def _try_download(self, url, target_path):
        try:
            resp = requests.get(url, stream=True, timeout=30)
            if resp.status_code != 200:
                return False
            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            with open(target_path, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    if self.cancel_flag:
                        target_path.unlink(missing_ok=True)
                        return False
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int(100 * downloaded / total)
                        self.progress.emit(pct, f"下载中 {pct}%")
            self.progress.emit(100, "下载完成")
            return True
        except Exception:
            if target_path.exists():
                target_path.unlink()
            return False

    def ensure_installed(self, mc_version, loader_type):
        if self.is_installed(mc_version):
            self.progress.emit(100, "模组已存在")
            return True, "e4mc 模组已就绪"

        self.progress.emit(0, "正在获取下载链接...")
        download_url = self._get_download_url_from_modrinth(mc_version, loader_type)
        if download_url:
            target_path = self.get_local_path(mc_version)
            self.progress.emit(10, f"开始下载 e4mc-{mc_version}.jar...")
            if self._try_download(download_url, target_path):
                return True, "e4mc 模组已下载"
            else:
                return False, "下载失败，请检查网络连接"
        else:
            base_ver = self._extract_base_version(mc_version)
            return False, f"未找到 e4mc {base_ver} 版本 ({loader_type})，请检查网络或稍后重试"

    def install_async(self, mc_version, loader_type):
        if self.downloading:
            return
        self.downloading = True
        self.cancel_flag = False
        threading.Thread(target=self._install_worker, args=(mc_version, loader_type), daemon=True).start()

    def _install_worker(self, mc_version, loader_type):
        ok, msg = self.ensure_installed(mc_version, loader_type)
        self.downloading = False
        self.finished.emit(ok, msg)

    def cancel(self):
        self.cancel_flag = True

    def cleanup(self, mc_version=None):
        if mc_version:
            target = self.get_local_path(mc_version)
            if target.exists():
                target.unlink()
            return True
        count = 0
        for f in self.mods_dir.glob("e4mc-*.jar"):
            f.unlink()
            count += 1
        return count > 0

    def get_public_address(self, mc_version):
        base_ver = self._extract_base_version(mc_version)
        return f"e4mc-{base_ver}.e4mc.com"