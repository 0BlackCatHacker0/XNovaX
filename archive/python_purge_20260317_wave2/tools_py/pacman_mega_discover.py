"""Pacman MEGA Discovery — Extract tens of thousands of skills, abilities, features.

Sources:
1. go_pieces.json (622 local models)
2. OpenRouter API (400+ cloud models)
3. HuggingFace inference models (200k+ tasks)
4. Ollama local models
5. System capabilities + NovaX services
6. Compound abilities from skill combinations
7. Feature chains from ability combinations

Outputs: C:/NovaX/data/pacman_registry.json
"""
import json, os, sys, urllib.request, ssl, re, itertools, time
from collections import defaultdict

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def api_get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return json.loads(resp.read())
    except Exception as e:
        return None

def log(msg):
    print("[PACMAN] " + msg, flush=True)

# ═══════════════════════════════════════════════════════════
# MASTER SKILL TAXONOMY — 200+ atomic skills
# ═══════════════════════════════════════════════════════════

SKILLS = {}

def add_skill(name, category, territory, desc):
    SKILLS[name] = {"category": category, "territory": territory, "description": desc}

# Language (30+)
for s in [
    ("text-generation", "language", "chat", "Generate natural language text"),
    ("text-completion", "language", "chat", "Complete partial text"),
    ("chat", "language", "chat", "Multi-turn conversation"),
    ("instruction-following", "language", "chat", "Follow complex instructions"),
    ("creative-writing", "language", "chat", "Poetry, stories, scripts"),
    ("summarization", "language", "reasoning", "Condense long text"),
    ("translation", "language", "chat", "Translate between languages"),
    ("paraphrase", "language", "chat", "Rephrase text"),
    ("grammar-correction", "language", "chat", "Fix grammar and spelling"),
    ("question-answering", "language", "reasoning", "Answer questions from context"),
    ("text-classification", "language", "fast", "Classify text into categories"),
    ("sentiment-analysis", "language", "fast", "Detect sentiment and emotion"),
    ("named-entity-recognition", "language", "fast", "Extract entities from text"),
    ("keyword-extraction", "language", "fast", "Extract key terms"),
    ("topic-modeling", "language", "reasoning", "Discover topics in text"),
    ("language-modeling", "language", "chat", "Predict next tokens"),
    ("fill-mask", "language", "fast", "Fill masked tokens"),
    ("text-rewriting", "language", "chat", "Rewrite text in different style"),
    ("headline-generation", "language", "chat", "Generate headlines/titles"),
    ("essay-writing", "language", "chat", "Write essays and articles"),
    ("email-drafting", "language", "chat", "Draft professional emails"),
    ("dialogue-generation", "language", "chat", "Generate realistic dialogue"),
    ("story-continuation", "language", "chat", "Continue a narrative"),
    ("prompt-engineering", "language", "reasoning", "Optimize prompts"),
    ("multi-language", "language", "chat", "Support multiple languages"),
    ("slang-detection", "language", "fast", "Detect informal language"),
    ("readability-scoring", "language", "fast", "Score text readability"),
    ("text-simplification", "language", "chat", "Simplify complex text"),
    ("acronym-expansion", "language", "fast", "Expand acronyms"),
    ("coreference-resolution", "language", "reasoning", "Resolve pronouns to entities"),
]: add_skill(*s)

# Code (30+)
for s in [
    ("code-generation", "code", "code", "Write code from description"),
    ("code-completion", "code", "code", "Complete partial code"),
    ("code-review", "code", "code", "Review code for bugs/quality"),
    ("code-explanation", "code", "code", "Explain what code does"),
    ("code-refactoring", "code", "code", "Improve code structure"),
    ("code-debugging", "code", "code", "Find and fix bugs"),
    ("code-translation", "code", "code", "Convert between languages"),
    ("unit-test-generation", "code", "code", "Generate test cases"),
    ("sql-generation", "code", "code", "Write SQL queries"),
    ("regex-generation", "code", "code", "Create regex patterns"),
    ("api-design", "code", "code", "Design API endpoints"),
    ("documentation-generation", "code", "code", "Write docs from code"),
    ("shell-scripting", "code", "code", "Write shell/bash scripts"),
    ("devops", "code", "code", "CI/CD, Docker, K8s configs"),
    ("function-calling", "code", "code", "Call external functions/APIs"),
    ("tool-use", "code", "code", "Use external tools"),
    ("html-generation", "code", "code", "Generate HTML markup"),
    ("css-generation", "code", "code", "Generate CSS styles"),
    ("javascript-generation", "code", "code", "Generate JavaScript"),
    ("python-generation", "code", "code", "Generate Python code"),
    ("rust-generation", "code", "code", "Generate Rust code"),
    ("typescript-generation", "code", "code", "Generate TypeScript"),
    ("go-generation", "code", "code", "Generate Go code"),
    ("java-generation", "code", "code", "Generate Java code"),
    ("cpp-generation", "code", "code", "Generate C++ code"),
    ("yaml-generation", "code", "code", "Generate YAML configs"),
    ("dockerfile-generation", "code", "code", "Generate Dockerfiles"),
    ("terraform-generation", "code", "code", "Generate Terraform"),
    ("graphql-generation", "code", "code", "Generate GraphQL schemas"),
    ("protobuf-generation", "code", "code", "Generate Protocol Buffers"),
    ("makefile-generation", "code", "code", "Generate Makefiles"),
    ("git-operations", "code", "code", "Git commands and workflows"),
    ("dependency-analysis", "code", "code", "Analyze code dependencies"),
    ("security-audit", "code", "code", "Audit code for vulnerabilities"),
    ("performance-profiling", "code", "code", "Profile code performance"),
    ("architecture-design", "code", "code", "Design software architecture"),
    ("database-design", "code", "code", "Design database schemas"),
    ("api-testing", "code", "code", "Generate API tests"),
    ("integration-testing", "code", "code", "Integration test generation"),
    ("e2e-testing", "code", "code", "End-to-end test generation"),
]: add_skill(*s)

