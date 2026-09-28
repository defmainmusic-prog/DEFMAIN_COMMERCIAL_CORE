#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import resolve_release_path

def find_font():
    """Finds a suitable bold/monospace font on macOS."""
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf"
    ]
    for path in font_paths:
        if os.path.exists(path):
            return path
    return None

def create_diagonal_preview(base_img, text, font_path, angle=45):
    """Creates a preview artwork with an angled semi-transparent banner and text."""
    # Convert base image to grayscale and keep it as RGBA
    gray_img = ImageOps.grayscale(base_img).convert("RGBA")
    w, h = gray_img.size
    
    # Create overlay canvas
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    
    # Create a separate canvas for the band to rotate
    # Diagonal length of w x h square is sqrt(2)*w
    band_len = int((w**2 + h**2)**0.5) + 100
    band_h = int(h * 0.15) # 15% of height
    
    band_canvas = Image.new("RGBA", (band_len, band_h), (0, 0, 0, 0))
    draw_band = ImageDraw.Draw(band_canvas)
    
    # Draw the semi-transparent black banner
    # Draw a dark background band
    draw_band.rectangle([(0, 0), (band_len, band_h)], fill=(0, 0, 0, 200))
    
    # Draw top and bottom thin accent lines
    draw_band.line([(0, 2), (band_len, 2)], fill=(255, 255, 255, 220), width=3)
    draw_band.line([(0, band_h - 4), (band_len, band_h - 4)], fill=(255, 255, 255, 220), width=3)
    
    # Load Font
    font_size = int(band_h * 0.5)
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()
        
    # Get text size to center it
    text_w = draw_band.textlength(text, font=font)
    text_x = (band_len - text_w) // 2
    
    # Use standard text drawing (adjust y slightly to center vertically)
    text_y = (band_h - font_size) // 2 - int(font_size * 0.08)
    
    # Draw text in white
    draw_band.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))
    
    # Rotate the band (positive angle rotates counter-clockwise, meaning P bottom-left to W top-right)
    rotated_band = band_canvas.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    
    # Paste rotated band onto overlay centered
    rb_w, rb_h = rotated_band.size
    paste_x = (w - rb_w) // 2
    paste_y = (h - rb_h) // 2
    
    overlay.paste(rotated_band, (paste_x, paste_y), mask=rotated_band)
    
    # Composite overlay onto grayscale base
    final_img = Image.alpha_composite(gray_img, overlay)
    return final_img.convert("RGB")

def create_horizontal_preview(base_img, text, font_path):
    """Creates a preview artwork with straight centered outlined text (stamp-like)."""
    gray_img = ImageOps.grayscale(base_img).convert("RGBA")
    w, h = gray_img.size
    
    # Create overlay canvas
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Load Font - make it very large
    font_size = int(w * 0.12) # 12% of width
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()
        
    # Get text size to center it
    text_w = draw.textlength(text, font=font)
    text_x = (w - text_w) // 2
    text_y = (h - font_size) // 2
    
    # Draw a semi-transparent black background block behind the text to increase contrast
    box_padding_x = int(w * 0.05)
    box_padding_y = int(h * 0.02)
    box_x0 = text_x - box_padding_x
    box_y0 = text_y - box_padding_y
    box_x1 = text_x + text_w + box_padding_x
    box_y1 = text_y + font_size + box_padding_y
    
    draw.rectangle([(box_x0, box_y0), (box_x1, box_y1)], fill=(0, 0, 0, 180))
    draw.rectangle([(box_x0, box_y0), (box_x1, box_y1)], outline=(255, 255, 255, 220), width=4)
    
    # Draw text in white
    draw.text((text_x, text_y - int(font_size * 0.08)), text, font=font, fill=(255, 255, 255, 255))
    
    # Composite overlay onto grayscale base
    final_img = Image.alpha_composite(gray_img, overlay)
    return final_img.convert("RGB")

def main():
    parser = argparse.ArgumentParser(description="Generate grayscale preview cover art with watermarks.")
    parser.add_argument("serial", help="Release serial (e.g., SRC004)")
    parser.add_argument("--text", default="P R E V I E W", help="Watermark text (default: 'P R E V I E W')")
    
    args = parser.parse_args()
    serial = args.serial.upper().strip()
    
    project_path_str = resolve_release_path(serial)
    if not project_path_str:
        print(f"[ERROR]: Could not locate project directory for serial {serial}")
        sys.exit(1)
        
    project_path = Path(project_path_str)
    artwork_dir = project_path / "02_Artwork"
    
    if not artwork_dir.exists():
        print(f"[ERROR]: Artwork directory does not exist: {artwork_dir}")
        sys.exit(1)
        
    # Find original cover art to transform
    cover_art_candidates = [
        artwork_dir / f"{serial}_CoverArt.png",
        artwork_dir / f"{serial}_CoverArt_V1.png",
        artwork_dir / f"{serial}_CoverArt_V1_archived.png"
    ]
    
    # If not found directly, search for any png containing CoverArt and the serial
    cover_art_path = None
    for cand in cover_art_candidates:
        if cand.exists():
            cover_art_path = cand
            break
            
    if not cover_art_path:
        # Generic fallback search
        pngs = list(artwork_dir.glob("*.png"))
        for p in pngs:
            if "coverart" in p.name.lower():
                cover_art_path = p
                break
                
    if not cover_art_path or not cover_art_path.exists():
        print(f"[ERROR]: Could not find any base cover art image in {artwork_dir}")
        sys.exit(1)
        
    print(f"[*] Found base cover art: {cover_art_path.name}")
    
    try:
        base_img = Image.open(str(cover_art_path)).convert("RGBA")
    except Exception as e:
        print(f"[ERROR]: Failed to load image {cover_art_path}: {e}")
        sys.exit(1)
        
    font_path = find_font()
    if font_path:
        print(f"[*] Using system font: {font_path}")
    else:
        print("[WARNING]: No TrueType system fonts found, falling back to default PIL font.")
        
    # Generate 45-degree Angled version (P bottom-left to W top-right)
    angled_path = artwork_dir / f"{serial}_CoverArt_Preview_Angled.png"
    angled_img = create_diagonal_preview(base_img, args.text, font_path, angle=45)
    angled_img.save(str(angled_path), "PNG")
    print(f"[SUCCESS]: Generated 45-degree angled preview cover -> {angled_path.name}")
    
    # Generate Horizontal version
    horizontal_path = artwork_dir / f"{serial}_CoverArt_Preview_Horizontal.png"
    horizontal_img = create_horizontal_preview(base_img, args.text, font_path)
    horizontal_img.save(str(horizontal_path), "PNG")
    print(f"[SUCCESS]: Generated horizontal preview cover -> {horizontal_path.name}")
    
    # Create the standard preview cover linking to angled version by default
    standard_preview_path = artwork_dir / f"{serial}_CoverArt_Preview.png"
    angled_img.save(str(standard_preview_path), "PNG")
    print(f"[SUCCESS]: Saved default preview cover art to -> {standard_preview_path.name}")

if __name__ == "__main__":
    main()
