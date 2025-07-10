#!/usr/bin/env python3
"""
Dual Character Conversation System

This module manages simultaneous connections to both Maya and Miles characters,
enabling them to have conversations with each other while recording the audio
in stereo format (Maya on left channel, Miles on right channel).
"""

import sys
import os
import time
import threading
import logging
import queue
import numpy as np
from datetime import datetime
import sys
import os
# Add the parent directory to the path so we can import sesame_ai
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sesame_ai import SesameAI, SesameWebSocket, TokenManager, InvalidTokenError, NetworkError, APIError

logger = logging.getLogger('sesame.dual_conversation')

class DualWebSocketManager:
    """
    Manages dual WebSocket connections for Maya and Miles characters
    """
    
    def __init__(self, maya_token_file="token.json", miles_token_file="token2.json"):
        """
        Initialize the dual WebSocket manager
        
        Args:
            maya_token_file (str): Path to Maya's token storage file
            miles_token_file (str): Path to Miles's token storage file
        """
        # API clients and token managers for each character
        self.maya_api_client = SesameAI()
        self.miles_api_client = SesameAI()
        
        self.maya_token_manager = TokenManager(self.maya_api_client, token_file=maya_token_file)
        self.miles_token_manager = TokenManager(self.miles_api_client, token_file=miles_token_file)
        
        # WebSocket clients
        self.maya_ws = None
        self.miles_ws = None
        
        # Tokens
        self.maya_token = None
        self.miles_token = None
        
        # Connection state
        self.maya_connected = threading.Event()
        self.miles_connected = threading.Event()
        self.both_connected = threading.Event()
        
        # Audio queues for each character
        self.maya_audio_queue = queue.Queue(maxsize=1000)
        self.miles_audio_queue = queue.Queue(maxsize=1000)
        
        # Connection callbacks
        self.on_both_connected_callback = None
        self.on_disconnected_callback = None
        
        # Thread control
        self.running = False
        self.threads = []
        
        logger.debug("DualWebSocketManager initialized with separate token files")
    
    def authenticate(self):
        """
        Authenticate and get tokens for both connections
        
        Returns:
            bool: True if authentication successful
        """
        logger.info("Authenticating for dual connections...")
        try:
            # Get tokens for both characters
            self.maya_token = self.maya_token_manager.get_valid_token()
            self.miles_token = self.miles_token_manager.get_valid_token()
            
            logger.info("Authentication successful for both characters!")
            return True
        except (InvalidTokenError, NetworkError, APIError) as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def connect_both_characters(self):
        """
        Connect to both Maya and Miles simultaneously
        
        Returns:
            bool: True if both connections successful
        """
        logger.info("Connecting to both Maya and Miles...")
        
        # Reset connection events
        self.maya_connected.clear()
        self.miles_connected.clear()
        self.both_connected.clear()
        
        # Create WebSocket clients with separate tokens
        self.maya_ws = SesameWebSocket(
            id_token=self.maya_token,
            character="Maya"
        )
        
        self.miles_ws = SesameWebSocket(
            id_token=self.miles_token,
            character="Miles"
        )
        
        # Set up callbacks for Maya
        self.maya_ws.set_connect_callback(self._on_maya_connected)
        self.maya_ws.set_disconnect_callback(self._on_maya_disconnected)
        
        # Set up callbacks for Miles
        self.miles_ws.set_connect_callback(self._on_miles_connected)
        self.miles_ws.set_disconnect_callback(self._on_miles_disconnected)
        
        # Start connection threads
        maya_thread = threading.Thread(target=self._connect_maya)
        miles_thread = threading.Thread(target=self._connect_miles)
        
        maya_thread.daemon = True
        miles_thread.daemon = True
        
        maya_thread.start()
        miles_thread.start()
        
        self.threads.extend([maya_thread, miles_thread])
        
        # Wait for both connections (timeout after 30 seconds)
        logger.info("Waiting for both characters to connect...")
        if self.both_connected.wait(timeout=30):
            logger.info("Both Maya and Miles connected successfully!")
            return True
        else:
            logger.error("Failed to connect both characters within timeout")
            return False
    
    def _connect_maya(self):
        """Connect Maya in a separate thread"""
        try:
            logger.debug("Connecting Maya...")
            if self.maya_ws.connect(blocking=True):
                logger.debug("Maya connection established")
            else:
                logger.error("Maya connection failed")
        except Exception as e:
            logger.error(f"Error connecting Maya: {e}", exc_info=True)
    
    def _connect_miles(self):
        """Connect Miles in a separate thread"""
        try:
            logger.debug("Connecting Miles...")
            if self.miles_ws.connect(blocking=True):
                logger.debug("Miles connection established")
            else:
                logger.error("Miles connection failed")
        except Exception as e:
            logger.error(f"Error connecting Miles: {e}", exc_info=True)
    
    def _on_maya_connected(self):
        """Callback when Maya connects"""
        logger.info("Maya connected!")
        self.maya_connected.set()
        self._check_both_connected()
        
        # Start Maya audio processing
        maya_audio_thread = threading.Thread(target=self._process_maya_audio)
        maya_audio_thread.daemon = True
        maya_audio_thread.start()
        self.threads.append(maya_audio_thread)
    
    def _on_miles_connected(self):
        """Callback when Miles connects"""
        logger.info("Miles connected!")
        self.miles_connected.set()
        self._check_both_connected()
        
        # Start Miles audio processing
        miles_audio_thread = threading.Thread(target=self._process_miles_audio)
        miles_audio_thread.daemon = True
        miles_audio_thread.start()
        self.threads.append(miles_audio_thread)
    
    def _check_both_connected(self):
        """Check if both characters are connected and trigger callback"""
        if self.maya_connected.is_set() and self.miles_connected.is_set():
            self.both_connected.set()
            logger.info("Both characters are now connected!")
            
            if self.on_both_connected_callback:
                self.on_both_connected_callback()
    
    def _on_maya_disconnected(self):
        """Callback when Maya disconnects"""
        logger.warning("Maya disconnected!")
        self.maya_connected.clear()
        self.both_connected.clear()
        
        if self.on_disconnected_callback:
            self.on_disconnected_callback("Maya")
    
    def _on_miles_disconnected(self):
        """Callback when Miles disconnects"""
        logger.warning("Miles disconnected!")
        self.miles_connected.clear()
        self.both_connected.clear()
        
        if self.on_disconnected_callback:
            self.on_disconnected_callback("Miles")
    
    def _process_maya_audio(self):
        """Process incoming audio from Maya"""
        logger.debug("Maya audio processing started")
        
        while self.running and self.maya_ws and self.maya_ws.is_connected():
            try:
                # Get audio chunk from Maya
                audio_chunk = self.maya_ws.get_next_audio_chunk(timeout=0.01)
                if audio_chunk:
                    # Add to Maya's audio queue
                    try:
                        self.maya_audio_queue.put_nowait(audio_chunk)
                    except queue.Full:
                        # If queue is full, remove oldest and add new
                        try:
                            self.maya_audio_queue.get_nowait()
                            self.maya_audio_queue.put_nowait(audio_chunk)
                        except queue.Empty:
                            pass
            except Exception as e:
                if self.running:
                    logger.error(f"Error processing Maya audio: {e}", exc_info=True)
                    time.sleep(0.1)
    
    def _process_miles_audio(self):
        """Process incoming audio from Miles"""
        logger.debug("Miles audio processing started")
        
        while self.running and self.miles_ws and self.miles_ws.is_connected():
            try:
                # Get audio chunk from Miles
                audio_chunk = self.miles_ws.get_next_audio_chunk(timeout=0.01)
                if audio_chunk:
                    # Add to Miles's audio queue
                    try:
                        self.miles_audio_queue.put_nowait(audio_chunk)
                    except queue.Full:
                        # If queue is full, remove oldest and add new
                        try:
                            self.miles_audio_queue.get_nowait()
                            self.miles_audio_queue.put_nowait(audio_chunk)
                        except queue.Empty:
                            pass
            except Exception as e:
                if self.running:
                    logger.error(f"Error processing Miles audio: {e}", exc_info=True)
                    time.sleep(0.1)
    
    def send_audio_to_maya(self, audio_data):
        """
        Send audio data to Maya
        
        Args:
            audio_data (bytes): Raw audio data
            
        Returns:
            bool: True if sent successfully
        """
        if self.maya_ws and self.maya_ws.is_connected():
            return self.maya_ws.send_audio_data(audio_data)
        return False
    
    def send_audio_to_miles(self, audio_data):
        """
        Send audio data to Miles
        
        Args:
            audio_data (bytes): Raw audio data
            
        Returns:
            bool: True if sent successfully
        """
        if self.miles_ws and self.miles_ws.is_connected():
            return self.miles_ws.send_audio_data(audio_data)
        return False
    
    def get_maya_audio(self, timeout=None):
        """
        Get next audio chunk from Maya
        
        Args:
            timeout (float, optional): Timeout in seconds
            
        Returns:
            bytes: Audio data or None if timeout
        """
        try:
            return self.maya_audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_miles_audio(self, timeout=None):
        """
        Get next audio chunk from Miles
        
        Args:
            timeout (float, optional): Timeout in seconds
            
        Returns:
            bytes: Audio data or None if timeout
        """
        try:
            return self.miles_audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def is_both_connected(self):
        """
        Check if both characters are connected
        
        Returns:
            bool: True if both Maya and Miles are connected
        """
        return self.both_connected.is_set()
    
    def is_maya_connected(self):
        """Check if Maya is connected"""
        return self.maya_connected.is_set()
    
    def is_miles_connected(self):
        """Check if Miles is connected"""
        return self.miles_connected.is_set()
    
    def set_both_connected_callback(self, callback):
        """
        Set callback for when both characters are connected
        
        Args:
            callback (callable): Function with no arguments
        """
        self.on_both_connected_callback = callback
    
    def set_disconnected_callback(self, callback):
        """
        Set callback for when a character disconnects
        
        Args:
            callback (callable): Function with character name argument
        """
        self.on_disconnected_callback = callback
    
    def start(self):
        """
        Start the dual connection system
        
        Returns:
            bool: True if startup successful
        """
        # Authenticate
        if not self.authenticate():
            return False
        
        # Set running flag
        self.running = True
        
        # Connect both characters
        if not self.connect_both_characters():
            self.running = False
            return False
        
        logger.info("Dual WebSocket system started successfully!")
        return True
    
    def stop(self):
        """Stop the dual connection system"""
        if not self.running:
            return
        
        self.running = False
        logger.info("Stopping dual WebSocket system...")
        
        # Disconnect WebSockets
        if self.maya_ws and self.maya_ws.is_connected():
            self.maya_ws.disconnect()
        
        if self.miles_ws and self.miles_ws.is_connected():
            self.miles_ws.disconnect()
        
        # Clear connection events
        self.maya_connected.clear()
        self.miles_connected.clear()
        self.both_connected.clear()
        
        logger.info("Dual WebSocket system stopped")
    
    def run(self):
        """Run the dual connection system"""
        try:
            if self.start():
                # Keep main thread alive
                while self.running and self.is_both_connected():
                    time.sleep(0.1)
        except KeyboardInterrupt:
            logger.debug("Interrupted by user")
        finally:
            self.stop()


