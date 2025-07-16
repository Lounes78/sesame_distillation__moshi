#!/usr/bin/env python3
"""
Prompt Generation Script

Generates audio prompts using TTS for all entries in the prompts.csv file.
Uses the TTS server to convert text prompts to audio files.
"""

import csv
import os
import requests
import sys
import time
from pathlib import Path

def check_tts_server():
    """Check if the TTS server is running and accessible"""
    try:
        response = requests.get("http://127.0.0.1:8765/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def generate_audio(prompt_text, voice="tara", output_file="output.wav"):
    """Generate audio from text using the TTS server"""
    url = "http://127.0.0.1:8765/predict"
    
    params = {
        "prompt": prompt_text,
        "voice": voice
    }
    
    try:
        print(f"  Generating audio for: '{prompt_text[:50]}...'")
        response = requests.post(url, params=params, stream=True, timeout=30)
        response.raise_for_status()
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"  ✅ Audio saved to {output_file}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error generating audio: {e}")
        return False

def load_prompts_csv(csv_path):
    """Load prompts from CSV file"""
    prompts = []
    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                prompts.append(row)
        return prompts
    except FileNotFoundError:
        print(f"❌ CSV file not found: {csv_path}")
        return []
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return []

def update_csv_with_paths(csv_path, updated_prompts):
    """Update the CSV file with new audio paths and wav_exists status"""
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['prompt_id', 'text', 'audio_path', 'topic', 'voice', 'wav_exists', 'usage_count']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for prompt in updated_prompts:
                writer.writerow(prompt)
        print(f"✅ Updated CSV file: {csv_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to update CSV: {e}")
        return False

def update_single_prompt_in_csv(csv_path, prompt_id, wav_exists_status):
    """Update a single prompt's wav_exists status in the CSV file"""
    try:
        # Read all prompts
        prompts = load_prompts_csv(csv_path)
        
        # Update the specific prompt
        for prompt in prompts:
            if int(prompt['prompt_id']) == int(prompt_id):
                prompt['wav_exists'] = wav_exists_status
                break
        
        # Write back to CSV
        return update_csv_with_paths(csv_path, prompts)
    except Exception as e:
        print(f"❌ Failed to update single prompt in CSV: {e}")
        return False

