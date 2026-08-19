from pathlib import Path

import numpy as np

from tool_hub_web.pcd_chunker import (
    PcdChunkOptions,
    build_chunk_preview_from_points,
    bucket_points,
    export_chunked_map_from_points,
    export_chunked_map_native,
    generate_loc_config,
    load_cloud_xyz,
    pos_to_grid,
    prepare_output_dir,
    save_chunk_pcd,
    voxel_downsample,
)


def write_ascii_pcd(path: Path, points):
    rows = "\n".join(f"{x} {y} {z}" for x, y, z in points)
    path.write_text(
        "\n".join(
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
                "DATA ascii",
                rows,
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_generate_loc_config_replaces_only_system_map_path(tmp_path):
    template_dir = tmp_path / "templates"
    output_dir = tmp_path / "chunks"
    config_dir = tmp_path / "localization-config"
    template_dir.mkdir()
    output_dir.mkdir()
    (template_dir / "rycx_loc_outdoor_template.yaml").write_text(
        "\n".join(
            [
                "common:",
                "  map_path: /keep/common",
                "system:",
                "  with_ui: true",
                "  map_path: /old/map",
                "other:",
                "  map_path: /keep/other",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    config_path = generate_loc_config(
        "outdoor",
        output_dir,
        "robot_loc",
        template_dir=template_dir,
        config_output_dir=config_dir,
    )

    assert config_path == config_dir / "robot_loc.yaml"
    assert config_path.read_text(encoding="utf-8").splitlines() == [
        "common:",
        "  map_path: /keep/common",
        "system:",
        "  with_ui: true",
        f"  map_path: {output_dir.resolve()}",
        "other:",
        "  map_path: /keep/other",
    ]


def test_pos_to_grid_matches_reference_rounding():
    points_xy = np.asarray(
        [
            [0.0, 0.0],
            [49.9, 0.0],
            [50.1, 0.0],
            [-24.9, 0.0],
            [-25.1, 0.0],
        ],
        dtype=np.float64,
    )

    grids = pos_to_grid(points_xy, 50.0)

    assert grids.tolist() == [
        [0, 0],
        [1, 0],
        [1, 0],
        [0, 0],
        [-1, 0],
    ]


def test_bucket_points_preserves_first_seen_grid_order():
    points_xyz = np.asarray(
        [
            [60.0, 1.0, 0.0],
            [0.0, 0.0, 0.0],
            [55.0, 2.0, 0.0],
            [-30.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    )
    grids = pos_to_grid(points_xyz[:, :2], 50.0)

    buckets = bucket_points(points_xyz, grids)

    assert list(buckets.keys()) == [(1, 0), (0, 0), (-1, 0)]
    assert buckets[(1, 0)].shape == (2, 3)


def test_build_chunk_preview_from_points_returns_chunk_summary_and_index_preview(tmp_path):
    points_xyz = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [10.0, 10.0, 0.0],
            [60.0, 5.0, 0.0],
            [-30.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    )

    preview = build_chunk_preview_from_points(
        points_xyz,
        tmp_path / "chunks",
        PcdChunkOptions(chunk_size=50.0, start_x=1.5, start_y=-2.0, start_z=0.2),
    )

    assert preview.total_input_points == 4
    assert preview.total_output_points == 4
    assert preview.chunk_count == 3
    assert [chunk.chunk_id for chunk in preview.chunks] == [0, 1, 2]
    assert [(chunk.grid_x, chunk.grid_y) for chunk in preview.chunks] == [(0, 0), (1, 0), (-1, 0)]
    assert [chunk.point_count for chunk in preview.chunks] == [2, 1, 1]
    assert preview.index_preview.splitlines() == [
        "0 0 0",
        f"0 0 0 {(tmp_path / 'chunks' / '0.pcd').resolve()}",
        f"1 1 0 {(tmp_path / 'chunks' / '1.pcd').resolve()}",
        f"2 -1 0 {(tmp_path / 'chunks' / '2.pcd').resolve()}",
        "# functional points",
        "start 1.5 -2 0.200000000000000011 0 0 0 1",
    ]


def test_export_chunked_map_from_points_writes_index_and_numeric_chunk_files(tmp_path):
    points_xyz = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [55.0, 0.0, 0.0],
            [60.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )
    output_dir = tmp_path / "chunks"
    saved = []

    def fake_save_chunk(points, output_path):
        saved.append((points.copy(), output_path))
        output_path.write_text(f"points={len(points)}\n", encoding="utf-8")

    exported = export_chunked_map_from_points(
        points_xyz,
        output_dir,
        PcdChunkOptions(chunk_size=50.0, force=False),
        save_chunk_fn=fake_save_chunk,
    )

    assert exported.chunk_count == 2
    assert output_dir.joinpath("index.txt").is_file()
    assert output_dir.joinpath("0.pcd").read_text(encoding="utf-8") == "points=1\n"
    assert output_dir.joinpath("1.pcd").read_text(encoding="utf-8") == "points=2\n"
    assert [path.name for _, path in saved] == ["0.pcd", "1.pcd"]


def test_prepare_output_dir_force_only_removes_generated_chunk_outputs(tmp_path):
    output_dir = tmp_path / "chunks"
    output_dir.mkdir()
    (output_dir / "index.txt").write_text("index\n", encoding="utf-8")
    (output_dir / "0.pcd").write_text("chunk\n", encoding="utf-8")
    (output_dir / "notes.txt").write_text("keep\n", encoding="utf-8")

    prepare_output_dir(output_dir, force=True, repo_root=tmp_path / "repo")

    assert not (output_dir / "index.txt").exists()
    assert not (output_dir / "0.pcd").exists()
    assert (output_dir / "notes.txt").read_text(encoding="utf-8") == "keep\n"


def test_save_chunk_pcd_writes_binary_pcd_without_open3d_dependency(tmp_path):
    pcd_path = tmp_path / "chunk.pcd"

    save_chunk_pcd(
        np.asarray(
            [
                [1.0, 2.0, 0.5],
                [3.0, 4.0, 0.7],
            ],
            dtype=np.float64,
        ),
        pcd_path,
    )

    loaded = load_cloud_xyz(pcd_path)

    assert loaded.tolist() == [
        [1.0, 2.0, 0.5],
        [3.0, 4.0, 0.699999988079071],
    ]


def test_voxel_downsample_keeps_one_representative_point_per_voxel():
    points_xyz = np.asarray(
        [
            [0.01, 0.01, 0.0],
            [0.04, 0.03, 0.0],
            [0.26, 0.26, 0.0],
        ],
        dtype=np.float64,
    )

    reduced = voxel_downsample(points_xyz, 0.1)

    assert reduced.shape == (2, 3)
    assert reduced[0].tolist() == [0.025, 0.02, 0.0]
    assert reduced[1].tolist() == [0.26, 0.26, 0.0]


def test_build_chunk_preview_reads_existing_pcd_without_open3d(tmp_path):
    pcd_path = tmp_path / "sample.pcd"
    write_ascii_pcd(pcd_path, [(0.0, 0.0, 0.0), (60.0, 0.0, 0.0)])

    preview = build_chunk_preview_from_points(
        load_cloud_xyz(pcd_path),
        tmp_path / "chunks",
        PcdChunkOptions(chunk_size=50.0),
    )

    assert preview.chunk_count == 2


def test_export_chunked_map_uses_process_pool_when_workers_gt_one(monkeypatch, tmp_path):
    points_xyz = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [60.0, 0.0, 0.0],
            [120.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    )
    output_dir = tmp_path / "chunks"
    calls = {"max_workers": None, "jobs": 0}

    class FakeExecutor:
        def __init__(self, max_workers):
            calls["max_workers"] = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def map(self, fn, jobs):
            job_list = list(jobs)
            calls["jobs"] = len(job_list)
            return [fn(job) for job in job_list]

    monkeypatch.setattr("tool_hub_web.pcd_chunker.ProcessPoolExecutor", FakeExecutor)

    exported = export_chunked_map_from_points(
        points_xyz,
        output_dir,
        PcdChunkOptions(chunk_size=50.0, workers=3),
    )

    assert exported.chunk_count == 3
    assert calls == {"max_workers": 3, "jobs": 3}


def test_export_chunked_map_native_passes_workers_to_binary(monkeypatch, tmp_path):
    output_dir = tmp_path / "chunks"
    calls = {}

    class Completed:
        returncode = 0
        stderr = ""

    def fake_run(command, capture_output, text, check):
        calls["command"] = command
        output_dir.mkdir(parents=True)
        (output_dir / "index.txt").write_text("0 0 0\n# functional points\nstart 0 0 0 0 0 0 1\n", encoding="utf-8")
        (output_dir / "chunker.summary").write_text(
            "\n".join(
                [
                    "chunk_size=50",
                    "voxel_size=",
                    "start_x=0",
                    "start_y=0",
                    "start_z=0",
                    "total_input_points=0",
                    "total_output_points=0",
                    "chunk_count=0",
                    f"output_dir={output_dir}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return Completed()

    monkeypatch.setattr("tool_hub_web.pcd_chunker.subprocess.run", fake_run)

    export_chunked_map_native(
        tmp_path / "map.pcd",
        output_dir,
        PcdChunkOptions(chunk_size=50, workers=4),
        Path("/tmp/pcd_chunker"),
    )

    assert "--workers" in calls["command"]
    assert calls["command"][calls["command"].index("--workers") + 1] == "4"


def test_build_chunk_preview_native_uses_summary_only(monkeypatch, tmp_path):
    from tool_hub_web.pcd_chunker import build_chunk_preview_native

    output_dir = tmp_path / "chunks"
    calls = {}

    class Completed:
        returncode = 0
        stderr = ""

    def fake_run(command, capture_output, text, check):
        calls["command"] = command
        temp_output = Path(command[command.index("--output") + 1])
        temp_output.mkdir(parents=True, exist_ok=True)
        (temp_output / "index.txt").write_text("0 0 0\n# functional points\nstart 0 0 0 0 0 0 1\n", encoding="utf-8")
        (temp_output / "chunker.summary").write_text(
            "\n".join(
                [
                    "chunk_size=50",
                    "voxel_size=",
                    "start_x=0",
                    "start_y=0",
                    "start_z=0",
                    "total_input_points=4",
                    "total_output_points=4",
                    "chunk_count=1",
                    f"output_dir={temp_output}",
                    f"chunk\t0\t0\t0\t4\t{temp_output / '0.pcd'}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return Completed()

    monkeypatch.setattr("tool_hub_web.pcd_chunker.subprocess.run", fake_run)

    preview = build_chunk_preview_native(
        tmp_path / "map.pcd",
        output_dir,
        PcdChunkOptions(chunk_size=50, workers=4),
        Path("/tmp/pcd_chunker"),
    )

    assert "--summary-only" in calls["command"]
    assert preview.chunks[0].file_path == str((output_dir / "0.pcd").resolve())
