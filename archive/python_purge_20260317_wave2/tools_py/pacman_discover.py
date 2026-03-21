"""Pacman Discovery Pipeline — Extract skills, abilities, and features from all sources.

Scans:
1. go_pieces.json — extract skills from model names/types
2. OpenRouter API — model capabilities, tags, pricing
3. Ollama library — local model capabilities
4. HuggingFace — task types, pipeline tags
5. Cloud config — provider features
6. System capabilities — installed tools, services

Outputs: C:/NovaX/data/pacman_registry.json
"""
import json, os, sys, urllib.request, ssl, re
from collections import defaultdict

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def api_get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return json.loads(resp.read())
    except:
        return None

# ═══════════════════════════════════════════════════════════════
# SKILL TAXONOMY — what models and tools CAN DO
# ═══════════════════════════════════════════════════════════════

SKILL_CATEGORIES = {
    # Language Skills
    "text-generation": {"category": "language", "territory": "chat", "description": "Generate natural language text"},
    "text-completion": {"category": "language", "territory": "chat", "description": "Complete partial text"},
    "chat": {"category": "language", "territory": "chat", "description": "Multi-turn conversation"},
    "instruction-following": {"category": "language", "territory": "chat", "description": "Follow complex instructions"},
    "creative-writing": {"category": "language", "territory": "chat", "description": "Poetry, stories, scripts"},
    "summarization": {"category": "language", "territory": "reasoning", "description": "Condense long text"},
    "translation": {"category": "language", "territory": "chat", "description": "Translate between languages"},
    "paraphrase": {"category": "language", "territory": "chat", "description": "Rephrase text"},
    "grammar-correction": {"category": "language", "territory": "chat", "description": "Fix grammar and spelling"},
    "question-answering": {"category": "language", "territory": "reasoning", "description": "Answer questions from context"},
    "text-classification": {"category": "language", "territory": "fast", "description": "Classify text into categories"},
    "sentiment-analysis": {"category": "language", "territory": "fast", "description": "Detect sentiment/emotion"},
    "named-entity-recognition": {"category": "language", "territory": "fast", "description": "Extract entities from text"},
    "keyword-extraction": {"category": "language", "territory": "fast", "description": "Extract key terms"},
    "topic-modeling": {"category": "language", "territory": "reasoning", "description": "Discover topics in text"},

    # Code Skills
    "code-generation": {"category": "code", "territory": "code", "description": "Write code from description"},
    "code-completion": {"category": "code", "territory": "code", "description": "Complete partial code"},
    "code-review": {"category": "code", "territory": "code", "description": "Review code for bugs/quality"},
    "code-explanation": {"category": "code", "territory": "code", "description": "Explain what code does"},
    "code-refactoring": {"category": "code", "territory": "code", "description": "Improve code structure"},
    "code-debugging": {"category": "code", "territory": "code", "description": "Find and fix bugs"},
    "code-translation": {"category": "code", "territory": "code", "description": "Convert between languages"},
    "unit-test-generation": {"category": "code", "territory": "code", "description": "Generate test cases"},
    "sql-generation": {"category": "code", "territory": "code", "description": "Write SQL queries"},
    "regex-generation": {"category": "code", "territory": "code", "description": "Create regex patterns"},
    "api-design": {"category": "code", "territory": "code", "description": "Design API endpoints"},
    "documentation-generation": {"category": "code", "territory": "code", "description": "Write docs from code"},
    "shell-scripting": {"category": "code", "territory": "code", "description": "Write shell/bash scripts"},
    "devops": {"category": "code", "territory": "code", "description": "CI/CD, Docker, K8s configs"},

    # Reasoning Skills
    "mathematical-reasoning": {"category": "reasoning", "territory": "reasoning", "description": "Solve math problems"},
    "logical-reasoning": {"category": "reasoning", "territory": "reasoning", "description": "Logic puzzles and proofs"},
    "chain-of-thought": {"category": "reasoning", "territory": "reasoning", "description": "Step-by-step reasoning"},
    "analysis": {"category": "reasoning", "territory": "reasoning", "description": "Analyze complex scenarios"},
    "comparison": {"category": "reasoning", "territory": "reasoning", "description": "Compare and contrast"},
    "planning": {"category": "reasoning", "territory": "reasoning", "description": "Create plans and strategies"},
    "problem-solving": {"category": "reasoning", "territory": "reasoning", "description": "Solve complex problems"},
    "decision-making": {"category": "reasoning", "territory": "reasoning", "description": "Evaluate options and decide"},
    "research": {"category": "reasoning", "territory": "reasoning", "description": "Research and synthesize info"},
    "fact-checking": {"category": "reasoning", "territory": "reasoning", "description": "Verify factual claims"},
    "scientific-reasoning": {"category": "reasoning", "territory": "reasoning", "description": "Scientific method and analysis"},

    # Vision Skills
    "image-generation": {"category": "vision", "territory": "image", "description": "Generate images from text"},
    "image-editing": {"category": "vision", "territory": "image", "description": "Edit and modify images"},
    "image-classification": {"category": "vision", "territory": "image", "description": "Classify image content"},
    "image-captioning": {"category": "vision", "territory": "image", "description": "Describe images in text"},
    "object-detection": {"category": "vision", "territory": "image", "description": "Detect objects in images"},
    "ocr": {"category": "vision", "territory": "image", "description": "Extract text from images"},
    "visual-qa": {"category": "vision", "territory": "image", "description": "Answer questions about images"},
    "image-segmentation": {"category": "vision", "territory": "image", "description": "Segment image regions"},
    "style-transfer": {"category": "vision", "territory": "image", "description": "Apply artistic styles"},
    "image-upscaling": {"category": "vision", "territory": "image", "description": "Enhance image resolution"},
    "background-removal": {"category": "vision", "territory": "image", "description": "Remove image backgrounds"},
    "face-detection": {"category": "vision", "territory": "image", "description": "Detect faces in images"},
    "diagram-generation": {"category": "vision", "territory": "image", "description": "Create diagrams/charts"},
    "screenshot-analysis": {"category": "vision", "territory": "image", "description": "Analyze UI screenshots"},

    # Audio Skills
    "speech-to-text": {"category": "audio", "territory": "audio", "description": "Transcribe audio to text"},
    "text-to-speech": {"category": "audio", "territory": "audio", "description": "Convert text to speech"},
    "audio-classification": {"category": "audio", "territory": "audio", "description": "Classify audio content"},
    "music-generation": {"category": "audio", "territory": "audio", "description": "Generate music"},
    "voice-cloning": {"category": "audio", "territory": "audio", "description": "Clone voice characteristics"},
    "audio-transcription": {"category": "audio", "territory": "audio", "description": "Transcribe audio files"},
    "sound-effects": {"category": "audio", "territory": "audio", "description": "Generate sound effects"},
    "audio-enhancement": {"category": "audio", "territory": "audio", "description": "Improve audio quality"},
    "speaker-diarization": {"category": "audio", "territory": "audio", "description": "Identify speakers in audio"},
    "language-detection": {"category": "audio", "territory": "audio", "description": "Detect spoken language"},

    # Embedding Skills
    "text-embedding": {"category": "embedding", "territory": "embedding", "description": "Convert text to vectors"},
    "semantic-search": {"category": "embedding", "territory": "embedding", "description": "Search by meaning"},
    "similarity-scoring": {"category": "embedding", "territory": "embedding", "description": "Score text similarity"},
    "clustering": {"category": "embedding", "territory": "embedding", "description": "Group similar items"},
    "retrieval-augmented-generation": {"category": "embedding", "territory": "embedding", "description": "RAG pipeline"},
    "document-indexing": {"category": "embedding", "territory": "embedding", "description": "Index documents for search"},
    "recommendation": {"category": "embedding", "territory": "embedding", "description": "Recommend similar items"},

    # Fast/Utility Skills
    "classification": {"category": "fast", "territory": "fast", "description": "Fast categorization"},
    "extraction": {"category": "fast", "territory": "fast", "description": "Extract structured data"},
    "formatting": {"category": "fast", "territory": "fast", "description": "Format and structure text"},
    "validation": {"category": "fast", "territory": "fast", "description": "Validate data/inputs"},
    "routing": {"category": "fast", "territory": "fast", "description": "Route queries to handlers"},
    "moderation": {"category": "fast", "territory": "fast", "description": "Content moderation"},
    "tokenization": {"category": "fast", "territory": "fast", "description": "Tokenize text"},

    # System/Tool Skills
    "function-calling": {"category": "system", "territory": "code", "description": "Call external functions/APIs"},
    "tool-use": {"category": "system", "territory": "code", "description": "Use external tools"},
    "json-mode": {"category": "system", "territory": "fast", "description": "Structured JSON output"},
    "system-prompts": {"category": "system", "territory": "chat", "description": "Follow system instructions"},
    "multi-turn": {"category": "system", "territory": "chat", "description": "Multi-turn conversation"},
    "streaming": {"category": "system", "territory": "fast", "description": "Stream responses token-by-token"},
    "batch-processing": {"category": "system", "territory": "fast", "description": "Process multiple inputs"},
    "context-window-128k": {"category": "system", "territory": "reasoning", "description": "128K+ token context"},
    "context-window-1m": {"category": "system", "territory": "reasoning", "description": "1M+ token context"},

    # Data Skills
    "data-analysis": {"category": "data", "territory": "reasoning", "description": "Analyze datasets"},
    "data-visualization": {"category": "data", "territory": "code", "description": "Create charts/graphs"},
    "csv-processing": {"category": "data", "territory": "code", "description": "Process CSV files"},
    "json-processing": {"category": "data", "territory": "fast", "description": "Process JSON data"},
    "xml-processing": {"category": "data", "territory": "fast", "description": "Process XML data"},
    "spreadsheet": {"category": "data", "territory": "code", "description": "Spreadsheet operations"},
    "database-query": {"category": "data", "territory": "code", "description": "Query databases"},

    # Domain Skills
    "medical": {"category": "domain", "territory": "reasoning", "description": "Medical/health knowledge"},
    "legal": {"category": "domain", "territory": "reasoning", "description": "Legal analysis"},
    "financial": {"category": "domain", "territory": "reasoning", "description": "Financial analysis"},
    "scientific": {"category": "domain", "territory": "reasoning", "description": "Scientific knowledge"},
    "educational": {"category": "domain", "territory": "chat", "description": "Teaching and tutoring"},
    "cybersecurity": {"category": "domain", "territory": "code", "description": "Security analysis"},
    "marketing": {"category": "domain", "territory": "chat", "description": "Marketing content"},
    "customer-support": {"category": "domain", "territory": "chat", "description": "Customer service"},

    # Multimodal Skills
    "multimodal": {"category": "multimodal", "territory": "image", "description": "Process multiple modalities"},
    "vision-language": {"category": "multimodal", "territory": "image", "description": "Combined vision+language"},
    "audio-language": {"category": "multimodal", "territory": "audio", "description": "Combined audio+language"},
    "video-understanding": {"category": "multimodal", "territory": "image", "description": "Analyze video content"},
    "document-understanding": {"category": "multimodal", "territory": "reasoning", "description": "Process documents with layout"},
}

