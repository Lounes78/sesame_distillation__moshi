#!/usr/bin/env python3
"""
Configurable batch orchestrator to run multiple batches of conversation_orchestrator.py
with customizable batch sizes and number of batches.
"""

import os
import time
import subprocess
import signal
import glob
import wave
import statistics
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_orchestrator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def clean_tokens_directory():
    """Remove all files in tokens directory"""
    tokens_dir = Path("tokens")
    if tokens_dir.exists():
        for file in tokens_dir.glob("*"):
            try:
                os.remove(file)
                logger.info(f"Removed {file}")
            except Exception as e:
                logger.error(f"Error removing {file}: {e}")

def count_wav_files(batch_number):
    """Count WAV files for a specific batch"""
    pattern = f"conversations/*batch{batch_number}*"
    files = glob.glob(pattern)
    return len(files)

def count_available_token_pairs(batch_number):
    """Count available token pairs for a specific batch"""
    tokens_dir = Path("tokens")
    count = 0
    
    # We need to check all possible pair IDs, not just up to batch_size
    # because some pairs might be missing in the middle
    pair_id = 0
    max_check = 200  # Safety limit to avoid infinite loop
    
    while pair_id < max_check:
        maya_token = tokens_dir / f"token_batch{batch_number}_{pair_id}_maya.json"
        miles_token = tokens_dir / f"token_batch{batch_number}_{pair_id}_miles.json"
        
        if maya_token.exists() and miles_token.exists():
            count += 1
            pair_id += 1
        else:
            # If we find a gap, check a few more to see if there are tokens beyond the gap
            gap_count = 0
            temp_pair_id = pair_id + 1
            found_more = False
            
            # Check next 10 positions for more tokens
            while gap_count < 10 and temp_pair_id < max_check:
                temp_maya = tokens_dir / f"token_batch{batch_number}_{temp_pair_id}_maya.json"
                temp_miles = tokens_dir / f"token_batch{batch_number}_{temp_pair_id}_miles.json"
                
                if temp_maya.exists() and temp_miles.exists():
                    found_more = True
                    break
                    
                gap_count += 1
                temp_pair_id += 1
            
            if found_more:
                pair_id += 1  # Continue checking
            else:
                break  # No more tokens found, stop checking
    
    return count

def analyze_wav_files(directory):
    """Analyze WAV files and return statistics"""
    wav_files = list(Path(directory).glob("*.wav"))
    
    if not wav_files:
        return {
            'total_files': 0,
            'total_duration': 0,
            'longer_than_minute': 0,
            'shorter_than_minute': 0,
            'durations': []
        }
    
    total_duration = 0
    longer_than_minute = 0
    shorter_than_minute = 0
    durations = []
    
    for wav_file in wav_files:
        try:
            with wave.open(str(wav_file), 'rb') as audio:
                frames = audio.getnframes()
                sample_rate = audio.getframerate()
                duration = frames / sample_rate
                
                total_duration += duration
                durations.append(duration)
                
                if duration > 60:
                    longer_than_minute += 1
                else:
                    shorter_than_minute += 1
                    
        except Exception as e:
            logger.error(f"Error processing {wav_file}: {e}")
    
    return {
        'total_files': len(wav_files),
        'total_duration': total_duration,
        'longer_than_minute': longer_than_minute,
        'shorter_than_minute': shorter_than_minute,
        'durations': durations
    }

def analyze_batch_wav_files(batch_number):
    """Analyze WAV files for a specific batch"""
    conversations_dir = Path("conversations")
    pattern = f"*batch{batch_number}*.wav"
    wav_files = list(conversations_dir.glob(pattern))
    
    if not wav_files:
        return {
            'total_files': 0,
            'total_duration': 0,
            'longer_than_minute': 0,
            'shorter_than_minute': 0,
            'durations': []
        }
    
    total_duration = 0
    longer_than_minute = 0
    shorter_than_minute = 0
    durations = []
    
    logger.info(f"🔍 Analyzing {len(wav_files)} WAV files for batch {batch_number}:")
    
    for wav_file in wav_files:
        try:
            with wave.open(str(wav_file), 'rb') as audio:
                frames = audio.getnframes()
                sample_rate = audio.getframerate()
                duration = frames / sample_rate
                
                total_duration += duration
                durations.append(duration)
                
                duration_str = f"{duration:.1f}s"
                if duration > 60:
                    longer_than_minute += 1
                    logger.info(f"   📈 {wav_file.name}: {duration_str} (>1min)")
                else:
                    shorter_than_minute += 1
                    logger.info(f"   📉 {wav_file.name}: {duration_str} (<1min)")
                    
        except Exception as e:
            logger.error(f"   ❌ Error processing {wav_file}: {e}")
    
    return {
        'total_files': len(wav_files),
        'total_duration': total_duration,
        'longer_than_minute': longer_than_minute,
        'shorter_than_minute': shorter_than_minute,
        'durations': durations
    }

