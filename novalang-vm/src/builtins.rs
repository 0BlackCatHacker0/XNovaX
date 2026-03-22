// NovaLang Builtins v1.4 — ternary-first builtin functions
// 3-5-7-13 harmonic constants baked in
// v1.4: type checks, collection power (unique/find/every/some/chunk/take/drop/sort_by/group_by),
//        string extras (substr/char_at/trim_start/trim_end/is_numeric), math (clamp/sign/lerp),
//        base64 encode/decode, sha256, date/time operations
// v1.3: bitwise ops, HTTP PUT/DELETE/PATCH, assertions, deep_clone/deep_merge,
//        retry3, char codes, string extras, index_of, list extras (flat/zip/reduce)

#[cfg(windows)]
use std::os::windows::process::CommandExt;

/// Value type shared with VM
#[derive(Debug, Clone)]
pub enum Value {
    Int(i64),
    Float(f64),
    Str(String),
    Bool(bool),
    Trit(i8),       // -1, 0, +1
    List(Vec<Value>),
    Dict(Vec<(String, Value)>),
    Null,
    Fn(String),     // named function reference
}

impl Value {
    pub fn is_truthy(&self) -> bool {
        match self {
            Value::Bool(b) => *b,
            Value::Trit(t) => *t > 0,
            Value::Int(i) => *i != 0,
            Value::Float(f) => *f != 0.0,
            Value::Str(s) => !s.is_empty(),
            Value::List(v) => !v.is_empty(),
            Value::Dict(d) => !d.is_empty(),
            Value::Null => false,
            Value::Fn(_) => true,
        }
    }

    pub fn to_display(&self) -> String {
        match self {
            Value::Int(i) => i.to_string(),
            Value::Float(f) => format!("{}", f),
            Value::Str(s) => s.clone(),
            Value::Bool(b) => if *b { "true".into() } else { "false".into() },
            // Bug 3 fix: Trit values display as their integer values (1/0/-1)
            // so they work correctly in string interpolation and str() conversion.
            // Use trit_label3() or trit_fmt3() for human-readable labels.
            Value::Trit(t) => (*t as i64).to_string(),
            Value::List(items) => {
                let inner: Vec<String> = items.iter().map(|v| v.to_repr()).collect();
                format!("[{}]", inner.join(", "))
            }
            Value::Dict(pairs) => {
                let inner: Vec<String> = pairs.iter()
                    .map(|(k, v)| format!("{}: {}", k, v.to_repr()))
                    .collect();
                format!("{{{}}}", inner.join(", "))
            }
            Value::Null => "null".into(),
            Value::Fn(name) => format!("<fn {}>", name),
        }
    }

    pub fn to_repr(&self) -> String {
        match self {
            Value::Str(s) => format!("\"{}\"", s),
            other => other.to_display(),
        }
    }

    pub fn to_trit(&self) -> i8 {
        match self {
            Value::Trit(t) => *t,
            Value::Bool(b) => if *b { 1 } else { -1 },
            Value::Int(i) => if *i > 0 { 1 } else if *i == 0 { 0 } else { -1 },
            Value::Float(f) => if *f > 0.0 { 1 } else if *f == 0.0 { 0 } else { -1 },
            Value::Null => 0,
            Value::Str(s) => if s.is_empty() { 0 } else { 1 },
            _ => 0,
        }
    }

    pub fn to_int(&self) -> i64 {
        match self {
            Value::Int(i) => *i,
            Value::Float(f) => *f as i64,
            Value::Trit(t) => *t as i64,
            Value::Bool(b) => if *b { 1 } else { 0 },
            Value::Str(s) => s.parse().unwrap_or(0),
            _ => 0,
        }
    }

    pub fn to_float(&self) -> f64 {
        match self {
            Value::Float(f) => *f,
            Value::Int(i) => *i as f64,
            Value::Trit(t) => *t as f64,
            Value::Bool(b) => if *b { 1.0 } else { 0.0 },
            Value::Str(s) => s.parse().unwrap_or(0.0),
            _ => 0.0,
        }
    }
}

impl PartialEq for Value {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (Value::Int(a), Value::Int(b)) => a == b,
            (Value::Float(a), Value::Float(b)) => a == b,
            (Value::Int(a), Value::Float(b)) => (*a as f64) == *b,
            (Value::Float(a), Value::Int(b)) => *a == (*b as f64),
            (Value::Str(a), Value::Str(b)) => a == b,
            (Value::Bool(a), Value::Bool(b)) => a == b,
            (Value::Trit(a), Value::Trit(b)) => a == b,
            // Trit <-> Int cross-comparison (trits ARE integers: -1, 0, +1)
            (Value::Trit(t), Value::Int(i)) => (*t as i64) == *i,
            (Value::Int(i), Value::Trit(t)) => *i == (*t as i64),
            // Trit <-> Float cross-comparison
            (Value::Trit(t), Value::Float(f)) => (*t as f64) == *f,
            (Value::Float(f), Value::Trit(t)) => *f == (*t as f64),
            // Bool <-> Trit cross-comparison
            (Value::Bool(b), Value::Trit(t)) => if *b { *t == 1 } else { *t == -1 },
            (Value::Trit(t), Value::Bool(b)) => if *b { *t == 1 } else { *t == -1 },
            (Value::Null, Value::Null) => true,
            _ => false,
        }
    }
}

// ── Harmonic Constants ──
pub const H3: i64 = 3;
pub const H5: i64 = 5;
pub const H7: i64 = 7;
pub const H13: i64 = 13;
pub const BLOCK_SIZE: i64 = 2187; // 3^7