# ═══════════════════════════════════════════════════════════════
# MODEL → SKILL MAPPING (pattern-based extraction)
# ═══════════════════════════════════════════════════════════════

MODEL_SKILL_PATTERNS = {
    # Code models
    r"code|coder|codegen|starcoder|codellama|deepseek-coder|wizardcoder|magicoder|sqlcoder|granite-code|codegeex|stable-code|qwen.*coder|yi-coder|codestral": [
        "code-generation", "code-completion", "code-review", "code-debugging",
        "code-explanation", "unit-test-generation", "shell-scripting"
    ],
    # Vision models
    r"vision|llava|bakllava|moondream|cogvlm|internvl|minicpm-v|pixtral|qwen.*vl|gemini.*pro.*vision|gpt-4o|gpt-4-turbo|claude-3|gemini-2": [
        "image-captioning", "visual-qa", "ocr", "screenshot-analysis", "multimodal", "vision-language"
    ],
    # Image generation
    r"dall-e|stable-diffusion|sdxl|flux|midjourney|playground|kandinsky|imagen": [
        "image-generation", "image-editing", "style-transfer"
    ],
    # Reasoning models
    r"o1|o3|deepseek-r1|qwq|reasoner|think|reflection|phi-4|gemini.*think": [
        "chain-of-thought", "mathematical-reasoning", "logical-reasoning",
        "problem-solving", "scientific-reasoning", "analysis"
    ],
    # Math models
    r"math|wizard-math|metamath|llemma|minerva|numina": [
        "mathematical-reasoning", "problem-solving", "scientific-reasoning"
    ],
    # Chat/instruct models (broad)
    r"instruct|chat|assistant|hermes|openhermes|neural-chat|openchat|zephyr|starling|vicuna|orca|yi-chat|solar": [
        "text-generation", "chat", "instruction-following", "multi-turn",
        "creative-writing", "question-answering", "system-prompts"
    ],
    # Fast/small models
    r"tiny|mini|nano|small|1b|3b|phi-[123]|qwen.*0\.5|gemma-2b|smol": [
        "classification", "extraction", "formatting", "routing",
        "text-classification", "sentiment-analysis", "json-mode"
    ],
    # Embedding models
    r"embed|e5|bge|gte|nomic-embed|mxbai-embed|all-minilm|jina-embed|voyage|cohere-embed": [
        "text-embedding", "semantic-search", "similarity-scoring",
        "clustering", "retrieval-augmented-generation", "document-indexing"
    ],
    # Audio models
    r"whisper|tts|audio|speech|voice|bark|tortoise|coqui|melo": [
        "speech-to-text", "text-to-speech", "audio-transcription",
        "language-detection"
    ],
    # Large flagship models
    r"gpt-4o|gpt-4-turbo|claude-3\.5|claude-3-opus|gemini-1\.5-pro|gemini-2\.0|command-r-plus|llama-3\.1-405b|mixtral-8x22b|qwen-2\.5-72b|deepseek-v3": [
        "text-generation", "chat", "instruction-following", "code-generation",
        "chain-of-thought", "analysis", "planning", "research",
        "function-calling", "tool-use", "json-mode", "multi-turn",
        "creative-writing", "summarization", "translation"
    ],
    # Medium models
    r"llama-3|mistral-7b|mixtral|qwen-2\.5|gemma|phi-3|command-r[^-]|solar-10": [
        "text-generation", "chat", "instruction-following",
        "question-answering", "summarization", "multi-turn"
    ],
    # Document/long context
    r"long|128k|1m|200k|context|document": [
        "context-window-128k", "document-understanding", "summarization", "research"
    ],
    # Moderation
    r"modera|guard|safety|shield|llama-guard": [
        "moderation", "classification", "validation"
    ],
    # Translation
    r"nllb|madlad|opus-mt|marian|seamless|tower": [
        "translation", "language-detection"
    ],
    # Medical
    r"med|clinical|bio|pubmed|meditron": [
        "medical", "scientific-reasoning", "question-answering"
    ],
    # Legal
    r"legal|law|saul": [
        "legal", "analysis", "summarization"
    ],
    # Finance
    r"finance|fin-|bloom-fin|trading": [
        "financial", "data-analysis", "analysis"
    ],
}

