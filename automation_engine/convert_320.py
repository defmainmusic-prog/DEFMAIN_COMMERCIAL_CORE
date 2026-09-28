#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

from config import resolve_release_path

def convert_to_320():
    print("--- DEFMAIN 320KBPS MP3 CONVERTER ---")
    if len(sys.argv) > 1:
        serial = sys.argv[1]
    else:
        serial = input("ENTER SERIAL (e.g., SRC55 or NSS01): ").strip()
        
    project_path_str = resolve_release_path(serial)
    if not project_path_str:
        print(f"\n[!] ERROR: Could not find a release folder for {serial}")
        return

    project_path = Path(project_path_str)
    source_dir = project_path / "01_Masters"
    output_dir = project_path / "EPK" / "MP3_320kbps"

    if not source_dir.exists():
        print(f"\n[!] ERROR: Masters directory does not exist at: {source_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clear out any existing MP3s to avoid old suffix duplicates
    for old_file in output_dir.glob("*.mp3"):
        try:
            old_file.unlink()
        except Exception:
            pass
    
    extensions = ("*.wav", "*.aif", "*.aiff", "*.flac")
    # Clean string matching for extension structures regardless of case
    files_to_convert = []
    for ext in extensions:
        files_to_convert.extend(source_dir.glob(ext))
        files_to_convert.extend(source_dir.glob(ext.upper()))

    if not files_to_convert:
        print(f"\n[!] ERROR: No audio files found in: {source_dir}")
        return

    print(f"\n[+] SOURCE: {source_dir}")
    print(f"[+] TARGET: {output_dir}\n")

    for file_path in files_to_convert:
        # Clean track name of suffixes for output file naming
        clean_track_stem = file_path.stem
        suffixes_to_remove = ["- master", "-master", "_master", " master", "- ref", "-ref", " ref"]
        for suffix in suffixes_to_remove:
            if clean_track_stem.lower().endswith(suffix):
                clean_track_stem = clean_track_stem[:-len(suffix)].strip(" -_")
                break
        
        output_path = output_dir / f"{clean_track_stem}.mp3"
        print(f"[*] Converting: {file_path.name} -> {clean_track_stem}.mp3...")
        
        cmd = [
            'ffmpeg', '-v', 'warning', '-i', str(file_path),
            '-codec:a', 'libmp3lame',
            '-b:a', '320k',
            '-map_metadata', '0', 
            '-id3v2_version', '3',
            '-y', 
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            print(f"[-] FAILED to convert {file_path.name}")
            continue

    print(f"\n[=] SUCCESS: EPK MP3s RENDERED [=]\n")

if __name__ == "__main__":
    convert_to_320()