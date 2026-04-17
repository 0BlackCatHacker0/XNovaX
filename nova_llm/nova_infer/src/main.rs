//! NovaX Ternary LLM Inference Engine
//!
//! Pure Rust inference — no Python, no PyTorch, no CUDA.
//! Loads a .trit checkpoint and runs the transformer forward pass
//! using trit_engine's AVX2 SIMD ternary matmul (additions only).
//!
//! Modes:
//!   nova_infer --prompt "What is ML?"        Single generation
//!   nova_infer --interactive                  REPL chat mode
//!   nova_infer --api --port 9805             HTTP API server

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::io::{self, BufRead, Write};

// ─────────────────────────────────────────────────────────
// Model Configuration
// ─────────────────────────────────────────────────────────

const DEFAULT_CHECKPOINT: &str = "C:/NovaX/nova_llm/checkpoints/novax_llm_v1.trit";
const DEFAULT_VOCAB: &str = "C:/NovaX/nova_llm/bpe_vocab_32k.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ModelConfig {
    embed_dim: usize,
    num_layers: usize,
    num_heads: usize,
    head_dim: usize,
    vocab_size: usize,
    max_seq_len: usize,
    ffn_dim: usize,
}

impl Default for ModelConfig {
    fn default() -> Self {
        ModelConfig {
            embed_dim: 1024,
            num_layers: 16,
            num_heads: 16,
            head_dim: 64,
            vocab_size: 32768,
            max_seq_len: 256,
            ffn_dim: 4096,
        }
    }
}

// ─────────────────────────────────────────────────────────
// BPE Tokenizer (minimal, matches bpe_vocab_32k.json)
// ─────────────────────────────────────────────────────────

struct BpeTokenizer {
    token_to_id: HashMap<String, u32>,
    id_to_token: HashMap<u32, String>,
    merges: Vec<(String, String)>,
}

impl BpeTokenizer {
    fn load(path: &str) -> Result<Self, Box<dyn std::error::Error>> {
        let content = fs::read_to_string(path)?;
        let json: serde_json::Value = serde_json::from_str(&content)?;

        let mut token_to_id = HashMap::new();
        let mut id_to_token = HashMap::new();

        if let Some(vocab) = json.get("vocab").and_then(|v| v.as_object()) {
            for (token, id) in vocab {
                let id = id.as_u64().unwrap_or(0) as u32;
                token_to_id.insert(token.clone(), id);
                id_to_token.insert(id, token.clone());
            }
        }

        let mut merges = Vec::new();
        if let Some(merge_list) = json.get("merges").and_then(|m| m.as_array()) {
            for m in merge_list {
                if let Some(s) = m.as_str() {
                    let parts: Vec<&str> = s.splitn(2, ' ').collect();
                    if parts.len() == 2 {
                        merges.push((parts[0].to_string(), parts[1].to_string()));
                    }
                }
            }
        }

        println!("  Tokenizer: {} vocab, {} merges", token_to_id.len(), merges.len());
        Ok(BpeTokenizer {
            token_to_id,
            id_to_token,
            merges,
        })
    }

    fn encode(&self, text: &str) -> Vec<u32> {
        // Character-level initial split
        let mut tokens: Vec<String> = text.chars().map(|c| c.to_string()).collect();

        // Apply BPE merges greedily
        for (a, b) in &self.merges {
            let merged = format!("{}{}", a, b);
            let mut i = 0;
            while i + 1 < tokens.len() {
                if tokens[i] == *a && tokens[i + 1] == *b {
                    tokens[i] = merged.clone();
                    tokens.remove(i + 1);
                } else {
                    i += 1;
                }
            }
        }

        // Map to IDs
        tokens
            .iter()
            .map(|t| *self.token_to_id.get(t).unwrap_or(&0))
            .collect()
    }

    fn decode(&self, ids: &[u32]) -> String {
        ids.iter()
            .map(|id| {
                self.id_to_token
                    .get(id)
                    .cloned()
                    .unwrap_or_else(|| format!("[{}]", id))
            })
            .collect::<Vec<_>>()
            .join("")
    }
}

// ─────────────────────────────────────────────────────────
// Ternary Model (loaded from .trit checkpoint)
// ─────────────────────────────────────────────────────────

struct TernaryModel {
    config: ModelConfig,
    // Weights stored as TZip-packed bytes per layer
    // Each layer has: q_proj, k_proj, v_proj, o_proj, ffn_up, ffn_down, ffn_gate
    // Plus: token_embed, ln weights, lm_head
    //
    // TODO: Load from .trit checkpoint format
    // For now, this is the skeleton — the actual weight loading
    // will be implemented once we define the .trit binary format
    _placeholder: Vec<u8>,
}

impl TernaryModel {
    fn load(checkpoint_path: &str, config: ModelConfig) -> Result<Self, Box<dyn std::error::Error>> {
        println!("  Loading checkpoint: {}", checkpoint_path);
        let data = fs::read(checkpoint_path)?;
        println!("  Checkpoint size: {:.1} MB", data.len() as f64 / 1024.0 / 1024.0);
        println!("  Config: {}d, {}L, {}H, vocab {}",
            config.embed_dim, config.num_layers, config.num_heads, config.vocab_size);

        // TODO: Parse the .trit format and extract packed ternary weights
        // The trit_engine crate provides expand_trit_bitmaps() for SIMD inference

        Ok(TernaryModel {
            config,
            _placeholder: data,
        })
    }

