#!/usr/bin/env python3
"""
Audio Processing Components for AI Conversation System

Contains audio utilities, processing functions, and audio handling classes.
"""

import os
import time
import threading
import logging
import wave
from datetime import datetime
import numpy as np
import pyaudio

# Try to import scipy for better resampling
try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# Configuration
CONFIG = {
    "target_chunk_size": 1024,
    "conversation_rate": 16000,
    "recording_rate": 24000,
    "channels": 2,
    "agent_input_buffer_size": 50,
    "connect_timeout_sec": 40,
    "stabilization_wait_sec": 10,
    "adaptive_chunks": True,
    "live_playback": True,  # Enable live audio playback to hear them :)
    "default_prompt_file": "prompts/Prompt_sesame.wav",
    "prompt_agent": "Maya",  # Which agent receives the prompt
    "record_prompt": True,   # Include prompt in final recording
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


def load_audio_prompt(prompt_file_path, target_rate=None, target_chunk_size=None):
    """
    Load WAV file and convert to AI-ready format.
    
    Args:
        prompt_file_path: Path to the WAV file
        target_rate: Target sample rate (default: CONFIG["conversation_rate"])
        target_chunk_size: Target chunk size (default: CONFIG["target_chunk_size"])
    
    Returns:
        List of 1024-sample chunks at target_rate, ready for AI injection
        
    Raises:
        FileNotFoundError: If prompt file doesn't exist
        ValueError: If audio file is invalid or corrupted
    """
    if target_rate is None:
        target_rate = CONFIG["conversation_rate"]
    if target_chunk_size is None:
        target_chunk_size = CONFIG["target_chunk_size"]
    
    if not os.path.exists(prompt_file_path):
        raise FileNotFoundError(f"Prompt file not found: {prompt_file_path}")
    
    logger.info(f"Loading audio prompt from: {prompt_file_path}")
    
    try:
        # Load WAV file with robust handling for streaming WAV files
        with wave.open(prompt_file_path, 'rb') as wav_file:
            # Get WAV file parameters
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            original_rate = wav_file.getframerate()
            total_frames = wav_file.getnframes()
            
            logger.info(f"Prompt audio: {channels} channels, {sample_width} bytes/sample, {original_rate}Hz, {total_frames} frames")
            
            # Handle streaming WAV files with incorrect headers (total_frames = 0)
            if total_frames == 0:
                logger.warning("WAV header shows 0 frames, attempting to read actual audio data...")
                
                # Read the entire file and extract audio data manually
                wav_file.setpos(0)  # Reset to beginning
                
                # Try to read a large amount of data to get all available audio
                audio_bytes = b''
                try:
                    # Read in chunks until we can't read anymore
                    chunk_size = 8192
                    while True:
                        chunk = wav_file.readframes(chunk_size)
                        if not chunk:
                            break
                        audio_bytes += chunk
                except:
                    # If readframes fails, try reading raw data after WAV header
                    pass
                
                # If still no data, try reading raw file data after WAV header
                if len(audio_bytes) == 0:
                    logger.info("Attempting to read raw audio data from file...")
                    with open(prompt_file_path, 'rb') as raw_file:
                        # Skip WAV header (typically 44 bytes for standard WAV)
                        raw_file.seek(44)
                        audio_bytes = raw_file.read()
                
                # Calculate actual frames from data size
                if len(audio_bytes) > 0:
                    bytes_per_frame = channels * sample_width
                    actual_frames = len(audio_bytes) // bytes_per_frame
                    logger.info(f"Found {actual_frames} actual frames in audio data ({len(audio_bytes)} bytes)")
                else:
                    raise ValueError("No audio data found in WAV file")
            else:
                # Normal WAV file with correct header
                audio_bytes = wav_file.readframes(total_frames)
            
            # Convert to numpy array based on sample width
            if sample_width == 1:
                # 8-bit unsigned
                audio_samples = np.frombuffer(audio_bytes, dtype=np.uint8).astype(np.float32)
                audio_samples = (audio_samples - 128) * 256  # Convert to 16-bit range
            elif sample_width == 2:
                # 16-bit signed
                audio_samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            elif sample_width == 4:
                # 32-bit (could be int or float)
                try:
                    audio_samples = np.frombuffer(audio_bytes, dtype=np.int32).astype(np.float32)
                    audio_samples = audio_samples / 65536  # Scale down to 16-bit range
                except:
                    audio_samples = np.frombuffer(audio_bytes, dtype=np.float32)
                    audio_samples = audio_samples * 32767  # Scale to 16-bit range
            else:
                raise ValueError(f"Unsupported sample width: {sample_width} bytes")
            
            # Handle multi-channel audio - convert to mono
            if channels > 1:
                # Reshape and average channels
                audio_samples = audio_samples.reshape(-1, channels)
                audio_samples = np.mean(audio_samples, axis=1)
                logger.info(f"Converted {channels}-channel audio to mono")
            
            # Resample if needed
            if original_rate != target_rate:
                logger.info(f"Resampling prompt from {original_rate}Hz to {target_rate}Hz")
                
                if SCIPY_AVAILABLE:
                    # High-quality resampling with scipy
                    num_samples = int(len(audio_samples) * target_rate / original_rate)
                    audio_samples = signal.resample(audio_samples, num_samples)
                else:
                    # Linear interpolation fallback
                    ratio = target_rate / original_rate
                    new_length = int(len(audio_samples) * ratio)
                    old_indices = np.linspace(0, len(audio_samples) - 1, new_length)
                    audio_samples = np.interp(old_indices, np.arange(len(audio_samples)), audio_samples)
            
            # Clip and convert to 16-bit integers
            audio_samples = np.clip(audio_samples, -32768, 32767).astype(np.int16)
            
            # Split into target-sized chunks
            chunks = []
            total_samples = len(audio_samples)
            
            for i in range(0, total_samples, target_chunk_size):
                chunk_samples = audio_samples[i:i + target_chunk_size]
                
                # Pad last chunk if needed
                if len(chunk_samples) < target_chunk_size:
                    padding = np.zeros(target_chunk_size - len(chunk_samples), dtype=np.int16)
                    chunk_samples = np.concatenate([chunk_samples, padding])
                
                chunks.append(chunk_samples.tobytes())
            
            duration_sec = total_samples / target_rate
            logger.info(f"Prompt processed: {len(chunks)} chunks, {duration_sec:.2f}s duration")
            
            return chunks
            
    except wave.Error as e:
        raise ValueError(f"Invalid WAV file format: {e}")
    except Exception as e:
        raise ValueError(f"Failed to process audio prompt: {e}")


def create_fallback_prompt(target_rate=None, target_chunk_size=None):
    """
    Create a fallback prompt (random noise) when audio prompt loading fails.
    
    Returns:
        List containing a single chunk of random noise
    """
    if target_rate is None:
        target_rate = CONFIG["conversation_rate"]
    if target_chunk_size is None:
        target_chunk_size = CONFIG["target_chunk_size"]
    
    logger.warning("Using fallback random noise prompt")
    noise = np.random.randint(-100, 100, target_chunk_size, dtype=np.int16).tobytes()
    return [noise]


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