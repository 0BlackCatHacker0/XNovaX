// NovaLang VM — tree-walking evaluator for NovaLang AST
// Executes parsed AST nodes with ternary-first semantics
// v1.3: Hot-reload support — file-watch + graceful restart

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use crate::parser::{Expr, Stmt, Op};
use crate::lexer;
use crate::builtins::{self, Value};

/// Control flow signals for break/continue/return
enum Signal {
    None,
    Return(Value),
    Break,
    Continue,
}

/// A user-defined function
#[derive(Debug, Clone)]
struct FnDef {
    params: Vec<String>,
    body: Vec<Stmt>,
}

/// A class definition (class3/extends3)
#[derive(Debug, Clone)]
struct ClassDef {
    name: String,
    parent: Option<String>,
    methods: HashMap<String, FnDef>,
    fields: Vec<(String, Expr)>, // let fields in class body
}

pub struct Runtime {
    /// Variable scope stack — each frame is a HashMap
    scopes: Vec<HashMap<String, Value>>,
    /// User-defined functions (global for now)
    functions: HashMap<String, FnDef>,
    /// Class definitions (class3)
    classes: HashMap<String, ClassDef>,
    /// HTTP server state (for tserve/troute/tstart)
    servers: HashMap<String, ServerDef>,
    /// Base directory for import3 resolution
    pub base_dir: String,
    /// import3 cache — prevents re-parsing the same file
    imported_files: HashSet<String>,
    /// Counter for generating unique lambda names
    lambda_counter: u64,
    /// Source file path for hot-reload (set by main.rs)
    pub source_file: Option<String>,
    /// Shutdown signal shared with HTTP server threads
    shutdown_flag: Arc<AtomicBool>,
    /// Skip tstart during reload re-parse (prevents recursive server bind)
    skip_tstart: bool,
}

impl Clone for Runtime {
    fn clone(&self) -> Self {
        Runtime {
            scopes: self.scopes.clone(),
            functions: self.functions.clone(),
            classes: self.classes.clone(),
            servers: HashMap::new(), // Don't clone server bindings
            base_dir: self.base_dir.clone(),
            imported_files: self.imported_files.clone(),
            lambda_counter: 0,
            source_file: self.source_file.clone(),
            shutdown_flag: self.shutdown_flag.clone(),
            skip_tstart: self.skip_tstart,
        }
    }
}

#[derive(Debug, Clone)]
struct ServerDef {
    port: u16,
    name: String,
    routes: Vec<(String, String, String)>, // (method, path, fn_name)
}

impl Runtime {
    pub fn new() -> Self {
        let mut global = HashMap::new();
        // Pre-load harmonic constants
        global.insert("H3".into(), Value::Int(builtins::H3));
        global.insert("H5".into(), Value::Int(builtins::H5));
        global.insert("H7".into(), Value::Int(builtins::H7));
        global.insert("H13".into(), Value::Int(builtins::H13));
        global.insert("BLOCK".into(), Value::Int(builtins::BLOCK_SIZE));
        global.insert("TRUE".into(), Value::Trit(1));
        global.insert("FALSE_".into(), Value::Trit(-1));
        global.insert("MAYBE".into(), Value::Trit(0));
        global.insert("T_TRUE".into(), Value::Trit(1));
        global.insert("T_FALSE".into(), Value::Trit(-1));
        global.insert("T_MAYBE".into(), Value::Trit(0));

        Runtime {
            scopes: vec![global],
            functions: HashMap::new(),
            classes: HashMap::new(),
            servers: HashMap::new(),
            base_dir: String::new(),
            imported_files: HashSet::new(),
            lambda_counter: 0,
            source_file: None,
            shutdown_flag: Arc::new(AtomicBool::new(false)),
            skip_tstart: false,
        }
    }

    pub fn execute(&mut self, stmts: &[Stmt]) -> Result<(), String> {
        for stmt in stmts {
            match self.exec_stmt(stmt)? {
                Signal::Return(_) => return Ok(()),
                Signal::Break | Signal::Continue => {
                    return Err("break3/continue3 outside loop".into());
                }
                Signal::None => {}
            }
        }
        Ok(())
    }

