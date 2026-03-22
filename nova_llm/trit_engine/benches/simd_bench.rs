//! Benchmarks: scalar trit_dot vs SIMD trit_dot_bitmap
//!
//! Run with:
//!   RUSTFLAGS="-C target-cpu=native" cargo bench
//!   (Windows: set RUSTFLAGS=-C target-cpu=native && cargo bench)

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use trit_engine::{expand_trit_bitmaps, TritBitmaps};

// We need access to internals, so we re-implement the core functions here
// using the public API. The actual hot path is trit_matmul vs trit_matmul_simd.

/// Generate deterministic packed weights and input for a given dimension.
fn setup_data(k: usize) -> (Vec<f32>, Vec<u8>, Vec<f32>) {
    let n = 1; // single column for dot product benchmarks
    let pk = (k + 4) / 5;

    // Create float weights, quantize them
    let mut weights_float = vec![0.0f32; k * n];
    for i in 0..k {
        weights_float[i] = match (i * 7 + 3) % 5 {
            0 => 1.0,
            1 => -1.0,
            _ => 0.0,
        };
    }

    let mut packed = vec![0u8; pk * n];
    let mut scales = vec![0.0f32; n];

    unsafe {
        trit_engine::trit_quantize_weights(
            weights_float.as_ptr(),
            packed.as_mut_ptr(),
            scales.as_mut_ptr(),
            k as i32,
            n as i32,
        );
    }

    // Create input
    let input: Vec<f32> = (0..k).map(|i| ((i % 17) as f32 - 8.0) * 0.1).collect();

    (input, packed, scales)
}

fn bench_scalar_matmul(c: &mut Criterion) {
    let mut group = c.benchmark_group("trit_matmul_scalar");

    for &k in &[768, 1024, 2048] {
        let n = 64usize;
        let m = 1usize;
        let pk = (k + 4) / 5;

        // Setup
        let mut weights_float = vec![0.0f32; k * n];
        for j in 0..n {
            for i in 0..k {
                weights_float[i * n + j] = match (i * 7 + j * 13) % 5 {
                    0 => 1.0,
                    1 => -1.0,
                    _ => 0.0,
                };
            }
        }
        let mut packed = vec![0u8; pk * n];
        let mut scales = vec![0.0f32; n];
        unsafe {
            trit_engine::trit_quantize_weights(
                weights_float.as_ptr(),
                packed.as_mut_ptr(),
                scales.as_mut_ptr(),
                k as i32,
                n as i32,
            );
        }
        let input: Vec<f32> = (0..m * k).map(|i| ((i % 17) as f32 - 8.0) * 0.1).collect();
        let mut output = vec![0.0f32; m * n];

        group.bench_with_input(BenchmarkId::new("scalar", k), &k, |b, _| {
            b.iter(|| {
                trit_engine::trit_matmul(
                    black_box(input.as_ptr()),
                    black_box(packed.as_ptr()),
                    black_box(output.as_mut_ptr()),
                    black_box(scales.as_ptr()),
                    m as i32,
                    k as i32,
                    n as i32,
                );
            });
        });
    }
    group.finish();
}

fn bench_simd_matmul(c: &mut Criterion) {
    let mut group = c.benchmark_group("trit_matmul_simd");

    for &k in &[768, 1024, 2048] {
        let n = 64usize;
        let m = 1usize;
        let pk = (k + 4) / 5;

        // Setup
        let mut weights_float = vec![0.0f32; k * n];
        for j in 0..n {
            for i in 0..k {
                weights_float[i * n + j] = match (i * 7 + j * 13) % 5 {
                    0 => 1.0,
                    1 => -1.0,
                    _ => 0.0,
                };
            }
        }
        let mut packed = vec![0u8; pk * n];
        let mut scales = vec![0.0f32; n];
        unsafe {
            trit_engine::trit_quantize_weights(
                weights_float.as_ptr(),
                packed.as_mut_ptr(),
                scales.as_mut_ptr(),
                k as i32,
                n as i32,
            );
        }
        let input: Vec<f32> = (0..m * k).map(|i| ((i % 17) as f32 - 8.0) * 0.1).collect();
        let mut output = vec![0.0f32; m * n];

        group.bench_with_input(BenchmarkId::new("simd", k), &k, |b, _| {
            b.iter(|| {
                trit_engine::trit_matmul_simd(
                    black_box(input.as_ptr()),
                    black_box(packed.as_ptr()),
                    black_box(output.as_mut_ptr()),
                    black_box(scales.as_ptr()),
                    m as i32,
                    k as i32,
                    n as i32,
                );
            });
        });
    }
    group.finish();
}

fn bench_dot_product_comparison(c: &mut Criterion) {
    let mut group = c.benchmark_group("trit_dot_comparison");

    for &k in &[768, 1024, 2048] {
        let (input, packed, _scales) = setup_data(k);

        // Benchmark: full scalar matmul (1x1xK dot product)
        let mut output_scalar = vec![0.0f32; 1];
        let scales_one = vec![1.0f32; 1];
        group.bench_with_input(BenchmarkId::new("scalar_dot", k), &k, |b, _| {
            b.iter(|| {
                trit_engine::trit_matmul(
                    black_box(input.as_ptr()),
                    black_box(packed.as_ptr()),
                    black_box(output_scalar.as_mut_ptr()),
                    black_box(scales_one.as_ptr()),
                    1,
                    k as i32,
                    1,
                );
            });
        });

        // Benchmark: SIMD matmul (1x1xK dot product)
        let mut output_simd = vec![0.0f32; 1];
        group.bench_with_input(BenchmarkId::new("simd_dot", k), &k, |b, _| {
            b.iter(|| {
                trit_engine::trit_matmul_simd(
                    black_box(input.as_ptr()),
                    black_box(packed.as_ptr()),
                    black_box(output_simd.as_mut_ptr()),
                    black_box(scales_one.as_ptr()),
                    1,
                    k as i32,
                    1,
                );
            });
        });
    }
    group.finish();
}

criterion_group!(benches, bench_scalar_matmul, bench_simd_matmul, bench_dot_product_comparison);
criterion_main!(benches);
