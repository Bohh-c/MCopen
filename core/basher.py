import os
import time

def check_and_create_mco(version_id, game_root):
    versions_dir = os.path.join(game_root, "versions")
    version_dir = os.path.join(versions_dir, version_id)
    mco_path = os.path.join(version_dir, f"{version_id}.mco")
    if os.path.exists(mco_path):
        return True
    os.makedirs(version_dir, exist_ok=True)
    with open(mco_path, "w", encoding="utf-8") as f:
        f.write(str(int(time.time())))
    return False