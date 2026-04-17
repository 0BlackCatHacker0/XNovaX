"""
SYNTHETIC PAIR GENERATOR - No model needed, pure template + combinatorics.
Target: 12,000+ pairs from templates across many domains.
Writes to: C:/NovaX/data/llm_training/pairs_synthetic.json
"""
import json
import random
import itertools
import hashlib
import os

random.seed(42)
OUTPUT = "C:/NovaX/data/llm_training/pairs_synthetic.json"
pairs = []

def add(prompt, response, domain):
    pairs.append({
        "prompt": prompt.strip(),
        "response": response.strip(),
        "domain": domain,
        "provider": "synthetic_template",
        "model": "template_v1"
    })

# ============================================================
# 1. MATH PAIRS (2000+)
# ============================================================
print("[1/8] Generating math pairs...")

# Arithmetic
ops = [('+', 'sum', lambda a,b: a+b), ('-', 'difference', lambda a,b: a-b),
       ('*', 'product', lambda a,b: a*b)]
for a in range(1, 51):
    for b in range(1, 21):
        for sym, word, fn in ops:
            result = fn(a, b)
            add(f"What is {a} {sym} {b}?",
                f"The {word} of {a} and {b} is {result}.",
                "math_arithmetic")

# Powers and squares
for n in range(1, 101):
    add(f"What is {n} squared?", f"{n} squared is {n**2}.", "math_powers")
    add(f"What is the square root of {n*n}?", f"The square root of {n*n} is {n}.", "math_powers")

# Fractions
for num in range(1, 11):
    for den in range(2, 11):
        if num < den:
            dec = round(num/den, 4)
            add(f"Convert {num}/{den} to a decimal.",
                f"{num}/{den} as a decimal is {dec}.",
                "math_fractions")

# Percentages
for pct in [10, 15, 20, 25, 30, 33, 40, 50, 60, 75, 80, 90, 100]:
    for val in [50, 100, 150, 200, 250, 300, 500, 1000]:
        result = round(pct * val / 100, 2)
        add(f"What is {pct}% of {val}?",
            f"{pct}% of {val} is {result}.",
            "math_percentage")

# Unit conversions
conversions = [
    ("miles", "kilometers", 1.60934),
    ("kilometers", "miles", 0.621371),
    ("pounds", "kilograms", 0.453592),
    ("kilograms", "pounds", 2.20462),
    ("Fahrenheit", "Celsius", None),
    ("inches", "centimeters", 2.54),
    ("feet", "meters", 0.3048),
    ("gallons", "liters", 3.78541),
    ("ounces", "grams", 28.3495),
]
for val in [1, 2, 3, 5, 10, 15, 20, 25, 50, 100]:
    for src, dst, factor in conversions:
        if factor is None:  # F to C
            result = round((val - 32) * 5/9, 2)
            add(f"Convert {val} {src} to {dst}.",
                f"{val} degrees {src} is {result} degrees {dst}.",
                "math_conversion")
        else:
            result = round(val * factor, 4)
            add(f"Convert {val} {src} to {dst}.",
                f"{val} {src} is {result} {dst}.",
                "math_conversion")

# Number properties
for n in range(2, 201):
    is_prime = all(n % i != 0 for i in range(2, int(n**0.5)+1)) and n > 1
    add(f"Is {n} a prime number?",
        f"{'Yes' if is_prime else 'No'}, {n} is {'a prime' if is_prime else 'not a prime'} number." +
        (f" It is only divisible by 1 and {n}." if is_prime else
         f" It is divisible by {next(i for i in range(2, n) if n%i==0)}."),
        "math_number_theory")

    if n <= 50:
        facts = []
        x = n
        d = 2
        while d * d <= x:
            while x % d == 0:
                facts.append(d)
                x //= d
            d += 1
        if x > 1:
            facts.append(x)
        add(f"What is the prime factorization of {n}?",
            f"The prime factorization of {n} is {' x '.join(map(str, facts))}.",
            "math_number_theory")

# Fibonacci
fib = [0, 1]
for i in range(2, 31):
    fib.append(fib[-1] + fib[-2])
for i in range(1, 26):
    add(f"What is the {i}th Fibonacci number?",
        f"The {i}th Fibonacci number is {fib[i]}. The sequence up to this point is: {', '.join(map(str, fib[:i+1]))}.",
        "math_sequences")

print(f"  Math pairs: {len(pairs)}")
math_count = len(pairs)

# ============================================================
# 2. PROGRAMMING PAIRS (2000+)
# ============================================================
print("[2/8] Generating programming pairs...")

# Python built-in explanations
python_builtins = {
    "len()": "Returns the number of items in an object (string, list, dict, etc.).",
    "range()": "Returns a sequence of numbers, commonly used in for loops. range(start, stop, step).",
    "print()": "Outputs text or values to the console. Accepts multiple arguments separated by commas.",
    "type()": "Returns the type of an object, such as <class 'int'>, <class 'str'>, etc.",
    "int()": "Converts a value to an integer. Can convert strings of digits or floats.",
    "str()": "Converts a value to its string representation.",
    "float()": "Converts a value to a floating-point number.",
    "list()": "Creates a new list or converts an iterable to a list.",
    "dict()": "Creates a new dictionary from keyword arguments or an iterable of key-value pairs.",
    "set()": "Creates a new set, which is an unordered collection of unique elements.",
    "tuple()": "Creates a new tuple, which is an immutable sequence.",
    "sorted()": "Returns a new sorted list from an iterable. Accepts key and reverse parameters.",
    "reversed()": "Returns a reversed iterator over a sequence.",
    "enumerate()": "Returns an enumerate object yielding (index, value) pairs from an iterable.",
    "zip()": "Aggregates elements from multiple iterables into tuples.",
    "map()": "Applies a function to every item of an iterable and returns an iterator.",
    "filter()": "Returns an iterator of elements for which a function returns True.",
    "sum()": "Returns the sum of a numeric iterable, with an optional start value.",
    "min()": "Returns the smallest item in an iterable or the smallest of two or more arguments.",
    "max()": "Returns the largest item in an iterable or the largest of two or more arguments.",
    "abs()": "Returns the absolute value of a number.",
    "round()": "Rounds a number to a given precision in decimal digits.",
    "isinstance()": "Returns True if an object is an instance of a class or tuple of classes.",
    "hasattr()": "Returns True if an object has the specified attribute.",
    "getattr()": "Returns the value of a named attribute of an object, with optional default.",
    "input()": "Reads a line of text from the user via the console.",
    "open()": "Opens a file and returns a file object. Common modes: 'r', 'w', 'a', 'rb', 'wb'.",
    "any()": "Returns True if any element of an iterable is true.",
    "all()": "Returns True if all elements of an iterable are true.",
    "chr()": "Returns the character for a Unicode code point.",
    "ord()": "Returns the Unicode code point for a single character.",
    "hex()": "Converts an integer to a hexadecimal string prefixed with '0x'.",
    "bin()": "Converts an integer to a binary string prefixed with '0b'.",
    "oct()": "Converts an integer to an octal string prefixed with '0o'.",
    "id()": "Returns the unique identity of an object (memory address in CPython).",
    "hash()": "Returns the hash value of an object, used for dictionary keys and sets.",
    "dir()": "Returns a list of names in the current scope or attributes of an object.",
    "help()": "Invokes the built-in help system for a module, function, class, or keyword.",
    "callable()": "Returns True if the object appears callable (has __call__ method).",
    "eval()": "Evaluates a Python expression from a string and returns the result.",
    "exec()": "Executes Python code from a string. Does not return a value.",
    "compile()": "Compiles source code into a code object that can be executed by exec() or eval().",
    "globals()": "Returns a dictionary representing the current global symbol table.",
    "locals()": "Returns a dictionary representing the current local symbol table.",
    "vars()": "Returns the __dict__ attribute of an object, or locals() if no argument given.",
    "super()": "Returns a proxy object for delegating method calls to a parent class.",
    "property()": "Returns a property attribute for a class, enabling getter/setter/deleter.",
    "staticmethod()": "Transforms a method into a static method that doesn't receive self.",
    "classmethod()": "Transforms a method into a class method that receives cls as first argument.",
    "iter()": "Returns an iterator object for the given iterable.",
    "next()": "Retrieves the next item from an iterator.",
    "format()": "Formats a value according to a format specification.",
    "repr()": "Returns a string containing a printable representation of an object.",
    "bool()": "Converts a value to Boolean (True or False).",
    "bytes()": "Returns a bytes object, which is an immutable sequence of integers (0-255).",
    "bytearray()": "Returns a mutable bytearray object.",
    "memoryview()": "Returns a memory view object from a bytes-like object.",
    "complex()": "Returns a complex number with real and imaginary parts.",
    "frozenset()": "Returns an immutable frozenset object.",
    "slice()": "Returns a slice object used for extended indexing.",
    "pow()": "Returns base raised to power, optionally modulo. pow(base, exp[, mod]).",
    "divmod()": "Returns a tuple of quotient and remainder of integer division.",
}

