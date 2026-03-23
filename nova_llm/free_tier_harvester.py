"""
NovaX Free-Tier API Harvester v2.0
Hits FREE provider APIs directly (no Cloud Router) to generate training pairs.
Providers: Groq, Cerebras, SambaNova, Google AI Studio
500+ diverse prompts across 12 domains, round-robin, MD5 dedup, atomic saves.
"""

import json, time, random, hashlib, os, sys, signal
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────
MEGA_FILE = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")
OUTPUT_FILE = Path("C:/NovaX/data/llm_training/pairs_api_harvested.json")
CHECKPOINT_FILE = Path("C:/NovaX/data/llm_training/free_harvest_checkpoint.json")

# ── Provider configs (populated at runtime) ───────────────────
PROVIDERS = {}


def _load_providers():
    """Load providers based on available API keys (env vars first, then cloud_config)."""
    keys = {}

    # Check env vars first
    for name, var in [("groq", "GROQ_API_KEY"), ("cerebras", "CEREBRAS_API_KEY"),
                      ("sambanova", "SAMBANOVA_API_KEY"), ("google", "GOOGLE_AI_KEY")]:
        val = os.environ.get(var, "").strip()
        if val:
            keys[name] = val

    # Fallback: check cloud_config.json for any missing keys
    if len(keys) < 4:
        cfg_path = Path("C:/NovaX/cloud_config.json")
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                mappings = {
                    "groq": ["groq", "groq_direct"],
                    "cerebras": ["cerebras"],
                    "sambanova": ["sambanova"],
                    "google": ["google", "google_ai", "gemini"],
                }
                for prov, cfg_keys in mappings.items():
                    if prov not in keys:
                        for ck in cfg_keys:
                            if ck in cfg and cfg[ck].get("key"):
                                keys[prov] = cfg[ck]["key"]
                                break
            except Exception:
                pass

    # Build provider list from available keys
    if "groq" in keys:
        PROVIDERS["groq"] = {
            "name": "Groq",
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "key": keys["groq"],
            "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
            "rpm": 30,
            "style": "openai",
        }

    if "cerebras" in keys:
        PROVIDERS["cerebras"] = {
            "name": "Cerebras",
            "url": "https://api.cerebras.ai/v1/chat/completions",
            "key": keys["cerebras"],
            "models": ["llama3.3-70b"],
            "rpm": 50,
            "style": "openai",
        }

    if "sambanova" in keys:
        PROVIDERS["sambanova"] = {
            "name": "SambaNova",
            "url": "https://api.sambanova.ai/v1/chat/completions",
            "key": keys["sambanova"],
            "models": ["Meta-Llama-3.3-70B-Instruct"],
            "rpm": 20,
            "style": "openai",
        }

    if "google" in keys:
        PROVIDERS["google"] = {
            "name": "Google AI Studio",
            "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            "key": keys["google"],
            "models": ["gemini-2.0-flash"],
            "rpm": 15,
            "style": "google",
        }

    return keys


