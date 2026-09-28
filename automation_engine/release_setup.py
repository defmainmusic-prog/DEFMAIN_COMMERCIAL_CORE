import os
import shutil
import json
from pathlib import Path

from config import BASE_ROOT, TEMPLATE_DIR_BASE, OPERATIONS_DIR, resolve_label_info

def deploy_release(artist=None, title=None, serial=None, rel_date=None):
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
        serial = input("SERIAL (e.g., SRC1 or NSS1): ").strip().upper()
    else:
        serial = serial.strip().upper()
        
    if not rel_date:
        rel_date = input("RELEASE DATE (YYYY-MM-DD): ").strip() or "TBC"
    else:
        rel_date = rel_date.strip()

    # 2. Dynamic Routing Matrix
    try:
        output_label_dir, template_dir, active_label = resolve_label_info(serial)
    except ValueError:
        print("\n[!] ERROR: Serial signature validation failed. Aborting.")
        return None, None

    # 3. Path Generation
    folder_name = f"{artist} - {title} - {serial}"
    dest_path = output_label_dir / folder_name

    if dest_path.exists():
        print(f"[!] ERROR: Target path already initialized: {dest_path}")
        return None, None

    # 4. Physical Structural Deployment
    try:
        if not template_dir.exists():
            print(f"\n[-] SYSTEM ERROR: Blueprint template folder missing at:\n    {template_dir}")
            return None, None

        # Ensure live directory branch exists on drive
        output_label_dir.mkdir(parents=True, exist_ok=True)

        # Mirror template structure to destination
        shutil.copytree(template_dir, dest_path)
        
        # 5. Manifest Commit (Pure Data, No Copywriting)
        manifest_data = {
            "artist": artist,
            "title": title,
            "serial": serial,
            "release_date": rel_date,
            "mood_notes": "",
            "label": active_label,
            "status": "initialized"
        }
        
        with open(dest_path / "release_manifest.json", 'w') as f:
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