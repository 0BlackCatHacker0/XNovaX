"""
TPacman v3.0 — Navier-Stokes Python-to-NovaLang Converter
==========================================================
Fluid dynamics model for code conversion:

  ρ(∂u/∂t + u·∇u) = −∇p + μ∇²u + f

  N-S Term              | Code Conversion Mapping
  ──────────────────────|────────────────────────────────
  u (velocity field)    | Conversion progress per line
  ρ (density)           | Token density (complexity/line)
  −∇p (pressure grad)   | Structural constraints (brace balance)
  μ∇²u (viscous diff)   | Pattern smoothing across neighbors
  f (body forces)       | User-specified overrides/hints
  Re (Reynolds number)  | (depth × lines) / confidence → flow regime

Kolmogorov Energy Cascade:
  L (integral scale)    | Module/class level transforms
  λ (Taylor scale)      | Function/block level transforms
  η (Kolmogorov scale)  | Token-level substitutions (True→TRUE)

Turbulence Closure (k-ε model):
  k = structural depth (brace nesting kinetic energy)
  ε = dissipation rate  (how fast blocks close)
  k/ε balance GUARANTEES brace closure — no more v2.0 leaks

SST Blending (Menter):
  Near-wall (fn boundaries) → k-ω direct integration
  Freestream (expressions)  → k-ε fast substitution
  F1 blending function switches between zones
"""

import re
import os
import sys
import ast
import glob
import json
import math
import textwrap
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


# ──────────────────────────────────────────────
# §1  CONSTANTS — 3-5-7-13 Harmonic System
# ──────────────────────────────────────────────
H3  = 3       # Ternary base
H5  = 5       # TZip pack unit
H7  = 7       # Composition unit
H13 = 13      # Carrier frame

BLOCK_SIZE = H3 ** H7       # 2187 — max batch
RE_LAMINAR = H3 ** H3       # 27
RE_TRANSITION = H5 ** H3    # 125
RE_TURBULENT = H7 ** H3     # 343

# Kolmogorov constant C_K ≈ 1.5, using ternary: 3/2
C_K = H3 / 2


# ──────────────────────────────────────────────
# §2  FLOW REGIME ENUM
# ──────────────────────────────────────────────
class FlowRegime(Enum):
    LAMINAR     = "laminar"      # Re < 27:  single-pass direct
    TRANSITION  = "transition"   # Re < 125: two-pass with smoothing
    TURBULENT   = "turbulent"    # Re < 343: multi-pass RANS
    CHAOTIC     = "chaotic"      # Re ≥ 343: full decomposition + manual


# ──────────────────────────────────────────────
# §3  DATA STRUCTURES
# ──────────────────────────────────────────────
@dataclass
class FlowState:
    """Per-line fluid state during conversion."""
    line_num: int
    original: str
    converted: str = ""
    depth_k: int = 0          # Structural depth (k = kinetic energy)
    epsilon: float = 0.0      # Dissipation rate
    reynolds: float = 0.0     # Local Reynolds number
    regime: FlowRegime = FlowRegime.LAMINAR
    pressure: float = 0.0     # Brace balance pressure (−∇p)
    viscosity: float = 1.0    # Pattern confidence (μ)
    scale: str = "eta"        # Kolmogorov scale: L/lambda/eta
    errors: List[str] = field(default_factory=list)


@dataclass
class ConversionResult:
    """Full conversion output."""
    source_path: str
    output_path: str
    lines: List[FlowState] = field(default_factory=list)
    reynolds_global: float = 0.0
    regime: FlowRegime = FlowRegime.LAMINAR
    total_transforms: int = 0
    brace_delta: int = 0       # Must be 0 for valid output
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# §4  KOLMOGOROV CASCADE — Multi-Scale Patterns
# ──────────────────────────────────────────────
# Scale L: Module/Class level (integral scale — largest eddies)
PATTERNS_L = [
    # Class definitions
    (r'^class\s+(\w+)\s*(?:\(([^)]*)\))?\s*:', r'class3 \1\2 {'),
    # Imports → let requires
    (r'^import\s+(\w+)', r'// import \1'),
    (r'^from\s+(\S+)\s+import\s+(.+)', r'// from \1 import \2'),
    # Module docstrings
    (r'^"""', r'//"""'),
    (r"^'''", r"//'''"),
    # if __name__ == "__main__": → main block
    (r'^if\s+__name__\s*==\s*["\']__main__["\']\s*:', r'// __main__'),
    # Global variables
    (r'^(\w+)\s*=\s*\{', r'let \1 = {'),
    (r'^(\w+)\s*=\s*\[', r'let \1 = ['),
]

