"""
NovaX Route Classifier v1.0
Lightweight query classifier that routes to the optimal model/specialist.

Routes queries to 5 categories:
  DIRECT   - Answer from small local model (trivial queries)
  MATH     - Route to math specialist or calculator tool
  CODE     - Route to code specialist
  RETRIEVAL - RAG pipeline first, then answer
  ESCALATE  - Cascade to cloud API (complex/knowledge-heavy)

Phase 1: TF-IDF + keyword-based (zero neural overhead, <1ms)
Phase 2: Embed with small model (when ternary router is trained)

Usage:
    classifier = RouteClassifier()
    route, confidence = classifier.classify("Write a Python function to sort a list")
    # -> ("CODE", 0.92)
"""
import re
import math
from collections import Counter


class RouteClassifier:
    """Lightweight query router — keyword + TF-IDF based."""

    # Route categories
    DIRECT = "DIRECT"
    MATH = "MATH"
    CODE = "CODE"
    RETRIEVAL = "RETRIEVAL"
    ESCALATE = "ESCALATE"

    def __init__(self):
        # Keyword weights per route (curated from 24 research agents)
        self._patterns = {
            self.MATH: {
                "keywords": [
                    "calculate", "compute", "solve", "equation", "integral",
                    "derivative", "matrix", "eigenvalue", "probability",
                    "statistics", "algebra", "geometry", "theorem", "proof",
                    "factorial", "logarithm", "polynomial", "quadratic",
                    "calculus", "trigonometry", "arithmetic", "sum of",
                    "product of", "find x", "how many", "what is the value",
                    "percentage", "fraction", "ratio", "sqrt", "prime",
                ],
                "patterns": [
                    r'\d+\s*[\+\-\*/\^]\s*\d+',  # arithmetic expressions
                    r'x\s*[\+\-\*/\^=]',           # algebraic expressions
                    r'\bsin\b|\bcos\b|\btan\b',     # trig functions
                    r'\blog\b|\bln\b|\bexp\b',      # log/exp
                ],
                "weight": 1.0,
            },
            self.CODE: {
                "keywords": [
                    "code", "function", "implement", "write", "program",
                    "debug", "algorithm", "class", "method", "variable",
                    "compile", "syntax", "error", "bug", "test", "unittest",
                    "python", "javascript", "rust", "java", "c++", "golang",
                    "typescript", "html", "css", "sql", "regex", "api",
                    "database", "server", "client", "framework", "library",
                    "import", "module", "package", "docker", "git",
                    "array", "list", "dict", "hash", "tree", "graph",
                    "sort", "search", "binary", "linked list", "stack",
                    "queue", "heap", "trie", "recursion", "iteration",
                    "refactor", "optimize", "performance", "benchmark",
                ],
                "patterns": [
                    r'```',                         # code blocks
                    r'def\s+\w+',                   # python function
                    r'function\s+\w+',              # js function
                    r'class\s+\w+',                 # class definition
                    r'\w+\.\w+\(',                  # method calls
                    r'import\s+\w+',                # imports
                    r'for\s+\w+\s+in\s+',           # for loops
                ],
                "weight": 1.0,
            },
            self.RETRIEVAL: {
                "keywords": [
                    "who", "when", "where", "what year", "what date",
                    "current", "latest", "recent", "news", "today",
                    "happened", "history", "biography", "born", "died",
                    "founded", "invented", "discovered", "published",
                    "capital of", "population of", "president of",
                    "ceo of", "author of", "director of", "location",
                    "address", "phone", "website", "price", "cost",
                    "weather", "stock", "score", "result", "status",
                    "look up", "search for", "find information",
                ],
                "patterns": [
                    r'who (is|was|are|were)\b',
                    r'when (did|was|is|will)\b',
                    r'where (is|was|are|were)\b',
                    r'what (is|was) the (name|capital|population)',
                    r'how (old|tall|much|many|long|far)',
                ],
                "weight": 0.9,
            },
            self.DIRECT: {
                "keywords": [
                    "hello", "hi", "hey", "thanks", "thank you",
                    "yes", "no", "ok", "okay", "sure", "bye",
                    "good morning", "good night", "how are you",
                    "what can you do", "help", "repeat",
                    "define", "meaning of", "synonym", "antonym",
                    "translate", "spell", "grammar",
                ],
                "patterns": [
                    r'^(hi|hello|hey|thanks|bye|ok)\b',
                    r'^what (is|does) \w+$',  # simple definitions
                ],
                "weight": 1.2,  # slight boost — prefer direct when possible
            },
        }

        # Compile regex patterns
        for route in self._patterns:
            self._patterns[route]["compiled"] = [
                re.compile(p, re.IGNORECASE)
                for p in self._patterns[route]["patterns"]
            ]

    def classify(self, query):
        """Classify a query into a route category.

        Returns:
            (route: str, confidence: float)
            route is one of DIRECT, MATH, CODE, RETRIEVAL, ESCALATE
            confidence is 0.0 to 1.0
        """
        query_lower = query.lower().strip()
        words = set(re.findall(r'\b\w+\b', query_lower))
        scores = {}

        for route, config in self._patterns.items():
            score = 0.0

            # Keyword matching
            keyword_hits = sum(1 for kw in config["keywords"]
                             if kw in query_lower)
            score += keyword_hits * 2.0

            # Pattern matching
            pattern_hits = sum(1 for pat in config["compiled"]
                             if pat.search(query_lower))
            score += pattern_hits * 3.0

            # Apply route weight
            score *= config["weight"]

            scores[route] = score

        # Find best route
        if not scores or max(scores.values()) == 0:
            return self.ESCALATE, 0.3  # default: escalate uncertain queries

        best_route = max(scores, key=scores.get)
        best_score = scores[best_route]

        # Normalize confidence
        total = sum(scores.values()) + 0.001
        confidence = best_score / total

        # If confidence is too low, escalate
        if confidence < 0.4:
            return self.ESCALATE, confidence

        return best_route, min(confidence, 1.0)

    def route_with_cascade(self, query, threshold=0.7):
        """Route with cascade logic for the NovaX swarm.

        Returns a list of (handler, priority) tuples.
        High confidence -> single handler.
        Low confidence -> cascade through multiple.
        """
        route, confidence = self.classify(query)

        if confidence >= threshold:
            # High confidence: single handler
            return [(route, 1.0)]
        elif confidence >= 0.4:
            # Medium confidence: primary + fallback
            return [(route, confidence), (self.ESCALATE, 1.0 - confidence)]
        else:
            # Low confidence: full cascade
            return [
                (self.DIRECT, 0.1),      # try local first (free)
                (self.ESCALATE, 0.9),     # then cloud
            ]

    def batch_classify(self, queries):
        """Classify multiple queries at once."""
        return [self.classify(q) for q in queries]


