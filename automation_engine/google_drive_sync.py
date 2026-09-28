#!/usr/bin/env python3
import os
import json
import hashlib
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import resolve_release_path, GOOGLE_CREDS_PATH

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_local_md5(file_path):
    """Calculates the MD5 checksum of a local file."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"[!] Warning: Failed to calculate MD5 for {file_path}: {e}")
        return None

def load_env_manually():
    """Loads environment variables from .env file in parent directory."""
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

# Try loading env variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    load_env_manually()

def should_skip_sync(serial, project_path):
    """
    Evaluates whether this release should be excluded from Google Drive syncing.
    Excludes test serials (e.g. contains 'TEST'), serials blacklisted in .env,
    or releases marked with 'skip_drive_sync': true in their manifest.
    """
    clean_serial = serial.upper().replace("_", "").replace("-", "").strip()
    
    # 1. Check for "TEST" in serial name
    if "TEST" in clean_serial:
        print(f"[*] Skipping Google Drive sync: Serial '{serial}' identified as a test project.")
        return True
        
    # 2. Check blacklist in .env
    blacklist_str = os.environ.get("DRIVE_SYNC_SKIP_SERIALS", "")
    if blacklist_str:
        blacklist = [s.strip().upper() for s in blacklist_str.split(",") if s.strip()]
        if clean_serial in blacklist:
            print(f"[*] Skipping Google Drive sync: Serial '{serial}' is blacklisted in DRIVE_SYNC_SKIP_SERIALS.")
            return True
            
    # 3. Check release_manifest.json for skip flag
    if project_path:
        manifest_path = Path(project_path) / "release_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                if manifest.get("skip_drive_sync") is True:
                    print(f"[*] Skipping Google Drive sync: 'skip_drive_sync' set to true in release manifest.")
                    return True
            except Exception as e:
                print(f"[!] Warning: Could not parse manifest to check skip flag: {e}")
                
    return False

def get_drive_service():
    """Initializes and returns the Google Drive API client using OAuth 2.0 User credentials."""
    creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_path:
        creds_path = str(GOOGLE_CREDS_PATH)
        
    creds_file = Path(creds_path)
    if not creds_file.exists():
        print(f"[*] Google Drive sync: OAuth credentials file not found at: {creds_path}")
        return None
        
    token_path = creds_file.parent / "token.json"
    creds = None
    
    # The file token.json stores the user's access and refresh tokens
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception as e:
            print(f"[!] Warning: Failed to load token.json: {e}")
            
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as ref_err:
                    print(f"[*] Refresh token invalid/revoked ({ref_err}). Re-authenticating...")
                    creds = None

            if not creds or not creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
                print("\n[Google Drive] A browser window will open now to authenticate your Google Account...")
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(token_path, "w") as token:
                token.write(creds.to_json())
            print(f"[+] Saved authorization token to: {token_path}")
        except Exception as e:
            print(f"[!] ERROR: Failed to authenticate Google Drive: {e}")
            return None
            
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"[!] ERROR: Failed to build Google Drive client: {e}")
        return None

def get_or_create_subfolder(service, folder_name, parent_id):
    """Checks if a subfolder exists inside the parent folder, creating it if it doesn't."""
    try:
        # Search for folder
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed = false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        
        if files:
            return files[0]['id']
            
        # Create folder if it doesn't exist
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = folder.get('id')
        print(f"[+] Created Google Drive release subfolder '{folder_name}' (ID: {folder_id})")
        return folder_id
    except Exception as e:
        print(f"[!] ERROR: Failed to lookup or create subfolder '{folder_name}': {e}")
        raise e

