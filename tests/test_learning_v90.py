from digital_paint.core.learning import ReferenceLibrary, ReferenceProfile, available_acceleration_providers


def test_reference_library_recommends_from_approved_samples(tmp_path):
    library = ReferenceLibrary(tmp_path / "references.json")
    library.add(ReferenceProfile("autumn-1", "landscape", 12.0, 24, 40, 0.55, 0.30))
    library.add(ReferenceProfile("autumn-2", "landscape", 18.0, 36, 30, 0.75, 0.45))
    result = library.recommend(megapixels=14.0, detail_score=0.60, edge_density=0.34, category="landscape")
    assert result is not None
    assert 24 <= result.target_colors <= 36
    assert 30 <= result.min_region_area <= 40
    assert result.source_sample_ids
    assert 0.0 <= result.confidence <= 1.0


def test_acceleration_always_has_cpu():
    assert "CPU" in available_acceleration_providers()
