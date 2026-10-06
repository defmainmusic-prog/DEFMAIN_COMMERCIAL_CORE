import os
import shutil
import json
from pathlib import Path

from config import BASE_ROOT, TEMPLATE_DIR_BASE, OPERATIONS_DIR, resolve_label_info

from datetime import datetime

def deploy_release(
    artist=None,
    title=None,
    serial=None,
    rel_date=None,
    format_type="EP Bundle (3 Tracks)",
    upc="5059432018491",
    label_name=None,
    tracks=None
):
    print("--- DEFMAIN PLATFORM DEPLOYMENT ENGINE V7.0 [NO-AI ROOT] ---")
    
    # 1. Capture Core Release Metadata
    if not artist:
        artist = input("ARTIST NAME: ").strip().title()
    else:
        artist = artist.strip().title()
        
    if not title:
        title = input("RELEASE TITLE: ").strip().title()
    else:
        title = title.strip().title()
        
    if not serial:
        serial = input("SERIAL (e.g., SRC1, NSS1, or APEX005): ").strip().upper()
    else:
        serial = serial.strip().upper()
        
    if not rel_date:
        rel_date = input("RELEASE DATE (YYYY-MM-DD): ").strip() or "TBC"
    else:
        rel_date = rel_date.strip()

    # 2. Dynamic Routing Matrix
    try:
        output_label_dir, template_dir, active_label = resolve_label_info(serial, label_name)
    except Exception as e:
        print(f"\n[!] ERROR: Serial signature validation failed ({e}). Aborting.")
        return None, None

    # 3. Path Generation
    folder_name = f"{artist} - {title} - {serial}"
    dest_path = output_label_dir / folder_name

    # Canonical Release Folder Blueprint
    subdirs = [
        "00_Original_Files",
        "01_Masters",
        "02_Artwork",
        "03_Social",
        "04_DTV",
        "05_Legal",
        "EPK",
    ]

    # 4. Physical Structural Deployment
    try:
        # Ensure live directory branch exists on drive
        output_label_dir.mkdir(parents=True, exist_ok=True)
        dest_path.mkdir(parents=True, exist_ok=True)

        for sub in subdirs:
            (dest_path / sub).mkdir(parents=True, exist_ok=True)

        # Copy any template files if template folder exists
        if template_dir and template_dir.exists():
            for item in template_dir.iterdir():
                target = dest_path / item.name
                if not target.exists():
                    if item.is_dir():
                        shutil.copytree(item, target)
                    else:
                        shutil.copy2(item, target)

        # 5. Manifest Commit (Pure Data, No Copywriting)
        manifest_path = dest_path / "release_manifest.json"
        manifest_data = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest_data = json.load(f)
            except Exception:
                manifest_data = {}

        manifest_data.update({
            "artist": artist,
            "title": title,
            "serial": serial,
            "catalog_number": serial,
            "release_date": rel_date,
            "format": format_type,
            "upc": upc,
            "mood_notes": manifest_data.get("mood_notes", ""),
            "label": active_label,
            "status": manifest_data.get("status", "initialized"),
            "tracks": tracks or manifest_data.get("tracks", []),
            "initialized_at": manifest_data.get("initialized_at", datetime.now().isoformat()),
            "last_updated": datetime.now().isoformat()
        })
        
        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=4)

        print(f"\n[+] SUCCESS: {serial} STRUCTURALLY INITIALIZED.")
        print(f"    PATH: {dest_path}")
        return serial, dest_path

    except Exception as e:
        print(f"\n[-] CRITICAL DEPLOYMENT FAILURE: {e}")
        return None, None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 3:
        r_date = sys.argv[4] if len(sys.argv) > 4 else "TBC"
        deploy_release(sys.argv[1], sys.argv[2], sys.argv[3], r_date)
    else:
        deploy_release()