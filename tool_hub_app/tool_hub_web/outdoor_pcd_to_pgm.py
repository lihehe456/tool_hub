from __future__ import annotations

import base64
from dataclasses import dataclass
import math
import os
from pathlib import Path
import subprocess
import struct
from typing import Any
import warnings
import zlib

import numpy as np

from tool_hub_web.pcd_to_map import parse_pcd_file


@dataclass(frozen=True)
class OutdoorPcdToPgmOptions:
    z_min: float = 0.0
    z_max: float = 0.4
    flag_pass_through: bool = False
    radius: float = 0.5
    min_neighbors: int = 10
    resolution: float = 0.05
    trajectory_pcd_path: Path | None = None
    sensor_height: float = 0.5
    trajectory_search_radius: float = 2.0
    preview_max_dimension: int = 0


@dataclass(frozen=True)
class OutdoorPcdToPgmResult:
    width: int
    height: int
    resolution: float
    origin: list[float]
    occupancy: list[int]
    raw_point_count: int
    filtered_point_count: int
    trajectory_used: bool
    warnings: list[str]
    preview_png_base64: str
    trajectory_mask: list[int] | None = None

    def to_preview_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "resolution": self.resolution,
            "origin": self.origin,
            "raw_point_count": self.raw_point_count,
            "filtered_point_count": self.filtered_point_count,
            "trajectory_used": self.trajectory_used,
            "warnings": list(self.warnings),
            "preview_png_base64": self.preview_png_base64,
        }


def convert_outdoor_pcd_to_pgm(pcd_path: Path, options: OutdoorPcdToPgmOptions) -> OutdoorPcdToPgmResult:
    _validate_options(options)
    points = _load_points(pcd_path)
    x_min, x_max, y_min, y_max = _bounds(points)
    width = max(int(math.ceil((x_max - x_min) / options.resolution)), 1)
    height = max(int(math.ceil((y_max - y_min) / options.resolution)), 1)

    warnings: list[str] = []
    floor_grid = None
    trajectory_points = None
    trajectory_used = False
    if options.trajectory_pcd_path:
        trajectory_path = Path(options.trajectory_pcd_path).expanduser().resolve()
        if trajectory_path.is_file():
            trajectory = _load_points(trajectory_path)
            trajectory_points = trajectory
            point_cols = np.floor((points[:, 0] - x_min) / options.resolution).astype(np.int64)
            point_rows = np.floor((points[:, 1] - y_min) / options.resolution).astype(np.int64)
            occupied_cells = np.unique(np.column_stack((point_cols, point_rows)), axis=0)
            floor_grid = _build_floor_grid(
                trajectory,
                x_min,
                y_min,
                width,
                height,
                options.resolution,
                options.sensor_height,
                options.trajectory_search_radius,
                occupied_cells,
            )
            trajectory_used = True
        else:
            warnings.append(f"trajectory PCD not found, fallback to absolute Z filter: {trajectory_path}")

    filtered = _filter_by_height(
        points,
        floor_grid,
        x_min,
        y_min,
        width,
        height,
        options,
    )
    filtered = _radius_outlier_filter(filtered, options.radius, options.min_neighbors)
    occupancy = _build_occupancy(filtered, x_min, y_min, width, height, options.resolution)
    trajectory_mask = None
    if trajectory_points is not None:
        trajectory_mask = _build_occupancy(trajectory_points, x_min, y_min, width, height, options.resolution)
    preview = _png_base64_from_occupancy(
        width,
        height,
        occupancy,
        [round(x_min, 6), round(y_min, 6), 0.0],
        options.resolution,
        options.preview_max_dimension,
    )
    return OutdoorPcdToPgmResult(
        width=width,
        height=height,
        resolution=float(options.resolution),
        origin=[round(x_min, 6), round(y_min, 6), 0.0],
        occupancy=occupancy,
        raw_point_count=int(len(points)),
        filtered_point_count=int(len(filtered)),
        trajectory_used=trajectory_used,
        warnings=warnings,
        preview_png_base64=preview,
        trajectory_mask=trajectory_mask,
    )


