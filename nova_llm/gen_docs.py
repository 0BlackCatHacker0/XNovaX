"""
DOCUMENTATION MINER - Convert README, .md, and text docs into Q&A pairs.
Also generates pairs from Python stdlib docs and common knowledge.
Target: 3,000+ pairs.
Writes to: C:/NovaX/data/llm_training/pairs_docs.json
"""
import json
import os
import re
import random

random.seed(321)
OUTPUT = "C:/NovaX/data/llm_training/pairs_docs.json"
NOVAX_ROOT = "C:/NovaX"
pairs = []
seen = set()

def add(prompt, response, domain):
    key = prompt.strip().lower()[:200]
    if key in seen:
        return
    if len(prompt.strip()) < 10 or len(response.strip()) < 30:
        return
    seen.add(key)
    pairs.append({
        "prompt": prompt.strip(),
        "response": response.strip(),
        "domain": domain,
        "provider": "docs_miner",
        "model": "docs_v1"
    })

# ============================================================
# 1. MARKDOWN FILES -> Q&A PAIRS
# ============================================================
print("[1/4] Mining markdown files...")

md_files = []
skip_dirs = {'node_modules', '.git', 'ai_env', '__pycache__', 'target', 'dist'}
for dirpath, dirnames, filenames in os.walk(NOVAX_ROOT):
    dirnames[:] = [d for d in dirnames if d not in skip_dirs]
    for f in filenames:
        if f.endswith('.md') or f.endswith('.txt') or f.endswith('.rst'):
            md_files.append(os.path.join(dirpath, f))

print(f"  Found {len(md_files)} doc files")

for filepath in md_files:
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        continue

    if len(content) < 100:
        continue

    rel_path = os.path.relpath(filepath, NOVAX_ROOT).replace('\\', '/')

    # Extract sections by headers
    sections = re.split(r'\n(#{1,3})\s+(.+)\n', content)

    i = 0
    while i < len(sections) - 2:
        if sections[i].startswith('#'):
            level = len(sections[i])
            title = sections[i+1].strip()
            body = sections[i+2] if i+2 < len(sections) else ""

            # Clean body
            body = body.strip()
            if len(body) < 50:
                i += 3
                continue

            # Truncate long bodies
            body = body[:1500]

            add(f"What does the section '{title}' in {rel_path} describe?",
                f"In `{rel_path}`, the '{title}' section describes:\n\n{body}",
                "docs_section")

            # If it looks like a feature/concept, create a "what is" pair
            if len(title) < 50 and not title.startswith(('How', 'Why', 'When')):
                add(f"What is {title} in NovaX?",
                    f"{title}: {body[:500]}",
                    "docs_concept")
            i += 3
        else:
            i += 1

    # File-level pair
    first_500 = content[:500].strip()
    add(f"What is documented in {rel_path}?",
        f"The file `{rel_path}` contains documentation:\n\n{first_500}",
        "docs_file")

md_count = len(pairs)
print(f"  Markdown pairs: {md_count}")

# ============================================================
# 2. PYTHON STANDARD LIBRARY Q&A
# ============================================================
print("[2/4] Generating stdlib pairs...")

