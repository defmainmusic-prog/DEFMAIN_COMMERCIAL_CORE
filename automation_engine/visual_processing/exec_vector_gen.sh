#!/bin/bash
# ----------------------------------------------------
# DEFMAIN: VEHICLE WRAP / LAYER VECTOR LAUNCHER
# ----------------------------------------------------

if [ -z "$1" ]; then
  echo "Usage: ./exec_vector_gen.sh <SERIAL> [square|vertical]"
  exit 1
fi

SERIAL="$1"
# Default to square format layout if a second parameter is not defined
MODE="${2:-square}"

# Standardize text strings for internal Python argument maps
if [ "$MODE" == "9x16" ] || [ "$MODE" == "vertical" ] || [ "$MODE" == "9-16" ]; then
    TARGET_MODE="vertical"
else
    TARGET_MODE="square"
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo "[INIT]: Booting Cairo Engine for $SERIAL (Mode: $TARGET_MODE)..."

# Auto-detect Homebrew lib path for macOS architecture compatibility (ARM + Intel)
if command -v brew &> /dev/null; then
    export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib"
else
    export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
fi

python3 "$SCRIPT_DIR/render_vector_overlay.py" "$SERIAL" --mode "$TARGET_MODE"