for func, desc in python_builtins.items():
    add(f"What does the Python built-in function {func} do?",
        f"The Python built-in `{func}` {desc.lower() if desc[0].isupper() else desc}\n\nExample usage:\n```python\nresult = {func.replace('()','')}(argument)\n```",
        "programming_python")
    add(f"Explain {func} in Python.",
        f"`{func}` in Python: {desc}",
        "programming_python")

# Data structures
ds_explanations = {
    "array": "A contiguous block of memory storing elements of the same type. O(1) access by index, O(n) insertion/deletion. Used when you need fast random access.",
    "linked list": "A sequence of nodes where each node contains data and a pointer to the next node. O(1) insertion/deletion at head, O(n) access. Used for frequent insertions.",
    "stack": "A LIFO (Last In, First Out) data structure. Push adds to top, pop removes from top. O(1) for both. Used for undo operations, expression parsing, DFS.",
    "queue": "A FIFO (First In, First Out) data structure. Enqueue adds to back, dequeue removes from front. O(1) for both with proper implementation. Used for BFS, scheduling.",
    "hash table": "Maps keys to values using a hash function. Average O(1) for insert, delete, lookup. Handles collisions via chaining or open addressing. Used for dictionaries, caches.",
    "binary search tree": "A tree where each node's left children are smaller and right children are larger. O(log n) average for search, insert, delete. Used for sorted data and range queries.",
    "heap": "A complete binary tree satisfying the heap property (parent >= children for max-heap). O(1) to find max/min, O(log n) to insert or extract. Used for priority queues.",
    "graph": "A set of vertices connected by edges. Can be directed/undirected, weighted/unweighted. Represented as adjacency matrix or list. Used for networks, paths, relationships.",
    "trie": "A tree-like structure for storing strings character by character. O(m) lookup where m is key length. Space-efficient for shared prefixes. Used for autocomplete, spell check.",
    "red-black tree": "A self-balancing BST with O(log n) guaranteed for insert, delete, search. Each node is red or black with rules ensuring balance. Used in language standard libraries.",
    "B-tree": "A self-balancing tree optimized for disk access. Nodes can have multiple keys and children. Used in databases and file systems for indexing.",
    "skip list": "A probabilistic data structure using multiple levels of linked lists. O(log n) average for search, insert, delete. Simpler alternative to balanced trees.",
    "deque": "A double-ended queue supporting O(1) insertion and deletion at both ends. Used for sliding window problems and work-stealing algorithms.",
    "bloom filter": "A probabilistic data structure for set membership testing. Can have false positives but no false negatives. Very space-efficient. Used for caches and spell checkers.",
    "disjoint set": "Also called Union-Find. Tracks partitions of a set. Near O(1) for union and find with path compression. Used for connected components and Kruskal's algorithm.",
}
for ds, desc in ds_explanations.items():
    add(f"Explain the {ds} data structure.",
        f"**{ds.title()}**: {desc}",
        "programming_ds")
    add(f"What is a {ds} and when would you use it?",
        f"A {ds} is: {desc}",
        "programming_ds")
    add(f"What is the time complexity of operations on a {ds}?",
        f"For a {ds}: {desc}",
        "programming_ds")

# Algorithm explanations
algorithms = {
    "bubble sort": ("O(n^2)", "Repeatedly swaps adjacent elements if they are in wrong order. Simple but inefficient for large datasets."),
    "selection sort": ("O(n^2)", "Finds the minimum element and places it at the beginning, repeating for each position. Not stable."),
    "insertion sort": ("O(n^2)", "Builds sorted array one element at a time by inserting each into its correct position. Efficient for small/nearly sorted data."),
    "merge sort": ("O(n log n)", "Divides array in half, recursively sorts each half, then merges. Stable, guaranteed O(n log n), but uses O(n) extra space."),
    "quick sort": ("O(n log n) average", "Picks a pivot, partitions array around it, recursively sorts partitions. In-place but O(n^2) worst case."),
    "heap sort": ("O(n log n)", "Builds a max-heap, repeatedly extracts the maximum. In-place, not stable, guaranteed O(n log n)."),
    "binary search": ("O(log n)", "Searches sorted array by repeatedly dividing search interval in half. Requires sorted input."),
    "depth-first search": ("O(V+E)", "Explores as far as possible along each branch before backtracking. Uses stack/recursion. Good for path finding, cycle detection."),
    "breadth-first search": ("O(V+E)", "Explores all neighbors at current depth before moving deeper. Uses queue. Finds shortest path in unweighted graphs."),
    "Dijkstra's algorithm": ("O((V+E) log V)", "Finds shortest paths from source to all vertices in weighted graph with non-negative weights. Uses priority queue."),
    "dynamic programming": ("varies", "Breaks problems into overlapping subproblems, stores results to avoid recomputation. Bottom-up (tabulation) or top-down (memoization)."),
    "greedy algorithm": ("varies", "Makes locally optimal choice at each step. Works when local optima lead to global optimum (e.g., Huffman coding, Kruskal's)."),
    "backtracking": ("exponential", "Explores all potential solutions by building candidates incrementally and abandoning paths that cannot lead to valid solutions."),
    "A* search": ("O(b^d)", "Best-first search using f(n) = g(n) + h(n). Finds optimal path if heuristic is admissible. Used in pathfinding and games."),
    "topological sort": ("O(V+E)", "Linear ordering of vertices in a DAG such that for every edge (u,v), u comes before v. Used for dependency resolution."),
}
for algo, (complexity, desc) in algorithms.items():
    add(f"Explain {algo}.",
        f"**{algo.title()}** (Time complexity: {complexity}): {desc}",
        "programming_algorithms")
    add(f"What is the time complexity of {algo}?",
        f"The time complexity of {algo} is {complexity}. {desc}",
        "programming_algorithms")
    add(f"When should I use {algo}?",
        f"{algo.title()} ({complexity}): {desc}",
        "programming_algorithms")

