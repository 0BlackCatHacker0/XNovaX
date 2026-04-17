// ============================================================================
// NovaX Ternary Instruction Set Architecture (ISA) v1.0
// ============================================================================
//
// STATUS: DESIGN SPEC / REFERENCE ONLY — NOT WIRED TO THE VM.
// ---------------------------------------------------------------------------
// This file contains a complete ternary bytecode ISA design (1700+ lines)
// but NO module or binary in this crate actually imports or executes it.
// The NovaLang VM (vm.rs) is a tree-walking interpreter that operates on
// the AST directly — it does NOT compile to this bytecode.
//
// This file is kept because:
//   1. It documents the ternary-first ISA vision for a future compiler pass.
//   2. The opcode definitions, encoding layout, and register model are
//      reference material for anyone building a bytecode backend.
//
// If you're here looking for the active interpreter, see vm.rs. If you
// implement a bytecode compiler later, this ISA is a starting point.
// ---------------------------------------------------------------------------
//
// A native ternary ISA built on the 3-5-7-13 harmonic system.
// Every value is a balanced ternary trit: {-1, 0, +1} (written as {N, Z, P})
//
// KEY DESIGN PRINCIPLES:
//   1. Everything is ternary — registers, memory, instructions
//   2. 3-way branching in ONE instruction (the killer feature)
//   3. TZip packing: 5 trits = 1 TZip byte (3^5 = 243 values)
//   4. 3-5-7-13 harmonic block sizes throughout
//   5. TCMP produces {-1,0,+1} naturally — no flags register needed
//
// INSTRUCTION WORD: 27 trits (one ternary word)
//   ┌─────────┬─────────┬─────────┬──────────┐
//   │ OPCODE  │ OPER 1  │ OPER 2  │ IMMEDIATE│
//   │ 9 trits │ 5 trits │ 5 trits │ 8 trits  │
//   └─────────┴─────────┴─────────┴──────────┘
//   Total: 9 + 5 + 5 + 8 = 27 trits = 1 word
//
// ============================================================================

use std::fmt;

// ============================================================================
// SECTION 1: TRIT AND WORD FUNDAMENTALS
// ============================================================================

/// A single balanced ternary trit: -1 (N), 0 (Z), or +1 (P)
pub type Trit = i8;

/// Ternary word: 27 trits, stored as an array.
/// Represents one register value or one instruction.
/// Value range: -(3^27-1)/2 to +(3^27-1)/2 = -3,812,798,742,493 to +3,812,798,742,493
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TWord {
    pub trits: [Trit; 27],
}

/// TZip byte: 5 trits packed into one unit (3^5 = 243 values, fits in u8)
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TZipByte {
    pub trits: [Trit; 5],
}

impl TWord {
    pub const ZERO: TWord = TWord { trits: [0; 27] };

    /// Create a TWord from an integer value (balanced ternary conversion)
    pub fn from_int(mut val: i64) -> Self {
        let mut trits = [0i8; 27];
        let negative = val < 0;
        if negative { val = -val; }
        for i in 0..27 {
            let rem = val % 3;
            val /= 3;
            trits[i] = match rem {
                0 => 0,
                1 => 1,
                2 => { val += 1; -1 }  // balanced ternary: 2 becomes -1 with carry
                _ => unreachable!(),
            };
        }
        if negative {
            for t in trits.iter_mut() { *t = -*t; }
        }
        TWord { trits }
    }

    /// Convert TWord back to integer
    pub fn to_int(&self) -> i64 {
        let mut val: i64 = 0;
        let mut power: i64 = 1;
        for i in 0..27 {
            val += self.trits[i] as i64 * power;
            power *= 3;
        }
        val
    }

    /// Get a single trit at position (0 = LST, 26 = MST)
    #[inline]
    pub fn get_trit(&self, pos: usize) -> Trit {
        self.trits[pos.min(26)]
    }

    /// Set a single trit at position
    #[inline]
    pub fn set_trit(&mut self, pos: usize, val: Trit) {
        if pos < 27 {
            self.trits[pos] = val.max(-1).min(1);
        }
    }

    /// Extract a range of trits as an integer value
    pub fn extract_field(&self, start: usize, len: usize) -> i64 {
        let mut val: i64 = 0;
        let mut power: i64 = 1;
        for i in 0..len {
            let pos = start + i;
            if pos < 27 {
                val += self.trits[pos] as i64 * power;
            }
            power *= 3;
        }
        val
    }

    /// Ternary NOT (negate): flip every trit's sign
    pub fn tnot(&self) -> TWord {
        let mut result = TWord::ZERO;
        for i in 0..27 {
            result.trits[i] = -self.trits[i];
        }
        result
    }

    /// Ternary AND (min): trit-wise minimum
    pub fn tand(&self, other: &TWord) -> TWord {
        let mut result = TWord::ZERO;
        for i in 0..27 {
            result.trits[i] = self.trits[i].min(other.trits[i]);
        }
        result
    }

    /// Ternary OR (max): trit-wise maximum
    pub fn tor(&self, other: &TWord) -> TWord {
        let mut result = TWord::ZERO;
        for i in 0..27 {
            result.trits[i] = self.trits[i].max(other.trits[i]);
        }
        result
    }

    /// Pack TWord into TZip bytes (5 trits each, 5 full + 2 remaining)
    /// 27 trits = 5 TZip bytes (25 trits) + 1 partial (2 trits)
    pub fn to_tzip(&self) -> [TZipByte; 6] {
        let mut result = [TZipByte { trits: [0; 5] }; 6];
        for byte_idx in 0..5 {
            for t in 0..5 {
                result[byte_idx].trits[t] = self.trits[byte_idx * 5 + t];
            }
        }
        // Last 2 trits in partial byte
        result[5].trits[0] = self.trits[25];
        result[5].trits[1] = self.trits[26];
        result
    }
}

impl fmt::Display for TWord {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Display MST first (left to right = most significant to least)
        for i in (0..27).rev() {
            let ch = match self.trits[i] {
                -1 => 'N',
                 0 => 'Z',
                 1 => 'P',
                 _ => '?',
            };
            write!(f, "{}", ch)?;
            // Group by 3s for readability (3-5-7-13 harmonic)
            if i > 0 && i % 3 == 0 { write!(f, ".")?; }
        }
        Ok(())
    }
}

impl TZipByte {
    /// Convert TZip byte to integer (0..242, or with balanced: -121..+121)
    pub fn to_int(&self) -> i64 {
        let mut val: i64 = 0;
        let mut power: i64 = 1;
        for i in 0..5 {
            val += self.trits[i] as i64 * power;
            power *= 3;
        }
        val
    }

    /// Create from integer
    pub fn from_int(mut val: i64) -> Self {
        let mut trits = [0i8; 5];
        let negative = val < 0;
        if negative { val = -val; }
        for i in 0..5 {
            let rem = val % 3;
            val /= 3;
            trits[i] = match rem {
                0 => 0,
                1 => 1,
                2 => { val += 1; -1 }
                _ => unreachable!(),
            };
        }
        if negative {
            for t in trits.iter_mut() { *t = -*t; }
        }
        TZipByte { trits }
    }
}

// ============================================================================
// SECTION 2: REGISTER FILE
// ============================================================================
//
// 27 general-purpose registers (3^3), named T0-T26
// Each holds one TWord (27 trits)
//
// Register index encoding: 5 trits (3^5 = 243 values, 27 used for registers)
//   Values 0-26:   T0-T26 (general purpose)
//   Values 27-29:  TPC, TSP, TFP (special registers)
//   Values 30-242: Reserved for addressing modes (see Section 4)
//
// REGISTER CONVENTIONS:
//   T0         = zero register (hardwired to 0, writes ignored)
//   T1-T8      = argument/return registers (T1 = first arg, T1 = return value)
//   T9-T17     = callee-saved (preserved across calls)
//   T18-T25    = caller-saved (temporaries)
//   T26        = link register (return address, set by TCALL)
//   TPC (27)   = program counter
//   TSP (28)   = stack pointer
//   TFP (29)   = frame pointer
// ============================================================================

/// Number of general-purpose registers: 3^3 = 27
pub const NUM_GP_REGS: usize = 27;

/// Special register indices (in the 5-trit operand space)
pub const REG_ZERO: usize = 0;   // T0: hardwired zero
pub const REG_LINK: usize = 26;  // T26: link register
pub const REG_TPC: usize  = 27;  // Program counter
pub const REG_TSP: usize  = 28;  // Stack pointer
pub const REG_TFP: usize  = 29;  // Frame pointer

/// The complete register file
#[derive(Clone, Debug)]
pub struct RegisterFile {
    /// T0-T26: general purpose (T0 hardwired to zero)
    pub gp: [TWord; NUM_GP_REGS],
    /// TPC: program counter
    pub tpc: TWord,
    /// TSP: stack pointer
    pub tsp: TWord,
    /// TFP: frame pointer
    pub tfp: TWord,
}

impl RegisterFile {
    pub fn new() -> Self {
        RegisterFile {
            gp: [TWord::ZERO; NUM_GP_REGS],
            tpc: TWord::ZERO,
            tsp: TWord::ZERO,
            tfp: TWord::ZERO,
        }
    }

