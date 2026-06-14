from pathlib import Path

import pytest

from tool_hub_web.pcd_to_map import (
    PcdToMapOptions,
    convert_pcd_to_map,
    export_map_files,
    parse_pcd_file,
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


def test_parse_ascii_pcd_extracts_xyz_points(tmp_path):
    pcd_path = tmp_path / "sample.pcd"
    write_ascii_pcd(pcd_path, [(1.0, 2.0, 0.1), (3.0, 4.0, 0.2)])

    points = parse_pcd_file(pcd_path)

    assert points == [(1.0, 2.0, 0.1), (3.0, 4.0, 0.2)]


def test_convert_pcd_to_map_matches_original_slice_projection(tmp_path):
    pcd_path = tmp_path / "sample.pcd"
    write_ascii_pcd(
        pcd_path,
        [
            (0.0, 0.0, 0.2),
            (0.05, 0.0, 0.2),
            (0.0, 0.05, 0.2),
            (1.0, 1.0, 2.0),
        ],
    )

    result = convert_pcd_to_map(
        pcd_path,
        PcdToMapOptions(
            z_min=0.0,
            z_max=0.5,
            resolution=0.05,
            radius=0.08,
            min_neighbors=1,
        ),
    )

    assert result.point_count == 3
    assert result.width == 1
    assert result.height == 1
    assert result.origin == [0.0, 0.0, 0.0]
    assert result.occupancy == [100]
    assert result.preview_png_base64


def test_radius_filter_counts_query_point_like_pcl(tmp_path):
    pcd_path = tmp_path / "single.pcd"
    write_ascii_pcd(pcd_path, [(0.0, 0.0, 0.2)])

    result = convert_pcd_to_map(
        pcd_path,
        PcdToMapOptions(
            z_min=0.0,
            z_max=0.5,
            resolution=0.05,
            radius=0.08,
            min_neighbors=1,
        ),
    )

    assert result.point_count == 1


def test_export_map_files_writes_pgm_and_yaml(tmp_path):
    pcd_path = tmp_path / "sample.pcd"
    output_dir = tmp_path / "maps"
    write_ascii_pcd(
        pcd_path,
        [
            (1.0, 2.0, 0.2),
            (1.05, 2.0, 0.2),
            (1.0, 2.05, 0.2),
        ],
    )
    result = convert_pcd_to_map(
        pcd_path,
        PcdToMapOptions(z_min=0.0, z_max=0.5, resolution=0.05, radius=0.08, min_neighbors=1),
    )

    exported = export_map_files(result, output_dir, "demo_map")

    assert exported["pgm_path"] == str(output_dir / "demo_map.pgm")
    assert exported["yaml_path"] == str(output_dir / "demo_map.yaml")
    assert (output_dir / "demo_map.pgm").read_bytes().startswith(b"P5\n")
    yaml_text = (output_dir / "demo_map.yaml").read_text(encoding="utf-8")
    assert "image: demo_map.pgm" in yaml_text
    assert "resolution: 0.05" in yaml_text
    assert "origin: [1.0, 2.0, 0.0]" in yaml_text


def test_convert_rejects_invalid_slice_limits(tmp_path):
    pcd_path = tmp_path / "sample.pcd"
    write_ascii_pcd(pcd_path, [(0.0, 0.0, 0.0)])

    with pytest.raises(ValueError, match="z_min"):
        convert_pcd_to_map(pcd_path, PcdToMapOptions(z_min=1.0, z_max=1.0))
