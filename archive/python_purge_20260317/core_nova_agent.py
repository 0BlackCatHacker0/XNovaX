# nova_agent.py — Nova Agent Loop: think -> plan -> act -> respond
# Uses HiveMind for AI reasoning, ActionBus for executing actions,
# and nova_persona for Claude-style continuity across sessions.
# Orchestrator calls agent_loop(text) expecting {"ok": bool, "reply": str, ...}

import time
import json
import re


def agent_loop(task=None, context=None, max_steps=10, **kwargs):
    """
    Run the Nova agent loop on a task.
    1. Load session context + persona (so AI knows what we've been doing)
    2. Ask HiveMind to reason about the task
    3. Extract any actions (terminal commands, file operations)
    4. Execute actions via ActionBus
    5. Save results to session memory
    6. Return combined result

    Returns: {"ok": bool, "reply": str, "actions": list, "iterations": int}
    """
    if not task:
        return {"ok": False, "reply": "", "actions": [], "iterations": 0}

    try:
        from hive_mind import hive
        from drivers import bus
    except ImportError:
        return {"ok": False, "reply": "", "actions": [], "iterations": 0,
                "error": "Agent dependencies not available"}

    # Load persona system prompt (includes session history + system state)
    system_prompt = None
    try:
        from nova_persona import build_system_prompt
        system_prompt = build_system_prompt(include_session=True, include_state=True)
    except Exception:
        system_prompt = "You are Nova, the AI executive of NovaX OS."

    actions_taken = []
    iterations = 0
    accumulated_context = f"User request: {task}\n"

    for step in range(max_steps):
        iterations += 1

        agent_prompt = _build_agent_prompt(task, accumulated_context, actions_taken)

        try:
            hive_result = hive.fan_out(
                agent_prompt,
                max_models=2,
                timeout=20,
                system=system_prompt,
            )
            if not hive_result or not hive_result.get("consensus"):
                break
            ai_text = hive_result["consensus"]
        except Exception:
            break

        # Check if AI wants to execute a command
        action = _extract_action(ai_text)
        if action:
            try:
                result = bus.execute(
                    action["driver"],
                    action["action"],
                    action["params"]
                )
                action_record = {
                    "step": step + 1,
                    "driver": action["driver"],
                    "action": action["action"],
                    "ok": result.ok,
                    "output": result.output[:500],
                }
                actions_taken.append(action_record)
                accumulated_context += (
                    f"\nStep {step+1}: Executed {action['driver']}.{action['action']}\n"
                    f"Result: {'OK' if result.ok else 'FAIL'} -- {result.output[:300]}\n"
                )
            except Exception as e:
                accumulated_context += f"\nStep {step+1}: Action failed -- {e}\n"
        else:
            # No action extracted -- this is the final answer
            # Format through persona for consistent style
            reply = ai_text
            try:
                from nova_persona import format_response
                reply = format_response(ai_text)
            except Exception:
                pass

            # Auto-save context
            _auto_save(task, actions_taken)

            return {
                "ok": True,
                "reply": reply,
                "actions": actions_taken,
                "iterations": iterations,
            }

    # Exhausted max steps -- ask for summary
    try:
        summary_prompt = (
            f"You completed {iterations} steps for: {task}\n"
            f"Actions taken: {json.dumps(actions_taken, default=str)[:1000]}\n"
            "Give a concise final answer to the user."
        )
        hive_result = hive.fan_out(summary_prompt, max_models=1, timeout=15,
                                    system=system_prompt)
        reply = hive_result.get("consensus", "") if hive_result else ""
        if reply:
            try:
                from nova_persona import format_response
                reply = format_response(reply)
            except Exception:
                pass
    except Exception:
        reply = f"Completed {iterations} steps with {len(actions_taken)} actions."

    _auto_save(task, actions_taken)

    return {
        "ok": bool(reply),
        "reply": reply,
        "actions": actions_taken,
        "iterations": iterations,
    }


def _build_agent_prompt(task, context, actions):
    """Build the prompt for the agent's next reasoning step."""
    parts = [
        "You are Nova, the AI agent inside NovaX OS.",
        "You can execute terminal commands and file operations.",
        "If you need to run a command, respond with: [ACTION] driver.action: params",
        "Example: [ACTION] terminal.run_command: {\"cmd\": \"dir C:\\\\NovaX\"}",
        "Example: [ACTION] file.read_file: {\"path\": \"C:\\\\NovaX\\\\README.md\"}",
        "If you have the answer, just respond normally (no [ACTION] tag).",
        "",
        "FORMAT YOUR RESPONSE with markdown. Use code blocks with language tags.",
        "Use insight blocks when explaining architecture:",
        "```",
        "★ Insight ─────────────────────────────────────",
        "[key points]",
        "─────────────────────────────────────────────────",
        "```",
        "",
        context,
    ]
    if actions:
        parts.append(f"Actions completed so far: {len(actions)}")
    return "\n".join(parts)


def _extract_action(text):
    """Extract an [ACTION] directive from AI response, if any."""
    # Pattern: [ACTION] driver.action: {json_params}
    match = re.search(
        r'\[ACTION\]\s*(\w+)\.(\w+)\s*:\s*(\{[^}]+\})',
        text
    )
    if match:
        driver = match.group(1)
        action = match.group(2)
        try:
            params = json.loads(match.group(3))
        except json.JSONDecodeError:
            params = {}
        return {"driver": driver, "action": action, "params": params}

    # Simpler pattern: [ACTION] driver.action: single_value
    match = re.search(r'\[ACTION\]\s*(\w+)\.(\w+)\s*:\s*(.+)', text)
    if match:
        driver = match.group(1)
        action = match.group(2)
        value = match.group(3).strip()
        param_map = {
            "run_command": "cmd",
            "run_python": "code",
            "read_file": "path",
            "write_file": "path",
            "list_dir": "path",
        }
        key = param_map.get(action, "value")
        return {"driver": driver, "action": action, "params": {key: value}}

    return None


def _auto_save(task, actions):
    """Save session context after agent completes."""
    try:
        from nova_persona import auto_save_context
        auto_save_context(
            current_goal=task[:200] if task else "",
            tasks=[task[:100]] if task else [],
        )
    except Exception:
        pass

    try:
        from session_memory import record_action
        record_action(
            action="agent_loop",
            task=task[:200] if task else "",
            actions_count=len(actions),
            success=bool(actions),
        )
    except Exception:
        pass
