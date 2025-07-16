#!/usr/bin/env python3
"""
Conversation Orchestrator for Large-Scale AI-to-AI Conversations

This script handles:
1. Token generation with proper naming scheme
2. Batch conversation management with parameter variations
3. Integration with existing two_phase_conversation.py
"""

import os
import sys
import time
import random
import logging
import subprocess
import threading
from datetime import datetime
import numpy as np
import argparse
from pathlib import Path

# Add parent directory to path to import sesame_ai
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sesame_ai import SesameAI, TokenManager



os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('ALL_PROXY', None)

import requests
response = requests.get('https://api.ipify.org')
print("Public IP via Python:", response.text)





# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('orchestrator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('orchestrator')


class ConversationOrchestrator:
    """
    Orchestrates large-scale AI-to-AI conversation generation.
    
    Features:
    - Token pre-generation with proper naming
    - Batch conversation management
    - Parameter variation (gaussian distributions)
    - Conversation naming scheme
    """
    
    def __init__(self, batch_size=50, batch_number=0):
        self.batch_size = batch_size
        self.batch_number = batch_number
        self.tokens_dir = Path("tokens")
        self.conversations_dir = Path("conversations")
        
        # Create directories
        self.tokens_dir.mkdir(exist_ok=True)
        self.conversations_dir.mkdir(exist_ok=True)
        
        # Statistics
        self.stats = {
            'tokens_generated': 0,
            'tokens_failed': 0,
            'conversations_launched': 0,
            'conversations_failed': 0
        }
        
        logger.info(f"🚀 Orchestrator initialized - Batch {batch_number}, Size {batch_size}")
    
    def generate_token_pool(self):
        """
        Generate token pairs for the batch with proper naming scheme.
        
        Token naming: token_batch{batch_number}_{pair_id}_{maya|miles}.json
        """
        logger.info(f"🔑 Starting token generation for batch {self.batch_number}")
        logger.info(f"📊 Target: {self.batch_size} token pairs ({self.batch_size * 2} total tokens)")
        
        successful_pairs = 0
        failed_attempts = 0
        
        for pair_id in range(self.batch_size):
            try:
                logger.info(f"Creating token pair {pair_id + 1}/{self.batch_size}")
                
                # Generate Maya token
                maya_token_file = self.tokens_dir / f"token_batch{self.batch_number}_{pair_id}_maya.json"
                maya_success = self._generate_single_token(maya_token_file, "Maya", pair_id)
                
                if not maya_success:
                    failed_attempts += 1
                    continue
                
                # Small delay between Maya and Miles
                delay = random.uniform(0.5, 1.0)
                logger.debug(f"  ⏱️ Inter-token delay: {delay:.1f}s")
                time.sleep(delay)
                
                # Generate Miles token
                miles_token_file = self.tokens_dir / f"token_batch{self.batch_number}_{pair_id}_miles.json"
                miles_success = self._generate_single_token(miles_token_file, "Miles", pair_id)
                
                if not miles_success:
                    failed_attempts += 1
                    # Clean up Maya token if Miles failed
                    if maya_token_file.exists():
                        maya_token_file.unlink()
                        logger.warning(f"  🧹 Cleaned up Maya token due to Miles failure")
                    continue
                
                successful_pairs += 1
                self.stats['tokens_generated'] += 2
                logger.info(f"  ✅ Token pair {pair_id} completed successfully")
                
                # Progressive delay between pairs
                pair_delay = self._calculate_pair_delay(pair_id)
                logger.debug(f"  ⏱️ Pair delay: {pair_delay:.1f}s")
                time.sleep(pair_delay)
                
            except Exception as e:
                logger.error(f"  ❌ Failed to create token pair {pair_id}: {e}")
                failed_attempts += 1
                self.stats['tokens_failed'] += 2
                
                # Handle rate limiting
                if "429" in str(e) or "rate" in str(e).lower():
                    logger.warning("  🚨 Rate limit detected - waiting 30 seconds...")
                    time.sleep(30)
                else:
                    time.sleep(5)  # General error delay
        
        # Final statistics
        logger.info(f"\n📊 Token generation complete for batch {self.batch_number}:")
        logger.info(f"  ✅ Successful pairs: {successful_pairs}")
        logger.info(f"  ❌ Failed attempts: {failed_attempts}")
        logger.info(f"  📁 Tokens saved in: {self.tokens_dir}")
        
        return successful_pairs >= (self.batch_size * 0.8)  # 80% success rate required
    
    def _generate_single_token(self, token_file, agent_name, pair_id):
        """Generate a single token with error handling."""
        try:
            token_manager = TokenManager(SesameAI(), str(token_file))
            token = token_manager.get_valid_token()
            logger.debug(f"    ✅ {agent_name} token {pair_id} created")
            return True
        except Exception as e:
            logger.error(f"    ❌ {agent_name} token {pair_id} failed: {e}")
            return False
    
    def _calculate_pair_delay(self, pair_id):
        """Calculate progressive delay between token pairs."""
        if pair_id < 10:
            return random.uniform(1, 2)      # 1-2s for first 10
        elif pair_id < 25:
            return random.uniform(2, 3)      # 2-3s for next 15
        else:
            return random.uniform(3, 5)      # 3-5s for remaining
    
    def run_single_batch(self):
        """
        Run a single batch of conversations with parameter variations.
        
        Parameter variations:
        - 25% no prompt
        - Processing time: gaussian around 15s (10-20s range)
        - Stabilization time: gaussian around 10s (7-15s range)
        - Prompt target: 70% both, 15% maya, 15% miles
        """
        logger.info(f"🎭 Starting conversation batch {self.batch_number}")
        
        # Check if we have enough tokens
        available_pairs = self._count_available_token_pairs()
        if available_pairs < self.batch_size:
            logger.error(f"❌ Insufficient token pairs: {available_pairs}/{self.batch_size}")
            return False
        
        logger.info(f"📊 Launching {self.batch_size} conversations with parameter variations")
        
        # Launch conversations with staggered timing
        processes = []
        for conv_id in range(self.batch_size):
            try:
                # Generate conversation parameters
                params = self._generate_conversation_parameters(conv_id)
                
                # Create conversation filename
                filename = self._generate_conversation_filename(conv_id, params)
                
                # Build command
                cmd = self._build_conversation_command(conv_id, filename, params)
                
                # Launch conversation
                logger.info(f"🚀 Launching conversation {conv_id + 1}/{self.batch_size}: {filename}")
                logger.debug(f"   Command: {' '.join(cmd)}")
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=os.path.dirname(__file__)
                )
                processes.append((process, conv_id, filename))
                
                self.stats['conversations_launched'] += 1
                
                # Small delay between launches
                launch_delay = random.uniform(0.2, 0.5)
                time.sleep(launch_delay)
                
            except Exception as e:
                logger.error(f"❌ Failed to launch conversation {conv_id}: {e}")
                self.stats['conversations_failed'] += 1
        
        logger.info(f"✅ Batch launch complete: {len(processes)} conversations started")
        
        # Monitor processes (optional - for logging purposes)
        self._monitor_conversations(processes)
        
        return True
    
    def _count_available_token_pairs(self):
        """Count available token pairs for the current batch."""
        count = 0
        for pair_id in range(self.batch_size):
            maya_token = self.tokens_dir / f"token_batch{self.batch_number}_{pair_id}_maya.json"
            miles_token = self.tokens_dir / f"token_batch{self.batch_number}_{pair_id}_miles.json"
            
            if maya_token.exists() and miles_token.exists():
                count += 1
        
        return count
    
    def _generate_conversation_parameters(self, conv_id):
        """Generate conversation parameters with specified distributions."""
        params = {}
        
        # Prompt configuration (25% no prompt)
        params['use_prompt'] = random.random() > 0.25
        
        if params['use_prompt']:
            # Select random prompt ID (1-80 based on CSV)
            params['prompt_id'] = random.randint(1, 80)
            
            # Prompt target distribution (70% both, 15% maya, 15% miles)
            rand = random.random()
            if rand < 0.70:
                params['prompt_target'] = 'both'
            elif rand < 0.85:
                params['prompt_target'] = 'maya'
            else:
                params['prompt_target'] = 'miles'
        else:
            params['prompt_id'] = None
            params['prompt_target'] = 'both'  # Default, but won't be used
        
        # Processing time: gaussian around 15s (10-20s range)
        params['processing_time'] = int(np.clip(
            np.random.normal(15, 2), 10, 20
        ))
        
        # Stabilization time: gaussian around 10s (7-15s range)
        params['stabilization_time'] = int(np.clip(
            np.random.normal(10, 1.5), 7, 15
        ))
        
        return params
    
    def _generate_conversation_filename(self, conv_id, params):
        """
        Generate conversation filename based on parameters.
        
        Format: maya_miles_{prompted|not}_{prompt_id}_{processing_time}_{stabilization_time}_{prompt_target}
        """
        if params['use_prompt']:
            prompt_part = f"prompted_{params['prompt_id']}"
        else:
            prompt_part = "not"
        
        filename = (
            f"maya_miles_{prompt_part}_{params['processing_time']}"
            f"_{params['stabilization_time']}_{params['prompt_target']}"
            f"_batch{self.batch_number}_{conv_id}.wav"
        )
        
        return filename
    
    def _build_conversation_command(self, conv_id, filename, params):
        """Build the command to launch a conversation."""
        # Token files for this conversation
        maya_token = str(self.tokens_dir / f"token_batch{self.batch_number}_{conv_id}_maya.json")
        miles_token = str(self.tokens_dir / f"token_batch{self.batch_number}_{conv_id}_miles.json")
        
        # Base command
        cmd = [
            "python", "two_phase_conversation.py",
            "--filename", str(self.conversations_dir / filename),
            "--maya-token", maya_token,
            "--miles-token", miles_token,
            "--processing-time", str(params['processing_time']),
            "--stabilization-time", str(params['stabilization_time']),
            "--no-record-prompt",
            "--no-playback",  # Disable audio playback for batch processing
        ]
        
        # Add prompt-related arguments
        if params['use_prompt']:
            cmd.extend([
                "--prompt-id", str(params['prompt_id']),
                "--prompt-target", params['prompt_target']
            ])
        else:
            cmd.append("--no-prompt")
        
        return cmd
    
    def _validate_token_pair(self, conv_id):
        """Validate that both tokens exist for a conversation."""
        maya_token = self.tokens_dir / f"token_batch{self.batch_number}_{conv_id}_maya.json"
        miles_token = self.tokens_dir / f"token_batch{self.batch_number}_{conv_id}_miles.json"
        
        return maya_token.exists() and miles_token.exists()
    
    def _monitor_conversations(self, processes):
        """Monitor conversation processes (basic implementation)."""
        logger.info(f"👀 Monitoring {len(processes)} conversation processes...")
        
        # This is a basic implementation - in production you might want more sophisticated monitoring
        active_count = len(processes)
        
        def check_process_status():
            nonlocal active_count
            while active_count > 0:
                time.sleep(30)  # Check every 30 seconds
                still_active = 0
                
                for process, conv_id, filename in processes:
                    if process.poll() is None:  # Still running
                        still_active += 1
                    else:
                        # Process finished
                        return_code = process.returncode
                        if return_code == 0:
                            logger.info(f"✅ Conversation {conv_id} completed successfully: {filename}")
                        else:
                            logger.warning(f"⚠️ Conversation {conv_id} finished with code {return_code}: {filename}")
                
                if still_active != active_count:
                    logger.info(f"📊 Active conversations: {still_active}/{len(processes)}")
                    active_count = still_active
        
        # Start monitoring in background thread
        monitor_thread = threading.Thread(target=check_process_status, daemon=True)
        monitor_thread.start()
    
    def print_statistics(self):
        """Print orchestrator statistics."""
        logger.info("\n📊 Orchestrator Statistics:")
        logger.info(f"  🔑 Tokens generated: {self.stats['tokens_generated']}")
        logger.info(f"  ❌ Token failures: {self.stats['tokens_failed']}")
        logger.info(f"  🎭 Conversations launched: {self.stats['conversations_launched']}")
        logger.info(f"  ❌ Conversation failures: {self.stats['conversations_failed']}")


