# This Blender Addon provides an easy way to render the wireframe of
# the current scene.
# Copyright (C) 2023  Jonas Wischeropp
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

bl_info = {
    "name": "Render Wireframe",
    "author": "Jonas Wischeropp",
    "version": (1, 2),
    "blender": (2, 82, 0),
    "location": "Render Properties > Wireframe Renderer or Render > Render Wireframe (Image|Animation)",
    "description": "Renders the wireframe of the active scene",
    "warning": "",
    "doc_url": "",
    "category": "Render",
}

import bpy

# Renders the wireframe of the scene from the active camera by using view port rendering.
# This script automates and extends the technique described in the following article by D. Austin:
# https://www.artstation.com/blogs/daustindoodles/GKpw/quick-and-easy-wireframe-renders-in-blender

# Helper functions
def get_3D_view_space(context):
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            return area.spaces[0]
    return None

def swap(attr):
    for t in attr:
        old = getattr(t[0], t[1])
        setattr(t[0], t[1], t[2])
        t[2] = old

# Actual logic
def render_wireframe(context, animation, line_width):
    space = get_3D_view_space(context)
    overlay = space.overlay
    renderer = context.scene.render
    delay_needed = line_width != bpy.context.preferences.view.ui_line_width
    objects = bpy.data.objects

    old_data = {
        'overlay_attrs': [attr for attr in dir(overlay) if attr.startswith("show_")],
        'selected_objects': context.selected_objects,
        'other_attrs': [
            [renderer, "film_transparent", True],
            [renderer, "engine", 'CYCLES'],
            [space.shading, "type", 'RENDERED'],
            [bpy.context.preferences.view, "ui_line_width", line_width]
        ],
        'view_matrix': space.region_3d.view_matrix.copy(),
        'view_pers': space.region_3d.view_perspective,
        'visible': [obj.hide_get() for obj in objects],
        'optimal_display': [],# modifiers where optimal_display has to be toggled
        'show_viewport' : [],# modifiers where show_viewport has to be toggled
        'render_levels' : [],# (modifier, old level)
    }
    old_data['overlay_values'] = [getattr(overlay, attr) for attr in old_data['overlay_attrs']]

    # Setup settings for rendering
    for obj in old_data['selected_objects']:
        obj.select_set(False)
        
    for attr in old_data['overlay_attrs']:
        setattr(overlay, attr, False)
    overlay.show_wireframes = True
    overlay.show_overlays = True

    swap(old_data['other_attrs'])

    space.region_3d.view_perspective = 'CAMERA'
    
    for obj in objects:
        if obj.name in context.view_layer.objects:
            obj.hide_set(obj.hide_render)
    
    optimal_display = context.scene.wireframe_renderer_properties.optimal_display
    render_levels = context.scene.wireframe_renderer_properties.render_levels
    optimal = None if optimal_display == 'CUSTOM' else optimal_display == 'ON'
    for obj in objects:
        if not obj.hide_get():
            for modifier in obj.modifiers:
                if modifier.show_render != modifier.show_viewport:
                    modifier.show_viewport = modifier.show_render
                    old_data['show_viewport'].append(modifier)
                if optimal != None and hasattr(modifier, 'show_only_control_edges'):
                    if modifier.show_only_control_edges != optimal:
                        modifier.show_only_control_edges = optimal
                        old_data['optimal_display'].append(modifier)
                if render_levels and hasattr(modifier, 'render_levels'):
                    if modifier.levels != modifier.render_levels:
                        old_data['render_levels'].append((modifier, modifier.levels))
                        modifier.levels = modifier.render_levels


    def render_and_reset():
        # Render
        bpy.ops.render.opengl(view_context=True, animation=animation)
        
        # Restore old settings from before rendering
        for modifier in old_data['optimal_display']:
            modifier.show_only_control_edges = not modifier.show_only_control_edges
        for modifier in old_data['show_viewport']:
            modifier.show_viewport = not modifier.show_viewport
        for modifier, level in old_data['render_levels']:
            modifier.levels = level

        for obj, visible in zip(objects, old_data["visible"]):
            obj.hide_set(visible)
        
        space.region_3d.view_matrix = old_data['view_matrix']
        space.region_3d.view_perspective = old_data['view_pers']
        
        swap(old_data['other_attrs'])
        
        for attr, old_value in zip(old_data['overlay_attrs'], old_data['overlay_values']):
            setattr(overlay, attr, old_value)
        
        for obj in old_data['selected_objects']:
            if obj.name in context.view_layer.objects:
                obj.select_set(True)

    # A short delay is needed for blender to update the viewport
    # incase the ui_line_width for rendering is not the same as the one currently used.
    if delay_needed:
        bpy.app.timers.register(render_and_reset, first_interval=0.01)
    else:
        render_and_reset()

    # Show render    
    bpy.ops.render.view_show('INVOKE_DEFAULT')

