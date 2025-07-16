# To make it short

# Genrating the tokens
python conversation_orchestrator.py --batch-size 50 --batch-number 0 --tokens-only

# Generating the conversations with proper killing 
python conversation_orchestrator.py --batch-size 50 --batch-number 0 --conversations-only && echo "Waiting 5 minutes for 50 conversations..." && sleep 320 && echo "Stopping conversations..." && pkill -SIGINT -f "batch0" && echo "Checking for WAV files..." && sleep 3 && ls -la conversations/*batch0* | wc -l









# AI-to-AI Conversation Orchestrator

This orchestrator script manages large-scale AI-to-AI conversation generation with proper token management and parameter variations.

## Features

- **Token Pre-generation**: Creates authentication tokens with proper naming scheme
- **Batch Management**: Launches conversations in controlled batches
- **Parameter Variations**: Implements gaussian distributions for timing parameters
- **Conversation Naming**: Systematic naming based on parameters
- **Monitoring**: Basic process monitoring and logging

## Quick Start

### 1. Generate Tokens Only (Recommended First Step)

```bash
# Generate 50 token pairs for batch 0
python conversation_orchestrator.py --batch-size 50 --batch-number 0 --tokens-only
```

This creates tokens with names like:
- `tokens/token_batch0_0_maya.json`
- `tokens/token_batch0_0_miles.json`
- `tokens/token_batch0_1_maya.json`
- `tokens/token_batch0_1_miles.json`
- ... and so on

### 2. Run Conversations Only (Using Pre-generated Tokens)

```bash
# Run 50 conversations using existing tokens
python conversation_orchestrator.py --batch-size 50 --batch-number 0 --conversations-only
```

### 3. Full Pipeline (Tokens + Conversations)

```bash
# Generate tokens and run conversations in one go
python conversation_orchestrator.py --batch-size 50 --batch-number 0
```

## Parameter Variations

The orchestrator automatically varies conversation parameters:

- **Prompt Usage**: 25% no prompt, 75% with prompt
- **Processing Time**: Gaussian distribution around 15s (range: 10-20s)
- **Stabilization Time**: Gaussian distribution around 10s (range: 7-15s)
- **Prompt Target**: 70% both AIs, 15% Maya only, 15% Miles only

## Conversation Naming

Conversations are named systematically:
```
maya_miles_{prompted|not}_{prompt_id}_{processing_time}_{stabilization_time}_{prompt_target}_batch{batch_number}_{conv_id}.wav
```

Examples:
- `maya_miles_prompted_42_15_10_both_batch0_0.wav`
- `maya_miles_not_18_12_maya_batch0_1.wav`
- `maya_miles_prompted_7_14_9_miles_batch0_2.wav`

## Directory Structure

```
AI_to_AI/
├── conversation_orchestrator.py
├── two_phase_conversation.py
├── tokens/                     # Generated tokens
│   ├── token_batch0_0_maya.json
│   ├── token_batch0_0_miles.json
│   └── ...
├── conversations/              # Generated conversations
│   ├── maya_miles_prompted_42_15_10_both_batch0_0.wav
│   └── ...
└── orchestrator.log           # Orchestrator logs
```

## Command Line Options

```bash
python conversation_orchestrator.py [OPTIONS]

Options:
  --batch-size INT        Number of conversations per batch (default: 50)
  --batch-number INT      Batch number for token naming (default: 0)
  --tokens-only          Only generate tokens, don't run conversations
  --conversations-only   Only run conversations, skip token generation
  --log-level LEVEL      Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
```

## Scaling Strategy

For large-scale generation (100+ hours of conversations):

1. **Pre-generate tokens in batches**:
   ```bash
   # Batch 0: 50 conversations
   python conversation_orchestrator.py --batch-size 50 --batch-number 0 --tokens-only
   
   # Batch 1: 50 conversations
   python conversation_orchestrator.py --batch-size 50 --batch-number 1 --tokens-only
   
   # Continue for more batches...
   ```

2. **Run conversations in parallel batches**:
   ```bash
   # Terminal 1
   python conversation_orchestrator.py --batch-size 50 --batch-number 0 --conversations-only
   
   # Terminal 2 (after batch 0 is running)
   python conversation_orchestrator.py --batch-size 50 --batch-number 1 --conversations-only
   ```

## Monitoring

- **Real-time logs**: Check `orchestrator.log` for detailed progress
- **Process monitoring**: The script monitors conversation processes automatically
- **Statistics**: Final statistics are printed at completion

## Safety Features

- **Progressive delays**: Longer delays between token generation as batch size increases
- **Rate limit handling**: Automatic backoff on authentication rate limits
- **Token validation**: Validates token pairs exist before launching conversations
- **Error recovery**: Continues processing even if individual conversations fail

## Troubleshooting

### Token Generation Issues
- Check internet connection
- Verify VPN if using one
- Check `orchestrator.log` for rate limiting messages

### Conversation Launch Issues
- Ensure tokens exist in `tokens/` directory
- Check that `two_phase_conversation.py` is in the same directory
- Verify prompt CSV file exists at `prompts/prompts.csv`

### Resource Issues
- Monitor CPU/memory usage during large batches
- Consider reducing batch size if system becomes unstable
- Use `--log-level DEBUG` for detailed troubleshooting