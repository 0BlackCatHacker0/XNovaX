// NovaX Shield v3.0 - Background Service Worker (Bundled, ASCII-only)

const NOVAX_ENDPOINT = "http://127.0.0.1:9999";
const TRIT = { PLUS: 1, ZERO: 0, MINUS: -1 };

const THREAT = {
  PHISHING: "phishing", MALWARE: "malware", TRACKER: "tracker",
  CRYPTO_MINER: "crypto_miner", XSS: "xss", DATA_EXFIL: "data_exfiltration",
  INJECTION: "injection", SUSPICIOUS_REDIRECT: "suspicious_redirect",
  FAKE_FORM: "fake_form", HOMOGRAPH: "homograph_attack"
};

// --- PROXY ---
const novaProxy = {
  stats: { totalIntercepted: 0, totalProcessed: 0, tokensSaved: 0, bytesRouted: 0, queriesIntercepted: 0, queriesRouted: 0, lastProvider: "" },
  streamBuffer: new Map(),

  async ping() {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 4000);
      const resp = await fetch(NOVAX_ENDPOINT + "/health", { signal: controller.signal });
      clearTimeout(timer);
      return resp.ok ? TRIT.PLUS : TRIT.ZERO;
    } catch (e) {
      return TRIT.MINUS;
    }
  },

  interceptStream(requestId, url, body) {
    const provider = this._isAI(url);
    if (!provider) return null;
    this.stats.totalIntercepted++;
    return { trit: TRIT.PLUS, provider, buffered: 1 };
  },

  _isAI(url) {
    const providers = [
      ["api.anthropic.com", "anthropic"], ["api.openai.com", "openai"],
      ["openrouter.ai/api", "openrouter"], ["claude.ai/api", "claude_web"],
      ["chat.openai.com", "chatgpt_web"]
    ];
    for (const [m, p] of providers) { if (url.includes(m)) return p; }
    return null;
  },

  getStats() {
    return { ...this.stats, enabled: true, trit: this.stats.totalProcessed > 0 ? TRIT.PLUS : TRIT.ZERO };
  }
};

