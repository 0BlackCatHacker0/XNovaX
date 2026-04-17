"""
SYNTHETIC BOOST - Generate more pairs in underrepresented areas.
Focus: more math variations, coding challenges, Q&A about concepts.
Target: 8,000+ additional pairs.
Writes to: C:/NovaX/data/llm_training/pairs_synthetic_boost.json
"""
import json
import random
import math

random.seed(2024)
OUTPUT = "C:/NovaX/data/llm_training/pairs_synthetic_boost.json"
pairs = []
seen = set()

def add(prompt, response, domain):
    key = prompt.strip().lower()[:200]
    if key in seen:
        return
    seen.add(key)
    pairs.append({
        "prompt": prompt.strip(),
        "response": response.strip(),
        "domain": domain,
        "provider": "synthetic_boost",
        "model": "template_v2"
    })

# ============================================================
# 1. EXTENDED MATH (3000+)
# ============================================================
print("[1/6] Extended math...")

# GCD and LCM
for a in range(2, 101):
    for b in range(2, 51):
        if a != b:
            g = math.gcd(a, b)
            l = a * b // g
            add("What is the GCD of %d and %d?" % (a, b),
                "The GCD (Greatest Common Divisor) of %d and %d is %d." % (a, b, g),
                "math_gcd")
            add("What is the LCM of %d and %d?" % (a, b),
                "The LCM (Least Common Multiple) of %d and %d is %d. (LCM = a*b/GCD = %d*%d/%d)" % (a, b, l, a, b, g),
                "math_lcm")

# Exponents
for base in range(2, 16):
    for exp in range(2, 11):
        result = base ** exp
        if result < 10**12:
            add("What is %d^%d (power)?" % (base, exp),
                "%d raised to the power of %d is %d." % (base, exp, result),
                "math_exponents")

# Modular arithmetic
for a in range(1, 51):
    for m in [2, 3, 5, 7, 10, 12, 13, 16, 100]:
        r = a % m
        add("What is %d mod %d?" % (a, m),
            "%d mod %d = %d (the remainder when %d is divided by %d)." % (a, m, r, a, m),
            "math_modular")

# Absolute values
for n in range(-50, 51):
    add("What is the absolute value of %d?" % n,
        "The absolute value of %d is %d. |%d| = %d." % (n, abs(n), n, abs(n)),
        "math_abs")

# Floor and ceil
for n in [0.1, 0.5, 0.9, 1.1, 1.5, 1.9, 2.3, 2.7, 3.14, 3.99, -0.5, -1.3, -2.7, 99.9]:
    add("What is floor(%s)?" % n,
        "floor(%s) = %d. The floor function rounds down to the nearest integer." % (n, math.floor(n)),
        "math_floor")
    add("What is ceil(%s)?" % n,
        "ceil(%s) = %d. The ceiling function rounds up to the nearest integer." % (n, math.ceil(n)),
        "math_ceil")

# Triangular numbers
for n in range(1, 101):
    tri = n * (n + 1) // 2
    add("What is the %d%s triangular number?" % (n, "st" if n==1 else "nd" if n==2 else "rd" if n==3 else "th"),
        "The %d%s triangular number is %d. Formula: n*(n+1)/2 = %d*%d/2 = %d." % (
            n, "st" if n==1 else "nd" if n==2 else "rd" if n==3 else "th", tri, n, n+1, tri),
        "math_sequences")

# Powers of 2
for n in range(0, 33):
    p = 2**n
    add("What is 2 to the power of %d?" % n,
        "2^%d = %d." % (n, p),
        "math_powers2")

# Factorials
for n in range(0, 21):
    f = math.factorial(n)
    add("What is %d! (factorial)?" % n,
        "%d! = %d. Factorial is the product of all positive integers up to n." % (n, f),
        "math_factorial")

math_count = len(pairs)
print("  Extended math pairs: %d" % math_count)

# ============================================================
# 2. CODING CHALLENGES WITH SOLUTIONS (1500+)
# ============================================================
print("[2/6] Coding challenges...")