    /// Read a register by index (0-29)
    pub fn read(&self, idx: usize) -> TWord {
        match idx {
            0 => TWord::ZERO,           // T0 always reads zero
            1..=26 => self.gp[idx],
            27 => self.tpc,             // REG_TPC
            28 => self.tsp,             // REG_TSP
            29 => self.tfp,             // REG_TFP
            _ => TWord::ZERO,           // Invalid → zero
        }
    }

    /// Write to a register by index (0-29). T0 writes are silently ignored.
    pub fn write(&mut self, idx: usize, val: TWord) {
        match idx {
            0 => {},                    // T0 is hardwired zero
            1..=26 => self.gp[idx] = val,
            27 => self.tpc = val,
            28 => self.tsp = val,
            29 => self.tfp = val,
            _ => {},                    // Invalid → ignore
        }
    }
}

// ============================================================================
// SECTION 3: INSTRUCTION FORMAT
// ============================================================================
//
// Every instruction is exactly 27 trits (one TWord):
//
//   Bit layout (trit positions, LST = 0):
//   ┌──────────────────────────────────────────────────────────────┐
//   │ [0..8]   OPCODE     9 trits   3^9 = 19,683 possible opcodes│
//   │ [9..13]  OPERAND 1  5 trits   register/mode index          │
//   │ [14..18] OPERAND 2  5 trits   register/mode index          │
//   │ [19..26] IMMEDIATE  8 trits   3^8 = 6,561 value range      │
//   │                               (balanced: -3,280 to +3,280)  │
//   └──────────────────────────────────────────────────────────────┘
//
// INSTRUCTION CATEGORIES (by opcode high trits):
//   Opcode[8..6] = NNN..NNP: Arithmetic  (TADD, TSUB, TMUL, TDIV)
//   Opcode[8..6] = NNZ..NZP: Logic       (TAND, TOR, TNOT, TXOR)
//   Opcode[8..6] = NZZ..NPP: Memory      (TLOAD, TSTORE)
//   Opcode[8..6] = ZNN..ZNP: Branch      (TJMP, TBR3, TCMP)
//   Opcode[8..6] = ZZN..ZZP: Call/Stack  (TCALL, TRET, TPUSH, TPOP)
//   Opcode[8..6] = ZPN..ZPP: Pack/Unpack (TPACK, TUNPACK)
//   Opcode[8..6] = PNN..PNP: Shift/Rot   (TSHIFT, TROT)
//   Opcode[8..6] = PZN..PZP: System      (THALT, TNOP, TSYSCALL)
//   Opcode[8..6] = PPN..PPP: Extended     (future expansion)
//
// ============================================================================

/// Decoded instruction
#[derive(Clone, Debug)]
pub struct Instruction {
    pub opcode: Opcode,
    pub op1: u8,       // operand 1 index (0-242, but typically 0-29)
    pub op2: u8,       // operand 2 index
    pub imm: i16,      // immediate value (balanced ternary, -3280 to +3280)
    pub mode: AddrMode,
}

/// Opcode enumeration — core instruction set
/// Organized by functional group, opcode value in parentheses.
///
/// ENCODING TABLE (9-trit opcode as balanced ternary integer):
///
/// ┌────────────────┬────────────┬─────────────────────────────────────────┐
/// │ Mnemonic       │ Opcode Val │ Description                             │
/// ├────────────────┼────────────┼─────────────────────────────────────────┤
/// │                │            │ === ARITHMETIC (opcode -9841 to -6561) ==│
/// │ TADD           │      -9841 │ Td = Ts1 + Ts2 (ternary addition)      │
/// │ TADDI          │      -9840 │ Td = Ts + imm  (add immediate)         │
/// │ TSUB           │      -9839 │ Td = Ts1 - Ts2 (ternary subtraction)   │
/// │ TSUBI          │      -9838 │ Td = Ts - imm  (sub immediate)         │
/// │ TMUL           │      -9837 │ Td = Ts1 * Ts2 (ternary multiply)      │
/// │ TMULI          │      -9836 │ Td = Ts * imm  (mul immediate)         │
/// │ TDIV           │      -9835 │ Td = Ts1 / Ts2 (ternary divide)        │
/// │ TDIVI          │      -9834 │ Td = Ts / imm  (div immediate)         │
/// │ TMOD           │      -9833 │ Td = Ts1 % Ts2 (modulo)                │
/// │ TNEG           │      -9832 │ Td = -Ts       (negate all trits)      │
/// │ TABS           │      -9831 │ Td = |Ts|      (absolute value)        │
/// │ TSIGN          │      -9830 │ Td = sign(Ts)  (result: {-1,0,+1})     │
/// ├────────────────┼────────────┼─────────────────────────────────────────┤
/// │                │            │ === LOGIC (opcode -6560 to -3281) ======│
/// │ TAND           │      -6560 │ Td = min(Ts1, Ts2) per-trit            │
/// │ TOR            │      -6559 │ Td = max(Ts1, Ts2) per-trit            │
/// │ TNOT           │      -6558 │ Td = -Ts per-trit (flip signs)         │
/// │ TXOR           │      -6557 │ Td = Ts1 * Ts2 per-trit (ternary XOR) │
/// │ TCLAMP         │      -6556 │ Td = clamp(Ts, -1, +1) per-trit       │
/// │ TANY           │      -6555 │ Td = +1 if any trit in Ts != 0        │
/// │ TALL           │      -6554 │ Td = +1 if all trits in Ts != 0       │
/// │ TCOUNT         │      -6553 │ Td = count of non-zero trits in Ts     │
/// ├────────────────┼────────────┼─────────────────────────────────────────┤
/// │                │            │ === MEMORY (opcode -3280 to -1) =======│
/// │ TLOAD          │      -3280 │ Td = MEM[Ts + imm]  (load word)        │
/// │ TSTORE         │      -3279 │ MEM[Ts1 + imm] = Ts2 (store word)      │
/// │ TLOADB         │      -3278 │ Td = MEM_TZIP[Ts + imm] (load TZip)    │
/// │ TSTOREB        │      -3277 │ MEM_TZIP[Ts + imm] = Ts2 (store TZip)  │
/// │ TLEA           │      -3276 │ Td = Ts + imm (load effective address)  │
/// ├────────────────┼────────────┼─────────────────────────────────────────┤
/// │                │            │ === BRANCH (opcode 0 to 3280) =========│
/// │ TNOP           │          0 │ No operation                            │
/// │ TJMP           │          1 │ TPC = Ts + imm (unconditional jump)     │
/// │ TBR3           │          2 │ 3-WAY BRANCH (see Section 5)            │
/// │                │            │   if Ts < 0 → TPC = op1_addr            │
/// │                │            │   if Ts = 0 → TPC = op2_addr            │
/// │                │            │   if Ts > 0 → TPC = imm_addr            │
/// │ TCMP           │          3 │ Td = compare(Ts1, Ts2) → {-1,0,+1}     │
/// │ TCMPI          │          4 │ Td = compare(Ts, imm) → {-1,0,+1}      │
/// │ TBRN           │          5 │ if Ts < 0: TPC = imm (branch negative)  │
/// │ TBRZ           │          6 │ if Ts = 0: TPC = imm (branch zero)      │
/// │ TBRP           │          7 │ if Ts > 0: TPC = imm (branch positive)  │
/// │ TBRNZ          │          8 │ if Ts != 0: TPC = imm (branch nonzero)  │
/// ├────────────────┼────────────┼─────────────────────────────────────────┤
/// │                │            │ === CALL/STACK (opcode 3281 to 6560) ===│
/// │ TCALL          │       3281 │ T26=TPC+1, TPC=Ts+imm (call function)  │
/// │ TRET           │       3282 │ TPC = T26 (return from call)            │
/// │ TPUSH          │       3283 │ TSP-=1, MEM[TSP] = Ts (push to stack)   │
/// │ TPOP           │       3284 │ Td = MEM[TSP], TSP+=1 (pop from stack)  │
/// │ TENTER         │       3285 │ Push TFP, TFP=TSP (enter function frame)│
/// │ TLEAVE         │       3286 │ TSP=TFP, Pop TFP (leave function frame) │
/// ├────────────────┼────────────┼─────────────────────────────────────────┤
/// │                │            │ === PACK/UNPACK (opcode 6561 to 9840) ==│
/// │ TPACK          │       6561 │ Td = pack 5 trits from Ts into TZip     │
/// │ TUNPACK        │       6562 │ Unpack TZip Ts into 5 trits → Td        │
/// │ TPACKW         │       6563 │ Pack TWord into 6 TZip bytes → memory   │
/// │ TUNPACKW       │       6564 │ Unpack 6 TZip bytes from memory → Td    │
/// ├────────────────┼────────────┼─────────────────────────────────────────┤
/// │                │            │ === SHIFT/ROTATE (opcode 9841+) ========│
/// │ TSHIFTL        │       9841 │ Td = Ts << imm (shift trits left)       │
/// │ TSHIFTR        │       9842 │ Td = Ts >> imm (shift trits right)      │
/// │ TROTL          │       9843 │ Td = rotate_left(Ts, imm) (27-trit rot) │
/// │ TROTR          │       9844 │ Td = rotate_right(Ts, imm)              │
/// │ TEXTRACT       │       9845 │ Td = Ts[imm..imm+op2] (extract field)  │
/// │ TINSERT        │       9846 │ Td[imm..imm+op2] = Ts (insert field)   │
/// ├────────────────┼────────────┼─────────────────────────────────────────┤
/// │                │            │ === SYSTEM (opcode 9847+) ==============│
/// │ THALT          │       9847 │ Halt execution                          │
/// │ TSYSCALL       │       9848 │ System call (call # in imm)             │
/// │ TDEBUG         │       9849 │ Debug breakpoint                        │
/// │ TPRINT         │       9850 │ Print register Ts (debug output)        │
/// │ TMOV           │       9851 │ Td = Ts (register move)                 │
/// │ TMOVI          │       9852 │ Td = sign_extend(imm) (load immediate)  │
/// │ TLUI           │       9853 │ Td[high] = imm (load upper immediate)   │
/// └────────────────┴────────────┴─────────────────────────────────────────┘
///
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(i16)]
pub enum Opcode {
    // === Arithmetic ===
    TADD    = -9841_i16,  // Overflow note: i16 range is -32768..32767, fits
    TADDI   = -9840,
    TSUB    = -9839,
    TSUBI   = -9838,
    TMUL    = -9837,
    TMULI   = -9836,
    TDIV    = -9835,
    TDIVI   = -9834,
    TMOD    = -9833,
    TNEG    = -9832,
    TABS    = -9831,
    TSIGN   = -9830,

