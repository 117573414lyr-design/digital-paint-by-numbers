import numpy as np

from digital_paint.core.smoothing import cubic_bezier_controls, smooth_closed_boundary


def test_smoothing_preserves_closure_and_topology():
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], dtype=float)
    result = smooth_closed_boundary(square, iterations=1, max_area_error=0.2)
    assert np.allclose(result.points[0], result.points[-1])
    assert result.self_intersections == 0


def test_smoothing_rejects_excessive_area_change():
    thin = np.array([[0, 0], [20, 0], [20, 1], [0, 1], [0, 0]], dtype=float)
    result = smooth_closed_boundary(thin, iterations=3, max_area_error=0.001)
    assert not result.accepted
    assert np.array_equal(result.points, thin)


def test_bezier_segments_share_endpoints():
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], dtype=float)
    segments = cubic_bezier_controls(square)
    assert len(segments) == 4
    for i, seg in enumerate(segments):
        next_seg = segments[(i + 1) % len(segments)]
        assert np.allclose(seg[3], next_seg[0])