challenges = [
    ("Write a Python function to check if a string is a palindrome.",
     "```python\ndef is_palindrome(s):\n    s = s.lower().replace(' ', '')\n    return s == s[::-1]\n\n# Examples:\n# is_palindrome('racecar') -> True\n# is_palindrome('hello') -> False\n# is_palindrome('A man a plan a canal Panama') -> True\n```",
     "coding_challenge"),
    ("Write a Python function to find the nth Fibonacci number.",
     "```python\ndef fibonacci(n):\n    if n <= 0: return 0\n    if n == 1: return 1\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b\n\n# Examples: fibonacci(10) -> 55, fibonacci(20) -> 6765\n```",
     "coding_challenge"),
    ("Write a Python function to check if a number is prime.",
     "```python\ndef is_prime(n):\n    if n < 2: return False\n    if n < 4: return True\n    if n % 2 == 0 or n % 3 == 0: return False\n    i = 5\n    while i * i <= n:\n        if n % i == 0 or n % (i + 2) == 0:\n            return False\n        i += 6\n    return True\n```",
     "coding_challenge"),
    ("Write a Python function to flatten a nested list.",
     "```python\ndef flatten(lst):\n    result = []\n    for item in lst:\n        if isinstance(item, list):\n            result.extend(flatten(item))\n        else:\n            result.append(item)\n    return result\n\n# flatten([1, [2, [3, 4]], 5]) -> [1, 2, 3, 4, 5]\n```",
     "coding_challenge"),
    ("Write a Python function to remove duplicates from a list while preserving order.",
     "```python\ndef remove_duplicates(lst):\n    seen = set()\n    result = []\n    for item in lst:\n        if item not in seen:\n            seen.add(item)\n            result.append(item)\n    return result\n\n# remove_duplicates([1, 3, 2, 3, 1, 4]) -> [1, 3, 2, 4]\n```",
     "coding_challenge"),
    ("Write a Python function for binary search.",
     "```python\ndef binary_search(arr, target):\n    left, right = 0, len(arr) - 1\n    while left <= right:\n        mid = (left + right) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1\n\n# binary_search([1, 3, 5, 7, 9], 7) -> 3\n```",
     "coding_challenge"),
    ("Write a Python function to reverse a linked list.",
     "```python\nclass ListNode:\n    def __init__(self, val=0, next=None):\n        self.val = val\n        self.next = next\n\ndef reverse_list(head):\n    prev = None\n    current = head\n    while current:\n        next_node = current.next\n        current.next = prev\n        prev = current\n        current = next_node\n    return prev\n```",
     "coding_challenge"),
    ("Write a Python function to find two numbers that sum to a target.",
     "```python\ndef two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        complement = target - num\n        if complement in seen:\n            return [seen[complement], i]\n        seen[num] = i\n    return []\n\n# two_sum([2, 7, 11, 15], 9) -> [0, 1]\n```",
     "coding_challenge"),
    ("Write a Python function to merge two sorted lists.",
     "```python\ndef merge_sorted(list1, list2):\n    result = []\n    i = j = 0\n    while i < len(list1) and j < len(list2):\n        if list1[i] <= list2[j]:\n            result.append(list1[i])\n            i += 1\n        else:\n            result.append(list2[j])\n            j += 1\n    result.extend(list1[i:])\n    result.extend(list2[j:])\n    return result\n```",
     "coding_challenge"),
    ("Write a Python function to count word frequencies in a string.",
     "```python\ndef word_count(text):\n    words = text.lower().split()\n    freq = {}\n    for word in words:\n        word = word.strip('.,!?;:')\n        freq[word] = freq.get(word, 0) + 1\n    return freq\n\n# word_count('the cat sat on the mat') -> {'the': 2, 'cat': 1, 'sat': 1, 'on': 1, 'mat': 1}\n```",
     "coding_challenge"),
    ("Write a Python function to validate an email address.",
     "```python\nimport re\n\ndef is_valid_email(email):\n    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'\n    return bool(re.match(pattern, email))\n\n# is_valid_email('user@example.com') -> True\n# is_valid_email('invalid@') -> False\n```",
     "coding_challenge"),
    ("Write a Python function to find the maximum subarray sum (Kadane's algorithm).",
     "```python\ndef max_subarray(nums):\n    max_sum = current_sum = nums[0]\n    for num in nums[1:]:\n        current_sum = max(num, current_sum + num)\n        max_sum = max(max_sum, current_sum)\n    return max_sum\n\n# max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]) -> 6 (subarray [4, -1, 2, 1])\n```",
     "coding_challenge"),
    ("Write a Python function to implement a stack using a list.",
     "```python\nclass Stack:\n    def __init__(self):\n        self.items = []\n    \n    def push(self, item):\n        self.items.append(item)\n    \n    def pop(self):\n        if not self.is_empty():\n            return self.items.pop()\n        raise IndexError('pop from empty stack')\n    \n    def peek(self):\n        if not self.is_empty():\n            return self.items[-1]\n        return None\n    \n    def is_empty(self):\n        return len(self.items) == 0\n    \n    def size(self):\n        return len(self.items)\n```",
     "coding_challenge"),
    ("Write a Python function to check balanced parentheses.",
     "```python\ndef is_balanced(s):\n    stack = []\n    matching = {')': '(', ']': '[', '}': '{'}\n    for char in s:\n        if char in '([{':\n            stack.append(char)\n        elif char in ')]}':\n            if not stack or stack[-1] != matching[char]:\n                return False\n            stack.pop()\n    return len(stack) == 0\n\n# is_balanced('({[]})') -> True\n# is_balanced('([)]') -> False\n```",
     "coding_challenge"),
    ("Write a Python function to rotate a list by k positions.",
     "```python\ndef rotate_list(lst, k):\n    if not lst:\n        return lst\n    k = k % len(lst)\n    return lst[-k:] + lst[:-k]\n\n# rotate_list([1, 2, 3, 4, 5], 2) -> [4, 5, 1, 2, 3]\n```",
     "coding_challenge"),
    ("Write a Python function to find the longest common prefix among strings.",
     "```python\ndef longest_common_prefix(strs):\n    if not strs:\n        return ''\n    prefix = strs[0]\n    for s in strs[1:]:\n        while not s.startswith(prefix):\n            prefix = prefix[:-1]\n            if not prefix:\n                return ''\n    return prefix\n\n# longest_common_prefix(['flower', 'flow', 'flight']) -> 'fl'\n```",
     "coding_challenge"),
    ("Write a Python function to convert a Roman numeral to integer.",
     "```python\ndef roman_to_int(s):\n    values = {'I': 1, 'V': 5, 'X': 10, 'L': 50,\n              'C': 100, 'D': 500, 'M': 1000}\n    result = 0\n    for i in range(len(s)):\n        if i + 1 < len(s) and values[s[i]] < values[s[i+1]]:\n            result -= values[s[i]]\n        else:\n            result += values[s[i]]\n    return result\n\n# roman_to_int('MCMXCIV') -> 1994\n```",
     "coding_challenge"),
    ("Write a Python function for depth-first search on a graph.",
     "```python\ndef dfs(graph, start, visited=None):\n    if visited is None:\n        visited = set()\n    visited.add(start)\n    result = [start]\n    for neighbor in graph.get(start, []):\n        if neighbor not in visited:\n            result.extend(dfs(graph, neighbor, visited))\n    return result\n\n# graph = {'A': ['B', 'C'], 'B': ['D'], 'C': ['D'], 'D': []}\n# dfs(graph, 'A') -> ['A', 'B', 'D', 'C']\n```",
     "coding_challenge"),
    ("Write a Python function for breadth-first search on a graph.",
     "```python\nfrom collections import deque\n\ndef bfs(graph, start):\n    visited = set([start])\n    queue = deque([start])\n    result = []\n    while queue:\n        node = queue.popleft()\n        result.append(node)\n        for neighbor in graph.get(node, []):\n            if neighbor not in visited:\n                visited.add(neighbor)\n                queue.append(neighbor)\n    return result\n```",
     "coding_challenge"),
    ("Write a Python function to find all permutations of a string.",
     "```python\ndef permutations(s):\n    if len(s) <= 1:\n        return [s]\n    result = []\n    for i, char in enumerate(s):\n        remaining = s[:i] + s[i+1:]\n        for perm in permutations(remaining):\n            result.append(char + perm)\n    return result\n\n# permutations('abc') -> ['abc', 'acb', 'bac', 'bca', 'cab', 'cba']\n```",
     "coding_challenge"),
]

