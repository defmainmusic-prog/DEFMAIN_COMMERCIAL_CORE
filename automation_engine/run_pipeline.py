#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

from config import (
    BASE_ROOT,
    AUTOMATION_ENGINE_DIR,
    resolve_release_path,
    get_pipeline_env,
)

try:
    from release_setup import deploy_release
except ImportError:
    deploy_release = None

def check_audio_masters(project_path):
    """Checks if there are master audio files in the 01_Masters directory."""
    source_dir = project_path / "01_Masters"
    if not source_dir.exists():
        return []
    
    extensions = ("*.wav", "*.aif", "*.aiff", "*.flac")
    audio_files = []
    for ext in extensions:
        audio_files.extend(source_dir.glob(ext))
        audio_files.extend(source_dir.glob(ext.upper()))
    return audio_files

def run_step(step_name, command_args, cwd=AUTOMATION_ENGINE_DIR):
    """Executes a pipeline step as a subprocess and streams output."""
    print("\n" + "=" * 60)
    print(f"[RUNNING] {step_name}")
    print(f"COMMAND: {' '.join(command_args)}")
    print("=" * 60)
    
    env = get_pipeline_env()
    
    try:
        # Run command with outputs printed in real-time
        result = subprocess.run(command_args, cwd=cwd, env=env, check=True)
        print(f"[SUCCESS] {step_name} completed successfully.\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n[FATAL ERROR] {step_name} failed with return code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n[FATAL ERROR] {step_name} execution encountered an exception: {e}")
        return False

def _save_checkpoint(project_path, step_number, step_name):
    """Persists pipeline progress so a failed run can resume from here."""
    state_file = project_path / "pipeline_state.json"
    state = {
        "last_completed_step": step_number,
        "last_step_name": step_name,
        "timestamp": datetime.now().isoformat(),
    }
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception:
        pass  # Checkpoint failure should never halt the pipeline

def _load_checkpoint(project_path):
    """Returns the last completed step number, or 0 if no checkpoint exists."""
    state_file = project_path / "pipeline_state.json"
    if not state_file.exists():
        return 0
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        step = state.get("last_completed_step", 0)
        name = state.get("last_step_name", "Unknown")
        ts = state.get("timestamp", "Unknown")
        print(f"[CHECKPOINT] Last successful step: #{step} ({name}) at {ts}")
        return step
    except Exception:
        return 0

