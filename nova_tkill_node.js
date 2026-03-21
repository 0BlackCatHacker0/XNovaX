#!/usr/bin/env node
/**
 * NovaX TKill Node v2.0 -- Ternary Process Killswitch (Port 9900)
 *
 * JavaScript/Node.js implementation of the TKill killswitch.
 * Complements the Python TKill (:9899) with cross-runtime kill capabilities.
 * Node can sometimes kill processes that Python can't (and vice versa).
 *
 * 3-5-7-13 Ternary Constants:
 *   3  = ternary kill states (+1=killed, 0=skipped, -1=failed)
 *   5  = max kill retries per service
 *   7  = kill batch size
 *   13 = verification interval (13s health loop)
 *
 * Endpoints:
 *   GET  /health               -- Health check with ternary harmonics
 *   GET  /tkill/status         -- All service PIDs and ternary versions
 *   POST /tkill/flush          -- Kill ALL non-protected services
 *   POST /tkill/flush-one      -- Kill specific service by name or port
 *   POST /tkill/flush-and-boot -- Full killswitch: flush + reboot + verify
 *   POST /tkill/verify         -- Check ternary status of all services
 */

const http = require('http');
const { execSync, spawn } = require('child_process');
const net = require('net');

// ── 3-5-7-13 Ternary Constants ──────────────────────────────────────
const H3 = 3, H5 = 5, H7 = 7, H13 = 13;
const TRUE = 1, MAYBE = 0, FALSE_ = -1;
const BLOCK_SIZE = Math.pow(3, H7);  // 2187
const RE_LAMINAR = Math.pow(H3, H3);     // 27
const RE_TRANSITION = Math.pow(H5, H3);  // 125
const RE_TURBULENT = Math.pow(H7, H3);   // 343

const PORT = 9900;
const t0 = Date.now();

const stats = {
    flushes: 0, kills: 0, boots: 0,
    trits: { [TRUE]: 0, [MAYBE]: 0, [FALSE_]: 0 }
};

// ── Service Registry ────────────────────────────────────────────────
const SERVICES = {
    9875:  { name: 'stt',              script: 'C:\\NovaX\\nova_stt.py' },
    9877:  { name: 'exec-server',      script: 'C:\\NovaX\\launchers\\exec_server.py' },
    9878:  { name: 'cloud-router',     script: 'C:\\NovaX\\nova_cloud_router.py' },
    9880:  { name: 'vpn-core',         script: 'C:\\NovaX\\nova_vpn_core.py' },
    9881:  { name: 'hivemind',         script: 'C:\\NovaX\\nova_hivemind.py' },
    9882:  { name: 'nexus',            script: 'C:\\NovaX\\nova_nexus.py' },
    9884:  { name: 'sentinel',         script: 'C:\\NovaX\\nova_sentinel.py' },
    9889:  { name: 'max-patch',        script: 'C:\\NovaX\\nova_max_patch.py' },
    9890:  { name: 'tshell',           script: 'C:\\NovaX\\nova_tshell.py' },
    9891:  { name: 'nova-tools',       script: 'C:\\NovaX\\nova_tools.py' },
    9892:  { name: 'nova-vault',       script: 'C:\\NovaX\\nova_vault.py' },
    9893:  { name: 'nova-deepstorage', script: 'C:\\NovaX\\nova_deepstorage.py' },
    9894:  { name: 'nova-ttools',      script: 'C:\\NovaX\\nova_ternary_tools.py' },
    9895:  { name: 'nova-tspeak',      script: 'C:\\NovaX\\nova_tspeak.py' },
    9896:  { name: 'nova-cortex',      script: 'C:\\NovaX\\nova_cortex.py' },
    9897:  { name: 'nova-tfetch',      script: 'C:\\NovaX\\nova_tfetch.py' },
    9899:  { name: 'nova-tkill-py',    script: 'C:\\NovaX\\nova_tkill.py' },
    9990:  { name: 'brain',            script: 'C:\\NovaX\\core\\server.py' },
    9998:  { name: 'websocket',        script: 'C:\\NovaX\\ws_server_standalone.py', healthPort: 9997 },
};

