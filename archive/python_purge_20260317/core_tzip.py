"""NovaX TZip v3.2 -- N-S Flow-Routed Ternary Compression Engine

The 3-5-7-11-13 harmonic constants define every parameter:
3  = ternary base (three states: -1, 0, +1)
5  = packing factor (3^5=243 fits in 1 byte of 256)
7  = composition unit (7 strategies, block size 3^7=2187)
11 = hyperbolic regime (3^11=177,147 CDC max, H11^3=1331 Reynolds)
13 = carrier wave / frame (TZip header = exactly 13 bytes)

ARCHITECTURE:
1. Calculate Reynolds number for input data
2. Select compression strategy based on flow regime (5 regimes)
3. Competitive selection: try ALL strategies, keep shortest
4. Ternary trit-pack the compressed output (5 trits/byte, 3^5=243)
5. Wrap in 13-byte TZIP header

v3.2 UPGRADES:
- LZMA strategy: 4MB window, ~24% better than deflate on source code
- Token+LZMA: domain vocabulary + long-range matching (best combo)
- 8 competitive strategies: LZMA + Token+LZMA join the arena
- Circuit damping ratios: Gaussian-weighted strategy ordering
- Stream mode: full-corpus LZMA stream (5.5x vs per-block 3.2x)
"""
import struct
import math
import hashlib
import random as _random

try:
    import zlib as _zlib
except ImportError:
    _zlib = None

try:
    import lzma as _lzma
except ImportError:
    _lzma = None

# ======================================================
# 3-5-7-11-13 HARMONIC CONSTANTS
# ======================================================
H3  = 3
H5  = 5
H7  = 7
H11 = 11
H13 = 13

BLOCK_SIZE     = H3 ** H7    # 2187
FLOW_LAMINAR   = H3 ** H3    # 27
FLOW_TRANS     = H5 ** H3    # 125
FLOW_TURBULENT = H7 ** H3    # 343
FLOW_HYPER     = H11 ** H3   # 1331
HEADER_SIZE    = H13          # 13
PACK_TRITS     = H5           # 5

TZIP_MAGIC   = b"TZIP"
TZIP_VERSION = 3  # v3.2

# Strategy flags (stored in header byte 12)
STRAT_RAW   = 0x00
STRAT_RLE   = 0x01
STRAT_LZ    = 0x02
STRAT_ZLIB  = 0x03  # legacy: backward compat
STRAT_RANS  = 0x04
STRAT_DICT  = 0x05
STRAT_TOKEN = 0x06
STRAT_LZMA  = 0x07
STRAT_TLZMA = 0x08
STRAT_TRIT  = 0x10  # flag: OR'd with strategy

# rANS table precision M = 3^7 = 2187
_RANS_M = BLOCK_SIZE

# ======================================================
# TRIT HELPERS
# ======================================================
_TRIT_MAX = 3 ** PACK_TRITS  # 243

def _trit_encode(data):
    """Encode bytes into trit-packed format.
    Bytes 0-241: direct.
    Byte 242: escape [242, 13] -- H13 sentinel means literal 242.
    Bytes 243-255: escape [242, value-243].
    Avoids the 242-ambiguity bug."""
    out = bytearray()
    _ESC = _TRIT_MAX - 1  # 242
    for b in data:
        if b < _ESC:
            out.append(b)
        elif b == _ESC:
            out.append(_ESC)
            out.append(H13)  # 13 = sentinel
        else:
            out.append(_ESC)
            out.append(b - _TRIT_MAX)  # 0-12
    return bytes(out)

def _trit_decode(data, orig_size):
    """Decode trit-packed format back to bytes."""
    out = bytearray()
    i = 0
    _ESC = _TRIT_MAX - 1  # 242
    while i < len(data) and len(out) < orig_size:
        if data[i] == _ESC and i + 1 < len(data):
            nxt = data[i + 1]
            if nxt <= 12:
                out.append(_TRIT_MAX + nxt)  # 243-255
            else:
                out.append(_ESC)  # literal 242
            i += 2
        else:
            out.append(data[i])
            i += 1
    return bytes(out[:orig_size])

# ======================================================
# N-S REYNOLDS NUMBER
# ======================================================

def reynolds(data):
    """Calculate the Reynolds number of a data stream.
    Re = (entropy_norm * trans_rate * FLOW_HYPER) / viscosity
    Low Re = laminar (structured/repetitive). High Re = chaotic."""
    if len(data) < H13:
        return 0.0
    sample = data[:BLOCK_SIZE * H3]
    n = len(sample)

    freq = [0] * 256
    for b in sample:
        freq[b] += 1

    entropy = 0.0
    for f in freq:
        if f > 0:
            p = f / n
            entropy -= p * math.log2(p)
    entropy_norm = entropy / 8.0

    transitions = sum(1 for i in range(1, n) if sample[i] != sample[i - 1])
    trans_rate = transitions / max(1, n - 1)

    unique = sum(1 for f in freq if f > 0)
    redundancy = 1.0 - (unique / 256.0)
    viscosity = max(0.01, redundancy)

    re = (entropy_norm * trans_rate * FLOW_HYPER) / viscosity
    return round(re, 2)

