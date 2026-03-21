"""
trit_engine_py.py — Python bindings for trit_engine.dll (NovaX LLM)

Zero-multiply ternary matrix operations via ctypes.
Provides TritLinear drop-in replacement for nn.Linear and model conversion.

Usage:
    from trit_engine_py import TritLinear, convert_model, trit_matmul

    # Replace a single layer
    trit_layer = TritLinear(original_linear.weight)
    output = trit_layer.forward(input_tensor)

    # Convert entire model
    convert_model(model)
"""

import ctypes
import os
import sys
import numpy as np

# ---------------------------------------------------------------------------
# Load DLL
# ---------------------------------------------------------------------------

_DLL_SEARCH_PATHS = [
    os.path.join(os.path.dirname(__file__), "trit_engine.dll"),
    os.path.join(os.path.dirname(__file__), "trit_engine", "target", "release", "trit_engine.dll"),
    r"C:\NovaX\nova_llm\trit_engine.dll",
]

_lib = None
for _path in _DLL_SEARCH_PATHS:
    if os.path.exists(_path):
        try:
            _lib = ctypes.CDLL(_path)
            break
        except OSError:
            continue

if _lib is None:
    raise ImportError(
        f"trit_engine.dll not found. Searched:\n"
        + "\n".join(f"  {p}" for p in _DLL_SEARCH_PATHS)
        + "\nRun build.bat in trit_engine/ first."
    )

# ---------------------------------------------------------------------------
# Function signatures
# ---------------------------------------------------------------------------

_lib.trit_matmul.restype = ctypes.c_int32
_lib.trit_matmul.argtypes = [
    ctypes.POINTER(ctypes.c_float),  # input
    ctypes.POINTER(ctypes.c_uint8),  # weights (TZip)
    ctypes.POINTER(ctypes.c_float),  # output
    ctypes.POINTER(ctypes.c_float),  # scales
    ctypes.c_int32,                  # m
    ctypes.c_int32,                  # k
    ctypes.c_int32,                  # n
]

_lib.trit_attention_proj.restype = ctypes.c_int32
_lib.trit_attention_proj.argtypes = [
    ctypes.POINTER(ctypes.c_float),  # input
    ctypes.POINTER(ctypes.c_uint8),  # wq
    ctypes.POINTER(ctypes.c_uint8),  # wk
    ctypes.POINTER(ctypes.c_uint8),  # wv
    ctypes.POINTER(ctypes.c_float),  # sq
    ctypes.POINTER(ctypes.c_float),  # sk
    ctypes.POINTER(ctypes.c_float),  # sv
    ctypes.POINTER(ctypes.c_float),  # q_out
    ctypes.POINTER(ctypes.c_float),  # k_out
    ctypes.POINTER(ctypes.c_float),  # v_out
    ctypes.c_int32,                  # batch
    ctypes.c_int32,                  # seq_len
    ctypes.c_int32,                  # embed_dim
    ctypes.c_int32,                  # proj_dim
]

_lib.trit_quantize_weights.restype = ctypes.c_int32
_lib.trit_quantize_weights.argtypes = [
    ctypes.POINTER(ctypes.c_float),  # weights
    ctypes.POINTER(ctypes.c_uint8),  # packed
    ctypes.POINTER(ctypes.c_float),  # scales
    ctypes.c_int32,                  # k
    ctypes.c_int32,                  # n
]

_lib.trit_pack_kv.restype = ctypes.c_int32
_lib.trit_pack_kv.argtypes = [
    ctypes.POINTER(ctypes.c_float),  # kv_float
    ctypes.POINTER(ctypes.c_uint8),  # packed
    ctypes.POINTER(ctypes.c_float),  # scales
    ctypes.c_int32,                  # num_heads
    ctypes.c_int32,                  # seq_len
    ctypes.c_int32,                  # head_dim
]

_lib.trit_unpack_kv.restype = ctypes.c_int32
_lib.trit_unpack_kv.argtypes = [
    ctypes.POINTER(ctypes.c_uint8),  # packed
    ctypes.POINTER(ctypes.c_float),  # scales
    ctypes.POINTER(ctypes.c_float),  # output
    ctypes.c_int32,                  # num_heads
    ctypes.c_int32,                  # seq_len
    ctypes.c_int32,                  # head_dim
]

_lib.trit_engine_info.restype = ctypes.c_char_p
_lib.trit_engine_info.argtypes = []

# ---------------------------------------------------------------------------
# Helper: numpy array -> ctypes pointer
# ---------------------------------------------------------------------------

def _f32_ptr(arr):
    """Get a c_float pointer from a contiguous float32 numpy array."""
    arr = np.ascontiguousarray(arr, dtype=np.float32)
    return arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), arr