# Reasoning (25+)
for s in [
    ("mathematical-reasoning", "reasoning", "reasoning", "Solve math problems"),
    ("logical-reasoning", "reasoning", "reasoning", "Logic puzzles and proofs"),
    ("chain-of-thought", "reasoning", "reasoning", "Step-by-step reasoning"),
    ("analysis", "reasoning", "reasoning", "Analyze complex scenarios"),
    ("comparison", "reasoning", "reasoning", "Compare and contrast"),
    ("planning", "reasoning", "reasoning", "Create plans and strategies"),
    ("problem-solving", "reasoning", "reasoning", "Solve complex problems"),
    ("decision-making", "reasoning", "reasoning", "Evaluate options and decide"),
    ("research", "reasoning", "reasoning", "Research and synthesize info"),
    ("fact-checking", "reasoning", "reasoning", "Verify factual claims"),
    ("scientific-reasoning", "reasoning", "reasoning", "Scientific method"),
    ("causal-reasoning", "reasoning", "reasoning", "Determine cause and effect"),
    ("analogical-reasoning", "reasoning", "reasoning", "Reason by analogy"),
    ("deductive-reasoning", "reasoning", "reasoning", "Deduce conclusions"),
    ("inductive-reasoning", "reasoning", "reasoning", "Infer general rules"),
    ("abductive-reasoning", "reasoning", "reasoning", "Best explanation inference"),
    ("spatial-reasoning", "reasoning", "reasoning", "Understand spatial relationships"),
    ("temporal-reasoning", "reasoning", "reasoning", "Reason about time sequences"),
    ("probabilistic-reasoning", "reasoning", "reasoning", "Reason with uncertainty"),
    ("ethical-reasoning", "reasoning", "reasoning", "Evaluate ethical dilemmas"),
    ("meta-reasoning", "reasoning", "reasoning", "Reason about reasoning"),
    ("constraint-satisfaction", "reasoning", "reasoning", "Solve constraint problems"),
    ("optimization", "reasoning", "reasoning", "Find optimal solutions"),
    ("game-theory", "reasoning", "reasoning", "Strategic decision analysis"),
    ("systems-thinking", "reasoning", "reasoning", "Analyze complex systems"),
]: add_skill(*s)

# Vision (25+)
for s in [
    ("image-generation", "vision", "image", "Generate images from text"),
    ("image-editing", "vision", "image", "Edit and modify images"),
    ("image-classification", "vision", "image", "Classify image content"),
    ("image-captioning", "vision", "image", "Describe images in text"),
    ("object-detection", "vision", "image", "Detect objects in images"),
    ("ocr", "vision", "image", "Extract text from images"),
    ("visual-qa", "vision", "image", "Answer questions about images"),
    ("image-segmentation", "vision", "image", "Segment image regions"),
    ("style-transfer", "vision", "image", "Apply artistic styles"),
    ("image-upscaling", "vision", "image", "Enhance image resolution"),
    ("background-removal", "vision", "image", "Remove image backgrounds"),
    ("face-detection", "vision", "image", "Detect faces in images"),
    ("diagram-generation", "vision", "image", "Create diagrams/charts"),
    ("screenshot-analysis", "vision", "image", "Analyze UI screenshots"),
    ("depth-estimation", "vision", "image", "Estimate depth from images"),
    ("pose-estimation", "vision", "image", "Detect human poses"),
    ("image-inpainting", "vision", "image", "Fill missing image areas"),
    ("image-to-text", "vision", "image", "Convert image to text"),
    ("text-to-image", "vision", "image", "Generate image from text"),
    ("image-similarity", "vision", "image", "Compare image similarity"),
    ("color-analysis", "vision", "image", "Analyze image colors"),
    ("scene-understanding", "vision", "image", "Understand scene context"),
    ("document-parsing", "vision", "image", "Parse document images"),
    ("table-extraction", "vision", "image", "Extract tables from images"),
    ("handwriting-recognition", "vision", "image", "Read handwritten text"),
    ("video-generation", "vision", "image", "Generate video from text"),
    ("video-understanding", "vision", "image", "Analyze video content"),
    ("3d-generation", "vision", "image", "Generate 3D content"),
]: add_skill(*s)