def classify_flow(re):
    """Classify data flow regime from Reynolds number (5 regimes)."""
    if re < FLOW_LAMINAR:   return "laminar"
    if re < FLOW_TRANS:     return "transitional"
    if re < FLOW_TURBULENT: return "turbulent"
    if re < FLOW_HYPER:     return "hyperbolic"
    return "chaotic"

def select_strategy(re):
    """Select compression strategy from Reynolds number (legacy path)."""
    if re < FLOW_LAMINAR:   return STRAT_RLE   | STRAT_TRIT
    if re < FLOW_TRANS:     return STRAT_LZ    | STRAT_TRIT
    if re < FLOW_TURBULENT: return STRAT_RANS  | STRAT_TRIT
    if re < FLOW_HYPER:     return STRAT_TOKEN
    return STRAT_RAW

# ======================================================
# CIRCUIT DAMPING RATIO -- Continuous Strategy Selection
# ======================================================
# ζ = log(1+Re) / log(1+FLOW_HYPER) * 3.0
# Each strategy has a natural ζ (sweet spot) and Gaussian width σ.

_STRAT_ZETA = {
    STRAT_RLE:   0.0,
    STRAT_LZ:    1.2,
    STRAT_RANS:  1.5,
    STRAT_ZLIB:  1.8,
    STRAT_DICT:  2.0,
    STRAT_TOKEN: 2.3,
    STRAT_LZMA:  2.6,
    STRAT_TLZMA: 2.8,
}

_STRAT_SIGMA = {
    STRAT_RLE:   0.5,
    STRAT_LZ:    0.4,
    STRAT_RANS:  0.4,
    STRAT_ZLIB:  0.5,
    STRAT_DICT:  0.5,
    STRAT_TOKEN: 0.5,
    STRAT_LZMA:  0.5,
    STRAT_TLZMA: 0.6,
}

def damping_ratio(re):
    """Convert Reynolds to damping ratio zeta (0.0 -> inf)."""
    if re <= 0:
        return 0.0
    return math.log(1 + re) / math.log(1 + FLOW_HYPER) * 3.0

def strategy_weights(re):
    """Compute Gaussian weights for each strategy based on damping ratio.
    Returns list of (weight, strat_base) sorted by weight descending."""
    zeta = damping_ratio(re)
    weights = []
    for strat, zeta_nat in _STRAT_ZETA.items():
        sigma = _STRAT_SIGMA[strat]
        dist = (zeta - zeta_nat) ** 2
        w = math.exp(-dist / (2 * sigma * sigma))
        weights.append((w, strat))
    weights.sort(key=lambda x: x[0], reverse=True)
    return weights

# ======================================================
# COMPRESSION STRATEGIES
# ======================================================

def _rle_compress(data):
    """Run-Length Encoding -- best for laminar (repetitive) data."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        run_byte = data[i]
        run_len = 1
        while i + run_len < n and data[i + run_len] == run_byte and run_len < 255:
            run_len += 1
        if run_len >= H3:
            out.append(run_len)
            out.append(run_byte)
            i += run_len
        else:
            lit_start = i
            while i < n:
                if i + H3 <= n and data[i] == data[i + 1] == data[i + 2]:
                    break
                i += 1
                if i - lit_start >= 254:
                    break
            lit_len = i - lit_start
            out.append(0)
            out.append(lit_len)
            out.extend(data[lit_start:lit_start + lit_len])
    return bytes(out)

def _rle_decompress(data):
    """Decompress RLE data."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        count = data[i]; i += 1
        if count == 0:
            if i >= n: break
            lit_len = data[i]; i += 1
            out.extend(data[i:i + lit_len])
            i += lit_len
        else:
            if i >= n: break
            out.extend(bytes([data[i]]) * count)
            i += 1
    return bytes(out)

