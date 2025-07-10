#!/usr/bin/env python3
"""
AI Conversation Recorder with Direct Audio Playback

Records conversations between two AI agents with proper audio handling.
Plays Maya's audio directly like voice_chat for testing.
"""

import sys
import os
import time
import threading
import logging
import wave
from datetime import datetime
from collections import deque
import numpy as np
import pyaudio

# Try to import scipy for better resampling
try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# Add parent directory to path to import sesame_ai
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sesame_ai import SesameAI, SesameWebSocket, TokenManager

# Configuration
CONFIG = {
    "target_chunk_size": 1024,
    "conversation_rate": 16000,
    "recording_rate": 24000,
    "channels": 2,
    "buffer_before_recording_chunks": 50,
    "agent_input_buffer_size": 50,
    "connect_timeout_sec": 40,
    "stabilization_wait_sec": 10,
    "adaptive_chunks": True,
    "live_playback": True,  # Enable live audio playback to hear them :)
}

logger = logging.getLogger('sesame.conversation')


def process_variable_chunk(audio_chunk, target_size=None):
    """Process variable-sized audio chunks into consistent target sizes."""
    if target_size is None:
        target_size = CONFIG["target_chunk_size"]
    
    samples = np.frombuffer(audio_chunk, dtype=np.int16)
    total_samples = len(samples)
    
    chunks = []
    for i in range(0, total_samples, target_size):
        chunk_samples = samples[i:i + target_size]
        
        if len(chunk_samples) < target_size:
            padding = np.zeros(target_size - len(chunk_samples), dtype=np.int16)
            chunk_samples = np.concatenate([chunk_samples, padding])
        
        chunks.append(chunk_samples.tobytes())
    
    return chunks


def resample_audio(audio_data, from_rate, to_rate, target_chunk_size=None):
    """Handle variable input sizes properly during resampling."""
    if target_chunk_size is None:
        target_chunk_size = CONFIG["target_chunk_size"]
    
    samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
    
    if from_rate == to_rate and len(samples) <= target_chunk_size:
        if len(samples) < target_chunk_size:
            padding = np.zeros(target_chunk_size - len(samples))
            samples = np.concatenate([samples, padding])
        else:
            samples = samples[:target_chunk_size]
        return samples.astype(np.int16).tobytes()

    # Resample if rates differ
    if SCIPY_AVAILABLE:
        num_samples = int(len(samples) * to_rate / from_rate)
        resampled = signal.resample(samples, num_samples)
    else:
        ratio = to_rate / from_rate
        new_length = int(len(samples) * ratio)
        old_indices = np.linspace(0, len(samples) - 1, new_length)
        resampled = np.interp(old_indices, np.arange(len(samples)), samples)

    # Take only what we need for target size
    if len(resampled) > target_chunk_size:
        resampled = resampled[:target_chunk_size]
    elif len(resampled) < target_chunk_size:
        padding = np.zeros(target_chunk_size - len(resampled))
        resampled = np.concatenate([resampled, padding])

    return np.clip(resampled, -32768, 32767).astype(np.int16).tobytes()


