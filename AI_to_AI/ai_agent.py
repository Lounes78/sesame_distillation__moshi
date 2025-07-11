#!/usr/bin/env python3
"""
AI Agent Management for Conversation System

Handles WebSocket connections, audio streaming, and AI agent lifecycle.
"""

import sys
import os
import time
import threading
import logging
from collections import deque
import numpy as np

# Add parent directory to path to import sesame_ai
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sesame_ai import SesameAI, SesameWebSocket, TokenManager
from audio_processing import CONFIG, process_variable_chunk

logger = logging.getLogger('sesame.conversation')


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