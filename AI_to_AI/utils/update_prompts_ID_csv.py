import pandas as pd
import os
import re
from pathlib import Path

def update_usage_count(csv_path, conversations_dir):
    """
    Update usage_count in CSV based on prompt_id occurrences in conversation filenames.
    
    Args:
        csv_path: Path to the prompts CSV file
        conversations_dir: Path to the conversations directory
    """
    
    # Read the CSV file
    df = pd.read_csv(csv_path)
    
    # Initialize usage_count to 0
    df['usage_count'] = 0
    
    # Get all conversation files
    conversations_path = Path(conversations_dir)
    conversation_files = list(conversations_path.glob("*.wav"))
    
    # Count occurrences of each prompt_id
    for file in conversation_files:
        filename = file.stem  # Get filename without extension
        
        # Extract prompt_id using regex pattern
        # Looking for pattern: maya_miles_prompted_{prompt_id}_...
        match = re.search(r'maya_miles_prompted_(\d+)_', filename)
        
        if match:
            prompt_id = int(match.group(1))
            
            # Increment usage_count for this prompt_id
            df.loc[df['prompt_id'] == prompt_id, 'usage_count'] += 1
            print(f"Found prompt_id {prompt_id} in {filename}")
    
    # Save the updated CSV
    df.to_csv(csv_path, index=False)
    print(f"\nUpdated CSV saved to {csv_path}")
    
    # Print summary
    print("\nUsage count summary:")
    for _, row in df.iterrows():
        print(f"Prompt ID {row['prompt_id']}: {row['usage_count']} uses")

# Usage
if __name__ == "__main__":
    csv_path = "/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/prompts/prompts.csv"
    conversations_dir = "/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/conversations"
    
    update_usage_count(csv_path, conversations_dir)