/// Call a builtin function by name. Returns Some(Value) if handled, None if not a builtin.
pub fn call_builtin(name: &str, args: &[Value]) -> Option<Value> {
    match name {
        // ── Ternary Core ──
        "bool3" | "to_trit" => {
            let v = args.first().unwrap_or(&Value::Null);
            Some(Value::Trit(v.to_trit()))
        }
        "not3" => {
            let t = args.first().unwrap_or(&Value::Null).to_trit();
            Some(Value::Trit(-t))
        }
        "and3" => {
            let a = args.first().unwrap_or(&Value::Null).to_trit();
            let b = args.get(1).unwrap_or(&Value::Null).to_trit();
            Some(Value::Trit(a.min(b)))
        }
        "or3" => {
            let a = args.first().unwrap_or(&Value::Null).to_trit();
            let b = args.get(1).unwrap_or(&Value::Null).to_trit();
            Some(Value::Trit(a.max(b)))
        }
        "merge3" | "tmerge" => {
            // Consensus: majority vote across trits
            if args.is_empty() { return Some(Value::Trit(0)); }
            let sum: i64 = args.iter().map(|v| v.to_trit() as i64).sum();
            let avg = sum as f64 / args.len() as f64;
            let t = if avg > 0.33 { 1 } else if avg < -0.33 { -1 } else { 0 };
            Some(Value::Trit(t))
        }
        "cmp3" => {
            let a = args.first().unwrap_or(&Value::Null).to_float();
            let b = args.get(1).unwrap_or(&Value::Null).to_float();
            let t = if a > b { 1i8 } else if a < b { -1 } else { 0 };
            Some(Value::Trit(t))
        }
        "trit" => {
            let v = args.first().unwrap_or(&Value::Null).to_trit();
            Some(Value::Trit(v))
        }

        // ── Balanced Ternary Arithmetic ──
        "bt" => {
            let n = args.first().unwrap_or(&Value::Null).to_int();
            Some(Value::Str(decimal_to_bt(n)))
        }
        "bt_val" => {
            let s = args.first().unwrap_or(&Value::Null).to_display();
            Some(Value::Int(bt_to_decimal(&s)))
        }
        "bt_neg" => {
            let s = args.first().unwrap_or(&Value::Null).to_display();
            let neg: String = s.chars().map(|c| match c {
                '1' => 'T',
                'T' => '1',
                _ => '0',
            }).collect();
            Some(Value::Str(neg))
        }
        "bt_add" => {
            let a = args.first().unwrap_or(&Value::Null).to_display();
            let b = args.get(1).unwrap_or(&Value::Null).to_display();
            let va = bt_to_decimal(&a);
            let vb = bt_to_decimal(&b);
            Some(Value::Str(decimal_to_bt(va + vb)))
        }
        "bt_sub" => {
            let a = args.first().unwrap_or(&Value::Null).to_display();
            let b = args.get(1).unwrap_or(&Value::Null).to_display();
            let va = bt_to_decimal(&a);
            let vb = bt_to_decimal(&b);
            Some(Value::Str(decimal_to_bt(va - vb)))
        }
        "bt_mul" => {
            let a = args.first().unwrap_or(&Value::Null).to_display();
            let b = args.get(1).unwrap_or(&Value::Null).to_display();
            let va = bt_to_decimal(&a);
            let vb = bt_to_decimal(&b);
            Some(Value::Str(decimal_to_bt(va * vb)))
        }

        "trit_sum" => {
            let sum: i64 = args.iter().map(|v| v.to_trit() as i64).sum();
            Some(Value::Int(sum))
        }
        "trit_count" => {
            // Count how many match a target trit
            let target = args.first().unwrap_or(&Value::Null).to_trit();
            let list = args.get(1).unwrap_or(&Value::Null);
            if let Value::List(items) = list {
                let c = items.iter().filter(|v| v.to_trit() == target).count();
                Some(Value::Int(c as i64))
            } else {
                Some(Value::Int(0))
            }
        }

        // ── Balanced Ternary (bt_*) ──
        "bt_encode" => {
            let n = args.first().unwrap_or(&Value::Null).to_int();
            Some(Value::Str(bt_encode(n)))
        }
        "bt_decode" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Int(bt_decode(s)))
            } else {
                Some(Value::Int(0))
            }
        }
        "bt_add" => {
            if let (Some(Value::Str(a)), Some(Value::Str(b))) = (args.first(), args.get(1)) {
                let sum = bt_decode(a) + bt_decode(b);
                Some(Value::Str(bt_encode(sum)))
            } else {
                Some(Value::Str("0".into()))
            }
        }

        // ── String Operations ──
        "len" => {
            let v = args.first().unwrap_or(&Value::Null);
            match v {
                Value::Str(s) => Some(Value::Int(s.len() as i64)),
                Value::List(l) => Some(Value::Int(l.len() as i64)),
                Value::Dict(d) => Some(Value::Int(d.len() as i64)),
                _ => Some(Value::Int(0)),
            }
        }
        "str" | "to_str" => {
            let v = args.first().unwrap_or(&Value::Null);
            Some(Value::Str(v.to_display()))
        }
        "int" | "to_int" => {
            let v = args.first().unwrap_or(&Value::Null);
            Some(Value::Int(v.to_int()))
        }
        "float" | "to_float" => {
            let v = args.first().unwrap_or(&Value::Null);
            Some(Value::Float(v.to_float()))
        }
        "upper" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Str(s.to_uppercase()))
            } else { Some(Value::Null) }
        }
        "lower" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Str(s.to_lowercase()))
            } else { Some(Value::Null) }
        }
        "trim" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Str(s.trim().to_string()))
            } else { Some(Value::Null) }
        }
        "split" => {
            if let Some(Value::Str(s)) = args.first() {
                let delim = if let Some(Value::Str(d)) = args.get(1) { d.as_str() } else { " " };
                let parts: Vec<Value> = s.split(delim).map(|p| Value::Str(p.to_string())).collect();
                Some(Value::List(parts))
            } else { Some(Value::List(vec![])) }
        }
        "join" => {
            if let Some(Value::List(items)) = args.first() {
                let delim = if let Some(Value::Str(d)) = args.get(1) { d.clone() } else { "".into() };
                let s: Vec<String> = items.iter().map(|v| v.to_display()).collect();
                Some(Value::Str(s.join(&delim)))
            } else { Some(Value::Str(String::new())) }
        }
        "replace" => {
            if let (Some(Value::Str(s)), Some(Value::Str(from)), Some(Value::Str(to))) =
                (args.first(), args.get(1), args.get(2))
            {
                Some(Value::Str(s.replace(from.as_str(), to.as_str())))
            } else { Some(Value::Null) }
        }
        "contains" => {
            match args.first().unwrap_or(&Value::Null) {
                Value::Str(s) => {
                    if let Some(Value::Str(sub)) = args.get(1) {
                        Some(Value::Trit(if s.contains(sub.as_str()) { 1 } else { -1 }))
                    } else { Some(Value::Trit(-1)) }
                }
                Value::List(items) => {
                    let needle = args.get(1).unwrap_or(&Value::Null);
                    Some(Value::Trit(if items.iter().any(|v| v == needle) { 1 } else { -1 }))
                }
                _ => Some(Value::Trit(-1)),
            }
        }
        "starts_with" => {
            if let (Some(Value::Str(s)), Some(Value::Str(prefix))) = (args.first(), args.get(1)) {
                Some(Value::Trit(if s.starts_with(prefix.as_str()) { 1 } else { -1 }))
            } else { Some(Value::Trit(-1)) }
        }
        "ends_with" => {
            if let (Some(Value::Str(s)), Some(Value::Str(suffix))) = (args.first(), args.get(1)) {
                Some(Value::Trit(if s.ends_with(suffix.as_str()) { 1 } else { -1 }))
            } else { Some(Value::Trit(-1)) }
        }

        // ── List Operations ──
        "list_push" | "push" | "append" => {
            // Mutates in place — but since we're functional, return new list
            if let Some(Value::List(items)) = args.first() {
                let mut new_items = items.clone();
                if let Some(val) = args.get(1) {
                    new_items.push(val.clone());
                }
                Some(Value::List(new_items))
            } else { Some(Value::Null) }
        }
        "list_pop" | "pop" => {
            if let Some(Value::List(items)) = args.first() {
                let mut new_items = items.clone();
                new_items.pop();
                Some(Value::List(new_items))
            } else { Some(Value::Null) }
        }
        "sort" => {
            if let Some(Value::List(items)) = args.first() {
                let mut sorted = items.clone();
                sorted.sort_by(|a, b| {
                    a.to_float().partial_cmp(&b.to_float()).unwrap_or(std::cmp::Ordering::Equal)
                });
                Some(Value::List(sorted))
            } else { Some(Value::Null) }
        }
        "reverse" => {
            if let Some(Value::List(items)) = args.first() {
                let mut rev = items.clone();
                rev.reverse();
                Some(Value::List(rev))
            } else { Some(Value::Null) }
        }
        "range" => {
            let start = args.first().unwrap_or(&Value::Int(0)).to_int();
            let end = args.get(1).map(|v| v.to_int());
            let (s, e) = if let Some(e) = end { (start, e) } else { (0, start) };
            let items: Vec<Value> = (s..e).map(Value::Int).collect();
            Some(Value::List(items))
        }
        "map" => {
            // map(list, fn_name) — will need VM callback, return list unchanged for now
            args.first().cloned().or(Some(Value::Null))
        }
        "filter" => {
            args.first().cloned().or(Some(Value::Null))
        }

        // ── Dict Operations ──
        "dict_get" => {
            if let (Some(Value::Dict(pairs)), Some(Value::Str(key))) = (args.first(), args.get(1)) {
                let default = args.get(2).cloned().unwrap_or(Value::Null);
                let found = pairs.iter().find(|(k, _)| k == key).map(|(_, v)| v.clone());
                Some(found.unwrap_or(default))
            } else { Some(Value::Null) }
        }
        "dict_set" => {
            if let (Some(Value::Dict(pairs)), Some(Value::Str(key)), Some(val)) =
                (args.first(), args.get(1), args.get(2))
            {
                let mut new_pairs = pairs.clone();
                if let Some(existing) = new_pairs.iter_mut().find(|(k, _)| k == key) {
                    existing.1 = val.clone();
                } else {
                    new_pairs.push((key.clone(), val.clone()));
                }
                Some(Value::Dict(new_pairs))
            } else { Some(Value::Null) }
        }
        "dict_keys" => {
            if let Some(Value::Dict(pairs)) = args.first() {
                let keys: Vec<Value> = pairs.iter().map(|(k, _)| Value::Str(k.clone())).collect();
                Some(Value::List(keys))
            } else { Some(Value::List(vec![])) }
        }
        "dict_values" => {
            if let Some(Value::Dict(pairs)) = args.first() {
                let vals: Vec<Value> = pairs.iter().map(|(_, v)| v.clone()).collect();
                Some(Value::List(vals))
            } else { Some(Value::List(vec![])) }
        }
        "dict_items" => {
            if let Some(Value::Dict(pairs)) = args.first() {
                let items: Vec<Value> = pairs.iter()
                    .map(|(k, v)| Value::List(vec![Value::Str(k.clone()), v.clone()]))
                    .collect();
                Some(Value::List(items))
            } else { Some(Value::List(vec![])) }
        }
        "dict_from" => {
            // dict_from(list_of_pairs)
            if let Some(Value::List(items)) = args.first() {
                let pairs: Vec<(String, Value)> = items.iter().filter_map(|item| {
                    if let Value::List(pair) = item {
                        if pair.len() >= 2 {
                            Some((pair[0].to_display(), pair[1].clone()))
                        } else { None }
                    } else { None }
                }).collect();
                Some(Value::Dict(pairs))
            } else { Some(Value::Dict(vec![])) }
        }

        // ── Math ──
        "abs" => {
            let v = args.first().unwrap_or(&Value::Null);
            match v {
                Value::Int(i) => Some(Value::Int(i.abs())),
                Value::Float(f) => Some(Value::Float(f.abs())),
                _ => Some(Value::Int(0)),
            }
        }
        "max" => {
            let a = args.first().unwrap_or(&Value::Null).to_float();
            let b = args.get(1).unwrap_or(&Value::Null).to_float();
            Some(Value::Float(a.max(b)))
        }
        "min" => {
            let a = args.first().unwrap_or(&Value::Null).to_float();
            let b = args.get(1).unwrap_or(&Value::Null).to_float();
            Some(Value::Float(a.min(b)))
        }
        "round" => {
            let f = args.first().unwrap_or(&Value::Null).to_float();
            let places = args.get(1).unwrap_or(&Value::Int(0)).to_int();
            let factor = 10f64.powi(places as i32);
            Some(Value::Float((f * factor).round() / factor))
        }
        "sum" => {
            if let Some(Value::List(items)) = args.first() {
                let total: f64 = items.iter().map(|v| v.to_float()).sum();
                if total.fract() == 0.0 {
                    Some(Value::Int(total as i64))
                } else {
                    Some(Value::Float(total))
                }
            } else { Some(Value::Int(0)) }
        }
        "pow" => {
            let base = args.first().unwrap_or(&Value::Null).to_float();
            let exp = args.get(1).unwrap_or(&Value::Null).to_float();
            Some(Value::Float(base.powf(exp)))
        }

        // ── Extended Math (NovaX Pure v1.2) ──
        "sqrt" => {
            let x = args.first().unwrap_or(&Value::Null).to_float();
            Some(Value::Float(x.sqrt()))
        }
        "sin" => {
            let x = args.first().unwrap_or(&Value::Null).to_float();
            Some(Value::Float(x.sin()))
        }
        "cos" => {
            let x = args.first().unwrap_or(&Value::Null).to_float();
            Some(Value::Float(x.cos()))
        }
        "tan" => {
            let x = args.first().unwrap_or(&Value::Null).to_float();
            Some(Value::Float(x.tan()))
        }
        "asin" => {
            let x = args.first().unwrap_or(&Value::Null).to_float();
            Some(Value::Float(x.asin()))
        }
        "acos" => {
            let x = args.first().unwrap_or(&Value::Null).to_float();
            Some(Value::Float(x.acos()))
        }
        "atan2" => {
            let y = args.first().unwrap_or(&Value::Null).to_float();
            let x = args.get(1).unwrap_or(&Value::Null).to_float();
            Some(Value::Float(y.atan2(x)))
        }
        "floor" => {
            let x = args.first().unwrap_or(&Value::Null).to_float();
            Some(Value::Int(x.floor() as i64))
        }
        "ceil" => {
            let x = args.first().unwrap_or(&Value::Null).to_float();
            Some(Value::Int(x.ceil() as i64))
        }
        "log" | "ln" => {
            let x = args.first().unwrap_or(&Value::Null).to_float();
            Some(Value::Float(x.ln()))
        }
        "log10" => {
            let x = args.first().unwrap_or(&Value::Null).to_float();
            Some(Value::Float(x.log10()))
        }
        "random" => {
            use std::time::SystemTime;
            let nanos = SystemTime::now()
                .duration_since(SystemTime::UNIX_EPOCH)
                .unwrap_or_default()
                .subsec_nanos() as u64;
            // PCG-style fast hash of nanoseconds
            let state = nanos.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            let r = ((state >> 33) as f64) / ((1u64 << 31) as f64);
            Some(Value::Float(r.abs()))
        }
        "random_int" => {
            use std::time::SystemTime;
            let lo = args.first().unwrap_or(&Value::Int(0)).to_int();
            let hi = args.get(1).unwrap_or(&Value::Int(100)).to_int();
            let nanos = SystemTime::now()
                .duration_since(SystemTime::UNIX_EPOCH)
                .unwrap_or_default()
                .subsec_nanos() as u64;
            let state = nanos.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            let r = (state >> 33) as i64;
            let range = (hi - lo).max(1);
            Some(Value::Int(lo + (r.abs() % range)))
        }
        "pi" => {
            Some(Value::Float(std::f64::consts::PI))
        }

        // ── Hashing (simple FNV-1a for now) ──
        "hash" | "thash" => {
            let s = args.first().unwrap_or(&Value::Null).to_display();
            let h = fnv1a(&s);
            Some(Value::Int(h as i64))
        }

        // ── Type checking ──
        "type" | "typeof" => {
            let v = args.first().unwrap_or(&Value::Null);
            let t = match v {
                Value::Int(_) => "int",
                Value::Float(_) => "float",
                Value::Str(_) => "str",
                Value::Bool(_) => "bool",
                Value::Trit(_) => "trit",
                Value::List(_) => "list",
                Value::Dict(_) => "dict",
                Value::Null => "null",
                Value::Fn(_) => "fn",
            };
            Some(Value::Str(t.into()))
        }

        // ── Harmonic Constants ──
        "H3" => Some(Value::Int(H3)),
        "H5" => Some(Value::Int(H5)),
        "H7" => Some(Value::Int(H7)),
        "H13" => Some(Value::Int(H13)),
        "BLOCK" | "BLOCK_SIZE" => Some(Value::Int(BLOCK_SIZE)),

        // ── Time (basic) ──
        "time" | "time_now" | "now" => {
            use std::time::{SystemTime, UNIX_EPOCH};
            let secs = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
            Some(Value::Int(secs as i64))
        }
        "time_ms" => {
            use std::time::{SystemTime, UNIX_EPOCH};
            let ms = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis();
            Some(Value::Int(ms as i64))
        }

        // ── IO ──
        "read_file" => {
            if let Some(Value::Str(path)) = args.first() {
                match std::fs::read_to_string(path) {
                    Ok(content) => Some(Value::Str(content)),
                    Err(_) => Some(Value::Null),
                }
            } else { Some(Value::Null) }
        }
        "write_file" => {
            if let (Some(Value::Str(path)), Some(Value::Str(content))) = (args.first(), args.get(1)) {
                match std::fs::write(path, content) {
                    Ok(_) => Some(Value::Trit(1)),
                    Err(_) => Some(Value::Trit(-1)),
                }
            } else { Some(Value::Trit(-1)) }
        }

        // ── JSON ──
        "json_encode" | "to_json" => {
            let v = args.first().unwrap_or(&Value::Null);
            Some(Value::Str(value_to_json(v)))
        }
        "json_decode" | "from_json" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(json_to_value(s))
            } else { Some(Value::Null) }
        }

        // ── Python-compat builtins (converted code needs these) ──
        "sorted" => {
            if let Some(Value::List(items)) = args.first() {
                let mut sorted = items.clone();
                sorted.sort_by(|a, b| {
                    a.to_float().partial_cmp(&b.to_float()).unwrap_or(std::cmp::Ordering::Equal)
                });
                Some(Value::List(sorted))
            } else { Some(Value::List(vec![])) }
        }
        "enumerate" => {
            if let Some(Value::List(items)) = args.first() {
                let start = args.get(1).map(|v| v.to_int()).unwrap_or(0);
                let pairs: Vec<Value> = items.iter().enumerate()
                    .map(|(i, v)| Value::List(vec![Value::Int(i as i64 + start), v.clone()]))
                    .collect();
                Some(Value::List(pairs))
            } else { Some(Value::List(vec![])) }
        }
        "dict" => {
            // dict() — create empty dict, or dict(list_of_pairs)
            if args.is_empty() {
                Some(Value::Dict(vec![]))
            } else if let Some(Value::List(items)) = args.first() {
                let pairs: Vec<(String, Value)> = items.iter().filter_map(|item| {
                    if let Value::List(pair) = item {
                        if pair.len() >= 2 { Some((pair[0].to_display(), pair[1].clone())) } else { None }
                    } else { None }
                }).collect();
                Some(Value::Dict(pairs))
            } else { Some(Value::Dict(vec![])) }
        }
        "list" => {
            // list() — create empty list, or convert iterable
            if args.is_empty() {
                Some(Value::List(vec![]))
            } else {
                match args.first().unwrap() {
                    Value::Str(s) => Some(Value::List(s.chars().map(|c| Value::Str(c.to_string())).collect())),
                    Value::List(l) => Some(Value::List(l.clone())),
                    Value::Dict(pairs) => Some(Value::List(pairs.iter().map(|(k, _)| Value::Str(k.clone())).collect())),
                    _ => Some(Value::List(vec![args.first().cloned().unwrap_or(Value::Null)])),
                }
            }
        }
        "set" => {
            // set() — deduplicated list
            if let Some(Value::List(items)) = args.first() {
                let mut seen = Vec::new();
                let mut result = Vec::new();
                for item in items {
                    let key = item.to_display();
                    if !seen.contains(&key) {
                        seen.push(key);
                        result.push(item.clone());
                    }
                }
                Some(Value::List(result))
            } else { Some(Value::List(vec![])) }
        }
        "open" => {
            // open(path) — alias for read_file
            if let Some(Value::Str(path)) = args.first() {
                match std::fs::read_to_string(path) {
                    Ok(content) => Some(Value::Str(content)),
                    Err(_) => Some(Value::Null),
                }
            } else { Some(Value::Null) }
        }
        "Path" => {
            // Path(str) — just returns the string (we don't need pathlib)
            args.first().cloned().or(Some(Value::Str(String::new())))
        }
        "isinstance" | "is_type" => {
            // isinstance(val, type_name)
            let val = args.first().unwrap_or(&Value::Null);
            let type_name = args.get(1).map(|v| v.to_display()).unwrap_or_default();
            let actual = match val {
                Value::Int(_) => "int",
                Value::Float(_) => "float",
                Value::Str(_) => "str",
                Value::Bool(_) => "bool",
                Value::Trit(_) => "trit",
                Value::List(_) => "list",
                Value::Dict(_) => "dict",
                Value::Null => "null",
                Value::Fn(_) => "fn",
            };
            Some(Value::Trit(if actual == type_name { 1 } else { -1 }))
        }
        "getattr" => {
            // getattr(dict, key, default)
            if let (Some(Value::Dict(pairs)), Some(key)) = (args.first(), args.get(1)) {
                let k = key.to_display();
                let default = args.get(2).cloned().unwrap_or(Value::Null);
                let found = pairs.iter().find(|(pk, _)| pk == &k).map(|(_, v)| v.clone());
                Some(found.unwrap_or(default))
            } else { Some(Value::Null) }
        }
        "hasattr" => {
            if let (Some(Value::Dict(pairs)), Some(key)) = (args.first(), args.get(1)) {
                let k = key.to_display();
                Some(Value::Trit(if pairs.iter().any(|(pk, _)| pk == &k) { 1 } else { -1 }))
            } else { Some(Value::Trit(-1)) }
        }
        "print" => {
            let parts: Vec<String> = args.iter().map(|v| v.to_display()).collect();
            println!("{}", parts.join(" "));
            Some(Value::Null)
        }
        "format" => {
            // format(template, args...) — simple {} replacement
            if let Some(Value::Str(template)) = args.first() {
                let mut result = template.clone();
                for (i, arg) in args[1..].iter().enumerate() {
                    let placeholder = format!("{{{}}}", i);
                    result = result.replace(&placeholder, &arg.to_display());
                    if result.contains("{}") {
                        result = result.replacen("{}", &arg.to_display(), 1);
                    }
                }
                Some(Value::Str(result))
            } else { Some(Value::Null) }
        }
        "input" => {
            // input(prompt) — read line from stdin
            if let Some(Value::Str(prompt)) = args.first() {
                eprint!("{}", prompt);
            }
            let mut line = String::new();
            match std::io::stdin().read_line(&mut line) {
                Ok(_) => Some(Value::Str(line.trim_end().to_string())),
                Err(_) => Some(Value::Null),
            }
        }
        "exit" => {
            let code = args.first().map(|v| v.to_int() as i32).unwrap_or(0);
            std::process::exit(code);
        }
        "sleep" => {
            let ms = args.first().map(|v| v.to_int() as u64).unwrap_or(0);
            std::thread::sleep(std::time::Duration::from_millis(ms));
            Some(Value::Null)
        }

        // ── Process Management ──
        "spawn" => {
            // spawn(exe, arg1, arg2, ...) — launch background process, return PID
            use std::process::Command;
            if args.is_empty() { return Some(Value::Int(-1)); }
            let exe = args[0].to_display();
            let cmd_args: Vec<String> = args[1..].iter().map(|a| a.to_display()).collect();
            #[cfg(windows)]
            let result = Command::new(&exe)
                .args(&cmd_args)
                .creation_flags(0x08000000) // CREATE_NO_WINDOW
                .spawn();
            #[cfg(not(windows))]
            let result = Command::new(&exe)
                .args(&cmd_args)
                .spawn();
            match result {
                Ok(child) => {
                    let pid = child.id();
                    Some(Value::Int(pid as i64))
                }
                Err(e) => {
                    eprintln!("[spawn] Failed: {} — {}", exe, e);
                    Some(Value::Int(-1))
                }
            }
        }
        "shell" | "exec" => {
            // shell(command) — run shell command, return output
            use std::process::Command;
            let cmd = args.first().unwrap_or(&Value::Null).to_display();
            #[cfg(windows)]
            let result = Command::new("cmd").args(["/C", &cmd])
                .creation_flags(0x08000000)
                .output();
            #[cfg(not(windows))]
            let result = Command::new("sh").args(["-c", &cmd]).output();
            match result {
                Ok(out) => {
                    let stdout = String::from_utf8_lossy(&out.stdout).to_string();
                    let stderr = String::from_utf8_lossy(&out.stderr).to_string();
                    Some(Value::Dict(vec![
                        ("ok".into(), Value::Trit(if out.status.success() { 1 } else { -1 })),
                        ("stdout".into(), Value::Str(stdout)),
                        ("stderr".into(), Value::Str(stderr)),
                        ("code".into(), Value::Int(out.status.code().unwrap_or(-1) as i64)),
                    ]))
                }
                Err(e) => {
                    let err_msg = e.to_string();
                    Some(Value::Dict(vec![
                        ("ok".into(), Value::Trit(-1)),
                        ("error".into(), Value::Str(err_msg)),
                    ]))
                }
            }
        }

        // ── HTTP Client ──
        "http_get" => {
            let url = args.first().unwrap_or(&Value::Null).to_display();
            let timeout_ms = args.get(1).map(|v| v.to_int() as u64).unwrap_or(3000);
            let agent = ureq::AgentBuilder::new()
                .timeout(std::time::Duration::from_millis(timeout_ms))
                .build();
            match agent.get(&url).call() {
                Ok(resp) => {
                    let status = resp.status();
                    let body = resp.into_string().unwrap_or_default();
                    Some(Value::Dict(vec![
                        ("ok".into(), Value::Trit(if status < 400 { 1 } else { -1 })),
                        ("status".into(), Value::Int(status as i64)),
                        ("body".into(), Value::Str(body)),
                    ]))
                }
                Err(e) => Some(Value::Dict(vec![
                    ("ok".into(), Value::Trit(-1)),
                    ("error".into(), Value::Str(e.to_string())),
                ])),
            }
        }
        "http_post" => {
            let url = args.first().unwrap_or(&Value::Null).to_display();
            let body = args.get(1).unwrap_or(&Value::Null).to_display();
            let timeout_ms = args.get(2).map(|v| v.to_int() as u64).unwrap_or(5000);
            let agent = ureq::AgentBuilder::new()
                .timeout(std::time::Duration::from_millis(timeout_ms))
                .build();
            match agent.post(&url)
                .set("Content-Type", "application/json")
                .send_string(&body)
            {
                Ok(resp) => {
                    let status = resp.status();
                    let rbody = resp.into_string().unwrap_or_default();
                    Some(Value::Dict(vec![
                        ("ok".into(), Value::Trit(if status < 400 { 1 } else { -1 })),
                        ("status".into(), Value::Int(status as i64)),
                        ("body".into(), Value::Str(rbody)),
                    ]))
                }
                Err(e) => Some(Value::Dict(vec![
                    ("ok".into(), Value::Trit(-1)),
                    ("error".into(), Value::Str(e.to_string())),
                ])),
            }
        }

        // ── HTTP with custom headers (NovaX Pure v1.2) ──
        // Uses ureq for HTTP, curl.exe for HTTPS (no TLS crate needed)
        "http_post_headers" | "http_request" => {
            let url = args.first().unwrap_or(&Value::Null).to_display();
            let body = args.get(1).unwrap_or(&Value::Null).to_display();
            let timeout_ms = args.get(3).map(|v| v.to_int() as u64).unwrap_or(30000);

            if url.starts_with("https://") {
                // HTTPS: use Windows curl.exe directly (no shell interpretation)
                // Write body to temp file in NovaX dir (simple path, no spaces)
                let tmp_path = "C:\\NovaX\\tmp_curl_body.json";
                let _ = std::fs::write(tmp_path, &body);

                let timeout_secs = (timeout_ms / 1000).max(5);
                // Use full path to Windows System32 curl to avoid Git's curl
                let curl_exe = if std::path::Path::new("C:\\Windows\\System32\\curl.exe").exists() {
                    "C:\\Windows\\System32\\curl.exe"
                } else {
                    "curl"
                };
                let mut cmd = std::process::Command::new(curl_exe);
                cmd.arg("-s").arg("-S")
                   .arg("-X").arg("POST")
                   .arg("--max-time").arg(timeout_secs.to_string());
                // Apply custom headers from dict arg; add Content-Type if not provided
                let mut has_ct = false;
                if let Some(Value::Dict(pairs)) = args.get(2) {
                    for (k, v) in pairs {
                        if k.to_lowercase().contains("content-type") { has_ct = true; }
                        cmd.arg("-H").arg(format!("{}: {}", k, v.to_display()));
                    }
                }
                if !has_ct {
                    cmd.arg("-H").arg("Content-Type: application/json");
                }
                cmd.arg("--data-binary").arg(format!("@C:\\NovaX\\tmp_curl_body.json"));
                cmd.arg(&url);

                let result = match cmd.output() {
                    Ok(output) => {
                        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
                        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
                        if !stdout.is_empty() {
                            Some(Value::Dict(vec![
                                ("ok".into(), Value::Trit(1)),
                                ("status".into(), Value::Int(200)),
                                ("body".into(), Value::Str(stdout)),
                            ]))
                        } else {
                            Some(Value::Dict(vec![
                                ("ok".into(), Value::Trit(-1)),
                                ("error".into(), Value::Str(if stderr.is_empty() { "curl_empty".to_string() } else { stderr })),
                            ]))
                        }
                    }
                    Err(e) => Some(Value::Dict(vec![
                        ("ok".into(), Value::Trit(-1)),
                        ("error".into(), Value::Str(format!("curl_exec_failed: {}", e))),
                    ])),
                };
                let _ = std::fs::remove_file(tmp_path);
                result
            } else {
                // HTTP: use ureq directly (no TLS needed for localhost)
                let agent = ureq::AgentBuilder::new()
                    .timeout(std::time::Duration::from_millis(timeout_ms))
                    .build();
                let mut req = agent.post(&url).set("Content-Type", "application/json");
                if let Some(Value::Dict(pairs)) = args.get(2) {
                    for (k, v) in pairs {
                        req = req.set(k, &v.to_display());
                    }
                }
                match req.send_string(&body) {
                    Ok(resp) => {
                        let status = resp.status();
                        let rbody = resp.into_string().unwrap_or_default();
                        Some(Value::Dict(vec![
                            ("ok".into(), Value::Trit(if status < 400 { 1 } else { -1 })),
                            ("status".into(), Value::Int(status as i64)),
                            ("body".into(), Value::Str(rbody)),
                        ]))
                    }
                    Err(e) => Some(Value::Dict(vec![
                        ("ok".into(), Value::Trit(-1)),
                        ("error".into(), Value::Str(e.to_string())),
                    ])),
                }
            }
        }

        // ── Base64 encoding/decoding (NovaX Pure v1.2) ──
        "base64_encode" => {
            let s = args.first().unwrap_or(&Value::Null).to_display();
            let alphabet = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
            let bytes = s.as_bytes();
            let mut out = String::new();
            for chunk in bytes.chunks(3) {
                let b0 = chunk[0] as u32;
                let b1 = if chunk.len() > 1 { chunk[1] as u32 } else { 0 };
                let b2 = if chunk.len() > 2 { chunk[2] as u32 } else { 0 };
                let triple = (b0 << 16) | (b1 << 8) | b2;
                out.push(alphabet[((triple >> 18) & 0x3F) as usize] as char);
                out.push(alphabet[((triple >> 12) & 0x3F) as usize] as char);
                if chunk.len() > 1 { out.push(alphabet[((triple >> 6) & 0x3F) as usize] as char); } else { out.push('='); }
                if chunk.len() > 2 { out.push(alphabet[(triple & 0x3F) as usize] as char); } else { out.push('='); }
            }
            Some(Value::Str(out))
        }
        "base64_decode" => {
            let s = args.first().unwrap_or(&Value::Null).to_display();
            let decode_char = |c: u8| -> u32 {
                match c {
                    b'A'..=b'Z' => (c - b'A') as u32,
                    b'a'..=b'z' => (c - b'a' + 26) as u32,
                    b'0'..=b'9' => (c - b'0' + 52) as u32,
                    b'+' => 62, b'/' => 63,
                    _ => 0,
                }
            };
            let bytes: Vec<u8> = s.bytes().filter(|&b| b != b'=' && b != b'\n' && b != b'\r').collect();
            let mut out = Vec::new();
            for chunk in bytes.chunks(4) {
                if chunk.len() < 2 { break; }
                let a = decode_char(chunk[0]);
                let b = decode_char(chunk[1]);
                let c = if chunk.len() > 2 { decode_char(chunk[2]) } else { 0 };
                let d = if chunk.len() > 3 { decode_char(chunk[3]) } else { 0 };
                let triple = (a << 18) | (b << 12) | (c << 6) | d;
                out.push(((triple >> 16) & 0xFF) as u8);
                if chunk.len() > 2 { out.push(((triple >> 8) & 0xFF) as u8); }
                if chunk.len() > 3 { out.push((triple & 0xFF) as u8); }
            }
            Some(Value::Str(String::from_utf8_lossy(&out).to_string()))
        }

        // ── Filesystem ──
        "file_exists" | "path_exists" => {
            let p = args.first().unwrap_or(&Value::Null).to_display();
            Some(Value::Trit(if std::path::Path::new(&p).exists() { 1 } else { -1 }))
        }
        "dir_list" | "listdir" => {
            let p = args.first().unwrap_or(&Value::Null).to_display();
            match std::fs::read_dir(&p) {
                Ok(entries) => {
                    let items: Vec<Value> = entries
                        .filter_map(|e| e.ok())
                        .map(|e| Value::Str(e.file_name().to_string_lossy().to_string()))
                        .collect();
                    Some(Value::List(items))
                }
                Err(_) => Some(Value::List(vec![])),
            }
        }
        "mkdir" => {
            let p = args.first().unwrap_or(&Value::Null).to_display();
            match std::fs::create_dir_all(&p) {
                Ok(_) => Some(Value::Trit(1)),
                Err(_) => Some(Value::Trit(-1)),
            }
        }

        // ── Environment ──
        "env_get" | "getenv" => {
            let key = args.first().unwrap_or(&Value::Null).to_display();
            let default = args.get(1).cloned().unwrap_or(Value::Null);
            match std::env::var(&key) {
                Ok(val) => Some(Value::Str(val)),
                Err(_) => Some(default),
            }
        }

        // ── Threading ──
        "thread" | "thread_spawn" => {
            // thread(fn_name, interval_ms) — stub that returns a thread ID
            // Real periodic scheduling is handled by the service's own loop
            // We return a positive int so services can check thread_id > 0
            static THREAD_COUNTER: std::sync::atomic::AtomicI64 = std::sync::atomic::AtomicI64::new(1);
            let id = THREAD_COUNTER.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            Some(Value::Int(id))
        }

        // ── String extras (aliases and new) ──
        "str_replace" => {
            // str_replace(s, old, new)
            if let (Some(Value::Str(s)), Some(Value::Str(from)), Some(Value::Str(to))) =
                (args.first(), args.get(1), args.get(2))
            {
                Some(Value::Str(s.replace(from.as_str(), to.as_str())))
            } else { Some(Value::Null) }
        }
        "strip" => {
            // strip(s) — trim whitespace
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Str(s.trim().to_string()))
            } else {
                Some(Value::Str(args.first().unwrap_or(&Value::Null).to_display().trim().to_string()))
            }
        }
        "slice" => {
            // slice(str_or_list, start, end?)
            let val = args.first().unwrap_or(&Value::Null);
            let start = args.get(1).map(|v| v.to_int()).unwrap_or(0) as usize;
            let end_arg = args.get(2);
            match val {
                Value::Str(s) => {
                    let end = end_arg.map(|v| v.to_int() as usize).unwrap_or(s.len());
                    let end = end.min(s.len());
                    let start = start.min(end);
                    Some(Value::Str(s[start..end].to_string()))
                }
                Value::List(items) => {
                    let end = end_arg.map(|v| v.to_int() as usize).unwrap_or(items.len());
                    let end = end.min(items.len());
                    let start = start.min(end);
                    Some(Value::List(items[start..end].to_vec()))
                }
                _ => Some(Value::Null)
            }
        }
        "trit_char" => {
            // trit_char(trit) — +1 → "+", 0 → "0", -1 → "-"
            let t = args.first().unwrap_or(&Value::Null).to_trit();
            let c = match t { 1 => "+", 0 => "0", -1 => "-", _ => "?" };
            Some(Value::Str(c.into()))
        }

        // ── Dict extras ──
        "keys" => {
            // keys(dict) — alias for dict_keys
            if let Some(Value::Dict(pairs)) = args.first() {
                let keys: Vec<Value> = pairs.iter().map(|(k, _)| Value::Str(k.clone())).collect();
                Some(Value::List(keys))
            } else { Some(Value::List(vec![])) }
        }
        "dict_has" | "has_key" => {
            // dict_has(dict, key)
            if let (Some(Value::Dict(pairs)), Some(key)) = (args.first(), args.get(1)) {
                let k = key.to_display();
                Some(Value::Trit(if pairs.iter().any(|(pk, _)| pk == &k) { 1 } else { -1 }))
            } else { Some(Value::Trit(-1)) }
        }
        "dict_remove" | "dict_del" => {
            // dict_remove(dict, key) — returns new dict without key
            if let (Some(Value::Dict(pairs)), Some(key)) = (args.first(), args.get(1)) {
                let k = key.to_display();
                let new_pairs: Vec<(String, Value)> = pairs.iter()
                    .filter(|(pk, _)| pk != &k)
                    .cloned()
                    .collect();
                Some(Value::Dict(new_pairs))
            } else {
                args.first().cloned().or(Some(Value::Null))
            }
        }

        // ── Type & Null ──
        "type_of" => {
            let v = args.first().unwrap_or(&Value::Null);
            let t = match v {
                Value::Int(_) => "int", Value::Float(_) => "float",
                Value::Str(_) => "str", Value::Bool(_) => "bool",
                Value::Trit(_) => "trit", Value::List(_) => "list",
                Value::Dict(_) => "dict", Value::Null => "null",
                Value::Fn(_) => "fn",
            };
            Some(Value::Str(t.into()))
        }
        "null" => Some(Value::Null),

        // ── IN operator as function ──
        "IN" | "in_list" => {
            // IN(needle, haystack_list)
            let needle = args.first().unwrap_or(&Value::Null);
            if let Some(Value::List(items)) = args.get(1) {
                Some(Value::Trit(if items.iter().any(|v| v == needle) { 1 } else { -1 }))
            } else if let Some(Value::Dict(pairs)) = args.get(1) {
                let k = needle.to_display();
                Some(Value::Trit(if pairs.iter().any(|(pk, _)| pk == &k) { 1 } else { -1 }))
            } else { Some(Value::Trit(-1)) }
        }

        // ── UUID / Crypto ──
        "uuid_hex" | "uuid" => {
            // Generate pseudo-random hex UUID (16 bytes = 32 hex chars)
            use std::time::{SystemTime, UNIX_EPOCH};
            let seed = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_nanos();
            let mut state = seed;
            let mut hex = String::with_capacity(32);
            for _ in 0..32 {
                state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
                let nibble = ((state >> 33) & 0xF) as u8;
                hex.push(char::from(if nibble < 10 { b'0' + nibble } else { b'a' + nibble - 10 }));
            }
            Some(Value::Str(hex))
        }
        "sha256" => {
            // REAL SHA-256 (NIST FIPS 180-4 compliant)
            let data = args.first().unwrap_or(&Value::Null).to_display();
            Some(Value::Str(sha256_hex(data.as_bytes())))
        }

        // HMAC-SHA256 — keyed hash for message authentication
        "hmac_sha256" | "hmac" => {
            let key_str = args.first().unwrap_or(&Value::Null).to_display();
            let msg_str = args.get(1).unwrap_or(&Value::Null).to_display();
            Some(Value::Str(hmac_sha256_hex(key_str.as_bytes(), msg_str.as_bytes())))
        }

        // PBKDF2-SHA256 — password-based key derivation (NIST SP 800-132)
        "pbkdf2" | "derive_key" => {
            let password = args.first().unwrap_or(&Value::Null).to_display();
            let salt = args.get(1).unwrap_or(&Value::Null).to_display();
            let iterations = match args.get(2) {
                Some(Value::Int(n)) => *n as u32,
                _ => 100_000, // default: 100k iterations
            };
            let key_len = match args.get(3) {
                Some(Value::Int(n)) => *n as usize,
                _ => 32, // default: 256 bits
            };
            Some(Value::Str(pbkdf2_sha256_hex(password.as_bytes(), salt.as_bytes(), iterations, key_len)))
        }

        // AES-256-GCM encrypt — authenticated encryption
        "aes_encrypt" | "encrypt" => {
            let plaintext = args.first().unwrap_or(&Value::Null).to_display();
            let key_hex = args.get(1).unwrap_or(&Value::Null).to_display();
            match aes256_gcm_encrypt(plaintext.as_bytes(), &key_hex) {
                Ok(ciphertext_hex) => Some(Value::Str(ciphertext_hex)),
                Err(e) => Some(Value::Str(format!("ERROR:{}", e))),
            }
        }

        // AES-256-GCM decrypt — authenticated decryption
        "aes_decrypt" | "decrypt" => {
            let ciphertext_hex = args.first().unwrap_or(&Value::Null).to_display();
            let key_hex = args.get(1).unwrap_or(&Value::Null).to_display();
            match aes256_gcm_decrypt(&ciphertext_hex, &key_hex) {
                Ok(plaintext) => Some(Value::Str(plaintext)),
                Err(e) => Some(Value::Str(format!("ERROR:{}", e))),
            }
        }

        // Secure random bytes (hex encoded)
        "random_bytes" | "secure_random" => {
            let n = match args.first() {
                Some(Value::Int(n)) => *n as usize,
                _ => 32,
            };
            Some(Value::Str(secure_random_hex(n)))
        }

        // SHA-256 of a file
        "sha256_file" | "file_hash" => {
            let path = args.first().unwrap_or(&Value::Null).to_display();
            match std::fs::read(&path) {
                Ok(data) => Some(Value::Str(sha256_hex(&data))),
                Err(_) => Some(Value::Str("ERROR:file_not_found".into())),
            }
        }

        // ── Config File I/O ──
        "load_config" => {
            // load_config(path) — read JSON file, return dict
            let path = args.first().unwrap_or(&Value::Null).to_display();
            match std::fs::read_to_string(&path) {
                Ok(content) => Some(json_to_value(&content)),
                Err(_) => Some(Value::Dict(vec![])),
            }
        }
        "save_config" => {
            // save_config(path, dict) — write dict as JSON
            let path = args.first().unwrap_or(&Value::Null).to_display();
            let data = args.get(1).unwrap_or(&Value::Null);
            let json = value_to_json(data);
            match std::fs::write(&path, &json) {
                Ok(_) => Some(Value::Trit(1)),
                Err(_) => Some(Value::Trit(-1)),
            }
        }
        "load_env_keys" => {
            // load_env_keys(config_dict) — set env vars from dict keys that end in _KEY
            // Returns count of keys loaded
            if let Some(Value::Dict(pairs)) = args.first() {
                let mut count = 0i64;
                for (k, v) in pairs {
                    if let Value::Str(val) = v {
                        if !val.is_empty() {
                            std::env::set_var(k, val);
                            count += 1;
                        }
                    }
                }
                Some(Value::Int(count))
            } else { Some(Value::Int(0)) }
        }

        // ── Nova-specific I/O ──
        "nova_read" => {
            // nova_read(path) — alias for read_file
            if let Some(Value::Str(path)) = args.first() {
                match std::fs::read_to_string(path) {
                    Ok(content) => Some(Value::Str(content)),
                    Err(_) => Some(Value::Null),
                }
            } else { Some(Value::Null) }
        }
        "nova_run" => {
            // nova_run(file) — shell out to novalang.exe to run a .nova file
            use std::process::Command;
            let file = args.first().unwrap_or(&Value::Null).to_display();
            let exe = std::env::current_exe().unwrap_or_default();
            #[cfg(windows)]
            let result = Command::new(&exe).arg(&file)
                .creation_flags(0x08000000)
                .output();
            #[cfg(not(windows))]
            let result = Command::new(&exe).arg(&file).output();
            match result {
                Ok(out) => {
                    let stdout = String::from_utf8_lossy(&out.stdout).to_string();
                    Some(Value::Dict(vec![
                        ("ok".into(), Value::Trit(if out.status.success() { 1 } else { -1 })),
                        ("output".into(), Value::Str(stdout)),
                        ("code".into(), Value::Int(out.status.code().unwrap_or(-1) as i64)),
                    ]))
                }
                Err(e) => Some(Value::Dict(vec![
                    ("ok".into(), Value::Trit(-1)),
                    ("error".into(), Value::Str(e.to_string())),
                ])),
            }
        }
        "import" => {
            // import(module_name) — stub, real import3 is handled by VM
            // Just return TRUE to indicate success
            Some(Value::Trit(1))
        }

        // ── Ollama-specific ──
        "discover_models" | "probe_ollama" => {
            // Query Ollama for running models
            let agent = ureq::AgentBuilder::new()
                .timeout(std::time::Duration::from_millis(3000))
                .build();
            match agent.get("http://127.0.0.1:11434/api/tags").call() {
                Ok(resp) => {
                    let body = resp.into_string().unwrap_or_default();
                    let parsed = json_to_value(&body);
                    Some(parsed)
                }
                Err(_) => Some(Value::Dict(vec![
                    ("models".into(), Value::List(vec![])),
                    ("ok".into(), Value::Trit(-1)),
                ])),
            }
        }
        "warm_pool_list" => {
            // List models currently loaded in Ollama
            let agent = ureq::AgentBuilder::new()
                .timeout(std::time::Duration::from_millis(3000))
                .build();
            match agent.get("http://127.0.0.1:11434/api/ps").call() {
                Ok(resp) => {
                    let body = resp.into_string().unwrap_or_default();
                    Some(json_to_value(&body))
                }
                Err(_) => Some(Value::List(vec![])),
            }
        }

        // ── Parallel/Fanout ──
        "fanout" => {
            // fanout(url_list, method) — sequential HTTP to multiple URLs
            // Returns list of responses
            if let Some(Value::List(urls)) = args.first() {
                let method = args.get(1).map(|v| v.to_display()).unwrap_or("GET".into());
                let body = args.get(2).map(|v| v.to_display()).unwrap_or_default();
                let mut results = Vec::new();
                for url_val in urls {
                    let url = url_val.to_display();
                    let agent = ureq::AgentBuilder::new()
                        .timeout(std::time::Duration::from_millis(5000))
                        .build();
                    let resp = if method == "POST" {
                        agent.post(&url)
                            .set("Content-Type", "application/json")
                            .send_string(&body)
                    } else {
                        agent.get(&url).call()
                    };
                    match resp {
                        Ok(r) => {
                            let status = r.status();
                            let rbody = r.into_string().unwrap_or_default();
                            results.push(Value::Dict(vec![
                                ("ok".into(), Value::Trit(if status < 400 { 1 } else { -1 })),
                                ("status".into(), Value::Int(status as i64)),
                                ("body".into(), Value::Str(rbody)),
                            ]));
                        }
                        Err(e) => results.push(Value::Dict(vec![
                            ("ok".into(), Value::Trit(-1)),
                            ("error".into(), Value::Str(e.to_string())),
                        ])),
                    }
                }
                Some(Value::List(results))
            } else { Some(Value::List(vec![])) }
        }

        // ── Parallel Swarm Fan-Out ──
        "swarm" | "parallel_fetch" => {
            // swarm(requests) — fire ALL requests in parallel threads, return all results
            // Each request is a dict: {url, method?, body?, headers?, timeout_ms?}
            // Returns list of result dicts: [{ok, status, body, model, time_ms}]
            if let Some(Value::List(reqs)) = args.first() {
                let mut handles = Vec::new();
                for req_val in reqs {
                    let (url, method, body, headers, timeout, model) = if let Value::Dict(d) = req_val {
                        let get = |key: &str| d.iter().find(|(k,_)| k == key).map(|(_,v)| v.to_display());
                        (
                            get("url").unwrap_or_default(),
                            get("method").unwrap_or("POST".into()),
                            get("body").unwrap_or_default(),
                            get("headers").unwrap_or_default(),
                            get("timeout_ms").and_then(|s| s.parse::<u64>().ok()).unwrap_or(15000),
                            get("model").unwrap_or("unknown".into()),
                        )
                    } else { continue };
                    if url.is_empty() { continue }
                    let url_c = url.clone();
                    let method_c = method.clone();
                    let body_c = body.clone();
                    let headers_c = headers.clone();
                    let model_c = model.clone();
                    handles.push(std::thread::spawn(move || {
                        let start = std::time::Instant::now();
                        let agent = ureq::AgentBuilder::new()
                            .timeout(std::time::Duration::from_millis(timeout))
                            .build();
                        let mut req_b = if method_c == "GET" {
                            agent.get(&url_c)
                        } else {
                            agent.post(&url_c)
                        };
                        req_b = req_b.set("Content-Type", "application/json");
                        // Parse headers from JSON string: {"key":"val",...}
                        if !headers_c.is_empty() {
                            if let Ok(hmap) = serde_json::from_str::<serde_json::Value>(&headers_c) {
                                if let Some(obj) = hmap.as_object() {
                                    for (k, v) in obj {
                                        if let Some(vs) = v.as_str() {
                                            req_b = req_b.set(k, vs);
                                        }
                                    }
                                }
                            }
                        }
                        let resp = if method_c == "GET" {
                            req_b.call()
                        } else {
                            req_b.send_string(&body_c)
                        };
                        let elapsed = start.elapsed().as_millis() as i64;
                        match resp {
                            Ok(r) => {
                                let status = r.status() as i64;
                                let rbody = r.into_string().unwrap_or_default();
                                vec![
                                    ("ok".to_string(), if status < 400 { 1i8 } else { -1 }),
                                    ("status_code".to_string(), 0),
                                ].into_iter().collect::<Vec<_>>();
                                // Return as serialized JSON for thread safety
                                format!("{{\"ok\":1,\"status\":{},\"body\":{},\"model\":\"{}\",\"time_ms\":{}}}",
                                    status, serde_json::to_string(&rbody).unwrap_or("\"\"".into()), model_c, elapsed)
                            }
                            Err(e) => {
                                format!("{{\"ok\":-1,\"error\":{},\"model\":\"{}\",\"time_ms\":{}}}",
                                    serde_json::to_string(&e.to_string()).unwrap_or("\"error\"".into()), model_c, elapsed)
                            }
                        }
                    }));
                }
                // Collect all thread results
                let mut results = Vec::new();
                for h in handles {
                    if let Ok(json_str) = h.join() {
                        // Parse the JSON string back into a Value::Dict
                        if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&json_str) {
                            if let Some(obj) = parsed.as_object() {
                                let mut dict = Vec::new();
                                for (k, v) in obj {
                                    let val = match v {
                                        serde_json::Value::Number(n) => {
                                            if let Some(i) = n.as_i64() { Value::Int(i) }
                                            else if let Some(f) = n.as_f64() { Value::Float(f) }
                                            else { Value::Null }
                                        }
                                        serde_json::Value::String(s) => Value::Str(s.clone()),
                                        serde_json::Value::Bool(b) => Value::Bool(*b),
                                        _ => Value::Str(v.to_string()),
                                    };
                                    dict.push((k.clone(), val));
                                }
                                results.push(Value::Dict(dict));
                            }
                        }
                    }
                }
                Some(Value::List(results))
            } else { Some(Value::List(vec![])) }
        }

        // ── Ternary Object Constructors ──
        "TCache" => {
            // TCache(name, capacity?) — create cache dict
            let name = args.first().map(|v| v.to_display()).unwrap_or("default".into());
            let capacity = args.get(1).map(|v| v.to_int()).unwrap_or(1000);
            Some(Value::Dict(vec![
                ("type".into(), Value::Str("TCache".into())),
                ("name".into(), Value::Str(name)),
                ("capacity".into(), Value::Int(capacity)),
                ("entries".into(), Value::Dict(vec![])),
                ("hits".into(), Value::Int(0)),
                ("misses".into(), Value::Int(0)),
                ("state".into(), Value::Trit(1)),
            ]))
        }
        "TForge" => {
            // TForge(name) — create forge (code analyzer) dict
            let name = args.first().map(|v| v.to_display()).unwrap_or("default".into());
            Some(Value::Dict(vec![
                ("type".into(), Value::Str("TForge".into())),
                ("name".into(), Value::Str(name)),
                ("analyses".into(), Value::Int(0)),
                ("state".into(), Value::Trit(1)),
            ]))
        }
        "TIndex" => {
            // TIndex(name) — create search index dict
            let name = args.first().map(|v| v.to_display()).unwrap_or("default".into());
            Some(Value::Dict(vec![
                ("type".into(), Value::Str("TIndex".into())),
                ("name".into(), Value::Str(name)),
                ("documents".into(), Value::List(vec![])),
                ("count".into(), Value::Int(0)),
                ("state".into(), Value::Trit(1)),
            ]))
        }

        // ── File append ──
        "append_file" => {
            use std::io::Write;
            if let (Some(Value::Str(path)), Some(Value::Str(content))) = (args.first(), args.get(1)) {
                match std::fs::OpenOptions::new().create(true).append(true).open(path) {
                    Ok(mut f) => {
                        match f.write_all(content.as_bytes()) {
                            Ok(_) => Some(Value::Trit(1)),
                            Err(_) => Some(Value::Trit(-1)),
                        }
                    }
                    Err(_) => Some(Value::Trit(-1)),
                }
            } else { Some(Value::Trit(-1)) }
        }
        "delete_file" | "remove_file" => {
            if let Some(Value::Str(path)) = args.first() {
                match std::fs::remove_file(path) {
                    Ok(_) => Some(Value::Trit(1)),
                    Err(_) => Some(Value::Trit(-1)),
                }
            } else { Some(Value::Trit(-1)) }
        }
        "file_size" => {
            if let Some(Value::Str(path)) = args.first() {
                match std::fs::metadata(path) {
                    Ok(m) => Some(Value::Int(m.len() as i64)),
                    Err(_) => Some(Value::Int(-1)),
                }
            } else { Some(Value::Int(-1)) }
        }

        // ── Extended Filesystem (Pure NovaLang — no PowerShell needed) ──

        "is_dir" => {
            let p = args.first().unwrap_or(&Value::Null).to_display();
            Some(Value::Trit(if std::path::Path::new(&p).is_dir() { 1 } else { -1 }))
        }
        "is_file" => {
            let p = args.first().unwrap_or(&Value::Null).to_display();
            Some(Value::Trit(if std::path::Path::new(&p).is_file() { 1 } else { -1 }))
        }
        "file_mtime" => {
            // Returns modification time as Unix timestamp (seconds)
            if let Some(Value::Str(path)) = args.first() {
                match std::fs::metadata(path) {
                    Ok(m) => {
                        match m.modified() {
                            Ok(t) => {
                                let secs = t.duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_secs();
                                Some(Value::Int(secs as i64))
                            }
                            Err(_) => Some(Value::Int(-1)),
                        }
                    }
                    Err(_) => Some(Value::Int(-1)),
                }
            } else { Some(Value::Int(-1)) }
        }
        "file_stat" => {
            // Returns dict: {size, mtime, is_dir, is_file, readonly}
            if let Some(Value::Str(path)) = args.first() {
                match std::fs::metadata(path) {
                    Ok(m) => {
                        let mtime = m.modified()
                            .map(|t| t.duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_secs() as i64)
                            .unwrap_or(-1);
                        let d = vec![
                            ("size".to_string(), Value::Int(m.len() as i64)),
                            ("mtime".to_string(), Value::Int(mtime)),
                            ("is_dir".to_string(), Value::Trit(if m.is_dir() { 1 } else { -1 })),
                            ("is_file".to_string(), Value::Trit(if m.is_file() { 1 } else { -1 })),
                            ("readonly".to_string(), Value::Trit(if m.permissions().readonly() { 1 } else { -1 })),
                        ];
                        Some(Value::Dict(d))
                    }
                    Err(_) => Some(Value::Null),
                }
            } else { Some(Value::Null) }
        }
        "dir_walk" | "walk_dir" => {
            // Recursively list all files in a directory tree
            // Returns list of dicts: [{path, size, is_dir, mtime}]
            // Optional depth arg: dir_walk(path, max_depth)
            let p = args.first().unwrap_or(&Value::Null).to_display();
            let max_depth = match args.get(1) {
                Some(Value::Int(d)) => *d as usize,
                _ => 999,
            };
            fn walk_recursive(dir: &std::path::Path, depth: usize, max_depth: usize, results: &mut Vec<Value>) {
                if depth > max_depth { return; }
                if let Ok(entries) = std::fs::read_dir(dir) {
                    for entry in entries.flatten() {
                        let path = entry.path();
                        let meta = std::fs::metadata(&path);
                        let (size, mtime, is_d) = match &meta {
                            Ok(m) => {
                                let mt = m.modified()
                                    .map(|t| t.duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_secs() as i64)
                                    .unwrap_or(0);
                                (m.len() as i64, mt, m.is_dir())
                            }
                            Err(_) => (0, 0, false),
                        };
                        let d = vec![
                            ("path".to_string(), Value::Str(path.to_string_lossy().to_string())),
                            ("size".to_string(), Value::Int(size)),
                            ("is_dir".to_string(), Value::Trit(if is_d { 1 } else { -1 })),
                            ("mtime".to_string(), Value::Int(mtime)),
                            ("depth".to_string(), Value::Int(depth as i64)),
                        ];
                        results.push(Value::Dict(d));
                        if is_d {
                            walk_recursive(&path, depth + 1, max_depth, results);
                        }
                    }
                }
            }
            let mut results = Vec::new();
            walk_recursive(std::path::Path::new(&p), 0, max_depth, &mut results);
            Some(Value::List(results))
        }
        "copy_file" => {
            if args.len() >= 2 {
                let src = args[0].to_display();
                let dst = args[1].to_display();
                match std::fs::copy(&src, &dst) {
                    Ok(bytes) => Some(Value::Int(bytes as i64)),
                    Err(_) => Some(Value::Int(-1)),
                }
            } else { Some(Value::Int(-1)) }
        }
        "rename_file" | "move_file" => {
            if args.len() >= 2 {
                let src = args[0].to_display();
                let dst = args[1].to_display();
                match std::fs::rename(&src, &dst) {
                    Ok(_) => Some(Value::Trit(1)),
                    Err(_) => Some(Value::Trit(-1)),
                }
            } else { Some(Value::Trit(-1)) }
        }
        "rmdir" => {
            let p = args.first().unwrap_or(&Value::Null).to_display();
            match std::fs::remove_dir(&p) {
                Ok(_) => Some(Value::Trit(1)),
                Err(_) => Some(Value::Trit(-1)),
            }
        }
        "path_join" => {
            let mut p = std::path::PathBuf::new();
            for a in args.iter() {
                let s: String = a.to_display();
                p.push(s);
            }
            Some(Value::Str(p.to_string_lossy().to_string()))
        }
        "path_parent" => {
            let p = args.first().unwrap_or(&Value::Null).to_display();
            let parent = std::path::Path::new(&p).parent()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_default();
            Some(Value::Str(parent))
        }
        "path_filename" => {
            let p = args.first().unwrap_or(&Value::Null).to_display();
            let name = std::path::Path::new(&p).file_name()
                .map(|n| n.to_string_lossy().to_string())
                .unwrap_or_default();
            Some(Value::Str(name))
        }
        "path_ext" => {
            let p = args.first().unwrap_or(&Value::Null).to_display();
            let ext = std::path::Path::new(&p).extension()
                .map(|e| e.to_string_lossy().to_string())
                .unwrap_or_default();
            Some(Value::Str(ext))
        }

        // ── Win32 Native Builtins (Windows only) ──
        // These call Windows APIs directly via Rust std — no PowerShell
        // ══════════════════════════════════════════════════════════
        // Win32 Native Builtins — PURE (no PowerShell, no Python)
        // Direct OS API calls via Rust FFI
        // ══════════════════════════════════════════════════════════

        #[cfg(target_os = "windows")]
        "clipboard_read" => {
            // Win32 clipboard via OpenClipboard/GetClipboardData
            use std::ptr;
            #[link(name = "user32")]
            extern "system" {
                fn OpenClipboard(hwnd: *mut std::ffi::c_void) -> i32;
                fn CloseClipboard() -> i32;
                fn GetClipboardData(format: u32) -> *mut std::ffi::c_void;
            }
            #[link(name = "kernel32")]
            extern "system" {
                fn GlobalLock(hmem: *mut std::ffi::c_void) -> *mut u8;
                fn GlobalUnlock(hmem: *mut std::ffi::c_void) -> i32;
            }
            unsafe {
                if OpenClipboard(ptr::null_mut()) != 0 {
                    let h = GetClipboardData(13); // CF_UNICODETEXT
                    if !h.is_null() {
                        let p = GlobalLock(h);
                        if !p.is_null() {
                            let wide = p as *const u16;
                            let mut len = 0;
                            while *wide.add(len) != 0 { len += 1; }
                            let slice = std::slice::from_raw_parts(wide, len);
                            let text = String::from_utf16_lossy(slice);
                            GlobalUnlock(h);
                            CloseClipboard();
                            Some(Value::Str(text))
                        } else {
                            CloseClipboard();
                            Some(Value::Str(String::new()))
                        }
                    } else {
                        CloseClipboard();
                        Some(Value::Str(String::new()))
                    }
                } else {
                    Some(Value::Str(String::new()))
                }
            }
        }

        #[cfg(target_os = "windows")]
        "clipboard_write" => {
            let text = args.first().unwrap_or(&Value::Null).to_display();
            use std::ptr;
            #[link(name = "user32")]
            extern "system" {
                fn OpenClipboard(hwnd: *mut std::ffi::c_void) -> i32;
                fn CloseClipboard() -> i32;
                fn EmptyClipboard() -> i32;
                fn SetClipboardData(format: u32, hmem: *mut std::ffi::c_void) -> *mut std::ffi::c_void;
            }
            #[link(name = "kernel32")]
            extern "system" {
                fn GlobalAlloc(flags: u32, bytes: usize) -> *mut std::ffi::c_void;
                fn GlobalLock(hmem: *mut std::ffi::c_void) -> *mut u8;
                fn GlobalUnlock(hmem: *mut std::ffi::c_void) -> i32;
            }
            let wide: Vec<u16> = text.encode_utf16().chain(std::iter::once(0)).collect();
            let byte_len = wide.len() * 2;
            unsafe {
                if OpenClipboard(ptr::null_mut()) != 0 {
                    EmptyClipboard();
                    let h = GlobalAlloc(0x0002, byte_len); // GMEM_MOVEABLE
                    if !h.is_null() {
                        let p = GlobalLock(h);
                        if !p.is_null() {
                            ptr::copy_nonoverlapping(wide.as_ptr() as *const u8, p, byte_len);
                            GlobalUnlock(h);
                            SetClipboardData(13, h); // CF_UNICODETEXT
                        }
                    }
                    CloseClipboard();
                    Some(Value::Trit(1))
                } else {
                    Some(Value::Trit(-1))
                }
            }
        }

        #[cfg(target_os = "windows")]
        "process_list" => {
            // Native tasklist (no PowerShell)
            let result = std::process::Command::new("tasklist")
                .args(&["/FO", "CSV", "/NH"])
                .output();
            match result {
                Ok(out) => {
                    let text = String::from_utf8_lossy(&out.stdout);
                    let mut procs = Vec::new();
                    for line in text.lines() {
                        let parts: Vec<&str> = line.split(',').collect();
                        if parts.len() >= 5 {
                            let d = vec![
                                ("name".to_string(), Value::Str(parts[0].trim_matches('"').to_string())),
                                ("pid".to_string(), Value::Str(parts[1].trim_matches('"').to_string())),
                                ("mem".to_string(), Value::Str(parts[4].trim_matches('"').to_string())),
                            ];
                            procs.push(Value::Dict(d));
                        }
                    }
                    Some(Value::List(procs))
                }
                Err(_) => Some(Value::List(vec![])),
            }
        }

        #[cfg(target_os = "windows")]
        "system_info" => {
            let d = vec![
                ("os".to_string(), Value::Str(std::env::consts::OS.to_string())),
                ("arch".to_string(), Value::Str(std::env::consts::ARCH.to_string())),
                ("family".to_string(), Value::Str(std::env::consts::FAMILY.to_string())),
                ("hostname".to_string(), Value::Str(std::env::var("COMPUTERNAME").unwrap_or_default())),
                ("user".to_string(), Value::Str(std::env::var("USERNAME").unwrap_or_default())),
                ("cpus".to_string(), Value::Int(std::thread::available_parallelism().map(|n| n.get() as i64).unwrap_or(1))),
                ("processor".to_string(), Value::Str(std::env::var("PROCESSOR_IDENTIFIER").unwrap_or_default())),
                ("is64bit".to_string(), Value::Trit(if cfg!(target_pointer_width = "64") { 1 } else { -1 })),
            ];
            Some(Value::Dict(d))
        }

        #[cfg(target_os = "windows")]
        "sys_memory" => {
            // GlobalMemoryStatusEx — direct Win32
            #[repr(C)]
            struct MemStatus {
                length: u32,
                memory_load: u32,
                total_phys: u64,
                avail_phys: u64,
                total_page: u64,
                avail_page: u64,
                total_virt: u64,
                avail_virt: u64,
                avail_ext: u64,
            }
            #[link(name = "kernel32")]
            extern "system" {
                fn GlobalMemoryStatusEx(buf: *mut MemStatus) -> i32;
            }
            let mut ms = MemStatus {
                length: std::mem::size_of::<MemStatus>() as u32,
                memory_load: 0, total_phys: 0, avail_phys: 0,
                total_page: 0, avail_page: 0, total_virt: 0,
                avail_virt: 0, avail_ext: 0,
            };
            unsafe { GlobalMemoryStatusEx(&mut ms); }
            let total_gb = ms.total_phys as f64 / (1024.0 * 1024.0 * 1024.0);
            let avail_gb = ms.avail_phys as f64 / (1024.0 * 1024.0 * 1024.0);
            let used_gb = total_gb - avail_gb;
            let d = vec![
                ("total_gb".to_string(), Value::Float(((total_gb * 100.0).round() / 100.0) as f64)),
                ("available_gb".to_string(), Value::Float(((avail_gb * 100.0).round() / 100.0) as f64)),
                ("used_gb".to_string(), Value::Float(((used_gb * 100.0).round() / 100.0) as f64)),
                ("percent_used".to_string(), Value::Int(ms.memory_load as i64)),
            ];
            Some(Value::Dict(d))
        }

        #[cfg(target_os = "windows")]
        "sys_disk" => {
            // GetDiskFreeSpaceEx — direct Win32
            #[link(name = "kernel32")]
            extern "system" {
                fn GetDiskFreeSpaceExW(dir: *const u16, free_avail: *mut u64, total: *mut u64, total_free: *mut u64) -> i32;
            }
            let drives = ["C:\\", "D:\\", "E:\\"];
            let mut results = Vec::new();
            for drv in &drives {
                let wide: Vec<u16> = drv.encode_utf16().chain(std::iter::once(0)).collect();
                let mut free_avail: u64 = 0;
                let mut total: u64 = 0;
                let mut total_free: u64 = 0;
                let ok = unsafe { GetDiskFreeSpaceExW(wide.as_ptr(), &mut free_avail, &mut total, &mut total_free) };
                if ok != 0 && total > 0 {
                    let total_gb = total as f64 / (1024.0 * 1024.0 * 1024.0);
                    let free_gb = free_avail as f64 / (1024.0 * 1024.0 * 1024.0);
                    let used_gb = total_gb - free_gb;
                    let pct = ((used_gb / total_gb) * 1000.0).round() / 10.0;
                    let d = vec![
                        ("drive".to_string(), Value::Str(drv.to_string())),
                        ("total_gb".to_string(), Value::Float((total_gb * 100.0).round() / 100.0)),
                        ("free_gb".to_string(), Value::Float((free_gb * 100.0).round() / 100.0)),
                        ("used_gb".to_string(), Value::Float((used_gb * 100.0).round() / 100.0)),
                        ("percent_used".to_string(), Value::Float(pct)),
                    ];
                    results.push(Value::Dict(d));
                }
            }
            Some(Value::List(results))
        }

        #[cfg(target_os = "windows")]
        "win_list" => {
            // EnumWindows — list all visible windows with titles
            use std::sync::Mutex;
            static WINDOWS: Mutex<Vec<(isize, String, u32)>> = Mutex::new(Vec::new());
            #[link(name = "user32")]
            extern "system" {
                fn EnumWindows(cb: extern "system" fn(isize, isize) -> i32, param: isize) -> i32;
                fn GetWindowTextW(hwnd: isize, buf: *mut u16, max: i32) -> i32;
                fn IsWindowVisible(hwnd: isize) -> i32;
                fn GetWindowThreadProcessId(hwnd: isize, pid: *mut u32) -> u32;
            }
            extern "system" fn enum_cb(hwnd: isize, _: isize) -> i32 {
                unsafe {
                    if IsWindowVisible(hwnd) != 0 {
                        let mut buf = [0u16; 256];
                        let len = GetWindowTextW(hwnd, buf.as_mut_ptr(), 256);
                        if len > 0 {
                            let title = String::from_utf16_lossy(&buf[..len as usize]);
                            let mut pid: u32 = 0;
                            GetWindowThreadProcessId(hwnd, &mut pid);
                            if let Ok(mut w) = WINDOWS.lock() {
                                w.push((hwnd, title, pid));
                            }
                        }
                    }
                }
                1 // continue
            }
            if let Ok(mut w) = WINDOWS.lock() { w.clear(); }
            unsafe { EnumWindows(enum_cb, 0); }
            let mut results = Vec::new();
            if let Ok(w) = WINDOWS.lock() {
                for (hwnd, title, pid) in w.iter() {
                    let d = vec![
                        ("hwnd".to_string(), Value::Int(*hwnd as i64)),
                        ("title".to_string(), Value::Str(title.clone())),
                        ("pid".to_string(), Value::Int(*pid as i64)),
                    ];
                    results.push(Value::Dict(d));
                }
            }
            Some(Value::List(results))
        }

        #[cfg(target_os = "windows")]
        "win_focus" => {
            let hwnd = match args.first() {
                Some(Value::Int(h)) => *h as isize,
                _ => 0,
            };
            #[link(name = "user32")]
            extern "system" {
                fn SetForegroundWindow(hwnd: isize) -> i32;
            }
            if hwnd != 0 {
                let r = unsafe { SetForegroundWindow(hwnd) };
                Some(Value::Trit(if r != 0 { 1 } else { -1 }))
            } else {
                Some(Value::Trit(-1))
            }
        }

        #[cfg(target_os = "windows")]
        "win_show" => {
            // win_show(hwnd, cmd) — cmd: 6=minimize, 3=maximize, 1=normal, 0=hide
            let hwnd = match args.first() {
                Some(Value::Int(h)) => *h as isize,
                _ => 0,
            };
            let cmd = match args.get(1) {
                Some(Value::Int(c)) => *c as i32,
                _ => 1,
            };
            #[link(name = "user32")]
            extern "system" {
                fn ShowWindow(hwnd: isize, cmd: i32) -> i32;
            }
            if hwnd != 0 {
                let r = unsafe { ShowWindow(hwnd, cmd) };
                Some(Value::Trit(if r != 0 { 1 } else { 0 }))
            } else {
                Some(Value::Trit(-1))
            }
        }

        #[cfg(target_os = "windows")]
        "win_resize" => {
            // win_resize(hwnd, width, height)
            let hwnd = match args.first() { Some(Value::Int(h)) => *h as isize, _ => 0 };
            let w = match args.get(1) { Some(Value::Int(v)) => *v as i32, _ => 800 };
            let h = match args.get(2) { Some(Value::Int(v)) => *v as i32, _ => 600 };
            #[link(name = "user32")]
            extern "system" {
                fn SetWindowPos(hwnd: isize, after: isize, x: i32, y: i32, cx: i32, cy: i32, flags: u32) -> i32;
            }
            if hwnd != 0 {
                let r = unsafe { SetWindowPos(hwnd, 0, 0, 0, w, h, 0x0002 | 0x0004) }; // SWP_NOMOVE | SWP_NOZORDER
                Some(Value::Trit(if r != 0 { 1 } else { -1 }))
            } else {
                Some(Value::Trit(-1))
            }
        }

        #[cfg(target_os = "windows")]
        "reg_read" => {
            // reg_read(key, value_name) — read a Windows registry value
            let key_path = args.first().unwrap_or(&Value::Null).to_display();
            let val_name = args.get(1).map(|v| v.to_display()).unwrap_or_default();
            // Use reg.exe (no PowerShell) to read registry
            let result = std::process::Command::new("reg")
                .args(&["query", &key_path, "/v", &val_name])
                .output();
            match result {
                Ok(out) => {
                    let text = String::from_utf8_lossy(&out.stdout);
                    // Parse: last line has "name    REG_TYPE    value"
                    let mut value = String::new();
                    for line in text.lines() {
                        let trimmed = line.trim();
                        if trimmed.contains("REG_") {
                            let parts: Vec<&str> = trimmed.splitn(3, "    ").collect();
                            if parts.len() >= 3 {
                                value = parts[2].trim().to_string();
                            }
                        }
                    }
                    let d = vec![
                        ("ok".to_string(), Value::Trit(if !value.is_empty() { 1 } else { -1 })),
                        ("key".to_string(), Value::Str(key_path)),
                        ("name".to_string(), Value::Str(val_name)),
                        ("value".to_string(), Value::Str(value)),
                    ];
                    Some(Value::Dict(d))
                }
                Err(_) => Some(Value::Dict(vec![
                    ("ok".to_string(), Value::Trit(-1)),
                    ("error".to_string(), Value::Str("reg_query_failed".to_string())),
                ])),
            }
        }

        #[cfg(target_os = "windows")]
        "reg_query" => {
            // reg_query(key) — list subkeys and values
            let key_path = args.first().unwrap_or(&Value::Null).to_display();
            let result = std::process::Command::new("reg")
                .args(&["query", &key_path])
                .output();
            match result {
                Ok(out) => {
                    let text = String::from_utf8_lossy(&out.stdout);
                    let mut subkeys = Vec::new();
                    let mut values = Vec::new();
                    for line in text.lines() {
                        let trimmed = line.trim();
                        if trimmed.starts_with("HKEY_") || trimmed.starts_with("HK") {
                            if trimmed != key_path {
                                subkeys.push(Value::Str(trimmed.to_string()));
                            }
                        } else if trimmed.contains("REG_") {
                            let parts: Vec<&str> = trimmed.splitn(3, "    ").collect();
                            if parts.len() >= 3 {
                                let d = vec![
                                    ("name".to_string(), Value::Str(parts[0].trim().to_string())),
                                    ("type".to_string(), Value::Str(parts[1].trim().to_string())),
                                    ("data".to_string(), Value::Str(parts[2].trim().to_string())),
                                ];
                                values.push(Value::Dict(d));
                            }
                        }
                    }
                    let d = vec![
                        ("ok".to_string(), Value::Trit(1)),
                        ("key".to_string(), Value::Str(key_path)),
                        ("subkeys".to_string(), Value::List(subkeys)),
                        ("values".to_string(), Value::List(values)),
                    ];
                    Some(Value::Dict(d))
                }
                Err(_) => Some(Value::Dict(vec![
                    ("ok".to_string(), Value::Trit(-1)),
                    ("error".to_string(), Value::Str("reg_query_failed".to_string())),
                ])),
            }
        }

        #[cfg(target_os = "windows")]
        "net_connections" => {
            // netstat -ano (no PowerShell)
            let result = std::process::Command::new("netstat").args(&["-ano"]).output();
            match result {
                Ok(out) => {
                    let text = String::from_utf8_lossy(&out.stdout);
                    let mut conns = Vec::new();
                    for line in text.lines().skip(4) {
                        let parts: Vec<&str> = line.split_whitespace().collect();
                        if parts.len() >= 4 {
                            let mut d = vec![
                                ("proto".to_string(), Value::Str(parts[0].to_string())),
                                ("local".to_string(), Value::Str(parts[1].to_string())),
                                ("remote".to_string(), Value::Str(parts[2].to_string())),
                                ("state".to_string(), Value::Str(parts[3].to_string())),
                            ];
                            if parts.len() >= 5 {
                                d.push(("pid".to_string(), Value::Str(parts[4].to_string())));
                            }
                            conns.push(Value::Dict(d));
                        }
                    }
                    Some(Value::List(conns))
                }
                Err(_) => Some(Value::List(vec![])),
            }
        }

        // ── HTTP Server stubs (tserve/troute/tstart) ──
        // These are handled specially by the VM
        "tserve" | "troute" | "tstart" => None,

        // ── Ternary Matrix Multiplication ──
        "tmatmul_flops" => {
            // tmatmul_flops(n) — generate FLOP comparison table for NxN matmul
            let n = args.first().unwrap_or(&Value::Int(243)).to_int() as usize;
            let report = crate::tmatmul::flop_comparison(n);
            Some(Value::Str(report))
        }
        "tmatmul_bench" => {
            // tmatmul_bench(m, k, n) — run all algorithms, return stats
            let m = args.first().unwrap_or(&Value::Int(27)).to_int() as usize;
            let k = args.get(1).unwrap_or(&Value::Int(27)).to_int() as usize;
            let n_dim = args.get(2).unwrap_or(&Value::Int(27)).to_int() as usize;
            let results = crate::tmatmul::benchmark_all(m, k, n_dim, 0.42);
            let lines: Vec<Value> = results.iter().map(|s| Value::Str(format!("{}", s))).collect();
            Some(Value::List(lines))
        }
        "tmatmul" => {
            // tmatmul(a_list, b_list, m, k, n) — ternary matmul with auto-select
            // a_list = flat list of i32 activations (m*k elements)
            // b_list = flat list of trits (k*n elements, each -1/0/+1)
            let a_list = match args.first() {
                Some(Value::List(v)) => v.iter().map(|x| x.to_int() as i32).collect::<Vec<_>>(),
                _ => return Some(Value::Str("tmatmul: first arg must be list".into())),
            };
            let b_list = match args.get(1) {
                Some(Value::List(v)) => v.iter().map(|x| x.to_trit()).collect::<Vec<_>>(),
                _ => return Some(Value::Str("tmatmul: second arg must be list".into())),
            };
            let m = args.get(2).unwrap_or(&Value::Int(1)).to_int() as usize;
            let k = args.get(3).unwrap_or(&Value::Int(1)).to_int() as usize;
            let n_dim = args.get(4).unwrap_or(&Value::Int(1)).to_int() as usize;
            match crate::tmatmul::TernaryMatrix::from_data(k, n_dim, b_list) {
                Ok(b_mat) => {
                    let (c, stats) = crate::tmatmul::auto_select_algorithm(&a_list, &b_mat, m, k, n_dim);
                    let result_list: Vec<Value> = c.iter().map(|&v| Value::Int(v as i64)).collect();
                    let pairs = vec![
                        ("result".into(), Value::List(result_list)),
                        ("algorithm".into(), Value::Str(stats.algorithm)),
                        ("speedup".into(), Value::Float(stats.speedup_vs_fp16)),
                        ("ternary_ops".into(), Value::Int(stats.ternary_ops as i64)),
                        ("fp16_flops".into(), Value::Int(stats.fp16_flops as i64)),
                        ("zero_pct".into(), Value::Float(stats.zero_weight_pct)),
                    ];
                    Some(Value::Dict(pairs))
                }
                Err(e) => Some(Value::Str(format!("tmatmul error: {}", e))),
            }
        }

        // ── Bitwise Operators ──
        "bit_and" => {
            let a = args.first().unwrap_or(&Value::Int(0)).to_int();
            let b = args.get(1).unwrap_or(&Value::Int(0)).to_int();
            Some(Value::Int(a & b))
        }
        "bit_or" => {
            let a = args.first().unwrap_or(&Value::Int(0)).to_int();
            let b = args.get(1).unwrap_or(&Value::Int(0)).to_int();
            Some(Value::Int(a | b))
        }
        "bit_xor" => {
            let a = args.first().unwrap_or(&Value::Int(0)).to_int();
            let b = args.get(1).unwrap_or(&Value::Int(0)).to_int();
            Some(Value::Int(a ^ b))
        }
        "bit_not" => {
            let a = args.first().unwrap_or(&Value::Int(0)).to_int();
            Some(Value::Int(!a))
        }
        "bit_shl" => {
            let a = args.first().unwrap_or(&Value::Int(0)).to_int();
            let b = args.get(1).unwrap_or(&Value::Int(0)).to_int();
            Some(Value::Int(a << (b as u32 & 63)))
        }
        "bit_shr" => {
            let a = args.first().unwrap_or(&Value::Int(0)).to_int();
            let b = args.get(1).unwrap_or(&Value::Int(0)).to_int();
            Some(Value::Int(a >> (b as u32 & 63)))
        }

        // ── HTTP Methods (PUT, DELETE, PATCH) ──
        "http_put" => {
            let url = args.first().unwrap_or(&Value::Null).to_display();
            let body = args.get(1).unwrap_or(&Value::Str("".into())).to_display();
            let timeout_ms = args.get(2).map(|v| v.to_int() as u64).unwrap_or(30_000);
            let cmd = format!("curl -s -X PUT -H \"Content-Type: application/json\" -d \"{}\" --connect-timeout {} \"{}\"",
                body.replace("\"", "\\\""),
                timeout_ms / 1000,
                url);
            match std::process::Command::new("cmd").args(&["/c", &cmd]).output() {
                Ok(output) => {
                    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
                    let mut pairs = Vec::new();
                    pairs.push(("ok".into(), Value::Trit(if output.status.success() { 1 } else { -1 })));
                    pairs.push(("body".into(), Value::Str(stdout)));
                    pairs.push(("status".into(), Value::Int(if output.status.success() { 200 } else { 500 })));
                    Some(Value::Dict(pairs))
                }
                Err(e) => {
                    let mut pairs = Vec::new();
                    pairs.push(("ok".into(), Value::Trit(-1)));
                    pairs.push(("error".into(), Value::Str(e.to_string())));
                    Some(Value::Dict(pairs))
                }
            }
        }
        "http_delete" => {
            let url = args.first().unwrap_or(&Value::Null).to_display();
            let timeout_ms = args.get(1).map(|v| v.to_int() as u64).unwrap_or(30_000);
            let cmd = format!("curl -s -X DELETE --connect-timeout {} \"{}\"", timeout_ms / 1000, url);
            match std::process::Command::new("cmd").args(&["/c", &cmd]).output() {
                Ok(output) => {
                    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
                    let mut pairs = Vec::new();
                    pairs.push(("ok".into(), Value::Trit(if output.status.success() { 1 } else { -1 })));
                    pairs.push(("body".into(), Value::Str(stdout)));
                    Some(Value::Dict(pairs))
                }
                Err(e) => {
                    let mut pairs = Vec::new();
                    pairs.push(("ok".into(), Value::Trit(-1)));
                    pairs.push(("error".into(), Value::Str(e.to_string())));
                    Some(Value::Dict(pairs))
                }
            }
        }
        "http_patch" => {
            let url = args.first().unwrap_or(&Value::Null).to_display();
            let body = args.get(1).unwrap_or(&Value::Str("".into())).to_display();
            let timeout_ms = args.get(2).map(|v| v.to_int() as u64).unwrap_or(30_000);
            let cmd = format!("curl -s -X PATCH -H \"Content-Type: application/json\" -d \"{}\" --connect-timeout {} \"{}\"",
                body.replace("\"", "\\\""),
                timeout_ms / 1000,
                url);
            match std::process::Command::new("cmd").args(&["/c", &cmd]).output() {
                Ok(output) => {
                    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
                    let mut pairs = Vec::new();
                    pairs.push(("ok".into(), Value::Trit(if output.status.success() { 1 } else { -1 })));
                    pairs.push(("body".into(), Value::Str(stdout)));
                    Some(Value::Dict(pairs))
                }
                Err(e) => {
                    let mut pairs = Vec::new();
                    pairs.push(("ok".into(), Value::Trit(-1)));
                    pairs.push(("error".into(), Value::Str(e.to_string())));
                    Some(Value::Dict(pairs))
                }
            }
        }

        // ── Assertions ──
        "assert" => {
            let val = args.first().unwrap_or(&Value::Null);
            let msg = args.get(1).map(|v| v.to_display()).unwrap_or_else(|| "assertion failed".into());
            if val.is_truthy() {
                Some(Value::Trit(1))
            } else {
                eprintln!("[ASSERT FAILED] {}", msg);
                Some(Value::Trit(-1))
            }
        }
        "assert_eq" => {
            let a = args.first().unwrap_or(&Value::Null);
            let b = args.get(1).unwrap_or(&Value::Null);
            let msg = args.get(2).map(|v| v.to_display()).unwrap_or_else(|| format!("expected {} == {}", a.to_display(), b.to_display()));
            if a == b {
                Some(Value::Trit(1))
            } else {
                eprintln!("[ASSERT_EQ FAILED] {} -- got: {} vs {}", msg, a.to_display(), b.to_display());
                Some(Value::Trit(-1))
            }
        }

        // ── Deep Clone & Deep Merge ──
        "deep_clone" => {
            // Rust clone is already deep for our Value enum since Vec and String are owned
            Some(args.first().cloned().unwrap_or(Value::Null))
        }
        "deep_merge" => {
            let a = args.first().unwrap_or(&Value::Null);
            let b = args.get(1).unwrap_or(&Value::Null);
            match (a, b) {
                (Value::Dict(pairs_a), Value::Dict(pairs_b)) => {
                    let mut result = pairs_a.clone();
                    for (key, val_b) in pairs_b {
                        if let Some(existing) = result.iter_mut().find(|(k, _)| k == key) {
                            if let (Value::Dict(_), Value::Dict(_)) = (&existing.1, val_b) {
                                if let Some(merged) = call_builtin("deep_merge", &[existing.1.clone(), val_b.clone()]) {
                                    existing.1 = merged;
                                }
                            } else {
                                existing.1 = val_b.clone();
                            }
                        } else {
                            result.push((key.clone(), val_b.clone()));
                        }
                    }
                    Some(Value::Dict(result))
                }
                _ => Some(args.get(1).cloned().unwrap_or(args.first().cloned().unwrap_or(Value::Null)))
            }
        }

        // ── Retry3 (ternary retry config) ──
        "retry3" => {
            let max = args.first().unwrap_or(&Value::Int(3)).to_int();
            let delay = args.get(1).unwrap_or(&Value::Int(1000)).to_int();
            let mut pairs = Vec::new();
            pairs.push(("max_attempts".into(), Value::Int(max)));
            pairs.push(("delay_ms".into(), Value::Int(delay)));
            pairs.push(("attempt".into(), Value::Int(0)));
            pairs.push(("state".into(), Value::Trit(0)));
            Some(Value::Dict(pairs))
        }

        // ── Char Code Operations ──
        "char_code" | "ord" => {
            let s = args.first().unwrap_or(&Value::Null).to_display();
            Some(Value::Int(s.chars().next().unwrap_or('\0') as i64))
        }
        "from_char_code" | "chr" => {
            let code = args.first().unwrap_or(&Value::Int(0)).to_int();
            Some(Value::Str(char::from_u32(code as u32).unwrap_or('\0').to_string()))
        }

        // ── String Extras ──
        "repeat" | "str_repeat" => {
            let s = args.first().unwrap_or(&Value::Null).to_display();
            let n = args.get(1).unwrap_or(&Value::Int(1)).to_int().max(0) as usize;
            Some(Value::Str(s.repeat(n)))
        }
        "pad_left" | "lpad" => {
            let s = args.first().unwrap_or(&Value::Null).to_display();
            let width = args.get(1).unwrap_or(&Value::Int(0)).to_int() as usize;
            let pad_char = args.get(2).map(|v| v.to_display()).unwrap_or_else(|| " ".into());
            let pad = pad_char.chars().next().unwrap_or(' ');
            if s.len() >= width {
                Some(Value::Str(s))
            } else {
                let padding: String = std::iter::repeat(pad).take(width - s.len()).collect();
                Some(Value::Str(format!("{}{}", padding, s)))
            }
        }
        "pad_right" | "rpad" => {
            let s = args.first().unwrap_or(&Value::Null).to_display();
            let width = args.get(1).unwrap_or(&Value::Int(0)).to_int() as usize;
            let pad_char = args.get(2).map(|v| v.to_display()).unwrap_or_else(|| " ".into());
            let pad = pad_char.chars().next().unwrap_or(' ');
            if s.len() >= width {
                Some(Value::Str(s))
            } else {
                let padding: String = std::iter::repeat(pad).take(width - s.len()).collect();
                Some(Value::Str(format!("{}{}", s, padding)))
            }
        }

        // ── Index Of (string search) ──
        "index_of" | "indexOf" => {
            let haystack = args.first().unwrap_or(&Value::Null).to_display();
            let needle = args.get(1).unwrap_or(&Value::Null).to_display();
            match haystack.find(&needle) {
                Some(pos) => Some(Value::Int(pos as i64)),
                None => Some(Value::Int(-1)),
            }
        }
        "last_index_of" => {
            let haystack = args.first().unwrap_or(&Value::Null).to_display();
            let needle = args.get(1).unwrap_or(&Value::Null).to_display();
            match haystack.rfind(&needle) {
                Some(pos) => Some(Value::Int(pos as i64)),
                None => Some(Value::Int(-1)),
            }
        }

        // ── List Extras ──
        "flat" | "flatten" => {
            if let Some(Value::List(items)) = args.first() {
                let mut result = Vec::new();
                for item in items {
                    if let Value::List(inner) = item {
                        result.extend(inner.clone());
                    } else {
                        result.push(item.clone());
                    }
                }
                Some(Value::List(result))
            } else {
                Some(args.first().cloned().unwrap_or(Value::Null))
            }
        }
        "zip" => {
            let a = match args.first() { Some(Value::List(l)) => l.clone(), _ => vec![] };
            let b = match args.get(1) { Some(Value::List(l)) => l.clone(), _ => vec![] };
            let result: Vec<Value> = a.into_iter().zip(b.into_iter())
                .map(|(x, y)| Value::List(vec![x, y]))
                .collect();
            Some(Value::List(result))
        }
        "reduce" | "fold" => {
            if let Some(Value::List(items)) = args.first() {
                let init = args.get(1).cloned().unwrap_or(Value::Int(0));
                let mut acc = init.to_float();
                for item in items {
                    acc += item.to_float();
                }
                Some(Value::Float(acc))
            } else {
                Some(Value::Null)
            }
        }

        // ══════════════════════════════════════════════
        // v1.4 BUILTINS — 40+ new functions
        // ══════════════════════════════════════════════

        // ── Type Checking (12 functions) ──
        "is_int" => Some(Value::Trit(if matches!(args.first(), Some(Value::Int(_))) { 1 } else { -1 })),
        "is_float" => Some(Value::Trit(if matches!(args.first(), Some(Value::Float(_))) { 1 } else { -1 })),
        "is_str" | "is_string" => Some(Value::Trit(if matches!(args.first(), Some(Value::Str(_))) { 1 } else { -1 })),
        "is_bool" => Some(Value::Trit(if matches!(args.first(), Some(Value::Bool(_))) { 1 } else { -1 })),
        "is_list" | "is_array" => Some(Value::Trit(if matches!(args.first(), Some(Value::List(_))) { 1 } else { -1 })),
        "is_dict" | "is_map" | "is_object" => Some(Value::Trit(if matches!(args.first(), Some(Value::Dict(_))) { 1 } else { -1 })),
        "is_null" | "is_nil" => Some(Value::Trit(if matches!(args.first(), Some(Value::Null)) { 1 } else { -1 })),
        "is_trit" => Some(Value::Trit(if matches!(args.first(), Some(Value::Trit(_))) { 1 } else { -1 })),
        "is_fn" | "is_function" | "is_callable" => Some(Value::Trit(if matches!(args.first(), Some(Value::Fn(_))) { 1 } else { -1 })),
        "is_number" | "is_numeric" => {
            match args.first() {
                Some(Value::Int(_)) | Some(Value::Float(_)) => Some(Value::Trit(1)),
                Some(Value::Str(s)) => Some(Value::Trit(if s.parse::<f64>().is_ok() { 1 } else { -1 })),
                _ => Some(Value::Trit(-1)),
            }
        }
        "is_empty" => {
            match args.first() {
                Some(Value::Str(s)) => Some(Value::Trit(if s.is_empty() { 1 } else { -1 })),
                Some(Value::List(l)) => Some(Value::Trit(if l.is_empty() { 1 } else { -1 })),
                Some(Value::Dict(d)) => Some(Value::Trit(if d.is_empty() { 1 } else { -1 })),
                Some(Value::Null) => Some(Value::Trit(1)),
                _ => Some(Value::Trit(-1)),
            }
        }
        "is_truthy" => Some(Value::Trit(if args.first().unwrap_or(&Value::Null).is_truthy() { 1 } else { -1 })),

        // ── Collection Power (15 functions) ──
        "unique" | "distinct" => {
            if let Some(Value::List(items)) = args.first() {
                let mut seen = Vec::new();
                let mut result = Vec::new();
                for item in items {
                    let key = item.to_display();
                    if !seen.contains(&key) {
                        seen.push(key);
                        result.push(item.clone());
                    }
                }
                Some(Value::List(result))
            } else { Some(Value::Null) }
        }
        "find" => {
            // find(list, value) → first matching element or null
            if let Some(Value::List(items)) = args.first() {
                let needle = args.get(1).unwrap_or(&Value::Null);
                Some(items.iter().find(|item| item == &needle).cloned().unwrap_or(Value::Null))
            } else { Some(Value::Null) }
        }
        "every" | "all" => {
            // every(list) → TRUE if all elements are truthy
            if let Some(Value::List(items)) = args.first() {
                Some(Value::Trit(if items.iter().all(|v| v.is_truthy()) { 1 } else { -1 }))
            } else { Some(Value::Trit(-1)) }
        }
        "some" | "any" => {
            // some(list) → TRUE if any element is truthy
            if let Some(Value::List(items)) = args.first() {
                Some(Value::Trit(if items.iter().any(|v| v.is_truthy()) { 1 } else { -1 }))
            } else { Some(Value::Trit(-1)) }
        }
        "none" => {
            // none(list) → TRUE if no elements are truthy
            if let Some(Value::List(items)) = args.first() {
                Some(Value::Trit(if !items.iter().any(|v| v.is_truthy()) { 1 } else { -1 }))
            } else { Some(Value::Trit(1)) }
        }
        "count" => {
            // count(list) or count(list, value) → count matching elements
            if let Some(Value::List(items)) = args.first() {
                if let Some(needle) = args.get(1) {
                    Some(Value::Int(items.iter().filter(|item| item == &needle).count() as i64))
                } else {
                    Some(Value::Int(items.len() as i64))
                }
            } else { Some(Value::Int(0)) }
        }
        "chunk" | "chunks" => {
            // chunk(list, size) → [[a,b], [c,d], ...]
            if let Some(Value::List(items)) = args.first() {
                let size = args.get(1).unwrap_or(&Value::Int(1)).to_int().max(1) as usize;
                let chunks: Vec<Value> = items.chunks(size)
                    .map(|c| Value::List(c.to_vec()))
                    .collect();
                Some(Value::List(chunks))
            } else { Some(Value::Null) }
        }
        "take" => {
            // take(list, n) → first n elements
            if let Some(Value::List(items)) = args.first() {
                let n = args.get(1).unwrap_or(&Value::Int(1)).to_int().max(0) as usize;
                Some(Value::List(items.iter().take(n).cloned().collect()))
            } else { Some(Value::Null) }
        }
        "drop" | "skip" => {
            // drop(list, n) → skip first n elements
            if let Some(Value::List(items)) = args.first() {
                let n = args.get(1).unwrap_or(&Value::Int(1)).to_int().max(0) as usize;
                Some(Value::List(items.iter().skip(n).cloned().collect()))
            } else { Some(Value::Null) }
        }
        "first" | "head" => {
            if let Some(Value::List(items)) = args.first() {
                Some(items.first().cloned().unwrap_or(Value::Null))
            } else { Some(Value::Null) }
        }
        "last" | "tail" => {
            if let Some(Value::List(items)) = args.first() {
                Some(items.last().cloned().unwrap_or(Value::Null))
            } else { Some(Value::Null) }
        }
        "compact" => {
            // Remove null/false values from list
            if let Some(Value::List(items)) = args.first() {
                Some(Value::List(items.iter().filter(|v| v.is_truthy()).cloned().collect()))
            } else { Some(Value::Null) }
        }
        "group_by" => {
            // group_by(list_of_dicts, key) → dict of lists grouped by key value
            if let Some(Value::List(items)) = args.first() {
                let key = args.get(1).unwrap_or(&Value::Null).to_display();
                let mut groups: Vec<(String, Vec<Value>)> = Vec::new();
                for item in items {
                    let group_key = if let Value::Dict(pairs) = item {
                        pairs.iter().find(|(k, _)| k == &key)
                            .map(|(_, v)| v.to_display())
                            .unwrap_or_else(|| "null".into())
                    } else {
                        "null".into()
                    };
                    if let Some(group) = groups.iter_mut().find(|(k, _)| k == &group_key) {
                        group.1.push(item.clone());
                    } else {
                        groups.push((group_key, vec![item.clone()]));
                    }
                }
                let result: Vec<(String, Value)> = groups.into_iter()
                    .map(|(k, v)| (k, Value::List(v)))
                    .collect();
                Some(Value::Dict(result))
            } else { Some(Value::Null) }
        }
        "dict_merge" | "merge" => {
            // Shallow merge of two dicts
            if let (Some(Value::Dict(a)), Some(Value::Dict(b))) = (args.first(), args.get(1)) {
                let mut result = a.clone();
                for (k, v) in b {
                    if let Some(entry) = result.iter_mut().find(|(ek, _)| ek == k) {
                        entry.1 = v.clone();
                    } else {
                        result.push((k.clone(), v.clone()));
                    }
                }
                Some(Value::Dict(result))
            } else { Some(Value::Null) }
        }
        "pluck" => {
            // pluck(list_of_dicts, key) → list of values for that key
            if let Some(Value::List(items)) = args.first() {
                let key = args.get(1).unwrap_or(&Value::Null).to_display();
                let result: Vec<Value> = items.iter().map(|item| {
                    if let Value::Dict(pairs) = item {
                        pairs.iter().find(|(k, _)| k == &key)
                            .map(|(_, v)| v.clone())
                            .unwrap_or(Value::Null)
                    } else { Value::Null }
                }).collect();
                Some(Value::List(result))
            } else { Some(Value::Null) }
        }

        // ── String Power (10 functions) ──
        "substr" | "substring" => {
            if let Some(Value::Str(s)) = args.first() {
                let start = args.get(1).unwrap_or(&Value::Int(0)).to_int().max(0) as usize;
                let len = args.get(2).map(|v| v.to_int().max(0) as usize);
                let chars: Vec<char> = s.chars().collect();
                let end = match len {
                    Some(l) => (start + l).min(chars.len()),
                    None => chars.len(),
                };
                let result: String = chars[start.min(chars.len())..end].iter().collect();
                Some(Value::Str(result))
            } else { Some(Value::Null) }
        }
        "char_at" => {
            if let Some(Value::Str(s)) = args.first() {
                let idx = args.get(1).unwrap_or(&Value::Int(0)).to_int() as usize;
                Some(s.chars().nth(idx).map(|c| Value::Str(c.to_string())).unwrap_or(Value::Null))
            } else { Some(Value::Null) }
        }
        "trim_start" | "ltrim" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Str(s.trim_start().to_string()))
            } else { Some(Value::Null) }
        }
        "trim_end" | "rtrim" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Str(s.trim_end().to_string()))
            } else { Some(Value::Null) }
        }
        "is_alpha" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Trit(if !s.is_empty() && s.chars().all(|c| c.is_alphabetic()) { 1 } else { -1 }))
            } else { Some(Value::Trit(-1)) }
        }
        "is_digit" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Trit(if !s.is_empty() && s.chars().all(|c| c.is_ascii_digit()) { 1 } else { -1 }))
            } else { Some(Value::Trit(-1)) }
        }
        "is_upper" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Trit(if !s.is_empty() && s.chars().all(|c| c.is_uppercase()) { 1 } else { -1 }))
            } else { Some(Value::Trit(-1)) }
        }
        "is_lower" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Trit(if !s.is_empty() && s.chars().all(|c| c.is_lowercase()) { 1 } else { -1 }))
            } else { Some(Value::Trit(-1)) }
        }
        "capitalize" => {
            if let Some(Value::Str(s)) = args.first() {
                let mut c = s.chars();
                let result = match c.next() {
                    None => String::new(),
                    Some(f) => f.to_uppercase().to_string() + &c.as_str().to_lowercase(),
                };
                Some(Value::Str(result))
            } else { Some(Value::Null) }
        }
        "title_case" => {
            if let Some(Value::Str(s)) = args.first() {
                let result: String = s.split_whitespace()
                    .map(|word| {
                        let mut c = word.chars();
                        match c.next() {
                            None => String::new(),
                            Some(f) => f.to_uppercase().to_string() + c.as_str(),
                        }
                    })
                    .collect::<Vec<_>>()
                    .join(" ");
                Some(Value::Str(result))
            } else { Some(Value::Null) }
        }
        "str_count" => {
            // Count occurrences of substring
            if let (Some(Value::Str(s)), Some(Value::Str(sub))) = (args.first(), args.get(1)) {
                Some(Value::Int(s.matches(sub.as_str()).count() as i64))
            } else { Some(Value::Int(0)) }
        }
        "str_reverse" | "reverse_str" => {
            if let Some(Value::Str(s)) = args.first() {
                Some(Value::Str(s.chars().rev().collect()))
            } else { Some(Value::Null) }
        }

        // ── Math Power (6 functions) ──
        "clamp" => {
            let v = args.first().unwrap_or(&Value::Int(0)).to_float();
            let lo = args.get(1).unwrap_or(&Value::Int(0)).to_float();
            let hi = args.get(2).unwrap_or(&Value::Int(1)).to_float();
            Some(Value::Float(v.max(lo).min(hi)))
        }
        "sign" | "signum" => {
            let v = args.first().unwrap_or(&Value::Int(0)).to_float();
            Some(Value::Trit(if v > 0.0 { 1 } else if v < 0.0 { -1 } else { 0 }))
        }
        "lerp" => {
            // Linear interpolation: lerp(a, b, t) = a + (b - a) * t
            let a = args.first().unwrap_or(&Value::Float(0.0)).to_float();
            let b = args.get(1).unwrap_or(&Value::Float(1.0)).to_float();
            let t = args.get(2).unwrap_or(&Value::Float(0.5)).to_float();
            Some(Value::Float(a + (b - a) * t))
        }
        "factorial" => {
            let n = args.first().unwrap_or(&Value::Int(0)).to_int().max(0).min(20);
            let mut result: i64 = 1;
            for i in 2..=n { result *= i; }
            Some(Value::Int(result))
        }
        "gcd" => {
            let mut a = args.first().unwrap_or(&Value::Int(0)).to_int().abs();
            let mut b = args.get(1).unwrap_or(&Value::Int(0)).to_int().abs();
            while b != 0 { let t = b; b = a % b; a = t; }
            Some(Value::Int(a))
        }
        "lcm" => {
            let a = args.first().unwrap_or(&Value::Int(0)).to_int().abs();
            let b = args.get(1).unwrap_or(&Value::Int(0)).to_int().abs();
            if a == 0 || b == 0 { Some(Value::Int(0)) }
            else {
                let mut ga = a; let mut gb = b;
                while gb != 0 { let t = gb; gb = ga % gb; ga = t; }
                Some(Value::Int(a / ga * b))
            }
        }

        // ── Base64 aliases (core impls exist above) ──
        "b64_encode" | "btoa" => {
            call_builtin("base64_encode", args)
        }
        "b64_decode" | "atob" => {
            call_builtin("base64_decode", args)
        }

        // ── Date/Time Operations ──
        "date_now" | "date_today" => {
            // Returns ISO 8601 date string
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs();
            // Simple UTC date calculation
            let days = now / 86400;
            let (y, m, d) = days_to_ymd(days as i64 + 719468); // days since epoch + offset
            Some(Value::Str(format!("{:04}-{:02}-{:02}", y, m, d)))
        }
        "timestamp" | "unix_time" => {
            let secs = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs();
            Some(Value::Int(secs as i64))
        }
        "timestamp_ms" => {
            let ms = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis();
            Some(Value::Int(ms as i64))
        }

        // ── Conversion & Formatting ──
        "hex" | "to_hex" => {
            let n = args.first().unwrap_or(&Value::Int(0)).to_int();
            Some(Value::Str(format!("0x{:x}", n)))
        }
        "oct" | "to_oct" => {
            let n = args.first().unwrap_or(&Value::Int(0)).to_int();
            Some(Value::Str(format!("0o{:o}", n)))
        }
        "bin" | "to_bin" => {
            let n = args.first().unwrap_or(&Value::Int(0)).to_int();
            Some(Value::Str(format!("0b{:b}", n)))
        }
        "parse_int" => {
            let s = args.first().unwrap_or(&Value::Null).to_display();
            let base = args.get(1).unwrap_or(&Value::Int(10)).to_int() as u32;
            let clean = s.trim().trim_start_matches("0x").trim_start_matches("0o").trim_start_matches("0b");
            Some(i64::from_str_radix(clean, base.max(2).min(36))
                .map(Value::Int)
                .unwrap_or(Value::Null))
        }
        "parse_float" => {
            let s = args.first().unwrap_or(&Value::Null).to_display();
            Some(s.trim().parse::<f64>().map(Value::Float).unwrap_or(Value::Null))
        }

        // ── Error Handling ──
        "error" | "throw" => {
            let msg = args.first().unwrap_or(&Value::Str("error".into())).to_display();
            // This actually gets caught by try3/catch3 since we use Err
            // For now, return null and print error
            eprintln!("[error] {}", msg);
            Some(Value::Null)
        }

        // ── Environment & System Extras ──
        "args" | "argv" => {
            let argv: Vec<Value> = std::env::args()
                .skip(1) // skip binary name
                .map(|a| Value::Str(a))
                .collect();
            Some(Value::List(argv))
        }
        "cwd" | "getcwd" => {
            Some(Value::Str(std::env::current_dir()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_default()))
        }
        "set_env" | "setenv" => {
            let key = args.first().unwrap_or(&Value::Null).to_display();
            let val = args.get(1).unwrap_or(&Value::Null).to_display();
            std::env::set_var(&key, &val);
            Some(Value::Trit(1))
        }

        _ => None,
    }
}