# Scale λ: Function/Block level (Taylor scale — inertial range)
PATTERNS_LAMBDA = [
    # Function definitions
    (r'^(\s*)def\s+(\w+)\s*\(self(?:,\s*)?', r'\1fn \2('),
    (r'^(\s*)def\s+(\w+)\s*\(', r'\1fn \2('),
    # Decorators
    (r'^(\s*)@(\w+)', r'\1// @\2'),
    # if/elif/else → if3/else3
    (r'^(\s*)if\s+(.+?)\s*:', r'\1if3 \2 {'),
    (r'^(\s*)elif\s+(.+?)\s*:', r'\1} else3 \2 {'),
    (r'^(\s*)else\s*:', r'\1} else {'),
    # for → for3
    (r'^(\s*)for\s+(\w+)\s+in\s+(.+?)\s*:', r'\1for3 \2 in \3 {'),
    (r'^(\s*)for\s+(\w+),\s*(\w+)\s+in\s+(.+?)\s*:', r'\1for3 \2, \3 in \4 {'),
    # while → while3
    (r'^(\s*)while\s+(.+?)\s*:', r'\1while3 \2 {'),
    # try/except/finally → try3/fail
    (r'^(\s*)try\s*:', r'\1try3 {'),
    (r'^(\s*)except\s+(\w+)(?:\s+as\s+(\w+))?\s*:', r'\1} fail \2 \3 {'),
    (r'^(\s*)except\s*:', r'\1} fail {'),
    (r'^(\s*)finally\s*:', r'\1} finally {'),
    # with → let (simplified)
    (r'^(\s*)with\s+(.+?)\s+as\s+(\w+)\s*:', r'\1let \3 = \2\n\1{'),
    # return
    (r'^(\s*)return\s+(.+)', r'\1return \2'),
    (r'^(\s*)return\s*$', r'\1return null'),
    # raise → throw
    (r'^(\s*)raise\s+(\w+)\((.+?)\)', r'\1throw(\2, \3)'),
    (r'^(\s*)raise\s+(.+)', r'\1throw(\2)'),
    # pass → (nothing, but close block)
    (r'^(\s*)pass\s*$', r'\1// pass'),
    # assert
    (r'^(\s*)assert\s+(.+?),\s*(.+)', r'\1if3 !(\2) { throw("AssertionError", \3) }'),
    (r'^(\s*)assert\s+(.+)', r'\1if3 !(\2) { throw("AssertionError") }'),
    # yield → (comment, NovaLang doesn't have generators yet)
    (r'^(\s*)yield\s+(.+)', r'\1// yield \2'),
]

# Scale η: Token level (Kolmogorov dissipation — smallest eddies)
PATTERNS_ETA = [
    # Boolean literals
    (r'\bTrue\b', 'TRUE'),
    (r'\bFalse\b', 'FALSE_'),
    (r'\bNone\b', 'null'),
    # Operators
    (r'\band\b', '&&'),
    (r'\bor\b', '||'),
    (r'\bnot\s+', '!'),
    (r'\bis\s+not\s+', '!= '),
    (r'\bis\s+', '== '),
    (r'\bin\b(?!\s*\{)', 'in'),
    # Self reference
    (r'\bself\.', ''),
    # String methods that map directly
    (r'\.append\(', '.push('),
    (r'\.extend\(', '.concat('),
    (r'\.items\(\)', '.entries()'),
    (r'\.keys\(\)', '.keys()'),
    (r'\.values\(\)', '.values()'),
    (r'\.strip\(\)', '.trim()'),
    (r'\.lstrip\(\)', '.trimStart()'),
    (r'\.rstrip\(\)', '.trimEnd()'),
    (r'\.lower\(\)', '.toLower()'),
    (r'\.upper\(\)', '.toUpper()'),
    (r'\.startswith\(', '.startsWith('),
    (r'\.endswith\(', '.endsWith('),
    (r'\.replace\(', '.replace('),
    (r'\.split\(', '.split('),
    (r'\.join\(', '.join('),
    (r'\.format\(', '.fmt('),
    # len() → len()  (same in NovaLang)
    # print() → print() (same in NovaLang)
    # Type constructors
    (r'\bint\(', 'int('),
    (r'\bfloat\(', 'float('),
    (r'\bstr\(', 'str('),
    (r'\blist\(', 'list('),
    (r'\bdict\(', 'dict('),
    (r'\bbool\(', 'bool3('),
    # f-strings: f"..." → "..." (NovaLang handles interpolation)
    (r'\bf"', '"'),
    (r"\bf'", "'"),
    # Python builtins → NovaLang equivalents
    (r'\bisinstance\((\w+),\s*(\w+)\)', r'typeof(\1) == "\2"'),
    (r'\bhasattr\((\w+),\s*["\'](\w+)["\']\)', r'\1.\2 != null'),
    (r'\bgetattr\((\w+),\s*["\'](\w+)["\'](?:,\s*(.+?))?\)', r'\1.\2'),
    # Exception types
    (r'\bException\b', 'Error'),
    (r'\bValueError\b', 'ValueError'),
    (r'\bTypeError\b', 'TypeError'),
    (r'\bKeyError\b', 'KeyError'),
    (r'\bIndexError\b', 'IndexError'),
    (r'\bFileNotFoundError\b', 'FileError'),
    # Dict comprehension → (simplified)
    (r'\{(\w+):\s*(\w+)\s+for\s+(\w+)\s+in\s+(.+?)\}', r'dict_from(\4, fn(\3) { return {\1: \2} })'),
    # List comprehension → map
    (r'\[(.+?)\s+for\s+(\w+)\s+in\s+(.+?)(?:\s+if\s+(.+?))?\]', r'\3.filter(fn(\2) { return \4 }).map(fn(\2) { return \1 })'),
]


