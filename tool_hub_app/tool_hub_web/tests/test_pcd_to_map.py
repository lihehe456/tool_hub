import base64
from pathlib import Path
import struct
import zlib

import pytest

from tool_hub_web.pcd_to_map import (
    PcdToMapOptions,
    convert_pcd_to_map,
    convert_pcd_to_map_preview,
    export_map_files,
    find_trajectory_pcd,
    parse_pcd_file,
    project_trajectory_to_map,
    render_preview_with_trajectory,
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


def lzf_literal_compress(data: bytes) -> bytes:
    chunks = []
    for start in range(0, len(data), 32):
        chunk = data[start : start + 32]
        chunks.append(bytes([len(chunk) - 1]) + chunk)
    return b"".join(chunks)


def write_binary_compressed_pcd(path: Path, points):
    fields = ["x", "y", "z"]
    field_blocks = []
    for field_index in range(len(fields)):
        field_blocks.append(b"".join(struct.pack("<f", point[field_index]) for point in points))
    uncompressed = b"".join(field_blocks)
    compressed = lzf_literal_compress(uncompressed)
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
            "DATA binary_compressed",
        ]
    ).encode("ascii") + b"\n"
    path.write_bytes(header + struct.pack("<II", len(compressed), len(uncompressed)) + compressed)


def write_binary_compressed_pcd_with_extended_lzf_reference(path: Path):
    point_count = 22
    uncompressed = b"\x00" * (point_count * 3 * 4)
    compressed = b"\x00\x00\xe0\xfe\x00"
    header = "\n".join(
        [
            "# .PCD v0.7 - Point Cloud Data file format",
            "VERSION 0.7",
            "FIELDS x y z",
            "SIZE 4 4 4",
            "TYPE F F F",
            "COUNT 1 1 1",
            f"WIDTH {point_count}",
            "HEIGHT 1",
            "VIEWPOINT 0 0 0 1 0 0 0",
            f"POINTS {point_count}",
            "DATA binary_compressed",
        ]
    ).encode("ascii") + b"\n"
    path.write_bytes(header + struct.pack("<II", len(compressed), len(uncompressed)) + compressed)


