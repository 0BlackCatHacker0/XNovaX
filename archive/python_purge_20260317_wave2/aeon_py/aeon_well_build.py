"""
AEON WELL — Procedural Megastructure Scene Builder
NovaX Studio x Blender 5.x (Cycles)

Ternary build phases — each returns trit: +1 complete, 0 partial, -1 failed
Reynolds flow classification per phase complexity.

Run: blender --python aeon_well_build.py
"""
import bpy
import math
import os
import random
from mathutils import Vector, Euler

# ── 3-5-7-13 Harmonic Constants ──
H3, H5, H7, H13 = 3, 5, 7, 13
SCENE_SCALE = 1.0  # 1 BU = 1 meter

# ── Ternary state tracking ──
BUILD_LOG = []

def trit(val):
    return 1 if val else -1

def log_phase(name, success, detail=""):
    t = trit(success)
    BUILD_LOG.append({"phase": name, "trit": t, "detail": detail})
    sym = "+1" if t == 1 else "-1"
    print(f"  [{sym}] {name} {detail}")
    return t


def get_fcurves(action):
    """Get fcurves from Blender 5.0 layered action (no more action.fcurves)."""
    if hasattr(action, 'layers') and len(action.layers) > 0:
        layer = action.layers[0]
        if hasattr(layer, 'strips') and len(layer.strips) > 0:
            strip = layer.strips[0]
            if hasattr(strip, 'channelbags') and len(strip.channelbags) > 0:
                return strip.channelbags[0].fcurves
    return []