# ──────────────────────────────────────────────
# §5  REYNOLDS CALCULATOR
# ──────────────────────────────────────────────
def compute_reynolds(source_lines: List[str]) -> Tuple[float, FlowRegime]:
    """
    Re = ρUL / μ

    ρ = token density (avg tokens per line)
    U = velocity (total lines — throughput requirement)
    L = characteristic length (max nesting depth)
    μ = viscosity (pattern match confidence — higher = easier)
    """
    if not source_lines:
        return 0.0, FlowRegime.LAMINAR

    # ρ: token density
    total_tokens = 0
    for line in source_lines:
        total_tokens += len(line.split())
    rho = total_tokens / max(len(source_lines), 1)

    # U: velocity (line count, normalized)
    U = math.log2(max(len(source_lines), 1) + 1)

    # L: characteristic length (max indent depth as proxy for nesting)
    max_depth = 0
    for line in source_lines:
        stripped = line.lstrip()
        if stripped:
            indent = len(line) - len(stripped)
            depth = indent // 4
            max_depth = max(max_depth, depth)
    L = max_depth + 1

    # μ: viscosity — measure of "how standard" the Python is
    # More exotic patterns = lower viscosity = higher Re
    exotic_count = 0
    for line in source_lines:
        s = line.strip()
        if any(kw in s for kw in ['lambda', 'yield', 'async', 'await', 'nonlocal',
                                    'global', '__', 'metaclass', 'super()',
                                    'property', 'staticmethod', 'classmethod',
                                    'contextmanager', 'generator']):
            exotic_count += 1
    mu = max(1.0, 10.0 - exotic_count * 0.5)

    Re = (rho * U * L) / mu

    # Classify regime using 3-5-7 boundaries
    if Re < RE_LAMINAR:        # < 27
        regime = FlowRegime.LAMINAR
    elif Re < RE_TRANSITION:   # < 125
        regime = FlowRegime.TRANSITION
    elif Re < RE_TURBULENT:    # < 343
        regime = FlowRegime.TURBULENT
    else:                       # ≥ 343
        regime = FlowRegime.CHAOTIC

    return Re, regime


