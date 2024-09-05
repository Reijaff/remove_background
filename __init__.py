import bpy
import requests
import os
import hashlib
import random

bl_info = {
    "name": "Remove Background",
    "author": "reijaff",
    "version": (1, 0),
    "blender": (3, 40, 0),
    "location": "Sequencer > Strip > Remove Background",
    "description": "Removes Background of a VSE strip",
    "warning": "",
    "doc_url": "",
    "category": "Sequencer",
}


class SnapshotRenderInsertOperator(bpy.types.Operator):
    bl_idname = "vse.snapshot_render_insert"
    bl_label = "Snapshot Current Render Image"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.space_data.type == "SEQUENCE_EDITOR"

    def execute(self, context):
        # Store original file format to restore later
        original_file_format = bpy.context.scene.render.image_settings.file_format

        # Temporarily set file format to PNG
        bpy.context.scene.render.image_settings.file_format = "PNG"

        bpy.context.scene.render.film_transparent = True

        # Generate random hash for filename
        random_hash = hashlib.sha256(
            str(random.getrandbits(256)).encode("utf-8")
        ).hexdigest()[:8]
        new_filepath = bpy.path.abspath(f"//pics/{random_hash}.png")

        # Set render output path and render
        bpy.context.scene.render.filepath = new_filepath
        bpy.ops.render.render(write_still=True)

        # Add rendered image to sequencer
        scene = bpy.context.scene
        sequencer = scene.sequence_editor
        if sequencer:
            # Find the next available channel
            channels = (
                [s.channel for s in bpy.context.sequences]
                if bpy.context.sequences
                else []
            )
            next_channel = max(channels) + 1 if channels else 1

            # Create new image sequence strip
            strip = sequencer.sequences.new_image(
                name=random_hash,
                filepath=new_filepath,
                channel=next_channel,
                frame_start=scene.frame_current,
            )

            # Set strip duration (adjust as needed)
            strip.frame_final_duration = 240

            # Refresh sequencer
            bpy.ops.sequencer.refresh_all()
        else:
            print("Error: No sequencer found in the current scene")

        # Restore original file format
        bpy.context.scene.render.image_settings.file_format = original_file_format

        return {"FINISHED"}


class RemoveBackgroundOperator(bpy.types.Operator):
    """Remove the background from a VSE strip and import the resulting images as a new strip."""

    bl_idname = "vse.remove_background"
    bl_label = "Remove Background"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.space_data.type == "SEQUENCE_EDITOR"
            and context.scene.sequence_editor.active_strip
        )

    def execute(self, context):
        strip = context.scene.sequence_editor.active_strip

        if strip.type != "IMAGE":  # Simplified check
            self.report({"ERROR"}, "Can only remove background from image strips")
            return {"CANCELLED"}

        mfilepath = bpy.path.abspath(strip.directory + strip.elements[0].filename)

        new_filepath = bpy.path.abspath(
            "//pics/" + os.path.splitext(strip.name)[0] + "_transparent.png"
        )  # Use os.path.splitext to handle extensions

        try:
            with open(mfilepath, "rb") as f:
                response = requests.post(
                    "http://localhost:7000/api/remove", files={"file": f}
                )
                response.raise_for_status()

            with open(new_filepath, "wb") as f:
                f.write(response.content)

        except requests.exceptions.RequestException as e:
            self.report({"WARNING"}, f"Error processing: {e}")
            return {"CANCELLED"}  # Stop execution on error

        bpy.ops.sequencer.duplicate_move(
            SEQUENCER_OT_duplicate={},
            TRANSFORM_OT_seq_slide={
                "value": (0, 1),
                "snap": True,  # Other options are likely defaults, can be removed
            },
        )

        new_strip = context.scene.sequence_editor.active_strip

        new_strip.directory = os.path.dirname(new_filepath)
        new_strip.elements[0].filename = os.path.basename(new_filepath)

        bpy.ops.sequencer.refresh_all()

        return {"FINISHED"}


def menu_remove_bg(self, context):
    self.layout.separator()
    self.layout.operator(RemoveBackgroundOperator.bl_idname, icon="OUTLINER_OB_IMAGE")
    self.layout.operator(SnapshotRenderInsertOperator.bl_idname)


def register():
    bpy.utils.register_class(RemoveBackgroundOperator)
    bpy.utils.register_class(SnapshotRenderInsertOperator)
    bpy.types.SEQUENCER_MT_context_menu.append(menu_remove_bg)


def unregister():
    bpy.utils.unregister_class(RemoveBackgroundOperator)
    bpy.utils.unregister_class(SnapshotRenderInsertOperator)
    bpy.types.SEQUENCER_MT_context_menu.remove(menu_remove_bg)


if __name__ == "__main__":
    register()