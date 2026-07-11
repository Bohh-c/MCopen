import sys
import subprocess
import re
import socket
from PyQt5.QtCore import QObject, pyqtSignal


class NetworkDiagnostics(QObject):
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(str, bool)

    def __init__(self):
        super().__init__()

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("114.114.114.114", 53))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "无法获取"

    def ping(self, host="114.114.114.114", count=4):
        if sys.platform == "win32":
            cmd = ["ping", "-n", str(count), host]
        else:
            cmd = ["ping", "-c", str(count), host]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8" if sys.platform == "win32" else "utf-8",
                errors="replace",
                timeout=15
            )
            output = result.stdout + result.stderr

            if "TTL" not in output and "ttl" not in output:
                return {"status": "error", "message": "网络不通，请检查网络连接"}

            stats = {"sent": count, "received": 0, "lost": count, "lost_rate": "100%", "min_ms": 0, "max_ms": 0, "avg_ms": 0}

            match_lost = re.search(r'丢失[：:]\s*(\d+)', output)
            if match_lost:
                stats["lost"] = int(match_lost.group(1))

            match_received = re.search(r'已接收[：:]\s*(\d+)', output)
            if match_received:
                stats["received"] = int(match_received.group(1))

            if not match_received and not match_lost:
                match_total = re.search(r'Packets[：:]\s*Sent\s*=\s*(\d+),\s*Received\s*=\s*(\d+),\s*Lost\s*=\s*(\d+)', output, re.IGNORECASE)
                if match_total:
                    stats["sent"] = int(match_total.group(1))
                    stats["received"] = int(match_total.group(2))
                    stats["lost"] = int(match_total.group(3))

            if stats["sent"] > 0:
                stats["lost_rate"] = f"{(stats['lost'] / stats['sent'] * 100):.0f}%"

            match_avg = re.search(r'平均[=＝]\s*(\d+)ms', output)
            if match_avg:
                stats["avg_ms"] = int(match_avg.group(1))

            match_min = re.search(r'最短[=＝]\s*(\d+)ms', output)
            if match_min:
                stats["min_ms"] = int(match_min.group(1))

            match_max = re.search(r'最长[=＝]\s*(\d+)ms', output)
            if match_max:
                stats["max_ms"] = int(match_max.group(1))

            if stats["received"] == 0:
                return {"status": "error", "message": "100% 丢包，网络不通", "stats": stats}

            return {"status": "ok", "message": f"延迟 {stats['avg_ms']} ms", "stats": stats}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "ping 超时，网络可能不稳定"}
        except Exception as e:
            return {"status": "error", "message": f"ping 失败: {e}"}

    def run_full_diagnosis(self):
        target = "114.114.114.114"
        self.log_signal.emit("╔══════════════════════════════════════╗")
        self.log_signal.emit("║        网 络 诊 断 报 告              ║")
        self.log_signal.emit("╚══════════════════════════════════════╝")
        self.log_signal.emit("")

        local_ip = self._get_local_ip()
        self.log_signal.emit(f"  本机 IP : {local_ip}")
        self.log_signal.emit(f"  检测目标: {target} (国内公共 DNS)")
        self.log_signal.emit("")

        result = self.ping(target)

        if result.get("stats"):
            s = result["stats"]
            self.log_signal.emit("   ┌────────── Ping 统计 ──────────┐")
            self.log_signal.emit(f"  │  发送包数  : {s['sent']}")
            self.log_signal.emit(f"  │  接收包数  : {s['received']}")
            self.log_signal.emit(f"  │  丢包数    : {s['lost']} ({s['lost_rate']})")
            self.log_signal.emit(f"  │  最小延迟  : {s['min_ms']} ms")
            self.log_signal.emit(f"  │  平均延迟  : {s['avg_ms']} ms")
            self.log_signal.emit(f"  │  最大延迟  : {s['max_ms']} ms")
            self.log_signal.emit("   └─────────────────────────────────┘")
            self.log_signal.emit("")
        else:
            self.log_signal.emit(f"  Ping 结果: {result['message']}")
            self.log_signal.emit("")

        if result["status"] == "ok":
            avg = result["stats"]["avg_ms"]
            if avg <= 30:
                quality = "优秀"
                self.result_signal.emit("网络质量", True)
            elif avg <= 60:
                quality = "良好"
                self.result_signal.emit("网络质量", True)
            elif avg <= 120:
                quality = "一般"
                self.result_signal.emit("网络质量", True)
            else:
                quality = "较差"
                self.result_signal.emit("网络质量", False)
            self.log_signal.emit(f"  网络质量: {quality} (延迟 {avg} ms)")
            self.log_signal.emit("")
            self.log_signal.emit("  诊断结果: 网络连通，状态正常")
        else:
            self.log_signal.emit("  诊断结果: 网络异常，请检查连接")
            self.result_signal.emit("网络质量", False)

        self.log_signal.emit("")
        self.log_signal.emit("══════════════════════════════════════")

    def quick_check(self):
        self.run_full_diagnosis()