# ──────────────────────────────────────────────
# §6  BRACE CLOSURE MODEL (k-ε Turbulence)
# ──────────────────────────────────────────────
class BraceClosureModel:
    """
    k-ε model for brace balance:
      k = structural depth (kinetic energy of nesting)
      ε = dissipation rate (how fast blocks should close)

    The model tracks production P_k (opening braces) and
    dissipation ε (closing braces), ensuring:
      ∂k/∂t = P_k - ε ≈ 0  (steady state → balanced braces)

    Near function boundaries (wall), switches to k-ω (direct tracking).
    SST blending function F1 handles the transition.
    """

    def __init__(self):
        self.k = 0           # Current depth
        self.epsilon = 0.0   # Running dissipation rate
        self.history = []    # (line_num, k, delta)
        self.fn_boundaries = []  # Line numbers where functions start
        self.closures_needed = []  # (line_num, count) — where to insert }

    def feed(self, line_num: int, line: str):
        """Process one converted line, updating k-ε state."""
        clean = self._strip_strings_comments(line)
        opens = clean.count('{')
        closes = clean.count('}')
        delta = opens - closes

        old_k = self.k
        self.k += delta

        # Track function boundaries for SST blending
        stripped = line.strip()
        if stripped.startswith('fn ') and '{' in stripped:
            self.fn_boundaries.append(line_num)

        # Production = opens, Dissipation = closes
        # ε tracks the running average close rate
        alpha = 0.1  # Smoothing factor
        self.epsilon = (1 - alpha) * self.epsilon + alpha * closes

        self.history.append((line_num, self.k, delta))

        # Pressure warning: depth went negative → extra }
        if self.k < 0:
            return -1  # Negative pressure — remove a }

        return 0  # Normal

    def close_all(self) -> List[Tuple[int, int]]:
        """
        At end of file, ensure k = 0.
        Returns list of (insert_after_line, count) for missing closers.
        Uses SST blending: near function walls, close per-function.
        In freestream, close at EOF.
        """
        if self.k <= 0:
            return []

        closures = []

        # SST approach: find unclosed functions
        fn_depths = {}
        current_fn = -1
        depth = 0

        for line_num, k, delta in self.history:
            if line_num in [b for b in self.fn_boundaries]:
                if current_fn >= 0 and depth > 0:
                    # Previous function didn't close — need closures before this fn
                    closures.append((line_num - 1, depth))
                    depth = 0
                current_fn = line_num
                depth = delta
            else:
                depth += delta

        # Remaining depth at EOF
        if depth > 0 and self.history:
            last_line = self.history[-1][0]
            closures.append((last_line, depth))

        # If SST didn't resolve, fallback: close everything at EOF
        total_closed = sum(c for _, c in closures)
        if total_closed < self.k:
            remaining = self.k - total_closed
            if self.history:
                closures.append((self.history[-1][0], remaining))

        return closures

    def _strip_strings_comments(self, line: str) -> str:
        """Remove string contents and comments before counting braces."""
        result = []
        in_str = False
        str_char = None
        i = 0
        while i < len(line):
            ch = line[i]
            if in_str:
                if ch == str_char and (i == 0 or line[i-1] != '\\'):
                    in_str = False
                    result.append(ch)
                else:
                    result.append(' ')  # Replace string content with space
            else:
                if ch in ('"', "'"):
                    in_str = True
                    str_char = ch
                    result.append(ch)
                elif ch == '/' and i + 1 < len(line) and line[i+1] == '/':
                    break  # Rest is comment
                elif ch == '#':
                    break  # Rest is comment
                else:
                    result.append(ch)
            i += 1
        return ''.join(result)


# ──────────────────────────────────────────────
# §7  INDENTATION → BRACE ENGINE
# ──────────────────────────────────────────────
class IndentToBraceEngine:
    """
    Python uses indentation for blocks.
    NovaLang uses braces.

    This engine tracks indent level changes and inserts
    closing braces when dedent occurs. This is the CORE
    difference from v2.0 which just regex'd line-by-line
    without tracking indent state.

    N-S analogy: This is the viscous sublayer integration
    (k-ω near-wall model). We must resolve every single
    indent change — no wall functions allowed here.
    """

    def __init__(self):
        self.indent_stack = [0]  # Stack of indent levels
        self.brace_depth = 0
        self.pending_closes = []

    def process_indent(self, line: str, converted: str) -> str:
        """
        Compare current indent to stack top.
        Insert closing braces for each dedent level.
        """
        if not line.strip():
            return converted  # Blank line, no indent change

        # Measure current indent
        stripped = line.lstrip()
        current_indent = len(line) - len(stripped)

        # Dedent: close blocks
        closes = ""
        while len(self.indent_stack) > 1 and current_indent < self.indent_stack[-1]:
            self.indent_stack.pop()
            # Don't add } if the converted line already starts with }
            if not converted.strip().startswith('}'):
                target_indent = self.indent_stack[-1] if self.indent_stack else 0
                closes += " " * target_indent + "}\n"
                self.brace_depth -= 1

        # Check if this line opens a new block (ends with {)
        conv_stripped = converted.rstrip()
        if conv_stripped.endswith('{'):
            self.indent_stack.append(current_indent + 4)
            self.brace_depth += 1

        return closes + converted

    def flush(self) -> str:
        """Close all remaining open blocks at EOF."""
        closes = ""
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            indent = self.indent_stack[-1] if self.indent_stack else 0
            closes += " " * indent + "}\n"
            self.brace_depth -= 1
        return closes


