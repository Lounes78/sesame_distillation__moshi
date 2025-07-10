#!/usr/bin/env python3
"""
Final Maya-Miles Conversation System

BASED ON WHAT ACTUALLY WORKS:
- Only silence feeding (no audio routing)
- Direct recording of responses
- Simple and stable

This is based on silent_conversation.py that achieved 72.7% activity.
Now updated to use separate token files for each character.
"""

import sys
import os
import time
import threading
import logging
import argparse
import numpy as np
import wave
from datetime import datetime

# Add the current directory to the path so we can import local modules
sys.path.insert(0, os.path.dirname(__file__))

from dual_conversation import DualWebSocketManager

logger = logging.getLogger('sesame.final_conversation')

class FinalRecorder:
    """
    Simple recorder that writes audio immediately
    """
    
    def __init__(self, filename=None, sample_rate=24000):
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"maya_miles_conversation_{timestamp}.wav"
        
        self.filename = filename
        self.sample_rate = sample_rate
        self.channels = 2  # Stereo
        self.sample_width = 2  # 16-bit
        
        self.recording = False
        self.wav_file = None
        self.frames_written = 0
        self.recording_start_time = None
        self.write_lock = threading.Lock()
        
        logger.debug(f"FinalRecorder initialized: {filename}")
    
    def start_recording(self):
        """Start recording"""
        if self.recording:
            return
        
        logger.info(f"Starting recording: {self.filename}")
        
        # Open WAV file for writing
        self.wav_file = wave.open(self.filename, 'wb')
        self.wav_file.setnchannels(self.channels)
        self.wav_file.setsampwidth(self.sample_width)
        self.wav_file.setframerate(self.sample_rate)
        
        self.recording = True
        self.recording_start_time = time.time()
        self.frames_written = 0
        
        logger.info("Recording started")
    
    def stop_recording(self):
        """Stop recording"""
        if not self.recording:
            return
        
        logger.info("Stopping recording...")
        self.recording = False
        
        with self.write_lock:
            if self.wav_file:
                self.wav_file.close()
                self.wav_file = None
        
        duration = time.time() - self.recording_start_time if self.recording_start_time else 0
        logger.info(f"Recording stopped: {self.frames_written} frames, {duration:.1f}s")
        
        print(f"\n🎵 Recording saved: {self.filename}")
        print(f"   Duration: {duration:.1f} seconds")
        print(f"   Frames: {self.frames_written}")
        print(f"   Format: {self.sample_rate}Hz, 16-bit, Stereo")
        print(f"   Channels: Left=Maya, Right=Miles")
    
    def record_audio(self, maya_audio, miles_audio):
        """Record audio from both characters"""
        if not self.recording:
            return
        
        # Only record if we have audio from at least one character
        if not maya_audio and not miles_audio:
            return
        
        with self.write_lock:
            if self.wav_file:
                # Convert to samples
                maya_samples = np.frombuffer(maya_audio, dtype=np.int16) if maya_audio else None
                miles_samples = np.frombuffer(miles_audio, dtype=np.int16) if miles_audio else None
                
                # Determine frame size
                frame_size = 0
                if maya_samples is not None:
                    frame_size = max(frame_size, len(maya_samples))
                if miles_samples is not None:
                    frame_size = max(frame_size, len(miles_samples))
                
                if frame_size == 0:
                    return
                
                # Create stereo frame
                stereo_samples = np.zeros(frame_size * 2, dtype=np.int16)
                
                # Fill left channel with Maya
                if maya_samples is not None:
                    copy_size = min(len(maya_samples), frame_size)
                    stereo_samples[0::2][:copy_size] = maya_samples[:copy_size]
                
                # Fill right channel with Miles
                if miles_samples is not None:
                    copy_size = min(len(miles_samples), frame_size)
                    stereo_samples[1::2][:copy_size] = miles_samples[:copy_size]
                
                self.wav_file.writeframes(stereo_samples.tobytes())
                self.frames_written += 1
    
    def get_recording_duration(self):
        """Get current recording duration"""
        if self.recording_start_time:
            return time.time() - self.recording_start_time
        return 0.0