def export_outdoor_pcd_to_pgm(
    result: OutdoorPcdToPgmResult,
    output_dir: Path,
    map_name: str,
) -> dict[str, str]:
    name = _safe_map_name(map_name)
    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    pgm_path = target_dir / f"{name}.pgm"
    yaml_path = target_dir / f"{name}.yaml"
    pgm_path.write_bytes(_render_pgm(result))
    yaml_path.write_text(_render_yaml(pgm_path.name, result), encoding="utf-8")
    exported = {"pgm_path": str(pgm_path), "yaml_path": str(yaml_path)}
    if result.trajectory_mask:
        overlay_path = target_dir / f"{name}_with_trajectory.ppm"
        overlay_path.write_bytes(_render_trajectory_overlay_ppm(result))
        exported["trajectory_overlay_ppm_path"] = str(overlay_path)
    return exported


def find_cpp_backend() -> Path | None:
    configured = os.environ.get("OUTDOOR_PCD_TO_PGM_BINARY", "")
    candidates = [
        Path(configured).expanduser() if configured else None,
        Path(__file__).resolve().parent / "bin" / "outdoor_pcd_to_pgm",
        Path(__file__).resolve().parent / "build" / "outdoor-pcd-to-pgm" / "outdoor_pcd_to_pgm",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None


def convert_outdoor_pcd_to_pgm_cpp(
    pcd_path: Path,
    output_dir: Path,
    map_name: str,
    options: OutdoorPcdToPgmOptions,
) -> tuple[OutdoorPcdToPgmResult, dict[str, str]]:
    binary = find_cpp_backend()
    if binary is None:
        raise RuntimeError("Linux outdoor PCD2PGM backend is not built")
    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(binary), "--pcd", str(Path(pcd_path).expanduser().resolve()),
        "--output-dir", str(target_dir), "--map-name", str(map_name),
        "--z-min", str(options.z_min), "--z-max", str(options.z_max),
        "--radius", str(options.radius), "--min-neighbors", str(options.min_neighbors),
        "--resolution", str(options.resolution), "--sensor-height", str(options.sensor_height),
        "--trajectory-search-radius", str(options.trajectory_search_radius),
        "--preview-max-dimension", str(options.preview_max_dimension),
    ]
    if options.trajectory_pcd_path:
        command.extend(["--trajectory", str(Path(options.trajectory_pcd_path).expanduser().resolve())])
    if options.flag_pass_through:
        command.append("--negative")
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "C++ outdoor PCD2PGM backend failed")

    summary_path = target_dir / f"{map_name}.summary.txt"
    values = _read_summary(summary_path)
    preview_path = Path(values["preview_pgm"])
    preview_width = int(values["preview_width"])
    preview_height = int(values["preview_height"])
    preview_occupancy = _read_pgm_occupancy(preview_path, preview_width, preview_height)
    preview_resolution = options.resolution * max(
        1,
        int(math.ceil(max(int(values["width"]), int(values["height"])) / max(preview_width, preview_height))),
    )
    result = OutdoorPcdToPgmResult(
        width=int(values["width"]),
        height=int(values["height"]),
        resolution=options.resolution,
        origin=[round(float(values["x_min"]), 6), round(float(values["y_min"]), 6), 0.0],
        occupancy=[],
        raw_point_count=int(values["raw_count"]),
        filtered_point_count=int(values["filtered_count"]),
        trajectory_used=bool(options.trajectory_pcd_path and Path(options.trajectory_pcd_path).is_file()),
        warnings=[],
        preview_png_base64=_png_base64_from_occupancy(
            preview_width,
            preview_height,
            preview_occupancy,
            [round(float(values["x_min"]), 6), round(float(values["y_min"]), 6), 0.0],
            preview_resolution,
            preview_width,
        ),
        trajectory_mask=None,
    )
    exported = {"pgm_path": values["pgm"], "yaml_path": values["yaml"]}
    if values.get("trajectory_overlay_ppm"):
        exported["trajectory_overlay_ppm_path"] = values["trajectory_overlay_ppm"]
    return result, exported