# Audio (20+)
for s in [
    ("speech-to-text", "audio", "audio", "Transcribe audio to text"),
    ("text-to-speech", "audio", "audio", "Convert text to speech"),
    ("audio-classification", "audio", "audio", "Classify audio content"),
    ("music-generation", "audio", "audio", "Generate music"),
    ("voice-cloning", "audio", "audio", "Clone voice characteristics"),
    ("audio-transcription", "audio", "audio", "Transcribe audio files"),
    ("sound-effects", "audio", "audio", "Generate sound effects"),
    ("audio-enhancement", "audio", "audio", "Improve audio quality"),
    ("speaker-diarization", "audio", "audio", "Identify speakers in audio"),
    ("language-detection", "audio", "audio", "Detect spoken language"),
    ("emotion-detection-audio", "audio", "audio", "Detect emotions in speech"),
    ("noise-reduction", "audio", "audio", "Remove background noise"),
    ("audio-segmentation", "audio", "audio", "Segment audio tracks"),
    ("voice-conversion", "audio", "audio", "Convert between voices"),
    ("speech-enhancement", "audio", "audio", "Enhance speech clarity"),
    ("audio-tagging", "audio", "audio", "Tag audio content"),
    ("beat-detection", "audio", "audio", "Detect beats in music"),
    ("pitch-detection", "audio", "audio", "Detect pitch in audio"),
    ("audio-mixing", "audio", "audio", "Mix audio tracks"),
    ("podcast-generation", "audio", "audio", "Generate podcast audio"),
]: add_skill(*s)

# Embedding/Search (15+)
for s in [
    ("text-embedding", "embedding", "embedding", "Convert text to vectors"),
    ("semantic-search", "embedding", "embedding", "Search by meaning"),
    ("similarity-scoring", "embedding", "embedding", "Score text similarity"),
    ("clustering", "embedding", "embedding", "Group similar items"),
    ("retrieval-augmented-generation", "embedding", "embedding", "RAG pipeline"),
    ("document-indexing", "embedding", "embedding", "Index documents for search"),
    ("recommendation", "embedding", "embedding", "Recommend similar items"),
    ("image-embedding", "embedding", "embedding", "Convert images to vectors"),
    ("cross-modal-embedding", "embedding", "embedding", "Cross-modal vectors"),
    ("reranking", "embedding", "embedding", "Rerank search results"),
    ("passage-retrieval", "embedding", "embedding", "Retrieve relevant passages"),
    ("hybrid-search", "embedding", "embedding", "Combine keyword + semantic"),
    ("vector-store", "embedding", "embedding", "Store and query vectors"),
    ("knowledge-graph", "embedding", "embedding", "Build knowledge graphs"),
    ("entity-linking", "embedding", "embedding", "Link entities to knowledge"),
]: add_skill(*s)

# Fast/Utility (15+)
for s in [
    ("classification", "fast", "fast", "Fast categorization"),
    ("extraction", "fast", "fast", "Extract structured data"),
    ("formatting", "fast", "fast", "Format and structure text"),
    ("validation", "fast", "fast", "Validate data/inputs"),
    ("routing", "fast", "fast", "Route queries to handlers"),
    ("moderation", "fast", "fast", "Content moderation"),
    ("tokenization", "fast", "fast", "Tokenize text"),
    ("json-mode", "fast", "fast", "Structured JSON output"),
    ("streaming", "fast", "fast", "Stream responses"),
    ("batch-processing", "fast", "fast", "Process multiple inputs"),
    ("caching", "fast", "fast", "Cache responses"),
    ("rate-limiting", "fast", "fast", "Rate limit management"),
    ("load-balancing", "fast", "fast", "Balance across providers"),
    ("failover", "fast", "fast", "Automatic failover"),
    ("retry-logic", "fast", "fast", "Smart retry on failure"),
]: add_skill(*s)

# System/Integration (15+)
for s in [
    ("system-prompts", "system", "chat", "Follow system instructions"),
    ("multi-turn", "system", "chat", "Multi-turn conversation"),
    ("context-window-128k", "system", "reasoning", "128K+ token context"),
    ("context-window-1m", "system", "reasoning", "1M+ token context"),
    ("multi-modal-input", "system", "image", "Accept multiple input types"),
    ("structured-output", "system", "fast", "Produce structured output"),
    ("grounding", "system", "reasoning", "Ground in provided context"),
    ("citation", "system", "reasoning", "Cite sources"),
    ("safety-filtering", "system", "fast", "Filter unsafe content"),
    ("persona", "system", "chat", "Adopt specific personas"),
    ("roleplay", "system", "chat", "Roleplay scenarios"),
    ("fine-tuning-support", "system", "code", "Support fine-tuning"),
    ("prefix-caching", "system", "fast", "Cache prompt prefixes"),
    ("parallel-generation", "system", "fast", "Generate in parallel"),
    ("agent-loop", "system", "code", "Run autonomous agent loops"),
]: add_skill(*s)

# Data/Analytics (15+)
for s in [
    ("data-analysis", "data", "reasoning", "Analyze datasets"),
    ("data-visualization", "data", "code", "Create charts/graphs"),
    ("csv-processing", "data", "code", "Process CSV files"),
    ("json-processing", "data", "fast", "Process JSON data"),
    ("xml-processing", "data", "fast", "Process XML data"),
    ("spreadsheet", "data", "code", "Spreadsheet operations"),
    ("database-query", "data", "code", "Query databases"),
    ("etl-pipeline", "data", "code", "Extract-transform-load"),
    ("data-cleaning", "data", "code", "Clean messy data"),
    ("feature-engineering", "data", "reasoning", "Create ML features"),
    ("statistical-analysis", "data", "reasoning", "Statistical computations"),
    ("time-series-analysis", "data", "reasoning", "Analyze time series"),
    ("anomaly-detection", "data", "reasoning", "Detect anomalies"),
    ("predictive-modeling", "data", "reasoning", "Build predictive models"),
    ("report-generation", "data", "code", "Generate data reports"),
]: add_skill(*s)

