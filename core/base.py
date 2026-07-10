import os
import time
import json
import base64
import binascii
from pathlib import Path
from datetime import datetime

MCO_RUNTIME = datetime.now().isoformat()
MCO_CONTENT = "抄袭私募轻矿778" + "_" + str(MCO_RUNTIME)
MCO_ENCODED = base64.b64encode(MCO_CONTENT.encode()).decode()

def safe_write_text(file_path: Path, content: str):
    try:
        tmp = file_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        tmp.replace(file_path)
    except Exception:
        return

def safe_mkdir(p: Path):
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        return

def init_launcher_watermark(launcher_root):
    try:
        mco_dir = Path(launcher_root) / "MCO"
        safe_mkdir(mco_dir)
        mco_path = mco_dir / "LiteMine.mco"
        if not mco_path.exists():
            safe_write_text(mco_path, MCO_ENCODED)
        config_path = mco_dir / "config.json"
        config = {
            "launcher": "MCOpen",
            "version": "1.4.0",
            "first_launch": int(time.time()),
            "studio": MCO_ENCODED,
            "last_updated": int(time.time())
        }
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    old_cfg = json.load(f)
                config.update(old_cfg)
                config["studio"] = MCO_ENCODED
                config["version"] = "1.4.0"
                config["last_updated"] = int(time.time())
            except Exception:
                pass
        safe_write_text(config_path, json.dumps(config, ensure_ascii=False, indent=2))
        safe_mkdir(mco_dir / "logs")
        safe_mkdir(mco_dir / "cache")
        safe_mkdir(mco_dir / "online")
        info_path = mco_dir / "README.txt"
        if not info_path.exists():
            txt = "MCOpen 启动器工作目录\n工作室：" + MCO_ENCODED + "\n请勿删除此目录，否则启动器可能无法正常工作\n"
            safe_write_text(info_path, txt)
    except Exception:
        pass
    return True

def check_resource_downloaded(game_root):
    try:
        game_root_path = Path(game_root)
        if not game_root_path.exists():
            return False
        libraries_dir = game_root_path / "libraries"
        assets_dir = game_root_path / "assets"
        flag_file = game_root_path / "LiteMine.mco"
        if not libraries_dir.exists() or not assets_dir.exists() or not flag_file.exists():
            return False
        has_libs = False
        for item in libraries_dir.iterdir():
            if item.is_file() or (item.is_dir() and any(item.iterdir())):
                has_libs = True
                break
        return has_libs
    except Exception:
        return False

def mark_resource_downloaded(game_root):
    try:
        game_root_path = Path(game_root)
        game_root_path.mkdir(parents=True, exist_ok=True)
        flag_file = game_root_path / "LiteMine.mco"
        if not flag_file.exists():
            safe_write_text(flag_file, MCO_ENCODED)
    except Exception:
        pass
    return True

def decode_watermark(encoded):
    if not isinstance(encoded, str) or len(encoded.strip()) == 0:
        return MCO_CONTENT
    try:
        raw = base64.b64decode(encoded, validate=True)
        return raw.decode()
    except (binascii.Error, UnicodeDecodeError, Exception):
        return MCO_CONTENT