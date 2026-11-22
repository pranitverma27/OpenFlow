"""
OpenFlow Language Configuration
Defines supported language modes, UI labels, and routing profiles.
"""
from enum import Enum
from typing import Dict, Any

class LanguageMode(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hinglish"

# Metadata for UI representation
LANGUAGE_LABELS = {
    LanguageMode.ENGLISH.value: "English",
    LanguageMode.HINDI.value: "Hindi (हिन्दी)",
    LanguageMode.HINGLISH.value: "Hinglish",
}

# Transcription profile parameters per mode
LANGUAGE_PROFILES: Dict[str, Dict[str, Any]] = {
    LanguageMode.ENGLISH.value: {
        "engine": "english",           # Routes to baseline TranscriptionEngine (models/tiny.en)
        "model_id": "tiny.en",
        "transliterate": False,
        "description": "Ultra-fast local English dictation using faster-whisper tiny.en",
    },
    LanguageMode.HINDI.value: {
        "engine": "shruti",            # Routes to ShrutiTranscriptionEngine (models/shruti-hi)
        "model_id": "shruti-hi",
        "language": "hi",
        "beams": 5,
        "transliterate": False,        # Devanagari output with English words in Latin
        "description": "Accurate Hindi dictation using Udgam Labs Shruti with English terms preserved",
    },
    LanguageMode.HINGLISH.value: {
        "engine": "shruti",            # Routes to ShrutiTranscriptionEngine
        "model_id": "shruti-hi",
        "language": None,              # Dynamic code-switching detection
        "beams": 5,
        "transliterate": True,         # Converts Devanagari to Roman script while keeping English untouched
        "description": "Conversational code-switched Hindi-English in Roman script",
    },
}

def get_language_profile(mode: str) -> Dict[str, Any]:
    """Returns the profile dictionary for a given mode string, defaulting to English."""
    return LANGUAGE_PROFILES.get(mode, LANGUAGE_PROFILES[LanguageMode.ENGLISH.value])
