#!/usr/bin/env python3
"""
Two-Phase AI Conversation System

Phase 1: Both AIs process the prompt independently (no cross-feeding)
Phase 2: Enable cross-feeding for natural conversation between AIs

This creates more natural conversations where both AIs first understand
the topic before discussing it with each other.
"""

import os
import time
import logging
import numpy as np
import threading

from audio_processing import CONFIG, SCIPY_AVAILABLE, ProperStereoPlayer, ConversationRecorder, resample_audio, load_audio_prompt, create_fallback_prompt
from ai_agent import AIAgent
from prompt_manager import PromptManager, select_prompt

logger = logging.getLogger('sesame.two_phase')


class TwoPhaseConversationManager:
    """
    Manages a two-phase conversation between AI agents.
    
    Phase 1: Independent prompt processing (no cross-feeding)
    Phase 2: Connected conversation (cross-feeding enabled)
    """
    
    def __init__(self, maya_token="token.json", miles_token="token2.json", filename=None,
                 prompt_file=None, disable_prompt=False, prompt_processing_time=15,
                 prompt_id=None, random_prompt=False, prompt_topic=None, prompts_csv="prompts/prompts.csv",
                 stabilization_time=10):
        self.recorder = ConversationRecorder(filename=filename)
        self.maya = AIAgent("Maya", maya_token, self._handle_audio_response)
        self.miles = AIAgent("Miles", miles_token, self._handle_audio_response)
        self.running = False
        
        # Initialize proper stereo player
        self.audio_player = ProperStereoPlayer() if CONFIG["live_playback"] else None
        
        # Prompt configuration
        self.prompt_file = prompt_file
        self.disable_prompt = disable_prompt
        self.prompt_chunks = None
        self.prompt_processing_time = prompt_processing_time
        self.stabilization_time = stabilization_time
        
        # New prompt management system
        self.prompt_id = prompt_id
        self.random_prompt = random_prompt
        self.prompt_topic = prompt_topic
        self.prompts_csv = prompts_csv
        self.prompt_manager = PromptManager(prompts_csv)
        self.selected_prompt_info = None
        
        # Two-phase state management
        self.cross_feed_enabled = False
        self.phase_start_time = None
        self.current_phase = "INITIALIZATION"
        self.phase_lock = threading.Lock()
        
        self._load_prompt()

    def _load_prompt(self):
        """Load and process the audio prompt for conversation initiation."""
        print(f"🔍 DEBUG: _load_prompt called - disable_prompt={self.disable_prompt}")
        print(f"🔍 DEBUG: prompt_file={self.prompt_file}, prompt_id={self.prompt_id}, random_prompt={self.random_prompt}")
        
        if self.disable_prompt:
            print("🚫 DEBUG: Prompt disabled by --no-prompt flag, using fallback noise")
            logger.info("Prompt disabled by --no-prompt flag, using fallback noise")
            self.prompt_chunks = create_fallback_prompt()
            return
            
        try:
            selected_prompt_file = None
            
            # Priority 1: Direct file path (backward compatibility)
            if self.prompt_file:
                print(f"📁 DEBUG: Loading custom prompt file: {self.prompt_file}")
                logger.info(f"Loading custom prompt file: {self.prompt_file}")
                selected_prompt_file = self.prompt_file
                self.selected_prompt_info = f"Custom file: {self.prompt_file}"
                
            # Priority 2: Specific prompt ID from CSV
            elif self.prompt_id is not None:
                print(f"🎯 DEBUG: Loading prompt by ID: {self.prompt_id}")
                prompt = self.prompt_manager.get_prompt_by_id(self.prompt_id)
                if prompt:
                    selected_prompt_file = self.prompt_manager.get_prompt_file_path(prompt)
                    if selected_prompt_file:
                        self.selected_prompt_info = f"ID {prompt['prompt_id']}: {prompt['topic']} - {prompt['text'][:50]}..."
                        logger.info(f"Selected prompt ID {self.prompt_id}: {prompt['topic']}")
                    else:
                        print(f"❌ DEBUG: Audio file not found for prompt ID {self.prompt_id}")
                        logger.error(f"Audio file not found for prompt ID {self.prompt_id}")
                else:
                    print(f"❌ DEBUG: Prompt ID {self.prompt_id} not found in CSV")
                    logger.error(f"Prompt ID {self.prompt_id} not found in CSV")
                    
            # Priority 3: Random prompt selection
            elif self.random_prompt:
                print(f"🎲 DEBUG: Loading random prompt (topic filter: {self.prompt_topic})")
                prompt = self.prompt_manager.get_random_prompt(self.prompt_topic)
                if prompt:
                    selected_prompt_file = self.prompt_manager.get_prompt_file_path(prompt)
                    if selected_prompt_file:
                        self.selected_prompt_info = f"Random ID {prompt['prompt_id']}: {prompt['topic']} - {prompt['text'][:50]}..."
                        logger.info(f"Selected random prompt ID {prompt['prompt_id']}: {prompt['topic']}")
                    else:
                        print(f"❌ DEBUG: Audio file not found for random prompt ID {prompt['prompt_id']}")
                        logger.error(f"Audio file not found for random prompt ID {prompt['prompt_id']}")
                else:
                    print("❌ DEBUG: No random prompt available")
                    logger.error("No random prompt available")
                    
            # Priority 4: Default behavior - try CSV random, then fallback to original default
            else:
                print("🔍 DEBUG: No specific prompt requested, trying random from CSV")
                prompt = self.prompt_manager.get_random_prompt()
                if prompt:
                    selected_prompt_file = self.prompt_manager.get_prompt_file_path(prompt)
                    if selected_prompt_file:
                        self.selected_prompt_info = f"Default random ID {prompt['prompt_id']}: {prompt['topic']} - {prompt['text'][:50]}..."
                        logger.info(f"Selected default random prompt ID {prompt['prompt_id']}: {prompt['topic']}")
                    else:
                        print(f"❌ DEBUG: Audio file not found for default random prompt ID {prompt['prompt_id']}")
                        logger.error(f"Audio file not found for default random prompt ID {prompt['prompt_id']}")
                
                # Fallback to original default prompt file
                if not selected_prompt_file:
                    default_prompt = CONFIG["default_prompt_file"]
                    print(f"🔍 DEBUG: Trying original default prompt: {default_prompt}")
                    if os.path.exists(default_prompt):
                        selected_prompt_file = default_prompt
                        self.selected_prompt_info = f"Original default: {default_prompt}"
                        logger.info(f"Using original default prompt: {default_prompt}")
            
            # Load the selected prompt file
            if selected_prompt_file:
                print(f"📁 DEBUG: Loading selected prompt: {selected_prompt_file}")
                self.prompt_chunks = load_audio_prompt(selected_prompt_file)
                print(f"✅ DEBUG: Successfully loaded prompt: {self.selected_prompt_info}")
            else:
                print("🔀 DEBUG: No valid prompt found, using fallback")
                logger.info("No valid prompt found, using fallback")
                self.prompt_chunks = create_fallback_prompt()
                self.selected_prompt_info = "Fallback random noise"
                    
        except (FileNotFoundError, ValueError) as e:
            print(f"❌ DEBUG: Failed to load audio prompt: {e}")
            logger.warning(f"Failed to load audio prompt: {e}")
            logger.info("Using fallback random noise prompt")
            self.prompt_chunks = create_fallback_prompt()
            self.selected_prompt_info = "Fallback random noise (error)"

    def _inject_prompt_to_both(self):
        """Inject the audio prompt to BOTH AIs simultaneously."""
        print(f"🔍 DEBUG: _inject_prompt_to_both called - disable_prompt={self.disable_prompt}")
        
        if self.disable_prompt:
            print("🚫 DEBUG: Prompt injection SKIPPED due to --no-prompt flag")
            logger.info("Prompt injection skipped due to --no-prompt flag")
            return
            
        if not self.prompt_chunks:
            print("❌ DEBUG: No prompt chunks available!")
            logger.error("No prompt chunks available!")
            return

        print(f"🎙️ DEBUG: Injecting audio prompt to BOTH Maya and Miles ({len(self.prompt_chunks)} chunks)")
        logger.info(f"🎙️ Injecting audio prompt to BOTH Maya and Miles ({len(self.prompt_chunks)} chunks)")
        
        # Inject all prompt chunks to both AIs simultaneously
        for i, chunk in enumerate(self.prompt_chunks):
            self.maya.add_input_audio(chunk)
            self.miles.add_input_audio(chunk)
            logger.debug(f"Injected prompt chunk {i+1}/{len(self.prompt_chunks)} to both AIs")
        
        # If we want to record the prompt in the output
        if CONFIG["record_prompt"]:
            print("📝 DEBUG: Recording prompt in conversation output")
            logger.info("📝 Recording prompt in conversation output")
            for chunk in self.prompt_chunks:
                # Convert chunk back to samples for recording
                samples = np.frombuffer(chunk, dtype=np.int16)
                # Resample to recording rate if needed
                if CONFIG["conversation_rate"] != self.recorder.recording_rate:
                    # Convert to bytes first, then resample
                    resampled_chunk = resample_audio(
                        chunk,
                        CONFIG["conversation_rate"],
                        self.recorder.recording_rate
                    )
                    # Record as both Maya and Miles receiving the prompt
                    self.recorder.add_audio("Maya", resampled_chunk)
                    self.recorder.add_audio("Miles", resampled_chunk)
                else:
                    self.recorder.add_audio("Maya", chunk)
                    self.recorder.add_audio("Miles", chunk)
        
        print(f"✅ DEBUG: Prompt injection complete to both AIs")
        logger.info(f"✅ Prompt injection complete to both AIs")

    def _start_phase_timer(self):
        """Start the timer for phase transition."""
        with self.phase_lock:
            self.current_phase = "PHASE_1_PROCESSING"
            self.phase_start_time = time.time()
            self.cross_feed_enabled = False
            
        print(f"⏱️ DEBUG: Phase 1 started - {self.prompt_processing_time}s timer for independent processing")
        logger.info(f"Phase 1: Independent prompt processing ({self.prompt_processing_time}s)")
        
        # Start timer thread to enable cross-feeding
        timer_thread = threading.Thread(target=self._phase_transition_timer, daemon=True)
        timer_thread.start()

    def _phase_transition_timer(self):
        """Timer thread to transition from Phase 1 to Phase 2."""
        time.sleep(self.prompt_processing_time)
        
        with self.phase_lock:
            if self.current_phase == "PHASE_1_PROCESSING":
                self.current_phase = "PHASE_2_CONVERSATION"
                self.cross_feed_enabled = True
                
        print(f"🔗 DEBUG: Phase 2 started - Cross-feeding enabled between AIs")
        logger.info("Phase 2: Cross-feeding enabled - natural conversation begins")

    def _handle_audio_response(self, character_name, audio_chunk):
        """
        Handle audio responses with two-phase cross-feeding control.
        
        Phase 1: Record and play, but NO cross-feeding
        Phase 2: Full cross-feeding enabled
        """
        # Always record the audio regardless of phase
        self.recorder.add_audio(character_name, audio_chunk)

        # Always play audio for live monitoring
        if self.audio_player:
            if character_name == "Maya":
                self.audio_player.add_maya_chunk(audio_chunk)
            elif character_name == "Miles":
                self.audio_player.add_miles_chunk(audio_chunk)

        # Cross-feeding logic based on current phase
        with self.phase_lock:
            if not self.cross_feed_enabled:
                # Phase 1: No cross-feeding
                # print(f"🔇 DEBUG: {character_name} audio received but cross-feed disabled (Phase 1)")
                return
            # else:
                # Phase 2: Enable cross-feeding
                # print(f"🔊 DEBUG: {character_name} audio received - cross-feeding to other AI (Phase 2)")

        # Cross-feed to the other agent (same as original system)
        source_agent = self.maya if character_name == "Maya" else self.miles
        dest_agent = self.miles if character_name == "Maya" else self.maya

        # Resample and send to other agent
        resampled_audio = resample_audio(
            audio_chunk, 
            source_agent.output_rate,
            dest_agent.input_rate,
            target_chunk_size=CONFIG["target_chunk_size"]
        )

        dest_agent.add_input_audio(resampled_audio)
    
    def start(self):
        """Starts both agents and initiates the two-phase conversation."""
        logger.info("Starting two-phase conversation manager...")
        self.running = True
        
        if not self.maya.start() or not self.miles.start():
            logger.error("Failed to start one or both agents.")
            self.stop()
            return False

        # Wait for both agents to connect
        start_time = time.time()
        while time.time() - start_time < CONFIG["connect_timeout_sec"]:
            if self.maya.connected and self.miles.connected:
                logger.info("Both agents connected. Stabilizing...")
                
                self.recorder.recording_rate = self.maya.output_rate
                logger.info(f"Recording will be at {self.recorder.recording_rate}Hz")
                
                # Initialize proper stereo player
                if self.audio_player:
                    self.audio_player.initialize_stream(self.maya.output_rate)
                    self.audio_player.start_playback()
                    logger.info("🔊 Proper stereo playback enabled (Maya=Left, Miles=Right)")
                
                time.sleep(self.stabilization_time)
                
                # Inject prompt to both AIs and start phase timer
                self._inject_prompt_to_both()
                self._start_phase_timer()
                
                logger.info("🚀 Two-phase conversation started!")
                logger.info("📊 Recording: Maya=Left channel, Miles=Right channel")
                if CONFIG["live_playback"]:
                    logger.info("🔊 Live Stereo Playback: Maya=Left ear, Miles=Right ear")
                if SCIPY_AVAILABLE:
                    logger.info("🔧 Using high-quality SciPy resampling")
                logger.info("Press Ctrl+C to stop and save recording.")
                return True
            time.sleep(0.5)

        logger.error("Timeout waiting for agents to connect.")
        self.stop()
        return False
    
    def stop(self):
        """Stops the agents and saves the recording."""
        if not self.running: return
        logger.info("Stopping two-phase conversation manager...")
        self.running = False
        
        # Stop audio playback first
        if self.audio_player:
            self.audio_player.stop_playback()
        
        self.maya.stop()
        self.miles.stop()
        
        self.recorder.save()
        logger.info("Two-phase conversation stopped and recording saved.")

    def run(self):
        """Main loop to run the conversation until interrupted."""
        if not self.start():
            return
        
        try:
            while self.running:
                if not (self.maya.connected and self.miles.connected):
                    logger.warning("An agent disconnected. Shutting down.")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("User interrupted. Stopping conversation...")
        finally:
            self.stop()


