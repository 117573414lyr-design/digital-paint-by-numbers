from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

Point = tuple[float, float]
Segment = tuple[Point, Point]


def shared_boundary_segments(indexed: np.ndarray) -> list[Segment]:
    """Create each color boundary exactly once from the indexed raster."""
    h, w = indexed.shape
    segments: set[Segment] = set()

    def add(a: Point, b: Point) -> None:
        segments.add((a, b) if a <= b else (b, a))

    # Outer frame.
    for x in range(w):
        add((x, 0), (x + 1, 0))
        add((x, h), (x + 1, h))
    for y in range(h):
        add((0, y), (0, y + 1))
        add((w, y), (w, y + 1))

    # Vertical boundaries between left/right pixels.
    diff_v = indexed[:, 1:] != indexed[:, :-1]
    ys, xs = np.nonzero(diff_v)
    for y, x in zip(ys.tolist(), xs.tolist()):
        xx = x + 1
        add((xx, y), (xx, y + 1))

    # Horizontal boundaries between top/bottom pixels.
    diff_h = indexed[1:, :] != indexed[:-1, :]
    ys, xs = np.nonzero(diff_h)
    for y, x in zip(ys.tolist(), xs.tolist()):
        yy = y + 1
        add((x, yy), (x + 1, yy))

    return sorted(segments)


def chain_segments(segments: list[Segment]) -> list[list[Point]]:
    """Chain non-branching boundary segments into polylines."""
    graph: dict[Point, set[Point]] = defaultdict(set)
    for a, b in segments:
        graph[a].add(b)
        graph[b].add(a)

    unused = {frozenset((a, b)) for a, b in segments}
    paths: list[list[Point]] = []

    def walk(start: Point, nxt: Point) -> list[Point]:
        path = [start, nxt]
        unused.discard(frozenset((start, nxt)))
        prev, cur = start, nxt
        while True:
            candidates = [p for p in graph[cur] if p != prev and frozenset((cur, p)) in unused]
            if len(graph[cur]) != 2 or not candidates:
                break
            following = candidates[0]
            path.append(following)
            unused.discard(frozenset((cur, following)))
            prev, cur = cur, following
            if cur == start:
                break
        return path

    # Start at junctions/endpoints so intersections remain exact.
    for point, neighbors in graph.items():
        if len(neighbors) == 2:
            continue
        for neighbor in list(neighbors):
            edge = frozenset((point, neighbor))
            if edge in unused:
                paths.append(walk(point, neighbor))

    # Closed loops have degree 2 everywhere.
    while unused:
        edge = next(iter(unused))
        a, b = tuple(edge)
        paths.append(walk(a, b))

    return paths


def chaikin(points: list[Point], iterations: int = 2) -> list[Point]:
    """Corner-cutting smoother used only between exact junction endpoints."""
    if len(points) < 4 or iterations <= 0:
        return points
    closed = points[0] == points[-1]
    out = points[:]
    for _ in range(iterations):
        src = out
        dst: list[Point] = [] if closed else [src[0]]
        limit = len(src) - 1
        for i in range(limit):
            p, q = src[i], src[i + 1]
            q1 = (0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1])
            q2 = (0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1])
            dst.extend((q1, q2))
        if closed:
            dst.append(dst[0])
        else:
            dst.append(src[-1])
        out = dst
    return out


def shared_boundary_paths(indexed: np.ndarray, smooth_iterations: int = 2) -> list[list[Point]]:
    paths = chain_segments(shared_boundary_segments(indexed))
    return [chaikin(path, smooth_iterations) for path in paths]