    fn exec_stmt(&mut self, stmt: &Stmt) -> Result<Signal, String> {
        match stmt {
            Stmt::Let(name, expr) => {
                let val = self.eval_expr(expr)?;
                // Bug 2 fix: if the variable already exists in any enclosing scope,
                // update it there instead of creating a new local that shadows it.
                // This ensures `let x = expr` inside for3/if3/while3/try3 blocks
                // modifies the enclosing scope's variable, not creates an invisible local.
                // In function scope (top of stack), set_var and update_var behave the same.
                let exists_in_scope = self.scopes.iter().rev().any(|s| s.contains_key(name.as_str()));
                if exists_in_scope {
                    self.update_var(name, val);
                } else {
                    self.set_var(name.clone(), val);
                }
                Ok(Signal::None)
            }
            Stmt::Assign(name, expr) => {
                let val = self.eval_expr(expr)?;
                self.update_var(name, val);
                Ok(Signal::None)
            }
            Stmt::CompoundAssign(name, op, expr) => {
                let current = self.get_var(name);
                let rhs = self.eval_expr(expr)?;
                let result = self.apply_binop(op, &current, &rhs);
                self.update_var(name, result);
                Ok(Signal::None)
            }
            Stmt::DotAssign(obj_name, field, expr) => {
                let val = self.eval_expr(expr)?;
                let obj = self.get_var(obj_name);
                if let Value::Dict(mut pairs) = obj {
                    if let Some(existing) = pairs.iter_mut().find(|(k, _)| k == field) {
                        existing.1 = val;
                    } else {
                        pairs.push((field.clone(), val));
                    }
                    self.update_var(obj_name, Value::Dict(pairs));
                }
                Ok(Signal::None)
            }
            Stmt::IndexAssign(name, index_expr, val_expr) => {
                let idx = self.eval_expr(index_expr)?;
                let val = self.eval_expr(val_expr)?;
                let obj = self.get_var(name);
                match obj {
                    Value::List(mut items) => {
                        let i = idx.to_int() as usize;
                        if i < items.len() {
                            items[i] = val;
                            self.update_var(name, Value::List(items));
                        }
                    }
                    Value::Dict(mut pairs) => {
                        let key = idx.to_display();
                        if let Some(existing) = pairs.iter_mut().find(|(k, _)| k == &key) {
                            existing.1 = val;
                        } else {
                            pairs.push((key, val));
                        }
                        self.update_var(name, Value::Dict(pairs));
                    }
                    _ => {}
                }
                Ok(Signal::None)
            }
            Stmt::Return(expr) => {
                let val = if let Some(e) = expr {
                    self.eval_expr(e)?
                } else {
                    Value::Null
                };
                Ok(Signal::Return(val))
            }
            Stmt::Print(exprs) => {
                let parts: Result<Vec<String>, String> = exprs.iter()
                    .map(|e| self.eval_expr(e).map(|v| v.to_display()))
                    .collect();
                println!("{}", parts?.join(" "));
                Ok(Signal::None)
            }
            Stmt::Expr(expr) => {
                self.eval_expr(expr)?;
                Ok(Signal::None)
            }
            Stmt::FnDef(name, params, body) => {
                self.functions.insert(name.clone(), FnDef {
                    params: params.clone(),
                    body: body.clone(),
                });
                Ok(Signal::None)
            }
            Stmt::If3(cond, then_body, elif_branches, maybe_body, else_body) => {
                let val = self.eval_expr(cond)?;

                if maybe_body.is_some() {
                    // Ternary branching: TRUE (+1/positive) → then, MAYBE (0/null) → maybe, FALSE (-1/negative) → else
                    let trit = match &val {
                        Value::Trit(t) => *t,
                        Value::Int(n) => if *n > 0 { 1 } else if *n == 0 { 0 } else { -1 },
                        Value::Float(f) => if *f > 0.0 { 1 } else if *f == 0.0 { 0 } else { -1 },
                        Value::Bool(b) => if *b { 1 } else { -1 },
                        Value::Null => 0,
                        Value::Str(s) => if s.is_empty() { 0 } else { 1 },
                        Value::List(l) => if l.is_empty() { 0 } else { 1 },
                        _ => if val.is_truthy() { 1 } else { -1 },
                    };
                    if trit > 0 {
                        return self.exec_block(then_body);
                    }
                    // Check elif branches
                    for (elif_cond, elif_body) in elif_branches {
                        let v = self.eval_expr(elif_cond)?;
                        if v.is_truthy() {
                            return self.exec_block(elif_body);
                        }
                    }
                    if trit == 0 {
                        if let Some(mb) = maybe_body {
                            return self.exec_block(mb);
                        }
                    }
                    if let Some(eb) = else_body {
                        return self.exec_block(eb);
                    }
                } else {
                    // Binary branching (no maybe branch): truthy/falsy
                    if val.is_truthy() {
                        return self.exec_block(then_body);
                    }
                    for (elif_cond, elif_body) in elif_branches {
                        let v = self.eval_expr(elif_cond)?;
                        if v.is_truthy() {
                            return self.exec_block(elif_body);
                        }
                    }
                    if let Some(eb) = else_body {
                        return self.exec_block(eb);
                    }
                }
                Ok(Signal::None)
            }
            Stmt::For3(var, iter_expr, body) => {
                let iter_val = self.eval_expr(iter_expr)?;
                let items = match iter_val {
                    Value::List(items) => items,
                    Value::Str(s) => s.chars().map(|c| Value::Str(c.to_string())).collect(),
                    Value::Dict(pairs) => pairs.into_iter()
                        .map(|(k, _)| Value::Str(k))
                        .collect(),
                    _ => vec![],
                };
                for item in items {
                    self.set_var(var.clone(), item);
                    match self.exec_block(body)? {
                        Signal::Break => break,
                        Signal::Continue => continue,
                        Signal::Return(v) => return Ok(Signal::Return(v)),
                        Signal::None => {}
                    }
                }
                Ok(Signal::None)
            }
            Stmt::While3(cond, body) => {
                loop {
                    let val = self.eval_expr(cond)?;
                    if !val.is_truthy() { break; }
                    match self.exec_block(body)? {
                        Signal::Break => break,
                        Signal::Continue => continue,
                        Signal::Return(v) => return Ok(Signal::Return(v)),
                        Signal::None => {}
                    }
                }
                Ok(Signal::None)
            }
            Stmt::Try3(try_body, err_var, fail_body) => {
                // Execute try body, catch errors and run fail body
                match self.exec_block(try_body) {
                    Ok(sig) => Ok(sig),
                    Err(e) => {
                        // If error variable specified, bind the error message
                        if let Some(var_name) = err_var {
                            self.set_var(var_name.clone(), Value::Str(e));
                        }
                        self.exec_block(fail_body)
                    }
                }
            }
            Stmt::Match3(expr, arms) => {
                let val = self.eval_expr(expr)?;
                let trit = val.to_trit();
                for (arm_trit, arm_body) in arms {
                    if *arm_trit == trit {
                        return self.exec_block(arm_body);
                    }
                }
                Ok(Signal::None)
            }
            Stmt::Break3 => Ok(Signal::Break),
            Stmt::Continue3 => Ok(Signal::Continue),
            Stmt::Block(stmts) => self.exec_block(stmts),
            Stmt::Class3(name, parent, body) => {
                let mut methods = HashMap::new();
                let mut fields = Vec::new();
                // If parent exists, inherit its methods first
                if let Some(parent_name) = parent {
                    if let Some(parent_class) = self.classes.get(parent_name).cloned() {
                        for (k, v) in &parent_class.methods {
                            methods.insert(k.clone(), v.clone());
                        }
                        fields.extend(parent_class.fields.clone());
                    }
                }
                // Process class body
                for stmt in body {
                    match stmt {
                        Stmt::FnDef(fname, params, fbody) => {
                            methods.insert(fname.clone(), FnDef {
                                params: params.clone(),
                                body: fbody.clone(),
                            });
                            // Also register as ClassName_method for backwards compat
                            let global_name = format!("{}_{}", name, fname);
                            self.functions.insert(global_name, FnDef {
                                params: params.clone(),
                                body: fbody.clone(),
                            });
                        }
                        Stmt::Let(fname, expr) => {
                            fields.push((fname.clone(), expr.clone()));
                        }
                        _ => {
                            // Execute other statements (e.g. prints) at class definition time
                            let _ = self.exec_stmt(stmt);
                        }
                    }
                }
                self.classes.insert(name.clone(), ClassDef {
                    name: name.clone(),
                    parent: parent.clone(),
                    methods,
                    fields,
                });
                Ok(Signal::None)
            }
            Stmt::Import3(path) => {
                // Resolve path relative to base_dir
                let full_path = if path.contains(':') || path.starts_with('/') || path.starts_with('\\') {
                    path.clone()
                } else if !self.base_dir.is_empty() {
                    format!("{}\\{}", self.base_dir, path)
                } else {
                    path.clone()
                };
                // import3 cache — skip if already imported
                if !self.imported_files.contains(&full_path) {
                    match std::fs::read_to_string(&full_path) {
                        Ok(code) => {
                            self.imported_files.insert(full_path.clone());
                            let tokens = crate::lexer::tokenize(&code);
                            let ast = crate::parser::parse(tokens);
                            self.execute(&ast)?;
                        }
                        Err(e) => {
                            eprintln!("[warn] import3 failed: {}: {}", full_path, e);
                        }
                    }
                }
                Ok(Signal::None)
            }
        }
    }