    // === Logic ===
    TAND    = -6560,
    TOR     = -6559,
    TNOT    = -6558,
    TXOR    = -6557,
    TCLAMP  = -6556,
    TANY    = -6555,
    TALL    = -6554,
    TCOUNT  = -6553,

    // === Memory ===
    TLOAD   = -3280,
    TSTORE  = -3279,
    TLOADB  = -3278,
    TSTOREB = -3277,
    TLEA    = -3276,

    // === Branch ===
    TNOP    = 0,
    TJMP    = 1,
    TBR3    = 2,          // THE 3-way branch — the killer feature
    TCMP    = 3,
    TCMPI   = 4,
    TBRN    = 5,
    TBRZ    = 6,
    TBRP    = 7,
    TBRNZ   = 8,

    // === Call/Stack ===
    TCALL   = 3281,
    TRET    = 3282,
    TPUSH   = 3283,
    TPOP    = 3284,
    TENTER  = 3285,
    TLEAVE  = 3286,

    // === Pack/Unpack ===
    TPACK   = 6561,
    TUNPACK = 6562,
    TPACKW  = 6563,
    TUNPACKW= 6564,

    // === Shift/Rotate ===
    TSHIFTL = 9841,
    TSHIFTR = 9842,
    TROTL   = 9843,
    TROTR   = 9844,
    TEXTRACT= 9845,
    TINSERT = 9846,

    // === System ===
    THALT   = 9847,
    TSYSCALL= 9848,
    TDEBUG  = 9849,
    TPRINT  = 9850,
    TMOV    = 9851,
    TMOVI   = 9852,
    TLUI    = 9853,
}

// ============================================================================
// SECTION 4: ADDRESSING MODES
// ============================================================================
//
// The 5-trit operand field (3^5 = 243 values) encodes both the register
// index AND the addressing mode:
//
// ┌────────────────────┬──────────────┬──────────────────────────────────────┐
// │ Mode               │ Operand Range│ Semantics                            │
// ├────────────────────┼──────────────┼──────────────────────────────────────┤
// │ Register Direct    │    0 -  29   │ value = REG[operand]                 │
// │ Immediate          │   30         │ value = sign_extend(imm field)       │
// │ Direct Memory      │   31 -  57   │ value = MEM[REG[operand-31] + imm]   │
// │ Indirect           │   58 -  84   │ value = MEM[MEM[REG[operand-58]]]    │
// │ Indexed (Base+Off) │   85 - 111   │ value = MEM[REG[operand-85] + Ridx]  │
// │ Pre-decrement      │  112 - 138   │ REG[n] -= 1; value = MEM[REG[n]]     │
// │ Post-increment     │  139 - 165   │ value = MEM[REG[n]]; REG[n] += 1     │
// │ TZip Packed        │  166 - 192   │ 5-trit TZip access at REG[n]+imm     │
// │ Reserved           │  193 - 242   │ Future: SIMD, coprocessor, etc.      │
// └────────────────────┴──────────────┴──────────────────────────────────────┘
//
// The mode is determined by the operand value range. This avoids wasting
// opcode bits on mode encoding — the 5-trit operand space has 243 slots,
// far more than the 30 registers need.
//
// ============================================================================

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AddrMode {
    /// Value is in the register (operand 0-29)
    Register,
    /// Value is the immediate field (operand 30)
    Immediate,
    /// Value at memory address REG[n] + imm (operand 31-57, n = operand-31)
    Direct,
    /// Value at MEM[MEM[REG[n]]] (operand 58-84, n = operand-58)
    Indirect,
    /// Value at MEM[REG[base] + REG[idx]] (operand 85-111)
    Indexed,
    /// Pre-decrement: REG[n]-=1, then MEM[REG[n]] (operand 112-138)
    PreDecrement,
    /// Post-increment: MEM[REG[n]], then REG[n]+=1 (operand 139-165)
    PostIncrement,
    /// TZip packed access (operand 166-192)
    TZipPacked,
    /// Reserved for future use
    Reserved,
}

/// Decode the addressing mode from a 5-trit operand value (0-242)
pub fn decode_addr_mode(operand: u8) -> (AddrMode, usize) {
    match operand {
        0..=29    => (AddrMode::Register, operand as usize),
        30        => (AddrMode::Immediate, 0),
        31..=57   => (AddrMode::Direct, (operand - 31) as usize),
        58..=84   => (AddrMode::Indirect, (operand - 58) as usize),
        85..=111  => (AddrMode::Indexed, (operand - 85) as usize),
        112..=138 => (AddrMode::PreDecrement, (operand - 112) as usize),
        139..=165 => (AddrMode::PostIncrement, (operand - 139) as usize),
        166..=192 => (AddrMode::TZipPacked, (operand - 166) as usize),
        _         => (AddrMode::Reserved, 0),
    }
}

// ============================================================================
// SECTION 5: THE 3-WAY BRANCH (TBR3) — THE KILLER FEATURE
// ============================================================================
//
// TBR3 is the instruction that makes ternary ISAs fundamentally superior
// to binary ISAs for control flow.
//
// BINARY ISA (x86/ARM):
//   CMP  r1, r2          ; compare → sets flags (1 instruction)
//   BLT  label_less      ; branch if less (1 instruction)
//   BEQ  label_equal     ; branch if equal (1 instruction)
//   JMP  label_greater   ; fall-through to greater (1 instruction)
//   ─────────────────────
//   TOTAL: 4 instructions for 3-way decision
//
// TERNARY ISA (NovaX):
//   TCMP T3, T4, T5      ; T3 = compare(T4, T5) → {-1, 0, +1} (1 instruction)
//   TBR3 T3, neg, zero, pos  ; branch 3 ways based on T3 (1 instruction)
//   ─────────────────────
//   TOTAL: 2 instructions for 3-way decision
//   SAVINGS: 50% fewer instructions
//
// In hot loops and decision trees, this halves the branch overhead.
//
// ENCODING OF TBR3:
//   The 27-trit instruction word is divided as:
//   ┌───────────┬────────────────┬────────────────┬──────────────────┐
//   │ OPCODE=2  │ COND_REG (op1) │ TGT_ZERO (op2) │ TGT_POS (imm)   │
//   │ 9 trits   │ 5 trits        │ 5 trits        │ 8 trits          │
//   └───────────┴────────────────┴────────────────┴──────────────────┘
//
//   op1  = register to test (must contain {-1, 0, +1})
//   op2  = target offset for ZERO case (relative)
//   imm  = target offset for POSITIVE case (relative)
//   NEG case = fall through to next instruction (PC + 1)
//
//   Full 3-way with arbitrary targets uses TCMP + TBR3:
//     TCMP T1, T2, T3     ; T1 = {-1, 0, +1}
//     TBR3 T1, +0, +5, +10 ; N→next, Z→PC+5, P→PC+10
//
// ALTERNATIVE: Match3 pattern from NovaLang maps directly:
//   match3 value {
//       +1 { ... }    →  TBR3 → positive target
//        0 { ... }    →  TBR3 → zero target
//       -1 { ... }    →  TBR3 → negative target (fall-through)
//   }
//
// ============================================================================

/// TBR3 branch target resolution
#[derive(Clone, Debug)]
pub struct TBR3Targets {
    /// Address when condition register < 0 (negative)
    pub addr_neg: i64,
    /// Address when condition register = 0 (zero/maybe)
    pub addr_zero: i64,
    /// Address when condition register > 0 (positive)
    pub addr_pos: i64,
}

/// Resolve TBR3 targets from instruction fields and current PC
pub fn resolve_tbr3(pc: i64, op2_offset: i16, imm_offset: i16) -> TBR3Targets {
    TBR3Targets {
        addr_neg: pc + 1,                     // fall through
        addr_zero: pc + op2_offset as i64,    // relative offset
        addr_pos: pc + imm_offset as i64,     // relative offset
    }
}

// ============================================================================
// SECTION 6: INSTRUCTION ENCODING/DECODING
// ============================================================================

