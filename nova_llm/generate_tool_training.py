"""
NovaX Tool-Use Training Data Generator
Generates ReAct-format training pairs that teach the model to:
1. Decide WHEN to use a tool vs answer directly
2. Pick the RIGHT tool
3. Format the tool call correctly
4. Synthesize tool output into a final answer
"""
import json, random
from pathlib import Path

OUTPUT_FILE = Path("C:/NovaX/data/llm_training/tool_training_pairs.json")

# ── Tool Definitions ────────────────────────────────────────────
TOOLS = {
    "calculator": "Evaluate a mathematical expression and return the result.",
    "search": "Search a knowledge base for factual information.",
    "code_exec": "Execute Python code and return the output.",
    "file_read": "Read the contents of a local file.",
    "web_search": "Search the web for current information.",
    "model_query": "Send a query to a specialized AI model for complex reasoning.",
}

# ── Training Examples ───────────────────────────────────────────
def generate_tool_use_examples():
    """Generate diverse tool-use training pairs."""
    pairs = []

    # === CATEGORY 1: Calculator tool calls ===
    calc_examples = [
        {
            "prompt": "What is 1547 * 382?",
            "response": """<THOUGHT>This is a multiplication that I should compute precisely rather than estimate.</THOUGHT>
<ACTION><tool_call>{"name": "calculator", "args": {"expression": "1547 * 382"}}</tool_call></ACTION>
<OBSERVATION>590854</OBSERVATION>
The answer is 590,854.""",
        },
        {
            "prompt": "If I invest $10,000 at 7% annual interest compounded monthly, how much will I have after 5 years?",
            "response": """<THOUGHT>This requires the compound interest formula: A = P(1 + r/n)^(nt). Let me calculate it precisely.</THOUGHT>
<ACTION><tool_call>{"name": "calculator", "args": {"expression": "10000 * (1 + 0.07/12) ** (12*5)"}}</tool_call></ACTION>
<OBSERVATION>14176.25</OBSERVATION>
After 5 years of investing $10,000 at 7% annual interest compounded monthly, you would have approximately $14,176.25.""",
        },
        {
            "prompt": "What's the area of a circle with radius 13.7?",
            "response": """<THOUGHT>Area of a circle is pi * r^2. Let me compute this precisely.</THOUGHT>
<ACTION><tool_call>{"name": "calculator", "args": {"expression": "3.14159265359 * 13.7 ** 2"}}</tool_call></ACTION>
<OBSERVATION>589.636</OBSERVATION>
The area of a circle with radius 13.7 is approximately 589.64 square units.""",
        },
    ]

    # === CATEGORY 2: Search/RAG tool calls ===
    search_examples = [
        {
            "prompt": "What were the key findings of the latest IPCC climate report?",
            "response": """<THOUGHT>This is a factual question about a specific report. I should search for accurate information rather than rely on my training data.</THOUGHT>
<ACTION><tool_call>{"name": "search", "args": {"query": "IPCC climate report key findings latest"}}</tool_call></ACTION>
<OBSERVATION>The IPCC Sixth Assessment Report (AR6) concluded that human activities have unequivocally caused global warming, with global surface temperature increasing by 1.1C above pre-industrial levels. The report emphasizes that limiting warming to 1.5C requires rapid, deep emissions reductions across all sectors.</OBSERVATION>
According to the latest IPCC report, human activities have unequivocally caused global warming of 1.1C above pre-industrial levels. The report stresses that limiting warming to 1.5C requires rapid emissions reductions across all sectors.""",
        },
        {
            "prompt": "Who holds the current world record for the 100m sprint?",
            "response": """<THOUGHT>Sports records change over time. I should look this up to give an accurate answer.</THOUGHT>
<ACTION><tool_call>{"name": "search", "args": {"query": "100m sprint world record holder current"}}</tool_call></ACTION>
<OBSERVATION>Usain Bolt holds the men's 100m world record at 9.58 seconds, set at the 2009 World Championships in Berlin. Florence Griffith-Joyner holds the women's record at 10.49 seconds from 1988.</OBSERVATION>
Usain Bolt holds the men's 100m world record at 9.58 seconds (set in 2009), and Florence Griffith-Joyner holds the women's record at 10.49 seconds (set in 1988).""",
        },
    ]

    # === CATEGORY 3: Code execution ===
    code_examples = [
        {
            "prompt": "Generate the first 20 Fibonacci numbers.",
            "response": """<THOUGHT>I'll write a quick Python script to generate these accurately.</THOUGHT>
<ACTION><tool_call>{"name": "code_exec", "args": {"code": "a, b = 0, 1\\nfibs = []\\nfor _ in range(20):\\n    fibs.append(a)\\n    a, b = b, a + b\\nprint(fibs)"}}</tool_call></ACTION>
<OBSERVATION>[0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181]</OBSERVATION>
The first 20 Fibonacci numbers are: 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181.""",
        },
        {
            "prompt": "Sort this list and remove duplicates: [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]",
            "response": """<THOUGHT>I'll use Python to sort and deduplicate this list.</THOUGHT>
<ACTION><tool_call>{"name": "code_exec", "args": {"code": "data = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]\\nresult = sorted(set(data))\\nprint(result)"}}</tool_call></ACTION>
<OBSERVATION>[1, 2, 3, 4, 5, 6, 9]</OBSERVATION>
The sorted list with duplicates removed is: [1, 2, 3, 4, 5, 6, 9].""",
        },
    ]

    # === CATEGORY 4: NO tool needed (teach when NOT to call) ===
    no_tool_examples = [
        {
            "prompt": "What is 2 + 2?",
            "response": "4.",
        },
        {
            "prompt": "What color is the sky on a clear day?",
            "response": "The sky appears blue on a clear day due to Rayleigh scattering, where shorter blue wavelengths of sunlight are scattered more than other colors by the atmosphere.",
        },
        {
            "prompt": "Say hello in French.",
            "response": "Bonjour! This is the standard greeting in French, used throughout the day. In the evening, you can also say 'Bonsoir.'",
        },
        {
            "prompt": "What is a variable in programming?",
            "response": "A variable is a named container that stores a value in a program's memory. You can think of it like a labeled box. In Python, you create one simply by assigning: `x = 42`. The variable `x` now holds the integer 42 and can be used in expressions, passed to functions, or reassigned.",
        },
        {
            "prompt": "Is Python interpreted or compiled?",
            "response": "Python is primarily an interpreted language. The Python interpreter reads and executes code line by line at runtime. However, it does compile source code to bytecode (.pyc files) first, which is then executed by the Python Virtual Machine (PVM). So technically it's both compiled (to bytecode) and interpreted (bytecode execution).",
        },
    ]

    # === CATEGORY 5: Model routing (escalate to specialist) ===
    routing_examples = [
        {
            "prompt": "Write a 2000-word essay analyzing the economic impact of artificial intelligence on developing nations.",
            "response": """<THOUGHT>This is a complex, long-form analysis that requires deep reasoning. I should escalate to a larger, more capable model.</THOUGHT>
<ACTION><tool_call>{"name": "model_query", "args": {"query": "Write a 2000-word essay analyzing the economic impact of artificial intelligence on developing nations.", "model_type": "reasoning"}}</tool_call></ACTION>
<OBSERVATION>[Long-form essay from specialist model]</OBSERVATION>
[Synthesized response from specialist model]""",
        },
        {
            "prompt": "Analyze this 500-line Python codebase for security vulnerabilities.",
            "response": """<THOUGHT>Security analysis of a large codebase requires specialized code analysis capabilities. I should route this to a code specialist.</THOUGHT>
<ACTION><tool_call>{"name": "model_query", "args": {"query": "Analyze this codebase for security vulnerabilities", "model_type": "code"}}</tool_call></ACTION>
<OBSERVATION>[Detailed security analysis from code specialist]</OBSERVATION>
[Security analysis results]""",
        },
    ]

    # === CATEGORY 6: Multi-step ReAct chains ===
    multistep_examples = [
        {
            "prompt": "What is the population density of the country that won the most recent FIFA World Cup?",
            "response": """<THOUGHT>I need to find two pieces of information: (1) who won the most recent World Cup, and (2) that country's population density.</THOUGHT>
<ACTION><tool_call>{"name": "search", "args": {"query": "most recent FIFA World Cup winner"}}</tool_call></ACTION>
<OBSERVATION>Argentina won the 2022 FIFA World Cup in Qatar.</OBSERVATION>
<THOUGHT>Now I need Argentina's population density.</THOUGHT>
<ACTION><tool_call>{"name": "search", "args": {"query": "Argentina population density"}}</tool_call></ACTION>
<OBSERVATION>Argentina has a population of approximately 46 million across 2.78 million square kilometers, giving a population density of about 16.6 people per square kilometer.</OBSERVATION>
Argentina won the most recent FIFA World Cup (2022). Argentina has a population density of approximately 16.6 people per square kilometer, making it one of the more sparsely populated countries in South America.""",
        },
    ]

    # Combine all categories
    for ex in calc_examples:
        ex["domain"] = "tool_calculator"
        pairs.append(ex)
    for ex in search_examples:
        ex["domain"] = "tool_search"
        pairs.append(ex)
    for ex in code_examples:
        ex["domain"] = "tool_code"
        pairs.append(ex)
    for ex in no_tool_examples:
        ex["domain"] = "no_tool"
        pairs.append(ex)
    for ex in routing_examples:
        ex["domain"] = "tool_routing"
        pairs.append(ex)
    for ex in multistep_examples:
        ex["domain"] = "tool_multistep"
        pairs.append(ex)

    return pairs


if __name__ == "__main__":
    pairs = generate_tool_use_examples()

    # Add model metadata
    for p in pairs:
        p["model"] = "synthetic_tool_training"
        p["timestamp"] = "2026-03-20"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=1, ensure_ascii=False)

    print(f"Generated {len(pairs)} tool-use training pairs")
    print(f"  Calculator: {sum(1 for p in pairs if p['domain']=='tool_calculator')}")
    print(f"  Search/RAG: {sum(1 for p in pairs if p['domain']=='tool_search')}")
    print(f"  Code exec:  {sum(1 for p in pairs if p['domain']=='tool_code')}")
    print(f"  No-tool:    {sum(1 for p in pairs if p['domain']=='no_tool')}")
    print(f"  Routing:    {sum(1 for p in pairs if p['domain']=='tool_routing')}")
    print(f"  Multi-step: {sum(1 for p in pairs if p['domain']=='tool_multistep')}")
    print(f"Saved to {OUTPUT_FILE}")
