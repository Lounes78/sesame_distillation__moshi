#!/usr/bin/env python3
"""
Configurable batch orchestrator to run multiple batches of conversation_orchestrator.py
with customizable batch sizes and number of batches.
Includes VPN rotation to prevent IP blocking.
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
import getpass
import random
from datetime import datetime
from pathlib import Path



# to force the program to go through the vpn tunnel
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('ALL_PROXY', None)



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

# Global variable to store sudo password
SUDO_PASSWORD = None

def get_sudo_password():
    """Prompt for sudo password at the beginning of the script."""
    global SUDO_PASSWORD
    if SUDO_PASSWORD is None:
        print("🔐 VPN rotation requires sudo privileges for OpenVPN management.")
        SUDO_PASSWORD = getpass.getpass("Please enter your sudo password: ")
    return SUDO_PASSWORD

def get_available_vpn_configs():
    """Get list of available VPN configuration files."""
    vpn_config_dir = Path("/mnt/nas/KITT/DISTILLATION/VPN_config")
    vpn_configs = list(vpn_config_dir.glob("*.ovpn"))
    
    if not vpn_configs:
        logger.error("❌ No VPN configuration files found in VPN_config directory")
        return []
    
    logger.info(f"🌐 Found {len(vpn_configs)} VPN configurations:")
    for config in vpn_configs:
        logger.info(f"   📁 {config.name}")
    
    return vpn_configs

def kill_all_openvpn_processes():
    """Kill all existing OpenVPN processes."""
    try:
        logger.info("🔪 Killing all existing OpenVPN processes...")
        
        # Use sudo to kill all openvpn processes
        sudo_password = get_sudo_password()
        kill_cmd = f"echo '{sudo_password}' | sudo -S pkill -f openvpn"
        
        result = subprocess.run(
            kill_cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("✅ All OpenVPN processes killed successfully")
        else:
            # pkill returns 1 if no processes found, which is fine
            if "no process found" in result.stderr.lower() or result.returncode == 1:
                logger.info("ℹ️ No existing OpenVPN processes found")
            else:
                logger.warning(f"⚠️ pkill returned code {result.returncode}: {result.stderr}")
        
        # Wait a moment for processes to fully terminate
        time.sleep(2)
        
    except Exception as e:
        logger.error(f"❌ Error killing OpenVPN processes: {e}")

def start_vpn_connection(vpn_config_path):
    """Start a new VPN connection with the specified config."""
    try:
        logger.info(f"🌐 Starting VPN connection: {vpn_config_path.name}")
        
        sudo_password = get_sudo_password()
        
        # Start OpenVPN in background
        vpn_cmd = f"echo '{sudo_password}' | sudo -S openvpn --config {vpn_config_path} --daemon"
        
        result = subprocess.run(
            vpn_cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("✅ VPN connection started successfully")
            
            # Wait for VPN to establish connection
            logger.info("⏳ Waiting for VPN connection to establish...")
            time.sleep(10)
            
            # Verify new IP
            try:
                import requests
                ip_response = requests.get('https://api.ipify.org', timeout=10)
                new_ip = ip_response.text.strip()
                logger.info(f"🌍 New public IP: {new_ip}")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Could not verify new IP: {e}")
                return True  # Assume VPN is working
                
        else:
            logger.error(f"❌ Failed to start VPN: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error starting VPN connection: {e}")
        return False

def switch_vpn_for_batch(batch_number, vpn_configs):
    """Switch to a different VPN configuration for the given batch."""
    if not vpn_configs:
        logger.warning("⚠️ No VPN configurations available, continuing without VPN rotation")
        return True
    
    # Select VPN config based on batch number (rotate through available configs)
    config_index = batch_number % len(vpn_configs)
    selected_config = vpn_configs[config_index]
    
    logger.info(f"🔄 Switching VPN for batch {batch_number}")
    logger.info(f"📍 Selected VPN: {selected_config.name} ({config_index + 1}/{len(vpn_configs)})")
    
    # Kill existing VPN connections
    kill_all_openvpn_processes()
    
    # Start new VPN connection
    success = start_vpn_connection(selected_config)
    
    if success:
        logger.info(f"✅ VPN rotation complete for batch {batch_number}")
    else:
        logger.error(f"❌ VPN rotation failed for batch {batch_number}")
    
    return success

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
    parser = argparse.ArgumentParser(description='Run batch orchestrator for AI-to-AI conversations with VPN rotation')
    parser.add_argument('--start-batch', type=int, default=0,
                       help='Starting batch number (default: 0)')
    parser.add_argument('--end-batch', type=int, default=9,
                       help='Ending batch number (default: 9)')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Number of conversations per batch (default: 50)')
    parser.add_argument('--num-batches', type=int, default=None,
                       help='Number of batches to run (overrides end-batch if specified)')
    parser.add_argument('--no-vpn-rotation', action='store_true',
                       help='Disable VPN rotation between batches')
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
    
    # Initialize VPN rotation if enabled
    vpn_configs = []
    if not args.no_vpn_rotation:
        logger.info("🌐 Initializing VPN rotation system...")
        vpn_configs = get_available_vpn_configs()
        if vpn_configs:
            logger.info(f"✅ VPN rotation enabled with {len(vpn_configs)} configurations")
            # Prompt for sudo password once at the beginning
            get_sudo_password()
        else:
            logger.warning("⚠️ No VPN configs found, continuing without VPN rotation")
    else:
        logger.info("🚫 VPN rotation disabled by user")
    
    batch_stats = []
    
    for batch_num in range(args.start_batch, args.end_batch + 1):
        logger.info(f"{'='*60}")
        logger.info(f"🎯 BATCH {batch_num} STARTING")
        logger.info(f"{'='*60}")
        
        # Step 1: Switch VPN for this batch (if enabled)
        if vpn_configs:
            logger.info(f"🔄 Step 1: VPN Rotation for batch {batch_num}")
            vpn_success = switch_vpn_for_batch(batch_num, vpn_configs)
            if not vpn_success:
                logger.error(f"❌ VPN rotation failed for batch {batch_num}, continuing anyway...")
            else:
                logger.info("✅ VPN rotation successful, proceeding with batch")
        
        # Step 2: Clean tokens directory
        logger.info(f"🧹 Step 2: Cleaning tokens directory for batch {batch_num}")
        clean_tokens_directory()
        
        # Step 3: Generate tokens
        logger.info(f"🔑 Step 3: Generating tokens for batch {batch_num}")
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
        
        # Step 4: Launch conversations
        logger.info(f"🎭 Step 4: Launching conversations for batch {batch_num}")
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
        
        # Step 5: Analyze batch audio
        logger.info(f"📊 Step 5: Analyzing batch {batch_num} results")
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
    
    # Cleanup: Kill VPN processes if we used VPN rotation
    if vpn_configs:
        logger.info("🧹 Cleaning up VPN connections...")
        kill_all_openvpn_processes()
        logger.info("✅ VPN cleanup complete")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("⚠️ Script interrupted by user")
        # Try to cleanup VPN processes on interrupt
        try:
            kill_all_openvpn_processes()
            logger.info("✅ VPN cleanup complete")
        except:
            pass
    except Exception as e:
        logger.error(f"💥 Script failed: {e}")
        # Try to cleanup VPN processes on error
        try:
            kill_all_openvpn_processes()
            logger.info("✅ VPN cleanup complete")
        except:
            pass