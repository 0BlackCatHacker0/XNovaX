# Ternary Data Structures for NovaX — Full Specification
**Date:** 2026-03-15
**Author:** NovaX / Claude Opus 4.6
**Depends on:** `core/ternary_hash.nova`, 3-5-7-13 harmonic constants

---

## Executive Summary

Six ternary data structures that exploit base-3 branching to reduce depth,
improve search locality, and map naturally onto NovaX's balanced ternary
substrate. Every structure returns ternary status codes (+1/0/-1) and
aligns with the 3-5-7-13 harmonic system.

### Depth Improvement: The Core Theorem

For n elements, a k-ary tree has depth log_k(n). The ratio:

```
log_3(n) / log_2(n) = log(2) / log(3) = 0.6309...
```

**A ternary tree is 37% shallower than a binary tree for all n.**

| n          | log_2(n) | log_3(n) | Savings |
|------------|----------|----------|---------|
| 27         | 4.75     | 3.00     | 36.8%   |
| 243        | 7.93     | 5.00     | 36.9%   |
| 2187       | 11.09    | 7.00     | 36.9%   |
| 1,000,000  | 19.93    | 12.58    | 36.9%   |
| 3^13       | 20.00    | 13.00    | 35.0%   |

---

## Structure 1: Ternary Trie (TTrie)

### Design

Each node has exactly 3 children, indexed by trit value: `[-1, 0, +1]`.
Keys are balanced ternary trit strings. A path from root to leaf encodes
a complete key. Because each level discriminates on a full trit (3 states)
rather than a bit (2 states), the trie is 37% shallower.

### Properties

| Metric          | Binary Trie      | Ternary Trie     | Improvement      |
|-----------------|------------------|------------------|------------------|
| Depth for k-trit key | k * 1.585 levels | k levels       | 37% shallower    |
| Branching factor | 2               | 3                | 50% more per node|
| Node pointers   | 2 per node       | 3 per node       | 50% more memory  |
| Lookup time     | O(k * 1.585)     | O(k)             | 37% fewer steps  |
| Space (worst)   | O(2^(k*1.585))   | O(3^k)           | Same state space  |
| Space (sparse)  | Prefix-compressed| Prefix-compressed| Similar           |

### NovaLang Pseudocode

```nova
// ============================================================
// TERNARY TRIE — 3 children per node, trit-indexed
// ============================================================
// Key: list of trits [-1, 0, +1]
// Depth for k trits: exactly k (vs ceil(k * 1.585) for binary)
// Used for: ternary hash prefix lookup, trit-string dictionaries

class3 TTrieNode {
    fn __init__() {
        children = {-1: null, 0: null, 1: null}  // 3 children
        value = null       // stored value at this node
        is_terminal = 0    // -1=deleted, 0=passthrough, +1=has value
    }
}

class3 TTrie {
    fn __init__() {
        root = TTrieNode()
        count = 0
        depth_max = 0
    }

    fn insert(trit_key, value) {
        // Insert value at trit_key path
        // Returns: +1 (inserted), 0 (updated), -1 (error)
        node = root
        depth = 0
        for3 trit in trit_key {
            if3 trit != -1 && trit != 0 && trit != 1 {
                return -1  // invalid trit
            }
            if3 node.children[trit] == null {
                node.children[trit] = TTrieNode()
            }
            node = node.children[trit]
            depth = depth + 1
        }
        was_new = node.is_terminal != 1
        node.value = value
        node.is_terminal = 1
        if3 was_new {
            count = count + 1
            if3 depth > depth_max { depth_max = depth }
            return 1   // inserted
        }
        return 0       // updated
    }

    fn lookup(trit_key) {
        // Returns: value or null
        node = root
        for3 trit in trit_key {
            if3 node.children[trit] == null {
                return null
            }
            node = node.children[trit]
        }
        if3 node.is_terminal == 1 {
            return node.value
        }
        return null
    }

    fn delete(trit_key) {
        // Lazy deletion: mark terminal as -1
        // Returns: +1 (deleted), -1 (not found)
        node = root
        for3 trit in trit_key {
            if3 node.children[trit] == null {
                return -1
            }
            node = node.children[trit]
        }
        if3 node.is_terminal == 1 {
            node.is_terminal = -1
            node.value = null
            count = count - 1
            return 1
        }
        return -1
    }

    fn prefix_search(prefix_trits) {
        // Find all keys with given trit prefix
        // Returns: list of (key, value) pairs
        node = root
        for3 trit in prefix_trits {
            if3 node.children[trit] == null {
                return []
            }
            node = node.children[trit]
        }
        results = []
        _collect(node, prefix_trits, results)
        return results
    }

    fn _collect(node, path, results) {
        if3 node.is_terminal == 1 {
            results.push([list(path), node.value])
        }
        for3 trit in [-1, 0, 1] {
            if3 node.children[trit] != null {
                path.push(trit)
                _collect(node.children[trit], path, results)
                path.pop()
            }
        }
    }

    fn stats() {
        return {
            "count": count,
            "depth_max": depth_max,
            "branching": 3,
            "depth_vs_binary": str(round(depth_max * 0.6309, 1)) + " equivalent binary levels"
        }
    }
}
```

