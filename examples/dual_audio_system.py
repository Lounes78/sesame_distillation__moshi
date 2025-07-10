#!/usr/bin/env python3
"""
Dual Audio System with Individual Recording

This system:
1. Routes audio from Maya to Miles
2. Routes audio from Miles to Maya
3. Records Maya's output to a separate WAV file
4. Records Miles's output to a separate WAV file
"""

import sys
import os
import time
import threading
import logging
import queue
import wave
import numpy as np
from datetime import datetime
import argparse

# Add the current directory to the path so we can import local modules
sys.path.insert(0, os.path.dirname(__file__))

from dual_conversation import DualWebSocketManager

logger = logging.getLogger('sesame.dual_audio_system')

class IndividualRecorder:
    """
    Records audio for a single character to a WAV file
    """
    
    def __init__(self, character_name, filename=None, sample_rate=24000):
        """
        Initialize the individual recorder
        
        Args:
            character_name (str): Name of the character ("Maya" or "Miles")
            filename (str, optional): Output filename. If None, generates timestamp-based name.
            sample_rate (int): Audio sample rate (default: 24000)
        """
        self.character_name = character_name
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{character_name.lower()}_output_{timestamp}.wav"
        
        self.filename = filename
        self.sample_rate = sample_rate
        self.channels = 1  # Mono
        self.sample_width = 2  # 16-bit
        
        # Audio buffer
        self.audio_buffer = queue.Queue(maxsize=1000)
        
        # Recording control
        self.recording = False
        self.recording_thread = None
        self.wav_file = None
        
        # Statistics
        self.frames_written = 0
        self.recording_start_time = None
        
        logger.debug(f"IndividualRecorder initialized for {character_name}: {filename}")
    
    def start_recording(self):
        """Start recording"""
        if self.recording:
            logger.warning(f"Recording already in progress for {self.character_name}")
            return
        
        logger.info(f"Starting recording for {self.character_name}: {self.filename}")
        
        # Open WAV file for writing
        self.wav_file = wave.open(self.filename, 'wb')
        self.wav_file.setnchannels(self.channels)
        self.wav_file.setsampwidth(self.sample_width)
        self.wav_file.setframerate(self.sample_rate)
        
        self.recording = True
        self.recording_start_time = time.time()
        self.frames_written = 0
        
        # Start recording thread
        self.recording_thread = threading.Thread(target=self._recording_loop)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
        logger.info(f"Recording started for {self.character_name}")
    
    def stop_recording(self):
        """Stop recording"""
        if not self.recording:
            return
        
        logger.info(f"Stopping recording for {self.character_name}...")
        self.recording = False
        
        # Wait for recording thread to finish
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
        
        # Close WAV file
        if self.wav_file:
            self.wav_file.close()
            self.wav_file = None
        
        # Print recording statistics
        duration = time.time() - self.recording_start_time if self.recording_start_time else 0
        logger.info(f"Recording stopped for {self.character_name}: {self.frames_written} frames, {duration:.1f}s")
        
        print(f"\n🎵 {self.character_name} recording saved: {self.filename}")
        print(f"   Duration: {duration:.1f} seconds")
        print(f"   Frames: {self.frames_written}")
        print(f"   Format: {self.sample_rate}Hz, 16-bit, Mono")
    
    def add_audio(self, audio_data):
        """Add audio data to the recording buffer"""
        if self.recording and audio_data:
            try:
                self.audio_buffer.put_nowait(audio_data)
            except queue.Full:
                # If buffer is full, remove oldest and add new
                try:
                    self.audio_buffer.get_nowait()
                    self.audio_buffer.put_nowait(audio_data)
                except queue.Empty:
                    pass
    
    def _recording_loop(self):
        """Main recording loop"""
        logger.debug(f"Recording loop started for {self.character_name}")
        
        while self.recording:
            try:
                # Get audio from buffer (with timeout)
                audio_data = None
                
                try:
                    audio_data = self.audio_buffer.get(timeout=0.01)
                except queue.Empty:
                    continue
                
                if audio_data:
                    # Write directly to WAV file
                    self.wav_file.writeframes(audio_data)
                    self.frames_written += 1
                
            except Exception as e:
                if self.recording:
                    logger.error(f"Error in recording loop for {self.character_name}: {e}", exc_info=True)
                    time.sleep(0.1)
    
    def is_recording(self):
        """Check if currently recording"""
        return self.recording
    
    def get_recording_duration(self):
        """Get current recording duration in seconds"""
        if self.recording_start_time:
            return time.time() - self.recording_start_time
        return 0.0