class FinalConversation:
    """
    Final conversation system - only silence feeding and recording
    """
    
    def __init__(self, maya_token_file="token.json", miles_token_file="token2.json", recording_filename=None):
        # Core components
        self.dual_manager = DualWebSocketManager(
            maya_token_file=maya_token_file,
            miles_token_file=miles_token_file
        )
        self.recorder = None
        
        # System state
        self.system_running = False
        self.silence_feeding_active = False
        
        # Filenames
        self.recording_filename = recording_filename
        
        # Audio settings (match recording sample rate)
        self.chunk_size = 1024
        self.sample_rate = 24000  # Match recorder sample rate
        
        # Statistics
        self.session_start_time = None
        
        logger.debug("FinalConversation initialized with separate token files")
    
    def initialize_system(self):
        """Initialize system"""
        logger.info("Initializing final conversation system...")
        
        self.dual_manager.set_both_connected_callback(self._on_both_connected)
        self.dual_manager.set_disconnected_callback(self._on_character_disconnected)
        
        logger.info("System initialization complete")
    
    def start_system(self):
        """Start the system"""
        if self.system_running:
            return False
        
        logger.info("Starting final conversation system...")
        self.session_start_time = time.time()
        
        if not self.dual_manager.start():
            logger.error("Failed to start dual WebSocket connections")
            return False
        
        self.system_running = True
        logger.info("System started successfully")
        return True
    
    def stop_system(self):
        """Stop the system"""
        if not self.system_running:
            return
        
        logger.info("Stopping final conversation system...")
        
        # Stop silence feeding
        self.silence_feeding_active = False
        
        # Stop recording
        if self.recorder:
            self.recorder.stop_recording()
        
        # Stop dual manager
        self.dual_manager.stop()
        self.system_running = False
        
        # Print summary
        self._print_session_summary()
        
        logger.info("System stopped")
    
    def _on_both_connected(self):
        """When both characters connect"""
        logger.info("Both characters connected - starting final mode...")
        
        # Initialize recorder
        self.recorder = FinalRecorder(filename=self.recording_filename)
        self.recorder.start_recording()
        
        # Start recording integration
        self._start_recording_integration()
        
        # Start silence feeding
        self._start_silence_feeding()
        
        logger.info("Final conversation mode active!")
        
        print("\n🎉 Maya and Miles are connected!")
        print("🎵 Stereo recording started (Maya=Left, Miles=Right)")
        print("\n🎯 FINAL CONVERSATION MODE")
        print("   🤫 Silence feeding → Both characters")
        print("   🎙️  Recording their responses to silence")
        print("   📝 NO audio routing - they respond naturally to silence")
        print("   ✅ Based on proven working system (72.7% activity)")
        print("   🔑 Using separate authentication tokens for security")
    
    def _on_character_disconnected(self, character):
        """When character disconnects"""
        logger.warning(f"{character} disconnected!")
        print(f"\n⚠️  {character} disconnected!")
    
    def _start_recording_integration(self):
        """Start recording integration"""
        logger.info("Starting recording integration...")
        
        recording_thread = threading.Thread(target=self._recording_loop)
        recording_thread.daemon = True
        recording_thread.start()
        
        logger.info("Recording integration started")
    
    def _recording_loop(self):
        """Recording loop - get audio and record it"""
        logger.debug("Recording loop started")
        
        while self.system_running and self.dual_manager.running:
            try:
                # Get audio from both characters with shorter timeout for responsiveness
                maya_audio = self.dual_manager.get_maya_audio(timeout=0.001)
                miles_audio = self.dual_manager.get_miles_audio(timeout=0.001)
                
                # Record if we have any audio
                if maya_audio or miles_audio:
                    if self.recorder:
                        self.recorder.record_audio(maya_audio, miles_audio)
                        logger.debug(f"Recorded audio - Maya: {len(maya_audio) if maya_audio else 0}, Miles: {len(miles_audio) if miles_audio else 0}")
                
                # Very short sleep to avoid busy waiting
                time.sleep(0.001)
                
            except Exception as e:
                if self.system_running:
                    logger.error(f"Error in recording loop: {e}")
                    time.sleep(0.1)
    
    def _start_silence_feeding(self):
        """Start silence feeding"""
        logger.info("Starting silence feeding...")
        self.silence_feeding_active = True
        
        # Maya silence thread
        maya_silence_thread = threading.Thread(target=self._feed_silence_to_maya)
        maya_silence_thread.daemon = True
        maya_silence_thread.start()
        
        # Miles silence thread
        miles_silence_thread = threading.Thread(target=self._feed_silence_to_miles)
        miles_silence_thread.daemon = True
        miles_silence_thread.start()
        
        logger.info("Silence feeding started")
    
    def _feed_silence_to_maya(self):
        """Feed silence to Maya"""
        silent_data = np.zeros(self.chunk_size, dtype=np.int16).tobytes()
        
        while self.silence_feeding_active and self.system_running:
            try:
                if self.dual_manager.is_maya_connected():
                    self.dual_manager.send_audio_to_maya(silent_data)
                time.sleep(1.0)  # 1000ms intervals
            except Exception as e:
                if self.silence_feeding_active:
                    logger.error(f"Error feeding silence to Maya: {e}")
                    time.sleep(0.1)
    
    def _feed_silence_to_miles(self):
        """Feed silence to Miles"""
        silent_data = np.zeros(self.chunk_size, dtype=np.int16).tobytes()
        
        while self.silence_feeding_active and self.system_running:
            try:
                if self.dual_manager.is_miles_connected():
                    self.dual_manager.send_audio_to_miles(silent_data)
                time.sleep(1.0)  # 1000ms intervals
            except Exception as e:
                if self.silence_feeding_active:
                    logger.error(f"Error feeding silence to Miles: {e}")
                    time.sleep(0.1)
    
    def _print_session_summary(self):
        """Print session summary"""
        if not self.session_start_time:
            return
        
        session_duration = time.time() - self.session_start_time
        
        print("\n" + "="*60)
        print("FINAL CONVERSATION SESSION SUMMARY")
        print("="*60)
        print(f"Total session time: {session_duration:.1f} seconds ({session_duration/60:.1f} minutes)")
        
        if self.recorder:
            print(f"Recording duration: {self.recorder.get_recording_duration():.1f}s")
            print(f"Recording saved: {self.recorder.filename}")
        
        print("="*60)
    
    def run_auto_observe(self, duration):
        """Run automatic observation"""
        if not self.start_system():
            print("❌ Failed to start system")
            return
        
        # Wait for connection
        print("⏳ Waiting for both characters to connect...")
        while not self.dual_manager.is_both_connected():
            time.sleep(1)
        
        # Observe
        print(f"🎙️  Recording final conversation for {duration} seconds...")
        
        start_time = time.time()
        last_status = time.time()
        
        while time.time() - start_time < duration:
            if time.time() - last_status >= 30:
                elapsed = time.time() - start_time
                remaining = duration - elapsed
                print(f"⏱️  Elapsed: {elapsed:.0f}s, Remaining: {remaining:.0f}s")
                last_status = time.time()
            
            time.sleep(1)
        
        self.stop_system()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Final Maya-Miles Conversation System")
    parser.add_argument("--maya-token", default="token.json",
                       help="Path to Maya's token storage file")
    parser.add_argument("--miles-token", default="token2.json",
                       help="Path to Miles's token storage file")
    parser.add_argument("--recording", 
                       help="Output recording filename (auto-generated if not specified)")
    parser.add_argument("--duration", type=int, default=300,
                       help="Recording duration in seconds (default: 300)")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Reduce websocket noise
    logging.getLogger('websocket').setLevel(logging.WARNING)
    
    # Create conversation system
    conversation_system = FinalConversation(
        maya_token_file=args.maya_token,
        miles_token_file=args.miles_token,
        recording_filename=args.recording
    )
    
    conversation_system.initialize_system()
    
    # Run automatic observation
    print("🎙️  Running final conversation recording...")
    print(f"🔑 Using Maya token: {args.maya_token}")
    print(f"🔑 Using Miles token: {args.miles_token}")
    conversation_system.run_auto_observe(args.duration)


