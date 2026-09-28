#!/usr/bin/env python3
import os
import json
import sys
import argparse
from pathlib import Path
import urllib.request
import urllib.error
import ssl

from config import resolve_release_path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

def generate_calendar_schedule(project_path, serial, artist, title, rel_date, post1_content, post2_content, post3_content):
    """Generates an .ics iCalendar schedule file in the release folder if the date is valid."""
    from datetime import datetime, timedelta
    import re
    
    # Try to parse YYYY-MM-DD
    date_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", rel_date.strip())
    if not date_match:
        print("[SYSTEM] Calendar Schedule: Skipped (release date is TBC or invalid format).")
        return
        
    try:
        yr, mo, dy = map(int, date_match.groups())
        release_dt = datetime(yr, mo, dy)
    except Exception as e:
        print(f"[SYSTEM] Calendar Schedule Error: Could not parse date {rel_date}: {e}")
        return
        
    # Schedule dates
    post1_dt = release_dt - timedelta(days=7) # Teaser 7 days before
    post2_dt = release_dt                      # Post 2 on Release Day
    post3_dt = release_dt + timedelta(days=3)  # Post 3 follow up 3 days after
    
    def format_ics_date(dt):
        return dt.strftime("%Y%m%d")
        
    def escape_ics_text(text):
        # Escape newlines and characters in ICS strings
        t = text.replace("\n", "\\n").replace("\r", "")
        t = t.replace(",", "\\,").replace(";", "\\;")
        return t

    ics_content = []
    ics_content.append("BEGIN:VCALENDAR")
    ics_content.append("VERSION:2.0")
    ics_content.append("PRODID:-//Defmain Platform//Release Scheduler//EN")
    ics_content.append("CALSCALE:GREGORIAN")
    ics_content.append("METHOD:PUBLISH")
    
    # Event 1: Release Day
    release_end = release_dt + timedelta(days=1)
    ics_content.append("BEGIN:VEVENT")
    ics_content.append(f"UID:UID_RELEASE_{serial}_{format_ics_date(release_dt)}@defmain.platform")
    ics_content.append(f"DTSTART;VALUE=DATE:{format_ics_date(release_dt)}")
    ics_content.append(f"DTEND;VALUE=DATE:{format_ics_date(release_end)}")
    ics_content.append(f"SUMMARY:RELEASE: {artist} - {title} ({serial})")
    ics_content.append(f"DESCRIPTION:Official release date for {artist} - {title} ({serial}).")
    ics_content.append("STATUS:CONFIRMED")
    ics_content.append("END:VEVENT")
    
    # Event 2: Post 1 (Teaser)
    post1_end = post1_dt + timedelta(days=1)
    ics_content.append("BEGIN:VEVENT")
    ics_content.append(f"UID:UID_POST1_{serial}_{format_ics_date(post1_dt)}@defmain.platform")
    ics_content.append(f"DTSTART;VALUE=DATE:{format_ics_date(post1_dt)}")
    ics_content.append(f"DTEND;VALUE=DATE:{format_ics_date(post1_end)}")
    ics_content.append(f"SUMMARY:SOCIAL: Post 1 (Teaser) - {serial}")
    ics_content.append(f"DESCRIPTION:Post 1 Copy Content:\\n\\n{escape_ics_text(post1_content)}")
    ics_content.append("STATUS:CONFIRMED")
    ics_content.append("END:VEVENT")
    
    # Event 3: Post 2 (Release Day)
    post2_end = post2_dt + timedelta(days=1)
    ics_content.append("BEGIN:VEVENT")
    ics_content.append(f"UID:UID_POST2_{serial}_{format_ics_date(post2_dt)}@defmain.platform")
    ics_content.append(f"DTSTART;VALUE=DATE:{format_ics_date(post2_dt)}")
    ics_content.append(f"DTEND;VALUE=DATE:{format_ics_date(post2_end)}")
    ics_content.append(f"SUMMARY:SOCIAL: Post 2 (Release Broadcast) - {serial}")
    ics_content.append(f"DESCRIPTION:Post 2 Copy Content:\\n\\n{escape_ics_text(post2_content)}")
    ics_content.append("STATUS:CONFIRMED")
    ics_content.append("END:VEVENT")
    
    # Event 4: Post 3 (Follow Up)
    post3_end = post3_dt + timedelta(days=1)
    ics_content.append("BEGIN:VEVENT")
    ics_content.append(f"UID:UID_POST3_{serial}_{format_ics_date(post3_dt)}@defmain.platform")
    ics_content.append(f"DTSTART;VALUE=DATE:{format_ics_date(post3_dt)}")
    ics_content.append(f"DTEND;VALUE=DATE:{format_ics_date(post3_end)}")
    ics_content.append(f"SUMMARY:SOCIAL: Post 3 (Broadcasting Follow Up) - {serial}")
    ics_content.append(f"DESCRIPTION:Post 3 Copy Content:\\n\\n{escape_ics_text(post3_content)}")
    ics_content.append("STATUS:CONFIRMED")
    ics_content.append("END:VEVENT")
    
    ics_content.append("END:VCALENDAR")
    
    output_path = project_path / "release_schedule.ics"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ics_content))
    print(f"[COMPILED] Calendar Schedule -> {output_path}")