// --- SECURITY ---
const DANGER_PATTERNS = [
  /coinhive|cryptonight|minero|coin-?hive/i,
  /exfil|steal|grab|harvest.*cookie/i,
  /eval\s*\(\s*atob/i,
  /document\.cookie\s*[+=]/i,
  /xn--.*\.(com|net|org|io)/i
];
// TLD patterns tested against domain only (not full URL) to avoid false positives
const DANGER_TLD_PATTERN = /\.(tk|ml|ga|cf|gq)$/i;

const SAFE_DOMAINS = new Set([
  "127.0.0.1", "localhost", "github.com", "gitlab.com",
  "google.com", "googleapis.com", "anthropic.com", "claude.ai",
  "openai.com", "huggingface.co", "microsoft.com", "brave.com",
  "mozilla.org", "wikipedia.org", "stackoverflow.com",
  "python.org", "nodejs.org", "rust-lang.org",
  "npmjs.com", "pypi.org", "crates.io"
]);

const novaSecurity = {
  cache: new Map(),
  threatLog: [],
  stats: { urlsScanned: 0, threatsBlocked: 0, warningsIssued: 0, downloadsScanned: 0, formsProtected: 0 },

  async scanURL(url) {
    this.stats.urlsScanned++;
    const cached = this.cache.get(url);
    if (cached && Date.now() - cached.ts < 300000) return cached.r;

    // Evict if cache too large (cap at 10000)
    if (this.cache.size > 10000) {
      const cutoff = Date.now() - 300000;
      for (const [k, v] of this.cache) {
        if (v.ts < cutoff) this.cache.delete(k);
      }
      if (this.cache.size > 8000) {
        const keys = [...this.cache.keys()].slice(0, 2000);
        keys.forEach(k => this.cache.delete(k));
      }
    }

    const domain = extractDomain(url);
    if (SAFE_DOMAINS.has(domain)) {
      const r = { trit: TRIT.PLUS, source: "allowlist", domain };
      this.cache.set(url, { r, ts: Date.now() });
      return r;
    }

    for (const pat of DANGER_PATTERNS) {
      if (pat.test(url)) {
        const r = { trit: TRIT.MINUS, source: "local_pattern", threat: THREAT.MALWARE };
        this.stats.threatsBlocked++;
        this.threatLog.unshift({ url, details: r, timestamp: Date.now() });
        if (this.threatLog.length > 100) this.threatLog.length = 100;
        this.cache.set(url, { r, ts: Date.now() });
        return r;
      }
    }

    // Check suspicious free TLDs against domain only (not path)
    if (DANGER_TLD_PATTERN.test(domain)) {
      const r = { trit: TRIT.ZERO, source: "suspicious_tld" };
      this.stats.warningsIssued++;
      this.cache.set(url, { r, ts: Date.now() });
      return r;
    }

    const subdomains = domain.split(".").length;
    if (subdomains > 4) {
      const r = { trit: TRIT.ZERO, source: "suspicious_subdomains" };
      this.stats.warningsIssued++;
      this.cache.set(url, { r, ts: Date.now() });
      return r;
    }

    const r = { trit: TRIT.PLUS, source: "local_clean" };
    this.cache.set(url, { r, ts: Date.now() });
    return r;
  },

  async scanDownload(item) {
    this.stats.downloadsScanned++;
    const fname = item.filename || "";
    const dangerExt = /\.(exe|bat|cmd|ps1|vbs|vbe|js|jse|wsf|wsh|scr|pif|msi|dll|com|hta|cpl)$/i;
    const warnings = [];
    let trit = TRIT.PLUS;

    if (dangerExt.test(fname)) {
      trit = TRIT.MINUS;
      warnings.push({ level: "critical", msg: "Dangerous executable file type" });
      this.stats.threatsBlocked++;
    }

    const parts = fname.split(".");
    if (parts.length > 2 && dangerExt.test(fname)) {
      warnings.push({ level: "critical", msg: "Double extension - likely disguised" });
    }

    return { trit, warnings, filename: fname };
  },

  scanForm(data) {
    this.stats.formsProtected++;
    const warnings = [];
    let trit = TRIT.PLUS;

    if (data.action && data.pageUrl) {
      const fd = extractDomain(data.action);
      const pd = extractDomain(data.pageUrl);
      if (fd && pd && fd !== pd) {
        trit = TRIT.ZERO;
        warnings.push({ level: "warn", msg: "Form submits to different domain: " + fd });
      }
    }

    for (const field of (data.fields || [])) {
      const name = (field.name || "").toLowerCase();
      if (/password|ssn|credit|card|cvv|pin|secret|token/.test(name)) {
        if (data.pageUrl && data.pageUrl.startsWith("http://")) {
          trit = TRIT.MINUS;
          warnings.push({ level: "critical", msg: "Sensitive field on non-HTTPS page" });
        }
        break;
      }
    }
    return { trit, warnings };
  },

  scanScript(content, url) {
    const warnings = [];
    let trit = TRIT.PLUS;
    const pats = [
      [/eval\s*\(\s*atob/i, "eval_atob"], [/eval\s*\(\s*unescape/i, "eval_unescape"],
      [/eval\s*\(\s*String\.fromCharCode/i, "eval_charcode"],
      [/coinhive|CoinHive|startMining/i, "crypto_miner"]
    ];
    for (const [re, threat] of pats) {
      if (re.test(content)) { trit = TRIT.MINUS; warnings.push({ level: "critical", threat }); }
    }
    return { trit, warnings, sourceUrl: url };
  },

  getStats() {
    return { ...this.stats, cacheSize: this.cache.size, recentThreats: this.threatLog.slice(0, 10), enabled: true };
  }
};

function extractDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch (e) { return ""; }
}

// --- STATE ---
let novaAlive = true;
let failCount = 0;
let lastBadgeState = null;
let config = {
  proxyEnabled: true, securityEnabled: true, blockThreats: true,
  warnUncertain: true, scanDownloads: true, scanForms: true,
  scanScripts: true, notifyThreats: true
};

// Set badge to ON immediately on service worker start (before any async)
chrome.action.setBadgeText({ text: "ON" });
chrome.action.setBadgeBackgroundColor({ color: "#00C853" });
chrome.action.setTitle({ title: "NovaX Shield - ACTIVE (Level 4)" });

// --- BADGE ---
function updateBadge() {
  const newState = novaAlive ? "ON" : "OFF";
  if (newState === lastBadgeState) return;
  lastBadgeState = newState;
  if (novaAlive) {
    chrome.action.setBadgeText({ text: "ON" });
    chrome.action.setBadgeBackgroundColor({ color: "#00C853" });
    chrome.action.setTitle({ title: "NovaX Shield - ACTIVE (Level 4)" });
  } else {
    chrome.action.setBadgeText({ text: "OFF" });
    chrome.action.setBadgeBackgroundColor({ color: "#FF5252" });
    chrome.action.setTitle({ title: "NovaX Shield - DISCONNECTED" });
  }
}

// Save stats to storage so they survive service worker restarts
async function saveStats() {
  try {
    await chrome.storage.local.set({
      novax_security_stats: novaSecurity.stats,
      novax_proxy_stats: novaProxy.stats
    });
  } catch (e) {}
}

// Load stats from storage on startup
async function loadStats() {
  try {
    const stored = await chrome.storage.local.get([
      "novax_security_stats", "novax_proxy_stats"
    ]);
    if (stored.novax_security_stats) {
      Object.assign(novaSecurity.stats, stored.novax_security_stats);
    }
    if (stored.novax_proxy_stats) {
      Object.assign(novaProxy.stats, stored.novax_proxy_stats);
    }
  } catch (e) {}
}

// Restore state on startup
(async () => {
  try {
    const stored = await chrome.storage.local.get("novax_alive");
    if (stored.novax_alive !== undefined) {
      novaAlive = stored.novax_alive;
    }
    lastBadgeState = null;
    updateBadge();
    await loadStats();
  } catch (e) {}
})();

async function checkHealth() {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);
    const resp = await fetch(NOVAX_ENDPOINT + "/health", { signal: controller.signal });
    clearTimeout(timer);
    if (resp.ok) { novaAlive = true; failCount = 0; }
    else { failCount++; }
  } catch (e) { failCount++; }
  if (failCount >= 5) { novaAlive = false; }
  try { await chrome.storage.local.set({ novax_alive: novaAlive }); } catch (e) {}
  updateBadge();
  await saveStats();
}

async function loadConfig() {
  try {
    const stored = await chrome.storage.local.get(["novax_config", "novax_alive"]);
    if (stored.novax_config) config = { ...config, ...stored.novax_config };
    if (stored.novax_alive !== undefined) {
      novaAlive = stored.novax_alive;
    }
    lastBadgeState = null;
    updateBadge();
    await loadStats();
  } catch (e) {}
}

async function saveConfig() {
  try { await chrome.storage.local.set({ novax_config: config }); } catch (e) {}
}

// --- INIT ---
async function ensureAlarm() {
  const existing = await chrome.alarms.get("nova-health");
  if (!existing) chrome.alarms.create("nova-health", { periodInMinutes: 2 });
}

chrome.runtime.onInstalled.addListener(async () => {
  await loadConfig();
  await checkHealth();
  await ensureAlarm();
});

chrome.runtime.onStartup.addListener(async () => {
  await loadConfig();
  await checkHealth();
  await ensureAlarm();
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === "nova-health") await checkHealth();
});

