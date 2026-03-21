"""Render preview frames — with rendering fixes for visibility."""
import bpy
import os

scene = bpy.context.scene

# Hide atmosphere volume
atmos = bpy.data.objects.get("ATMOS_VOLUME")
if atmos:
    atmos.hide_render = True

# Fix 1: Standard view transform instead of Filmic (Filmic lifts blacks to gray)
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'

# Fix 2: Make world background pure black
world = scene.world
if world and world.node_tree:
    for n in world.node_tree.nodes:
        if n.type == 'BACKGROUND':
            n.inputs['Color'].default_value = (0.002, 0.004, 0.012, 1)
            n.inputs['Strength'].default_value = 1.0

# Fix 3: Boost lights for visibility at this scale
for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        obj.data.energy *= 3

# Preview settings
scene.render.resolution_percentage = 50
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.render.image_settings.file_format = 'PNG'

out_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "RENDER"
)
os.makedirs(out_dir, exist_ok=True)

for frame in [1, 144, 250]:
    scene.frame_set(frame)
    path = os.path.join(out_dir, f"preview_f{frame:03d}.png")
    scene.render.filepath = path
    print(f"  Rendering frame {frame}...")
    bpy.ops.render.render(write_still=True)
    print(f"  Saved: {path}")

print("\nDone.")