def extract_skills_from_model(model_name, provider=""):
    """Extract skills a model likely has based on its name."""
    skills = set()
    model_lower = model_name.lower()

    for pattern, model_skills in MODEL_SKILL_PATTERNS.items():
        if re.search(pattern, model_lower):
            skills.update(model_skills)

    # All models get basic skills
    if not skills:
        skills.update(["text-generation", "chat", "instruction-following"])

    # Provider-specific capabilities
    if provider in ("openai",):
        skills.update(["function-calling", "json-mode", "streaming"])
    if provider in ("anthropic",):
        skills.update(["tool-use", "json-mode", "streaming", "system-prompts"])
    if provider in ("google",):
        skills.update(["function-calling", "streaming"])

    return sorted(skills)


def extract_skills_from_openrouter(key):
    """Pull model capabilities from OpenRouter's API (includes tags/context)."""
    data = api_get("https://openrouter.ai/api/v1/models", {"Authorization": f"Bearer {key}"})
    if not data:
        return {}

    model_skills = {}
    for m in data.get("data", []):
        mid = m.get("id", "")
        if not mid:
            continue

        skills = set()
        ctx_len = m.get("context_length", 0)
        pricing = m.get("pricing", {})
        arch = m.get("architecture", {})
        modality = arch.get("modality", "text->text") if arch else "text->text"

        # Context window skills
        if ctx_len >= 1000000:
            skills.add("context-window-1m")
        elif ctx_len >= 100000:
            skills.add("context-window-128k")

        # Modality skills
        if "image" in modality:
            skills.update(["multimodal", "vision-language", "image-captioning", "visual-qa"])
        if "audio" in modality:
            skills.update(["audio-language", "speech-to-text"])

        # Tool use from OpenRouter
        if m.get("supported_parameters"):
            params = m.get("supported_parameters", [])
            if isinstance(params, list):
                if "tools" in params:
                    skills.update(["function-calling", "tool-use"])
                if "response_format" in params:
                    skills.add("json-mode")

        # Pattern-based skills from model name
        name_skills = extract_skills_from_model(mid, "openrouter")
        skills.update(name_skills)

        model_skills[mid] = sorted(skills)

    return model_skills


