from pathlib import Path

import numpy as np

from digital_paint.core.project_store import ProjectMeta, ProjectStore
from digital_paint.core.sample_store import SampleStore


def test_project_save_load_and_snapshot(tmp_path: Path):
    store = ProjectStore(tmp_path / "project")
    meta = ProjectMeta(name="demo", colors=24)
    region_id = np.arange(12, dtype=np.int32).reshape(3, 4)
    store.save(meta, region_id=region_id)
    loaded = store.load_meta()
    arrays = store.load_arrays()
    assert loaded.name == "demo"
    assert np.array_equal(arrays["region_id"], region_id)
    snapshot = store.snapshot("before-edit", meta)
    assert snapshot.exists()
    assert store.journal()[-1]["action"] == "snapshot"


def test_sample_store_roundtrip(tmp_path: Path):
    with SampleStore(tmp_path / "samples.db") as store:
        sample_id = store.add(
            kind="reference",
            name="approved-ai-example",
            tags=["linework", "approved"],
            metadata={"colors": 24},
        )
        records = store.search("approved", kind="reference")
        assert records
        assert records[0].id == sample_id
        assert records[0].metadata["colors"] == 24
