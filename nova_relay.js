/**
 * Nova Relay — Hybrid Transfer & Execution Server
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 * One server. One window. Handles:
 *   - Large file transfers (streaming, no size limit)
 *   - Base64 chunk reassembly
 *   - PowerShell command execution
 *   - File operations (read/write/list/delete)
 *   - System status checks
 * 
 * Port: 9876 (configurable via --port)
 * Launch: node nova_relay.js
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec, spawn } = require('child_process');
const os = require('os');

const PORT = parseInt(process.argv.find((a,i,arr) => arr[i-1] === '--port') || '9876');
const MAX_BODY = 100 * 1024 * 1024; // 100MB max per request
const CHUNK_STORE = {};  // in-memory chunk assembly

// ━━━ CORS + Body Parser ━━━
function parseBody(req) {
  return new Promise((resolve, reject) => {
    let chunks = [];
    let size = 0;
    req.on('data', chunk => {
      size += chunk.length;
      if (size > MAX_BODY) { reject(new Error('Body too large')); return; }
      chunks.push(chunk);
    });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

function json(res, data, status = 200) {
  cors(res);
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

function err(res, msg, status = 500) {
  json(res, { error: msg }, status);
}

// ━━━ ROUTE HANDLERS ━━━

// POST /file/write — write file directly (JSON body: {path, content} or {path, b64})
async function handleFileWrite(req, res) {
  try {
    const body = JSON.parse((await parseBody(req)).toString());
    const filePath = body.path;
    if (!filePath) return err(res, 'Missing path', 400);
    
    // Ensure directory exists
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    
    if (body.b64) {
      // Base64 decode and write binary
      const buf = Buffer.from(body.b64, 'base64');
      fs.writeFileSync(filePath, buf);
      json(res, { ok: true, path: filePath, size: buf.length, encoding: 'base64' });
    } else if (body.content !== undefined) {
      // Write raw string content
      fs.writeFileSync(filePath, body.content, 'utf8');
      const stat = fs.statSync(filePath);
      json(res, { ok: true, path: filePath, size: stat.size, encoding: 'utf8' });
    } else if (body.binary) {
      // Binary array
      const buf = Buffer.from(body.binary);
      fs.writeFileSync(filePath, buf);
      json(res, { ok: true, path: filePath, size: buf.length, encoding: 'binary' });
    } else {
      err(res, 'Provide content, b64, or binary', 400);
    }
  } catch (e) {
    err(res, e.message);
  }
}

// POST /file/stream — streaming upload (query: ?path=C:\...) body = raw file data
async function handleFileStream(req, res) {
  try {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const filePath = url.searchParams.get('path');
    if (!filePath) return err(res, 'Missing ?path= parameter', 400);
    
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    const ws = fs.createWriteStream(filePath);
    let size = 0;
    
    req.on('data', chunk => { ws.write(chunk); size += chunk.length; });
    req.on('end', () => {
      ws.end();
      json(res, { ok: true, path: filePath, size: size });
    });
    req.on('error', e => { ws.destroy(); err(res, e.message); });
  } catch (e) {
    err(res, e.message);
  }
}

// POST /file/chunk — chunked reassembly
// {id: "transfer_id", index: 0, total: 5, data: "base64chunk", path: "final/path"}
async function handleChunk(req, res) {
  try {
    const body = JSON.parse((await parseBody(req)).toString());
    const { id, index, total, data, path: filePath } = body;
    if (!id || index === undefined || !total || !data) 
      return err(res, 'Missing id, index, total, or data', 400);
    
    if (!CHUNK_STORE[id]) CHUNK_STORE[id] = { chunks: new Array(total).fill(null), path: filePath, total };
    CHUNK_STORE[id].chunks[index] = data;
    
    const received = CHUNK_STORE[id].chunks.filter(c => c !== null).length;
    
    if (received === total) {
      // All chunks received — reassemble
      const fullB64 = CHUNK_STORE[id].chunks.join('');
      const buf = Buffer.from(fullB64, 'base64');
      fs.mkdirSync(path.dirname(filePath), { recursive: true });
      fs.writeFileSync(filePath, buf);
      delete CHUNK_STORE[id];
      json(res, { ok: true, complete: true, path: filePath, size: buf.length, chunks: total });
    } else {
      json(res, { ok: true, complete: false, received, total, remaining: total - received });
    }
  } catch (e) {
    err(res, e.message);
  }
}

// GET /file/read?path=... — read file
function handleFileRead(req, res) {
  try {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const filePath = url.searchParams.get('path');
    const asB64 = url.searchParams.get('b64') === '1';
    
    if (!filePath || !fs.existsSync(filePath)) return err(res, 'File not found', 404);
    
    const stat = fs.statSync(filePath);
    if (asB64) {
      const content = fs.readFileSync(filePath).toString('base64');
      json(res, { path: filePath, size: stat.size, b64: content });
    } else {
      const content = fs.readFileSync(filePath, 'utf8');
      json(res, { path: filePath, size: stat.size, content: content.substring(0, 500000) });
    }
  } catch (e) {
    err(res, e.message);
  }
}

// GET /file/list?dir=... — list directory
function handleFileList(req, res) {
  try {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const dir = url.searchParams.get('dir') || 'C:\\NovaX';
    
    if (!fs.existsSync(dir)) return err(res, 'Directory not found', 404);
    
    const entries = fs.readdirSync(dir, { withFileTypes: true }).map(e => ({
      name: e.name,
      type: e.isDirectory() ? 'dir' : 'file',
      size: e.isFile() ? fs.statSync(path.join(dir, e.name)).size : undefined
    }));
    json(res, { dir, entries });
  } catch (e) {
    err(res, e.message);
  }
}

// POST /exec — execute command
async function handleExec(req, res) {
  try {
    const body = JSON.parse((await parseBody(req)).toString());
    const cmd = body.command || body.cmd;
    const shell = body.shell || 'powershell';
    const timeout = body.timeout || 30000;
    
    if (!cmd) return err(res, 'Missing command', 400);
    
    exec(cmd, { shell, timeout, encoding: 'utf8', env: { ...process.env, PYTHONUTF8: '1' } }, 
      (error, stdout, stderr) => {
        json(res, { 
          ok: !error, 
          stdout: stdout.trim(), 
          stderr: stderr.trim(), 
          code: error ? error.code : 0 
        });
      }
    );
  } catch (e) {
    err(res, e.message);
  }
}

// POST /exec/ps — shorthand PowerShell
async function handlePS(req, res) {
  try {
    const body = JSON.parse((await parseBody(req)).toString());
    const script = body.script || body.command;
    if (!script) return err(res, 'Missing script', 400);
    
    exec(`powershell -NoProfile -Command "${script.replace(/"/g, '\\"')}"`, 
      { timeout: 30000, encoding: 'utf8' },
      (error, stdout, stderr) => {
        json(res, { ok: !error, output: stdout.trim(), error: stderr.trim() });
      }
    );
  } catch (e) {
    err(res, e.message);
  }
}

// GET /status — system info
function handleStatus(req, res) {
  json(res, {
    relay: 'Nova Relay v1.0',
    port: PORT,
    uptime: process.uptime(),
    platform: os.platform(),
    hostname: os.hostname(),
    memory: {
      total: Math.round(os.totalmem() / 1024 / 1024) + 'MB',
      free: Math.round(os.freemem() / 1024 / 1024) + 'MB'
    },
    cpu: os.cpus()[0].model,
    pendingChunks: Object.keys(CHUNK_STORE).length
  });
}

// POST /batch — execute multiple operations in one request
async function handleBatch(req, res) {
  try {
    const body = JSON.parse((await parseBody(req)).toString());
    const ops = body.operations || [];
    const results = [];
    
    for (const op of ops) {
      try {
        if (op.type === 'write') {
          fs.mkdirSync(path.dirname(op.path), { recursive: true });
          if (op.b64) {
            const buf = Buffer.from(op.b64, 'base64');
            fs.writeFileSync(op.path, buf);
            results.push({ ok: true, path: op.path, size: buf.length });
          } else {
            fs.writeFileSync(op.path, op.content, 'utf8');
            results.push({ ok: true, path: op.path, size: Buffer.byteLength(op.content) });
          }
        } else if (op.type === 'exec') {
          const out = require('child_process').execSync(op.command, { 
            timeout: 10000, encoding: 'utf8', shell: 'powershell'
          });
          results.push({ ok: true, output: out.trim() });
        } else if (op.type === 'read') {
          const content = fs.readFileSync(op.path, 'utf8');
          results.push({ ok: true, content: content.substring(0, 100000) });
        } else if (op.type === 'delete') {
          fs.unlinkSync(op.path);
          results.push({ ok: true, deleted: op.path });
        }
      } catch (e) {
        results.push({ ok: false, error: e.message });
      }
    }
    json(res, { ok: true, results });
  } catch (e) {
    err(res, e.message);
  }
}

// ━━━ ROUTER ━━━
const server = http.createServer(async (req, res) => {
  cors(res);
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }
  
  const url = req.url.split('?')[0];
  
  try {
    switch (url) {
      case '/status':           return handleStatus(req, res);
      case '/health':           return handleStatus(req, res);
      case '/file/write':       return await handleFileWrite(req, res);
      case '/file/stream':      return await handleFileStream(req, res);
      case '/file/chunk':       return await handleChunk(req, res);
      case '/file/read':        return handleFileRead(req, res);
      case '/file/list':        return handleFileList(req, res);
      case '/exec':             return await handleExec(req, res);
      case '/exec/ps':          return await handlePS(req, res);
      case '/batch':            return await handleBatch(req, res);
      default:                  return err(res, `Unknown route: ${url}`, 404);
    }
  } catch (e) {
    err(res, e.message);
  }
});

server.listen(PORT, () => {
  console.log(`\n  ╔═══════════════════════════════════════╗`);
  console.log(`  ║   Nova Relay v1.0 — Hybrid Transfer   ║`);
  console.log(`  ║   Port: ${PORT}                          ║`);
  console.log(`  ║   File Write  │ /file/write            ║`);
  console.log(`  ║   Stream      │ /file/stream?path=     ║`);
  console.log(`  ║   Chunk       │ /file/chunk            ║`);
  console.log(`  ║   Read        │ /file/read?path=       ║`);
  console.log(`  ║   List        │ /file/list?dir=        ║`);
  console.log(`  ║   Exec        │ /exec                  ║`);
  console.log(`  ║   PowerShell  │ /exec/ps               ║`);
  console.log(`  ║   Batch       │ /batch                 ║`);
  console.log(`  ║   Status      │ /status                ║`);
  console.log(`  ╚═══════════════════════════════════════╝\n`);
});

process.on('uncaughtException', e => console.error('[Relay Error]', e.message));