def extract_skills_from_ollama():
    """Pull local Ollama model capabilities."""
    data = api_get("http://127.0.0.1:11434/api/tags")
    if not data:
        return {}

    model_skills = {}
    for m in data.get("models", []):
        name = m.get("name", "")
        if not name:
            continue
        skills = extract_skills_from_model(name, "ollama")

        # Local models always get streaming
        skills = list(set(skills) | {"streaming"})
        model_skills[name] = sorted(skills)

    return model_skills


def extract_huggingface_tasks():
    """Discover HuggingFace pipeline tasks (no auth needed for public API)."""
    # Known HF task taxonomy — these are the pipelines available
    hf_tasks = {
        "text-generation": ["text-generation", "chat", "instruction-following"],
        "text2text-generation": ["text-generation", "translation", "summarization"],
        "fill-mask": ["text-completion", "named-entity-recognition"],
        "token-classification": ["named-entity-recognition", "keyword-extraction"],
        "text-classification": ["text-classification", "sentiment-analysis"],
        "question-answering": ["question-answering", "extraction"],
        "summarization": ["summarization", "analysis"],
        "translation": ["translation", "language-detection"],
        "conversational": ["chat", "multi-turn", "instruction-following"],
        "image-classification": ["image-classification", "visual-qa"],
        "object-detection": ["object-detection", "image-classification"],
        "image-segmentation": ["image-segmentation", "object-detection"],
        "image-to-text": ["image-captioning", "ocr", "visual-qa"],
        "text-to-image": ["image-generation", "style-transfer"],
        "visual-question-answering": ["visual-qa", "multimodal", "vision-language"],
        "document-question-answering": ["document-understanding", "ocr", "extraction"],
        "automatic-speech-recognition": ["speech-to-text", "audio-transcription"],
        "text-to-speech": ["text-to-speech", "voice-cloning"],
        "audio-classification": ["audio-classification", "language-detection"],
        "feature-extraction": ["text-embedding", "semantic-search", "similarity-scoring"],
        "sentence-similarity": ["similarity-scoring", "semantic-search", "text-embedding"],
        "zero-shot-classification": ["classification", "text-classification"],
        "table-question-answering": ["database-query", "data-analysis", "extraction"],
        "image-to-image": ["image-editing", "style-transfer", "image-upscaling"],
        "depth-estimation": ["image-segmentation", "multimodal"],
        "video-classification": ["video-understanding", "multimodal"],
        "reinforcement-learning": ["planning", "decision-making"],
    }
    return hf_tasks