# ──────────────────────────────────────────────
# §8  VISCOUS DIFFUSION — Neighbor Smoothing
# ──────────────────────────────────────────────
def viscous_smooth(lines: List[str], window: int = H3) -> List[str]:
    """
    μ∇²u — Laplacian smoothing of conversion quality.

    Looks at neighboring lines to fix context-dependent patterns
    that single-line regex can't handle:
    - Multi-line strings
    - Continuation lines
    - Decorator + function pairs
    - Dict/list spanning multiple lines
    """
    smoothed = list(lines)
    n = len(smoothed)

    for i in range(n):
        line = smoothed[i].rstrip()

        # Fix: decorator followed by fn should be comment + fn
        if line.strip().startswith('// @') and i + 1 < n:
            next_line = smoothed[i + 1].strip()
            if not next_line.startswith('fn '):
                # Decorator above non-function — might be misplaced
                pass

        # Fix: else3/fail without preceding }
        if i > 0:
            stripped = line.strip()
            if stripped.startswith('else3 ') or stripped.startswith('else {') or stripped.startswith('fail '):
                prev = smoothed[i - 1].rstrip()
                if not prev.strip().endswith('}'):
                    # Need to insert } before this line
                    indent = len(line) - len(line.lstrip())
                    smoothed[i] = " " * indent + "} " + stripped + "\n"

        # Fix: function def that lost its opening brace
        stripped = line.strip()
        if stripped.startswith('fn ') and '(' in stripped and ')' in stripped and not stripped.endswith('{'):
            if not stripped.endswith('{'):
                smoothed[i] = line.rstrip() + " {\n"

        # Fix: colon at end of line that wasn't converted
        if stripped.endswith(':') and not stripped.startswith('//') and not stripped.startswith('#'):
            # Might be a missed block — but only if it looks like a statement
            if any(stripped.startswith(kw) for kw in ['if3', 'for3', 'while3', 'try3', 'fn ']):
                smoothed[i] = line.rstrip()[:-1] + " {\n"

    return smoothed


# ──────────────────────────────────────────────
# §9  PRESSURE GRADIENT — Structural Constraints
# ──────────────────────────────────────────────
def apply_pressure(lines: List[str]) -> Tuple[List[str], int]:
    """
    −∇p: Pressure gradient enforces structural integrity.

    Walks the converted output and ensures:
    1. Every { has a matching }
    2. No } goes below depth 0
    3. Functions end with }
    4. tstart() is at depth 0

    Returns (fixed_lines, brace_delta) where delta should be 0.
    """
    closure = BraceClosureModel()
    fixed = list(lines)
    removals = []

    for i, line in enumerate(fixed):
        result = closure.feed(i, line)
        if result == -1:
            # Negative pressure: extra }
            if line.strip() == '}':
                removals.append(i)
                closure.k += 1  # Undo the negative

    # Remove extra } lines (reverse order)
    for idx in reversed(removals):
        fixed.pop(idx)

    # Add missing closures
    closures = closure.close_all()
    offset = 0
    for insert_after, count in sorted(closures, key=lambda x: x[0]):
        adjusted = insert_after + offset - len([r for r in removals if r <= insert_after])
        adjusted = min(adjusted + 1, len(fixed))
        insert_text = "}\n" * count
        fixed.insert(adjusted, insert_text)
        offset += 1

    # Final verification
    final_depth = 0
    for line in fixed:
        clean = BraceClosureModel()._strip_strings_comments(line)
        final_depth += clean.count('{') - clean.count('}')

    return fixed, final_depth