def decode_preview_png_rgb_rows(preview_png_base64):
    png = base64.b64decode(preview_png_base64)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    width = height = color_type = None
    idat = bytearray()
    while offset < len(png):
        length = struct.unpack_from(">I", png, offset)[0]
        chunk_type = png[offset + 4 : offset + 8]
        data = png[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, _, color_type, _, _, _ = struct.unpack(">IIBBBBB", data)
        elif chunk_type == b"IDAT":
            idat.extend(data)
        elif chunk_type == b"IEND":
            break
    assert color_type == 2
    raw = zlib.decompress(bytes(idat))
    stride = width * 3
    rows = []
    cursor = 0
    for _ in range(height):
        assert raw[cursor] == 0
        cursor += 1
        row = []
        for column in range(width):
            start = cursor + column * 3
            row.append(tuple(raw[start : start + 3]))
        cursor += stride
        rows.append(row)
    return rows


def flatten_pixels(rows):
    return [pixel for row in rows for pixel in row]


def test_parse_ascii_pcd_extracts_xyz_points(tmp_path):
    pcd_path = tmp_path / "sample.pcd"
    write_ascii_pcd(pcd_path, [(1.0, 2.0, 0.1), (3.0, 4.0, 0.2)])

    points = parse_pcd_file(pcd_path)

    assert len(points) == 2
    assert points[0] == pytest.approx((1.0, 2.0, 0.1))
    assert points[1] == pytest.approx((3.0, 4.0, 0.2))


def test_parse_binary_compressed_pcd_extracts_xyz_points(tmp_path):
    pcd_path = tmp_path / "compressed.pcd"
    write_binary_compressed_pcd(pcd_path, [(1.0, 2.0, 0.1), (3.0, 4.0, 0.2)])

    points = parse_pcd_file(pcd_path)

    assert len(points) == 2
    assert points[0] == pytest.approx((1.0, 2.0, 0.1))
    assert points[1] == pytest.approx((3.0, 4.0, 0.2))


def test_parse_binary_compressed_pcd_supports_extended_lzf_references(tmp_path):
    pcd_path = tmp_path / "compressed_extended_reference.pcd"
    write_binary_compressed_pcd_with_extended_lzf_reference(pcd_path)

    points = parse_pcd_file(pcd_path)

    assert len(points) == 22
    assert points == pytest.approx([(0.0, 0.0, 0.0)] * 22)


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


def test_fast_preview_skips_radius_filter_for_sparse_points(tmp_path):
    pcd_path = tmp_path / "sparse.pcd"
    write_ascii_pcd(pcd_path, [(0.0, 0.0, 0.2), (10.0, 10.0, 0.2)])

    result = convert_pcd_to_map_preview(
        pcd_path,
        PcdToMapOptions(
            z_min=0.0,
            z_max=0.5,
            resolution=1.0,
            radius=0.5,
            min_neighbors=10,
        ),
        fast_preview=True,
    )

    assert result.point_count == 2


def test_fast_preview_uses_coarser_resolution_for_large_preview(tmp_path):
    pcd_path = tmp_path / "large_span.pcd"
    write_ascii_pcd(pcd_path, [(0.0, 0.0, 0.2), (100.0, 100.0, 0.2)])

    result = convert_pcd_to_map_preview(
        pcd_path,
        PcdToMapOptions(
            z_min=0.0,
            z_max=0.5,
            resolution=1.0,
            radius=0.5,
            min_neighbors=10,
        ),
        fast_preview=True,
        max_preview_dimension=10,
    )

    assert result.resolution == 10.0
    assert result.width == 10
    assert result.height == 10


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


def test_find_trajectory_pcd_prefers_same_directory_trajectory_opt(tmp_path):
    map_path = tmp_path / "map_1.pcd"
    trajectory_path = tmp_path / "Trajectory-Opt.pcd"
    write_ascii_pcd(map_path, [(0.0, 0.0, 0.0)])
    write_ascii_pcd(trajectory_path, [(0.5, 0.5, 0.0)])

    assert find_trajectory_pcd(map_path) == trajectory_path


def test_project_trajectory_to_map_uses_map_grid_geometry(tmp_path):
    map_path = tmp_path / "map_1.pcd"
    trajectory_path = tmp_path / "Trajectory-Opt.pcd"
    write_ascii_pcd(map_path, [(-1.0, -1.0, 0.2), (1.0, 1.0, 0.2)])
    write_ascii_pcd(
        trajectory_path,
        [
            (-1.0, -1.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.5, 0.5, 0.0),
            (2.0, 2.0, 0.0),
        ],
    )
    result = convert_pcd_to_map(
        map_path,
        PcdToMapOptions(z_min=0.0, z_max=0.5, resolution=0.5, radius=0.0, min_neighbors=0),
    )

    mask = project_trajectory_to_map(trajectory_path, result)

    assert mask.point_count == 4
    assert mask.in_bounds_count == 3
    assert mask.mask == [
        100, 0, 0, 0,
        0, 0, 0, 0,
        0, 0, 100, 0,
        0, 0, 0, 100,
    ]


def test_export_map_files_writes_trajectory_mask_and_overlay(tmp_path):
    pcd_path = tmp_path / "map_1.pcd"
    trajectory_path = tmp_path / "Trajectory-Opt.pcd"
    output_dir = tmp_path / "maps"
    write_ascii_pcd(pcd_path, [(-1.0, -1.0, 0.2), (1.0, 1.0, 0.2)])
    write_ascii_pcd(trajectory_path, [(0.0, 0.0, 0.0)])
    result = convert_pcd_to_map(
        pcd_path,
        PcdToMapOptions(z_min=0.0, z_max=0.5, resolution=0.5, radius=0.0, min_neighbors=0),
    )
    mask = project_trajectory_to_map(trajectory_path, result)

    exported = export_map_files(
        result,
        output_dir,
        "demo_map",
        trajectory_mask=mask,
        include_trajectory_overlay=True,
    )

    assert exported["trajectory_pgm_path"] == str(output_dir / "demo_map_trajectory.pgm")
    assert exported["trajectory_yaml_path"] == str(output_dir / "demo_map_trajectory.yaml")
    assert exported["overlay_pgm_path"] == str(output_dir / "demo_map_with_trajectory.pgm")
    assert exported["overlay_yaml_path"] == str(output_dir / "demo_map_with_trajectory.yaml")
    assert (output_dir / "demo_map_trajectory.pgm").is_file()
    assert (output_dir / "demo_map_trajectory.yaml").read_text(encoding="utf-8").startswith(
        "image: demo_map_trajectory.pgm"
    )
    assert (output_dir / "demo_map_with_trajectory.pgm").is_file()
    assert (output_dir / "demo_map_with_trajectory.yaml").read_text(encoding="utf-8").startswith(
        "image: demo_map_with_trajectory.pgm"
    )


def test_render_preview_with_trajectory_draws_red_mask_pixels(tmp_path):
    map_path = tmp_path / "map_1.pcd"
    trajectory_path = tmp_path / "Trajectory-Opt.pcd"
    write_ascii_pcd(map_path, [(-1.0, -1.0, 0.2), (1.0, 1.0, 0.2)])
    write_ascii_pcd(trajectory_path, [(0.5, 0.5, 0.0)])
    result = convert_pcd_to_map(
        map_path,
        PcdToMapOptions(z_min=0.0, z_max=0.5, resolution=0.5, radius=0.0, min_neighbors=0),
    )
    mask = project_trajectory_to_map(trajectory_path, result)

    rows = decode_preview_png_rgb_rows(render_preview_with_trajectory(result, mask))

    assert (255, 64, 64) in flatten_pixels(rows)


def test_preview_png_draws_yaml_origin_axes(tmp_path):
    pcd_path = tmp_path / "sample.pcd"
    write_ascii_pcd(pcd_path, [(-1.0, -2.0, 0.2), (1.0, 1.0, 0.2)])

    result = convert_pcd_to_map(
        pcd_path,
        PcdToMapOptions(z_min=0.0, z_max=0.5, resolution=0.1, radius=0.0, min_neighbors=0),
    )
    rows = decode_preview_png_rgb_rows(result.preview_png_base64)

    origin_col = int(round((-result.origin[0]) / result.resolution))
    preview_row = len(rows) - 1 - int(round((-result.origin[1]) / result.resolution))

    assert rows[preview_row][origin_col] == (255, 230, 96)
    assert rows[preview_row][min(origin_col + 1, len(rows[preview_row]) - 1)] == (220, 40, 40)
    assert rows[max(preview_row - 1, 0)][origin_col] == (40, 180, 80)


def test_convert_rejects_invalid_slice_limits(tmp_path):
    pcd_path = tmp_path / "sample.pcd"
    write_ascii_pcd(pcd_path, [(0.0, 0.0, 0.0)])

    with pytest.raises(ValueError, match="z_min"):
        convert_pcd_to_map(pcd_path, PcdToMapOptions(z_min=1.0, z_max=1.0))
