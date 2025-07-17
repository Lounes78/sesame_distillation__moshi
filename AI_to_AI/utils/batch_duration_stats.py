#!/usr/bin/env python3
"""
Batch Duration Statistics Analyzer

This script analyzes duration statistics per batch number from conversation files
in the conversations folder. It extracts batch numbers from filenames and provides
detailed statistics for each batch.

Filename pattern expected: *_batch{number}_*.wav
"""

import os
import re
import wave
from pathlib import Path
from collections import defaultdict
import argparse


def extract_batch_number(filename):
    """
    Extract batch number from filename.
    
    Expected pattern: *_batch{number}_*.wav
    Returns None if no batch number found.
    """
    match = re.search(r'batch(\d+)', filename)
    return int(match.group(1)) if match else None


def analyze_wav_duration(filepath):
    """
    Analyze duration of a single WAV file.
    
    Returns:
        float: Duration in seconds, or None if error
    """
    try:
        with wave.open(str(filepath), 'rb') as audio:
            frames = audio.getnframes()
            sample_rate = audio.getframerate()
            duration = frames / sample_rate
            return duration
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return None


def format_duration(seconds):
    """Format duration in HH:MM:SS format."""
    if seconds is None:
        return "N/A"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def analyze_batch_durations(conversations_dir):
    """
    Analyze duration statistics per batch number.
    
    Args:
        conversations_dir: Path to the conversations directory
        
    Returns:
        dict: Statistics per batch number
    """
    conversations_path = Path(conversations_dir)
    
    if not conversations_path.exists():
        print(f"Error: Directory {conversations_dir} does not exist")
        return {}
    
    wav_files = list(conversations_path.glob("*.wav"))
    
    if not wav_files:
        print("No .wav files found in the directory")
        return {}
    
    # Group files by batch number
    batch_data = defaultdict(list)
    no_batch_files = []
    
    print(f"📁 Analyzing {len(wav_files)} WAV files...")
    
    for wav_file in wav_files:
        batch_number = extract_batch_number(wav_file.name)
        duration = analyze_wav_duration(wav_file)
        
        if duration is not None:
            if batch_number is not None:
                batch_data[batch_number].append({
                    'filename': wav_file.name,
                    'duration': duration
                })
            else:
                no_batch_files.append({
                    'filename': wav_file.name,
                    'duration': duration
                })
    
    # Calculate statistics per batch
    batch_stats = {}
    
    for batch_number in sorted(batch_data.keys()):
        files = batch_data[batch_number]
        durations = [f['duration'] for f in files]
        
        total_duration = sum(durations)
        avg_duration = total_duration / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        
        # Count files by duration categories
        short_files = sum(1 for d in durations if d < 60)
        medium_files = sum(1 for d in durations if 60 <= d < 300)  # 1-5 minutes
        long_files = sum(1 for d in durations if d >= 300)  # 5+ minutes
        
        batch_stats[batch_number] = {
            'file_count': len(files),
            'total_duration': total_duration,
            'avg_duration': avg_duration,
            'min_duration': min_duration,
            'max_duration': max_duration,
            'short_files': short_files,  # < 1 minute
            'medium_files': medium_files,  # 1-5 minutes
            'long_files': long_files,  # 5+ minutes
            'files': files
        }
    
    # Handle files without batch numbers
    if no_batch_files:
        durations = [f['duration'] for f in no_batch_files]
        total_duration = sum(durations)
        avg_duration = total_duration / len(durations)
        
        batch_stats['no_batch'] = {
            'file_count': len(no_batch_files),
            'total_duration': total_duration,
            'avg_duration': avg_duration,
            'min_duration': min(durations),
            'max_duration': max(durations),
            'short_files': sum(1 for d in durations if d < 60),
            'medium_files': sum(1 for d in durations if 60 <= d < 300),
            'long_files': sum(1 for d in durations if d >= 300),
            'files': no_batch_files
        }
    
    return batch_stats