stdlib_modules = {
    "os": "Provides functions for interacting with the operating system. Key functions: os.path.join(), os.listdir(), os.makedirs(), os.getcwd(), os.environ, os.walk().",
    "sys": "Provides access to system-specific parameters. Key attributes: sys.argv (command line args), sys.path (module search path), sys.stdin/stdout/stderr, sys.exit().",
    "json": "Encode and decode JSON data. Key functions: json.dumps() (object to string), json.loads() (string to object), json.dump() (to file), json.load() (from file).",
    "re": "Regular expression operations. Key functions: re.match() (match at start), re.search() (search anywhere), re.findall() (find all matches), re.sub() (substitute), re.compile() (precompile pattern).",
    "datetime": "Date and time handling. Key classes: datetime.datetime, datetime.date, datetime.timedelta. Methods: .now(), .strftime() (format), .strptime() (parse), arithmetic with timedelta.",
    "collections": "Specialized container types. Counter (counting), defaultdict (dict with defaults), OrderedDict (ordered), deque (double-ended queue), namedtuple (named fields).",
    "itertools": "Functions for efficient iteration. product() (cartesian product), permutations(), combinations(), chain() (concatenate), cycle() (infinite repeat), islice() (slicing).",
    "functools": "Higher-order functions. reduce() (cumulative operation), partial() (partial application), lru_cache (memoization), wraps (decorator helper), total_ordering.",
    "pathlib": "Object-oriented filesystem paths. Path objects with methods: .exists(), .read_text(), .write_text(), .mkdir(), .glob(), .stem, .suffix, .parent, / operator for joining.",
    "typing": "Type hints for Python code. Types: List, Dict, Tuple, Optional, Union, Any, Callable. Used with mypy for static type checking. TypeVar for generics.",
    "threading": "Thread-based parallelism. Thread class, Lock, RLock, Semaphore, Event, Condition. GIL limits CPU-bound parallelism but works for I/O-bound tasks.",
    "multiprocessing": "Process-based parallelism. Process class, Pool for worker pools, Queue/Pipe for inter-process communication. Bypasses GIL for true CPU parallelism.",
    "asyncio": "Async I/O framework. async/await syntax, event loop, coroutines, Tasks, gather() for concurrent execution. Ideal for I/O-bound concurrent operations.",
    "subprocess": "Run external commands. subprocess.run() (simple), Popen (advanced). Capture stdout/stderr, pipe data, set timeouts. Replace os.system().",
    "logging": "Flexible logging framework. Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL. Handlers: StreamHandler, FileHandler, RotatingFileHandler. Formatters for output style.",
    "unittest": "Unit testing framework. TestCase class with assertEqual(), assertTrue(), assertRaises(). setUp()/tearDown() for fixtures. Test discovery with -m unittest.",
    "argparse": "Command-line argument parsing. ArgumentParser with add_argument() for positional and optional args. Type checking, defaults, help text, subcommands.",
    "hashlib": "Secure hash algorithms. md5(), sha1(), sha256(), sha512(). Methods: .update() (add data), .hexdigest() (get hash string), .digest() (get bytes).",
    "socket": "Low-level networking. TCP/UDP socket creation, bind(), listen(), accept(), connect(), send(), recv(). Foundation for all network programming.",
    "http": "HTTP protocol handling. http.server for simple servers, http.client for client connections. urllib and requests library are higher-level alternatives.",
    "sqlite3": "SQLite database interface. connect() to open/create database, cursor() for queries, execute() for SQL, commit()/rollback() for transactions. No server needed.",
    "csv": "CSV file reading and writing. reader/writer for basic operations, DictReader/DictWriter for named columns. Handles different delimiters and quoting.",
    "pickle": "Object serialization. pickle.dumps()/loads() for bytes, dump()/load() for files. WARNING: never unpickle untrusted data (security risk). Use json for safe serialization.",
    "struct": "Pack and unpack binary data. struct.pack() converts Python values to bytes, struct.unpack() converts bytes back. Format strings specify data types and byte order.",
    "math": "Mathematical functions. sin(), cos(), sqrt(), log(), exp(), pi, e, ceil(), floor(), factorial(), gcd(). For arrays, use numpy instead.",
    "random": "Random number generation. random() (0-1 float), randint(a,b) (integer), choice() (pick from list), shuffle() (randomize list), seed() (reproducibility).",
    "os.path": "Path manipulation utilities. join() (combine paths), exists(), isfile(), isdir(), basename(), dirname(), splitext() (split extension), getsize().",
    "shutil": "High-level file operations. copy(), copy2() (with metadata), copytree() (recursive), rmtree() (remove tree), move(), disk_usage(), make_archive().",
    "glob": "Unix-style path pattern matching. glob() finds files matching patterns like '*.py', '**/*.json'. Supports wildcards: * (any), ? (single char), [] (range).",
    "time": "Time access and conversions. time() (epoch seconds), sleep() (delay), perf_counter() (high-resolution timer), strftime() (format time), monotonic() (always increases).",
}