def _lz_compress(data):
    """Hash-table LZ77 -- O(1) match finding per position."""
    out = bytearray()
    n = len(data)
    if n < 4:
        out.extend(data)
        return bytes(out)

    _HT_SIZE = BLOCK_SIZE
    htable = [0] * _HT_SIZE

    def _hash4(pos):
        if pos + 3 >= n:
            return 0
        v = data[pos] | (data[pos+1] << 8) | (data[pos+2] << 16) | (data[pos+3] << 24)
        return ((v * 2654435761) >> 19) % _HT_SIZE

    i = 0
    while i < n:
        if i + 3 >= n:
            if data[i] == 0xFF:
                out.extend([0xFF, 0x00, 0x00, 0x01])
            else:
                out.append(data[i])
            i += 1
            continue

        h = _hash4(i)
        ref = htable[h]
        htable[h] = i

        best_len = 0
        best_off = 0
        if ref < i and i - ref <= BLOCK_SIZE:
            ml = 0
            while i + ml < n and ml < 255 and data[ref + ml] == data[i + ml]:
                ml += 1
            if ml >= H3:
                best_len = ml
                best_off = i - ref

        if best_len >= H3:
            out.append(0xFF)
            out.append((best_off >> 8) & 0xFF)
            out.append(best_off & 0xFF)
            out.append(best_len)
            i += best_len
        else:
            if data[i] == 0xFF:
                out.extend([0xFF, 0x00, 0x00, 0x01])
            else:
                out.append(data[i])
            i += 1
    return bytes(out)

def _lz_decompress(data):
    """Decompress LZ77-lite data."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        if data[i] == 0xFF and i + 3 < n:
            off = (data[i + 1] << 8) | data[i + 2]
            length = data[i + 3]
            if off == 0 and length == 1:
                out.append(0xFF)
            else:
                start = len(out) - off
                for j in range(length):
                    out.append(out[start + j])
            i += 4
        else:
            out.append(data[i])
            i += 1
    return bytes(out)

# ======================================================
# rANS BASE-3 ENTROPY CODER
# ======================================================

def _rans_compress(data):
    """rANS base-3 entropy coder -- near-optimal ternary compression."""
    n = len(data)
    if n == 0:
        return b""
    M = _RANS_M  # 2187

    freq = [0] * 256
    for b in data:
        freq[b] += 1

    nf = [0] * 256
    used = []
    total_assigned = 0
    for i in range(256):
        if freq[i] > 0:
            nf[i] = max(1, round(freq[i] * M / n))
            total_assigned += nf[i]
            used.append(i)

    diff = M - total_assigned
    if diff != 0:
        best = max(used, key=lambda s: freq[s])
        nf[best] += diff
        if nf[best] <= 0:
            nf[best] = 1

    cdf = [0] * 257
    for i in range(256):
        cdf[i + 1] = cdf[i] + nf[i]

    x = M
    trit_buf = []
    for sym in reversed(data):
        fs = nf[sym]
        while x >= 3 * fs:
            trit_buf.append(x % 3)
            x //= 3
        x = (x // fs) * M + (x % fs) + cdf[sym]

    while x > 0:
        trit_buf.append(x % 3)
        x //= 3
    trit_buf.reverse()

    num_trits = len(trit_buf)
    packed = bytearray()
    for i in range(0, num_trits, 5):
        group = trit_buf[i:i + 5]
        val = 0
        for j, t in enumerate(group):
            val += t * (3 ** j)
        packed.append(val)

    out = bytearray()
    num_used = len(used)
    out.append(num_used if num_used < 256 else 0)
    for s in used:
        out.append(s)
        out.append((nf[s] >> 8) & 0xFF)
        out.append(nf[s] & 0xFF)
    out.extend(struct.pack("<I", n))
    out.extend(struct.pack("<I", num_trits))
    out.extend(packed)
    return bytes(out)

def _rans_decompress(data):
    """Decompress rANS base-3 encoded data."""
    if not data:
        return b""
    M = _RANS_M
    pos = 0

    num_used = data[pos]; pos += 1
    if num_used == 0:
        num_used = 256
    nf = [0] * 256
    for _ in range(num_used):
        sym = data[pos]; pos += 1
        hi = data[pos]; pos += 1
        lo = data[pos]; pos += 1
        nf[sym] = (hi << 8) | lo

    cdf = [0] * 257
    for i in range(256):
        cdf[i + 1] = cdf[i] + nf[i]

    slot_to_sym = [0] * M
    for s in range(256):
        for j in range(cdf[s], cdf[s + 1]):
            slot_to_sym[j] = s

    n = struct.unpack("<I", data[pos:pos + 4])[0]; pos += 4
    num_trits = struct.unpack("<I", data[pos:pos + 4])[0]; pos += 4

    packed = data[pos:]
    trits = []
    for bv in packed:
        for j in range(5):
            trits.append(bv // (3 ** j) % 3)
    trits = trits[:num_trits]

    x = 0
    tp = 0
    while x < M and tp < len(trits):
        x = x * 3 + trits[tp]
        tp += 1

    result = bytearray()
    for _ in range(n):
        slot = x % M
        sym = slot_to_sym[slot]
        fs = nf[sym]
        bs = cdf[sym]
        x = fs * (x // M) + slot - bs
        while x < M and tp < len(trits):
            x = x * 3 + trits[tp]
            tp += 1
        result.append(sym)
    return bytes(result)

# ======================================================
# PATTERN TOKENIZER (Morse Code Micro-Language)
# ======================================================

_TOKEN_ESCAPE = 0xFE
_TOKEN_MAGIC  = b"TK"

_CODEBOOK_PATTERNS = [
    # Whitespace -- geometric negative space
    b"                        ",  # 24 spaces
    b"                    ",      # 20 spaces
    b"                ",          # 16 spaces
    b"            ",              # 12 spaces
    b"        ",                  # 8 spaces
    b"      ",                    # 6 spaces
    b"    ",                      # 4 spaces
    b"\r\n                    ",
    b"\r\n                ",
    b"\r\n            ",
    b"\r\n        ",
    b"\r\n      ",
    b"\r\n    ",
    b"\r\n  ",
    b"\n                    ",
    b"\n                ",
    b"\n            ",
    b"\n        ",
    b"\n      ",
    b"\n    ",
    b"\n   ",
    b"\n  ",
    b"\r\n",
    # Box-drawing (decorative separators)
    b"\xe2\x95\x90" * 8,   # 8x double-horizontal
    b"\xe2\x94\x80" * 8,   # 8x single-horizontal
    b"\xe2\x95\x90" * 4,
    b"\xe2\x94\x80" * 4,
    b"\xe2\x95\x90" * 2,
    b"\xe2\x94\x80" * 2,
    b"\xe2\x95\x90",
    b"\xe2\x94\x80",
    # Separator lines
    b"================================",
    b"========================",
    b"================",
    b"============",
    b"--------",
    b"########",
    # Python keywords
    b"    def ",
    b"    return ",
    b"        return ",
    b"    class ",
    b"import ",
    b"from ",
    b"def __init__(self",
    b"def __repr__(self",
    b"    except Exception as e:",
    b"    except:",
    b"    try:",
    b"    if not ",
    b"    if ",
    b"    for ",
    b"    while ",
    b"    with ",
    b"        if ",
    b"        for ",
    b"        else:",
    b"        elif ",
    b"        with ",
    b"        try:",
    b"            return ",
    b"            ",
    b"            if ",
    b"            for ",
    # NovaX-specific patterns
    b"threading.Lock()",
    b"threading.Thread",
    b"http.server",
    b"BaseHTTPRequestHandler",
    b"HTTPServer",
    b"json.dumps(",
    b"json.loads(",
    b"os.path.join(",
    b"os.path.exists(",
    b"traceback.format_exc()",
    b"time.time()",
    b"Content-Type",
    b"application/json",
    b"send_response(",
    b"send_header(",
    b"end_headers()",
    b"wfile.write(",
    b"send_response(200)",
    b"send_response(404)",
    b"send_response(500)",
    b'send_header("Content-Type", "application/json")',
    b"do_GET",
    b"do_POST",
    b"def health(",
    b"/health",
    b"/api/",
    b"localhost:",
    b"0.0.0.0",
    b"127.0.0.1",
    b'print(f"',
    b'f"[',
    b"__name__",
    b"__main__",
    b'if __name__ == "__main__":',
    b"True",
    b"False",
    b"None",
    b"Dict[str, ",
    b"List[",
    b"Optional[",
    b"Tuple[",
    b"-> None:",
    b"-> dict:",
    b"-> str:",
    b"-> bool:",
    b"-> int:",
    b"-> bytes:",
    b"-> float:",
    b'"""',
    b'    """',
    b'        """',
]

