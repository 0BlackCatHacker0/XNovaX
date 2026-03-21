---
name: system_manage
description: "System management - processes, services, environment"
tools:
  - name: system_info
    description: Get system status (CPU, RAM, disk, running apps)
    parameters: []
  - name: check_port
    description: Check if a port is in use
    parameters:
      - name: port
        type: integer
        required: true
metadata:
  novax:
    risk: LOW
    driver: system
    confidence: 0.85
---

# system_manage

System monitoring and management.
Uses core/state.py for system summary.

## Key Ports
- 9990: NovaX Brain
- 9999: NovaX Bridge  
- 9998: NovaX WS
- 18789: OpenClaw Gateway
- 11434: Ollama