/// Encode an instruction into a TWord
pub fn encode_instruction(opcode: Opcode, op1: u8, op2: u8, imm: i16) -> TWord {
    let mut word = TWord::ZERO;

    // Encode opcode into trits 0..8 (9 trits)
    let opcode_word = TWord::from_int(opcode as i64);
    for i in 0..9 {
        word.trits[i] = opcode_word.trits[i];
    }

    // Encode operand 1 into trits 9..13 (5 trits)
    let op1_word = TWord::from_int(op1 as i64);
    for i in 0..5 {
        word.trits[9 + i] = op1_word.trits[i];
    }

    // Encode operand 2 into trits 14..18 (5 trits)
    let op2_word = TWord::from_int(op2 as i64);
    for i in 0..5 {
        word.trits[14 + i] = op2_word.trits[i];
    }

    // Encode immediate into trits 19..26 (8 trits)
    let imm_word = TWord::from_int(imm as i64);
    for i in 0..8 {
        word.trits[19 + i] = imm_word.trits[i];
    }

    word
}

/// Decode a TWord into an Instruction
pub fn decode_instruction(word: &TWord) -> Instruction {
    // Extract opcode (trits 0..8)
    let opcode_val = word.extract_field(0, 9) as i16;

    // Extract operand 1 (trits 9..13)
    let op1_val = word.extract_field(9, 5);
    let op1 = op1_val.max(0).min(242) as u8;

    // Extract operand 2 (trits 14..18)
    let op2_val = word.extract_field(14, 5);
    let op2 = op2_val.max(0).min(242) as u8;

    // Extract immediate (trits 19..26)
    let imm = word.extract_field(19, 8) as i16;

    let opcode = opcode_from_i16(opcode_val);
    let (mode, _) = decode_addr_mode(op1);

    Instruction { opcode, op1, op2, imm, mode }
}

/// Convert raw i16 to Opcode enum (with fallback to TNOP)
fn opcode_from_i16(val: i16) -> Opcode {
    match val {
        -9841 => Opcode::TADD,
        -9840 => Opcode::TADDI,
        -9839 => Opcode::TSUB,
        -9838 => Opcode::TSUBI,
        -9837 => Opcode::TMUL,
        -9836 => Opcode::TMULI,
        -9835 => Opcode::TDIV,
        -9834 => Opcode::TDIVI,
        -9833 => Opcode::TMOD,
        -9832 => Opcode::TNEG,
        -9831 => Opcode::TABS,
        -9830 => Opcode::TSIGN,
        -6560 => Opcode::TAND,
        -6559 => Opcode::TOR,
        -6558 => Opcode::TNOT,
        -6557 => Opcode::TXOR,
        -6556 => Opcode::TCLAMP,
        -6555 => Opcode::TANY,
        -6554 => Opcode::TALL,
        -6553 => Opcode::TCOUNT,
        -3280 => Opcode::TLOAD,
        -3279 => Opcode::TSTORE,
        -3278 => Opcode::TLOADB,
        -3277 => Opcode::TSTOREB,
        -3276 => Opcode::TLEA,
        0     => Opcode::TNOP,
        1     => Opcode::TJMP,
        2     => Opcode::TBR3,
        3     => Opcode::TCMP,
        4     => Opcode::TCMPI,
        5     => Opcode::TBRN,
        6     => Opcode::TBRZ,
        7     => Opcode::TBRP,
        8     => Opcode::TBRNZ,
        3281  => Opcode::TCALL,
        3282  => Opcode::TRET,
        3283  => Opcode::TPUSH,
        3284  => Opcode::TPOP,
        3285  => Opcode::TENTER,
        3286  => Opcode::TLEAVE,
        6561  => Opcode::TPACK,
        6562  => Opcode::TUNPACK,
        6563  => Opcode::TPACKW,
        6564  => Opcode::TUNPACKW,
        9841  => Opcode::TSHIFTL,
        9842  => Opcode::TSHIFTR,
        9843  => Opcode::TROTL,
        9844  => Opcode::TROTR,
        9845  => Opcode::TEXTRACT,
        9846  => Opcode::TINSERT,
        9847  => Opcode::THALT,
        9848  => Opcode::TSYSCALL,
        9849  => Opcode::TDEBUG,
        9850  => Opcode::TPRINT,
        9851  => Opcode::TMOV,
        9852  => Opcode::TMOVI,
        9853  => Opcode::TLUI,
        _     => Opcode::TNOP,  // Unknown opcodes become NOP
    }
}

// ============================================================================
// SECTION 7: TERNARY VIRTUAL MACHINE CORE
// ============================================================================

/// Memory size: 3^13 = 1,594,323 words (each word = 27 trits)
/// Total memory: 1,594,323 * 27 trits = 43,046,721 trits (~5.4 MB at 1 byte/trit)
pub const MEMORY_SIZE: usize = 1_594_323; // 3^13 — the harmonic carrier

/// Stack starts at top of memory, grows downward (toward address 0)
pub const STACK_TOP: i64 = MEMORY_SIZE as i64 - 1;

/// The Ternary Virtual Machine
pub struct TernaryVM {
    pub regs: RegisterFile,
    pub memory: Vec<TWord>,
    pub halted: bool,
    pub cycle_count: u64,
}

impl TernaryVM {
    pub fn new() -> Self {
        TernaryVM {
            regs: RegisterFile::new(),
            memory: vec![TWord::ZERO; MEMORY_SIZE],
            halted: false,
            cycle_count: 0,
        }
    }

    /// Load a program (list of instructions) into memory starting at address 0
    pub fn load_program(&mut self, instructions: &[TWord]) {
        for (i, inst) in instructions.iter().enumerate() {
            if i < MEMORY_SIZE {
                self.memory[i] = *inst;
            }
        }
        self.regs.tpc = TWord::ZERO;
        self.regs.tsp = TWord::from_int(STACK_TOP);
        self.regs.tfp = TWord::from_int(STACK_TOP);
    }

    /// Execute one instruction cycle
    pub fn step(&mut self) -> Result<(), String> {
        if self.halted {
            return Err("VM halted".into());
        }

        let pc = self.regs.tpc.to_int();
        if pc < 0 || pc as usize >= MEMORY_SIZE {
            return Err(format!("TPC out of bounds: {}", pc));
        }

        let word = self.memory[pc as usize];
        let inst = decode_instruction(&word);

        // Advance PC before execution (branch instructions override)
        self.regs.tpc = TWord::from_int(pc + 1);

        self.execute_instruction(&inst)?;
        self.cycle_count += 1;
        Ok(())
    }

    /// Run until THALT or error
    pub fn run(&mut self) -> Result<u64, String> {
        while !self.halted {
            self.step()?;
            // Safety: prevent infinite loops in testing
            if self.cycle_count > 10_000_000 {
                return Err("Cycle limit exceeded".into());
            }
        }
        Ok(self.cycle_count)
    }

    /// Read a value using addressing mode
    fn read_operand(&mut self, operand: u8, imm: i16) -> TWord {
        let (mode, reg_idx) = decode_addr_mode(operand);
        match mode {
            AddrMode::Register => self.regs.read(reg_idx),
            AddrMode::Immediate => TWord::from_int(imm as i64),
            AddrMode::Direct => {
                let addr = self.regs.read(reg_idx).to_int() + imm as i64;
                self.mem_read(addr)
            }
            AddrMode::Indirect => {
                let ptr = self.regs.read(reg_idx).to_int();
                let addr = self.mem_read(ptr).to_int();
                self.mem_read(addr)
            }
            AddrMode::Indexed => {
                // Base register + index register (op2 used as index register)
                let base = self.regs.read(reg_idx).to_int();
                let offset = imm as i64;
                self.mem_read(base + offset)
            }
            AddrMode::PreDecrement => {
                let mut val = self.regs.read(reg_idx).to_int();
                val -= 1;
                self.regs.write(reg_idx, TWord::from_int(val));
                self.mem_read(val)
            }
            AddrMode::PostIncrement => {
                let val = self.regs.read(reg_idx).to_int();
                let result = self.mem_read(val);
                self.regs.write(reg_idx, TWord::from_int(val + 1));
                result
            }
            AddrMode::TZipPacked => {
                // Read 5 trits from memory at TZip-aligned address
                let addr = self.regs.read(reg_idx).to_int() + imm as i64;
                let word = self.mem_read(addr / 5); // 5 trits per TZip
                let offset = (addr % 5) as usize;
                let mut result = TWord::ZERO;
                for i in 0..5 {
                    if offset + i < 27 {
                        result.trits[i] = word.trits[offset + i];
                    }
                }
                result
            }
            AddrMode::Reserved => TWord::ZERO,
        }
    }

    /// Memory read with bounds checking
    fn mem_read(&self, addr: i64) -> TWord {
        if addr >= 0 && (addr as usize) < MEMORY_SIZE {
            self.memory[addr as usize]
        } else {
            TWord::ZERO // Out of bounds reads return zero
        }
    }

    /// Memory write with bounds checking
    fn mem_write(&mut self, addr: i64, val: TWord) {
        if addr >= 0 && (addr as usize) < MEMORY_SIZE {
            self.memory[addr as usize] = val;
        }
    }