def upload_file_and_share(service, local_file_path, parent_folder_id):
    """
    Uploads a local file to a specified Google Drive folder, shares it publicly,
    and returns its direct download link. Reuses existing file if already uploaded.
    """
    path = Path(local_file_path)
    if not path.exists():
        print(f"[!] Warning: Local file '{local_file_path}' not found. Cannot sync to Google Drive.")
        return None
        
    filename = path.name
    
    try:
        # 1. Check if file already exists in the destination folder
        query = f"name = '{filename}' and '{parent_folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name, mimeType, md5Checksum)').execute()
        files = results.get('files', [])
        
        if files:
            file_id = files[0]['id']
            remote_md5 = files[0].get('md5Checksum')
            local_md5 = get_local_md5(path)
            
            if remote_md5 and local_md5 and remote_md5.lower() == local_md5.lower():
                print(f"[*] File '{filename}' is up to date on Google Drive (ID: {file_id}). Skipping upload.")
            else:
                print(f"[*] File '{filename}' has changed locally. Updating on Google Drive...")
                media = MediaFileUpload(str(path), resumable=True)
                service.files().update(fileId=file_id, media_body=media).execute()
                print(f"[+] Updated '{filename}' on Google Drive (ID: {file_id})")
        else:
            # 2. Upload file
            file_metadata = {
                'name': filename,
                'parents': [parent_folder_id]
            }
            media = MediaFileUpload(str(path), resumable=True)
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            file_id = file.get('id')
            print(f"[+] Uploaded '{filename}' to Google Drive (ID: {file_id})")
            
        # 3. Share the file (grant public Viewer access, which Metricool requires)
        # Check permissions to avoid redundant permission creation calls
        perm_results = service.permissions().list(fileId=file_id, fields='permissions(id, role, type)').execute()
        has_public_reader = False
        for perm in perm_results.get('permissions', []):
            if perm.get('type') == 'anyone' and perm.get('role') == 'reader':
                has_public_reader = True
                break
                
        if not has_public_reader:
            user_permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            service.permissions().create(fileId=file_id, body=user_permission).execute()
            print(f"  [+] Set public Viewer permission (anyone with link can view) specifically for '{filename}'")
        else:
            print(f"  [*] Public Viewer permission already configured for '{filename}'")
            
        # 4. Return Metricool-compatible Google Drive link
        return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        
    except Exception as e:
        print(f"[!] ERROR: Failed to upload or share file '{filename}': {e}")
        return None

def sync_release_assets(serial, project_path, local_files):
    """
    Main entrypoint: syncs a dict of local files for a release to Google Drive.
    Returns a dict mapping the asset keys to their Google Drive direct download URLs.
    """
    # 1. Skip sync check
    if should_skip_sync(serial, project_path):
        return {}
        
    # 2. Initialize service
    service = get_drive_service()
    if not service:
        return {}
        
    # 3. Retrieve parent folder ID
    parent_folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if not parent_folder_id:
        print("[*] Google Drive sync: GOOGLE_DRIVE_FOLDER_ID not defined in .env.")
        return {}
        
    print(f"\n[*] Initiating Google Drive asset synchronization for release {serial}...")
    
    try:
        # Resolve label-specific parent folder on Drive (inside Defmain_Sync)
        if serial.upper().startswith("SRC"):
            label_dir_name = "SRC Records"
        elif serial.upper().startswith("NSS"):
            label_dir_name = "Neural State Sound"
        else:
            label_dir_name = "Other Releases"
        label_folder_id = get_or_create_subfolder(service, label_dir_name, parent_folder_id)
        
        # 4. Resolve release-specific subfolder on Drive inside the label folder
        release_folder_id = get_or_create_subfolder(service, serial.upper(), label_folder_id)
        
        # 5. Upload files and collect links
        remote_urls = {}
        for key, filepath in local_files.items():
            if not filepath:
                continue
            
            print(f"  - Syncing '{key}' from path: {filepath}")
            download_url = upload_file_and_share(service, filepath, release_folder_id)
            if download_url:
                remote_urls[key] = download_url
                
        print(f"[SUCCESS] Google Drive sync completed for {serial}.\n")
        return remote_urls
    except Exception as e:
        print(f"[!] ERROR: Google Drive sync aborted due to exception: {e}")
        return {}