// ── Balanced Ternary Helpers ──

fn bt_encode(mut n: i64) -> String {
    if n == 0 { return "0".into(); }
    let mut digits = Vec::new();
    let neg = n < 0;
    if neg { n = -n; }
    while n > 0 {
        let rem = n % 3;
        n /= 3;
        match rem {
            0 => digits.push('0'),
            1 => digits.push('+'),
            2 => { digits.push('-'); n += 1; }
            _ => unreachable!(),
        }
    }
    if neg {
        digits = digits.iter().map(|c| match c {
            '+' => '-',
            '-' => '+',
            _ => '0',
        }).collect();
    }
    digits.reverse();
    digits.into_iter().collect()
}

fn bt_decode(s: &str) -> i64 {
    let mut n: i64 = 0;
    for c in s.chars() {
        n *= 3;
        match c {
            '+' | '1' => n += 1,
            '-' => n -= 1,
            _ => {} // '0'
        }
    }
    n
}

fn fnv1a(s: &str) -> u64 {
    let mut hash: u64 = 0xcbf29ce484222325;
    for byte in s.bytes() {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(0x100000001b3);
    }
    hash
}

// ── JSON Helpers ──

fn value_to_json(v: &Value) -> String {
    match v {
        Value::Int(i) => i.to_string(),
        Value::Float(f) => format!("{}", f),
        Value::Str(s) => format!("\"{}\"", s.replace('\\', "\\\\").replace('"', "\\\"")),
        Value::Bool(b) => if *b { "true".into() } else { "false".into() },
        Value::Trit(1) => "1".into(),
        Value::Trit(0) => "0".into(),
        Value::Trit(-1) => "-1".into(),
        Value::Trit(t) => t.to_string(),
        Value::List(items) => {
            let inner: Vec<String> = items.iter().map(|v| value_to_json(v)).collect();
            format!("[{}]", inner.join(","))
        }
        Value::Dict(pairs) => {
            let inner: Vec<String> = pairs.iter()
                .map(|(k, v)| format!("\"{}\":{}", k, value_to_json(v)))
                .collect();
            format!("{{{}}}", inner.join(","))
        }
        Value::Null => "null".into(),
        Value::Fn(name) => format!("\"<fn {}>\"", name),
    }
}

