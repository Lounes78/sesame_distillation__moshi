Impossible ? 

# To make it short

# Genrating the tokens
python conversation_orchestrator.py --batch-size 50 --batch-number 0 --tokens-only

# Generating the conversations with proper killing 
python conversation_orchestrator.py --batch-size 50 --batch-number 0 --conversations-only && echo "Waiting 5 minutes for 50 conversations..." && sleep 320 && echo "Stopping conversations..." && pkill -SIGINT -f "batch0" && echo "Checking for WAV files..." && sleep 3 && ls -la conversations/*batch0* | wc -l

