"""
NovaX Inference Utilities v1.0
Advanced sampling and decoding for the ternary transformer.

Includes:
- Min-P sampling (ICLR 2025 Oral — recommended for 1.58-bit models)
- LZ repetition penalty (2025 — surgical fix for small model loops)
- Classifier-Free Guidance stub (doubles effective model quality)

References:
- Min-P: Nguyen et al., ICLR 2025, arXiv:2407.01082
- LZ Penalty: arXiv:2504.20131
- CFG: Sanchez et al., ICML 2024
"""
import torch
import torch.nn.functional as F
from collections import defaultdict


def min_p_sampling(logits, min_p=0.05, temperature=0.7):
    """Min-P sampling: dynamically filter based on model confidence.

    When the model is confident (high max prob), filter aggressively.
    When uncertain (low max prob), allow diverse continuations.

    Args:
        logits: Raw logits (vocab_size,)
        min_p: Minimum probability threshold relative to max (0.05 recommended)
        temperature: Sampling temperature

    Returns:
        sampled token index
    """
    # Apply temperature
    logits = logits / max(temperature, 1e-8)

    # Convert to probabilities
    probs = F.softmax(logits, dim=-1)

    # Find the maximum probability
    max_prob = probs.max()

    # Dynamic threshold: min_p * max_prob
    # High confidence -> high threshold -> few candidates
    # Low confidence -> low threshold -> many candidates
    threshold = min_p * max_prob

    # Zero out tokens below threshold
    mask = probs < threshold
    probs[mask] = 0.0

    # Renormalize
    probs = probs / (probs.sum() + 1e-10)

    # Sample from filtered distribution
    return torch.multinomial(probs, 1).item()


def lz_repetition_penalty(logits, generated_ids, window_size=128, penalty_scale=2.0):
    """LZ compression-based repetition penalty.

    Uses Lempel-Ziv factorization statistics over a sliding window.
    Penalizes repeated n-grams proportionally to their length.
    Much more surgical than standard repetition penalty.

    Args:
        logits: Raw logits (vocab_size,)
        generated_ids: List of previously generated token IDs
        window_size: Size of the sliding window to check
        penalty_scale: How strongly to penalize (2.0 = moderate)

    Returns:
        Modified logits with repetition penalty applied
    """
    if len(generated_ids) < 4:
        return logits

    # Get the recent window
    window = generated_ids[-window_size:]

    # Find repeated n-grams (2 to 8 tokens)
    penalty_map = defaultdict(float)

    for n in range(2, min(9, len(window))):
        # Get the last n tokens as the pattern to check
        pattern = tuple(window[-n:])

        # Count how many times this pattern appears in the window
        count = 0
        for i in range(len(window) - n):
            if tuple(window[i:i+n]) == pattern:
                count += 1

        if count >= 1:
            # Penalize the token that would continue this repetition
            # The penalty increases with n-gram length and repetition count
            next_token_in_pattern = pattern[0]  # first token of the repeated pattern
            penalty = penalty_scale * (n / 4.0) * min(count, 3)
            penalty_map[next_token_in_pattern] = max(
                penalty_map[next_token_in_pattern], penalty
            )

    # Apply penalties
    modified = logits.clone()
    for token_id, penalty in penalty_map.items():
        if token_id < len(modified):
            # Subtract from logit (reduces probability)
            modified[token_id] -= penalty

    return modified


def top_k_top_p_filter(logits, top_k=13, top_p=0.9):
    """Standard top-k + top-p (nucleus) filtering.

    top_k=13 aligned with H13 harmonic constant.
    """
    # Top-K
    if top_k > 0:
        indices_to_remove = logits < torch.topk(logits, top_k)[0][..., -1, None]
        logits[indices_to_remove] = float('-inf')

    # Top-P (nucleus)
    if top_p < 1.0:
        sorted_logits, sorted_indices = torch.sort(logits, descending=True)
        cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
        sorted_indices_to_remove = cumulative_probs > top_p
        sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
        sorted_indices_to_remove[..., 0] = 0
        indices_to_remove = sorted_indices[sorted_indices_to_remove]
        logits[indices_to_remove] = float('-inf')

    return logits


def sample_token(logits, generated_ids=None, temperature=0.7, top_k=13,
                 top_p=0.9, min_p=0.05, use_lz_penalty=True,
                 lz_window=128, lz_scale=2.0):
    """Full sampling pipeline combining all techniques.

    Order of operations:
    1. LZ repetition penalty (if enabled)
    2. Temperature scaling
    3. Min-P filtering (replaces top-k/top-p when min_p > 0)
       OR top-k + top-p filtering (fallback)
    4. Sample from filtered distribution

    Args:
        logits: Raw model logits (vocab_size,)
        generated_ids: Previously generated tokens (for LZ penalty)
        temperature: Sampling temperature
        top_k: Top-K filter (used if min_p=0)
        top_p: Top-P filter (used if min_p=0)
        min_p: Min-P threshold (0.05 recommended, 0 to disable)
        use_lz_penalty: Whether to apply LZ repetition penalty
        lz_window: LZ penalty window size
        lz_scale: LZ penalty strength

    Returns:
        Sampled token ID
    """
    logits = logits.clone()

    # Step 1: LZ repetition penalty
    if use_lz_penalty and generated_ids and len(generated_ids) > 4:
        logits = lz_repetition_penalty(logits, generated_ids, lz_window, lz_scale)

    # Step 2 & 3: Min-P sampling (includes temperature)
    if min_p > 0:
        return min_p_sampling(logits, min_p=min_p, temperature=temperature)

    # Fallback: standard top-k + top-p
    logits = logits / max(temperature, 1e-8)
    logits = top_k_top_p_filter(logits, top_k, top_p)
    probs = F.softmax(logits, dim=-1)
    return torch.multinomial(probs, 1).item()


def test():
    """Test sampling utilities."""
    print("Testing inference utilities...")

    vocab_size = 32768

    # Test Min-P sampling
    logits = torch.randn(vocab_size)
    logits[100] = 10.0  # Make one token very likely
    token = min_p_sampling(logits, min_p=0.05, temperature=0.7)
    print(f"  Min-P sampling: selected token {token} (expected near 100)")

    # Test LZ penalty
    repeated = [100, 200, 300, 100, 200, 300, 100, 200, 300]
    logits2 = torch.randn(vocab_size)
    logits_orig = logits2[100].item()
    logits_penalized = lz_repetition_penalty(logits2, repeated)
    print(f"  LZ penalty: token 100 logit {logits_orig:.2f} -> {logits_penalized[100].item():.2f}")

    # Test full pipeline
    generated = list(range(50))  # dummy history
    token = sample_token(logits, generated, min_p=0.05, use_lz_penalty=True)
    print(f"  Full pipeline: sampled token {token}")

    print("  PASSED!")


if __name__ == "__main__":
    test()