// NEVER kill these
const PROTECTED = new Set([9999, 11434, 6379, 7700, PORT]);


// ── Ternary Helpers ─────────────────────────────────────────────────

function btString(trits) {
    return trits.map(t => t === 1 ? '1' : t === 0 ? '0' : 'T').join('');
}

function tritChar(t) {
    return t === 1 ? '1' : t === 0 ? '0' : 'T';
}


// ── Port + PID Utilities ────────────────────────────────────────────

function findPids(port) {
    try {
        const out = execSync('netstat -ano', { encoding: 'utf8', windowsHide: true, timeout: 10000 });
        const pids = new Set();
        for (const line of out.split('\n')) {
            if (line.includes('LISTEN') && line.includes(`:${port} `)) {
                const parts = line.trim().split(/\s+/);
                const pid = parseInt(parts[parts.length - 1]);
                if (pid > 0) pids.add(pid);
            }
        }
        return [...pids];
    } catch {
        return [];
    }
}

function killPid(pid) {
    // Phase 1: taskkill /F /T (tree kill — kills children too)
    try {
        execSync(`taskkill /F /T /PID ${pid}`, { encoding: 'utf8', windowsHide: true, timeout: 10000 });
        return TRUE;
    } catch (e) {
        if (e.stderr && e.stderr.toLowerCase().includes('not found')) return MAYBE;
    }

    // Phase 2: PowerShell Stop-Process (higher privilege)
    try {
        execSync(
            `powershell -NoProfile -NonInteractive -Command "Stop-Process -Id ${pid} -Force -ErrorAction SilentlyContinue"`,
            { encoding: 'utf8', windowsHide: true, timeout: 10000 }
        );
        return TRUE;
    } catch { /* fall through */ }

    // Phase 3: process.kill (Node native — sometimes works when others don't)
    try {
        process.kill(pid, 'SIGKILL');
        return TRUE;
    } catch { /* fall through */ }

    // Phase 4: Verify if actually dead
    try {
        process.kill(pid, 0);  // Signal 0 = check existence
        return FALSE_;  // Still alive
    } catch {
        return MAYBE;  // Process gone
    }
}

function checkPort(port) {
    return new Promise(resolve => {
        const s = new net.Socket();
        s.setTimeout(1000);
        s.connect(port, '127.0.0.1', () => { s.destroy(); resolve(true); });
        s.on('error', () => { s.destroy(); resolve(false); });
        s.on('timeout', () => { s.destroy(); resolve(false); });
    });
}


// ── Health Check ────────────────────────────────────────────────────

function httpGet(port, path = '/health', timeout = 3000) {
    return new Promise(resolve => {
        const req = http.get({ hostname: '127.0.0.1', port, path, timeout }, res => {
            let data = '';
            res.on('data', c => data += c);
            res.on('end', () => {
                try { resolve(JSON.parse(data)); }
                catch { resolve(null); }
            });
        });
        req.on('error', () => resolve(null));
        req.on('timeout', () => { req.destroy(); resolve(null); });
    });
}

function httpPost(url, body = {}, timeout = 60000) {
    return new Promise(resolve => {
        const u = new URL(url);
        const data = JSON.stringify(body);
        const req = http.request({
            hostname: u.hostname, port: u.port, path: u.pathname,
            method: 'POST', timeout,
            headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) }
        }, res => {
            let buf = '';
            res.on('data', c => buf += c);
            res.on('end', () => {
                try { resolve(JSON.parse(buf)); }
                catch { resolve(null); }
            });
        });
        req.on('error', () => resolve(null));
        req.on('timeout', () => { req.destroy(); resolve(null); });
        req.write(data);
        req.end();
    });
}

async function checkTernary(port) {
    const svc = SERVICES[port] || {};
    const healthPort = svc.healthPort || port;
    const data = await httpGet(healthPort);
    if (!data) return { hasTernary: false, version: 'offline', raw: {} };
    const hasTernary = !!(data.ternary || data.harmonics);
    return { hasTernary, version: data.version || '?', raw: data };
}