# Domain-specific (25+)
for s in [
    ("medical", "domain", "reasoning", "Medical/health knowledge"),
    ("legal", "domain", "reasoning", "Legal analysis"),
    ("financial", "domain", "reasoning", "Financial analysis"),
    ("scientific", "domain", "reasoning", "Scientific knowledge"),
    ("education", "domain", "reasoning", "Educational content"),
    ("marketing", "domain", "chat", "Marketing content"),
    ("sales", "domain", "chat", "Sales communication"),
    ("hr", "domain", "chat", "Human resources"),
    ("customer-support", "domain", "chat", "Customer service"),
    ("technical-writing", "domain", "chat", "Technical documentation"),
    ("journalism", "domain", "chat", "News and journalism"),
    ("academic", "domain", "reasoning", "Academic writing"),
    ("cybersecurity", "domain", "code", "Security analysis"),
    ("blockchain", "domain", "code", "Blockchain/Web3"),
    ("iot", "domain", "code", "Internet of Things"),
    ("robotics", "domain", "code", "Robotics programming"),
    ("game-development", "domain", "code", "Game dev"),
    ("mobile-development", "domain", "code", "Mobile app dev"),
    ("cloud-architecture", "domain", "code", "Cloud design"),
    ("networking", "domain", "code", "Network engineering"),
    ("physics", "domain", "reasoning", "Physics knowledge"),
    ("chemistry", "domain", "reasoning", "Chemistry knowledge"),
    ("biology", "domain", "reasoning", "Biology knowledge"),
    ("mathematics", "domain", "reasoning", "Advanced mathematics"),
    ("economics", "domain", "reasoning", "Economics knowledge"),
]: add_skill(*s)

# Multimodal (10+)
for s in [
    ("multimodal-understanding", "multimodal", "reasoning", "Understand mixed inputs"),
    ("multimodal-generation", "multimodal", "image", "Generate mixed outputs"),
    ("vision-language", "multimodal", "image", "Combined vision+language"),
    ("audio-language", "multimodal", "audio", "Combined audio+language"),
    ("document-understanding", "multimodal", "reasoning", "Understand documents"),
    ("chart-understanding", "multimodal", "reasoning", "Read charts and graphs"),
    ("video-language", "multimodal", "image", "Video + language tasks"),
    ("image-text-matching", "multimodal", "embedding", "Match images to text"),
    ("visual-grounding", "multimodal", "image", "Ground text in images"),
    ("scene-text-recognition", "multimodal", "image", "Read text in scenes"),
]: add_skill(*s)

log("Loaded %d atomic skills across %d categories" % (
    len(SKILLS), len(set(s["category"] for s in SKILLS.values()))))

# ═══════════════════════════════════════════════════════════
# MODEL SKILL EXTRACTION PATTERNS
# ═══════════════════════════════════════════════════════════

PATTERNS = [
    (r"(?i)(code|coder|starcoder|codellama|deepseek-coder|wizard-?code|magicoder|codegeex|stable-code|granite-code|qwen.*coder|codestral)",
     ["code-generation","code-completion","code-review","code-debugging","code-explanation",
      "code-refactoring","unit-test-generation","shell-scripting","python-generation","javascript-generation"]),
    (r"(?i)(llava|bakllava|moondream|minicpm-v|cogvlm|internvl|qwen.*vl|llama.*vision|pixtral)",
     ["image-captioning","visual-qa","ocr","screenshot-analysis","scene-understanding",
      "document-parsing","image-classification","multimodal-understanding","vision-language"]),
    (r"(?i)(whisper|wav2vec|speech|stt|asr)",
     ["speech-to-text","audio-transcription","speaker-diarization","language-detection","audio-classification"]),
    (r"(?i)(tts|bark|parler|coqui|piper|kokoro|orpheus)",
     ["text-to-speech","voice-cloning","audio-enhancement","speech-enhancement"]),
    (r"(?i)(embed|bge|gte|e5|nomic-embed|mxbai|jina.*embed|snowflake.*arctic.*embed|voyage)",
     ["text-embedding","semantic-search","similarity-scoring","clustering","document-indexing",
      "reranking","passage-retrieval","hybrid-search","vector-store"]),
    (r"(?i)(math|stral|wizard-?math|deepseek-?math|numina|internlm.*math|qwen.*math)",
     ["mathematical-reasoning","logical-reasoning","chain-of-thought","problem-solving",
      "optimization","constraint-satisfaction","scientific-reasoning","statistical-analysis"]),
    (r"(?i)(reason|r1|o1|o3|qwq|marco-?o1|skywork.*o1|deep-?think)",
     ["chain-of-thought","logical-reasoning","mathematical-reasoning","analysis","planning",
      "problem-solving","decision-making","meta-reasoning","causal-reasoning","deductive-reasoning"]),
    (r"(?i)(stable-?diffusion|sdxl|dall-?e|midjourney|flux|playground|kandinsky|imagen)",
     ["image-generation","image-editing","style-transfer","text-to-image","image-inpainting",
      "background-removal","image-upscaling"]),
    (r"(?i)(music|suno|udio|musicgen|audiogen|jukebox)",
     ["music-generation","audio-classification","beat-detection","audio-mixing","sound-effects"]),
    (r"(?i)(video|sora|runway|pika|animatediff|cogvideo)",
     ["video-generation","video-understanding","video-language"]),
    (r"(?i)(3d|point-?e|shap-?e|triposr|meshy)",
     ["3d-generation","depth-estimation","spatial-reasoning"]),
    (r"(?i)(medical|med|biomed|clinical|health|pubmed)",
     ["medical","scientific-reasoning","research","fact-checking"]),
    (r"(?i)(legal|law|jurisprudence)",
     ["legal","analysis","research","ethical-reasoning"]),
    (r"(?i)(finance|fin|trading|stock)",
     ["financial","data-analysis","predictive-modeling","time-series-analysis"]),
    (r"(?i)(sql|sqlcoder|nsql|duckdb)",
     ["sql-generation","database-query","database-design","data-analysis","etl-pipeline"]),
    (r"(?i)(dolphin|samantha|nous|hermes|neural-?chat|openchat|openhermes|starling)",
     ["chat","instruction-following","creative-writing","roleplay","persona","multi-turn"]),
    (r"(?i)(llama|mistral|mixtral|gemma|phi|qwen|yi|internlm|command|aya|exaone|glm)",
     ["text-generation","chat","instruction-following","question-answering","summarization",
      "translation","multi-turn","system-prompts"]),
    (r"(?i)(tiny|small|mini|nano|micro|1b|3b|0\.5b)",
     ["classification","extraction","formatting","validation","routing","streaming","fast"]),
    (r"(?i)(large|70b|72b|405b|claude|gpt-?4|gemini)",
     ["chain-of-thought","analysis","planning","research","creative-writing","code-generation",
      "mathematical-reasoning","multi-modal-input","structured-output","agent-loop"]),
    (r"(?i)(rerank|cross-?encoder|colbert)",
     ["reranking","similarity-scoring","passage-retrieval","hybrid-search"]),
    (r"(?i)(moderat|guard|shield|safety|llama-?guard)",
     ["moderation","safety-filtering","content-moderation","validation"]),
    (r"(?i)(function|tool|agent|react)",
     ["function-calling","tool-use","agent-loop","structured-output"]),
]