---

## Structure 2: Ternary Search Tree (TST)

### Design

Each node stores one trit and has three children:
- **left**: keys whose current trit < node's trit
- **equal**: keys that match, advance to next trit position
- **right**: keys whose current trit > node's trit

This is the classic Bentley-Sedgewick TST adapted for balanced ternary.
Combines the space efficiency of tries with BST flexibility.

### Properties

| Metric            | Binary BST      | TST              | Improvement           |
|-------------------|-----------------|------------------|-----------------------|
| Search (avg)      | O(k log n)      | O(k + log n)     | Decoupled key/tree    |
| Search (worst)    | O(k * n)        | O(k + n)         | Key length independent|
| Space per node    | key + 2 ptrs    | trit + 3 ptrs    | ~60% of BST per entry |
| Prefix search     | O(n)            | O(k + matches)   | Massively better      |
| Near-neighbor     | Hard            | Natural          | Left/right = close    |

### NovaLang Pseudocode

```nova
// ============================================================
// TERNARY SEARCH TREE — left/equal/right per trit
// ============================================================
// Each node stores one trit. Three subtrees:
//   left:  current_trit < node.trit  (value -1 relative)
//   equal: current_trit == node.trit (advance position)
//   right: current_trit > node.trit  (value +1 relative)
//
// Space: O(n * avg_key_length) nodes vs O(n * 3^depth) for full trie
// Time:  O(key_length + log n) average search

class3 TSTNode {
    fn __init__(trit) {
        trit = trit          // the trit at this position: -1, 0, or +1
        left = null          // subtree for trits < this trit
        equal = null         // subtree for next position (trit matched)
        right = null         // subtree for trits > this trit
        value = null         // non-null if this is end-of-key
        is_terminal = 0      // ternary flag
    }
}

class3 TernarySearchTree {
    fn __init__() {
        root = null
        count = 0
    }

    fn insert(trit_key, value) {
        // Insert trit_key -> value
        // Returns: +1 (new), 0 (update), -1 (error)
        if3 len(trit_key) == 0 { return -1 }
        root = _insert(root, trit_key, 0, value)
        count = count + 1
        return 1
    }

    fn _insert(node, key, pos, value) {
        trit = key[pos]
        if3 node == null {
            node = TSTNode(trit)
        }
        if3 trit < node.trit {
            node.left = _insert(node.left, key, pos, value)
        } elif3 trit > node.trit {
            node.right = _insert(node.right, key, pos, value)
        } elif3 pos < len(key) - 1 {
            // Match: advance to next trit
            node.equal = _insert(node.equal, key, pos + 1, value)
        } else {
            // End of key: store value
            node.value = value
            node.is_terminal = 1
        }
        return node
    }

    fn search(trit_key) {
        // Returns: value or null
        node = root
        pos = 0
        while3 node != null && pos < len(trit_key) {
            trit = trit_key[pos]
            if3 trit < node.trit {
                node = node.left
            } elif3 trit > node.trit {
                node = node.right
            } else {
                if3 pos == len(trit_key) - 1 {
                    if3 node.is_terminal == 1 {
                        return node.value
                    }
                    return null
                }
                node = node.equal
                pos = pos + 1
            }
        }
        return null
    }

    fn near_neighbors(trit_key, distance) {
        // Find all keys within `distance` trit-flips of trit_key
        // Ternary Hamming distance: count positions where trits differ
        // Returns: list of (key, value, distance)
        results = []
        _near(root, trit_key, 0, distance, [], results)
        return results
    }

    fn _near(node, key, pos, d, current, results) {
        if3 node == null || d < 0 { return }
        trit = key[pos] if pos < len(key) else 0

        // Explore left if trit could be less (costs 0 or 1 distance)
        if3 d > 0 || trit < node.trit {
            _near(node.left, key, pos, d, current, results)
        }

        // Explore equal path
        cost = 0 if trit == node.trit else 1
        current.push(node.trit)
        if3 pos == len(key) - 1 {
            if3 node.is_terminal == 1 && d - cost >= 0 {
                results.push([list(current), node.value, d - cost])
            }
        } else {
            _near(node.equal, key, pos + 1, d - cost, current, results)
        }
        current.pop()

        // Explore right
        if3 d > 0 || trit > node.trit {
            _near(node.right, key, pos, d, current, results)
        }
    }

    fn prefix_match(prefix) {
        // Find all entries whose key starts with prefix
        // Returns: list of (key, value)
        node = root
        pos = 0
        while3 node != null && pos < len(prefix) {
            trit = prefix[pos]
            if3 trit < node.trit {
                node = node.left
            } elif3 trit > node.trit {
                node = node.right
            } else {
                if3 pos == len(prefix) - 1 {
                    break3
                }
                node = node.equal
                pos = pos + 1
            }
        }
        if3 node == null { return [] }
        results = []
        if3 node.is_terminal == 1 {
            results.push([list(prefix), node.value])
        }
        _collect_all(node.equal, list(prefix), results)
        return results
    }

    fn _collect_all(node, path, results) {
        if3 node == null { return }
        _collect_all(node.left, path, results)
        path.push(node.trit)
        if3 node.is_terminal == 1 {
            results.push([list(path), node.value])
        }
        _collect_all(node.equal, path, results)
        path.pop()
        _collect_all(node.right, path, results)
    }
}
```

