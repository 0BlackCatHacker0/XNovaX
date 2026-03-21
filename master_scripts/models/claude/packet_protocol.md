# Packet Protocol v1.0
## The ONLY reliable method for large file transfer to NovaX

### Problem
Browser JS execution context truncates strings > 3KB.
File write API works but embedding content in JS fails for files > 5KB.

### Solution: Base64 Packet Protocol
1. Base64-encode the file on Claude container
2. Split into 2500-char chunks (safe for PowerShell string embedding)
3. Chunk 1: `Set-Content -Path C:\NovaX\_temp.b64 -Value 'chunk' -NoNewline`
4. Chunks 2-N: `Add-Content -Path C:\NovaX\_temp.b64 -Value 'chunk' -NoNewline`
5. Decode: PowerShell `[System.Convert]::FromBase64String()` → `WriteAllBytes()`
6. Verify: Check file size matches expected
7. Clean up: Delete .b64 temp file

### Stats
- 2500 chars/packet = ~1875 bytes decoded per packet
- 10KB file = ~6 packets
- 20KB file = ~11 packets
- Each packet takes ~1 second round-trip

### When to use
- Files > 5KB that need to reach Windows disk
- Always verify size after decode
- Use Nova Relay (:9877) /file/write for files < 100KB instead (faster)
