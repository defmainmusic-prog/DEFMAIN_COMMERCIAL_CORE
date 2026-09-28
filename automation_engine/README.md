# DEFMAIN PLATFORM: RELEASE AUTOMATION TOOLCHAIN
Internal operational sequence manual for the native Python 3.14/FFmpeg processing core.

---

## Pre-Flight Requisites
Ensure your root environment file is configured at the parent level:
* File location: `Defmain_Platform_Root/.env`
* Required keys:
  * `GEMINI_API_KEY="..."` (For AI text copy generation)
  * `NOTION_TOKEN="..."` (For Notion EPK database integrations)
  * `NOTION_DATABASE_ID="..."` (For Notion EPK database routing)

---

## Unified Execution Entrypoint
To run the automated flow, use the unified pipeline runner:
```bash
python3 run_pipeline.py
```
This script acts as the main orchestrator and guides you through the process step-by-step.

### Choosing Options:
* **Option 1**: Creates and initializes a new release from scratch, builds the folder structures, prompts you for metadata, and runs the sequence.
* **Option 2**: Runs the pipeline over an existing folder structure that has already been initialized.

> [!IMPORTANT]
> **Manual Master Audio Step**: Immediately after Choice 1 creates the release folders, you must manually copy your master audio files (`.wav`, `.aif`, `.aiff`, or `.flac`) into the newly created `01_Masters/` directory. The pipeline will scan the directory and wait for these files to proceed with rendering.

---

## Core Execution Sequence

### Step 1: Text Generation & Metadata Injection
Runs text copy generation using Gemini and creates social media and calendar scheduling files.
* **Script**: `generate_release_text.py`
* **Outputs**:
  * `[Release_Folder]/EPK/EPK.txt` (Bio/Press kit description)
  * `[Release_Folder]/03_Social/Post1.txt` (Teaser copy)
  * `[Release_Folder]/03_Social/Post2.txt` (Release announcement copy)
  * `[Release_Folder]/03_Social/Post3.txt` (Broadcasting follow-up copy)
  * `[Release_Folder]/release_schedule.ics` (iCalendar file to import schedule dates and caption copy directly into Google Calendar or Apple Calendar)

### Step 2: Audio Masters MP3 Coupling
Transcodes raw engineering masters into a standardized distribution bundle.
* **Script**: `convert_320.py`
* **Outputs**:
  * `[Release_Folder]/EPK/MP3_320kbps/*` (320kbps distribution-ready MP3 files)

### Step 3: Audio-Reactive Background Ignition
Communicates with TouchDesigner via subprocess flags to render raw generative loops.
* **Script**: `visual_processing/td_trigger.py`
* **Outputs**:
  * `[Release_Folder]/03_Social/td_masters/*_TD_Master.mp4` (Generative loops mapped to the track audio frequencies)

### Step 4: Vector Branding Compilation (Square)
Fires the Cairo graphic vector driver to render transparent square layout branding overlays.
* **Script**: `visual_processing/exec_vector_gen.sh <SERIAL> square`
* **Outputs**:
  * `[Release_Folder]/02_Artwork/<SERIAL>_overlay_square.png`

### Step 5: Vector Branding Compilation (Vertical)
Renders transparent vertical overlays incorporating social safe zone bounds (100px top, 200px bottom).
* **Script**: `visual_processing/exec_vector_gen.sh <SERIAL> vertical`
* **Outputs**:
  * `[Release_Folder]/02_Artwork/<SERIAL>_overlay_vertical.png`

### Step 6: Final Multiplex Compositor
Extracts reference frames from video masters, overlays branding assets, and packages final media.
* **Script**: `visual_processing/audio_art_generator.py <SERIAL>`
* **Outputs**:
  * `[Release_Folder]/02_Artwork/*_CoverArt_V1.png` (Plus V2 and V3 variants)
  * `[Release_Folder]/03_Social/*_9x16_Social_Clip.mp4` (Padded vertical clip with safe-zone overlays)
  * `[Release_Folder]/04_DTV/*_YT_Full.mp4` (16:9 YouTube master video)

### Step 6b: Grayscale SoundCloud Preview Art
Generates grayscale watermarked preview variants of the selected cover art.
* **Script**: `visual_processing/generate_preview_artwork.py <SERIAL>`
* **Outputs**:
  * `[Release_Folder]/02_Artwork/*_CoverArt_Preview_Horizontal.png`
  * `[Release_Folder]/02_Artwork/*_CoverArt_Preview_Angled.png`
  * `[Release_Folder]/02_Artwork/*_CoverArt_Preview.png` (Default)

### Step 6c: 3000x3000px JPG Distribution Cover Art
Generates a true high-resolution 3000x3000px JPG cover art for distribution platforms.
* **Script**: `visual_processing/generate_distribution_cover.py <SERIAL>`
* **Outputs**:
  * `[Release_Folder]/02_Artwork/*_CoverArt.jpg`

### Step 7: Push EPK to Notion
Feeds database records containing release metadata, generated bio copy, and social links to the central Defmain Notion database page.
* **Script**: `push_to_notion.py`
* **Result**: Notion EPK page record created/updated.

### Step 8: Generate Metricool CSV Schedule
Constructs bulk-scheduling social templates for automated social queue managers.
* **Script**: `generate_metricool_csv.py`
* **Outputs**:
  * `[Release_Folder]/03_Social/metricool_schedule.csv` (Ready for bulk upload)

---

## Commercial / External Deployment Configuration
This project is configured out-of-the-box to use Google Drive for hosting and sharing release assets (including Notion cover and bio image embeds). 

> [!IMPORTANT]
> **Storage Portability Notice:** For external labels or commercial distribution, users must configure and provide their own dedicated Google Cloud Storage/Google Drive credentials or AWS S3 buckets in `.env`. Do not share the central Defmain storage credentials with external tenants.

---
[SYSTEM POSTURE SECURE — ALL ENGINES FUNCTIONAL]