if __name__ == "__main__":
    main()















# #!/usr/bin/env python3
# """
# Final Maya-Miles Conversation System

# BASED ON WHAT ACTUALLY WORKS:
# - Only silence feeding (no audio routing)
# - Direct recording of responses
# - Simple and stable

# This is based on silent_conversation.py that achieved 72.7% activity.
# """

# import sys
# import os
# import time
# import threading
# import logging
# import argparse
# import numpy as np
# import wave
# from datetime import datetime

# # Add the current directory to the path so we can import local modules
# sys.path.insert(0, os.path.dirname(__file__))

# from dual_conversation import DualWebSocketManager

# logger = logging.getLogger('sesame.final_conversation')

# class FinalRecorder:
#     """
#     Simple recorder that writes audio immediately
#     """
    
#     def __init__(self, filename=None, sample_rate=24000):
#         if filename is None:
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             filename = f"maya_miles_conversation_{timestamp}.wav"
        
#         self.filename = filename
#         self.sample_rate = sample_rate
#         self.channels = 2  # Stereo
#         self.sample_width = 2  # 16-bit
        
#         self.recording = False
#         self.wav_file = None
#         self.frames_written = 0
#         self.recording_start_time = None
#         self.write_lock = threading.Lock()
        
#         logger.debug(f"FinalRecorder initialized: {filename}")
    
