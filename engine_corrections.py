"""
OpenFlow Personal Corrections Dictionary Engine
Applies user-defined word/phrase replacements after transcription and transliteration.
Pattern adapted from FreeWispr (MIT License, https://github.com/x26prakhar/freewispr).

Storage:
- %APPDATA%/OpenFlow/corrections.json (Windows writable user data directory)
- Case-insensitive regex matching with exact replacement string.
"""
import os
import json
import re
from typing import Dict
from utils_paths import get_user_data_dir

# Default baseline vocabulary substitutions
DEFAULT_CORRECTIONS: Dict[str, str] = {
    "open flow": "OpenFlow",
    "openflow": "OpenFlow",
    "py thon": "Python",
    "git hub": "GitHub",
    "vs code": "VS Code",
    "vscode": "VS Code",
    "javascript": "JavaScript",
    "type script": "TypeScript",
    "nextjs": "Next.js",
    "nodejs": "Node.js",
    "reactjs": "React",
}

def _get_corrections_file_path() -> str:
    return os.path.join(get_user_data_dir(), "corrections.json")

def load_corrections() -> Dict[str, str]:
    """
    Loads dictionary of corrections from user data directory.
    If file doesn't exist, initializes it with DEFAULT_CORRECTIONS.
    """
    path = _get_corrections_file_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"[CorrectionsEngine] Warning: Failed to read corrections file: {e}")

    # Initialize file with default corrections if not found
    save_corrections(DEFAULT_CORRECTIONS)
    return dict(DEFAULT_CORRECTIONS)

def save_corrections(corrections: Dict[str, str]):
    """Saves corrections dictionary to user data directory."""
    path = _get_corrections_file_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(corrections, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[CorrectionsEngine] Error writing corrections file: {e}")

def apply_corrections(text: str) -> str:
    """
    Replaces all correction pairs using whole-word case-insensitive boundary matches.
    """
    if not text:
        return ""

    corr = load_corrections()
    for wrong, right in corr.items():
        # Using word boundaries
        pattern = r'\b' + re.escape(wrong) + r'\b'
        text = re.sub(pattern, right, text, flags=re.IGNORECASE)

    return text