for module, desc in stdlib_modules.items():
    add(f"What is the Python `{module}` module?",
        f"The `{module}` module in Python's standard library: {desc}",
        "python_stdlib")
    add(f"How do I use `{module}` in Python?",
        f"The Python `{module}` module: {desc}\n\nImport with: `import {module}`",
        "python_stdlib")
    add(f"What are the main functions in Python's `{module}`?",
        f"Python's `{module}` module: {desc}",
        "python_stdlib")

stdlib_count = len(pairs) - md_count
print(f"  Stdlib pairs: {stdlib_count}")

# ============================================================
# 3. HTTP STATUS CODES, LINUX COMMANDS, GIT COMMANDS
# ============================================================
print("[3/4] Generating reference pairs...")

# HTTP status codes
http_codes = {
    200: ("OK", "Request succeeded. Standard response for successful HTTP requests."),
    201: ("Created", "Request fulfilled, new resource created. Typically for POST requests."),
    204: ("No Content", "Request succeeded but no content to return. Common for DELETE requests."),
    301: ("Moved Permanently", "Resource permanently moved to new URL. Browsers cache this redirect."),
    302: ("Found", "Resource temporarily at different URL. Browser follows redirect but doesn't cache."),
    304: ("Not Modified", "Resource hasn't changed since last request. Browser uses cached version."),
    400: ("Bad Request", "Server cannot process request due to client error (malformed syntax, invalid parameters)."),
    401: ("Unauthorized", "Authentication required. Client must provide valid credentials."),
    403: ("Forbidden", "Server understood request but refuses to authorize it. Different from 401."),
    404: ("Not Found", "Requested resource doesn't exist on the server."),
    405: ("Method Not Allowed", "HTTP method not supported for this resource (e.g., POST on read-only endpoint)."),
    408: ("Request Timeout", "Server timed out waiting for the client request."),
    409: ("Conflict", "Request conflicts with current state (e.g., duplicate resource, version conflict)."),
    413: ("Payload Too Large", "Request body exceeds server's size limit."),
    422: ("Unprocessable Entity", "Request is well-formed but contains semantic errors (common in APIs)."),
    429: ("Too Many Requests", "Rate limit exceeded. Client should wait before retrying."),
    500: ("Internal Server Error", "Generic server error. Something went wrong on the server side."),
    502: ("Bad Gateway", "Server acting as gateway received invalid response from upstream server."),
    503: ("Service Unavailable", "Server temporarily unable to handle request (overloaded or maintenance)."),
    504: ("Gateway Timeout", "Server acting as gateway didn't receive timely response from upstream."),
}

for code, (name, desc) in http_codes.items():
    add(f"What is HTTP status code {code}?",
        f"HTTP {code} {name}: {desc}",
        "reference_http")
    add(f"What does HTTP {code} mean?",
        f"HTTP status {code} ({name}): {desc}",
        "reference_http")

