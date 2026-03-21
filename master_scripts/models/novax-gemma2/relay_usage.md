# Nova Relay v1.0 — Usage Guide
## Port: 9877 | Launch: node C:\NovaX\nova_relay.js --port 9877

### Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | /file/write | Write file (JSON: {path, content} or {path, b64}) |
| POST | /file/stream?path= | Stream raw bytes to file |
| POST | /file/chunk | Chunked reassembly (auto-merge when all arrive) |
| GET | /file/read?path= | Read file content |
| GET | /file/list?dir= | List directory |
| POST | /exec | Execute command (any shell) |
| POST | /exec/ps | PowerShell shorthand |
| POST | /batch | Multiple operations in one request |
| GET | /status | System info |

### Best Practices
- Use /file/write for files < 100KB (single request)
- Use /file/chunk for files > 100KB (auto-reassembly)
- Use /batch to combine multiple operations (saves round-trips)
- Use /exec for commands, never bridge terminal API
- Always set PYTHONUTF8=1 for Python commands