#     def start_recording(self):
#         """Start recording"""
#         if self.recording:
#             return
        
#         logger.info(f"Starting recording: {self.filename}")
        
#         # Open WAV file for writing
#         self.wav_file = wave.open(self.filename, 'wb')
#         self.wav_file.setnchannels(self.channels)
#         self.wav_file.setsampwidth(self.sample_width)
#         self.wav_file.setframerate(self.sample_rate)
        
#         self.recording = True
#         self.recording_start_time = time.time()
#         self.frames_written = 0
        
#         logger.info("Recording started")
    
#     def stop_recording(self):
#         """Stop recording"""
#         if not self.recording:
#             return
        
#         logger.info("Stopping recording...")
#         self.recording = False
        
#         with self.write_lock:
#             if self.wav_file:
#                 self.wav_file.close()
#                 self.wav_file = None
        
#         duration = time.time() - self.recording_start_time if self.recording_start_time else 0
#         logger.info(f"Recording stopped: {self.frames_written} frames, {duration:.1f}s")
        
#         print(f"\n🎵 Recording saved: {self.filename}")
#         print(f"   Duration: {duration:.1f} seconds")
#         print(f"   Frames: {self.frames_written}")
#         print(f"   Format: {self.sample_rate}Hz, 16-bit, Stereo")
#         print(f"   Channels: Left=Maya, Right=Miles")
    
#     def record_audio(self, maya_audio, miles_audio):
#         """Record audio from both characters"""
#         if not self.recording:
#             return
        
#         # Only record if we have audio from at least one character
#         if not maya_audio and not miles_audio:
#             return
        
#         with self.write_lock:
#             if self.wav_file:
#                 # Convert to samples
#                 maya_samples = np.frombuffer(maya_audio, dtype=np.int16) if maya_audio else None
#                 miles_samples = np.frombuffer(miles_audio, dtype=np.int16) if miles_audio else None
                
#                 # Determine frame size
#                 frame_size = 0
#                 if maya_samples is not None:
#                     frame_size = max(frame_size, len(maya_samples))
#                 if miles_samples is not None:
#                     frame_size = max(frame_size, len(miles_samples))
                
#                 if frame_size == 0:
#                     return
                
#                 # Create stereo frame
#                 stereo_samples = np.zeros(frame_size * 2, dtype=np.int16)
                
#                 # Fill left channel with Maya
#                 if maya_samples is not None:
#                     copy_size = min(len(maya_samples), frame_size)
#                     stereo_samples[0::2][:copy_size] = maya_samples[:copy_size]
                
#                 # Fill right channel with Miles
#                 if miles_samples is not None:
#                     copy_size = min(len(miles_samples), frame_size)
#                     stereo_samples[1::2][:copy_size] = miles_samples[:copy_size]
                
#                 self.wav_file.writeframes(stereo_samples.tobytes())
#                 self.frames_written += 1
    
#     def get_recording_duration(self):
#         """Get current recording duration"""
#         if self.recording_start_time:
#             return time.time() - self.recording_start_time
#         return 0.0