# Common code patterns
patterns = [
    ("How do I reverse a string in Python?", "To reverse a string in Python:\n```python\ns = 'hello'\nreversed_s = s[::-1]  # 'olleh'\n# Or: reversed_s = ''.join(reversed(s))\n```", "programming_python"),
    ("How do I read a file in Python?", "To read a file in Python:\n```python\nwith open('file.txt', 'r') as f:\n    content = f.read()  # Read entire file\n    # Or: lines = f.readlines()  # Read as list of lines\n```", "programming_python"),
    ("How do I sort a list in Python?", "To sort a list in Python:\n```python\nmy_list = [3, 1, 4, 1, 5]\nsorted_list = sorted(my_list)  # Returns new sorted list\nmy_list.sort()  # Sorts in place\nmy_list.sort(reverse=True)  # Descending\nmy_list.sort(key=lambda x: x.name)  # Custom key\n```", "programming_python"),
    ("How do I handle exceptions in Python?", "Exception handling in Python:\n```python\ntry:\n    result = risky_operation()\nexcept ValueError as e:\n    print(f'Value error: {e}')\nexcept Exception as e:\n    print(f'Unexpected error: {e}')\nfinally:\n    cleanup()\n```", "programming_python"),
    ("How do I create a class in Python?", "Creating a class in Python:\n```python\nclass Dog:\n    def __init__(self, name, breed):\n        self.name = name\n        self.breed = breed\n    \n    def bark(self):\n        return f'{self.name} says Woof!'\n\nmy_dog = Dog('Rex', 'Labrador')\nprint(my_dog.bark())\n```", "programming_python"),
    ("How do I use list comprehension in Python?", "List comprehension in Python:\n```python\n# Basic\nsquares = [x**2 for x in range(10)]\n# With condition\nevens = [x for x in range(20) if x % 2 == 0]\n# Nested\nflat = [x for row in matrix for x in row]\n# Dict comprehension\nd = {k: v for k, v in pairs}\n```", "programming_python"),
    ("How do I make an HTTP request in Python?", "Making HTTP requests with the requests library:\n```python\nimport requests\n\n# GET\nresponse = requests.get('https://api.example.com/data')\ndata = response.json()\n\n# POST\nresponse = requests.post('https://api.example.com/data',\n    json={'key': 'value'},\n    headers={'Authorization': 'Bearer token'})\n```", "programming_python"),
    ("How do I use decorators in Python?", "Python decorators wrap functions to extend behavior:\n```python\ndef timer(func):\n    import time\n    def wrapper(*args, **kwargs):\n        start = time.time()\n        result = func(*args, **kwargs)\n        print(f'{func.__name__} took {time.time()-start:.2f}s')\n        return result\n    return wrapper\n\n@timer\ndef slow_function():\n    time.sleep(1)\n```", "programming_python"),
    ("How do I use async/await in Python?", "Async programming in Python:\n```python\nimport asyncio\n\nasync def fetch_data(url):\n    async with aiohttp.ClientSession() as session:\n        async with session.get(url) as response:\n            return await response.json()\n\nasync def main():\n    data = await fetch_data('https://api.example.com')\n    # Or run concurrently:\n    results = await asyncio.gather(fetch_data(url1), fetch_data(url2))\n\nasyncio.run(main())\n```", "programming_python"),
    ("How do I use generators in Python?", "Generators yield values lazily:\n```python\ndef fibonacci():\n    a, b = 0, 1\n    while True:\n        yield a\n        a, b = b, a + b\n\nfib = fibonacci()\nfor _ in range(10):\n    print(next(fib))  # 0, 1, 1, 2, 3, 5, 8, 13, 21, 34\n\n# Generator expression\nsquares = (x**2 for x in range(1000000))  # Memory efficient\n```", "programming_python"),
]
for p, r, d in patterns:
    add(p, r, d)

# JavaScript equivalents
js_patterns = [
    ("How do I declare variables in JavaScript?", "Variable declarations in JavaScript:\n```javascript\nconst x = 10;     // Block-scoped, cannot be reassigned\nlet y = 20;       // Block-scoped, can be reassigned\nvar z = 30;       // Function-scoped (avoid in modern JS)\n\n// const doesn't mean immutable for objects:\nconst obj = { a: 1 };\nobj.a = 2;  // Valid - the reference is constant, not the value\n```", "programming_javascript"),
    ("How do I use promises in JavaScript?", "Promises in JavaScript:\n```javascript\n// Creating a promise\nconst promise = new Promise((resolve, reject) => {\n  setTimeout(() => resolve('Done!'), 1000);\n});\n\n// Using it\npromise.then(result => console.log(result))\n       .catch(error => console.error(error));\n\n// Async/await (preferred)\nasync function getData() {\n  try {\n    const response = await fetch('/api/data');\n    const data = await response.json();\n    return data;\n  } catch (error) {\n    console.error(error);\n  }\n}\n```", "programming_javascript"),
    ("How do I use array methods in JavaScript?", "Common JavaScript array methods:\n```javascript\nconst arr = [1, 2, 3, 4, 5];\n\narr.map(x => x * 2);           // [2, 4, 6, 8, 10]\narr.filter(x => x > 3);        // [4, 5]\narr.reduce((sum, x) => sum + x, 0); // 15\narr.find(x => x > 3);          // 4\narr.some(x => x > 4);          // true\narr.every(x => x > 0);         // true\narr.forEach(x => console.log(x));\n[...arr, 6];                    // [1, 2, 3, 4, 5, 6]\n```", "programming_javascript"),
    ("Explain closures in JavaScript.", "A closure is a function that retains access to its outer scope's variables even after the outer function has returned:\n```javascript\nfunction counter() {\n  let count = 0;\n  return {\n    increment: () => ++count,\n    decrement: () => --count,\n    getCount: () => count\n  };\n}\n\nconst c = counter();\nc.increment(); // 1\nc.increment(); // 2\nc.getCount();  // 2\n```\nClosures are fundamental for data privacy, callbacks, and functional patterns.", "programming_javascript"),
]
for p, r, d in js_patterns:
    add(p, r, d)