def generate_all_prompts(csv_path="prompts/prompts.csv", force_regenerate=False):
    """Generate audio files for all prompts in the CSV with topic_id_voice naming"""
    
    # Check TTS server
    print("🔍 Checking TTS server...")
    if not check_tts_server():
        print("❌ TTS server is not running or not responding")
        print("   Please start the TTS server at http://127.0.0.1:8765")
        return False
    
    print("✅ TTS server is running")
    
    # Load prompts
    print(f"📖 Loading prompts from {csv_path}...")
    prompts = load_prompts_csv(csv_path)
    
    if not prompts:
        print("❌ No prompts found or failed to load CSV")
        return False
    
    print(f"📝 Found {len(prompts)} prompts to process")
    
    # Filter prompts that need generation
    prompts_to_generate = []
    prompts_already_exist = 0
    
    for prompt in prompts:
        wav_exists = prompt.get('wav_exists', 'false').lower() == 'true'
        if wav_exists and not force_regenerate:
            prompts_already_exist += 1
        else:
            prompts_to_generate.append(prompt)
    
    print(f"📝 Prompts already generated: {prompts_already_exist}")
    print(f"📝 Prompts to generate: {len(prompts_to_generate)}")
    
    # Generate audio for each prompt and update CSV immediately
    success_count = prompts_already_exist
    failed_count = 0
    
    for i, prompt in enumerate(prompts_to_generate, 1):
        prompt_id = prompt['prompt_id']
        text = prompt['text']
        voice = prompt.get('voice', 'tara')
        topic = prompt.get('topic', 'general')
        
        # Create new filename: topic_id_voice.wav
        new_filename = f"{topic}_{prompt_id}_{voice}.wav"
        new_audio_path = f"prompts/{new_filename}"
        
        print(f"\n🎙️ [{i}/{len(prompts_to_generate)}] Processing prompt {prompt_id} ({topic}):")
        print(f"  📁 Target file: {new_audio_path}")
        
        # Check if file already exists (file system check)
        if os.path.exists(new_audio_path) and not force_regenerate:
            print(f"  ⏭️  Audio file already exists: {new_audio_path}")
            # Update CSV immediately
            if update_single_prompt_in_csv(csv_path, prompt_id, 'true'):
                print(f"  ✅ Updated CSV: wav_exists=true for prompt {prompt_id}")
                success_count += 1
            else:
                print(f"  ❌ Failed to update CSV for prompt {prompt_id}")
                failed_count += 1
        else:
            # Generate audio
            if generate_audio(text, voice, new_audio_path):
                # Update CSV immediately after successful generation
                if update_single_prompt_in_csv(csv_path, prompt_id, 'true'):
                    print(f"  ✅ Generated audio and updated CSV: wav_exists=true for prompt {prompt_id}")
                    success_count += 1
                else:
                    print(f"  ⚠️  Audio generated but failed to update CSV for prompt {prompt_id}")
                    success_count += 1  # Still count as success since audio was generated
                # Small delay to avoid overwhelming the server
                time.sleep(0.5)
            else:
                # Update CSV to mark as failed
                if update_single_prompt_in_csv(csv_path, prompt_id, 'false'):
                    print(f"  ❌ Failed to generate audio, updated CSV: wav_exists=false for prompt {prompt_id}")
                else:
                    print(f"  ❌ Failed to generate audio and failed to update CSV for prompt {prompt_id}")
                failed_count += 1
    
    print(f"\n🎉 Generation complete!")
    print(f"   ✅ Successfully processed: {success_count}/{len(prompts)} prompts")
    print(f"   📁 Already existed: {prompts_already_exist} prompts")
    print(f"   🆕 Newly generated: {success_count - prompts_already_exist} prompts")
    
    if failed_count > 0:
        print(f"   ⚠️  Failed to generate: {failed_count} prompts")
        return False
    
    return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate audio prompts using TTS")
    parser.add_argument("--csv", default="prompts/prompts.csv", 
                       help="Path to prompts CSV file (default: prompts/prompts.csv)")
    parser.add_argument("--force", action="store_true", 
                       help="Force regeneration of existing audio files")
    parser.add_argument("--prompt-id", type=int, 
                       help="Generate audio for specific prompt ID only")
    
    args = parser.parse_args()
    
    print("🎭 Prompt Audio Generator")
    print("=" * 40)
    
    # Change to the script's directory to ensure relative paths work
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    if args.prompt_id:
        # Generate single prompt
        prompts = load_prompts_csv(args.csv)
        target_prompt = None
        
        for prompt in prompts:
            if int(prompt['prompt_id']) == args.prompt_id:
                target_prompt = prompt
                break
        
        if not target_prompt:
            print(f"❌ Prompt ID {args.prompt_id} not found in CSV")
            sys.exit(1)
        
        print(f"🎯 Generating single prompt: {args.prompt_id}")
        
        if not check_tts_server():
            print("❌ TTS server is not running")
            sys.exit(1)
        
        # Create filename with topic_id_voice format
        topic = target_prompt.get('topic', 'general')
        voice = target_prompt.get('voice', 'tara')
        prompt_id = target_prompt['prompt_id']
        new_filename = f"{topic}_{prompt_id}_{voice}.wav"
        new_audio_path = f"prompts/{new_filename}"
        
        print(f"📁 Target file: {new_audio_path}")
        
        success = generate_audio(
            target_prompt['text'],
            voice,
            new_audio_path
        )
        
        if success:
            # Update CSV immediately with new path and wav_exists status
            if update_single_prompt_in_csv(args.csv, args.prompt_id, 'true'):
                print("✅ Single prompt generation completed and CSV updated!")
            else:
                print("⚠️  Audio generated but failed to update CSV")
        else:
            # Update CSV to mark as failed
            update_single_prompt_in_csv(args.csv, args.prompt_id, 'false')
            print("❌ Failed to generate prompt")
            sys.exit(1)
    else:
        # Generate all prompts
        success = generate_all_prompts(args.csv, args.force)
        
        if not success:
            print("❌ Some prompts failed to generate")
            sys.exit(1)
        
        print("✅ All prompts generated successfully!")

if __name__ == "__main__":
    main()