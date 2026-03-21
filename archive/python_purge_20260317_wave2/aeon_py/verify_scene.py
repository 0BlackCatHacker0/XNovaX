"""AEON WELL Scene Verification - Ternary Phase Check"""
import bpy

H3, H5, H7, H13 = 3, 5, 7, 13
results = []

# Check collections
expected_colls = ["COLL_WORLD", "COLL_MEGASTRUCTURE", "COLL_PORTAL", "COLL_VFX", "COLL_CAM_LIGHT"]
for c in expected_colls:
    trit = 1 if c in bpy.data.collections else -1
    results.append((c, trit))

# Check key objects
expected_objs = ["OCEAN_PLANE", "ATMOS_VOLUME", "RING_BASE", "CITY_BELT", "PORTAL_WELL",
                 "ENERGY_LATTICE", "CAM_MAIN", "KEY_LIGHT", "RIM_LIGHT", "PORTAL_LIGHT"]
for o in expected_objs:
    trit = 1 if o in bpy.data.objects else -1
    results.append((o, trit))

# Check materials
expected_mats = ["MAT_OCEAN", "MAT_ATMOSPHERE", "MAT_RING_METAL", "MAT_CITY_WINDOWS",
                 "MAT_PORTAL_EMIT", "MAT_LATTICE_EMIT"]
for m in expected_mats:
    trit = 1 if m in bpy.data.materials else -1
    results.append((m, trit))

# Check camera animation
cam = bpy.data.objects.get("CAM_MAIN")
cam_anim = 1 if cam and cam.constraints else -1
results.append(("CAM_ANIMATION", cam_anim))

# Check render settings
scene = bpy.context.scene
render_ok = 1 if scene.render.engine == 'CYCLES' else -1
results.append(("CYCLES_ENGINE", render_ok))

fps_ok = 1 if scene.render.fps == 24 else -1
results.append(("FPS_24", fps_ok))

frames_ok = 1 if scene.frame_end >= 288 else -1
results.append(("FRAME_COUNT", frames_ok))

# Check compositing
comp_ok = 1 if scene.use_nodes else -1
results.append(("COMPOSITOR", comp_ok))

# Summary
total = len(results)
passed = sum(1 for _, t in results if t == 1)
failed = sum(1 for _, t in results if t == -1)

print("=" * 50)
print("AEON WELL SCENE VERIFICATION")
print("=" * 50)
for name, trit in results:
    sym = "+1" if trit == 1 else "-1"
    print(f"  [{sym}] {name}")
print("=" * 50)
print(f"TOTAL: {total} | PASS: {passed} | FAIL: {failed}")
print(f"TERNARY SCORE: {passed}/{total} = {passed/total:.1%}")
print("=" * 50)