def extract_system_capabilities():
    """Discover system-level tools and capabilities."""
    capabilities = {}

    # Check for installed Python packages that add skills
    tools_dir = "C:/NovaX/tools"
    if os.path.exists(tools_dir):
        for f in os.listdir(tools_dir):
            if f.endswith(".py"):
                tool_name = f.replace(".py", "")
                capabilities[f"tool:{tool_name}"] = {
                    "type": "tool",
                    "source": "novax-tools",
                    "skills": ["function-calling", "tool-use"],
                    "description": f"NovaX tool: {tool_name}"
                }

    # Check for NovaLang services
    service_dir = "C:/NovaX"
    if os.path.exists(service_dir):
        for f in os.listdir(service_dir):
            if f.endswith("_service.nova"):
                svc_name = f.replace("_service.nova", "").replace("nova_", "")
                capabilities[f"service:{svc_name}"] = {
                    "type": "service",
                    "source": "novax-fleet",
                    "skills": ["streaming", "function-calling"],
                    "description": f"NovaX service: {svc_name}"
                }

    # Check for Ollama availability
    try:
        data = api_get("http://127.0.0.1:11434/api/tags", timeout=3)
        if data:
            capabilities["runtime:ollama"] = {
                "type": "runtime",
                "source": "local",
                "skills": ["text-generation", "streaming", "code-generation"],
                "description": f"Ollama runtime with {len(data.get('models',[]))} models"
            }
    except:
        pass

    return capabilities