# Rust patterns
rust_patterns = [
    ("What is ownership in Rust?", "Ownership is Rust's core memory safety mechanism with three rules:\n1. Each value has exactly one owner\n2. When the owner goes out of scope, the value is dropped\n3. Ownership can be transferred (moved) or borrowed\n\n```rust\nlet s1 = String::from(\"hello\");\nlet s2 = s1;  // s1 is moved, no longer valid\n// let s3 = s1;  // ERROR: value used after move\n\nlet s4 = s2.clone();  // Deep copy, both valid\n```", "programming_rust"),
    ("Explain borrowing in Rust.", "Borrowing lets you reference a value without taking ownership:\n```rust\nfn calculate_length(s: &String) -> usize {  // Immutable borrow\n    s.len()\n}\n\nfn add_exclaim(s: &mut String) {  // Mutable borrow\n    s.push_str(\"!\");\n}\n\nlet mut s = String::from(\"hello\");\nlet len = calculate_length(&s);  // Borrow immutably\nadd_exclaim(&mut s);  // Borrow mutably\n```\nRules: many immutable borrows OR one mutable borrow at a time.", "programming_rust"),
    ("What are lifetimes in Rust?", "Lifetimes ensure references are valid for as long as they're used:\n```rust\nfn longest<'a>(x: &'a str, y: &'a str) -> &'a str {\n    if x.len() > y.len() { x } else { y }\n}\n\nstruct Config<'a> {\n    name: &'a str,  // Config cannot outlive the string it borrows\n}\n```\nLifetimes prevent dangling references at compile time with zero runtime cost.", "programming_rust"),
    ("What is pattern matching in Rust?", "Pattern matching with match is exhaustive and powerful:\n```rust\nenum Shape {\n    Circle(f64),\n    Rectangle(f64, f64),\n    Triangle(f64, f64, f64),\n}\n\nfn area(shape: &Shape) -> f64 {\n    match shape {\n        Shape::Circle(r) => std::f64::consts::PI * r * r,\n        Shape::Rectangle(w, h) => w * h,\n        Shape::Triangle(a, b, c) => {\n            let s = (a + b + c) / 2.0;\n            (s * (s-a) * (s-b) * (s-c)).sqrt()\n        }\n    }\n}\n```", "programming_rust"),
]
for p, r, d in rust_patterns:
    add(p, r, d)

prog_count = len(pairs) - math_count
print(f"  Programming pairs: {prog_count}")

# ============================================================
# 3. SCIENCE PAIRS (1500+)
# ============================================================
print("[3/8] Generating science pairs...")

# Physics constants and formulas
physics = {
    "speed of light": ("299,792,458 m/s (approximately 3 x 10^8 m/s)", "The maximum speed at which information and matter can travel in the universe. Denoted as 'c'. Fundamental to Einstein's special relativity: E = mc^2."),
    "gravitational constant": ("6.674 x 10^-11 N m^2/kg^2", "Denoted G, it determines the strength of gravitational attraction between masses. F = G * m1 * m2 / r^2 (Newton's law of gravitation)."),
    "Planck's constant": ("6.626 x 10^-34 J*s", "Fundamental constant relating energy of a photon to its frequency: E = hf. Central to quantum mechanics. Reduced form: h-bar = h/(2*pi)."),
    "Boltzmann constant": ("1.381 x 10^-23 J/K", "Relates average kinetic energy of particles in a gas to temperature. Bridges macroscopic thermodynamics and microscopic statistical mechanics."),
    "Avogadro's number": ("6.022 x 10^23 per mole", "The number of atoms, molecules, or particles in one mole of a substance. Connects atomic-scale measurements to macroscopic quantities."),
    "electron mass": ("9.109 x 10^-31 kg", "The rest mass of an electron. Much lighter than protons and neutrons (about 1/1836 of proton mass). Important in atomic and particle physics."),
    "proton mass": ("1.673 x 10^-27 kg", "The rest mass of a proton. About 938 MeV/c^2. Protons are composed of quarks held together by the strong force."),
    "elementary charge": ("1.602 x 10^-19 C", "The electric charge carried by a single proton (positive) or electron (negative). Fundamental unit of electric charge."),
}
for const, (value, desc) in physics.items():
    add(f"What is the {const}?",
        f"The {const} is {value}. {desc}",
        "science_physics")
    add(f"What is the value of the {const}?",
        f"The {const} = {value}.",
        "science_physics")

# Chemistry elements
elements = [
    (1, "Hydrogen", "H", "Lightest element, most abundant in universe, used in fuel cells"),
    (2, "Helium", "He", "Noble gas, second lightest, used in balloons and cryogenics"),
    (6, "Carbon", "C", "Basis of organic chemistry, forms 4 bonds, found in all life"),
    (7, "Nitrogen", "N", "Makes up 78% of atmosphere, essential for amino acids and DNA"),
    (8, "Oxygen", "O", "Essential for respiration, makes up 21% of atmosphere"),
    (11, "Sodium", "Na", "Alkali metal, reacts vigorously with water, essential electrolyte"),
    (12, "Magnesium", "Mg", "Light metal, used in alloys, essential for chlorophyll"),
    (13, "Aluminum", "Al", "Most abundant metal in Earth's crust, lightweight and corrosion-resistant"),
    (14, "Silicon", "Si", "Semiconductor, second most abundant in crust, basis of computer chips"),
    (15, "Phosphorus", "P", "Essential for DNA and ATP, used in fertilizers"),
    (16, "Sulfur", "S", "Yellow nonmetal, used in sulfuric acid production, found in proteins"),
    (17, "Chlorine", "Cl", "Halogen, used in water purification and PVC production"),
    (19, "Potassium", "K", "Alkali metal, essential for nerve function, found in bananas"),
    (20, "Calcium", "Ca", "Alkaline earth metal, essential for bones and teeth"),
    (26, "Iron", "Fe", "Most common metal on Earth by mass, essential for hemoglobin"),
    (29, "Copper", "Cu", "Excellent conductor, used in wiring, turns green when oxidized"),
    (30, "Zinc", "Zn", "Used in galvanization, essential trace element for immune function"),
    (47, "Silver", "Ag", "Best conductor of electricity, precious metal, antimicrobial"),
    (79, "Gold", "Au", "Noble metal, excellent conductor, does not corrode, symbol of wealth"),
    (82, "Lead", "Pb", "Dense toxic metal, formerly used in paint and gasoline"),
    (92, "Uranium", "U", "Radioactive, used in nuclear power and weapons"),
]
for num, name, sym, desc in elements:
    add(f"What is {name} on the periodic table?",
        f"{name} ({sym}) is element {num}. {desc}.",
        "science_chemistry")
    add(f"What is element {num} on the periodic table?",
        f"Element {num} is {name} ({sym}). {desc}.",
        "science_chemistry")
    add(f"What is the atomic number of {name}?",
        f"The atomic number of {name} ({sym}) is {num}.",
        "science_chemistry")