def test():
    """Test the classifier with example queries."""
    c = RouteClassifier()

    tests = [
        ("Hello, how are you?", "DIRECT"),
        ("What is 2 + 2?", "MATH"),
        ("Solve the integral of sin(x) dx", "MATH"),
        ("Write a Python function to sort a list", "CODE"),
        ("Implement a binary search tree in Rust", "CODE"),
        ("Who invented the telephone?", "RETRIEVAL"),
        ("What is the capital of France?", "RETRIEVAL"),
        ("Explain the implications of quantum computing on cryptography", "ESCALATE"),
        ("Debug this code: def foo(): return bar", "CODE"),
        ("Calculate the eigenvalues of [[3,1],[1,3]]", "MATH"),
        ("Thanks!", "DIRECT"),
        ("What are the philosophical implications of consciousness?", "ESCALATE"),
    ]

    print("Route Classifier Test Results:")
    print("-" * 70)
    correct = 0
    for query, expected in tests:
        route, conf = c.classify(query)
        match = "OK" if route == expected else "XX"
        if route == expected:
            correct += 1
        print(f"  {match} [{route:10s} {conf:.2f}] {query[:50]}")
        if route != expected:
            print(f"    Expected: {expected}")

    print(f"\nAccuracy: {correct}/{len(tests)} ({correct/len(tests)*100:.0f}%)")

    # Test cascade routing
    print(f"\nCascade Routing Examples:")
    for query in ["Hi", "Solve x^2 = 4", "Explain general relativity"]:
        cascade = c.route_with_cascade(query)
        print(f"  '{query}' -> {cascade}")


if __name__ == "__main__":
    test()
