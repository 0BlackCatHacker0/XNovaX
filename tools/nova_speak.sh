#!/bin/bash
# Nova TTS — pipe text to Nova's voice
# Usage: echo "text" | bash nova_speak.sh
# Or:    bash nova_speak.sh "text to speak"

TEXT="${1:-$(cat)}"
if [ -z "$TEXT" ]; then exit 0; fi

# Clean markdown/code blocks for speech
CLEAN=$(echo "$TEXT" | sed 's/```[^`]*```//g' | sed 's/\*\*//g' | sed 's/\[.*\]//g' | sed 's/#\+ //g' | head -c 800)
if [ -z "$CLEAN" ]; then exit 0; fi

curl -s -X POST http://127.0.0.1:9999/api/voice/speak \
  -H "Content-Type: application/json" \
  -d "{\"text\": $(echo "$CLEAN" | python -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")}" \
  > /dev/null 2>&1