for prompt, response, domain in challenges:
    add(prompt, response, domain)

# Generate variations of challenges
for base_prompt, base_response, domain in challenges:
    # "Write in JavaScript" variant
    js_response = base_response.replace("python", "javascript").replace("def ", "function ").replace("self.", "this.")
    add(base_prompt.replace("Python", "JavaScript"),
        js_response,
        "coding_challenge_js")

code_count = len(pairs) - math_count
print("  Coding challenge pairs: %d" % code_count)

# ============================================================
# 3. EXPLAIN LIKE I'M 5 VERSIONS (1000+)
# ============================================================
print("[3/6] ELI5 pairs...")

eli5_topics = {
    "How does the internet work?": "Imagine you want to send a letter to your friend. You write it, put it in an envelope with your friend's address, and give it to the mailman. The internet works similarly! When you type a website name, your computer sends a message through wires (like roads) to a big computer (server) that has the website. That computer sends the website back to you through the same wires. It happens so fast it feels instant!",
    "What is gravity?": "Gravity is like an invisible force that pulls things toward each other. The Earth is really big, so it pulls everything toward its center - that's why when you jump, you come back down! The bigger something is, the stronger it pulls. The Sun's gravity is what keeps Earth going around it, like a ball on a string.",
    "How do computers work?": "A computer is like a really fast calculator that can also remember things. Inside, there's a brain called a CPU that does math really quickly. It thinks in only two numbers: 0 and 1 (like on and off switches). By using millions of tiny switches really fast, it can show pictures, play music, and run games!",
    "What is DNA?": "DNA is like a recipe book inside every tiny cell in your body. It has instructions for making YOU - your eye color, hair color, how tall you'll be. It looks like a twisted ladder (double helix). You got half your recipe book from your mom and half from your dad, which is why you might look like both of them!",
    "How do airplanes fly?": "Airplane wings have a special shape - curved on top and flat on bottom. When the plane moves fast, air goes over and under the wings. The air on top moves faster and pushes less, while the air below pushes more. This difference in pushing lifts the plane up! The engines push the plane forward fast enough for this to work.",
    "What is electricity?": "Electricity is tiny particles called electrons moving through wires, kind of like water flowing through a pipe. When you flip a light switch, you're opening a path for these electrons to flow. They zoom through the wire to the light bulb, making it glow. Batteries are like little electron pumps that push electrons through your toys!",
    "How does a rainbow form?": "When sunlight hits raindrops, something magical happens! Sunlight looks white but it's actually made of all colors mixed together. The raindrop acts like a tiny prism, bending the light and splitting it into all its colors: red, orange, yellow, green, blue, indigo, and violet. That's why you see rainbows after rain when the sun comes out!",
    "What is a black hole?": "A black hole is like a cosmic vacuum cleaner, but way more powerful. When a really big star runs out of fuel and dies, it can collapse into a tiny point that's incredibly heavy. Its gravity is so strong that nothing can escape - not even light! That's why it's 'black'. If you got too close, you'd be stretched out like spaghetti!",
    "How do vaccines work?": "Vaccines are like a training course for your body's soldiers (immune system). They show your body a weakened or fake version of a germ, so your soldiers can practice fighting it without you getting sick. Then if the real germ comes along, your soldiers already know how to beat it! It's like doing a fire drill so you know what to do in a real fire.",
    "What is artificial intelligence?": "AI is when we teach computers to do things that normally need a human brain - like recognizing faces, understanding speech, or playing games. We show the computer lots of examples (like thousands of cat pictures), and it learns patterns. It's not really 'thinking' like you do - it's more like a very good pattern-finding machine!",
    "How does Wi-Fi work?": "Wi-Fi is like an invisible walkie-talkie between your device and a box called a router. The router is connected to the internet by a wire. When you want a webpage, your device sends a radio signal to the router saying 'please get this for me.' The router grabs it from the internet and sends it back to you through radio waves - all in less than a blink!",
    "What is a virus?": "A virus is like a tiny pirate that invades your body's cells. It's so small you can't see it, even with a regular microscope. It sneaks into a cell and uses the cell's tools to make copies of itself, then breaks out to invade more cells. Your immune system sends soldier cells to fight them off, which is why you get a fever - it's your body's battle!",
    "How do magnets work?": "Every magnet has an invisible force field around it, with a North and South pole. Opposite poles attract (North loves South), and same poles repel (North pushes North away). This happens because of how tiny particles called electrons spin inside the magnet. Earth itself is a giant magnet, which is why compass needles always point North!",
    "What is climate change?": "Earth is wrapped in a blanket of gases called the atmosphere. Some gases (like CO2) trap heat from the sun, keeping Earth warm enough for life - like a greenhouse. But humans are adding too much of these gases by burning fuel for cars and factories. The blanket is getting too thick, making Earth warmer than it should be, which changes weather patterns.",
    "How do touchscreens work?": "Your finger has a tiny bit of electricity in it. The touchscreen has a grid of invisible electric sensors under the glass. When your finger touches the screen, it changes the electricity at that spot. The phone detects exactly where you touched and responds! That's why a glove doesn't work - it blocks your finger's electricity.",
}