// ── Flush + Boot ────────────────────────────────────────────────────

function flushService(port, retries = H5) {
    if (PROTECTED.has(port)) {
        const name = (SERVICES[port] || {}).name || `port-${port}`;
        return { port, name, skipped: true, reason: 'protected', trit: MAYBE, char: '0' };
    }

    const svc = SERVICES[port] || { name: `port-${port}` };
    const killed = [], failed = [];

    for (let attempt = 0; attempt < retries; attempt++) {
        const pids = findPids(port);
        if (pids.length === 0) break;
        for (const pid of pids) {
            const trit = killPid(pid);
            if (trit === TRUE) killed.push(pid);
            else if (trit === FALSE_) failed.push(pid);
        }
        // Small sync wait between retries
        execSync('timeout /t 1 /nobreak >nul 2>&1', { windowsHide: true });
    }

    // Check if port is free now
    const pidsLeft = findPids(port);
    const portFree = pidsLeft.length === 0;
    const trit = portFree && killed.length > 0 ? TRUE : portFree ? MAYBE : FALSE_;

    return {
        port, name: svc.name, pidsKilled: killed, pidsFailed: failed,
        portFree, trit, char: tritChar(trit)
    };
}

function flushAll() {
    const results = [];
    for (const port of Object.keys(SERVICES).map(Number).sort((a, b) => a - b)) {
        results.push(flushService(port));
    }
    return results;
}

async function triggerBoot() {
    return await httpPost('http://localhost:9999/api/services/boot', {});
}

async function verifyAll() {
    const results = [];
    for (const [portStr, svc] of Object.entries(SERVICES).sort(([a], [b]) => a - b)) {
        const port = parseInt(portStr);
        const alive = await checkPort(port);
        let hasTernary = false, version = 'offline';
        if (alive) {
            const check = await checkTernary(port);
            hasTernary = check.hasTernary;
            version = check.version;
        }
        const stale = alive && !hasTernary;
        const trit = hasTernary ? TRUE : alive ? MAYBE : FALSE_;
        results.push({ port, name: svc.name, alive, ternary: hasTernary, version, stale, trit, char: tritChar(trit) });
    }
    return results;
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}


// ── HTTP Server ─────────────────────────────────────────────────────