    fn generate(&self, _input_ids: &[u32], _max_new_tokens: usize, _temperature: f32) -> Vec<u32> {
        // HONEST ERROR: the Rust inference path is NOT YET IMPLEMENTED.
        // Previous version silently returned the input unchanged, which was a
        // hallucination — the CLI printed "Ternary LLM Inference (Rust)" and
        // loaded a checkpoint but did no forward pass. Now we refuse to
        // generate and point the user to the working Python path.
        //
        // To implement: port the TernaryTransformer forward pass from train.py:
        //   1. Token embedding lookup
        //   2. For each layer: RMSNorm → QKV → RoPE → Attn → OutProj → residual → RMSNorm → FFN → residual
        //   3. Final RMSNorm → LM head → logits → temperature sampling
        // The trit_engine crate provides SIMD matmul primitives ready for use.
        eprintln!();
        eprintln!("  ERROR: Rust inference forward pass is not yet implemented.");
        eprintln!("  Use the Python path instead:");
        eprintln!("      python C:/NovaX/nova_llm/chat.py --prompt \"your prompt here\"");
        eprintln!();
        eprintln!("  When this Rust path is ready, the trit_engine SIMD matmul");
        eprintln!("  will drive all Q/K/V/O and FFN layers. Skeleton is complete");
        eprintln!("  (tokenizer, checkpoint loader, CLI); forward pass is the");
        eprintln!("  remaining work (~500-800 lines of transformer math).");
        eprintln!();
        std::process::exit(2);
    }
}

// ─────────────────────────────────────────────────────────
// CLI Interface
// ─────────────────────────────────────────────────────────

fn print_banner(config: &ModelConfig) {
    println!("============================================================");
    println!("  NovaX Ternary LLM Inference (Rust) — SKELETON ONLY");
    println!("  Forward pass not yet implemented — use chat.py for real inference");
    println!("============================================================");
    // Param count = token embedding + per-layer (attention Q/K/V/O + FFN gate/up/down)
    //             = vocab*embed + layers * (4*embed^2 + 3*embed*ffn_dim)
    // Previously missed the 4*embed^2 attention-projection term entirely.
    let attn_params = 4 * config.embed_dim * config.embed_dim;
    let ffn_params = 3 * config.embed_dim * config.ffn_dim;
    let total_params = config.embed_dim * config.vocab_size
        + config.num_layers * (attn_params + ffn_params);
    println!("  Parameters:    ~{}M", total_params / 1_000_000);
    println!("  Embed dim:     {}", config.embed_dim);
    println!("  Layers:        {}", config.num_layers);
    println!("  Heads:         {}", config.num_heads);
    println!("  Max seq len:   {}", config.max_seq_len);
    println!("  Vocab size:    {}", config.vocab_size);
    println!("  Engine:        trit_engine (AVX2 SIMD)");
    println!("  Runtime:       Pure Rust (no Python, no PyTorch)");
    println!("============================================================");
}

fn interactive_mode(model: &TernaryModel, tokenizer: &BpeTokenizer) {
    let stdin = io::stdin();
    let mut stdout = io::stdout();

    loop {
        print!("\nNovaX> ");
        stdout.flush().unwrap();

        let mut input = String::new();
        if stdin.lock().read_line(&mut input).is_err() || input.trim().is_empty() {
            continue;
        }

        let input = input.trim();
        match input {
            "/quit" | "/exit" | "/q" => break,
            "/help" => {
                println!("Commands: /quit, /help");
                continue;
            }
            _ => {}
        }

        let tokens = tokenizer.encode(input);
        let start = std::time::Instant::now();
        let output = model.generate(&tokens, 256, 0.7);
        let elapsed = start.elapsed();

        let text = tokenizer.decode(&output);
        println!("{}", text);
        println!("  [{} tokens, {:.2}s]", output.len(), elapsed.as_secs_f64());
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    let checkpoint = args
        .iter()
        .position(|a| a == "--checkpoint")
        .and_then(|i| args.get(i + 1))
        .map(|s| s.as_str())
        .unwrap_or(DEFAULT_CHECKPOINT);

    let vocab_path = args
        .iter()
        .position(|a| a == "--vocab")
        .and_then(|i| args.get(i + 1))
        .map(|s| s.as_str())
        .unwrap_or(DEFAULT_VOCAB);

    let config = ModelConfig::default();
    print_banner(&config);

    // Load tokenizer
    let tokenizer = match BpeTokenizer::load(vocab_path) {
        Ok(t) => t,
        Err(e) => {
            eprintln!("Failed to load tokenizer: {}", e);
            std::process::exit(1);
        }
    };

    // Load model
    let model = match TernaryModel::load(checkpoint, config) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("Failed to load model: {}", e);
            std::process::exit(1);
        }
    };

    // Mode selection
    if let Some(prompt_pos) = args.iter().position(|a| a == "--prompt") {
        if let Some(prompt) = args.get(prompt_pos + 1) {
            let tokens = tokenizer.encode(prompt);
            let output = model.generate(&tokens, 256, 0.7);
            println!("{}", tokenizer.decode(&output));
        }
    } else {
        interactive_mode(&model, &tokenizer);
    }
}