    /// Execute a decoded instruction
    fn execute_instruction(&mut self, inst: &Instruction) -> Result<(), String> {
        match inst.opcode {
            // ── Arithmetic ──
            Opcode::TADD => {
                let a = self.regs.read(inst.op1 as usize).to_int();
                let b = self.regs.read(inst.op2 as usize).to_int();
                self.regs.write(inst.op1 as usize, TWord::from_int(a + b));
            }
            Opcode::TADDI => {
                let a = self.regs.read(inst.op1 as usize).to_int();
                self.regs.write(inst.op1 as usize, TWord::from_int(a + inst.imm as i64));
            }
            Opcode::TSUB => {
                let a = self.regs.read(inst.op1 as usize).to_int();
                let b = self.regs.read(inst.op2 as usize).to_int();
                self.regs.write(inst.op1 as usize, TWord::from_int(a - b));
            }
            Opcode::TSUBI => {
                let a = self.regs.read(inst.op1 as usize).to_int();
                self.regs.write(inst.op1 as usize, TWord::from_int(a - inst.imm as i64));
            }
            Opcode::TMUL => {
                let a = self.regs.read(inst.op1 as usize).to_int();
                let b = self.regs.read(inst.op2 as usize).to_int();
                self.regs.write(inst.op1 as usize, TWord::from_int(a * b));
            }
            Opcode::TMULI => {
                let a = self.regs.read(inst.op1 as usize).to_int();
                self.regs.write(inst.op1 as usize, TWord::from_int(a * inst.imm as i64));
            }
            Opcode::TDIV => {
                let a = self.regs.read(inst.op1 as usize).to_int();
                let b = self.regs.read(inst.op2 as usize).to_int();
                if b == 0 { return Err("Division by zero".into()); }
                self.regs.write(inst.op1 as usize, TWord::from_int(a / b));
            }
            Opcode::TDIVI => {
                let a = self.regs.read(inst.op1 as usize).to_int();
                if inst.imm == 0 { return Err("Division by zero".into()); }
                self.regs.write(inst.op1 as usize, TWord::from_int(a / inst.imm as i64));
            }
            Opcode::TMOD => {
                let a = self.regs.read(inst.op1 as usize).to_int();
                let b = self.regs.read(inst.op2 as usize).to_int();
                if b == 0 { return Err("Modulo by zero".into()); }
                self.regs.write(inst.op1 as usize, TWord::from_int(a % b));
            }
            Opcode::TNEG => {
                let a = self.regs.read(inst.op2 as usize);
                self.regs.write(inst.op1 as usize, a.tnot());
            }
            Opcode::TABS => {
                let a = self.regs.read(inst.op2 as usize).to_int();
                self.regs.write(inst.op1 as usize, TWord::from_int(a.abs()));
            }
            Opcode::TSIGN => {
                let a = self.regs.read(inst.op2 as usize).to_int();
                let sign = if a > 0 { 1 } else if a < 0 { -1 } else { 0 };
                self.regs.write(inst.op1 as usize, TWord::from_int(sign));
            }

            // ── Logic ──
            Opcode::TAND => {
                let a = self.regs.read(inst.op1 as usize);
                let b = self.regs.read(inst.op2 as usize);
                self.regs.write(inst.op1 as usize, a.tand(&b));
            }
            Opcode::TOR => {
                let a = self.regs.read(inst.op1 as usize);
                let b = self.regs.read(inst.op2 as usize);
                self.regs.write(inst.op1 as usize, a.tor(&b));
            }
            Opcode::TNOT => {
                let a = self.regs.read(inst.op2 as usize);
                self.regs.write(inst.op1 as usize, a.tnot());
            }
            Opcode::TXOR => {
                // Ternary XOR: trit-wise multiplication
                let a = self.regs.read(inst.op1 as usize);
                let b = self.regs.read(inst.op2 as usize);
                let mut result = TWord::ZERO;
                for i in 0..27 {
                    result.trits[i] = (a.trits[i] as i16 * b.trits[i] as i16).max(-1).min(1) as i8;
                }
                self.regs.write(inst.op1 as usize, result);
            }
            Opcode::TCLAMP => {
                let a = self.regs.read(inst.op2 as usize);
                let mut result = TWord::ZERO;
                for i in 0..27 {
                    result.trits[i] = a.trits[i].max(-1).min(1);
                }
                self.regs.write(inst.op1 as usize, result);
            }
            Opcode::TANY => {
                let a = self.regs.read(inst.op2 as usize);
                let any = a.trits.iter().any(|&t| t != 0);
                self.regs.write(inst.op1 as usize, TWord::from_int(if any { 1 } else { 0 }));
            }
            Opcode::TALL => {
                let a = self.regs.read(inst.op2 as usize);
                let all = a.trits.iter().all(|&t| t != 0);
                self.regs.write(inst.op1 as usize, TWord::from_int(if all { 1 } else { 0 }));
            }
            Opcode::TCOUNT => {
                let a = self.regs.read(inst.op2 as usize);
                let count = a.trits.iter().filter(|&&t| t != 0).count();
                self.regs.write(inst.op1 as usize, TWord::from_int(count as i64));
            }

            // ── Memory ──
            Opcode::TLOAD => {
                let addr = self.regs.read(inst.op2 as usize).to_int() + inst.imm as i64;
                let val = self.mem_read(addr);
                self.regs.write(inst.op1 as usize, val);
            }
            Opcode::TSTORE => {
                let addr = self.regs.read(inst.op1 as usize).to_int() + inst.imm as i64;
                let val = self.regs.read(inst.op2 as usize);
                self.mem_write(addr, val);
            }
            Opcode::TLOADB => {
                // Load TZip byte (5 trits)
                let addr = self.regs.read(inst.op2 as usize).to_int() + inst.imm as i64;
                let word = self.mem_read(addr);
                // Extract lower 5 trits as TZip
                let mut result = TWord::ZERO;
                for i in 0..5 {
                    result.trits[i] = word.trits[i];
                }
                self.regs.write(inst.op1 as usize, result);
            }
            Opcode::TSTOREB => {
                // Store TZip byte (lower 5 trits of register)
                let addr = self.regs.read(inst.op1 as usize).to_int() + inst.imm as i64;
                let val = self.regs.read(inst.op2 as usize);
                let mut word = self.mem_read(addr);
                for i in 0..5 {
                    word.trits[i] = val.trits[i];
                }
                self.mem_write(addr, word);
            }
            Opcode::TLEA => {
                let addr = self.regs.read(inst.op2 as usize).to_int() + inst.imm as i64;
                self.regs.write(inst.op1 as usize, TWord::from_int(addr));
            }

            // ── Branch ──
            Opcode::TNOP => {} // do nothing

            Opcode::TJMP => {
                let target = self.regs.read(inst.op1 as usize).to_int() + inst.imm as i64;
                self.regs.tpc = TWord::from_int(target);
            }

            Opcode::TBR3 => {
                // THE KILLER FEATURE: 3-way branch
                let cond = self.regs.read(inst.op1 as usize).to_int();
                let pc = self.regs.tpc.to_int() - 1; // PC was already incremented
                if cond < 0 {
                    // Negative: fall through (PC already advanced)
                    // (addr_neg = PC+1, already set)
                } else if cond == 0 {
                    // Zero: branch to op2 offset
                    self.regs.tpc = TWord::from_int(pc + inst.op2 as i64);
                } else {
                    // Positive: branch to imm offset
                    self.regs.tpc = TWord::from_int(pc + inst.imm as i64);
                }
            }

            Opcode::TCMP => {
                // Compare two registers, result is {-1, 0, +1}
                let a = self.regs.read(inst.op2 as usize).to_int();
                let b_val = self.read_operand(inst.op2, inst.imm).to_int();
                // We use op1 as destination, comparing op2 vs the value at imm
                // Actually: TCMP Td, Ts1, Ts2 → Td = sign(Ts1 - Ts2)
                let a_val = self.regs.read(inst.op1 as usize).to_int();
                let b_cmp = self.regs.read(inst.op2 as usize).to_int();
                let result = if a_val < b_cmp { -1 } else if a_val > b_cmp { 1 } else { 0 };
                // Store in register indicated by immediate (or op1 if 3-operand)
                // Convention: TCMP Td, Ts1, Ts2 — but we only have 2 operand fields
                // So: TCMP op1, op2 → op1 = sign(op1 - op2)
                self.regs.write(inst.op1 as usize, TWord::from_int(result));
            }

            Opcode::TCMPI => {
                let a = self.regs.read(inst.op1 as usize).to_int();
                let result = if a < inst.imm as i64 { -1 } else if a > inst.imm as i64 { 1 } else { 0 };
                self.regs.write(inst.op1 as usize, TWord::from_int(result));
            }

            Opcode::TBRN => {
                let cond = self.regs.read(inst.op1 as usize).to_int();
                if cond < 0 {
                    let pc = self.regs.tpc.to_int() - 1;
                    self.regs.tpc = TWord::from_int(pc + inst.imm as i64);
                }
            }
            Opcode::TBRZ => {
                let cond = self.regs.read(inst.op1 as usize).to_int();
                if cond == 0 {
                    let pc = self.regs.tpc.to_int() - 1;
                    self.regs.tpc = TWord::from_int(pc + inst.imm as i64);
                }
            }
            Opcode::TBRP => {
                let cond = self.regs.read(inst.op1 as usize).to_int();
                if cond > 0 {
                    let pc = self.regs.tpc.to_int() - 1;
                    self.regs.tpc = TWord::from_int(pc + inst.imm as i64);
                }
            }
            Opcode::TBRNZ => {
                let cond = self.regs.read(inst.op1 as usize).to_int();
                if cond != 0 {
                    let pc = self.regs.tpc.to_int() - 1;
                    self.regs.tpc = TWord::from_int(pc + inst.imm as i64);
                }
            }

            // ── Call/Stack ──
            Opcode::TCALL => {
                let return_addr = self.regs.tpc.to_int(); // already PC+1
                self.regs.write(REG_LINK, TWord::from_int(return_addr));
                let target = self.regs.read(inst.op1 as usize).to_int() + inst.imm as i64;
                self.regs.tpc = TWord::from_int(target);
            }
            Opcode::TRET => {
                let return_addr = self.regs.read(REG_LINK);
                self.regs.tpc = return_addr;
            }
            Opcode::TPUSH => {
                let sp = self.regs.tsp.to_int() - 1;
                self.regs.tsp = TWord::from_int(sp);
                let val = self.regs.read(inst.op1 as usize);
                self.mem_write(sp, val);
            }
            Opcode::TPOP => {
                let sp = self.regs.tsp.to_int();
                let val = self.mem_read(sp);
                self.regs.write(inst.op1 as usize, val);
                self.regs.tsp = TWord::from_int(sp + 1);
            }
            Opcode::TENTER => {
                // Push old frame pointer, set new frame
                let sp = self.regs.tsp.to_int() - 1;
                self.regs.tsp = TWord::from_int(sp);
                self.mem_write(sp, self.regs.tfp);
                self.regs.tfp = self.regs.tsp;
            }
            Opcode::TLEAVE => {
                // Restore stack and frame pointer
                self.regs.tsp = self.regs.tfp;
                let sp = self.regs.tsp.to_int();
                self.regs.tfp = self.mem_read(sp);
                self.regs.tsp = TWord::from_int(sp + 1);
            }

            // ── Pack/Unpack ──
            Opcode::TPACK => {
                // Pack 5 register trits into TZip format in destination
                let src = self.regs.read(inst.op2 as usize);
                let tzip = TZipByte {
                    trits: [src.trits[0], src.trits[1], src.trits[2], src.trits[3], src.trits[4]],
                };
                let packed_val = tzip.to_int();
                self.regs.write(inst.op1 as usize, TWord::from_int(packed_val));
            }
            Opcode::TUNPACK => {
                // Unpack TZip integer to 5 trits in destination register
                let src_val = self.regs.read(inst.op2 as usize).to_int();
                let tzip = TZipByte::from_int(src_val);
                let mut result = TWord::ZERO;
                for i in 0..5 {
                    result.trits[i] = tzip.trits[i];
                }
                self.regs.write(inst.op1 as usize, result);
            }
            Opcode::TPACKW => {
                // Pack full TWord (27 trits) into 6 TZip bytes → write to memory
                let src = self.regs.read(inst.op1 as usize);
                let tzips = src.to_tzip();
                let base_addr = self.regs.read(inst.op2 as usize).to_int();
                for (i, tz) in tzips.iter().enumerate() {
                    self.mem_write(base_addr + i as i64, TWord::from_int(tz.to_int()));
                }
            }
            Opcode::TUNPACKW => {
                // Read 6 TZip bytes from memory → reconstruct TWord
                let base_addr = self.regs.read(inst.op2 as usize).to_int();
                let mut result = TWord::ZERO;
                for byte_idx in 0..6 {
                    let tz_val = self.mem_read(base_addr + byte_idx as i64).to_int();
                    let tz = TZipByte::from_int(tz_val);
                    for t in 0..5 {
                        let dest = byte_idx * 5 + t;
                        if dest < 27 {
                            result.trits[dest] = tz.trits[t];
                        }
                    }
                }
                self.regs.write(inst.op1 as usize, result);
            }

            // ── Shift/Rotate ──
            Opcode::TSHIFTL => {
                let src = self.regs.read(inst.op1 as usize);
                let shift = inst.imm.abs() as usize;
                let mut result = TWord::ZERO;
                for i in shift..27 {
                    result.trits[i] = src.trits[i - shift];
                }
                self.regs.write(inst.op1 as usize, result);
            }
            Opcode::TSHIFTR => {
                let src = self.regs.read(inst.op1 as usize);
                let shift = inst.imm.abs() as usize;
                let mut result = TWord::ZERO;
                for i in 0..(27 - shift) {
                    result.trits[i] = src.trits[i + shift];
                }
                self.regs.write(inst.op1 as usize, result);
            }
            Opcode::TROTL => {
                let src = self.regs.read(inst.op1 as usize);
                let rot = (inst.imm.abs() as usize) % 27;
                let mut result = TWord::ZERO;
                for i in 0..27 {
                    result.trits[(i + rot) % 27] = src.trits[i];
                }
                self.regs.write(inst.op1 as usize, result);
            }
            Opcode::TROTR => {
                let src = self.regs.read(inst.op1 as usize);
                let rot = (inst.imm.abs() as usize) % 27;
                let mut result = TWord::ZERO;
                for i in 0..27 {
                    result.trits[i] = src.trits[(i + rot) % 27];
                }
                self.regs.write(inst.op1 as usize, result);
            }
            Opcode::TEXTRACT => {
                let src = self.regs.read(inst.op1 as usize);
                let start = inst.imm.abs() as usize;
                let len = inst.op2 as usize;
                let mut result = TWord::ZERO;
                for i in 0..len.min(27) {
                    if start + i < 27 {
                        result.trits[i] = src.trits[start + i];
                    }
                }
                self.regs.write(inst.op1 as usize, result);
            }
            Opcode::TINSERT => {
                let src = self.regs.read(inst.op2 as usize);
                let mut dest = self.regs.read(inst.op1 as usize);
                let start = inst.imm.abs() as usize;
                let len = 5; // insert 5 trits (one TZip unit)
                for i in 0..len {
                    if start + i < 27 {
                        dest.trits[start + i] = src.trits[i];
                    }
                }
                self.regs.write(inst.op1 as usize, dest);
            }

            // ── System ──
            Opcode::THALT => {
                self.halted = true;
            }
            Opcode::TSYSCALL => {
                // System call dispatch (call number in imm)
                // This would interface with the NovaX orchestrator
                match inst.imm {
                    0 => { /* sys_exit */ self.halted = true; }
                    1 => { /* sys_print */
                        let val = self.regs.read(inst.op1 as usize).to_int();
                        println!("[TPRINT] T{} = {}", inst.op1, val);
                    }
                    _ => {} // unknown syscall = nop
                }
            }
            Opcode::TDEBUG => {
                let val = self.regs.read(inst.op1 as usize);
                eprintln!("[DEBUG] T{} = {} (int: {})", inst.op1, val, val.to_int());
            }
            Opcode::TPRINT => {
                let val = self.regs.read(inst.op1 as usize);
                println!("{}", val.to_int());
            }
            Opcode::TMOV => {
                let val = self.regs.read(inst.op2 as usize);
                self.regs.write(inst.op1 as usize, val);
            }
            Opcode::TMOVI => {
                self.regs.write(inst.op1 as usize, TWord::from_int(inst.imm as i64));
            }
            Opcode::TLUI => {
                // Load upper immediate: set high trits (trits 13-26)
                let imm_word = TWord::from_int(inst.imm as i64);
                let mut val = self.regs.read(inst.op1 as usize);
                for i in 0..8 {
                    if 13 + i < 27 {
                        val.trits[13 + i] = imm_word.trits[i];
                    }
                }
                self.regs.write(inst.op1 as usize, val);
            }
        }

        Ok(())
    }
}