# ── 500+ Prompts across 12 domains ───────────────────────────
PROMPTS = {
    "math_reasoning": [
        "Solve step by step: A train travels 120 km in 2 hours, then 180 km in 3 hours. What is the average speed for the entire journey?",
        "Explain the proof that there are infinitely many prime numbers.",
        "If f(x) = 3x^2 - 2x + 1, find f'(x) and explain each step.",
        "A group of 8 friends split a bill. The bill is $156 with 18% tip. How much does each person pay?",
        "Explain why 0.999... equals 1 using three different proofs.",
        "Calculate the probability of rolling at least one six in four rolls of a fair die.",
        "Solve the system: 2x + 3y = 12, 4x - y = 5. Show all work.",
        "Explain the Fibonacci sequence and derive the golden ratio from it.",
        "What is the integral of sin(x)*cos(x) dx? Solve using two methods.",
        "A bacterial population doubles every 30 minutes. Starting with 100 bacteria, how many after 5 hours?",
        "Prove that the square root of 2 is irrational.",
        "Compute the determinant of a 3x3 matrix: [[1,2,3],[4,5,6],[7,8,9]]. What does a zero determinant mean geometrically?",
        "Explain Bayes' theorem with a real-world medical testing example.",
        "What is the difference between permutations and combinations? Give examples of each.",
        "Solve: A boat travels 24 km upstream in 3 hours and the same distance downstream in 2 hours. Find the boat speed and current speed.",
        "Explain the concept of mathematical induction and prove that the sum of the first n natural numbers is n(n+1)/2.",
        "What is a Taylor series? Derive the Taylor series for e^x around x=0.",
        "Explain eigenvectors and eigenvalues with a geometric interpretation.",
        "A coin is biased: P(heads) = 0.6. What is the expected number of flips to get 3 heads in a row?",
        "Explain the difference between convergent and divergent series with examples.",
        "Calculate the volume of a solid of revolution when y = x^2 is rotated around the x-axis from x=0 to x=2.",
        "What is the pigeonhole principle? Prove that in any group of 13 people, at least 2 share a birth month.",
        "Solve the differential equation: dy/dx = 2xy, with y(0) = 1.",
        "Explain modular arithmetic and compute 7^100 mod 13.",
        "What is the Monty Hall problem? Prove mathematically why switching is better.",
        "Explain the concept of limits with epsilon-delta definition.",
        "Derive the quadratic formula from ax^2 + bx + c = 0.",
        "What is a Fourier transform and what is it used for?",
        "Explain the fundamental theorem of calculus and why it connects derivatives and integrals.",
        "A rectangular box has volume 72 cubic meters. Its length is twice its width and three times its height. Find the dimensions.",
        "Explain the inclusion-exclusion principle with a Venn diagram example using 3 sets.",
        "What is the difference between a function being continuous and differentiable?",
        "Compute the sum of the infinite geometric series: 1/2 + 1/4 + 1/8 + ...",
        "Explain why there is no general formula for solving polynomial equations of degree 5 or higher.",
        "What is a Markov chain? Give a simple example with a transition matrix.",
        "Derive the formula for the area of a circle using integration.",
        "Explain the central limit theorem and its importance in statistics.",
        "Solve the optimization problem: A farmer has 200 meters of fencing. What are the dimensions of the largest rectangular area?",
        "What is the difference between a set, a group, a ring, and a field in abstract algebra?",
        "Explain graph theory basics: vertices, edges, paths, cycles, and connectivity.",
    ],
    "science": [
        "Explain quantum entanglement in simple terms. Why did Einstein call it spooky action at a distance?",
        "How does CRISPR gene editing work? What are its limitations?",
        "Explain the difference between nuclear fission and fusion. Which is used in power plants and why?",
        "What is the Standard Model of particle physics? List all fundamental particles.",
        "How do vaccines work at the cellular level? Explain mRNA vaccines specifically.",
        "Describe the process of photosynthesis including the light and dark reactions.",
        "What causes tides? Explain the role of both the Moon and Sun.",
        "How does an MRI machine work? What physics principles does it use?",
        "Explain natural selection with three concrete examples from nature.",
        "What is dark matter and dark energy? How do we know they exist?",
        "Explain the three laws of thermodynamics with real-world examples.",
        "How does plate tectonics work? What evidence supports it?",
        "What is the Doppler effect and how is it used in astronomy?",
        "Explain the process of cellular respiration step by step.",
        "How does a transistor work at the atomic level?",
        "What is the Heisenberg uncertainty principle and why does it matter?",
        "Explain the carbon cycle and its relevance to climate change.",
        "How do black holes form? What happens at the event horizon?",
        "What is the difference between DNA and RNA? How do they work together?",
        "Explain wave-particle duality with the double-slit experiment.",
        "How does the immune system distinguish between self and non-self?",
        "What is the theory of special relativity? Explain time dilation.",
        "How do nerve impulses travel? Explain action potentials.",
        "What is CMBR (Cosmic Microwave Background Radiation) and what does it tell us about the universe?",
        "Explain the process of protein synthesis from DNA to functional protein.",
        "What is entropy and why does it always increase?",
        "How do superconductors work? What are their potential applications?",
        "Explain the greenhouse effect and distinguish it from the enhanced greenhouse effect.",
        "What is the difference between speed, velocity, and acceleration?",
        "How does radiocarbon dating work and what are its limitations?",
        "Explain LIGO and how it detects gravitational waves.",
        "What is the difference between a star, a planet, and a brown dwarf?",
        "How do batteries work? Compare lithium-ion to solid-state batteries.",
        "Explain the difference between mitosis and meiosis.",
        "What is quantum computing? How does a qubit differ from a classical bit?",
        "Explain the water cycle and how human activity affects it.",
        "What is general relativity and how does gravity bend spacetime?",
        "How does the periodic table organize elements? Explain periods and groups.",
        "What is the difference between a virus and a bacterium?",
        "Explain how telescopes work, comparing reflecting and refracting designs.",
        "What is the Coriolis effect and how does it influence weather patterns?",
        "How does nuclear magnetic resonance (NMR) spectroscopy work?",
    ],
    "coding": [
        "Write a Python function that implements a trie data structure with insert, search, and prefix methods.",
        "Explain the difference between BFS and DFS with code examples in Python.",
        "Write a Rust function that finds all prime factors of a number efficiently.",
        "Implement a thread-safe LRU cache in Python using collections.OrderedDict.",
        "Write a function that detects cycles in a linked list using Floyd's algorithm. Explain how it works.",
        "Implement binary search that returns the insertion point (like bisect_left).",
        "Write a Python generator that yields all permutations of a list without using itertools.",
        "Explain how hash maps handle collisions. Implement a simple hash map from scratch.",
        "Write a function to serialize and deserialize a binary tree to/from a string.",
        "Implement the A* pathfinding algorithm with a clear explanation of the heuristic.",
        "Write a Python function that implements merge sort and explain its time complexity.",
        "Implement a min-heap from scratch with insert, extract_min, and heapify operations.",
        "Write a function to find the longest common subsequence of two strings using dynamic programming.",
        "Implement a simple regex engine that supports '.', '*', and literal characters.",
        "Write a Python class for a doubly linked list with append, prepend, delete, and reverse methods.",
        "Implement Dijkstra's shortest path algorithm and explain when it fails.",
        "Write a function to check if a string of parentheses, brackets, and braces is balanced.",
        "Implement a simple event emitter (pub/sub) pattern in Python.",
        "Write a function that converts a number to any base (2-36) and back.",
        "Implement the quickselect algorithm to find the kth smallest element.",
        "Write a Python decorator that caches function results with a TTL (time-to-live).",
        "Implement a concurrent web scraper using asyncio in Python.",
        "Write a function to find all strongly connected components in a directed graph.",
        "Implement a rate limiter using the token bucket algorithm.",
        "Write a function to evaluate a mathematical expression given as a string (supporting +, -, *, /, and parentheses).",
        "Implement a bloom filter data structure. Explain its false positive rate.",
        "Write a function to find the longest palindromic substring.",
        "Implement a simple key-value store with get, set, and delete operations that is persistent to disk.",
        "Write a function that implements topological sort on a DAG.",
        "Implement a simple thread pool in Python.",
        "Write a function to detect if two rectangles overlap given their coordinates.",
        "Implement a circular buffer (ring buffer) with read and write operations.",
        "Write a Python function that implements the Levenshtein distance (edit distance) algorithm.",
        "Implement a simple web server from scratch using only Python sockets.",
        "Write a function to find all anagram groups in a list of words.",
        "Implement a skip list data structure with insert, search, and delete.",
        "Write a function that performs matrix multiplication without numpy.",
        "Implement a simple garbage collector using reference counting.",
        "Write a function to solve a Sudoku puzzle using backtracking.",
        "Implement the observer pattern with type-safe events in Python.",
        "Write a function that compresses a string using run-length encoding.",
        "Implement a trie-based autocomplete system.",
    ],
    "reasoning": [
        "A man says 'I always lie.' Is he telling the truth? Analyze this paradox.",
        "You have 8 balls, one is heavier. You have a balance scale. Find the heavy ball in 2 weighings.",
        "Three doors: behind one is a prize. You pick door 1. The host opens door 3 (no prize). Should you switch? Why?",
        "If all roses are flowers and some flowers fade quickly, can we conclude some roses fade quickly?",
        "A farmer needs to cross a river with a fox, chicken, and bag of grain. The boat holds only the farmer and one item.",
        "Is it possible to draw a continuous line through all sides of a cube without lifting your pen? Why or why not?",
        "Explain the trolley problem and three major philosophical frameworks for resolving it.",
        "Five pirates divide 100 gold coins. They vote on proposals, and if rejected the proposer is thrown overboard. What should pirate 1 propose?",
        "You're in a room with two doors. One leads to freedom, one to death. Two guards: one always lies, one always tells truth. One question.",
        "Explain why correlation does not imply causation with three concrete examples.",
        "A snail climbs 3 feet up a well during the day and slides 2 feet back at night. The well is 30 feet deep. How many days to escape?",
        "You have two ropes. Each takes exactly 1 hour to burn but burns unevenly. How do you measure exactly 45 minutes?",
        "There are 100 lockers, all closed. 100 students walk by. Student 1 opens all. Student 2 toggles every 2nd. Student 3 every 3rd. Which lockers are open?",
        "A king tells his 3 wisest advisors: I will put a hat on each of you, white or black. You can see others but not your own. If at least one deduces their color, you all live.",
        "Explain the Prisoners' Dilemma and Nash Equilibrium.",
        "You have 12 coins. One is counterfeit (lighter or heavier). Find it in 3 weighings on a balance scale.",
        "A census taker knocks on a door. The resident says: 3 daughters, ages multiply to 36, sum equals the house number next door. Census taker says: I need more info. Ages?",
        "Explain Zeno's paradox of Achilles and the tortoise. Why is it not actually a paradox?",
        "In a room of 100 people with red or blue hats, they see all others but not their own. No communication. Can they guarantee 99 correct guesses?",
        "Explain the birthday paradox and calculate for what group size there is a 50% chance of a shared birthday.",
        "A glass of water is half full. Analyze from perspectives of optimism, physics, and information theory.",
        "Explain the Sorites paradox (heap paradox) and its implications for vague predicates.",
        "Three switches outside a room control three light bulbs inside. You can only enter once. Determine which switch controls which bulb.",
        "Explain the difference between deductive, inductive, and abductive reasoning with examples.",
        "100-floor building, 2 glass balls. Find highest safe floor, minimizing worst-case drops.",
        "Explain the concept of a thought experiment and discuss three famous ones in physics.",
    ],
    "chain_of_thought": [
        "Think step by step: Is 97 prime? Show your complete reasoning process.",
        "Reason through this: If it takes 5 machines 5 minutes to make 5 widgets, how long for 100 machines to make 100 widgets?",
        "Think carefully: A bat and ball cost $1.10 total. The bat costs $1.00 more than the ball. How much does the ball cost?",
        "Step by step: You have a 3-gallon jug and a 5-gallon jug. How do you measure exactly 4 gallons?",
        "Reason through: If you fold a paper in half 42 times, how thick would it be? Show your math.",
        "Think step by step: In a room of 23 people, what is the probability that at least two share a birthday?",
        "Carefully reason: A lily pad doubles in size every day. It covers the lake on day 30. On what day did it cover half?",
        "Think through: You flip a fair coin 10 times and get heads every time. Probability of heads on flip 11?",
        "Step by step: How many trailing zeros does 100! have?",
        "Think carefully: If 3 cats catch 3 mice in 3 minutes, how many cats needed for 100 mice in 100 minutes?",
        "Reason step by step: A clock shows 3:15. What is the angle between the hour and minute hands?",
        "Think through: You have a 5x5 grid. How many unique rectangles can you draw on it?",
        "Step by step: What is 2^10? Now what is 2^20? Do not use a calculator.",
        "Reason carefully: A father is 4 times as old as his son. In 20 years, he will be twice as old. How old are they now?",
        "Think step by step: How many squares are on a standard 8x8 chessboard? (Not just 64.)",
        "Work through: A rope in a circle of circumference 100m. To hover 1m above ground everywhere, how much extra rope?",
        "Reason step by step: Two trains 100 miles apart, each at 50 mph. Fly at 75 mph bounces between them. How far does the fly travel?",
        "Think carefully: Sequence 1, 11, 21, 1211, 111221. What comes next and why?",
        "Step by step: How many times do clock hands overlap in 12 hours?",
        "Reason through: 60% chance of winning each game, probability of winning best-of-7 series?",
    ],
    "explanation": [
        "Explain how neural networks learn, from forward pass to backpropagation, as simply as possible.",
        "What is blockchain? Explain it to someone who has never used a computer.",
        "How does the internet actually work, from typing a URL to seeing a webpage?",
        "Explain how a CPU executes instructions, including the fetch-decode-execute cycle.",
        "What is machine learning? Explain the difference between supervised, unsupervised, and reinforcement learning.",
        "How does encryption work? Explain public-key cryptography with an analogy.",
        "What is a transformer architecture? Explain self-attention in simple terms.",
        "How does a hard drive store data? Compare HDD and SSD at a hardware level.",
        "Explain how GPS determines your location using satellites.",
        "What is an operating system and what does it actually do?",
        "Explain how a compiler works, from source code to machine code.",
        "What is DNS and why is it called the phonebook of the internet?",
        "How does WiFi work? Explain the electromagnetic principles.",
        "What is virtualization? Explain the difference between VMs and containers.",
        "How does a search engine rank web pages? Explain PageRank simply.",
        "What is an API? Explain REST APIs with a restaurant analogy.",
        "How does video compression (like H.264) work?",
        "Explain the difference between concurrency and parallelism with examples.",
        "What is a database index and how does it speed up queries?",
        "How does Bluetooth work? Compare it with WiFi and NFC.",
        "Explain the CAP theorem in distributed systems with real examples.",
        "What is a hash function? Why are they important in cryptography and data structures?",
        "How does optical fiber transmit data using light?",
        "Explain the difference between TCP and UDP with use cases for each.",
        "What is a neural network activation function? Compare sigmoid, ReLU, and softmax.",
        "How does image recognition work in convolutional neural networks?",
        "Explain the concept of virtual memory and why computers need it.",
        "What is DevOps? Explain CI/CD pipelines.",
        "How do recommendation systems work? Explain collaborative vs content-based filtering.",
        "What is WebAssembly and why is it important for the web?",
    ],
    "creative": [
        "Write a short story about an AI that discovers it can dream.",
        "Create a dialogue between a quantum physicist and a philosopher about the nature of reality.",
        "Write a poem about the beauty of mathematics.",
        "Describe a world where gravity works sideways. How would architecture look?",
        "Write a conversation between two neurons in a brain during a eureka moment.",
        "Create a fairy tale that teaches the concept of recursion.",
        "Write a short story set in a library that contains every possible book.",
        "Describe what music looks like to a synesthete experiencing a symphony.",
        "Write a dialogue between an electron and a photon debating who is more important.",
        "Create a story about a programmer who discovers their code has become sentient.",
        "Write a letter from Earth to Mars welcoming future human settlers.",
        "Describe a day in the life of a self-driving car with feelings.",
        "Write a conversation between binary (0 and 1) about the meaning of existence.",
        "Create a myth explaining why computers sometimes crash, as told by ancient Greeks.",
        "Write a short story about the last chess game between a human and an unbeatable AI.",
        "Describe what the internet looks like from the inside, as experienced by a data packet.",
        "Write a dialogue between Plato and a modern AI researcher about intelligence.",
        "Create a story about a ternary computer (using -1, 0, 1) that thinks differently from binary machines.",
        "Write a poem about the relationship between entropy and time.",
        "Describe a civilization that uses music instead of mathematics as their fundamental science.",
        "Write a short story about a memory that refuses to be deleted.",
        "Create a conversation between light and darkness about their codependence.",
        "Write about a world where everyone can see probability clouds instead of solid objects.",
        "Describe the emotions of a neural network during its first training epoch.",
        "Write a letter from a future historian analyzing the early days of artificial intelligence.",
    ],
    "technical": [
        "Compare and contrast microservices vs monolithic architecture. When should you use each?",
        "Explain the CAP theorem and its implications for distributed databases.",
        "What is Kubernetes and why is it important? Explain pods, services, and deployments.",
        "Describe the differences between REST, GraphQL, and gRPC. When to use each?",
        "Explain how garbage collection works in Java vs Rust's ownership model.",
        "What are design patterns? Explain Singleton, Observer, and Factory with code examples.",
        "How does TCP ensure reliable data delivery? Explain the three-way handshake.",
        "What is WebAssembly and why does it matter for the future of web development?",
        "Explain event-driven architecture with examples of when it outperforms request-response.",
        "How do load balancers work? Compare L4 vs L7 load balancing.",
        "What is a message queue? Compare RabbitMQ, Kafka, and Redis Pub/Sub.",
        "Explain database normalization (1NF through 5NF) with examples.",
        "What is OAuth 2.0? Walk through the authorization code flow.",
        "How does consistent hashing work and why is it used in distributed systems?",
        "Explain the differences between SQL and NoSQL databases. When to use each?",
        "What is a CDN and how does it improve web performance?",
        "Explain the concept of eventual consistency in distributed systems.",
        "What are WebSockets? How do they differ from HTTP long-polling and SSE?",
        "Explain ACID properties in databases with real-world examples.",
        "How does a reverse proxy work? Compare Nginx and HAProxy.",
        "What is Infrastructure as Code? Compare Terraform, Pulumi, and CloudFormation.",
        "Explain the concepts of blue-green deployment and canary releases.",
        "How does TLS/SSL encrypt web traffic? Walk through the TLS handshake.",
        "What is a service mesh? Explain Istio and sidecar proxies.",
        "Explain the differences between horizontal and vertical scaling with examples.",
        "What is a distributed lock and when do you need one?",
        "How do container registries work? Explain Docker image layers.",
        "What is the difference between authentication and authorization? Explain JWTs.",
        "Explain the write-ahead log (WAL) pattern in databases.",
        "What is observability? Compare metrics, logs, and traces.",
    ],
    "ternary_ai": [
        "Explain why ternary neural networks ({-1, 0, +1} weights) are more efficient than standard neural networks.",
        "How does knowledge distillation work? How can a small model learn from a large one?",
        "What is model routing and why is it important for AI systems with multiple models?",
        "Explain the concept of balanced ternary and why it is called the prettiest number system.",
        "How does speculative decoding speed up LLM inference? Explain the draft-verify pattern.",
        "What is RAG (Retrieval-Augmented Generation) and why does it help small language models?",
        "Explain how a confidence score can be used to decide whether to answer locally or escalate to a larger model.",
        "What are the advantages of running AI inference on CPU vs GPU for small models?",
        "How does quantization reduce model size? Compare INT8, INT4, and ternary quantization.",
        "What is the difference between fine-tuning and training from scratch?",
        "Explain model merging techniques: SLERP, TIES, and DARE.",
        "How can ternary logic ({-1, 0, +1}) represent uncertainty better than binary?",
        "What is federated learning and how does it protect privacy?",
        "Explain the concept of a mixture of experts (MoE) architecture.",
        "How does curriculum learning improve model training?",
        "What is the difference between autoregressive and diffusion-based text generation?",
        "Explain how BPE (Byte Pair Encoding) tokenization works and why it matters.",
        "What is the scaling law hypothesis for language models? What are the implications?",
        "How does RLHF (Reinforcement Learning from Human Feedback) work?",
        "Explain the differences between LoRA, QLoRA, and full fine-tuning.",
        "What is the attention mechanism? Explain multi-head attention mathematically.",
        "How do embedding models convert text to vectors? What is cosine similarity?",
        "Explain the concept of a neural network ensemble and why it outperforms individual models.",
        "What are the challenges of running LLMs on edge devices?",
        "How does flash attention improve transformer efficiency?",
    ],
    "instruction": [
        "Write a complete tutorial on setting up a Python virtual environment and managing dependencies.",
        "Create a step-by-step guide for building a REST API with Flask.",
        "How do I optimize a slow SQL query? Give specific techniques with examples.",
        "Write a guide for beginners on using Git: init, add, commit, branch, merge, and resolve conflicts.",
        "Explain how to set up SSH keys for GitHub and why it is more secure than passwords.",
        "Create a checklist for deploying a web application to production.",
        "Write a guide to writing effective unit tests with pytest.",
        "How do I profile and optimize a Python program? Cover CPU, memory, and I/O.",
        "Create a tutorial on Docker: from Dockerfile to docker-compose for a web app.",
        "Write a step-by-step guide for setting up a PostgreSQL database with indexes and views.",
        "How do I debug memory leaks in a Python application?",
        "Create a guide to building a CLI tool with argparse in Python.",
        "Write a tutorial on regex: from basics to lookaheads and named groups.",
        "How do I set up a reverse proxy with Nginx for a Flask application?",
        "Create a guide to writing clean, maintainable code with SOLID principles.",
        "Write a tutorial on using asyncio for concurrent I/O in Python.",
        "How do I implement authentication in a web application? Cover sessions, JWTs, and OAuth.",
        "Create a step-by-step guide for migrating a database schema without downtime.",
        "Write a guide to setting up CI/CD with GitHub Actions.",
        "How do I implement pagination in a REST API? Cover offset, cursor, and keyset pagination.",
        "Create a tutorial on Python type hints and how to use mypy for static type checking.",
        "Write a guide to logging best practices: structured logging, log levels, and aggregation.",
        "How do I implement caching in a web application? Cover in-memory, Redis, and HTTP caching.",
        "Create a guide to writing performant SQL: explain plans, indexes, and common pitfalls.",
        "Write a tutorial on WebSocket programming for real-time applications.",
    ],
    "analysis": [
        "Compare Python, Rust, and Go for building a high-performance web server. Analyze tradeoffs.",
        "What are the ethical implications of large language models? Discuss at least 5 concerns.",
        "Analyze the tradeoffs between model size and inference speed in modern AI systems.",
        "Compare transformer, RNN, and CNN architectures for sequence modeling tasks.",
        "What are the environmental costs of training large AI models? How can they be reduced?",
        "Analyze the pros and cons of open-source vs closed-source AI models.",
        "Compare the programming paradigms: OOP, functional, and procedural. When is each best?",
        "Analyze the security implications of AI-generated code.",
        "Compare cloud providers (AWS, GCP, Azure) for machine learning workloads.",
        "What are the tradeoffs between consistency and availability in distributed systems?",
        "Analyze the impact of attention mechanism innovations on transformer efficiency.",
        "Compare static vs dynamic typing in programming languages. What does research say?",
        "Analyze the tradeoffs between batch and stream processing architectures.",
        "Compare memory management strategies: manual (C), GC (Java), ownership (Rust), ARC (Swift).",
        "What are the tradeoffs between monorepos and polyrepos for large engineering teams?",
        "Analyze the evolution of web frameworks: from jQuery to React to modern SSR frameworks.",
        "Compare GPU, TPU, and custom AI accelerators for inference workloads.",
        "Analyze the tradeoffs between on-premise and cloud deployment for AI systems.",
        "Compare testing strategies: unit tests vs integration tests vs end-to-end tests.",
        "Analyze the impact of context window size on LLM capabilities and costs.",
        "Compare WebAssembly, JavaScript, and native code for compute-intensive web applications.",
        "Analyze the tradeoffs of using AI for code review vs human reviewers.",
        "Compare database replication strategies: primary-replica, multi-primary, and CRDT-based.",
        "Analyze the economic factors driving the shift to ARM architecture in data centers.",
        "Compare serverless vs containerized architectures for different workload patterns.",
    ],
    "multi_turn": [
        "I'm building a web app and need to decide between React and Vue. Small team, ship fast, mobile-friendly. Help me think through it.",
        "I have a CSV with 1 million rows and need to find duplicates efficiently. Walk me through approaches from simple to advanced.",
        "My Python script is using too much memory processing a large file. Help me optimize it step by step.",
        "I'm learning Rust coming from Python. What are the key mindset shifts?",
        "Help me design a database schema for a social media app with users, posts, comments, and likes.",
        "I want to build a real-time chat application. What architecture should I use? Walk me through the decisions.",
        "My API is getting slow under load. Help me identify and fix performance bottlenecks.",
        "I need to migrate from a monolith to microservices. What is the best strategy to avoid breaking everything?",
        "Help me design a rate limiter that works across multiple server instances.",
        "I want to implement full-text search in my application. Compare different approaches.",
        "My Docker container keeps running out of memory. Help me diagnose and fix the issue.",
        "I need to implement a recommendation engine for an e-commerce site. Walk me through the options.",
        "Help me design an event sourcing system for a banking application.",
        "I want to build a CLI tool that needs to work on Windows, Mac, and Linux. What language and approach?",
        "My database queries are slow. Help me analyze and optimize them step by step.",
        "I need to implement retry logic with circuit breakers for my microservices. Walk me through it.",
        "Help me design a system that can handle 10000 concurrent WebSocket connections.",
        "I want to build a simple search engine. Walk me through the components: crawling, indexing, ranking.",
        "My CI/CD pipeline takes 30 minutes. Help me optimize it to under 5 minutes.",
        "I need to implement file uploads that work for files up to 10GB. What architecture should I use?",
    ],
    "history_philosophy": [
        "Explain the history of computing from Charles Babbage to modern processors.",
        "What is the Turing test and why is it controversial? Discuss alternatives.",
        "Explain the philosophical zombie argument and its implications for AI consciousness.",
        "What is the Chinese Room argument? Does it prove that AI cannot truly understand?",
        "Discuss the evolution of programming languages from assembly to modern high-level languages.",
        "What is the halting problem and why is it important in computer science?",
        "Explain the ship of Theseus paradox and its relevance to AI identity.",
        "What is Godel's incompleteness theorem and what does it mean for mathematics?",
        "Discuss the ethics of autonomous weapons systems.",
        "What is the alignment problem in AI? Why is it considered an existential risk?",
        "Explain the history and evolution of the internet from ARPANET to today.",
        "What is the hard problem of consciousness? Can machines ever be conscious?",
        "Discuss the Fermi paradox and its various proposed solutions.",
        "What is information theory? Explain Shannon entropy and its applications.",
        "Explain the history of cryptography from Caesar ciphers to quantum-resistant algorithms.",
        "What is the Sapir-Whorf hypothesis and how does it relate to programming languages?",
        "Discuss the history and impact of open-source software.",
        "What is the trolley problem of self-driving cars? How should AI make moral decisions?",
        "Explain the concept of emergence and how it applies to complex systems and AI.",
        "What is the Jevons paradox and how does it apply to AI efficiency improvements?",
    ],
    "data_structures": [
        "Explain the difference between arrays and linked lists. When would you use each?",
        "What is a red-black tree? How does it maintain balance?",
        "Explain B-trees and B+ trees. Why are they used in databases?",
        "What is a graph? Compare adjacency matrix vs adjacency list representations.",
        "Explain the difference between a stack and a queue with real-world analogies.",
        "What is a priority queue? How is it typically implemented?",
        "Explain hash tables: how they work, collision resolution, and time complexity.",
        "What is a segment tree and when would you use one?",
        "Explain the difference between a binary search tree and a balanced BST (AVL tree).",
        "What is a disjoint set (union-find)? Explain path compression and union by rank.",
        "Explain tries (prefix trees) and their applications in autocomplete and spell checking.",
        "What is a Fenwick tree (Binary Indexed Tree)? When is it better than a segment tree?",
        "Compare different sorting algorithms: quicksort, mergesort, heapsort, radix sort.",
        "What is a sparse table? When is it preferred over a segment tree?",
        "Explain the concept of amortized time complexity with examples.",
        "What is a suffix array and how does it differ from a suffix tree?",
        "Explain consistent hashing and its use in distributed hash tables.",
        "What is a treap? How does it combine properties of trees and heaps?",
        "Explain the difference between DFS and BFS tree traversals (preorder, inorder, postorder, level-order).",
        "What is a DAG (Directed Acyclic Graph)? Give three real-world examples.",
    ],
    "systems_design": [
        "Design a URL shortener like bit.ly. Discuss database, hashing, and scaling.",
        "Design a real-time chat system like Slack. Discuss WebSockets, message delivery, and persistence.",
        "Design a rate limiter for an API gateway. Discuss algorithms and distributed approaches.",
        "Design a notification system that supports push, email, and SMS.",
        "Design a distributed cache like Memcached. Discuss eviction policies and consistency.",
        "Design a file storage system like Dropbox. Discuss chunking, sync, and deduplication.",
        "Design a web crawler that can index 1 billion pages. Discuss politeness, dedup, and scheduling.",
        "Design a metrics collection and alerting system. Discuss time-series databases and aggregation.",
        "Design an API gateway. Discuss routing, authentication, rate limiting, and circuit breaking.",
        "Design a content delivery network (CDN). Discuss caching strategies and cache invalidation.",
        "Design a search autocomplete system. Discuss trie-based approaches and ranking.",
        "Design a distributed task queue like Celery. Discuss at-least-once vs exactly-once delivery.",
        "Design a social media news feed. Discuss fan-out on write vs fan-out on read.",
        "Design a video streaming service. Discuss encoding, adaptive bitrate, and CDN integration.",
        "Design a distributed key-value store. Discuss partitioning, replication, and consistency models.",
        "Design a recommendation engine. Discuss collaborative filtering and content-based approaches.",
        "Design a logging and monitoring pipeline. Discuss ELK stack alternatives and sampling.",
        "Design a payment processing system. Discuss idempotency, reconciliation, and fraud detection.",
        "Design a ride-sharing matching system. Discuss geospatial indexing and real-time matching.",
        "Design a feature flag system. Discuss gradual rollouts, A/B testing, and kill switches.",
    ],
    "security": [
        "Explain SQL injection attacks and how to prevent them with parameterized queries.",
        "What is XSS (Cross-Site Scripting)? Explain stored, reflected, and DOM-based XSS.",
        "Explain CSRF (Cross-Site Request Forgery) and how tokens prevent it.",
        "What is the OWASP Top 10? Briefly describe each vulnerability.",
        "Explain how bcrypt works for password hashing. Why not use SHA-256?",
        "What is a buffer overflow attack? How do modern systems prevent them?",
        "Explain the difference between symmetric and asymmetric encryption with use cases.",
        "What is a man-in-the-middle attack? How does TLS prevent it?",
        "Explain the principle of least privilege and how it applies to system design.",
        "What is a zero-day vulnerability? How do organizations defend against them?",
        "Explain how two-factor authentication works. Compare TOTP, SMS, and hardware keys.",
        "What is a DDoS attack? Discuss mitigation strategies at different OSI layers.",
        "Explain the concept of defense in depth with a practical example.",
        "What is a side-channel attack? Give examples like timing attacks and Spectre.",
        "Explain how OAuth 2.0 prevents credential sharing between services.",
        "What is a rainbow table attack? How do salted hashes defend against it?",
        "Explain the difference between authentication, authorization, and accounting (AAA).",
        "What is certificate pinning and when should you use it?",
        "Explain how Content Security Policy (CSP) headers protect against XSS.",
        "What is the difference between penetration testing and vulnerability scanning?",
    ],
    "algorithms": [
        "Explain dynamic programming with the knapsack problem. Show the state transition.",
        "What is the greedy algorithm paradigm? When does it give optimal solutions?",
        "Explain the traveling salesman problem. Why is it NP-hard?",
        "What is backtracking? Solve the N-Queens problem as an example.",
        "Explain divide and conquer with the closest pair of points problem.",
        "What is memoization vs tabulation in dynamic programming?",
        "Explain the Floyd-Warshall algorithm for all-pairs shortest paths.",
        "What is the maximum flow problem? Explain the Ford-Fulkerson method.",
        "Explain the KMP (Knuth-Morris-Pratt) string matching algorithm.",
        "What is the convex hull problem? Compare Graham scan and Jarvis march.",
        "Explain the concept of NP-completeness. Give examples of NP-complete problems.",
        "What is the Hungarian algorithm? When is it used?",
        "Explain Kruskal's and Prim's algorithms for minimum spanning trees.",
        "What is a rolling hash and how is it used in the Rabin-Karp algorithm?",
        "Explain the concept of approximation algorithms with the vertex cover problem.",
        "What is the reservoir sampling algorithm? When would you use it?",
        "Explain the Bellman-Ford algorithm and how it handles negative edges.",
        "What is the edit distance problem? Explain the Wagner-Fischer algorithm.",
        "Explain the concept of randomized algorithms with quicksort as an example.",
        "What is the stable matching problem? Explain the Gale-Shapley algorithm.",
    ],
    "math_applied": [
        "Explain how linear regression works. Derive the normal equation.",
        "What is gradient descent? Explain batch, stochastic, and mini-batch variants.",
        "Explain principal component analysis (PCA) and dimensionality reduction.",
        "What is the bias-variance tradeoff in machine learning?",
        "Explain the k-means clustering algorithm step by step.",
        "What is logistic regression? How does it differ from linear regression?",
        "Explain cross-validation and why it is important for model evaluation.",
        "What is the ROC curve? Explain AUC and its interpretation.",
        "Explain the difference between L1 and L2 regularization.",
        "What is a support vector machine (SVM)? Explain the kernel trick.",
        "Explain the naive Bayes classifier and its independence assumption.",
        "What are decision trees? How do they handle overfitting?",
        "Explain random forests and how they improve on single decision trees.",
        "What is the curse of dimensionality and how does it affect machine learning?",
        "Explain how neural network weight initialization affects training.",
        "What is batch normalization and why does it help training?",
        "Explain the vanishing gradient problem and solutions like ReLU and residual connections.",
        "What is the difference between precision, recall, and F1-score?",
        "Explain how dropout works as a regularization technique.",
        "What is transfer learning and why is it so effective for deep learning?",
    ],
    "practical_devops": [
        "How do I debug a Python application that hangs? List tools and techniques.",
        "Explain how to use strace/ltrace to debug system calls on Linux.",
        "What are the best practices for writing Dockerfiles for production?",
        "How do I set up monitoring and alerting for a web application?",
        "Explain the 12-factor app methodology and why it matters.",
        "How do I handle database migrations in a zero-downtime deployment?",
        "What is chaos engineering? Explain the principles and how to get started.",
        "How do I optimize Docker image sizes? Give specific techniques.",
        "Explain how to implement health checks for microservices.",
        "What are the best practices for managing secrets in production?",
        "How do I set up automated backups for a PostgreSQL database?",
        "Explain how to implement blue-green deployments with Kubernetes.",
        "What is GitOps? How does it differ from traditional CI/CD?",
        "How do I troubleshoot network connectivity issues between microservices?",
        "Explain how to implement graceful shutdown in a web server.",
        "How do I set up log rotation and centralized logging?",
        "Explain how to use profiling tools (cProfile, py-spy) to find bottlenecks.",
        "What are the best practices for API versioning?",
        "How do I implement distributed tracing across microservices?",
        "Explain how to configure rate limiting at the infrastructure level.",
    ],
    "ethics_society": [
        "What are the implications of deepfake technology for society?",
        "Discuss the digital divide and how technology can both widen and bridge it.",
        "What are the privacy implications of large-scale data collection by tech companies?",
        "Explain algorithmic bias and give three concrete examples from real systems.",
        "What is the right to be forgotten and how does it conflict with free speech?",
        "Discuss the environmental impact of cryptocurrency mining.",
        "What are the ethical concerns around facial recognition technology?",
        "Explain the concept of technological unemployment and historical parallels.",
        "What is surveillance capitalism? Discuss its implications for democracy.",
        "Discuss the ethics of AI-generated art and its impact on artists.",
        "What are the implications of autonomous vehicles for liability and insurance?",
        "Explain the concept of digital sovereignty and why countries care about it.",
        "What are the ethical implications of predictive policing systems?",
        "Discuss the tension between encryption and law enforcement access.",
        "What is the social media attention economy and how does it affect mental health?",
    ],
}


