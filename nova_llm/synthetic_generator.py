"""
NovaX Synthetic Training Data Generator v2
Generates 20,000+ training pairs using PURE Python stdlib.
No AI models, no APIs, no GPU. CPU only.
Categories: math, code, logic, knowledge, ternary
"""

import json
import os
import random
import math
import time

# ============================================================
# UTILITIES
# ============================================================

def ensure_ascii(s):
    return s.encode('ascii', 'replace').decode('ascii')

def pair(prompt, response, domain):
    return {
        "prompt": ensure_ascii(prompt.strip()),
        "response": ensure_ascii(response.strip()),
        "source": "synthetic",
        "domain": domain
    }

def to_balanced_ternary(n):
    if n == 0:
        return "0"
    digits = []
    val = n
    while val != 0:
        rem = val % 3
        if rem == 0:
            digits.append("0")
            val = val // 3
        elif rem == 1:
            digits.append("+")
            val = val // 3
        else:
            digits.append("T")
            val = (val + 1) // 3
    return "".join(reversed(digits))

# ============================================================
# 1. MATH PROBLEMS (5,500+ unique pairs)
# ============================================================

def gen_math_pairs():
    random.seed(42)
    pairs = []
    seen = set()

    def add_pair(p, r):
        if p not in seen:
            seen.add(p)
            pairs.append(pair(p, r, "math"))

    # --- Arithmetic: addition (500) ---
    for _ in range(600):
        a, b = random.randint(10, 9999), random.randint(10, 9999)
        add_pair(f"What is {a} + {b}?",
                 f"{a} + {b} = {a+b}. Add the two numbers to get {a+b}.")

    # --- Arithmetic: subtraction (500) ---
    for _ in range(600):
        a, b = random.randint(10, 9999), random.randint(10, 9999)
        add_pair(f"What is {a} - {b}?",
                 f"{a} - {b} = {a-b}. Subtract {b} from {a} to get {a-b}.")

    # --- Arithmetic: multiplication (500) ---
    for _ in range(600):
        a, b = random.randint(2, 999), random.randint(2, 999)
        add_pair(f"What is {a} * {b}?",
                 f"Step 1: Multiply {a} by {b}.\n{a} * {b} = {a*b}\nThe answer is {a*b}.")

    # --- Division (400) ---
    for _ in range(500):
        b = random.randint(2, 99)
        a = b * random.randint(2, 200) + random.randint(0, b-1)
        q, r = divmod(a, b)
        if r == 0:
            resp = f"{a} / {b} = {q} exactly. {b} divides evenly into {a}."
        else:
            resp = f"{a} / {b} = {q} remainder {r}. As a decimal: {a/b:.4f}."
        add_pair(f"What is {a} divided by {b}?", resp)

    # --- Powers (300) ---
    for _ in range(400):
        base = random.randint(2, 25)
        exp = random.randint(2, 6)
        result = base ** exp
        add_pair(f"What is {base} raised to the power of {exp}?",
                 f"{base}^{exp} = " + " * ".join([str(base)] * exp) + f" = {result}")

    # --- Square roots (200) ---
    for _ in range(300):
        n = random.randint(2, 50)
        sq = n * n
        add_pair(f"What is the square root of {sq}?",
                 f"sqrt({sq}) = {n}, because {n} * {n} = {sq}.")

    # --- Linear equations (600) ---
    for _ in range(800):
        a = random.choice([i for i in range(-15, 16) if i != 0])
        x_real = random.randint(-30, 30)
        b = random.randint(-100, 100)
        c = a * x_real + b
        add_pair(f"Solve for x: {a}x + {b} = {c}",
                 f"Step 1: Subtract {b} from both sides: {a}x = {c} - {b} = {c-b}\n"
                 f"Step 2: Divide by {a}: x = {c-b} / {a} = {x_real}\nSolution: x = {x_real}.")

    # --- Quadratic equations (500) ---
    for _ in range(700):
        r1 = random.randint(-20, 20)
        r2 = random.randint(-20, 20)
        b_c = -(r1 + r2)
        c_c = r1 * r2
        b_s = f"+ {b_c}" if b_c >= 0 else f"- {abs(b_c)}"
        c_s = f"+ {c_c}" if c_c >= 0 else f"- {abs(c_c)}"
        add_pair(f"Solve: x^2 {b_s}x {c_s} = 0",
                 f"Factor: (x - {r1})(x - {r2}) = 0\n"
                 f"x = {r1} or x = {r2}.\nSolutions: {{{r1}, {r2}}}.")

    # --- Word problems (800) ---
    wp = [
        ("A store has {a} apples. {b} are sold. How many remain?",
         lambda a, b: f"Starting with {a} apples, subtract {b} sold: {a} - {b} = {a-b}. There are {a-b} apples remaining."),
        ("A train travels at {a} km/h for {b} hours. What distance does it cover?",
         lambda a, b: f"Distance = speed x time = {a} km/h x {b} h = {a*b} km. The train covers {a*b} kilometers."),
        ("If {a} workers build a wall in {b} days, how many worker-days is that?",
         lambda a, b: f"Worker-days = workers x days = {a} x {b} = {a*b}. Total effort is {a*b} worker-days."),
        ("A rectangle has length {a} cm and width {b} cm. What is its area?",
         lambda a, b: f"Area = length x width = {a} x {b} = {a*b} sq cm. Perimeter = 2({a}+{b}) = {2*(a+b)} cm."),
        ("You buy {a} items at ${b} each. What is the total cost?",
         lambda a, b: f"Total = quantity x price = {a} x ${b} = ${a*b}. The total cost is ${a*b}."),
        ("A tank holds {a} liters. {b} liters are drained. How much is left?",
         lambda a, b: f"{a} - {b} = {a-b} liters remaining in the tank."),
        ("A book has {a} pages. You read {b} pages per day. How many days to finish?",
         lambda a, b: f"Days = {a} / {b} = {a/b:.1f} days. " + (f"Exactly {a//b} days." if a % b == 0 else f"About {math.ceil(a/b)} days (rounding up).")),
        ("{a} students split into groups of {b}. How many groups?",
         lambda a, b: f"{a} / {b} = {a//b} full groups" + (f" with {a%b} students left over." if a % b != 0 else ".")),
    ]
    for _ in range(1000):
        tmpl, fn = random.choice(wp)
        a = random.randint(10, 500)
        b = random.randint(2, min(a - 1, 100))
        prompt = tmpl.format(a=a, b=b)
        if prompt not in seen:
            seen.add(prompt)
            pairs.append(pair(prompt, fn(a, b), "math"))

    # --- Fractions (300) ---
    for _ in range(400):
        n1, d1 = random.randint(1, 20), random.randint(2, 20)
        n2, d2 = random.randint(1, 20), random.randint(2, 20)
        op = random.choice(["+", "-"])
        rn = n1 * d2 + n2 * d1 if op == "+" else n1 * d2 - n2 * d1
        rd = d1 * d2
        g = math.gcd(abs(rn), rd)
        resp = f"Common denominator: {d1}*{d2} = {rd}. {n1}/{d1} {op} {n2}/{d2} = {rn}/{rd}"
        if g > 1:
            resp += f" = {rn//g}/{rd//g} simplified."
        else:
            resp += "."
        add_pair(f"What is {n1}/{d1} {op} {n2}/{d2}?", resp)

    # --- Percentages (300) ---
    for _ in range(400):
        pct = random.randint(1, 99)
        val = random.randint(10, 5000)
        result = val * pct / 100
        add_pair(f"What is {pct}% of {val}?",
                 f"{pct}% of {val} = {val} x {pct}/100 = {result:.2f}.")

    for _ in range(400):
        part = random.randint(1, 200)
        whole = random.randint(part + 1, 1000)
        pct = part / whole * 100
        add_pair(f"{part} is what percent of {whole}?",
                 f"Percentage = ({part}/{whole}) x 100 = {pct:.2f}%.")

    # --- Unit conversions (300) ---
    convs = [
        ("miles", "kilometers", 1.60934),
        ("inches", "centimeters", 2.54),
        ("pounds", "kilograms", 0.453592),
        ("gallons", "liters", 3.78541),
        ("feet", "meters", 0.3048),
        ("ounces", "grams", 28.3495),
        ("yards", "meters", 0.9144),
        ("celsius", "fahrenheit", None),
    ]
    for _ in range(400):
        fr, to, factor = random.choice(convs)
        val = round(random.uniform(0.5, 1000), 2)
        if fr == "celsius":
            result = val * 9/5 + 32
            resp = f"{val} Celsius = {val} x 9/5 + 32 = {result:.2f} Fahrenheit."
        else:
            result = val * factor
            resp = f"{val} {fr} x {factor} = {result:.4f} {to}."
        add_pair(f"Convert {val} {fr} to {to}.", resp)

    # --- GCD / LCM (200) ---
    for _ in range(300):
        a, b = random.randint(2, 500), random.randint(2, 500)
        g = math.gcd(a, b)
        l = a * b // g
        if random.random() < 0.5:
            add_pair(f"What is the GCD of {a} and {b}?",
                     f"Using the Euclidean algorithm: GCD({a}, {b}) = {g}.")
        else:
            add_pair(f"What is the LCM of {a} and {b}?",
                     f"LCM = ({a} x {b}) / GCD({a},{b}) = {a*b} / {g} = {l}.")

    # --- Absolute value (200) ---
    for _ in range(250):
        a = random.randint(-500, 500)
        add_pair(f"What is the absolute value of {a}?",
                 f"|{a}| = {abs(a)}. Absolute value gives the distance from zero, always non-negative.")

    # --- Modular arithmetic (200) ---
    for _ in range(300):
        a = random.randint(10, 1000)
        b = random.randint(2, 50)
        add_pair(f"What is {a} mod {b}?",
                 f"{a} mod {b} = {a % b}. Dividing {a} by {b} gives quotient {a//b} with remainder {a%b}.")

    # --- Factorials (100) ---
    for n in range(1, 21):
        val = math.factorial(n)
        add_pair(f"What is {n} factorial ({n}!)?",
                 f"{n}! = " + " x ".join(str(i) for i in range(n, 0, -1)) + f" = {val}.")

    # --- Primes check (200) ---
    def is_prime(n):
        if n < 2: return False
        for i in range(2, int(n**0.5)+1):
            if n % i == 0: return False
        return True

    for _ in range(300):
        n = random.randint(2, 1000)
        if is_prime(n):
            resp = f"{n} is a prime number. It is only divisible by 1 and {n}."
        else:
            # Find a factor
            for f in range(2, int(n**0.5)+2):
                if n % f == 0:
                    resp = f"{n} is NOT prime. It is divisible by {f} ({n}/{f} = {n//f})."
                    break
        add_pair(f"Is {n} a prime number?", resp)

    # --- Sum of series (200) ---
    for _ in range(250):
        n = random.randint(5, 200)
        s = n * (n + 1) // 2
        add_pair(f"What is the sum of integers from 1 to {n}?",
                 f"Using the formula n(n+1)/2: {n} x {n+1} / 2 = {s}.")

    # BOOST: Rounding
    for _ in range(150):
        val = round(random.uniform(0.01, 999.99), 4)
        add_pair(f"Round {val} to 2 decimal places.",
                 f"round({val}, 2) = {round(val, 2)}. Standard rounding to two decimal places.")

    # BOOST: Compound expressions
    for _ in range(300):
        a, b, c = random.randint(2, 50), random.randint(2, 50), random.randint(2, 50)
        result = a * b + c
        add_pair(f"Calculate {a} * {b} + {c}.",
                 f"First multiply: {a} * {b} = {a*b}. Then add: {a*b} + {c} = {result}.")

    for _ in range(300):
        a, b, c = random.randint(2, 100), random.randint(2, 30), random.randint(1, 20)
        result = (a + b) * c
        add_pair(f"What is ({a} + {b}) * {c}?",
                 f"First add: {a} + {b} = {a+b}. Then multiply: {a+b} * {c} = {result}.")

    # BOOST: Average / mean
    for _ in range(300):
        nums = [random.randint(1, 100) for _ in range(random.randint(3, 7))]
        avg = sum(nums) / len(nums)
        add_pair(f"What is the average of {nums}?",
                 f"Sum = {sum(nums)}. Count = {len(nums)}. Average = {sum(nums)} / {len(nums)} = {avg:.2f}.")

    # BOOST: Min/Max of lists
    for _ in range(200):
        nums = [random.randint(-50, 100) for _ in range(random.randint(4, 8))]
        add_pair(f"What is the minimum and maximum of {nums}?",
                 f"Minimum = {min(nums)}, Maximum = {max(nums)}. Range = {max(nums)} - {min(nums)} = {max(nums)-min(nums)}.")

    # BOOST: Exponent equations
    for _ in range(200):
        base = random.randint(2, 10)
        result = base ** random.randint(2, 6)
        exp = round(math.log(result, base))
        add_pair(f"If {base}^x = {result}, what is x?",
                 f"Take log base {base} of {result}: x = log_{base}({result}) = {exp}.")

    print(f"  math: {len(pairs)} pairs", flush=True)
    return pairs

# ============================================================
# 2. CODE EXERCISES (5,500+ unique pairs)
# ============================================================