for question, answer in eli5_topics.items():
    add("Explain simply: %s" % question, answer, "eli5")
    add("ELI5: %s" % question, "Here's a simple explanation: %s" % answer, "eli5")

eli5_count = len(pairs) - math_count - code_count
print("  ELI5 pairs: %d" % eli5_count)

# ============================================================
# 4. WORD DEFINITIONS (1000+)
# ============================================================
print("[4/6] Word definitions...")

words = {
    "algorithm": "A step-by-step procedure for solving a problem or performing a computation",
    "paradigm": "A typical example or pattern of something; a model or framework",
    "ephemeral": "Lasting for a very short time; transient",
    "ubiquitous": "Present, appearing, or found everywhere",
    "pragmatic": "Dealing with things sensibly and realistically; practical",
    "ambiguous": "Open to more than one interpretation; not clear",
    "eloquent": "Fluent or persuasive in speaking or writing",
    "resilient": "Able to withstand or recover quickly from difficult conditions",
    "volatile": "Liable to change rapidly and unpredictably; unstable",
    "benevolent": "Well meaning and kindly; charitable",
    "meticulous": "Showing great attention to detail; very careful and precise",
    "arbitrary": "Based on random choice or personal whim, rather than reason or system",
    "concurrent": "Existing, happening, or done at the same time",
    "deprecated": "No longer recommended for use; superseded by something better",
    "empirical": "Based on observation or experience rather than theory",
    "heuristic": "A practical approach to problem-solving that may not be optimal but is sufficient",
    "idempotent": "An operation that produces the same result whether applied once or multiple times",
    "latency": "The delay between a request and a response",
    "mutable": "Able to be changed; not fixed",
    "immutable": "Unable to be changed; permanent",
    "nominal": "Existing in name only; very small or minimal",
    "orthogonal": "Independent or unrelated; not affecting or dependent on each other",
    "polymorphism": "The ability of different types to be treated through the same interface",
    "redundant": "Not needed; exceeding what is necessary (in engineering: backup systems)",
    "semantic": "Relating to meaning in language or logic",
    "syntactic": "Relating to the arrangement of words or symbols according to rules",
    "taxonomy": "A scheme of classification; a hierarchical organization of categories",
    "verbose": "Using more words than needed; overly detailed or wordy",
    "abstract": "Existing in thought or as an idea but not having physical existence",
    "aggregate": "A whole formed by combining several elements",
    "asynchronous": "Not occurring at the same time; independent of time sequence",
    "binary": "Relating to a system of two elements; base-2 numeral system",
    "boolean": "Having only two possible values: true or false",
    "cache": "A store of things for future use; temporary data storage for quick access",
    "compile": "To convert source code into machine code; to gather and assemble",
    "debug": "To identify and remove errors from computer software",
    "deploy": "To move software from development to production; to make available",
    "encrypt": "To convert information into a code to prevent unauthorized access",
    "iterate": "To perform repeatedly; to go through a sequence one item at a time",
    "kernel": "The core component of an operating system that manages hardware resources",
    "legacy": "Old or outdated but still in use; inherited from a previous version",
    "middleware": "Software that connects different applications or components together",
    "node": "A point of connection in a network; an element in a data structure",
    "optimize": "To make the best or most effective use of; to improve performance",
    "parse": "To analyze and break down into component parts for understanding",
    "query": "A request for data or information from a database or search engine",
    "recursive": "Relating to a process that repeats itself; a function that calls itself",
    "schema": "A plan or framework; the structure definition of a database",
    "serialize": "To convert data into a format suitable for storage or transmission",
    "thread": "A sequence of instructions within a process that can run independently",
    "token": "A discrete unit of data; a piece of text processed by a language model",
    "validate": "To check or confirm that something is correct or meets requirements",
}

