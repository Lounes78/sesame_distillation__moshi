#!/usr/bin/env python3
"""
Test script for audio prompt injection functionality
"""

import os
import sys
import logging
from audio_processing import load_audio_prompt, create_fallback_prompt, CONFIG

def test_prompt_loading():
    """Test the audio prompt loading functionality."""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🧪 Testing Audio Prompt System")
    print("=" * 50)
    
    # Test 1: Check if default prompt exists
    default_prompt = CONFIG["default_prompt_file"]
    print(f"Default prompt path: {default_prompt}")
    
    if os.path.exists(default_prompt):
        print("✅ Default prompt file found")
        try:
            chunks = load_audio_prompt(default_prompt)
            print(f"✅ Successfully loaded {len(chunks)} chunks from default prompt")
            
            # Analyze first chunk
            if chunks:
                chunk_size = len(chunks[0])
                expected_size = CONFIG["target_chunk_size"] * 2  # 2 bytes per int16 sample
                print(f"   First chunk size: {chunk_size} bytes")
                print(f"   Expected size: {expected_size} bytes")
                print(f"   ✅ Chunk size correct" if chunk_size == expected_size else f"   ❌ Chunk size mismatch")
                
        except Exception as e:
            print(f"❌ Failed to load default prompt: {e}")
    else:
        print("⚠️  Default prompt file not found")
    
    # Test 2: Test fallback prompt
    print("\n📝 Testing fallback prompt...")
    try:
        fallback_chunks = create_fallback_prompt()
        print(f"✅ Created fallback prompt with {len(fallback_chunks)} chunks")
        
        if fallback_chunks:
            chunk_size = len(fallback_chunks[0])
            expected_size = CONFIG["target_chunk_size"] * 2
            print(f"   Fallback chunk size: {chunk_size} bytes")
            print(f"   ✅ Fallback chunk size correct" if chunk_size == expected_size else f"   ❌ Fallback chunk size mismatch")
            
    except Exception as e:
        print(f"❌ Failed to create fallback prompt: {e}")
    
    # Test 3: Test various file scenarios
    print("\n🔧 Testing error handling...")
    
    # Test non-existent file
    try:
        load_audio_prompt("non_existent_file.wav")
        print("❌ Should have failed for non-existent file")
    except FileNotFoundError:
        print("✅ Correctly handled non-existent file")
    except Exception as e:
        print(f"⚠️  Unexpected error for non-existent file: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Prompt System Configuration:")
    print(f"   Target chunk size: {CONFIG['target_chunk_size']} samples")
    print(f"   Conversation rate: {CONFIG['conversation_rate']} Hz")
    print(f"   Default prompt: {CONFIG['default_prompt_file']}")
    print(f"   Prompt agent: {CONFIG['prompt_agent']}")
    print(f"   Record prompt: {CONFIG['record_prompt']}")
    
    return True

if __name__ == "__main__":
    test_prompt_loading()