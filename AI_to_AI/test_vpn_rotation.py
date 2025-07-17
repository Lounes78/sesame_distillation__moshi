#!/usr/bin/env python3
"""
Test script for VPN rotation functionality
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from main import get_available_vpn_configs, switch_vpn_for_batch, kill_all_openvpn_processes
import logging


# to force the program to go through the vpn tunnel
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('ALL_PROXY', None)


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_vpn_rotation():
    """Test VPN rotation functionality"""
    logger.info("🧪 Testing VPN rotation system...")
    
    # Get available VPN configs
    vpn_configs = get_available_vpn_configs()
    
    if not vpn_configs:
        logger.error("❌ No VPN configurations found!")
        return False
    
    logger.info(f"✅ Found {len(vpn_configs)} VPN configurations")
    
    # Test switching to first VPN
    logger.info("🔄 Testing VPN switch to first configuration...")
    success = switch_vpn_for_batch(0, vpn_configs)
    
    if success:
        logger.info("✅ VPN rotation test successful!")
        
        # Cleanup
        logger.info("🧹 Cleaning up test VPN connection...")
        kill_all_openvpn_processes()
        logger.info("✅ Cleanup complete")
        return True
    else:
        logger.error("❌ VPN rotation test failed!")
        return False

if __name__ == "__main__":
    success = test_vpn_rotation()
    exit(0 if success else 1)