def main():
    """Test the dual WebSocket connection system"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set websocket-client logger to WARNING level
    logging.getLogger('websocket').setLevel(logging.WARNING)
    
    # Create dual connection manager with separate token files
    dual_manager = DualWebSocketManager(
        maya_token_file="token.json",
        miles_token_file="token2.json"
    )
    
    # Set up callbacks
    def on_both_connected():
        print("\n🎉 Both Maya and Miles are connected and ready!")
        print("You can now start the conversation system...")
    
    def on_disconnected(character):
        print(f"\n⚠️  {character} disconnected!")
    
    dual_manager.set_both_connected_callback(on_both_connected)
    dual_manager.set_disconnected_callback(on_disconnected)
    
    # Run the system
    print("Starting dual WebSocket connection test...")
    print("Press Ctrl+C to exit")
    dual_manager.run()


if __name__ == "__main__":
    main()















# #!/usr/bin/env python3
# """
# Dual Character Conversation System

# This module manages simultaneous connections to both Maya and Miles characters,
# enabling them to have conversations with each other while recording the audio
# in stereo format (Maya on left channel, Miles on right channel).
# """

# import sys
# import os
# import time
# import threading
# import logging
# import queue
# import numpy as np
# from datetime import datetime
# import sys
# import os
# # Add the parent directory to the path so we can import sesame_ai
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# from sesame_ai import SesameAI, SesameWebSocket, TokenManager, InvalidTokenError, NetworkError, APIError

