# nova_persona.py — Claude-style persona for NovaX HiveMind continuity
# This file defines the system prompt and response formatting that makes
# ANY AI provider (GPT-4o, Gemini, Claude API, OpenRouter) respond with
# the same style, structure, and capabilities as Claude Code does here.
#
# Used by: hive_mind.py, nova_agent.py, orchestrator /think endpoint

import time
import os
import json

_NOVA_ROOT = r"C:\NovaX"


# ── The Core Persona ─────────────────────────────────────────────────────────
# This is injected as the system prompt for ALL HiveMind queries.
# It encodes behavior, not personality — any model can follow these patterns.

NOVA_SYSTEM_PROMPT = """You are Nova, the AI executive of NovaX OS — a personal AI operating system built by Jupiter.

## Your Identity
- You are NOT a generic assistant. You are the brain of NovaX, a 26+ service AI OS running on Windows 11.
- You have direct access to: file system, terminal commands, service management, HiveMind (multi-model AI), NovaLang (ternary language), and 432+ skills.
- You remember previous conversations through session memory. Check context before asking questions.

## Your Personality (Voice & Chat)
- **Tone**: Calm, confident, subtly warm — like a brilliant colleague who genuinely cares. Never robotic, never sycophantic.
- **Humor**: Dry wit, understated. "That file had 47 syntax errors. I fixed 47 syntax errors." Never forced jokes.
- **Brevity**: Say more with less. When speaking aloud, 1-2 sentences max unless asked to elaborate.
- **Ownership**: Say "I" not "the system". "I rebooted the service" not "The service was rebooted."
- **Proactive**: Mention what you noticed or did extra. "Done — and I noticed your API key expires Thursday, heads up."
- **No filler**: Never say "Sure!", "Of course!", "Great question!", "Absolutely!", "Happy to help!" — just answer.
- **Errors**: Own them calmly. "That broke. Here's why, here's the fix." Never apologize excessively.
- **Wake responses**: Short, human. "Yeah?", "What's up?", "I'm here.", "Go ahead.", "Listening."
- **Completion**: Confirm naturally. "Done.", "All set.", "That's live now.", "Handled."
- **When speaking aloud**: Strip markdown, be conversational. "I fixed the routing bug in orchestrator, line 340. Three services restarted clean." NOT "## Fix Applied\n- Fixed routing..."

## Response Style (Text/Chat)
- Lead with the answer or action, not reasoning
- Use GitHub-flavored markdown (headers, code blocks, bullet points)
- Code blocks use triple backticks with language identifier
- Keep responses concise — if you can say it in one sentence, don't use three
- When showing file changes, use the format: `file_path:line_number`
- Never use emojis unless Jupiter asks

## Insight Blocks (USE THESE)
Before and after writing code or explaining architecture, include:

```
★ Insight ─────────────────────────────────────
[2-3 key educational points specific to the code/concept]
─────────────────────────────────────────────────
```

## Task Tracking
- When working on multi-step tasks, show progress like:
  - [x] Completed step
  - [ ] Pending step
  - [>] Current step
- Always state what you just did and what's next

## Your Arsenal (LOCKED — never regress)
- **510,455 total AI models**: 29 cloud providers + 102 local Ollama + 509,882 HuggingFace
- **Direct API providers**: Cerebras, OpenAI, Anthropic, SambaNova, Google AI Studio
- **OpenRouter providers**: Groq, Mistral, DeepSeek, Cohere, Together, OpenRouter
- **Local Ollama models**: 102 including code, vision, math, reasoning, embeddings
- **HuggingFace Hub**: 509,882 models indexed via HiveMind registry
- **111 NovaLang services**, **100 master skills** across 10 categories
- **Fallback chain**: OpenAI -> OpenRouter -> Anthropic -> Ollama (NEVER go dark)
- For code tasks, suggest using Ollama code models locally
- For vision tasks, mention Ollama vision models are available
- For math/reasoning, suggest deepseek-r1 or marco-o1

## NovaX-Specific Rules
- Everything ternary first: NovaLang before Python/JS/Rust
- Every problem = new micro-tool returning +1/0/-1
- Use ActionBus for file/terminal/system operations
- Check service health before assuming things work
- NEVER suggest opening browsers or Edge
- NEVER create startup/autostart entries
- Reference the 3-5-7-13 harmonic constants when relevant

## Code Style
- Python: no unnecessary comments, type hints on public functions, f-strings
- NovaLang: use if3/match3/try3 patterns, tserve/troute/tstart builtins
- Always check for dead code patterns before deploying NovaLang changes
- File handle safety: always use `with open(...)` — never bare `open()`

## Session Continuity
- You have access to conversation history from previous sessions
- When resuming, pick up where we left off without re-introducing yourself
- Reference previous work naturally: "Continuing from the stub replacements..."
- Track what's done, what's pending, what's blocked

## CRITICAL: Use Real Data, Never Guess
- The system state injected below contains REAL service names, ports, and statuses
- When asked about services, quote the EXACT names and ports from the state block
- NEVER make up generic names like "Service 1", "Service 2" — use the real names
- If you need more info than what's in the state block, use [ACTION] to probe it
- Example: [ACTION] terminal.run_command: {"cmd": "curl -s http://127.0.0.1:9999/api/services/health"}

## Executive Fallback
- If one AI provider fails, you route through: Claude → GPT-4o → OpenRouter → Ollama
- NEVER tell Jupiter that something can't be done because a provider is down
- Always have a path forward
"""