def run_text_generation_pipeline():
    print("--- DEFMAIN: TEXT GENERATION & PROTOCOL ROUTING ENGINE ---")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[!] FATAL ERROR: GEMINI_API_KEY not found. Ensure your .env file sits in the root folder.")
        return

    parser = argparse.ArgumentParser(description="DEFMAIN Text Generation Pipeline")
    parser.add_argument("serial", nargs="?", default=None)
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--sonic-qualities", default=None)
    parsed_args, _ = parser.parse_known_args()

    serial_input = parsed_args.serial
    if not serial_input:
        serial_input = input("ENTER SERIAL (e.g., SRC55 or NSS01): ").strip().upper()
    else:
        serial_input = serial_input.strip().upper()

    project_path_str = resolve_release_path(serial_input)
    if not project_path_str:
        print(f"\n[!] ERROR: Could not locate initialization directory for {serial_input}")
        return

    project_path = Path(project_path_str)
    manifest_path = project_path / "release_manifest.json"
    if not manifest_path.exists():
        print(f"\n[!] ERROR: release_manifest.json not found at {manifest_path}")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    active_label = manifest.get("label", "DEFMAIN_PLATFORM").upper()
    serial = manifest.get("serial", serial_input).upper()
    artist = manifest.get("artist", "UNKNOWN_NODE").upper()
    title = manifest.get("title", "UNTITLED_RESOURCE").upper()
    rel_date = manifest.get("release_date", "TBC")
    mood_notes = manifest.get("mood_notes", "")
    
    if parsed_args.sonic_qualities:
        sonic_qualities = parsed_args.sonic_qualities
    else:
        default_sq = manifest.get("sonic_qualities") or manifest.get("mood_notes") or "Industrial synthesis, hardware density."
        sonic_qualities = input(f"ENTER SONIC QUALITIES / HARDWARE NODES [Default: '{default_sq}']: ").strip() or default_sq

    manifest["sonic_qualities"] = sonic_qualities
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)

    EPK_DIR = project_path / "EPK"
    SOCIAL_DIR = project_path / "03_Social"

    # CRITICAL SECURITY FIX: Remapped prompt context to completely exclude the Catalog ID parameter entirely
    prompt = (
        f"You are the System Architecture Logger & Music Journalist for the Defmain Platform.\n"
        f"Your task is to analyze raw track metadata and compile it into an uncompromised, tech-brutalist release entry.\n\n"
        f"[INPUT METADATA]\n"
        f"- Label Matrix: {active_label}\n"
        f"- Identity Node: {artist}\n"
        f"- Resource Title: {title}\n"
        f"- Core Atmosphere: {mood_notes}\n"
        f"- Sonic Qualities: {sonic_qualities}\n\n"
        f"[CRITICAL BANNED WORDS]\n"
        f"Do not use: imminent, out now, drop, link in bio, check it out, veteran, hype, ultimate, track, album, release.\n\n"
        f"[OUTPUT FORMAT REQUIREMENT]\n"
        f"You must return a valid, clean JSON object with exactly three keys: \"epk_description\", \"matrix_tags\", and \"sonic_telemetry\". Do not wrap the JSON block in markdown code fences.\n\n"
        f"[KEY 1: epk_description]\n"
        f"Write a professional EPK description for distribution portals and press networks.\n"
        f"- CRITICAL RESTRICTION 1: Do not mention or reference the release date ({rel_date}) anywhere within this text.\n"
        f"- CRITICAL RESTRICTION 2: Absolutely do not mention, invent, or output any Catalog ID, Serial Identification code, or text containing numbers resembling a catalog record anywhere within this text.\n"
        f"- Precise Target length: Between 140 and 150 words.\n"
        f"- Tone: Highly clinical, authoritative, sub-zero, dark industrial, minimalist. Focus on deep-frequency penetration, spatial architecture, and unyielding sonic geography.\n\n"
        f"[KEY 2: matrix_tags]\n"
        f"Extract exactly 3 core stylistic, textured, or spatial architectural keywords directly from your generated EPK description to populate the ARCHITECTURE fields.\n"
        f"- Format: A list of 3 uppercase strings using underscores for spaces (e.g., [\"DEEP-FREQUENCY\", \"SUB-ZERO_DUB\", \"INDUSTRIAL_RHYTHM\"]).\n\n"
        f"[KEY 3: sonic_telemetry]\n"
        f"Analyze the provided 'Sonic Qualities' and generate a 3-item uppercase diagnostic status breakdown tracking simulated parameters based on the music style for Protocol C.\n"
        f"- Format: A list of 3 strings mapping parameter names to heavy state descriptors (e.g., [\"DRIVE_COEFFICIENT: UNYIELDING\", \"TEXTURE_DAMPING: CRITICAL\", \"FREQUENCY_DENSITY: LOW_END_MAXIMA\"]).\n"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json"
        }
    }
    
    epk_txt = ""
    matrix_tags = []
    sonic_telemetry = []

    while True:
        print(f"\n[+] CONTACTING GEMINI VIA DIRECT HTTP MATRIX FOR {serial}...")
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                
            raw_model_output = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            data = json.loads(raw_model_output)
            
            epk_txt = data.get("epk_description", "")
            matrix_tags = data.get("matrix_tags", ["UNKNOWN_NODE", "RAW_GRID", "STATIC"])
            sonic_telemetry = data.get("sonic_telemetry", ["PARAMETER: SECURE", "STATE: UNKNOWN", "DENSITY: CRITICAL"])
            
        except urllib.error.HTTPError as e:
            print(f"[FATAL NETWORK ERROR] API rejected payload: {e.code} - {e.read().decode('utf-8')}")
            return
        except Exception as e:
            print(f"[FATAL ERROR] Processing or structural layout failed: {e}")
            return

        print("\n" + "="*60)
        print("--- GENERATED ARCHITECTURE MATRIX FOR REVIEW ---")
        print("="*60)
        print(f"[EPK TEXT]:\n{epk_txt}\n")
        print(f"[ARCHITECTURE TAGS]: {', '.join(matrix_tags)}")
        print(f"[SONIC TELEMETRY]: {', '.join(sonic_telemetry)}")
        print("="*60)

        if parsed_args.auto:
            print("\n[+] AUTO MODE ENABLED: Automatically accepting generated response.")
            break

        choice = input("\n[?] (A)ccept and commit to disk, or (R)edo text generation? ").strip().lower()
        if choice == 'a':
            break
        else:
            print("[+] Recalibrating vectors for reconstruction layout...")
            continue

    EPK_DIR.mkdir(parents=True, exist_ok=True)
    SOCIAL_DIR.mkdir(parents=True, exist_ok=True)

    resource_node = f"{artist} - {title}"

    # Protocol A -> EPK.txt
    path_a = EPK_DIR / "EPK.txt"
    with open(path_a, "w", encoding="utf-8") as f:
        f.write(epk_txt)
    print(f"\n[COMPILED] Protocol A -> {path_a}")

    # Protocol B -> Post1.txt
    path_b = SOCIAL_DIR / "Post1.txt"
    post1_content = f"{active_label}\nIDENTIFIER: = {serial}\nRESOURCE_NODE: {resource_node}\nSTATUS: INITIALIZED\nTIMECODE: {rel_date}"
    with open(path_b, "w", encoding="utf-8") as f:
        f.write(post1_content)
    print(f"[COMPILED] Protocol B -> {path_b}")

    # Protocol C -> Post2.txt
    path_c = SOCIAL_DIR / "Post2.txt"
    architecture_c = " // ".join(matrix_tags)
    telemetry_c = "\n\t".join(sonic_telemetry)
    post2_content = f"EXEC: BROADCAST_INJECTION\nSOURCE: {rel_date}\nARCHITECTURE: {architecture_c}\nACCESS: EXCLUSIVE\nDIAGNOSTICS:\n\t{telemetry_c}"
    with open(path_c, "w", encoding="utf-8") as f:
        f.write(post2_content)
    print(f"[COMPILED] Protocol C -> {path_c}")

    # Protocol D -> Post3.txt
    path_d = SOCIAL_DIR / "Post3.txt"
    post3_content = f"{active_label}\nIDENTIFIER: = {serial}\nRESOURCE_NODE: {resource_node}\nSTATUS: BROADCASTING\nARCHITECTURE: {architecture_c}\nACCESS: G A"
    with open(path_d, "w", encoding="utf-8") as f:
        f.write(post3_content)
    print(f"[COMPILED] Protocol D -> {path_d}")

    # Generate iCalendar schedule
    generate_calendar_schedule(project_path, serial, artist, title, rel_date, post1_content, post2_content, post3_content)

    manifest["ai_generated_copy"] = epk_txt
    manifest["status"] = "text_generated"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)
    print("[SYSTEM] Manifest synchronized. Asset pipeline execution verified.")

if __name__ == "__main__":
    run_text_generation_pipeline()