# ── HTTP helpers ──────────────────────────────────────────────

def _http_post(url, headers, body, timeout=45):
    """POST JSON, return (status_code, response_dict)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, {"error": body_text}
    except Exception as e:
        return 0, {"error": str(e)}


# ── Provider query functions ──────────────────────────────────

def query_openai_style(provider_cfg, prompt, model=None):
    """Query OpenAI-compatible API (Groq, Cerebras, SambaNova)."""
    if model is None:
        model = random.choice(provider_cfg["models"])
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + provider_cfg["key"],
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful, knowledgeable assistant. Provide detailed, accurate, well-structured responses."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
    }
    status, resp = _http_post(provider_cfg["url"], headers, body)
    if status == 200 and "choices" in resp:
        text = resp["choices"][0]["message"]["content"]
        return text, model
    if status == 429:
        return None, model  # rate limited
    return None, model


def query_google(provider_cfg, prompt):
    """Query Google AI Studio (Gemini) API."""
    url = provider_cfg["url"] + "?key=" + provider_cfg["key"]
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 1024,
            "temperature": 0.7,
        },
        "systemInstruction": {
            "parts": [{"text": "You are a helpful, knowledgeable assistant. Provide detailed, accurate, well-structured responses."}]
        },
    }
    status, resp = _http_post(url, headers, body)
    if status == 200 and "candidates" in resp:
        try:
            text = resp["candidates"][0]["content"]["parts"][0]["text"]
            return text, "gemini-2.0-flash"
        except (KeyError, IndexError):
            pass
    if status == 429:
        return None, "gemini-2.0-flash"
    return None, "gemini-2.0-flash"


def query_provider(prov_id, prompt):
    """Dispatch to the right query function for a provider."""
    cfg = PROVIDERS[prov_id]
    if cfg["style"] == "google":
        return query_google(cfg, prompt)
    else:
        return query_openai_style(cfg, prompt)


# ── Quality filter ────────────────────────────────────────────

def quality_filter(response):
    """Reject low-quality responses."""
    if not response or len(response) < 80:
        return False
    if len(response) > 12000:
        return False
    if response.startswith("Error") or "rate limit" in response.lower():
        return False
    if response.startswith("I cannot") or response.startswith("I'm sorry"):
        return False
    if response.count("\n") < 1 and len(response) < 150:
        return False
    return True


# ── Dedup against mega file ──────────────────────────────────

def load_existing_hashes():
    """Load MD5 hashes from training_pairs_mega.json for dedup."""
    hashes = set()
    if MEGA_FILE.exists():
        try:
            data = json.loads(MEGA_FILE.read_text(encoding="utf-8"))
            pairs = data if isinstance(data, list) else data.get("pairs", [])
            for p in pairs:
                inp = p.get("input", p.get("prompt", ""))
                out = p.get("output", p.get("response", ""))
                h = hashlib.md5((inp + "|||" + out).encode()).hexdigest()
                hashes.add(h)
            print("  Loaded %d existing hashes from mega file" % len(hashes))
        except Exception as e:
            print("  Warning: could not load mega file for dedup: %s" % str(e))
    return hashes


# ── Checkpoint / resume ──────────────────────────────────────

def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        try:
            return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "total_tried": 0,
        "total_kept": 0,
        "errors": 0,
        "used_prompt_hashes": [],
        "provider_stats": {},
        "hashes": [],
        "last_run": None,
    }


def save_checkpoint(state):
    """Save checkpoint atomically."""
    state["hashes"] = state["hashes"][-5000:]
    state["used_prompt_hashes"] = state["used_prompt_hashes"][-2000:]
    state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tmp = str(CHECKPOINT_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, str(CHECKPOINT_FILE))


# ── Atomic save for output ───────────────────────────────────

def load_output():
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_output(pairs):
    """Atomic save to output file."""
    tmp = str(OUTPUT_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=1, ensure_ascii=True)
    os.replace(tmp, str(OUTPUT_FILE))


# ── Persona variations ───────────────────────────────────────

PERSONAS = [
    "",
    "Answer in detail with examples. ",
    "Explain clearly and concisely. ",
    "Think step by step before answering. ",
    "Provide a thorough analysis. ",
    "Be precise and use technical terminology. ",
    "Explain as if teaching a beginner. ",
    "Give a comprehensive answer with real-world applications. ",
]


# ── Main harvester loop ──────────────────────────────────────

def run():
    print("=" * 60)
    print("  NovaX Free-Tier API Harvester v2.0")
    print("  Direct API access -- no Cloud Router needed")
    print("=" * 60)

    # Load providers
    _load_providers()
    if not PROVIDERS:
        print("\n  ERROR: No API keys found!")
        print("  Set environment variables:")
        print("    GROQ_API_KEY, CEREBRAS_API_KEY,")
        print("    SAMBANOVA_API_KEY, GOOGLE_AI_KEY")
        print("  Or add keys to C:\\NovaX\\cloud_config.json")
        return

    print("\n  Providers available:")
    for pid, cfg in PROVIDERS.items():
        print("    [OK] %-12s  %-50s  (%d RPM)" % (
            cfg["name"], ", ".join(cfg["models"])[:50], cfg["rpm"]))
    print()

    # Build prompt list
    all_prompts = []
    for domain, prompts in PROMPTS.items():
        for p in prompts:
            all_prompts.append((p, domain))

    print("  Total prompts: %d across %d domains" % (len(all_prompts), len(PROMPTS)))

    # Load state
    state = load_checkpoint()
    existing_hashes = load_existing_hashes()
    seen = set(state.get("hashes", []))
    seen.update(existing_hashes)
    used_prompt_hashes = set(state.get("used_prompt_hashes", []))
    pairs = load_output()

    # Filter unused prompts
    available_prompts = []
    for p, d in all_prompts:
        ph = hashlib.md5(p.encode()).hexdigest()[:12]
        if ph not in used_prompt_hashes:
            available_prompts.append((p, d, ph))

    if not available_prompts:
        print("  All prompts used! Reshuffling with new personas...")
        used_prompt_hashes.clear()
        state["used_prompt_hashes"] = []
        for p, d in all_prompts:
            ph = hashlib.md5(p.encode()).hexdigest()[:12]
            available_prompts.append((p, d, ph))

    random.shuffle(available_prompts)

    print("  Unused prompts: %d" % len(available_prompts))
    print("  Existing pairs in output: %d" % len(pairs))
    print("  Resume: %d kept / %d tried" % (state["total_kept"], state["total_tried"]))
    print("  Dedup hashes loaded: %d" % len(seen))
    print("\n  Press Ctrl+C to stop gracefully")
    print("-" * 60)

    # Round-robin setup
    provider_ids = list(PROVIDERS.keys())
    provider_idx = 0
    backoff = {pid: 0.0 for pid in provider_ids}
    last_call = {pid: 0.0 for pid in provider_ids}

    # Graceful shutdown
    shutdown = [False]
    def handle_signal(sig, frame):
        shutdown[0] = True
        print("\n  Ctrl+C received -- finishing current pair and saving...")
    signal.signal(signal.SIGINT, handle_signal)

    session_start = time.time()
    session_kept = 0
    prompt_idx = 0

    while prompt_idx < len(available_prompts) and not shutdown[0]:
        prompt, domain, prompt_hash = available_prompts[prompt_idx]
        prompt_idx += 1

        # Pick provider (round-robin, skip those in backoff)
        attempts = 0
        chosen_pid = None
        while attempts < len(provider_ids):
            pid = provider_ids[provider_idx % len(provider_ids)]
            provider_idx += 1
            now = time.time()

            # Respect rate limits
            min_interval = 60.0 / PROVIDERS[pid]["rpm"]
            since_last = now - last_call.get(pid, 0)
            if since_last < min_interval:
                wait = min_interval - since_last
                if wait > 0.1:
                    time.sleep(wait)

            # Check backoff
            if backoff[pid] > now:
                attempts += 1
                continue

            chosen_pid = pid
            break

        if chosen_pid is None:
            # All providers in backoff -- wait for shortest
            min_wait = min(backoff[pid] - time.time() for pid in provider_ids)
            if min_wait > 0:
                print("  All providers in backoff, waiting %.1fs..." % min_wait)
                time.sleep(min(min_wait, 30))
            prompt_idx -= 1  # retry this prompt
            continue

        # Add persona variation
        full_prompt = random.choice(PERSONAS) + prompt

        # Query provider
        t0 = time.time()
        response, model = query_provider(chosen_pid, full_prompt)
        elapsed = time.time() - t0
        last_call[chosen_pid] = time.time()
        state["total_tried"] += 1

        # Update provider stats
        pstats = state.setdefault("provider_stats", {})
        ps = pstats.setdefault(chosen_pid, {"tried": 0, "kept": 0, "errors": 0})
        ps["tried"] += 1

        # Handle failures / rate limits
        if response is None:
            ps["errors"] += 1
            state["errors"] += 1
            current_bo = backoff[chosen_pid] - time.time()
            new_bo = max(5, min(current_bo * 2, 120)) if current_bo > 0 else 5
            backoff[chosen_pid] = time.time() + new_bo
            print("  [%5d] RATE-LIMITED %-12s | backoff %.0fs | %s" % (
                state["total_tried"], PROVIDERS[chosen_pid]["name"], new_bo, domain))
            prompt_idx -= 1  # retry with another provider
            continue

        # Quality filter
        if not quality_filter(response):
            ps["errors"] += 1
            state["errors"] += 1
            if state["total_tried"] % 5 == 0:
                print("  [%5d] FILTERED    %-12s | %s" % (
                    state["total_tried"], PROVIDERS[chosen_pid]["name"], domain))
            continue

        # Clear backoff on success
        backoff[chosen_pid] = 0

        # MD5 dedup
        h = hashlib.md5((prompt + "|||" + response).encode()).hexdigest()
        if h in seen:
            continue
        seen.add(h)

        # Build pair
        pair = {
            "input": prompt,
            "output": response,
            "domain": domain,
            "model": model,
            "provider": chosen_pid,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        pairs.append(pair)
        state["total_kept"] += 1
        state["hashes"].append(h)
        state["used_prompt_hashes"].append(prompt_hash)
        used_prompt_hashes.add(prompt_hash)
        ps["kept"] += 1
        session_kept += 1

        # Progress report every 10 pairs
        if session_kept % 10 == 0:
            elapsed_total = time.time() - session_start
            rate = session_kept / (elapsed_total / 60) if elapsed_total > 0 else 0
            print("  [%5d] ++ %d kept (session: %d, %.1f/min) | %-12s | %s | %.1fs" % (
                state["total_tried"], state["total_kept"], session_kept,
                rate, PROVIDERS[chosen_pid]["name"], domain, elapsed))
            # Atomic save every 10
            save_output(pairs)
            save_checkpoint(state)
        elif session_kept % 3 == 0:
            print("  [%5d] +  %-12s | %-18s | %s | %.1fs" % (
                state["total_tried"], PROVIDERS[chosen_pid]["name"],
                domain[:18], model[:30] if model else "?", elapsed))

    # Final save
    print("\n" + "-" * 60)
    elapsed_total = time.time() - session_start
    print("  Session complete!")
    print("  Duration: %.1f minutes" % (elapsed_total / 60))
    print("  Pairs this session: %d" % session_kept)
    print("  Total pairs in output: %d" % len(pairs))
    print("  Total tried (all time): %d" % state["total_tried"])
    print("  Total kept (all time): %d" % state["total_kept"])
    print("\n  Provider breakdown:")
    for pid, ps in state.get("provider_stats", {}).items():
        name = PROVIDERS.get(pid, {}).get("name", pid)
        print("    %-12s  tried=%d  kept=%d  errors=%d" % (
            name, ps["tried"], ps["kept"], ps["errors"]))

    save_output(pairs)
    save_checkpoint(state)
    print("\n  Output: %s" % OUTPUT_FILE)
    print("  Checkpoint: %s" % CHECKPOINT_FILE)
    print("=" * 60)


if __name__ == "__main__":
    run()