# Biology
bio_concepts = {
    "DNA": "Deoxyribonucleic acid (DNA) is a double-helix molecule that carries genetic instructions for all known organisms. It consists of nucleotides with bases: adenine (A), thymine (T), guanine (G), and cytosine (C). A pairs with T, G pairs with C. DNA replication is semi-conservative.",
    "RNA": "Ribonucleic acid (RNA) is a single-stranded molecule involved in protein synthesis. Types include mRNA (carries genetic message), tRNA (transfers amino acids), and rRNA (forms ribosomes). RNA uses uracil (U) instead of thymine.",
    "mitosis": "Mitosis is cell division producing two identical daughter cells. Phases: prophase (chromosomes condense), metaphase (align at center), anaphase (separate), telophase (new nuclei form), cytokinesis (cell splits). Used for growth and repair.",
    "meiosis": "Meiosis is cell division producing four genetically unique gametes (sex cells) with half the chromosome number. Involves two divisions (meiosis I and II). Crossing over and independent assortment create genetic diversity.",
    "photosynthesis": "Photosynthesis converts light energy to chemical energy: 6CO2 + 6H2O + light -> C6H12O6 + 6O2. Light reactions occur in thylakoids (produce ATP and NADPH). Calvin cycle occurs in stroma (fixes CO2 into glucose).",
    "cellular respiration": "Cellular respiration breaks down glucose to produce ATP: C6H12O6 + 6O2 -> 6CO2 + 6H2O + ATP. Three stages: glycolysis (cytoplasm, 2 ATP), Krebs cycle (mitochondrial matrix, 2 ATP), electron transport chain (inner membrane, 34 ATP).",
    "natural selection": "Natural selection is the mechanism of evolution proposed by Darwin. Organisms with traits better suited to their environment survive and reproduce more (survival of the fittest). Over time, advantageous traits become more common in a population.",
    "protein synthesis": "Protein synthesis involves transcription (DNA to mRNA in nucleus) and translation (mRNA to protein at ribosomes). mRNA codons are read in triplets, each coding for a specific amino acid. tRNA molecules bring matching amino acids.",
    "immune system": "The immune system defends against pathogens. Innate immunity provides immediate, non-specific defense (skin, inflammation). Adaptive immunity is specific and has memory (B cells produce antibodies, T cells kill infected cells).",
    "evolution": "Evolution is the change in allele frequencies in a population over time. Mechanisms: natural selection, genetic drift, gene flow, and mutation. Evidence includes fossil record, comparative anatomy, DNA similarities, and observed speciation.",
}
for concept, desc in bio_concepts.items():
    add(f"What is {concept}?", desc, "science_biology")
    add(f"Explain {concept}.",
        f"**{concept.title()}**: {desc}",
        "science_biology")

science_count = len(pairs) - math_count - prog_count
print(f"  Science pairs: {science_count}")

# ============================================================
# 4. AI/ML PAIRS (1500+)
# ============================================================
print("[4/8] Generating AI/ML pairs...")

ml_concepts = {
    "neural network": "A neural network is a computing system inspired by biological neural networks. It consists of layers of interconnected nodes (neurons). Input layer receives data, hidden layers process it through weighted connections and activation functions, output layer produces predictions. Trained by backpropagation to minimize a loss function.",
    "gradient descent": "An optimization algorithm that iteratively adjusts parameters to minimize a loss function. Computes the gradient (partial derivatives) and moves in the opposite direction. Variants: SGD (stochastic, one sample), mini-batch (subset), Adam (adaptive learning rates). Learning rate controls step size.",
    "backpropagation": "The algorithm for computing gradients in neural networks. Uses the chain rule to propagate error from output layer back through the network, computing how much each weight contributed to the error. Enables efficient training of deep networks.",
    "convolutional neural network": "A CNN uses convolutional layers that apply learnable filters to detect spatial features. Architecture: convolutional layers (feature extraction), pooling layers (downsampling), fully connected layers (classification). Excellent for images, achieving translation invariance through weight sharing.",
    "recurrent neural network": "An RNN processes sequential data by maintaining hidden state that captures information from previous steps. Each step takes current input and previous hidden state. Issues: vanishing/exploding gradients. Solutions: LSTM and GRU architectures with gating mechanisms.",
    "transformer": "A transformer uses self-attention to process all positions in parallel, unlike RNNs. Architecture: encoder (self-attention + feed-forward) and decoder (masked self-attention + cross-attention + feed-forward). Scales well and captures long-range dependencies. Basis for GPT, BERT, etc.",
    "attention mechanism": "Attention allows a model to focus on relevant parts of input when producing output. Computes alignment scores between query and key vectors, applies softmax, and takes weighted sum of value vectors. Multi-head attention runs multiple attention functions in parallel.",
    "transfer learning": "Transfer learning applies knowledge from one task to another. Pre-train a model on a large dataset (e.g., ImageNet for vision, large text corpus for NLP), then fine-tune on a smaller target dataset. Dramatically reduces data and compute requirements.",
    "reinforcement learning": "An agent learns by interacting with an environment, receiving rewards or penalties. Key concepts: state, action, reward, policy, value function. Algorithms: Q-learning, policy gradient, PPO. Used in games, robotics, and recommendation systems.",
    "generative adversarial network": "GANs consist of two networks: a generator (creates fake data) and a discriminator (distinguishes real from fake). They train adversarially until the generator produces data indistinguishable from real. Used for image synthesis, style transfer, data augmentation.",
    "overfitting": "When a model learns training data too well, including noise, and performs poorly on new data. Signs: low training error, high validation error. Solutions: regularization (L1/L2, dropout), early stopping, more data, data augmentation, simpler model.",
    "underfitting": "When a model is too simple to capture patterns in the data. Signs: high error on both training and validation sets. Solutions: more complex model, more features, less regularization, longer training.",
    "batch normalization": "Normalizes layer inputs to have zero mean and unit variance within each mini-batch. Reduces internal covariate shift, allowing higher learning rates and faster training. Applied after linear transformation, before activation function.",
    "dropout": "Regularization technique that randomly sets a fraction of neurons to zero during training. Prevents co-adaptation of neurons and acts like an ensemble of sub-networks. Typically drop rate of 0.1-0.5. Not applied during inference.",
    "learning rate": "The step size for parameter updates during training. Too high: divergence or oscillation. Too low: slow convergence, stuck in local minima. Solutions: learning rate scheduling (warmup, cosine decay), adaptive methods (Adam, AdaGrad).",
    "loss function": "Measures how far model predictions are from true values. Common choices: MSE (regression), cross-entropy (classification), binary cross-entropy (binary), hinge loss (SVM). Choice depends on task and output distribution.",
    "embedding": "A learned dense vector representation of discrete data (words, items, categories). Maps high-dimensional sparse data to low-dimensional dense space. Similar items have similar embeddings. Key to NLP (Word2Vec, GloVe) and recommendation systems.",
    "tokenization": "Breaking text into tokens (words, subwords, or characters) for processing. BPE (Byte-Pair Encoding) and SentencePiece learn subword vocabularies. Balance between vocabulary size and sequence length. Critical for LLM performance.",
    "fine-tuning": "Adapting a pre-trained model to a specific task by continuing training on task-specific data. Methods: full fine-tuning (update all weights), LoRA (low-rank adaptation), prefix tuning, prompt tuning. Requires much less data than training from scratch.",
    "RLHF": "Reinforcement Learning from Human Feedback trains language models to align with human preferences. Steps: supervised fine-tuning, train reward model from human comparisons, optimize policy with PPO against reward model. Used in ChatGPT, Claude.",
    "diffusion model": "Generates data by learning to reverse a gradual noising process. Forward process adds Gaussian noise over many steps. Reverse process (the model) learns to denoise. Produces high-quality images. Examples: DALL-E, Stable Diffusion, Midjourney.",
    "quantization": "Reducing model precision from 32-bit float to lower bit-widths (16-bit, 8-bit, 4-bit) to reduce memory and increase speed. Post-training quantization or quantization-aware training. GPTQ, GGUF, and AWQ are popular methods for LLMs.",
    "knowledge distillation": "Training a smaller 'student' model to mimic a larger 'teacher' model. Student learns from teacher's soft probability outputs (dark knowledge), capturing more information than hard labels alone. Produces efficient models for deployment.",
    "mixture of experts": "Architecture using multiple specialized sub-networks (experts) with a gating network that routes each input to the most relevant experts. Only activates a subset of parameters per input, scaling model capacity without proportional compute increase.",
    "RAG": "Retrieval-Augmented Generation combines a retriever (searches relevant documents) with a generator (LLM). Reduces hallucination by grounding responses in retrieved evidence. Components: document store, embedding model, retriever, and generator.",
    "LoRA": "Low-Rank Adaptation freezes pre-trained weights and adds small trainable rank decomposition matrices. Instead of updating W, learns W + BA where B and A are low-rank. Reduces trainable parameters by 10,000x while maintaining quality. Memory efficient.",
    "prompt engineering": "Crafting inputs to language models to elicit desired outputs. Techniques: few-shot examples, chain-of-thought reasoning, role assignment, structured output requests. Critical skill for using LLMs effectively without fine-tuning.",
    "hallucination": "When AI models generate confident but factually incorrect or fabricated information. Causes: statistical pattern matching without true understanding, training data gaps. Mitigations: RAG, fact-checking, confidence calibration, RLHF.",
    "context window": "The maximum number of tokens an LLM can process in a single interaction. Determines how much text the model can 'see'. Modern models range from 4K to 1M+ tokens. Techniques to extend: RoPE, ALiBi, sparse attention, context compression.",
    "perplexity": "A metric measuring how well a language model predicts text. Lower perplexity = better predictions. Calculated as exp(average negative log-likelihood). A perplexity of k means the model is as uncertain as choosing uniformly among k options.",
}
for concept, desc in ml_concepts.items():
    add(f"What is {concept} in machine learning?", desc, "ai_ml")
    add(f"Explain {concept}.", f"**{concept.title()}**: {desc}", "ai_ml")