    fn exec_block(&mut self, stmts: &[Stmt]) -> Result<Signal, String> {
        for stmt in stmts {
            match self.exec_stmt(stmt)? {
                Signal::None => {}
                other => return Ok(other),
            }
        }
        Ok(Signal::None)
    }

    // ── Expression Evaluation ──

    fn eval_expr(&mut self, expr: &Expr) -> Result<Value, String> {
        match expr {
            Expr::Int(v) => Ok(Value::Int(*v)),
            Expr::Float(v) => Ok(Value::Float(*v)),
            Expr::Str(s) => Ok(Value::Str(s.clone())),
            Expr::Bool(b) => Ok(Value::Bool(*b)),
            Expr::Null => Ok(Value::Null),
            Expr::Trit(t) => Ok(Value::Trit(*t)),
            Expr::Ident(name) => {
                let v = self.get_var(name);
                // If variable not found, check if it's a function name
                // (allows passing fn names as values, e.g. to troute)
                if matches!(v, Value::Null) && self.functions.contains_key(name.as_str()) {
                    Ok(Value::Str(name.clone()))
                } else {
                    Ok(v)
                }
            }

            Expr::BinOp(left, Op::Pipe, right) => {
                let lv = self.eval_expr(left)?;
                // Pipe: lv |> f  becomes f(lv)
                // Pipe: lv |> f(a, b) becomes f(lv, a, b)
                match right.as_ref() {
                    Expr::Ident(fname) => {
                        self.call_fn(fname, vec![lv])
                    }
                    Expr::Call(fname, args) => {
                        let mut eval_args = vec![lv];
                        for a in args {
                            eval_args.push(self.eval_expr(a)?);
                        }
                        self.call_fn(fname, eval_args)
                    }
                    _ => {
                        // Fallback: evaluate right side and try to call it
                        let rv = self.eval_expr(right)?;
                        if let Value::Fn(fname) = rv {
                            self.call_fn(&fname, vec![lv])
                        } else {
                            Ok(lv)
                        }
                    }
                }
            }

            Expr::BinOp(left, op, right) => {
                let lv = self.eval_expr(left)?;
                // Short-circuit for And/Or
                match op {
                    Op::And => {
                        if !lv.is_truthy() { return Ok(lv); }
                        return self.eval_expr(right);
                    }
                    Op::Or => {
                        if lv.is_truthy() { return Ok(lv); }
                        return self.eval_expr(right);
                    }
                    _ => {}
                }
                let rv = self.eval_expr(right)?;
                Ok(self.apply_binop(op, &lv, &rv))
            }

            Expr::UnaryOp(Op::Not, inner) => {
                let val = self.eval_expr(inner)?;
                Ok(Value::Trit(if val.is_truthy() { -1 } else { 1 }))
            }
            Expr::UnaryOp(_, inner) => self.eval_expr(inner),

            Expr::Call(name, args) => {
                let mut eval_args = Vec::new();
                for a in args {
                    eval_args.push(self.eval_expr(a)?);
                }
                self.call_fn(name, eval_args)
            }

            Expr::MethodCall(obj_expr, method, args) => {
                let obj = self.eval_expr(obj_expr)?;
                // Check if this is a class instance method call
                if let Value::Dict(ref pairs) = obj {
                    if let Some((_, Value::Str(class_name))) = pairs.iter().find(|(k, _)| k == "__class__") {
                        let class_name = class_name.clone();
                        // Look up method in class hierarchy
                        if let Some(class_method) = self.find_class_method(&class_name, method) {
                            let mut eval_args = Vec::new();
                            for a in args {
                                eval_args.push(self.eval_expr(a)?);
                            }
                            // Push scope with self bound to instance
                            let mut frame = HashMap::new();
                            frame.insert("self".into(), obj.clone());
                            let param_start = if class_method.params.first().map(|p| p.as_str()) == Some("self") { 1 } else { 0 };
                            for (i, param) in class_method.params[param_start..].iter().enumerate() {
                                frame.insert(param.clone(), eval_args.get(i).cloned().unwrap_or(Value::Null));
                            }
                            self.scopes.push(frame);
                            let mut result = Value::Null;
                            for stmt in &class_method.body {
                                match self.exec_stmt(stmt)? {
                                    Signal::Return(v) => { result = v; break; }
                                    Signal::Break | Signal::Continue => break,
                                    Signal::None => {}
                                }
                            }
                            self.scopes.pop();
                            return Ok(result);
                        }
                    }
                }

                let mut all_args = vec![obj];
                for a in args {
                    all_args.push(self.eval_expr(a)?);
                }
                // Try builtin first
                if let Some(result) = builtins::call_builtin(method, &all_args) {
                    return Ok(result);
                }
                // Common methods as fallback
                match method.as_str() {
                    "get" => {
                        if let Value::Dict(pairs) = &all_args[0] {
                            let key = all_args.get(1).unwrap_or(&Value::Null).to_display();
                            let default = all_args.get(2).cloned().unwrap_or(Value::Null);
                            let found = pairs.iter().find(|(k, _)| k == &key).map(|(_, v)| v.clone());
                            Ok(found.unwrap_or(default))
                        } else {
                            Ok(Value::Null)
                        }
                    }
                    "keys" => {
                        if let Value::Dict(pairs) = &all_args[0] {
                            Ok(Value::List(pairs.iter().map(|(k, _)| Value::Str(k.clone())).collect()))
                        } else { Ok(Value::List(vec![])) }
                    }
                    "values" => {
                        if let Value::Dict(pairs) = &all_args[0] {
                            Ok(Value::List(pairs.iter().map(|(_, v)| v.clone()).collect()))
                        } else { Ok(Value::List(vec![])) }
                    }
                    "items" => {
                        if let Value::Dict(pairs) = &all_args[0] {
                            Ok(Value::List(pairs.iter()
                                .map(|(k, v)| Value::List(vec![Value::Str(k.clone()), v.clone()]))
                                .collect()))
                        } else { Ok(Value::List(vec![])) }
                    }
                    "append" | "push" => {
                        if let Value::List(mut items) = all_args[0].clone() {
                            if let Some(val) = all_args.get(1) {
                                items.push(val.clone());
                            }
                            Ok(Value::List(items))
                        } else { Ok(Value::Null) }
                    }
                    "format" => {
                        // str.format(...) — simple {} replacement
                        if let Value::Str(template) = &all_args[0] {
                            let mut result = template.clone();
                            for (i, arg) in all_args[1..].iter().enumerate() {
                                let placeholder = format!("{{{}}}", i);
                                result = result.replace(&placeholder, &arg.to_display());
                                // Also replace bare {} in order
                                if result.contains("{}") {
                                    result = result.replacen("{}", &arg.to_display(), 1);
                                }
                            }
                            Ok(Value::Str(result))
                        } else { Ok(Value::Null) }
                    }
                    _ => Ok(Value::Null),
                }
            }

            Expr::Index(obj_expr, idx_expr) => {
                let obj = self.eval_expr(obj_expr)?;
                let idx = self.eval_expr(idx_expr)?;
                match obj {
                    Value::List(items) => {
                        let i = idx.to_int();
                        let i = if i < 0 { (items.len() as i64 + i) as usize } else { i as usize };
                        Ok(items.get(i).cloned().unwrap_or(Value::Null))
                    }
                    Value::Dict(pairs) => {
                        let key = idx.to_display();
                        Ok(pairs.iter().find(|(k, _)| k == &key)
                            .map(|(_, v)| v.clone())
                            .unwrap_or(Value::Null))
                    }
                    Value::Str(s) => {
                        let i = idx.to_int() as usize;
                        Ok(s.chars().nth(i).map(|c| Value::Str(c.to_string()))
                            .unwrap_or(Value::Null))
                    }
                    _ => Ok(Value::Null),
                }
            }

            Expr::DotAccess(obj_expr, field) => {
                let obj = self.eval_expr(obj_expr)?;
                match &obj {
                    Value::Dict(pairs) => {
                        Ok(pairs.iter().find(|(k, _)| k == field)
                            .map(|(_, v)| v.clone())
                            .unwrap_or(Value::Null))
                    }
                    Value::Str(s) => {
                        match field.as_str() {
                            "length" => Ok(Value::Int(s.len() as i64)),
                            _ => Ok(Value::Null),
                        }
                    }
                    Value::List(items) => {
                        match field.as_str() {
                            "length" => Ok(Value::Int(items.len() as i64)),
                            _ => Ok(Value::Null),
                        }
                    }
                    _ => Ok(Value::Null),
                }
            }

            Expr::List(items) => {
                let mut vals = Vec::new();
                for item in items {
                    // Spread: ...expr unpacks list into parent list
                    if let Expr::Spread(inner) = item {
                        let v = self.eval_expr(inner)?;
                        if let Value::List(inner_items) = v {
                            vals.extend(inner_items);
                        } else {
                            vals.push(v);
                        }
                    } else {
                        vals.push(self.eval_expr(item)?);
                    }
                }
                Ok(Value::List(vals))
            }

            Expr::Dict(pairs) => {
                let mut result = Vec::new();
                for (key, val) in pairs {
                    let k = self.eval_expr(key)?;
                    // Spread: {...other_dict} merges entries
                    if k.to_display() == "__spread__" {
                        let v = self.eval_expr(val)?;
                        if let Value::Dict(spread_pairs) = v {
                            result.extend(spread_pairs);
                        }
                    } else {
                        let v = self.eval_expr(val)?;
                        result.push((k.to_display(), v));
                    }
                }
                Ok(Value::Dict(result))
            }

            Expr::Lambda(params, body) => {
                self.lambda_counter += 1;
                let name = format!("__lambda_{}", self.lambda_counter);
                self.functions.insert(name.clone(), FnDef {
                    params: params.clone(),
                    body: body.clone(),
                });
                Ok(Value::Fn(name))
            }

            // Range: start..end → generates list [start, start+1, ..., end-1]
            Expr::Range(start, end) => {
                let s = self.eval_expr(start)?.to_int();
                let e = self.eval_expr(end)?.to_int();
                let items: Vec<Value> = if s <= e {
                    (s..e).map(|i| Value::Int(i)).collect()
                } else {
                    (e..s).rev().map(|i| Value::Int(i)).collect()
                };
                Ok(Value::List(items))
            }

            // Spread: ...expr → evaluates to the inner value (flattened in List/Dict context)
            Expr::Spread(inner) => {
                self.eval_expr(inner)
            }

            Expr::New3(class_name, args) => {
                let class = self.classes.get(class_name).cloned()
                    .ok_or_else(|| format!("Unknown class: {}", class_name))?;
                // Create instance dict with __class__ marker
                let mut instance_pairs: Vec<(String, Value)> = vec![
                    ("__class__".into(), Value::Str(class_name.clone())),
                ];
                // Initialize fields from class definition
                for (fname, fexpr) in &class.fields {
                    let val = self.eval_expr(fexpr)?;
                    instance_pairs.push((fname.clone(), val));
                }
                let mut instance = Value::Dict(instance_pairs);
                // Call init if it exists
                if let Some(init_fn) = class.methods.get("init") {
                    let mut eval_args = Vec::new();
                    for a in args {
                        eval_args.push(self.eval_expr(a)?);
                    }
                    // Push scope with self bound to instance
                    let mut frame = HashMap::new();
                    frame.insert("self".into(), instance.clone());
                    // Bind params (skip first param which is 'self')
                    let param_start = if init_fn.params.first().map(|p| p.as_str()) == Some("self") { 1 } else { 0 };
                    for (i, param) in init_fn.params[param_start..].iter().enumerate() {
                        frame.insert(param.clone(), eval_args.get(i).cloned().unwrap_or(Value::Null));
                    }
                    self.scopes.push(frame);
                    for stmt in &init_fn.body {
                        match self.exec_stmt(stmt)? {
                            Signal::Return(_) => break,
                            Signal::Break | Signal::Continue => break,
                            Signal::None => {}
                        }
                    }
                    // Get the modified self from scope
                    instance = self.get_var("self");
                    self.scopes.pop();
                }
                Ok(instance)
            }
        }
    }