# logger = logging.getLogger('sesame.dual_conversation')

# class DualWebSocketManager:
#     """
#     Manages dual WebSocket connections for Maya and Miles characters
#     """
    
#     def __init__(self, token_file=None):
#         """
#         Initialize the dual WebSocket manager
        
#         Args:
#             token_file (str, optional): Path to token storage file
#         """
#         # API client and token manager
#         self.api_client = SesameAI()
#         self.token_manager = TokenManager(self.api_client, token_file=token_file)
        
#         # WebSocket clients
#         self.maya_ws = None
#         self.miles_ws = None
        
#         # Connection state
#         self.maya_connected = threading.Event()
#         self.miles_connected = threading.Event()
#         self.both_connected = threading.Event()
        
#         # Audio queues for each character
#         self.maya_audio_queue = queue.Queue(maxsize=1000)
#         self.miles_audio_queue = queue.Queue(maxsize=1000)
        
#         # Connection callbacks
#         self.on_both_connected_callback = None
#         self.on_disconnected_callback = None
        
#         # Thread control
#         self.running = False
#         self.threads = []
        
#         logger.debug("DualWebSocketManager initialized")
    
#     def authenticate(self):
#         """
#         Authenticate and get tokens for both connections
        
#         Returns:
#             bool: True if authentication successful
#         """
#         logger.info("Authenticating for dual connections...")
#         try:
#             # Get a valid token - we'll use the same token for both connections
#             self.id_token = self.token_manager.get_valid_token()
#             logger.info("Authentication successful!")
#             return True
#         except (InvalidTokenError, NetworkError, APIError) as e:
#             logger.error(f"Authentication failed: {e}")
#             return False
    