// ============================================================================
// SECTION 8: BINARY ISA COMPARISON
// ============================================================================
//
// ┌─────────────────────────────────────────────────────────────────────────┐
// │           BINARY (x86/ARM) vs TERNARY (NovaX) ISA COMPARISON          │
// ├────────────────────┬────────────────────────┬──────────────────────────┤
// │ Feature            │ Binary ISA             │ Ternary ISA (NovaX)     │
// ├────────────────────┼────────────────────────┼──────────────────────────┤
// │ Value states       │ 2 (0, 1)               │ 3 (-1, 0, +1)          │
// │ Word size          │ 32/64 bits             │ 27 trits               │
// │ Value range (word) │ 0..2^32 or ±2^31      │ ±3,812,798,742,493     │
// │                    │ = ±2.1 billion         │ = ±3.8 trillion        │
// │ Info per digit     │ 1 bit = 1.000 bits     │ 1 trit = 1.585 bits    │
// │ Info per word      │ 32 bits                │ 27*1.585 = 42.8 bits   │
// │                    │                        │ (34% MORE per word)    │
// ├────────────────────┼────────────────────────┼──────────────────────────┤
// │ Comparison result  │ Flags register (CF,ZF, │ Direct {-1,0,+1} value │
// │                    │ SF,OF) — indirect      │ in register — direct   │
// │ 3-way branch       │ CMP + 2-3 branches     │ TCMP + TBR3 (2 instr) │
// │                    │ (3-4 instructions)     │ 50% fewer instructions │
// │ Negation           │ NEG (two's complement, │ TNOT (flip signs,      │
// │                    │ special case for MIN)  │ no special cases)      │
// │ Sign detection     │ TEST + conditional     │ Inherent (MST is sign) │
// │ Overflow           │ Flags-based detection  │ Natural balanced range │
// ├────────────────────┼────────────────────────┼──────────────────────────┤
// │ Logic operations   │ AND, OR, NOT, XOR      │ TAND(min), TOR(max),   │
// │                    │ (Boolean)              │ TNOT(negate), TXOR(mul)│
// │                    │                        │ (Kleene/Lukasiewicz)   │
// │ Logic truth values │ 2: true, false         │ 3: true, maybe, false │
// │                    │                        │ (natural for AI/fuzzy) │
// ├────────────────────┼────────────────────────┼──────────────────────────┤
// │ Memory efficiency  │ 1 byte = 8 bits        │ 1 TZip = 5 trits      │
// │ (packing)          │                        │ = 7.92 bits in 8-bit   │
// │                    │                        │ byte (99% efficient)   │
// ├────────────────────┼────────────────────────┼──────────────────────────┤
// │ Multiplication     │ Full binary multiply   │ Trit multiply:         │
// │ (weight matrices)  │ O(n) per element       │ w*x = {-x, 0, +x}     │
// │                    │                        │ = sign flip or skip    │
// │                    │                        │ NO MULTIPLIER NEEDED   │
// │                    │                        │ 3.4-10x faster matmul  │
// ├────────────────────┼────────────────────────┼──────────────────────────┤
// │ Instruction word   │ 32 bits (x86/ARM32)    │ 27 trits = 42.8 bits  │
// │                    │ 16 bits (Thumb)        │ 27 trits in 6 TZip    │
// │                    │                        │ bytes = 6 bytes        │
// │                    │                        │ (vs 4 bytes binary)    │
// │ Opcode space       │ 8-16 bits = 256-65536  │ 9 trits = 19,683      │
// │ Register space     │ 3-5 bits = 8-32 regs   │ 5 trits = 243 slots   │
// │                    │                        │ (27 regs + 213 modes)  │
// └────────────────────┴────────────────────────┴──────────────────────────┘
//
// KEY ADVANTAGES OF TERNARY ISA:
//
// 1. 3-WAY BRANCHING: TCMP+TBR3 replaces CMP+Jcc+Jcc+JMP, saving 50% of
//    branch instructions. In a typical program where ~20% of instructions
//    are branches, this is a ~10% total instruction count reduction.
//
// 2. NATURAL COMPARISON: TCMP produces {-1,0,+1} directly in a register.
//    No flags register needed. No flag-clobbering issues. The result IS
//    the answer, ready for TBR3 or further computation.
//
// 3. SIGNED ARITHMETIC FOR FREE: Balanced ternary is inherently signed.
//    No unsigned/signed distinction needed. Negation is just flipping signs
//    of all trits — no two's complement edge cases (no "most negative" trap).
//
// 4. TERNARY AI ACCELERATION: Weight matrices with values {-1,0,+1} are
//    native. TPACK/TUNPACK handle TZip compression. Matrix multiply becomes
//    pure addition/subtraction with zero-skipping: 3.4-10x faster than FP16.
//
// 5. FUZZY LOGIC NATIVE: Three-valued logic (true/maybe/false) is built in.
//    AI confidence, sensor uncertainty, null propagation — all first-class.
//
// ============================================================================

