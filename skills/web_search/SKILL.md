---
name: web_search
description: "Web search - Brave Search API integration"
tools:
  - name: search
    description: Search the web via Brave Search API
    parameters:
      - name: query
        type: string
        required: true
      - name: count
        type: integer
        description: Number of results (default 5)
        required: false
metadata:
  novax:
    risk: LOW
    driver: ai
    confidence: 0.8
---

# web_search

Web search via Brave Search API.
Requires BRAVE_API_KEY in ~/.openclaw/.env
Integrated through OpenClaw's web_search tool.
