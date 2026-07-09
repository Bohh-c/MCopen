import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


class MultiDownloader:
    def __init__(self, max_workers=8):
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._total_files = 0
        self._downloaded_files = 0
        self._current_file = ""

    def download_file(self, url, save_path, progress_callback=None, timeout=30):
        try:
            resp = requests.get(url, stream=True, timeout=timeout, verify=False)
            resp.raise_for_status()
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0

            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        pct = int(100 * downloaded / total_size)
                        progress_callback(pct, f"下载中: {os.path.basename(save_path)} ({downloaded//1024}/{total_size//1024} KB)")
            return True, save_path
        except Exception as e:
            return False, str(e)

    def download_files(self, tasks, progress_callback=None):
        self._total_files = len(tasks)
        self._downloaded_files = 0

        def task_wrapper(url, save_path):
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            if os.path.exists(save_path):
                with self._lock:
                    self._downloaded_files += 1
                return True, save_path

            with self._lock:
                self._current_file = os.path.basename(save_path)

            success, result = self.download_file(url, save_path)

            with self._lock:
                self._downloaded_files += 1
                pct = int(100 * self._downloaded_files / self._total_files)
                if progress_callback:
                    progress_callback(pct, f"下载中: {self._current_file} ({self._downloaded_files}/{self._total_files})")

            return success, result

        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(task_wrapper, url, path) for url, path in tasks]
            for future in as_completed(futures):
                results.append(future.result())

        success_count = sum(1 for s, _ in results if s)
        if progress_callback:
            progress_callback(100, f"下载完成: {success_count}/{self._total_files}")

        return success_count == self._total_files, f"{success_count}/{self._total_files} 文件下载成功"
