"""
Defmain Platform — Shared Configuration Module
================================================
Single source of truth for all path resolution, environment detection,
and shared constants across the release pipeline.

Every automation script imports from here instead of hardcoding paths.
"""
import os
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. AUTO-DETECTED BASE ROOT
#    Resolves to the project root regardless of where the repo is cloned.
#    Layout assumption: this file lives at <BASE_ROOT>/automation_engine/config.py
# ---------------------------------------------------------------------------
BASE_ROOT = Path(__file__).resolve().parent.parent

AUTOMATION_ENGINE_DIR = BASE_ROOT / "automation_engine"
OPERATIONS_DIR = BASE_ROOT / "operations"
TEMPLATE_DIR_BASE = AUTOMATION_ENGINE_DIR / "templates"
VISUAL_PROCESSING_DIR = AUTOMATION_ENGINE_DIR / "visual_processing"

# Label-specific operations directories
RELEASE_DIRS = [
    OPERATIONS_DIR / "SRC_Records" / "Releases",
    OPERATIONS_DIR / "Neural_State_Sound" / "Releases",
]

# Label-specific template pool directories
TEMPLATE_POOL = {
    "SRC": VISUAL_PROCESSING_DIR / "template_pool" / "SRC",
    "NSS": VISUAL_PROCESSING_DIR / "template_pool" / "NSS",
}

# Label-specific folder templates for new releases
LABEL_TEMPLATES = {
    "SRC": TEMPLATE_DIR_BASE / "_TEMPLATE_FOLDER_SRC",
    "NSS": TEMPLATE_DIR_BASE / "_TEMPLATE_FOLDER_NSS",
}

# Credentials (relative to project root)
GOOGLE_CREDS_PATH = BASE_ROOT / "google_creds.json"
ENV_PATH = BASE_ROOT / ".env"

# TouchDesigner executable (macOS default)
TD_EXECUTABLE = "/Applications/TouchDesigner.app/Contents/MacOS/TouchDesigner"


# ---------------------------------------------------------------------------
# 2. RELEASE PATH RESOLUTION — Single Source of Truth
#    Replaces the copy-pasted get_project_path / get_routing_paths in every script.
# ---------------------------------------------------------------------------
def resolve_release_path(serial: str) -> Path | None:
    """Dynamically locates the release folder for the given serial code.

    Uses strict prefix matching to avoid SRC1 matching SRC10/SRC11.
    Returns the Path to the release folder, or None if not found.
    """
    clean_serial = serial.upper().replace("_", "").replace("-", "").strip()

    matches = []
    for base_dir in RELEASE_DIRS:
        if not base_dir.exists():
            continue

        for folder in os.listdir(base_dir):
            clean_folder = folder.upper().replace("_", "").replace("-", "")
            full_path = base_dir / folder

            if not full_path.is_dir():
                continue

            # Strict boundary match: clean_serial must appear as a complete
            # token boundary (followed by end-of-string or a non-alphanumeric).
            # This prevents SRC1 from matching SRC10, SRC11, etc.
            idx = clean_folder.find(clean_serial)
            if idx == -1:
                continue

            end_idx = idx + len(clean_serial)
            if end_idx < len(clean_folder) and clean_folder[end_idx].isalnum():
                # The character after the match is alphanumeric — not a clean boundary.
                # e.g. searching "SRC1" found inside "SRC10" — skip this.
                continue

            is_temp = any(
                term in clean_folder
                for term in ["TEMP", "BACKUP", "ARCHIVE", "OLD"]
            )
            matches.append((full_path, is_temp, len(folder)))

    if not matches:
        return None

    # Sort: non-temp first, then shortest name length
    matches.sort(key=lambda x: (x[1], x[2]))
    return matches[0][0]


def resolve_template_pool(serial: str) -> Path:
    """Returns the template pool directory for the given serial's label prefix."""
    clean = serial.upper().strip()
    for prefix, pool_path in TEMPLATE_POOL.items():
        if clean.startswith(prefix):
            return pool_path
    # Default fallback
    return TEMPLATE_POOL["SRC"]


def resolve_label_info(serial: str) -> tuple[Path, Path, str]:
    """Returns (output_label_dir, template_dir, active_label) for a given serial."""
    clean = serial.upper().strip()
    if clean.startswith("SRC"):
        return (
            OPERATIONS_DIR / "SRC_Records" / "Releases",
            LABEL_TEMPLATES["SRC"],
            "SRC_Records",
        )
    elif clean.startswith("NSS"):
        return (
            OPERATIONS_DIR / "Neural_State_Sound" / "Releases",
            LABEL_TEMPLATES["NSS"],
            "Neural State Sound (NSS)",
        )
    else:
        raise ValueError(f"Unknown label prefix in serial: {serial}")


# ---------------------------------------------------------------------------
# 3. ENVIRONMENT HELPERS
# ---------------------------------------------------------------------------
def get_homebrew_lib_path() -> str:
    """Auto-detect Homebrew library path for Cairo/system library compatibility.

    Works on both ARM (/opt/homebrew) and Intel (/usr/local) macOS.
    Falls back to /opt/homebrew/lib if brew is not installed.
    """
    try:
        prefix = subprocess.check_output(
            ["brew", "--prefix"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        return f"{prefix}/lib"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "/opt/homebrew/lib"


def get_pipeline_env() -> dict:
    """Returns an environment dict with Homebrew library paths injected.

    Use this when launching subprocesses that depend on Cairo or other
    Homebrew-installed native libraries.
    """
    env = os.environ.copy()
    brew_lib = get_homebrew_lib_path()
    existing = env.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    if brew_lib not in existing:
        env["DYLD_FALLBACK_LIBRARY_PATH"] = f"{existing}:{brew_lib}" if existing else brew_lib
    return env

