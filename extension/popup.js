/* ───────────────────────────────────────────
   NovaX Control Panel — popup.js
   ─────────────────────────────────────────── */

const BRIDGE = 'http://localhost:9999';

const SERVICES = [
  { id: 'bridge',   name: 'Bridge',       port: 9999 },
  { id: 'brain',    name: 'Brain',        port: 9990 },
  { id: 'ws',       name: 'WebSocket',    port: 9998 },
  { id: 'executor', name: 'Executor',     port: 9991 },
  { id: 'terminal', name: 'UI Terminal',  port: 9997 },
  { id: 'openclaw', name: 'OpenClaw GW',  port: 18789 }
];

const SECTIONS = [
  { name: 'Shell',          file: 'shell.html' },
  { name: 'OS v2',          file: 'os_v2.html' },
  { name: 'Voice',          file: 'voice_terminal.html' },
  { name: 'Scripts',        file: 'server_scripts.html' },
  { name: 'VCC',            file: 'vcc_dashboard.html' },
  { name: 'Extensions',     file: 'extensions.html' },
  { name: 'GhostX',         file: 'ghostx.html' },
  { name: 'Discovery',      file: 'discovery.html' },
  { name: 'Debugger',       file: 'debugger.html' },
  { name: 'DevTools',       file: 'devtools.html' },
  { name: 'Media',          file: 'media_library.html' },
  { name: 'Servers',        file: 'servers.html' },
  { name: 'Env',            file: 'env.html' },
  { name: 'Killswitch',     file: 'killswitch.html' }
];

const PYTHON = 'C:\\NovaX\\ai_env\\Scripts\\python.exe';

/* ── DOM refs ── */
const serviceGrid  = document.getElementById('serviceGrid');
const masterStatus = document.getElementById('masterStatus');
const termOutput   = document.getElementById('termOutput');
const termInput    = document.getElementById('termInput');
const sectionsGrid = document.getElementById('sectionsGrid');

/* ── Build UI ── */
function buildServiceGrid() {
  serviceGrid.innerHTML = SERVICES.map(s => `
    <div class="service" data-port="${s.port}" id="svc-${s.id}">
      <div class="dot checking" id="dot-${s.id}"></div>
      <div class="info">
        <div class="name">${s.name}</div>
        <div class="port">:${s.port}</div>
      </div>
    </div>
  `).join('');
}

function buildSectionsGrid() {
  sectionsGrid.innerHTML = SECTIONS.map(s => `
    <button class="section-btn" data-file="${s.file}">${s.name}</button>
  `).join('');

  sectionsGrid.querySelectorAll('.section-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      chrome.tabs.create({ url: `${BRIDGE}/static/${btn.dataset.file}` });
    });
  });
}

/* ── Port checking ── */
async function checkPort(port) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2000);
    
    // For the bridge, just hit root. For others, try a quick fetch.
    const url = port === 9999 
      ? `${BRIDGE}/static/shell.html`
      : `http://localhost:${port}/`;
    
    const resp = await fetch(url, { 
      method: 'HEAD', 
      mode: 'no-cors',
      signal: controller.signal 
    });
    clearTimeout(timeout);
    return true;
  } catch (e) {
    return false;
  }
}

async function checkAllServices() {
  masterStatus.textContent = 'Checking...';
  masterStatus.className = 'header-status checking';

  const results = {};
  
  // Check bridge first (required for everything)
  const bridgeUp = await checkPort(9999);
  results.bridge = bridgeUp;
  updateDot('bridge', bridgeUp);

  if (bridgeUp) {
    // Use the bridge terminal API to check all ports at once
    try {
      const resp = await runCommand('netstat -ano | findstr "LISTENING" | findstr "9990 9991 9997 9998 9999 18789"', true);
      const lines = resp.split('\n');
      
      SERVICES.forEach(s => {
        if (s.id === 'bridge') return;
        const portStr = ':' + s.port;
        const found = lines.some(l => l.includes(portStr) && l.includes('LISTENING'));
        results[s.id] = found;
        updateDot(s.id, found);
      });
    } catch (e) {
      // Bridge up but API not working — mark degraded
      masterStatus.textContent = 'Degraded';
      masterStatus.className = 'header-status degraded';
    }
  } else {
    // Bridge down — mark all services as down
    SERVICES.forEach(s => {
      if (s.id !== 'bridge') {
        results[s.id] = false;
        updateDot(s.id, false);
      }
    });
    masterStatus.textContent = 'Offline';
    masterStatus.className = 'header-status offline';
  }

  return results;
}

function updateDot(serviceId, isUp) {
  const dot = document.getElementById(`dot-${serviceId}`);
  if (dot) {
    dot.className = isUp ? 'dot green' : 'dot red';
  }
}

