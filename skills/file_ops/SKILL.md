---
name: file_ops
description: "File system operations - read, write, copy, move, delete"
tools:
  - name: read_file
    description: Read contents of a file
    parameters:
      - name: path
        type: string
        required: true
  - name: write_file
    description: Write content to a file
    parameters:
      - name: path
        type: string
        required: true
      - name: content
        type: string
        required: true
  - name: list_dir
    description: List directory contents
    parameters:
      - name: path
        type: string
        required: true
metadata:
  novax:
    risk: MEDIUM
    driver: file
    confidence: 0.7
---

# file_ops

File system operations with VCC (Verified Capability Contract) trust pipeline.
All writes go through: DETECTED > READ > SCANNED > WRITE_REQUESTED > MODIFIED > VERIFIED > TRUSTED.

## Risk: MEDIUM (write operations require approval)