    // ── Function Calls ──

    fn call_fn(&mut self, name: &str, args: Vec<Value>) -> Result<Value, String> {
        // Check builtins first
        if let Some(result) = builtins::call_builtin(name, &args) {
            return Ok(result);
        }

        // Special built-in calls
        match name {
            "print" => {
                let parts: Vec<String> = args.iter().map(|v| v.to_display()).collect();
                println!("{}", parts.join(" "));
                return Ok(Value::Null);
            }
            "tserve" => {
                let port = args.first().unwrap_or(&Value::Int(8080)).to_int() as u16;
                let sname = args.get(1).map(|v| v.to_display()).unwrap_or_else(|| "server".into());
                let id = format!("server_{}", port);
                self.servers.insert(id.clone(), ServerDef {
                    port,
                    name: sname,
                    routes: Vec::new(),
                });
                return Ok(Value::Str(id));
            }
            "troute" => {
                let server_id = args.first().unwrap_or(&Value::Null).to_display();
                let method = args.get(1).unwrap_or(&Value::Null).to_display();
                let path = args.get(2).unwrap_or(&Value::Null).to_display();
                let handler = args.get(3).unwrap_or(&Value::Null).to_display();
                if let Some(server) = self.servers.get_mut(&server_id) {
                    server.routes.push((method, path, handler));
                }
                return Ok(Value::Trit(1));
            }
            "tstart" => {
                // During hot-reload re-parse, skip tstart to avoid recursive bind
                if self.skip_tstart {
                    return Ok(Value::Trit(1));
                }
                let server_id = args.first().unwrap_or(&Value::Null).to_display();
                if let Some(server) = self.servers.get(&server_id).cloned() {
                    return self.start_http_server(server);
                }
                return Err(format!("Unknown server: {}", server_id));
            }
            "typeof" | "type" => {
                return Ok(builtins::call_builtin("type", &args).unwrap_or(Value::Null));
            }
            _ => {}
        }

        // Check if name is a variable holding a function reference (e.g. lambda)
        if !self.functions.contains_key(name) {
            let val = self.get_var(name);
            if let Value::Fn(actual_name) = val {
                if let Some(fndef) = self.functions.get(&actual_name).cloned() {
                    let mut frame = HashMap::new();
                    for (i, param) in fndef.params.iter().enumerate() {
                        frame.insert(param.clone(), args.get(i).cloned().unwrap_or(Value::Null));
                    }
                    self.scopes.push(frame);
                    let mut result = Value::Null;
                    for stmt in &fndef.body {
                        match self.exec_stmt(stmt)? {
                            Signal::Return(v) => { result = v; break; }
                            Signal::Break | Signal::Continue => break,
                            Signal::None => {}
                        }
                    }
                    self.scopes.pop();
                    return Ok(result);
                }
            }
        }

        // User-defined function
        if let Some(fndef) = self.functions.get(name).cloned() {
            // Push new scope
            let mut frame = HashMap::new();
            for (i, param) in fndef.params.iter().enumerate() {
                frame.insert(param.clone(), args.get(i).cloned().unwrap_or(Value::Null));
            }
            self.scopes.push(frame);

            let mut result = Value::Null;
            for stmt in &fndef.body {
                match self.exec_stmt(stmt)? {
                    Signal::Return(v) => { result = v; break; }
                    Signal::Break | Signal::Continue => break,
                    Signal::None => {}
                }
            }

            self.scopes.pop();
            return Ok(result);
        }

        // Unknown function — return null instead of error (lenient mode)
        eprintln!("[warn] Unknown function: {}()", name);
        Ok(Value::Null)
    }

