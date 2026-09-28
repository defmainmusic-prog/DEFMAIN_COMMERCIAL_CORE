#!/usr/bin/env python3
import os
import sys
import json
import argparse
from pathlib import Path
import urllib.request
import urllib.error
import ssl
import uuid
from PIL import Image

from config import resolve_release_path

def load_env_manually():
    """Fallback to load .env file manually if python-dotenv is not installed."""
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    os.environ[key] = val

# Try loading env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    load_env_manually()

def upload_to_gdrive(file_path, artist, title, serial_code):
    """Uploads a local image to Google Drive, shares it publicly, and returns a direct web content link."""
    try:
        import sys
        from pathlib import Path
        current_dir = Path(__file__).resolve().parent
        if str(current_dir) not in sys.path:
            sys.path.append(str(current_dir))
            
        from google_drive_sync import get_drive_service, get_or_create_subfolder, upload_file_and_share
        
        service = get_drive_service()
        if not service:
            print("[!] Google Drive service failed to initialize for image upload.")
            return None
            
        parent_folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        if not parent_folder_id:
            print("[!] GOOGLE_DRIVE_FOLDER_ID not found in environment.")
            return None
            
        # Resolve label-specific parent folder
        if serial_code.upper().startswith("SRC"):
            label_dir_name = "SRC Records"
        elif serial_code.upper().startswith("NSS"):
            label_dir_name = "Neural State Sound"
        else:
            label_dir_name = "Other Releases"
        label_folder_id = get_or_create_subfolder(service, label_dir_name, parent_folder_id)
        
        # Resolve main release folder
        main_folder_name = f"{artist} - {title} - {serial_code.upper()}"
        main_folder_id = get_or_create_subfolder(service, main_folder_name, label_folder_id)
        
        # Resolve Media Pack & Artwork folder
        media_pack_drive_id = get_or_create_subfolder(service, "Media Pack", main_folder_id)
        artwork_drive_id = get_or_create_subfolder(service, "Artwork", media_pack_drive_id)
        
        # Upload and share
        gdrive_url = upload_file_and_share(service, file_path, artwork_drive_id)
        if gdrive_url and "/d/" in gdrive_url:
            file_id = gdrive_url.split("/d/")[1].split("/")[0]
            # Standard Google Drive direct image content link
            direct_url = f"https://lh3.googleusercontent.com/d/{file_id}"
            return direct_url
        return None
    except Exception as e:
        print(f"[!] ERROR: Failed to upload image to Google Drive: {e}")
        return None

def generate_notion_banner(project_path, serial_code):
    """Crops the top portion of the release cover art to generate a custom Notion banner."""
    cover_path = project_path / "02_Artwork" / f"{serial_code}_CoverArt.png"
    if not cover_path.exists():
        cover_path = project_path / "02_Artwork" / f"{serial_code}_CoverArt_V1.png"
        
    banner_path = project_path / "02_Artwork" / f"{serial_code}_Notion_Banner.png"
    
    if not cover_path.exists():
        print(f"[!] Warning: Cover art does not exist at {cover_path} to crop a banner.")
        return None
        
    try:
        print(f"[+] Cropping top portion of cover art for Notion banner...")
        with Image.open(cover_path) as img:
            width, height = img.size
            # Notion banner standard aspect ratio is roughly 3:1 (e.g. 1500 x 500)
            # Crop centered vertically to capture the heart of the coverart visual
            crop_height = int(width * 0.33)
            
            y_start = (height - crop_height) // 2
            y_end = y_start + crop_height
            if y_end > height:
                y_end = height
                y_start = max(0, y_end - crop_height)
                
            banner_img = img.crop((0, y_start, width, y_end))
            banner_img.save(banner_path, "PNG")
            print(f"[+] Saved cropped banner locally at: {banner_path}")
            return banner_path
    except Exception as e:
        print(f"[!] Warning: Failed to crop cover art: {e}")
        return None

