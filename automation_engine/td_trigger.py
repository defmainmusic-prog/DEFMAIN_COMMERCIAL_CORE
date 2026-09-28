#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import random
import shutil
from pathlib import Path

# --- CONFIG ---
from config import resolve_release_path, resolve_template_pool, TD_EXECUTABLE

# --- 9-THEME PALETTE REGISTRY & HARMONIC SELECTION MATRIX ---
ALL_THEMES = [
    "industrial_gunmetal",  # Cold steel, electric cyan-blue mid, deep navy base
    "corroded_rust",        # Scorched iron, burnished amber/orange, bronze highlight
    "acid_toxic",           # Sludge green, toxic lime/chartreuse, acid highlight
    "brutal_concrete",      # Raw tungsten, cold slate/silver, white titanium specular
    "blood_iron",           # Crimson cast, obsidian blood, deep ruby highlight
    "subzero_cryo",         # Deep oceanic cobalt abyss, electric ultramarine, crystalline frost
    "hazard_amber",         # Bitumen black base, vivid nuclear warning yellow-gold, phosphor
    "amethyst_void",        # Obsidian void, vivid ultraviolet/electric amethyst, fluorite specular
    "molten_magma"          # Charcoal crucible crust, blazing thermal coral/magma, radiant core
]

# Harmonic priority mapping across 12 pitch classes
PITCH_THEME_PRIORITY = {
    0: ["industrial_gunmetal", "subzero_cryo", "brutal_concrete", "amethyst_void"],  # C
    1: ["corroded_rust", "molten_magma", "hazard_amber", "blood_iron"],              # C#
    2: ["acid_toxic", "hazard_amber", "subzero_cryo", "industrial_gunmetal"],         # D
    3: ["amethyst_void", "blood_iron", "subzero_cryo", "corroded_rust"],              # D#
    4: ["brutal_concrete", "industrial_gunmetal", "hazard_amber", "molten_magma"],    # E
    5: ["brutal_concrete", "subzero_cryo", "acid_toxic", "blood_iron"],              # F
    6: ["acid_toxic", "hazard_amber", "molten_magma", "corroded_rust"],              # F#
    7: ["corroded_rust", "hazard_amber", "molten_magma", "acid_toxic"],              # G
    8: ["blood_iron", "amethyst_void", "corroded_rust", "subzero_cryo"],              # G#
    9: ["industrial_gunmetal", "subzero_cryo", "brutal_concrete", "amethyst_void"],  # A
    10: ["acid_toxic", "hazard_amber", "molten_magma", "blood_iron"],                 # A#
    11: ["molten_magma", "corroded_rust", "hazard_amber", "brutal_concrete"]         # B
}

def select_release_track_theme(track_name, pitch_class, used_themes):
    """Stateful, non-repeating color scheme selector for release batches.
    Guarantees no palette is reused across an EP/album until all 9 themes have been exhausted.
    """
    t_lower = track_name.lower()
    
    keyword_map = {
        "venom": "acid_toxic",
        "toxic": "acid_toxic",
        "snake": "corroded_rust",
        "rust": "corroded_rust",
        "skeleton": "brutal_concrete",
        "concrete": "brutal_concrete",
        "tungsten": "brutal_concrete",
        "molt": "blood_iron",
        "blood": "blood_iron",
        "cryo": "subzero_cryo",
        "frost": "subzero_cryo",
        "abyss": "subzero_cryo",
        "hazard": "hazard_amber",
        "amber": "hazard_amber",
        "void": "amethyst_void",
        "amethyst": "amethyst_void",
        "magma": "molten_magma",
        "molten": "molten_magma",
        "crucible": "molten_magma"
    }
    
    preferred_theme = None
    for kw, th in keyword_map.items():
        if kw in t_lower:
            preferred_theme = th
            break
            
    if preferred_theme and preferred_theme not in used_themes:
        used_themes.add(preferred_theme)
        return preferred_theme
        
    candidates = PITCH_THEME_PRIORITY.get(int(pitch_class) % 12, ALL_THEMES)
    for c in candidates:
        if c not in used_themes:
            used_themes.add(c)
            return c
            
    for c in ALL_THEMES:
        if c not in used_themes:
            used_themes.add(c)
            return c
            
    # If all 9 themes exhausted, reset cycle
    used_themes.clear()
    fallback = preferred_theme or (candidates[0] if candidates else "industrial_gunmetal")
    used_themes.add(fallback)
    return fallback


