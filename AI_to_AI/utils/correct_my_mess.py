import os
import re
from pathlib import Path

def rename_batch_files(conversations_dir):
    """
    Rename .wav files with batch 102, 103, or 104 from 'prompted' to 'not'.
    
    Args:
        conversations_dir: Path to the conversations directory
    """
    
    conversations_path = Path(conversations_dir)
    wav_files = list(conversations_path.glob("*.wav"))
    
    renamed_count = 0
    
    for file in wav_files:
        filename = file.name
        
        # Check if file has batch 102, 103, or 104 and contains 'prompted'
        if re.search(r'batch10[234]', filename) and 'prompted' in filename:
            # Replace 'prompted' with 'not'
            new_filename = filename.replace('prompted', 'not')
            new_path = file.parent / new_filename
            
            # Rename the file
            file.rename(new_path)
            print(f"Renamed: {filename} -> {new_filename}")
            renamed_count += 1
    
    print(f"\nTotal files renamed: {renamed_count}")

# Usage
if __name__ == "__main__":
    conversations_dir = "/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/conversations"
    rename_batch_files(conversations_dir)