# Git commands
git_commands = {
    "git init": "Initializes a new Git repository in the current directory. Creates a .git subdirectory with repository metadata.",
    "git clone <url>": "Creates a local copy of a remote repository. Downloads all history and branches.",
    "git add <file>": "Stages changes for the next commit. Use 'git add .' for all changes, 'git add -p' for interactive staging.",
    "git commit -m '<msg>'": "Records staged changes with a message. Creates a new snapshot in the repository history.",
    "git push": "Uploads local commits to the remote repository. Use 'git push -u origin branch' for first push of a new branch.",
    "git pull": "Fetches and merges remote changes. Equivalent to 'git fetch' + 'git merge'. Use '--rebase' for linear history.",
    "git branch": "Lists, creates, or deletes branches. 'git branch <name>' creates, 'git branch -d <name>' deletes.",
    "git checkout <branch>": "Switches to a different branch. 'git checkout -b <name>' creates and switches. Modern alternative: 'git switch'.",
    "git merge <branch>": "Integrates changes from one branch into the current branch. Creates a merge commit unless fast-forward.",
    "git rebase <branch>": "Replays commits on top of another branch for linear history. Changes commit hashes. Never rebase shared branches.",
    "git stash": "Temporarily saves uncommitted changes. 'git stash pop' restores them. Useful for switching branches with dirty working directory.",
    "git log": "Shows commit history. Options: --oneline (compact), --graph (visual), --author=<name> (filter), -n <count> (limit).",
    "git diff": "Shows changes between commits, branches, or working directory. 'git diff --staged' for staged changes.",
    "git reset": "Unstages changes or moves HEAD. --soft (keep changes staged), --mixed (unstage), --hard (discard all changes).",
    "git cherry-pick <hash>": "Applies a specific commit from another branch to the current branch. Creates a new commit.",
    "git tag <name>": "Creates a reference to a specific commit. Lightweight (pointer) or annotated (with metadata). Used for releases.",
    "git remote": "Manages remote connections. 'git remote add origin <url>', 'git remote -v' (list), 'git remote remove <name>'.",
    "git fetch": "Downloads remote changes without merging. Updates remote-tracking branches. Safe to run anytime.",
    "git bisect": "Binary search through commits to find which one introduced a bug. 'git bisect start', mark good/bad, Git finds the culprit.",
    "git reflog": "Shows log of all reference updates (even deleted commits). Useful for recovering lost work. Entries expire after 90 days.",
}

for cmd, desc in git_commands.items():
    add(f"What does `{cmd}` do in Git?", f"`{cmd}`: {desc}", "reference_git")
    add(f"How do I use `{cmd}`?", f"{desc}\n\nUsage: `{cmd}`", "reference_git")

# Linux/shell commands
shell_commands = {
    "ls": "List directory contents. -l (long format), -a (show hidden), -h (human-readable sizes), -R (recursive).",
    "cd": "Change directory. cd ~ (home), cd .. (parent), cd - (previous), cd / (root).",
    "pwd": "Print working directory. Shows the full path of the current directory.",
    "cp": "Copy files/directories. -r (recursive for dirs), -i (interactive/confirm), -v (verbose).",
    "mv": "Move or rename files/directories. mv source dest. Works for both moving and renaming.",
    "rm": "Remove files/directories. -r (recursive), -f (force), -i (interactive). BE CAREFUL with rm -rf.",
    "mkdir": "Create directories. -p (create parent dirs as needed). mkdir -p a/b/c creates all three.",
    "chmod": "Change file permissions. Numeric: chmod 755 file. Symbolic: chmod u+x file. u=user, g=group, o=other.",
    "chown": "Change file ownership. chown user:group file. -R for recursive.",
    "grep": "Search text using patterns. -r (recursive), -i (case-insensitive), -n (line numbers), -l (filenames only), -E (extended regex).",
    "find": "Search for files. find path -name '*.py' -type f -mtime -7 (Python files modified in last week).",
    "cat": "Concatenate and display file contents. cat file1 file2 > combined. Also used to view files.",
    "less": "View files page by page. Navigate: space (next page), b (back), / (search), q (quit).",
    "head/tail": "View beginning/end of files. head -n 20 file (first 20 lines). tail -f file (follow/stream new lines).",
    "wc": "Count lines, words, and characters. -l (lines only), -w (words only), -c (bytes).",
    "sort": "Sort lines of text. -n (numeric), -r (reverse), -u (unique), -k (by field).",
    "uniq": "Filter duplicate lines (must be sorted first). -c (count), -d (only duplicates).",
    "awk": "Pattern scanning and text processing. awk '{print $1}' (first field). Powerful for columnar data.",
    "sed": "Stream editor for text transformation. sed 's/old/new/g' file (substitute all occurrences).",
    "curl": "Transfer data via URLs. -X (method), -H (headers), -d (data), -o (output file), -s (silent).",
    "wget": "Download files from the web. -O (output name), -r (recursive), -c (continue interrupted download).",
    "tar": "Archive files. tar -czf archive.tar.gz dir/ (create), tar -xzf archive.tar.gz (extract).",
    "ssh": "Secure shell remote login. ssh user@host. -i (identity file), -p (port), -L (tunnel).",
    "scp": "Secure copy between hosts. scp file user@host:/path. -r (recursive), -P (port).",
    "ps": "List running processes. ps aux (all processes), ps -ef (full format). Pipe to grep to filter.",
    "top/htop": "Interactive process viewer. Shows CPU, memory usage. htop has better UI and mouse support.",
    "kill": "Send signal to process. kill PID (SIGTERM), kill -9 PID (SIGKILL force). killall name.",
    "df": "Show disk space usage. -h (human-readable), -T (filesystem type).",
    "du": "Show directory space usage. -h (human-readable), -s (summary), --max-depth=1.",
    "ping": "Test network connectivity. ping host. -c (count), -t (ttl). Shows round-trip time.",
    "netstat/ss": "Show network connections. ss -tuln (listening TCP/UDP ports). netstat being replaced by ss.",
}