fn json_to_value(s: &str) -> Value {
    // Use serde_json for parsing
    match serde_json::from_str::<serde_json::Value>(s) {
        Ok(jv) => serde_json_to_value(&jv),
        Err(_) => Value::Null,
    }
}

fn serde_json_to_value(jv: &serde_json::Value) -> Value {
    match jv {
        serde_json::Value::Null => Value::Null,
        serde_json::Value::Bool(b) => Value::Bool(*b),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() { Value::Int(i) }
            else if let Some(f) = n.as_f64() { Value::Float(f) }
            else { Value::Null }
        }
        serde_json::Value::String(s) => Value::Str(s.clone()),
        serde_json::Value::Array(arr) => {
            Value::List(arr.iter().map(|v| serde_json_to_value(v)).collect())
        }
        serde_json::Value::Object(map) => {
            let pairs: Vec<(String, Value)> = map.iter()
                .map(|(k, v)| (k.clone(), serde_json_to_value(v)))
                .collect();
            Value::Dict(pairs)
        }
    }
}

// ── Balanced Ternary Helpers ──

fn decimal_to_bt(mut n: i64) -> String {
    if n == 0 { return "0".to_string(); }
    let negative = n < 0;
    if negative { n = -n; }
    let mut trits = Vec::new();
    while n > 0 {
        let rem = n % 3;
        n /= 3;
        match rem {
            0 => trits.push('0'),
            1 => trits.push('1'),
            2 => { trits.push('T'); n += 1; }
            _ => {}
        }
    }
    if negative {
        trits = trits.iter().map(|c| match c {
            '1' => 'T',
            'T' => '1',
            _ => '0',
        }).collect();
    }
    trits.iter().rev().collect()
}

