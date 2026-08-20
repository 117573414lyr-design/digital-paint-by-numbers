import numpy as np

from digital_paint.core.geometry import (
    count_self_intersections,
    geometry_metrics,
    polygon_area,
    simplify_closed_boundary,
)


def test_simplify_closed_boundary_preserves_area():
    boundary = np.array([
        [0.0, 0.0], [2.0, 0.0], [4.0, 0.0], [6.0, 0.0],
        [6.0, 4.0], [4.0, 4.0], [2.0, 4.0], [0.0, 4.0], [0.0, 0.0],
    ])
    simplified = simplify_closed_boundary(boundary, epsilon=0.5, max_area_error=0.05)
    assert np.allclose(simplified[0], simplified[-1])
    assert polygon_area(simplified[:-1]) > 20.0
    metrics = geometry_metrics(boundary, simplified)
    assert metrics.area_error_ratio <= 0.05
    assert metrics.self_intersections == 0


def test_self_intersection_detection():
    bow = np.array([[0.0, 0.0], [4.0, 4.0], [0.0, 4.0], [4.0, 0.0], [0.0, 0.0]])
    assert count_self_intersections(bow) == 1