class DualAudioRouter:
    """
    Routes audio between Maya and Miles while recording each separately
    """
    
    def __init__(self, dual_manager, maya_recorder=None, miles_recorder=None):
        """
        Initialize the dual audio router
        
        Args:
            dual_manager (DualWebSocketManager): The dual connection manager
            maya_recorder (IndividualRecorder, optional): Maya's recorder
            miles_recorder (IndividualRecorder, optional): Miles's recorder
        """
        self.dual_manager = dual_manager
        self.maya_recorder = maya_recorder
        self.miles_recorder = miles_recorder
        
        # Audio routing control
        self.routing_enabled = False
        self.routing_threads = []
        
        # Statistics
        self.stats = {
            "maya_to_miles_packets": 0,
            "miles_to_maya_packets": 0,
            "maya_audio_recorded": 0,
            "miles_audio_recorded": 0
        }
        
        logger.debug("DualAudioRouter initialized")
    
    def start_routing(self):
        """Start audio routing between characters"""
        if self.routing_enabled:
            logger.warning("Audio routing already enabled")
            return
        
        logger.info("Starting dual audio routing...")
        self.routing_enabled = True
        
        # Start routing threads
        maya_to_miles_thread = threading.Thread(target=self._route_maya_to_miles)
        miles_to_maya_thread = threading.Thread(target=self._route_miles_to_maya)
        
        maya_to_miles_thread.daemon = True
        miles_to_maya_thread.daemon = True
        
        maya_to_miles_thread.start()
        miles_to_maya_thread.start()
        
        self.routing_threads = [maya_to_miles_thread, miles_to_maya_thread]
        
        logger.info("Dual audio routing started successfully")
    
    def stop_routing(self):
        """Stop audio routing"""
        if not self.routing_enabled:
            return
        
        logger.info("Stopping dual audio routing...")
        self.routing_enabled = False
        
        # Wait for threads to finish
        for thread in self.routing_threads:
            if thread.is_alive():
                thread.join(timeout=1.0)
        
        self.routing_threads = []
        logger.info("Dual audio routing stopped")
    
    def _route_maya_to_miles(self):
        """Route Maya's audio to Miles and record it"""
        logger.debug("Maya -> Miles routing started")
        
        while self.routing_enabled and self.dual_manager.running:
            try:
                # Get audio from Maya
                maya_audio = self.dual_manager.get_maya_audio(timeout=0.01)
                if maya_audio:
                    # Record Maya's audio
                    if self.maya_recorder:
                        self.maya_recorder.add_audio(maya_audio)
                        self.stats["maya_audio_recorded"] += 1
                    
                    # Send Maya's audio to Miles
                    if self.dual_manager.send_audio_to_miles(maya_audio):
                        self.stats["maya_to_miles_packets"] += 1
                        
            except Exception as e:
                if self.routing_enabled:
                    logger.error(f"Error routing Maya -> Miles: {e}", exc_info=True)
                    time.sleep(0.1)
    
    def _route_miles_to_maya(self):
        """Route Miles's audio to Maya and record it"""
        logger.debug("Miles -> Maya routing started")
        
        while self.routing_enabled and self.dual_manager.running:
            try:
                # Get audio from Miles
                miles_audio = self.dual_manager.get_miles_audio(timeout=0.01)
                if miles_audio:
                    # Record Miles's audio
                    if self.miles_recorder:
                        self.miles_recorder.add_audio(miles_audio)
                        self.stats["miles_audio_recorded"] += 1
                    
                    # Send Miles's audio to Maya
                    if self.dual_manager.send_audio_to_maya(miles_audio):
                        self.stats["miles_to_maya_packets"] += 1
                        
            except Exception as e:
                if self.routing_enabled:
                    logger.error(f"Error routing Miles -> Maya: {e}", exc_info=True)
                    time.sleep(0.1)
    
    def get_stats(self):
        """Get routing statistics"""
        return self.stats.copy()
    
    def print_stats(self):
        """Print routing statistics"""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("DUAL AUDIO ROUTING STATISTICS")
        print("="*60)
        print("Audio Routing:")
        print(f"  Maya -> Miles packets: {stats['maya_to_miles_packets']}")
        print(f"  Miles -> Maya packets: {stats['miles_to_maya_packets']}")
        print()
        print("Audio Recording:")
        print(f"  Maya audio chunks recorded: {stats['maya_audio_recorded']}")
        print(f"  Miles audio chunks recorded: {stats['miles_audio_recorded']}")
        print("="*60)