ai_count = len(pairs) - math_count - prog_count - science_count
print(f"  AI/ML pairs: {ai_count}")

# ============================================================
# 5. GENERAL KNOWLEDGE (1000+)
# ============================================================
print("[5/8] Generating general knowledge pairs...")

# World capitals
capitals = [
    ("France", "Paris"), ("Germany", "Berlin"), ("Japan", "Tokyo"),
    ("United Kingdom", "London"), ("Italy", "Rome"), ("Spain", "Madrid"),
    ("China", "Beijing"), ("India", "New Delhi"), ("Brazil", "Brasilia"),
    ("Russia", "Moscow"), ("Australia", "Canberra"), ("Canada", "Ottawa"),
    ("South Korea", "Seoul"), ("Mexico", "Mexico City"), ("Egypt", "Cairo"),
    ("Turkey", "Ankara"), ("Argentina", "Buenos Aires"), ("South Africa", "Pretoria"),
    ("Thailand", "Bangkok"), ("Indonesia", "Jakarta"), ("Nigeria", "Abuja"),
    ("Poland", "Warsaw"), ("Netherlands", "Amsterdam"), ("Sweden", "Stockholm"),
    ("Switzerland", "Bern"), ("Norway", "Oslo"), ("Denmark", "Copenhagen"),
    ("Finland", "Helsinki"), ("Portugal", "Lisbon"), ("Greece", "Athens"),
    ("Israel", "Jerusalem"), ("Saudi Arabia", "Riyadh"), ("Iran", "Tehran"),
    ("Pakistan", "Islamabad"), ("Vietnam", "Hanoi"), ("Philippines", "Manila"),
    ("Colombia", "Bogota"), ("Chile", "Santiago"), ("Peru", "Lima"),
    ("Ukraine", "Kyiv"), ("Czech Republic", "Prague"), ("Romania", "Bucharest"),
    ("Hungary", "Budapest"), ("Ireland", "Dublin"), ("New Zealand", "Wellington"),
    ("Singapore", "Singapore"), ("Malaysia", "Kuala Lumpur"), ("Kenya", "Nairobi"),
    ("Morocco", "Rabat"), ("Belgium", "Brussels"),
]
for country, capital in capitals:
    add(f"What is the capital of {country}?",
        f"The capital of {country} is {capital}.",
        "knowledge_geography")
    add(f"Which country has {capital} as its capital?",
        f"{capital} is the capital of {country}.",
        "knowledge_geography")

# Historical events
events = [
    ("1776", "American Declaration of Independence signed, declaring independence from Britain"),
    ("1789", "French Revolution began with the storming of the Bastille"),
    ("1865", "American Civil War ended; Abraham Lincoln assassinated"),
    ("1903", "Wright brothers achieved first powered flight at Kitty Hawk"),
    ("1914", "World War I began after assassination of Archduke Franz Ferdinand"),
    ("1929", "Stock market crash led to the Great Depression"),
    ("1945", "World War II ended; United Nations founded; atomic bombs used"),
    ("1969", "Apollo 11 moon landing; first humans on the Moon"),
    ("1989", "Fall of the Berlin Wall, symbolizing end of Cold War"),
    ("1991", "Soviet Union dissolved; World Wide Web publicly launched"),
    ("2001", "September 11 attacks on the United States"),
    ("2008", "Global financial crisis triggered by subprime mortgage collapse"),
    ("2020", "COVID-19 pandemic declared; global lockdowns implemented"),
]
for year, event in events:
    add(f"What happened in {year}?",
        f"In {year}: {event}.",
        "knowledge_history")
    add(f"When did {event.split(',')[0].lower().replace('the ','')} happen?",
        f"It happened in {year}. {event}.",
        "knowledge_history")