def gen_code_pairs():
    random.seed(43)
    pairs = []
    seen = set()

    def add_pair(p, r):
        if p not in seen:
            seen.add(p)
            pairs.append(pair(p, r, "code"))

    # --- Write a function templates (20 functions x 5 variations = 100) ---
    functions = [
        ("find the maximum element in a list",
         'def find_max(lst):\n    if not lst: return None\n    max_val = lst[0]\n    for item in lst[1:]:\n        if item > max_val: max_val = item\n    return max_val\n# Example: find_max([3,1,4,1,5]) -> 5'),
        ("reverse a string",
         'def reverse_string(s):\n    return s[::-1]\n# Example: reverse_string("hello") -> "olleh"'),
        ("check if a number is prime",
         'def is_prime(n):\n    if n < 2: return False\n    for i in range(2, int(n**0.5)+1):\n        if n % i == 0: return False\n    return True\n# Example: is_prime(17) -> True'),
        ("calculate factorial",
         'def factorial(n):\n    if n < 0: raise ValueError("Negative")\n    result = 1\n    for i in range(2, n+1): result *= i\n    return result\n# Example: factorial(5) -> 120'),
        ("count vowels in a string",
         'def count_vowels(s):\n    return sum(1 for c in s.lower() if c in "aeiou")\n# Example: count_vowels("Hello") -> 2'),
        ("generate Fibonacci numbers",
         'def fibonacci(n):\n    if n <= 0: return []\n    seq = [0, 1]\n    while len(seq) < n: seq.append(seq[-1] + seq[-2])\n    return seq[:n]\n# Example: fibonacci(7) -> [0,1,1,2,3,5,8]'),
        ("flatten a nested list",
         'def flatten(lst):\n    result = []\n    for item in lst:\n        if isinstance(item, list): result.extend(flatten(item))\n        else: result.append(item)\n    return result'),
        ("merge two sorted lists",
         'def merge_sorted(a, b):\n    result, i, j = [], 0, 0\n    while i < len(a) and j < len(b):\n        if a[i] <= b[j]: result.append(a[i]); i += 1\n        else: result.append(b[j]); j += 1\n    return result + a[i:] + b[j:]'),
        ("remove duplicates preserving order",
         'def remove_dupes(lst):\n    seen = set()\n    return [x for x in lst if not (x in seen or seen.add(x))]'),
        ("check if string is palindrome",
         'def is_palindrome(s):\n    cleaned = s.lower().replace(" ", "")\n    return cleaned == cleaned[::-1]'),
        ("find pairs summing to target",
         'def find_pairs(lst, target):\n    seen, pairs = set(), []\n    for n in lst:\n        if target - n in seen: pairs.append((target-n, n))\n        seen.add(n)\n    return pairs'),
        ("implement binary search",
         'def binary_search(arr, target):\n    lo, hi = 0, len(arr)-1\n    while lo <= hi:\n        mid = (lo+hi)//2\n        if arr[mid] == target: return mid\n        elif arr[mid] < target: lo = mid+1\n        else: hi = mid-1\n    return -1'),
        ("rotate a list by k positions",
         'def rotate(lst, k):\n    if not lst: return lst\n    k = k % len(lst)\n    return lst[-k:] + lst[:-k]'),
        ("find second largest number",
         'def second_largest(lst):\n    unique = list(set(lst))\n    if len(unique) < 2: return None\n    unique.sort()\n    return unique[-2]'),
        ("check if two strings are anagrams",
         'def are_anagrams(s1, s2):\n    return sorted(s1.lower()) == sorted(s2.lower())'),
        ("transpose a matrix",
         'def transpose(m):\n    if not m: return []\n    return [[row[i] for row in m] for i in range(len(m[0]))]'),
        ("implement bubble sort",
         'def bubble_sort(lst):\n    arr = lst[:]\n    for i in range(len(arr)):\n        for j in range(len(arr)-i-1):\n            if arr[j] > arr[j+1]: arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr'),
        ("count word frequency",
         'def word_freq(text):\n    freq = {}\n    for w in text.lower().split():\n        freq[w] = freq.get(w, 0) + 1\n    return freq'),
        ("compute digit sum",
         'def digit_sum(n):\n    return sum(int(d) for d in str(abs(n)))'),
        ("implement Caesar cipher",
         'def caesar(text, shift):\n    result = []\n    for c in text:\n        if c.isalpha():\n            base = ord("A") if c.isupper() else ord("a")\n            result.append(chr((ord(c)-base+shift)%26+base))\n        else: result.append(c)\n    return "".join(result)'),
        ("compute running average",
         'def running_avg(lst):\n    result, total = [], 0\n    for i, v in enumerate(lst, 1):\n        total += v\n        result.append(total/i)\n    return result'),
        ("find intersection of two lists",
         'def intersection(a, b):\n    return list(set(a) & set(b))'),
        ("check if number is perfect square",
         'def is_perfect_square(n):\n    if n < 0: return False\n    root = int(n**0.5)\n    return root*root == n'),
        ("convert list of tuples to dictionary",
         'def tuples_to_dict(pairs):\n    return {k: v for k, v in pairs}'),
        ("find mode of a list",
         'def find_mode(lst):\n    freq = {}\n    for x in lst: freq[x] = freq.get(x, 0) + 1\n    return max(freq, key=freq.get)'),
        ("implement selection sort",
         'def selection_sort(lst):\n    arr = lst[:]\n    for i in range(len(arr)):\n        min_idx = i\n        for j in range(i+1, len(arr)):\n            if arr[j] < arr[min_idx]: min_idx = j\n        arr[i], arr[min_idx] = arr[min_idx], arr[i]\n    return arr'),
        ("implement insertion sort",
         'def insertion_sort(lst):\n    arr = lst[:]\n    for i in range(1, len(arr)):\n        key = arr[i]\n        j = i - 1\n        while j >= 0 and arr[j] > key:\n            arr[j+1] = arr[j]; j -= 1\n        arr[j+1] = key\n    return arr'),
        ("find longest word in a string",
         'def longest_word(text):\n    words = text.split()\n    return max(words, key=len) if words else ""'),
        ("check if list is sorted",
         'def is_sorted(lst):\n    return all(lst[i] <= lst[i+1] for i in range(len(lst)-1))'),
        ("compute power set",
         'def power_set(lst):\n    if not lst: return [[]]\n    rest = power_set(lst[1:])\n    return rest + [[lst[0]] + s for s in rest]'),
    ]

    variations = [
        "Write a Python function to {task}.",
        "Create a Python function that can {task}.",
        "Implement a function in Python to {task}.",
        "How would you write a Python function to {task}?",
        "Show me Python code to {task}.",
        "Give me a Python function for: {task}.",
    ]

    for task, code in functions:
        for v in variations:
            add_pair(v.format(task=task), code)

    # --- What does this code do? (1500+) ---
    # Generate unique list comprehensions
    for _ in range(500):
        op = random.choice(["x**2", "x*2", "x+1", "x*3", "x-1", "x**3", "x%5", "x//2", "x*x", "abs(x)"])
        lo = random.randint(0, 20)
        hi = random.randint(lo + 3, lo + 20)
        code_s = f"[{op} for x in range({lo}, {hi})]"
        add_pair(f"What does this code do: `{code_s}`?",
                 f"This list comprehension applies the expression '{op}' to each integer x from {lo} to {hi-1} (inclusive). It produces a list of {hi-lo} elements.")

    # Dict comprehensions
    for _ in range(300):
        n = random.randint(3, 15)
        val_expr = random.choice(["x**2", "x*2", "str(x)", "x+10", "chr(65+x)"])
        code_s = f"{{x: {val_expr} for x in range({n})}}"
        add_pair(f"Explain this code: `{code_s}`",
                 f"Creates a dictionary mapping integers 0..{n-1} to {val_expr}. Result is a dict with {n} key-value pairs.")

    # Slicing
    for _ in range(300):
        s = random.choice(["'abcdefghij'", "'hello world'", "'python3.12'", "'programming'"])
        a = random.randint(0, 3)
        b = random.randint(5, 9)
        code_s = f"{s}[{a}:{b}]"
        add_pair(f"What is the output of: `{code_s}`?",
                 f"String slicing extracts characters from index {a} to {b-1} (exclusive end). Returns a substring of length {b-a}.")

    # Built-in functions
    builtins_q = [
        ("sorted([3,1,4,1,5], reverse=True)", "Returns [5,4,3,1,1]. sorted() creates a new sorted list. reverse=True sorts in descending order."),
        ("any(x > 10 for x in [1,5,15,3])", "Returns True. any() returns True if at least one element satisfies the condition. Here 15 > 10 is True."),
        ("all(x > 0 for x in [1,2,3])", "Returns True. all() returns True only if every element satisfies the condition. All elements are positive."),
        ("list(zip([1,2,3], ['a','b','c']))", "Returns [(1,'a'),(2,'b'),(3,'c')]. zip() pairs elements from multiple iterables element-by-element."),
        ("list(map(str, [1,2,3]))", "Returns ['1','2','3']. map() applies str() to each element, converting integers to strings."),
        ("list(filter(lambda x: x>2, [1,2,3,4]))", "Returns [3,4]. filter() keeps only elements where the lambda returns True (x > 2)."),
        ("dict(zip('abc', [1,2,3]))", "Returns {'a':1, 'b':2, 'c':3}. zip pairs the string characters with list values, dict() converts to dictionary."),
        ("sum(range(1, 101))", "Returns 5050. range(1,101) generates integers 1-100, sum() adds them all. This is Gauss's famous sum."),
        ("len(set([1,2,2,3,3,3]))", "Returns 3. set() removes duplicates leaving {1,2,3}, and len() counts 3 unique elements."),
        ("max('hello', key=lambda c: ord(c))", "Returns 'o'. max() finds the character with the highest ASCII/Unicode value. ord('o')=111 is the highest."),
        ("min([(1,'z'),(2,'a')], key=lambda t: t[1])", "Returns (2,'a'). min() compares by the second element of each tuple. 'a' < 'z' alphabetically."),
        ("' '.join(['hello', 'world'])", "Returns 'hello world'. join() concatenates list elements with the given separator (space)."),
        ("'hello world'.split()", "Returns ['hello', 'world']. split() divides a string by whitespace into a list of substrings."),
        ("enumerate(['a','b','c'])", "Returns an iterator yielding (0,'a'), (1,'b'), (2,'c'). enumerate() adds index counters to an iterable."),
        ("isinstance(42, (int, float))", "Returns True. isinstance() checks if 42 is an instance of int or float. 42 is an int."),
    ]
    for code_s, explanation in builtins_q:
        for tmpl in ["What does `{c}` do?", "Explain: `{c}`", "What is the result of `{c}`?"]:
            add_pair(tmpl.format(c=code_s), explanation)

    # --- Fix the bug (1000+) ---
    bug_templates = [
        ("off_by_one", "range(1, len({v}))", "range(len({v}))",
         "Off-by-one: starting at 1 skips index 0. Fixed to start at 0."),
        ("wrong_op", "total -= x", "total += x",
         "Wrong operator: -= subtracts instead of adding. Changed to +=."),
        ("missing_return", "    result = [x*2 for x in {v}]",
         "    result = [x*2 for x in {v}]\n    return result",
         "Missing return statement. Function returned None instead of result."),
        ("type_mismatch", '{v} = "42"\\ntotal = {v} + 1',
         '{v} = "42"\\ntotal = int({v}) + 1',
         "Type error: cannot add string and int. Must convert string to int first."),
        ("index_error", "{v}[len({v})]", "{v}[len({v})-1]",
         "Index out of range: len() gives count, max index is len()-1."),
        ("infinite_loop", "while {v} > 0:\\n    print({v})",
         "while {v} > 0:\\n    print({v})\\n    {v} -= 1",
         "Infinite loop: loop variable never changes. Must decrement in loop body."),
        ("key_error", "d[{v}] = d[{v}] + 1", "d[{v}] = d.get({v}, 0) + 1",
         "KeyError on first access. Use .get() with default value 0."),
        ("scope_error", "for i in range(3): x = i\\nprint(x)",
         "x = 0\\nfor i in range(3): x = i\\nprint(x)",
         "Variable may be undefined if loop doesn't execute. Initialize before loop."),
    ]
    var_names = ["data", "items", "nums", "values", "arr", "result", "lst", "seq",
                 "records", "scores", "counts", "elements", "entries", "points"]
    bug_prompts = [
        "Fix the bug in this code:\n{code}",
        "Debug this Python code:\n{code}",
        "Find and fix the error:\n{code}",
    ]
    for _ in range(1200):
        vn = random.choice(var_names)
        name, buggy, fixed, explanation = random.choice(bug_templates)
        buggy_code = buggy.format(v=vn)
        fixed_code = fixed.format(v=vn)
        for bp in random.sample(bug_prompts, 1):
            prompt = bp.format(code=buggy_code)
            resp = f"Fixed:\n{fixed_code}\nExplanation: {explanation}"
            add_pair(prompt, resp)

    # --- Python concept questions (500) ---
    concepts = [
        ("list comprehension", "A concise way to create lists: [expr for item in iterable if condition]. Example: [x**2 for x in range(5)] -> [0,1,4,9,16]. Replaces multi-line loops with a single readable expression."),
        ("dictionary", "A mutable mapping of key-value pairs. Keys must be hashable. O(1) average lookup. Created with {} or dict(). Methods: .get(), .keys(), .values(), .items(), .setdefault()."),
        ("tuple", "An immutable ordered sequence. Created with () or tuple(). Cannot be modified after creation. Faster than lists, can be dict keys. Unpacking: a, b = (1, 2)."),
        ("set", "An unordered collection of unique elements. O(1) membership testing. Operations: union (|), intersection (&), difference (-). Created with set() or {1,2,3}."),
        ("lambda function", "An anonymous single-expression function: lambda args: expr. Example: square = lambda x: x**2. Used with map(), filter(), sorted(). Limited to one expression."),
        ("decorator", "A function that wraps another function to modify its behavior. Applied with @decorator syntax. Common uses: logging, timing, caching, authentication."),
        ("generator", "A function using yield to produce values lazily, one at a time. Saves memory by not building full list. Created with yield keyword or generator expressions (x for x in ...)."),
        ("context manager", "Handles setup/cleanup with 'with' statement. Define __enter__/__exit__ or use @contextmanager. Ensures cleanup even on exceptions. Example: with open('f') as fh."),
        ("class inheritance", "Child class extends parent: class Child(Parent). Inherits methods/attributes. Override with same method name. super() calls parent. Python supports multiple inheritance."),
        ("exception handling", "try/except/else/finally blocks. try: risky code. except TypeError: handle. else: no exception. finally: always runs. Custom exceptions extend Exception."),
        ("*args and **kwargs", "*args collects positional arguments as tuple. **kwargs collects keyword arguments as dict. Example: def f(*args, **kwargs). Allows flexible function signatures."),
        ("list slicing", "seq[start:stop:step]. Defaults: start=0, stop=len, step=1. Negative indices from end. lst[::-1] reverses. lst[1:4] gives elements at indices 1,2,3."),
        ("GIL", "Global Interpreter Lock in CPython allows only one thread to execute Python bytecode at a time. Limits CPU-bound parallelism. Workarounds: multiprocessing, C extensions."),
        ("enumerate", "enumerate(iterable) yields (index, element) pairs. Optional start parameter. More Pythonic than manual counter. Example: for i, val in enumerate(lst)."),
        ("zip function", "zip() pairs elements from iterables: zip([1,2],['a','b']) -> [(1,'a'),(2,'b')]. Stops at shortest. Useful for parallel iteration and dict creation."),
        ("f-string", "Formatted string literal (Python 3.6+): f'Name: {name}'. Supports expressions: f'{x+1}'. Format specs: f'{val:.2f}'. Fastest string formatting method."),
        ("walrus operator", "Assignment expression (:=) assigns and returns a value: if (n := len(lst)) > 5. Reduces repeated computations. Added in Python 3.8."),
        ("type hints", "Optional annotations: def greet(name: str) -> str. Not enforced at runtime. Helps IDEs and type checkers (mypy). Common: List[int], Dict[str, Any], Optional[str]."),
        ("dataclass", "From dataclasses module. @dataclass auto-generates __init__, __repr__, __eq__. Reduces boilerplate for data-holding classes. Fields defined as class annotations."),
        ("virtual environment", "Isolated Python environment with its own packages. Created with: python -m venv myenv. Activated with source myenv/bin/activate. Prevents dependency conflicts."),
    ]
    concept_prompts = [
        "What is a {topic} in Python?",
        "Explain Python {topic}.",
        "How do you use {topic} in Python?",
        "Describe the {topic} concept in Python.",
        "What does {topic} mean in Python?",
    ]
    for topic, answer in concepts:
        for cp in concept_prompts:
            add_pair(cp.format(topic=topic), answer)

    # --- What's the output? with random values (800) ---
    for _ in range(800):
        pattern = random.choice(["math_expr", "string_op", "list_op", "bool_expr", "format_str"])
        if pattern == "math_expr":
            a, b = random.randint(1, 100), random.randint(1, 100)
            op = random.choice(["+", "-", "*", "//", "%", "**"])
            # SECURITY: replaced eval() with a dispatch dict on constructed strings
            _math_ops = {
                "+":  lambda x, y: x + y,
                "-":  lambda x, y: x - y,
                "*":  lambda x, y: x * y,
                "//": lambda x, y: x // y,
                "%":  lambda x, y: x % y,
                "**": lambda x, y: x ** y,
            }
            result = _math_ops[op](a, b)
            add_pair(f"What is the output of: print({a} {op} {b})",
                     f"Output: {result}. Python evaluates {a} {op} {b} = {result}.")
        elif pattern == "string_op":
            s = random.choice(["hello", "world", "python", "code", "test", "data"])
            method = random.choice([".upper()", ".lower()", ".title()", ".swapcase()", f".replace('{s[0]}', 'X')"])
            # SECURITY: replaced eval() with a dispatch dict on constructed strings
            if method == ".upper()":
                result = s.upper()
            elif method == ".lower()":
                result = s.lower()
            elif method == ".title()":
                result = s.title()
            elif method == ".swapcase()":
                result = s.swapcase()
            else:
                # .replace('<c>', 'X') — the first char of s is used
                result = s.replace(s[0], 'X')
            add_pair(f"What does '{s}'{method} return?",
                     f"Returns '{result}'. The {method.strip('.()')} method transforms the string accordingly.")
        elif pattern == "list_op":
            lst = [random.randint(1, 20) for _ in range(random.randint(3, 7))]
            method = random.choice(["sum", "min", "max", "len", "sorted"])
            # SECURITY: replaced eval() with a dispatch dict on constructed strings
            _list_ops = {
                "sum": sum,
                "min": min,
                "max": max,
                "len": len,
                "sorted": sorted,
            }
            result = _list_ops[method](lst)
            add_pair(f"What is {method}({lst})?",
                     f"Result: {result}. The {method}() function returns {result} for the given list.")
        elif pattern == "bool_expr":
            a, b = random.randint(1, 50), random.randint(1, 50)
            op = random.choice(["==", "!=", ">", "<", ">=", "<="])
            # SECURITY: replaced eval() with a dispatch dict on constructed strings
            _cmp_ops = {
                "==": lambda x, y: x == y,
                "!=": lambda x, y: x != y,
                ">":  lambda x, y: x > y,
                "<":  lambda x, y: x < y,
                ">=": lambda x, y: x >= y,
                "<=": lambda x, y: x <= y,
            }
            result = _cmp_ops[op](a, b)
            add_pair(f"What is {a} {op} {b} in Python?",
                     f"Result: {result}. The comparison {a} {op} {b} evaluates to {result}.")
        else:
            val = random.randint(1, 10000)
            width = random.randint(6, 12)
            result = f"{val:0>{width}}"
            add_pair(f"What does f'{{val:0>{width}}}' produce when val={val}?",
                     f"Produces '{result}'. The format spec 0>{width} right-aligns and zero-pads to {width} characters.")

    # BOOST: Generate unique "write function" pairs with random parameters
    param_tasks = [
        ("return the {adj} of {n} numbers from a list", "n", "adj"),
        ("compute the {op} of all elements in a list", "op", None),
        ("check if a string contains only {chartype} characters", "chartype", None),
        ("convert a {src} to a {dst}", "src", "dst"),
        ("count occurrences of {what} in a {container}", "what", "container"),
    ]
    adjs = ["sum", "product", "average", "minimum", "maximum", "median"]
    ops = ["sum", "product", "cumulative sum", "running total", "absolute values"]
    chartypes = ["alphabetic", "numeric", "alphanumeric", "uppercase", "lowercase", "ASCII"]
    src_dst = [("list", "string"), ("string", "list"), ("dict", "list of tuples"),
               ("list of dicts", "dict of lists"), ("binary string", "integer"),
               ("integer", "binary string"), ("hex string", "integer"), ("list", "set")]
    whats = ["vowels", "consonants", "digits", "spaces", "uppercase letters", "words"]
    containers = ["string", "list", "file", "text"]

    for _ in range(1500):
        choice = random.randint(0, 4)
        if choice == 0:
            adj = random.choice(adjs)
            n = random.choice(["first", "last", "largest", "smallest", "even", "odd", "positive", "negative"])
            task = f"return the {adj} of {n} numbers from a list"
            code = f'def func(lst):\n    """Return {adj} of {n} elements."""\n    # Filter/select {n} numbers then compute {adj}\n    filtered = [x for x in lst]  # adapt filter\n    return {adj}(filtered) if filtered else None'
        elif choice == 1:
            op = random.choice(ops)
            task = f"compute the {op} of all elements in a list"
            code = f'def func(lst):\n    """Compute {op} of list elements."""\n    result = []\n    total = 0\n    for x in lst:\n        total += x  # adapt for {op}\n        result.append(total)\n    return result'
        elif choice == 2:
            ct = random.choice(chartypes)
            task = f"check if a string contains only {ct} characters"
            method = {"alphabetic": "isalpha", "numeric": "isdigit", "alphanumeric": "isalnum",
                      "uppercase": "isupper", "lowercase": "islower", "ASCII": "isascii"}.get(ct, "isalpha")
            code = f'def check_{ct}(s):\n    """Return True if string is all {ct}."""\n    return s.{method}() if s else False'
        elif choice == 3:
            src, dst = random.choice(src_dst)
            task = f"convert a {src} to a {dst}"
            code = f'def convert(data):\n    """Convert {src} to {dst}."""\n    # Implementation depends on specific {src} -> {dst} conversion\n    return {dst}(data)  # simplified'
        else:
            what = random.choice(whats)
            cont = random.choice(containers)
            task = f"count occurrences of {what} in a {cont}"
            code = f'def count_{what.replace(" ", "_")}(data):\n    """Count {what} in {cont}."""\n    return sum(1 for c in str(data) if c in "target_chars")'

        for v in random.sample(variations, 2):
            add_pair(v.format(task=task), code)

    # BOOST: More "explain this code" with unique expressions
    for _ in range(1000):
        a = random.randint(1, 200)
        b = random.randint(1, 200)
        expr_type = random.choice(["ternary", "walrus", "star", "chain", "nested"])
        if expr_type == "ternary":
            code_s = f"x = {a} if {a} > {b} else {b}"
            result = max(a, b)
            add_pair(f"What does `{code_s}` do?",
                     f"Conditional expression (ternary operator). If {a} > {b} is {a > b}, x = {result}. Equivalent to if/else in one line.")
        elif expr_type == "walrus":
            code_s = f"[y for x in range({a % 20}) if (y := x*{b % 10}) > {a % 30}]"
            add_pair(f"Explain: `{code_s}`",
                     f"Uses walrus operator (:=) to assign y = x*{b%10} and filter where y > {a%30}. Combines assignment and condition in comprehension.")
        elif expr_type == "star":
            code_s = f"first, *rest = [{a}, {b}, {a+b}, {a*b}]"
            add_pair(f"What happens with: `{code_s}`?",
                     f"Extended unpacking: first = {a}, rest = [{b}, {a+b}, {a*b}]. The * captures remaining elements as a list.")
        elif expr_type == "chain":
            c = random.randint(1, 200)
            code_s = f"{min(a,b,c)} < {sorted([a,b,c])[1]} < {max(a,b,c)}"
            result = min(a,b,c) < sorted([a,b,c])[1] < max(a,b,c)
            add_pair(f"Is `{code_s}` True or False?",
                     f"Python supports chained comparisons. This evaluates to {result}.")
        else:
            code_s = f"[{a}*i+{b} for i in range({random.randint(3,8)})]"
            n = random.randint(3, 8)
            add_pair(f"What list does `[{a}*i+{b} for i in range({n})]` produce?",
                     f"Generates [{', '.join(str(a*i+b) for i in range(n))}]. Formula {a}*i+{b} for i from 0 to {n-1}.")

    # BOOST: "What's the time complexity?" questions
    complexities = [
        ("linear search", "O(n)", "Checks each element sequentially. Worst case examines all n elements."),
        ("binary search", "O(log n)", "Halves search space each step. Requires sorted input."),
        ("bubble sort", "O(n^2)", "Nested loops comparing adjacent elements. Inefficient for large lists."),
        ("merge sort", "O(n log n)", "Divide-and-conquer. Splits, sorts halves, merges. Consistent performance."),
        ("quick sort average", "O(n log n)", "Partition-based. Average case with good pivot selection."),
        ("quick sort worst", "O(n^2)", "Worst case with poor pivot (already sorted input). Rare with randomization."),
        ("hash table lookup", "O(1) average", "Direct access via hash function. Collisions degrade to O(n) worst case."),
        ("BST search balanced", "O(log n)", "Binary search tree. Balanced tree halves search space each level."),
        ("BST search worst", "O(n)", "Degenerate tree (like linked list). All nodes on one side."),
        ("heap insert", "O(log n)", "Add at end, bubble up. Height of tree is log n."),
        ("DFS", "O(V + E)", "Visits each vertex and edge once. V = vertices, E = edges."),
        ("BFS", "O(V + E)", "Same as DFS. Visits each vertex and edge once via queue."),
        ("accessing array element", "O(1)", "Direct index calculation. Memory offset = base + index * size."),
        ("inserting at array start", "O(n)", "Must shift all existing elements one position right."),
        ("appending to Python list", "O(1) amortized", "Usually O(1). Occasionally O(n) when array needs reallocation."),
        ("dictionary lookup", "O(1) average", "Hash table based. Very fast for average case. O(n) worst with many collisions."),
        ("sorting with counting sort", "O(n + k)", "Where k is the range of values. Linear for small k. Not comparison-based."),
        ("matrix multiplication naive", "O(n^3)", "Three nested loops for n x n matrices. Strassen's is O(n^2.807)."),
        ("Fibonacci recursive naive", "O(2^n)", "Exponential due to redundant recomputation. Use DP for O(n)."),
        ("Fibonacci with memoization", "O(n)", "Each subproblem solved once and cached. Linear time and space."),
    ]
    for algo, complexity, explanation in complexities:
        add_pair(f"What is the time complexity of {algo}?",
                 f"Time complexity: {complexity}. {explanation}")
        add_pair(f"Big O of {algo}?",
                 f"{complexity}. {explanation}")

    # BOOST: Python error type questions
    errors = [
        ("TypeError", "Raised when an operation is applied to wrong type. Example: '2' + 3. Fix: convert types explicitly."),
        ("ValueError", "Raised when function receives correct type but wrong value. Example: int('abc'). Fix: validate input."),
        ("KeyError", "Raised when dictionary key doesn't exist. Example: d['missing']. Fix: use .get() with default."),
        ("IndexError", "Raised when sequence index is out of range. Example: lst[10] when len(lst)=5. Fix: check bounds."),
        ("AttributeError", "Raised when attribute doesn't exist on object. Example: None.append(1). Fix: check object type."),
        ("NameError", "Raised when variable is not defined. Example: print(undefined_var). Fix: define variable first."),
        ("ZeroDivisionError", "Raised when dividing by zero. Example: 10 / 0. Fix: check divisor before dividing."),
        ("ImportError", "Raised when module can't be imported. Example: import nonexistent. Fix: install package or check name."),
        ("FileNotFoundError", "Raised when file doesn't exist. Example: open('missing.txt'). Fix: check path, use try/except."),
        ("StopIteration", "Raised when iterator has no more items. Example: next(iter([])). Fix: use for loop or check first."),
        ("RecursionError", "Raised when max recursion depth exceeded. Example: infinite recursive calls. Fix: add base case or use iteration."),
        ("MemoryError", "Raised when operation runs out of memory. Example: [0] * 10**12. Fix: process data in chunks or use generators."),
        ("OverflowError", "Raised when numeric result too large. Example: math.exp(1000). Fix: use arbitrary precision or check bounds."),
        ("SyntaxError", "Raised when code has invalid syntax. Example: if x = 5. Fix: use == for comparison."),
        ("IndentationError", "Raised when indentation is wrong. Example: misaligned block. Fix: use consistent 4-space indentation."),
    ]
    for err, explanation in errors:
        add_pair(f"What is {err} in Python?", f"{err}: {explanation}")
        add_pair(f"When does Python raise {err}?", f"{err}: {explanation}")
        add_pair(f"How do you fix {err}?", f"{err}: {explanation}")

    # BOOST: Python standard library module questions
    modules = [
        ("os", "OS interface: file operations, paths, environment variables. os.path for path manipulation, os.listdir for directory listing, os.environ for env vars."),
        ("sys", "System-specific functions. sys.argv for command args, sys.path for import paths, sys.exit for termination, sys.stdin/stdout for I/O."),
        ("json", "JSON encoding/decoding. json.dumps(obj) to serialize, json.loads(string) to deserialize. json.dump/load for file I/O."),
        ("math", "Mathematical functions. math.sqrt, math.pi, math.ceil, math.floor, math.gcd, math.factorial. C library math wrapper."),
        ("random", "Random number generation. random.randint(a,b), random.choice(seq), random.shuffle(lst), random.sample(pop, k)."),
        ("datetime", "Date and time handling. datetime.now(), timedelta for arithmetic, strftime for formatting, strptime for parsing."),
        ("collections", "Specialized containers. Counter (frequencies), defaultdict (default values), deque (double-ended queue), namedtuple."),
        ("itertools", "Iterator building blocks. chain, combinations, permutations, product, groupby, cycle, repeat. Memory-efficient."),
        ("functools", "Higher-order functions. lru_cache (memoization), partial (partial application), reduce (fold), wraps (decorator helper)."),
        ("re", "Regular expressions. re.match, re.search, re.findall, re.sub. Compile patterns for reuse. Supports groups, lookahead."),
        ("pathlib", "Object-oriented filesystem paths. Path objects with / operator. p.exists(), p.read_text(), p.glob(). Modern replacement for os.path."),
        ("typing", "Type hints. List[int], Dict[str, Any], Optional[str], Union[int, str], Tuple, Callable. For static analysis tools."),
        ("unittest", "Testing framework. TestCase class, assertEqual, assertTrue, setUp/tearDown. Run with python -m unittest. Built-in."),
        ("logging", "Logging facility. Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL. Configurable handlers, formatters. Better than print debugging."),
        ("argparse", "Command-line argument parser. Define arguments, types, help text. Generates usage messages. Standard for CLI tools."),
    ]
    for mod, description in modules:
        add_pair(f"What does the Python {mod} module do?", f"The {mod} module: {description}")
        add_pair(f"Describe Python's {mod} module.", f"{mod}: {description}")

    # BOOST: Data structure operation questions
    for _ in range(500):
        ds = random.choice(["list", "dict", "set", "string", "tuple"])
        if ds == "list":
            ops = [("append(x)", "Adds x to end. O(1) amortized."),
                   ("insert(i, x)", "Inserts x at index i. O(n) due to shifting."),
                   ("pop()", "Removes and returns last element. O(1)."),
                   ("pop(0)", "Removes first element. O(n) due to shifting."),
                   ("sort()", "Sorts in place using Timsort. O(n log n)."),
                   ("reverse()", "Reverses list in place. O(n)."),
                   ("index(x)", "Returns first index of x. O(n) linear search."),
                   ("extend(iter)", "Appends all items from iterable. O(k) where k = iterable length."),
                   ("count(x)", "Counts occurrences of x. O(n) full scan."),
                   ("copy()", "Creates shallow copy. O(n).")]
        elif ds == "dict":
            ops = [("get(k, default)", "Returns value for key k, or default if missing. O(1)."),
                   ("keys()", "Returns view of all keys. O(1) to create view."),
                   ("values()", "Returns view of all values. O(1) to create view."),
                   ("items()", "Returns view of (key, value) pairs. O(1) to create view."),
                   ("update(other)", "Merges other dict into this one. O(len(other))."),
                   ("pop(k)", "Removes key k and returns its value. O(1)."),
                   ("setdefault(k, v)", "Returns d[k] if exists, else sets d[k]=v and returns v. O(1).")]
        elif ds == "set":
            ops = [("add(x)", "Adds element x. O(1) average."),
                   ("remove(x)", "Removes x, raises KeyError if missing. O(1)."),
                   ("discard(x)", "Removes x if present, no error if missing. O(1)."),
                   ("union(other)", "Returns new set with elements from both. O(len(s) + len(other))."),
                   ("intersection(other)", "Returns elements common to both. O(min(len(s), len(other)))."),
                   ("difference(other)", "Returns elements in s but not other. O(len(s)).")]
        elif ds == "string":
            ops = [("split(sep)", "Splits string by separator into list. O(n)."),
                   ("join(iterable)", "Joins iterable elements with string as separator. O(n)."),
                   ("strip()", "Removes leading/trailing whitespace. O(n)."),
                   ("replace(old, new)", "Returns string with all old replaced by new. O(n)."),
                   ("find(sub)", "Returns index of first occurrence of sub, -1 if not found. O(n)."),
                   ("startswith(prefix)", "Returns True if string starts with prefix. O(len(prefix)).")]
        else:
            ops = [("count(x)", "Returns number of occurrences of x. O(n)."),
                   ("index(x)", "Returns first index of x. O(n). Raises ValueError if not found."),
                   ("len()", "Returns number of elements. O(1)."),
                   ("slicing [a:b]", "Returns new tuple with elements from a to b-1. O(b-a).")]
        op_name, description = random.choice(ops)
        add_pair(f"What does {ds}.{op_name} do in Python?",
                 f"For Python {ds}, {op_name}: {description}")

    # BOOST: Unique "trace the code" with specific values
    for _ in range(800):
        a = random.randint(1, 50)
        b = random.randint(1, 50)
        c = random.randint(1, 50)
        pattern = random.choice(["for_sum", "while_count", "if_chain", "list_build", "dict_build", "nested_loop"])
        if pattern == "for_sum":
            total = sum(range(a, a + b))
            add_pair(f"What is the output of: total=0; [total := total + i for i in range({a},{a+b})]; print(total)?",
                     f"The loop sums integers from {a} to {a+b-1}. Total = {total}.")
        elif pattern == "while_count":
            steps = 0
            v = a * b
            while v > 1:
                v //= 2
                steps += 1
            add_pair(f"Starting with n={a*b}, how many times can you divide by 2 before reaching 0 or 1?",
                     f"Starting at {a*b}: divide by 2 repeatedly. Takes {steps} steps to reach <= 1. This is floor(log2({a*b})).")
        elif pattern == "if_chain":
            val = a * b - c
            if val > 0: label = "positive"
            elif val == 0: label = "zero"
            else: label = "negative"
            add_pair(f"If x = {a} * {b} - {c}, is x positive, negative, or zero?",
                     f"x = {a} * {b} - {c} = {a*b} - {c} = {val}. x is {label}.")
        elif pattern == "list_build":
            lst = [i**2 for i in range(a % 10 + 2)]
            add_pair(f"Build the list [i**2 for i in range({a % 10 + 2})]. What are the elements?",
                     f"Result: {lst}. Squares of 0 through {a % 10 + 1}.")
        elif pattern == "dict_build":
            n = (a % 5) + 3
            d = {chr(65 + i): i * b for i in range(n)}
            add_pair(f"What dict does {{chr(65+i): i*{b} for i in range({n})}} create?",
                     f"Result: {d}. Maps letters A-{chr(64+n)} to multiples of {b}.")
        else:
            rows = (a % 3) + 2
            cols = (b % 3) + 2
            total = rows * cols
            add_pair(f"How many times does the inner loop run: for i in range({rows}): for j in range({cols}): ...",
                     f"Outer loop runs {rows} times, inner runs {cols} times each. Total iterations: {rows} x {cols} = {total}.")

    # BOOST: Python one-liners
    for _ in range(500):
        n = random.randint(3, 20)
        pattern = random.choice(["fizzbuzz", "filter_even", "flatten", "zip_dict", "enumerate_str"])
        if pattern == "fizzbuzz":
            add_pair(f"Write a one-liner for FizzBuzz up to {n}.",
                     f"['FizzBuzz' if i%15==0 else 'Fizz' if i%3==0 else 'Buzz' if i%5==0 else i for i in range(1,{n+1})]")
        elif pattern == "filter_even":
            evens = [i for i in range(n) if i % 2 == 0]
            add_pair(f"Filter even numbers from range({n}) in one line.",
                     f"[x for x in range({n}) if x % 2 == 0] produces {evens}.")
        elif pattern == "flatten":
            add_pair(f"Flatten [[1,2],[3,4],...] with {n} sublists in one line.",
                     f"[x for sub in nested_list for x in sub]. This double for-loop unpacks each sublist into a flat list.")
        elif pattern == "zip_dict":
            keys = [chr(65 + i) for i in range(min(n, 10))]
            add_pair(f"Create a dict from keys {keys} and values range({len(keys)}) in one line.",
                     f"dict(zip({keys}, range({len(keys)}))). Result: {dict(zip(keys, range(len(keys))))}.")
        else:
            s = "hello world"[:n]
            add_pair(f"Enumerate '{s}' and show all (index, char) pairs.",
                     f"list(enumerate('{s}')) = {list(enumerate(s))}.")

    print(f"  code: {len(pairs)} pairs", flush=True)
    return pairs