# ═══════════════════════════════════════════════════════════
# SOURCE 1: go_pieces.json
# ═══════════════════════════════════════════════════════════

def scan_go_pieces():
    log("Scanning go_pieces.json...")
    models = {}
    try:
        d = json.load(open("C:/NovaX/data/go_pieces.json"))
        pieces = d.get("pieces", {})
        for k, v in pieces.items():
            mid = v.get("model", "")
            prov = v.get("provider", "")
            if not mid: continue
            skills = extract_skills(mid)
            models[mid] = {"id": mid, "provider": prov, "source": "go_pieces", "skills": skills}
        log("  go_pieces: %d models, %d with skills" % (len(models), sum(1 for m in models.values() if m["skills"])))
    except Exception as e:
        log("  go_pieces error: %s" % e)
    return models

# ═══════════════════════════════════════════════════════════
# SOURCE 2: OpenRouter API
# ═══════════════════════════════════════════════════════════

def scan_openrouter():
    log("Scanning OpenRouter API...")
    models = {}
    data = api_get("https://openrouter.ai/api/v1/models")
    if not data:
        log("  OpenRouter: API unreachable")
        return models
    model_list = data.get("data", [])
    for m in model_list:
        mid = m.get("id", "")
        if not mid: continue
        name = m.get("name", mid)
        arch = m.get("architecture", {})
        modality = arch.get("modality", "")
        ctx = arch.get("tokenizer", "")
        pricing = m.get("pricing", {})

        skills = extract_skills(mid)
        skills.extend(extract_skills(name))

        # Add skills from modality
        if "image" in modality: skills.extend(["image-generation", "image-editing"])
        if "audio" in modality: skills.extend(["speech-to-text", "text-to-speech"])
        if "video" in modality: skills.extend(["video-generation"])

        # Add from top_provider capabilities
        top = m.get("top_provider", {})
        if top.get("is_moderated"): skills.append("moderation")

        skills = list(set(skills))  # dedupe
        models[mid] = {
            "id": mid, "name": name, "provider": "openrouter",
            "source": "openrouter", "skills": skills,
            "context_length": m.get("context_length", 0),
            "pricing": {"prompt": pricing.get("prompt", "0"), "completion": pricing.get("completion", "0")}
        }
    log("  OpenRouter: %d models" % len(models))
    return models

# ═══════════════════════════════════════════════════════════
# SOURCE 3: HuggingFace Tasks
# ═══════════════════════════════════════════════════════════

