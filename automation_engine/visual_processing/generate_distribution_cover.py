#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import resolve_release_path

def extract_high_res_frame(video_path, timestamp, output_path):
    """Extracts a 3000x3000px high-resolution frame from the video using FFmpeg."""
    cmd = [
        'ffmpeg', '-y',
        '-ss', timestamp,
        '-i', str(video_path),
        '-vf', 'scale=3000:3000:force_original_aspect_ratio=increase,crop=3000:3000',
        '-vframes', '1',
        '-q:v', '2',
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True)
    return output_path.exists()

def generate_high_res_cover(serial, timestamp=None):
    """Generates a 3000x3000px JPG cover art for distribution."""
    serial = serial.upper().strip()
    project_path_str = resolve_release_path(serial)
    if not project_path_str:
        print(f"[ERROR]: Could not find project directory for serial {serial}")
        return False
        
    project_path = Path(project_path_str)
    artwork_dir = project_path / "02_Artwork"
    
    # 1. Determine timestamp if not provided
    if not timestamp:
        # Check archive files to determine which version was selected
        v1_archived = artwork_dir / f"{serial}_CoverArt_V1_archived.png"
        v2_archived = artwork_dir / f"{serial}_CoverArt_V2_archived.png"
        v3_archived = artwork_dir / f"{serial}_CoverArt_V3_archived.png"
        
        # If V1 was promoted, V1_archived will NOT exist (it was renamed to CoverArt.png)
        # while V2 and V3 will exist.
        if not v1_archived.exists() and (v2_archived.exists() or v3_archived.exists()):
            timestamp = "00:00:30" # V1
            print("[*] Detected V1 cover art selection.")
        elif not v2_archived.exists() and (v1_archived.exists() or v3_archived.exists()):
            timestamp = "00:01:00" # V2
            print("[*] Detected V2 cover art selection.")
        elif not v3_archived.exists() and (v1_archived.exists() or v2_archived.exists()):
            timestamp = "00:01:30" # V3
            print("[*] Detected V3 cover art selection.")
        else:
            timestamp = "00:00:30" # Default fallback
            print("[*] No archival signature detected. Defaulting to V1 (30s) timestamp.")
            
    print(f"[*] Target frame extraction timestamp: {timestamp}")
    
    # 2. Find video file
    td_path = project_path / "03_Social" / "td_masters"
    if not td_path.exists():
        print(f"[ERROR]: td_masters path missing at {td_path}")
        return False
        
    mp4_files = list(td_path.glob("*.mp4"))
    if not mp4_files:
        print("[ERROR]: No TD master videos found to extract frame from.")
        return False
        
    video_path = mp4_files[0]
    print(f"[*] Found video master source: {video_path.name}")
    
    # 3. Find overlay file
    overlay_path = artwork_dir / f"{serial}_overlay_square.png"
    if not overlay_path.exists():
        print(f"[ERROR]: High-res overlay file missing at {overlay_path}")
        return False
        
    # 4. Extract base high-res frame
    temp_frame = artwork_dir / "temp_frame_3000.png"
    print("[*] Extracting and upscaling base frame to 3000x3000px...")
    if not extract_high_res_frame(video_path, timestamp, temp_frame):
        print("[ERROR]: Failed to extract frame via FFmpeg.")
        return False
        
    # 5. Composite and save
    try:
        base_img = Image.open(str(temp_frame)).convert("RGBA")
        overlay_img = Image.open(str(overlay_path)).convert("RGBA")
        
        # Ensure overlay matches base image size (3000x3000px)
        if overlay_img.size != base_img.size:
            print(f"[*] Resizing overlay from {overlay_img.size} to {base_img.size}")
            overlay_img = overlay_img.resize(base_img.size, Image.Resampling.LANCZOS)
            
        # Draw bottom-scrim gradient for typography readability
        # Original: height 400 for 1080 canvas. Equivalent for 3000 canvas is 400 * 3000 / 1080 = 1111px.
        scrim_h = int(base_img.height * (400 / 1080))
        gradient = Image.new('L', (base_img.width, scrim_h), color=0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(gradient)
        for i in range(scrim_h):
            draw.line([(0, i), (base_img.width, i)], fill=int(255 * (i / scrim_h)))
        scrim = ImageOps.colorize(gradient, black="black", white="black").convert("RGBA")
        
        base_img.paste(scrim, (0, base_img.height - scrim_h), mask=gradient)
        base_img.paste(overlay_img, (0, 0), mask=overlay_img)
        
        # Save as high-quality JPG for distribution
        output_jpg_path = artwork_dir / f"{serial}_CoverArt.jpg"
        base_img.convert("RGB").save(str(output_jpg_path), "JPEG", quality=95)
        print(f"[SUCCESS]: Generated 3000x3000px distribution cover -> {output_jpg_path.name}")
        
        # Clean up temp frame
        if temp_frame.exists():
            temp_frame.unlink()
            
        return True
    except Exception as e:
        print(f"[ERROR]: Image compositing failed: {e}")
        if temp_frame.exists():
            temp_frame.unlink()
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate 3000x3000px high-res JPG cover art for distribution.")
    parser.add_argument("serial", help="Release serial (e.g. SRC004)")
    parser.add_argument("--timestamp", help="Specific timestamp to extract (e.g. 00:00:30)")
    
    args = parser.parse_args()
    success = generate_high_res_cover(args.serial, args.timestamp)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