def _read_summary(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    required = {"width", "height", "preview_width", "preview_height", "raw_count", "filtered_count", "x_min", "y_min", "pgm", "yaml", "preview_pgm"}
    missing = required - values.keys()
    if missing:
        raise RuntimeError(f"C++ outdoor PCD2PGM summary is missing: {', '.join(sorted(missing))}")
    return values


def _read_pgm_occupancy(path: Path, width: int, height: int) -> list[int]:
    raw = path.read_bytes()
    marker = raw.find(b"\n255\n")
    if marker < 0:
        raise RuntimeError(f"invalid preview PGM: {path}")
    pixels = raw[marker + len(b"\n255\n"):]
    if len(pixels) < width * height:
        raise RuntimeError(f"preview PGM is truncated: {path}")
    return [100 if value < 128 else 0 for value in pixels[: width * height]]


def _load_points(path: Path) -> np.ndarray:
    source = Path(path).expanduser().resolve()
    points = np.asarray(parse_pcd_file(source), dtype=np.float64)
    if points.size == 0:
        raise ValueError(f"PCD file is empty: {source}")
    if points.ndim != 2 or points.shape[1] < 3:
        raise ValueError(f"invalid PCD point shape {points.shape}: {source}")
    return points[:, :3]


def _validate_options(options: OutdoorPcdToPgmOptions) -> None:
    if not math.isfinite(options.z_min) or not math.isfinite(options.z_max) or options.z_min >= options.z_max:
        raise ValueError("z_min must be finite and less than z_max")
    if not math.isfinite(options.resolution) or options.resolution <= 0:
        raise ValueError("resolution must be greater than 0")
    if not math.isfinite(options.radius) or options.radius < 0:
        raise ValueError("radius must be greater than or equal to 0")
    if int(options.min_neighbors) < 0:
        raise ValueError("min_neighbors must be greater than or equal to 0")
    if not math.isfinite(options.sensor_height):
        raise ValueError("sensor_height must be finite")
    if not math.isfinite(options.trajectory_search_radius) or options.trajectory_search_radius <= 0:
        raise ValueError("trajectory_search_radius must be greater than 0")
    if int(options.preview_max_dimension) < 0:
        raise ValueError("preview_max_dimension must be greater than or equal to 0")


def _bounds(points: np.ndarray) -> tuple[float, float, float, float]:
    return (
        float(np.min(points[:, 0])),
        float(np.max(points[:, 0])),
        float(np.min(points[:, 1])),
        float(np.max(points[:, 1])),
    )


def _build_floor_grid(
    trajectory: np.ndarray,
    origin_x: float,
    origin_y: float,
    width: int,
    height: int,
    resolution: float,
    sensor_height: float,
    search_radius: float,
    occupied_cells: np.ndarray,
) -> tuple[dict[tuple[int, int], float], float]:
    fallback_floor = float(np.mean(trajectory[:, 2]) - sensor_height)
    centers_x = origin_x + (occupied_cells[:, 0].astype(np.float64) + 0.5) * resolution
    centers_y = origin_y + (occupied_cells[:, 1].astype(np.float64) + 0.5) * resolution
    trajectory_xy = trajectory[:, :2]
    radius_squared = search_radius * search_radius
    floor_values: dict[tuple[int, int], float] = {}

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from scipy.spatial import cKDTree

        tree = cKDTree(trajectory_xy)
        query = np.column_stack((centers_x, centers_y))
        neighbors = tree.query_ball_point(query, search_radius)
        for index, indices in enumerate(neighbors):
            cell = (int(occupied_cells[index, 0]), int(occupied_cells[index, 1]))
            value = fallback_floor
            if indices:
                delta = trajectory_xy[indices] - query[index]
                distances_squared = np.sum(delta * delta, axis=1)
                weights = 1.0 / (distances_squared + 1e-6)
                value = float(np.sum(weights * trajectory[indices, 2]) / np.sum(weights) - sensor_height)
            floor_values[cell] = value
        return floor_values, fallback_floor
    except ImportError:
        pass

    for index, (x, y) in enumerate(zip(centers_x, centers_y)):
        cell = (int(occupied_cells[index, 0]), int(occupied_cells[index, 1]))
        value = fallback_floor
        delta = trajectory_xy - np.asarray([x, y])
        distances_squared = np.sum(delta * delta, axis=1)
        mask = distances_squared <= radius_squared
        if np.any(mask):
            weights = 1.0 / (distances_squared[mask] + 1e-6)
            value = float(np.sum(weights * trajectory[mask, 2]) / np.sum(weights) - sensor_height)
        floor_values[cell] = value
    return floor_values, fallback_floor


def _filter_by_height(
    points: np.ndarray,
    floor_grid: tuple[dict[tuple[int, int], float], float] | None,
    origin_x: float,
    origin_y: float,
    width: int,
    height: int,
    options: OutdoorPcdToPgmOptions,
) -> np.ndarray:
    if floor_grid is None:
        mask = (points[:, 2] >= options.z_min) & (points[:, 2] <= options.z_max)
    else:
        floor_values, fallback_floor = floor_grid
        cols = np.floor((points[:, 0] - origin_x) / options.resolution).astype(np.int64)
        rows = np.floor((points[:, 1] - origin_y) / options.resolution).astype(np.int64)
        floor_z = np.fromiter(
            (floor_values.get((int(col), int(row)), fallback_floor) for col, row in zip(cols, rows)),
            dtype=np.float64,
            count=len(points),
        )
        mask = (points[:, 2] >= floor_z + options.z_min) & (points[:, 2] <= floor_z + options.z_max)
    if options.flag_pass_through:
        mask = ~mask
    return points[mask]


def _radius_outlier_filter(points: np.ndarray, radius: float, min_neighbors: int) -> np.ndarray:
    if len(points) == 0 or radius <= 0 or min_neighbors <= 0:
        return points
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from scipy.spatial import cKDTree

        counts = cKDTree(points).query_ball_point(points, radius, return_length=True, workers=-1)
        return points[np.asarray(counts) >= min_neighbors]
    except (ImportError, TypeError):
        return _radius_outlier_filter_grid(points, radius, min_neighbors)


def _radius_outlier_filter_grid(points: np.ndarray, radius: float, min_neighbors: int) -> np.ndarray:
    radius_squared = radius * radius
    cell_size = radius
    cells: dict[tuple[int, int, int], list[int]] = {}
    keys = np.floor(points / cell_size).astype(np.int64)
    for index, key in enumerate(keys):
        cells.setdefault((int(key[0]), int(key[1]), int(key[2])), []).append(index)
    keep = []
    for index, point in enumerate(points):
        key = keys[index]
        candidate_indices = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    candidate_indices.extend(cells.get((int(key[0] + dx), int(key[1] + dy), int(key[2] + dz)), []))
        candidate_points = points[candidate_indices]
        neighbor_count = int(np.count_nonzero(np.sum((candidate_points - point) ** 2, axis=1) <= radius_squared))
        if neighbor_count >= min_neighbors:
            keep.append(index)
    return points[keep]


def _build_occupancy(points: np.ndarray, origin_x: float, origin_y: float, width: int, height: int, resolution: float) -> list[int]:
    occupancy = np.zeros((height, width), dtype=np.uint8)
    if len(points):
        cols = np.floor((points[:, 0] - origin_x) / resolution).astype(np.int64)
        rows = np.floor((points[:, 1] - origin_y) / resolution).astype(np.int64)
        valid = (cols >= 0) & (cols < width) & (rows >= 0) & (rows < height)
        occupancy[rows[valid], cols[valid]] = 100
    return occupancy.reshape(-1).tolist()


def _render_pgm(result: OutdoorPcdToPgmResult) -> bytes:
    body = bytearray()
    occupancy = np.asarray(result.occupancy, dtype=np.uint8).reshape((result.height, result.width))
    for row in reversed(range(result.height)):
        body.extend(np.where(occupancy[row] >= 100, 0, 254).astype(np.uint8).tobytes())
    return f"P5\n{result.width} {result.height}\n255\n".encode("ascii") + bytes(body)


def _render_trajectory_overlay_ppm(result: OutdoorPcdToPgmResult) -> bytes:
    if not result.trajectory_mask:
        raise ValueError("trajectory mask is required")
    occupancy = np.asarray(result.occupancy, dtype=np.uint8).reshape((result.height, result.width))
    trajectory = np.asarray(result.trajectory_mask, dtype=np.uint8).reshape((result.height, result.width))
    body = bytearray()
    for row in reversed(range(result.height)):
        for column in range(result.width):
            if trajectory[row, column] >= 100:
                body.extend((255, 64, 64))
            elif occupancy[row, column] >= 100:
                body.extend((0, 0, 0))
            else:
                body.extend((254, 254, 254))
    return f"P6\n{result.width} {result.height}\n255\n".encode("ascii") + bytes(body)


def _render_yaml(image_name: str, result: OutdoorPcdToPgmResult) -> str:
    origin = ", ".join(str(value) for value in result.origin)
    return (
        f"image: {image_name}\n"
        "mode: trinary\n"
        f"resolution: {result.resolution}\n"
        f"origin: [{origin}]\n"
        "negate: 0\n"
        "occupied_thresh: 0.65\n"
        "free_thresh: 0.25\n"
    )


def _png_base64_from_occupancy(
    width: int,
    height: int,
    occupancy: list[int],
    origin: list[float],
    resolution: float,
    max_dimension: int = 1600,
) -> str:
    scale = 1
    if scale > 1:
        source = np.asarray(occupancy, dtype=np.uint8).reshape((height, width))
        preview = source[::scale, ::scale]
        height, width = preview.shape
        occupancy = preview.reshape(-1).tolist()
        resolution *= scale
    raw = bytearray()
    origin_x = max(0, min(width - 1, int(math.floor(-origin[0] / resolution + 1e-9))))
    origin_row = max(0, min(height - 1, height - 1 - int(math.floor(-origin[1] / resolution + 1e-9))))
    axis_length = max(4, min(width, height, 48) // 4)
    x_axis_end = min(width - 1, origin_x + axis_length)
    y_axis_end = max(0, origin_row - axis_length)
    for row in reversed(range(height)):
        raw.append(0)
        preview_y = height - 1 - row
        for column in range(width):
            value = occupancy[column + row * width]
            pixel = (0, 0, 0) if value >= 100 else (254, 254, 254)
            if column == origin_x and preview_y == origin_row:
                pixel = (255, 230, 96)
            elif preview_y == origin_row and origin_x <= column <= x_axis_end:
                pixel = (220, 40, 40)
            elif column == origin_x and y_axis_end <= preview_y <= origin_row:
                pixel = (40, 180, 80)
            raw.extend(pixel)
    return base64.b64encode(_make_png(width, height, bytes(raw))).decode("ascii")


def _make_png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _safe_map_name(map_name: str) -> str:
    name = str(map_name or "").strip()
    if not name:
        raise ValueError("map_name is required")
    if Path(name).name != name or name in {".", ".."}:
        raise ValueError("map_name must be a simple file name")
    return name