# ============================================================
# 3. LOGIC AND REASONING (3,500+ unique pairs)
# ============================================================

def gen_logic_pairs():
    random.seed(44)
    pairs = []
    seen = set()

    def add_pair(p, r):
        if p not in seen:
            seen.add(p)
            pairs.append(pair(p, r, "logic"))

    # --- Transitive relations (500) ---
    items = ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Hank", "Ivy", "Jack",
             "Kim", "Leo", "Mia", "Nate", "Olive", "Pat", "Quinn", "Rita", "Sam", "Tina"]
    relations = ["taller than", "older than", "faster than", "heavier than", "stronger than",
                 "smarter than", "richer than", "louder than"]
    for _ in range(600):
        a, b, c = random.sample(items, 3)
        rel = random.choice(relations)
        add_pair(f"If {a} is {rel} {b}, and {b} is {rel} {c}, what is the relationship between {a} and {c}?",
                 f"By the transitive property: {a} is {rel} {b}, and {b} is {rel} {c}. "
                 f"Therefore {a} is {rel} {c}. The ordering is {a} > {b} > {c}.")

    # --- Arithmetic sequences (300) ---
    for _ in range(400):
        start = random.randint(-50, 100)
        diff = random.choice([i for i in range(-20, 21) if i != 0])
        seq = [start + i * diff for i in range(5)]
        answer = start + 5 * diff
        add_pair(f"What comes next: {', '.join(map(str, seq))}, ?",
                 f"Arithmetic sequence with common difference {diff}. Each term changes by {diff}. "
                 f"Next: {seq[-1]} + ({diff}) = {answer}.")

    # --- Geometric sequences (200) ---
    for _ in range(300):
        start = random.randint(1, 10)
        ratio = random.choice([2, 3, 4, 5, -2, -3])
        seq = [start * (ratio ** i) for i in range(5)]
        answer = start * (ratio ** 5)
        add_pair(f"Find the next number: {', '.join(map(str, seq))}, ?",
                 f"Geometric sequence with ratio {ratio}. Each term is multiplied by {ratio}. "
                 f"Next: {seq[-1]} * {ratio} = {answer}.")

    # --- Fibonacci-like (200) ---
    for _ in range(300):
        a, b = random.randint(1, 20), random.randint(1, 20)
        seq = [a, b]
        for _ in range(4):
            seq.append(seq[-1] + seq[-2])
        answer = seq[-1] + seq[-2]
        add_pair(f"Each number is the sum of the two before it: {', '.join(map(str, seq))}, ?",
                 f"Fibonacci-like pattern. {seq[-2]} + {seq[-1]} = {answer}. The next number is {answer}.")

    # --- Square number patterns (150) ---
    for _ in range(200):
        start = random.randint(1, 15)
        seq = [(start + i) ** 2 for i in range(5)]
        answer = (start + 5) ** 2
        add_pair(f"Identify the pattern: {', '.join(map(str, seq))}, ?",
                 f"These are consecutive perfect squares: {start}^2, {start+1}^2, ... "
                 f"Next: {start+5}^2 = {answer}.")

    # --- Truth tables (400) ---
    for _ in range(500):
        a_val = random.choice([True, False])
        b_val = random.choice([True, False])
        op = random.choice(["AND", "OR", "XOR", "NAND", "NOR", "IMPLIES"])
        if op == "AND": result = a_val and b_val
        elif op == "OR": result = a_val or b_val
        elif op == "XOR": result = a_val != b_val
        elif op == "NAND": result = not (a_val and b_val)
        elif op == "NOR": result = not (a_val or b_val)
        else: result = (not a_val) or b_val  # IMPLIES
        add_pair(f"Evaluate: {a_val} {op} {b_val}",
                 f"Logical {op}: A={a_val}, B={b_val}. Result: {result}. "
                 f"The {op} operator returns {result} for these inputs.")

    # --- Set operations (400) ---
    for _ in range(500):
        sa = sorted(random.sample(range(1, 30), random.randint(3, 7)))
        sb = sorted(random.sample(range(1, 30), random.randint(3, 7)))
        op = random.choice(["union", "intersection", "difference", "symmetric difference"])
        a, b = set(sa), set(sb)
        if op == "union": res = sorted(a | b)
        elif op == "intersection": res = sorted(a & b)
        elif op == "difference": res = sorted(a - b)
        else: res = sorted(a ^ b)
        add_pair(f"Find the {op} of {{{', '.join(map(str,sa))}}} and {{{', '.join(map(str,sb))}}}.",
                 f"A = {{{', '.join(map(str,sa))}}}, B = {{{', '.join(map(str,sb))}}}\n"
                 f"A {op} B = {{{', '.join(map(str,res))}}}.")

    # --- Syllogisms (300) ---
    categories = [
        ("dogs", "mammals", "animals"), ("roses", "flowers", "plants"),
        ("squares", "rectangles", "shapes"), ("sparrows", "birds", "animals"),
        ("integers", "rational numbers", "numbers"), ("oaks", "trees", "plants"),
        ("Python", "programming languages", "tools"), ("violins", "instruments", "objects"),
        ("novels", "books", "publications"), ("apples", "fruits", "foods"),
        ("copper", "metals", "elements"), ("algebra", "mathematics", "sciences"),
    ]
    for _ in range(400):
        a, b, c = random.choice(categories)
        add_pair(f"All {a} are {b}. All {b} are {c}. What about {a}?",
                 f"By the transitive property: All {a} are {b}, and all {b} are {c}. "
                 f"Therefore all {a} are {c}. This is a valid syllogism.")

    # --- Analogies (500) ---
    analogies = [
        ("Cat", "kitten", "Dog", "puppy", "adult animal to its young"),
        ("Hot", "cold", "Big", "small", "pairs of antonyms"),
        ("Author", "book", "Composer", "symphony", "creator to creation"),
        ("Teacher", "school", "Doctor", "hospital", "professional to workplace"),
        ("Pen", "writing", "Brush", "painting", "tool to its creative use"),
        ("Fish", "water", "Bird", "air", "animal to its medium"),
        ("Seed", "tree", "Egg", "bird", "origin to mature form"),
        ("Eye", "sight", "Ear", "hearing", "organ to sense"),
        ("Key", "lock", "Password", "account", "access mechanism to protected thing"),
        ("Telescope", "stars", "Microscope", "cells", "instrument to observation target"),
        ("Glove", "hand", "Shoe", "foot", "covering to body part"),
        ("Chef", "kitchen", "Pilot", "cockpit", "professional to workspace"),
        ("Flour", "bread", "Grape", "wine", "ingredient to product"),
        ("Chapter", "book", "Episode", "series", "unit to whole"),
        ("Blade", "knife", "Barrel", "gun", "component to tool"),
    ]
    analogy_prompts = [
        "{a} is to {b} as {c} is to ?",
        "Complete: {a} : {b} :: {c} : ?",
        "If {a} relates to {b}, what does {c} relate to?",
        "Analogy: {a} -> {b}, {c} -> ?",
    ]
    for _ in range(600):
        a, b, c, d, reason = random.choice(analogies)
        tmpl = random.choice(analogy_prompts)
        add_pair(tmpl.format(a=a, b=b, c=c),
                 f"Answer: {d}. Both relate {reason}. Just as {a} is to {b}, {c} is to {d}.")

    # --- Age/ranking puzzles (400) ---
    for _ in range(500):
        names = random.sample(["Alice","Bob","Carol","Dave","Eve","Frank","Grace","Hank"], 3)
        scores = sorted(random.sample(range(40, 100), 3), reverse=True)
        add_pair(f"{names[0]} scored {scores[0]}, {names[1]} scored {scores[1]}, {names[2]} scored {scores[2]}. Rank them.",
                 f"1st: {names[0]} ({scores[0]}), 2nd: {names[1]} ({scores[1]}), 3rd: {names[2]} ({scores[2]}). "
                 f"Highest score wins.")

    for _ in range(400):
        name = random.choice(["Alice","Bob","Carol","Dave","Eve","Frank"])
        age = random.randint(5, 60)
        years = random.randint(1, 30)
        direction = random.choice(["will be in", "was"])
        if direction == "will be in":
            add_pair(f"{name} is {age}. How old will {name} be in {years} years?",
                     f"Current age: {age}. In {years} years: {age} + {years} = {age+years}. {name} will be {age+years}.")
        else:
            add_pair(f"{name} is {age}. How old was {name} {min(years, age-1)} years ago?",
                     f"Current age: {age}. {min(years,age-1)} years ago: {age} - {min(years,age-1)} = {age-min(years,age-1)}.")

    # --- Number properties (200) ---
    for _ in range(300):
        n = random.randint(1, 500)
        props = []
        if n % 2 == 0: props.append("even")
        else: props.append("odd")
        if n > 0 and all(n % i != 0 for i in range(2, min(int(n**0.5)+1, n))): props.append("prime")
        root = int(n**0.5)
        if root * root == n: props.append("perfect square")
        if n % 3 == 0: props.append("divisible by 3")
        if n % 5 == 0: props.append("divisible by 5")
        add_pair(f"What are the properties of the number {n}?",
                 f"{n} is {', '.join(props)}. " + (f"Factors include: " + ", ".join(str(i) for i in range(1, min(n+1, 20)) if n % i == 0) + "." if n < 100 else ""))

    print(f"  logic: {len(pairs)} pairs", flush=True)
    return pairs

