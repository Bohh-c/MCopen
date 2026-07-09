"""Java检测工具"""

import os
import subprocess
import glob


def find_java_paths():
    paths = []
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        java_exe = os.path.join(java_home, "bin", "java.exe")
        if os.path.exists(java_exe):
            paths.append(java_exe)

    common_paths = [
        r"C:\Program Files\Java",
        r"C:\Program Files (x86)\Java",
        r"C:\Program Files\Zulu",
        r"C:\Program Files\Microsoft\jdk-*",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Java"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "jdk-*"),
    ]

    for base in common_paths:
        if "*" in base:
            matches = glob.glob(base)
            for match in matches:
                if os.path.isdir(match):
                    java_exe = os.path.join(match, "bin", "java.exe")
                    if os.path.exists(java_exe):
                        paths.append(java_exe)
        elif os.path.isdir(base):
            for root, dirs, files in os.walk(base):
                if "java.exe" in files:
                    java_exe = os.path.join(root, "java.exe")
                    paths.append(java_exe)

    return list(dict.fromkeys(paths))


def get_java_version(java_path):
    try:
        result = subprocess.run(
            [java_path, "-version"],
            capture_output=True, text=True, timeout=10, errors="replace"
        )
        if result.returncode == 0:
            lines = result.stderr.strip().split("\n")
            if lines:
                return lines[0]
        return "Unknown"
    except Exception:
        return "Error"


def find_recommended_java():
    paths = find_java_paths()
    for path in paths:
        ver = get_java_version(path)
        if "17" in ver:
            return path, ver
    if paths:
        return paths[0], get_java_version(paths[0])
    return None, None