#     def connect_both_characters(self):
#         """
#         Connect to both Maya and Miles simultaneously
        
#         Returns:
#             bool: True if both connections successful
#         """
#         logger.info("Connecting to both Maya and Miles...")
        
#         # Reset connection events
#         self.maya_connected.clear()
#         self.miles_connected.clear()
#         self.both_connected.clear()
        
#         # Create WebSocket clients
#         self.maya_ws = SesameWebSocket(
#             id_token=self.id_token,
#             character="Maya"
#         )
        
#         self.miles_ws = SesameWebSocket(
#             id_token=self.id_token,
#             character="Miles"
#         )
        
#         # Set up callbacks for Maya
#         self.maya_ws.set_connect_callback(self._on_maya_connected)
#         self.maya_ws.set_disconnect_callback(self._on_maya_disconnected)
        
#         # Set up callbacks for Miles
#         self.miles_ws.set_connect_callback(self._on_miles_connected)
#         self.miles_ws.set_disconnect_callback(self._on_miles_disconnected)
        
#         # Start connection threads
#         maya_thread = threading.Thread(target=self._connect_maya)
#         miles_thread = threading.Thread(target=self._connect_miles)
        
#         maya_thread.daemon = True
#         miles_thread.daemon = True
        
#         maya_thread.start()
#         miles_thread.start()
        
#         self.threads.extend([maya_thread, miles_thread])
        
#         # Wait for both connections (timeout after 30 seconds)
#         logger.info("Waiting for both characters to connect...")
#         if self.both_connected.wait(timeout=30):
#             logger.info("Both Maya and Miles connected successfully!")
#             return True
#         else:
#             logger.error("Failed to connect both characters within timeout")
#             return False
    
#     def _connect_maya(self):
#         """Connect Maya in a separate thread"""
#         try:
#             logger.debug("Connecting Maya...")
#             if self.maya_ws.connect(blocking=True):
#                 logger.debug("Maya connection established")
#             else:
#                 logger.error("Maya connection failed")
#         except Exception as e:
#             logger.error(f"Error connecting Maya: {e}", exc_info=True)
    
#     def _connect_miles(self):
#         """Connect Miles in a separate thread"""
#         try:
#             logger.debug("Connecting Miles...")
#             if self.miles_ws.connect(blocking=True):
#                 logger.debug("Miles connection established")
#             else:
#                 logger.error("Miles connection failed")
#         except Exception as e:
#             logger.error(f"Error connecting Miles: {e}", exc_info=True)
    