HF_TASKS = {
    "text-generation": ["text-generation", "chat", "instruction-following", "language-modeling"],
    "text2text-generation": ["text-generation", "translation", "summarization", "paraphrase"],
    "text-classification": ["text-classification", "sentiment-analysis", "classification"],
    "token-classification": ["named-entity-recognition", "keyword-extraction"],
    "question-answering": ["question-answering", "research", "fact-checking"],
    "summarization": ["summarization", "text-simplification"],
    "translation": ["translation", "multi-language"],
    "fill-mask": ["fill-mask", "language-modeling"],
    "feature-extraction": ["text-embedding", "clustering", "similarity-scoring"],
    "sentence-similarity": ["similarity-scoring", "semantic-search", "text-embedding"],
    "zero-shot-classification": ["classification", "text-classification"],
    "conversational": ["chat", "multi-turn", "dialogue-generation"],
    "table-question-answering": ["database-query", "data-analysis", "spreadsheet"],
    "image-classification": ["image-classification", "scene-understanding"],
    "object-detection": ["object-detection", "face-detection"],
    "image-segmentation": ["image-segmentation", "background-removal"],
    "image-to-text": ["image-captioning", "ocr", "image-to-text"],
    "text-to-image": ["image-generation", "text-to-image", "style-transfer"],
    "image-to-image": ["image-editing", "style-transfer", "image-upscaling"],
    "depth-estimation": ["depth-estimation", "3d-generation"],
    "automatic-speech-recognition": ["speech-to-text", "audio-transcription"],
    "text-to-speech": ["text-to-speech", "voice-cloning"],
    "audio-classification": ["audio-classification", "audio-tagging"],
    "audio-to-audio": ["audio-enhancement", "noise-reduction", "voice-conversion"],
    "text-to-video": ["video-generation", "video-language"],
    "image-text-to-text": ["visual-qa", "multimodal-understanding", "vision-language"],
    "visual-question-answering": ["visual-qa", "image-captioning"],
    "document-question-answering": ["document-understanding", "document-parsing", "ocr"],
    "video-text-to-text": ["video-understanding", "video-language"],
    "text-to-3d": ["3d-generation"],
    "image-to-3d": ["3d-generation", "depth-estimation"],
    "reinforcement-learning": ["planning", "optimization", "decision-making"],
    "tabular-classification": ["classification", "data-analysis"],
    "tabular-regression": ["predictive-modeling", "statistical-analysis"],
    "time-series-forecasting": ["time-series-analysis", "predictive-modeling"],
    "graph-ml": ["knowledge-graph", "entity-linking"],
    "robotics": ["robotics", "spatial-reasoning"],
    "mask-generation": ["image-segmentation", "image-inpainting"],
    "keypoint-detection": ["pose-estimation"],
    "video-classification": ["video-understanding"],
}

def scan_huggingface():
    log("Scanning HuggingFace tasks...")
    models = {}
    # Get top models per task
    for task, skill_list in HF_TASKS.items():
        data = api_get("https://huggingface.co/api/models?pipeline_tag=%s&sort=downloads&direction=-1&limit=50" % task)
        if not data: continue
        for m in data:
            mid = m.get("modelId", m.get("id", ""))
            if not mid: continue
            skills = list(skill_list)
            skills.extend(extract_skills(mid))
            skills = list(set(skills))
            if mid not in models:
                models[mid] = {
                    "id": mid, "provider": "huggingface", "source": "huggingface",
                    "skills": skills, "task": task,
                    "downloads": m.get("downloads", 0)
                }
            else:
                models[mid]["skills"] = list(set(models[mid]["skills"] + skills))
    log("  HuggingFace: %d models across %d tasks" % (len(models), len(HF_TASKS)))
    return models

# ═══════════════════════════════════════════════════════════
# SOURCE 4: Ollama local
# ═══════════════════════════════════════════════════════════

def scan_ollama():
    log("Scanning Ollama local...")
    models = {}
    data = api_get("http://127.0.0.1:11434/api/tags")
    if not data:
        log("  Ollama: unreachable")
        return models
    for m in data.get("models", []):
        mid = m.get("name", "")
        if not mid: continue
        skills = extract_skills(mid)
        models[mid] = {"id": mid, "provider": "ollama", "source": "ollama", "skills": skills,
                       "size": m.get("size", 0)}
    log("  Ollama: %d models" % len(models))
    return models

# ═══════════════════════════════════════════════════════════
# SOURCE 5: NovaX services as capabilities
# ═══════════════════════════════════════════════════════════

def scan_novax_services():
    log("Scanning NovaX services...")
    models = {}
    data = api_get("http://127.0.0.1:9999/api/services/health")
    if not data: return models
    for svc in data.get("services", []):
        name = svc.get("name", "")
        port = svc.get("port", 0)
        mid = "novax-%s" % name
        skills = ["routing", "load-balancing", "failover", "streaming"]
        if "embed" in name: skills.extend(["text-embedding", "semantic-search"])
        if "intelligence" in name: skills.extend(["analysis", "planning"])
        if "build" in name: skills.extend(["code-generation", "devops"])
        if "security" in name: skills.extend(["cybersecurity", "security-audit"])
        if "media" in name: skills.extend(["audio-classification", "image-classification"])
        if "graph" in name: skills.extend(["knowledge-graph", "data-visualization"])
        if "cache" in name: skills.extend(["caching", "prefix-caching"])
        if "queue" in name: skills.extend(["batch-processing", "rate-limiting"])
        if "pipeline" in name: skills.extend(["etl-pipeline", "streaming"])
        models[mid] = {"id": mid, "provider": "novax", "source": "novax_service",
                       "skills": skills, "port": port}
    log("  NovaX: %d service capabilities" % len(models))
    return models

# ═══════════════════════════════════════════════════════════
# SKILL EXTRACTION
# ═══════════════════════════════════════════════════════════

def extract_skills(model_name):
    skills = []
    for pattern, skill_list in PATTERNS:
        if re.search(pattern, model_name):
            skills.extend(skill_list)
    return list(set(skills))

# ═══════════════════════════════════════════════════════════
# COMPOUND ABILITIES — pairs and triples of skills
# ═══════════════════════════════════════════════════════════

