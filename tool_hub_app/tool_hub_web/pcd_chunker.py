from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from tool_hub_web.pcd_to_map import parse_pcd_file


@dataclass(frozen=True)
class PcdChunkOptions:
    chunk_size: float
    voxel_size: float | None = None
    start_x: float = 0.0
    start_y: float = 0.0
    start_z: float = 0.0
    force: bool = False
    workers: int = 1


@dataclass(frozen=True)
class ChunkSummary:
    chunk_id: int
    grid_x: int
    grid_y: int
    point_count: int
    file_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "grid_x": self.grid_x,
            "grid_y": self.grid_y,
            "point_count": self.point_count,
            "file_path": self.file_path,
            "file_name": Path(self.file_path).name,
        }


@dataclass(frozen=True)
class ChunkPreview:
    chunk_size: float
    voxel_size: float | None
    start_xyz: tuple[float, float, float]
    total_input_points: int
    total_output_points: int
    chunk_count: int
    chunks: list[ChunkSummary]
    index_preview: str
    output_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_size": self.chunk_size,
            "voxel_size": self.voxel_size,
            "start_xyz": list(self.start_xyz),
            "total_input_points": self.total_input_points,
            "total_output_points": self.total_output_points,
            "chunk_count": self.chunk_count,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "index_preview": self.index_preview,
            "output_dir": self.output_dir,
        }


@dataclass(frozen=True)
class ChunkJob:
    chunk_id: int
    grid_x: int
    grid_y: int
    points_xyz: np.ndarray
    output_path: str
    voxel_size: float | None


def validate_chunk_inputs(input_pcd: Path, options: PcdChunkOptions) -> Path:
    input_path = Path(input_pcd).expanduser().resolve()
    if not input_path.exists() or not input_path.is_file():
        raise ValueError(f"input_pcd does not exist or is not a file: {input_path}")
    if input_path.suffix.lower() != ".pcd":
        raise ValueError(f"input_pcd must be a .pcd file: {input_path}")
    validate_chunk_options(options)
    return input_path


def validate_chunk_options(options: PcdChunkOptions) -> None:
    if options.chunk_size <= 0:
        raise ValueError(f"chunk_size must be > 0, got: {options.chunk_size}")
    if options.voxel_size is not None and options.voxel_size <= 0:
        raise ValueError(f"voxel_size must be > 0 when provided, got: {options.voxel_size}")
    if int(options.workers) <= 0:
        raise ValueError(f"workers must be > 0, got: {options.workers}")


def prepare_output_dir(output_dir: Path, force: bool, repo_root: Path) -> Path:
    target = Path(output_dir).expanduser().resolve()
    dangerous = {
        Path("/").resolve(),
        Path(".").resolve(),
        repo_root.resolve(),
    }
    if target in dangerous:
        raise ValueError(f"refusing to use dangerous output_dir: {target}")

    if target.exists():
        if not target.is_dir():
            raise ValueError(f"output_dir exists but is not a directory: {target}")
        if not force:
            raise ValueError(f"output_dir already exists: {target}. Use force to overwrite it.")

        index_path = target / "index.txt"
        if index_path.exists():
            index_path.unlink()
        for chunk_file in target.glob("*.pcd"):
            if chunk_file.stem.isdigit():
                chunk_file.unlink()
        return target

    target.mkdir(parents=True, exist_ok=False)
    return target


def load_cloud_xyz(input_pcd: Path) -> np.ndarray:
    points = np.asarray(parse_pcd_file(input_pcd), dtype=np.float64)
    if points.size == 0:
        raise ValueError(f"input point cloud is empty: {input_pcd}")
    if points.ndim != 2 or points.shape[1] < 3:
        raise ValueError(f"invalid point cloud shape {points.shape}, expected Nx3 or richer")
    return points[:, :3]


def pos_to_grid(points_xy: np.ndarray, chunk_size: float) -> np.ndarray:
    return np.floor(points_xy * (1.0 / chunk_size) + 0.5).astype(np.int64)


def bucket_points(points_xyz: np.ndarray, grids: np.ndarray) -> dict[tuple[int, int], np.ndarray]:
    if points_xyz.shape[0] != grids.shape[0]:
        raise ValueError("points and grids must have the same number of rows")
    if points_xyz.shape[0] == 0:
        return {}

    grouped_rows, grouped_points = _group_rows_preserving_first_seen(grids, points_xyz)
    return {
        (int(row[0]), int(row[1])): np.asarray(points, dtype=np.float64)
        for row, points in zip(grouped_rows, grouped_points)
    }


def voxel_downsample(points_xyz: np.ndarray, voxel_size: float) -> np.ndarray:
    if points_xyz.size == 0:
        return points_xyz
    points = np.asarray(points_xyz, dtype=np.float64)
    voxel_keys = np.floor(points / float(voxel_size)).astype(np.int64)
    _, ordered_inverse, order = _ordered_unique_inverse(voxel_keys)
    sums = np.zeros((len(order), points.shape[1]), dtype=np.float64)
    np.add.at(sums, ordered_inverse, points)
    counts = np.bincount(ordered_inverse, minlength=len(order)).astype(np.float64)
    return sums / counts[:, None]


