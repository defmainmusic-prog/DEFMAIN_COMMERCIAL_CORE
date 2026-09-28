#!/usr/bin/env python3
import os
import sys
import json
import uuid
import argparse
import datetime
import random
from pathlib import Path

from config import resolve_release_path

def find_title_track_file(files, release_title):
    """Identifies the file in a list that best matches the release title."""
    if not files:
        return None
    clean_title = release_title.lower().replace(" ", "").replace("_", "").replace("-", "")
    
    # Check exact substring overlap
    for f in files:
        clean_name = f.name.lower().replace(" ", "").replace("_", "").replace("-", "")
        if clean_title in clean_name or clean_name in clean_title:
            return f
            
    # Check individual words overlap
    title_words = [w for w in release_title.lower().split() if len(w) > 2]
    for f in files:
        clean_name = f.name.lower()
        if any(word in clean_name for word in title_words):
            return f
            
    # Fallback to the first file
    return files[0]

def populate_row(headers, text, date_val, time_val, media_url, is_ig, is_fb, is_tt, is_yt, title_val, yt_type_val="SHORT"):
    """Dynamically maps CSV fields to headers based on substring matching."""
    has_time_col = any("time" in h.lower() for h in headers)
    row = {}
    
    # Initialize all columns
    for h in headers:
        h_low = h.lower()
        if any(net == h_low for net in ["instagram", "facebook", "tiktok", "youtube"]):
            row[h] = "FALSE"
        elif any(f in h_low for f in ["disable comment", "disable duet", "disable stitch"]):
            row[h] = "FALSE"
        else:
            row[h] = ""
            
    # Populate fields based on matching rules
    for h in headers:
        h_low = h.lower()
        if "text" in h_low or "caption" in h_low:
            row[h] = text
        elif "time" in h_low:
            row[h] = time_val
        elif "date" in h_low:
            if has_time_col:
                row[h] = str(date_val)
            else:
                row[h] = f"{date_val} {time_val}"
        elif "picture" in h_low or "image" in h_low or "media" in h_low or "url" in h_low or h_low == "link":
            row[h] = media_url
        elif "youtube video title" in h_low or (h_low == "title" and is_yt):
            row[h] = title_val
        elif "youtube video type" in h_low:
            row[h] = yt_type_val
        elif "youtube video privacy" in h_low:
            row[h] = "PUBLIC"
        elif "youtube video category" in h_low:
            row[h] = "MUSIC"
        elif "tiktok post privacy" in h_low:
            row[h] = "PUBLIC_TO_EVERYONE"
        elif h_low == "instagram":
            row[h] = "TRUE" if is_ig else "FALSE"
        elif h_low == "facebook":
            row[h] = "TRUE" if is_fb else "FALSE"
        elif h_low == "tiktok":
            row[h] = "TRUE" if is_tt else "FALSE"
        elif h_low == "youtube":
            row[h] = "TRUE" if is_yt else "FALSE"
            
    return row

