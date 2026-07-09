import os
import shutil
import time
import subprocess
from datetime import datetime


class CrashDetector:
    def __init__(self, game_root):
        self.game_root = game_root
        self.process = None
        self.start_time = None
        self.crash_reports_dir = os.path.join(game_root, "crash-reports")
        self.logs_dir = os.path.join(game_root, "logs")
        self.last_crash_file = None
        self._initial_crash_files = set()

    def monitor_process(self, proc):
        self.process = proc
        self.start_time = time.time()
        self._scan_existing_crashes()

    def _scan_existing_crashes(self):
        self._initial_crash_files = set()
        if os.path.exists(self.crash_reports_dir):
            for f in os.listdir(self.crash_reports_dir):
                if f.startswith("crash-") and f.endswith(".txt"):
                    fp = os.path.join(self.crash_reports_dir, f)
                    self._initial_crash_files.add(fp)

    def is_running(self):
        if self.process is None:
            return False
        if not isinstance(self.process, subprocess.Popen):
            return False
        return self.process.poll() is None

    def wait_for_exit(self, timeout=None):
        if self.process is None:
            return None
        try:
            return self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def get_exit_code(self):
        if self.process is None:
            return None
        return self.process.poll()

    def check_for_crash(self):
        if not os.path.exists(self.crash_reports_dir):
            return None

        latest_file = None
        latest_time = 0

        for f in os.listdir(self.crash_reports_dir):
            if f.startswith("crash-") and f.endswith(".txt"):
                fp = os.path.join(self.crash_reports_dir, f)
                if fp in self._initial_crash_files:
                    continue
                mt = os.path.getmtime(fp)
                if mt > latest_time:
                    latest_time = mt
                    latest_file = fp

        if latest_file:
            self.last_crash_file = latest_file
            return latest_file

        return None

    def get_crash_report(self, crash_file=None):
        if crash_file is None:
            crash_file = self.last_crash_file
        if crash_file and os.path.exists(crash_file):
            with open(crash_file, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        return None

    def get_latest_log(self):
        if not os.path.exists(self.logs_dir):
            return None, None

        latest_file = None
        latest_time = 0

        for f in os.listdir(self.logs_dir):
            if f.endswith(".log"):
                fp = os.path.join(self.logs_dir, f)
                mt = os.path.getmtime(fp)
                if mt > latest_time:
                    latest_time = mt
                    latest_file = fp

        if latest_file and os.path.exists(latest_file):
            with open(latest_file, "r", encoding="utf-8", errors="replace") as f:
                return f.read(), os.path.basename(latest_file)
        return None, None

    def export_logs(self, export_dir=None):
        if export_dir is None:
            export_dir = os.path.join(
                os.path.dirname(self.game_root),
                "minecraft_logs_export",
                datetime.now().strftime("%Y%m%d_%H%M%S")
            )
        os.makedirs(export_dir, exist_ok=True)

        exported_files = []

        if os.path.exists(self.logs_dir):
            log_dest = os.path.join(export_dir, "logs")
            shutil.copytree(self.logs_dir, log_dest)
            exported_files.append(f"logs/")

        if os.path.exists(self.crash_reports_dir):
            crash_dest = os.path.join(export_dir, "crash-reports")
            shutil.copytree(self.crash_reports_dir, crash_dest)
            exported_files.append(f"crash-reports/")

        launcher_log = os.path.join(os.path.dirname(self.game_root), "launcher.log")
        if os.path.exists(launcher_log):
            shutil.copy(launcher_log, export_dir)
            exported_files.append("launcher.log")

        return export_dir, exported_files

    def analyze_crash(self, crash_content):
        if not crash_content:
            return {"error": "No crash content"}

        lines = crash_content.split("\n")
        result = {
            "type": "unknown",
            "description": "",
            "cause": "",
            "java_version": "",
            "minecraft_version": "",
            "suggestion": "",
        }

        for line in lines:
            if "---- Minecraft Crash Report ----" in line:
                result["type"] = "minecraft_crash"
            elif "java.lang.OutOfMemoryError" in line:
                result["type"] = "out_of_memory"
                result["description"] = "Java 内存溢出"
                result["suggestion"] = "请尝试增加最大内存分配 (Xmx)"
            elif "java.lang.NullPointerException" in line:
                result["type"] = "null_pointer"
                result["description"] = "空指针异常"
            elif "java.lang.ArrayIndexOutOfBoundsException" in line:
                result["type"] = "array_out_of_bounds"
                result["description"] = "数组越界"
            elif "java.lang.ClassNotFoundException" in line:
                result["type"] = "class_not_found"
                result["description"] = "类找不到"
                result["suggestion"] = "可能是模组冲突或文件损坏"
            elif "java.lang.NoClassDefFoundError" in line:
                result["type"] = "class_def_error"
                result["description"] = "类定义错误"
            elif "Forge" in line and "mod" in line.lower():
                result["type"] = "forge_mod_conflict"
                result["description"] = "Forge 模组冲突"
                result["suggestion"] = "尝试禁用最近添加的模组"
            elif "Fabric" in line and "mod" in line.lower():
                result["type"] = "fabric_mod_conflict"
                result["description"] = "Fabric 模组冲突"
                result["suggestion"] = "尝试禁用最近添加的模组"
            elif "Version:" in line:
                result["minecraft_version"] = line.strip()
            elif "Java Version:" in line:
                result["java_version"] = line.strip()

        if result["description"] == "":
            for i, line in enumerate(lines):
                if "Caused by:" in line:
                    result["cause"] = line.strip()
                    if i + 1 < len(lines):
                        result["description"] = lines[i + 1].strip()
                    break

        if result["type"] == "unknown" and result["cause"]:
            result["type"] = "other"

        return result