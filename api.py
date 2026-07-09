from core.launcher import VersionParser, AccountManager, JavaLaunchEngine, UnifiedLaunchCore
from core.e4mc_manager import E4MCManager
from core.base import check_and_create_mco


def parse_version(game_root, version_id, ver_folder_name=None, json_filename=None, ver_type="vanilla", progress_callback=None):
    parser = VersionParser(game_root)
    return parser.parse(version_id, ver_folder_name, json_filename, ver_type, progress_callback)


def launch_game(game_root, java_path, cfg, account, min_mem=1024, max_mem=4096, ver_type="vanilla"):
    core = UnifiedLaunchCore(game_root, java_path)
    return core.launch("java", cfg, account, min_mem, max_mem, ver_type)


def create_offline_account(name):
    mgr = AccountManager()
    return mgr.create_offline(name)


def ensure_e4mc(game_root, mc_version, loader_type, progress_callback=None):
    e4mc = E4MCManager(game_root)
    if progress_callback:
        e4mc.progress.connect(progress_callback)
    return e4mc.ensure_installed(mc_version, loader_type)


def check_mco(version_id, game_root):
    return check_and_create_mco(version_id, game_root)


__all__ = [
    "parse_version",
    "launch_game",
    "create_offline_account",
    "ensure_e4mc",
    "check_mco",
]