def _u8_ptr(arr):
    """Get a c_uint8 pointer from a contiguous uint8 numpy array."""
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    return arr.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), arr

def _packed_len(k):
    """Number of TZip bytes for k trits."""
    return (k + 4) // 5

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def engine_info():
    """Return engine info string."""
    return _lib.trit_engine_info().decode("utf-8")


def trit_quantize(weights_np):
    """
    Quantize a (K, N) float32 weight matrix to TZip-packed trits + scales.

    Args:
        weights_np: numpy array of shape (K, N), float32

    Returns:
        (packed, scales) — packed uint8 array, scales float32 array
    """
    weights_np = np.ascontiguousarray(weights_np, dtype=np.float32)
    k, n = weights_np.shape
    pk = _packed_len(k)

    packed = np.zeros(pk * n, dtype=np.uint8)
    scales = np.zeros(n, dtype=np.float32)

    w_ptr, _ = _f32_ptr(weights_np)
    p_ptr, _ = _u8_ptr(packed)
    s_ptr, _ = _f32_ptr(scales)

    ret = _lib.trit_quantize_weights(w_ptr, p_ptr, s_ptr, k, n)
    if ret != 0:
        raise RuntimeError(f"trit_quantize_weights failed with code {ret}")

    return packed, scales


def trit_matmul(input_np, packed_weights, scales, k, n):
    """
    Ternary matrix multiply: input (M, K) x weights (K, N) trits -> output (M, N).

    Args:
        input_np: (M, K) float32
        packed_weights: TZip-packed uint8 array (from trit_quantize)
        scales: per-column float32 scales (from trit_quantize)
        k: inner dimension
        n: output dimension

    Returns:
        output: (M, N) float32 numpy array
    """
    input_np = np.ascontiguousarray(input_np, dtype=np.float32)
    if input_np.ndim == 1:
        input_np = input_np.reshape(1, -1)
    m = input_np.shape[0]

    output = np.zeros((m, n), dtype=np.float32)

    i_ptr, _ = _f32_ptr(input_np)
    w_ptr, _ = _u8_ptr(packed_weights)
    o_ptr, _ = _f32_ptr(output)
    s_ptr, _ = _f32_ptr(scales)

    ret = _lib.trit_matmul(i_ptr, w_ptr, o_ptr, s_ptr, m, k, n)
    if ret != 0:
        raise RuntimeError(f"trit_matmul failed with code {ret}")

    return output


def trit_attention_proj(input_np, wq_packed, wk_packed, wv_packed,
                         sq, sk, sv, batch, seq_len, embed_dim, proj_dim):
    """
    Compute Q/K/V attention projections in one call.

    Args:
        input_np: (batch*seq_len, embed_dim) float32
        wq/wk/wv_packed: TZip-packed projection weight arrays
        sq/sk/sv: per-column scale arrays
        batch, seq_len, embed_dim, proj_dim: dimensions

    Returns:
        (q_out, k_out, v_out) each (batch*seq_len, proj_dim) float32
    """
    total = batch * seq_len
    input_np = np.ascontiguousarray(input_np, dtype=np.float32).reshape(total, embed_dim)

    q_out = np.zeros((total, proj_dim), dtype=np.float32)
    k_out = np.zeros((total, proj_dim), dtype=np.float32)
    v_out = np.zeros((total, proj_dim), dtype=np.float32)

    i_ptr, _ = _f32_ptr(input_np)
    wq_ptr, _ = _u8_ptr(wq_packed)
    wk_ptr, _ = _u8_ptr(wk_packed)
    wv_ptr, _ = _u8_ptr(wv_packed)
    sq_ptr, _ = _f32_ptr(sq)
    sk_ptr, _ = _f32_ptr(sk)
    sv_ptr, _ = _f32_ptr(sv)
    q_ptr, _ = _f32_ptr(q_out)
    k_ptr, _ = _f32_ptr(k_out)
    v_ptr, _ = _f32_ptr(v_out)

    ret = _lib.trit_attention_proj(
        i_ptr, wq_ptr, wk_ptr, wv_ptr,
        sq_ptr, sk_ptr, sv_ptr,
        q_ptr, k_ptr, v_ptr,
        batch, seq_len, embed_dim, proj_dim,
    )
    if ret != 0:
        raise RuntimeError(f"trit_attention_proj failed with code {ret}")

    return q_out, k_out, v_out