for cmd, desc in shell_commands.items():
    add(f"What does the `{cmd}` command do?", f"The `{cmd}` command: {desc}", "reference_shell")
    add(f"How do I use `{cmd}` in Linux?", f"`{cmd}`: {desc}", "reference_shell")

ref_count = len(pairs) - md_count - stdlib_count
print(f"  Reference pairs: {ref_count}")

# ============================================================
# 4. DESIGN PATTERNS & SOFTWARE CONCEPTS
# ============================================================
print("[4/4] Generating design pattern pairs...")

design_patterns = {
    "Singleton": "Ensures a class has only one instance with a global access point. Use for shared resources like database connections, configuration managers, or logger instances. In Python: use a module-level instance or metaclass.",
    "Factory": "Creates objects without specifying the exact class. Defines an interface for creating objects but lets subclasses decide which class to instantiate. Useful when object creation logic is complex or varies.",
    "Observer": "Defines a one-to-many dependency where when one object changes state, all dependents are notified. Used for event systems, pub/sub patterns, and reactive programming. Example: GUI event handlers.",
    "Strategy": "Defines a family of algorithms, encapsulates each one, and makes them interchangeable. Lets the algorithm vary independently from clients that use it. Example: different sorting or compression strategies.",
    "Decorator": "Dynamically adds behavior to objects without modifying their class. Wraps an object to extend its functionality. In Python, the @decorator syntax is a language-level implementation.",
    "Adapter": "Converts the interface of a class into another interface clients expect. Lets classes work together that couldn't otherwise due to incompatible interfaces. Like a power adapter for different countries.",
    "Command": "Encapsulates a request as an object, allowing parameterization, queuing, logging, and undoing of operations. Used for undo/redo, task queues, and macro recording.",
    "Iterator": "Provides a way to access elements of a collection sequentially without exposing its underlying representation. In Python: __iter__() and __next__() methods, or generator functions.",
    "Template Method": "Defines the skeleton of an algorithm in a superclass, letting subclasses override specific steps without changing the algorithm's structure. Uses inheritance for customization.",
    "Builder": "Separates construction of a complex object from its representation. Allows step-by-step construction. Useful when an object has many optional parameters. Method chaining common.",
    "Proxy": "Provides a surrogate or placeholder for another object to control access to it. Types: virtual (lazy init), protection (access control), remote (network), caching.",
    "Facade": "Provides a simplified interface to a complex subsystem. Doesn't prevent access to the subsystem but offers a convenient default. Like a universal remote for a home theater.",
    "State": "Allows an object to alter its behavior when its internal state changes. Appears as if the object changed its class. Used for finite state machines and workflow engines.",
    "Chain of Responsibility": "Passes a request along a chain of handlers. Each handler decides to process or pass to the next. Used for middleware, logging pipelines, and event bubbling.",
    "MVC": "Model-View-Controller separates concerns: Model (data/logic), View (presentation), Controller (input handling). Foundation of many web frameworks (Django, Rails, Spring).",
    "Repository": "Mediates between domain and data mapping layers using a collection-like interface. Abstracts data storage details. Makes it easy to swap databases or add caching.",
    "Dependency Injection": "Objects receive their dependencies from external sources rather than creating them. Improves testability and decoupling. Types: constructor injection, setter injection, interface injection.",
    "Event Sourcing": "Stores all changes to application state as a sequence of events rather than just current state. Enables audit trails, time travel, and rebuilding state from events.",
    "CQRS": "Command Query Responsibility Segregation separates read and write operations into different models. Commands modify state, queries read state. Enables independent scaling and optimization.",
    "Circuit Breaker": "Detects failures and prevents cascading failures by temporarily stopping calls to a failing service. States: closed (normal), open (failing, reject calls), half-open (testing recovery).",
}

