from pathlib import Path

import yaml


DEFAULT_FRAME_ID = "map"
DEFAULT_THICKNESS = 0.1


def _as_origin(origin):
    if not isinstance(origin, (list, tuple)) or len(origin) < 2:
        raise ValueError("map_origin must contain at least x and y")
    return [
        round(float(origin[0]), 5),
        round(float(origin[1]), 5),
        round(float(origin[2]) if len(origin) > 2 else 0.0, 5),
    ]


def _as_point(point):
    if isinstance(point, dict):
        return {
            "x": float(point.get("x", 0.0)),
            "y": float(point.get("y", 0.0)),
            "z": float(point.get("z", 0.0)),
        }
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        return {
            "x": float(point[0]),
            "y": float(point[1]),
            "z": float(point[2]) if len(point) > 2 else 0.0,
        }
    raise ValueError(f"Invalid point: {point!r}")


def _round_point(point):
    return [round(point["x"], 5), round(point["y"], 5), round(point["z"], 5)]


def _relative_point(point, origin):
    return [
        round(point["x"] - origin[0], 5),
        round(point["y"] - origin[1], 5),
        round(point["z"] - origin[2], 5),
    ]


def _world_point(point, origin):
    source = _as_point(point)
    return {
        "x": round(source["x"] + origin[0], 5),
        "y": round(source["y"] + origin[1], 5),
        "z": round(source["z"] + origin[2], 5),
    }


def _same_point(left, right):
    return (
        round(left["x"], 5) == round(right["x"], 5)
        and round(left["y"], 5) == round(right["y"], 5)
        and round(left["z"], 5) == round(right["z"], 5)
    )


def _normalise_polylines(polylines, default_thickness):
    normalised = []
    for polyline in polylines or []:
        points = [_as_point(point) for point in polyline.get("points", [])]
        if len(points) < 2:
            continue
        normalised.append(
            {
                "points": points,
                "thickness": float(polyline.get("thickness", default_thickness)),
            }
        )
    return normalised


def build_virtual_wall_document(
    polylines,
    map_origin,
    frame_id=DEFAULT_FRAME_ID,
    default_thickness=DEFAULT_THICKNESS,
):
    """Build the YAML document consumed by the old VirtualWallManager.

    The manager stores image-relative coordinates by subtracting the live map
    origin. Keeping the same rule here makes files portable across map poses.
    """
    origin = _as_origin(map_origin)
    normalised = _normalise_polylines(polylines, default_thickness)
    segments = []

    for polyline in normalised:
        points = polyline["points"]
        thickness = round(polyline["thickness"], 5)
        for index in range(len(points) - 1):
            segments.append(
                {
                    "start": _relative_point(points[index], origin),
                    "end": _relative_point(points[index + 1], origin),
                    "thickness": thickness,
                }
            )

    return {
        "virtual_walls": {
            "coordinate_mode": "image_relative",
            "frame_id": frame_id or DEFAULT_FRAME_ID,
            "map_origin": origin,
            "thickness": round(float(default_thickness), 5),
            "segments": segments,
        }
    }


def save_virtual_wall_file(
    path,
    polylines,
    map_origin,
    frame_id=DEFAULT_FRAME_ID,
    default_thickness=DEFAULT_THICKNESS,
):
    target = Path(path).expanduser().resolve()
    if target.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("path must point to a .yaml or .yml file")
    target.parent.mkdir(parents=True, exist_ok=True)
    document = build_virtual_wall_document(polylines, map_origin, frame_id, default_thickness)
    target.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return target


def _segments_to_polylines(segments, origin, default_thickness):
    polylines = []
    for segment in segments or []:
        thickness = float(segment.get("thickness", default_thickness))
        start = _world_point(segment["start"], origin)
        end = _world_point(segment["end"], origin)

        if (
            polylines
            and polylines[-1]["thickness"] == thickness
            and _same_point(polylines[-1]["points"][-1], start)
        ):
            polylines[-1]["points"].append(end)
        else:
            polylines.append({"points": [start, end], "thickness": thickness})
    return polylines


def _legacy_walls_to_polylines(walls, origin, default_thickness):
    polylines = []
    for wall in walls or []:
        points = wall.get("points", [])
        if len(points) < 2:
            continue
        polylines.append(
            {
                "points": [_world_point(point, origin) for point in points],
                "thickness": float(wall.get("thickness", default_thickness)),
            }
        )
    return polylines


def load_virtual_wall_file(path, current_map_origin=None):
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Virtual wall file not found: {source}")

    data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    walls = data.get("virtual_walls")
    if not isinstance(walls, dict):
        raise ValueError("Invalid virtual wall file: missing virtual_walls")

    default_thickness = float(walls.get("thickness", DEFAULT_THICKNESS))
    coordinate_mode = walls.get("coordinate_mode", "absolute")
    origin = [0.0, 0.0, 0.0]
    if coordinate_mode == "image_relative":
        origin = _as_origin(current_map_origin or walls.get("map_origin", [0.0, 0.0, 0.0]))

    polylines = []
    polylines.extend(_legacy_walls_to_polylines(walls.get("walls", []), origin, default_thickness))
    polylines.extend(_segments_to_polylines(walls.get("segments", []), origin, default_thickness))

    return {
        "frame_id": walls.get("frame_id", DEFAULT_FRAME_ID),
        "coordinate_mode": coordinate_mode,
        "map_origin": _as_origin(walls.get("map_origin", [0.0, 0.0, 0.0])),
        "current_map_origin": _as_origin(current_map_origin or origin),
        "thickness": default_thickness,
        "polylines": polylines,
    }