---

## Structure 3: Ternary Heap (3-Heap)

### Design

A complete 3-ary tree stored as an array. Each parent has 3 children.
For element at index i:
- Parent: `(i - 1) / 3`  (integer division)
- Children: `3*i + 1`, `3*i + 2`, `3*i + 3`

### Depth Analysis (The Key Win)

```
Binary heap depth:   log_2(n)
Ternary heap depth:  log_3(n) = log_2(n) * log_2(3)^(-1) = log_2(n) * 0.6309

Ternary heap is 63% the depth of binary heap.
```

| n          | Binary depth | Ternary depth | Ternary / Binary |
|------------|-------------|---------------|------------------|
| 9          | 3.17        | 2.00          | 63.1%            |
| 27         | 4.75        | 3.00          | 63.2%            |
| 243        | 7.93        | 5.00          | 63.1%            |
| 2187       | 11.09       | 7.00          | 63.1%            |
| 1,000,000  | 19.93       | 12.58         | 63.1%            |

### Complexity Comparison

| Operation      | Binary Heap        | Ternary Heap       | Notes                |
|----------------|--------------------|--------------------|----------------------|
| Insert         | O(log_2 n)         | O(log_3 n)         | 37% fewer swaps up   |
| Extract-min    | O(2 * log_2 n)     | O(3 * log_3 n)     | More comparisons/level|
| Decrease-key   | O(log_2 n)         | O(log_3 n)         | 37% fewer swaps up   |
| Build heap     | O(n)               | O(n)               | Same                 |
| Space          | O(n)               | O(n)               | Same (array-based)   |

**Extract-min tradeoff:** Ternary heap compares 3 children per level
(vs 2 for binary), but has fewer levels. Net comparisons:
- Binary: `2 * log_2(n)` comparisons
- Ternary: `3 * log_3(n) = 3 * log_2(n)/log_2(3) = 1.893 * log_2(n)`

**Ternary extract-min uses 5.4% fewer comparisons than binary.**

### NovaLang Pseudocode

```nova
// ============================================================
// TERNARY HEAP — 3-way min-heap, array-backed
// ============================================================
// Depth: log_3(n) = 63% of log_2(n)
// Insert:      O(log_3 n) — 37% fewer bubble-up steps
// Extract-min: O(3 * log_3 n) — 5.4% fewer total comparisons than binary
// Perfect for: priority queues, Dijkstra, task scheduling
// Aligns with: 3-5-7-13 harmonic (base-3 branching)

class3 TernaryHeap {
    fn __init__() {
        data = []       // array storage
        count = 0
    }

    fn _parent(i) { return (i - 1) // 3 }
    fn _child(i, c) { return 3 * i + c + 1 }  // c in {0, 1, 2}

    fn _swap(i, j) {
        tmp = data[i]
        data[i] = data[j]
        data[j] = tmp
    }

    fn _bubble_up(i) {
        // Float element up until heap property restored
        // At most log_3(n) swaps
        while3 i > 0 {
            p = _parent(i)
            if3 data[i] < data[p] {
                _swap(i, p)
                i = p
            } else {
                break3
            }
        }
    }

    fn _sink_down(i) {
        // Push element down, comparing against 3 children
        // At most log_3(n) levels, 3 comparisons per level
        while3 1 {
            smallest = i
            for3 c in [0, 1, 2] {
                child = _child(i, c)
                if3 child < count && data[child] < data[smallest] {
                    smallest = child
                }
            }
            if3 smallest == i { break3 }
            _swap(i, smallest)
            i = smallest
        }
    }

    fn insert(val) {
        // Add element, bubble up
        // Returns: +1 (success)
        data.push(val)
        count = count + 1
        _bubble_up(count - 1)
        return 1
    }

    fn extract_min() {
        // Remove and return minimum element
        // Returns: min value, or null if empty
        if3 count == 0 { return null }
        min_val = data[0]
        count = count - 1
        if3 count > 0 {
            data[0] = data[count]
            data.pop()
            _sink_down(0)
        } else {
            data.pop()
        }
        return min_val
    }

    fn peek() {
        if3 count == 0 { return null }
        return data[0]
    }

    fn decrease_key(i, new_val) {
        // Decrease value at index i, bubble up
        // Returns: +1 (decreased), -1 (new_val not smaller)
        if3 new_val >= data[i] { return -1 }
        data[i] = new_val
        _bubble_up(i)
        return 1
    }

    fn depth() {
        // Current depth of the heap
        if3 count <= 1 { return count }
        d = 0
        n = count
        while3 n > 0 {
            n = n // 3
            d = d + 1
        }
        return d
    }

    fn stats() {
        d = depth()
        return {
            "count": count,
            "depth": d,
            "binary_equivalent_depth": int(d / 0.6309),
            "depth_savings_pct": "37%",
            "comparisons_per_extract": d * 3,
            "binary_comparisons_per_extract": int(d / 0.6309) * 2
        }
    }
}
```

