# LANGUAGE_FUSION_SPEC_v1

## Purpose

Define a unified language that maps multiple programming paradigms
(systems, scripting, query, shader, HDL, esoteric/signal) into one
semantic core with multiple execution backends.

## Core Philosophy

One grammar → many execution planes.

The language does not copy other syntaxes. It translates intent into
execution domains.

## Universal Semantic Blocks

-   fn : computation
-   flow : data transformation pipelines
-   query : structured data retrieval
-   task : system automation
-   kernel : parallel GPU compute
-   circuit : hardware logic
-   rule : constraint / logic reasoning

## Type System

Static by default with gradual escape: - Int, Float, Bool, Str, Bytes -
Vec\[T\], Map\[K,V\] - Option\[T\], Result\[T,E\] - dyn (dynamic) -
Traits for polymorphism - Effects: io, net, gpu, fs, unsafe

## Execution Targets

| Block   | Backend                |
|---------|------------------------|
| fn/flow | native / wasm / vm     |
| query   | sql / graphql / cypher |
| kernel  | wgsl / glsl / hlsl     |
| circuit | verilog subset         |
| task    | shell / powershell     |
| rule    | logic solver engine    |

## Interop

ffi.c → C ABI ffi.wasm → WebAssembly modules ffi.jvm → JVM ffi.dotnet →
CLR ffi.js → JavaScript runtime

## Compilation Pipeline

Source → AST → NOVA-IR → backend lowering

NOVA-IR properties: - SSA form - effect metadata - execution domain
tags - async aware

## Safety Model

Safe by default. Unsafe blocks require explicit declaration.

## Example

flow files \| filter ext == “txt” \| count

query users where age \> 18

kernel particles update position

task install “python”

circuit Adder { a + b -\> y }

rule reachable(a,b)

## Goal

Describe behavior once. Compiler selects the correct machine.
