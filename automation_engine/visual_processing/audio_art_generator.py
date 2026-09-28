#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

# Ensure visual_processing is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import resolve_release_path
from render_vector_overlay import render_overlay

def parse_track_metadata(track_name, fallback_artist):
    """Parses track artist and title from a filename like 'Artist - Track Title - Master'."""
    if " - " in track_name:
        parts = track_name.split(" - ", 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    else:
        artist = fallback_artist
        title = track_name.strip()
        
    # If the title starts with the artist name case-insensitively, strip it and any trailing separator
    if artist and title.lower().startswith(artist.lower()):
        prefix_len = len(artist)
        if len(title) > prefix_len and title[prefix_len] in ['-', '_', ' ']:
            title = title[prefix_len + 1:]
        elif len(title) > prefix_len:
            title = title[prefix_len:]
            
    # Clean up common suffixes
    suffixes_to_remove = [
        "- master", "-master", "_master", " master",
        "- ref", "-ref", " ref",
        "- mix", "-mix", " mix"
    ]
    for suffix in suffixes_to_remove:
        if title.lower().endswith(suffix):
            title = title[:-len(suffix)]
            break
            
    # Replace underscores with spaces and clean
    title = title.replace("_", " ")
    title = title.strip(" -_")
    return artist, title


def extract_specific_frame(video_path, timestamp, frame_path):
    """Extracts a high-resolution reference frame at a specific timestamp via FFmpeg."""
    cmd = [
        'ffmpeg', '-y', 
        '-ss', timestamp, 
        '-i', str(video_path), 
        '-vf', 'scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080',
        '-vframes', '1', 
        '-q:v', '2', 
        str(frame_path)
    ]
    result = subprocess.run(cmd, capture_output=True)
    return frame_path.exists()

def generate_multi_cover_art(serial, project_path):
    """Generates three distinct cover options from different timestamps to ensure optimal visual selection."""
    clean_serial = serial.upper().strip()
    artwork_dir = project_path / "02_Artwork"
    td_path = project_path / "03_Social" / "td_masters"
    
    if not td_path.exists():
        print(f"[!] ERROR: td_masters path missing at {td_path}")
        return
        
    mp4_files = list(td_path.glob("*.mp4"))
    if not mp4_files: 
        print(f"[!] ERROR: No TD master videos found to extract frames from.")
        return
        
    video_path = mp4_files[0]
    overlay_path = artwork_dir / f"{clean_serial}_overlay_square.png"
    
    if not overlay_path.exists():
        print(f"[!] ERROR: Square overlay missing at {overlay_path}")
        return

    # Timestamps targeted across different sectors of the audio timeline
    variants = {
        "V1": "00:00:30",
        "V2": "00:01:00",
        "V3": "00:01:30"
    }

    print(f"[*] INITIATING MULTI-FRAME EXTENSION PROTOCOL FOR {clean_serial}...")

    for suffix, timestamp in variants.items():
        temp_frame = artwork_dir / f"temp_frame_{suffix}.png"
        output_path = artwork_dir / f"{clean_serial}_CoverArt_{suffix}.png"
        
        # 1. Extract the unique snapshot
        if not extract_specific_frame(video_path, timestamp, temp_frame):
            print(f"[-] Failed to extract frame at {timestamp}. Skipping variant {suffix}...")
            continue
            
        # 2. Composite graphics layer with Pillow
        base_img = Image.open(str(temp_frame)).convert("RGBA")
        overlay_img = Image.open(str(overlay_path)).convert("RGBA").resize(base_img.size, Image.Resampling.LANCZOS)
        
        # Bottom-scrim gradient composition block for typography contrast isolation
        gradient = Image.new('L', (base_img.width, 400), color=0)
        draw = ImageDraw.Draw(gradient)
        for i in range(400):
            draw.line([(0, i), (base_img.width, i)], fill=int(255 * (i/400)))
        scrim = ImageOps.colorize(gradient, black="black", white="black").convert("RGBA")
        
        base_img.paste(scrim, (0, base_img.height - 400), mask=gradient)
        base_img.paste(overlay_img, (0, 0), mask=overlay_img)
        base_img.convert("RGB").save(str(output_path), "PNG")
        print(f"[+] COMPILED VARIANT: {output_path.name} ({timestamp})")
        
        # 3. Automatic Housekeeping Sweep
        if temp_frame.exists():
            temp_frame.unlink()

def generate_social_clip_9x16(serial, project_path, start_time="00:00:30"):
    """Multiplexes the vertical overlay on a centered 9x16 crop of the TouchDesigner loop."""
    clean_serial = serial.upper().strip()
    td_path = project_path / "03_Social" / "td_masters"
    td_masters = list(td_path.glob("*_TD_Master.mp4"))
    
    if not td_masters:
        print(f"[!] ERROR: No files ending in '_TD_Master.mp4' found in {td_path}")
        return

    # Load release artist fallback from manifest
    manifest_artist = ""
    try:
        manifest_path = project_path / 'release_manifest.json'
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_artist = json.load(f).get('artist', '')
    except Exception:
        pass

    for master_file in td_masters:
        track_name = master_file.stem.replace("_TD_Master", "")
        output_clip = project_path / "03_Social" / f"{track_name}_9x16_Social_Clip.mp4"
        
        # Parse track-specific metadata
        track_artist, track_title = parse_track_metadata(track_name, manifest_artist)
        
        # Generate track-specific vertical overlay
        overlay_path = render_overlay(serial, 'vertical', track_title=track_title, track_artist=track_artist)
        
        # Fallback to general release overlay if rendering failed
        if not overlay_path or not overlay_path.exists():
            overlay_path = project_path / "02_Artwork" / f"{clean_serial}_overlay_vertical.png"
            
        if not overlay_path.exists():
            print(f"[!] ERROR: Vertical overlay missing at {overlay_path}")
            continue

        print(f"[*] COMPOSITING VERTICAL CLIP: {master_file.name} (Artist: {track_artist}, Track: {track_title})")
        
        cmd = [
            'ffmpeg', '-y',
            '-ss', start_time,
            '-t', '30',
            '-i', str(master_file),
            '-i', str(overlay_path),
            '-filter_complex', 
            "[0:v]scale=1080:-1[scaled];"
            "[scaled]pad=1080:1920:0:(oh-ih)/2:color=black[bg];"
            "[bg][1:v]overlay=0:0",
            '-c:a', 'aac', '-b:a', '320k',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            str(output_clip)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"[+] SUCCESS: VERTICAL CLIP -> {output_clip.name}")
            
            # Extract 30-second SoundCloud Preview MP3 from the vertical clip
            preview_dir = project_path / "EPK" / "MP3_320kbps"
            preview_dir.mkdir(parents=True, exist_ok=True)
            
            # Clean track name of suffixes for preview file naming
            clean_track_stem = track_name
            suffixes_to_remove = ["- master", "-master", "_master", " master", "- ref", "-ref", " ref"]
            for suffix in suffixes_to_remove:
                if clean_track_stem.lower().endswith(suffix):
                    clean_track_stem = clean_track_stem[:-len(suffix)].strip(" -_")
                    break
            preview_path = preview_dir / f"{clean_track_stem}_Preview.mp3"
            
            preview_cmd = [
                'ffmpeg', '-y', '-v', 'warning',
                '-i', str(output_clip),
                '-vn',
                '-acodec', 'libmp3lame',
                '-b:a', '320k',
                str(preview_path)
            ]
            try:
                subprocess.run(preview_cmd, check=True)
                print(f"[+] SUCCESS: SOUNDCLOUD PREVIEW MP3 -> {preview_path.name}")
            except Exception as ex:
                print(f"[!] Warning: Failed to extract SoundCloud preview for {track_name}: {ex}")
        except subprocess.CalledProcessError as e:
            print(f"[-] ERROR: FFmpeg multiplexing failed for {track_name}")
            print(f"[-] STDERR: {e.stderr}")
        finally:
            # Clean up temporary track-specific overlay image
            if overlay_path and overlay_path.exists() and f"overlay_vertical_" in overlay_path.name:
                try:
                    overlay_path.unlink()
                except Exception:
                    pass

def generate_youtube_clip_16x9(serial, project_path):
    """Multiplexes the square overlay on a centered 16x9 landscape canvas for YouTube."""
    clean_serial = serial.upper().strip()
    td_path = project_path / "03_Social" / "td_masters"
    td_masters = list(td_path.glob("*_TD_Master.mp4"))
    
    # Load release artist fallback from manifest
    manifest_artist = ""
    try:
        manifest_path = project_path / 'release_manifest.json'
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_artist = json.load(f).get('artist', '')
    except Exception:
        pass

    for master_file in td_masters:
        track_name = master_file.stem.replace("_TD_Master", "")
        output_clip = project_path / "04_DTV" / f"{track_name}_YT_Full.mp4"
        
        # Parse track-specific metadata
        track_artist, track_title = parse_track_metadata(track_name, manifest_artist)
        
        # Generate track-specific square overlay
        overlay_path = render_overlay(serial, 'square', track_title=track_title, track_artist=track_artist)
        
        # Fallback to general release overlay if rendering failed
        if not overlay_path or not overlay_path.exists():
            overlay_path = project_path / "02_Artwork" / f"{clean_serial}_overlay_square.png"
            
        if not overlay_path.exists():
            print(f"[!] ERROR: Square overlay missing at {overlay_path}")
            continue

        print(f"[*] COMPOSITING YOUTUBE LANDSCAPE MASTER: {master_file.name} (Artist: {track_artist}, Track: {track_title})")
        
        cmd = [
            'ffmpeg', '-y', 
            '-i', str(master_file), 
            '-i', str(overlay_path),
            '-filter_complex', 
            "[0:v]scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080[vscaled];"
            "[1:v]scale=1080:1080[oscaled];"
            "color=c=black:s=1920x1080:d=1200[canvas];" 
            "[canvas][vscaled]overlay=(W-w)/2:(H-h)/2[base];"
            "[base][oscaled]overlay=(W-w)/2:(H-h)/2",
            '-c:a', 'copy', 
            '-c:v', 'libx264', 
            '-preset', 'ultrafast', 
            '-pix_fmt', 'yuv420p',
            '-shortest', 
            str(output_clip)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"[+] SUCCESS: YOUTUBE FULL -> {output_clip.name}")
        except subprocess.CalledProcessError as e:
            print(f"[-] ERROR: FFmpeg landscape composition failed for {master_file.name}")
        finally:
            # Clean up temporary track-specific overlay image
            if overlay_path and overlay_path.exists() and f"overlay_square_" in overlay_path.name:
                try:
                    overlay_path.unlink()
                except Exception:
                    pass

if __name__ == "__main__":
    serial_input = sys.argv[1] if len(sys.argv) > 1 else input("ENTER SERIAL: ").strip()
    project_path_str = resolve_release_path(serial_input)
    
    if not project_path_str:
        print(f"[!] ERROR: Could not locate project matching {serial_input}")
        sys.exit(1)

    project_path = Path(project_path_str)

    print("\n--- DEFMAIN: AUDIO-ART COMPOSITING & SOCIAL PACKAGER ---")
    # 1. Fire Multi-Variant Engine
    generate_multi_cover_art(serial_input, project_path)
    # 2. Compile Social assets
    generate_social_clip_9x16(serial_input, project_path, start_time="00:01:30")
    generate_youtube_clip_16x9(serial_input, project_path)
    print("\n[=] ALL PIPELINE SOCIAL ASSETS PACKAGES GENERATED [=]\n")