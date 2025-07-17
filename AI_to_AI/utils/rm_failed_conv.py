import os
import wave

TARGET_DIR = '/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/conversations'

def is_wav_too_short(filepath, min_duration_sec=60):
    try:
        with wave.open(filepath, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / float(rate)
            return duration < min_duration_sec
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False  # If unreadable, skip

def remove_short_wavs():
    for root, _, files in os.walk(TARGET_DIR):
        for file in files:
            if file.lower().endswith('.wav'):
                filepath = os.path.join(root, file)
                if is_wav_too_short(filepath):
                    print(f"Deleting {filepath} (under 60 seconds)")
                    os.remove(filepath)

if __name__ == '__main__':
    remove_short_wavs()