class ProperStereoPlayer:
    """Stereo player that preserves voice_chat timing - no processing delays"""
    
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.output_stream = None
        self.running = False
        
        # Minimal buffers for stereo sync (not queues!)
        self.maya_buffer = np.array([], dtype=np.int16)
        self.miles_buffer = np.array([], dtype=np.int16)
        
        self.lock = threading.Lock()
        self.playback_thread = None
        
    def initialize_stream(self, sample_rate):
        """Initialize true stereo stream"""
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
        
        try:
            self.output_stream = self.p.open(
                format=pyaudio.paInt16,
                channels=2,  # True stereo
                rate=sample_rate,
                output=True
            )
            logger.info(f"Proper stereo playback initialized at {sample_rate}Hz")
        except Exception as e:
            logger.error(f"Failed to initialize stereo stream: {e}")
            self.output_stream = None
    
    def start_playback(self):
        """Start minimal playback thread"""
        if self.playback_thread and self.playback_thread.is_alive():
            return
        
        self.running = True
        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()
        logger.info("Proper stereo playback thread started")
    
    def stop_playback(self):
        """Stop playback"""
        self.running = False
        
        if self.playback_thread:
            self.playback_thread.join(timeout=1.0)
        
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None
        
        self.p.terminate()
        logger.info("Proper stereo playback stopped")
    
    def add_maya_chunk(self, audio_chunk):
        """Add Maya chunk - IMMEDIATE processing like voice_chat"""
        samples = np.frombuffer(audio_chunk, dtype=np.int16)
        
        with self.lock:
            self.maya_buffer = np.concatenate([self.maya_buffer, samples])
    
    def add_miles_chunk(self, audio_chunk):
        """Add Miles chunk - IMMEDIATE processing like voice_chat"""
        samples = np.frombuffer(audio_chunk, dtype=np.int16)
        
        with self.lock:
            self.miles_buffer = np.concatenate([self.miles_buffer, samples])
    
    def _playback_loop(self):
        """Minimal stereo playback - preserves voice_chat timing"""
        logger.info("Proper stereo playback loop started")
        
        while self.running:
            try:
                with self.lock:
                    # Check if we have samples from both agents
                    min_samples = min(len(self.maya_buffer), len(self.miles_buffer))
                    
                    if min_samples > 512:  # Small threshold for responsiveness
                        # Take samples (no padding, no size forcing)
                        maya_play = self.maya_buffer[:min_samples].copy()
                        miles_play = self.miles_buffer[:min_samples].copy()
                        
                        # Remove played samples
                        self.maya_buffer = self.maya_buffer[min_samples:]
                        self.miles_buffer = self.miles_buffer[min_samples:]
                        
                        play_data = (maya_play, miles_play, min_samples)
                    else:
                        play_data = None
                
                if play_data and self.output_stream:
                    maya_play, miles_play, min_samples = play_data
                    
                    # Create stereo (minimal operation)
                    stereo_data = np.empty(min_samples * 2, dtype=np.int16)
                    stereo_data[0::2] = maya_play  # Left channel
                    stereo_data[1::2] = miles_play  # Right channel
                    
                    # Play immediately like voice_chat
                    self.output_stream.write(stereo_data.tobytes())
                else:
                    # Small sleep when no audio - like voice_chat
                    time.sleep(0.001)
                    
            except Exception as e:
                if self.running:
                    logger.error(f"Error in proper stereo playback: {e}")
                    time.sleep(0.01)