def save_chunk_pcd(points_xyz: np.ndarray, output_path: Path) -> None:
    points = np.asarray(points_xyz, dtype="<f4")
    header = "\n".join(
        [
            "# .PCD v0.7 - Point Cloud Data file format",
            "VERSION 0.7",
            "FIELDS x y z",
            "SIZE 4 4 4",
            "TYPE F F F",
            "COUNT 1 1 1",
            f"WIDTH {len(points)}",
            "HEIGHT 1",
            "VIEWPOINT 0 0 0 1 0 0 0",
            f"POINTS {len(points)}",
            "DATA binary",
        ]
    ).encode("ascii") + b"\n"
    Path(output_path).write_bytes(header + points.tobytes(order="C"))


def build_index_preview(index_entries: list[tuple[int, int, int, Path]], start_xyz: tuple[float, float, float]) -> str:
    lines = [" ".join(f"{value:.18g}" for value in (0.0, 0.0, 0.0))]
    for chunk_id, grid_x, grid_y, chunk_path in index_entries:
        lines.append(f"{chunk_id} {grid_x} {grid_y} {chunk_path}")
    lines.append("# functional points")
    sx, sy, sz = start_xyz
    lines.append(f"start {sx:.18g} {sy:.18g} {sz:.18g} 0 0 0 1")
    return "\n".join(lines)


def write_index_file(output_dir: Path, index_entries: list[tuple[int, int, int, Path]], start_xyz: tuple[float, float, float]) -> Path:
    index_path = output_dir / "index.txt"
    index_path.write_text(build_index_preview(index_entries, start_xyz) + "\n", encoding="utf-8")
    return index_path


def build_chunk_preview(input_pcd: Path, output_dir: Path, options: PcdChunkOptions) -> ChunkPreview:
    input_path = validate_chunk_inputs(input_pcd, options)
    points_xyz = load_cloud_xyz(input_path)
    return build_chunk_preview_from_points(points_xyz, output_dir, options)


def build_chunk_preview_from_points(
    points_xyz: np.ndarray,
    output_dir: Path,
    options: PcdChunkOptions,
    downsample_fn: Callable[[np.ndarray, float], np.ndarray] | None = None,
) -> ChunkPreview:
    validate_chunk_options(options)
    points_xyz = np.asarray(points_xyz, dtype=np.float64)
    if points_xyz.size == 0:
        raise ValueError("input point cloud is empty")
    if points_xyz.ndim != 2 or points_xyz.shape[1] < 3:
        raise ValueError(f"invalid point cloud shape {points_xyz.shape}, expected Nx3 or richer")

    target_dir = Path(output_dir).expanduser().resolve()
    grids = pos_to_grid(points_xyz[:, :2], options.chunk_size)
    buckets = bucket_points(points_xyz[:, :3], grids)
    index_entries: list[tuple[int, int, int, Path]] = []
    chunks: list[ChunkSummary] = []
    total_output_points = 0
    downsample = downsample_fn or voxel_downsample

    for chunk_id, key in enumerate(buckets.keys()):
        grid_x, grid_y = key
        chunk_points = buckets[key]
        if options.voxel_size is not None:
            chunk_points = downsample(chunk_points, options.voxel_size)
        if chunk_points.size == 0:
            continue
        chunk_path = (target_dir / f"{chunk_id}.pcd").resolve()
        index_entries.append((chunk_id, grid_x, grid_y, chunk_path))
        point_count = int(chunk_points.shape[0])
        total_output_points += point_count
        chunks.append(
            ChunkSummary(
                chunk_id=chunk_id,
                grid_x=grid_x,
                grid_y=grid_y,
                point_count=point_count,
                file_path=str(chunk_path),
            )
        )

    return ChunkPreview(
        chunk_size=options.chunk_size,
        voxel_size=options.voxel_size,
        start_xyz=(options.start_x, options.start_y, options.start_z),
        total_input_points=int(points_xyz.shape[0]),
        total_output_points=total_output_points,
        chunk_count=len(chunks),
        chunks=chunks,
        index_preview=build_index_preview(index_entries, (options.start_x, options.start_y, options.start_z)),
        output_dir=str(target_dir),
    )


def export_chunked_map(input_pcd: Path, output_dir: Path, options: PcdChunkOptions) -> ChunkPreview:
    input_path = validate_chunk_inputs(input_pcd, options)
    points_xyz = load_cloud_xyz(input_path)
    return export_chunked_map_from_points(points_xyz, output_dir, options)