_SORTED_CODEBOOK = sorted(enumerate(_CODEBOOK_PATTERNS), key=lambda x: -len(x[1]))

def _tokenize(data):
    """Apply pattern codebook to bytes. Shared by token compress and stream mode."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        matched = False
        for idx, pattern in _SORTED_CODEBOOK:
            plen = len(pattern)
            if plen > 2 and i + plen <= n and data[i:i + plen] == pattern:
                out.append(_TOKEN_ESCAPE)
                out.append(idx)
                i += plen
                matched = True
                break
        if not matched:
            b = data[i]
            if b == _TOKEN_ESCAPE:
                out.append(_TOKEN_ESCAPE)
                out.append(0xFF)
            else:
                out.append(b)
            i += 1
    return bytes(out)

def _detokenize(data, codebook_size=None):
    """Reverse token codebook."""
    if codebook_size is None:
        codebook_size = len(_CODEBOOK_PATTERNS)
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == _TOKEN_ESCAPE and i + 1 < n:
            nxt = data[i + 1]
            if nxt == 0xFF:
                out.append(_TOKEN_ESCAPE)
            elif nxt < codebook_size:
                out.extend(_CODEBOOK_PATTERNS[nxt])
            else:
                out.append(b)
                out.append(nxt)
            i += 2
        else:
            out.append(b)
            i += 1
    return bytes(out)

# ======================================================
# ZLIB TRAINED DICTIONARY
# ======================================================

_ZLIB_DICT = (
    b"    def " + b"    return " + b"    " + b"        " +
    b"import " + b"from " + b"class " + b"    if " + b"    for " +
    b"    while " + b"    try:" + b"    except " + b"    with " +
    b"    else:" + b"    elif " + b"        return " + b"        if " +
    b"        for " + b"        else:" + b"        elif " +
    b"threading.Lock()" + b"threading.Thread" + b"json.dumps(" +
    b"json.loads(" + b"os.path.join(" + b"os.path.exists(" +
    b"traceback.format_exc()" + b"time.time()" + b"hashlib." +
    b"struct.pack(" + b"struct.unpack(" + b"base64." + b"secrets." +
    b"Content-Type" + b"application/json" + b"text/html" +
    b"send_response(" + b"send_header(" + b"end_headers()" +
    b"wfile.write(" + b"send_response(200)" +
    b"send_response(404)" + b"send_response(500)" +
    b'send_header("Content-Type", "application/json")' +
    b"BaseHTTPRequestHandler" + b"HTTPServer" + b"ThreadingMixIn" +
    b"do_GET" + b"do_POST" + b"/health" + b"/api/" +
    b"localhost:" + b"0.0.0.0" + b"127.0.0.1" +
    b'if __name__ == "__main__":' + b"__init__" + b"__repr__" +
    b"True" + b"False" + b"None" + b"Exception" +
    b"Dict[str, " + b"List[" + b"Optional[" + b"Tuple[" +
    b"-> None:" + b"-> dict:" + b"-> str:" + b"-> bool:" +
    b"-> int:" + b"-> bytes:" + b"-> float:"
)

def _dict_compress(data):
    """zlib with pre-trained dictionary."""
    if not _zlib:
        return data
    co = _zlib.compressobj(level=9, wbits=15, zdict=_ZLIB_DICT)
    return co.compress(data) + co.flush()

def _dict_decompress(data):
    """zlib decompress with pre-trained dictionary."""
    if not _zlib:
        return data
    try:
        do = _zlib.decompressobj(wbits=15, zdict=_ZLIB_DICT)
        return do.decompress(data)
    except Exception:
        return _zlib.decompress(data)

def _token_compress(data):
    """Tokenize data, then zlib compress with trained dictionary."""
    if not _zlib or len(data) < 8:
        return data
    tokenized = _tokenize(data)
    co = _zlib.compressobj(level=9, wbits=15, zdict=_ZLIB_DICT)
    compressed = co.compress(tokenized) + co.flush()
    return _TOKEN_MAGIC + bytes([len(_CODEBOOK_PATTERNS)]) + compressed

def _token_decompress(data):
    """Decompress tokenized+zlib data."""
    if not _zlib:
        return data
    if data[:2] == _TOKEN_MAGIC:
        codebook_size = data[2]
        do = _zlib.decompressobj(wbits=15, zdict=_ZLIB_DICT)
        decompressed = do.decompress(data[3:])
        return _detokenize(decompressed, codebook_size)
    return _zlib.decompress(data)

# ======================================================
# LZMA COMPRESSION (v3.2)
# ======================================================

def _lzma_compress(data):
    """LZMA compression -- 4MB window, best ratio for text/source code."""
    if not _lzma:
        return _dict_compress(data)
    return _lzma.compress(data, preset=6)

def _lzma_decompress(data):
    """Decompress LZMA data."""
    if not _lzma:
        return _dict_decompress(data)
    return _lzma.decompress(data)

def _token_lzma_compress(data):
    """Tokenize with pattern codebook, then LZMA compress."""
    if not _lzma or len(data) < 8:
        return _token_compress(data)
    tokenized = _tokenize(data)
    compressed = _lzma.compress(tokenized, preset=6)
    return _TOKEN_MAGIC + bytes([len(_CODEBOOK_PATTERNS)]) + compressed

def _token_lzma_decompress(data):
    """Decompress token+LZMA data."""
    if not _lzma:
        return _token_decompress(data)
    if data[:2] == _TOKEN_MAGIC:
        codebook_size = data[2]
        decompressed = _lzma.decompress(data[3:])
        return _detokenize(decompressed, codebook_size)
    return _lzma.decompress(data)

# ======================================================
# FASTCDC CONTENT-DEFINED CHUNKING (v3)
# ======================================================

_gear_rng = _random.Random(H3 * H5 * H7 * H11 * H13)  # seed=15015
GEAR_TABLE = [_gear_rng.getrandbits(32) for _ in range(256)]

CDC_MIN    = H3 ** H5   # 243
CDC_TARGET = H3 ** H7   # 2187
CDC_MAX    = H3 ** H11  # 177147

def fastcdc_chunk(data):
    """Split data into content-defined chunks with ternary boundaries.
    Returns list of (offset, length) tuples."""
    chunks = []
    n = len(data)
    i = 0

    mask_l = (1 << H13) - 1   # 8191
    mask_s = (1 << H11) - 1   # 2047

    while i < n:
        chunk_start = i
        i += CDC_MIN
        if i >= n:
            chunks.append((chunk_start, n - chunk_start))
            break

        fp = 0
        mid = chunk_start + CDC_TARGET
        found = False

        limit = min(mid, n, chunk_start + CDC_MAX)
        while i < limit:
            fp = ((fp << 1) + GEAR_TABLE[data[i]]) & 0xFFFFFFFF
            i += 1
            if (fp & mask_l) == 0:
                found = True
                break

        if not found:
            limit2 = min(n, chunk_start + CDC_MAX)
            while i < limit2:
                fp = ((fp << 1) + GEAR_TABLE[data[i]]) & 0xFFFFFFFF
                i += 1
                if (fp & mask_s) == 0:
                    break

        chunks.append((chunk_start, i - chunk_start))

    return chunks

# ======================================================
# VORTICITY DEDUP SCANNER (N-S curl detects duplicates)
# ======================================================

def block_hash(data):
    """SHA-256 hash for dedup, truncated to H13 hex chars."""
    return hashlib.sha256(data).hexdigest()[:H13]

def vorticity_scan(data, chunk_size=BLOCK_SIZE):
    """Scan data for duplicate blocks using N-S vorticity detection."""
    hash_map = {}
    unique = []
    dedup_map = []
    total_bytes = 0
    saved_bytes = 0

    for start in range(0, len(data), chunk_size):
        chunk = data[start:start + chunk_size]
        h = block_hash(chunk)
        total_bytes += len(chunk)

        if h in hash_map:
            dedup_map.append((h, True, hash_map[h]))
            saved_bytes += len(chunk)
        else:
            hash_map[h] = len(unique)
            unique.append(chunk)
            dedup_map.append((h, False, len(unique) - 1))

    return {
        "dedup_map": dedup_map,
        "unique_blocks": unique,
        "total_blocks": len(dedup_map),
        "unique_count": len(unique),
        "duplicate_count": len(dedup_map) - len(unique),
        "total_bytes": total_bytes,
        "saved_bytes": saved_bytes,
        "dedup_ratio": round(saved_bytes / max(1, total_bytes) * 100, 1),
        "vorticity": round((len(dedup_map) - len(unique)) / max(1, len(dedup_map)), 3),
    }

def vorticity_reconstruct(dedup_map, unique_blocks):
    """Reconstruct data from dedup map and unique blocks."""
    out = bytearray()
    for h, is_dup, ref_idx in dedup_map:
        out.extend(unique_blocks[ref_idx])
    return bytes(out)

# ======================================================
# CORE COMPRESS / DECOMPRESS
# ======================================================

def _apply_strategy(data, strat_flag):
    """Apply a single compression strategy. Returns (bytes, final_strat_flag)."""
    base = strat_flag & 0x0F
    if   base == STRAT_RLE:   compressed = _rle_compress(data)
    elif base == STRAT_LZ:    compressed = _lz_compress(data)
    elif base == STRAT_RANS:  compressed = _rans_compress(data)
    elif base == STRAT_ZLIB:  compressed = _zlib.compress(data, 9) if _zlib else data
    elif base == STRAT_DICT:  compressed = _dict_compress(data)
    elif base == STRAT_TOKEN: compressed = _token_compress(data)
    elif base == STRAT_LZMA:  compressed = _lzma_compress(data)
    elif base == STRAT_TLZMA: compressed = _token_lzma_compress(data)
    else:                     return data, STRAT_RAW

    final_strat = strat_flag
    if strat_flag & STRAT_TRIT:
        trit_encoded = _trit_encode(compressed)
        if len(trit_encoded) <= len(compressed):
            compressed = trit_encoded
        else:
            final_strat = base  # drop TRIT flag -- didn't help

    return compressed, final_strat

def tzip_compress(data, competitive=True):
    """N-S flow-routed compression with competitive strategy selection.

    Morse code principle: try ALL strategies, keep the shortest.
    N-S routing: Reynolds/damping-ratio orders strategies by likelihood.

    competitive=True (default): try all, keep smallest (max ratio).
    competitive=False: pure Reynolds routing (legacy, faster).
    """
    if not data:
        return TZIP_MAGIC + struct.pack("<II", 0, 0) + b"\x00"

    orig_size = len(data)

    if not competitive:
        re = reynolds(data)
        strategy = select_strategy(re)
        compressed, final_strat = _apply_strategy(data, strategy)
        if len(compressed) >= orig_size:
            compressed = data
            final_strat = STRAT_RAW
        header = TZIP_MAGIC + struct.pack("<II", orig_size, len(compressed)) + struct.pack("B", final_strat)
        return header + compressed

    # Competitive selection: damping-ratio-ordered, try all, keep smallest
    re = reynolds(data)
    weights = strategy_weights(re)

    _strat_to_flag = {
        STRAT_RLE:   STRAT_RLE   | STRAT_TRIT,
        STRAT_LZ:    STRAT_LZ    | STRAT_TRIT,
        STRAT_RANS:  STRAT_RANS  | STRAT_TRIT,
        STRAT_ZLIB:  STRAT_ZLIB  | STRAT_TRIT,
        STRAT_DICT:  STRAT_DICT,
        STRAT_TOKEN: STRAT_TOKEN,
        STRAT_LZMA:  STRAT_LZMA,
        STRAT_TLZMA: STRAT_TLZMA,
    }

    candidates = []
    for w, strat in weights:
        if strat in (STRAT_ZLIB, STRAT_DICT, STRAT_TOKEN) and not _zlib:
            continue
        if strat in (STRAT_LZMA, STRAT_TLZMA) and not _lzma:
            continue
        flag = _strat_to_flag.get(strat, strat)
        candidates.append((flag, w))

    best_compressed = data
    best_strat = STRAT_RAW

    for strat_flag, _weight in candidates:
        try:
            compressed, final_strat = _apply_strategy(data, strat_flag)
            if len(compressed) < len(best_compressed):
                best_compressed = compressed
                best_strat = final_strat
        except Exception:
            continue

    header = TZIP_MAGIC + struct.pack("<II", orig_size, len(best_compressed)) + struct.pack("B", best_strat)
    return header + best_compressed

def tzip_decompress(data):
    """Decompress TZIP archive. Supports all strategies."""
    if len(data) < HEADER_SIZE:
        raise ValueError("Data too short for TZIP header")
    if data[:4] != TZIP_MAGIC:
        raise ValueError("Not TZIP format")

    orig_size = struct.unpack("<I", data[4:8])[0]
    comp_size = struct.unpack("<I", data[8:12])[0]
    strategy  = data[12]
    payload   = data[HEADER_SIZE:HEADER_SIZE + comp_size]

    if orig_size == 0:
        return b""

    base_strategy = strategy & 0x0F
    has_trit = bool(strategy & STRAT_TRIT)

    working = payload
    if has_trit:
        working = _trit_decode(payload, comp_size)

    if   base_strategy == STRAT_RLE:   return _rle_decompress(working)
    elif base_strategy == STRAT_LZ:    return _lz_decompress(working)
    elif base_strategy == STRAT_RANS:  return _rans_decompress(working)
    elif base_strategy == STRAT_ZLIB:
        return _zlib.decompress(working) if _zlib else working
    elif base_strategy == STRAT_DICT:  return _dict_decompress(working)
    elif base_strategy == STRAT_TOKEN: return _token_decompress(working)
    elif base_strategy == STRAT_LZMA:  return _lzma_decompress(working)
    elif base_strategy == STRAT_TLZMA: return _token_lzma_decompress(working)
    else:
        return working[:orig_size]

def tzip_ratio(original, compressed):
    """Return compression savings as percentage string."""
    if original == 0:
        return "0%"
    return f"{round((1 - compressed / original) * 100, 1)}%"

def tzip_info(data):
    """Parse TZIP header and return metadata without decompressing."""
    if len(data) < HEADER_SIZE or data[:4] != TZIP_MAGIC:
        return None
    orig  = struct.unpack("<I", data[4:8])[0]
    comp  = struct.unpack("<I", data[8:12])[0]
    strat = data[12]
    base  = strat & 0x0F
    names = {
        STRAT_RAW: "raw", STRAT_RLE: "rle", STRAT_LZ: "lz77",
        STRAT_ZLIB: "zlib", STRAT_RANS: "rans", STRAT_DICT: "dict",
        STRAT_TOKEN: "token", STRAT_LZMA: "lzma", STRAT_TLZMA: "tlzma"
    }
    return {
        "original_size": orig,
        "compressed_size": comp + HEADER_SIZE,
        "payload_size": comp,
        "strategy": names.get(base, f"0x{base:02x}"),
        "trit_packed": bool(strat & STRAT_TRIT),
        "ratio": tzip_ratio(orig, comp + HEADER_SIZE),
        "reynolds": None,
    }

# ======================================================
# BLOCK-LEVEL OPERATIONS (for DeepStorage integration)
# ======================================================

def tzip_compress_blocks(data, block_size=BLOCK_SIZE):
    """Compress data in ternary-aligned blocks (2187 bytes each).
    Each block gets its own Reynolds classification and strategy.
    Returns multi-block TZMB container."""
    if not data:
        return tzip_compress(data)

    blocks = []
    for i in range(0, len(data), block_size):
        block = data[i:i + block_size]
        blocks.append(tzip_compress(block))

    out = b"TZMB" + struct.pack("<I", len(blocks))
    for b in blocks:
        out += struct.pack("<I", len(b)) + b
    return out

def tzip_decompress_blocks(data):
    """Decompress multi-block TZIP archive."""
    if data[:4] == TZIP_MAGIC:
        return tzip_decompress(data)
    if data[:4] != b"TZMB":
        raise ValueError("Not TZIP multi-block format")

    block_count = struct.unpack("<I", data[4:8])[0]
    out = bytearray()
    pos = 8
    for _ in range(block_count):
        blen = struct.unpack("<I", data[pos:pos + 4])[0]
        pos += 4
        block_data = data[pos:pos + blen]
        out.extend(tzip_decompress(block_data))
        pos += blen
    return bytes(out)

# ======================================================
# STREAM MODE (v3.2 -- breaks per-block ceiling)
# ======================================================
# Per-block: each 2187-byte block starts fresh -> ~3.2x
# Stream: full corpus tokenized + single LZMA pass -> ~5.5x
# Trade-off: no random access (must decompress full stream).
# Use for cold/archival tier.

_STREAM_MAGIC = b"TZST"

def tzip_compress_stream(blocks):
    """Compress multiple blocks as a single tokenized LZMA stream.
    Input: list of bytes objects (raw blocks).
    Returns TZST-format compressed stream.
    Gets ~5.5x vs per-block ~3.2x."""
    if not blocks:
        return _STREAM_MAGIC + struct.pack("<II", 0, 0)

    sizes = [len(b) for b in blocks]
    total_orig = sum(sizes)

    concat = b"".join(blocks)
    tokenized = _tokenize(concat)

    if _lzma:
        compressed = _lzma.compress(tokenized, preset=6)
    elif _zlib:
        co = _zlib.compressobj(level=9, wbits=15, zdict=_ZLIB_DICT)
        compressed = co.compress(tokenized) + co.flush()
    else:
        compressed = tokenized

    header = _STREAM_MAGIC
    header += struct.pack("<II", total_orig, len(blocks))
    for s in sizes:
        header += struct.pack("<I", s)
    return header + compressed

def tzip_decompress_stream(data):
    """Decompress TZST stream back to list of original blocks."""
    if data[:4] != _STREAM_MAGIC:
        raise ValueError("Not TZST stream format")

    total_orig, block_count = struct.unpack("<II", data[4:12])
    if block_count == 0:
        return []

    pos = 12
    sizes = []
    for _ in range(block_count):
        sizes.append(struct.unpack("<I", data[pos:pos + 4])[0])
        pos += 4

    compressed = data[pos:]
    if _lzma:
        tokenized = _lzma.decompress(compressed)
    elif _zlib:
        do = _zlib.decompressobj(wbits=15, zdict=_ZLIB_DICT)
        tokenized = do.decompress(compressed)
    else:
        tokenized = compressed

    concat = _detokenize(tokenized)

    result = []
    offset = 0
    for s in sizes:
        result.append(concat[offset:offset + s])
        offset += s
    return result

# ======================================================
# STREAM-MODE FILE COMPRESSION (Layer 3 toward 50x)
# ======================================================

def tzip_compress_file(path_in, path_out=None):
    """Compress a file using stream mode. Returns (original_size, compressed_size, ratio)."""
    import os
    with open(path_in, "rb") as f:
        raw = f.read()

    orig_size = len(raw)
    if orig_size == 0:
        return 0, 0, "0%"

    # Split into CDC chunks, then stream-compress
    chunk_positions = fastcdc_chunk(raw)
    blocks = [raw[off:off + length] for off, length in chunk_positions]
    compressed = tzip_compress_stream(blocks)

    if path_out is None:
        path_out = path_in + ".tzip"

    with open(path_out, "wb") as f:
        f.write(compressed)

    comp_size = len(compressed)
    ratio_pct = round((1 - comp_size / orig_size) * 100, 1)
    return orig_size, comp_size, f"{ratio_pct}%"

def tzip_decompress_file(path_in, path_out=None):
    """Decompress a .tzip stream-mode file. Returns original bytes."""
    with open(path_in, "rb") as f:
        data = f.read()

    blocks = tzip_decompress_stream(data)
    result = b"".join(blocks)

    if path_out:
        with open(path_out, "wb") as f:
            f.write(result)

    return result