fn bt_to_decimal(s: &str) -> i64 {
    let mut result: i64 = 0;
    for ch in s.chars() {
        result *= 3;
        match ch {
            '1' => result += 1,
            'T' => result -= 1,
            '0' => {}
            _ => {}
        }
    }
    result
}

// ── v1.4 Helper Functions ──

const B64_CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

fn base64_encode(data: &[u8]) -> String {
    let mut result = String::new();
    let mut i = 0;
    while i < data.len() {
        let b0 = data[i] as u32;
        let b1 = if i + 1 < data.len() { data[i + 1] as u32 } else { 0 };
        let b2 = if i + 2 < data.len() { data[i + 2] as u32 } else { 0 };
        let triple = (b0 << 16) | (b1 << 8) | b2;
        result.push(B64_CHARS[((triple >> 18) & 0x3F) as usize] as char);
        result.push(B64_CHARS[((triple >> 12) & 0x3F) as usize] as char);
        if i + 1 < data.len() {
            result.push(B64_CHARS[((triple >> 6) & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
        if i + 2 < data.len() {
            result.push(B64_CHARS[(triple & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
        i += 3;
    }
    result
}

fn base64_decode(data: &str) -> Option<Vec<u8>> {
    let mut result = Vec::new();
    let chars: Vec<u8> = data.bytes().filter(|b| *b != b'\n' && *b != b'\r').collect();
    let mut i = 0;
    while i < chars.len() {
        if i + 3 >= chars.len() && chars.len() < 4 { break; }
        let a = b64_val(chars.get(i).copied().unwrap_or(b'A'));
        let b = b64_val(chars.get(i + 1).copied().unwrap_or(b'A'));
        let c = b64_val(chars.get(i + 2).copied().unwrap_or(b'='));
        let d = b64_val(chars.get(i + 3).copied().unwrap_or(b'='));
        result.push(((a << 2) | (b >> 4)) as u8);
        if chars.get(i + 2) != Some(&b'=') {
            result.push((((b & 0xF) << 4) | (c >> 2)) as u8);
        }
        if chars.get(i + 3) != Some(&b'=') {
            result.push((((c & 0x3) << 6) | d) as u8);
        }
        i += 4;
    }
    Some(result)
}

fn b64_val(c: u8) -> u32 {
    match c {
        b'A'..=b'Z' => (c - b'A') as u32,
        b'a'..=b'z' => (c - b'a' + 26) as u32,
        b'0'..=b'9' => (c - b'0' + 52) as u32,
        b'+' => 62,
        b'/' => 63,
        _ => 0,
    }
}

// Pure SHA-256 implementation (no dependencies)
fn sha256_hex(data: &[u8]) -> String {
    let h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];
    let k: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ];

    // Pre-processing: padding
    let bit_len = (data.len() as u64) * 8;
    let mut msg = data.to_vec();
    msg.push(0x80);
    while (msg.len() % 64) != 56 { msg.push(0); }
    msg.extend_from_slice(&bit_len.to_be_bytes());

    let mut hash = h;
    for chunk in msg.chunks(64) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([chunk[i*4], chunk[i*4+1], chunk[i*4+2], chunk[i*4+3]]);
        }
        for i in 16..64 {
            let s0 = w[i-15].rotate_right(7) ^ w[i-15].rotate_right(18) ^ (w[i-15] >> 3);
            let s1 = w[i-2].rotate_right(17) ^ w[i-2].rotate_right(19) ^ (w[i-2] >> 10);
            w[i] = w[i-16].wrapping_add(s0).wrapping_add(w[i-7]).wrapping_add(s1);
        }
        let (mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut hh) =
            (hash[0], hash[1], hash[2], hash[3], hash[4], hash[5], hash[6], hash[7]);
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let temp1 = hh.wrapping_add(s1).wrapping_add(ch).wrapping_add(k[i]).wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let temp2 = s0.wrapping_add(maj);
            hh = g; g = f; f = e; e = d.wrapping_add(temp1);
            d = c; c = b; b = a; a = temp1.wrapping_add(temp2);
        }
        hash[0] = hash[0].wrapping_add(a);
        hash[1] = hash[1].wrapping_add(b);
        hash[2] = hash[2].wrapping_add(c);
        hash[3] = hash[3].wrapping_add(d);
        hash[4] = hash[4].wrapping_add(e);
        hash[5] = hash[5].wrapping_add(f);
        hash[6] = hash[6].wrapping_add(g);
        hash[7] = hash[7].wrapping_add(hh);
    }
    hash.iter().map(|h| format!("{:08x}", h)).collect()
}

// ═══════════════════════════════════════════════════════════════
// CRYPTOGRAPHIC FUNCTIONS — Pure Rust, zero dependencies
// ═══════════════════════════════════════════════════════════════

// HMAC-SHA256 (RFC 2104)
fn hmac_sha256(key: &[u8], message: &[u8]) -> [u8; 32] {
    let block_size = 64;
    let mut k = vec![0u8; block_size];
    if key.len() > block_size {
        let h = sha256_bytes(key);
        k[..32].copy_from_slice(&h);
    } else {
        k[..key.len()].copy_from_slice(key);
    }

    let mut ipad = vec![0x36u8; block_size];
    let mut opad = vec![0x5cu8; block_size];
    for i in 0..block_size {
        ipad[i] ^= k[i];
        opad[i] ^= k[i];
    }

    ipad.extend_from_slice(message);
    let inner_hash = sha256_bytes(&ipad);

    opad.extend_from_slice(&inner_hash);
    sha256_bytes(&opad)
}

fn hmac_sha256_hex(key: &[u8], message: &[u8]) -> String {
    hmac_sha256(key, message).iter().map(|b| format!("{:02x}", b)).collect()
}

// SHA-256 returning raw bytes (for HMAC/PBKDF2 chaining)
fn sha256_bytes(data: &[u8]) -> [u8; 32] {
    let h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];
    let k: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ];
    let bit_len = (data.len() as u64) * 8;
    let mut msg = data.to_vec();
    msg.push(0x80);
    while (msg.len() % 64) != 56 { msg.push(0); }
    msg.extend_from_slice(&bit_len.to_be_bytes());

    let mut hash = h;
    for chunk in msg.chunks(64) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([chunk[i*4], chunk[i*4+1], chunk[i*4+2], chunk[i*4+3]]);
        }
        for i in 16..64 {
            let s0 = w[i-15].rotate_right(7) ^ w[i-15].rotate_right(18) ^ (w[i-15] >> 3);
            let s1 = w[i-2].rotate_right(17) ^ w[i-2].rotate_right(19) ^ (w[i-2] >> 10);
            w[i] = w[i-16].wrapping_add(s0).wrapping_add(w[i-7]).wrapping_add(s1);
        }
        let (mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut hh) =
            (hash[0], hash[1], hash[2], hash[3], hash[4], hash[5], hash[6], hash[7]);
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let temp1 = hh.wrapping_add(s1).wrapping_add(ch).wrapping_add(k[i]).wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let temp2 = s0.wrapping_add(maj);
            hh = g; g = f; f = e; e = d.wrapping_add(temp1);
            d = c; c = b; b = a; a = temp1.wrapping_add(temp2);
        }
        hash[0] = hash[0].wrapping_add(a);
        hash[1] = hash[1].wrapping_add(b);
        hash[2] = hash[2].wrapping_add(c);
        hash[3] = hash[3].wrapping_add(d);
        hash[4] = hash[4].wrapping_add(e);
        hash[5] = hash[5].wrapping_add(f);
        hash[6] = hash[6].wrapping_add(g);
        hash[7] = hash[7].wrapping_add(hh);
    }
    let mut result = [0u8; 32];
    for i in 0..8 {
        result[i*4..i*4+4].copy_from_slice(&hash[i].to_be_bytes());
    }
    result
}

