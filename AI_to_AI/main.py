#!/usr/bin/env python3
"""
Simple batch orchestrator to run 10 batches of conversation_orchestrator.py
"""

import os
import time
import subprocess
import signal
import glob
import wave
import statistics
import logging
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

def format_duration(seconds):
    """Format duration in HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def main():
    logger.info("🚀 Starting 10 batches of conversation orchestrator")
    
    batch_stats = []
    
    for batch_num in range(10):
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
            "--batch-size", "50",
            "--batch-number", str(batch_num),
            "--tokens-only"
        ]
        
        try:
            result = subprocess.run(token_cmd, check=True, capture_output=True, text=True)
            logger.info("✅ Token generation completed")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Token generation failed: {e}")
            continue
        
        # Step 3: Launch conversations
        logger.info(f"🎭 Launching conversations for batch {batch_num}")
        conv_cmd = [
            "python", "conversation_orchestrator.py",
            "--batch-size", "50",
            "--batch-number", str(batch_num),
            "--conversations-only"
        ]
        
        try:
            # Start conversations in background
            conv_process = subprocess.Popen(conv_cmd)
            logger.info(f"✅ Conversations launched (PID: {conv_process.pid})")
            
            # Wait 5 minutes
            logger.info("⏰ Waiting 5 minutes for 50 conversations...")
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
        batch_analysis = analyze_wav_files("conversations")
        batch_stats.append({
            'batch': batch_num,
            'wav_count': wav_count,
            'analysis': batch_analysis
        })
        
        # Print batch summary
        total_hours = batch_analysis['total_duration'] / 3600
        logger.info(f"📊 BATCH {batch_num} SUMMARY:")
        logger.info(f"   WAV files: {wav_count}")
        logger.info(f"   Total duration: {format_duration(batch_analysis['total_duration'])} ({total_hours:.2f} hours)")
        logger.info(f"   Files >1 min: {batch_analysis['longer_than_minute']}")
        logger.info(f"   Files <1 min: {batch_analysis['shorter_than_minute']}")
    
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
    
    for batch_stat in batch_stats:
        analysis = batch_stat['analysis']
        total_files += analysis['total_files']
        total_duration += analysis['total_duration']
        total_longer += analysis['longer_than_minute']
        total_shorter += analysis['shorter_than_minute']
        all_durations.extend(analysis['durations'])
    
    total_hours = total_duration / 3600
    
    logger.info(f"📊 OVERALL SUMMARY:")
    logger.info(f"   Total batches: 10")
    logger.info(f"   Total WAV files: {total_files}")
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
        logger.info(f"   Batch {batch_num}: {analysis['total_files']} files, {format_duration(analysis['total_duration'])} ({batch_hours:.2f}h)")
    
    logger.info("🎉 All batches completed!")

if __name__ == "__main__":
    main()