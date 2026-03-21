// ===================================================================
// NovaX Proxy Module -- Route AI output through NovaX ternary layer
// ===================================================================
// Instead of Claude Desktop consuming tokens to render output,
// this module intercepts AI responses and routes them through
// NovaX's ternary processing pipeline for display.
//
// Architecture:
//   Claude API -> Response Stream -> NovaX Proxy -> Ternary Process -> Display
//   (tokens saved: Claude never re-processes for rendering)
// ===================================================================

const NOVAX_ENDPOINT = "http://127.0.0.1:9999";

// -- Ternary result codes --
const TRIT = { PLUS: 1, ZERO: 0, MINUS: -1 };

class NovaProxy {
  constructor() {
    this.enabled = true;
    this.interceptedStreams = new Map();
    this.stats = {
      totalIntercepted: 0,
      totalProcessed: 0,
      tokensSaved: 0,
      bytesRouted: 0
    };
    this.streamBuffer = new Map();
  }

  // -- Check if NovaX orchestrator is alive --
  async ping() {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 3000);
      const resp = await fetch(`${NOVAX_ENDPOINT}/health`, {
        method: "GET",
        signal: controller.signal
      });
      clearTimeout(timer);
      if (resp.ok) return TRIT.PLUS;
      return TRIT.ZERO;
    } catch {
      return TRIT.MINUS;
    }
  }

  // -- Route content through NovaX for ternary processing --
  async routeThroughNova(content, metadata = {}) {
    try {
      const resp = await fetch(`${NOVAX_ENDPOINT}/api/proxy/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: content,
          source: metadata.source || "brave_extension",
          type: metadata.type || "ai_output",
          timestamp: Date.now(),
          ternary_mode: true
        }),
        signal: AbortSignal.timeout(10000)
      });
      if (resp.ok) {
        const result = await resp.json();
        this.stats.totalProcessed++;
        this.stats.bytesRouted += content.length;
        return { trit: TRIT.PLUS, data: result };
      }
      return { trit: TRIT.ZERO, data: { raw: content } };
    } catch {
      // Fallback: pass through unprocessed
      return { trit: TRIT.MINUS, data: { raw: content } };
    }
  }

  // -- Intercept AI API response streams --
  // Detects Claude/OpenAI/Anthropic API calls and captures responses
  interceptStream(requestId, url, responseBody) {
    const isAI = this._isAIEndpoint(url);
    if (!isAI) return null;

    this.stats.totalIntercepted++;

    // Buffer the stream chunks
    if (!this.streamBuffer.has(requestId)) {
      this.streamBuffer.set(requestId, {
        url: url,
        chunks: [],
        startTime: Date.now(),
        provider: isAI
      });
    }

    const buffer = this.streamBuffer.get(requestId);
    buffer.chunks.push(responseBody);

    return {
      trit: TRIT.PLUS,
      provider: isAI,
      buffered: buffer.chunks.length
    };
  }

  // -- Finalize a stream and route through NovaX --
  async finalizeStream(requestId) {
    const buffer = this.streamBuffer.get(requestId);
    if (!buffer) return { trit: TRIT.MINUS };

    const fullContent = buffer.chunks.join("");
    this.streamBuffer.delete(requestId);

    // Estimate tokens saved (rough: 4 chars per token)
    const estimatedTokens = Math.ceil(fullContent.length / 4);
    this.stats.tokensSaved += estimatedTokens;

    // Route through NovaX for ternary processing
    const result = await this.routeThroughNova(fullContent, {
      source: buffer.provider,
      type: "ai_stream_complete"
    });

    return {
      trit: result.trit,
      content: fullContent,
      processed: result.data,
      tokensSaved: estimatedTokens,
      duration: Date.now() - buffer.startTime
    };
  }

  // -- Detect AI API endpoints --
  _isAIEndpoint(url) {
    const patterns = [
      { match: "api.anthropic.com", provider: "anthropic" },
      { match: "api.openai.com", provider: "openai" },
      { match: "openrouter.ai/api", provider: "openrouter" },
      { match: "claude.ai/api", provider: "claude_web" },
      { match: "chat.openai.com/backend-api", provider: "chatgpt_web" },
      { match: "generativelanguage.googleapis.com", provider: "gemini" },
      { match: "api-inference.huggingface.co", provider: "huggingface" }
    ];
    for (const p of patterns) {
      if (url.includes(p.match)) return p.provider;
    }
    return null;
  }

  // -- Get proxy statistics --
  getStats() {
    return {
      ...this.stats,
      activeStreams: this.streamBuffer.size,
      enabled: this.enabled,
      trit: this.stats.totalProcessed > 0 ? TRIT.PLUS : TRIT.ZERO
    };
  }

  // -- Reset stats --
  resetStats() {
    this.stats = {
      totalIntercepted: 0,
      totalProcessed: 0,
      tokensSaved: 0,
      bytesRouted: 0
    };
  }
}

// Export singleton
const novaProxy = new NovaProxy();
export { novaProxy, NovaProxy, TRIT, NOVAX_ENDPOINT };