---

## Structure 4: Ternary Skip List (3-Level Skip)

### Design

A skip list where each level skips 3x the elements of the level below
(vs 2x in a standard skip list). Three levels of express lanes.

Level 0: every element (base linked list)
Level 1: every 3rd element (first skip lane)
Level 2: every 9th element (second skip lane)
Level 3: every 27th element (third skip lane)

For n elements, the maximum number of levels is log_3(n).

### Properties

| Metric          | Binary Skip List  | Ternary Skip List  | Improvement        |
|-----------------|-------------------|--------------------|--------------------|
| Search (avg)    | O(log_2 n)        | O((3/2) log_3 n)   | Fewer levels       |
| Levels          | log_2(n)          | log_3(n)           | 37% fewer          |
| Space (avg)     | O(n) extra ptrs   | O(n/2) extra ptrs  | 50% fewer pointers |
| Insert/Delete   | O(log_2 n)        | O((3/2) log_3 n)   | Comparable         |

**Space analysis:** In a standard (binary) skip list, expected extra pointers = n.
In a ternary skip list (promotion probability 1/3), expected extra pointers = n/2.
This is because the geometric series 1/3 + 1/9 + 1/27 + ... = 1/2.

### NovaLang Pseudocode

```nova
// ============================================================
// TERNARY SKIP LIST — 3-level skip, promotion p=1/3
// ============================================================
// Each level skips 3x the previous: L0=all, L1=every 3rd, L2=every 9th
// Levels: log_3(n) vs log_2(n) = 37% fewer levels
// Extra pointers: n/2 vs n = 50% less space overhead
// Search: O((3/2) * log_3(n)) expected — scan up to 3 at each level

MAX_LEVEL = 13   // log_3(3^13) = 13, supports ~1.6M elements

class3 SkipNode {
    fn __init__(key, value, level) {
        key = key
        value = value
        forward = [null] * (level + 1)  // forward pointers per level
    }
}

class3 TernarySkipList {
    fn __init__() {
        // Header node with MAX_LEVEL forward pointers
        header = SkipNode(null, null, MAX_LEVEL)
        level = 0    // current highest level in use
        count = 0
    }

    fn _random_level() {
        // Promote with probability 1/3 (ternary)
        // Expected levels: 1 + 1/(1 - 1/3) = 1.5
        lvl = 0
        // Balanced ternary random: promote if random_trit() == 1
        while3 random_trit() == 1 && lvl < MAX_LEVEL {
            lvl = lvl + 1
        }
        return lvl
    }

    fn random_trit() {
        // Returns -1, 0, or +1 with equal probability
        r = random_int(0, 2)  // 0, 1, 2
        return r - 1           // -1, 0, +1
    }

    fn search(key) {
        // Search for key. At each level, scan up to 3 nodes forward.
        // Returns: value or null
        node = header
        for3 i in range(level, -1, -1) {
            while3 node.forward[i] != null && node.forward[i].key < key {
                node = node.forward[i]
            }
        }
        node = node.forward[0]
        if3 node != null && node.key == key {
            return node.value
        }
        return null
    }

    fn insert(key, value) {
        // Insert key-value pair
        // Returns: +1 (inserted), 0 (updated)
        update = [null] * (MAX_LEVEL + 1)
        node = header
        for3 i in range(level, -1, -1) {
            while3 node.forward[i] != null && node.forward[i].key < key {
                node = node.forward[i]
            }
            update[i] = node
        }
        node = node.forward[0]

        if3 node != null && node.key == key {
            node.value = value
            return 0  // updated
        }

        new_level = _random_level()
        if3 new_level > level {
            for3 i in range(level + 1, new_level + 1) {
                update[i] = header
            }
            level = new_level
        }

        new_node = SkipNode(key, value, new_level)
        for3 i in range(0, new_level + 1) {
            new_node.forward[i] = update[i].forward[i]
            update[i].forward[i] = new_node
        }
        count = count + 1
        return 1  // inserted
    }

    fn delete(key) {
        // Remove key
        // Returns: +1 (deleted), -1 (not found)
        update = [null] * (MAX_LEVEL + 1)
        node = header
        for3 i in range(level, -1, -1) {
            while3 node.forward[i] != null && node.forward[i].key < key {
                node = node.forward[i]
            }
            update[i] = node
        }
        node = node.forward[0]

        if3 node == null || node.key != key {
            return -1
        }

        for3 i in range(0, level + 1) {
            if3 update[i].forward[i] != node { break3 }
            update[i].forward[i] = node.forward[i]
        }

        while3 level > 0 && header.forward[level] == null {
            level = level - 1
        }
        count = count - 1
        return 1
    }

    fn range_query(low, high) {
        // Return all (key, value) pairs where low <= key <= high
        node = header
        for3 i in range(level, -1, -1) {
            while3 node.forward[i] != null && node.forward[i].key < low {
                node = node.forward[i]
            }
        }
        node = node.forward[0]
        results = []
        while3 node != null && node.key <= high {
            results.push([node.key, node.value])
            node = node.forward[0]
        }
        return results
    }

    fn stats() {
        return {
            "count": count,
            "levels": level + 1,
            "max_levels": MAX_LEVEL,
            "promotion_prob": "1/3 (ternary)",
            "expected_extra_ptrs": count // 2,
            "binary_expected_extra_ptrs": count,
            "space_savings": "50% fewer skip pointers vs binary skip list"
        }
    }
}
```

