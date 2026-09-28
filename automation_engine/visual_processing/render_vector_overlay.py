#!/usr/bin/env python3
import json
import os
import sys
import argparse
from pathlib import Path
import ctypes.util

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import resolve_release_path

# Apple Silicon macOS Homebrew library resolution monkeypatch
orig_find_library = ctypes.util.find_library
def patched_find_library(name):
    path = orig_find_library(name)
    if not path and sys.platform == 'darwin':
        # Check standard Apple Silicon Homebrew paths
        for suffix in ['.2.dylib', '.dylib']:
            test_path = f"/opt/homebrew/lib/lib{name}{suffix}"
            if os.path.exists(test_path):
                return test_path
            test_path_intel = f"/usr/local/lib/lib{name}{suffix}"
            if os.path.exists(test_path_intel):
                return test_path_intel
    return path
ctypes.util.find_library = patched_find_library

import cairosvg
from jinja2 import Template


def render_overlay(serial, mode, track_title=None, track_artist=None, template_name=None):
    """Renders the label SVG layout to PNG, optionally with a custom track title and artist."""
    release_dir_str = resolve_release_path(serial)
    if not release_dir_str:
        print(f"[ERROR]: Could not find a release directory for {serial}")
        return None

    release_dir = Path(release_dir_str)
    script_dir = Path(__file__).resolve().parent
    
    # 1. Prefix Isolation for Template Routing
    clean_serial = serial.upper().strip()
    label_prefix = "nss" if clean_serial.startswith("NSS") else "src"
    
    # 2. Dynamic Template Selection Matrix
    if template_name:
        template_file = template_name
    elif mode == 'vertical':
        template_file = f"{label_prefix}_layout_9x16.svg"
    else:
        template_file = f"{label_prefix}_layout.svg"
        
    template_path = script_dir / template_file
    
    if not template_path.exists():
        print(f"[ERROR]: Target vector template missing at: {template_path}")
        return None

    # Routing generated artwork overlays straight into 02_Artwork
    if track_title:
        # Clean track title for filename safety
        safe_title = "".join([c if c.isalnum() else "_" for c in track_title])
        output_name = f"{clean_serial}_overlay_{mode}_{safe_title}.png"
    elif template_name:
        # Include custom template name stem in output to prevent overwriting prod files
        template_stem = Path(template_name).stem
        output_name = f"{clean_serial}_overlay_{mode}_{template_stem}.png"
    else:
        output_name = f"{clean_serial}_overlay_{mode}.png"
        
    output_dir = release_dir / '02_Artwork'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name

    manifest_path = release_dir / 'release_manifest.json'
    if not manifest_path.exists():
        print(f"[ERROR]: release_manifest.json not found at {manifest_path}")
        return None

    with open(manifest_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with open(template_path, 'r', encoding='utf-8') as f:
        tmpl = Template(f.read())
        
    # Font scaling calibration matrix
    if mode == 'vertical':
        f_size1, f_size2 = 70, 40
    else:
        f_size1, f_size2 = 200, 100

    # Resolve dynamic track title and artist
    artist_name = track_artist if track_artist else data.get('artist', 'UNKNOWN')
    title_name = track_title if track_title else data.get('title', 'UNTITLED')

    # Load and Base64-encode logo file for direct embedding
    import base64
    logo_data = ""
    logo_path = Path(__file__).resolve().parent / "SRC_logoFull.png"
    if label_prefix == "src" and logo_path.exists():
        try:
            with open(logo_path, "rb") as image_file:
                logo_data = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"[WARNING]: Could not load logo image: {e}")

    rendered_svg = tmpl.render(
        ARTIST=artist_name.upper(),
        TITLE=title_name.upper(),
        CATALOG_ID=clean_serial,
        FONT_SIZE_1=f_size1, 
        FONT_SIZE_2=f_size2,
        RELEASE_DATE=data.get('release_date', 'N/A'),
        STATUS=data.get('status', 'ACTIVE').upper(),
        LOGO_DATA=logo_data
    )

    try:
        cairosvg.svg2png(bytestring=rendered_svg.encode('utf-8'), write_to=str(output_path))
        print(f"[SUCCESS]: Overlay compiled -> {output_path}")
        return output_path
    except Exception as e:
        print(f"[ERROR]: Cairo processing failed: {e}")
        return None

def run_render():
    parser = argparse.ArgumentParser()
    parser.add_argument("serial")
    parser.add_argument("--mode", choices=['square', 'vertical'], default='square')
    parser.add_argument("--template", default=None, help="Custom SVG template file name")
    args = parser.parse_args()
    
    render_overlay(args.serial, args.mode, template_name=args.template)

if __name__ == "__main__":
    run_render()