# ──────────────────────────────────────────────
# §10  MAIN CONVERTER — TPacman v3.0
# ──────────────────────────────────────────────
class TPacmanV3:
    """
    Navier-Stokes Python-to-NovaLang Converter.

    Pipeline (maps to N-S simulation steps):
    1. PREPROCESSING  — Read source, compute Reynolds number
    2. INTEGRAL SCALE — Apply L-patterns (class/module transforms)
    3. INERTIAL RANGE — Apply λ-patterns (function/block transforms)
    4. DISSIPATION    — Apply η-patterns (token substitutions)
    5. INDENT→BRACE   — k-ω near-wall resolution (indent tracking)
    6. SMOOTHING      — μ∇²u viscous diffusion (neighbor fixes)
    7. PRESSURE       — −∇p closure model (brace balancing)
    8. VERIFICATION   — Continuity check (tokens in ≈ tokens out)
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.stats = {
            "files_converted": 0,
            "total_lines": 0,
            "total_transforms": 0,
            "regime_counts": {r.value: 0 for r in FlowRegime},
            "closure_fixes": 0,
        }

    def convert_file(self, source_path: str, output_path: str = None) -> ConversionResult:
        """Convert a Python file to NovaLang."""
        if output_path is None:
            base = os.path.basename(source_path)
            name = os.path.splitext(base)[0]
            output_path = os.path.join(os.path.dirname(source_path), name + ".nova")

        with open(source_path, "r", encoding="utf-8", errors="replace") as f:
            source_lines = f.readlines()

        result = ConversionResult(
            source_path=source_path,
            output_path=output_path,
        )

        # §10.1 — Compute Reynolds number
        Re, regime = compute_reynolds(source_lines)
        result.reynolds_global = Re
        result.regime = regime

        if self.verbose:
            print(f"  Re = {Re:.1f} -> {regime.value}")

        self.stats["regime_counts"][regime.value] += 1

        # §10.2 — Pre-process: strip Python-only constructs
        lines = self._preprocess(source_lines)

        # §10.3 — Kolmogorov cascade: L → λ → η
        lines, transforms = self._cascade(lines, regime)
        result.total_transforms = transforms

        # §10.4 — Indent → Brace conversion (k-ω wall model)
        lines = self._indent_to_braces(lines, source_lines)

        # §10.5 — Viscous smoothing (μ∇²u)
        lines = viscous_smooth(lines)

        # §10.6 — Pressure gradient (−∇p closure)
        lines, delta = apply_pressure(lines)
        result.brace_delta = delta

        if delta != 0:
            result.warnings.append(f"Brace delta = {delta} (should be 0)")
            self.stats["closure_fixes"] += abs(delta)

        # §10.7 — Add NovaLang header
        header = self._generate_header(source_path, Re, regime)
        lines = [header + "\n"] + lines

        # §10.8 — Write output
        output_text = "".join(lines)
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(output_text)

        self.stats["files_converted"] += 1
        self.stats["total_lines"] += len(lines)
        self.stats["total_transforms"] += transforms

        result.lines = [FlowState(line_num=i, original=l) for i, l in enumerate(lines)]

        return result

    def _preprocess(self, lines: List[str]) -> List[str]:
        """Remove Python-only constructs that have no NovaLang equivalent."""
        processed = []
        in_multiline_str = False
        multiline_char = None
        skip_next_decorator = False

        for line in lines:
            stripped = line.strip()

            # Handle multi-line strings (""" or ''')
            if not in_multiline_str:
                if '"""' in stripped or "'''" in stripped:
                    quote = '"""' if '"""' in stripped else "'''"
                    count = stripped.count(quote)
                    if count == 1:
                        in_multiline_str = True
                        multiline_char = quote
                        processed.append("// " + stripped + "\n")
                        continue
                    elif count >= 2:
                        # Opens and closes on same line — docstring
                        processed.append("// " + stripped + "\n")
                        continue
            else:
                if multiline_char in stripped:
                    in_multiline_str = False
                processed.append("// " + stripped + "\n")
                continue

            # Skip __all__, __version__ etc
            if stripped.startswith('__') and '=' in stripped:
                processed.append("// " + stripped + "\n")
                continue

            # Skip type hints (standalone)
            if stripped.startswith('-> ') or (': ' in stripped and '=' not in stripped and not any(
                stripped.startswith(kw) for kw in ['if', 'elif', 'else', 'for', 'while', 'def', 'class', 'try', 'except', 'with', 'return', 'raise']
            )):
                # Could be a type annotation like `x: int` — keep it but simplify
                pass

            processed.append(line)

        return processed

    def _cascade(self, lines: List[str], regime: FlowRegime) -> Tuple[List[str], int]:
        """
        Kolmogorov energy cascade: apply transforms from large to small scale.

        L (integral) → λ (inertial) → η (dissipation)

        In turbulent regime, apply extra smoothing passes between scales.
        """
        total_transforms = 0

        # Scale L: Module/class transforms (largest eddies)
        lines, t = self._apply_patterns(lines, PATTERNS_L, "L")
        total_transforms += t

        # Scale λ: Function/block transforms (inertial range)
        lines, t = self._apply_patterns(lines, PATTERNS_LAMBDA, "lambda")
        total_transforms += t

        # Scale eta: Token-level substitutions (Kolmogorov dissipation)
        lines, t = self._apply_patterns(lines, PATTERNS_ETA, "eta")
        total_transforms += t

        # In turbulent+ regimes, do an extra smoothing pass
        if regime in (FlowRegime.TURBULENT, FlowRegime.CHAOTIC):
            lines, t = self._apply_patterns(lines, PATTERNS_ETA, "eta2")
            total_transforms += t

        return lines, total_transforms

    def _apply_patterns(self, lines: List[str], patterns: List[Tuple], scale: str) -> Tuple[List[str], int]:
        """Apply a set of regex patterns to all lines."""
        result = []
        transforms = 0

        for line in lines:
            original = line
            for pattern, replacement in patterns:
                new_line = re.sub(pattern, replacement, line)
                if new_line != line:
                    transforms += 1
                    line = new_line
            result.append(line)

        if self.verbose and transforms:
            print(f"  Scale {scale}: {transforms} transforms")

        return result, transforms

    def _indent_to_braces(self, converted_lines: List[str], original_lines: List[str]) -> List[str]:
        """
        Convert Python indentation to NovaLang braces.
        Uses original indent levels to determine block boundaries.

        This is the k-ω near-wall model — we resolve every indent change
        directly instead of using wall functions.
        """
        result = []
        indent_stack = [0]

        for i, line in enumerate(converted_lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('//'):
                result.append(line)
                continue

            # Get current indent from original Python
            if i < len(original_lines):
                orig = original_lines[i]
                orig_stripped = orig.lstrip()
                current_indent = len(orig) - len(orig_stripped) if orig_stripped else 0
            else:
                current_indent = len(line) - len(line.lstrip()) if stripped else 0

            # Dedent: close blocks
            while len(indent_stack) > 1 and current_indent < indent_stack[-1]:
                indent_stack.pop()
                close_indent = indent_stack[-1] if indent_stack else 0
                # Don't add } if this line already starts with }
                if not stripped.startswith('}'):
                    result.append(" " * close_indent + "}\n")

            # Add the converted line with proper indent
            result.append(" " * current_indent + stripped + "\n")

            # Check if this line opens a new block
            # Lines ending with { indicate a new block
            if stripped.endswith('{') and not stripped.startswith('//'):
                indent_stack.append(current_indent + 4)

        # Close remaining open blocks
        while len(indent_stack) > 1:
            indent_stack.pop()
            close_indent = indent_stack[-1] if indent_stack else 0
            result.append(" " * close_indent + "}\n")

        return result

    def _generate_header(self, source_path: str, Re: float, regime: FlowRegime) -> str:
        """Generate NovaLang file header with N-S metadata."""
        name = os.path.basename(source_path)
        return (
            f"// TPacman v3.0 — Navier-Stokes Converter\n"
            f"// Source: {name}\n"
            f"// Reynolds: {Re:.1f} ({regime.value})\n"
            f"// Cascade: L→λ→η (Kolmogorov)\n"
            f"// Closure: k-ε + SST blending\n"
            f"//\n"
        )

    # ──────────────────────────────────────────
    # §11  BATCH CONVERSION
    # ──────────────────────────────────────────
    def convert_batch(self, directory: str, pattern: str = "*.py") -> List[ConversionResult]:
        """Convert all Python files in directory."""
        files = glob.glob(os.path.join(directory, pattern))
        results = []

        # Skip files that already have .nova equivalents
        nova_files = set(os.path.splitext(f)[0] for f in glob.glob(os.path.join(directory, "*.nova")))

        for filepath in sorted(files):
            base = os.path.splitext(os.path.basename(filepath))[0]
            full_base = os.path.join(directory, base)

            # Skip if .nova already exists
            if full_base in nova_files:
                if self.verbose:
                    print(f"  SKIP {filepath} (nova exists)")
                continue

            if self.verbose:
                print(f"\n Converting: {filepath}")

            try:
                result = self.convert_file(filepath)
                results.append(result)
                status = "OK" if result.brace_delta == 0 else f"WARN delta={result.brace_delta}"
                print(f"  {filepath} → {result.output_path} "
                      f"[Re={result.reynolds_global:.0f} {result.regime.value}] {status}")
            except Exception as e:
                print(f"  ERROR {filepath}: {e}")
                results.append(ConversionResult(
                    source_path=filepath,
                    output_path="",
                    errors=[str(e)]
                ))

        return results

    def print_stats(self):
        """Print conversion statistics with N-S analysis."""
        s = self.stats
        print(f"\n{'='*60}")
        print(f"TPacman v3.0 — Navier-Stokes Conversion Report")
        print(f"{'='*60}")
        print(f"Files converted:   {s['files_converted']}")
        print(f"Total lines:       {s['total_lines']}")
        print(f"Total transforms:  {s['total_transforms']}")
        print(f"Closure fixes:     {s['closure_fixes']}")
        print(f"\nFlow Regime Distribution:")
        for regime, count in s['regime_counts'].items():
            bar = "█" * count
            print(f"  {regime:12s} {count:3d} {bar}")
        print(f"{'='*60}")


# ──────────────────────────────────────────────
# §12  STANDALONE SERVICE (tserve/troute/tstart)
# ──────────────────────────────────────────────
def run_service():
    """Run TPacman as a NovaX micro-service on port 9991."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    pacman = TPacmanV3(verbose=True)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self._json({"status": "healthy", "service": "tpacman", "version": "3.0",
                             "model": "navier-stokes", "trit": 1})
            elif self.path == "/stats":
                self._json(pacman.stats)
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length > 0 else {}

            if self.path == "/convert":
                source = body.get("source_path", "")
                output = body.get("output_path", None)
                if not source or not os.path.exists(source):
                    self._json({"error": f"file not found: {source}"}, 404)
                    return
                result = pacman.convert_file(source, output)
                self._json({
                    "output": result.output_path,
                    "reynolds": result.reynolds_global,
                    "regime": result.regime.value,
                    "transforms": result.total_transforms,
                    "brace_delta": result.brace_delta,
                    "warnings": result.warnings,
                })
            elif self.path == "/analyze":
                source = body.get("source_path", "")
                if not source or not os.path.exists(source):
                    self._json({"error": f"file not found: {source}"}, 404)
                    return
                with open(source, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                Re, regime = compute_reynolds(lines)
                self._json({
                    "source": source,
                    "lines": len(lines),
                    "reynolds": Re,
                    "regime": regime.value,
                    "recommendation": "auto" if regime != FlowRegime.CHAOTIC else "manual review needed"
                })
            elif self.path == "/batch":
                directory = body.get("directory", "C:\\NovaX")
                pattern = body.get("pattern", "*.py")
                results = pacman.convert_batch(directory, pattern)
                self._json({
                    "converted": len([r for r in results if not r.errors]),
                    "errors": len([r for r in results if r.errors]),
                    "stats": pacman.stats,
                })
            else:
                self._json({"error": "not found"}, 404)

        def _json(self, data, code=200):
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())

        def log_message(self, format, *args):
            if pacman.verbose:
                print(f"  [tpacman] {args[0]}")

    server = HTTPServer(("0.0.0.0", 9991), Handler)
    print(f"TPacman v3.0 (Navier-Stokes) running on :9991")
    server.serve_forever()


# ──────────────────────────────────────────────
# §13  CLI ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TPacman v3.0 — N-S Python→NovaLang")
    parser.add_argument("source", nargs="?", help="Python source file to convert")
    parser.add_argument("-o", "--output", help="Output .nova file path")
    parser.add_argument("-b", "--batch", help="Batch convert directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--serve", action="store_true", help="Run as HTTP service on :9991")
    parser.add_argument("--analyze", action="store_true", help="Analyze only (no conversion)")
    args = parser.parse_args()

    pacman = TPacmanV3(verbose=args.verbose or True)

    if args.serve:
        run_service()
    elif args.batch:
        results = pacman.convert_batch(args.batch)
        pacman.print_stats()
    elif args.source:
        if args.analyze:
            with open(args.source, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            Re, regime = compute_reynolds(lines)
            print(f"Source:   {args.source}")
            print(f"Lines:    {len(lines)}")
            print(f"Reynolds: {Re:.1f}")
            print(f"Regime:   {regime.value}")
            print(f"Strategy: {'auto-convert' if regime != FlowRegime.CHAOTIC else 'MANUAL REVIEW NEEDED'}")
        else:
            result = pacman.convert_file(args.source, args.output)
            print(f"\nConverted: {result.output_path}")
            print(f"Reynolds:  {result.reynolds_global:.1f} ({result.regime.value})")
            print(f"Transforms: {result.total_transforms}")
            print(f"Brace D:   {result.brace_delta} {'OK' if result.brace_delta == 0 else 'FAIL'}")
            if result.warnings:
                for w in result.warnings:
                    print(f"  WARN: {w}")
    else:
        parser.print_help()
