import os
import json5
from typing import Any, Dict, Optional

# Load the base configuration from config.jsonc
def load_base_config() -> Dict[str, Any]:
    path = "config.jsonc"
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json5.load(f)
    except FileNotFoundError:
        return {}

# Load secrets (tokens, etc.) from secrets.jsonc
def load_secrets() -> Dict[str, Any]:
    path = "secrets.jsonc"
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json5.load(f)
    except FileNotFoundError:
        return {}

# Load the personality prompt from a profile-specific file
def load_personality() -> Dict[str, Any]:
    profile = os.getenv("PROFILE", "default").lower()
    path = f"profiles/{profile}.jsonc"
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json5.load(f)
    except FileNotFoundError:
        # Fallback to a default if the specific profile doesn't exist
        print(f"Warning: Profile {profile} not found in profiles/, using empty personality.")
        return {}

# Global configuration state
BASE_CONFIG = load_base_config()
SECRETS = load_secrets()
PROFILE_NAME = os.getenv("PROFILE", "default").lower()
PERSONALITY = load_personality()

# The master config object used by the application
# It merges base settings, secrets (filtered by profile), and personality.
CONFIG: Dict[str, Any] = {
    "profile": PROFILE_NAME,
    "base": BASE_CONFIG,
    "secrets": SECRETS.get(PROFILE_NAME, {}),
    "personality": PERSONALITY,
}

# Helper functions for easy access
def get_config(key: str) -> Any:
    return BASE_CONFIG.get(key)

def get_secret(key: str) -> Any:
    # This looks into the subset of secrets belonging to the active profile
    profile_secrets = SECRETS.get(PROFILE_NAME, {})
    return profile_secrets.get(key)

def get_personality() -> Dict[str, Any]:
    return PERSONALITY

# Convenience accessors for common items
def get_model_info(model_type: str, index: int = 0) -> Dict[str, Any]:
    models = BASE_CONFIG.get("models", {}).get(model_type, [])
    if 0 <= index < len(models):
        return models[index]
    return {}

def get_gif_url(category: str, index: int = 0) -> str:
    gifs = BASE_CONFIG.get("gifs", {}).get(category, [])
    if 0 <= index < len(gifs):
        return gifs[index]
    return ""