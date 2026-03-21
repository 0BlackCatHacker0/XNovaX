/* ───────────────────────────────────────────
   NovaX Background Service Worker
   Updates badge icon with service count
   ─────────────────────────────────────────── */

const BRIDGE = 'http://localhost:9999';
const CHECK_INTERVAL = 30000; // 30 seconds

const PORTS = [9999, 9990, 9991, 9997, 9998, 18789];

async function checkHealth() {
  let bridgeUp = false;
  let upCount = 0;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    await fetch(`${BRIDGE}/static/shell.html`, { method: 'HEAD', mode: 'no-cors', signal: controller.signal });
    clearTimeout(timeout);
    bridgeUp = true; upCount = 1;
  } catch (e) {
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444' });
    return;
  }
  if (bridgeUp) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      const resp = await fetch(`${BRIDGE}/api/terminal`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'netstat -ano | findstr "LISTENING" | findstr "9990 9991 9997 9998 18789"' }),
        signal: controller.signal
      });
      clearTimeout(timeout);
      const data = await resp.json();
      const output = data.output || data.result || '';
      [9990, 9991, 9997, 9998, 18789].forEach(port => {
        if (output.includes(':' + port)) upCount++;
      });
    } catch (e) {}
  }
  const total = PORTS.length;
  if (upCount >= total) {
    chrome.action.setBadgeText({ text: '✓' });
    chrome.action.setBadgeBackgroundColor({ color: '#22c55e' });
  } else if (upCount > 1) {
    chrome.action.setBadgeText({ text: `${upCount}` });
    chrome.action.setBadgeBackgroundColor({ color: '#eab308' });
  } else {
    chrome.action.setBadgeText({ text: '1' });
    chrome.action.setBadgeBackgroundColor({ color: '#f97316' });
  }
}
chrome.runtime.onInstalled.addListener(() => { checkHealth(); });
chrome.alarms.create('healthCheck', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => { if (alarm.name === 'healthCheck') { checkHealth(); } });
checkHealth();
