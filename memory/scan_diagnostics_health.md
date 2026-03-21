# DIAGNOSTICS: Full System Health Report
## Date: 2026-03-05

### SYSTEM STATUS: 29/34 healthy (85.3%), 0 zombies

### DOWN SERVICES (5)
| Service | Port | Cause |
|---------|------|-------|
| cloud-router | 9878 | ai_env dependency / API config |
| vpn-core | 9880 | Tor not installed (SOCKS5 on 9050) |
| nexus | 9882 | Cascade from cloud-router/vpn-core |
| nova-cli | 9887 | PORT CONFLICT with nova-appcontrol |
| nova-tfetch | 9897 | Dual-port bind fail (9897+9898) |

### PORT CONFLICTS
1. **9887**: nova-cli AND nova-appcontrol both claim it
2. **9886**: nova-tbuffer listed TWICE in BOOT_ORDER (lines 1904+1916)
3. **9999**: nova-bridge AND orchestrator both in launch.json

### NOT BOOTED (Phase 2 — in BOOT_ORDER but never started)
- nova-tbus (9945), nova-tresilience (9948), nova-tintelligence (9924)
- nova-twatch (9950), nova-tmesh (9951)

### SLOWEST SERVICES
- meilisearch: 198ms, ternary-server: 150ms, exec-server: 119ms

### FASTEST SERVICES
- nova-tbuild: 2.0ms, nova-vault: 2.1ms, nova-tsysmon: 2.1ms

### PRIORITY FIXES
1. Move nova-appcontrol to port 9904 (fix 9887 conflict)
2. Restart cloud-router (unblocks nexus cascade)
3. Remove duplicate nova-tbuffer BOOT_ORDER entry
4. Boot Phase 2 services (tbus, tresilience, tintelligence, twatch, tmesh)