#     def _on_maya_connected(self):
#         """Callback when Maya connects"""
#         logger.info("Maya connected!")
#         self.maya_connected.set()
#         self._check_both_connected()
        
#         # Start Maya audio processing
#         maya_audio_thread = threading.Thread(target=self._process_maya_audio)
#         maya_audio_thread.daemon = True
#         maya_audio_thread.start()
#         self.threads.append(maya_audio_thread)
    
#     def _on_miles_connected(self):
#         """Callback when Miles connects"""
#         logger.info("Miles connected!")
#         self.miles_connected.set()
#         self._check_both_connected()
        
#         # Start Miles audio processing
#         miles_audio_thread = threading.Thread(target=self._process_miles_audio)
#         miles_audio_thread.daemon = True
#         miles_audio_thread.start()
#         self.threads.append(miles_audio_thread)
    
#     def _check_both_connected(self):
#         """Check if both characters are connected and trigger callback"""
#         if self.maya_connected.is_set() and self.miles_connected.is_set():
#             self.both_connected.set()
#             logger.info("Both characters are now connected!")
            
#             if self.on_both_connected_callback:
#                 self.on_both_connected_callback()
    
#     def _on_maya_disconnected(self):
#         """Callback when Maya disconnects"""
#         logger.warning("Maya disconnected!")
#         self.maya_connected.clear()
#         self.both_connected.clear()
        
#         if self.on_disconnected_callback:
#             self.on_disconnected_callback("Maya")
    
#     def _on_miles_disconnected(self):
#         """Callback when Miles disconnects"""
#         logger.warning("Miles disconnected!")
#         self.miles_connected.clear()
#         self.both_connected.clear()
        
#         if self.on_disconnected_callback:
#             self.on_disconnected_callback("Miles")
    
#     def _process_maya_audio(self):
#         """Process incoming audio from Maya"""
#         logger.debug("Maya audio processing started")
        
#         while self.running and self.maya_ws and self.maya_ws.is_connected():
#             try:
#                 # Get audio chunk from Maya
#                 audio_chunk = self.maya_ws.get_next_audio_chunk(timeout=0.01)
#                 if audio_chunk:
#                     # Add to Maya's audio queue
#                     try:
#                         self.maya_audio_queue.put_nowait(audio_chunk)
#                     except queue.Full:
#                         # If queue is full, remove oldest and add new
#                         try:
#                             self.maya_audio_queue.get_nowait()
#                             self.maya_audio_queue.put_nowait(audio_chunk)
#                         except queue.Empty:
#                             pass
#             except Exception as e:
#                 if self.running:
#                     logger.error(f"Error processing Maya audio: {e}", exc_info=True)
#                     time.sleep(0.1)
    
#     def _process_miles_audio(self):
#         """Process incoming audio from Miles"""
#         logger.debug("Miles audio processing started")
        
#         while self.running and self.miles_ws and self.miles_ws.is_connected():
#             try:
#                 # Get audio chunk from Miles
#                 audio_chunk = self.miles_ws.get_next_audio_chunk(timeout=0.01)
#                 if audio_chunk:
#                     # Add to Miles's audio queue
#                     try:
#                         self.miles_audio_queue.put_nowait(audio_chunk)
#                     except queue.Full:
#                         # If queue is full, remove oldest and add new
#                         try:
#                             self.miles_audio_queue.get_nowait()
#                             self.miles_audio_queue.put_nowait(audio_chunk)
#                         except queue.Empty:
#                             pass
#             except Exception as e:
#                 if self.running:
#                     logger.error(f"Error processing Miles audio: {e}", exc_info=True)
#                     time.sleep(0.1)
    
#     def send_audio_to_maya(self, audio_data):
#         """
#         Send audio data to Maya
        
#         Args:
#             audio_data (bytes): Raw audio data
            
#         Returns:
#             bool: True if sent successfully
#         """
#         if self.maya_ws and self.maya_ws.is_connected():
#             return self.maya_ws.send_audio_data(audio_data)
#         return False
    
#     def send_audio_to_miles(self, audio_data):
#         """
#         Send audio data to Miles
        