def clear_scene():
    """Wipe everything for a clean build."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    # Remove orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in bpy.data.cameras:
        if block.users == 0:
            bpy.data.cameras.remove(block)
    for block in bpy.data.lights:
        if block.users == 0:
            bpy.data.lights.remove(block)
    for block in bpy.data.curves:
        if block.users == 0:
            bpy.data.curves.remove(block)


def get_or_create_collection(name, parent=None):
    """Get or create a collection by name."""
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    if parent:
        parent.children.link(col)
    else:
        bpy.context.scene.collection.children.link(col)
    return col


def link_to_collection(obj, col_name):
    """Link object to named collection, unlink from scene root."""
    col = get_or_create_collection(col_name)
    if obj.name not in col.objects:
        col.objects.link(obj)
    if obj.name in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.unlink(obj)


# ============================================================
# PHASE 1: COLLECTIONS (Re < 27 — laminar)
# ============================================================
def phase_collections():
    """Create the collection hierarchy."""
    try:
        get_or_create_collection("COLL_WORLD")
        get_or_create_collection("COLL_MEGASTRUCTURE")
        get_or_create_collection("COLL_PORTAL")
        get_or_create_collection("COLL_VFX")
        get_or_create_collection("COLL_CAM_LIGHT")
        return log_phase("Collections", True, "5 collections")
    except Exception as e:
        return log_phase("Collections", False, str(e)[:80])


# ============================================================
# PHASE 2: OCEAN + SPRAY (Re ~125 — transitional)
# ============================================================
def phase_ocean():
    """Ocean plane with modifier + foam-driven material."""
    try:
        bpy.ops.mesh.primitive_plane_add(size=2000, location=(0, 0, -50))
        ocean = bpy.context.active_object
        ocean.name = "OCEAN_PLANE"
        link_to_collection(ocean, "COLL_WORLD")

        # Ocean modifier
        mod = ocean.modifiers.new(name="Ocean", type='OCEAN')
        mod.geometry_mode = 'GENERATE'
        mod.resolution = 14
        mod.size = 20
        mod.spatial_size = 200
        mod.depth = 200
        mod.wave_scale = 1.5
        mod.choppiness = 1.5
        mod.wind_velocity = 35
        mod.use_foam = True
        mod.foam_coverage = -0.3

        # Ocean material
        mat = bpy.data.materials.new("MAT_OCEAN")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        out = nodes.new('ShaderNodeOutputMaterial')
        out.location = (600, 0)
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (200, 0)
        bsdf.inputs['Base Color'].default_value = (0.01, 0.03, 0.08, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.1
        bsdf.inputs['IOR'].default_value = 1.33
        bsdf.inputs['Metallic'].default_value = 0.0
        links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

        # Foam via vertex color
        attr = nodes.new('ShaderNodeAttribute')
        attr.attribute_name = "foam"
        attr.location = (-400, -200)
        mix = nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.location = (-100, 0)
        mix.inputs['A'].default_value = (0.01, 0.03, 0.08, 1)
        mix.inputs['B'].default_value = (0.7, 0.75, 0.8, 1)
        links.new(attr.outputs['Fac'], mix.inputs['Factor'])
        links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])

        ocean.data.materials.append(mat)
        return log_phase("Ocean", True, "2000m plane, foam enabled")
    except Exception as e:
        return log_phase("Ocean", False, str(e)[:80])


# ============================================================
# PHASE 3: ATMOSPHERE VOLUME (Re ~125 — transitional)
# ============================================================
def phase_atmosphere():
    """Large volume cube for fog + portal beam scattering."""
    try:
        bpy.ops.mesh.primitive_cube_add(size=2500, location=(0, 0, 200))
        vol = bpy.context.active_object
        vol.name = "ATMOS_VOLUME"
        vol.display_type = 'WIRE'
        vol.hide_render = True  # Disable for now — fogs out at this scale
        link_to_collection(vol, "COLL_WORLD")

        mat = bpy.data.materials.new("MAT_ATMOSPHERE")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        out = nodes.new('ShaderNodeOutputMaterial')
        out.location = (800, 0)

        # Principled Volume
        pvol = nodes.new('ShaderNodeVolumePrincipled')
        pvol.location = (400, 0)
        pvol.inputs['Density'].default_value = 0.00008  # Low base — beam falloff adds density near portal
        pvol.inputs['Anisotropy'].default_value = 0.7
        pvol.inputs['Absorption Color'].default_value = (0.8, 0.85, 0.95, 1)
        pvol.inputs['Emission Color'].default_value = (0.0, 0.0, 0.0, 1)
        links.new(pvol.outputs['Volume'], out.inputs['Volume'])

        # Portal beam density overlay: radial falloff from center axis
        tex_coord = nodes.new('ShaderNodeTexCoord')
        tex_coord.location = (-600, 0)
        mapping = nodes.new('ShaderNodeMapping')
        mapping.location = (-400, 0)
        links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])

        sep_xyz = nodes.new('ShaderNodeSeparateXYZ')
        sep_xyz.location = (-200, -100)
        links.new(mapping.outputs['Vector'], sep_xyz.inputs['Vector'])

        # Radial distance from Y axis (portal is vertical)
        math_x2 = nodes.new('ShaderNodeMath')
        math_x2.operation = 'POWER'
        math_x2.location = (0, -100)
        links.new(sep_xyz.outputs['X'], math_x2.inputs[0])
        math_x2.inputs[1].default_value = 2.0

        math_z2 = nodes.new('ShaderNodeMath')
        math_z2.operation = 'POWER'
        math_z2.location = (0, -250)
        links.new(sep_xyz.outputs['Z'], math_z2.inputs[0])
        math_z2.inputs[1].default_value = 2.0

        math_add = nodes.new('ShaderNodeMath')
        math_add.operation = 'ADD'
        math_add.location = (180, -180)
        links.new(math_x2.outputs['Value'], math_add.inputs[0])
        links.new(math_z2.outputs['Value'], math_add.inputs[1])

        # Invert for beam shape (brighter at center)
        math_inv = nodes.new('ShaderNodeMath')
        math_inv.operation = 'DIVIDE'
        math_inv.location = (360, -180)
        math_inv.inputs[0].default_value = 0.5
        links.new(math_add.outputs['Value'], math_inv.inputs[1])

        # Mix beam into density
        math_beam = nodes.new('ShaderNodeMath')
        math_beam.operation = 'ADD'
        math_beam.location = (200, 100)
        math_beam.inputs[0].default_value = 0.00008  # base density (low to avoid fog-out)
        links.new(math_inv.outputs['Value'], math_beam.inputs[1])
        links.new(math_beam.outputs['Value'], pvol.inputs['Density'])

        vol.data.materials.append(mat)
        return log_phase("Atmosphere", True, "2500m volume, beam falloff")
    except Exception as e:
        return log_phase("Atmosphere", False, str(e)[:80])


# ============================================================
# PHASE 4: RING BASE (Re ~343 — turbulent, GN complexity)
# ============================================================
def phase_ring_base():
    """Procedural ring megastructure with panel variation."""
    try:
        # Create base torus as ring
        bpy.ops.mesh.primitive_torus_add(
            major_radius=500, minor_radius=15,
            major_segments=128, minor_segments=16,
            location=(0, 0, 100)
        )
        ring = bpy.context.active_object
        ring.name = "RING_BASE"
        link_to_collection(ring, "COLL_MEGASTRUCTURE")

        # Ring metal material
        mat = bpy.data.materials.new("MAT_RING_METAL")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        out = nodes.new('ShaderNodeOutputMaterial')
        out.location = (800, 0)
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (400, 0)
        bsdf.inputs['Metallic'].default_value = 1.0
        bsdf.inputs['Roughness'].default_value = 0.25
        bsdf.inputs['Base Color'].default_value = (0.15, 0.17, 0.2, 1.0)
        links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

        # Micro detail bump via noise
        noise = nodes.new('ShaderNodeTexNoise')
        noise.location = (-200, -200)
        noise.inputs['Scale'].default_value = 80.0
        noise.inputs['Detail'].default_value = 12.0
        bump = nodes.new('ShaderNodeBump')
        bump.location = (100, -200)
        bump.inputs['Strength'].default_value = 0.05
        links.new(noise.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

        # Panel lines via wave texture
        wave = nodes.new('ShaderNodeTexWave')
        wave.location = (-200, 200)
        wave.wave_type = 'RINGS'
        wave.inputs['Scale'].default_value = 30.0
        wave.inputs['Distortion'].default_value = 2.0

        # Edge wear via geometry -> pointiness
        geom = nodes.new('ShaderNodeNewGeometry')
        geom.location = (-200, 400)

        # Mix roughness for edges
        mix_rough = nodes.new('ShaderNodeMath')
        mix_rough.operation = 'MULTIPLY'
        mix_rough.location = (100, 300)
        mix_rough.inputs[1].default_value = 0.4
        links.new(wave.outputs['Fac'], mix_rough.inputs[0])

        ring.data.materials.append(mat)

        # Solidify for thickness
        solid = ring.modifiers.new("Solidify", 'SOLIDIFY')
        solid.thickness = 8.0
        solid.offset = -1

        # Bevel for highlights
        bevel = ring.modifiers.new("Bevel", 'BEVEL')
        bevel.width = 0.3
        bevel.segments = 2

        return log_phase("Ring Base", True, "R=500m, 128seg, metal shader")
    except Exception as e:
        return log_phase("Ring Base", False, str(e)[:80])


# ============================================================
# PHASE 5: CITY BELT (Re ~343 — turbulent)
# ============================================================
def phase_city_belt():
    """Dense city band along outer ring — instanced buildings."""
    try:
        # Create building kit (simple boxes of varying height)
        building_col = get_or_create_collection("BUILDING_KIT")
        buildings = []
        random.seed(H13 * H7)  # Harmonic seed

        for i in range(H13 * 3):  # 39 building types (13*3)
            w = random.uniform(3, 12)
            d = random.uniform(3, 12)
            h = random.uniform(8, 80)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
            bldg = bpy.context.active_object
            bldg.name = f"BLDG_{i:03d}"
            bldg.scale = (w, d, h)
            bpy.ops.object.transform_apply(scale=True)
            link_to_collection(bldg, "BUILDING_KIT")
            buildings.append(bldg)

        # Hide building templates from viewport (particle system still uses them)
        building_col.hide_viewport = True

        # City window material
        mat_city = bpy.data.materials.new("MAT_CITY_WINDOWS")
        mat_city.use_nodes = True
        cn = mat_city.node_tree.nodes
        cl = mat_city.node_tree.links
        cn.clear()

        out = cn.new('ShaderNodeOutputMaterial')
        out.location = (800, 0)
        bsdf = cn.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (400, 0)
        bsdf.inputs['Base Color'].default_value = (0.05, 0.06, 0.08, 1)
        bsdf.inputs['Metallic'].default_value = 0.8
        bsdf.inputs['Roughness'].default_value = 0.3
        cl.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

        # Emissive windows via noise
        noise_w = cn.new('ShaderNodeTexNoise')
        noise_w.location = (-400, -100)
        noise_w.inputs['Scale'].default_value = 50.0
        noise_w.inputs['Detail'].default_value = 4.0

        ramp = cn.new('ShaderNodeValToRGB')
        ramp.location = (-100, -100)
        ramp.color_ramp.elements[0].position = 0.55
        ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
        ramp.color_ramp.elements[1].position = 0.6
        ramp.color_ramp.elements[1].color = (1, 0.9, 0.7, 1)
        cl.new(noise_w.outputs['Fac'], ramp.inputs['Fac'])

        # Mix emissive windows
        emit = cn.new('ShaderNodeEmission')
        emit.location = (200, -200)
        emit.inputs['Strength'].default_value = 5.0
        cl.new(ramp.outputs['Color'], emit.inputs['Color'])

        mix_shader = cn.new('ShaderNodeMixShader')
        mix_shader.location = (600, 0)
        cl.new(ramp.outputs['Color'], mix_shader.inputs['Fac'])
        cl.new(bsdf.outputs['BSDF'], mix_shader.inputs[1])
        cl.new(emit.outputs['Emission'], mix_shader.inputs[2])
        cl.new(mix_shader.outputs['Shader'], out.inputs['Surface'])

        for b in buildings:
            b.data.materials.append(mat_city)

        # Place buildings along ring using particle system on a ring mesh
        bpy.ops.mesh.primitive_torus_add(
            major_radius=520, minor_radius=5,
            major_segments=256, minor_segments=4,
            location=(0, 0, 100)
        )
        city_base = bpy.context.active_object
        city_base.name = "CITY_BELT"
        link_to_collection(city_base, "COLL_MEGASTRUCTURE")

        # Use particle system for building placement
        ps = city_base.modifiers.new("CityInstances", 'PARTICLE_SYSTEM')
        psys = city_base.particle_systems[-1]
        settings = psys.settings
        settings.type = 'HAIR'
        settings.count = 3000
        settings.hair_length = 1
        settings.use_advanced_hair = True
        settings.render_type = 'COLLECTION'
        settings.instance_collection = building_col
        settings.use_rotation_instance = True
        settings.use_collection_pick_random = True
        settings.particle_size = 1.0
        settings.size_random = 0.5

        return log_phase("City Belt", True, f"{len(buildings)} bldg types, 3000 instances")
    except Exception as e:
        return log_phase("City Belt", False, str(e)[:80])


# ============================================================
# PHASE 6: PORTAL WELL + ENERGY LATTICE (Re ~343)
# ============================================================
def phase_portal():
    """Portal cylinder with helical ribs + energy lattice."""
    try:
        # Portal well — cylinder
        bpy.ops.mesh.primitive_cylinder_add(
            radius=40, depth=300,
            vertices=64, location=(0, 0, 100)
        )
        portal = bpy.context.active_object
        portal.name = "PORTAL_WELL"
        link_to_collection(portal, "COLL_PORTAL")

        # Portal material — dark metal with emissive edge
        mat_p = bpy.data.materials.new("MAT_PORTAL")
        mat_p.use_nodes = True
        pn = mat_p.node_tree.nodes
        pl = mat_p.node_tree.links
        pn.clear()

        out = pn.new('ShaderNodeOutputMaterial')
        out.location = (800, 0)
        bsdf = pn.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (400, 0)
        bsdf.inputs['Base Color'].default_value = (0.02, 0.02, 0.03, 1)
        bsdf.inputs['Metallic'].default_value = 1.0
        bsdf.inputs['Roughness'].default_value = 0.15
        pl.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

        portal.data.materials.append(mat_p)

        # Helical ribs around portal
        for i in range(H7):  # 7 helical ribs (harmonic)
            bpy.ops.curve.primitive_bezier_circle_add(radius=45, location=(0, 0, -100))
            helix = bpy.context.active_object
            helix.name = f"PORTAL_RIB_{i}"
            # Make it a helix by modifying points
            helix.data.twist_mode = 'Z_UP'
            # Add screw modifier for helix effect
            screw = helix.modifiers.new("Screw", 'SCREW')
            screw.screw_offset = 300 / H7
            screw.iterations = 1
            screw.angle = math.radians(360 / H7)
            screw.axis = 'Z'

            # Convert and apply
            helix.rotation_euler.z = math.radians(i * (360 / H7))
            link_to_collection(helix, "COLL_PORTAL")

        # Energy lattice — grid of emissive tubes
        bpy.ops.mesh.primitive_ico_sphere_add(
            radius=30, subdivisions=3, location=(0, 0, 100)
        )
        lattice = bpy.context.active_object
        lattice.name = "ENERGY_LATTICE"
        lattice.display_type = 'WIRE'
        link_to_collection(lattice, "COLL_PORTAL")

        # Wireframe modifier for tube effect
        wire = lattice.modifiers.new("Wireframe", 'WIREFRAME')
        wire.thickness = 0.5
        wire.use_replace = True

        # Emissive lattice material
        mat_l = bpy.data.materials.new("MAT_LATTICE_EMIT")
        mat_l.use_nodes = True
        ln = mat_l.node_tree.nodes
        ll = mat_l.node_tree.links
        ln.clear()

        out = ln.new('ShaderNodeOutputMaterial')
        out.location = (600, 0)
        emit = ln.new('ShaderNodeEmission')
        emit.location = (300, 0)
        emit.inputs['Color'].default_value = (0.0, 0.8, 1.0, 1)  # Cyan
        emit.inputs['Strength'].default_value = 8.0
        ll.new(emit.outputs['Emission'], out.inputs['Surface'])

        # Animated flicker via noise
        noise = ln.new('ShaderNodeTexNoise')
        noise.location = (-100, -100)
        noise.noise_dimensions = '4D'  # Must set BEFORE accessing W input
        noise.inputs['Scale'].default_value = 5.0
        noise.inputs['W'].default_value = 0.0

        math_mul = ln.new('ShaderNodeMath')
        math_mul.operation = 'MULTIPLY'
        math_mul.location = (100, -100)
        math_mul.inputs[1].default_value = 12.0
        ll.new(noise.outputs['Fac'], math_mul.inputs[0])
        ll.new(math_mul.outputs['Value'], emit.inputs['Strength'])

        # Keyframe noise W for animation
        noise.inputs['W'].default_value = 0.0
        noise.inputs['W'].keyframe_insert(data_path="default_value", frame=1)
        noise.inputs['W'].default_value = 10.0
        noise.inputs['W'].keyframe_insert(data_path="default_value", frame=432)

        lattice.data.materials.append(mat_l)

        return log_phase("Portal", True, f"well R=40m, {H7} ribs, lattice")
    except Exception as e:
        return log_phase("Portal", False, str(e)[:80])


# ============================================================
# PHASE 7: LIGHTING (Re ~125 — transitional)
# ============================================================
def phase_lighting():
    """Cinematic storm lighting — key, rim, portal emission."""
    try:
        # World — dark stormy sky
        world = bpy.context.scene.world
        if not world:
            world = bpy.data.worlds.new("STORM_WORLD")
            bpy.context.scene.world = world
        world.use_nodes = True
        wn = world.node_tree.nodes
        wl = world.node_tree.links
        wn.clear()

        out = wn.new('ShaderNodeOutputWorld')
        out.location = (400, 0)
        bg = wn.new('ShaderNodeBackground')
        bg.location = (200, 0)
        bg.inputs['Color'].default_value = (0.005, 0.008, 0.02, 1)
        bg.inputs['Strength'].default_value = 0.3
        wl.new(bg.outputs['Background'], out.inputs['Surface'])

        # Key light — moonlight
        bpy.ops.object.light_add(type='AREA', location=(800, -400, 600))
        key = bpy.context.active_object
        key.name = "KEY_LIGHT"
        key.data.energy = 50000
        key.data.size = 200
        key.data.color = (0.7, 0.75, 0.9)
        key.rotation_euler = (math.radians(45), 0, math.radians(-30))
        link_to_collection(key, "COLL_CAM_LIGHT")

        # Rim light — backlight silhouette
        bpy.ops.object.light_add(type='AREA', location=(-600, 300, 400))
        rim = bpy.context.active_object
        rim.name = "RIM_LIGHT"
        rim.data.energy = 30000
        rim.data.size = 150
        rim.data.color = (0.3, 0.5, 1.0)
        rim.rotation_euler = (math.radians(50), 0, math.radians(150))
        link_to_collection(rim, "COLL_CAM_LIGHT")

        # Portal emission helper — point light inside well
        bpy.ops.object.light_add(type='POINT', location=(0, 0, 100))
        portal_light = bpy.context.active_object
        portal_light.name = "PORTAL_EMISSION"
        portal_light.data.energy = 100000
        portal_light.data.color = (0.0, 0.8, 1.0)  # Cyan
        portal_light.data.shadow_soft_size = 50
        link_to_collection(portal_light, "COLL_CAM_LIGHT")

        # Animate portal pulse: sin wave on energy
        portal_light.data.energy = 80000
        portal_light.data.keyframe_insert(data_path="energy", frame=1)
        portal_light.data.energy = 150000
        portal_light.data.keyframe_insert(data_path="energy", frame=72)
        portal_light.data.energy = 80000
        portal_light.data.keyframe_insert(data_path="energy", frame=144)
        portal_light.data.energy = 200000
        portal_light.data.keyframe_insert(data_path="energy", frame=216)
        portal_light.data.energy = 120000
        portal_light.data.keyframe_insert(data_path="energy", frame=288)

        # Make the keyframes cycle (Blender 5.0 layered actions)
        for fc in get_fcurves(portal_light.data.animation_data.action):
            mod = fc.modifiers.new('CYCLES')

        return log_phase("Lighting", True, "key+rim+portal, pulse anim")
    except Exception as e:
        return log_phase("Lighting", False, str(e)[:80])


# ============================================================
# PHASE 8: CAMERA + ANIMATION (Re ~125)
# ============================================================
def phase_camera():
    """Cinematic fly-through camera on bezier path."""
    try:
        # Camera
        bpy.ops.object.camera_add(location=(0, -800, -20))
        cam = bpy.context.active_object
        cam.name = "CAM_MAIN"
        cam.data.lens = 28
        cam.data.clip_end = 5000
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = 4.0
        bpy.context.scene.camera = cam
        link_to_collection(cam, "COLL_CAM_LIGHT")

        # Camera path — bezier curve for fly-through
        coords = [
            Vector((0, -800, -20)),    # F000: low over water
            Vector((0, -500, 30)),     # approach
            Vector((0, -200, 80)),     # F072: ring in frame
            Vector((0, -50, 100)),     # F168: close to ring
            Vector((0, 0, 150)),       # entering portal
            Vector((0, 0, 300)),       # F288: through beam, reveal lattice
        ]

        curve_data = bpy.data.curves.new("CAM_PATH", type='CURVE')
        curve_data.dimensions = '3D'
        spline = curve_data.splines.new('BEZIER')
        spline.bezier_points.add(len(coords) - 1)

        for i, co in enumerate(coords):
            bp = spline.bezier_points[i]
            bp.co = co
            bp.handle_left_type = 'AUTO'
            bp.handle_right_type = 'AUTO'

        path_obj = bpy.data.objects.new("CAM_PATH", curve_data)
        bpy.context.scene.collection.objects.link(path_obj)
        link_to_collection(path_obj, "COLL_CAM_LIGHT")

        # Follow Path constraint
        follow = cam.constraints.new('FOLLOW_PATH')
        follow.target = path_obj
        follow.use_curve_follow = True
        follow.forward_axis = 'FORWARD_Y'
        follow.up_axis = 'UP_Z'

        # Animate path offset
        path_obj.data.path_duration = 288
        follow.offset_factor = 0.0
        follow.keyframe_insert(data_path="offset_factor", frame=1)
        follow.offset_factor = 1.0
        follow.keyframe_insert(data_path="offset_factor", frame=288)

        # Make offset linear (Blender 5.0 layered actions)
        if cam.animation_data and cam.animation_data.action:
            for fc in get_fcurves(cam.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'

        # Track To target (portal center)
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 100))
        target = bpy.context.active_object
        target.name = "PORTAL_CENTER"
        link_to_collection(target, "COLL_CAM_LIGHT")

        track = cam.constraints.new('TRACK_TO')
        track.target = target
        track.track_axis = 'TRACK_NEGATIVE_Z'
        track.up_axis = 'UP_Y'

        return log_phase("Camera", True, "fly-through path, 288 frames")
    except Exception as e:
        return log_phase("Camera", False, str(e)[:80])


# ============================================================
# PHASE 9: RENDER SETTINGS (Re < 27 — laminar)
# ============================================================
def phase_render_settings():
    """Cycles render config with AOVs."""
    try:
        scene = bpy.context.scene
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'GPU'
        scene.cycles.samples = 512
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'

        # Motion blur
        scene.render.use_motion_blur = True
        scene.render.motion_blur_shutter = 0.4

        # Volumes
        scene.cycles.volume_step_rate = 1.0
        scene.cycles.volume_max_steps = 256

        # Color management
        scene.view_settings.view_transform = 'Filmic'
        scene.view_settings.look = 'Medium High Contrast'

        # Frame range
        scene.frame_start = 1
        scene.frame_end = 288
        scene.render.fps = 24

        # Resolution
        scene.render.resolution_x = 1920
        scene.render.resolution_y = 1080
        scene.render.resolution_percentage = 100

        # Output
        scene.render.filepath = "//../../RENDER/FINAL_LOCKED/"
        scene.render.image_settings.file_format = 'OPEN_EXR'

        # Enable passes
        vl = scene.view_layers[0]
        vl.use_pass_emit = True
        vl.use_pass_mist = True
        vl.use_pass_z = True
        vl.use_pass_cryptomatte_object = True

        return log_phase("Render Settings", True, "Cycles GPU, 512spp, 1920x1080")
    except Exception as e:
        return log_phase("Render Settings", False, str(e)[:80])


# ============================================================
# PHASE 10: COMPOSITING (Re ~125 — transitional)
# ============================================================
def phase_compositing():
    """Glare, lens distortion, vignette — Blender 5.0 node group compositor."""
    try:
        scene = bpy.context.scene
        scene.use_nodes = True

        # Blender 5.0: compositor uses node groups, not scene.node_tree
        tree = bpy.data.node_groups.new("AEON_COMPOSITOR", 'CompositorNodeTree')
        scene.compositing_node_group = tree
        nodes = tree.nodes
        links = tree.links

        # Input: Render Layers
        rl = nodes.new('CompositorNodeRLayers')
        rl.location = (0, 400)

        # Output: NodeGroupOutput (replaces CompositorNodeComposite in 5.0)
        out = nodes.new('NodeGroupOutput')
        out.location = (1200, 400)

        # Viewer for preview
        viewer = nodes.new('CompositorNodeViewer')
        viewer.location = (1200, 200)

        # Glare — Blender 5.0: settings are socket inputs, not node attrs
        glare = nodes.new('CompositorNodeGlare')
        glare.location = (400, 400)
        glare.inputs['Threshold'].default_value = 2.0
        glare.inputs['Strength'].default_value = 0.8
        links.new(rl.outputs['Image'], glare.inputs['Image'])

        # Lens distortion (subtle barrel)
        lens = nodes.new('CompositorNodeLensdist')
        lens.location = (600, 400)
        lens.inputs['Distortion'].default_value = -0.01
        links.new(glare.outputs['Image'], lens.inputs['Image'])

        # Vignette via ellipse mask + blur
        ellipse = nodes.new('CompositorNodeEllipseMask')
        ellipse.location = (600, 100)
        ellipse.width = 0.85
        ellipse.height = 0.85

        blur_v = nodes.new('CompositorNodeBlur')
        blur_v.location = (800, 100)
        blur_v.inputs['Size'].default_value = (200, 200)
        links.new(ellipse.outputs['Mask'], blur_v.inputs['Image'])

        # AlphaOver for vignette blend (replaces MixRGB in 5.0)
        vignette = nodes.new('CompositorNodeAlphaOver')
        vignette.location = (1000, 400)
        vignette.inputs['Fac'].default_value = 0.3
        links.new(lens.outputs['Image'], vignette.inputs[1])
        links.new(blur_v.outputs['Image'], vignette.inputs[2])

        # Connect to outputs
        links.new(vignette.outputs['Image'], viewer.inputs['Image'])
        # NodeGroupOutput gets auto-socket from first link
        tree.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        links.new(vignette.outputs['Image'], out.inputs['Image'])

        return log_phase("Compositing", True, "glare+lens+vignette (5.0 node group)")
    except Exception as e:
        return log_phase("Compositing", False, str(e)[:80])


# ============================================================
# PHASE 11: PORTAL SPIN ANIMATION (Re ~125)
# ============================================================
def phase_portal_animation():
    """Rotate portal inner rings + lattice pulse."""
    try:
        # Rotate portal well
        portal = bpy.data.objects.get("PORTAL_WELL")
        if portal:
            portal.rotation_euler = (0, 0, 0)
            portal.keyframe_insert(data_path="rotation_euler", frame=1)
            portal.rotation_euler = (0, 0, math.radians(360))
            portal.keyframe_insert(data_path="rotation_euler", frame=288)
            # Make linear (Blender 5.0 layered actions)
            if portal.animation_data and portal.animation_data.action:
                for fc in get_fcurves(portal.animation_data.action):
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
                    fc.modifiers.new('CYCLES')

        # Counter-rotate lattice
        lattice = bpy.data.objects.get("ENERGY_LATTICE")
        if lattice:
            lattice.rotation_euler = (0, 0, 0)
            lattice.keyframe_insert(data_path="rotation_euler", frame=1)
            lattice.rotation_euler = (0, 0, math.radians(-720))
            lattice.keyframe_insert(data_path="rotation_euler", frame=288)
            if lattice.animation_data and lattice.animation_data.action:
                for fc in get_fcurves(lattice.animation_data.action):
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
                    fc.modifiers.new('CYCLES')

        # Scale pulse on lattice
        if lattice:
            lattice.scale = (1, 1, 1)
            lattice.keyframe_insert(data_path="scale", frame=1)
            lattice.scale = (1.1, 1.1, 1.1)
            lattice.keyframe_insert(data_path="scale", frame=36)
            lattice.scale = (0.95, 0.95, 0.95)
            lattice.keyframe_insert(data_path="scale", frame=72)
            lattice.scale = (1, 1, 1)
            lattice.keyframe_insert(data_path="scale", frame=108)

        return log_phase("Portal Animation", True, "spin+counter-spin+pulse")
    except Exception as e:
        return log_phase("Portal Animation", False, str(e)[:80])


# ============================================================
# MASTER BUILD SEQUENCE
# ============================================================
def build_aeon_well():
    """Execute all phases in ternary-tracked order."""
    print("\n" + "=" * 60)
    print("  AEON WELL — NovaX Ternary Build System")
    print("  3-5-7-13 Harmonic Constants Active")
    print("=" * 60 + "\n")

    clear_scene()

    phases = [
        ("Collections",       phase_collections),
        ("Ocean",             phase_ocean),
        ("Atmosphere",        phase_atmosphere),
        ("Ring Base",         phase_ring_base),
        ("City Belt",         phase_city_belt),
        ("Portal",            phase_portal),
        ("Lighting",          phase_lighting),
        ("Camera",            phase_camera),
        ("Render Settings",   phase_render_settings),
        ("Compositing",       phase_compositing),
        ("Portal Animation",  phase_portal_animation),
    ]

    results = []
    for name, fn in phases:
        print(f"\n--- Phase: {name} ---")
        t = fn()
        results.append(t)

    # Summary
    total = len(results)
    success = sum(1 for r in results if r == 1)
    failed = sum(1 for r in results if r == -1)

    print("\n" + "=" * 60)
    print(f"  BUILD COMPLETE: {success}/{total} phases trit +1")
    if failed:
        print(f"  FAILED: {failed} phases trit -1")
    print("=" * 60)

    # Save the blend file
    blend_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "BLEND", "AEON_WELL_SCENE_01_v1.blend"
    )
    try:
        os.makedirs(os.path.dirname(blend_path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)
        print(f"\n  Saved: {blend_path}")
    except Exception as e:
        print(f"\n  Save error: {e}")

    return success, total


# Run
if __name__ == "__main__":
    build_aeon_well()
