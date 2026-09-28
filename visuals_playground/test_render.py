#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="DEFMAIN PLATFORM: BATCH RENDER STABILITY TESTER")
    parser.add_argument("--template", required=True, help="Template name to test (e.g., 'scopes' or 'liquid')")
    parser.add_argument("--audio", help="Fallback audio file to use for all 3 runs")
    
    # Resolve default test track directory (local to this script)
    default_tracks_dir = Path(__file__).parent / "test_tracks"
    
    parser.add_argument(
        "--audio1", 
        default=str(default_tracks_dir / "breakbeat_track.wav"),
        help="Audio file for Run 1 (Default: test_tracks/breakbeat_track.wav)"
    )
    parser.add_argument(
        "--audio2", 
        default=str(default_tracks_dir / "melodic_perc_track.wav"),
        help="Audio file for Run 2 (Default: test_tracks/melodic_perc_track.wav)"
    )
    parser.add_argument(
        "--audio3", 
        default=str(default_tracks_dir / "4_4_kick_bass_track.wav"),
        help="Audio file for Run 3 (Default: test_tracks/4_4_kick_bass_track.wav)"
    )
    args = parser.parse_args()

    # Resolve audio paths for each run
    runs_config = [
        {"id": 1, "arg_val": args.audio1, "desc": "Run 1 (Breakbeat / Non-4-4)", "bpm": 140.0, "pitch_class": 0},
        {"id": 2, "arg_val": args.audio2, "desc": "Run 2 (Melodic / Percussion)", "bpm": 125.0, "pitch_class": 4},
        {"id": 3, "arg_val": args.audio3, "desc": "Run 3 (4-4 Kick / Bass Drops)", "bpm": 133.0, "pitch_class": 8}
    ]

    # Validate template
    template_dir = Path(__file__).parent / "templates"
    template_path = template_dir / f"{args.template}.toe"
    if not template_path.exists():
        print(f"[!] ERROR: Template not found: {template_path}")
        return

    print("=" * 60)
    print(f"[*] INITIATING BATCH RENDERING TEST: 3 tracks x 2 minutes")
    print(f"    Template: {template_path.name}")
    print("=" * 60)

    success_count = 0
    start_time = time.time()

    for run in runs_config:
        run_id = run["id"]
        bpm = run["bpm"]
        pitch_class = run["pitch_class"]
        desc = run["desc"]
        
        # Determine raw audio source
        raw_audio_val = run["arg_val"] or args.audio
        if not raw_audio_val:
            print(f"[-] ERROR: No audio file provided for Run {run_id}. Please specify --audio{run_id} or fallback --audio.")
            return
            
        raw_audio_path = Path(raw_audio_val).resolve()
        if not raw_audio_path.exists():
            print(f"[-] ERROR: Audio file for Run {run_id} not found: {raw_audio_path}")
            print(f"    Please ensure the default test track exists or pass a custom path.")
            return
            
        sliced_audio = Path(f"/tmp/test_2min_{run_id}.wav")
        silent_video = Path(f"/tmp/test_render_{run_id}_SILENT.mp4")
        final_video = Path(f"/tmp/test_render_{run_id}_Master.mp4")
        
        # Clean up old test files if they exist
        if sliced_audio.exists(): sliced_audio.unlink()
        if silent_video.exists(): silent_video.unlink()
        if final_video.exists(): final_video.unlink()

        print(f"\n[ RUN {run_id}/3 ] {desc}")
        print(f"  Source Audio: {raw_audio_path.name}")
        print(f"  Simulated:    BPM: {bpm} | Pitch Class: {pitch_class}")
        
        # Slice audio to 2 minutes
        slice_cmd = [
            "ffmpeg", "-v", "warning", "-y",
            "-i", str(raw_audio_path),
            "-t", "120",
            "-c", "copy",
            str(sliced_audio)
        ]
        try:
            subprocess.run(slice_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  [-] ERROR: Slicing failed with FFmpeg: {e}")
            continue

        # Write task payload
        payload = {
            "audio_in": str(sliced_audio),
            "video_out": str(silent_video),
            "test_mode": False,  # Offline rendering (record and quit)
            "bpm": bpm,
            "brightness": 0.5,
            "energy": 0.7,
            "pitch_class": pitch_class
        }
        
        with open("/tmp/defmain_td_task.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
            
        print(f"  [*] Launching TouchDesigner background render...")
        td_start = time.time()
        
        # Launch TouchDesigner and wait for it to render and exit
        try:
            subprocess.run(["/Applications/TouchDesigner.app/Contents/MacOS/TouchDesigner", str(template_path)], check=True)
            td_duration = time.time() - td_start
            print(f"  [+] TouchDesigner exited successfully in {td_duration:.1f} seconds.")
        except subprocess.CalledProcessError as e:
            print(f"  [-] ERROR: TouchDesigner rendering process failed: {e}")
            if sliced_audio.exists(): sliced_audio.unlink()
            continue

        # Multiplex audio and transcode video using macOS VideoToolbox Hardware Encoder
        if silent_video.exists():
            print(f"  [*] Transcoding and multiplexing video to H.264 (Apple Hardware Accelerated)...")
            ffmpeg_cmd = [
                "ffmpeg", "-v", "warning", "-y",
                "-i", str(silent_video),
                "-i", str(sliced_audio),
                "-c:v", "h264_videotoolbox",  # Uses Apple silicon hardware chip!
                "-c:a", "aac", "-b:a", "320k",
                "-shortest",
                str(final_video)
            ]
            try:
                subprocess.run(ffmpeg_cmd, check=True)
                print(f"  [+] SUCCESS: Created final master: {final_video}")
                silent_video.unlink()
                success_count += 1
            except subprocess.CalledProcessError as e:
                print(f"  [-] ERROR: FFmpeg transcoding failed: {e}")
        else:
            print(f"  [-] ERROR: Expected output video missing at: {silent_video}")

        # Clean up sliced audio chunk
        if sliced_audio.exists():
            sliced_audio.unlink()
            
        # Short cooldown to let macOS release window/gpu context
        time.sleep(2)

    # Summary
    total_duration = time.time() - start_time
    print("\n" + "=" * 60)
    print("   BATCH RENDER TEST RESULTS")
    print("=" * 60)
    print(f"Rendered:  {success_count}/3 tracks successfully")
    print(f"Duration:  {total_duration:.1f} seconds (average {total_duration/3:.1f}s per track)")
    if success_count == 3:
        print("[STATUS]   PASS - Template is fully stable and sequential rendering is bulletproof!")
    else:
        print("[STATUS]   FAIL - Sequential rendering encountered errors.")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