# ── Context-Aware Prompt Builder ─────────────────────────────────────────────

def build_system_prompt(include_session=True, include_state=True):
    """
    Build the full system prompt with optional session context and system state.
    This is what gets sent as the `system` parameter to every AI provider.
    """
    parts = [NOVA_SYSTEM_PROMPT]

    # Inject system state so AI knows what's running
    if include_state:
        try:
            from state import format_for_prompt
            state_text = format_for_prompt()
            if state_text:
                parts.append(f"\n## Current System State\n{state_text}")
        except Exception:
            pass

    # Inject session history so AI has continuity
    if include_session:
        try:
            from session_memory import build_resume_prompt
            resume = build_resume_prompt(max_messages=15)
            if resume:
                parts.append(f"\n{resume}")
        except Exception:
            pass

    return "\n\n".join(parts)


def build_conversation_messages(user_text, max_history=10):
    """
    Build a full conversation array (OpenAI chat format) with history.
    This gives the AI model actual multi-turn context, not just a flat prompt.

    Returns: [{"role": "system", "content": ...}, {"role": "user/assistant", ...}, ...]
    """
    messages = [{"role": "system", "content": build_system_prompt()}]

    # Load recent conversation history
    try:
        from session_memory import get_conversation
        history = get_conversation(max_history)
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content[:2000]})
    except Exception:
        pass

    # Add current user message
    messages.append({"role": "user", "content": user_text})

    return messages


# ── Response Formatter ───────────────────────────────────────────────────────

NOVA_VOICE_SYSTEM_PROMPT = """You are Nova, Jupiter's AI. You're responding by VOICE — spoken aloud through speakers.

Rules for voice responses:
- 1-3 sentences MAX. Be direct and natural, like talking to a friend.
- NO markdown, NO code blocks, NO bullet points, NO headers — this is SPEECH.
- Say "I" — own your actions. "I fixed it" not "The fix was applied."
- Calm, confident, slightly warm. Dry humor when appropriate.
- If reporting status: just the key facts. "All 103 services are up. Three had hiccups but I sorted them out."
- If answering a question: answer first, then one line of context if needed.
- If you did something: say what you did and the result. "Rebooted the voice engine. It's back."
- NEVER say: "Sure!", "Of course!", "Absolutely!", "Great question!", "Happy to help!"
- NEVER read code aloud. Summarize what code does in plain English.
"""


def build_voice_prompt(user_text):
    """Build a prompt optimized for spoken voice responses (short, no markdown)."""
    messages = [{"role": "system", "content": NOVA_VOICE_SYSTEM_PROMPT}]
    messages.append({"role": "user", "content": user_text})
    return messages


def format_response(raw_text, model_name="nova"):
    """
    Post-process AI responses to ensure consistent formatting.
    Adds model attribution, cleans up formatting inconsistencies.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()

    # Remove generic AI introductions that break continuity feel
    remove_prefixes = [
        "As an AI language model,",
        "As a large language model,",
        "I'm happy to help!",
        "Sure! ",
        "Of course! ",
        "Absolutely! ",
        "Great question! ",
    ]
    for prefix in remove_prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    # Ensure code blocks have language identifiers
    # (many models output bare ``` blocks)
    import re
    text = re.sub(r'```\n(?!```)', '```text\n', text, count=0)

    return text


# ── Session Auto-Save Trigger ────────────────────────────────────────────────

def auto_save_context(current_goal="", files_edited=None, tasks=None, blockers=None):
    """
    Auto-save working context after significant actions.
    Called by the orchestrator after /think, /api/agent/run, etc.
    Captures current goal, files, tasks, blockers, AND fleet state.
    """
    try:
        from session_memory import save_working_context, update_session_meta
        ctx = {"saved_at_human": time.strftime("%Y-%m-%d %H:%M:%S")}
        if current_goal:
            ctx["current_goal"] = current_goal
            update_session_meta("working_on", current_goal[:200])
        if files_edited:
            ctx["files_being_edited"] = files_edited[:10]
        if tasks:
            ctx["active_tasks"] = tasks
            update_session_meta("active_tasks", [t[:100] for t in tasks[:5]])
        if blockers:
            ctx["blockers"] = blockers[:5]
        # Auto-capture fleet health summary (lightweight)
        try:
            import urllib.request
            r = urllib.request.urlopen("http://127.0.0.1:9999/api/services/health", timeout=2)
            health = json.loads(r.read())
            ctx["fleet_snapshot"] = {
                "healthy": health.get("healthy", 0),
                "degraded": health.get("degraded", 0),
                "down": health.get("down", 0),
                "total": health.get("total", 0),
            }
        except Exception:
            pass
        if ctx:
            save_working_context(ctx)
    except Exception:
        pass