def main():
    import argparse
    import logging
    
    parser = argparse.ArgumentParser(description="Two-Phase Maya-Miles Conversation Recorder")
    parser.add_argument("--filename", help="Custom filename for the recording.")
    parser.add_argument("--no-playback", action="store_true", help="Disable live audio playback")
    
    # Prompt selection options
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", help="Path to audio prompt file (WAV format)")
    prompt_group.add_argument("--prompt-id", type=int, help="Use specific prompt ID from CSV")
    prompt_group.add_argument("--random-prompt", action="store_true", help="Use random prompt from CSV")
    
    parser.add_argument("--prompt-topic", help="Filter prompts by topic (use with --random-prompt)")
    parser.add_argument("--prompts-csv", default="prompts/prompts.csv", help="Path to prompts CSV file")
    parser.add_argument("--list-prompts", action="store_true", help="List available prompts and exit")
    parser.add_argument("--list-topics", action="store_true", help="List available topics and exit")
    
    parser.add_argument("--no-prompt", action="store_true", help="Disable audio prompt, use random noise")
    parser.add_argument("--no-record-prompt", action="store_true",
                       help="Don't include prompt in final recording")
    parser.add_argument("--processing-time", type=int, default=15,
                       help="Seconds for Phase 1 independent processing (default: 15)")
    parser.add_argument("--stabilization-time", type=int, default=10,
                       help="Seconds to wait for agent stabilization after connection (default: 10)")
    args = parser.parse_args()


    # python two_phase_conversation.py --no-playback --random-prompt --no-record-prompt

    # 15 seconds AFTER prompt injection, stabilization time = 10s
    # launch at 25s 

    # Handle list operations first (exit after listing)
    if args.list_prompts or args.list_topics:
        from prompt_manager import PromptManager
        manager = PromptManager(args.prompts_csv)
        
        if args.list_prompts:
            prompts = manager.list_prompts()
            print(f"📋 Available prompts ({len(prompts)} total):")
            for prompt in prompts:
                file_status = "✅" if manager.validate_prompt_file(prompt) else "❌"
                print(f"  {prompt['prompt_id']}: {prompt['topic']} - {prompt['text'][:60]}... {file_status}")
            return
            
        if args.list_topics:
            topics = manager.list_topics()
            print(f"🏷️  Available topics: {', '.join(topics)}")
            return

    # Configure playback
    if args.no_playback:
        CONFIG["live_playback"] = False
    
    if args.no_record_prompt:
        CONFIG["record_prompt"] = False
    
    # Determine prompt configuration
    prompt_file = args.prompt
    prompt_id = args.prompt_id
    random_prompt = args.random_prompt
    prompt_topic = args.prompt_topic
    disable_prompt = args.no_prompt
    
    print(f"🔍 DEBUG: Prompt configuration:")
    print(f"  disable_prompt={disable_prompt}")
    print(f"  prompt_file={prompt_file}")
    print(f"  prompt_id={prompt_id}")
    print(f"  random_prompt={random_prompt}")
    print(f"  prompt_topic={prompt_topic}")
    
    # Validate prompt topic filter
    if prompt_topic and not random_prompt:
        print("⚠️  WARNING: --prompt-topic specified but --random-prompt not used. Topic filter will be ignored.")

    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.getLogger('websocket').setLevel(logging.WARNING)

    print("🎭 Two-Phase Maya-Miles Conversation Recorder")
    print("📊 Recording: Maya=Left channel, Miles=Right channel")
    if CONFIG["live_playback"]:
        print("🔊 Live Stereo: Maya=Left ear, Miles=Right ear (no processing delays)")
    if SCIPY_AVAILABLE:
        print("🔧 Using high-quality SciPy resampling")
    
    # Show configuration
    print(f"⏱️ Phase 1 Duration: {args.processing_time}s (independent processing)")
    print(f"🔧 Stabilization Time: {args.stabilization_time}s (agent connection wait)")
    
    # Show prompt configuration
    if disable_prompt:
        print("🚫 Audio Prompt: DISABLED (--no-prompt flag)")
    elif prompt_file:
        print(f"🎙️ Audio Prompt: Custom file '{prompt_file}' → both AIs")
    elif prompt_id is not None:
        print(f"🎯 Audio Prompt: ID {prompt_id} from CSV → both AIs")
    elif random_prompt:
        if prompt_topic:
            print(f"🎲 Audio Prompt: Random from topic '{prompt_topic}' → both AIs")
        else:
            print("🎲 Audio Prompt: Random from CSV → both AIs")
    else:
        print("🔍 Audio Prompt: Auto-select (random from CSV or default) → both AIs")
    
    if CONFIG["record_prompt"] and not disable_prompt:
        print("📝 Prompt will be included in recording")
    
    conversation = TwoPhaseConversationManager(
        maya_token="token0.json",
        miles_token="token1.json",
        filename=args.filename,
        prompt_file=prompt_file,
        disable_prompt=disable_prompt,
        prompt_processing_time=args.processing_time,
        prompt_id=prompt_id,
        random_prompt=random_prompt,
        prompt_topic=prompt_topic,
        prompts_csv=args.prompts_csv,
        stabilization_time=args.stabilization_time
    )
    conversation.run()


if __name__ == "__main__":
    main()