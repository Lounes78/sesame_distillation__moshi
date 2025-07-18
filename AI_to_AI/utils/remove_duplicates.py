import pandas as pd
import os
import re
from collections import defaultdict

def parse_log_file(log_file_path):
    """
    Parse the log file to extract duplicate and similar prompt information.
    
    Args:
        log_file_path: Path to the log file
    
    Returns:
        Dictionary with exact duplicates and similar pairs
    """
    with open(log_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract exact duplicates
    exact_duplicates = []
    
    # Pattern to match exact duplicate sections
    duplicate_pattern = r'Duplicate prompt \(appears \d+ times\):\s*\'([^\']*)\'\s*((?:\s*- [^\n]+ \(row \d+\)\s*)+)'
    
    for match in re.finditer(duplicate_pattern, content, re.MULTILINE):
        prompt_text = match.group(1)
        locations_text = match.group(2)
        
        # Extract file paths and row numbers
        location_pattern = r'- ([^(]+) \(row (\d+)\)'
        locations = []
        for loc_match in re.finditer(location_pattern, locations_text):
            file_path = loc_match.group(1).strip()
            row_num = int(loc_match.group(2))
            locations.append({'file': file_path, 'row': row_num})
        
        exact_duplicates.append({
            'prompt': prompt_text,
            'locations': locations
        })
    
    # Extract similar pairs
    similar_pairs = []
    
    # Pattern to match similar prompt pairs
    similar_pattern = r'Similarity: ([\d.]+)\s*1: \'([^\']*)\'\s*\(([^)]+) row (\d+)\)\s*2: \'([^\']*)\'\s*\(([^)]+) row (\d+)\)'
    
    for match in re.finditer(similar_pattern, content, re.MULTILINE):
        similarity = float(match.group(1))
        prompt1_text = match.group(2)
        file1_path = match.group(3).strip()
        row1 = int(match.group(4))
        prompt2_text = match.group(5)
        file2_path = match.group(6).strip()
        row2 = int(match.group(7))
        
        similar_pairs.append({
            'similarity': similarity,
            'prompt1': {'text': prompt1_text, 'file': file1_path, 'row': row1},
            'prompt2': {'text': prompt2_text, 'file': file2_path, 'row': row2}
        })
    
    return {
        'exact_duplicates': exact_duplicates,
        'similar_pairs': similar_pairs
    }

def determine_rows_to_remove(parsed_data, prefer_file_pattern="prompts2.csv"):
    """
    Determine which rows to remove based on duplicates and similar pairs.
    Prefer to keep prompts from files matching prefer_file_pattern.
    
    Args:
        parsed_data: Dictionary from parse_log_file
        prefer_file_pattern: Pattern to match preferred files (keep these)
    
    Returns:
        Dictionary mapping file paths to sets of row numbers to remove
    """
    rows_to_remove = defaultdict(set)
    
    # Handle exact duplicates
    print(f"Processing {len(parsed_data['exact_duplicates'])} exact duplicates...")
    for duplicate in parsed_data['exact_duplicates']:
        locations = duplicate['locations']
        
        # Sort locations by preference (preferred files last)
        locations.sort(key=lambda x: (prefer_file_pattern in x['file'], x['row']))
        
        # Remove all but the last one (which should be from preferred file if it exists there)
        for location in locations[:-1]:
            # Convert row number to 0-based index (CSV row - 2, since row 1 is header)
            df_index = location['row'] - 2
            rows_to_remove[location['file']].add(df_index)
            print(f"  Marking for removal: {os.path.basename(location['file'])} row {location['row']} (index {df_index})")
    
    # Handle similar pairs
    print(f"Processing {len(parsed_data['similar_pairs'])} similar pairs...")
    for pair in parsed_data['similar_pairs']:
        prompt1 = pair['prompt1']
        prompt2 = pair['prompt2']
        
        # Decide which one to remove based on preference
        if prefer_file_pattern in prompt1['file'] and prefer_file_pattern not in prompt2['file']:
            # Keep prompt1 (from preferred file), remove prompt2
            df_index = prompt2['row'] - 2
            rows_to_remove[prompt2['file']].add(df_index)
            print(f"  Removing from non-preferred: {os.path.basename(prompt2['file'])} row {prompt2['row']} (index {df_index})")
        elif prefer_file_pattern in prompt2['file'] and prefer_file_pattern not in prompt1['file']:
            # Keep prompt2 (from preferred file), remove prompt1
            df_index = prompt1['row'] - 2
            rows_to_remove[prompt1['file']].add(df_index)
            print(f"  Removing from non-preferred: {os.path.basename(prompt1['file'])} row {prompt1['row']} (index {df_index})")
        elif prompt1['file'] == prompt2['file']:
            # Same file, remove the later one
            if prompt1['row'] > prompt2['row']:
                df_index = prompt1['row'] - 2
                rows_to_remove[prompt1['file']].add(df_index)
                print(f"  Removing later duplicate: {os.path.basename(prompt1['file'])} row {prompt1['row']} (index {df_index})")
            else:
                df_index = prompt2['row'] - 2
                rows_to_remove[prompt2['file']].add(df_index)
                print(f"  Removing later duplicate: {os.path.basename(prompt2['file'])} row {prompt2['row']} (index {df_index})")
        else:
            # Both from non-preferred files, remove from prompts.csv if available
            if "prompts.csv" in prompt1['file'] and "prompts.csv" not in prompt2['file']:
                df_index = prompt1['row'] - 2
                rows_to_remove[prompt1['file']].add(df_index)
                print(f"  Removing from prompts.csv: {os.path.basename(prompt1['file'])} row {prompt1['row']} (index {df_index})")
            elif "prompts.csv" in prompt2['file'] and "prompts.csv" not in prompt1['file']:
                df_index = prompt2['row'] - 2
                rows_to_remove[prompt2['file']].add(df_index)
                print(f"  Removing from prompts.csv: {os.path.basename(prompt2['file'])} row {prompt2['row']} (index {df_index})")
            else:
                # Remove from the file that comes first alphabetically
                if prompt1['file'] < prompt2['file']:
                    df_index = prompt1['row'] - 2
                    rows_to_remove[prompt1['file']].add(df_index)
                    print(f"  Removing from first file: {os.path.basename(prompt1['file'])} row {prompt1['row']} (index {df_index})")
                else:
                    df_index = prompt2['row'] - 2
                    rows_to_remove[prompt2['file']].add(df_index)
                    print(f"  Removing from first file: {os.path.basename(prompt2['file'])} row {prompt2['row']} (index {df_index})")
    
    return dict(rows_to_remove)

def remove_duplicates_from_files(rows_to_remove):
    """
    Remove the specified rows from CSV files.
    
    Args:
        rows_to_remove: Dictionary mapping file paths to sets of row indices to remove
    
    Returns:
        Dictionary with removal statistics
    """
    removal_stats = {}
    
    for file_path, indices_to_remove in rows_to_remove.items():
        if not indices_to_remove:
            continue
            
        if not os.path.exists(file_path):
            print(f"Warning: File {file_path} does not exist, skipping...")
            continue
        
        print(f"\nProcessing {os.path.basename(file_path)}...")
        
        # Load the CSV file
        df = pd.read_csv(file_path)
        original_count = len(df)
        
        # Remove the specified rows
        indices_list = sorted(list(indices_to_remove), reverse=True)  # Remove from end to start
        print(f"  Removing {len(indices_list)} rows: {indices_list}")
        
        df = df.drop(indices_list).reset_index(drop=True)
        
        # Save the cleaned file
        df.to_csv(file_path, index=False)
        
        removed_count = original_count - len(df)
        removal_stats[file_path] = {
            'original_count': original_count,
            'removed_count': removed_count,
            'final_count': len(df)
        }
        
        print(f"  {os.path.basename(file_path)}: {original_count} -> {len(df)} (removed {removed_count})")
    
    return removal_stats

def main():
    """Main function to remove duplicates based on log file analysis"""
    
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file_path = os.path.join(script_dir, "log.py")
    
    if not os.path.exists(log_file_path):
        print(f"Error: Log file not found at {log_file_path}")
        return
    
    print("Parsing log file to extract duplicate information...")
    parsed_data = parse_log_file(log_file_path)
    
    print(f"Found {len(parsed_data['exact_duplicates'])} exact duplicates")
    print(f"Found {len(parsed_data['similar_pairs'])} similar pairs")
    
    # Determine which rows to remove (prefer to keep prompts2.csv)
    print("\nDetermining which rows to remove...")
    rows_to_remove = determine_rows_to_remove(parsed_data, prefer_file_pattern="prompts2.csv")
    
    # Create backup files before making changes
    print("\nCreating backup files...")
    for file_path in rows_to_remove.keys():
        if os.path.exists(file_path):
            backup_path = file_path + '.backup'
            df = pd.read_csv(file_path)
            df.to_csv(backup_path, index=False)
            print(f"  Created backup: {os.path.basename(backup_path)}")
    
    # Remove duplicates
    print("\nRemoving duplicates from files...")
    removal_stats = remove_duplicates_from_files(rows_to_remove)
    
    # Print summary
    print(f"\n🎯 Duplicate removal complete!")
    total_removed = sum(stats['removed_count'] for stats in removal_stats.values())
    total_remaining = sum(stats['final_count'] for stats in removal_stats.values())
    
    print(f"Total prompts removed: {total_removed}")
    print(f"Total prompts remaining: {total_remaining}")
    
    for file_path, stats in removal_stats.items():
        filename = os.path.basename(file_path)
        print(f"  {filename}: {stats['removed_count']} removed, {stats['final_count']} remaining")

if __name__ == "__main__":
    main()