    // ── Binary Operations ──

    fn apply_binop(&self, op: &Op, lv: &Value, rv: &Value) -> Value {
        // Bug 3 fix: auto-coerce Trit to Int for arithmetic contexts.
        // When a Trit participates in math or string concatenation with numbers,
        // treat it as its integer value (1/0/-1) rather than a trit label.
        let lv_coerced;
        let rv_coerced;
        let lv = match (op, lv) {
            (Op::Add | Op::Sub | Op::Mul | Op::Div | Op::Mod, Value::Trit(t)) => {
                lv_coerced = Value::Int(*t as i64);
                &lv_coerced
            }
            _ => lv,
        };
        let rv = match (op, rv) {
            (Op::Add | Op::Sub | Op::Mul | Op::Div | Op::Mod, Value::Trit(t)) => {
                rv_coerced = Value::Int(*t as i64);
                &rv_coerced
            }
            _ => rv,
        };
        match op {
            Op::Add => {
                // String concatenation
                if matches!(lv, Value::Str(_)) || matches!(rv, Value::Str(_)) {
                    return Value::Str(format!("{}{}", lv.to_display(), rv.to_display()));
                }
                // Float if either is float
                if matches!(lv, Value::Float(_)) || matches!(rv, Value::Float(_)) {
                    return Value::Float(lv.to_float() + rv.to_float());
                }
                Value::Int(lv.to_int() + rv.to_int())
            }
            Op::Sub => {
                if matches!(lv, Value::Float(_)) || matches!(rv, Value::Float(_)) {
                    Value::Float(lv.to_float() - rv.to_float())
                } else {
                    Value::Int(lv.to_int() - rv.to_int())
                }
            }
            Op::Mul => {
                // String repetition: "abc" * 3
                if let Value::Str(s) = lv {
                    return Value::Str(s.repeat(rv.to_int().max(0) as usize));
                }
                if matches!(lv, Value::Float(_)) || matches!(rv, Value::Float(_)) {
                    Value::Float(lv.to_float() * rv.to_float())
                } else {
                    Value::Int(lv.to_int() * rv.to_int())
                }
            }
            Op::Div => {
                let r = rv.to_float();
                if r == 0.0 { return Value::Null; }
                Value::Float(lv.to_float() / r)
            }
            Op::Mod => {
                let r = rv.to_int();
                if r == 0 { return Value::Null; }
                Value::Int(lv.to_int() % r)
            }
            Op::Eq => Value::Trit(if lv == rv { 1 } else { -1 }),
            Op::NotEq => Value::Trit(if lv != rv { 1 } else { -1 }),
            Op::Lt => Value::Trit(if lv.to_float() < rv.to_float() { 1 } else { -1 }),
            Op::Gt => Value::Trit(if lv.to_float() > rv.to_float() { 1 } else { -1 }),
            Op::LtEq => Value::Trit(if lv.to_float() <= rv.to_float() { 1 } else { -1 }),
            Op::GtEq => Value::Trit(if lv.to_float() >= rv.to_float() { 1 } else { -1 }),
            Op::And => {
                if lv.is_truthy() { rv.clone() } else { lv.clone() }
            }
            Op::Or => {
                if lv.is_truthy() { lv.clone() } else { rv.clone() }
            }
            Op::Not => Value::Trit(if lv.is_truthy() { -1 } else { 1 }),
            Op::Pipe => lv.clone(), // Pipe is handled in eval_expr; fallback returns left value
            Op::NullCoalesce => {
                // x ?? default → returns x if non-null, else default
                if matches!(lv, Value::Null) { rv.clone() } else { lv.clone() }
            }
            Op::In => {
                // x in list/dict → membership test
                match rv {
                    Value::List(items) => {
                        Value::Trit(if items.iter().any(|item| item == lv) { 1 } else { -1 })
                    }
                    Value::Dict(pairs) => {
                        let key = lv.to_display();
                        Value::Trit(if pairs.iter().any(|(k, _)| k == &key) { 1 } else { -1 })
                    }
                    Value::Str(s) => {
                        let needle = lv.to_display();
                        Value::Trit(if s.contains(&needle) { 1 } else { -1 })
                    }
                    _ => Value::Trit(-1),
                }
            }
        }
    }