// ============================================================================
// SECTION 9: ASSEMBLY EXAMPLES
// ============================================================================
//
// Example 1: Absolute value using TBR3
// ─────────────────────────────────────
//   ; T1 = input, T2 = output
//   TSIGN T3, T1           ; T3 = sign(T1) → {-1, 0, +1}
//   TBR3  T3, +1, +2, +3   ; N→neg_case, Z→zero_case, P→pos_case
//   TNEG  T2, T1            ; neg_case: T2 = -T1 (make positive)
//   TJMP  T0, +2            ; skip to end
//   TMOV  T2, T0            ; zero_case: T2 = 0
//   TJMP  T0, +1            ; skip to end
//   TMOV  T2, T1            ; pos_case: T2 = T1 (already positive)
//   ; done: T2 = |T1|
//
// In binary ISA this would be:
//   CMP   r1, #0
//   BGE   pos_or_zero
//   NEG   r2, r1
//   B     done
//   pos_or_zero:
//   BEQ   zero_case
//   MOV   r2, r1
//   B     done
//   zero_case:
//   MOV   r2, #0
//   done:
// → 9 instructions (binary) vs 7 instructions (ternary)
// → But ternary has NO FLAGS REGISTER and the branch is ONE instruction
//
//
// Example 2: Fibonacci with TBR3
// ──────────────────────────────
//   ; T1 = n (input), T2 = fib(n) (output)
//   ; T3 = fib_prev, T4 = fib_curr, T5 = counter, T6 = temp
//   TMOVI T3, 0              ; fib_prev = 0
//   TMOVI T4, 1              ; fib_curr = 1
//   TMOV  T5, T1             ; counter = n
//   loop:
//   TCMPI T5, 0              ; compare counter to 0
//   TBR3  T5, +2, +5, +2     ; N→loop_body, Z→done, P→loop_body
//   ; loop_body:
//   TMOV  T6, T4             ; temp = fib_curr
//   TADD  T4, T3             ; fib_curr += fib_prev
//   TMOV  T3, T6             ; fib_prev = temp
//   TSUBI T5, 1              ; counter -= 1
//   TJMP  T0, -5             ; jump back to loop
//   ; done:
//   TMOV  T2, T4             ; output = fib_curr
//   THALT                    ; stop
//
//
// Example 3: TZip pack/unpack for AI weights
// ───────────────────────────────────────────
//   ; Pack 5 weight trits {+1, -1, 0, +1, -1} into TZip byte
//   TMOVI T1, 1              ; trit 0 = +1
//   TMOVI T2, -1             ; trit 1 = -1
//   ; ... (set up 5 trits in T1's lower positions)
//   TPACK T5, T1             ; T5 = TZip-packed value
//   TSTORE T10, T5, 0        ; store packed byte to memory
//   ;
//   ; Later: unpack
//   TLOAD T6, T10, 0         ; load packed byte
//   TUNPACK T7, T6           ; T7 = unpacked 5 trits
//   ; T7[0..4] now contains the original 5 weight trits
//
//
// Example 4: Function call convention
// ────────────────────────────────────
//   ; Caller: call add3(a, b, c)
//   TMOV  T1, T10            ; arg1 = a
//   TMOV  T2, T11            ; arg2 = b
//   TMOV  T3, T12            ; arg3 = c
//   TCALL T0, add3_addr      ; call (saves return addr in T26)
//   ; T1 = return value
//
//   ; Callee: fn add3(a, b, c) → a+b+c
//   add3:
//   TENTER                   ; push frame pointer
//   TADD  T1, T2             ; T1 = a + b
//   TADD  T1, T3             ; T1 = (a+b) + c
//   TLEAVE                   ; restore frame pointer
//   TRET                     ; return to caller (T26)
//
// ============================================================================

