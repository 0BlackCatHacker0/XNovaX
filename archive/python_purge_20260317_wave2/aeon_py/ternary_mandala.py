"""NovaX Ternary Energy Mandala — 3-5-7-13 Harmonic Generator
Creates a sacred geometry mandala around the AEON WELL using harmonic constants.
Inner ring: H3=3 large energy spheres (green glow)
Middle ring: H5=5 torus vortices (cyan glow)
Outer ring: H7=7 crystal shards (magenta glow)
Crown: H13=13 orbiting light points (white)
Rendered via EEVEE with bloom for cinematic neon effect.
"""
import bpy
import math
import os

# ── 3-5-7-13 Harmonic Constants ──
H3, H5, H7, H13 = 3, 5, 7, 13
BLOCK = H3 ** H7  # 2187

# ── NovaX Neon Colors (linear sRGB) ──
GREEN = (0.0, 1.0, 0.33, 1.0)    # #00ff55
CYAN = (0.0, 0.83, 1.0, 1.0)     # #00d4ff
MAGENTA = (1.0, 0.0, 1.0, 1.0)   # #ff00ff
WHITE = (1.0, 1.0, 1.0, 1.0)
DARK_BG = (0.02, 0.02, 0.04, 1.0)

# ── Helper: create emissive material ──
def make_emissive(name, color, strength=15.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = strength
    links.new(emission.outputs[0], output.inputs[0])
    return mat

# ── Helper: place object in ring ──
def ring_place(obj, radius, index, total, z=0):
    angle = 2 * math.pi * index / total
    obj.location = (radius * math.cos(angle), radius * math.sin(angle), z)

# ── Setup scene ──
scene = bpy.context.scene

# Detect Blender version for EEVEE engine name
blender_ver = bpy.app.version
if blender_ver >= (4, 0, 0) and blender_ver < (4, 2, 0):
    scene.render.engine = "BLENDER_EEVEE_NEXT"
else:
    scene.render.engine = "BLENDER_EEVEE"

scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100

# ── PURGE all existing worlds to prevent stale overrides ──
for w in list(bpy.data.worlds):
    bpy.data.worlds.remove(w)

# Force dark world background — fresh world with explicit wiring
new_world = bpy.data.worlds.new("NX_DarkVoid")
new_world.use_nodes = True
nt = new_world.node_tree
nt.nodes.clear()
bg_node = nt.nodes.new("ShaderNodeBackground")
bg_node.inputs["Color"].default_value = (0.002, 0.002, 0.008, 1.0)
bg_node.inputs["Strength"].default_value = 0.01
out_node = nt.nodes.new("ShaderNodeOutputWorld")
nt.links.new(bg_node.outputs["Background"], out_node.inputs["Surface"])
scene.world = new_world

# EEVEE settings — bloom was removed in Blender 4.0+ (moved to compositor)
if hasattr(scene.eevee, "use_bloom"):
    scene.eevee.use_bloom = True
    scene.eevee.bloom_threshold = 0.8
    scene.eevee.bloom_intensity = 0.5
    scene.eevee.bloom_radius = 6.0

# For Blender 4.0+ add compositor bloom via glare node
if blender_ver >= (4, 0, 0):
    try:
        scene.use_nodes = True
        comp_tree = scene.node_tree
        if comp_tree:
            comp_tree.nodes.clear()
            rl_node = comp_tree.nodes.new("CompositorNodeRLayers")
            glare_node = comp_tree.nodes.new("CompositorNodeGlare")
            glare_node.glare_type = 'BLOOM'
            glare_node.threshold = 0.8
            glare_node.size = 6
            glare_node.quality = 'HIGH'
            out_comp = comp_tree.nodes.new("CompositorNodeComposite")
            comp_tree.links.new(rl_node.outputs["Image"], glare_node.inputs["Image"])
            comp_tree.links.new(glare_node.outputs["Image"], out_comp.inputs["Image"])
    except (AttributeError, Exception) as e:
        print(f"[NovaX] Compositor bloom skipped: {e}")

# ── Materials ──
mat_green = make_emissive("NX_Energy_Green", GREEN, 12.0)
mat_cyan = make_emissive("NX_Vortex_Cyan", CYAN, 10.0)
mat_magenta = make_emissive("NX_Crystal_Magenta", MAGENTA, 15.0)
mat_white = make_emissive("NX_Crown_White", WHITE, 6.0)
mat_core = make_emissive("NX_Core_Pulse", GREEN, 30.0)

# ── Create mandala collection ──
mandala_col = bpy.data.collections.new("TERNARY_MANDALA")
scene.collection.children.link(mandala_col)

# ── Hide ALL existing objects (meshes, lights, cameras) for clean render ──
for obj in scene.objects:
    if not obj.name.startswith("NX_"):
        obj.hide_render = True
        obj.hide_viewport = True

# ── Color management: Standard for true neon colors ──
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0

# ── Central Core: pulsing energy sphere ──
bpy.ops.mesh.primitive_uv_sphere_add(radius=2.0, segments=32, ring_count=16, location=(0, 0, 0))
core = bpy.context.active_object
core.name = "NX_CORE"
core.data.materials.append(mat_core)
# Move to mandala collection
for col in core.users_collection:
    col.objects.unlink(core)
mandala_col.objects.link(core)

# ── Inner Ring: H3=3 Energy Spheres ──
for i in range(H3):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.2, segments=24, ring_count=12)
    obj = bpy.context.active_object
    obj.name = f"NX_ENERGY_{i}"
    obj.data.materials.append(mat_green)
    ring_place(obj, 8.0, i, H3, z=0)
    # Add wireframe modifier for energy field effect
    mod = obj.modifiers.new("Wireframe", "WIREFRAME")
    mod.thickness = 0.05
    mod.use_replace = False
    for col in obj.users_collection:
        col.objects.unlink(obj)
    mandala_col.objects.link(obj)