    // ── Variable Scope ──

    fn get_var(&self, name: &str) -> Value {
        // Walk scope stack from top to bottom
        for scope in self.scopes.iter().rev() {
            if let Some(val) = scope.get(name) {
                return val.clone();
            }
        }
        Value::Null
    }

    fn set_var(&mut self, name: String, val: Value) {
        if let Some(scope) = self.scopes.last_mut() {
            scope.insert(name, val);
        }
    }

    fn update_var(&mut self, name: &str, val: Value) {
        // Find the scope that has this var and update it
        for scope in self.scopes.iter_mut().rev() {
            if scope.contains_key(name) {
                scope.insert(name.to_string(), val);
                return;
            }
        }
        // If not found, set in current scope
        self.set_var(name.to_string(), val);
    }

    // ── Class Method Lookup (walks inheritance chain) ──

    fn find_class_method(&self, class_name: &str, method_name: &str) -> Option<FnDef> {
        let class = self.classes.get(class_name)?;
        if let Some(m) = class.methods.get(method_name) {
            return Some(m.clone());
        }
        // Walk parent chain
        if let Some(ref parent) = class.parent {
            return self.find_class_method(parent, method_name);
        }
        None
    }

    // ── HTTP Server (tiny_http) ──

    fn start_http_server(&mut self, mut server: ServerDef) -> Result<Value, String> {
        let source_file = self.source_file.clone();
        let base_dir = self.base_dir.clone();

        // Outer reload loop: re-bind and re-parse on file changes
        loop {
            let addr = format!("0.0.0.0:{}", server.port);
            println!("[NovaLang] Starting {} on port {}", server.name, server.port);

            let http_server = tiny_http::Server::http(&addr)
                .map_err(|e| format!("Failed to bind {}: {}", addr, e))?;

            println!("[NovaLang] {} listening on http://127.0.0.1:{}", server.name, server.port);

            // Build route lookup (shared across threads)
            let routes: Arc<HashMap<(String, String), String>> = Arc::new(
                server.routes.iter()
                    .map(|(m, p, h)| ((m.clone(), p.clone()), h.clone()))
                    .collect()
            );

            // Thread pool size: H7=7 concurrent handlers
            let pool_size = 7;
            let http_server = Arc::new(http_server);

            // Shutdown signal for this server generation
            let shutdown = Arc::new(AtomicBool::new(false));

            // Snapshot the VM state for handler threads
            let vm_snapshot = self.clone();
            let vm_arc = Arc::new(std::sync::Mutex::new(vm_snapshot));

            // ── File-watcher thread: monitors .nova source for changes ──
            let watcher_shutdown = shutdown.clone();
            let watcher_server = http_server.clone();
            let watcher_source = source_file.clone();
            let watcher_handle = std::thread::spawn(move || {
                let path = match &watcher_source {
                    Some(p) => p.clone(),
                    None => return, // No source file, no watching
                };
                // Record initial mtime
                let initial_mtime = match std::fs::metadata(&path) {
                    Ok(m) => m.modified().unwrap_or(std::time::SystemTime::UNIX_EPOCH),
                    Err(_) => return,
                };
                let mut last_mtime = initial_mtime;

                // Poll every 1 second (lightweight, no external deps)
                loop {
                    std::thread::sleep(std::time::Duration::from_secs(1));
                    if watcher_shutdown.load(Ordering::Relaxed) {
                        break;
                    }
                    match std::fs::metadata(&path) {
                        Ok(m) => {
                            if let Ok(mtime) = m.modified() {
                                if mtime != last_mtime {
                                    last_mtime = mtime;
                                    println!("[NovaLang] File change detected: {}", path);
                                    println!("[NovaLang] Hot-reloading...");
                                    // Signal shutdown to all worker threads
                                    watcher_shutdown.store(true, Ordering::SeqCst);
                                    // Unblock all workers waiting on recv_timeout
                                    // unblock() wakes one thread per call, so call it pool_size times
                                    for _ in 0..7 {
                                        watcher_server.unblock();
                                    }
                                    break;
                                }
                            }
                        }
                        Err(_) => {} // File temporarily unavailable during save
                    }
                }
            });

            // Spawn worker threads
            let mut handles = Vec::new();
            for _worker_id in 0..pool_size {
                let server_ref = http_server.clone();
                let routes_ref = routes.clone();
                let vm_ref = vm_arc.clone();
                let worker_shutdown = shutdown.clone();

                let handle = std::thread::spawn(move || {
                    loop {
                        // Check shutdown before blocking on recv
                        if worker_shutdown.load(Ordering::Relaxed) {
                            break;
                        }

                        let mut request = match server_ref.recv_timeout(std::time::Duration::from_secs(1)) {
                            Ok(Some(r)) => r,
                            Ok(None) => continue,  // Timeout, loop back to check shutdown
                            Err(_) => break,        // Server unblocked/dropped
                        };

                        // Double-check shutdown after waking up
                        if worker_shutdown.load(Ordering::Relaxed) {
                            // Respond 503 to in-flight request during shutdown
                            let resp = tiny_http::Response::from_string(
                                "{\"error\":\"service reloading\",\"trit\":0}"
                            ).with_status_code(503)
                             .with_header(tiny_http::Header::from_bytes(
                                 &b"Content-Type"[..], &b"application/json"[..]).unwrap());
                            let _ = request.respond(resp);
                            break;
                        }

                        let method = request.method().to_string();
                        let path = request.url().to_string();
                        let path_only = path.split('?').next().unwrap_or(&path).to_string();

                        // CORS preflight
                        if method == "OPTIONS" {
                            let response = tiny_http::Response::from_string("")
                                .with_header(tiny_http::Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..]).unwrap())
                                .with_header(tiny_http::Header::from_bytes(&b"Access-Control-Allow-Methods"[..], &b"GET,POST,PUT,DELETE,OPTIONS"[..]).unwrap())
                                .with_header(tiny_http::Header::from_bytes(&b"Access-Control-Allow-Headers"[..], &b"Content-Type,Authorization"[..]).unwrap());
                            let _ = request.respond(response);
                            continue;
                        }

                        // ── Internal reload endpoint: POST /_reload ──
                        if method == "POST" && path_only == "/_reload" {
                            let resp_body = "{\"ok\":true,\"message\":\"reloading\",\"trit\":1}";
                            let response = tiny_http::Response::from_string(resp_body)
                                .with_header(tiny_http::Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap())
                                .with_header(tiny_http::Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..]).unwrap());
                            let _ = request.respond(response);
                            // Trigger shutdown for reload
                            worker_shutdown.store(true, Ordering::SeqCst);
                            break;
                        }

                        // ── Internal hot-swap endpoint: POST /_hotswap ──
                        // Re-parses the source file and updates functions in-place
                        // without dropping the server socket (zero-downtime)
                        if method == "POST" && path_only == "/_hotswap" {
                            // Extract source_file and base_dir under a short lock to avoid deadlock
                            let (src_opt, bdir) = {
                                let vm = vm_ref.lock().unwrap();
                                (vm.source_file.clone(), vm.base_dir.clone())
                            };
                            let swap_result = if let Some(src_path) = src_opt {
                                match std::fs::read_to_string(&src_path) {
                                    Ok(code) => {
                                        let spanned = lexer::tokenize_spanned(&code);
                                        let tokens: Vec<lexer::Token> = spanned.iter().map(|st| st.token.clone()).collect();
                                        let ast = crate::parser::parse(tokens);
                                        // Build a fresh runtime to extract new function defs
                                        let mut fresh = Runtime::new();
                                        fresh.base_dir = bdir;
                                        fresh.source_file = Some(src_path);
                                        fresh.skip_tstart = true; // Don't re-bind during hotswap
                                        // Execute top-level statements to register functions and set vars
                                        if let Err(e) = fresh.execute(&ast) {
                                            format!("{{\"ok\":false,\"error\":\"parse error: {}\",\"trit\":-1}}", e)
                                        } else {
                                            // Swap functions and top-level vars into the live VM
                                            let mut vm = vm_ref.lock().unwrap();
                                            vm.functions = fresh.functions;
                                            // Merge top-level scope (preserve runtime state like _stats)
                                            if let Some(fresh_global) = fresh.scopes.first() {
                                                if let Some(live_global) = vm.scopes.first_mut() {
                                                    for (k, v) in fresh_global {
                                                        // Only update function-like and constant bindings,
                                                        // skip runtime state vars (prefixed with _)
                                                        if !k.starts_with('_') {
                                                            live_global.insert(k.clone(), v.clone());
                                                        }
                                                    }
                                                }
                                            }
                                            format!("{{\"ok\":true,\"message\":\"functions hot-swapped\",\"fn_count\":{},\"trit\":1}}",
                                                    vm.functions.len())
                                        }
                                    }
                                    Err(e) => format!("{{\"ok\":false,\"error\":\"read error: {}\",\"trit\":-1}}", e),
                                }
                            } else {
                                "{\"ok\":false,\"error\":\"no source file for hotswap\",\"trit\":-1}".to_string()
                            };
                            let response = tiny_http::Response::from_string(&swap_result)
                                .with_header(tiny_http::Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap())
                                .with_header(tiny_http::Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..]).unwrap());
                            let _ = request.respond(response);
                            continue;
                        }