def export_chunked_map_from_points(
    points_xyz: np.ndarray,
    output_dir: Path,
    options: PcdChunkOptions,
    downsample_fn: Callable[[np.ndarray, float], np.ndarray] | None = None,
    save_chunk_fn: Callable[[np.ndarray, Path], None] | None = None,
) -> ChunkPreview:
    validate_chunk_options(options)
    points_xyz = np.asarray(points_xyz, dtype=np.float64)
    if points_xyz.size == 0:
        raise ValueError("input point cloud is empty")
    if points_xyz.ndim != 2 or points_xyz.shape[1] < 3:
        raise ValueError(f"invalid point cloud shape {points_xyz.shape}, expected Nx3 or richer")

    repo_root = Path(__file__).resolve().parent.parent
    target_dir = prepare_output_dir(output_dir, options.force, repo_root)
    grids = pos_to_grid(points_xyz[:, :2], options.chunk_size)
    buckets = bucket_points(points_xyz[:, :3], grids)
    jobs = [
        ChunkJob(
            chunk_id=chunk_id,
            grid_x=grid_x,
            grid_y=grid_y,
            points_xyz=buckets[(grid_x, grid_y)],
            output_path=str((target_dir / f"{chunk_id}.pcd").resolve()),
            voxel_size=options.voxel_size,
        )
        for chunk_id, (grid_x, grid_y) in enumerate(buckets.keys())
    ]
    processed = _run_chunk_jobs(
        jobs,
        workers=options.workers,
        downsample_fn=downsample_fn,
        save_chunk_fn=save_chunk_fn,
    )
    index_entries: list[tuple[int, int, int, Path]] = []
    chunks: list[ChunkSummary] = []
    total_output_points = 0
    for result in processed:
        if result is None:
            continue
        chunk_id, grid_x, grid_y, point_count, output_path = result
        chunk_path = Path(output_path)
        index_entries.append((chunk_id, grid_x, grid_y, chunk_path))
        total_output_points += point_count
        chunks.append(
            ChunkSummary(
                chunk_id=chunk_id,
                grid_x=grid_x,
                grid_y=grid_y,
                point_count=point_count,
                file_path=str(chunk_path),
            )
        )

    write_index_file(target_dir, index_entries, (options.start_x, options.start_y, options.start_z))
    return ChunkPreview(
        chunk_size=options.chunk_size,
        voxel_size=options.voxel_size,
        start_xyz=(options.start_x, options.start_y, options.start_z),
        total_input_points=int(points_xyz.shape[0]),
        total_output_points=total_output_points,
        chunk_count=len(chunks),
        chunks=chunks,
        index_preview=build_index_preview(index_entries, (options.start_x, options.start_y, options.start_z)),
        output_dir=str(target_dir),
    )


def _ordered_unique_inverse(rows: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    row_keys = _row_keys(rows)
    _, first_indices, inverse = np.unique(row_keys, return_index=True, return_inverse=True)
    order = np.argsort(first_indices, kind="stable")
    remap = np.empty_like(order)
    remap[order] = np.arange(len(order))
    ordered_inverse = remap[inverse]
    ordered_rows = rows[first_indices[order]]
    return ordered_rows, ordered_inverse, order


def _group_rows_preserving_first_seen(rows: np.ndarray, payload: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
    ordered_rows, ordered_inverse, _ = _ordered_unique_inverse(rows)
    sort_order = np.argsort(ordered_inverse, kind="stable")
    sorted_groups = ordered_inverse[sort_order]
    split_indices = np.flatnonzero(np.diff(sorted_groups)) + 1
    grouped_payload = np.split(payload[sort_order], split_indices)
    return ordered_rows, grouped_payload


def _row_keys(rows: np.ndarray) -> np.ndarray:
    contiguous = np.ascontiguousarray(rows)
    return contiguous.view(np.dtype((np.void, contiguous.dtype.itemsize * contiguous.shape[1]))).ravel()


def _run_chunk_jobs(
    jobs: list[ChunkJob],
    workers: int,
    downsample_fn: Callable[[np.ndarray, float], np.ndarray] | None,
    save_chunk_fn: Callable[[np.ndarray, Path], None] | None,
) -> list[tuple[int, int, int, int, str] | None]:
    if not jobs:
        return []
    if workers > 1 and downsample_fn is None and save_chunk_fn is None and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            return list(executor.map(_process_chunk_job, jobs))
    return [
        _process_chunk_job_inline(
            job,
            downsample_fn or voxel_downsample,
            save_chunk_fn or save_chunk_pcd,
        )
        for job in jobs
    ]


def _process_chunk_job(job: ChunkJob) -> tuple[int, int, int, int, str] | None:
    return _process_chunk_job_inline(job, voxel_downsample, save_chunk_pcd)


def _process_chunk_job_inline(
    job: ChunkJob,
    downsample_fn: Callable[[np.ndarray, float], np.ndarray],
    save_chunk_fn: Callable[[np.ndarray, Path], None],
) -> tuple[int, int, int, int, str] | None:
    chunk_points = job.points_xyz
    if job.voxel_size is not None:
        chunk_points = downsample_fn(chunk_points, job.voxel_size)
    if chunk_points.size == 0:
        return None
    output_path = Path(job.output_path)
    save_chunk_fn(chunk_points, output_path)
    return (job.chunk_id, job.grid_x, job.grid_y, int(chunk_points.shape[0]), str(output_path))