// --- NAVIGATION SCANNING ---
chrome.webNavigation.onBeforeNavigate.addListener(async (details) => {
  if (!config.securityEnabled || details.frameId !== 0) return;
  const result = await novaSecurity.scanURL(details.url);
  await saveStats();
  if (result.trit === TRIT.MINUS && config.blockThreats) {
    try {
      await chrome.tabs.update(details.tabId, {
        url: chrome.runtime.getURL("warning.html?url=" + encodeURIComponent(details.url))
      });
    } catch (e) {}
  }
});

// --- DOWNLOAD SCANNING ---
chrome.downloads.onCreated.addListener(async (item) => {
  if (!config.scanDownloads) return;
  const result = await novaSecurity.scanDownload(item);
  await saveStats();
  if (result.trit === TRIT.MINUS) {
    try { await chrome.downloads.cancel(item.id); } catch (e) {}
    if (config.notifyThreats) {
      chrome.notifications.create({
        type: "basic", iconUrl: "icons/nova48.png",
        title: "NovaX Shield - Download Blocked",
        message: result.warnings.map(function(w) { return w.msg; }).join(", "), priority: 2
      });
    }
  }
});

// --- AI STREAM INTERCEPTION ---
chrome.webRequest.onCompleted.addListener(
  async (details) => {
    if (!config.proxyEnabled) return;
    novaProxy.interceptStream(details.requestId, details.url, null);
  },
  { urls: ["*://api.anthropic.com/*", "*://api.openai.com/*", "*://openrouter.ai/*", "*://claude.ai/*"] }
);

