import os
import wave
from pathlib import Path

def analyze_wav_files(directory):
    wav_files = list(Path(directory).glob("*.wav"))
    
    if not wav_files:
        print("No .wav files found in the directory")
        return
    
    total_duration = 0
    longer_than_minute = 0
    shorter_than_minute = 0
    
    for wav_file in wav_files:
        try:
            with wave.open(str(wav_file), 'rb') as audio:
                frames = audio.getnframes()
                sample_rate = audio.getframerate()
                duration = frames / sample_rate
                
                total_duration += duration
                
                if duration > 60:
                    longer_than_minute += 1
                else:
                    shorter_than_minute += 1
                    
        except Exception as e:
            print(f"Error processing {wav_file}: {e}")
    
    # Convert total duration to hours, minutes, seconds
    hours = int(total_duration // 3600)
    minutes = int((total_duration % 3600) // 60)
    seconds = int(total_duration % 60)
    
    print(f"Total files: {len(wav_files)}")
    print(f"Total duration: {hours:02d}:{minutes:02d}:{seconds:02d} ({total_duration:.2f} seconds)")
    print(f"Files longer than 1 minute: {longer_than_minute}")
    print(f"Files shorter than 1 minute: {shorter_than_minute}")

# Usage
directory_path = "/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/conversations"
analyze_wav_files(directory_path)