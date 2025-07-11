#!/usr/bin/env python3
"""
Conversation Manager for AI-to-AI Conversations

Orchestrates conversations between two AI agents with recording and playback.
"""

import os
import time
import logging
import numpy as np

from audio_processing import CONFIG, SCIPY_AVAILABLE, ProperStereoPlayer, ConversationRecorder, resample_audio, load_audio_prompt, create_fallback_prompt
from ai_agent import AIAgent

logger = logging.getLogger('sesame.conversation')


class ConversationManager:
    """Orchestrates the conversation between two AI agents and the recorder."""
    
    def __init__(self, maya_token="token.json", miles_token="token2.json", filename=None, prompt_file=None, disable_prompt=False):
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
        self._load_prompt()

    def _load_prompt(self):
        """Load and process the audio prompt for conversation initiation."""
        print(f"🔍 DEBUG: _load_prompt called - disable_prompt={self.disable_prompt}, prompt_file={self.prompt_file}")
        
        if self.disable_prompt:
            print("🚫 DEBUG: Prompt disabled by --no-prompt flag, using fallback noise")
            logger.info("Prompt disabled by --no-prompt flag, using fallback noise")
            self.prompt_chunks = create_fallback_prompt()
            return
            
        try:
            if self.prompt_file:
                # Use specified prompt file
                print(f"📁 DEBUG: Loading custom prompt: {self.prompt_file}")
                logger.info(f"Loading custom prompt: {self.prompt_file}")
                self.prompt_chunks = load_audio_prompt(self.prompt_file)
            else:
                # Try default prompt file
                default_prompt = CONFIG["default_prompt_file"]
                print(f"🔍 DEBUG: Checking default prompt: {default_prompt}, exists={os.path.exists(default_prompt)}")
                if os.path.exists(default_prompt):
                    print(f"📁 DEBUG: Loading default prompt: {default_prompt}")
                    logger.info(f"Loading default prompt: {default_prompt}")
                    self.prompt_chunks = load_audio_prompt(default_prompt)
                else:
                    print("🔀 DEBUG: No prompt file found, using fallback")
                    logger.info("No prompt file found, using fallback")
                    self.prompt_chunks = create_fallback_prompt()
                    
        except (FileNotFoundError, ValueError) as e:
            print(f"❌ DEBUG: Failed to load audio prompt: {e}")
            logger.warning(f"Failed to load audio prompt: {e}")
            logger.info("Using fallback random noise prompt")
            self.prompt_chunks = create_fallback_prompt()

    def _inject_prompt(self):
        """Inject the audio prompt to start the conversation."""
        print(f"🔍 DEBUG: _inject_prompt called - disable_prompt={self.disable_prompt}")
        
        if self.disable_prompt:
            print("🚫 DEBUG: Prompt injection SKIPPED due to --no-prompt flag")
            logger.info("Prompt injection skipped due to --no-prompt flag")
            return
            
        if not self.prompt_chunks:
            print("❌ DEBUG: No prompt chunks available!")
            logger.error("No prompt chunks available!")
            return
        
        target_agent = self.maya if CONFIG["prompt_agent"].lower() == "maya" else self.miles
        prompt_agent_name = CONFIG["prompt_agent"]
        
        print(f"🎙️ DEBUG: Injecting audio prompt to {prompt_agent_name} ({len(self.prompt_chunks)} chunks)")
        logger.info(f"🎙️ Injecting audio prompt to {prompt_agent_name} ({len(self.prompt_chunks)} chunks)")
        
        # Inject all prompt chunks sequentially
        for i, chunk in enumerate(self.prompt_chunks):
            target_agent.add_input_audio(chunk)
            logger.debug(f"Injected prompt chunk {i+1}/{len(self.prompt_chunks)}")
        
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
                    self.recorder.add_audio(prompt_agent_name, resampled_chunk)
                else:
                    self.recorder.add_audio(prompt_agent_name, chunk)
        
        print(f"✅ DEBUG: Prompt injection complete to {prompt_agent_name}")
        logger.info(f"✅ Prompt injection complete to {prompt_agent_name}")

    def _handle_audio_response(self, character_name, audio_chunk):
        """
        IMMEDIATE audio processing like voice_chat - minimal delays
        """
        source_agent = self.maya if character_name == "Maya" else self.miles
        dest_agent = self.miles if character_name == "Maya" else self.maya

        # 1. Record the original audio IMMEDIATELY (no processing)
        self.recorder.add_audio(character_name, audio_chunk)

        # 2. Play audio IMMEDIATELY like voice_chat (proper stereo)
        if self.audio_player:
            if character_name == "Maya":
                self.audio_player.add_maya_chunk(audio_chunk)
            elif character_name == "Miles":
                self.audio_player.add_miles_chunk(audio_chunk)

        # 3. Send to other agent with minimal processing
        resampled_audio = resample_audio(
            audio_chunk, 
            source_agent.output_rate,
            dest_agent.input_rate,
            target_chunk_size=CONFIG["target_chunk_size"]
        )

        # 4. Add to destination agent input buffer
        dest_agent.add_input_audio(resampled_audio)
    
    def start(self):
        """Starts both agents and waits for them to connect."""
        logger.info("Starting conversation manager...")
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
                
                time.sleep(CONFIG["stabilization_wait_sec"])
                
                # Kick off the conversation with audio prompt
                self._inject_prompt()
                
                logger.info("🚀 Conversation started!")
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
        logger.info("Stopping conversation manager...")
        self.running = False
        
        # Stop audio playback first
        if self.audio_player:
            self.audio_player.stop_playback()
        
        self.maya.stop()
        self.miles.stop()
        
        self.recorder.save()
        logger.info("Conversation stopped and recording saved.")

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
    
    parser = argparse.ArgumentParser(description="Maya-Miles Conversation Recorder with Live Playback")
    parser.add_argument("--filename", help="Custom filename for the recording.")
    parser.add_argument("--no-playback", action="store_true", help="Disable live audio playback")
    parser.add_argument("--prompt", help="Path to audio prompt file (WAV format)")
    parser.add_argument("--no-prompt", action="store_true", help="Disable audio prompt, use random noise")
    parser.add_argument("--prompt-agent", choices=["Maya", "Miles"], default="Maya",
                       help="Which agent receives the prompt (default: Maya)")
    parser.add_argument("--no-record-prompt", action="store_true",
                       help="Don't include prompt in final recording")
    args = parser.parse_args()

    # Configure playback
    if args.no_playback:
        CONFIG["live_playback"] = False
    
    # Configure prompt settings
    if args.prompt_agent:
        CONFIG["prompt_agent"] = args.prompt_agent
    
    if args.no_record_prompt:
        CONFIG["record_prompt"] = False
    
    # Determine prompt file to use
    prompt_file = None
    disable_prompt = args.no_prompt
    
    print(f"🔍 DEBUG: args.no_prompt={args.no_prompt}, disable_prompt={disable_prompt}")
    
    if not args.no_prompt:
        if args.prompt:
            prompt_file = args.prompt
        else:
            # Use default if it exists
            default_prompt = CONFIG["default_prompt_file"]
            if os.path.exists(default_prompt):
                prompt_file = default_prompt

    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.getLogger('websocket').setLevel(logging.WARNING)

    print("🎭 Maya-Miles Conversation Recorder with Audio Prompt Support")
    print("📊 Recording: Maya=Left channel, Miles=Right channel")
    if CONFIG["live_playback"]:
        print("🔊 Live Stereo: Maya=Left ear, Miles=Right ear (no processing delays)")
    if SCIPY_AVAILABLE:
        print("🔧 Using high-quality SciPy resampling")
    
    # Show prompt configuration
    if disable_prompt:
        print("🚫 Audio Prompt: DISABLED (--no-prompt flag)")
    elif prompt_file:
        print(f"🎙️ Audio Prompt: {prompt_file} → {CONFIG['prompt_agent']}")
        if CONFIG["record_prompt"]:
            print("📝 Prompt will be included in recording")
    else:
        print("🔀 Using fallback random noise prompt")
    
    conversation = ConversationManager(
        maya_token="token0.json",
        miles_token="token1.json",
        filename=args.filename,
        prompt_file=prompt_file,
        disable_prompt=disable_prompt
    )
    conversation.run()


if __name__ == "__main__":
    main()