const server = http.createServer(async (req, res) => {
    const [path] = req.url.split('?');
    const cleanPath = path.replace(/\/$/, '');

    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', '*');

    if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

    const json = (data, code = 200) => {
        const body = JSON.stringify(data);
        res.writeHead(code, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) });
        res.end(body);
    };

    const readBody = () => new Promise(resolve => {
        let buf = '';
        req.on('data', c => buf += c);
        req.on('end', () => { try { resolve(JSON.parse(buf)); } catch { resolve({}); } });
    });

    // ── GET routes ──
    if (req.method === 'GET') {
        if (cleanPath === '/health') {
            const uptime = Math.floor((Date.now() - t0) / 1000);
            const selfTrit = uptime > 10 ? TRUE : MAYBE;
            return json({
                ok: true, service: 'nova-tkill-node', port: PORT,
                version: '2.0', ternary: true, runtime: 'node',
                harmonics: { H3, H5, H7, H13 },
                selfTrit, char: tritChar(selfTrit),
                uptime, flushes: stats.flushes, totalKills: stats.kills,
                quality: {
                    strong: stats.trits[TRUE],
                    partial: stats.trits[MAYBE],
                    failed: stats.trits[FALSE_]
                }
            });
        }

        if (cleanPath === '/tkill/status') {
            const results = await verifyAll();
            const trits = results.map(r => r.trit);
            return json({
                ok: true, runtime: 'node',
                services: results,
                total: results.length,
                ternaryCount: results.filter(r => r.ternary).length,
                staleCount: results.filter(r => r.stale).length,
                offlineCount: results.filter(r => !r.alive).length,
                healthBt: btString(trits),
                needsFlush: results.some(r => r.stale)
            });
        }

        return json({ error: 'Unknown endpoint', routes: [
            '/health', '/tkill/status',
            'POST /tkill/flush', 'POST /tkill/flush-one',
            'POST /tkill/flush-and-boot', 'POST /tkill/verify'
        ] });
    }

    // ── POST routes ──
    if (req.method === 'POST') {
        const body = await readBody();

        if (cleanPath === '/tkill/flush') {
            stats.flushes++;
            const results = flushAll();
            const totalKilled = results.reduce((s, r) => s + (r.pidsKilled || []).length, 0);
            stats.kills += totalKilled;
            const trits = results.map(r => r.trit);
            trits.forEach(t => stats.trits[t]++);
            return json({ ok: true, action: 'flush', runtime: 'node', results, totalKilled, flushBt: btString(trits) });
        }

        if (cleanPath === '/tkill/flush-one') {
            let port = body.port;
            const name = body.name || '';
            if (!port && name) {
                for (const [p, s] of Object.entries(SERVICES)) {
                    if (s.name === name) { port = parseInt(p); break; }
                }
            }
            if (!port) return json({ error: 'port or name required' }, 400);
            const result = flushService(parseInt(port));
            stats.kills += (result.pidsKilled || []).length;
            return json({ ok: true, action: 'flush-one', runtime: 'node', result });
        }

        if (cleanPath === '/tkill/flush-and-boot') {
            stats.flushes++;
            console.log('[TKill-Node] === FLUSH AND BOOT ===');

            // Phase 1: Kill everything
            const flushResults = flushAll();
            const totalKilled = flushResults.reduce((s, r) => s + (r.pidsKilled || []).length, 0);
            stats.kills += totalKilled;
            console.log(`[TKill-Node] Killed ${totalKilled} processes`);

            // Phase 2: Wait for ports to free
            await sleep(3000);

            // Phase 3: Trigger orchestrator boot
            stats.boots++;
            const bootResult = await triggerBoot();
            console.log(`[TKill-Node] Boot BT: ${(bootResult || {}).boot_bt || '?'}`);

            // Phase 4: Poll until services come up (max 30s)
            for (let i = 0; i < 10; i++) {
                await sleep(H3 * 1000);
                let upCount = 0;
                for (const port of Object.keys(SERVICES).map(Number)) {
                    if (await checkPort(port)) upCount++;
                }
                if (upCount >= Object.keys(SERVICES).length - 3) break;
            }

            // Phase 5: Verify ternary
            const verify = await verifyAll();
            const stale = verify.filter(v => v.stale).length;
            const ternaryCount = verify.filter(v => v.ternary).length;

            return json({
                ok: true, action: 'flush-and-boot', runtime: 'node',
                phase1Flush: { totalKilled, flushBt: btString(flushResults.map(r => r.trit)) },
                phase3Boot: bootResult,
                phase5Verify: {
                    services: verify, ternaryCount, staleCount: stale,
                    healthBt: btString(verify.map(v => v.trit)),
                    allTernary: stale === 0
                }
            });
        }

        if (cleanPath === '/tkill/verify') {
            const results = await verifyAll();
            const trits = results.map(r => r.trit);
            return json({
                ok: true, action: 'verify', runtime: 'node',
                services: results,
                healthBt: btString(trits),
                staleCount: results.filter(r => r.stale).length,
                ternaryCount: results.filter(r => r.ternary).length
            });
        }

        return json({ error: 'Unknown endpoint' }, 404);
    }

    json({ error: 'Method not allowed' }, 405);
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`[TKill-Node] Nova TKill Node v2.0 -- Ternary Process Killswitch`);
    console.log(`[TKill-Node] Port ${PORT} | Runtime: Node.js | Harmonics: 3-5-7-13`);
    console.log(`[TKill-Node] Monitoring ${Object.keys(SERVICES).length} services`);
    console.log(`[TKill-Node] Protected ports: ${[...PROTECTED].sort().join(', ')}`);
    console.log(`[TKill-Node] Endpoints: /health, /tkill/status, /tkill/flush, /tkill/flush-and-boot`);
    console.log(`[TKill-Node] Ready at http://localhost:${PORT}/health`);
});