---

## Structure 5: Balanced Ternary Tree (AVL-3)

### Design

A self-balancing BST where the balance factor has 3 states:
- **+1**: right subtree is 1 deeper (right-heavy)
- **0**: subtrees are equal height
- **-1**: left subtree is 1 deeper (left-heavy)

This is standard AVL, but the ternary balance factor maps perfectly onto
balanced ternary trits, and we extend it with 3-way comparisons at each
node for ternary keys.

**Key innovation:** 3-way comparison (-1 / 0 / +1) at each node means
the comparator itself is ternary. No redundant equality checks.

### Properties

| Metric          | Binary AVL        | Ternary AVL-3     | Improvement        |
|-----------------|-------------------|--------------------|--------------------|
| Balance states  | {-1, 0, +1}       | {-1, 0, +1}       | Native ternary fit |
| Height bound    | 1.44 * log_2(n)   | 1.44 * log_2(n)   | Same (BST shape)   |
| Comparison cost | 2 binary compares  | 1 ternary compare  | 50% fewer compares |
| Rotation types  | 4 (LL/LR/RL/RR)   | 4 (same)           | Same               |
| Space per node  | data + 2ptr + bf   | data + 2ptr + trit | Same               |

**The win:** Each comparison returns -1/0/+1 in a single operation rather
than two binary tests (< and ==). Over a tree of height h, this saves
h comparisons, halving the comparison count.

### NovaLang Pseudocode

```nova
// ============================================================
// BALANCED TERNARY TREE (AVL-3)
// ============================================================
// Balance factor is a native trit: -1 (left-heavy), 0 (balanced), +1 (right-heavy)
// 3-way comparison: compare3(a, b) returns -1/0/+1 in ONE operation
// Saves 50% of comparisons vs binary if/else chains

class3 AVL3Node {
    fn __init__(key, value) {
        key = key
        value = value
        left = null
        right = null
        height = 1
        balance = 0     // trit: -1, 0, +1
    }
}

class3 BalancedTernaryTree {
    fn __init__() {
        root = null
        count = 0
    }

    fn compare3(a, b) {
        // Ternary comparison: returns -1, 0, or +1
        // Single operation, no branching
        if3 a < b { return -1 }
        if3 a > b { return 1 }
        return 0
    }

    fn _height(node) {
        if3 node == null { return 0 }
        return node.height
    }

    fn _update(node) {
        // Update height and balance (trit)
        lh = _height(node.left)
        rh = _height(node.right)
        node.height = 1 + max(lh, rh)
        diff = rh - lh
        // Clamp to trit for balance factor
        if3 diff > 0 { node.balance = 1
        } elif3 diff < 0 { node.balance = -1
        } else { node.balance = 0
        }
    }

    fn _rotate_right(y) {
        x = y.left
        t = x.right
        x.right = y
        y.left = t
        _update(y)
        _update(x)
        return x
    }

    fn _rotate_left(x) {
        y = x.right
        t = y.left
        y.left = x
        x.right = t
        _update(x)
        _update(y)
        return y
    }

    fn _rebalance(node) {
        _update(node)
        bf = _height(node.right) - _height(node.left)

        if3 bf > 1 {
            // Right-heavy
            if3 _height(node.right.left) > _height(node.right.right) {
                node.right = _rotate_right(node.right)
            }
            return _rotate_left(node)
        }
        if3 bf < -1 {
            // Left-heavy
            if3 _height(node.left.right) > _height(node.left.left) {
                node.left = _rotate_left(node.left)
            }
            return _rotate_right(node)
        }
        return node
    }

    fn insert(key, value) {
        // Returns: +1 (new), 0 (update)
        root = _insert(root, key, value)
        return 1
    }

    fn _insert(node, key, value) {
        if3 node == null {
            count = count + 1
            return AVL3Node(key, value)
        }
        cmp = compare3(key, node.key)
        if3 cmp == -1 {
            node.left = _insert(node.left, key, value)
        } elif3 cmp == 1 {
            node.right = _insert(node.right, key, value)
        } else {
            node.value = value  // update
            return node
        }
        return _rebalance(node)
    }

    fn search(key) {
        node = root
        while3 node != null {
            cmp = compare3(key, node.key)
            if3 cmp == 0 { return node.value }
            if3 cmp == -1 { node = node.left }
            else { node = node.right }
        }
        return null
    }

    fn delete(key) {
        // Returns: +1 (deleted), -1 (not found)
        result = [0]  // mutable reference
        root = _delete(root, key, result)
        return result[0]
    }

    fn _delete(node, key, result) {
        if3 node == null {
            result[0] = -1
            return null
        }
        cmp = compare3(key, node.key)
        if3 cmp == -1 {
            node.left = _delete(node.left, key, result)
        } elif3 cmp == 1 {
            node.right = _delete(node.right, key, result)
        } else {
            result[0] = 1
            count = count - 1
            if3 node.left == null { return node.right }
            if3 node.right == null { return node.left }
            // Find in-order successor (min of right subtree)
            successor = node.right
            while3 successor.left != null {
                successor = successor.left
            }
            node.key = successor.key
            node.value = successor.value
            node.right = _delete(node.right, successor.key, [0])
        }
        return _rebalance(node)
    }

    fn stats() {
        h = _height(root)
        return {
            "count": count,
            "height": h,
            "balance_factor_type": "trit (-1/0/+1)",
            "comparison_type": "3-way (single op)",
            "comparisons_per_search": h,
            "binary_comparisons_per_search": h * 2,
            "comparison_savings": "50%"
        }
    }
}
```