                        // Find matching route (exact match first, then prefix/wildcard)
                        let handler_name = routes_ref.get(&(method.clone(), path_only.clone()))
                            .or_else(|| routes_ref.get(&("*".into(), path_only.clone())))
                            .cloned()
                            .or_else(|| {
                                // Prefix wildcard: routes ending with /* match any path with that prefix
                                let mut best: Option<(usize, String)> = None;
                                for ((m, p), h) in routes_ref.iter() {
                                    if p.ends_with("/*") && (m == &method || m == "*") {
                                        let prefix = &p[..p.len() - 2];
                                        if path_only.starts_with(prefix) && path_only.len() > prefix.len() {
                                            let plen = prefix.len();
                                            if best.is_none() || plen > best.as_ref().unwrap().0 {
                                                best = Some((plen, h.clone()));
                                            }
                                        }
                                    }
                                }
                                best.map(|(_, h)| h)
                            });

                        if let Some(fn_name) = handler_name {
                            // Read request body
                            let mut body = String::new();
                            if let Ok(_) = request.as_reader().read_to_string(&mut body) {}

                            // Build request dict
                            let mut req_pairs: Vec<(String, Value)> = vec![
                                ("method".into(), Value::Str(method.clone())),
                                ("path".into(), Value::Str(path_only.clone())),
                                ("body".into(), Value::Str(body.clone())),
                            ];

                            if let Some(q) = path.split('?').nth(1) {
                                req_pairs.push(("query_string".into(), Value::Str(q.to_string())));
                                let query_dict: Vec<(String, Value)> = q.split('&')
                                    .filter_map(|pair| {
                                        let mut parts = pair.splitn(2, '=');
                                        let key = parts.next()?.to_string();
                                        let val = parts.next().unwrap_or("").to_string();
                                        Some((key, Value::Str(val)))
                                    })
                                    .collect();
                                req_pairs.push(("query".into(), Value::Dict(query_dict)));
                            }

                            let header_pairs: Vec<(String, Value)> = request.headers().iter()
                                .map(|h| (h.field.to_string().to_lowercase(), Value::Str(h.value.to_string())))
                                .collect();
                            req_pairs.push(("headers".into(), Value::Dict(header_pairs)));

                            let req_dict = Value::Dict(req_pairs);

                            // Call handler under lock (concurrent via mutex)
                            let response_body = {
                                let mut vm = vm_ref.lock().unwrap();
                                let result = vm.call_fn(&fn_name, vec![req_dict]);
                                match result {
                                    Ok(val) => builtins::call_builtin("json_encode", &[val])
                                        .map(|v| v.to_display())
                                        .unwrap_or_else(|| "null".into()),
                                    Err(e) => format!("{{\"error\":\"{}\"}}", e),
                                }
                            };

                            let response = tiny_http::Response::from_string(&response_body)
                                .with_header(
                                    tiny_http::Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap()
                                )
                                .with_header(
                                    tiny_http::Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..]).unwrap()
                                )
                                .with_header(
                                    tiny_http::Header::from_bytes(&b"Access-Control-Allow-Methods"[..], &b"GET,POST,PUT,DELETE,OPTIONS"[..]).unwrap()
                                );
                            let _ = request.respond(response);
                        } else {
                            // 404 not found
                            let not_found = format!("{{\"error\":\"not found\",\"path\":\"{}\"}}", path_only);
                            let response = tiny_http::Response::from_string(&not_found)
                                .with_status_code(404)
                                .with_header(
                                    tiny_http::Header::from_bytes(
                                        &b"Content-Type"[..],
                                        &b"application/json"[..],
                                    ).unwrap()
                                );
                            let _ = request.respond(response);
                        }
                    } // end loop
                }); // end thread::spawn
                handles.push(handle);
            } // end worker pool loop

            // Wait for all workers to finish (they exit on shutdown signal)
            for h in handles {
                let _ = h.join();
            }
            let _ = watcher_handle.join();

            // If shutdown was triggered by file change or /_reload, re-parse and loop
            if shutdown.load(Ordering::Relaxed) {
                // Drop the http_server (Arc) -- all refs gone after join, port is released
                drop(http_server);

                // Brief pause to let OS release the port (Windows TIME_WAIT)
                std::thread::sleep(std::time::Duration::from_millis(300));

                // Re-parse the source file
                if let Some(ref src_path) = source_file {
                    match std::fs::read_to_string(src_path) {
                        Ok(code) => {
                            println!("[NovaLang] Re-parsing {}...", src_path);
                            let spanned = lexer::tokenize_spanned(&code);
                            let tokens: Vec<lexer::Token> = spanned.iter().map(|st| st.token.clone()).collect();
                            let ast = crate::parser::parse(tokens);
                            // Re-execute in a fresh runtime to pick up new function defs
                            let mut fresh = Runtime::new();
                            fresh.base_dir = base_dir.clone();
                            fresh.source_file = source_file.clone();
                            fresh.skip_tstart = true; // Prevent recursive server bind
                            // Execute everything except tstart (which we handle ourselves)
                            for stmt in &ast {
                                match fresh.exec_stmt(stmt) {
                                    Ok(Signal::None) | Ok(Signal::Return(_)) => {}
                                    Ok(Signal::Break) | Ok(Signal::Continue) => {}
                                    Err(e) => {
                                        eprintln!("[NovaLang] Reload parse error: {}", e);
                                        // On error, wait and retry
                                        std::thread::sleep(std::time::Duration::from_secs(2));
                                        break;
                                    }
                                }
                                // If tstart was called, it means we've re-entered this function
                                // recursively via the fresh runtime. We need to stop and let
                                // the outer loop handle it instead.
                            }
                            // Update self with fresh functions and non-runtime state
                            self.functions = fresh.functions;
                            if let Some(fresh_global) = fresh.scopes.first() {
                                if let Some(live_global) = self.scopes.first_mut() {
                                    for (k, v) in fresh_global {
                                        if !k.starts_with('_') {
                                            live_global.insert(k.clone(), v.clone());
                                        }
                                    }
                                }
                            }
                            // Update server def if routes changed
                            if let Some(new_server) = fresh.servers.values().next() {
                                // Update the local server variable for next loop iteration
                                server = new_server.clone();
                                self.servers.insert(
                                    format!("server_{}", server.port),
                                    new_server.clone(),
                                );
                            }
                            println!("[NovaLang] Reload complete, restarting server...");
                        }
                        Err(e) => {
                            eprintln!("[NovaLang] Cannot read source for reload: {}", e);
                            std::thread::sleep(std::time::Duration::from_secs(2));
                        }
                    }
                } else {
                    // No source file -- full restart requested via /_reload
                    // but we can't re-parse. Just re-bind with existing state.
                    println!("[NovaLang] Restarting server (no source file for re-parse)...");
                }

                // Reset shutdown flag and loop back to re-bind
                continue;
            } else {
                // Normal exit (process termination)
                break;
            }
        } // end outer reload loop

        Ok(Value::Trit(1))
    }
}