# Definitions
definitions = {
    "algorithm": "A step-by-step procedure or set of rules for solving a problem or accomplishing a task. Algorithms have defined inputs, outputs, and must terminate in finite time.",
    "API": "Application Programming Interface - a set of rules and protocols that allows different software applications to communicate with each other. Defines methods and data formats for requesting and exchanging information.",
    "database": "An organized collection of structured data stored electronically. Types include relational (SQL), document (MongoDB), key-value (Redis), graph (Neo4j), and columnar (Cassandra).",
    "encryption": "The process of converting readable data (plaintext) into an unreadable format (ciphertext) using an algorithm and key. Only authorized parties with the correct key can decrypt it. Types: symmetric (AES) and asymmetric (RSA).",
    "recursion": "A technique where a function calls itself to solve a problem by breaking it into smaller instances of the same problem. Requires a base case to stop. Examples: factorial, Fibonacci, tree traversal.",
    "cache": "A hardware or software component that stores data to serve future requests faster. Uses temporal and spatial locality. Types: CPU cache (L1/L2/L3), browser cache, CDN cache, application cache (Redis).",
    "latency": "The time delay between a request and its response. Measured in milliseconds. Network latency depends on distance, bandwidth, and congestion. Low latency is critical for real-time applications.",
    "throughput": "The rate at which data is successfully transferred or processed over a given period. Measured in bits per second (bps) or requests per second. Different from bandwidth (maximum capacity).",
    "concurrency": "The ability to handle multiple tasks at the same time. Not necessarily parallel (can be interleaved on one CPU). Achieved through threads, processes, async/await, or event loops.",
    "parallelism": "True simultaneous execution of multiple tasks on multiple processors/cores. Different from concurrency (which can be interleaved). Types: data parallelism, task parallelism, pipeline parallelism.",
    "microservice": "An architectural style where an application is composed of small, independent services that communicate over APIs. Each service is deployable, scalable, and maintainable independently.",
    "container": "A lightweight, standalone executable package that includes everything needed to run software: code, runtime, libraries, settings. Docker containers are isolated but share the OS kernel.",
    "CI/CD": "Continuous Integration / Continuous Deployment. CI: automatically building and testing code when changes are committed. CD: automatically deploying tested code to production. Tools: Jenkins, GitHub Actions, GitLab CI.",
    "REST API": "Representational State Transfer - an architectural style for web APIs. Uses HTTP methods (GET, POST, PUT, DELETE), stateless communication, and resource-based URLs. Returns JSON or XML.",
    "GraphQL": "A query language for APIs that lets clients request exactly the data they need. Single endpoint, strongly typed schema. Solves over-fetching and under-fetching problems of REST.",
    "WebSocket": "A protocol providing full-duplex communication over a single TCP connection. Unlike HTTP request-response, WebSocket allows server to push data to clients. Used for chat, gaming, live data.",
    "OAuth": "An authorization framework that lets third-party applications access user resources without exposing credentials. Uses access tokens. OAuth 2.0 flows: authorization code, client credentials, implicit.",
    "JWT": "JSON Web Token - a compact, self-contained token for securely transmitting information between parties. Contains header, payload, and signature. Used for authentication and information exchange.",
    "DNS": "Domain Name System - translates human-readable domain names (google.com) to IP addresses (142.250.x.x). Distributed hierarchical database. Resolution: recursive resolver -> root -> TLD -> authoritative.",
    "TCP": "Transmission Control Protocol - reliable, ordered, connection-oriented protocol. Uses three-way handshake. Guarantees delivery through acknowledgments and retransmission. Used for web, email, file transfer.",
    "UDP": "User Datagram Protocol - connectionless, unreliable protocol. No handshake, no delivery guarantee, no ordering. Faster than TCP. Used for streaming, gaming, DNS queries, VoIP.",
    "HTTP": "HyperText Transfer Protocol - the foundation of web communication. Request-response protocol. Methods: GET (retrieve), POST (create), PUT (update), DELETE (remove). HTTP/2 adds multiplexing, HTTP/3 uses QUIC.",
    "TLS": "Transport Layer Security - cryptographic protocol providing privacy and data integrity between applications. Successor to SSL. Uses certificates, public-key encryption for key exchange, symmetric encryption for data.",
    "load balancer": "Distributes incoming network traffic across multiple servers. Algorithms: round-robin, least connections, IP hash, weighted. Ensures high availability, reliability, and performance. L4 (TCP) and L7 (HTTP).",
}
for term, defn in definitions.items():
    add(f"What is {term}?", defn, "knowledge_tech")
    add(f"Define {term}.", f"**{term}**: {defn}", "knowledge_tech")

gk_count = len(pairs) - math_count - prog_count - science_count - ai_count
print(f"  General knowledge pairs: {gk_count}")

# ============================================================
# 6. TERNARY/NOVALANG PAIRS (1000+)
# ============================================================
print("[6/8] Generating ternary/NovaLang pairs...")

# Ternary arithmetic
for a in range(-40, 41):
    for b in range(-10, 11):
        if b == 0:
            continue
        # Ternary representation
        def to_ternary(n):
            if n == 0: return "0"
            sign = "-" if n < 0 else ""
            n = abs(n)
            digits = []
            while n:
                digits.append(str(n % 3))
                n //= 3
            return sign + ''.join(reversed(digits))

        ta = to_ternary(a)
        tb = to_ternary(b)
        result = a + b
        tr = to_ternary(result)
        add(f"What is {ta} + {tb} in ternary (base-3)?",
            f"In ternary: {ta} + {tb} = {tr} (decimal: {a} + {b} = {result}).",
            "ternary_arithmetic")

# Ternary concepts
ternary_concepts = {
    "balanced ternary": "A numeral system using digits {-1, 0, +1} (often written as {T, 0, 1}). Unlike standard ternary (0,1,2), balanced ternary can represent negative numbers without a separate sign. Used in some early Soviet computers (Setun).",
    "trit": "A ternary digit - the fundamental unit of information in ternary computing. Can hold one of three states: 0, 1, or 2 (or -1, 0, +1 in balanced ternary). Analogous to a bit in binary.",
    "tryte": "A group of ternary digits, analogous to a byte. In NovaX, a tryte is typically 5 trits, giving 3^5 = 243 possible values. Used as the basic addressable unit in ternary systems.",
    "ternary logic": "Logic system with three truth values: True (+1), Unknown (0), False (-1). Operations: AND = min(a,b), OR = max(a,b), NOT = -a. More expressive than binary logic for handling uncertainty.",
    "ternary advantage": "Ternary is more efficient than binary by radix economy (3 is closest integer to e=2.718). A ternary system can represent the same range of values with fewer digits. 3^n grows faster per digit than 2^n.",
}
for concept, desc in ternary_concepts.items():
    add(f"What is {concept}?", desc, "ternary_concepts")
    add(f"Explain {concept} in computing.", f"**{concept.title()}**: {desc}", "ternary_concepts")

# NovaLang syntax examples
novalang_examples = [
    ("How do you declare a variable in NovaLang?", "In NovaLang, use `let`:\n```novalang\nlet x = 42\nlet name = \"NovaX\"\nlet items = [1, 2, 3]\nlet config = {\"key\": \"value\"}\n```\nVariables are dynamically typed.", "novalang_syntax"),
    ("How do you define a function in NovaLang?", "Functions use `fn` keyword:\n```novalang\nfn add(a, b) {\n    return a + b\n}\n\nfn greet(name) {\n    print(\"Hello, \" + name)\n}\n```", "novalang_syntax"),
    ("What is if3 in NovaLang?", "if3 is NovaLang's ternary conditional with three branches for positive/zero/negative:\n```novalang\nif3(value) {\n    positive: { print(\"positive\") }\n    zero: { print(\"zero\") }\n    negative: { print(\"negative\") }\n}\n```\nThis is a core ternary construct unique to NovaLang.", "novalang_syntax"),
    ("What is match3 in NovaLang?", "match3 is ternary pattern matching:\n```novalang\nmatch3(signal) {\n    +1: { print(\"high\") }\n    0: { print(\"neutral\") }\n    -1: { print(\"low\") }\n}\n```\nMatches values against ternary states.", "novalang_syntax"),
    ("What is try3 in NovaLang?", "try3 is ternary error handling with three outcomes:\n```novalang\ntry3 {\n    result = risky_operation()\n} success {\n    print(\"OK: \" + str(result))\n} partial {\n    print(\"Warning: partial result\")\n} failure {\n    print(\"Error occurred\")\n}\n```", "novalang_syntax"),
    ("How do loops work in NovaLang?", "NovaLang has while3 and for3:\n```novalang\nwhile3(condition) {\n    continue: { do_work() }\n    pause: { wait() }\n    stop: { break }\n}\n\nfor3(item in collection) {\n    process(item)\n}\n```\nwhile3 evaluates condition as +1/0/-1.", "novalang_syntax"),
    ("What are NovaLang built-in functions?", "NovaLang has 58+ built-ins including:\n- I/O: print, input, read_file, write_file\n- Math: abs, round, floor, ceil, sqrt, pow\n- String: split, join, replace, upper, lower, trim\n- List: push, pop, len, sort, reverse, map, filter\n- Dict: keys, values, has_key, dict_set, dict_get\n- System: time, sleep, random, http_get, http_post\n- Ternary: to_trit, from_trit, trit_and, trit_or", "novalang_syntax"),
    ("How do you handle HTTP in NovaLang?", "NovaLang provides built-in HTTP:\n```novalang\nlet response = http_get(\"http://127.0.0.1:9999/api/health\")\nlet data = json_parse(response)\nprint(data)\n\nlet result = http_post(\"http://127.0.0.1:9999/api/data\", {\n    \"key\": \"value\"\n})\n```", "novalang_syntax"),
]
for p, r, d in novalang_examples:
    add(p, r, d)