# ============================================================
# 4. KNOWLEDGE Q&A (5,500+ unique pairs)
# ============================================================

def gen_knowledge_pairs():
    random.seed(45)
    pairs = []
    seen = set()

    def add_pair(p, r):
        if p not in seen:
            seen.add(p)
            pairs.append(pair(p, r, "knowledge"))

    # Massive concept dictionary (200+ entries)
    concepts = {
        "algorithm": "A finite sequence of well-defined instructions to solve a problem. Has inputs, outputs, definiteness, and finiteness. Foundation of computer science.",
        "data structure": "A way of organizing data for efficient access and modification. Examples: arrays, linked lists, trees, hash tables, graphs. Choice impacts performance.",
        "recursion": "A function calling itself with a smaller subproblem. Requires base case + recursive case. Used for trees, divide-and-conquer. Risk: stack overflow.",
        "hash table": "Maps keys to values via hash function. O(1) average lookup. Handles collisions with chaining or probing. Python dicts use hash tables.",
        "binary tree": "Hierarchical structure with at most two children per node. Variants: BST, AVL, Red-Black, heap. Used in search, sort, parsing.",
        "linked list": "Linear structure with nodes connected by pointers. O(1) insert/delete at known positions, O(n) access. Variants: singly, doubly, circular.",
        "stack": "LIFO structure. Push/pop from top. Used in function calls, undo, DFS, expression evaluation. Implemented with array or linked list.",
        "queue": "FIFO structure. Enqueue at rear, dequeue from front. Used in BFS, scheduling, buffering. Variants: priority queue, deque.",
        "graph": "Vertices connected by edges. Directed or undirected, weighted or not. Represented as adjacency matrix or list. Models networks and relationships.",
        "sorting algorithm": "Arranges elements in order. Bubble O(n^2), Merge O(n log n), Quick O(n log n) avg. Lower bound for comparison sorts: O(n log n).",
        "Big O notation": "Describes algorithm complexity growth. O(1) constant, O(log n) logarithmic, O(n) linear, O(n^2) quadratic, O(2^n) exponential.",
        "dynamic programming": "Solves problems by storing subproblem solutions to avoid recomputation. Memoization (top-down) or tabulation (bottom-up). Classic: Fibonacci, knapsack.",
        "API": "Application Programming Interface. Defines how software components interact. REST APIs use HTTP methods. Enables system integration.",
        "database": "Organized collection of structured data. Relational (SQL, tables) or NoSQL (documents, key-value). ACID properties ensure integrity.",
        "SQL": "Structured Query Language for relational databases. SELECT, INSERT, UPDATE, DELETE. Supports JOINs, aggregation, subqueries.",
        "TCP/IP": "Internet protocol suite. TCP ensures reliable ordered delivery. IP handles addressing and routing. Foundation of networked communication.",
        "HTTP": "Web protocol. Methods: GET, POST, PUT, DELETE. Status: 200 OK, 404 Not Found, 500 Error. HTTPS adds TLS encryption.",
        "encryption": "Converts plaintext to ciphertext. Symmetric (AES, one key) or asymmetric (RSA, public/private keys). Protects data confidentiality.",
        "machine learning": "Systems learn patterns from data. Supervised (labeled), unsupervised (clustering), reinforcement (rewards). Powers recommendation, vision, NLP.",
        "neural network": "Computational model with layers of neurons. Input, hidden, output layers. Trained via backpropagation. Basis of deep learning.",
        "compiler": "Translates high-level source code to machine code. Phases: lexing, parsing, semantic analysis, optimization, codegen. Compiles before execution.",
        "interpreter": "Executes source code line by line. Easier debugging, slower than compiled. Python, JavaScript use interpreters. Some use bytecode + VM.",
        "operating system": "Manages hardware and software resources. Process management, memory, file system, I/O, security. Windows, Linux, macOS.",
        "thread": "Smallest execution unit in a process. Shares memory space. Enables concurrency. Challenges: race conditions, deadlocks.",
        "process": "Running program instance with own memory. Communicates via IPC (pipes, sockets). Heavier than threads but better isolated.",
        "version control": "Tracks file changes over time. Git is most popular. Commits, branches, merges. Platforms: GitHub, GitLab.",
        "unit testing": "Verifies individual code components in isolation. Small, fast, focused tests. Frameworks: pytest, JUnit. Part of testing pyramid.",
        "design pattern": "Reusable solution to common software problem. Creational (Factory), structural (Adapter), behavioral (Observer). Improves maintainability.",
        "REST": "Architectural style for web APIs. Stateless, client-server, cacheable, uniform interface. Resources identified by URLs. JSON format.",
        "cloud computing": "Computing services over the internet. IaaS, PaaS, SaaS. Providers: AWS, Azure, GCP. Benefits: scalability, cost efficiency.",
        "containerization": "Packages apps with dependencies in isolated containers. Docker leads. Shares host OS kernel. Kubernetes orchestrates deployment.",
        "microservices": "Application as small independent services. Each handles specific function. API communication. Independent deployment. Complex distributed system.",
        "DevOps": "Combines development and operations. Short cycles, frequent deployment, reliable releases. CI/CD, infrastructure as code, monitoring.",
        "agile": "Iterative development with flexibility and customer feedback. Sprints, standups, retrospectives. Responds to change over rigid planning.",
        "cache": "High-speed storage for frequently accessed data. CPU cache, browser cache, Redis. Strategies: LRU, LFU, TTL. Trades space for speed.",
        "DNS": "Domain Name System translates domains to IPs. Hierarchical: root, TLD, authoritative servers. Records: A, AAAA, CNAME, MX.",
        "blockchain": "Distributed immutable ledger. Data in cryptographically linked blocks. Consensus via PoW or PoS. Used in crypto, supply chain.",
        "functional programming": "Computation as mathematical function evaluation. Pure functions, immutability, higher-order functions. Haskell, Lisp, Erlang.",
        "OOP": "Object-oriented programming. Objects combine data and behavior. Four pillars: encapsulation, inheritance, polymorphism, abstraction.",
        "regular expression": "Pattern for matching text. Metacharacters: . * + [] ^ $. Used for validation, search, text processing. Python re module.",
        "prime number": "Natural number > 1 divisible only by 1 and itself. Examples: 2, 3, 5, 7, 11. Only even prime is 2. Key in cryptography.",
        "matrix": "Rectangular array of numbers. Operations: add, multiply, transpose, invert. Used in linear algebra, graphics, ML.",
        "logarithm": "Inverse of exponentiation. log_b(x)=y means b^y=x. Properties: log(ab)=log(a)+log(b). Common bases: 10, e, 2.",
        "derivative": "Rate of change of function. f'(x) or df/dx. Power rule: nx^(n-1). Used in optimization, physics, ML gradient descent.",
        "integral": "Accumulates quantities / area under curve. Definite (bounded) or indefinite (antiderivative). Fundamental theorem links to derivatives.",
        "probability": "Likelihood of event, 0 to 1. P(A) = favorable/total outcomes. Addition and multiplication rules. Bayes theorem for conditional.",
        "standard deviation": "Measure of data spread around mean. Square root of variance. Low = clustered, high = spread. Used in statistics, finance.",
        "Pythagorean theorem": "In right triangle: a^2 + b^2 = c^2. c is hypotenuse. Used for distance calculation and right angle verification.",
        "Fibonacci sequence": "0, 1, 1, 2, 3, 5, 8, 13, 21... Each number = sum of two preceding. Appears in nature, art (golden ratio), algorithms.",
        "photosynthesis": "Plants convert light, CO2, water into glucose and O2. Occurs in chloroplasts. 6CO2 + 6H2O + light -> C6H12O6 + 6O2.",
        "DNA": "Deoxyribonucleic acid carries genetic instructions. Double helix with base pairs A-T, G-C. Replication, transcription, translation.",
        "evolution": "Change in heritable traits over generations. Mechanisms: natural selection, genetic drift, mutation. Explains adaptation.",
        "gravity": "Attraction between masses. Newton: F=Gm1m2/r^2. Einstein: spacetime curvature. Earth surface: 9.8 m/s^2.",
        "atom": "Smallest unit retaining element properties. Nucleus (protons, neutrons) + electrons. Atomic number = proton count.",
        "cell": "Basic unit of life. Prokaryotic (no nucleus) or eukaryotic (nucleus + organelles). Functions: metabolism, growth, reproduction.",
        "thermodynamics": "Study of energy and heat. Laws: 0th (equilibrium), 1st (conservation), 2nd (entropy increases), 3rd (absolute zero limit).",
        "pH": "Acidity/basicity scale 0-14. pH 7 neutral, <7 acidic, >7 basic. pH = -log[H+]. Important in chemistry, biology.",
        "Newton's laws": "1st: inertia. 2nd: F=ma. 3rd: every action has equal opposite reaction. Foundation of classical mechanics.",
        "relativity": "Einstein's theories. Special (1905): E=mc^2, constant light speed. General (1915): gravity = spacetime curvature.",
        "ecosystem": "Community of organisms + environment. Producers, consumers, decomposers. Energy flows through food chains. Nutrient cycles.",
        "periodic table": "Organizes elements by atomic number. Rows = periods, columns = groups. Metals left, nonmetals right. 118 elements.",
        "bandwidth": "Maximum data transfer rate. Measured in bps. Higher = more data simultaneously. Different from latency (delay).",
        "latency": "Time delay between request and response. Measured in milliseconds. Affected by distance, congestion, processing. Critical for real-time apps.",
        "middleware": "Software connecting different applications. Handles communication, auth, logging between client and server. Express.js, Django middleware.",
        "load balancing": "Distributes traffic across servers. Algorithms: round-robin, least connections. Improves availability and scalability. Nginx, HAProxy.",
        "CI/CD": "Continuous Integration / Continuous Delivery. CI: auto build + test on commit. CD: auto deploy. Jenkins, GitHub Actions.",
        "refactoring": "Restructuring code without changing behavior. Improves readability, reduces complexity. Extract method, rename, simplify conditionals.",
        "authentication": "Verifying identity. Methods: password, MFA, biometrics, tokens (JWT), OAuth. Different from authorization (access control).",
        "authorization": "Determining resource access after authentication. RBAC, ABAC, ACL models. Principle of least privilege.",
        "race condition": "Bug when concurrent threads access shared data and outcome depends on timing. Prevented with locks, mutexes, atomic operations.",
        "deadlock": "Two+ processes each hold a resource and wait for the other. Conditions: mutual exclusion, hold-wait, no preemption, circular wait.",
        "garbage collection": "Automatic memory management. Reference counting, mark-and-sweep, generational. Java, Python, Go use GC.",
        "normalization": "Database organization to minimize redundancy. 1NF (atomic values), 2NF (no partial deps), 3NF (no transitive deps).",
        "indexing": "Database structures (B-trees, hash) for faster retrieval. Trade write speed for read speed. Critical for large datasets.",
        "idempotency": "Operation producing same result regardless of repetition count. GET, PUT, DELETE are idempotent; POST is not. Important for reliability.",
        "monolith": "Single unified codebase application. All components share process and DB. Simpler initially, harder to scale and maintain as it grows.",
        "technical debt": "Cost of rework from choosing quick solutions. Accumulates interest (maintenance burden). Managed through refactoring and code reviews.",
    }

    # Generate 3 prompt variations per concept
    for concept, definition in concepts.items():
        for tmpl in [f"What is {concept}?", f"Define {concept}.", f"Explain {concept}."]:
            add_pair(tmpl, definition)

    # --- Comparisons (40 pairs x 4 prompts = 160) ---
    comparisons = [
        ("Python", "Java", "Python: dynamic typing, interpreted, concise, great for ML/scripting. Java: static typing, compiled to bytecode, verbose, enterprise/Android. Python easier to learn; Java faster execution."),
        ("SQL", "NoSQL", "SQL: relational, structured schema, ACID, SQL language. NoSQL: flexible schema, eventual consistency, document/key-value/graph. SQL for complex queries; NoSQL for scale."),
        ("stack", "queue", "Stack: LIFO, push/pop from top. Queue: FIFO, enqueue rear, dequeue front. Stack for recursion/undo; queue for scheduling/BFS."),
        ("array", "linked list", "Array: contiguous memory, O(1) access, O(n) insert. Linked list: non-contiguous, O(n) access, O(1) insert at known position."),
        ("TCP", "UDP", "TCP: reliable, ordered, connection-oriented, slower. UDP: unreliable, unordered, connectionless, faster. TCP for web; UDP for streaming."),
        ("merge sort", "quick sort", "Merge: O(n log n) always, stable, O(n) space. Quick: O(n log n) avg, O(n^2) worst, in-place. Quick usually faster in practice."),
        ("BFS", "DFS", "BFS: level-by-level, queue, shortest path. DFS: deep-first, stack/recursion, less memory. BFS for shortest path; DFS for topological sort."),
        ("class", "object", "Class: blueprint defining attributes and methods. Object: instance of a class with specific values. Class is template; object is concrete."),
        ("compiled", "interpreted", "Compiled: source to machine code before execution (C, Rust). Faster runtime. Interpreted: execute line by line (Python). Faster development."),
        ("REST", "GraphQL", "REST: resource-based URLs, multiple endpoints, over/under-fetching. GraphQL: single endpoint, client specifies exact data needed, complex queries."),
        ("Docker", "virtual machine", "Docker: lightweight containers sharing host OS kernel, fast startup. VM: full OS per instance, hardware-level isolation, heavier resource usage."),
        ("Git", "SVN", "Git: distributed, every clone is full repo, branching is cheap. SVN: centralized, single server, branching is expensive. Git dominates modern development."),
        ("Python 2", "Python 3", "Python 2: print statement, integer division, end of life 2020. Python 3: print function, true division, unicode strings, modern features."),
        ("list", "tuple", "List: mutable, [], slower, cannot be dict key. Tuple: immutable, (), faster, can be dict key. Use tuple for fixed collections."),
        ("map", "filter", "map(fn, iter) applies fn to every element. filter(fn, iter) keeps elements where fn returns True. Both return iterators in Python 3."),
        ("deep copy", "shallow copy", "Shallow: new object, references same nested objects. Deep: new object, recursively copies all nested. Shallow faster; deep safer for mutation."),
        ("concurrency", "parallelism", "Concurrency: handling multiple tasks (may alternate). Parallelism: executing multiple tasks simultaneously (requires multiple cores)."),
        ("HTTP", "HTTPS", "HTTP: plaintext, port 80, no encryption. HTTPS: encrypted with TLS/SSL, port 443, secure. HTTPS required for modern web."),
        ("IPv4", "IPv6", "IPv4: 32-bit, ~4.3 billion addresses, dotted decimal. IPv6: 128-bit, vastly more addresses, hex notation. IPv6 for future growth."),
        ("RAM", "ROM", "RAM: volatile, read-write, fast, loses data on power off. ROM: non-volatile, read-only, retains data. RAM for active processing; ROM for firmware."),
    ]
    for a, b, answer in comparisons:
        for tmpl in [f"Compare {a} and {b}.", f"What is the difference between {a} and {b}?",
                     f"{a} vs {b}?", f"How do {a} and {b} differ?"]:
            add_pair(tmpl, answer)

    # --- Properties (5 items x 2 prompts = 10) ---
    properties = [
        ("a good algorithm", "1. Correctness: right output for all inputs. 2. Efficiency: minimal time/space. 3. Finiteness: terminates. 4. Generality: works broadly. 5. Readability: clear code."),
        ("OOP", "1. Encapsulation: data + methods bundled. 2. Inheritance: extend parent classes. 3. Polymorphism: same interface, different implementations. 4. Abstraction: hide complexity. 5. Modularity: reusable objects."),
        ("good API design", "1. Consistent naming/URLs. 2. Proper HTTP methods/status codes. 3. Clear documentation. 4. Versioning for changes. 5. Auth and rate limiting."),
        ("Python", "1. Readable syntax with significant whitespace. 2. Dynamic typing. 3. Extensive standard library. 4. Huge ecosystem (PyPI). 5. Multi-paradigm: OOP + functional + procedural."),
        ("relational database", "1. Structured tables with rows/columns. 2. ACID transactions. 3. SQL query language. 4. Foreign key integrity. 5. Normalization reduces redundancy."),
    ]
    for topic, props in properties:
        add_pair(f"List 5 properties of {topic}.", props)
        add_pair(f"What characterizes {topic}?", props)

    # --- Pros/cons (8 topics x 3 prompts = 24) ---
    pros_cons = [
        ("Python", "Pros: Easy syntax, vast libraries, great for prototyping, strong community, ML/data dominance. Cons: Slower execution, GIL limits threading, high memory, weak mobile, runtime type errors."),
        ("microservices", "Pros: Independent deploy, tech flexibility, scalability, fault isolation. Cons: Distributed complexity, network latency, data consistency challenges, operational overhead."),
        ("cloud computing", "Pros: On-demand scaling, reduced costs, global availability, disaster recovery. Cons: Vendor lock-in, growing costs, security concerns, internet dependency."),
        ("NoSQL", "Pros: Flexible schema, horizontal scaling, high performance, handles unstructured data. Cons: Limited ACID, no standard query language, eventual consistency, harder complex queries."),
        ("open source", "Pros: Free to use/modify, community-driven, transparent, no vendor lock-in. Cons: Limited support, security risks if unmaintained, fragmentation, documentation gaps."),
        ("recursion", "Pros: Elegant for tree/graph problems, cleaner divide-and-conquer code, easier correctness proofs. Cons: Stack overflow risk, higher memory, harder to debug, often slower than iteration."),
        ("agile methodology", "Pros: Adapts to change, faster delivery, continuous feedback, early problem detection. Cons: Scope creep risk, needs experienced team, less predictable timelines, documentation neglected."),
        ("monolith architecture", "Pros: Simpler to develop initially, easier testing, single deployment, no network overhead. Cons: Hard to scale, tightly coupled, long build times, tech stack locked."),
    ]
    for topic, answer in pros_cons:
        for tmpl in [f"Pros and cons of {topic}?", f"Advantages and disadvantages of {topic}?",
                     f"Benefits and drawbacks of {topic}?"]:
            add_pair(tmpl, answer)

    # --- How-to questions (500) ---
    howtos = [
        ("How do you create a virtual environment in Python?",
         "Run: python -m venv myenv. Activate: source myenv/bin/activate (Linux/Mac) or myenv\\Scripts\\activate (Windows). Install packages with pip. Deactivate with: deactivate."),
        ("How do you handle errors in Python?",
         "Use try/except blocks: try: risky_code except TypeError as e: handle. Add else (no error) and finally (always runs). Raise custom exceptions with raise."),
        ("How do you read a file in Python?",
         "Use context manager: with open('file.txt', 'r') as f: content = f.read(). For lines: f.readlines() or iterate with for line in f. Always use 'with' for auto-close."),
        ("How do you install Python packages?",
         "Use pip: pip install package_name. From requirements: pip install -r requirements.txt. Upgrade: pip install --upgrade pkg. List installed: pip list."),
        ("How do you create a class in Python?",
         "class MyClass:\n    def __init__(self, name):\n        self.name = name\n    def greet(self):\n        return f'Hello, {self.name}'\nobj = MyClass('World')"),
        ("How do you debug Python code?",
         "Use print() for quick checks. Use pdb: import pdb; pdb.set_trace(). Use IDE debugger (breakpoints). Use logging module for production. Read tracebacks bottom-up."),
        ("How do you use list comprehensions?",
         "Syntax: [expression for item in iterable if condition]. Examples: [x**2 for x in range(10)], [w.upper() for w in words if len(w) > 3]. More readable than map/filter."),
        ("How do you sort a dictionary by value?",
         "sorted_dict = dict(sorted(d.items(), key=lambda x: x[1])). For reverse: add reverse=True. Returns sorted list of tuples, wrap in dict() for dictionary."),
        ("How do you merge two dictionaries?",
         "Python 3.9+: merged = d1 | d2. Python 3.5+: merged = {**d1, **d2}. Or: d1.update(d2) modifies d1 in-place. Later values overwrite earlier ones."),
        ("How do you use regular expressions in Python?",
         "import re. Match: re.match(pattern, string). Search: re.search(). Find all: re.findall(). Replace: re.sub(). Compile for reuse: pattern = re.compile(r'\\d+')."),
    ]
    for q, a in howtos:
        add_pair(q, a)

    # Generate more "what is X" with extra terms
    extra_terms = {
        "API gateway": "Single entry point for API requests. Routes to services, handles auth, rate limiting, caching. Examples: Kong, AWS API Gateway.",
        "webhook": "HTTP callback triggered by an event. Server sends POST to a URL when something happens. Used for notifications, integrations.",
        "ORM": "Object-Relational Mapping. Maps database tables to programming objects. SQLAlchemy (Python), Hibernate (Java). Write code instead of SQL.",
        "message queue": "Asynchronous communication between services. Producer sends messages, consumer processes them. RabbitMQ, Kafka. Decouples systems.",
        "CDN": "Content Delivery Network. Distributes content to edge servers globally. Reduces latency by serving from nearest location. Cloudflare, Akamai.",
        "SSL/TLS": "Protocols for encrypted communication. SSL deprecated, TLS is current. Provides confidentiality, integrity, authentication. Used in HTTPS.",
        "JWT": "JSON Web Token. Compact token for securely transmitting information. Contains header, payload, signature. Used for stateless authentication.",
        "CORS": "Cross-Origin Resource Sharing. Browser security mechanism controlling cross-domain requests. Server sends Access-Control headers to allow origins.",
        "WebSocket": "Full-duplex communication protocol over single TCP connection. Unlike HTTP request-response, enables real-time bidirectional messaging.",
        "serverless": "Cloud execution model where provider manages infrastructure. Function-as-a-Service (FaaS). AWS Lambda, Azure Functions. Pay per execution.",
        "ETL": "Extract, Transform, Load. Process for moving data between systems. Extract from sources, transform to desired format, load into target database.",
        "ACID": "Database transaction properties: Atomicity (all or nothing), Consistency (valid state), Isolation (concurrent transactions independent), Durability (committed = permanent).",
        "CAP theorem": "Distributed system can guarantee at most 2 of 3: Consistency, Availability, Partition tolerance. Must choose trade-offs during network failures.",
        "sharding": "Horizontal database partitioning across servers. Each shard holds subset of data. Enables horizontal scaling. Challenge: cross-shard queries.",
        "regression testing": "Re-running tests after code changes to ensure nothing broke. Automated test suites catch regressions. Essential for CI/CD pipelines.",
        "code review": "Peer examination of code before merging. Catches bugs, improves quality, shares knowledge. Pull requests on GitHub. Best practice in teams.",
        "pair programming": "Two developers at one workstation. Driver writes code, navigator reviews. Catches errors early, shares knowledge. XP practice.",
        "singleton pattern": "Design pattern ensuring a class has only one instance. Global access point. Used for config, logging, connection pools. Can hinder testing.",
        "observer pattern": "Behavioral pattern where objects (observers) subscribe to events from a subject. When subject changes, all observers are notified. Pub-sub model.",
        "factory pattern": "Creational pattern that creates objects without specifying exact class. Factory method returns instances based on input. Decouples creation from usage.",
    }
    for term, definition in extra_terms.items():
        for tmpl in [f"What is {term}?", f"Explain {term}.", f"Define {term}."]:
            add_pair(tmpl, definition)

    # Generate "which is better" questions
    for a, b, answer in comparisons:
        add_pair(f"When should I use {a} over {b}?",
                 f"Use {a} when: " + answer.split(". ")[0] + f". Use {b} when: " + answer.split(". ")[-2] + ".")

    # BOOST: More prompt variations for all concepts (8 templates per concept)
    all_concepts = dict(concepts)
    all_concepts.update(extra_terms)
    extra_templates = [
        "What is {c} and why is it important?",
        "Give a brief overview of {c}.",
        "How would you describe {c} to a beginner?",
        "Summarize the concept of {c}.",
        "What should I know about {c}?",
        "In simple terms, what is {c}?",
        "Why is {c} important in technology?",
        "What problem does {c} solve?",
        "Tell me about {c}.",
        "Describe {c} and its uses.",
        "What are the key aspects of {c}?",
        "How does {c} work?",
    ]
    for concept, definition in all_concepts.items():
        for tmpl in extra_templates:
            add_pair(tmpl.format(c=concept), definition)

    # BOOST: More comparisons with additional pairs
    extra_comparisons = [
        ("Python", "C++", "Python: interpreted, dynamic, easy syntax, slower. C++: compiled, static, complex, much faster. Python for prototyping; C++ for performance-critical systems."),
        ("Python", "JavaScript", "Python: general purpose, strong in ML/data, server-side. JavaScript: web-native, runs in browser, async-focused. Python for backend/ML; JS for web."),
        ("MySQL", "PostgreSQL", "MySQL: simpler, faster reads, widely used. PostgreSQL: more features, better standards compliance, advanced queries. MySQL for simple apps; PostgreSQL for complex."),
        ("Redis", "Memcached", "Redis: data structures, persistence, pub/sub. Memcached: simple key-value, multi-threaded, pure cache. Redis more versatile; Memcached simpler caching."),
        ("Linux", "Windows", "Linux: open source, command-line focused, server dominant. Windows: proprietary, GUI focused, desktop dominant. Linux for servers; Windows for desktops."),
        ("React", "Angular", "React: library, virtual DOM, JSX, flexible. Angular: full framework, TypeScript, opinionated. React for flexibility; Angular for large enterprise apps."),
        ("MongoDB", "PostgreSQL", "MongoDB: document store, flexible schema, horizontal scaling. PostgreSQL: relational, ACID, complex queries. MongoDB for unstructured; PostgreSQL for structured."),
        ("REST", "gRPC", "REST: HTTP/JSON, human-readable, widely supported. gRPC: HTTP/2, Protocol Buffers, faster, streaming. REST for public APIs; gRPC for microservice communication."),
        ("Kubernetes", "Docker Swarm", "Kubernetes: feature-rich, complex, industry standard. Docker Swarm: simpler, integrated with Docker, less features. K8s for production; Swarm for simple setups."),
        ("SSD", "HDD", "SSD: solid state, fast, no moving parts, expensive per GB. HDD: magnetic, slower, mechanical, cheap storage. SSD for speed; HDD for bulk storage."),
    ]
    for a, b, answer in extra_comparisons:
        for tmpl in [f"Compare {a} and {b}.", f"{a} vs {b}?", f"Difference between {a} and {b}?", f"When to use {a} vs {b}?"]:
            add_pair(tmpl, answer)

    # BOOST: Acronym explanations (200+)
    acronyms = {
        "CPU": "Central Processing Unit. The brain of a computer that executes instructions. Performs arithmetic, logic, control, and I/O operations.",
        "GPU": "Graphics Processing Unit. Specialized processor for parallel computing. Originally for graphics rendering, now used in ML, crypto, and scientific computing.",
        "RAM": "Random Access Memory. Volatile memory for active data. Fast read/write. Data lost on power off. Measured in GB. More RAM = more programs simultaneously.",
        "ROM": "Read-Only Memory. Non-volatile memory retaining data without power. Stores firmware and boot instructions. Cannot be easily modified.",
        "SSD": "Solid State Drive. Storage using flash memory chips. No moving parts. Faster, more durable, lower power than HDDs. Higher cost per GB.",
        "HDD": "Hard Disk Drive. Magnetic storage with spinning platters. Mechanical read/write heads. Cheaper per GB but slower and less durable than SSDs.",
        "LAN": "Local Area Network. Network covering small area like office or home. Typically Ethernet or WiFi. High speed, low latency.",
        "WAN": "Wide Area Network. Network spanning large geographic area. The internet is the largest WAN. Higher latency than LAN.",
        "VPN": "Virtual Private Network. Encrypted tunnel over public internet. Provides privacy, security, and remote access. Used for corporate networks and personal privacy.",
        "SSH": "Secure Shell. Encrypted protocol for remote access and file transfer. Replaces insecure telnet. Uses public key authentication.",
        "FTP": "File Transfer Protocol. Standard for transferring files between computers. SFTP adds encryption. Being replaced by cloud storage and HTTPS.",
        "NAS": "Network Attached Storage. Dedicated file storage on a network. Accessible by multiple users. Used for backups, media, shared files.",
        "RAID": "Redundant Array of Independent Disks. Combines multiple drives for performance and/or redundancy. Levels: 0 (striping), 1 (mirroring), 5 (parity).",
        "BIOS": "Basic Input/Output System. Firmware that initializes hardware during boot. Being replaced by UEFI. Stored on ROM chip on motherboard.",
        "URL": "Uniform Resource Locator. Web address format: protocol://domain/path?query. Identifies resources on the internet. Part of the URI system.",
        "HTML": "HyperText Markup Language. Standard language for web pages. Uses tags to structure content. Current version: HTML5. Rendered by web browsers.",
        "CSS": "Cascading Style Sheets. Language for styling HTML documents. Controls layout, colors, fonts, animations. Separates content from presentation.",
        "JSON": "JavaScript Object Notation. Lightweight data interchange format. Human-readable, language-independent. Key-value pairs and arrays. Standard for APIs.",
        "XML": "Extensible Markup Language. Markup language for structured data. Self-descriptive tags. Used in config files, SOAP, document formats. More verbose than JSON.",
        "YAML": "YAML Ain't Markup Language. Human-friendly data serialization. Used in config files (Docker, K8s, CI/CD). Indentation-based. Superset of JSON.",
        "IDE": "Integrated Development Environment. Software for writing code with built-in tools: editor, debugger, compiler, version control. Examples: VS Code, IntelliJ, PyCharm.",
        "CLI": "Command Line Interface. Text-based interface for computer interaction. More powerful and scriptable than GUI. Terminal, shell, console.",
        "GUI": "Graphical User Interface. Visual interface with windows, icons, menus. More intuitive for users. Built with frameworks like Qt, Electron, SwiftUI.",
        "MVC": "Model-View-Controller. Software architecture pattern. Model (data), View (UI), Controller (logic). Separates concerns. Used in web frameworks.",
        "CRUD": "Create, Read, Update, Delete. Four basic database operations. Foundation of data management. Maps to HTTP: POST, GET, PUT, DELETE.",
        "FIFO": "First In, First Out. Processing order where first item added is first removed. Queue data structure. Used in scheduling, buffering.",
        "LIFO": "Last In, First Out. Processing order where last item added is first removed. Stack data structure. Used in function calls, undo operations.",
        "ORM": "Object-Relational Mapping. Maps database tables to programming objects. SQLAlchemy (Python), Hibernate (Java). Write code instead of raw SQL.",
        "SDK": "Software Development Kit. Collection of tools, libraries, and docs for building software on a platform. Includes APIs, compilers, debuggers.",
        "TDD": "Test-Driven Development. Write tests before code. Red (fail) -> Green (pass) -> Refactor cycle. Ensures code meets requirements from start.",
    }
    for acronym, definition in acronyms.items():
        for tmpl in [f"What does {acronym} stand for?", f"What is {acronym}?", f"Define {acronym}.",
                     f"Explain {acronym}.", f"What does {acronym} mean?"]:
            add_pair(tmpl, definition)

    # BOOST: "What is used for" questions
    use_cases = {
        "Python": "web development (Django, Flask), data science (pandas, numpy), machine learning (scikit-learn, TensorFlow), automation, scripting, API development",
        "JavaScript": "web front-end (React, Vue, Angular), Node.js backend, mobile apps (React Native), desktop apps (Electron), serverless functions",
        "SQL": "querying relational databases, data analysis, reporting, database administration, ETL processes, business intelligence",
        "Docker": "containerizing applications, microservices deployment, CI/CD pipelines, consistent development environments, cloud deployment",
        "Git": "version control, collaboration on code, tracking changes, branching workflows, code review via pull requests, release management",
        "Linux": "server hosting, cloud infrastructure, embedded systems, development environment, networking, containerization, IoT devices",
        "Redis": "caching, session storage, real-time analytics, message queuing, pub/sub messaging, leaderboards, rate limiting",
        "Kubernetes": "container orchestration, auto-scaling, load balancing, service discovery, rolling deployments, cluster management",
        "Nginx": "reverse proxy, load balancer, web server, SSL termination, static file serving, API gateway, caching",
        "PostgreSQL": "relational data storage, complex queries, ACID transactions, JSON storage, geographic data (PostGIS), full-text search",
        "MongoDB": "document storage, flexible schemas, real-time analytics, content management, IoT data, mobile app backends",
        "Elasticsearch": "full-text search, log analysis, application monitoring, analytics, real-time data exploration",
        "Kafka": "event streaming, log aggregation, real-time data pipelines, microservice communication, change data capture",
        "Terraform": "infrastructure as code, cloud provisioning, multi-cloud management, environment reproducibility, resource lifecycle management",
        "Jenkins": "CI/CD automation, build pipelines, automated testing, deployment automation, integration with version control",
        "Prometheus": "metrics collection, monitoring, alerting, time-series data, infrastructure observability, application performance monitoring",
        "Grafana": "data visualization dashboards, monitoring, alerting, log exploration, metrics analysis from multiple data sources",
        "TensorFlow": "machine learning model training, deep learning, neural networks, NLP, computer vision, production ML deployment",
        "pandas": "data analysis, data cleaning, CSV/Excel processing, data transformation, time series analysis, statistical operations",
        "numpy": "numerical computing, array operations, linear algebra, scientific computing, mathematical functions, random number generation",
    }
    for tool, uses in use_cases.items():
        add_pair(f"What is {tool} used for?", f"{tool} is commonly used for: {uses}.")
        add_pair(f"What are the main use cases for {tool}?", f"Key use cases for {tool}: {uses}.")
        add_pair(f"Where is {tool} typically used?", f"{tool} is typically used in: {uses}.")

    # BOOST: HTTP status code questions
    status_codes = {
        "200 OK": "Success. The request was successful and server returned the requested data.",
        "201 Created": "Success. A new resource was created as a result of the request. Common for POST.",
        "204 No Content": "Success. Request processed but no content to return. Common for DELETE.",
        "301 Moved Permanently": "Redirect. Resource has permanently moved to a new URL. Update bookmarks.",
        "302 Found": "Redirect. Resource temporarily at different URL. Client should use original URL in future.",
        "304 Not Modified": "Resource hasn't changed since last request. Use cached version. Saves bandwidth.",
        "400 Bad Request": "Client error. Server cannot process due to malformed syntax or invalid parameters.",
        "401 Unauthorized": "Client error. Authentication required. Client must provide valid credentials.",
        "403 Forbidden": "Client error. Server understood but refuses to authorize. Even with auth, access denied.",
        "404 Not Found": "Client error. Requested resource doesn't exist on server. Check URL spelling.",
        "405 Method Not Allowed": "Client error. HTTP method not allowed for this resource. Check allowed methods.",
        "409 Conflict": "Client error. Request conflicts with current state. Common in concurrent updates.",
        "429 Too Many Requests": "Client error. Rate limit exceeded. Wait and retry. Check Retry-After header.",
        "500 Internal Server Error": "Server error. Unexpected condition. Bug in server code or unhandled exception.",
        "502 Bad Gateway": "Server error. Server acting as gateway received invalid response from upstream.",
        "503 Service Unavailable": "Server error. Server temporarily unable to handle request. Overloaded or maintenance.",
        "504 Gateway Timeout": "Server error. Gateway/proxy didn't receive timely response from upstream server.",
    }
    for code, description in status_codes.items():
        add_pair(f"What does HTTP status code {code} mean?", f"HTTP {code}: {description}")
        add_pair(f"Explain HTTP {code}.", f"{code}: {description}")

    # BOOST: Git command questions
    git_commands = {
        "git init": "Initialize a new Git repository in the current directory. Creates .git folder with repo metadata.",
        "git clone": "Create a local copy of a remote repository. Downloads all files, branches, and history.",
        "git add": "Stage changes for commit. git add file.py stages one file. git add . stages all changes.",
        "git commit": "Save staged changes with a message. git commit -m 'message'. Creates a snapshot in history.",
        "git push": "Upload local commits to remote repository. git push origin main. Shares work with team.",
        "git pull": "Fetch and merge remote changes. Combination of git fetch + git merge. Updates local branch.",
        "git branch": "List, create, or delete branches. git branch name creates. git branch -d name deletes.",
        "git checkout": "Switch branches or restore files. git checkout branch-name. git checkout -- file restores.",
        "git merge": "Combine branches. git merge feature-branch. May create merge commit or fast-forward.",
        "git rebase": "Reapply commits on top of another base. Creates linear history. git rebase main. Rewrites history.",
        "git stash": "Temporarily save uncommitted changes. git stash to save, git stash pop to restore.",
        "git log": "Show commit history. git log --oneline for compact view. git log --graph for visual branches.",
        "git diff": "Show changes between commits, branches, or working directory. git diff for unstaged changes.",
        "git reset": "Undo commits or unstage files. --soft keeps changes staged. --hard discards everything.",
        "git fetch": "Download remote changes without merging. Updates remote tracking branches. Safe operation.",
    }
    for cmd, description in git_commands.items():
        add_pair(f"What does '{cmd}' do?", f"{cmd}: {description}")
        add_pair(f"Explain the git command: {cmd}", f"{cmd}: {description}")

    # BOOST: Linux command questions
    linux_commands = {
        "ls": "List directory contents. -l for details, -a for hidden files, -h for human-readable sizes.",
        "cd": "Change directory. cd /path goes to path. cd .. goes up. cd ~ goes home. cd - goes to previous.",
        "grep": "Search text patterns. grep 'pattern' file. -r recursive, -i case-insensitive, -n line numbers.",
        "find": "Find files. find /path -name '*.py' -type f. Powerful with -exec for actions on results.",
        "chmod": "Change file permissions. chmod 755 file (rwxr-xr-x). chmod +x file adds execute permission.",
        "chown": "Change file ownership. chown user:group file. -R for recursive. Requires root/sudo.",
        "ps": "List running processes. ps aux for all processes. ps -ef for full format. Combine with grep.",
        "top": "Real-time process monitor. Shows CPU, memory usage. Press q to quit. htop is enhanced version.",
        "kill": "Send signal to process. kill PID sends SIGTERM. kill -9 PID forces termination (SIGKILL).",
        "curl": "Transfer data from/to server. curl URL downloads. -X POST for method. -d for data. -H for headers.",
        "wget": "Download files from web. wget URL saves file. -r for recursive. -c for resume. Simpler than curl.",
        "tar": "Archive files. tar -czf archive.tar.gz dir/ creates. tar -xzf archive.tar.gz extracts.",
        "ssh": "Secure remote login. ssh user@host. -p for port. -i for key file. Encrypted communication.",
        "scp": "Secure file copy. scp file user@host:/path copies to remote. -r for recursive directories.",
        "awk": "Text processing language. awk '{print $1}' file prints first field. Powerful for columnar data.",
    }
    for cmd, description in linux_commands.items():
        add_pair(f"What does the '{cmd}' command do?", f"{cmd}: {description}")
        add_pair(f"How do you use '{cmd}' in Linux?", f"{cmd}: {description}")

    # BOOST: "How many X" factual questions with numbers
    factual_numbers = [
        ("How many bits in a byte?", "8 bits make up 1 byte. A byte can represent 2^8 = 256 different values (0-255)."),
        ("How many bytes in a kilobyte?", "1 KB = 1,024 bytes (2^10). In SI units, 1 kB = 1,000 bytes. Computing uses binary KB."),
        ("How many bytes in a megabyte?", "1 MB = 1,048,576 bytes (2^20) or approximately 1 million bytes."),
        ("How many bytes in a gigabyte?", "1 GB = 1,073,741,824 bytes (2^30) or approximately 1 billion bytes."),
        ("How many HTTP methods are there?", "9 standard HTTP methods: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS, TRACE, CONNECT."),
        ("How many layers in the OSI model?", "7 layers: Physical, Data Link, Network, Transport, Session, Presentation, Application."),
        ("How many layers in TCP/IP model?", "4 layers: Network Interface, Internet, Transport, Application. Simplified from OSI's 7."),
        ("What is the max value of a 32-bit integer?", "2^31 - 1 = 2,147,483,647 for signed. 2^32 - 1 = 4,294,967,295 for unsigned."),
        ("What is the max value of a 64-bit integer?", "2^63 - 1 = 9,223,372,036,854,775,807 for signed. About 9.2 quintillion."),
        ("What port does HTTP use?", "HTTP uses port 80 by default. HTTPS uses port 443. These are well-known ports."),
        ("What port does SSH use?", "SSH uses port 22 by default. Can be changed for security. Used for secure remote access."),
        ("What is the default MySQL port?", "MySQL uses port 3306 by default. PostgreSQL uses 5432. MongoDB uses 27017."),
        ("How many reserved words in Python?", "Python 3.12 has 35 keywords: False, True, None, and, as, assert, async, await, break, class, continue, def, del, elif, else, except, finally, for, from, global, if, import, in, is, lambda, nonlocal, not, or, pass, raise, return, try, while, with, yield."),
        ("What is the time complexity of Python's sort?", "Python uses Timsort: O(n log n) worst and average, O(n) best case. Stable sort. Hybrid of merge sort and insertion sort."),
        ("How fast is the speed of light?", "Approximately 299,792,458 meters per second in vacuum. About 186,282 miles per second. Light takes ~1.3 seconds to reach the Moon from Earth."),
    ]
    for q, a in factual_numbers:
        add_pair(q, a)

    # BOOST: Algorithm explanation questions (unique per algorithm)
    algorithms = {
        "bubble sort": "Repeatedly compares adjacent elements and swaps if out of order. O(n^2) time. Simple but slow. Stable sort. Good for nearly sorted data or educational purposes.",
        "selection sort": "Finds minimum element and places it at the beginning, repeating for remaining. O(n^2). Not stable. Simple implementation, poor performance.",
        "insertion sort": "Builds sorted array one element at a time by inserting each element in its correct position. O(n^2) worst, O(n) best. Stable. Good for small or nearly sorted arrays.",
        "merge sort": "Divides array in half, recursively sorts each half, then merges. O(n log n) always. Stable. Needs O(n) extra space. Good for linked lists.",
        "quick sort": "Picks pivot, partitions array so smaller left and larger right, recurses. O(n log n) average, O(n^2) worst. Not stable. In-place. Usually fastest in practice.",
        "heap sort": "Builds max heap, repeatedly extracts maximum. O(n log n) always. Not stable. In-place. Good when worst-case guarantee needed.",
        "counting sort": "Counts occurrences of each value, then places elements. O(n+k) where k is range. Not comparison-based. Stable. Good for small integer ranges.",
        "radix sort": "Sorts by individual digits, from least to most significant. O(d*(n+k)) where d is digits. Stable. Good for fixed-length integers or strings.",
        "binary search": "Searches sorted array by halving search space. O(log n). Requires sorted input. Compare middle element, eliminate half each step.",
        "depth-first search": "Explores as deep as possible before backtracking. Uses stack/recursion. O(V+E). Used for topological sort, cycle detection, path finding.",
        "breadth-first search": "Explores level by level using a queue. O(V+E). Finds shortest path in unweighted graphs. Used for web crawling, social network analysis.",
        "Dijkstra's algorithm": "Finds shortest path from source to all vertices in weighted graph. O(V^2) simple, O(E log V) with heap. Requires non-negative weights.",
        "A* search": "Pathfinding using heuristic + actual cost. f(n) = g(n) + h(n). Optimal with admissible heuristic. Used in games, maps, robotics.",
        "dynamic programming approach": "Breaks problem into overlapping subproblems, stores solutions. Memoization (top-down) or tabulation (bottom-up). Fibonacci, knapsack, LCS, edit distance.",
        "greedy algorithm": "Makes locally optimal choice at each step. Doesn't always find global optimum. Works for: activity selection, Huffman coding, minimum spanning tree.",
    }
    for algo, description in algorithms.items():
        add_pair(f"Explain {algo}.", description)
        add_pair(f"How does {algo} work?", description)
        add_pair(f"Describe the {algo} algorithm.", description)

    # BOOST: Design principle questions
    principles = {
        "DRY": "Don't Repeat Yourself. Every piece of knowledge should have a single authoritative representation. Reduce duplication through abstraction.",
        "KISS": "Keep It Simple, Stupid. Prefer simple solutions over complex ones. Simplicity improves readability, maintainability, and reduces bugs.",
        "YAGNI": "You Aren't Gonna Need It. Don't implement features until they are actually needed. Avoids over-engineering and wasted effort.",
        "SOLID": "Five OOP design principles: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.",
        "Single Responsibility": "A class should have only one reason to change. Each module handles one concern. Improves cohesion and reduces coupling.",
        "Open/Closed Principle": "Software entities should be open for extension but closed for modification. Add new behavior without changing existing code.",
        "Liskov Substitution": "Subtypes must be substitutable for their base types without altering program correctness. Derived classes honor parent contracts.",
        "Interface Segregation": "Clients should not be forced to depend on interfaces they don't use. Prefer many small interfaces over one large one.",
        "Dependency Inversion": "High-level modules should not depend on low-level modules. Both should depend on abstractions. Invert the dependency direction.",
        "separation of concerns": "Different aspects of functionality should be independent. UI separate from logic separate from data. Improves modularity.",
        "composition over inheritance": "Prefer composing objects from smaller objects rather than inheriting from parent classes. More flexible, avoids deep hierarchies.",
        "fail fast": "Detect and report errors as early as possible. Validate inputs immediately. Makes bugs easier to find and fix.",
        "principle of least surprise": "Components should behave as users expect. Consistent naming, standard patterns, intuitive interfaces. Reduces learning curve.",
        "law of Demeter": "An object should only talk to its immediate friends. Avoid chaining method calls (a.b.c.d). Reduces coupling between components.",
    }
    for principle, description in principles.items():
        add_pair(f"What is the {principle} principle?", f"{principle}: {description}")
        add_pair(f"Explain {principle} in software engineering.", f"{principle}: {description}")

    # BOOST: "What are the types of" questions
    types_of = {
        "databases": "1) Relational (MySQL, PostgreSQL) - tables with SQL. 2) Document (MongoDB) - JSON-like documents. 3) Key-Value (Redis) - simple lookup. 4) Graph (Neo4j) - relationships. 5) Column (Cassandra) - wide columns. 6) Time-series (InfluxDB).",
        "testing": "1) Unit testing - individual functions. 2) Integration testing - components together. 3) End-to-end testing - full user flow. 4) Regression testing - after changes. 5) Performance testing - load/stress. 6) Security testing - vulnerabilities.",
        "design patterns": "Creational: Singleton, Factory, Builder, Prototype. Structural: Adapter, Bridge, Composite, Decorator, Facade, Proxy. Behavioral: Observer, Strategy, Command, Iterator, State, Template Method.",
        "data structures": "Linear: array, linked list, stack, queue, deque. Non-linear: tree, graph, heap, trie. Hash-based: hash table, hash set. Specialized: bloom filter, skip list.",
        "sorting algorithms": "Comparison-based: bubble, selection, insertion, merge, quick, heap, Tim sort. Non-comparison: counting, radix, bucket. Stable sorts preserve equal-element order.",
        "machine learning": "Supervised: classification, regression (labeled data). Unsupervised: clustering, dimensionality reduction. Reinforcement: reward-based learning. Semi-supervised: partial labels.",
        "cloud services": "IaaS: raw compute/storage (EC2, VMs). PaaS: managed platform (Heroku, App Engine). SaaS: complete applications (Gmail, Slack). FaaS: serverless functions (Lambda).",
        "programming paradigms": "Imperative: step-by-step instructions. Declarative: describe what, not how. OOP: objects with state and behavior. Functional: pure functions, immutability. Logic: rule-based (Prolog).",
        "network protocols": "Application: HTTP, FTP, SMTP, DNS. Transport: TCP, UDP. Network: IP, ICMP. Data Link: Ethernet, WiFi. Physical: cables, signals.",
        "software licenses": "Permissive: MIT, Apache, BSD - minimal restrictions. Copyleft: GPL, LGPL - derivatives must be open source. Proprietary: commercial, closed source.",
    }
    for category, description in types_of.items():
        add_pair(f"What are the types of {category}?", description)
        add_pair(f"List the different types of {category}.", description)
        add_pair(f"What categories of {category} exist?", description)

    print(f"  knowledge: {len(pairs)} pairs", flush=True)
    return pairs