def format_duration(seconds):
    """Format duration in HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run batch orchestrator for AI-to-AI conversations')
    parser.add_argument('--start-batch', type=int, default=0,
                       help='Starting batch number (default: 0)')
    parser.add_argument('--end-batch', type=int, default=9,
                       help='Ending batch number (default: 9)')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Number of conversations per batch (default: 50)')
    parser.add_argument('--num-batches', type=int, default=None,
                       help='Number of batches to run (overrides end-batch if specified)')
    args = parser.parse_args()
    
    # Handle num-batches parameter
    if args.num_batches is not None:
        args.end_batch = args.start_batch + args.num_batches - 1
    
    # Validate batch range
    if args.start_batch < 0 or args.end_batch < args.start_batch:
        logger.error("Invalid batch range. start-batch must be >= 0 and end-batch must be >= start-batch")
        return
    
    # Validate batch size
    if args.batch_size <= 0:
        logger.error("Batch size must be greater than 0")
        return
    
    total_batches = args.end_batch - args.start_batch + 1
    logger.info(f"🚀 Starting {total_batches} batches of conversation orchestrator (batch {args.start_batch} to {args.end_batch})")
    logger.info(f"📊 Batch size: {args.batch_size} conversations per batch")
    
    batch_stats = []
    
    for batch_num in range(args.start_batch, args.end_batch + 1):
        logger.info(f"{'='*60}")
        logger.info(f"🎯 BATCH {batch_num} STARTING")
        logger.info(f"{'='*60}")
        
        # Step 1: Clean tokens directory
        logger.info(f"🧹 Cleaning tokens directory for batch {batch_num}")
        clean_tokens_directory()
        
        # Step 2: Generate tokens
        logger.info(f"🔑 Generating tokens for batch {batch_num}")
        token_cmd = [
            "python", "conversation_orchestrator.py",
            "--batch-size", str(args.batch_size),
            "--batch-number", str(batch_num),
            "--tokens-only"
        ]
        
        try:
            result = subprocess.run(token_cmd, check=True, capture_output=True, text=True)
            logger.info("✅ Token generation completed")
            
            # Check how many token pairs were actually generated
            available_pairs = count_available_token_pairs(batch_num)
            logger.info(f"📊 Available token pairs: {available_pairs}/{args.batch_size}")
            
            if available_pairs == 0:
                logger.error(f"❌ No token pairs generated for batch {batch_num}, skipping...")
                continue
            elif available_pairs < args.batch_size:
                logger.warning(f"⚠️ Only {available_pairs} token pairs available (requested {args.batch_size})")
                logger.info(f"🎯 Will launch {available_pairs} conversations instead")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Token generation failed: {e}")
            logger.error(f"STDOUT: {e.stdout}")
            logger.error(f"STDERR: {e.stderr}")
            # Wait longer before retrying due to potential rate limiting
            logger.info("⏰ Waiting 60 seconds before continuing due to token generation failure...")
            time.sleep(60)
            continue
        
        # Step 3: Launch conversations
        logger.info(f"🎭 Launching conversations for batch {batch_num}")
        conv_cmd = [
            "python", "conversation_orchestrator.py",
            "--batch-size", str(available_pairs),
            "--batch-number", str(batch_num),
            "--conversations-only"
        ]
        
        try:
            # Start conversations in background
            conv_process = subprocess.Popen(conv_cmd)
            logger.info(f"✅ Conversations launched (PID: {conv_process.pid})")
            
            # Wait 5 minutes
            logger.info(f"⏰ Waiting 5 minutes for {available_pairs} conversations...")
            time.sleep(300)
            
            # Stop conversations
            logger.info("🛑 Stopping conversations...")
            try:
                # Kill processes matching the batch pattern
                subprocess.run([
                    "pkill", "-SIGINT", "-f", f"batch{batch_num}"
                ], check=False)
                time.sleep(3)  # Give time for graceful shutdown
            except Exception as e:
                logger.warning(f"Warning: Error stopping processes: {e}")
            
            # Check for WAV files
            logger.info("🔍 Checking for WAV files...")
            time.sleep(3)
            wav_count = count_wav_files(batch_num)
            logger.info(f"📊 Found {wav_count} WAV files for batch {batch_num}")
            
        except Exception as e:
            logger.error(f"❌ Conversation launch failed: {e}")
            continue
        
        # Step 4: Analyze batch audio
        batch_analysis = analyze_batch_wav_files(batch_num)
        batch_stats.append({
            'batch': batch_num,
            'requested_conversations': args.batch_size,
            'available_tokens': available_pairs,
            'wav_count': wav_count,
            'analysis': batch_analysis
        })
        
        # Print batch summary
        total_hours = batch_analysis['total_duration'] / 3600
        logger.info(f"📊 BATCH {batch_num} SUMMARY:")
        logger.info(f"   Requested conversations: {args.batch_size}")
        logger.info(f"   Available token pairs: {available_pairs}")
        logger.info(f"   WAV files generated: {wav_count}")
        logger.info(f"   Success rate: {wav_count}/{available_pairs} ({(wav_count/available_pairs*100):.1f}%)" if available_pairs > 0 else "   Success rate: 0%")
        logger.info(f"   Total duration: {format_duration(batch_analysis['total_duration'])} ({total_hours:.2f} hours)")
        logger.info(f"   📈 Files >1 min: {batch_analysis['longer_than_minute']}")
        logger.info(f"   📉 Files <1 min: {batch_analysis['shorter_than_minute']}")
        if batch_analysis['total_files'] > 0:
            avg_duration = batch_analysis['total_duration'] / batch_analysis['total_files']
            logger.info(f"   ⏱️ Average duration: {avg_duration:.1f}s")
    
    # Final statistics
    logger.info(f"{'='*60}")
    logger.info("🏁 FINAL STATISTICS")
    logger.info(f"{'='*60}")
    
    # Calculate overall stats
    all_durations = []
    total_files = 0
    total_duration = 0
    total_longer = 0
    total_shorter = 0
    total_requested = 0
    total_available = 0
    
    for batch_stat in batch_stats:
        analysis = batch_stat['analysis']
        total_files += analysis['total_files']
        total_duration += analysis['total_duration']
        total_longer += analysis['longer_than_minute']
        total_shorter += analysis['shorter_than_minute']
        total_requested += batch_stat['requested_conversations']
        total_available += batch_stat['available_tokens']
        all_durations.extend(analysis['durations'])
    
    total_hours = total_duration / 3600
    
    logger.info(f"📊 OVERALL SUMMARY:")
    logger.info(f"   Total batches: {total_batches}")
    logger.info(f"   Total requested conversations: {total_requested}")
    logger.info(f"   Total available token pairs: {total_available}")
    logger.info(f"   Total WAV files generated: {total_files}")
    logger.info(f"   Token generation success rate: {total_available}/{total_requested} ({(total_available/total_requested*100):.1f}%)" if total_requested > 0 else "   Token generation success rate: 0%")
    logger.info(f"   Conversation success rate: {total_files}/{total_available} ({(total_files/total_available*100):.1f}%)" if total_available > 0 else "   Conversation success rate: 0%")
    logger.info(f"   Overall success rate: {total_files}/{total_requested} ({(total_files/total_requested*100):.1f}%)" if total_requested > 0 else "   Overall success rate: 0%")
    logger.info(f"   Total duration: {format_duration(total_duration)} ({total_hours:.2f} hours)")
    logger.info(f"   Files longer than 1 minute: {total_longer}")
    logger.info(f"   Files shorter than 1 minute: {total_shorter}")
    
    if all_durations:
        avg_duration = statistics.mean(all_durations)
        std_duration = statistics.stdev(all_durations) if len(all_durations) > 1 else 0
        logger.info(f"   Average duration: {avg_duration:.2f} seconds")
        logger.info(f"   Standard deviation: {std_duration:.2f} seconds")
    
    logger.info(f"📋 PER-BATCH BREAKDOWN:")
    for batch_stat in batch_stats:
        batch_num = batch_stat['batch']
        analysis = batch_stat['analysis']
        batch_hours = analysis['total_duration'] / 3600
        requested = batch_stat['requested_conversations']
        available = batch_stat['available_tokens']
        generated = analysis['total_files']
        
        logger.info(f"   Batch {batch_num}: {requested}→{available}→{generated} (req→tokens→wav), {format_duration(analysis['total_duration'])} ({batch_hours:.2f}h)")
    
    logger.info("🎉 All batches completed!")

if __name__ == "__main__":
    main()