// ============================================================================
// SECTION 10: TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tword_from_int_roundtrip() {
        for val in [-1000, -1, 0, 1, 13, 27, 81, 243, 2187, 100000] {
            let w = TWord::from_int(val);
            assert_eq!(w.to_int(), val, "Roundtrip failed for {}", val);
        }
    }

    #[test]
    fn test_tword_zero() {
        let z = TWord::ZERO;
        assert_eq!(z.to_int(), 0);
        for t in z.trits.iter() {
            assert_eq!(*t, 0);
        }
    }

    #[test]
    fn test_tword_ternary_logic() {
        let a = TWord::from_int(1);   // P in trit 0
        let b = TWord::from_int(-1);  // N in trit 0

        // TNOT: negate
        let neg_a = a.tnot();
        assert_eq!(neg_a.to_int(), -1);

        // TAND: min
        let and_ab = a.tand(&b);
        assert_eq!(and_ab.trits[0], -1); // min(1, -1) = -1

        // TOR: max
        let or_ab = a.tor(&b);
        assert_eq!(or_ab.trits[0], 1);   // max(1, -1) = 1
    }

    #[test]
    fn test_tzip_roundtrip() {
        let tz = TZipByte::from_int(42);
        let val = tz.to_int();
        assert_eq!(val, 42);

        let tz_neg = TZipByte::from_int(-100);
        assert_eq!(tz_neg.to_int(), -100);
    }

    #[test]
    fn test_register_file() {
        let mut regs = RegisterFile::new();

        // T0 always reads zero
        regs.write(0, TWord::from_int(999));
        assert_eq!(regs.read(0).to_int(), 0);

        // Normal register
        regs.write(1, TWord::from_int(42));
        assert_eq!(regs.read(1).to_int(), 42);

        // Special registers
        regs.write(REG_TPC, TWord::from_int(100));
        assert_eq!(regs.read(REG_TPC).to_int(), 100);
    }

    #[test]
    fn test_instruction_encode_decode() {
        let encoded = encode_instruction(Opcode::TADD, 1, 2, 0);
        let decoded = decode_instruction(&encoded);
        assert_eq!(decoded.opcode, Opcode::TADD);
        assert_eq!(decoded.op1, 1);
        assert_eq!(decoded.op2, 2);
    }

    #[test]
    fn test_vm_simple_add() {
        let mut vm = TernaryVM::new();
        let program = vec![
            encode_instruction(Opcode::TMOVI, 1, 0, 10),   // T1 = 10
            encode_instruction(Opcode::TMOVI, 2, 0, 32),   // T2 = 32
            encode_instruction(Opcode::TADD,  1, 2, 0),    // T1 = T1 + T2 = 42
            encode_instruction(Opcode::THALT, 0, 0, 0),    // halt
        ];
        vm.load_program(&program);
        let cycles = vm.run().unwrap();
        assert_eq!(vm.regs.read(1).to_int(), 42);
        assert_eq!(cycles, 4);
    }

    #[test]
    fn test_vm_tbr3_negative() {
        // Test 3-way branch with negative input
        let mut vm = TernaryVM::new();
        let program = vec![
            encode_instruction(Opcode::TMOVI, 1, 0, -5),   // T1 = -5 (negative)
            encode_instruction(Opcode::TSIGN, 2, 1, 0),    // T2 = sign(T1) = -1
            // TBR3: N→fall-through(PC+1=3), Z→PC+op2, P→PC+imm
            encode_instruction(Opcode::TBR3,  2, 5, 7),    // branch on T2
            // addr 3: negative case (fall-through)
            encode_instruction(Opcode::TMOVI, 3, 0, -1),   // T3 = -1 (we took neg path)
            encode_instruction(Opcode::THALT, 0, 0, 0),    // halt
        ];
        vm.load_program(&program);
        vm.run().unwrap();
        assert_eq!(vm.regs.read(3).to_int(), -1, "Should take negative branch");
    }

    #[test]
    fn test_vm_tbr3_zero() {
        // Test 3-way branch with zero input
        let mut vm = TernaryVM::new();
        let program = vec![
            encode_instruction(Opcode::TMOVI, 1, 0, 0),    // T1 = 0
            encode_instruction(Opcode::TSIGN, 2, 1, 0),    // T2 = sign(T1) = 0
            // TBR3 at PC=2: N→fall(3), Z→PC+4=6, P→PC+6=8
            encode_instruction(Opcode::TBR3,  2, 4, 6),
            // addr 3: negative case
            encode_instruction(Opcode::TMOVI, 3, 0, -1),
            encode_instruction(Opcode::THALT, 0, 0, 0),
            // addr 5: (padding)
            encode_instruction(Opcode::TNOP,  0, 0, 0),
            // addr 6: zero case (TBR3 op2 offset = 4, so PC=2+4=6)
            encode_instruction(Opcode::TMOVI, 3, 0, 0),    // T3 = 0 (we took zero path)
            encode_instruction(Opcode::THALT, 0, 0, 0),
        ];
        vm.load_program(&program);
        vm.run().unwrap();
        assert_eq!(vm.regs.read(3).to_int(), 0, "Should take zero branch");
    }

    #[test]
    fn test_vm_tbr3_positive() {
        // Test 3-way branch with positive input
        let mut vm = TernaryVM::new();
        let program = vec![
            encode_instruction(Opcode::TMOVI, 1, 0, 7),    // T1 = 7 (positive)
            encode_instruction(Opcode::TSIGN, 2, 1, 0),    // T2 = sign(T1) = +1
            // TBR3 at PC=2: N→fall(3), Z→PC+5=7, P→PC+7=9
            encode_instruction(Opcode::TBR3,  2, 5, 7),
            // addr 3: negative case
            encode_instruction(Opcode::TMOVI, 3, 0, -1),
            encode_instruction(Opcode::THALT, 0, 0, 0),
            // addr 5-6: padding
            encode_instruction(Opcode::TNOP,  0, 0, 0),
            encode_instruction(Opcode::TNOP,  0, 0, 0),
            // addr 7: zero case
            encode_instruction(Opcode::TMOVI, 3, 0, 0),
            encode_instruction(Opcode::THALT, 0, 0, 0),
            // addr 9: positive case (TBR3 imm offset = 7, PC=2+7=9)
            encode_instruction(Opcode::TMOVI, 3, 0, 1),    // T3 = 1 (we took pos path)
            encode_instruction(Opcode::THALT, 0, 0, 0),
        ];
        vm.load_program(&program);
        vm.run().unwrap();
        assert_eq!(vm.regs.read(3).to_int(), 1, "Should take positive branch");
    }

    #[test]
    fn test_vm_push_pop() {
        let mut vm = TernaryVM::new();
        let program = vec![
            encode_instruction(Opcode::TMOVI, 1, 0, 42),   // T1 = 42
            encode_instruction(Opcode::TPUSH, 1, 0, 0),    // push T1
            encode_instruction(Opcode::TMOVI, 1, 0, 0),    // T1 = 0 (clear it)
            encode_instruction(Opcode::TPOP,  2, 0, 0),    // pop into T2
            encode_instruction(Opcode::THALT, 0, 0, 0),
        ];
        vm.load_program(&program);
        vm.run().unwrap();
        assert_eq!(vm.regs.read(2).to_int(), 42);
    }

    #[test]
    fn test_vm_tpack_tunpack() {
        let mut vm = TernaryVM::new();
        let program = vec![
            encode_instruction(Opcode::TMOVI, 1, 0, 100),  // T1 = 100 (some value)
            encode_instruction(Opcode::TPACK, 2, 1, 0),    // T2 = pack(T1 lower 5 trits)
            encode_instruction(Opcode::TUNPACK, 3, 2, 0),   // T3 = unpack(T2)
            encode_instruction(Opcode::THALT, 0, 0, 0),
        ];
        vm.load_program(&program);
        vm.run().unwrap();
        // The lower 5 trits of T1 should survive pack/unpack
        let t1 = vm.regs.read(1);
        let t3 = vm.regs.read(3);
        for i in 0..5 {
            assert_eq!(t1.trits[i], t3.trits[i], "Trit {} mismatch after pack/unpack", i);
        }
    }

    #[test]
    fn test_vm_shift_left() {
        let mut vm = TernaryVM::new();
        let program = vec![
            encode_instruction(Opcode::TMOVI, 1, 0, 1),    // T1 = 1 (P in trit 0)
            encode_instruction(Opcode::TSHIFTL, 1, 0, 3),  // shift left 3 → trit 3 = P = 3^3 = 27
            encode_instruction(Opcode::THALT, 0, 0, 0),
        ];
        vm.load_program(&program);
        vm.run().unwrap();
        assert_eq!(vm.regs.read(1).to_int(), 27, "1 shifted left 3 trits = 3^3 = 27");
    }

    #[test]
    fn test_vm_tcmp_tbr3_integration() {
        // Full integration: compare two values, 3-way branch
        let mut vm = TernaryVM::new();
        let program = vec![
            encode_instruction(Opcode::TMOVI, 1, 0, 10),   // T1 = 10
            encode_instruction(Opcode::TMOVI, 2, 0, 10),   // T2 = 10
            encode_instruction(Opcode::TCMP,  1, 2, 0),    // T1 = sign(T1-T2) = 0 (equal)
            // TBR3 at PC=3: N→fall(4), Z→PC+3=6, P→PC+5=8
            encode_instruction(Opcode::TBR3,  1, 3, 5),
            // addr 4: less case
            encode_instruction(Opcode::TMOVI, 5, 0, -1),
            encode_instruction(Opcode::THALT, 0, 0, 0),
            // addr 6: equal case
            encode_instruction(Opcode::TMOVI, 5, 0, 0),    // T5 = 0 (equal!)
            encode_instruction(Opcode::THALT, 0, 0, 0),
            // addr 8: greater case
            encode_instruction(Opcode::TMOVI, 5, 0, 1),
            encode_instruction(Opcode::THALT, 0, 0, 0),
        ];
        vm.load_program(&program);
        vm.run().unwrap();
        assert_eq!(vm.regs.read(5).to_int(), 0, "10 == 10 should take zero/equal branch");
    }

    #[test]
    fn test_harmonic_constants() {
        // Verify 3-5-7-13 constants work in ternary
        assert_eq!(TWord::from_int(3).to_int(), 3);     // H3
        assert_eq!(TWord::from_int(243).to_int(), 243);  // 3^5 TZip
        assert_eq!(TWord::from_int(2187).to_int(), 2187); // 3^7 BLOCK_SIZE
        assert_eq!(TWord::from_int(1594323).to_int(), 1594323); // 3^13 MEMORY_SIZE

        // 3^27 - 1 (max value check)
        let max_val = 3i64.pow(27) / 2; // 3,812,798,742,493
        let w = TWord::from_int(max_val);
        assert_eq!(w.to_int(), max_val);
    }

    #[test]
    fn test_addr_mode_decode() {
        // Register mode
        let (mode, idx) = decode_addr_mode(5);
        assert_eq!(mode, AddrMode::Register);
        assert_eq!(idx, 5);

        // Immediate mode
        let (mode, _) = decode_addr_mode(30);
        assert_eq!(mode, AddrMode::Immediate);

        // Direct mode
        let (mode, idx) = decode_addr_mode(35);
        assert_eq!(mode, AddrMode::Direct);
        assert_eq!(idx, 4);
    }
}
