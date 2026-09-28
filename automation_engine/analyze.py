import sys
import os
import json
import numpy as np
import librosa

def analyze_audio(audio_path):
    if not os.path.exists(audio_path):
        print(json.dumps({"error": f"File not found: {audio_path}"}))
        sys.exit(1)

    try:
        # Load the first 120 seconds of audio for performance and analysis stability
        duration = 120
        y, sr = librosa.load(audio_path, duration=duration)
        
        # 1. Estimate Tempo (BPM)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        # Handle librosa v0.10+ returning an array or scalar
        bpm = float(tempo[0]) if isinstance(tempo, (list, np.ndarray, list)) else float(tempo)
        # Fallback for division or zero bpm cases
        if bpm <= 0:
            bpm = 120.0
            
        # 2. Estimate Spectral Centroid (Brightness)
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        mean_centroid = float(np.mean(spectral_centroid))
        
        # 3. Estimate RMS Energy (Intensity / Density)
        rms = librosa.feature.rms(y=y)
        mean_rms = float(np.mean(rms))
        
        # 4. Estimate Chroma (Tonality / Key vector)
        # Returns 12 values corresponding to C, C#, D, D#, E, F, F#, G, G#, A, A#, B
        chroma = librosa.feature.chroma_cens(y=y, sr=sr)
        mean_chroma = np.mean(chroma, axis=1)
        
        # Find dominant pitch class index (0-11)
        dominant_pitch_class = int(np.argmax(mean_chroma))
        
        # Normalize centroid and rms to standard 0.0 - 1.0 ranges for ease of use in shaders
        # Typ. spectral centroid maxes out around 5000Hz for bright electronic music, let's normalize by 6000
        norm_brightness = min(1.0, max(0.0, mean_centroid / 6000.0))
        # Typ. electronic music rms is around 0.05 to 0.35, let's normalize by 0.4
        norm_energy = min(1.0, max(0.0, mean_rms / 0.4))
        
        analysis_data = {
            "filename": os.path.basename(audio_path),
            "bpm": round(bpm, 2),
            "raw_brightness": round(mean_centroid, 2),
            "brightness": round(norm_brightness, 4),
            "raw_energy": round(mean_rms, 4),
            "energy": round(norm_energy, 4),
            "dominant_pitch_class": dominant_pitch_class,
            "chroma": [round(float(v), 4) for v in mean_chroma]
        }
        
        # Save analysis file next to original audio file
        dir_name = os.path.dirname(audio_path)
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        output_path = os.path.join(dir_name, f"{base_name}_analysis.json")
        
        with open(output_path, "w") as f:
            json.dump(analysis_data, f, indent=2)
            
        # Print output to stdout for the calling process
        print(json.dumps(analysis_data))
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No audio file path provided."}))
        sys.exit(1)
        
    analyze_audio(sys.argv[1])