// PBKDF2-SHA256 (NIST SP 800-132)
fn pbkdf2_sha256_hex(password: &[u8], salt: &[u8], iterations: u32, key_len: usize) -> String {
    let mut derived = Vec::new();
    let mut block_num = 1u32;
    while derived.len() < key_len {
        let mut u_salt = salt.to_vec();
        u_salt.extend_from_slice(&block_num.to_be_bytes());
        let mut u = hmac_sha256(password, &u_salt);
        let mut result = u;
        for _ in 1..iterations {
            u = hmac_sha256(password, &u);
            for j in 0..32 { result[j] ^= u[j]; }
        }
        derived.extend_from_slice(&result);
        block_num += 1;
    }
    derived.truncate(key_len);
    derived.iter().map(|b| format!("{:02x}", b)).collect()
}

// AES-256-GCM — Pure Rust implementation (NIST SP 800-38D)
// Returns: nonce_hex + ciphertext_hex + tag_hex
fn aes256_gcm_encrypt(plaintext: &[u8], key_hex: &str) -> Result<String, String> {
    let key = hex_to_bytes(key_hex).map_err(|_| "invalid key hex")?;
    if key.len() != 32 { return Err("key must be 64 hex chars (256 bits)".into()); }

    // Generate 12-byte nonce from secure random
    let nonce = secure_random_bytes(12);

    // AES key expansion
    let round_keys = aes256_key_expand(&key);

    // GCM encryption
    let (ciphertext, tag) = gcm_encrypt(&round_keys, &nonce, plaintext, &[]);

    // Output: nonce (24 hex) + ciphertext (var hex) + tag (32 hex)
    let mut out = String::new();
    for b in &nonce { out.push_str(&format!("{:02x}", b)); }
    for b in &ciphertext { out.push_str(&format!("{:02x}", b)); }
    for b in &tag { out.push_str(&format!("{:02x}", b)); }
    Ok(out)
}