// --- MESSAGE HANDLER ---
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || !msg.type) return false;

  if (msg.type === "GET_STATUS") {
    // Return cached state immediately -- health check runs on its own alarm
    sendResponse({
      novaAlive: novaAlive,
      failCount: failCount,
      proxyStats: novaProxy.getStats(),
      securityStats: novaSecurity.getStats(),
      config: config
    });
    return false;
  }

  if (msg.type === "UPDATE_CONFIG") {
    config = { ...config, ...msg.data };
    saveConfig();
    sendResponse({ trit: TRIT.PLUS });
    return false;
  }

  if (msg.type === "SCAN_FORM") {
    if (config.scanForms) {
      sendResponse(novaSecurity.scanForm(msg.data));
    } else {
      sendResponse({ trit: TRIT.ZERO, warnings: [] });
    }
    return false;
  }

  if (msg.type === "SCAN_SCRIPT") {
    if (config.scanScripts) {
      sendResponse(novaSecurity.scanScript(msg.data.content, msg.data.url));
    } else {
      sendResponse({ trit: TRIT.ZERO, warnings: [] });
    }
    return false;
  }

  if (msg.type === "GET_THREAT_LOG") {
    sendResponse({ threats: novaSecurity.getStats().recentThreats });
    return false;
  }

  if (msg.type === "PROXY_CACHE_HIT") {
    novaProxy.stats.tokensSaved += (msg.data && msg.data.tokens) || 0;
    novaProxy.stats.totalProcessed++;
    saveStats();
    return false;
  }

  if (msg.type === "PROXY_QUERY_INTERCEPTED") {
    novaProxy.stats.queriesIntercepted = (msg.data && msg.data.count) || (novaProxy.stats.queriesIntercepted + 1);
    saveStats();
    return false;
  }

  if (msg.type === "PROXY_ROUTED") {
    novaProxy.stats.queriesRouted++;
    novaProxy.stats.tokensSaved += (msg.data && msg.data.tokens) || 0;
    novaProxy.stats.lastProvider = (msg.data && msg.data.provider) || "";
    saveStats();
    return false;
  }

  if (msg.type === "PROXY_STATS_UPDATE") {
    // Use page-context stats as source of truth (avoid double-counting with per-event messages)
    if (msg.data) {
      if (msg.data.cacheHits !== undefined) novaProxy.stats.totalProcessed = msg.data.cacheHits;
      if (msg.data.tokensSaved !== undefined) novaProxy.stats.tokensSaved = msg.data.tokensSaved;
      if (msg.data.proxied !== undefined) novaProxy.stats.queriesRouted = msg.data.proxied;
      if (msg.data.queriesIntercepted !== undefined) novaProxy.stats.queriesIntercepted = msg.data.queriesIntercepted;
    }
    saveStats();
    return false;
  }

  return false;
});