def build_metricool_schedule(serial):
    project_path = resolve_release_path(serial)
    if not project_path:
        print(f"[!] ERROR: Could not locate release matching {serial}")
        return False
        
    manifest_path = project_path / "release_manifest.json"
    if not manifest_path.exists():
        print(f"[!] ERROR: release_manifest.json missing at {manifest_path}")
        return False
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    release_date_str = manifest.get("release_date")
    release_title = manifest.get("title", "UNTITLED")
    
    if not release_date_str:
        print("[!] ERROR: 'release_date' not defined in manifest.")
        return False
        
    try:
        release_date = datetime.datetime.strptime(release_date_str, "%Y-%m-%d").date()
    except Exception as e:
        print(f"[!] ERROR: Could not parse release date '{release_date_str}': {e}")
        return False
        
    # 1. Locate Social Media Post copy files
    social_dir = project_path / "03_Social"
    post_files = {
        "Post1": social_dir / "Post1.txt",
        "Post2": social_dir / "Post2.txt",
        "Post3": social_dir / "Post3.txt"
    }
    
    posts_copy = {}
    for key, path in post_files.items():
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                posts_copy[key] = f.read().strip()
        else:
            posts_copy[key] = ""
            print(f"[!] Warning: Post copy file missing: {path.name}")
            
    # 2. Locate generated vertical video clips
    social_clips = sorted(list(social_dir.glob("*_Social_Clip.mp4")))
    if not social_clips:
        print(f"[!] Warning: No vertical social clips found in {social_dir}")
        
    # 3. Locate generated full landscape DTV videos
    dtv_dir = project_path / "04_DTV"
    dtv_videos = sorted(list(dtv_dir.glob("*.mp4")))
    
    # 4. Resolve Teaser 1 & 2 Video Assets
    teaser2_clip = find_title_track_file(social_clips, release_title)
    
    other_clips = [c for c in social_clips if c != teaser2_clip]
    if other_clips:
        teaser1_clip = random.choice(other_clips)
    else:
        teaser1_clip = teaser2_clip # Fallback if only 1 clip exists
        
    # 5. Resolve YouTube Full DTV Video Asset
    youtube_full_video = find_title_track_file(dtv_videos, release_title)
    
    # 6. Resolve cover art image file
    cover_art_local = None
    artwork_dir = project_path / "02_Artwork"
    for ext in [".png", ".jpg", ".jpeg"]:
        test_path = artwork_dir / f"coverart{ext}"
        if test_path.exists():
            cover_art_local = test_path
            break
            
    if not cover_art_local:
        # Fallback to promoted CoverArt.png first, then V1 fallback
        cover_art_local = artwork_dir / f"{serial.upper()}_CoverArt.png"
        if not cover_art_local.exists():
            cover_art_local = artwork_dir / f"{serial.upper()}_CoverArt_V1.png"
        
    # Prepare local files dictionary for Google Drive syncing
    local_files = {
        "teaser1": teaser1_clip if (teaser1_clip and teaser1_clip.exists()) else None,
        "teaser2": teaser2_clip if (teaser2_clip and teaser2_clip.exists()) else None,
        "cover": cover_art_local if (cover_art_local and cover_art_local.exists()) else None,
        "dtv": youtube_full_video if (youtube_full_video and youtube_full_video.exists()) else None
    }
    
    # Try to sync files to Google Drive
    drive_urls = {}
    try:
        # Add parent folder of generate_metricool_csv.py to sys.path to ensure we can import google_drive_sync
        sys.path.append(str(Path(__file__).resolve().parent))
        import google_drive_sync
        drive_urls = google_drive_sync.sync_release_assets(serial, project_path, local_files)
    except Exception as e:
        print(f"[!] Warning: Exception during Google Drive sync setup/run: {e}")
        
    # Map final URLs (Google Drive link if sync worked, otherwise fallback to local filename)
    media_urls = {}
    for key, local_path in local_files.items():
        if not local_path:
            media_urls[key] = ""
            continue
        if key in drive_urls and drive_urls[key]:
            media_urls[key] = drive_urls[key]
        else:
            media_urls[key] = local_path.name
            
    if any(url.startswith("http") for url in media_urls.values()):
        print("[*] Referencing public Google Drive download URLs in CSV.")
    else:
        print("[*] Referencing local asset filenames as placeholders in CSV (upload to Google Drive manually).")

    # 7. Schedule Calculations
    date_post1 = release_date - datetime.timedelta(days=7)
    date_post2 = release_date - datetime.timedelta(days=3)
    date_post3 = release_date
    
    # 8. Define Default Headers
    template_path = Path(__file__).resolve().parent / "templates" / "metricool_template.csv"
    headers = [
        "Text", "Date", "Time", "Picture Url 1", 
        "YouTube Video Title", "YouTube Video Type", "YouTube Video Privacy", "YouTube Video Category", 
        "TikTok Post Privacy", "TikTok Disable Comments", "TikTok Disable Duet", "TikTok Disable Stitch",
        "Instagram", "Facebook", "TikTok", "Youtube"
    ]
    
    if template_path.exists():
        print(f"[+] Found custom Metricool template at: {template_path}")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line:
                    headers = [col.strip().strip('"') for col in first_line.split(",")]
        except Exception as e:
            print(f"[!] Warning: Could not parse template headers: {e}")
            
    csv_rows = []
    
    # Resolve and clean title string
    title_str = f"{manifest.get('artist', 'UNKNOWN')} - {release_title}"
    clean_title = title_str.replace("<", "").replace(">", "").strip()
    if len(clean_title) > 80:
        clean_title = clean_title[:80]

    # Post 1 (Teaser 1 - Youtube Shorts + Socials)
    if posts_copy["Post1"]:
        row = populate_row(headers, posts_copy["Post1"], date_post1, "18:00", media_urls.get("teaser1", ""), True, True, True, True, f"{clean_title} (Teaser 1)", "SHORT")
        csv_rows.append(row)
        
    # Post 2 (Teaser 2 - Youtube Shorts + Socials - Title Track)
    if posts_copy["Post2"]:
        row = populate_row(headers, posts_copy["Post2"], date_post2, "18:00", media_urls.get("teaser2", ""), True, True, True, True, f"{clean_title} (Teaser 2)", "SHORT")
        csv_rows.append(row)
        
    # Post 3 (Release Day Socials - Cover Art Image)
    if posts_copy["Post3"]:
        row = populate_row(headers, posts_copy["Post3"], date_post3, "12:00", media_urls.get("cover", ""), True, True, False, False, "")
        csv_rows.append(row)
 
    # Post 4 (Release Day YouTube Full Video)
    if posts_copy["Post3"] and media_urls.get("dtv"):
        row = populate_row(headers, posts_copy["Post3"], date_post3, "12:00", media_urls.get("dtv", ""), False, False, False, True, f"{clean_title} (Official Audio)", "VIDEO")
        csv_rows.append(row)

    # 9. Output CSV Generation
    output_csv_path = social_dir / "metricool_schedule.csv"
    
    import csv
    try:
        with open(output_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for r in csv_rows:
                writer.writerow(r)
        print(f"\n[SUCCESS] Metricool scheduling sheet created at:")
        print(f"  {output_csv_path}")
        print("\n[*] TO SCHEDULE POSTS FOR FREE:")
        print("  1. Log in to https://app.metricool.com/")
        print("  2. Open the Calendar / Planning section.")
        print("  3. Click 'Import CSV' and select this file.")
        print("  4. Teaser clips will be scheduled for Shorts, and full videos for YouTube!")
        return True
    except Exception as e:
        print(f"[!] ERROR: Failed to write CSV file: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="DEFMAIN: Metricool Bulk Schedule Creator")
    parser.add_argument("serial", help="Release serial (e.g. SRC56)")
    args = parser.parse_args()
    build_metricool_schedule(args.serial)

if __name__ == "__main__":
    main()