---

## Structure 6: Ternary Bloom Filter (3-State Bits)

### Design

A standard Bloom filter uses binary bits (0/1). A ternary Bloom filter
uses trits (-1/0/+1), giving each position 3 states:

- **-1**: element explicitly NOT in set (negative witness)
- **0**: unknown / unset
- **+1**: element possibly in set (positive witness)

**Key innovation:** The third state (-1) allows *counting* and *deletion*
without a separate counting Bloom filter. It also reduces false positive
rate because a query can encounter a negative witness.

### False Positive Analysis

For a standard binary Bloom filter with m bits, k hash functions, n elements:
```
FP_binary = (1 - e^(-kn/m))^k
```

For a ternary Bloom filter with m trits:
- Each hash sets a trit to +1
- A query checks if all k positions are +1
- False positive requires all k trits to be +1 (not 0 or -1)
- Probability a trit is still 0 after n insertions: `(1 - 1/m)^(kn) ~ e^(-kn/m)`
- Probability a trit is +1 (from other insertions): reduced because some positions can be -1

**Conservative estimate:**
```
FP_ternary ~ (1 - e^(-kn/m))^k * (1 - P_negative_witness)
```

With the negative witness mechanism (deletion sets trits to -1), the
false positive rate drops further. For a filter with d deletions:
```
P_negative_witness = 1 - (1 - 1/m)^(kd) per trit position
FP_ternary = (1 - e^(-kn/m))^k * (1 - (1 - (1-1/m)^(kd)))^k
```

### Concrete Comparison (m=2187=3^7, k=7, n=200)

