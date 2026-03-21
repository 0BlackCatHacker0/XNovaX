---
name: terminal_exec
description: "Terminal command execution - run shell commands safely"
tools:
  - name: exec_cmd
    description: Execute a shell command
    parameters:
      - name: cmd
        type: string
        required: true
      - name: cwd
        type: string
        required: false
metadata:
  novax:
    risk: MEDIUM
    driver: terminal
    confidence: 0.8
---

# terminal_exec

Execute shell commands via NovaX Bridge /api/run endpoint.
Uses `cmd` parameter (NOT `command`).

## Risk: MEDIUM