for pattern, desc in design_patterns.items():
    add(f"What is the {pattern} design pattern?",
        f"**{pattern} Pattern**: {desc}",
        "design_patterns")
    add(f"When should I use the {pattern} pattern?",
        f"The {pattern} pattern: {desc}",
        "design_patterns")
    add(f"Explain the {pattern} pattern with an example.",
        f"The {pattern} design pattern: {desc}",
        "design_patterns")

# Software principles
principles = {
    "SOLID": "Five principles for maintainable OOP: Single Responsibility (one reason to change), Open/Closed (open for extension, closed for modification), Liskov Substitution (subtypes must be substitutable), Interface Segregation (many specific interfaces), Dependency Inversion (depend on abstractions).",
    "DRY": "Don't Repeat Yourself - every piece of knowledge should have a single, authoritative representation. Reduce duplication through abstraction, functions, and modules. Opposite: WET (Write Everything Twice).",
    "KISS": "Keep It Simple, Stupid - most systems work best when kept simple. Avoid unnecessary complexity. Simple solutions are easier to understand, maintain, test, and debug.",
    "YAGNI": "You Aren't Gonna Need It - don't implement features until they're actually needed. Avoid speculative generality. Part of extreme programming principles.",
    "separation of concerns": "Divide a program into distinct sections, each addressing a separate concern. HTML (structure), CSS (presentation), JavaScript (behavior). Backend: data, business logic, presentation.",
    "composition over inheritance": "Prefer composing objects with desired functionality rather than inheriting from a base class. More flexible, avoids fragile base class problem, and reduces coupling.",
    "fail fast": "Detect and report errors as soon as possible. Validate inputs early, throw exceptions immediately on invalid state. Makes debugging easier and prevents error propagation.",
    "defensive programming": "Write code that handles unexpected inputs gracefully. Validate all inputs, handle edge cases, use assertions, never trust external data. Like defensive driving.",
    "least privilege": "Every module should have only the minimum access needed to perform its function. Reduces attack surface and limits damage from bugs or compromises.",
    "idempotency": "An operation that produces the same result regardless of how many times it's executed. PUT and DELETE should be idempotent. Important for retry logic and distributed systems.",
}

for principle, desc in principles.items():
    add(f"What is the {principle} principle in software engineering?",
        f"**{principle}**: {desc}",
        "principles")
    add(f"Explain {principle}.",
        f"The {principle} principle: {desc}",
        "principles")

dp_count = len(pairs) - md_count - stdlib_count - ref_count
print(f"  Design pattern/principle pairs: {dp_count}")

# ============================================================
# SAVE
# ============================================================
print(f"\n=== TOTAL DOCS PAIRS: {len(pairs)} ===")

with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(pairs, f, ensure_ascii=False, indent=1)

print(f"Saved to {OUTPUT}")
