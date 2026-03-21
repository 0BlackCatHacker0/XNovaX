/// Lookup table: 243 entries, each decoding a packed byte into 5 trits.
/// Encoding: value = t0 + 3*t1 + 9*t2 + 27*t3 + 81*t4
/// where each ti is stored as {0,1,2} mapping to {-1, 0, +1}.
///
/// LUT is 243 * 5 = 1215 bytes — fits entirely in L1 cache.

pub static TRIT_LUT: [[i8; 5]; 243] = generate_trit_lut();

const fn generate_trit_lut() -> [[i8; 5]; 243] {
    let mut lut = [[0i8; 5]; 243];
    let mut i: usize = 0;
    while i < 243 {
        let mut val = i as u8;
        let mut j: usize = 0;
        while j < 5 {
            let digit = val % 3;
            // Map: 0 -> -1, 1 -> 0, 2 -> +1
            lut[i][j] = (digit as i8) - 1;
            val /= 3;
            j += 1;
        }
        i += 1;
    }
    lut
}

/// Encode 5 trits (each -1, 0, or +1) into a single byte.
/// Maps {-1, 0, +1} -> {0, 1, 2}, then packs as base-3.
#[inline(always)]
pub fn encode_trits(trits: &[i8; 5]) -> u8 {
    let mut val: u8 = 0;
    let mut base: u8 = 1;
    for i in 0..5 {
        val += ((trits[i] + 1) as u8) * base;
        base *= 3;
    }
    val
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lut_roundtrip() {
        for i in 0..243u8 {
            let trits = TRIT_LUT[i as usize];
            let repacked = encode_trits(&trits);
            assert_eq!(repacked, i, "Roundtrip failed for byte {}", i);
        }
    }

    #[test]
    fn test_known_values() {
        // byte 0: all digits are 0, mapping to all -1
        assert_eq!(TRIT_LUT[0], [-1, -1, -1, -1, -1]);
        // byte 121 = 1 + 3 + 9 + 27 + 81 = all digits 1, mapping to all 0
        assert_eq!(TRIT_LUT[121], [0, 0, 0, 0, 0]);
        // byte 242 = 2 + 6 + 18 + 54 + 162 = all digits 2, mapping to all +1
        assert_eq!(TRIT_LUT[242], [1, 1, 1, 1, 1]);
    }
}