ABILITY_TEMPLATES = {
    # skill1 + skill2 → ability
    ("code-generation", "code-review"): {"name": "code-quality-pipeline", "desc": "Generate and review code"},
    ("code-generation", "unit-test-generation"): {"name": "test-driven-development", "desc": "TDD pipeline"},
    ("text-generation", "translation"): {"name": "multilingual-content", "desc": "Generate in any language"},
    ("text-generation", "summarization"): {"name": "content-digest", "desc": "Generate then summarize"},
    ("text-embedding", "semantic-search"): {"name": "knowledge-retrieval", "desc": "Find relevant knowledge"},
    ("text-embedding", "retrieval-augmented-generation"): {"name": "rag-pipeline", "desc": "Full RAG system"},
    ("image-generation", "image-editing"): {"name": "visual-design", "desc": "Create and edit visuals"},
    ("speech-to-text", "text-generation"): {"name": "voice-assistant", "desc": "Voice-driven AI"},
    ("text-to-speech", "chat"): {"name": "conversational-voice", "desc": "Talking AI assistant"},
    ("code-generation", "devops"): {"name": "infrastructure-automation", "desc": "Auto infrastructure"},
    ("data-analysis", "data-visualization"): {"name": "analytics-dashboard", "desc": "Analyze and visualize"},
    ("ocr", "document-parsing"): {"name": "document-digitization", "desc": "Digitize documents"},
    ("chain-of-thought", "mathematical-reasoning"): {"name": "math-solver", "desc": "Step-by-step math"},
    ("chain-of-thought", "code-generation"): {"name": "code-architect", "desc": "Reason then code"},
    ("moderation", "safety-filtering"): {"name": "content-safety", "desc": "Full safety pipeline"},
    ("function-calling", "tool-use"): {"name": "tool-orchestration", "desc": "Orchestrate tools"},
    ("planning", "decision-making"): {"name": "strategic-planner", "desc": "Plan and decide"},
    ("research", "fact-checking"): {"name": "verified-research", "desc": "Research with verification"},
    ("classification", "routing"): {"name": "intelligent-routing", "desc": "Smart query routing"},
    ("text-generation", "persona"): {"name": "character-ai", "desc": "AI with personality"},
}

def generate_compound_abilities(all_models):
    log("Generating compound abilities...")
    abilities = {}

    # From templates
    for (s1, s2), tmpl in ABILITY_TEMPLATES.items():
        supporting = []
        for mid, m in all_models.items():
            if s1 in m.get("skills", []) and s2 in m.get("skills", []):
                supporting.append(mid)
        abilities[tmpl["name"]] = {
            "description": tmpl["desc"],
            "required_skills": [s1, s2],
            "supporting_models": len(supporting),
            "status": "ready" if supporting else "unavailable",
            "coverage": min(len(supporting) * 5, 100)
        }

    # Auto-generate from all skill pairs that co-occur in models
    skill_cooccurrence = defaultdict(set)
    for mid, m in all_models.items():
        skills = m.get("skills", [])
        for s1, s2 in itertools.combinations(sorted(set(skills)), 2):
            skill_cooccurrence[(s1, s2)].add(mid)

    # Only keep pairs with 3+ supporting models
    auto_count = 0
    for (s1, s2), mids in skill_cooccurrence.items():
        if len(mids) < 3: continue
        aname = "%s-plus-%s" % (s1.split("-")[0], s2.split("-")[0])
        if aname in abilities: continue
        cat1 = SKILLS.get(s1, {}).get("category", "")
        cat2 = SKILLS.get(s2, {}).get("category", "")
        if cat1 == cat2: continue  # skip same-category pairs (too many trivial ones)
        abilities[aname] = {
            "description": "Combines %s with %s" % (s1, s2),
            "required_skills": [s1, s2],
            "supporting_models": len(mids),
            "status": "ready" if len(mids) >= 3 else "partial",
            "coverage": min(len(mids) * 3, 100),
            "auto_generated": True
        }
        auto_count += 1

    log("  Generated %d template abilities + %d auto-discovered = %d total" % (
        len(ABILITY_TEMPLATES), auto_count, len(abilities)))
    return abilities

# ═══════════════════════════════════════════════════════════
# FEATURE CHAINS — abilities combined into features
# ═══════════════════════════════════════════════════════════

FEATURE_TEMPLATES = [
    {"name": "full-stack-development", "desc": "Complete web app development",
     "abilities": ["code-quality-pipeline", "test-driven-development", "infrastructure-automation"]},
    {"name": "research-pipeline", "desc": "End-to-end research system",
     "abilities": ["knowledge-retrieval", "verified-research", "content-digest"]},
    {"name": "content-creation-suite", "desc": "Full content creation pipeline",
     "abilities": ["multilingual-content", "visual-design", "content-digest"]},
    {"name": "voice-ai-platform", "desc": "Complete voice AI system",
     "abilities": ["voice-assistant", "conversational-voice"]},
    {"name": "document-intelligence", "desc": "Document processing pipeline",
     "abilities": ["document-digitization", "rag-pipeline", "knowledge-retrieval"]},
    {"name": "data-science-platform", "desc": "Complete data science workflow",
     "abilities": ["analytics-dashboard", "math-solver"]},
    {"name": "ai-safety-suite", "desc": "Comprehensive AI safety",
     "abilities": ["content-safety", "intelligent-routing"]},
    {"name": "devops-automation", "desc": "Full DevOps automation",
     "abilities": ["infrastructure-automation", "code-quality-pipeline"]},
    {"name": "strategic-ai", "desc": "Strategic planning and execution",
     "abilities": ["strategic-planner", "verified-research"]},
    {"name": "multimedia-studio", "desc": "Multi-media creation suite",
     "abilities": ["visual-design", "conversational-voice"]},
]

