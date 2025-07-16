#!/usr/bin/env python3
"""
Test script for the conversation orchestrator.

This script runs a small test to validate the orchestrator functionality.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def test_token_generation():
    """Test token generation with a small batch."""
    print("🧪 Testing token generation...")
    
    cmd = [
        "python", "conversation_orchestrator.py",
        "--batch-size", "3",
        "--batch-number", "999",  # Use test batch number
        "--tokens-only",
        "--log-level", "INFO"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ Token generation test passed")
            
            # Check if tokens were created
            tokens_dir = Path("tokens")
            test_tokens = [
                tokens_dir / "token_batch999_0_maya.json",
                tokens_dir / "token_batch999_0_miles.json",
                tokens_dir / "token_batch999_1_maya.json",
                tokens_dir / "token_batch999_1_miles.json",
                tokens_dir / "token_batch999_2_maya.json",
                tokens_dir / "token_batch999_2_miles.json",
            ]
            
            created_tokens = [t for t in test_tokens if t.exists()]
            print(f"📊 Created {len(created_tokens)}/6 expected tokens")
            
            if len(created_tokens) >= 4:  # At least 2 pairs
                print("✅ Sufficient tokens created for testing")
                return True
            else:
                print("❌ Insufficient tokens created")
                return False
        else:
            print(f"❌ Token generation failed with code {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Token generation test timed out")
        return False
    except Exception as e:
        print(f"❌ Token generation test failed: {e}")
        return False

def test_conversation_launch():
    """Test conversation launch with existing tokens."""
    print("\n🧪 Testing conversation launch...")
    
    cmd = [
        "python", "conversation_orchestrator.py",
        "--batch-size", "2",  # Only test 2 conversations
        "--batch-number", "999",
        "--conversations-only",
        "--log-level", "INFO"
    ]
    
    try:
        # Start the process but don't wait for completion (conversations take 5+ minutes)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait a bit to see if it starts successfully
        time.sleep(10)
        
        if process.poll() is None:
            print("✅ Conversations launched successfully (still running)")
            
            # Terminate the test conversations
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            
            print("🛑 Test conversations terminated")
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Conversation launch failed with code {process.returncode}")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Conversation launch test failed: {e}")
        return False

def cleanup_test_files():
    """Clean up test files."""
    print("\n🧹 Cleaning up test files...")
    
    # Remove test tokens
    tokens_dir = Path("tokens")
    if tokens_dir.exists():
        for token_file in tokens_dir.glob("token_batch999_*.json"):
            token_file.unlink()
            print(f"  Removed {token_file}")
    
    # Remove test conversations
    conversations_dir = Path("conversations")
    if conversations_dir.exists():
        for conv_file in conversations_dir.glob("*batch999*.wav"):
            conv_file.unlink()
            print(f"  Removed {conv_file}")
    
    print("✅ Cleanup complete")

def main():
    """Run orchestrator tests."""
    print("🎭 Conversation Orchestrator Test Suite")
    print("=" * 50)
    
    # Change to the script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    success = True
    
    try:
        # Test 1: Token Generation
        if not test_token_generation():
            success = False
        
        # Test 2: Conversation Launch (only if tokens were created)
        if success:
            if not test_conversation_launch():
                success = False
        
    finally:
        # Always cleanup
        cleanup_test_files()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! Orchestrator is ready for use.")
        print("\nNext steps:")
        print("1. Run: python conversation_orchestrator.py --batch-size 50 --tokens-only")
        print("2. Then: python conversation_orchestrator.py --batch-size 50 --conversations-only")
    else:
        print("❌ Some tests failed. Check the output above for details.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())