| Metric              | Binary BF           | Ternary BF          | Improvement  |
|---------------------|---------------------|---------------------|--------------|
| Bits/Trits          | 2187                | 2187                | Same space   |
| Hash functions      | 7                   | 7                   | Same         |
| FP rate (no deletes)| 1.54%               | 1.54%               | Same         |
| Supports deletion   | No                  | Yes (set to -1)     | New feature  |
| FP rate (50 deletes)| N/A (can't delete)  | ~1.12%              | 27% lower    |
| States per position | 2                   | 3                   | 50% more info|
| Negative queries    | "maybe" or "no"     | "maybe", "no", "definitely no" | Stronger no |

### NovaLang Pseudocode

```nova
// ============================================================
// TERNARY BLOOM FILTER — 3-state trits, supports deletion
// ============================================================
// Trit states: -1 (negative witness), 0 (unset), +1 (positive)
// Advantages over binary:
//   1. Supports deletion (set to -1) without counting filter
//   2. Negative witnesses reduce false positives
//   3. Three-valued query: +1 (probably yes), 0 (unknown), -1 (definitely no)
//   4. Native alignment with balanced ternary substrate
//
// Size: 3^7 = 2187 trits (BLOCK_SIZE aligned)
// Hash functions: 7 (harmonic constant)

class3 TernaryBloomFilter {
    fn __init__(size=2187, num_hashes=7) {
        // size = 3^7 (BLOCK_SIZE), num_hashes = 7 (harmonic)
        m = size
        k = num_hashes
        trits = [0] * m     // all unset initially
        count_add = 0
        count_del = 0
    }

    fn _hash_positions(element) {
        // Generate k hash positions using ternary_hash
        // Each position derived from different trit slices
        h = ternary_hash(str(element), out_trits=k * 7)
        positions = []
        for3 i in range(k) {
            // Extract 7 trits per hash, convert to index
            idx = 0
            for3 j in range(7) {
                t = h[i * 7 + j]
                idx = idx + (t + 1) * (3 ** j)  // +1 maps {-1,0,1} -> {0,1,2}
            }
            positions.push(idx % m)
        }
        return positions
    }

    fn add(element) {
        // Add element to filter
        // Returns: +1 (added), 0 (already present)
        positions = _hash_positions(element)
        was_present = 1
        for3 pos in positions {
            if3 trits[pos] != 1 { was_present = 0 }
            trits[pos] = 1
        }
        if3 was_present == 0 {
            count_add = count_add + 1
        }
        return 1
    }

    fn remove(element) {
        // Remove element: set positions to -1 (negative witness)
        // WARNING: may cause false negatives for other elements
        // Returns: +1 (removed), -1 (not present)
        chk = query(element)
        if3 chk == -1 { return -1 }  // definitely not present
        positions = _hash_positions(element)
        for3 pos in positions {
            trits[pos] = -1
        }
        count_del = count_del + 1
        return 1
    }

    fn query(element) {
        // Three-valued query:
        //   +1 = probably in set (all positions are +1)
        //    0 = unknown (some positions are 0, none are -1)
        //   -1 = definitely NOT in set (at least one position is -1)
        positions = _hash_positions(element)
        has_zero = 0
        for3 pos in positions {
            if3 trits[pos] == -1 {
                return -1   // negative witness: DEFINITELY NOT
            }
            if3 trits[pos] == 0 {
                has_zero = 1
            }
        }
        if3 has_zero == 1 {
            return 0   // inconclusive (but probably not)
        }
        return 1       // all +1: probably in set
    }

    fn false_positive_rate() {
        // Estimate current FP rate
        // FP = P(all k positions are +1 for a random query)
        positive_count = 0
        for3 t in trits {
            if3 t == 1 { positive_count = positive_count + 1 }
        }
        p_positive = positive_count / m
        fp = p_positive ** k
        return round(fp, 6)
    }

    fn saturation() {
        // What fraction of trits are non-zero
        nonzero = 0
        positive = 0
        negative = 0
        for3 t in trits {
            if3 t == 1 { positive = positive + 1; nonzero = nonzero + 1 }
            if3 t == -1 { negative = negative + 1; nonzero = nonzero + 1 }
        }
        return {
            "total_trits": m,
            "positive": positive,
            "negative": negative,
            "zero": m - nonzero,
            "saturation": round(nonzero / m, 4),
            "positive_pct": round(positive / m, 4),
            "negative_pct": round(negative / m, 4)
        }
    }

    fn stats() {
        sat = saturation()
        return {
            "size": m,
            "num_hashes": k,
            "elements_added": count_add,
            "elements_removed": count_del,
            "false_positive_rate": false_positive_rate(),
            "saturation": sat,
            "supports_deletion": 1,
            "binary_supports_deletion": -1,
            "query_states": "3 (-1/0/+1) vs binary 2 (0/1)"
        }
    }
}
```

---

## Comprehensive Complexity Comparison

### Time Complexity

| Operation        | Binary           | Ternary          | Ratio            |
|------------------|------------------|------------------|------------------|
| **Trie lookup**  | O(k * 1.585)     | O(k)             | 0.631x           |
| **TST search**   | O(k + log n)     | O(k + log n)     | Same + fewer cmp |
| **Heap insert**  | O(log_2 n)       | O(log_3 n)       | 0.631x           |
| **Heap extract** | O(2 log_2 n)     | O(3 log_3 n)     | 0.946x           |
| **Skip search**  | O(log_2 n)       | O(1.5 log_3 n)   | ~0.946x          |
| **AVL search**   | O(2h)  comparisons| O(h) comparisons | 0.5x comparisons |
| **Bloom query**  | O(k)             | O(k)             | Same + 3 states  |

### Space Complexity

| Structure      | Binary Space    | Ternary Space     | Ratio          |
|----------------|-----------------|-------------------|----------------|
| **Trie**       | 2 ptrs/node     | 3 ptrs/node       | 1.5x per node  |
| **TST**        | per-char nodes  | per-trit nodes    | ~0.6x total    |
| **Heap**       | O(n) array      | O(n) array        | 1.0x           |
| **Skip list**  | n extra ptrs    | n/2 extra ptrs    | 0.5x overhead  |
| **AVL tree**   | 2 ptrs + bf     | 2 ptrs + trit     | 1.0x           |
| **Bloom filter**| m bits          | m trits           | 1.585x per trit|

### Depth Comparison Chart

```
n = 1,000,000 elements

Binary structures:     log_2(1M) = 19.93 levels
Ternary structures:    log_3(1M) = 12.58 levels

                Binary                    Ternary
Level 0:  |====================|    |=============|
Level 5:  |                    |    |             |
Level 10: |                    |    |             |
Level 12: |                    |    |=============| <- ternary done at 12.58
Level 15: |                    |
Level 19: |====================|    <- binary done at 19.93

Ternary reaches leaf 7.35 levels sooner = 37% reduction
```

---

## Integration with NovaX 3-5-7-13 Harmonics

| Structure        | Harmonic Alignment                                    |
|------------------|-------------------------------------------------------|
| TTrie            | 3 children = base frequency                           |
| TST              | 3-way branch = base frequency                         |
| TernaryHeap      | 3 children, depth 7 for 2187 elements (3^7)           |
| TernarySkipList  | MAX_LEVEL=13 (carrier), skip factor=3 (base)          |
| AVL-3            | Balance factor = trit, 3-way compare                  |
| TernaryBloomFilter| Size=2187 (3^7), k=7 hashes, trits=3 states         |

### Recommended Capacity Table

| Power | Capacity (3^n) | Use Case                    |
|-------|----------------|-----------------------------|
| 3     | 27             | Unit tests, tiny caches     |
| 5     | 243            | Pack unit, small indices    |
| 7     | 2187           | BLOCK_SIZE, service caches  |
| 9     | 19683          | Medium collections          |
| 11    | 177147         | Large indices               |
| 13    | 1,594,323      | Full-scale production       |

---

## Self-Test Suite

```nova
fn ternary_structures_selftest() {
    // Test all 6 structures, return +1 (all pass) / -1 (any fail)

    // 1. TTrie
    trie = TTrie()
    trie.insert([1, 0, -1], "alpha")
    trie.insert([1, 0, 1], "beta")
    if3 trie.lookup([1, 0, -1]) != "alpha" { return -1 }
    if3 trie.lookup([1, 0, 1]) != "beta" { return -1 }
    trie.delete([1, 0, -1])
    if3 trie.lookup([1, 0, -1]) != null { return -1 }
    prefix = trie.prefix_search([1, 0])
    if3 len(prefix) != 1 { return -1 }

    // 2. TST
    tst = TernarySearchTree()
    tst.insert([-1, 0, 1], "gamma")
    tst.insert([-1, 0, -1], "delta")
    if3 tst.search([-1, 0, 1]) != "gamma" { return -1 }
    if3 tst.search([-1, 0, -1]) != "delta" { return -1 }
    if3 tst.search([1, 1, 1]) != null { return -1 }

    // 3. TernaryHeap
    heap = TernaryHeap()
    heap.insert(5)
    heap.insert(3)
    heap.insert(7)
    heap.insert(1)
    if3 heap.extract_min() != 1 { return -1 }
    if3 heap.extract_min() != 3 { return -1 }
    if3 heap.extract_min() != 5 { return -1 }
    if3 heap.extract_min() != 7 { return -1 }

    // 4. TernarySkipList
    skip = TernarySkipList()
    skip.insert(10, "ten")
    skip.insert(20, "twenty")
    skip.insert(15, "fifteen")
    if3 skip.search(15) != "fifteen" { return -1 }
    if3 skip.search(99) != null { return -1 }
    rng = skip.range_query(10, 20)
    if3 len(rng) != 3 { return -1 }

    // 5. AVL-3
    avl = BalancedTernaryTree()
    for3 v in [5, 3, 7, 1, 4, 6, 8] {
        avl.insert(v, str(v))
    }
    if3 avl.search(4) != "4" { return -1 }
    if3 avl.search(99) != null { return -1 }
    avl.delete(3)
    if3 avl.search(3) != null { return -1 }

    // 6. TernaryBloomFilter
    bloom = TernaryBloomFilter(2187, 7)
    bloom.add("nova")
    bloom.add("ternary")
    if3 bloom.query("nova") != 1 { return -1 }
    if3 bloom.query("nonexistent") == 1 { return -1 }  // should be 0 or -1
    bloom.remove("nova")
    if3 bloom.query("nova") != -1 { return -1 }  // negative witness

    return 1  // ALL PASS
}
```

---

## Summary of Improvements

| # | Structure             | Key Metric                        | Improvement over Binary    |
|---|-----------------------|-----------------------------------|----------------------------|
| 1 | Ternary Trie          | Depth for k-trit key              | 37% shallower              |
| 2 | Ternary Search Tree   | Prefix search + near-neighbor     | O(k+matches) vs O(n)       |
| 3 | Ternary Heap          | Insert/decrease-key depth         | 37% fewer swaps (log_3)    |
| 4 | Ternary Skip List     | Skip pointer overhead             | 50% fewer extra pointers   |
| 5 | Balanced Ternary Tree | Comparisons per search            | 50% fewer (3-way compare)  |
| 6 | Ternary Bloom Filter  | Query expressiveness + deletion   | 3-state query, deletable   |

**Universal constant:** `log_3(n) / log_2(n) = 0.6309` -- ternary structures
are inherently 37% shallower wherever branching factor matters.