def get_routing_paths(serial):
    """Dynamically routes paths using the centralized config module."""
    project_path = resolve_release_path(serial)
    td_pool_dir = str(resolve_template_pool(serial))
    return str(project_path) if project_path else None, td_pool_dir

def trigger_td_engine():
    print("--- DEFMAIN: BATCH TOUCHDESIGNER IGNITION SEQUENCE ---")
    
    serial = None
    non_interactive = False
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            if arg == "--non-interactive":
                non_interactive = True
        else:
            serial = arg.strip().upper()
            
    if not serial:
        serial = input("ENTER SERIAL (e.g., SRC55 or NSS01): ").strip().upper()
        
    project_path_str, td_pool_dir_str = get_routing_paths(serial)
    if not project_path_str or not td_pool_dir_str: 
        print(f"\n[!] ERROR: Invalid paths or initialization directory missing for {serial}")
        return

    project_path = Path(project_path_str)
    td_pool_dir = Path(td_pool_dir_str)

    # 1. Locate Audio Masters
    audio_dir = project_path / "01_Masters"
    audio_files = list(audio_dir.glob("*.wav"))
    
    if not audio_files:
        print(f"\n[!] ERROR: No WAV files found in {audio_dir}")
        return
        
    print(f"\n[+] FOUND {len(audio_files)} MASTER(S) IN QUEUE.")

    # 2. Select Aesthetic Engine via Centralized Ledger Protocol
    release_toe_path = project_path / f"{serial}_Visuals.toe"
    reuse_existing = False

    if release_toe_path.exists():
        print(f"\n[+] Detected existing release-specific template: {release_toe_path.name}")
        if not non_interactive:
            choice = input(f"Reuse this existing template to regenerate visuals? (y/n) [Default: y]: ").strip().lower() or "y"
            if choice == "y":
                reuse_existing = True
        else:
            # Default to reuse in non-interactive mode
            reuse_existing = True

    if reuse_existing:
        print(f"[+] Reusing existing release-specific template: {release_toe_path.name}")
    else:
        if not td_pool_dir.exists():
            print(f"\n[-] FATAL ERROR: Template pool directory missing at {td_pool_dir}")
            return

        # Only match primary .toe files, filtering out numbered backups (e.g. template.19.toe)
        templates = [t for t in td_pool_dir.glob("*.toe") if not t.stem.split('.')[-1].isdigit()]
        if not templates:
            print(f"\n[-] FATAL ERROR: No .toe templates found in {td_pool_dir}")
            return
            
        ledger_path = td_pool_dir / "template_ledger.json"
        if ledger_path.exists():
            with open(ledger_path, 'r') as f:
                memory = json.load(f)
        else:
            memory = {"used_templates": []}
            
        available_templates = [t for t in templates if t.name not in memory["used_templates"]]
        
        if not available_templates:
            print("\n[!] WARNING: TEMPLATE POOL EXHAUSTED. All templates have been used once.")
            print("[!] INITIATING MEMORY WIPE. Resetting pool...")
            memory["used_templates"] = []
            available_templates = templates
            
        chosen_template = random.choice(available_templates)
        print(f"[*] STATEFUL SELECTION: {chosen_template.name}\n")
        
        memory["used_templates"].append(chosen_template.name)
        with open(ledger_path, 'w') as f:
            json.dump(memory, f, indent=4)
            
        # Copy chosen template to the root of the release folder
        try:
            shutil.copy(str(chosen_template), str(release_toe_path))
            print(f"[+] COPIED & ARCHIVED TEMPLATE TO RELEASE ROOT: {release_toe_path.name}")
        except Exception as e:
            print(f"[!] Warning: Failed to copy template to release root: {e}")
            release_toe_path = chosen_template  # Fallback to pool template directly
        
    # Redirecting output target vectors directly to 03_Social/td_masters
    td_masters_dir = project_path / "03_Social" / "td_masters"
    td_masters_dir.mkdir(parents=True, exist_ok=True)
    
    task_file = Path(f"/tmp/defmain_td_task_{serial}.json")
    used_themes_in_release = set()

    # 3. The Batch Loop Execution
    for index, master_audio in enumerate(audio_files, start=1):
        track_name = master_audio.stem
        
        print("-" * 50)
        print(f"[*] PROCESSING TRACK {index}/{len(audio_files)}: {master_audio.name}")
        
        silent_video_out = td_masters_dir / f"{track_name}_SILENT.mp4"
        final_video_out = td_masters_dir / f"{track_name}_TD_Master.mp4"
        
        # Load audio analysis cache generated in run_pipeline.py
        dir_name = master_audio.parent
        analysis_file = dir_name / f"{track_name}_analysis.json"
        
        track_analysis = {}
        if analysis_file.exists():
            try:
                with open(analysis_file, 'r') as af:
                    track_analysis = json.load(af)
                print(f"  [+] Loaded audio analysis cache (BPM: {track_analysis.get('bpm')})")
            except Exception as e:
                print(f"  [!] Warning: Could not read analysis cache: {e}")
        else:
            print(f"  [!] Warning: Analysis cache missing at {analysis_file}")

        pitch_class = track_analysis.get("dominant_pitch_class", 0)
        selected_theme = select_release_track_theme(track_name, pitch_class, used_themes_in_release)
        print(f"  [+] Assigned Harmonic Theme: '{selected_theme}' (Used in release: {len(used_themes_in_release)}/{len(ALL_THEMES)})")

        # Inject metadata parameters directly into payload JSON
        payload = {
            "audio_in": str(master_audio),
            "video_out": str(silent_video_out),
            "bpm": track_analysis.get("bpm", 120.0),
            "brightness": track_analysis.get("brightness", 0.5),
            "energy": track_analysis.get("energy", 0.5),
            "pitch_class": pitch_class,
            "chroma": track_analysis.get("chroma", [0.0]*12),
            "colortheme": selected_theme
        }

        with open(task_file, 'w') as f:
            json.dump(payload, f)

        try:
            subprocess.run([TD_EXECUTABLE, str(release_toe_path)], check=True, timeout=600)
            print("[+] TOUCHDESIGNER RENDER COMPLETE.")
        except subprocess.CalledProcessError:
            print(f"[-] ERROR: TouchDesigner sequence failed for {track_name}. Skipping...")
            continue
        except subprocess.TimeoutExpired:
            print(f"[-] ERROR: TouchDesigner timed out after 600s for {track_name}. Skipping...")
            continue

        if silent_video_out.exists():
            print(f"[*] INJECTING MASTER AUDIO VIA FFMPEG...")
            ffmpeg_cmd = [
                'ffmpeg', '-v', 'warning', '-y',
                '-i', str(silent_video_out),
                '-i', str(master_audio),
                '-c:v', 'copy',
                '-c:a', 'aac', '-b:a', '320k',
                '-shortest',
                str(final_video_out)
            ]
            
            try:
                subprocess.run(ffmpeg_cmd, check=True)
                print(f"[+] SUCCESS: FINAL ASSET -> {final_video_out.name}")
                silent_video_out.unlink()
            except subprocess.CalledProcessError:
                print(f"[-] ERROR: FFmpeg failed to inject audio for {track_name}.")
        else:
            print(f"[-] ERROR: Silent TD video was not generated for {track_name}.")

    if task_file.exists():
        task_file.unlink()

    print("\n" + "=" * 50)
    print(f"[=] BATCH PROCESSING COMPLETE FOR {serial.upper()} [=]")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    trigger_td_engine()