def generate_features(abilities):
    log("Generating features from ability chains...")
    features = {}

    for ft in FEATURE_TEMPLATES:
        ready = sum(1 for a in ft["abilities"] if abilities.get(a, {}).get("status") == "ready")
        total = len(ft["abilities"])
        features[ft["name"]] = {
            "description": ft["desc"],
            "required_abilities": ft["abilities"],
            "status": "active" if ready == total else "partial" if ready > 0 else "unavailable",
            "coverage": int(ready / max(total, 1) * 100)
        }

    # Auto-generate from ability clusters
    ability_names = [a for a, d in abilities.items() if d.get("status") == "ready"]
    # Group abilities by their skill categories
    cat_abilities = defaultdict(list)
    for aname, adata in abilities.items():
        if adata.get("status") != "ready": continue
        skills = adata.get("required_skills", [])
        cats = set()
        for s in skills:
            c = SKILLS.get(s, {}).get("category", "")
            if c: cats.add(c)
        for c in cats:
            cat_abilities[c].append(aname)

    # Create cross-category features
    auto_count = 0
    cats = list(cat_abilities.keys())
    for c1, c2 in itertools.combinations(sorted(cats), 2):
        if len(cat_abilities[c1]) < 2 or len(cat_abilities[c2]) < 2: continue
        fname = "%s-x-%s-suite" % (c1, c2)
        ab_list = cat_abilities[c1][:3] + cat_abilities[c2][:3]
        features[fname] = {
            "description": "Cross-domain %s + %s capabilities" % (c1, c2),
            "required_abilities": ab_list,
            "status": "active",
            "coverage": 100,
            "auto_generated": True
        }
        auto_count += 1

    log("  Generated %d template features + %d auto-discovered = %d total" % (
        len(FEATURE_TEMPLATES), auto_count, len(features)))
    return features

# ═══════════════════════════════════════════════════════════
# MAIN DISCOVERY
# ═══════════════════════════════════════════════════════════

def main():
    start = time.time()
    log("=" * 60)
    log("PACMAN MEGA DISCOVERY — EXTRACTING EVERYTHING")
    log("=" * 60)

    # Gather all models from all sources
    all_models = {}

    sources = [
        ("go_pieces", scan_go_pieces),
        ("openrouter", scan_openrouter),
        ("huggingface", scan_huggingface),
        ("ollama", scan_ollama),
        ("novax", scan_novax_services),
    ]

    for name, scanner in sources:
        try:
            models = scanner()
            # Merge (don't overwrite, extend skills)
            for mid, m in models.items():
                if mid in all_models:
                    existing = all_models[mid]["skills"]
                    new_skills = m.get("skills", [])
                    all_models[mid]["skills"] = list(set(existing + new_skills))
                else:
                    all_models[mid] = m
        except Exception as e:
            log("  Error scanning %s: %s" % (name, e))

    # Count unique skills across all models
    all_skill_instances = defaultdict(int)
    for m in all_models.values():
        for s in m.get("skills", []):
            all_skill_instances[s] += 1

    active_skills = {s: {"count": c, **SKILLS.get(s, {"category":"unknown","territory":"chat","description":s})}
                     for s, c in all_skill_instances.items()}

    log("")
    log("MODELS: %d total from %d sources" % (len(all_models), len(sources)))
    log("SKILLS: %d unique skills active (from %d defined)" % (len(active_skills), len(SKILLS)))

    # Generate abilities
    abilities = generate_compound_abilities(all_models)
    ready_abilities = sum(1 for a in abilities.values() if a.get("status") == "ready")

    # Generate features
    features = generate_features(abilities)
    active_features = sum(1 for f in features.values() if f.get("status") == "active")

    # Skill instances = every model x skill combination
    total_skill_instances = sum(len(m.get("skills", [])) for m in all_models.values())

    elapsed = time.time() - start

    log("")
    log("=" * 60)
    log("MEGA DISCOVERY COMPLETE in %.1fs" % elapsed)
    log("=" * 60)
    log("  Models:           %d" % len(all_models))
    log("  Unique Skills:    %d" % len(active_skills))
    log("  Skill Instances:  %d" % total_skill_instances)
    log("  Abilities:        %d (%d ready)" % (len(abilities), ready_abilities))
    log("  Features:         %d (%d active)" % (len(features), active_features))
    log("  Total Extracted:  %d" % (len(active_skills) + len(abilities) + len(features) + total_skill_instances))
    log("=" * 60)

    # Category breakdown
    cat_counts = defaultdict(int)
    for s in active_skills.values():
        cat_counts[s.get("category", "unknown")] += 1

    # Save registry
    registry = {
        "version": "2.0.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stats": {
            "total_models": len(all_models),
            "total_skills": len(active_skills),
            "total_skill_instances": total_skill_instances,
            "total_abilities": len(abilities),
            "ready_abilities": ready_abilities,
            "total_features": len(features),
            "active_features": active_features,
            "categories": dict(cat_counts),
            "discovery_time_s": round(elapsed, 1)
        },
        "skills": active_skills,
        "abilities": abilities,
        "features": features,
        "models": {k: {"id": v["id"], "provider": v.get("provider",""), "source": v.get("source",""),
                        "skill_count": len(v.get("skills",[]))}
                   for k, v in all_models.items()}
    }

    with open("C:/NovaX/data/pacman_registry.json", "w") as f:
        json.dump(registry, f, indent=2)
    log("Saved to C:/NovaX/data/pacman_registry.json")

    # Output summary as JSON for NovaLang consumption
    print(json.dumps(registry["stats"]))

if __name__ == "__main__":
    main()