# class FinalConversation:
#     """
#     Final conversation system - only silence feeding and recording
#     """
    
#     def __init__(self, token_file=None, recording_filename=None):
#         # Core components
#         self.dual_manager = DualWebSocketManager(token_file=token_file)
#         self.recorder = None
        
#         # System state
#         self.system_running = False
#         self.silence_feeding_active = False
        
#         # Filenames
#         self.recording_filename = recording_filename
        
#         # Audio settings
#         self.chunk_size = 1024
#         self.sample_rate = 16000
        
#         # Statistics
#         self.session_start_time = None
        
#         logger.debug("FinalConversation initialized")
    
#     def initialize_system(self):
#         """Initialize system"""
#         logger.info("Initializing final conversation system...")
        
#         self.dual_manager.set_both_connected_callback(self._on_both_connected)
#         self.dual_manager.set_disconnected_callback(self._on_character_disconnected)
        
#         logger.info("System initialization complete")
    
#     def start_system(self):
#         """Start the system"""
#         if self.system_running:
#             return False
        
#         logger.info("Starting final conversation system...")
#         self.session_start_time = time.time()
        
#         if not self.dual_manager.start():
#             logger.error("Failed to start dual WebSocket connections")
#             return False
        
#         self.system_running = True
#         logger.info("System started successfully")
#         return True
    
#     def stop_system(self):
#         """Stop the system"""
#         if not self.system_running:
#             return
        
#         logger.info("Stopping final conversation system...")
        
#         # Stop silence feeding
#         self.silence_feeding_active = False
        
#         # Stop recording
#         if self.recorder:
#             self.recorder.stop_recording()
        
#         # Stop dual manager
#         self.dual_manager.stop()
#         self.system_running = False
        
#         # Print summary
#         self._print_session_summary()
        
#         logger.info("System stopped")
    
#     def _on_both_connected(self):
#         """When both characters connect"""
#         logger.info("Both characters connected - starting final mode...")
        
#         # Initialize recorder
#         self.recorder = FinalRecorder(filename=self.recording_filename)
#         self.recorder.start_recording()
        
#         # Start recording integration
#         self._start_recording_integration()
        
#         # Start silence feeding
#         self._start_silence_feeding()
        
#         logger.info("Final conversation mode active!")
        
#         print("\n🎉 Maya and Miles are connected!")
#         print("🎵 Stereo recording started (Maya=Left, Miles=Right)")
#         print("\n🎯 FINAL CONVERSATION MODE")
#         print("   🤫 Silence feeding → Both characters")
#         print("   🎙️  Recording their responses to silence")
#         print("   📝 NO audio routing - they respond naturally to silence")
#         print("   ✅ Based on proven working system (72.7% activity)")
    
#     def _on_character_disconnected(self, character):
#         """When character disconnects"""
#         logger.warning(f"{character} disconnected!")
#         print(f"\n⚠️  {character} disconnected!")
    
#     def _start_recording_integration(self):
#         """Start recording integration"""
#         logger.info("Starting recording integration...")
        
#         recording_thread = threading.Thread(target=self._recording_loop)
#         recording_thread.daemon = True
#         recording_thread.start()
        
#         logger.info("Recording integration started")
    
#     def _recording_loop(self):
#         """Recording loop - get audio and record it"""
#         logger.debug("Recording loop started")
        
#         while self.system_running and self.dual_manager.running:
#             try:
#                 # Get audio from both characters
#                 maya_audio = self.dual_manager.get_maya_audio(timeout=0.01)
#                 miles_audio = self.dual_manager.get_miles_audio(timeout=0.01)
                
#                 # Record if we have any audio
#                 if maya_audio or miles_audio:
#                     if self.recorder:
#                         self.recorder.record_audio(maya_audio, miles_audio)
                
#             except Exception as e:
#                 if self.system_running:
#                     logger.error(f"Error in recording loop: {e}")
#                     time.sleep(0.1)
    
#     def _start_silence_feeding(self):
#         """Start silence feeding"""
#         logger.info("Starting silence feeding...")
#         self.silence_feeding_active = True
        
#         # Maya silence thread
#         maya_silence_thread = threading.Thread(target=self._feed_silence_to_maya)
#         maya_silence_thread.daemon = True
#         maya_silence_thread.start()
        
