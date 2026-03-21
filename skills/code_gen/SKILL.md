---
name: code_gen
description: "Code generation, analysis, refactoring, debugging"
tools:
  - name: generate
    description: Generate code from a description
    parameters:
      - name: description
        type: string
        required: true
      - name: language
        type: string
        required: false
  - name: debug
    description: Analyze and fix code
    parameters:
      - name: code
        type: string
        required: true
      - name: error
        type: string
        required: false
metadata:
  novax:
    risk: MEDIUM
    driver: code
    confidence: 0.6
---

# code_gen

Code generation and debugging.
Prefers Ollama for code tasks, Claude for planning.