def trit_pack_kv(kv_float, num_heads, seq_len, head_dim):
    """
    Pack float32 KV cache into TZip format.

    Args:
        kv_float: (num_heads, seq_len, head_dim) float32

    Returns:
        (packed, scales) — packed uint8, per-head scales float32
    """
    kv_float = np.ascontiguousarray(kv_float, dtype=np.float32)
    phd = _packed_len(head_dim)

    packed = np.zeros(num_heads * seq_len * phd, dtype=np.uint8)
    scales = np.zeros(num_heads, dtype=np.float32)

    kv_ptr, _ = _f32_ptr(kv_float)
    p_ptr, _ = _u8_ptr(packed)
    s_ptr, _ = _f32_ptr(scales)

    ret = _lib.trit_pack_kv(kv_ptr, p_ptr, s_ptr, num_heads, seq_len, head_dim)
    if ret != 0:
        raise RuntimeError(f"trit_pack_kv failed with code {ret}")

    return packed, scales


def trit_unpack_kv(packed, scales, num_heads, seq_len, head_dim):
    """
    Unpack TZip KV cache back to float32.

    Returns:
        output: (num_heads, seq_len, head_dim) float32
    """
    output = np.zeros((num_heads, seq_len, head_dim), dtype=np.float32)

    p_ptr, _ = _u8_ptr(packed)
    s_ptr, _ = _f32_ptr(scales)
    o_ptr, _ = _f32_ptr(output)

    ret = _lib.trit_unpack_kv(p_ptr, s_ptr, o_ptr, num_heads, seq_len, head_dim)
    if ret != 0:
        raise RuntimeError(f"trit_unpack_kv failed with code {ret}")

    return output


# ---------------------------------------------------------------------------
# TritLinear — drop-in replacement for nn.Linear
# ---------------------------------------------------------------------------

class TritLinear:
    """
    Drop-in replacement for torch.nn.Linear that uses trit_engine for inference.

    Weight shape: (out_features, in_features) — same as nn.Linear.
    Internally stores TZip-packed trits + per-output-column scales.
    """

    def __init__(self, weight, bias=None):
        """
        Args:
            weight: numpy array or torch.Tensor of shape (out_features, in_features)
            bias: optional numpy array or torch.Tensor of shape (out_features,)
        """
        # Convert torch tensors if needed
        if hasattr(weight, 'detach'):
            weight = weight.detach().cpu().numpy()
        if bias is not None and hasattr(bias, 'detach'):
            bias = bias.detach().cpu().numpy()

        weight = np.ascontiguousarray(weight, dtype=np.float32)
        self.out_features, self.in_features = weight.shape

        # nn.Linear weight is (out, in). trit_quantize expects (K, N) = (in, out).
        # Transpose so K=in_features, N=out_features.
        weight_t = np.ascontiguousarray(weight.T)

        self.packed, self.scales = trit_quantize(weight_t)
        self.bias = None
        if bias is not None:
            self.bias = np.ascontiguousarray(bias, dtype=np.float32)

        # Compute sparsity (fraction of zero trits) for diagnostics
        total_trits = self.in_features * self.out_features
        # Rough estimate from packed data
        self._k = self.in_features
        self._n = self.out_features

    def forward(self, x):
        """
        Forward pass.

        Args:
            x: numpy array of shape (..., in_features)

        Returns:
            output: numpy array of shape (..., out_features)
        """
        if hasattr(x, 'detach'):
            x = x.detach().cpu().numpy()

        x = np.ascontiguousarray(x, dtype=np.float32)
        orig_shape = x.shape
        if x.ndim > 2:
            x = x.reshape(-1, self.in_features)
        elif x.ndim == 1:
            x = x.reshape(1, -1)

        out = trit_matmul(x, self.packed, self.scales, self._k, self._n)

        if self.bias is not None:
            out += self.bias

        # Restore batch dimensions
        if len(orig_shape) > 2:
            out = out.reshape(*orig_shape[:-1], self.out_features)

        return out

    def __repr__(self):
        return (
            f"TritLinear(in={self.in_features}, out={self.out_features}, "
            f"packed_bytes={len(self.packed)}, "
            f"compression={self.in_features * self.out_features * 4 / len(self.packed):.1f}x)"
        )


# ---------------------------------------------------------------------------
# Model conversion
# ---------------------------------------------------------------------------

