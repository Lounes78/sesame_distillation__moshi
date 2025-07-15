# Prompt Management System

This document describes the new scalable prompt management system for the AI-to-AI conversation system.

## Overview

The prompt management system allows you to:
- Generate multiple conversation prompts using TTS
- Organize prompts by topic and metadata in a CSV database
- Select prompts randomly or by specific ID
- Maintain backward compatibility with direct file paths

## Components

### 1. CSV Prompt Database (`prompts/prompts.csv`)

The CSV file contains all available prompts with the following structure:

```csv
prompt_id,text,audio_path,topic,voice
1,Let's talk about space exploration and the future of humanity among the stars,prompts/prompt_1.wav,science,tara
2,Let's discuss artificial intelligence and its transformative impact on society,prompts/prompt_2.wav,technology,tara
```

**Fields:**
- `prompt_id`: Unique numeric identifier
- `text`: The text that will be converted to speech
- `audio_path`: Relative path to the generated audio file
- `topic`: Category/topic for filtering (science, technology, philosophy, arts, current_events)
- `voice`: TTS voice to use for generation

### 2. Prompt Generation Script (`generate_prompts.py`)

Generates audio files for all prompts in the CSV using the TTS server.

**Usage:**
```bash
# Generate all prompts
python generate_prompts.py

# Generate specific prompt by ID
python generate_prompts.py --prompt-id 5

# Force regeneration of existing files
python generate_prompts.py --force

# Use custom CSV file
python generate_prompts.py --csv custom_prompts.csv
```

**Requirements:**
- TTS server running at `http://127.0.0.1:8765`
- CSV file with valid prompt entries

### 3. Prompt Manager Module (`prompt_manager.py`)

Python module for programmatic prompt management.

**Key Classes:**
- `PromptManager`: Main class for loading and selecting prompts
- `select_prompt()`: Convenience function for quick prompt selection

**Example Usage:**
```python
from prompt_manager import PromptManager

# Initialize manager
manager = PromptManager("prompts/prompts.csv")

# Get specific prompt
prompt = manager.get_prompt_by_id(5)

# Get random prompt
random_prompt = manager.get_random_prompt()

# Get random prompt by topic
science_prompt = manager.get_random_prompt("science")

# List all topics
topics = manager.list_topics()
```

### 4. Enhanced Two-Phase Conversation (`two_phase_conversation.py`)

The main conversation script now supports multiple prompt selection methods.

## Usage Examples

### Command Line Options

**List available prompts:**
```bash
python two_phase_conversation.py --list-prompts
```

**List available topics:**
```bash
python two_phase_conversation.py --list-topics
```

**Use specific prompt by ID:**
```bash
python two_phase_conversation.py --prompt-id 3
```

**Use random prompt:**
```bash
python two_phase_conversation.py --random-prompt
```

**Use random prompt from specific topic:**
```bash
python two_phase_conversation.py --random-prompt --prompt-topic science
```

**Use custom prompt file (backward compatibility):**
```bash
python two_phase_conversation.py --prompt custom_prompt.wav
```

**Disable prompts:**
```bash
python two_phase_conversation.py --no-prompt
```

### Prompt Selection Priority

The system uses the following priority order:

1. **Direct file path** (`--prompt file.wav`) - Highest priority
2. **Specific ID** (`--prompt-id 5`) - Direct selection from CSV
3. **Random with topic** (`--random-prompt --prompt-topic science`) - Filtered random
4. **Random** (`--random-prompt`) - Any random prompt from CSV
5. **Auto-select** (default) - Random from CSV, fallback to original default
6. **Fallback** - Random noise if all else fails

### Setting Up the System

1. **Start TTS Server:**
   ```bash
   # Make sure your TTS server is running at http://127.0.0.1:8765
   ```

2. **Generate Prompts:**
   ```bash
   cd sesame_distillation__moshi/AI_to_AI
   python generate_prompts.py
   ```

3. **Verify Prompts:**
   ```bash
   python two_phase_conversation.py --list-prompts
   ```

4. **Run Conversation:**
   ```bash
   python two_phase_conversation.py --random-prompt
   ```

## Adding New Prompts

### Method 1: Edit CSV Directly

1. Open `prompts/prompts.csv`
2. Add new row with unique `prompt_id`
3. Run `python generate_prompts.py` to generate audio

### Method 2: Programmatic Addition

```python
import csv

# Add new prompt to CSV
new_prompt = {
    'prompt_id': 11,
    'text': 'Let\'s explore the mysteries of quantum computing',
    'audio_path': 'prompts/prompt_11.wav',
    'topic': 'technology',
    'voice': 'tara'
}

# Append to CSV file
with open('prompts/prompts.csv', 'a', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['prompt_id', 'text', 'audio_path', 'topic', 'voice'])
    writer.writerow(new_prompt)

# Generate audio
os.system('python generate_prompts.py --prompt-id 11')
```

## Topics

Current available topics:
- `science`: Space exploration, quantum physics, climate change
- `technology`: AI, digital innovation, social media
- `philosophy`: Consciousness, ethics, existential questions
- `arts`: Digital art, music evolution, creative expression
- `current_events`: Social issues, renewable energy, contemporary topics

## Troubleshooting

### Common Issues

**TTS Server Not Running:**
```
❌ TTS server is not running or not responding
```
Solution: Start your TTS server at `http://127.0.0.1:8765`

**Audio File Not Found:**
```
❌ Audio file not found for prompt ID 5
```
Solution: Run `python generate_prompts.py --prompt-id 5`

**CSV File Not Found:**
```
❌ Prompts CSV file not found: prompts/prompts.csv
```
Solution: Ensure you're in the correct directory and CSV file exists

**Invalid Prompt ID:**
```
❌ Prompt ID 99 not found in CSV
```
Solution: Use `--list-prompts` to see available IDs

### Validation

**Check prompt files exist:**
```bash
python prompt_manager.py --list --csv prompts/prompts.csv
```

**Test specific prompt:**
```bash
python prompt_manager.py --id 5 --csv prompts/prompts.csv
```

## Migration from Old System

The new system is fully backward compatible:

**Old way:**
```bash
python two_phase_conversation.py --prompt prompts/Prompt_sesame.wav
```

**New equivalent:**
```bash
python two_phase_conversation.py --prompt prompts/Prompt_sesame.wav  # Still works
# OR
python two_phase_conversation.py --prompt-id 1  # If added to CSV
```

## Performance Notes

- CSV loading is cached within `PromptManager` instances
- Audio files are loaded on-demand during conversation start
- TTS generation is done offline, not during conversations
- Random selection is O(1) after CSV loading

## Future Enhancements

Potential improvements:
- Web interface for prompt management
- Automatic topic classification
- Voice variety per prompt
- Prompt difficulty levels
- Multi-language support
- Prompt effectiveness tracking