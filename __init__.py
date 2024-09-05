import bpy
import requests
import os

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

        mfilepath = bpy.path.abspath(strip.directory + strip.name)

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


def register():
    bpy.utils.register_class(RemoveBackgroundOperator)
    bpy.types.SEQUENCER_MT_context_menu.append(menu_remove_bg)


def unregister():
    bpy.utils.unregister_class(RemoveBackgroundOperator)
    bpy.types.SEQUENCER_MT_context_menu.remove(menu_remove_bg)


if __name__ == "__main__":
    register()