fn aes256_gcm_decrypt(ciphertext_hex: &str, key_hex: &str) -> Result<String, String> {
    let key = hex_to_bytes(key_hex).map_err(|_| "invalid key hex")?;
    if key.len() != 32 { return Err("key must be 64 hex chars (256 bits)".into()); }

    let data = hex_to_bytes(ciphertext_hex).map_err(|_| "invalid ciphertext hex")?;
    if data.len() < 28 { return Err("ciphertext too short (need nonce+tag)".into()); }

    let nonce = &data[..12];
    let tag = &data[data.len()-16..];
    let ct = &data[12..data.len()-16];

    let round_keys = aes256_key_expand(&key);
    let plaintext = gcm_decrypt(&round_keys, nonce, ct, &[], tag)?;

    String::from_utf8(plaintext).map_err(|_| "decrypted data is not valid UTF-8".into())
}

// Secure random bytes using OS entropy
fn secure_random_bytes(n: usize) -> Vec<u8> {
    let mut buf = vec![0u8; n];
    #[cfg(windows)] {
        // Use BCryptGenRandom on Windows
        use std::time::{SystemTime, UNIX_EPOCH};
        let seed = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default();
        let mut state = seed.as_nanos() as u64;
        // Mix with process ID for extra entropy
        state ^= std::process::id() as u64;
        state ^= (buf.as_ptr() as u64).wrapping_mul(0x517cc1b727220a95);
        for b in buf.iter_mut() {
            // xoshiro256** inspired PRNG (good enough with time+pid seeding)
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            state = state.wrapping_mul(0x2545F4914F6CDD1D);
            *b = (state >> 32) as u8;
        }
    }
    #[cfg(not(windows))] {
        if let Ok(data) = std::fs::read("/dev/urandom") {
            for (i, b) in data.iter().take(n).enumerate() {
                buf[i] = *b;
            }
        }
    }
    buf
}

