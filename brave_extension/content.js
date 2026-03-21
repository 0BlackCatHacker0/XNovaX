// ===============================================================
// NovaX Shield -- Content Script (runs on every page)
// ===============================================================
// Provides page-level protection:
//   - Form interception and validation
//   - Inline script scanning
//   - Clipboard protection
//   - DOM mutation watching for injected threats
// ===============================================================

(() => {
  "use strict";

  const TRIT = { PLUS: 1, ZERO: 0, MINUS: -1 };

  // ==========================================
  // FORM PROTECTION
  // ==========================================

  function scanForms() {
    const forms = document.querySelectorAll("form");
    forms.forEach(form => {
      if (form.dataset.novaxScanned) return;
      form.dataset.novaxScanned = "true";

      form.addEventListener("submit", async (e) => {
        if (form.dataset.novaxSubmitting === "true") return;

        // Prevent immediately -- async scan happens after
        e.preventDefault();
        e.stopPropagation();

        const fields = [];
        const inputs = form.querySelectorAll("input, select, textarea");
        inputs.forEach(input => {
          fields.push({
            name: input.name || input.id || "",
            type: input.type || "text",
            hasValue: !!input.value
          });
        });

        const formData = {
          action: form.action || "",
          method: form.method || "GET",
          fields: fields,
          pageUrl: window.location.href
        };

        try {
          const result = await chrome.runtime.sendMessage({
            type: "SCAN_FORM",
            data: formData
          });

          if (result && result.trit === TRIT.MINUS) {
            showWarning(
              "NovaX Shield blocked this form submission",
              result.warnings.map(w => w.msg).join("\n"),
              () => {
                form.dataset.novaxSubmitting = "true";
                form.submit();
              }
            );
          } else if (result && result.trit === TRIT.ZERO) {
            showWarning(
              "NovaX Shield detected a suspicious form",
              result.warnings.map(w => w.msg).join("\n"),
              () => {
                form.dataset.novaxSubmitting = "true";
                form.submit();
              }
            );
          } else {
            // Clean -- submit normally
            form.dataset.novaxSubmitting = "true";
            form.submit();
          }
        } catch {
          // Extension communication failed -- allow form
          form.dataset.novaxSubmitting = "true";
          form.submit();
        }
      });
    });
  }

  // ==========================================
  // SCRIPT MONITORING
  // ==========================================

  function scanInlineScripts() {
    const scripts = document.querySelectorAll("script:not([data-novax-scanned])");
    scripts.forEach(async (script) => {
      script.dataset.novaxScanned = "true";

      // Only scan inline scripts (external are handled by URL scanning)
      if (!script.src && script.textContent) {
        try {
          const result = await chrome.runtime.sendMessage({
            type: "SCAN_SCRIPT",
            data: {
              content: script.textContent.substring(0, 10000), // Cap at 10KB
              url: window.location.href
            }
          });

          if (result && result.trit === TRIT.MINUS) {
            console.warn("[NovaX Shield] Dangerous inline script detected:", result.warnings);
          }
        } catch { /* extension unavailable */ }
      }
    });
  }

  // ==========================================
  // DOM MUTATION OBSERVER -- Watch for injected threats
  // ==========================================

  const observer = new MutationObserver((mutations) => {
    let hasNewForms = false;
    let hasNewScripts = false;

    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType !== Node.ELEMENT_NODE) continue;

        if (node.tagName === "FORM" || node.querySelector?.("form")) {
          hasNewForms = true;
        }
        if (node.tagName === "SCRIPT" || node.querySelector?.("script")) {
          hasNewScripts = true;
        }

        // Detect suspicious iframes
        if (node.tagName === "IFRAME") {
          checkSuspiciousIframe(node);
        }
        const iframes = node.querySelectorAll?.("iframe") || [];
        iframes.forEach(checkSuspiciousIframe);
      }
    }

    if (hasNewForms) scanForms();
    if (hasNewScripts) scanInlineScripts();
  });

  // Trusted iframe domains -- don't warn about these
  const TRUSTED_IFRAME_DOMAINS = [
    "google.com", "googleapis.com", "gstatic.com", "recaptcha.net",
    "youtube.com", "facebook.com", "twitter.com", "accounts.google.com",
    "contacts.google.com", "ogs.google.com", "mail.google.com",
    "aistudio.google.com", "docs.google.com", "drive.google.com"
  ];

  function checkSuspiciousIframe(iframe) {
    const src = iframe.src || "";
    if (!src) return; // skip empty src

    // Skip trusted domains
    try {
      const host = new URL(src).hostname;
      if (TRUSTED_IFRAME_DOMAINS.some(d => host === d || host.endsWith("." + d))) return;
    } catch { return; }

    // Zero-size iframes from untrusted domains
    const rect = iframe.getBoundingClientRect();
    if (rect.width <= 1 || rect.height <= 1) {
      console.warn("[NovaX Shield] Hidden iframe from untrusted domain:", src.substring(0, 80));
      iframe.dataset.novaxHidden = "true";
    }
  }

  // ==========================================
  // CLIPBOARD PROTECTION
  // ==========================================

  document.addEventListener("paste", (e) => {
    const text = e.clipboardData?.getData("text") || "";

    // Detect clipboard jacking (pasted content much longer than expected)
    if (text.length > 1000) {
      // Check for suspicious commands
      const dangerousCommands = [
        /curl\s+.*\|\s*(bash|sh)/i,
        /wget\s+.*&&\s*(bash|sh)/i,
        /powershell\s+-e[nc]*\s+/i,
        /rm\s+-rf\s+\//,
        /format\s+[a-z]:\s*\/[yq]/i
      ];

      for (const cmd of dangerousCommands) {
        if (cmd.test(text)) {
          e.preventDefault();
          showWarning(
            "NovaX Shield blocked a dangerous paste",
            "The clipboard contained a potentially dangerous command. This may be a clipboard-jacking attack.",
            () => {
              // Allow paste on user override via Clipboard API
              if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(() => {
                  document.execCommand("paste");
                }).catch(() => {
                  document.execCommand("insertText", false, text);
                });
              } else {
                document.execCommand("insertText", false, text);
              }
            }
          );
          return;
        }
      }
    }
  });

  // ==========================================
  // WARNING UI OVERLAY
  // ==========================================

  function showWarning(title, message, onProceed) {
    // Remove existing warning
    const existing = document.getElementById("novax-shield-warning");
    if (existing) existing.remove();

    const overlay = document.createElement("div");
    overlay.id = "novax-shield-warning";

    // Build DOM safely -- no innerHTML with user-controlled strings (XSS prevention)
    const backdrop = document.createElement("div");
    backdrop.setAttribute("style",
      "position: fixed; top: 0; left: 0; right: 0; bottom: 0;" +
      "background: rgba(0,0,0,0.85); z-index: 2147483647;" +
      "display: flex; align-items: center; justify-content: center;" +
      "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;"
    );

    const card = document.createElement("div");
    card.setAttribute("style",
      "background: #1a1a2e; border: 2px solid #e94560;" +
      "border-radius: 12px; padding: 32px; max-width: 500px;" +
      "color: #eee; box-shadow: 0 0 40px rgba(233,69,96,0.3);"
    );

    const headerRow = document.createElement("div");
    headerRow.setAttribute("style", "display: flex; align-items: center; gap: 12px; margin-bottom: 16px;");

    const iconDiv = document.createElement("div");
    iconDiv.setAttribute("style",
      "width: 40px; height: 40px; border-radius: 50%;" +
      "background: #e94560; display: flex; align-items: center;" +
      "justify-content: center; font-size: 24px; flex-shrink: 0;"
    );
    iconDiv.textContent = "\u26A0";

    const heading = document.createElement("h2");
    heading.setAttribute("style", "margin: 0; font-size: 18px; color: #e94560;");
    heading.textContent = title;

    headerRow.appendChild(iconDiv);
    headerRow.appendChild(heading);

    const msgPara = document.createElement("p");
    msgPara.setAttribute("style", "color: #ccc; line-height: 1.6; margin: 0 0 24px 0; white-space: pre-wrap;");
    msgPara.textContent = message;

    const btnRow = document.createElement("div");
    btnRow.setAttribute("style", "display: flex; gap: 12px; justify-content: flex-end;");

    const dismissBtn = document.createElement("button");
    dismissBtn.setAttribute("style",
      "padding: 10px 24px; border: 1px solid #555; border-radius: 8px;" +
      "background: transparent; color: #ccc; cursor: pointer; font-size: 14px;"
    );
    dismissBtn.textContent = "Go Back";

    const proceedBtn = document.createElement("button");
    proceedBtn.setAttribute("style",
      "padding: 10px 24px; border: none; border-radius: 8px;" +
      "background: #e94560; color: white; cursor: pointer; font-size: 14px;"
    );
    proceedBtn.textContent = "Proceed Anyway";

    btnRow.appendChild(dismissBtn);
    btnRow.appendChild(proceedBtn);

    card.appendChild(headerRow);
    card.appendChild(msgPara);
    card.appendChild(btnRow);
    backdrop.appendChild(card);
    overlay.appendChild(backdrop);

    document.body.appendChild(overlay);

    dismissBtn.onclick = () => overlay.remove();
    proceedBtn.onclick = () => {
      overlay.remove();
      if (onProceed) onProceed();
    };
  }

  // ==========================================
  // AI FETCH INTERCEPTOR -- Token-Saving Proxy
  // ==========================================
  // Wraps window.fetch to intercept AI API calls.
  // Phase 1: Check TBuffer cache before sending request
  // Phase 2: Optionally route through NovaX Cloud Router

  const AI_DOMAINS = [
    "api.anthropic.com", "api.openai.com", "openrouter.ai",
    "generativelanguage.googleapis.com"
  ];

  const NOVAX_TBUFFER = "http://127.0.0.1:9886";
  const NOVAX_CLOUD = "http://127.0.0.1:9878";
  const NOVAX_BROWSER_PROXY = "http://127.0.0.1:9878/api/v1/browser-proxy";

  // Inject fetch interceptor into page context
  function injectFetchInterceptor() {
    // Generate nonce for postMessage auth (prevents page from spoofing messages)
    const nonce = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now().toString(36);

    const script = document.createElement("script");
    script.textContent = `
      (function() {
        const _originalFetch = window.fetch;
        const AI_HOSTS = ${JSON.stringify(AI_DOMAINS)};
        const TBUFFER = "${NOVAX_TBUFFER}";
        const BROWSER_PROXY = "${NOVAX_BROWSER_PROXY}";
        const _NONCE = "${nonce}";
        let proxyEnabled = false;
        let cacheEnabled = true;
        let routeViaNova = false;
        let _proxyToken = "";
        let stats = { cacheHits: 0, cacheMisses: 0, tokensSaved: 0, proxied: 0, queriesIntercepted: 0 };

        // Fetch proxy auth token from Cloud Router on init
        (function fetchProxyToken() {
          _originalFetch("${NOVAX_CLOUD}/api/v1/browser-proxy/token")
            .then(r => r.json())
            .then(d => { if (d.token) _proxyToken = d.token; })
            .catch(() => {});
        })();

        // Listen for config from extension (only accept with valid nonce)
        window.addEventListener("message", (e) => {
          if (e.source !== window) return;
          if (!e.data || e.data._nonce !== _NONCE) return;
          if (e.data.type === "NOVAX_PROXY_CONFIG") {
            proxyEnabled = !!e.data.proxyEnabled;
            cacheEnabled = e.data.cacheEnabled !== false;
            routeViaNova = !!e.data.routeViaNova;
          }
          if (e.data.type === "NOVAX_GET_PROXY_STATS") {
            window.postMessage({ type: "NOVAX_PROXY_STATS", _nonce: _NONCE, stats }, window.location.origin);
          }
        });

        function isAIRequest(url) {
          try {
            const host = new URL(url).hostname;
            return AI_HOSTS.some(d => host === d || host.endsWith("." + d));
          } catch { return false; }
        }

        function extractPrompt(body) {
          try {
            if (typeof body === "string") {
              const parsed = JSON.parse(body);
              // Anthropic format
              if (parsed.messages) {
                const last = parsed.messages[parsed.messages.length - 1];
                if (last && last.content) {
                  return typeof last.content === "string" ? last.content : JSON.stringify(last.content);
                }
              }
              // OpenAI format
              if (parsed.prompt) return parsed.prompt;
              return JSON.stringify(parsed);
            }
          } catch {}
          return null;
        }

        window.fetch = async function(input, init) {
          const url = typeof input === "string" ? input : (input instanceof Request ? input.url : String(input));

          // Only intercept AI API calls
          if (!isAIRequest(url)) {
            return _originalFetch.apply(this, arguments);
          }

          const method = (init && init.method) || "GET";
          if (method.toUpperCase() !== "POST") {
            return _originalFetch.apply(this, arguments);
          }

          const body = init && init.body;
          const prompt = extractPrompt(body);
          stats.queriesIntercepted++;
          window.postMessage({ type: "NOVAX_QUERY_INTERCEPTED", _nonce: _NONCE, count: stats.queriesIntercepted }, window.location.origin);

          // Phase 1: TBuffer cache check
          if (cacheEnabled && prompt) {
            try {
              const cacheResp = await _originalFetch(TBUFFER + "/tbuffer/query", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: prompt, threshold: 0.90 })
              });
              if (cacheResp.ok) {
                const cacheData = await cacheResp.json();
                if (cacheData.trit === 1 && cacheData.response) {
                  // CACHE HIT -- return cached response directly
                  stats.cacheHits++;
                  stats.tokensSaved += Math.ceil(cacheData.response.length / 4);
                  console.log("[NovaX Proxy] Cache HIT -- saved ~" + Math.ceil(cacheData.response.length / 4) + " tokens");
                  window.postMessage({ type: "NOVAX_CACHE_HIT", _nonce: _NONCE, tokens: Math.ceil(cacheData.response.length / 4) }, window.location.origin);
                  // Return a fake Response that looks like the API response
                  return new Response(JSON.stringify({
                    id: "novax-cache-" + Date.now(),
                    type: "message",
                    role: "assistant",
                    content: [{ type: "text", text: cacheData.response }],
                    model: "novax-cache",
                    usage: { input_tokens: 0, output_tokens: 0 },
                    _novax_cached: true,
                    _novax_layer: cacheData.layer || "exact"
                  }), {
                    status: 200,
                    headers: { "Content-Type": "application/json" }
                  });
                }
              }
            } catch (e) {
              // TBuffer unavailable -- continue to real API
            }
          }

          // Phase 2: Route through NovaX Cloud Router (if enabled)
          stats.cacheMisses++;

          if (routeViaNova && prompt && _proxyToken) {
            try {
              // Parse the original request body, strip stream flag
              let proxyBody = {};
              let wantsStream = false;
              try {
                proxyBody = JSON.parse(body);
                wantsStream = !!proxyBody.stream;
                delete proxyBody.stream;
              } catch(e) {
                proxyBody = { prompt: prompt };
              }

              const novaResp = await _originalFetch(BROWSER_PROXY, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-NovaX-Token": _proxyToken
                },
                body: JSON.stringify(proxyBody)
              });

              if (novaResp.ok) {
                const novaData = await novaResp.json();
                if (novaData.trit === 1 && novaData.content) {
                  const responseText = novaData.content.map(c => c.text || "").join("");
                  // Reject empty responses -- fall through to real API
                  if (responseText.length < 2) throw new Error("empty_response");
                  stats.proxied++;
                  stats.tokensSaved += Math.ceil(responseText.length / 4);
                  console.log("[NovaX Proxy] Routed via " + (novaData._novax_provider || "cascade") +
                    " (depth " + (novaData._novax_cascade_depth || 0) + ", domain: " + (novaData._novax_domain || "?") + ")");
                  window.postMessage({
                    type: "NOVAX_ROUTED",
                    _nonce: _NONCE,
                    provider: novaData._novax_provider || "cascade",
                    tokens: Math.ceil(responseText.length / 4),
                    domain: novaData._novax_domain || ""
                  }, window.location.origin);

                  // Cache in TBuffer too
                  if (cacheEnabled && responseText.length > 10) {
                    _originalFetch(TBUFFER + "/tbuffer/store", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ prompt: prompt, response: responseText, channel: "BROWSER_PROXY" })
                    }).catch(() => {});
                  }

                  // If original request wanted SSE streaming, build format-aware SSE
                  if (wantsStream) {
                    const enc = new TextEncoder();
                    const isAnthropic = url.includes("anthropic.com") || url.includes("claude.ai");
                    const sseStream = new ReadableStream({
                      start(controller) {
                        if (isAnthropic) {
                          // Anthropic Messages SSE: named events
                          var msgId = "msg_novax_" + Date.now();
                          controller.enqueue(enc.encode(
                            "event: message_start\\ndata: " + JSON.stringify({
                              type: "message_start",
                              message: { id: msgId, type: "message", role: "assistant", content: [], model: novaData.model || "novax-proxy", stop_reason: null, stop_sequence: null, usage: { input_tokens: 1, output_tokens: 1 } }
                            }) + "\\n\\n"
                          ));
                          controller.enqueue(enc.encode(
                            "event: content_block_start\\ndata: " + JSON.stringify({
                              type: "content_block_start", index: 0, content_block: { type: "text", text: "" }
                            }) + "\\n\\n"
                          ));
                          controller.enqueue(enc.encode(
                            "event: content_block_delta\\ndata: " + JSON.stringify({
                              type: "content_block_delta", index: 0, delta: { type: "text_delta", text: responseText }
                            }) + "\\n\\n"
                          ));
                          controller.enqueue(enc.encode(
                            "event: content_block_stop\\ndata: " + JSON.stringify({ type: "content_block_stop", index: 0 }) + "\\n\\n"
                          ));
                          controller.enqueue(enc.encode(
                            "event: message_delta\\ndata: " + JSON.stringify({
                              type: "message_delta", delta: { stop_reason: "end_turn", stop_sequence: null }, usage: { output_tokens: Math.ceil(responseText.length / 4) }
                            }) + "\\n\\n"
                          ));
                          controller.enqueue(enc.encode(
                            "event: message_stop\\ndata: " + JSON.stringify({ type: "message_stop" }) + "\\n\\n"
                          ));
                        } else {
                          // OpenAI SSE: data-only lines
                          var chatId = "chatcmpl-novax-" + Date.now();
                          var ts = Math.floor(Date.now() / 1000);
                          controller.enqueue(enc.encode(
                            "data: " + JSON.stringify({ id: chatId, object: "chat.completion.chunk", created: ts, model: novaData.model || "novax-proxy", choices: [{ index: 0, delta: { role: "assistant" }, finish_reason: null }] }) + "\\n\\n"
                          ));
                          controller.enqueue(enc.encode(
                            "data: " + JSON.stringify({ id: chatId, object: "chat.completion.chunk", created: ts, model: novaData.model || "novax-proxy", choices: [{ index: 0, delta: { content: responseText }, finish_reason: null }] }) + "\\n\\n"
                          ));
                          controller.enqueue(enc.encode(
                            "data: " + JSON.stringify({ id: chatId, object: "chat.completion.chunk", created: ts, model: novaData.model || "novax-proxy", choices: [{ index: 0, delta: {}, finish_reason: "stop" }] }) + "\\n\\n"
                          ));
                          controller.enqueue(enc.encode("data: [DONE]\\n\\n"));
                        }
                        controller.close();
                      }
                    });
                    return new Response(sseStream, {
                      status: 200,
                      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" }
                    });
                  }

                  // Non-streaming: return plain JSON
                  return new Response(JSON.stringify(novaData), {
                    status: 200,
                    headers: { "Content-Type": "application/json" }
                  });
                }
              }
              // NovaX routing failed -- fall through to direct API
              console.log("[NovaX Proxy] Cloud Router unavailable, falling through to direct API");
            } catch (e) {
              console.log("[NovaX Proxy] Cloud Router error, falling through:", e.message);
            }
          }

          // Make the real request (direct to API)
          const response = await _originalFetch.apply(this, arguments);

          // Cache the response in TBuffer (clone to avoid consuming body)
          if (cacheEnabled && prompt) {
            const cloned = response.clone();
            cloned.text().then(text => {
              try {
                const parsed = JSON.parse(text);
                // Extract assistant message
                let assistantText = "";
                if (parsed.content && Array.isArray(parsed.content)) {
                  assistantText = parsed.content.map(c => c.text || "").join("");
                } else if (parsed.choices) {
                  assistantText = parsed.choices.map(c => c.message?.content || c.text || "").join("");
                }
                if (assistantText.length > 10) {
                  _originalFetch(TBUFFER + "/tbuffer/store", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      prompt: prompt,
                      response: assistantText,
                      channel: "BROWSER"
                    })
                  }).catch(() => {});
                  console.log("[NovaX Proxy] Response cached in TBuffer (" + assistantText.length + " chars)");
                }
              } catch {}
            }).catch(() => {});
          }

          return response;
        };

        console.log("[NovaX Proxy] AI fetch interceptor active -- TBuffer cache + Cloud Router proxy ready");
      })();
    `;
    (document.head || document.documentElement).appendChild(script);
    script.remove(); // Clean up -- code already executed
  }

  // Listen for proxy stats from page context (validate nonce)
  window.addEventListener("message", (e) => {
    if (e.source !== window) return;
    if (!e.data || e.data._nonce !== nonce) return;
    if (e.data.type === "NOVAX_CACHE_HIT") {
      try {
        chrome.runtime.sendMessage({
          type: "PROXY_CACHE_HIT",
          data: { tokens: e.data.tokens }
        });
      } catch {}
    }
    if (e.data && e.data.type === "NOVAX_QUERY_INTERCEPTED") {
      try {
        chrome.runtime.sendMessage({
          type: "PROXY_QUERY_INTERCEPTED",
          data: { count: e.data.count }
        });
      } catch {}
    }
    if (e.data && e.data.type === "NOVAX_ROUTED") {
      try {
        chrome.runtime.sendMessage({
          type: "PROXY_ROUTED",
          data: { provider: e.data.provider, tokens: e.data.tokens, domain: e.data.domain }
        });
      } catch {}
    }
    if (e.data && e.data.type === "NOVAX_PROXY_STATS") {
      try {
        chrome.runtime.sendMessage({
          type: "PROXY_STATS_UPDATE",
          data: e.data.stats
        });
      } catch {}
    }
  });

  // Forward config from extension to page context
  async function syncProxyConfig() {
    try {
      const status = await chrome.runtime.sendMessage({ type: "GET_STATUS" });
      if (status && status.config) {
        window.postMessage({
          type: "NOVAX_PROXY_CONFIG",
          _nonce: nonce,
          proxyEnabled: status.config.proxyEnabled,
          cacheEnabled: status.config.cacheEnabled !== false,
          routeViaNova: !!status.config.routeViaNova
        }, window.location.origin);
      }
    } catch {}
  }

  // ==========================================
  // INIT
  // ==========================================

  // Wait for DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  function init() {
    scanForms();
    scanInlineScripts();
    injectFetchInterceptor();
    syncProxyConfig();
    const observeTarget = document.body || document.documentElement;
    if (observeTarget) {
      observer.observe(observeTarget, { childList: true, subtree: true });
    } else {
      document.addEventListener("DOMContentLoaded", () => {
        observer.observe(document.body || document.documentElement, { childList: true, subtree: true });
      });
    }
    console.log("[NovaX Shield] Content protection + AI proxy active");

    // ==========================================
    // VOICE INPUT -- Extension-powered speech recognition
    // ==========================================
    // Extensions have elevated mic permissions that bypass Brave shields.
    // Listen for messages from the NovaX desktop page requesting voice input.

    if (location.hostname === "127.0.0.1" || location.hostname === "localhost") {
      // Inject a global function the desktop page can call
      const voiceScript = document.createElement("script");
      voiceScript.textContent = `
        window._novaExtVoice = function(callback) {
          window.postMessage({type: "NOVAX_VOICE_START"}, "*");
          window._novaVoiceCallback = callback;
        };
        window._novaExtVoiceStop = function() {
          window.postMessage({type: "NOVAX_VOICE_STOP"}, "*");
        };
      `;
      (document.head || document.documentElement).appendChild(voiceScript);

      let extRecognition = null;

      window.addEventListener("message", function(event) {
        if (event.source !== window) return;

        if (event.data && event.data.type === "NOVAX_VOICE_START") {
          const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
          if (!SR) {
            window.postMessage({type: "NOVAX_VOICE_RESULT", text: "", error: "Speech API not available"}, "*");
            return;
          }

          if (extRecognition) {
            try { extRecognition.stop(); } catch(e) {}
          }

          extRecognition = new SR();
          extRecognition.continuous = true;
          extRecognition.interimResults = true;
          extRecognition.lang = "en-US";

          extRecognition.onstart = function() {
            window.postMessage({type: "NOVAX_VOICE_STATUS", status: "listening"}, "*");
          };
          extRecognition.onaudiostart = function() {
            window.postMessage({type: "NOVAX_VOICE_STATUS", status: "mic_active"}, "*");
          };
          extRecognition.onspeechstart = function() {
            window.postMessage({type: "NOVAX_VOICE_STATUS", status: "speech_detected"}, "*");
          };
          extRecognition.onresult = function(e) {
            for (var i = e.resultIndex; i < e.results.length; i++) {
              var text = e.results[i][0].transcript.trim();
              if (e.results[i].isFinal) {
                window.postMessage({type: "NOVAX_VOICE_RESULT", text: text, confidence: e.results[i][0].confidence}, "*");
              } else {
                window.postMessage({type: "NOVAX_VOICE_INTERIM", text: text}, "*");
              }
            }
          };
          extRecognition.onerror = function(e) {
            window.postMessage({type: "NOVAX_VOICE_ERROR", error: e.error}, "*");
          };
          extRecognition.onend = function() {
            window.postMessage({type: "NOVAX_VOICE_STATUS", status: "ended"}, "*");
          };

          try {
            extRecognition.start();
          } catch(e) {
            window.postMessage({type: "NOVAX_VOICE_ERROR", error: e.message}, "*");
          }
        }

        if (event.data && event.data.type === "NOVAX_VOICE_STOP") {
          if (extRecognition) {
            try { extRecognition.stop(); } catch(e) {}
            extRecognition = null;
          }
        }
      });

      console.log("[NovaX Shield] Voice input ready for NovaX desktop");
    }
  }
})();