class ConversationRecorder:
    """Records a two-person conversation with minimal processing - no cutting."""
    
    def __init__(self, filename=None):
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_{timestamp}.wav"
        self.filename = filename

        # Use numpy arrays for efficient concatenation - no chunk forcing
        self.maya_audio = np.array([], dtype=np.int16)
        self.miles_audio = np.array([], dtype=np.int16)
        
        self.lock = threading.Lock()
        self.recording_rate = CONFIG["recording_rate"]
        
        logger.info(f"Recorder initialized. File: {self.filename} at {self.recording_rate}Hz")
        logger.info("Using minimal processing for cut-free recording")

    def add_audio(self, character_name, audio_chunk):
        """
        Add audio with MINIMAL processing - no chunk size forcing like playback
        """
        # Convert to samples immediately - no size validation
        samples = np.frombuffer(audio_chunk, dtype=np.int16)
        
        with self.lock:
            if character_name.lower() == "maya":
                # Concatenate directly - no processing delays
                self.maya_audio = np.concatenate([self.maya_audio, samples])
            elif character_name.lower() == "miles":
                # Concatenate directly - no processing delays  
                self.miles_audio = np.concatenate([self.miles_audio, samples])

    def save(self):
        """
        Save with minimal processing - handle variable sizes during save only
        """
        with self.lock:
            maya_samples = len(self.maya_audio)
            miles_samples = len(self.miles_audio)
            
            if maya_samples < 1000 and miles_samples < 1000:
                logger.warning("Recording not saved. Too short.")
                return

            logger.info(f"Saving conversation to {self.filename}...")
            logger.info(f"Audio lengths: Maya={maya_samples} samples, Miles={miles_samples} samples")
            
            # Use the longer audio as the base length
            max_samples = max(maya_samples, miles_samples)
            
            # Pad shorter audio to match (only at the end, no chunk forcing)
            maya_final = self.maya_audio.copy()
            miles_final = self.miles_audio.copy()
            
            if len(maya_final) < max_samples:
                padding = np.zeros(max_samples - len(maya_final), dtype=np.int16)
                maya_final = np.concatenate([maya_final, padding])
                
            if len(miles_final) < max_samples:
                padding = np.zeros(max_samples - len(miles_final), dtype=np.int16)
                miles_final = np.concatenate([miles_final, padding])

            try:
                with wave.open(self.filename, 'wb') as wav_file:
                    wav_file.setnchannels(CONFIG["channels"])
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(self.recording_rate)

                    # Write stereo audio efficiently - no chunk-by-chunk processing
                    stereo_audio = np.empty(max_samples * 2, dtype=np.int16)
                    stereo_audio[0::2] = maya_final   # Left channel
                    stereo_audio[1::2] = miles_final  # Right channel
                    
                    # Write all at once - no loop delays
                    wav_file.writeframes(stereo_audio.tobytes())

                duration_sec = max_samples / self.recording_rate
                logger.info(f"Successfully saved {duration_sec:.1f}s recording to {self.filename}")
                logger.info(f"No audio cutting - preserved all variable-sized chunks")

            except Exception as e:
                logger.error(f"Failed to save WAV file: {e}")


