#!/usr/bin/env python3
"""
Random Batch Audio Player

This script allows you to randomly select and play a WAV file from a specified batch
in the conversations folder. It can also list available files in a batch before playing.

Filename pattern expected: *_batch{number}_*.wav
"""

import os
import re
import random
import subprocess
import sys
import wave
from pathlib import Path
import argparse


def extract_batch_number(filename):
    """
    Extract batch number from filename.
    
    Expected pattern: *_batch{number}_*.wav
    Returns None if no batch number found.
    """
    match = re.search(r'batch(\d+)', filename)
    return int(match.group(1)) if match else None


def get_wav_duration(filepath):
    """
    Get duration of a WAV file in seconds.
    
    Returns:
        float: Duration in seconds, or None if error
    """
    try:
        with wave.open(str(filepath), 'rb') as audio:
            frames = audio.getnframes()
            sample_rate = audio.getframerate()
            duration = frames / sample_rate
            return duration
    except Exception:
        return None


def format_duration(seconds):
    """Format duration in MM:SS format."""
    if seconds is None:
        return "N/A"
    
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def find_batch_files(conversations_dir, batch_number):
    """
    Find all WAV files for a specific batch number.
    
    Args:
        conversations_dir: Path to conversations directory
        batch_number: Batch number to search for
        
    Returns:
        list: List of Path objects for matching files
    """
    conversations_path = Path(conversations_dir)
    
    if not conversations_path.exists():
        print(f"❌ Error: Directory {conversations_dir} does not exist")
        return []
    
    wav_files = list(conversations_path.glob("*.wav"))
    batch_files = []
    
    for wav_file in wav_files:
        file_batch = extract_batch_number(wav_file.name)
        if file_batch == batch_number:
            batch_files.append(wav_file)
    
    return batch_files


def list_available_batches(conversations_dir):
    """
    List all available batch numbers in the conversations directory.
    
    Returns:
        list: Sorted list of batch numbers
    """
    conversations_path = Path(conversations_dir)
    
    if not conversations_path.exists():
        return []
    
    wav_files = list(conversations_path.glob("*.wav"))
    batch_numbers = set()
    
    for wav_file in wav_files:
        batch_number = extract_batch_number(wav_file.name)
        if batch_number is not None:
            batch_numbers.add(batch_number)
    
    return sorted(batch_numbers)


def show_file_path(filepath):
    """
    Show the absolute path of the audio file for SSH/VSCode users.
    
    Args:
        filepath: Path to the audio file
        
    Returns:
        bool: Always True
    """
    print(f"🎵 Audio file path (click to open in VSCode):")
    print(f"📁 {filepath.absolute()}")
    return True


def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(description="Randomly select and play WAV files from a specific batch")
    parser.add_argument("batch_number", type=int, nargs='?',
                       help="Batch number to select from")
    parser.add_argument("--conversations-dir", 
                       default="/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/conversations",
                       help="Path to conversations directory")
    parser.add_argument("--list-batches", action="store_true",
                       help="List all available batch numbers")
    parser.add_argument("--list-files", action="store_true",
                       help="List all files in the specified batch without playing")
    parser.add_argument("--info", action="store_true",
                       help="Show file info before playing")
    parser.add_argument("--no-play", action="store_true",
                       help="Don't play the file, just show selection")
    
    args = parser.parse_args()
    
    print("🎵 Random Batch Audio Player")
    print(f"📁 Conversations directory: {args.conversations_dir}")
    
    # List available batches if requested
    if args.list_batches:
        available_batches = list_available_batches(args.conversations_dir)
        if available_batches:
            print(f"\n📊 Available batches: {available_batches}")
            print(f"Total batches: {len(available_batches)}")
        else:
            print("❌ No batches found")
        return 0
    
    # Check if batch number is provided
    if args.batch_number is None:
        available_batches = list_available_batches(args.conversations_dir)
        if available_batches:
            print(f"❌ Please specify a batch number. Available batches: {available_batches}")
        else:
            print("❌ Please specify a batch number. No batches found in directory.")
        return 1
    
    # Find files for the specified batch
    batch_files = find_batch_files(args.conversations_dir, args.batch_number)
    
    if not batch_files:
        print(f"❌ No files found for batch #{args.batch_number}")
        available_batches = list_available_batches(args.conversations_dir)
        if available_batches:
            print(f"Available batches: {available_batches}")
        return 1
    
    print(f"\n🎯 Found {len(batch_files)} files in batch #{args.batch_number}")
    
    # List files if requested
    if args.list_files:
        print(f"\n📋 Files in batch #{args.batch_number}:")
        for i, file_path in enumerate(sorted(batch_files), 1):
            duration = get_wav_duration(file_path)
            duration_str = format_duration(duration)
            print(f"  {i:2d}. {file_path.name} ({duration_str})")
        return 0
    
    # Randomly select a file
    selected_file = random.choice(batch_files)
    duration = get_wav_duration(selected_file)
    
    print(f"\n🎲 Randomly selected: {selected_file.name}")
    
    if args.info or args.no_play:
        print(f"   📁 Full path: {selected_file}")
        print(f"   ⏱️ Duration: {format_duration(duration)}")
        print(f"   📊 File size: {selected_file.stat().st_size / 1024 / 1024:.1f} MB")
        
        # Extract info from filename if possible
        filename = selected_file.name
        if 'prompted' in filename:
            print(f"   🎯 Type: Prompted conversation")
        elif 'not' in filename:
            print(f"   🎯 Type: Non-prompted conversation")
        
        # Try to extract other parameters from filename
        parts = filename.replace('.wav', '').split('_')
        if len(parts) >= 6:
            try:
                processing_time = parts[-4]
                stabilization_time = parts[-3]
                prompt_target = parts[-2]
                print(f"   ⚙️ Processing time: {processing_time}s")
                print(f"   ⚙️ Stabilization time: {stabilization_time}s")
                print(f"   🎯 Prompt target: {prompt_target}")
            except (IndexError, ValueError):
                pass
    
    if args.no_play:
        return 0
    
    # Show the file path for SSH/VSCode users
    print(f"\n▶️ Audio file ready:")
    success = show_file_path(selected_file)
    
    print("💡 Click on the path above in VSCode to open and listen to the file")
    
    return 0


if __name__ == "__main__":
    exit(main())