def main():
    """Main orchestrator function."""
    parser = argparse.ArgumentParser(description="AI-to-AI Conversation Orchestrator")
    parser.add_argument("--batch-size", type=int, default=50,
                       help="Number of conversations per batch (default: 50)")
    parser.add_argument("--batch-number", type=int, default=0,
                       help="Batch number for token naming (default: 0)")
    parser.add_argument("--tokens-only", action="store_true",
                       help="Only generate tokens, don't run conversations")
    parser.add_argument("--conversations-only", action="store_true",
                       help="Only run conversations, skip token generation")
    parser.add_argument("--log-level", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help="Logging level")
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create orchestrator
    orchestrator = ConversationOrchestrator(
        batch_size=args.batch_size,
        batch_number=args.batch_number
    )
    
    logger.info("🎭 AI-to-AI Conversation Orchestrator")
    logger.info(f"📊 Batch {args.batch_number}, Size {args.batch_size}")
    logger.info(f"🎯 Mode: {'Tokens only' if args.tokens_only else 'Conversations only' if args.conversations_only else 'Full pipeline'}")
    
    try:
        # Step 1: Generate tokens (unless skipped)
        if not args.conversations_only:
            logger.info("\n🔑 PHASE 1: Token Generation")
            success = orchestrator.generate_token_pool()
            
            if not success:
                logger.error("❌ Token generation failed - aborting")
                return 1
            
            if args.tokens_only:
                logger.info("✅ Token generation complete - exiting (tokens-only mode)")
                orchestrator.print_statistics()
                return 0
        
        # Step 2: Run conversations (unless skipped)
        if not args.tokens_only:
            logger.info("\n🎭 PHASE 2: Conversation Batch")
            success = orchestrator.run_single_batch()
            
            if not success:
                logger.error("❌ Conversation batch failed")
                return 1
        
        # Final statistics
        orchestrator.print_statistics()
        logger.info("🎉 Orchestration complete!")
        return 0
        
    except KeyboardInterrupt:
        logger.info("⚠️ Orchestration interrupted by user")
        orchestrator.print_statistics()
        return 1
    except Exception as e:
        logger.error(f"💥 Orchestration failed: {e}", exc_info=True)
        orchestrator.print_statistics()
        return 1


if __name__ == "__main__":
    exit(main())