class DualAudioSystem:
    """
    Complete dual audio system with routing and individual recording
    """
    
    def __init__(self, token_file=None, maya_filename=None, miles_filename=None):
        """
        Initialize the dual audio system
        
        Args:
            token_file (str, optional): Path to token storage file
            maya_filename (str, optional): Maya's output filename
            miles_filename (str, optional): Miles's output filename
        """
        # Core components
        self.dual_manager = DualWebSocketManager(token_file=token_file)
        self.maya_recorder = IndividualRecorder("Maya", maya_filename)
        self.miles_recorder = IndividualRecorder("Miles", miles_filename)
        self.audio_router = None
        
        # System state
        self.system_running = False
        self.session_start_time = None
        
        logger.debug("DualAudioSystem initialized")
    
    def initialize_system(self):
        """Initialize all system components"""
        logger.info("Initializing dual audio system...")
        
        # Set up dual connection callbacks
        self.dual_manager.set_both_connected_callback(self._on_both_connected)
        self.dual_manager.set_disconnected_callback(self._on_character_disconnected)
        
        logger.info("System initialization complete")
    
    def start_system(self):
        """Start the dual audio system"""
        if self.system_running:
            logger.warning("System already running")
            return False
        
        logger.info("Starting dual audio system...")
        self.session_start_time = time.time()
        
        # Start dual WebSocket connections
        if not self.dual_manager.start():
            logger.error("Failed to start dual WebSocket connections")
            return False
        
        self.system_running = True
        logger.info("System started successfully")
        return True
    
    def stop_system(self):
        """Stop the dual audio system"""
        if not self.system_running:
            return
        
        logger.info("Stopping dual audio system...")
        
        # Stop audio routing
        if self.audio_router:
            self.audio_router.stop_routing()
        
        # Stop recordings
        self.maya_recorder.stop_recording()
        self.miles_recorder.stop_recording()
        
        # Stop dual manager
        self.dual_manager.stop()
        
        self.system_running = False
        
        # Print session summary
        self._print_session_summary()
        
        logger.info("System stopped")
    
    def _on_both_connected(self):
        """Callback when both Maya and Miles are connected"""
        logger.info("Both characters connected - initializing audio system...")
        
        # Initialize audio router with recorders
        self.audio_router = DualAudioRouter(
            self.dual_manager, 
            self.maya_recorder, 
            self.miles_recorder
        )
        
        # Start recordings
        self.maya_recorder.start_recording()
        self.miles_recorder.start_recording()
        
        # Start audio routing
        self.audio_router.start_routing()
        
        logger.info("Dual audio system fully operational!")
        
        print("\n🎉 Maya and Miles are connected!")
        print("🎵 Individual recordings started:")
        print(f"   📹 Maya: {self.maya_recorder.filename}")
        print(f"   📹 Miles: {self.miles_recorder.filename}")
        print("\n🔄 DUAL AUDIO ROUTING ACTIVE")
        print("   📤 Maya's audio → Miles")
        print("   📤 Miles's audio → Maya")
        print("   🎙️ Recording each character separately")
    
    def _on_character_disconnected(self, character):
        """Callback when a character disconnects"""
        logger.warning(f"{character} disconnected!")
        print(f"\n⚠️  {character} disconnected!")
    
    def get_status(self):
        """Get current system status"""
        status = {
            "system_running": self.system_running,
            "both_connected": self.dual_manager.is_both_connected() if self.dual_manager else False,
            "maya_connected": self.dual_manager.is_maya_connected() if self.dual_manager else False,
            "miles_connected": self.dual_manager.is_miles_connected() if self.dual_manager else False,
            "maya_recording": self.maya_recorder.is_recording(),
            "miles_recording": self.miles_recorder.is_recording(),
            "routing_active": self.audio_router.routing_enabled if self.audio_router else False
        }
        
        status["maya_recording_duration"] = self.maya_recorder.get_recording_duration()
        status["miles_recording_duration"] = self.miles_recorder.get_recording_duration()
        
        return status
    
    def print_status(self):
        """Print current system status"""
        status = self.get_status()
        
        print("\n" + "="*60)
        print("DUAL AUDIO SYSTEM STATUS")
        print("="*60)
        
        # System status
        print("🔧 System Status:")
        print(f"   Running: {'✅' if status['system_running'] else '❌'}")
        print(f"   Maya Connected: {'✅' if status['maya_connected'] else '❌'}")
        print(f"   Miles Connected: {'✅' if status['miles_connected'] else '❌'}")
        print()
        
        # Recording status
        print("🎵 Recording Status:")
        print(f"   Maya Recording: {'✅' if status['maya_recording'] else '❌'}")
        print(f"   Maya Duration: {status['maya_recording_duration']:.1f}s")
        print(f"   Miles Recording: {'✅' if status['miles_recording'] else '❌'}")
        print(f"   Miles Duration: {status['miles_recording_duration']:.1f}s")
        print()
        
        # Routing status
        print("🔄 Routing Status:")
        print(f"   Active: {'✅' if status['routing_active'] else '❌'}")
        
        # Routing stats
        if self.audio_router:
            routing_stats = self.audio_router.get_stats()
            print(f"   Maya -> Miles packets: {routing_stats['maya_to_miles_packets']}")
            print(f"   Miles -> Maya packets: {routing_stats['miles_to_maya_packets']}")
            print(f"   Maya chunks recorded: {routing_stats['maya_audio_recorded']}")
            print(f"   Miles chunks recorded: {routing_stats['miles_audio_recorded']}")
        
        print("="*60)
    
    def _print_session_summary(self):
        """Print session summary"""
        if not self.session_start_time:
            return
        
        session_duration = time.time() - self.session_start_time
        
        print("\n" + "="*60)
        print("DUAL AUDIO SYSTEM SESSION SUMMARY")
        print("="*60)
        print(f"Total session time: {session_duration:.1f} seconds ({session_duration/60:.1f} minutes)")
        print()
        print("Recordings:")
        print(f"  Maya: {self.maya_recorder.filename} ({self.maya_recorder.get_recording_duration():.1f}s)")
        print(f"  Miles: {self.miles_recorder.filename} ({self.miles_recorder.get_recording_duration():.1f}s)")
        print()
        
        if self.audio_router:
            routing_stats = self.audio_router.get_stats()
            print("Audio Routing:")
            print(f"  Total packets routed: {routing_stats['maya_to_miles_packets'] + routing_stats['miles_to_maya_packets']}")
            print(f"  Total chunks recorded: {routing_stats['maya_audio_recorded'] + routing_stats['miles_audio_recorded']}")
        
        print("="*60)
    
    def run_auto_observe(self, duration):
        """Run automatic observation for specified duration"""
        if not self.start_system():
            print("❌ Failed to start system")
            return
        
        # Wait for connection
        print("⏳ Waiting for both characters to connect...")
        while not self.dual_manager.is_both_connected():
            time.sleep(1)
        
        # Observe for specified duration
        print(f"🎙️  Running dual audio system for {duration} seconds...")
        
        start_time = time.time()
        last_status = time.time()
        
        while time.time() - start_time < duration:
            # Show status every 30 seconds
            if time.time() - last_status >= 30:
                elapsed = time.time() - start_time
                remaining = duration - elapsed
                print(f"⏱️  Elapsed: {elapsed:.0f}s, Remaining: {remaining:.0f}s")
                last_status = time.time()
            
            time.sleep(1)
        
        # Stop system
        self.stop_system()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Dual Audio System with Individual Recording")
    parser.add_argument("--token-file", default="token.json",
                       help="Path to token storage file")
    parser.add_argument("--maya-output", 
                       help="Maya's output recording filename (auto-generated if not specified)")
    parser.add_argument("--miles-output", 
                       help="Miles's output recording filename (auto-generated if not specified)")
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
    
    # Create dual audio system
    audio_system = DualAudioSystem(
        token_file=args.token_file,
        maya_filename=args.maya_output,
        miles_filename=args.miles_output
    )
    
    audio_system.initialize_system()
    
    # Run automatic observation
    print("🎙️  Starting Dual Audio System...")
    print("📋 Features:")
    print("   ✅ Maya audio → Miles")
    print("   ✅ Miles audio → Maya") 
    print("   ✅ Maya output recorded separately")
    print("   ✅ Miles output recorded separately")
    
    audio_system.run_auto_observe(args.duration)


if __name__ == "__main__":
    main()