for word, definition in words.items():
    add("Define the word '%s'." % word,
        "'%s': %s." % (word.capitalize(), definition),
        "vocabulary")
    add("What does '%s' mean?" % word,
        "The word '%s' means: %s." % (word, definition),
        "vocabulary")
    add("Use '%s' in a sentence." % word,
        "Definition: %s.\n\nExample: The system's %s design ensures reliable performance." % (definition, word),
        "vocabulary")

vocab_count = len(pairs) - math_count - code_count - eli5_count
print("  Vocabulary pairs: %d" % vocab_count)

# ============================================================
# 5. REGEX PATTERNS (500+)
# ============================================================
print("[5/6] Regex patterns...")

regex_patterns = {
    r"\d+": "Matches one or more digits (0-9). Example: matches '123' in 'abc123def'.",
    r"\w+": "Matches one or more word characters (letters, digits, underscore). Example: matches 'hello' in 'hello world'.",
    r"\s+": "Matches one or more whitespace characters (space, tab, newline).",
    r"[a-z]+": "Matches one or more lowercase letters.",
    r"[A-Z]+": "Matches one or more uppercase letters.",
    r"[a-zA-Z]+": "Matches one or more letters (any case).",
    r"[0-9]{3}": "Matches exactly 3 digits. Example: '123' but not '12' or '1234'.",
    r"^hello": "Matches 'hello' only at the start of a string.",
    r"world$": "Matches 'world' only at the end of a string.",
    r"colou?r": "Matches 'color' or 'colour' (the 'u' is optional).",
    r"\b\w+\b": "Matches whole words (word boundary on both sides).",
    r"[^a-z]": "Matches any character that is NOT a lowercase letter.",
    r"(cat|dog)": "Matches either 'cat' or 'dog' (alternation with grouping).",
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}": "Matches IPv4 address format like '192.168.1.1'.",
    r"https?://\S+": "Matches HTTP and HTTPS URLs.",
    r"[\w.+-]+@[\w-]+\.[\w.]+": "Matches email addresses like 'user@example.com'.",
    r"\d{4}-\d{2}-\d{2}": "Matches dates in YYYY-MM-DD format.",
    r"#[0-9a-fA-F]{6}": "Matches hex color codes like '#FF5733'.",
    r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}": "Matches US phone numbers in various formats.",
    r"(?<=@)\w+": "Positive lookbehind: matches word after @ symbol.",
    r"\w+(?=ing)": "Positive lookahead: matches word before 'ing'.",
    r"(?:https?://)?([\w.-]+)": "Non-capturing group for protocol, capturing group for domain.",
}

