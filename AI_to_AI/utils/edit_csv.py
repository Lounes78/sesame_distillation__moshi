#!/usr/bin/env python3
"""
Script to edit prompts.csv and add new columns:
1. wav_exists: Boolean indicating if the wav file path exists
2. usage_count: Number of times the prompt was used (initialized to 0)
"""

import csv
import os
import sys

def edit_prompts_csv():
    # Path to the CSV file
    csv_path = "/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/prompts/prompts.csv"
    
    # Read the existing CSV
    rows = []
    with open(csv_path, 'r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        
        # Add new columns to fieldnames
        new_fieldnames = list(fieldnames) + ['wav_exists', 'usage_count']
        
        for row in reader:
            # Check if the wav file exists
            audio_path = row['audio_path']
            
            # Convert relative path to absolute path
            if audio_path.startswith('./prompts/'):
                # Remove the './' and prepend the full path
                full_audio_path = os.path.join(
                    "/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/prompts/",
                    audio_path[10:]  # Remove './prompts/' prefix
                )
            else:
                # Handle other path formats if needed
                full_audio_path = os.path.join(
                    "/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/",
                    audio_path
                )
            
            # Check if file exists
            wav_exists = os.path.exists(full_audio_path)
            
            # Add new columns
            row['wav_exists'] = str(wav_exists).lower()  # Convert boolean to lowercase string
            row['usage_count'] = '0'  # Initialize to 0
            
            rows.append(row)
    
    # Write the updated CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Successfully updated {csv_path}")
    print(f"Added columns: wav_exists, usage_count")
    print(f"Processed {len(rows)} rows")
    
    # Print summary of wav file existence
    existing_files = sum(1 for row in rows if row['wav_exists'] == 'true')
    missing_files = len(rows) - existing_files
    print(f"WAV files found: {existing_files}")
    print(f"WAV files missing: {missing_files}")

if __name__ == "__main__":
    try:
        edit_prompts_csv()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)