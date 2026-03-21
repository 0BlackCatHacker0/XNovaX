---
name: ai_route
description: "AI model routing - select and query models via OpenClaw/Ollama"
tools:
  - name: think
    description: Send a prompt to the best AI model for the task
    parameters:
      - name: prompt
        type: string
        description: The prompt or question
        required: true
      - name: role
        type: string
        description: "Role hint: planner, coder, terminal, repair, chat"
        required: false
  - name: classify
    description: Classify intent from user text
    parameters:
      - name: text
        type: string
        description: User input to classify
        required: true
metadata:
  novax:
    risk: LOW
    driver: ai
    confidence: 0.9
---

# ai_route

Routes AI requests to the best available model based on task role.
Uses adaptive scoring: score = (success_rate * 0.7) + (speed * 0.3).
Learns which model works best per task type over time.

## Models Available
- Claude Sonnet 4.5 (via OpenClaw/Anthropic)
- Ollama/Mixtral (local)
- Fallback chain configured in openclaw.json