nova_count = len(pairs) - math_count - prog_count - science_count - ai_count - gk_count
print(f"  Ternary/NovaLang pairs: {nova_count}")

# ============================================================
# 7. LOGIC/REASONING PAIRS (500+)
# ============================================================
print("[7/8] Generating logic/reasoning pairs...")

# Logical operations truth tables
for a_val in [True, False]:
    for b_val in [True, False]:
        a_str = str(a_val)
        b_str = str(b_val)
        add(f"What is {a_str} AND {b_str}?",
            f"{a_str} AND {b_str} = {a_val and b_val}. Logical AND returns True only when both operands are True.",
            "logic")
        add(f"What is {a_str} OR {b_str}?",
            f"{a_str} OR {b_str} = {a_val or b_val}. Logical OR returns True when at least one operand is True.",
            "logic")
        add(f"What is {a_str} XOR {b_str}?",
            f"{a_str} XOR {b_str} = {a_val ^ b_val}. Logical XOR returns True when operands differ.",
            "logic")

# Bit manipulation
for n in range(0, 256):
    binary = bin(n)
    hex_val = hex(n)
    add(f"Convert {n} to binary.",
        f"The binary representation of {n} is {binary} ({n:08b} with leading zeros).",
        "logic_binary")
    add(f"Convert {n} to hexadecimal.",
        f"The hexadecimal representation of {n} is {hex_val}.",
        "logic_hex")

# Syllogisms and reasoning
syllogisms = [
    ("All mammals are warm-blooded. Dogs are mammals.", "Therefore, dogs are warm-blooded. This is a valid deductive syllogism (Barbara form)."),
    ("All birds can fly. Penguins are birds.", "The conclusion 'penguins can fly' follows from the premises, but the major premise is false - not all birds can fly. This demonstrates that valid logic can lead to false conclusions from false premises."),
    ("Some fruits are red. Apples are fruits.", "We cannot conclude that apples are red. 'Some' does not mean 'all'. Some apples are red, but this doesn't follow from these premises alone."),
    ("If it rains, the ground is wet. The ground is wet.", "We cannot conclude it rained. This is the fallacy of affirming the consequent. The ground could be wet from other causes."),
    ("If it rains, the ground is wet. It is not raining.", "We cannot conclude the ground is dry. This is the fallacy of denying the antecedent. Other things could make the ground wet."),
    ("If it rains, the ground is wet. The ground is not wet.", "Therefore, it is not raining. This is valid modus tollens (denying the consequent)."),
    ("No reptiles are mammals. All snakes are reptiles.", "Therefore, no snakes are mammals. Valid syllogism (Celarent form)."),
]
for premise, conclusion in syllogisms:
    add(f"Given: {premise} What can we conclude?",
        conclusion,
        "logic_reasoning")

logic_count = len(pairs) - math_count - prog_count - science_count - ai_count - gk_count - nova_count
print(f"  Logic/reasoning pairs: {logic_count}")

# ============================================================
# 8. WORD PROBLEMS AND PRACTICAL MATH (500+)
# ============================================================
print("[8/8] Generating word problems...")

# Speed/distance/time
for speed in [30, 40, 50, 60, 70, 80, 100]:
    for time_h in [1, 2, 3, 4, 5, 0.5, 1.5, 2.5]:
        dist = speed * time_h
        time_str = f"{time_h} hour{'s' if time_h != 1 else ''}"
        if time_h == 0.5:
            time_str = "30 minutes"
        elif time_h == 1.5:
            time_str = "1.5 hours"
        elif time_h == 2.5:
            time_str = "2.5 hours"
        add(f"A car travels at {speed} mph for {time_str}. How far does it go?",
            f"Distance = Speed x Time = {speed} mph x {time_h} hours = {dist} miles.",
            "math_word_problems")

# Area calculations
for w in range(1, 21):
    for h in range(1, 21):
        if w <= h:
            add(f"What is the area of a rectangle with width {w} and height {h}?",
                f"Area = width x height = {w} x {h} = {w*h} square units.",
                "math_geometry")

# Circle calculations
import math
for r in range(1, 26):
    area = round(math.pi * r * r, 2)
    circ = round(2 * math.pi * r, 2)
    add(f"What is the area of a circle with radius {r}?",
        f"Area = pi * r^2 = pi * {r}^2 = {area} square units.",
        "math_geometry")
    add(f"What is the circumference of a circle with radius {r}?",
        f"Circumference = 2 * pi * r = 2 * pi * {r} = {circ} units.",
        "math_geometry")

# Compound interest
for principal in [100, 500, 1000, 5000, 10000]:
    for rate in [0.01, 0.02, 0.03, 0.05, 0.07, 0.10]:
        for years in [1, 2, 5, 10]:
            amount = round(principal * (1 + rate) ** years, 2)
            interest = round(amount - principal, 2)
            add(f"If you invest ${principal} at {rate*100}% annual interest for {years} years, how much will you have?",
                f"Using compound interest formula A = P(1+r)^t: A = {principal} * (1+{rate})^{years} = ${amount}. Total interest earned: ${interest}.",
                "math_finance")

word_count = len(pairs) - math_count - prog_count - science_count - ai_count - gk_count - nova_count - logic_count
print(f"  Word problems/practical: {word_count}")

# ============================================================
# SAVE
# ============================================================
print(f"\n=== TOTAL SYNTHETIC PAIRS: {len(pairs)} ===")

# Dedup by prompt
seen = set()
deduped = []
for p in pairs:
    key = p["prompt"].strip().lower()
    if key not in seen:
        seen.add(key)
        deduped.append(p)

print(f"After dedup: {len(deduped)}")

with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(deduped, f, ensure_ascii=False, indent=1)

print(f"Saved to {OUTPUT}")
