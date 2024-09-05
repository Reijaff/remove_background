import importlib.util
import bpy
import sys
import subprocess
from PIL import Image
import site
import requests
import os

bl_info = {
    "name": "Remove Background",
    "author": "tintwotin",
    "version": (1, 0),
    "blender": (3, 40, 0),
    "location": "Sequencer > Strip > Remove Background",
    "description": "Removes Background of a VSE strip",
    "warning": "",
    "doc_url": "",
    "category": "Sequencer",
}

app_path = site.USER_SITE

if app_path not in sys.path:
    sys.path.append(app_path)

class OPERATOR_OT_RemoveBackgroundOperator(bpy.types.Operator):
    """Remove the background from a VSE strip and import the resulting images as a new strip."""

    bl_idname = "vse.remove_background"
    bl_label = "Remove Background"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.space_data.type == "SEQUENCE_EDITOR" and context.scene.sequence_editor.active_strip

    def execute(self, context):
        strip = context.scene.sequence_editor.active_strip

        if strip.type not in ("MOVIE", "IMAGE"):
            self.report({"ERROR"}, "Can only remove background from movie or image strips")
            return {"CANCELLED"}

        original_scene = context.scene
        new_scene = bpy.data.scenes.new("Export Scene")
        context.window.scene = new_scene
        new_scene.sequence_editor_create()

        # Create new strip in the temporary scene, copying properties from the original
        new_strip = new_scene.sequence_editor.sequences.new_movie(
            name=strip.name, filepath=bpy.path.abspath(strip.filepath), channel=1, frame_start=1
        ) if strip.type == "MOVIE" else new_scene.sequence_editor.sequences.new_image(
            name=strip.name, filepath=bpy.path.abspath(strip.directory + strip.name), channel=1, frame_start=1
        )

        new_strip.frame_final_duration = strip.frame_final_duration

        # Set output path for rendered frames
        output_path = os.path.join(
            os.path.dirname(bpy.path.abspath(strip.filepath)), 
            f"{os.path.basename(strip.filepath)}_image_sequence/"
        )
        os.makedirs(output_path, exist_ok=True)  # Ensure the output directory exists

        new_scene.frame_start = 1
        new_scene.frame_end = new_strip.frame_final_duration
        new_scene.render.filepath = output_path
        new_scene.render.image_settings.file_format = "PNG"

        self.report({"INFO"}, "Saving images to disk.")
        bpy.ops.render.render(animation=True, scene=new_scene.name)

        files = []
        for i in range(1, new_strip.frame_final_duration + 1):
            filepath = os.path.join(output_path, f"{i:04d}.png")
            file_name = f"{i:04d}.png"
            msg = f"{i}/{new_strip.frame_final_duration}"
            self.report({"INFO"}, msg)
            try:
                with open(filepath, 'rb') as f:
                    response = requests.post("http://localhost:7000/api/remove", files={'file': f})
                    response.raise_for_status()  # Check for HTTP errors

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                files.append(file_name)
            except requests.exceptions.RequestException as e:
                self.report({"WARNING"}, f"Error processing frame {i}: {e}")

        # Delete the temporary scene
        bpy.data.scenes.remove(new_scene)
        context.window.scene = original_scene

        # Create the new image strip in the original scene
        image_strip = original_scene.sequence_editor.sequences.new_image(
            name=f"Removed_Background_{os.path.basename(strip.filepath)}",
            filepath=os.path.join(output_path, "0001.png"),  # Use the first frame as reference
            channel=strip.channel + 1,
            frame_start=strip.frame_final_start,
        )
        for f in files:
            image_strip.elements.append(f)
        image_strip.frame_final_duration = strip.frame_final_duration

        bpy.ops.sequencer.refresh_all()
        return {"FINISHED"}

def menu_append(self, context):
    layout = self.layout
    layout.separator()
    layout.operator(
        OPERATOR_OT_RemoveBackgroundOperator.bl_idname, icon="OUTLINER_OB_IMAGE"
    )


def register():
    bpy.utils.register_class(OPERATOR_OT_RemoveBackgroundOperator)
    bpy.types.SEQUENCER_MT_strip.append(menu_append)


def unregister():
    bpy.utils.unregister_class(OPERATOR_OT_RemoveBackgroundOperator)
    bpy.types.SEQUENCER_MT_strip.remove(menu_append)


if __name__ == "__main__":
    register()