def build_registry():
    """Main pipeline: discover everything, build unified registry."""
    print("[Pacman] Starting discovery pipeline...")
    registry = {
        "version": "2.0.0",
        "skills": {},
        "abilities": {},
        "features": {},
        "models_with_skills": {},
        "stats": {},
    }

    # Load cloud config for API keys
    config = {}
    try:
        config = json.load(open("C:/NovaX/cloud_config.json"))
    except:
        print("[Pacman] WARNING: Could not load cloud_config.json")

    # Load existing pieces
    pieces = {}
    try:
        data = json.load(open("C:/NovaX/data/go_pieces.json"))
        pieces = data.get("pieces", {})
    except:
        print("[Pacman] WARNING: Could not load go_pieces.json")

    all_skills = set()
    model_count = 0

    # --- Source 1: Extract skills from all known models (go_pieces.json) ---
    print(f"[Pacman] Source 1: Extracting skills from {len(pieces)} pieces...")
    for key, piece in pieces.items():
        model = piece.get("model", "")
        provider = piece.get("provider", "")
        skills = extract_skills_from_model(model, provider)
        registry["models_with_skills"][key] = {
            "model": model,
            "provider": provider,
            "territory": piece.get("territory", "chat"),
            "skills": skills,
            "max_tokens": piece.get("max_tokens", 8192),
            "locked": True,  # permanent lock
        }
        all_skills.update(skills)
        model_count += 1

    # --- Source 2: OpenRouter API (detailed capabilities) ---
    or_key = config.get("openrouter", {}).get("key", "")
    if or_key:
        print("[Pacman] Source 2: Scanning OpenRouter API for capabilities...")
        or_skills = extract_skills_from_openrouter(or_key)
        for mid, skills in or_skills.items():
            all_skills.update(skills)
            # Merge into existing model entries
            pkey = f"openrouter:{mid}"
            if pkey in registry["models_with_skills"]:
                existing = registry["models_with_skills"][pkey]["skills"]
                merged = sorted(set(existing + skills))
                registry["models_with_skills"][pkey]["skills"] = merged
    else:
        print("[Pacman] Source 2: No OpenRouter key, skipping API scan")

    # --- Source 3: Ollama local models ---
    print("[Pacman] Source 3: Scanning Ollama local models...")
    ollama_skills = extract_skills_from_ollama()
    for name, skills in ollama_skills.items():
        all_skills.update(skills)
        pkey = f"ollama:{name}"
        if pkey in registry["models_with_skills"]:
            existing = registry["models_with_skills"][pkey]["skills"]
            merged = sorted(set(existing + skills))
            registry["models_with_skills"][pkey]["skills"] = merged

    # --- Source 4: HuggingFace task taxonomy ---
    print("[Pacman] Source 4: Loading HuggingFace task taxonomy...")
    hf_tasks = extract_huggingface_tasks()
    hf_skill_count = 0
    for task, skills in hf_tasks.items():
        all_skills.update(skills)
        hf_skill_count += len(skills)

    # --- Source 5: System capabilities ---
    print("[Pacman] Source 5: Scanning system capabilities...")
    sys_caps = extract_system_capabilities()

    # ═══════════════════════════════════════════════════════════════
    # Build unified skill registry
    # ═══════════════════════════════════════════════════════════════

    # Count which models have each skill
    skill_model_count = defaultdict(int)
    for key, entry in registry["models_with_skills"].items():
        for skill in entry.get("skills", []):
            skill_model_count[skill] += 1

    # Build skill entries with metadata
    for skill_name in sorted(all_skills):
        meta = SKILL_CATEGORIES.get(skill_name, {
            "category": "unknown",
            "territory": "chat",
            "description": skill_name.replace("-", " ").title()
        })
        registry["skills"][skill_name] = {
            "name": skill_name,
            "category": meta["category"],
            "territory": meta["territory"],
            "description": meta["description"],
            "model_count": skill_model_count.get(skill_name, 0),
            "available": skill_model_count.get(skill_name, 0) > 0,
            "locked": True,  # all skills permanently locked
        }

    # ═══════════════════════════════════════════════════════════════
    # Build abilities (what NovaX can DO with these skills)
    # ═══════════════════════════════════════════════════════════════

    ABILITIES = {
        "ai-chat": {"skills": ["chat", "multi-turn", "instruction-following"], "description": "Conversational AI assistant"},
        "code-assistant": {"skills": ["code-generation", "code-completion", "code-debugging"], "description": "AI-powered coding assistant"},
        "code-reviewer": {"skills": ["code-review", "code-explanation", "unit-test-generation"], "description": "Automated code review"},
        "document-processor": {"skills": ["summarization", "extraction", "document-understanding"], "description": "Process and analyze documents"},
        "translator": {"skills": ["translation", "language-detection"], "description": "Multi-language translation"},
        "data-analyst": {"skills": ["data-analysis", "data-visualization", "database-query"], "description": "Data analysis and visualization"},
        "creative-writer": {"skills": ["creative-writing", "text-generation", "paraphrase"], "description": "Creative content generation"},
        "research-assistant": {"skills": ["research", "analysis", "summarization", "fact-checking"], "description": "Research and synthesis"},
        "math-solver": {"skills": ["mathematical-reasoning", "problem-solving", "chain-of-thought"], "description": "Mathematical problem solving"},
        "image-analyst": {"skills": ["image-captioning", "visual-qa", "ocr"], "description": "Analyze and describe images"},
        "image-creator": {"skills": ["image-generation", "image-editing", "style-transfer"], "description": "Generate and edit images"},
        "voice-assistant": {"skills": ["speech-to-text", "text-to-speech"], "description": "Voice input/output"},
        "search-engine": {"skills": ["semantic-search", "text-embedding", "retrieval-augmented-generation"], "description": "Semantic search across data"},
        "content-moderator": {"skills": ["moderation", "classification", "sentiment-analysis"], "description": "Content safety filtering"},
        "api-builder": {"skills": ["function-calling", "tool-use", "json-mode", "api-design"], "description": "Build and use APIs"},
        "tutor": {"skills": ["educational", "chain-of-thought", "question-answering"], "description": "Interactive teaching"},
        "security-analyst": {"skills": ["cybersecurity", "code-review", "analysis"], "description": "Security analysis and review"},
        "devops-engineer": {"skills": ["devops", "shell-scripting", "code-generation"], "description": "DevOps automation"},
        "customer-agent": {"skills": ["customer-support", "chat", "sentiment-analysis"], "description": "Customer support agent"},
        "report-generator": {"skills": ["summarization", "data-analysis", "formatting"], "description": "Generate reports from data"},
        "text-classifier": {"skills": ["text-classification", "sentiment-analysis", "named-entity-recognition"], "description": "Classify and categorize text"},
        "document-indexer": {"skills": ["document-indexing", "text-embedding", "clustering"], "description": "Index documents for search"},
        "multimodal-assistant": {"skills": ["multimodal", "vision-language", "image-captioning"], "description": "Process text, images, and audio"},
        "planning-agent": {"skills": ["planning", "decision-making", "analysis"], "description": "Strategic planning and decisions"},
        "legal-analyst": {"skills": ["legal", "analysis", "summarization"], "description": "Legal document analysis"},
        "medical-assistant": {"skills": ["medical", "question-answering", "scientific-reasoning"], "description": "Medical information assistant"},
        "financial-analyst": {"skills": ["financial", "data-analysis", "analysis"], "description": "Financial analysis and modeling"},
        "batch-processor": {"skills": ["batch-processing", "json-processing", "extraction"], "description": "Process data in bulk"},
        "regex-helper": {"skills": ["regex-generation", "validation", "extraction"], "description": "Create and test regex patterns"},
        "sql-assistant": {"skills": ["sql-generation", "database-query", "data-analysis"], "description": "SQL query generation and optimization"},
        "test-engineer": {"skills": ["unit-test-generation", "code-debugging", "validation"], "description": "Test generation and debugging"},
        "doc-writer": {"skills": ["documentation-generation", "formatting", "code-explanation"], "description": "Documentation generation"},
    }

    for ability_name, ability_def in ABILITIES.items():
        required_skills = ability_def["skills"]
        available_skills = [s for s in required_skills if registry["skills"].get(s, {}).get("available", False)]
        coverage = len(available_skills) / len(required_skills) if required_skills else 0

        # Count total models that support this ability
        supporting_models = 0
        for key, entry in registry["models_with_skills"].items():
            model_skills = set(entry.get("skills", []))
            if model_skills & set(required_skills):
                supporting_models += 1

        registry["abilities"][ability_name] = {
            "name": ability_name,
            "description": ability_def["description"],
            "required_skills": required_skills,
            "available_skills": available_skills,
            "coverage": round(coverage * 100, 1),
            "status": "ready" if coverage >= 0.5 else "partial" if coverage > 0 else "missing",
            "supporting_models": supporting_models,
            "locked": True,
        }

    # ═══════════════════════════════════════════════════════════════
    # Build features (higher-level capabilities enabled by abilities)
    # ═══════════════════════════════════════════════════════════════

    FEATURES = {
        "intelligent-routing": {"abilities": ["ai-chat", "text-classifier"], "description": "Route queries to optimal model"},
        "full-stack-dev": {"abilities": ["code-assistant", "code-reviewer", "test-engineer", "doc-writer"], "description": "Full-stack development workflow"},
        "research-pipeline": {"abilities": ["research-assistant", "search-engine", "document-processor", "report-generator"], "description": "End-to-end research pipeline"},
        "content-pipeline": {"abilities": ["creative-writer", "translator", "content-moderator"], "description": "Content creation and moderation"},
        "data-pipeline": {"abilities": ["data-analyst", "batch-processor", "sql-assistant", "document-indexer"], "description": "Data processing pipeline"},
        "multimodal-agent": {"abilities": ["multimodal-assistant", "image-analyst", "voice-assistant"], "description": "Multi-modal AI agent"},
        "security-suite": {"abilities": ["security-analyst", "code-reviewer", "content-moderator"], "description": "Security analysis suite"},
        "education-platform": {"abilities": ["tutor", "math-solver", "doc-writer"], "description": "Educational AI platform"},
        "enterprise-assistant": {"abilities": ["customer-agent", "report-generator", "planning-agent"], "description": "Enterprise AI assistant"},
        "developer-toolkit": {"abilities": ["code-assistant", "api-builder", "devops-engineer", "regex-helper"], "description": "Complete developer toolkit"},
        "image-studio": {"abilities": ["image-creator", "image-analyst"], "description": "Image creation and analysis"},
        "voice-interface": {"abilities": ["voice-assistant", "ai-chat"], "description": "Voice-driven AI interface"},
        "legal-suite": {"abilities": ["legal-analyst", "document-processor", "search-engine"], "description": "Legal document suite"},
        "medical-suite": {"abilities": ["medical-assistant", "research-assistant", "report-generator"], "description": "Medical information suite"},
        "financial-suite": {"abilities": ["financial-analyst", "data-analyst", "report-generator"], "description": "Financial analysis suite"},
    }

    for feature_name, feature_def in FEATURES.items():
        required_abilities = feature_def["abilities"]
        ready_abilities = [a for a in required_abilities if registry["abilities"].get(a, {}).get("status") == "ready"]
        coverage = len(ready_abilities) / len(required_abilities) if required_abilities else 0

        registry["features"][feature_name] = {
            "name": feature_name,
            "description": feature_def["description"],
            "required_abilities": required_abilities,
            "ready_abilities": ready_abilities,
            "coverage": round(coverage * 100, 1),
            "status": "active" if coverage >= 0.75 else "partial" if coverage > 0 else "inactive",
            "locked": True,
        }

    # ═══════════════════════════════════════════════════════════════
    # System capabilities
    # ═══════════════════════════════════════════════════════════════
    registry["system_capabilities"] = sys_caps
    registry["huggingface_tasks"] = hf_tasks

    # ═══════════════════════════════════════════════════════════════
    # Stats
    # ═══════════════════════════════════════════════════════════════
    skill_count = len(registry["skills"])
    ability_count = len(registry["abilities"])
    feature_count = len(registry["features"])
    ready_abilities = sum(1 for a in registry["abilities"].values() if a["status"] == "ready")
    active_features = sum(1 for f in registry["features"].values() if f["status"] == "active")
    sys_cap_count = len(sys_caps)

    # Category breakdown
    categories = defaultdict(int)
    for s in registry["skills"].values():
        categories[s["category"]] += 1

    # Territory breakdown
    territories = defaultdict(int)
    for s in registry["skills"].values():
        territories[s["territory"]] += 1

    registry["stats"] = {
        "total_skills": skill_count,
        "total_abilities": ability_count,
        "total_features": feature_count,
        "ready_abilities": ready_abilities,
        "active_features": active_features,
        "total_models": model_count,
        "system_capabilities": sys_cap_count,
        "skill_categories": dict(categories),
        "skill_territories": dict(territories),
        "all_locked": True,
        "discovery_sources": ["go_pieces", "openrouter_api", "ollama_local", "huggingface_tasks", "system_scan"],
    }

    # Write registry
    out_path = "C:/NovaX/data/pacman_registry.json"
    with open(out_path, "w") as f:
        json.dump(registry, f, indent=2)

    print(f"[Pacman] Discovery complete!")
    print(f"  Skills:      {skill_count} ({dict(categories)})")
    print(f"  Abilities:   {ability_count} ({ready_abilities} ready)")
    print(f"  Features:    {feature_count} ({active_features} active)")
    print(f"  Models:      {model_count} (all locked)")
    print(f"  System caps: {sys_cap_count}")
    print(f"  Registry:    {out_path}")

    # Output summary for piping
    summary = {
        "ok": 1,
        "total_skills": skill_count,
        "total_abilities": ability_count,
        "total_features": feature_count,
        "ready_abilities": ready_abilities,
        "active_features": active_features,
        "total_models": model_count,
        "all_locked": True,
    }
    print(json.dumps(summary))


if __name__ == "__main__":
    build_registry()
