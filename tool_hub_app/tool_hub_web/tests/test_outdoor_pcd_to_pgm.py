import base64
from pathlib import Path
import struct

from tool_hub_web.outdoor_pcd_to_pgm import (
    OutdoorPcdToPgmOptions,
    convert_outdoor_pcd_to_pgm,
    export_outdoor_pcd_to_pgm,
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


def test_outdoor_converter_uses_raw_bounds_and_absolute_z_filter(tmp_path):
    pcd_path = tmp_path / "outdoor.pcd"
    write_ascii_pcd(
        pcd_path,
        [
            (10.0, 20.0, 0.1),
            (10.2, 20.0, 0.3),
            (10.4, 20.0, 2.0),
        ],
    )

    result = convert_outdoor_pcd_to_pgm(
        pcd_path,
        OutdoorPcdToPgmOptions(z_min=0.0, z_max=0.5, resolution=0.1, radius=0, min_neighbors=0),
    )

    assert result.origin == [10.0, 20.0, 0.0]
    assert result.width == 5
    assert result.height == 1
    assert result.raw_point_count == 3
    assert result.filtered_point_count == 2
    assert result.trajectory_used is False
    assert result.preview_png_base64


def test_outdoor_converter_supports_trajectory_guided_relative_z_filter(tmp_path):
    pcd_path = tmp_path / "outdoor.pcd"
    trajectory_path = tmp_path / "Trajectory-Opt.pcd"
    write_ascii_pcd(pcd_path, [(0.1, 0.1, 1.0), (0.2, 0.1, 1.4), (0.3, 0.1, 2.0)])
    write_ascii_pcd(trajectory_path, [(0.0, 0.0, 1.5), (1.0, 0.0, 1.5)])

    result = convert_outdoor_pcd_to_pgm(
        pcd_path,
        OutdoorPcdToPgmOptions(
            z_min=-0.1,
            z_max=0.1,
            resolution=0.1,
            radius=0,
            min_neighbors=0,
            trajectory_pcd_path=trajectory_path,
            sensor_height=0.5,
            trajectory_search_radius=2.0,
        ),
    )

    assert result.trajectory_used is True
    assert result.filtered_point_count == 1
    assert result.warnings == []


def test_export_outdoor_pcd_to_pgm_writes_nav2_files(tmp_path):
    pcd_path = tmp_path / "outdoor.pcd"
    write_ascii_pcd(pcd_path, [(0.0, 0.0, 0.1), (0.2, 0.0, 0.1)])
    result = convert_outdoor_pcd_to_pgm(
        pcd_path,
        OutdoorPcdToPgmOptions(z_min=0, z_max=0.5, resolution=0.1, radius=0, min_neighbors=0),
    )

    exported = export_outdoor_pcd_to_pgm(result, tmp_path / "output", "outdoor_map")

    assert Path(exported["pgm_path"]).is_file()
    assert Path(exported["yaml_path"]).read_text(encoding="utf-8").startswith("image: outdoor_map.pgm")


def test_outdoor_preview_keeps_full_map_resolution_even_when_preview_cap_is_small(tmp_path):
    pcd_path = tmp_path / "outdoor.pcd"
    write_ascii_pcd(pcd_path, [(0.0, 0.0, 0.1), (0.4, 0.2, 0.1)])

    result = convert_outdoor_pcd_to_pgm(
        pcd_path,
        OutdoorPcdToPgmOptions(
            z_min=0,
            z_max=0.5,
            resolution=0.1,
            radius=0,
            min_neighbors=0,
            preview_max_dimension=2,
        ),
    )

    assert png_size(result.preview_png_base64) == (result.width, result.height)


def test_export_outdoor_pcd_to_pgm_writes_red_trajectory_overlay_image(tmp_path):
    pcd_path = tmp_path / "outdoor.pcd"
    trajectory_path = tmp_path / "Trajectory-Opt.pcd"
    write_ascii_pcd(pcd_path, [(0.0, 0.0, 0.1), (0.2, 0.0, 0.1)])
    write_ascii_pcd(trajectory_path, [(0.0, 0.0, 0.6), (0.2, 0.0, 0.6)])

    result = convert_outdoor_pcd_to_pgm(
        pcd_path,
        OutdoorPcdToPgmOptions(
            z_min=-0.1,
            z_max=0.1,
            resolution=0.1,
            radius=0,
            min_neighbors=0,
            trajectory_pcd_path=trajectory_path,
            sensor_height=0.5,
        ),
    )
    exported = export_outdoor_pcd_to_pgm(result, tmp_path / "output", "outdoor_map")

    overlay_path = Path(exported["trajectory_overlay_ppm_path"])
    assert overlay_path.is_file()
    assert b"\xff\x40\x40" in overlay_path.read_bytes()


def png_size(preview_png_base64: str) -> tuple[int, int]:
    raw = base64.b64decode(preview_png_base64)
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", raw[16:24])