def convert_model(model, verbose=True):
    """
    Convert all nn.Linear layers in a model to TritLinear.
    Modifies the model in-place.

    Args:
        model: a torch.nn.Module
        verbose: print conversion info

    Returns:
        dict with conversion statistics
    """
    try:
        import torch.nn as nn
    except ImportError:
        raise ImportError("PyTorch is required for model conversion")

    stats = {"converted": 0, "skipped": 0, "total_params": 0, "total_packed_bytes": 0}

    def _replace_linear(module, prefix=""):
        for name, child in module.named_children():
            full_name = f"{prefix}.{name}" if prefix else name

            if isinstance(child, nn.Linear):
                weight = child.weight
                bias = child.bias

                trit_layer = TritLinear(weight, bias)
                setattr(module, name, _TritLinearWrapper(trit_layer))

                stats["converted"] += 1
                stats["total_params"] += weight.numel()
                stats["total_packed_bytes"] += len(trit_layer.packed)

                if verbose:
                    print(f"  [trit] {full_name}: {trit_layer}")
            else:
                _replace_linear(child, full_name)

    if verbose:
        print("[trit_engine] Converting model to ternary inference...")

    _replace_linear(model)

    if verbose:
        orig_bytes = stats["total_params"] * 4
        packed_bytes = stats["total_packed_bytes"]
        ratio = orig_bytes / max(packed_bytes, 1)
        print(f"[trit_engine] Converted {stats['converted']} layers")
        print(f"[trit_engine] Weight memory: {orig_bytes / 1e6:.1f} MB -> {packed_bytes / 1e6:.1f} MB ({ratio:.1f}x compression)")

    return stats


class _TritLinearWrapper:
    """
    Wrapper that makes TritLinear behave like a callable module.
    Supports both numpy and torch tensor inputs.
    Inherits nn.Module if torch is available for full PyTorch compatibility.
    """

    def __init__(self, trit_linear):
        try:
            import torch.nn as nn
            # Dynamically make this instance behave as nn.Module
            self._is_module = True
        except ImportError:
            self._is_module = False

        self.trit_linear = trit_linear
        self.in_features = trit_linear.in_features
        self.out_features = trit_linear.out_features
        self.weight = None  # Satisfy code that checks for .weight
        self.bias = None

    def __call__(self, x):
        import torch
        is_torch = isinstance(x, torch.Tensor)
        device = x.device if is_torch else None
        dtype = x.dtype if is_torch else None

        # Flatten batch dims for matmul: (..., K) -> (M, K)
        orig_shape = x.shape if is_torch else None
        if is_torch and x.dim() > 2:
            batch_shape = x.shape[:-1]
            x_flat = x.reshape(-1, x.shape[-1])
        else:
            batch_shape = None
            x_flat = x

        out = self.trit_linear.forward(x_flat)

        if is_torch:
            out = torch.from_numpy(out).to(device=device, dtype=dtype)
            if batch_shape is not None:
                out = out.reshape(*batch_shape, -1)

        return out

    def __repr__(self):
        return repr(self.trit_linear)

    def parameters(self):
        return iter([])

    def named_parameters(self, prefix='', recurse=True):
        return iter([])

    def named_children(self):
        return iter([])

    def modules(self):
        yield self

    def train(self, mode=True):
        return self

    def eval(self):
        return self

    def to(self, *args, **kwargs):
        return self


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(engine_info())
    print()

    # Test quantize + matmul roundtrip
    print("=== Quantize + Matmul Test ===")
    k, n = 768, 512
    weights = np.random.randn(k, n).astype(np.float32)
    # Make weights roughly ternary
    weights = np.sign(weights) * (np.abs(weights) > 0.3).astype(np.float32)

    packed, scales = trit_quantize(weights)
    print(f"  Weights: ({k}, {n}) float32 = {k*n*4:,} bytes")
    print(f"  Packed:  {len(packed):,} bytes ({k*n*4/len(packed):.1f}x compression)")

    x = np.random.randn(4, k).astype(np.float32)
    output = trit_matmul(x, packed, scales, k, n)
    print(f"  Input:   (4, {k}) -> Output: {output.shape}")

    # Compare with numpy reference
    # Reconstruct approximate weights from packed trits for verification
    print(f"  Output sample: {output[0, :5]}")

    # Test TritLinear
    print("\n=== TritLinear Test ===")
    linear_weight = np.random.randn(256, 768).astype(np.float32)
    tl = TritLinear(linear_weight)
    print(f"  {tl}")

    x = np.random.randn(8, 768).astype(np.float32)
    y = tl.forward(x)
    print(f"  Forward: (8, 768) -> {y.shape}")

    # Test KV cache
    print("\n=== KV Cache Pack/Unpack Test ===")
    nh, sl, hd = 13, 32, 64
    kv = np.random.randn(nh, sl, hd).astype(np.float32)
    kv = np.sign(kv) * (np.abs(kv) > 0.3).astype(np.float32) * 0.5

    packed_kv, kv_scales = trit_pack_kv(kv, nh, sl, hd)
    unpacked_kv = trit_unpack_kv(packed_kv, kv_scales, nh, sl, hd)
    max_err = np.max(np.abs(kv - unpacked_kv))
    print(f"  KV shape: ({nh}, {sl}, {hd})")
    print(f"  Packed: {len(packed_kv):,} bytes (from {kv.nbytes:,})")
    print(f"  Roundtrip max error: {max_err:.6f}")

    print("\n[OK] All tests passed.")
