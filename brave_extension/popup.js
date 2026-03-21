// ===============================================================
// NovaX Shield -- Popup Dashboard Controller
// ===============================================================

document.addEventListener("DOMContentLoaded", async () => {
  await refreshStatus();

  // Set up toggle listeners
  document.querySelectorAll(".toggle-switch").forEach(toggle => {
    toggle.addEventListener("click", () => {
      const key = toggle.dataset.key;
      const isOn = toggle.classList.contains("on");
      toggle.classList.toggle("on");

      // Send config update to background
      chrome.runtime.sendMessage({
        type: "UPDATE_CONFIG",
        data: { [key]: !isOn }
      });
    });
  });

  // Auto-refresh every 5 seconds (clean up on popup close)
  const refreshInterval = setInterval(refreshStatus, 5000);
  window.addEventListener("unload", () => clearInterval(refreshInterval));
});

async function refreshStatus() {
  let status = null;

  try {
    status = await chrome.runtime.sendMessage({ type: "GET_STATUS" });
  } catch (e) {
    console.error("[NovaX Shield] Could not reach service worker:", e);
  }

  // If service worker is unavailable, load stats from storage directly
  if (!status) {
    try {
      const stored = await chrome.storage.local.get([
        "novax_alive", "novax_security_stats", "novax_proxy_stats"
      ]);
      status = {
        novaAlive: stored.novax_alive !== undefined ? stored.novax_alive : true,
        failCount: 0,
        securityStats: stored.novax_security_stats || {},
        proxyStats: stored.novax_proxy_stats || {},
        config: {},
        fromCache: true
      };
    } catch (e2) {
      return;
    }
  }

  // Update connection status dot and label
  const dot = document.getElementById("statusDot");
  const versionLine = document.getElementById("versionLine");

  if (status.novaAlive) {
    dot.className = "status-dot alive";
    if (versionLine) {
      versionLine.textContent = "v3.0.0 -- Connected";
      versionLine.style.color = "#00e676";
    }
  } else if (status.fromCache) {
    // Service worker down but we have cached data
    dot.className = "status-dot cached";
    if (versionLine) {
      versionLine.textContent = "v3.0.0 -- Offline (cached)";
      versionLine.style.color = "#ffc107";
    }
  } else {
    // Orchestrator is down but service worker is running
    dot.className = "status-dot dead";
    if (versionLine) {
      versionLine.textContent = "v3.0.0 -- Offline (cached)";
      versionLine.style.color = "#ffc107";
    }
  }

  // Update shield status indicator
  const shieldStatus = document.getElementById("shieldStatus");
  const shieldIcon = document.getElementById("shieldIcon");
  if (shieldStatus && shieldIcon) {
    if (status.novaAlive) {
      shieldStatus.textContent = "SHIELD ACTIVE";
      shieldStatus.style.color = "#00e676";
      shieldIcon.innerHTML = "&#x1F6E1;";
    } else {
      // Shield still provides local protection even when orchestrator is down
      shieldStatus.textContent = "SHIELD ACTIVE (Local)";
      shieldStatus.style.color = "#ffc107";
      shieldIcon.innerHTML = "&#x1F6E1;";
    }
  }

  // Update stats
  const secStats = status.securityStats || {};
  const proxyStats = status.proxyStats || {};

  document.getElementById("urlsScanned").textContent =
    formatNumber(secStats.urlsScanned || 0);
  document.getElementById("threatsBlocked").textContent =
    formatNumber(secStats.threatsBlocked || 0);
  document.getElementById("downloadsScanned").textContent =
    formatNumber(secStats.downloadsScanned || 0);
  document.getElementById("tokensSaved").textContent =
    formatNumber(proxyStats.tokensSaved || 0);

  // Cache stats
  const cacheHitsEl = document.getElementById("cacheHits");
  const aiInterceptedEl = document.getElementById("aiIntercepted");
  const queriesRoutedEl = document.getElementById("queriesRouted");
  const tokensSavedCacheEl = document.getElementById("tokensSavedCache");
  if (cacheHitsEl) cacheHitsEl.textContent = formatNumber(proxyStats.totalProcessed || 0);
  if (aiInterceptedEl) aiInterceptedEl.textContent = formatNumber(proxyStats.totalIntercepted || 0);
  if (queriesRoutedEl) queriesRoutedEl.textContent = formatNumber(proxyStats.queriesRouted || 0);
  if (tokensSavedCacheEl) tokensSavedCacheEl.textContent = "~" + formatNumber(proxyStats.tokensSaved || 0);

  // Last provider badge
  const providerBadge = document.getElementById("providerBadge");
  const lastProvider = document.getElementById("lastProvider");
  if (providerBadge && lastProvider && proxyStats.lastProvider) {
    providerBadge.style.display = "block";
    lastProvider.textContent = proxyStats.lastProvider;
  }

  // Update toggles to match config (skip if loaded from cache with no config)
  if (!status.fromCache) {
    const cfg = status.config || {};
    updateToggle("toggleSecurity", cfg.securityEnabled);
    updateToggle("toggleProxy", cfg.proxyEnabled);
    updateToggle("toggleBlock", cfg.blockThreats);
    updateToggle("toggleDownloads", cfg.scanDownloads);
    updateToggle("toggleForms", cfg.scanForms);
    updateToggle("toggleCache", cfg.cacheEnabled !== false);
    updateToggle("toggleRoute", cfg.routeViaNova);
  }

  // Update threat log
  updateThreatLog(secStats.recentThreats || []);
}

function updateToggle(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  if (value) {
    el.classList.add("on");
  } else {
    el.classList.remove("on");
  }
}

function updateThreatLog(threats) {
  const container = document.getElementById("threatLog");
  if (!threats || threats.length === 0) {
    container.innerHTML = '<div class="empty-threats">No threats detected -- all clear +1</div>';
    return;
  }

  container.innerHTML = threats.map(t => {
    const time = new Date(t.timestamp).toLocaleTimeString();
    const url = t.url || "unknown";
    const truncUrl = url.length > 50 ? url.substring(0, 50) + "..." : url;
    return '<div class="threat-item">' +
      '<span class="url" title="' + escapeHtml(url) + '">' + escapeHtml(truncUrl) + '</span>' +
      '<span class="time">' + time + '</span>' +
      '</div>';
  }).join("");
}

function formatNumber(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return String(n);
}

function escapeHtml(str) {
  var div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