def upload_file_private(service, local_file_path, parent_folder_id):
    """Uploads a local file to Google Drive and keeps it private (no public link sharing)."""
    path = Path(local_file_path)
    if not path.exists():
        print(f"[!] Warning: Local file '{local_file_path}' not found. Skipping.")
        return None
        
    filename = path.name
    
    try:
        # Check if file already exists in the destination folder
        query = f"name = '{filename}' and '{parent_folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name, md5Checksum)').execute()
        files = results.get('files', [])
        
        if files:
            file_id = files[0]['id']
            remote_md5 = files[0].get('md5Checksum')
            local_md5 = get_local_md5(path)
            
            if remote_md5 and local_md5 and remote_md5.lower() == local_md5.lower():
                print(f"[*] File '{filename}' is up to date on Google Drive (ID: {file_id}). Skipping.")
                return file_id
            else:
                print(f"[*] File '{filename}' has changed locally. Updating on Google Drive...")
                media = MediaFileUpload(str(path), resumable=True)
                service.files().update(fileId=file_id, media_body=media).execute()
                print(f"[+] Updated '{filename}' on Google Drive (ID: {file_id})")
                return file_id
            
        # Upload file
        file_metadata = {
            'name': filename,
            'parents': [parent_folder_id]
        }
        media = MediaFileUpload(str(path), resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = file.get('id')
        print(f"[+] Uploaded '{filename}' to Google Drive (ID: {file_id})")
        return file_id
    except Exception as e:
        print(f"[!] ERROR: Failed to upload file '{filename}': {e}")
        return None


def cleanup_remote_folder(service, drive_folder_id, allowed_names):
    """Trashes any files in the Drive folder that are not in the allowed_names list."""
    try:
        query = f"'{drive_folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        for file in files:
            name = file['name']
            file_id = file['id']
            if name not in allowed_names:
                print(f"[*] Cleaning up old file '{name}' from Google Drive (moving to trash)...")
                service.files().update(fileId=file_id, body={'trashed': True}).execute()
    except Exception as e:
        print(f"[!] Warning: Failed to clean up remote folder {drive_folder_id}: {e}")


def generate_posting_schedule_text(project_path, release_date_str):
    """Generates a text file detailing the social media posting schedule for the artist."""
    import datetime
    path = Path(project_path)
    social_dir = path / "03_Social"
    
    # Schedule Calculations
    try:
        release_date = datetime.datetime.strptime(release_date_str, "%Y-%m-%d").date()
    except Exception:
        # Fallback if date is not parsed
        release_date = datetime.date.today()
        
    date_post1 = release_date - datetime.timedelta(days=7)
    date_post2 = release_date - datetime.timedelta(days=3)
    date_post3 = release_date
    
    post_files = {
        "Post 1 (Teaser 1 - 7 Days Before Release)": (social_dir / "Post1.txt", date_post1, "18:00"),
        "Post 2 (Teaser 2 - 3 Days Before Release)": (social_dir / "Post2.txt", date_post2, "18:00"),
        "Post 3 (Release Day Announcement)": (social_dir / "Post3.txt", date_post3, "12:00")
    }
    
    schedule_content = "DEFMAIN PLATFORM: RELEASE POSTING SCHEDULE\n"
    schedule_content += "=" * 50 + "\n\n"
    
    for label, (file_path, post_date, post_time) in post_files.items():
        schedule_content += f"{label}\n"
        schedule_content += f"Scheduled Date/Time: {post_date} {post_time}\n"
        
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
            except Exception as e:
                text = f"[Error reading file: {e}]"
        else:
            text = "[No caption copy generated]"
            
        schedule_content += "Caption Copy:\n"
        schedule_content += "-" * 40 + "\n"
        schedule_content += f"{text}\n"
        schedule_content += "-" * 40 + "\n\n"
        
    output_path = social_dir / "posting_schedule.txt"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(schedule_content)
        print(f"[+] Generated local posting schedule file at: {output_path.name}")
        return output_path
    except Exception as e:
        print(f"[!] Warning: Failed to write posting schedule text file: {e}")
        return None


def sync_full_artist_package(serial, project_path):
    """
    Synchronizes the full release folder structure to Google Drive for artist review.
    Folders: Masters, Artwork, Social (including posting_schedule.txt), Legal, EPK, Artwork_Assets.
    Returns the URL of the main release folder on Google Drive.
    """
    # 1. Skip check
    if should_skip_sync(serial, project_path):
        return None
        
    # 2. Initialize service
    service = get_drive_service()
    if not service:
        return None
        
    # 3. Retrieve parent folder ID
    parent_folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if not parent_folder_id:
        print("[*] Google Drive sync: GOOGLE_DRIVE_FOLDER_ID not defined in .env.")
        return None
        
    # 4. Resolve release metadata from manifest
    path = Path(project_path)
    manifest_path = path / "release_manifest.json"
    if not manifest_path.exists():
        print(f"[!] ERROR: release_manifest.json missing at {manifest_path}")
        return None
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    artist = manifest.get("artist", "UNKNOWN_ARTIST")
    title = manifest.get("title", "UNTITLED_RELEASE")
    release_date_str = manifest.get("release_date", "")
    
    # Folder name: [Artist Name] - [Release Title] - [Serial]
    main_folder_name = f"{artist} - {title} - {serial.upper()}"
    print(f"\n[*] Initiating full Google Drive sync for artist package: '{main_folder_name}'...")
    
    try:
        # Resolve label-specific parent folder on Drive (inside Defmain_Sync)
        if serial.upper().startswith("SRC"):
            label_dir_name = "SRC Records"
        elif serial.upper().startswith("NSS"):
            label_dir_name = "Neural State Sound"
        else:
            label_dir_name = "Other Releases"
        label_folder_id = get_or_create_subfolder(service, label_dir_name, parent_folder_id)

        # 5. Create main folder inside the label folder
        main_folder_id = get_or_create_subfolder(service, main_folder_name, label_folder_id)
        
        # 6. Synchronize Masters/
        masters_local_dir = path / "01_Masters"
        if masters_local_dir.exists():
            masters_drive_id = get_or_create_subfolder(service, "Masters", main_folder_id)
            extensions = ("*.wav", "*.aif", "*.aiff", "*.flac")
            allowed_masters = []
            for ext in extensions:
                for f in masters_local_dir.glob(ext):
                    upload_file_private(service, f, masters_drive_id)
                    allowed_masters.append(f.name)
                for f in masters_local_dir.glob(ext.upper()):
                    upload_file_private(service, f, masters_drive_id)
                    allowed_masters.append(f.name)
            # Cleanup remote files not matching local
            cleanup_remote_folder(service, masters_drive_id, allowed_masters)
                    
        # 6b. Resolve or create "Media Pack" subfolder (holds Artwork, Artwork_Assets, and MP3_320kbps)
        media_pack_drive_id = get_or_create_subfolder(service, "Media Pack", main_folder_id)

        # 7. Synchronize Artwork/ (Official cover art only - PNG and JPG) inside Media Pack
        artwork_local_dir = path / "02_Artwork"
        if artwork_local_dir.exists():
            artwork_drive_id = get_or_create_subfolder(service, "Artwork", media_pack_drive_id)
            allowed_artwork = []
            
            # Find the promoted CoverArt.png
            cover_art_file = artwork_local_dir / f"{serial.upper()}_CoverArt.png"
            if not cover_art_file.exists():
                # Fallback to CoverArt_V1
                cover_art_file = artwork_local_dir / f"{serial.upper()}_CoverArt_V1.png"
            if cover_art_file.exists():
                upload_file_private(service, cover_art_file, artwork_drive_id)
                allowed_artwork.append(cover_art_file.name)
            
            # Sync high-res JPG CoverArt if it exists
            cover_art_jpg = artwork_local_dir / f"{serial.upper()}_CoverArt.jpg"
            if cover_art_jpg.exists():
                upload_file_private(service, cover_art_jpg, artwork_drive_id)
                allowed_artwork.append(cover_art_jpg.name)
                
            cleanup_remote_folder(service, artwork_drive_id, allowed_artwork)
                
        # 7b. Create empty Artwork_Assets/ folder inside Media Pack
        get_or_create_subfolder(service, "Artwork_Assets", media_pack_drive_id)

        # 7c. Synchronize MP3_320kbps/ inside Media Pack (sync all including previews)
        epk_mp3_dir = path / "EPK" / "MP3_320kbps"
        if epk_mp3_dir.exists():
            mp3_drive_id = get_or_create_subfolder(service, "MP3_320kbps", media_pack_drive_id)
            allowed_mp3s = []
            for f in epk_mp3_dir.glob("*.mp3"):
                upload_file_private(service, f, mp3_drive_id)
                allowed_mp3s.append(f.name)
            cleanup_remote_folder(service, mp3_drive_id, allowed_mp3s)
                    
        # 8. Synchronize Social/
        social_local_dir = path / "03_Social"
        dtv_local_dir = path / "04_DTV"
        social_drive_id = get_or_create_subfolder(service, "Social", main_folder_id)
        
        allowed_social = []
        # Upload social mp4 files
        if social_local_dir.exists():
            for f in social_local_dir.glob("*.mp4"):
                upload_file_private(service, f, social_drive_id)
                allowed_social.append(f.name)
        if dtv_local_dir.exists():
            for f in dtv_local_dir.glob("*.mp4"):
                upload_file_private(service, f, social_drive_id)
                allowed_social.append(f.name)
                
        # Upload preview mp3 files
        if epk_mp3_dir.exists():
            for f in epk_mp3_dir.glob("*_Preview.mp3"):
                upload_file_private(service, f, social_drive_id)
                allowed_social.append(f.name)
                
        # Generate and upload posting_schedule.txt
        schedule_file = generate_posting_schedule_text(project_path, release_date_str)
        if schedule_file and schedule_file.exists():
            upload_file_private(service, schedule_file, social_drive_id)
            allowed_social.append(schedule_file.name)
            
        cleanup_remote_folder(service, social_drive_id, allowed_social)
            
        # 9. Synchronize Legal/
        legal_local_dir = path / "05_Legal"
        if legal_local_dir.exists():
            legal_drive_id = get_or_create_subfolder(service, "Legal", main_folder_id)
            allowed_legal = []
            for f in legal_local_dir.iterdir():
                if f.is_file() and not f.name.startswith("."):
                    upload_file_private(service, f, legal_drive_id)
                    allowed_legal.append(f.name)
            cleanup_remote_folder(service, legal_drive_id, allowed_legal)
                    
        # 10. Synchronize EPK/
        epk_local_dir = path / "EPK"
        if epk_local_dir.exists():
            epk_drive_id = get_or_create_subfolder(service, "EPK", main_folder_id)
            allowed_epk = []
            for f in epk_local_dir.iterdir():
                if f.is_file() and not f.name.startswith("."):
                    upload_file_private(service, f, epk_drive_id)
                    allowed_epk.append(f.name)
            cleanup_remote_folder(service, epk_drive_id, allowed_epk)
        
        # 11. Cleanup old legacy folders at the root level (Artwork and Artwork_Assets)
        try:
            query = f"(name = 'Artwork' or name = 'Artwork_Assets') and mimeType = 'application/vnd.google-apps.folder' and '{main_folder_id}' in parents and trashed = false"
            results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            old_folders = results.get('files', [])
            for folder in old_folders:
                folder_id = folder['id']
                print(f"[*] Cleaning up legacy root folder '{folder['name']}' (moving to trash)...")
                service.files().update(fileId=folder_id, body={'trashed': True}).execute()
        except Exception as cleanup_err:
            print(f"[!] Warning: Failed to clean up legacy folders: {cleanup_err}")
        
        # 12. Complete and return folder URL
        folder_url = f"https://drive.google.com/drive/folders/{main_folder_id}"
        print(f"[SUCCESS] Google Drive artist package sync completed.")
        print(f"  Folder Link: {folder_url}\n")
        
        # Save link to release_manifest.json
        manifest["artist_drive_folder_url"] = folder_url
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)
            
        return folder_url
    except Exception as e:
        print(f"[!] ERROR: Google Drive artist package sync failed: {e}")
        return None


def main():
    import sys
    import argparse
    parser = argparse.ArgumentParser(description="DEFMAIN: Artist Package Google Drive Synchronizer")
    parser.add_argument("serial", help="Release serial (e.g. SRC56)")
    args = parser.parse_args()
    
    project_path = resolve_release_path(args.serial)
    if not project_path:
        print(f"[!] ERROR: Could not locate release directory for serial: {args.serial}")
        sys.exit(1)
        
    sync_full_artist_package(args.serial, project_path)


if __name__ == "__main__":
    main()