for pattern, desc in regex_patterns.items():
    add("What does the regex pattern '%s' match?" % pattern,
        "The regex `%s`: %s" % (pattern, desc),
        "regex")
    add("Write a regex pattern for: %s" % desc.split('.')[0].lower(),
        "Use this regex pattern: `%s`\n\n%s" % (pattern, desc),
        "regex")

regex_count = len(pairs) - math_count - code_count - eli5_count - vocab_count
print("  Regex pairs: %d" % regex_count)

# ============================================================
# 6. SYSTEM DESIGN CONCEPTS (300+)
# ============================================================
print("[6/6] System design...")

sysdesign = {
    "horizontal scaling": "Adding more machines to handle increased load (scaling out). Opposite of vertical scaling (adding more power to one machine). Requires load balancing and distributed state management.",
    "vertical scaling": "Adding more resources (CPU, RAM, storage) to an existing machine (scaling up). Simpler than horizontal scaling but has a ceiling. Good for databases that are hard to distribute.",
    "load balancing": "Distributing incoming requests across multiple servers to ensure no single server is overwhelmed. Strategies: round-robin, least connections, IP hash, weighted. Improves availability and throughput.",
    "CDN": "Content Delivery Network - geographically distributed servers that cache content closer to users. Reduces latency for static assets (images, CSS, JS). Major providers: Cloudflare, AWS CloudFront, Akamai.",
    "database sharding": "Splitting a database across multiple servers by a shard key (e.g., user ID ranges). Each shard holds a subset of data. Enables horizontal scaling but adds complexity for cross-shard queries.",
    "database replication": "Copying data from one database server to others. Primary-replica: one writable primary, multiple read replicas. Improves read performance and provides failover. Challenge: replication lag.",
    "message queue": "Asynchronous communication between services. Producer sends messages, consumer processes them. Decouples services, handles traffic spikes, enables retry. Examples: RabbitMQ, Kafka, SQS.",
    "API gateway": "Single entry point for all client requests. Handles routing, authentication, rate limiting, caching, request transformation. Simplifies client-side logic. Examples: Kong, AWS API Gateway, Nginx.",
    "service mesh": "Infrastructure layer for service-to-service communication. Handles load balancing, encryption, observability, and traffic management. Implemented as sidecar proxies. Examples: Istio, Linkerd.",
    "event sourcing": "Storing all state changes as a sequence of events rather than current state. Enables audit trails, temporal queries, and state reconstruction. Combined with CQRS for read/write separation.",
    "CAP theorem": "In a distributed system, you can only guarantee 2 of 3: Consistency (all nodes see same data), Availability (every request gets a response), Partition tolerance (system works despite network failures). You must choose PA or CP.",
    "rate limiting": "Controlling the number of requests a client can make in a time window. Prevents abuse and protects resources. Algorithms: token bucket, leaky bucket, fixed window, sliding window.",
    "circuit breaker": "Pattern that prevents cascading failures. States: closed (normal), open (failures detected, reject calls), half-open (test if service recovered). Like an electrical circuit breaker.",
    "caching strategies": "Write-through: write to cache and DB simultaneously. Write-back: write to cache, async to DB. Write-around: write to DB only, invalidate cache. Cache-aside: app manages cache explicitly.",
    "eventual consistency": "In distributed systems, after an update, all replicas will eventually have the same data, but not immediately. Tradeoff for higher availability. Used in DNS, social media feeds, shopping carts.",
    "microservice communication": "Synchronous: REST, gRPC (request-response). Asynchronous: message queues, event streams (fire-and-forget). Choose sync for immediate response needs, async for decoupling and resilience.",
    "containerization": "Packaging application with all dependencies into a container image. Docker for single containers, Kubernetes for orchestration (scaling, deployment, service discovery). Enables consistent deployment.",
    "blue-green deployment": "Running two identical production environments. Deploy new version to inactive (green) environment, test it, then switch traffic from active (blue) to green. Instant rollback by switching back.",
    "canary deployment": "Gradually rolling out changes to a small subset of users before full deployment. Monitor for errors/performance issues. If problems detected, roll back without affecting most users.",
    "observability": "The ability to understand a system's internal state from its external outputs. Three pillars: metrics (numbers over time), logs (event records), traces (request flow across services).",
}

for concept, desc in sysdesign.items():
    add("Explain %s in system design." % concept,
        "**%s**: %s" % (concept.title(), desc),
        "system_design")
    add("What is %s?" % concept,
        desc,
        "system_design")

sd_count = len(pairs) - math_count - code_count - eli5_count - vocab_count - regex_count
print("  System design pairs: %d" % sd_count)

# ============================================================
# SAVE
# ============================================================
print("\n=== TOTAL SYNTHETIC BOOST PAIRS: %d ===" % len(pairs))

with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(pairs, f, ensure_ascii=False, indent=1)

print("Saved to %s" % OUTPUT)