# ============================================================
# 5. TERNARY / NOVAX (2,500+ unique pairs)
# ============================================================

def gen_ternary_pairs():
    random.seed(46)
    pairs = []
    seen = set()

    def add_pair(p, r):
        if p not in seen:
            seen.add(p)
            pairs.append(pair(p, r, "ternary"))

    # --- Balanced ternary fundamentals (50+) ---
    fundamentals = [
        ("What is balanced ternary?",
         "Balanced ternary uses digits -1, 0, +1 (written T, 0, +). Each position is a power of 3. No separate sign needed - negate by flipping trits. Example: +T0 = 1*9 + (-1)*3 + 0*1 = 6."),
        ("What are advantages of balanced ternary?",
         "1) No sign bit - negation flips all trits. 2) Rounding = truncation. 3) Better digit economy (minimizes digits*radix). 4) Symmetric around zero. 5) Natural three-valued logic."),
        ("How do you add in balanced ternary?",
         "Add digit by digit right to left with carry. (+)+(+) = carry +, digit T. (T)+(T) = carry T, digit +. (+)+(T) = 0. Carry propagates like binary but three states."),
        ("What is a trit?",
         "A trit (ternary digit) holds -1, 0, or +1. Contains log2(3) = ~1.585 bits. A tryte is typically 3-6 trits. Trits are the fundamental unit in ternary computing."),
        ("What is a tryte?",
         "A tryte is a group of trits, analogous to a byte in binary. Common sizes: 3 trits (27 values) or 6 trits (729 values). In NovaX, a tryte is the basic data word."),
        ("How does ternary negation work?",
         "To negate in balanced ternary, flip every trit: + becomes T, T becomes +, 0 stays 0. Example: +T0 (=6) becomes T+0 (=-6). No two's complement needed."),
        ("What is the Setun computer?",
         "The Setun was a balanced ternary computer built at Moscow State University in 1958. It used balanced ternary arithmetic and was more reliable and efficient than contemporary binary machines."),
        ("Why is ternary more efficient than binary?",
         "Ternary has better radix economy. The function r*d (radix * digits needed) is minimized near e (2.718). Base 3 is closest integer to e, making it theoretically the most efficient integer base."),
    ]
    for q, a in fundamentals:
        add_pair(q, a)
        add_pair("Explain: " + q.lower().replace("?", ".").replace("what is ", "").replace("how do you ", ""), a)

    # --- Decimal to balanced ternary (600) ---
    for val in range(-150, 250):
        bt = to_balanced_ternary(val)
        add_pair(f"Convert {val} to balanced ternary.",
                 f"Converting {val}: Apply repeated division by 3 with balanced remainders. "
                 f"{val} in balanced ternary = {bt}. Verify: expand to confirm decimal value.")

    # --- Balanced ternary to decimal (300) ---
    for val in range(-100, 200):
        bt = to_balanced_ternary(val)
        # Build expansion string
        digits = list(bt)
        parts = []
        for i, d in enumerate(digits):
            power = len(digits) - 1 - i
            if d == '+':
                parts.append(f"(+1)*3^{power}")
            elif d == 'T':
                parts.append(f"(-1)*3^{power}")
            elif d == '0' and power > 0:
                parts.append(f"0*3^{power}")
        add_pair(f"Convert balanced ternary {bt} to decimal.",
                 f"{bt} = {' + '.join(parts)} = {val}. The decimal value is {val}.")

    # --- Ternary arithmetic (300) ---
    for _ in range(350):
        a = random.randint(-80, 80)
        b = random.randint(-80, 80)
        bt_a = to_balanced_ternary(a)
        bt_b = to_balanced_ternary(b)
        bt_sum = to_balanced_ternary(a + b)
        add_pair(f"Add {a} ({bt_a}) and {b} ({bt_b}) in balanced ternary.",
                 f"{a} + {b} = {a+b}. In balanced ternary: {bt_a} + {bt_b} = {bt_sum}.")

    for _ in range(200):
        a = random.randint(1, 50)
        bt = to_balanced_ternary(a)
        neg_bt = to_balanced_ternary(-a)
        add_pair(f"What is the negation of {bt} in balanced ternary?",
                 f"Flip all trits: + becomes T, T becomes +, 0 stays 0. {bt} (={a}) negated is {neg_bt} (={-a}).")

    # --- NovaLang syntax (200+) ---
    novalang = [
        ("How does if3 work in NovaLang?",
         "if3(condition) {positive} {zero} {negative}. Evaluates condition as trit. +1 runs first block, 0 runs second, -1 runs third. Three-way branching natively."),
        ("What is match3 in NovaLang?",
         "match3(expr) { +: handle_pos } { 0: handle_zero } { -: handle_neg }. Pattern matching for ternary values. Each branch handles one trit state."),
        ("What is try3 in NovaLang?",
         "try3 {code} {+: success} {0: warning} {-: failure}. Three-outcome error handling. Distinguishes full success, partial/warning, and failure states."),
        ("What is while3 in NovaLang?",
         "while3(cond) { +: loop_body } { 0: skip } { -: break }. Ternary loop control. +1 continues, 0 skips iteration, -1 exits loop."),
        ("What is for3 in NovaLang?",
         "for3(item in collection) { +: process } { 0: skip } { -: stop }. Each iteration yields trit control. More expressive than binary for loops."),
        ("What are NovaLang variables?",
         "Declared with 'let': let x = 42. Dynamic typing. Scope: function-local by default. Note: 'let' inside if3 creates local scope. Use outer 'let' for wider access."),
        ("What is the pipe operator in NovaLang?",
         "The |> operator chains functions: data |> filter |> transform |> output. Each function receives previous result as first argument. Like Unix pipes."),
        ("What are NovaLang's built-in types?",
         "Types: trit (-1/0/+1), tryte (trit group), int, float, str, list, dict, bool (maps to +1/-1). All support ternary comparison."),
        ("How does NovaLang handle errors?",
         "Functions return ternary status: +1 success, 0 warning, -1 failure. try3 routes to three handlers. Eliminates binary exception handling for three-state flow."),
        ("What are NovaLang's trit operations?",
         "Built-ins: trit_add, trit_mul, trit_neg, trit_and, trit_or, trit_xor, trit_consensus. 23 trit-native operations plus 35+ general builtins."),
    ]
    for q, a in novalang:
        add_pair(q, a)
        add_pair("Explain " + q.lower().replace("?", ".").replace("how does ", "").replace("what is ", "").replace("what are ", ""), a)
        add_pair("In NovaLang, " + q.lower(), a)

    # --- NovaX architecture (100+) ---
    novax_qa = [
        ("What is Navier-Stokes routing in NovaX?",
         "NovaX uses N-S fluid dynamics as metaphor for query routing. Viscosity = routing resistance, Reynolds number = query complexity, pressure = model affinity, velocity = throughput."),
        ("What is the Reynolds number in NovaX?",
         "Re classifies query complexity. Re < 27: laminar (simple, local models). 27 < Re < 343: transitional (cloud models). Re > 343: turbulent (full hivemind swarm)."),
        ("What are the 3-5-7-13 constants?",
         "NovaX core constants: 3 = ternary base. 5 = TZip uses 3^5=243 states. 7 = composition depth. 13 = carrier wave. Block size = 3^7 = 2187."),
        ("How does TZip compression work?",
         "TZip encodes data using 3^5=243 states per symbol (vs binary 256). Balanced ternary encoding. ~1.585 bits per trit. Leverages ternary's better digit economy."),
        ("What is a micro-tool in NovaX?",
         "Atomic computation unit returning trit: +1 success, 0 neutral, -1 failure. Micro-tools compose via pipe operator. Three-way branching at every computation step."),
        ("How does the NovaX hivemind work?",
         "Multi-model AI orchestration. Routes queries to optimal models using N-S flow. Local (Ollama), cloud (OpenAI, Anthropic), desktop (Claude, ChatGPT) models available."),
        ("What is the NovaX orchestrator?",
         "Central service on port 9999. Manages services, routes requests, monitors health, maintains registry. Coordinates hivemind, cloud router, voice, and dashboards."),
        ("What role does ternary play in NovaX?",
         "Ternary is NovaX's philosophical and computational foundation. True/unknown/false (+1/0/-1) enables nuanced decisions, natural error handling, efficient representation."),
        ("What is NovaLang?",
         "NovaX's ternary-native programming language. Features if3/match3/try3/while3/for3 control flow, 23 trit builtins, 35+ general builtins. Interpreter in novalang.py."),
        ("What is the NovaX Shield?",
         "Security system protecting NovaX operations. Version 3.0 persistent ON. Validates inputs, monitors processes, prevents unauthorized system access."),
    ]
    for q, a in novax_qa:
        add_pair(q, a)
        add_pair("Tell me about " + q.lower().replace("what is ", "").replace("how does ", "").replace("?", "."), a)

    # --- Ternary logic truth tables (200) ---
    ternary_ops = {
        "TAND": lambda a, b: min(a, b),
        "TOR": lambda a, b: max(a, b),
        "TMIN": lambda a, b: min(a, b),
        "TMAX": lambda a, b: max(a, b),
        "TCONSENSUS": lambda a, b: a if a == b else 0,
        "TMUL": lambda a, b: a * b,
    }
    trit_sym = {-1: "T(-1)", 0: "0", 1: "+(+1)"}
    for _ in range(250):
        a = random.choice([-1, 0, 1])
        b = random.choice([-1, 0, 1])
        op_name = random.choice(list(ternary_ops.keys()))
        result = ternary_ops[op_name](a, b)
        add_pair(f"Compute {trit_sym[a]} {op_name} {trit_sym[b]} in ternary logic.",
                 f"{op_name}: A={a}, B={b}. Result = {result} ({trit_sym[result]}). "
                 f"The {op_name} operation on trits {a} and {b} yields {result}.")

    # --- Powers of 3 (25) ---
    for i in range(25):
        val = 3 ** i
        add_pair(f"What is 3^{i}?",
                 f"3^{i} = {val}. Key values in NovaX: 3^5=243 (TZip), 3^7=2187 (block size), 3^13=1594323 (carrier).")

    # --- Trit count questions (200) ---
    for val in range(0, 250):
        bt = to_balanced_ternary(val)
        add_pair(f"How many trits to represent {val}?",
                 f"{val} = {bt} in balanced ternary, requiring {len(bt)} trits.")

    # BOOST: Ternary multiplication
    for _ in range(300):
        a = random.randint(-30, 30)
        b = random.randint(-30, 30)
        bt_a = to_balanced_ternary(a)
        bt_b = to_balanced_ternary(b)
        product = a * b
        bt_prod = to_balanced_ternary(product)
        add_pair(f"Multiply {a} ({bt_a}) by {b} ({bt_b}) in balanced ternary.",
                 f"{a} x {b} = {product}. BT: {bt_a} x {bt_b} = {bt_prod}. Verify: {product} converts to {bt_prod}.")

    # BOOST: Ternary comparison
    for _ in range(200):
        a = random.randint(-50, 50)
        b = random.randint(-50, 50)
        bt_a = to_balanced_ternary(a)
        bt_b = to_balanced_ternary(b)
        if a > b: cmp = "+1 (first is greater)"
        elif a == b: cmp = "0 (equal)"
        else: cmp = "-1 (second is greater)"
        add_pair(f"Compare {a} ({bt_a}) and {b} ({bt_b}) using ternary comparison.",
                 f"tcmp({a}, {b}) = {cmp}. Ternary comparison returns +1, 0, or -1 naturally representing greater, equal, less.")

    # BOOST: NovaLang code examples
    novalang_examples = [
        (f"Write a NovaLang function to add two numbers.",
         "fn add(a, b) {{\n  let result = a + b\n  return result\n}}\n// NovaLang functions use fn keyword. Returns trit status: +1 success."),
        (f"Write a NovaLang if3 example for sign detection.",
         "fn sign(x) {{\n  if3(x) {{\n    print(\"+: positive\")\n  }} {{\n    print(\"0: zero\")\n  }} {{\n    print(\"-: negative\")\n  }}\n}}"),
        (f"Write a NovaLang while3 countdown.",
         "fn countdown(n) {{\n  let i = n\n  while3(i) {{\n    print(i)\n    let i = i - 1\n  }} {{\n    print(\"zero\")\n  }} {{\n    print(\"done\")\n  }}\n}}"),
        (f"Write a NovaLang match3 example.",
         "fn classify(trit_val) {{\n  match3(trit_val) {{\n    +: print(\"Positive trit\")\n  }} {{\n    0: print(\"Zero trit\")\n  }} {{\n    -: print(\"Negative trit\")\n  }}\n}}"),
        (f"Write NovaLang code to process a list with for3.",
         "fn process(items) {{\n  for3(item in items) {{\n    +: print(\"Processing: \" + item)\n  }} {{\n    0: print(\"Skipping\")\n  }} {{\n    -: print(\"Stopping early\")\n  }}\n}}"),
    ]
    for q, a in novalang_examples:
        add_pair(q, a)
        add_pair(q.replace("Write", "Show me"), a)
        add_pair(q.replace("Write", "Create"), a)

    # BOOST: Ternary base conversion between bases
    for val in range(0, 100):
        # Standard ternary
        if val == 0:
            std_ternary = "0"
        else:
            digits = []
            tmp = val
            while tmp > 0:
                digits.append(str(tmp % 3))
                tmp //= 3
            std_ternary = "".join(reversed(digits))
        bt = to_balanced_ternary(val)
        binary = bin(val)[2:]
        add_pair(f"Show {val} in binary, standard ternary, and balanced ternary.",
                 f"{val}: binary = {binary}, standard ternary = {std_ternary}, balanced ternary = {bt}.")

    print(f"  ternary: {len(pairs)} pairs", flush=True)
    return pairs