def push_to_notion(serial):
    # 1. Check credentials
    token = os.environ.get("NOTION_TOKEN")
    db_id = os.environ.get("NOTION_DATABASE_ID")
    page_id = os.environ.get("NOTION_PAGE_ID")
    upload_artwork = os.environ.get("NOTION_UPLOAD_ARTWORK", "false").lower() in ("true", "1", "yes")

    if not token:
        print("\n[!] NOTION INTEGRATION NOT CONFIGURATED: Missing 'NOTION_TOKEN' in .env.")
        print("To enable Notion synchronization, please add the following to your .env:")
        print("  NOTION_TOKEN=\"secret_...\"")
        print("  NOTION_DATABASE_ID=\"...\" OR NOTION_PAGE_ID=\"...\"")
        return True # Exit gracefully so pipeline isn't blocked

    if not db_id and not page_id:
        print("\n[!] NOTION INTEGRATION NOT CONFIGURATED: Missing 'NOTION_DATABASE_ID' or 'NOTION_PAGE_ID' in .env.")
        print("Please configure a target parent in .env to enable synchronization.")
        return True

    # 2. Locate project and load manifest
    project_path = resolve_release_path(serial)
    if not project_path:
        print(f"[!] ERROR: Could not locate release directory for serial: {serial}")
        return False

    manifest_path = project_path / "release_manifest.json"
    if not manifest_path.exists():
        print(f"[!] ERROR: release_manifest.json not found at: {manifest_path}")
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 3. Read EPK content
    epk_text = ""
    epk_txt_path = project_path / "EPK" / "EPK.txt"
    desc_txt_path = project_path / "EPK" / "description.txt"

    if epk_txt_path.exists():
        with open(epk_txt_path, "r", encoding="utf-8") as f:
            epk_text = f.read().strip()
    elif desc_txt_path.exists():
        with open(desc_txt_path, "r", encoding="utf-8") as f:
            epk_text = f.read().strip()
    else:
        epk_text = manifest.get("ai_generated_copy", "").strip()

    # 4. Read Bio Content if available
    bio_paragraphs = []
    bio_dir = project_path / "EPK" / "Bio"
    if bio_dir.exists():
        txt_files = list(bio_dir.glob("*.txt"))
        if txt_files:
            try:
                with open(txt_files[0], "r", encoding="utf-8") as f:
                    bio_content = f.read().strip()
                if bio_content:
                    bio_paragraphs = [p.strip() for p in bio_content.split("\n") if p.strip()]
            except Exception as e:
                print(f"[!] Warning: Failed to read bio text file: {e}")

    # 5. Prepare metadata details
    artist = manifest.get("artist", "UNKNOWN_NODE")
    title = manifest.get("title", "UNTITLED_RESOURCE")
    label = manifest.get("label", "DEFMAIN_PLATFORM")
    rel_date = manifest.get("release_date", "TBC")
    serial_code = manifest.get("serial", serial).upper()

    page_title = f"Press Release - {artist} - {title}"

    # 6. Check & Upload Images (Cover Art and Bio Artist Photo)
    cover_art_url = None
    artist_image_url = None
    
    if upload_artwork:
        # Cover art
        cover_path = project_path / "02_Artwork" / f"{serial_code}_CoverArt.png"
        if not cover_path.exists():
            cover_path = project_path / "02_Artwork" / f"{serial_code}_CoverArt_V1.png"
        if cover_path.exists():
            print(f"[+] Found cover art file at: {cover_path}")
            try:
                cover_art_url = upload_to_gdrive(str(cover_path), artist, title, serial_code)
                print(f"[+] Successfully uploaded cover art to Google Drive: {cover_art_url}")
            except Exception as e:
                print(f"[!] Warning: Cover art upload failed: {e}")
        
        # Artist photo in Bio directory
        if bio_dir.exists():
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"):
                img_files = list(bio_dir.glob(ext))
                if img_files:
                    artist_img_path = img_files[0]
                    print(f"[+] Found artist photo at: {artist_img_path}")
                    try:
                        artist_image_url = upload_to_gdrive(str(artist_img_path), artist, title, serial_code)
                        print(f"[+] Successfully uploaded artist photo to Google Drive: {artist_image_url}")
                    except Exception as e:
                        print(f"[!] Warning: Artist photo upload failed: {e}")
                    break

    # 7. Format Notion request payload
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    # Reconstruct the reference layout
    children = []

    # A. Heading 2: FOR IMMEDIATE RELEASE (orange_background)
    children.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [
                {
                    "type": "text",
                    "text": { "content": "FOR IMMEDIATE RELEASE" },
                    "annotations": { "bold": True }
                }
            ],
            "color": "gray_background"
        }
    })

    # B. Divider
    children.append({
        "object": "block",
        "type": "divider",
        "divider": {}
    })

    # C. Paragraph: Metadata
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                { "type": "text", "text": { "content": "Artist: " } },
                { "type": "text", "text": { "content": f"{artist}\n" }, "annotations": { "bold": True } },
                { "type": "text", "text": { "content": "Title: " } },
                { "type": "text", "text": { "content": f"{title}\n" }, "annotations": { "bold": True } },
                { "type": "text", "text": { "content": "Label: " } },
                { "type": "text", "text": { "content": f"{label}\n" }, "annotations": { "bold": True } },
                { "type": "text", "text": { "content": "Catalog Number: " } },
                { "type": "text", "text": { "content": f"{serial_code}" }, "annotations": { "bold": True } }
            ]
        }
    })

    # D. Paragraph: Global Release
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                { "type": "text", "text": { "content": "Global Release: " } },
                { "type": "text", "text": { "content": f"{rel_date}" }, "annotations": { "bold": True } }
            ]
        }
    })

    # E. Divider
    children.append({
        "object": "block",
        "type": "divider",
        "divider": {}
    })

    # F. Blank spacing paragraph
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": { "rich_text": [] }
    })

    # G. EPK text paragraphs
    if epk_text:
        paragraphs = [p.strip() for p in epk_text.split('\n') if p.strip()]
        for para in paragraphs:
            chunks = [para[i:i+2000] for i in range(0, len(para), 2000)]
            for chunk in chunks:
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": { "content": chunk }
                            }
                        ]
                    }
                })

    # H. Divider + Cover Art image block (if uploaded)
    if cover_art_url:
        children.append({
            "object": "block",
            "type": "divider",
            "divider": {}
        })
        children.append({
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": { "url": cover_art_url }
            }
        })

    # SoundCloud Playlist Placeholder Section (with divider)
    children.append({
        "object": "block",
        "type": "divider",
        "divider": {}
    })
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": "[PASTE SOUNDCLOUD PLAYLIST EMBED OR LINK HERE]"
                    },
                    "annotations": {
                        "italic": True,
                        "color": "gray"
                    }
                }
            ]
        }
    })

    # I. Artist Bio Section (if bio paragraphs are loaded)
    if bio_paragraphs:
        children.append({
            "object": "block",
            "type": "divider",
            "divider": {}
        })
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": { "content": f"{artist} Bio" }
                    }
                ],
                "color": "orange"
            }
        })
        for para in bio_paragraphs:
            chunks = [para[i:i+2000] for i in range(0, len(para), 2000)]
            for chunk in chunks:
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": { "content": chunk }
                            }
                        ]
                    }
                })
        
        # Artist photo inside Bio section
        if artist_image_url:
            children.append({
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": { "url": artist_image_url }
                }
            })

    # J. Connect section header
    children.append({
        "object": "block",
        "type": "divider",
        "divider": {}
    })
    children.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [
                {
                    "type": "text",
                    "text": { "content": "Connect" }
                }
            ],
            "color": "gray_background"
        }
    })

    # K. Column list content definition
    label_instagram = "https://www.instagram.com/defmainmusic/"
    label_soundcloud = "https://soundcloud.com/defmainmusic"
    
    if "src" in label.lower():
        label_instagram = "https://www.instagram.com/src_record_label/"
    elif "neural" in label.lower() or "nss" in label.lower():
        label_instagram = "https://www.instagram.com/neuralstatesound/"

    artist_slug = artist.lower().replace(" ", "").replace("_", "").replace("-", "")
    
    artist_instagram = manifest.get("artist_instagram")
    if not artist_instagram or artist_instagram == "placeholder":
        artist_instagram = f"https://www.instagram.com/{artist_slug}/"
        
    artist_soundcloud = manifest.get("artist_soundcloud")
    if not artist_soundcloud or artist_soundcloud == "placeholder":
        artist_soundcloud = f"https://soundcloud.com/{artist_slug}"
        
    artist_facebook = manifest.get("artist_facebook")
    
    # Define Column 2 (Artist socials) contents dynamically
    col2_children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": { "content": "Artist" },
                        "annotations": { "bold": True }
                    }
                ],
                "color": "gray_background"
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"{artist} Instagram",
                            "link": { "url": artist_instagram }
                        }
                    }
                ]
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"{artist} Soundcloud",
                            "link": { "url": artist_soundcloud }
                        }
                    }
                ]
            }
        }
    ]
    
    if artist_facebook and artist_facebook != "skipped" and artist_facebook != "placeholder":
        col2_children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"{artist} Facebook",
                            "link": { "url": artist_facebook }
                        }
                    }
                ]
            }
        })
    
    # K2. Define the Connect columns with children inside the type-specific arrays
    children.append({
        "object": "block",
        "type": "column_list",
        "column_list": {
            "children": [
                # Column 1: Label Info
                {
                    "object": "block",
                    "type": "column",
                    "column": {
                        "children": [
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [
                                        {
                                            "type": "text",
                                            "text": { "content": "Label " },
                                            "annotations": { "bold": True }
                                        }
                                    ],
                                    "color": "gray_background"
                                }
                            },
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [
                                        {
                                            "type": "text",
                                            "text": {
                                                "content": f"{label} Instagram",
                                                "link": { "url": label_instagram }
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                },
                # Column 2: Artist Info
                {
                    "object": "block",
                    "type": "column",
                    "column": {
                        "children": col2_children
                    }
                },
                # Column 3: Platform Info
                {
                    "object": "block",
                    "type": "column",
                    "column": {
                        "children": [
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [
                                        {
                                            "type": "text",
                                            "text": { "content": "Platform" },
                                            "annotations": { "bold": True }
                                        }
                                    ],
                                    "color": "gray_background"
                                }
                            },
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [
                                        {
                                            "type": "text",
                                            "text": {
                                                "content": "Defmain Platform Instagram",
                                                "link": { "url": "https://www.instagram.com/defmainmusic/" }
                                            }
                                        }
                                    ]
                                }
                            },
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [
                                        {
                                            "type": "text",
                                            "text": {
                                                "content": "Defmain Platform Soundcloud ",
                                                "link": { "url": "https://soundcloud.com/defmainmusic" }
                                            }
                                        }
                                    ]
                                }
                            },
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [
                                        {
                                            "type": "text",
                                            "text": {
                                                "content": "Links / Website",
                                                "link": { "url": "https://beacons.ai/defmainmusic" }
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    })

    # L. Trailing spacing paragraph
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": { "rich_text": [] }
    })

    # Parent definitions
    if db_id:
        parent = { "database_id": db_id }
        properties = {
            "Name": {
                "title": [
                    { "text": { "content": page_title } }
                ]
            }
        }
    else:
        parent = { "page_id": page_id }
        properties = {
            "title": [
                { "text": { "content": page_title } }
            ]
        }

    # Resolve Page Cover & Icon (SRC / NSS labels)
    cover_url = os.environ.get("NOTION_COVER_URL")
    if not cover_url:
        banner_local_path = generate_notion_banner(project_path, serial_code)
        if banner_local_path and upload_artwork:
            try:
                cover_url = upload_to_gdrive(str(banner_local_path), artist, title, serial_code)
                print(f"[+] Successfully uploaded custom cover banner to Google Drive: {cover_url}")
            except Exception as e:
                print(f"[!] Warning: Failed to upload custom banner: {e}")
        
        # Fallback if generation or upload failed
        if not cover_url:
            cover_url = "https://files.catbox.moe/gtsrbk.jpg"
    
    icon_url = os.environ.get("NOTION_ICON_URL")
    if not icon_url:
        if "src" in label.lower():
            icon_url = "https://files.catbox.moe/d49srf.png"
        elif "neural" in label.lower() or "nss" in label.lower():
            icon_url = "📡"
        else:
            icon_url = "https://files.catbox.moe/d49srf.png"
            
    cover_definition = {
        "type": "external",
        "external": {
            "url": cover_url
        }
    }
    
    if icon_url.startswith("http"):
        icon_definition = {
            "type": "external",
            "external": {
                "url": icon_url
            }
        }
    else:
        icon_definition = {
            "type": "emoji",
            "emoji": icon_url
        }

    payload = {
        "parent": parent,
        "properties": properties,
        "cover": cover_definition,
        "icon": icon_definition,
        "children": children
    }

    # 9. Execute API Request to create page
    print(f"\n[+] PUBLISHING EPK TO NOTION FOR {serial_code}...")

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            notion_url = res_data.get("url")
            print(f"[SUCCESS] Notion page created successfully!")
            print(f"[URL] {notion_url}")

            # 10. Update manifest with notion details
            manifest["notion_page_url"] = notion_url
            manifest["notion_sync_status"] = "synced"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=4)
            print("[SYSTEM] Manifest synchronized with Notion page URL.")
            return True
            
    except urllib.error.HTTPError as e:
        error_resp = e.read().decode("utf-8")
        print(f"\n[!] Notion API HTTP Error {e.code}: {e.reason}")
        try:
            err_json = json.loads(error_resp)
            print(f"Details: {err_json.get('message', 'No details available')}")
        except Exception:
            print(f"Response: {error_resp}")
        return False
    except Exception as e:
        print(f"\n[!] Encountered exception when contacting Notion API: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="DEFMAIN: Notion EPK Publisher")
    parser.add_argument("serial", help="Release serial (e.g. SRC56)")
    args = parser.parse_args()

    success = push_to_notion(args.serial)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