# ── Middle Ring: H5=5 Torus Vortices ──
for i in range(H5):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=1.0, minor_radius=0.25,
        major_segments=36, minor_segments=12
    )
    obj = bpy.context.active_object
    obj.name = f"NX_VORTEX_{i}"
    obj.data.materials.append(mat_cyan)
    ring_place(obj, 16.0, i, H5, z=1.5)
    # Tilt each torus uniquely
    obj.rotation_euler = (math.pi * i / H5, math.pi / 4, 2 * math.pi * i / H5)
    for col in obj.users_collection:
        col.objects.unlink(obj)
    mandala_col.objects.link(obj)

# ── Outer Ring: H7=7 Crystal Shards ──
for i in range(H7):
    bpy.ops.mesh.primitive_cone_add(
        vertices=H3, radius1=0.8, depth=3.0
    )
    obj = bpy.context.active_object
    obj.name = f"NX_CRYSTAL_{i}"
    obj.data.materials.append(mat_magenta)
    ring_place(obj, 24.0, i, H7, z=-1.0)
    # Point outward
    angle = 2 * math.pi * i / H7
    obj.rotation_euler = (math.pi / 6, 0, angle + math.pi / 2)
    for col in obj.users_collection:
        col.objects.unlink(obj)
    mandala_col.objects.link(obj)

# ── Crown: H13=13 Light Points ──
for i in range(H13):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.3, subdivisions=2)
    obj = bpy.context.active_object
    obj.name = f"NX_CROWN_{i}"
    obj.data.materials.append(mat_white)
    # Spiral upward
    t = i / H13
    radius = 12.0 + 8.0 * t
    height = -3.0 + 10.0 * t
    angle = 2 * math.pi * i * H3 / H13  # H3/H13 = golden-ish spiral
    obj.location = (radius * math.cos(angle), radius * math.sin(angle), height)
    for col in obj.users_collection:
        col.objects.unlink(obj)
    mandala_col.objects.link(obj)

# ── Connecting Lines: energy beams between spheres ──
# Create curve circle for bevel
bpy.ops.curve.primitive_bezier_circle_add(radius=0.05)
bevel = bpy.context.active_object
bevel.name = "NX_BEVEL"
for col in bevel.users_collection:
    col.objects.unlink(bevel)
mandala_col.objects.link(bevel)

for i in range(H3):
    # Beam from core to each energy sphere
    angle = 2 * math.pi * i / H3
    end = (8.0 * math.cos(angle), 8.0 * math.sin(angle), 0)

    curve_data = bpy.data.curves.new(f"NX_BEAM_{i}", type="CURVE")
    curve_data.dimensions = "3D"
    spline = curve_data.splines.new("NURBS")
    spline.points.add(1)
    spline.points[0].co = (0, 0, 0, 1)
    spline.points[1].co = (*end, 1)
    curve_data.bevel_object = bevel

    beam = bpy.data.objects.new(f"NX_BEAM_{i}", curve_data)
    beam.data.materials.append(mat_green)
    mandala_col.objects.link(beam)

# ── Camera Setup ──
# Remove existing cameras
for obj in list(scene.objects):
    if obj.type == "CAMERA" and "NX_" in obj.name:
        bpy.data.objects.remove(obj, do_unlink=True)

cam_data = bpy.data.cameras.new("NX_CAMERA")
cam_data.lens = 28  # Wide angle for dramatic effect
cam_data.clip_end = 500
cam_obj = bpy.data.objects.new("NX_CAMERA", cam_data)
mandala_col.objects.link(cam_obj)
cam_obj.location = (35, -30, 20)
cam_obj.rotation_euler = (math.radians(60), 0, math.radians(48))

# Add Track-To constraint targeting the core
track = cam_obj.constraints.new("TRACK_TO")
track.target = core
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis = "UP_Y"
scene.camera = cam_obj

# ── Point Light at Center ──
light_data = bpy.data.lights.new("NX_LIGHT", type="POINT")
light_data.energy = 1000
light_data.color = (0.0, 1.0, 0.5)  # Green tint
light_data.shadow_soft_size = 5.0
light_obj = bpy.data.objects.new("NX_LIGHT", light_data)
light_obj.location = (0, 0, 5)
mandala_col.objects.link(light_obj)

# ── Render ──
output_path = os.path.join("C:\\NovaX\\projects\\AEON_WELL", "ternary_mandala_render.png")
scene.render.filepath = output_path
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False

# Set samples for quality
scene.eevee.taa_render_samples = 64

# Save the modified .blend so we can open it in the live Blender
blend_out = os.path.join("C:\\NovaX\\projects\\AEON_WELL\\BLEND", "AEON_WELL_MANDALA.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_out)
print(f"[NovaX] Scene saved: {blend_out}")

bpy.ops.render.render(write_still=True)

print(f"[NovaX] Ternary Mandala rendered to: {output_path}")
print(f"[NovaX] Objects created: {H3 + H5 + H7 + H13 + 1} + {H3} beams = {H3 + H5 + H7 + H13 + 1 + H3} total")
print(f"[NovaX] Harmonic structure: {H3}-{H5}-{H7}-{H13} (core-inner-middle-outer-crown)")