def print_batch_statistics(batch_stats, detailed=False):
    """Print formatted batch statistics."""
    
    if not batch_stats:
        print("No batch data to display")
        return
    
    print("\n" + "="*80)
    print("📊 DURATION STATISTICS PER BATCH")
    print("="*80)
    
    # Summary table
    print(f"\n{'Batch':<8} {'Files':<6} {'Total Duration':<15} {'Avg Duration':<12} {'Min':<8} {'Max':<8}")
    print("-" * 80)
    
    total_files = 0
    grand_total_duration = 0
    
    # Sort batches (handle 'no_batch' specially)
    sorted_batches = []
    regular_batches = [k for k in batch_stats.keys() if k != 'no_batch']
    sorted_batches.extend(sorted(regular_batches))
    if 'no_batch' in batch_stats:
        sorted_batches.append('no_batch')
    
    for batch in sorted_batches:
        stats = batch_stats[batch]
        batch_name = f"#{batch}" if batch != 'no_batch' else "No Batch"
        
        print(f"{batch_name:<8} {stats['file_count']:<6} "
              f"{format_duration(stats['total_duration']):<15} "
              f"{format_duration(stats['avg_duration']):<12} "
              f"{format_duration(stats['min_duration']):<8} "
              f"{format_duration(stats['max_duration']):<8}")
        
        total_files += stats['file_count']
        grand_total_duration += stats['total_duration']
    
    print("-" * 80)
    print(f"{'TOTAL':<8} {total_files:<6} {format_duration(grand_total_duration):<15}")
    
    # Detailed breakdown per batch
    if detailed:
        print("\n" + "="*80)
        print("📋 DETAILED BREAKDOWN PER BATCH")
        print("="*80)
        
        for batch in sorted_batches:
            stats = batch_stats[batch]
            batch_name = f"Batch #{batch}" if batch != 'no_batch' else "Files without batch number"
            
            print(f"\n🎯 {batch_name}")
            print(f"   Files: {stats['file_count']}")
            print(f"   Total Duration: {format_duration(stats['total_duration'])} ({stats['total_duration']:.1f}s)")
            print(f"   Average Duration: {format_duration(stats['avg_duration'])} ({stats['avg_duration']:.1f}s)")
            print(f"   Duration Range: {format_duration(stats['min_duration'])} - {format_duration(stats['max_duration'])}")
            print(f"   Duration Categories:")
            print(f"     • Short (< 1 min): {stats['short_files']} files")
            print(f"     • Medium (1-5 min): {stats['medium_files']} files")
            print(f"     • Long (5+ min): {stats['long_files']} files")
            
            if len(stats['files']) <= 10:  # Show individual files for small batches
                print(f"   Files:")
                for file_info in sorted(stats['files'], key=lambda x: x['duration'], reverse=True):
                    print(f"     • {file_info['filename']} - {format_duration(file_info['duration'])}")


def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(description="Analyze duration statistics per batch number")
    parser.add_argument("--conversations-dir", 
                       default="/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/conversations",
                       help="Path to conversations directory")
    parser.add_argument("--detailed", action="store_true",
                       help="Show detailed breakdown per batch")
    parser.add_argument("--batch", type=int,
                       help="Show detailed info for specific batch number only")
    
    args = parser.parse_args()
    
    print("🎵 Batch Duration Statistics Analyzer")
    print(f"📁 Analyzing directory: {args.conversations_dir}")
    
    # Analyze batch durations
    batch_stats = analyze_batch_durations(args.conversations_dir)
    
    if not batch_stats:
        print("❌ No data found to analyze")
        return 1
    
    # Show specific batch if requested
    if args.batch is not None:
        if args.batch in batch_stats:
            filtered_stats = {args.batch: batch_stats[args.batch]}
            print_batch_statistics(filtered_stats, detailed=True)
        else:
            print(f"❌ Batch #{args.batch} not found")
            available_batches = [k for k in batch_stats.keys() if k != 'no_batch']
            if available_batches:
                print(f"Available batches: {sorted(available_batches)}")
            return 1
    else:
        # Show all batches
        print_batch_statistics(batch_stats, detailed=args.detailed)
    
    return 0


if __name__ == "__main__":
    exit(main())