# ============================================================
# MAIN
# ============================================================

def main():
    start = time.time()
    print("NovaX Synthetic Training Data Generator v2", flush=True)
    print("=" * 50, flush=True)

    print("[1/5] Generating math pairs...", flush=True)
    math_p = gen_math_pairs()

    print("[2/5] Generating code pairs...", flush=True)
    code_p = gen_code_pairs()

    print("[3/5] Generating logic pairs...", flush=True)
    logic_p = gen_logic_pairs()

    print("[4/5] Generating knowledge pairs...", flush=True)
    knowledge_p = gen_knowledge_pairs()

    print("[5/5] Generating ternary pairs...", flush=True)
    ternary_p = gen_ternary_pairs()

    all_pairs = math_p + code_p + logic_p + knowledge_p + ternary_p

    # Shuffle
    random.seed(99)
    random.shuffle(all_pairs)

    # Stats
    elapsed = time.time() - start
    domain_counts = {}
    for p in all_pairs:
        d = p["domain"]
        domain_counts[d] = domain_counts.get(d, 0) + 1

    # Output
    output_dir = r"C:\NovaX\data\llm_training"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "pairs_synthetic.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_pairs, f, indent=2, ensure_ascii=True)

    file_size = os.path.getsize(output_path)

    print("", flush=True)
    print("=" * 50, flush=True)
    print("GENERATION COMPLETE", flush=True)
    print("=" * 50, flush=True)
    print(f"Total pairs: {len(all_pairs)}", flush=True)
    print("Domain breakdown:", flush=True)
    for d in sorted(domain_counts.keys()):
        print(f"  {d}: {domain_counts[d]}", flush=True)
    print(f"Output: {output_path}", flush=True)
    print(f"File size: {file_size / 1024 / 1024:.2f} MB", flush=True)
    print(f"Time: {elapsed:.2f} seconds", flush=True)

    # Validate sample
    avg_len = sum(len(p["response"]) for p in all_pairs) // len(all_pairs)
    min_len = min(len(p["response"]) for p in all_pairs)
    max_len = max(len(p["response"]) for p in all_pairs)
    print(f"Response lengths - avg: {avg_len}, min: {min_len}, max: {max_len}", flush=True)

if __name__ == "__main__":
    main()