def main():
    import argparse
    parser = argparse.ArgumentParser(description="DEFMAIN PLATFORM: UNIFIED PIPELINE AUTOMATION SYSTEM")
    parser.add_argument("--serial", help="Release serial (e.g. SRC999)")
    parser.add_argument("--artist", help="Artist name")
    parser.add_argument("--title", help="Release title")
    parser.add_argument("--date", help="Release date (YYYY-MM-DD)", default="TBC")
    parser.add_argument("--sonic-qualities", help="Sonic qualities/hardware nodes")
    parser.add_argument("--non-interactive", action="store_true", help="Skip interactive prompts and verify files directly")
    parser.add_argument("--resume", action="store_true", help="Resume from last completed pipeline step (reads pipeline_state.json)")
    args = parser.parse_args()

    print("=" * 70)
    print("   DEFMAIN PLATFORM: UNIFIED PIPELINE AUTOMATION SYSTEM V1.0   ")
    print("=" * 70)
    
    serial = None
    project_path = None
    sonic_qualities = None
    
    # Check if CLI parameters are supplied to run non-interactively
    if args.serial or args.non_interactive:
        if not args.serial:
            print("[!] ERROR: Serial is required for non-interactive mode. Use --serial.")
            return
        
        serial = args.serial.upper().strip()
        project_path = resolve_release_path(serial)
        
        if not project_path:
            # Try to create it if artist and title are provided
            if args.artist and args.title:
                print(f"[+] Serial {serial} not found. Attempting automatic creation...")
                if deploy_release is None:
                    print("[!] ERROR: release_setup.py could not be imported.")
                    return
                serial, project_path = deploy_release(args.artist, args.title, serial, args.date)
                if not serial or not project_path:
                    print("[!] ERROR: Automatic release setup failed.")
                    return
            else:
                print(f"[!] ERROR: Release {serial} does not exist and insufficient arguments to create it (--artist and --title are required).")
                return
        else:
            print(f"[+] Located Existing Release Path: {project_path}")
            
        if args.non_interactive:
            sonic_qualities = args.sonic_qualities or "Industrial synthesis, hardware density."
        else:
            sonic_qualities = args.sonic_qualities
    else:
        # Interactive Mode
        print("Options:")
        print("  [1] Create and initialize a new release + Run pipeline")
        print("  [2] Run pipeline on an existing initialized release")
        
        choice = input("\nSelect execution path (1 or 2): ").strip()
        
        if choice == "1":
            if deploy_release is None:
                print("[!] ERROR: release_setup.py could not be imported. Please ensure the script sits in automation_engine/.")
                return
            serial, project_path = deploy_release()
            if not serial or not project_path:
                print("[!] ERROR: Release setup failed or aborted.")
                return
        elif choice == "2":
            serial = input("ENTER SERIAL of the existing release (e.g. SRC55 or NSS01): ").strip().upper()
            project_path = resolve_release_path(serial)
            if not project_path:
                print(f"[!] ERROR: Could not locate project directory for serial: {serial}")
                return
            print(f"[+] Located Release Path: {project_path}")
        else:
            print("[!] ERROR: Invalid choice. Aborting.")
            return

    # Phase 2 & 3: Waiting for master audio files
    print("\n" + "-" * 60)
    print("   PHASE: RAW MASTER AUDIO INJECTION")
    print("-" * 60)
    
    if args.non_interactive:
        audio_files = check_audio_masters(project_path)
        if not audio_files:
            print(f"[!] ERROR: No master audio files found (WAV, AIF, AIFF, or FLAC) inside:")
            print(f"    {project_path / '01_Masters'}")
            print("Aborting non-interactive run.")
            return
        print(f"[+] Detected {len(audio_files)} master audio file(s) in queue:")
        for f in audio_files:
            print(f"    - {f.name}")
    else:
        while True:
            audio_files = check_audio_masters(project_path)
            if audio_files:
                print(f"\n[+] Detected {len(audio_files)} master audio file(s) in queue:")
                for f in audio_files:
                    print(f"    - {f.name}")
                confirm = input("\nProceed with these files? (y/n) [Default: y]: ").strip().lower() or "y"
                if confirm == "y":
                    break
            else:
                print(f"\n[!] WARNING: No master audio files found (WAV, AIF, AIFF, or FLAC) inside:")
                print(f"    {project_path / '01_Masters'}")
                print("\nPlease drop your files into that folder now.")
                input("Press [Enter] once files have been copied to re-scan...")

    # Phase 3.5: Run Pre-Processed Audio Feature Analysis
    print("\n" + "-" * 60)
    print("   PHASE: PRE-PROCESSED AUDIO FEATURE ANALYSIS")
    print("-" * 60)
    print("[*] Analyzing audio tracks for BPM, energy, brightness, and key...")
    
    for f in audio_files:
        print(f"  - Analyzing {f.name}...")
        try:
            analysis_script = AUTOMATION_ENGINE_DIR / "analyze.py"
            subprocess.run([sys.executable, str(analysis_script), str(f)], check=True, stdout=subprocess.DEVNULL)
            print(f"    [+] Features cached successfully.")
        except subprocess.CalledProcessError:
            print(f"    [!] Warning: Analysis failed for {f.name}. Visuals will use default values.")
            
    # Phase 4: Capture optional parameters
    manifest_path = project_path / "release_manifest.json"
    if not manifest_path.exists():
        print(f"[!] FATAL ERROR: release_manifest.json not found at {manifest_path}")
        print("    Run release_setup.py first to initialize this release.")
        return
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[!] FATAL ERROR: release_manifest.json is corrupted: {e}")
        return

    artist_ig = manifest.get("artist_instagram")
    artist_sc = manifest.get("artist_soundcloud")
    artist_fb = manifest.get("artist_facebook")

    if not args.non_interactive:
        print("\n" + "-" * 60)
        print("   PHASE: PIPELINE CONFIGURATION")
        print("-" * 60)
        
        if not sonic_qualities:
            default_sq = manifest.get("sonic_qualities") or manifest.get("mood_notes") or "Industrial synthesis, hardware density."
            user_input = input(f"ENTER SONIC QUALITIES / HARDWARE NODES\n[Default: '{default_sq}']: ").strip()
            sonic_qualities = user_input if user_input else default_sq
        manifest["sonic_qualities"] = sonic_qualities
        
        if not artist_ig:
            artist_ig = input("ENTER ARTIST INSTAGRAM LINK (Press [Enter] to generate placeholder): ").strip()
            if not artist_ig:
                artist_ig = "placeholder"
            manifest["artist_instagram"] = artist_ig
            
        if not artist_sc:
            artist_sc = input("ENTER ARTIST SOUNDCLOUD LINK (Press [Enter] to generate placeholder): ").strip()
            if not artist_sc:
                artist_sc = "placeholder"
            manifest["artist_soundcloud"] = artist_sc
            
        if not artist_fb:
            artist_fb = input("ENTER ARTIST FACEBOOK LINK (Press [Enter] to skip): ").strip()
            if not artist_fb:
                artist_fb = "skipped"
            manifest["artist_facebook"] = artist_fb
            
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)
    else:
        needs_write = False
        if not artist_ig:
            manifest["artist_instagram"] = "placeholder"
            needs_write = True
        if not artist_sc:
            manifest["artist_soundcloud"] = "placeholder"
            needs_write = True
        if not artist_fb:
            manifest["artist_facebook"] = "skipped"
            needs_write = True
            
        if needs_write:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=4)

        if not sonic_qualities:
            sonic_qualities = manifest.get("sonic_qualities") or manifest.get("mood_notes") or "Industrial synthesis, hardware density."
        manifest["sonic_qualities"] = sonic_qualities
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)

    # Phase 5: Sequential execution
    print("\n" + "-" * 60)
    print("   PHASE: PIPELINE EXECUTION SEQUENCE")
    print("-" * 60)

    # Checkpoint: determine starting step
    resume_from = 0
    if args.resume:
        resume_from = _load_checkpoint(project_path)
        if resume_from > 0:
            print(f"[RESUME] Skipping steps 1–{resume_from}, resuming from step {resume_from + 1}.\n")
        else:
            print("[RESUME] No checkpoint found. Running full pipeline.\n")

    # Step 1: Text generation (Gemini review allowed in interactive mode)
    if resume_from < 1:
        text_cmd = [sys.executable, "generate_release_text.py", serial, "--sonic-qualities", sonic_qualities]
        if args.non_interactive:
            text_cmd.append("--auto")
        if not run_step("Step 1: Text Generation & Metadata Injection", text_cmd):
            return
        _save_checkpoint(project_path, 1, "Text Generation & Metadata Injection")

    # Step 2: Audio Masters MP3 Transcoding
    if resume_from < 2:
        convert_cmd = [sys.executable, "convert_320.py", serial]
        if not run_step("Step 2: Audio Masters MP3 Coupling", convert_cmd):
            return
        _save_checkpoint(project_path, 2, "Audio Masters MP3 Coupling")

    # Step 3: TouchDesigner Generative Render
    if resume_from < 3:
        td_cmd = [sys.executable, "td_trigger.py", serial]
        if args.non_interactive:
            td_cmd.append("--non-interactive")
        if not run_step("Step 3: Audio-Reactive Background Rendering", td_cmd):
            return
        _save_checkpoint(project_path, 3, "Audio-Reactive Background Rendering")

    # Step 4: Cairo square vector overlay
    if resume_from < 4:
        vector_square_cmd = ["/bin/bash", "visual_processing/exec_vector_gen.sh", serial, "square"]
        if not run_step("Step 4: Vector Branding Overlay (Square)", vector_square_cmd):
            return
        _save_checkpoint(project_path, 4, "Vector Branding Overlay (Square)")

    # Step 5: Cairo vertical vector overlay
    if resume_from < 5:
        vector_vertical_cmd = ["/bin/bash", "visual_processing/exec_vector_gen.sh", serial, "vertical"]
        if not run_step("Step 5: Vector Branding Overlay (Vertical)", vector_vertical_cmd):
            return
        _save_checkpoint(project_path, 5, "Vector Branding Overlay (Vertical)")

    # Step 6: Pillow Art & FFmpeg Social Clips multiplexer
    if resume_from < 6:
        compositor_cmd = [sys.executable, "visual_processing/audio_art_generator.py", serial]
        if not run_step("Step 6: Final Multiplex Compositor & Social Packager", compositor_cmd):
            return
        _save_checkpoint(project_path, 6, "Final Multiplex Compositor & Social Packager")

    # Cover Art Version Selection & Archival Phase
    if resume_from < 7:
        artwork_dir = project_path / "02_Artwork"
        v1_path = artwork_dir / f"{serial}_CoverArt_V1.png"
        v2_path = artwork_dir / f"{serial}_CoverArt_V2.png"
        v3_path = artwork_dir / f"{serial}_CoverArt_V3.png"

        selected_ver = "1"
        if not args.non_interactive:
            print("\n" + "-" * 60)
            print("   PHASE: COVER ART VERSION SELECTION")
            print("-" * 60)
            print("Select the official cover art version for release:")
            print("  [1] V1 (Frame captured at 30s timestamp)")
            print("  [2] V2 (Frame captured at 60s timestamp)")
            print("  [3] V3 (Frame captured at 90s timestamp)")
            choice_cover = input("\nSelect version (1, 2, or 3) [Default: 1]: ").strip()
            if choice_cover in ["1", "2", "3"]:
                selected_ver = choice_cover

        # Rename selected to f"{serial}_CoverArt.png"
        # Rename non-selected to f"{serial}_CoverArt_V{x}_archived.png"
        ver_paths = {"1": v1_path, "2": v2_path, "3": v3_path}
        for ver, path in ver_paths.items():
            if path.exists():
                if ver == selected_ver:
                    new_path = artwork_dir / f"{serial}_CoverArt.png"
                    path.rename(new_path)
                    print(f"[+] Promoted Cover Art V{ver} to official release cover: {new_path.name}")
                else:
                    archive_path = artwork_dir / f"{serial}_CoverArt_V{ver}_archived.png"
                    path.rename(archive_path)
                    print(f"[+] Archived Cover Art V{ver} to: {archive_path.name}")

        # Step 6b: Auto-generate SoundCloud preview artwork variants
        preview_cmd = [sys.executable, "visual_processing/generate_preview_artwork.py", serial]
        run_step("Step 6b: Auto-Generate Grayscale SoundCloud Preview Cover Art", preview_cmd)

        # Step 6c: Auto-generate 3000x3000px high-res JPG cover art for distribution
        dist_cmd = [sys.executable, "visual_processing/generate_distribution_cover.py", serial]
        run_step("Step 6c: Auto-Generate 3000x3000px High-Res JPG Distribution Cover Art", dist_cmd)
        _save_checkpoint(project_path, 7, "Cover Art Selection & Distribution Art")

    # Step 7: Push EPK to Notion (Optional; failure will not halt the pipeline)
    if resume_from < 8:
        notion_cmd = [sys.executable, "push_to_notion.py", serial]
        run_step("Step 7: Push EPK to Notion", notion_cmd)
        _save_checkpoint(project_path, 8, "Push EPK to Notion")

    # Step 8: Generate Metricool bulk scheduler CSV (Optional)
    if resume_from < 9:
        metricool_cmd = [sys.executable, "generate_metricool_csv.py", serial]
        run_step("Step 8: Generate Metricool CSV Bulk Upload Schedule", metricool_cmd)
        _save_checkpoint(project_path, 9, "Metricool CSV Generation")

    # Step 9: Sync Full Artist Review Package to Google Drive (Optional)
    if resume_from < 10:
        artist_sync_cmd = [sys.executable, "google_drive_sync.py", serial]
        run_step("Step 9: Sync Full Artist Review Package to Google Drive", artist_sync_cmd)
        _save_checkpoint(project_path, 10, "Google Drive Sync")

    # Phase 6: Sync manifest status to completed
    manifest_path = project_path / "release_manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest["status"] = "completed"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=4)
            print("[SYSTEM] Manifest synchronized to status: completed")
        except Exception as e:
            print(f"[!] Warning: Failed to update status in manifest: {e}")

    # Phase 7: Verification and summary
    print("\n" + "=" * 70)
    print("   [PIPELINE SUCCESS] RELEASE AUTOMATION SEQUENCE COMPLETE!   ")
    print("=" * 70)
    print(f"Release Serial: {serial}")
    print(f"Project Path:   {project_path}")
    print("\nGenerated distribution assets:")
    
    # Find tracks
    # (Note: we read it inside try-except in check_audio_masters or simple check)
    tracks = []
    try:
        tracks = [f.stem for f in check_audio_masters(project_path)]
    except Exception:
        pass
    
    # List generated assets
    asset_paths = [
        ("EPK Text", project_path / "EPK" / "EPK.txt"),
        ("MP3 Masters Bundle", project_path / "EPK" / "MP3_320kbps"),
        ("TouchDesigner Masters", project_path / "03_Social" / "td_masters"),
        ("Overlays", project_path / "02_Artwork"),
        ("Official Release Cover Art", project_path / "02_Artwork" / f"{serial}_CoverArt.png"),
        ("Metricool Bulk Schedule", project_path / "03_Social" / "metricool_schedule.csv"),
    ]
    
    for t in tracks:
        asset_paths.append((f"9x16 Social Video Clip ({t})", project_path / "03_Social" / f"{t}_9x16_Social_Clip.mp4"))
        asset_paths.append((f"16:9 YouTube Video ({t})", project_path / "04_DTV" / f"{t}_YT_Full.mp4"))
        
    for name, path in asset_paths:
        status = "[FOUND]" if path.exists() else "[MISSING]"
        print(f"  {status:<9} {name}: {path.name}")
        
    # Print Artist Socials Summary
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            final_manifest = json.load(f)
        
        artist_ig = final_manifest.get("artist_instagram", "placeholder")
        artist_sc = final_manifest.get("artist_soundcloud", "placeholder")
        artist_fb = final_manifest.get("artist_facebook", "skipped")
        artist_name = final_manifest.get("artist", "")
        artist_slug = artist_name.lower().replace(" ", "").replace("_", "").replace("-", "")
        
        print("\nSynchronized Social Media Links:")
        
        # Instagram
        if artist_ig == "placeholder" or not artist_ig:
            print(f"  Instagram:  https://www.instagram.com/{artist_slug}/ [GENERATED PLACEHOLDER]")
        else:
            print(f"  Instagram:  {artist_ig}")
            
        # SoundCloud
        if artist_sc == "placeholder" or not artist_sc:
            print(f"  SoundCloud: https://soundcloud.com/{artist_slug} [GENERATED PLACEHOLDER]")
        else:
            print(f"  SoundCloud: {artist_sc}")
            
        # Facebook
        if artist_fb and artist_fb != "skipped":
            print(f"  Facebook:   {artist_fb}")
        else:
            print(f"  Facebook:   [SKIPPED]")
            
        # Print Artist Google Drive Folder Link
        artist_drive_url = final_manifest.get("artist_drive_folder_url")
        if artist_drive_url:
            print(f"\nArtist Review Google Drive Folder:")
            print(f"  Link:       {artist_drive_url}")
    except Exception as e:
        print(f"\n[!] Warning: Could not generate social links summary: {e}")
        
    print("\n[SYSTEM POSTURE SECURE — WORKFLOW SUCCESSFULLY COMPLETED]")

if __name__ == "__main__":
    main()