/* ── Terminal API ── */
async function runCommand(cmd, silent = false) {
  try {
    const resp = await fetch(`${BRIDGE}/api/terminal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd })
    });
    const data = await resp.json();
    const output = data.output || data.result || JSON.stringify(data);
    if (!silent) appendOutput(output);
    return output;
  } catch (e) {
    const errMsg = 'Bridge API unreachable — is the bridge running?';
    if (!silent) appendOutput(errMsg, 'error');
    throw new Error(errMsg);
  }
}

function appendOutput(text, cls = '') {
  const span = document.createElement('span');
  if (cls) span.className = cls;
  span.textContent = text + '\n';
  termOutput.appendChild(span);
  termOutput.scrollTop = termOutput.scrollHeight;
}

/* ── Command history ── */
let cmdHistory = [];
let historyIdx = -1;

/* ── Terminal input handler ── */
termInput.addEventListener('keydown', async (e) => {
  if (e.key === 'Enter') {
    const cmd = termInput.value.trim();
    if (!cmd) return;
    
    cmdHistory.unshift(cmd);
    historyIdx = -1;
    appendOutput(`❯ ${cmd}`, 'info');
    termInput.value = '';
    
    await runCommand(cmd);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (historyIdx < cmdHistory.length - 1) {
      historyIdx++;
      termInput.value = cmdHistory[historyIdx];
    }
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (historyIdx > 0) {
      historyIdx--;
      termInput.value = cmdHistory[historyIdx];
    } else {
      historyIdx = -1;
      termInput.value = '';
    }
  }
});

/* ── Button handlers ── */
document.getElementById('btnRefresh').addEventListener('click', () => {
  checkAllServices();
});

document.getElementById('btnOpenAll').addEventListener('click', () => {
  SECTIONS.forEach((s, i) => {
    setTimeout(() => {
      chrome.tabs.create({ url: `${BRIDGE}/static/${s.file}`, active: i === 0 });
    }, i * 150); // stagger to avoid overwhelming browser
  });
  appendOutput(`Opening all ${SECTIONS.length} sections...`, 'info');
});

document.getElementById('btnKillStale').addEventListener('click', async () => {
  appendOutput('Killing stale processes on NovaX ports...', 'info');
  try {
    // Get PIDs on our ports, kill everything except the bridge
    const result = await runCommand(
      'powershell -Command "Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in @(9990,9991,9997,9998,18789) } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Output \\"Killed PID $($_.OwningProcess) on port $($_.LocalPort)\\" }"',
      true
    );
    appendOutput(result || 'No stale processes found.');
    setTimeout(checkAllServices, 1500);
  } catch (e) {
    appendOutput('Failed — bridge may be down.', 'error');
  }
});

document.getElementById('btnLaunchNova').addEventListener('click', async () => {
  appendOutput('Launching Nova (main.py with UTF-8)...', 'info');
  try {
    await runCommand(
      `${PYTHON} -c "import subprocess; subprocess.Popen(['C:\\\\NovaX\\\\novalang.exe', 'C:\\\\NovaX\\\\nova_orchestrator.nova'], cwd='C:\\\\NovaX', creationflags=0x00000008)"`,
      true
    );
    appendOutput('Nova launched. Waiting for services...', 'info');
    // Poll for services
    let checks = 0;
    const poll = setInterval(async () => {
      checks++;
      const results = await checkAllServices();
      const upCount = Object.values(results).filter(v => v).length;
      if (upCount >= 5 || checks > 20) {
        clearInterval(poll);
        if (upCount >= 5) {
          appendOutput(`Nova is up! ${upCount}/${SERVICES.length} services running.`, 'info');
        } else {
          appendOutput(`Timeout — only ${upCount}/${SERVICES.length} services up. Check logs.`, 'error');
        }
      }
    }, 3000);
  } catch (e) {
    appendOutput('Launch failed: ' + e.message, 'error');
  }
});

document.getElementById('btnStopAll').addEventListener('click', async () => {
  appendOutput('Stopping all NovaX services (keeping bridge)...', 'info');
  try {
    await runCommand(
      'powershell -Command "Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in @(9990,9991,9997,9998,18789) } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Output \\"Stopped PID $($_.OwningProcess) on :$($_.LocalPort)\\" }"',
      true
    );
    appendOutput('All services stopped (bridge preserved).', 'info');
    setTimeout(checkAllServices, 1500);
  } catch (e) {
    appendOutput('Failed: ' + e.message, 'error');
  }
});

/* ── Init ── */
buildServiceGrid();
buildSectionsGrid();
checkAllServices();

// Auto-refresh every 15 seconds
setInterval(checkAllServices, 15000);
