#!/usr/bin/env python3
"""
Prompt Manager Module

Handles CSV operations and prompt selection for the AI conversation system.
Provides functionality to load, select, and manage conversation prompts.
"""

import csv
import os
import random
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger('sesame.prompt_manager')

class PromptManager:
    """
    Manages conversation prompts from CSV database.
    
    Provides methods to:
    - Load prompts from CSV
    - Select prompts randomly or by ID
    - Validate prompt files
    - Get prompt metadata
    """
    
    def __init__(self, csv_path: str = "prompts/prompts.csv"):
        """
        Initialize the prompt manager.
        
        Args:
            csv_path: Path to the prompts CSV file
        """
        self.csv_path = csv_path
        self.prompts: List[Dict] = []
        self.loaded = False
        
    def load_prompts(self) -> bool:
        """
        Load prompts from CSV file.
        
        Returns:
            True if prompts loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(self.csv_path):
                logger.error(f"Prompts CSV file not found: {self.csv_path}")
                return False
            
            self.prompts = []
            with open(self.csv_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Validate CSV headers
                expected_headers = {'prompt_id', 'text', 'audio_path', 'topic', 'voice'}
                if not expected_headers.issubset(set(reader.fieldnames)):
                    missing = expected_headers - set(reader.fieldnames)
                    logger.error(f"Missing CSV headers: {missing}")
                    return False
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                    # Validate required fields
                    if not all(row.get(field, '').strip() for field in expected_headers):
                        logger.warning(f"Row {row_num}: Missing required fields, skipping")
                        continue
                    
                    # Convert prompt_id to int
                    try:
                        row['prompt_id'] = int(row['prompt_id'])
                    except ValueError:
                        logger.warning(f"Row {row_num}: Invalid prompt_id '{row['prompt_id']}', skipping")
                        continue
                    
                    self.prompts.append(row)
            
            self.loaded = True
            logger.info(f"Loaded {len(self.prompts)} prompts from {self.csv_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load prompts: {e}")
            return False
    
    def get_prompt_by_id(self, prompt_id: int) -> Optional[Dict]:
        """
        Get a specific prompt by ID.
        
        Args:
            prompt_id: The prompt ID to retrieve
            
        Returns:
            Prompt dictionary if found, None otherwise
        """
        if not self.loaded and not self.load_prompts():
            return None
        
        for prompt in self.prompts:
            if prompt['prompt_id'] == prompt_id:
                return prompt.copy()
        
        logger.warning(f"Prompt ID {prompt_id} not found")
        return None
    
    def get_random_prompt(self, topic: Optional[str] = None) -> Optional[Dict]:
        """
        Get a random prompt, optionally filtered by topic.
        
        Args:
            topic: Optional topic filter (e.g., 'science', 'technology')
            
        Returns:
            Random prompt dictionary if available, None otherwise
        """
        if not self.loaded and not self.load_prompts():
            return None
        
        if not self.prompts:
            logger.warning("No prompts available")
            return None
        
        # Filter by topic if specified
        available_prompts = self.prompts
        if topic:
            available_prompts = [p for p in self.prompts if p['topic'].lower() == topic.lower()]
            if not available_prompts:
                logger.warning(f"No prompts found for topic '{topic}', using all prompts")
                available_prompts = self.prompts
        
        selected = random.choice(available_prompts)
        logger.info(f"Selected random prompt: ID {selected['prompt_id']} ({selected['topic']})")
        return selected.copy()
    
    def get_prompts_by_topic(self, topic: str) -> List[Dict]:
        """
        Get all prompts for a specific topic.
        
        Args:
            topic: The topic to filter by
            
        Returns:
            List of prompt dictionaries for the topic
        """
        if not self.loaded and not self.load_prompts():
            return []
        
        return [p.copy() for p in self.prompts if p['topic'].lower() == topic.lower()]
    
    def list_topics(self) -> List[str]:
        """
        Get list of all available topics.
        
        Returns:
            List of unique topics
        """
        if not self.loaded and not self.load_prompts():
            return []
        
        topics = list(set(p['topic'] for p in self.prompts))
        return sorted(topics)
    
    def list_prompts(self) -> List[Dict]:
        """
        Get list of all prompts with basic info.
        
        Returns:
            List of prompt dictionaries
        """
        if not self.loaded and not self.load_prompts():
            return []
        
        return [p.copy() for p in self.prompts]
    
    def validate_prompt_file(self, prompt: Dict) -> bool:
        """
        Validate that a prompt's audio file exists.
        
        Args:
            prompt: Prompt dictionary
            
        Returns:
            True if audio file exists, False otherwise
        """
        audio_path = prompt.get('audio_path', '')
        if not audio_path:
            return False
        
        # Handle path resolution properly
        if audio_path.startswith('./'):
            # Remove ./ prefix and use as relative path from current directory
            full_path = audio_path[2:]
        elif os.path.isabs(audio_path):
            # Absolute path
            full_path = audio_path
        else:
            # Relative path - join with CSV directory
            csv_dir = os.path.dirname(self.csv_path)
            full_path = os.path.join(csv_dir, audio_path)
        
        exists = os.path.exists(full_path)
        if not exists:
            logger.warning(f"Audio file not found: {full_path}")
        
        return exists
    
    def get_prompt_file_path(self, prompt: Dict) -> Optional[str]:
        """
        Get the full path to a prompt's audio file.
        
        Args:
            prompt: Prompt dictionary
            
        Returns:
            Full path to audio file if it exists, None otherwise
        """
        audio_path = prompt.get('audio_path', '')
        if not audio_path:
            return None
        
        # Handle path resolution properly
        if audio_path.startswith('./'):
            # Remove ./ prefix and use as relative path from current directory
            full_path = audio_path[2:]
        elif os.path.isabs(audio_path):
            # Absolute path
            full_path = audio_path
        else:
            # Relative path - join with CSV directory
            csv_dir = os.path.dirname(self.csv_path)
            full_path = os.path.join(csv_dir, audio_path)
        
        if os.path.exists(full_path):
            return full_path
        
        return None
    
    def get_prompt_info(self, prompt_id: int) -> Optional[str]:
        """
        Get formatted information about a prompt.
        
        Args:
            prompt_id: The prompt ID
            
        Returns:
            Formatted prompt information string
        """
        prompt = self.get_prompt_by_id(prompt_id)
        if not prompt:
            return None
        
        file_status = "✅" if self.validate_prompt_file(prompt) else "❌"
        return (f"Prompt {prompt['prompt_id']}: {prompt['topic']} - "
                f"'{prompt['text'][:50]}...' {file_status}")

def select_prompt(csv_path: str = "prompts/prompts.csv", 
                 prompt_id: Optional[int] = None,
                 topic: Optional[str] = None,
                 random_selection: bool = False) -> Optional[str]:
    """
    Convenience function to select a prompt and return its audio file path.
    
    Args:
        csv_path: Path to prompts CSV file
        prompt_id: Specific prompt ID to select
        topic: Topic filter for random selection
        random_selection: Whether to select randomly
        
    Returns:
        Path to selected prompt audio file, or None if not found
    """
    manager = PromptManager(csv_path)
    
    if prompt_id is not None:
        prompt = manager.get_prompt_by_id(prompt_id)
    elif random_selection:
        prompt = manager.get_random_prompt(topic)
    else:
        # Default to random if no specific selection method
        prompt = manager.get_random_prompt(topic)
    
    if not prompt:
        return None
    
    if not manager.validate_prompt_file(prompt):
        logger.error(f"Audio file not found for prompt {prompt['prompt_id']}")
        return None
    
    return manager.get_prompt_file_path(prompt)

if __name__ == "__main__":
    # Demo/test functionality
    import argparse
    
    parser = argparse.ArgumentParser(description="Prompt Manager Demo")
    parser.add_argument("--csv", default="prompts/prompts.csv", help="CSV file path")
    parser.add_argument("--list", action="store_true", help="List all prompts")
    parser.add_argument("--topics", action="store_true", help="List all topics")
    parser.add_argument("--id", type=int, help="Get specific prompt by ID")
    parser.add_argument("--random", action="store_true", help="Get random prompt")
    parser.add_argument("--topic", help="Filter by topic")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    manager = PromptManager(args.csv)
    
    if args.list:
        prompts = manager.list_prompts()
        print(f"Found {len(prompts)} prompts:")
        for prompt in prompts:
            file_status = "✅" if manager.validate_prompt_file(prompt) else "❌"
            print(f"  {prompt['prompt_id']}: {prompt['topic']} - {prompt['text'][:50]}... {file_status}")
    
    elif args.topics:
        topics = manager.list_topics()
        print(f"Available topics: {', '.join(topics)}")
    
    elif args.id:
        prompt = manager.get_prompt_by_id(args.id)
        if prompt:
            print(f"Prompt {args.id}:")
            print(f"  Topic: {prompt['topic']}")
            print(f"  Text: {prompt['text']}")
            print(f"  Audio: {prompt['audio_path']}")
            print(f"  File exists: {manager.validate_prompt_file(prompt)}")
        else:
            print(f"Prompt {args.id} not found")
    
    elif args.random:
        prompt = manager.get_random_prompt(args.topic)
        if prompt:
            print(f"Random prompt selected:")
            print(f"  ID: {prompt['prompt_id']}")
            print(f"  Topic: {prompt['topic']}")
            print(f"  Text: {prompt['text']}")
            print(f"  Audio: {prompt['audio_path']}")
            print(f"  File exists: {manager.validate_prompt_file(prompt)}")
        else:
            print("No prompts available")
    
    else:
        print("Use --help for available options")