class AIAgent:
    """Manages the connection and audio streams for a single AI character."""
    
    def __init__(self, character, token_file, on_response_callback):
        self.character = character
        self.token_file = token_file
        self.on_response_callback = on_response_callback

        self.input_audio = deque(maxlen=CONFIG["agent_input_buffer_size"])
        self.silence = np.zeros(CONFIG["target_chunk_size"], dtype=np.int16).tobytes()

        self.api_client = SesameAI()
        self.token_manager = TokenManager(self.api_client, token_file=self.token_file)
        self.ws = None
        
        self.running = False
        self.connected = False
        self.lock = threading.Lock()
        
        self.input_rate = CONFIG["conversation_rate"]
        self.output_rate = CONFIG["recording_rate"]

    def start(self):
        """Authenticates and starts the connection and processing threads."""
        logger.info(f"Starting agent: {self.character}")
        self.running = True
        try:
            id_token = self.token_manager.get_valid_token()
        except Exception as e:
            logger.error(f"Authentication failed for {self.character}: {e}")
            self.running = False
            return False

        self.ws = SesameWebSocket(id_token=id_token, character=self.character)
        self.ws.set_connect_callback(self._on_connect)
        self.ws.set_disconnect_callback(self._on_disconnect)
        
        threading.Thread(target=self.ws.connect, daemon=True).start()
        return True

    def stop(self):
        """Stops the agent and disconnects."""
        logger.info(f"Stopping agent: {self.character}")
        self.running = False
        if self.ws and self.connected:
            self.ws.disconnect()

    def _on_connect(self):
        """Callback for successful WebSocket connection."""
        with self.lock:
            if not self.running: return
            self.connected = True
            
        # Use server sample rate exactly like voice_chat
        self.output_rate = self.ws.server_sample_rate
        
        logger.info(f"{self.character} connected successfully.")
        logger.info(f"{self.character} using server rate: {self.output_rate}Hz")
        
        threading.Thread(target=self._send_loop, daemon=True).start()
        threading.Thread(target=self._receive_loop, daemon=True).start()

    def _on_disconnect(self):
        """Callback for WebSocket disconnection."""
        logger.warning(f"{self.character} disconnected.")
        with self.lock:
            self.connected = False

    def _send_loop(self):
        """Continuously sends audio from the input queue to the AI."""
        interval = CONFIG["target_chunk_size"] / self.input_rate
        next_time = time.time()
        
        while self.running and self.connected:
            try:
                audio_chunk = self.input_audio.popleft()
            except IndexError:
                audio_chunk = self.silence

            if self.ws and self.connected:
                self.ws.send_audio_data(audio_chunk)
            
            next_time += interval
            sleep_time = next_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _receive_loop(self):
        """
        Continuously receives audio from the AI - IMMEDIATE callback like voice_chat
        """
        while self.running and self.connected:
            # Get audio with short timeout like voice_chat
            audio_chunk = self.ws.get_next_audio_chunk(timeout=0.01)
            if audio_chunk:
                # IMMEDIATE callback - no delays, no processing
                self.on_response_callback(self.character, audio_chunk)

    def add_input_audio(self, audio_data):
        """Add audio to this agent's input buffer with variable chunk handling."""
        if CONFIG["adaptive_chunks"]:
            processed_chunks = process_variable_chunk(audio_data, CONFIG["target_chunk_size"])
            
            for chunk in processed_chunks:
                if len(self.input_audio) < CONFIG["agent_input_buffer_size"]:
                    self.input_audio.append(chunk)
        else:
            expected_bytes = CONFIG["target_chunk_size"] * 2
            if len(audio_data) != expected_bytes:
                samples = np.frombuffer(audio_data, dtype=np.int16)
                if len(samples) > CONFIG["target_chunk_size"]:
                    samples = samples[:CONFIG["target_chunk_size"]]
                elif len(samples) < CONFIG["target_chunk_size"]:
                    padding = np.zeros(CONFIG["target_chunk_size"] - len(samples), dtype=np.int16)
                    samples = np.concatenate([samples, padding])
                audio_data = samples.tobytes()
            
            if len(self.input_audio) < CONFIG["agent_input_buffer_size"]:
                self.input_audio.append(audio_data)


class ConversationManager:
    """Orchestrates the conversation between two AI agents and the recorder."""
    
    def __init__(self, maya_token="token.json", miles_token="token2.json", filename=None):
        self.recorder = ConversationRecorder(filename=filename)
        self.maya = AIAgent("Maya", maya_token, self._handle_audio_response)
        self.miles = AIAgent("Miles", miles_token, self._handle_audio_response)
        self.running = False
        
        # Initialize proper stereo player
        self.audio_player = ProperStereoPlayer() if CONFIG["live_playback"] else None

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
                
                # Kick off the conversation
                noise = np.random.randint(-100, 100, CONFIG["target_chunk_size"], dtype=np.int16).tobytes()
                self.maya.add_input_audio(noise)
                
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
    parser = argparse.ArgumentParser(description="Maya-Miles Conversation Recorder with Live Playback")
    parser.add_argument("--filename", help="Custom filename for the recording.")
    parser.add_argument("--no-playback", action="store_true", help="Disable live audio playback")
    args = parser.parse_args()

    # Configure playback
    if args.no_playback:
        CONFIG["live_playback"] = False

    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.getLogger('websocket').setLevel(logging.WARNING)

    print("🎭 Maya-Miles Conversation Recorder with Proper Stereo Playback")
    print("📊 Recording: Maya=Left channel, Miles=Right channel")
    if CONFIG["live_playback"]:
        print("🔊 Live Stereo: Maya=Left ear, Miles=Right ear (no processing delays)")
    if SCIPY_AVAILABLE:
        print("🔧 Using high-quality SciPy resampling")
    
    conversation = ConversationManager(
        maya_token="token.json",
        miles_token="token2.json",
        filename=args.filename
    )
    conversation.run()


if __name__ == "__main__":
    main()