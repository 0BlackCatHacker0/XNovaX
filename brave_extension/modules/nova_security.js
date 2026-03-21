// ===================================================================
// NovaX Security Module -- Ternary Threat Detection for Brave
// ===================================================================
// Extends NovaX's security infrastructure to the browser layer.
// Every URL, download, form, and script gets a ternary score:
//   +1 = safe (allow)    0 = uncertain (warn)    -1 = threat (block)
//
// Layers on TOP of Brave's existing shield -- defense in depth.
// Uses NovaX's shield service, validator, and intelligence services.
// ===================================================================

import { NOVAX_ENDPOINT, TRIT } from "./nova_proxy.js";

// -- Threat categories --
const THREAT = {
  PHISHING: "phishing",
  MALWARE: "malware",
  TRACKER: "tracker",
  CRYPTO_MINER: "crypto_miner",
  XSS: "xss",
  DATA_EXFIL: "data_exfiltration",
  INJECTION: "injection",
  SUSPICIOUS_REDIRECT: "suspicious_redirect",
  FAKE_FORM: "fake_form",
  HOMOGRAPH: "homograph_attack"
};

// -- Known dangerous patterns (local fast-check before NovaX call) --
const DANGER_PATTERNS = [
  // Crypto miners
  /coinhive|cryptonight|minero|coin-?hive/i,
  // Known phishing TLD abuse
  /\.(tk|ml|ga|cf|gq)\//i,
  // Data exfil patterns
  /exfil|steal|grab|harvest.*cookie/i,
  // Suspicious encoded payloads
  /eval\s*\(\s*atob/i,
  /document\.cookie\s*[+=]/i,
  // Homograph detection (mixed scripts in domain)
  /xn--.*\.(com|net|org|io)/i
];

// -- Safe domain allowlist (never block these) --
const SAFE_DOMAINS = new Set([
  "127.0.0.1", "localhost",
  "github.com", "gitlab.com",
  "google.com", "googleapis.com",
  "anthropic.com", "claude.ai",
  "openai.com", "huggingface.co",
  "microsoft.com", "brave.com",
  "mozilla.org", "wikipedia.org",
  "stackoverflow.com",
  "python.org", "nodejs.org", "rust-lang.org",
  "npmjs.com", "pypi.org", "crates.io"
]);

class NovaSecurity {
  constructor() {
    this.enabled = true;
    this.cache = new Map();        // URL -> { trit, timestamp, details }
    this.cacheMaxAge = 300000;     // 5 min cache
    this.cacheMaxSize = 10000;
    this.stats = {
      urlsScanned: 0,
      threatsBlocked: 0,
      warningsIssued: 0,
      downloadsScanned: 0,
      formsProtected: 0
    };
    this.threatLog = [];           // Recent threats for dashboard
    this.maxThreatLog = 100;
  }

  // ==========================================
  // URL SCANNING -- Ternary threat scoring
  // ==========================================

  async scanURL(url) {
    this.stats.urlsScanned++;

    // Layer 1: Cache check
    const cached = this._checkCache(url);
    if (cached !== null) return cached;

    // Layer 2: Allowlist fast-pass
    const domain = this._extractDomain(url);
    if (SAFE_DOMAINS.has(domain)) {
      const result = { trit: TRIT.PLUS, source: "allowlist", domain };
      this._setCache(url, result);
      return result;
    }

    // Layer 3: Local pattern scan (no network needed)
    const localScan = this._localPatternScan(url);
    if (localScan.trit === TRIT.MINUS) {
      this._logThreat(url, localScan);
      this._setCache(url, localScan);
      return localScan;
    }

    // Layer 4: NovaX deep scan via orchestrator
    const novaScan = await this._novaDeepScan(url, domain);
    this._setCache(url, novaScan);

    if (novaScan.trit === TRIT.MINUS) {
      this.stats.threatsBlocked++;
      this._logThreat(url, novaScan);
    } else if (novaScan.trit === TRIT.ZERO) {
      this.stats.warningsIssued++;
    }

    return novaScan;
  }

  // -- Local pattern matching (Layer 3) --
  _localPatternScan(url) {
    for (const pattern of DANGER_PATTERNS) {
      if (pattern.test(url)) {
        return {
          trit: TRIT.MINUS,
          source: "local_pattern",
          threat: THREAT.MALWARE,
          pattern: pattern.source,
          confidence: 0.85
        };
      }
    }

    // Check for suspicious URL structures
    const checks = [];

    // Too many subdomains (common in phishing)
    const domain = this._extractDomain(url);
    const subdomainCount = domain.split(".").length;
    if (subdomainCount > 4) {
      checks.push({ threat: THREAT.PHISHING, detail: "excessive_subdomains" });
    }

    // Extremely long URL (data exfil or encoded payload)
    if (url.length > 2000) {
      checks.push({ threat: THREAT.DATA_EXFIL, detail: "url_length_" + url.length });
    }

    // IP address as domain (bypassing DNS)
    if (/^https?:\/\/\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/.test(url)) {
      // Allow localhost/private ranges
      if (!url.includes("127.0.0.1") && !url.includes("192.168.") && !url.includes("10.")) {
        checks.push({ threat: THREAT.SUSPICIOUS_REDIRECT, detail: "raw_ip_domain" });
      }
    }

    // Homograph attack detection
    if (this._detectHomograph(domain)) {
      checks.push({ threat: THREAT.HOMOGRAPH, detail: "mixed_script_domain" });
    }

    if (checks.length > 0) {
      return {
        trit: TRIT.ZERO,
        source: "local_heuristic",
        threats: checks,
        confidence: 0.6
      };
    }

    return { trit: TRIT.PLUS, source: "local_clean" };
  }

  // -- NovaX deep scan (Layer 4) --
  async _novaDeepScan(url, domain) {
    try {
      const resp = await fetch(`${NOVAX_ENDPOINT}/api/security/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: url,
          domain: domain,
          scan_type: "url",
          ternary_mode: true,
          layers: ["shield", "validator", "intelligence"]
        }),
        signal: AbortSignal.timeout(5000)
      });

      if (resp.ok) {
        const result = await resp.json();
        return {
          trit: result.trit ?? TRIT.PLUS,
          source: "novax_deep",
          details: result,
          confidence: result.confidence ?? 0.9
        };
      }

      // NovaX unavailable -- trust but verify (ternary 0)
      return { trit: TRIT.ZERO, source: "novax_unavailable" };
    } catch {
      return { trit: TRIT.ZERO, source: "novax_timeout" };
    }
  }

  // ==========================================
  // DOWNLOAD SCANNING
  // ==========================================

  async scanDownload(downloadItem) {
    this.stats.downloadsScanned++;

    const url = downloadItem.url || "";
    const filename = downloadItem.filename || "";
    const mime = downloadItem.mime || "";
    const size = downloadItem.fileSize || 0;

    // Dangerous file extensions
    const dangerousExts = /\.(exe|bat|cmd|ps1|vbs|vbe|js|jse|wsf|wsh|scr|pif|msi|dll|com|hta|cpl|inf|reg)$/i;
    const suspiciousExts = /\.(zip|rar|7z|tar|iso|img|dmg)$/i;

    let trit = TRIT.PLUS;
    const warnings = [];

    // Check filename
    if (dangerousExts.test(filename)) {
      trit = TRIT.MINUS;
      warnings.push({ level: "critical", msg: "Dangerous executable file type" });
    } else if (suspiciousExts.test(filename)) {
      trit = TRIT.ZERO;
      warnings.push({ level: "warn", msg: "Archive file -- contents unknown" });
    }

    // Double extension trick (e.g., document.pdf.exe)
    const parts = filename.split(".");
    if (parts.length > 2 && dangerousExts.test(filename)) {
      trit = TRIT.MINUS;
      warnings.push({ level: "critical", msg: "Double extension detected -- likely disguised" });
    }

    // Abnormally small executable (dropper)
    if (dangerousExts.test(filename) && size > 0 && size < 50000) {
      warnings.push({ level: "warn", msg: "Suspiciously small executable -- possible dropper" });
    }

    // Route through NovaX for deep analysis
    const novaScan = await this._scanDownloadViaNova(url, filename, mime, size);
    if (novaScan.trit < trit) trit = novaScan.trit;

    if (trit === TRIT.MINUS) {
      this.stats.threatsBlocked++;
      this._logThreat(url, { threat: "dangerous_download", filename, warnings });
    }

    return { trit, warnings, filename, novaScan };
  }

  async _scanDownloadViaNova(url, filename, mime, size) {
    try {
      const resp = await fetch(`${NOVAX_ENDPOINT}/api/security/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url, filename, mime, size,
          scan_type: "download",
          ternary_mode: true
        }),
        signal: AbortSignal.timeout(5000)
      });
      if (resp.ok) {
        const result = await resp.json();
        return { trit: result.trit ?? TRIT.ZERO, details: result };
      }
      return { trit: TRIT.ZERO, source: "novax_unavailable" };
    } catch {
      return { trit: TRIT.ZERO, source: "novax_timeout" };
    }
  }

  // ==========================================
  // FORM PROTECTION -- Detect fake/phishing forms
  // ==========================================

  scanForm(formData) {
    this.stats.formsProtected++;

    const { action, method, fields, pageUrl } = formData;
    const warnings = [];
    let trit = TRIT.PLUS;

    // Form submits to different domain than page
    if (action && pageUrl) {
      const formDomain = this._extractDomain(action);
      const pageDomain = this._extractDomain(pageUrl);
      if (formDomain && pageDomain && formDomain !== pageDomain) {
        trit = TRIT.ZERO;
        warnings.push({
          level: "warn",
          msg: `Form submits to different domain: ${formDomain}`
        });
      }
    }

    // Form asks for sensitive data
    const sensitiveFields = ["password", "ssn", "social", "credit", "card", "cvv", "pin", "secret", "token"];
    for (const field of (fields || [])) {
      const name = (field.name || "").toLowerCase();
      const type = (field.type || "").toLowerCase();
      for (const sensitive of sensitiveFields) {
        if (name.includes(sensitive) || type === "password") {
          // Check if page is HTTPS
          if (pageUrl && pageUrl.startsWith("http://")) {
            trit = TRIT.MINUS;
            warnings.push({
              level: "critical",
              msg: `Sensitive field "${name}" on non-HTTPS page`
            });
          }
          break;
        }
      }
    }

    // Hidden fields with suspicious names
    const hiddenSuspicious = (fields || []).filter(f =>
      f.type === "hidden" && /token|redirect|return|callback|next/i.test(f.name || "")
    );
    if (hiddenSuspicious.length > 3) {
      trit = Math.min(trit, TRIT.ZERO);
      warnings.push({
        level: "warn",
        msg: `${hiddenSuspicious.length} suspicious hidden fields`
      });
    }

    return { trit, warnings };
  }

  // ==========================================
  // SCRIPT/CONTENT SCANNING
  // ==========================================

  scanScript(scriptContent, sourceUrl) {
    const warnings = [];
    let trit = TRIT.PLUS;

    // Detect obfuscation patterns
    const obfuscationPatterns = [
      { re: /eval\s*\(\s*unescape/i, threat: "eval_unescape" },
      { re: /eval\s*\(\s*atob/i, threat: "eval_atob" },
      { re: /eval\s*\(\s*String\.fromCharCode/i, threat: "eval_charcode" },
      { re: /document\.write\s*\(\s*unescape/i, threat: "doc_write_unescape" },
      { re: /\bwindow\[['"]eval['"]\]/i, threat: "indirect_eval" },
      { re: /new\s+Function\s*\(\s*atob/i, threat: "function_atob" }
    ];

    for (const pat of obfuscationPatterns) {
      if (pat.re.test(scriptContent)) {
        trit = TRIT.MINUS;
        warnings.push({ level: "critical", threat: pat.threat });
      }
    }

    // Crypto mining detection
    const minerPatterns = [
      /CryptoNight|cryptonight/,
      /coinhive|CoinHive/,
      /wasmMiner|WasmMiner/,
      /startMining|start_mining/i
    ];
    for (const pat of minerPatterns) {
      if (pat.test(scriptContent)) {
        trit = TRIT.MINUS;
        warnings.push({ level: "critical", threat: THREAT.CRYPTO_MINER });
      }
    }

    // Keylogger patterns
    if (/addEventListener.*keydown.*\.key/i.test(scriptContent) &&
        /XMLHttpRequest|fetch\s*\(/.test(scriptContent)) {
      trit = TRIT.ZERO;
      warnings.push({ level: "warn", threat: "possible_keylogger" });
    }

    return { trit, warnings, sourceUrl };
  }

  // ==========================================
  // HELPERS
  // ==========================================

  _extractDomain(url) {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return "";
    }
  }

  _detectHomograph(domain) {
    // Check for mixed-script characters (punycode/IDN abuse)
    if (domain.startsWith("xn--")) return true;
    // Check for look-alike characters
    const confusables = /[\u0430\u0435\u043e\u0440\u0441\u0443\u0445\u04bb]/; // Cyrillic lookalikes
    return confusables.test(domain);
  }

  _checkCache(url) {
    const entry = this.cache.get(url);
    if (!entry) return null;
    if (Date.now() - entry.timestamp > this.cacheMaxAge) {
      this.cache.delete(url);
      return null;
    }
    return entry.result;
  }

  _setCache(url, result) {
    if (this.cache.size >= this.cacheMaxSize) {
      // Evict oldest 20%
      const entries = [...this.cache.entries()];
      entries.sort((a, b) => a[1].timestamp - b[1].timestamp);
      const evictCount = Math.floor(this.cacheMaxSize * 0.2);
      for (let i = 0; i < evictCount; i++) {
        this.cache.delete(entries[i][0]);
      }
    }
    this.cache.set(url, { result, timestamp: Date.now() });
  }

  _logThreat(url, details) {
    this.threatLog.unshift({
      url, details, timestamp: Date.now()
    });
    if (this.threatLog.length > this.maxThreatLog) {
      this.threatLog.pop();
    }
  }

  getStats() {
    return {
      ...this.stats,
      cacheSize: this.cache.size,
      recentThreats: this.threatLog.slice(0, 10),
      enabled: this.enabled
    };
  }
}

const novaSecurity = new NovaSecurity();
export { novaSecurity, NovaSecurity, THREAT };
