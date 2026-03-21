# FLUENT MASTER FILE

Navier–Stokes Based Programming Language

================================================== SECTION 1 —
SPECIFICATION ================================================== Core
model: Programs are fields evolving over time.

Primitives: ScalarField VectorField TensorField Grid dt nu

Operators: grad, div, curl, lap advect diffuse project force source

Execution: step { … } run steps:N

================================================== SECTION 2 — STANDARD
OPERATORS ==================================================
advect(f,u,dt) transport along velocity diffuse(f,nu,dt) smoothing
project(u) incompressibility constraint force(F,dt) external injection
lap(f) curvature measure grad(f) direction of change div(v)
compression/expansion curl(v) rotation

================================================== SECTION 3 — IR MODEL
================================================== Program → AST →
FieldGraph → KernelSchedule → Backend

Nodes: Field Operator Constraint Boundary

Scheduler passes: local_ops global_projection stability_check

================================================== SECTION 4 — EXAMPLES
================================================== Example: Dye
simulation

domain D = grid(size:(256,256)) field u:VectorField on D field
dye:ScalarField on D

step { u = advect(u,u,0.016) dye = advect(dye,u,0.016) }

Example: Pathfinding Field

field goal:ScalarField flow = -grad(goal)

================================================== SECTION 5 — COMPILER
SKELETON ================================================== Parser →
tokens → AST AST → FieldGraph FieldGraph → GPU kernels (WGSL) Execute
loop

Pseudo:

parse() build_graph() schedule() emit_shader() run()

================================================== END