#         # Miles silence thread
#         miles_silence_thread = threading.Thread(target=self._feed_silence_to_miles)
#         miles_silence_thread.daemon = True
#         miles_silence_thread.start()
        
#         logger.info("Silence feeding started")
    
#     def _feed_silence_to_maya(self):
#         """Feed silence to Maya"""
#         silent_data = np.zeros(self.chunk_size, dtype=np.int16).tobytes()
        
#         while self.silence_feeding_active and self.system_running:
#             try:
#                 if self.dual_manager.is_maya_connected():
#                     self.dual_manager.send_audio_to_maya(silent_data)
#                 time.sleep(0.5)  # 500ms intervals
#             except Exception as e:
#                 if self.silence_feeding_active:
#                     logger.error(f"Error feeding silence to Maya: {e}")
#                     time.sleep(0.1)
    
#     def _feed_silence_to_miles(self):
#         """Feed silence to Miles"""
#         silent_data = np.zeros(self.chunk_size, dtype=np.int16).tobytes()
        
#         while self.silence_feeding_active and self.system_running:
#             try:
#                 if self.dual_manager.is_miles_connected():
#                     self.dual_manager.send_audio_to_miles(silent_data)
#                 time.sleep(0.5)  # 500ms intervals
#             except Exception as e:
#                 if self.silence_feeding_active:
#                     logger.error(f"Error feeding silence to Miles: {e}")
#                     time.sleep(0.1)
    
#     def _print_session_summary(self):
#         """Print session summary"""
#         if not self.session_start_time:
#             return
        
#         session_duration = time.time() - self.session_start_time
        
#         print("\n" + "="*60)
#         print("FINAL CONVERSATION SESSION SUMMARY")
#         print("="*60)
#         print(f"Total session time: {session_duration:.1f} seconds ({session_duration/60:.1f} minutes)")
        
#         if self.recorder:
#             print(f"Recording duration: {self.recorder.get_recording_duration():.1f}s")
#             print(f"Recording saved: {self.recorder.filename}")
        
#         print("="*60)
    
#     def run_auto_observe(self, duration):
#         """Run automatic observation"""
#         if not self.start_system():
#             print("❌ Failed to start system")
#             return
        
#         # Wait for connection
#         print("⏳ Waiting for both characters to connect...")
#         while not self.dual_manager.is_both_connected():
#             time.sleep(1)
        
#         # Observe
#         print(f"🎙️  Recording final conversation for {duration} seconds...")
        
#         start_time = time.time()
#         last_status = time.time()
        
#         while time.time() - start_time < duration:
#             if time.time() - last_status >= 30:
#                 elapsed = time.time() - start_time
#                 remaining = duration - elapsed
#                 print(f"⏱️  Elapsed: {elapsed:.0f}s, Remaining: {remaining:.0f}s")
#                 last_status = time.time()
            
#             time.sleep(1)
        
#         self.stop_system()


# def main():
#     """Main function"""
#     parser = argparse.ArgumentParser(description="Final Maya-Miles Conversation System")
#     parser.add_argument("--token-file", default="token.json",
#                        help="Path to token storage file")
#     parser.add_argument("--recording", 
#                        help="Output recording filename (auto-generated if not specified)")
#     parser.add_argument("--duration", type=int, default=300,
#                        help="Recording duration in seconds (default: 300)")
#     parser.add_argument("--debug", action="store_true",
#                        help="Enable debug logging")
    
#     args = parser.parse_args()
    
#     # Configure logging
#     log_level = logging.DEBUG if args.debug else logging.INFO
#     logging.basicConfig(
#         level=log_level,
#         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#         datefmt='%Y-%m-%d %H:%M:%S'
#     )
    
#     # Reduce websocket noise
#     logging.getLogger('websocket').setLevel(logging.WARNING)
    
#     # Create conversation system
#     conversation_system = FinalConversation(
#         token_file=args.token_file,
#         recording_filename=args.recording
#     )
    
#     conversation_system.initialize_system()
    
#     # Run automatic observation
#     print("🎙️  Running final conversation recording...")
#     conversation_system.run_auto_observe(args.duration)


# if __name__ == "__main__":
#     main()