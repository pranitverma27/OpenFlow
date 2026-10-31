"""
OpenFlow Path and Resource Resolution Utility
Handles:
1. Locating read-only bundled assets (HTML, model weights) in source and frozen PyInstaller environments.
2. Resolving writable user directories in %APPDATA%/OpenFlow for settings, logs, and user data.
"""
import os
import sys

def get_bundle_dir() -> str:
    """
    Returns the root directory where application assets (index.html, models, etc.) are located.
    Supports development mode and PyInstaller (--onedir and --onefile via sys._MEIPASS).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    elif getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_asset_path(relative_path: str) -> str:
    """Returns absolute path to a bundled asset given its relative path."""
    return os.path.join(get_bundle_dir(), relative_path)

def get_model_path(model_name: str = "tiny.en") -> str:
    """
    Resolves the offline model directory path.
    1. Checks if bundled in <bundle_dir>/models/<model_name>
    2. Checks if bundled beside executable in <exe_dir>/models/<model_name>
    3. Falls back to standard model name identifier for Hugging Face cache.
    """
    # 1. Bundled internal path
    bundled = os.path.join(get_bundle_dir(), "models", model_name)
    if os.path.isdir(bundled) and os.path.exists(os.path.join(bundled, "model.bin")):
        return bundled

    # 2. External adjacent models folder (beside executable or script)
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        adjacent = os.path.join(exe_dir, "models", model_name)
        if os.path.isdir(adjacent) and os.path.exists(os.path.join(adjacent, "model.bin")):
            return adjacent

    # Fallback to local source folder models/
    src_models = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", model_name)
    if os.path.isdir(src_models) and os.path.exists(os.path.join(src_models, "model.bin")):
        return src_models

    return model_name

def get_user_data_dir() -> str:
    """
    Returns the writable user data directory in %APPDATA%/OpenFlow.
    Ensures directory exists before returning.
    """
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.expanduser("~")
    user_dir = os.path.join(appdata, "OpenFlow")
    os.makedirs(user_dir, exist_ok=True)
    return user_dir