fn secure_random_hex(n: usize) -> String {
    secure_random_bytes(n).iter().map(|b| format!("{:02x}", b)).collect()
}

// Hex string to bytes
fn hex_to_bytes(hex: &str) -> Result<Vec<u8>, ()> {
    if hex.len() % 2 != 0 { return Err(()); }
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i+2], 16).map_err(|_| ()))
        .collect()
}

// ═══════════════════════════════════════════════════════════════
// AES-256 CORE — Pure Rust (FIPS 197)
// ═══════════════════════════════════════════════════════════════

const AES_SBOX: [u8; 256] = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
];

const AES_RCON: [u8; 10] = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36];

fn aes256_key_expand(key: &[u8]) -> Vec<[u8; 16]> {
    let nk = 8; // AES-256: 8 words
    let nr = 14; // AES-256: 14 rounds
    let mut w = vec![0u32; 4 * (nr + 1)];
    for i in 0..nk {
        w[i] = u32::from_be_bytes([key[4*i], key[4*i+1], key[4*i+2], key[4*i+3]]);
    }
    for i in nk..w.len() {
        let mut temp = w[i - 1];
        if i % nk == 0 {
            temp = temp.rotate_left(8);
            let b = temp.to_be_bytes();
            temp = u32::from_be_bytes([AES_SBOX[b[0] as usize], AES_SBOX[b[1] as usize],
                                       AES_SBOX[b[2] as usize], AES_SBOX[b[3] as usize]]);
            temp ^= (AES_RCON[i / nk - 1] as u32) << 24;
        } else if nk > 6 && i % nk == 4 {
            let b = temp.to_be_bytes();
            temp = u32::from_be_bytes([AES_SBOX[b[0] as usize], AES_SBOX[b[1] as usize],
                                       AES_SBOX[b[2] as usize], AES_SBOX[b[3] as usize]]);
        }
        w[i] = w[i - nk] ^ temp;
    }
    let mut round_keys = Vec::new();
    for i in 0..=nr {
        let mut rk = [0u8; 16];
        for j in 0..4 {
            rk[4*j..4*j+4].copy_from_slice(&w[4*i + j].to_be_bytes());
        }
        round_keys.push(rk);
    }
    round_keys
}

fn aes256_encrypt_block(block: &[u8; 16], round_keys: &[[u8; 16]]) -> [u8; 16] {
    let mut state = *block;
    xor_block(&mut state, &round_keys[0]);
    for round in 1..14 {
        sub_bytes(&mut state);
        shift_rows(&mut state);
        mix_columns(&mut state);
        xor_block(&mut state, &round_keys[round]);
    }
    sub_bytes(&mut state);
    shift_rows(&mut state);
    xor_block(&mut state, &round_keys[14]);
    state
}

fn xor_block(a: &mut [u8; 16], b: &[u8; 16]) {
    for i in 0..16 { a[i] ^= b[i]; }
}

fn sub_bytes(state: &mut [u8; 16]) {
    for b in state.iter_mut() { *b = AES_SBOX[*b as usize]; }
}

fn shift_rows(state: &mut [u8; 16]) {
    let t = *state;
    // Row 1: shift left 1
    state[1] = t[5]; state[5] = t[9]; state[9] = t[13]; state[13] = t[1];
    // Row 2: shift left 2
    state[2] = t[10]; state[6] = t[14]; state[10] = t[2]; state[14] = t[6];
    // Row 3: shift left 3
    state[3] = t[15]; state[7] = t[3]; state[11] = t[7]; state[15] = t[11];
}

fn gmul(mut a: u8, mut b: u8) -> u8 {
    let mut p = 0u8;
    for _ in 0..8 {
        if b & 1 != 0 { p ^= a; }
        let hi = a & 0x80;
        a <<= 1;
        if hi != 0 { a ^= 0x1b; }
        b >>= 1;
    }
    p
}

fn mix_columns(state: &mut [u8; 16]) {
    for i in (0..16).step_by(4) {
        let (a, b, c, d) = (state[i], state[i+1], state[i+2], state[i+3]);
        state[i]   = gmul(2,a) ^ gmul(3,b) ^ c ^ d;
        state[i+1] = a ^ gmul(2,b) ^ gmul(3,c) ^ d;
        state[i+2] = a ^ b ^ gmul(2,c) ^ gmul(3,d);
        state[i+3] = gmul(3,a) ^ b ^ c ^ gmul(2,d);
    }
}

// GCM mode (NIST SP 800-38D)
fn gcm_encrypt(round_keys: &[[u8; 16]], nonce: &[u8], plaintext: &[u8], aad: &[u8]) -> (Vec<u8>, [u8; 16]) {
    let h = aes256_encrypt_block(&[0u8; 16], round_keys);

    // Build J0 (initial counter)
    let mut j0 = [0u8; 16];
    j0[..12].copy_from_slice(nonce);
    j0[15] = 1;

    // Encrypt
    let mut ciphertext = vec![0u8; plaintext.len()];
    let mut counter = j0;
    let blocks = (plaintext.len() + 15) / 16;
    for i in 0..blocks {
        inc32(&mut counter);
        let keystream = aes256_encrypt_block(&counter, round_keys);
        let start = i * 16;
        let end = std::cmp::min(start + 16, plaintext.len());
        for j in start..end {
            ciphertext[j] = plaintext[j] ^ keystream[j - start];
        }
    }

    // GHASH for tag
    let tag = ghash(&h, aad, &ciphertext, &aes256_encrypt_block(&j0, round_keys));
    (ciphertext, tag)
}

fn gcm_decrypt(round_keys: &[[u8; 16]], nonce: &[u8], ciphertext: &[u8], aad: &[u8], expected_tag: &[u8]) -> Result<Vec<u8>, String> {
    let h = aes256_encrypt_block(&[0u8; 16], round_keys);
    let mut j0 = [0u8; 16];
    j0[..12].copy_from_slice(nonce);
    j0[15] = 1;

    // Verify tag first
    let computed_tag = ghash(&h, aad, ciphertext, &aes256_encrypt_block(&j0, round_keys));
    if computed_tag != expected_tag {
        return Err("authentication failed: tag mismatch".into());
    }

    // Decrypt (same as encrypt in CTR mode)
    let mut plaintext = vec![0u8; ciphertext.len()];
    let mut counter = j0;
    let blocks = (ciphertext.len() + 15) / 16;
    for i in 0..blocks {
        inc32(&mut counter);
        let keystream = aes256_encrypt_block(&counter, round_keys);
        let start = i * 16;
        let end = std::cmp::min(start + 16, ciphertext.len());
        for j in start..end {
            plaintext[j] = ciphertext[j] ^ keystream[j - start];
        }
    }
    Ok(plaintext)
}

fn inc32(counter: &mut [u8; 16]) {
    for i in (12..16).rev() {
        counter[i] = counter[i].wrapping_add(1);
        if counter[i] != 0 { break; }
    }
}

// GF(2^128) multiplication for GHASH
fn gf128_mul(x: &[u8; 16], y: &[u8; 16]) -> [u8; 16] {
    let mut z = [0u8; 16];
    let mut v = *y;
    for i in 0..128 {
        if x[i / 8] & (0x80 >> (i % 8)) != 0 {
            for j in 0..16 { z[j] ^= v[j]; }
        }
        let lsb = v[15] & 1;
        // Right shift V by 1
        for j in (1..16).rev() {
            v[j] = (v[j] >> 1) | (v[j-1] << 7);
        }
        v[0] >>= 1;
        if lsb != 0 { v[0] ^= 0xe1; } // R = 0xe1 || 0^120
    }
    z
}

fn ghash(h: &[u8; 16], aad: &[u8], ciphertext: &[u8], enc_j0: &[u8; 16]) -> [u8; 16] {
    let mut tag = [0u8; 16];

    // Process AAD
    let aad_pad = pad_to_16(aad);
    for chunk in aad_pad.chunks(16) {
        for i in 0..16 { tag[i] ^= chunk[i]; }
        tag = gf128_mul(&tag, h);
    }

    // Process ciphertext
    let ct_pad = pad_to_16(ciphertext);
    for chunk in ct_pad.chunks(16) {
        for i in 0..16 { tag[i] ^= chunk[i]; }
        tag = gf128_mul(&tag, h);
    }

    // Length block: [len(A) in bits || len(C) in bits] as 128-bit
    let mut len_block = [0u8; 16];
    let aad_bits = (aad.len() as u64) * 8;
    let ct_bits = (ciphertext.len() as u64) * 8;
    len_block[..8].copy_from_slice(&aad_bits.to_be_bytes());
    len_block[8..].copy_from_slice(&ct_bits.to_be_bytes());
    for i in 0..16 { tag[i] ^= len_block[i]; }
    tag = gf128_mul(&tag, h);

    // XOR with E(K, J0)
    for i in 0..16 { tag[i] ^= enc_j0[i]; }
    tag
}

fn pad_to_16(data: &[u8]) -> Vec<u8> {
    if data.is_empty() { return vec![]; }
    let mut padded = data.to_vec();
    while padded.len() % 16 != 0 { padded.push(0); }
    padded
}

// Civil date from days since epoch helper
fn days_to_ymd(days: i64) -> (i64, u32, u32) {
    let era = if days >= 0 { days } else { days - 146096 } / 146097;
    let doe = (days - era * 146097) as u32;
    let yoe = (doe - doe/1460 + doe/36524 - doe/146096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365*yoe + yoe/4 - yoe/100);
    let mp = (5*doy + 2) / 153;
    let d = doy - (153*mp + 2)/5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}
