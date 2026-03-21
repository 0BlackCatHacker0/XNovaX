//! trit_engine — Zero-multiply ternary matrix operations for NovaX LLM
//!
//! Ternary weights {-1, 0, +1} replace float32 matmul with add/subtract/skip.
//! TZip packing: 5 trits per byte (3^5 = 243 states in a u8).
//! LUT decode: 243-entry table stays in L1 cache (1.2 KB).
//!
//! Model constants:
//!   embed_dim=768, num_heads=13, head_dim=64, num_layers=13, vocab=32768

mod trit_lut;

use rayon::prelude::*;
use std::os::raw::c_char;
use std::slice;

use trit_lut::TRIT_LUT;

// ---------------------------------------------------------------------------
// Send/Sync wrappers for raw pointers (safe because we guarantee no aliasing)
// ---------------------------------------------------------------------------

#[derive(Copy, Clone)]
struct SendPtr<T>(*mut T);
unsafe impl<T> Send for SendPtr<T> {}
unsafe impl<T> Sync for SendPtr<T> {}

impl<T> SendPtr<T> {
    fn new(p: *mut T) -> Self { SendPtr(p) }
    fn ptr(self) -> *mut T { self.0 }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Number of packed bytes needed for `k` trits.
#[inline(always)]
fn packed_len(k: usize) -> usize {
    (k + 4) / 5
}

/// Core inner product: one output element.
/// `input_row` has length `k`, `weight_col_packed` has length `ceil(k/5)`.
/// Returns the raw accumulator (before scaling).
#[inline]
fn trit_dot(input_row: &[f32], weight_col_packed: &[u8], k: usize) -> f32 {
    let full_chunks = k / 5;
    let remainder = k % 5;
    let mut acc: f32 = 0.0;

    // Process full 5-trit chunks
    for chunk_idx in 0..full_chunks {
        let byte_val = weight_col_packed[chunk_idx] as usize;
        // Safety: byte_val < 243 guaranteed by valid TZip encoding
        let trits = unsafe { TRIT_LUT.get_unchecked(byte_val) };
        let base = chunk_idx * 5;

        // Unrolled: 5 trits per byte. Use trit as i8 multiplier — no branch.
        // Compiler will auto-vectorize with -O3.
        unsafe {
            acc += (*trits.get_unchecked(0) as f32) * *input_row.get_unchecked(base);
            acc += (*trits.get_unchecked(1) as f32) * *input_row.get_unchecked(base + 1);
            acc += (*trits.get_unchecked(2) as f32) * *input_row.get_unchecked(base + 2);
            acc += (*trits.get_unchecked(3) as f32) * *input_row.get_unchecked(base + 3);
            acc += (*trits.get_unchecked(4) as f32) * *input_row.get_unchecked(base + 4);
        }
    }

    // Process remaining trits
    if remainder > 0 {
        let byte_val = weight_col_packed[full_chunks] as usize;
        let trits = unsafe { TRIT_LUT.get_unchecked(byte_val) };
        let base = full_chunks * 5;
        for r in 0..remainder {
            unsafe {
                acc += (*trits.get_unchecked(r) as f32) * *input_row.get_unchecked(base + r);
            }
        }
    }

    acc
}

// ---------------------------------------------------------------------------
// trit_matmul  —  input (M,K) x weights (K,N) trits -> output (M,N)
// ---------------------------------------------------------------------------
// Weight layout (TZip, column-major packing):
//   For column j, the packed bytes are at offset j * packed_len(K).
//   Each packed byte encodes 5 consecutive trits along the K dimension.

/// Core ternary matrix multiply.
/// Returns 0 on success, -1 on null pointer.
#[no_mangle]
pub extern "C" fn trit_matmul(
    input: *const f32,
    weights: *const u8,
    output: *mut f32,
    scales: *const f32,
    m: i32,
    k: i32,
    n: i32,
) -> i32 {
    if input.is_null() || weights.is_null() || output.is_null() || scales.is_null() {
        return -1;
    }

    let m = m as usize;
    let k = k as usize;
    let n = n as usize;
    let pk = packed_len(k);

    let input_slice = unsafe { slice::from_raw_parts(input, m * k) };
    let weights_slice = unsafe { slice::from_raw_parts(weights, pk * n) };
    let scales_slice = unsafe { slice::from_raw_parts(scales, n) };
    let output_slice = unsafe { slice::from_raw_parts_mut(output, m * n) };

    // Parallel over rows (M dimension) — each row is independent
    output_slice
        .par_chunks_mut(n)
        .enumerate()
        .for_each(|(row_idx, out_row)| {
            let input_row = &input_slice[row_idx * k..(row_idx + 1) * k];

            for col_idx in 0..n {
                let weight_col = &weights_slice[col_idx * pk..(col_idx + 1) * pk];
                let raw = trit_dot(input_row, weight_col, k);
                out_row[col_idx] = raw * scales_slice[col_idx];
            }
        });

    0
}

// ---------------------------------------------------------------------------
// trit_attention_proj  —  Q/K/V projections in one call
// ---------------------------------------------------------------------------

/// Batch attention projections: input (B*T, embed_dim) -> Q/K/V each (B*T, proj_dim).
/// Fuses three trit_matmul calls with shared input for cache efficiency.
#[no_mangle]
pub extern "C" fn trit_attention_proj(
    input: *const f32,
    wq: *const u8,
    wk: *const u8,
    wv: *const u8,
    sq: *const f32,
    sk: *const f32,
    sv: *const f32,
    q_out: *mut f32,
    k_out: *mut f32,
    v_out: *mut f32,
    batch: i32,
    seq_len: i32,
    embed_dim: i32,
    proj_dim: i32,
) -> i32 {
    if input.is_null()
        || wq.is_null() || wk.is_null() || wv.is_null()
        || sq.is_null() || sk.is_null() || sv.is_null()
        || q_out.is_null() || k_out.is_null() || v_out.is_null()
    {
        return -1;
    }

    let total_tokens = (batch * seq_len) as usize;
    let ed = embed_dim as usize;
    let pd = proj_dim as usize;
    let pk = packed_len(ed);

    let input_slice = unsafe { slice::from_raw_parts(input, total_tokens * ed) };
    let wq_slice = unsafe { slice::from_raw_parts(wq, pk * pd) };
    let wk_slice = unsafe { slice::from_raw_parts(wk, pk * pd) };
    let wv_slice = unsafe { slice::from_raw_parts(wv, pk * pd) };
    let sq_slice = unsafe { slice::from_raw_parts(sq, pd) };
    let sk_slice = unsafe { slice::from_raw_parts(sk, pd) };
    let sv_slice = unsafe { slice::from_raw_parts(sv, pd) };

    // Wrap output pointers for Send+Sync
    let q_ptr = SendPtr::new(q_out);
    let k_ptr = SendPtr::new(k_out);
    let v_ptr = SendPtr::new(v_out);

    // Parallel over tokens — each token writes to non-overlapping output regions
    (0..total_tokens).into_par_iter().for_each(|t| {
        let inp_row = &input_slice[t * ed..(t + 1) * ed];

        // Q — each token writes to q_out[t*pd .. (t+1)*pd], no overlap
        let q_row = unsafe { slice::from_raw_parts_mut(q_ptr.ptr().add(t * pd), pd) };
        for j in 0..pd {
            let col = &wq_slice[j * pk..(j + 1) * pk];
            q_row[j] = trit_dot(inp_row, col, ed) * sq_slice[j];
        }

        // K
        let k_row = unsafe { slice::from_raw_parts_mut(k_ptr.ptr().add(t * pd), pd) };
        for j in 0..pd {
            let col = &wk_slice[j * pk..(j + 1) * pk];
            k_row[j] = trit_dot(inp_row, col, ed) * sk_slice[j];
        }

        // V
        let v_row = unsafe { slice::from_raw_parts_mut(v_ptr.ptr().add(t * pd), pd) };
        for j in 0..pd {
            let col = &wv_slice[j * pk..(j + 1) * pk];
            v_row[j] = trit_dot(inp_row, col, ed) * sv_slice[j];
        }
    });

    0
}

// ---------------------------------------------------------------------------
// trit_quantize_weights  —  float32 -> TZip + scales
// ---------------------------------------------------------------------------

/// Quantize a (K, N) float32 weight matrix into TZip-packed trits + per-column scales.
/// Threshold strategy: for each column, scale = max(|w|). If |w/scale| > 0.5 -> +1 or -1, else 0.
/// `packed` must have room for ceil(K/5) * N bytes.
/// `scales` must have room for N floats.
#[no_mangle]
pub extern "C" fn trit_quantize_weights(
    weights: *const f32,
    packed: *mut u8,
    scales: *mut f32,
    k: i32,
    n: i32,
) -> i32 {
    if weights.is_null() || packed.is_null() || scales.is_null() {
        return -1;
    }

    let k = k as usize;
    let n = n as usize;
    let pk = packed_len(k);

    let w = unsafe { slice::from_raw_parts(weights, k * n) };
    let p = unsafe { slice::from_raw_parts_mut(packed, pk * n) };

    // Wrap scales pointer for Send+Sync (each column writes unique index)
    let s_ptr = SendPtr::new(scales);

    // Parallel over columns
    p.par_chunks_mut(pk)
        .enumerate()
        .for_each(|(col, col_packed)| {
            // Find column scale
            let mut max_abs: f32 = 0.0;
            for row in 0..k {
                let val = w[row * n + col].abs();
                if val > max_abs {
                    max_abs = val;
                }
            }

            // Write scale (avoid division by zero)
            let scale = if max_abs < 1e-10 { 1.0 } else { max_abs };
            unsafe { *s_ptr.ptr().add(col) = scale };

            let inv_scale = 1.0 / scale;

            // Quantize and pack
            let mut trit_buf = [0i8; 5];
            let full_chunks = k / 5;
            let remainder = k % 5;

            for chunk in 0..full_chunks {
                for t in 0..5 {
                    let row = chunk * 5 + t;
                    let normalized = w[row * n + col] * inv_scale;
                    trit_buf[t] = if normalized > 0.5 {
                        1
                    } else if normalized < -0.5 {
                        -1
                    } else {
                        0
                    };
                }
                col_packed[chunk] = trit_lut::encode_trits(&trit_buf);
            }

            if remainder > 0 {
                trit_buf = [0i8; 5]; // zero padding
                for t in 0..remainder {
                    let row = full_chunks * 5 + t;
                    let normalized = w[row * n + col] * inv_scale;
                    trit_buf[t] = if normalized > 0.5 {
                        1
                    } else if normalized < -0.5 {
                        -1
                    } else {
                        0
                    };
                }
                col_packed[full_chunks] = trit_lut::encode_trits(&trit_buf);
            }
        });

    0
}

// ---------------------------------------------------------------------------
// KV cache packing / unpacking
// ---------------------------------------------------------------------------

/// Pack float32 KV cache into TZip format.
/// Input shape: (num_heads, seq_len, head_dim) — contiguous row-major.
/// Packed output: for each head, for each position, ceil(head_dim/5) bytes.
/// Scales: one per head (uniform quantization per head).
#[no_mangle]
pub extern "C" fn trit_pack_kv(
    kv_float: *const f32,
    packed: *mut u8,
    scales: *mut f32,
    num_heads: i32,
    seq_len: i32,
    head_dim: i32,
) -> i32 {
    if kv_float.is_null() || packed.is_null() || scales.is_null() {
        return -1;
    }

    let nh = num_heads as usize;
    let sl = seq_len as usize;
    let hd = head_dim as usize;
    let phd = packed_len(hd);

    let float_data = unsafe { slice::from_raw_parts(kv_float, nh * sl * hd) };

    // Wrap output pointers
    let pack_ptr = SendPtr::new(packed);
    let scale_ptr = SendPtr::new(scales);

    // Parallel over heads — each head writes to non-overlapping regions
    (0..nh).into_par_iter().for_each(|h| {
        let head_offset = h * sl * hd;
        let head_floats = &float_data[head_offset..head_offset + sl * hd];

        // Find max abs across entire head
        let mut max_abs: f32 = 0.0;
        for &v in head_floats {
            let a = v.abs();
            if a > max_abs {
                max_abs = a;
            }
        }

        let scale = if max_abs < 1e-10 { 1.0 } else { max_abs };
        unsafe { *scale_ptr.ptr().add(h) = scale };
        let inv_scale = 1.0 / scale;

        let pack_head_offset = h * sl * phd;

        for pos in 0..sl {
            let float_row = &head_floats[pos * hd..(pos + 1) * hd];
            let pack_row_offset = pack_head_offset + pos * phd;

            let full_chunks = hd / 5;
            let remainder = hd % 5;

            for chunk in 0..full_chunks {
                let mut trit_buf = [0i8; 5];
                for t in 0..5 {
                    let normalized = float_row[chunk * 5 + t] * inv_scale;
                    trit_buf[t] = if normalized > 0.5 {
                        1
                    } else if normalized < -0.5 {
                        -1
                    } else {
                        0
                    };
                }
                unsafe { *pack_ptr.ptr().add(pack_row_offset + chunk) = trit_lut::encode_trits(&trit_buf) };
            }

            if remainder > 0 {
                let mut trit_buf = [0i8; 5];
                for t in 0..remainder {
                    let normalized = float_row[full_chunks * 5 + t] * inv_scale;
                    trit_buf[t] = if normalized > 0.5 {
                        1
                    } else if normalized < -0.5 {
                        -1
                    } else {
                        0
                    };
                }
                unsafe { *pack_ptr.ptr().add(pack_row_offset + full_chunks) = trit_lut::encode_trits(&trit_buf) };
            }
        }
    });

    0
}

/// Unpack TZip KV cache back to float32.
#[no_mangle]
pub extern "C" fn trit_unpack_kv(
    packed: *const u8,
    scales: *const f32,
    output: *mut f32,
    num_heads: i32,
    seq_len: i32,
    head_dim: i32,
) -> i32 {
    if packed.is_null() || scales.is_null() || output.is_null() {
        return -1;
    }

    let nh = num_heads as usize;
    let sl = seq_len as usize;
    let hd = head_dim as usize;
    let phd = packed_len(hd);

    let pack_data = unsafe { slice::from_raw_parts(packed, nh * sl * phd) };
    let scale_data = unsafe { slice::from_raw_parts(scales, nh) };

    // Wrap output pointer
    let out_ptr = SendPtr::new(output);

    (0..nh).into_par_iter().for_each(|h| {
        let scale = scale_data[h];
        let pack_head_offset = h * sl * phd;
        let out_head_offset = h * sl * hd;

        for pos in 0..sl {
            let pack_row = &pack_data[pack_head_offset + pos * phd..];
            let out_offset = out_head_offset + pos * hd;

            let full_chunks = hd / 5;
            let remainder = hd % 5;

            for chunk in 0..full_chunks {
                let byte_val = pack_row[chunk] as usize;
                let trits = unsafe { TRIT_LUT.get_unchecked(byte_val) };
                let base = out_offset + chunk * 5;
                unsafe {
                    *out_ptr.ptr().add(base) = (trits[0] as f32) * scale;
                    *out_ptr.ptr().add(base + 1) = (trits[1] as f32) * scale;
                    *out_ptr.ptr().add(base + 2) = (trits[2] as f32) * scale;
                    *out_ptr.ptr().add(base + 3) = (trits[3] as f32) * scale;
                    *out_ptr.ptr().add(base + 4) = (trits[4] as f32) * scale;
                }
            }

            if remainder > 0 {
                let byte_val = pack_row[full_chunks] as usize;
                let trits = unsafe { TRIT_LUT.get_unchecked(byte_val) };
                let base = out_offset + full_chunks * 5;
                for r in 0..remainder {
                    unsafe {
                        *out_ptr.ptr().add(base + r) = (trits[r] as f32) * scale;
                    }
                }
            }
        }
    });

    0
}

// ---------------------------------------------------------------------------
// Engine info
// ---------------------------------------------------------------------------

static ENGINE_INFO: &[u8] = b"trit_engine v1.0.0 | NovaX LLM | zero-multiply ternary matmul | TZip(3^5=243) LUT decode | rayon parallel | embed=768 heads=13 layers=13 vocab=32768\0";

/// Returns a static C string with engine info.
#[no_mangle]
pub extern "C" fn trit_engine_info() -> *const c_char {
    ENGINE_INFO.as_ptr() as *const c_char
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_matmul_identity_like() {
        let m = 2usize;
        let k = 4usize;
        let n = 3usize;
        let pk = packed_len(k);

        let input = vec![1.0f32, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0];
        // All +1 trits for 4 active trits, 5th padded to 0
        let all_plus_byte = trit_lut::encode_trits(&[1, 1, 1, 1, 0]);
        let weights = vec![all_plus_byte; pk * n];
        let scales = vec![1.0f32; n];
        let mut output = vec![0.0f32; m * n];

        let ret = trit_matmul(
            input.as_ptr(),
            weights.as_ptr(),
            output.as_mut_ptr(),
            scales.as_ptr(),
            m as i32,
            k as i32,
            n as i32,
        );

        assert_eq!(ret, 0);
        // Row 0 sum: 1+2+3+4 = 10, Row 1 sum: 5+6+7+8 = 26
        for j in 0..n {
            assert!((output[0 * n + j] - 10.0).abs() < 1e-5);
            assert!((output[1 * n + j] - 26.0).abs() < 1e-5);
        }
    }

    #[test]
    fn test_quantize_roundtrip() {
        let k = 10usize;
        let n = 4usize;
        let pk = packed_len(k);

        let mut weights = vec![0.0f32; k * n];
        for j in 0..n {
            for i in 0..k {
                weights[i * n + j] = if (i + j) % 3 == 0 {
                    1.0
                } else if (i + j) % 3 == 1 {
                    -1.0
                } else {
                    0.0
                };
            }
        }

        let mut packed = vec![0u8; pk * n];
        let mut scales = vec![0.0f32; n];

        let ret = trit_quantize_weights(
            weights.as_ptr(),
            packed.as_mut_ptr(),
            scales.as_mut_ptr(),
            k as i32,
            n as i32,
        );
        assert_eq!(ret, 0);

        for j in 0..n {
            assert!((scales[j] - 1.0).abs() < 1e-5);
        }

        let input = vec![1.0f32; k];
        let mut output = vec![0.0f32; n];

        trit_matmul(
            input.as_ptr(),
            packed.as_ptr(),
            output.as_mut_ptr(),
            scales.as_ptr(),
            1,
            k as i32,
            n as i32,
        );

        for j in 0..n {
            let mut expected = 0.0f32;
            for i in 0..k {
                expected += weights[i * n + j];
            }
            assert!(
                (output[j] - expected).abs() < 1e-4,
                "Col {}: expected {}, got {}",
                j, expected, output[j]
            );
        }
    }

    #[test]
    fn test_kv_pack_unpack_roundtrip() {
        let nh = 2usize;
        let sl = 3usize;
        let hd = 10usize;
        let total = nh * sl * hd;

        let mut kv_float = vec![0.0f32; total];
        for i in 0..total {
            kv_float[i] = match i % 3 {
                0 => 1.0,
                1 => -1.0,
                _ => 0.0,
            };
        }

        let phd = packed_len(hd);
        let mut packed = vec![0u8; nh * sl * phd];
        let mut scales = vec![0.0f32; nh];

        trit_pack_kv(
            kv_float.as_ptr(),
            packed.as_mut_ptr(),
            scales.as_mut_ptr(),
            nh as i32,
            sl as i32,
            hd as i32,
        );

        let mut unpacked = vec![0.0f32; total];
        trit_unpack_kv(
            packed.as_ptr(),
            scales.as_ptr(),
            unpacked.as_mut_ptr(),
            nh as i32,
            sl as i32,
            hd as i32,
        );

        for i in 0..total {
            assert!(
                (kv_float[i] - unpacked[i]).abs() < 1e-4,
                "Index {}: expected {}, got {}",
                i, kv_float[i], unpacked[i]
            );
        }
    }
}
