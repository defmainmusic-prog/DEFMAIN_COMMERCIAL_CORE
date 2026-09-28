#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="DEFMAIN PLATFORM: VISUALS PLAYGROUND & DESIGN ENGINE")
    parser.add_argument("--template", required=True, help="Template name (e.g., 'scopes' or 'liquid')")
    parser.add_argument("--audio", required=True, help="Path to test WAV audio file")
    parser.add_argument("--bpm", type=float, default=120.0, help="Simulated track BPM (Default: 120.0)")
    parser.add_argument("--pitch-class", type=int, default=0, help="Simulated pitch class for color mapping [0-11] (Default: 0)")
    args = parser.parse_args()
    
    audio_path = Path(args.audio).resolve()
    if not audio_path.exists():
        print(f"[!] ERROR: Audio file not found at: {audio_path}")
        return

    # Write playground test task payload
    payload = {
        "audio_in": str(audio_path),
        "video_out": "/tmp/playground_out.mp4",
        "test_mode": True,
        "bpm": args.bpm,
        "brightness": 0.5,
        "energy": 0.7,
        "pitch_class": args.pitch_class
    }
    
    task_path = Path("/tmp/defmain_td_task.json")
    with open(task_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
        
    # Resolve selected template path
    template_dir = Path(__file__).parent / "templates"
    template_path = template_dir / f"{args.template}.toe"
    
    if not template_path.exists():
        # Fallback to check template_pool/SRC if not in local playground
        fallback_path = Path("/Users/dmm/Documents/Defmain_Platform_Root/automation_engine/visual_processing/template_pool/SRC") / f"T-{args.template}.toe"
        if fallback_path.exists():
            template_path = fallback_path
        else:
            print(f"[!] ERROR: Template not found at: {template_path}")
            print(f"    Also checked fallback path: {fallback_path}")
            return
            
    # Launch TouchDesigner in GUI mode
    subprocess.Popen(["/Applications/TouchDesigner.app/Contents/MacOS/TouchDesigner", str(template_path)])
    print(f"\n[+] LAUNCHED VISUALS PLAYGROUND")
    print(f"    Template: {template_path.name}")
    print(f"    Audio:    {audio_path.name}")
    print(f"    Simulated BPM: {args.bpm} | Pitch Class: {args.pitch_class}")
    print(f"    Configure and preview interactively in the GUI. Close TouchDesigner when finished.")

if __name__ == "__main__":
    main()