#         Args:
#             audio_data (bytes): Raw audio data
            
#         Returns:
#             bool: True if sent successfully
#         """
#         if self.miles_ws and self.miles_ws.is_connected():
#             return self.miles_ws.send_audio_data(audio_data)
#         return False
    
#     def get_maya_audio(self, timeout=None):
#         """
#         Get next audio chunk from Maya
        
#         Args:
#             timeout (float, optional): Timeout in seconds
            
#         Returns:
#             bytes: Audio data or None if timeout
#         """
#         try:
#             return self.maya_audio_queue.get(timeout=timeout)
#         except queue.Empty:
#             return None
    
#     def get_miles_audio(self, timeout=None):
#         """
#         Get next audio chunk from Miles
        
#         Args:
#             timeout (float, optional): Timeout in seconds
            
#         Returns:
#             bytes: Audio data or None if timeout
#         """
#         try:
#             return self.miles_audio_queue.get(timeout=timeout)
#         except queue.Empty:
#             return None
    
#     def is_both_connected(self):
#         """
#         Check if both characters are connected
        
#         Returns:
#             bool: True if both Maya and Miles are connected
#         """
#         return self.both_connected.is_set()
    
#     def is_maya_connected(self):
#         """Check if Maya is connected"""
#         return self.maya_connected.is_set()
    
#     def is_miles_connected(self):
#         """Check if Miles is connected"""
#         return self.miles_connected.is_set()
    
#     def set_both_connected_callback(self, callback):
#         """
#         Set callback for when both characters are connected
        
#         Args:
#             callback (callable): Function with no arguments
#         """
#         self.on_both_connected_callback = callback
    
#     def set_disconnected_callback(self, callback):
#         """
#         Set callback for when a character disconnects
        
#         Args:
#             callback (callable): Function with character name argument
#         """
#         self.on_disconnected_callback = callback
    
#     def start(self):
#         """
#         Start the dual connection system
        
#         Returns:
#             bool: True if startup successful
#         """
#         # Authenticate
#         if not self.authenticate():
#             return False
        
#         # Set running flag
#         self.running = True
        
#         # Connect both characters
#         if not self.connect_both_characters():
#             self.running = False
#             return False
        
#         logger.info("Dual WebSocket system started successfully!")
#         return True
    
#     def stop(self):
#         """Stop the dual connection system"""
#         if not self.running:
#             return
        
#         self.running = False
#         logger.info("Stopping dual WebSocket system...")
        
#         # Disconnect WebSockets
#         if self.maya_ws and self.maya_ws.is_connected():
#             self.maya_ws.disconnect()
        
#         if self.miles_ws and self.miles_ws.is_connected():
#             self.miles_ws.disconnect()
        
#         # Clear connection events
#         self.maya_connected.clear()
#         self.miles_connected.clear()
#         self.both_connected.clear()
        
#         logger.info("Dual WebSocket system stopped")
    
#     def run(self):
#         """Run the dual connection system"""
#         try:
#             if self.start():
#                 # Keep main thread alive
#                 while self.running and self.is_both_connected():
#                     time.sleep(0.1)
#         except KeyboardInterrupt:
#             logger.debug("Interrupted by user")
#         finally:
#             self.stop()


# def main():
#     """Test the dual WebSocket connection system"""
#     # Configure logging
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#         datefmt='%Y-%m-%d %H:%M:%S'
#     )
    
#     # Set websocket-client logger to WARNING level
#     logging.getLogger('websocket').setLevel(logging.WARNING)
    
#     # Create dual connection manager
#     dual_manager = DualWebSocketManager(token_file="token.json")
    
#     # Set up callbacks
#     def on_both_connected():
#         print("\n🎉 Both Maya and Miles are connected and ready!")
#         print("You can now start the conversation system...")
    
#     def on_disconnected(character):
#         print(f"\n⚠️  {character} disconnected!")
    
#     dual_manager.set_both_connected_callback(on_both_connected)
#     dual_manager.set_disconnected_callback(on_disconnected)
    
#     # Run the system
#     print("Starting dual WebSocket connection test...")
#     print("Press Ctrl+C to exit")
#     dual_manager.run()


# if __name__ == "__main__":
#     main()