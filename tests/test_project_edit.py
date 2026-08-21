import numpy as np

from digital_paint.core.editing import EditSession, EditState, recolor_region
from digital_paint.core.project_edit import ProjectEditor
from digital_paint.core.project_store import ProjectMeta, ProjectStore


def test_project_editor_persists_color_map_and_journal(tmp_path):
    store = ProjectStore(tmp_path)
    meta = ProjectMeta(name="demo")
    color_id = np.array([[0, 0], [1, 1]], dtype=np.int32)
    store.save(meta, color_id=color_id)

    editor = ProjectEditor(store, meta, EditSession(EditState(color_id=color_id.copy(), labels=[])))
    editor.apply("recolor", lambda state: recolor_region(state, 0, 1))
    editor.save(snapshot_label="before-save")

    arrays = store.load_arrays()
    assert np.all(arrays["color_id"] == 1)
    actions = [entry["action"] for entry in store.journal()]
    assert "edit" in actions
    assert "save_edit_state" in actions
