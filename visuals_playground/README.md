# Defmain Visuals Playground & Testing Framework

This playground is an independent workspace designed for iterating, designing, and stress-testing TouchDesigner visual templates before they are promoted to the production release pipeline.

---

## 1. How to Test Future Templates
The testing framework is fully template-agnostic. To test any new visual template you design:

1. Save your template `.toe` file inside the [`templates/`](file:///Users/dmm/Documents/Defmain_Platform_Root/visuals_playground/templates) directory (e.g., `templates/liquid.toe` or `templates/my_new_design.toe`).
2. Run the test script (it will automatically use the three default tracks in `Documents/Test_Tracks`):
   ```bash
   python3 test_render.py --template my_new_design
   ```
   *(You can still override them by passing custom paths to `--audio1`, `--audio2`, or `--audio3` if desired).*

---

## 2. Standard Template Interface Requirements
For any future template to be fully compatible with the playground launcher (`playground.py`) and the stability tester (`test_render.py`), it must meet two basic structural requirements:

### A. Node Layout
* An **Audio File In CHOP** at `/project1/audiofilein1` (handles the test track loading).
* A **Movie File Out TOP** at `/project1/moviefileout1` (handles the video output recording).
* A **Constant MAT** at `/project1/scopes_generator/constant1` (or your preferred material) to receive the dynamic colors.

### B. Standard Startup/Shutdown Script
An **Execute DAT** at `/project1/execute1` configured to run on Start and Frame Start, containing the standardized loading and delayed-quit code. This prevents the macOS file-flushing race condition:

```python
import json
import os
import wave
import contextlib
import colorsys

def onStart():
    task_path = "/tmp/defmain_td_task.json" 
    
    if os.path.exists(task_path):
        with open(task_path, 'r') as f:
            data = json.load(f)
            
        audio_path = data['audio_in']
        video_path = data['video_out']
        test_mode = data.get('test_mode', False)
        
        # Audio Analysis Parameters
        brightness = data.get('brightness', 0.5)
        energy = data.get('energy', 0.5)
        pitch_class = data.get('pitch_class', 0)
        
        # Compute dynamic HSV-to-RGB color mapping
        h = float(pitch_class) / 12.0
        s = 0.6 + float(energy) * 0.4
        v = 0.85 + float(brightness) * 0.15
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        
        # Apply color to scopes material
        mat = op('/project1/scopes_generator/constant1')
        if mat:
            mat.par.colorr = r
            mat.par.colorg = g
            mat.par.colorb = b

        # Compute project timeline length
        with contextlib.closing(wave.open(audio_path, 'r')) as w:
            audio_frames = w.getnframes()
            sample_rate = w.getframerate()
            duration_seconds = audio_frames / float(sample_rate)
        td_total_frames = int(duration_seconds * project.cookRate)
        
        # Load audio and set output path
        op('/project1/audiofilein1').par.file = audio_path
        op('/project1/moviefileout1').par.file = video_path
        
        # Configure timeline
        timeline = op('/local/time')
        timeline.par.start = 1
        timeline.par.end = td_total_frames
        timeline.par.rangeend = td_total_frames
        
        if test_mode:
            # GUI/Interactive Playground Mode
            project.realTime = True
            op('/project1/audiofilein1').par.play = 1
            op('/project1/audiofilein1').par.repeat = 'loop'
            op('/').time.play = True
            timeline.frame = 1
        else:
            # Offline/Batch Rendering Mode
            project.realTime = False
            timeline.frame = 1
            op('/project1/moviefileout1').par.record = 1

def onFrameStart(frame):
    video_node = op('/project1/moviefileout1')
    if not video_node:
        return
        
    end_frame = op('/local/time').par.end
    
    # 1. Stop recording at the end of the timeline
    if video_node.par.record == 1 and frame >= end_frame:
        video_node.par.record = 0
        return
        
    # 2. Wait for the next frame to let OS file buffers flush, then quit
    if video_node.par.record == 0 and frame > end_frame:
        project.quit(force=True)
```