class WireframeRenderer(bpy.types.Operator):
    """Renders the wireframe of the active scene"""
    bl_idname="render.wireframe"
    bl_label="Render Wireframe Image"
    
    animation: bpy.props.BoolProperty(
        name="Animation",
        description="True: Render Animation, False: Render Image",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        space = get_3D_view_space(context)
        if space == None:
            cls.poll_message_set("A 3D View needs to be opened for the rendering process to work.")
        return space != None
    
    def execute(self, context):
        render_wireframe(context, self.animation, context.scene.wireframe_renderer_properties.line_thickness)
        return {'FINISHED'}

def render_wireframe_image_op(self, context):
    self.layout.operator(WireframeRenderer.bl_idname, text="Render Wireframe Image").animation = False
def render_wireframe_animation_op(self, context):
    self.layout.operator(WireframeRenderer.bl_idname, text="Render Wireframe Animation").animation = True

class WireframeRendererProperties(bpy.types.PropertyGroup):
    line_thickness: bpy.props.EnumProperty(
        name="Line Thickness",
        description="Line Thickness\nPreferences>Interface>Display>Line Width",
        items=[
            ('AUTO', 'Auto', 'Uses width defined under Preferences>Interface>Display>Line Width'),
            ('THICK', 'Thick', 'Thicker Lines'),
            ('THIN', 'Thin', 'Thin Lines'),
        ],
        default='AUTO',
    )
    optimal_display: bpy.props.EnumProperty(
        name="Optimal Display",
        description="Should 'Optimal Display' be used on Subdivision Surface Modifiers",
        items=[
            ('CUSTOM', "As is", "Does not change Optimal Display setting"),
            ('ON', "On", "Renders all with Optimal Display"),
            ('OFF', "Off", "Renders all without Optimal Display"),
        ],
        default='CUSTOM'
    )
    render_levels: bpy.props.BoolProperty(
        name="Render Levels",
        description="Use render or else viewport subdivision level",
        default=False,
    )

class SettingsPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_settings_panel"
    bl_label = "Wireframe Renderer"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'render'

    def draw(self, context):
        layout = self.layout
        obj = context.object
        props = context.scene.wireframe_renderer_properties

        layout.label(text="Line Thickness")
        layout.prop(props, 'line_thickness', expand=True)
        layout.label(text="Optimal Display")
        layout.prop(props, 'optimal_display', expand=True)
        layout.prop(props, 'render_levels')

        layout.operator('render.wireframe', text="Render Image").animation = False
        layout.operator('render.wireframe', text="Render Animation").animation = True

classes = (
    WireframeRenderer,
    WireframeRendererProperties,
    SettingsPanel,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_render.append(render_wireframe_image_op)
    bpy.types.TOPBAR_MT_render.append(render_wireframe_animation_op)

    bpy.types.Scene.wireframe_renderer_properties = bpy.props.PointerProperty(type=WireframeRendererProperties)
    
def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    bpy.types.TOPBAR_MT_render.remove(render_wireframe_image_op)
    bpy.types.TOPBAR_MT_render.remove(render_wireframe_animation_op)
    
if __name__ == "__main__":
    register()