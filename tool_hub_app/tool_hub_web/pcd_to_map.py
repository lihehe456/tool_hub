import base64
from dataclasses import dataclass
import math
from pathlib import Path
import re
import struct
import zlib



Point = tuple[float, float, float]


@dataclass(frozen=True)
class PcdToMapOptions:
    z_min: float
    z_max: float
    resolution: float = 0.05
    radius: float = 0.5
    min_neighbors: int = 10
    flag_pass_through: bool = False
    odom_to_lidar_odom: tuple[float, float, float, float, float, float] = (
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )


@dataclass(frozen=True)
class PcdMapResult:
    width: int
    height: int
    resolution: float
    origin: list[float]
    occupancy: list[int]
    point_count: int
    z_min: float
    z_max: float
    preview_png_base64: str

    def to_preview_dict(self, slice_id=None):
        data = {
            "width": self.width,
            "height": self.height,
            "resolution": self.resolution,
            "origin": self.origin,
            "point_count": self.point_count,
            "z_min": self.z_min,
            "z_max": self.z_max,
            "preview_png_base64": self.preview_png_base64,
        }
        if slice_id is not None:
            data["id"] = slice_id
        return data


@dataclass(frozen=True)
class TrajectoryMaskResult:
    width: int
    height: int
    resolution: float
    origin: list[float]
    mask: list[int]
    point_count: int
    in_bounds_count: int
    source_path: str

    def to_preview_dict(self):
        return {
            "source_path": self.source_path,
            "point_count": self.point_count,
            "in_bounds_count": self.in_bounds_count,
        }


def parse_pcd_file(path):
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"PCD file not found: {source}")

    raw = source.read_bytes()
    header_end = _find_data_line_end(raw)
    header_text = raw[:header_end].decode("utf-8", errors="replace")
    metadata = _parse_header(header_text)
    data = raw[header_end:]

    fields = metadata.get("fields", [])
    if "x" not in fields or "y" not in fields or "z" not in fields:
        raise ValueError("PCD file must contain x, y and z fields")

    data_type = metadata.get("data", "").lower()
    if data_type == "ascii":
        return _parse_ascii_points(data.decode("utf-8", errors="replace"), fields)
    if data_type == "binary":
        return _parse_binary_points(data, metadata)
    if data_type == "binary_compressed":
        return _parse_binary_compressed_points(data, metadata)
    raise ValueError(f"Unsupported PCD DATA type: {metadata.get('data', '')}")


def convert_pcd_to_map(pcd_path, options):
    _validate_options(options)
    points = parse_pcd_file(pcd_path)
    transformed = [_apply_inverse_transform(point, options.odom_to_lidar_odom) for point in points]
    sliced = _pass_through(transformed, options.z_min, options.z_max, options.flag_pass_through)
    if not sliced:
        raise ValueError("Point cloud is empty after PassThrough filtering")

    filtered = _radius_outlier_filter(sliced, options.radius, options.min_neighbors)
    if not filtered:
        raise ValueError("Point cloud is empty after RadiusOutlier filtering")

    return _build_map(filtered, options)


def export_map_files(
    result,
    output_dir,
    map_name,
    trajectory_mask=None,
    include_trajectory_overlay=False,
):
    name = _safe_map_name(map_name)
    target_dir = Path(output_dir).expanduser().resolve()
    if not target_dir.is_absolute():
        raise ValueError("output_dir must be an absolute path")
    target_dir.mkdir(parents=True, exist_ok=True)

    pgm_path = target_dir / f"{name}.pgm"
    yaml_path = target_dir / f"{name}.yaml"
    pgm_path.write_bytes(_render_pgm(result))

    yaml_path.write_text(_render_map_yaml(pgm_path.name, result), encoding="utf-8")
    exported = {"pgm_path": str(pgm_path), "yaml_path": str(yaml_path)}

    if trajectory_mask:
        trajectory_pgm_path = target_dir / f"{name}_trajectory.pgm"
        trajectory_yaml_path = target_dir / f"{name}_trajectory.yaml"
        trajectory_pgm_path.write_bytes(_render_mask_pgm(trajectory_mask))
        trajectory_yaml_path.write_text(
            _render_map_yaml(trajectory_pgm_path.name, result), encoding="utf-8"
        )
        exported.update(
            {
                "trajectory_pgm_path": str(trajectory_pgm_path),
                "trajectory_yaml_path": str(trajectory_yaml_path),
            }
        )

        if include_trajectory_overlay:
            overlay_result = _result_with_trajectory_overlay(result, trajectory_mask)
            overlay_pgm_path = target_dir / f"{name}_with_trajectory.pgm"
            overlay_yaml_path = target_dir / f"{name}_with_trajectory.yaml"
            overlay_pgm_path.write_bytes(_render_pgm(overlay_result))
            overlay_yaml_path.write_text(
                _render_map_yaml(overlay_pgm_path.name, overlay_result), encoding="utf-8"
            )
            exported.update(
                {
                    "overlay_pgm_path": str(overlay_pgm_path),
                    "overlay_yaml_path": str(overlay_yaml_path),
                }
            )

    return exported


def render_preview_with_trajectory(result, trajectory_mask):
    occupancy = list(result.occupancy)
    return _png_base64_from_occupancy_with_trajectory(
        result.width,
        result.height,
        occupancy,
        trajectory_mask.mask,
        origin=result.origin,
        resolution=result.resolution,
    )


def find_trajectory_pcd(map_pcd_path):
    source = Path(map_pcd_path).expanduser().resolve()
    candidates = [
        source.parent / "Trajectory-Opt.pcd",
        source.parent / "trajectory-opt.pcd",
        source.parent / "trajectory.pcd",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def project_trajectory_to_map(trajectory_pcd_path, map_result, transform=None):
    points = parse_pcd_file(trajectory_pcd_path)
    if transform is not None:
        points = [_apply_inverse_transform(point, transform) for point in points]
    mask = [0] * (map_result.width * map_result.height)
    in_bounds_count = 0
    origin_x, origin_y = map_result.origin[0], map_result.origin[1]

    for point in points:
        i = int(math.floor((point[0] - origin_x) / map_result.resolution))
        j = int(math.floor((point[1] - origin_y) / map_result.resolution))
        if 0 <= i < map_result.width and 0 <= j < map_result.height:
            mask[i + j * map_result.width] = 100
            in_bounds_count += 1

    return TrajectoryMaskResult(
        width=map_result.width,
        height=map_result.height,
        resolution=map_result.resolution,
        origin=map_result.origin,
        mask=mask,
        point_count=len(points),
        in_bounds_count=in_bounds_count,
        source_path=str(Path(trajectory_pcd_path).expanduser().resolve()),
    )


def _find_data_line_end(raw):
    match = re.search(br"(?im)^DATA\s+\S+\s*\r?\n", raw)
    if not match:
        raise ValueError("Invalid PCD file: missing DATA line")
    return match.end()


def _parse_header(header_text):
    metadata = {}
    for line in header_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        key = parts[0].lower()
        values = parts[1:]
        if key in {"fields", "type"}:
            metadata[key] = values
        elif key in {"size", "count"}:
            metadata[key] = [int(value) for value in values]
        elif key in {"width", "height", "points"}:
            metadata[key] = int(values[0]) if values else 0
        elif key == "data":
            metadata[key] = values[0] if values else ""
    if "count" not in metadata and "fields" in metadata:
        metadata["count"] = [1] * len(metadata["fields"])
    return metadata


def _parse_ascii_points(text, fields):
    x_index = fields.index("x")
    y_index = fields.index("y")
    z_index = fields.index("z")
    points = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        values = line.split()
        points.append((float(values[x_index]), float(values[y_index]), float(values[z_index])))
    return points


def _parse_binary_points(data, metadata):
    fields = metadata["fields"]
    sizes = metadata.get("size", [])
    types = metadata.get("type", [])
    counts = metadata.get("count", [1] * len(fields))
    point_count = metadata.get("points") or metadata.get("width", 0) * metadata.get("height", 1)
    formats = []
    offsets = {}
    offset = 0
    for field, size, value_type, count in zip(fields, sizes, types, counts):
        if count != 1:
            offsets[field] = offset
            formats.append(f"{count * size}s")
            offset += count * size
            continue
        formats.append(_struct_format(size, value_type))
        offsets[field] = offset
        offset += size

    point_step = offset
    x_offset = offsets["x"]
    y_offset = offsets["y"]
    z_offset = offsets["z"]
    x_fmt = "<" + formats[fields.index("x")]
    y_fmt = "<" + formats[fields.index("y")]
    z_fmt = "<" + formats[fields.index("z")]
    points = []
    for index in range(point_count):
        start = index * point_step
        chunk = data[start : start + point_step]
        if len(chunk) < point_step:
            break
        points.append(
            (
                float(struct.unpack_from(x_fmt, chunk, x_offset)[0]),
                float(struct.unpack_from(y_fmt, chunk, y_offset)[0]),
                float(struct.unpack_from(z_fmt, chunk, z_offset)[0]),
            )
        )
    return points


def _parse_binary_compressed_points(data, metadata):
    if len(data) < 8:
        raise ValueError("Invalid binary_compressed PCD: missing compressed size header")
    compressed_size, uncompressed_size = struct.unpack_from("<II", data, 0)
    compressed = data[8 : 8 + compressed_size]
    if len(compressed) != compressed_size:
        raise ValueError("Invalid binary_compressed PCD: truncated compressed data")
    decompressed = _lzf_decompress(compressed, uncompressed_size)
    return _parse_binary_compressed_xyz_blocks(decompressed, metadata)


def _parse_binary_compressed_xyz_blocks(data, metadata):
    fields = metadata["fields"]
    sizes = metadata.get("size", [])
    counts = metadata.get("count", [1] * len(fields))
    point_count = metadata.get("points") or metadata.get("width", 0) * metadata.get("height", 1)
    field_sizes = [size * count for size, count in zip(sizes, counts)]
    field_offsets = {}
    offset = 0
    for field, field_size in zip(fields, field_sizes):
        field_offsets[field] = offset
        offset += field_size * point_count
    expected_size = sum(field_size * point_count for field_size in field_sizes)
    if len(data) < expected_size:
        raise ValueError("Invalid binary_compressed PCD: decompressed data is truncated")

    points = []
    for index in range(point_count):
        points.append(
            (
                _unpack_compressed_field(data, metadata, field_offsets, "x", index, point_count),
                _unpack_compressed_field(data, metadata, field_offsets, "y", index, point_count),
                _unpack_compressed_field(data, metadata, field_offsets, "z", index, point_count),
            )
        )
    return points


def _unpack_compressed_field(data, metadata, field_offsets, field_name, point_index, point_count):
    fields = metadata["fields"]
    field_index = fields.index(field_name)
    size = metadata["size"][field_index]
    value_type = metadata["type"][field_index]
    count = metadata.get("count", [1] * len(fields))[field_index]
    if count != 1:
        raise ValueError(f"Unsupported binary_compressed PCD field count for {field_name}: {count}")
    fmt = "<" + _struct_format(size, value_type)
    offset = field_offsets[field_name] + point_index * size
    return float(struct.unpack_from(fmt, data, offset)[0])


def _lzf_decompress(data, expected_size):
    output = bytearray()
    index = 0
    data_length = len(data)
    while index < data_length:
        control = data[index]
        index += 1
        if control < 32:
            length = control + 1
            output.extend(data[index : index + length])
            index += length
            continue

        length = control >> 5
        reference_offset = (control & 0x1F) << 8
        if length == 7:
            if index >= data_length:
                raise ValueError("Invalid LZF stream: missing extended length")
            length += data[index]
            index += 1
        if index >= data_length:
            raise ValueError("Invalid LZF stream: missing reference byte")
        reference_offset += data[index]
        index += 1
        length += 2

        reference_index = len(output) - reference_offset - 1
        if reference_index < 0:
            raise ValueError("Invalid LZF stream: reference before output")
        for _ in range(length):
            output.append(output[reference_index])
            reference_index += 1

    if len(output) != expected_size:
        raise ValueError(
            f"Invalid LZF stream: expected {expected_size} bytes, got {len(output)} bytes"
        )
    return bytes(output)


def _struct_format(size, value_type):
    key = (size, value_type.upper())
    formats = {
        (4, "F"): "f",
        (8, "F"): "d",
        (1, "I"): "B",
        (2, "I"): "H",
        (4, "I"): "I",
        (1, "U"): "B",
        (2, "U"): "H",
        (4, "U"): "I",
    }
    if key not in formats:
        raise ValueError(f"Unsupported binary PCD field type: size={size}, type={value_type}")
    return formats[key]


def _validate_options(options):
    if not (math.isfinite(options.z_min) and math.isfinite(options.z_max) and options.z_min < options.z_max):
        raise ValueError("Invalid slice limits: z_min must be finite and less than z_max")
    if not math.isfinite(options.resolution) or options.resolution <= 0:
        raise ValueError("resolution must be greater than 0")
    if not math.isfinite(options.radius) or options.radius < 0:
        raise ValueError("radius must be greater than or equal to 0")
    if int(options.min_neighbors) < 0:
        raise ValueError("min_neighbors must be greater than or equal to 0")
    if len(options.odom_to_lidar_odom) != 6:
        raise ValueError("odom_to_lidar_odom must contain 6 values")


def _apply_inverse_transform(point, transform):
    tx, ty, tz, roll, pitch, yaw = [float(value) for value in transform]
    x = point[0] - tx
    y = point[1] - ty
    z = point[2] - tz
    x, y, z = _rotate_z(x, y, z, -yaw)
    x, y, z = _rotate_y(x, y, z, -pitch)
    x, y, z = _rotate_x(x, y, z, -roll)
    return (x, y, z)


def _rotate_x(x, y, z, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    return x, c * y - s * z, s * y + c * z


def _rotate_y(x, y, z, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    return c * x + s * z, y, -s * x + c * z


def _rotate_z(x, y, z, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    return c * x - s * y, s * x + c * y, z


def _pass_through(points, z_min, z_max, negative):
    if negative:
        return [point for point in points if not (z_min <= point[2] <= z_max)]
    return [point for point in points if z_min <= point[2] <= z_max]


def _radius_outlier_filter(points, radius, min_neighbors):
    if min_neighbors <= 0 or radius <= 0:
        return list(points)

    radius_squared = radius * radius
    cell_size = radius
    grid = {}
    for index, point in enumerate(points):
        key = _cell_key(point, cell_size)
        grid.setdefault(key, []).append(index)

    filtered = []
    for index, point in enumerate(points):
        neighbor_count = 1
        if neighbor_count >= min_neighbors:
            filtered.append(point)
            continue
        cell = _cell_key(point, cell_size)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other_index in grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), []):
                        if other_index == index:
                            continue
                        other = points[other_index]
                        if _distance_squared(point, other) <= radius_squared:
                            neighbor_count += 1
                            if neighbor_count >= min_neighbors:
                                filtered.append(point)
                                dx = dy = dz = 2
                                break
                    else:
                        continue
                    break
                else:
                    continue
                break
            else:
                continue
            break
    return filtered


def _cell_key(point, cell_size):
    return (
        math.floor(point[0] / cell_size),
        math.floor(point[1] / cell_size),
        math.floor(point[2] / cell_size),
    )


def _distance_squared(left, right):
    return (
        (left[0] - right[0]) ** 2
        + (left[1] - right[1]) ** 2
        + (left[2] - right[2]) ** 2
    )


def _build_map(points, options):
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    x_min = min(x_values)
    x_max = max(x_values)
    y_min = min(y_values)
    y_max = max(y_values)
    width = int(math.ceil((x_max - x_min) / options.resolution))
    height = int(math.ceil((y_max - y_min) / options.resolution))
    width = max(width, 1)
    height = max(height, 1)
    occupancy = [0] * (width * height)

    for point in points:
        i = int(math.floor((point[0] - x_min) / options.resolution))
        j = int(math.floor((point[1] - y_min) / options.resolution))
        if 0 <= i < width and 0 <= j < height:
            occupancy[i + j * width] = 100

    return PcdMapResult(
        width=width,
        height=height,
        resolution=float(options.resolution),
        origin=[round(x_min, 6), round(y_min, 6), 0.0],
        occupancy=occupancy,
        point_count=len(points),
        z_min=float(options.z_min),
        z_max=float(options.z_max),
        preview_png_base64=_png_base64_from_occupancy(
            width,
            height,
            occupancy,
            origin=[round(x_min, 6), round(y_min, 6), 0.0],
            resolution=float(options.resolution),
        ),
    )


def _png_base64_from_occupancy(width, height, occupancy, origin, resolution):
    raw = bytearray()
    origin_x, origin_y = _preview_map_tf_pixel(width, height, origin, resolution)
    axis_length = max(4, min(width, height, 48) // 4)
    x_axis_end = min(width - 1, origin_x + axis_length)
    y_axis_end = max(0, origin_y - axis_length)

    for row in reversed(range(height)):
        raw.append(0)
        preview_y = height - 1 - row
        for column in range(width):
            value = occupancy[column + row * width]
            pixel = (0, 0, 0) if value >= 100 else (254, 254, 254)
            if column == origin_x and preview_y == origin_y:
                pixel = (255, 230, 96)
            elif preview_y == origin_y and origin_x <= column <= x_axis_end:
                pixel = (220, 40, 40)
            elif column == origin_x and y_axis_end <= preview_y <= origin_y:
                pixel = (40, 180, 80)
            raw.extend(pixel)
    png = _make_png(width, height, bytes(raw))
    return base64.b64encode(png).decode("ascii")


def _png_base64_from_occupancy_with_trajectory(width, height, occupancy, trajectory_mask, origin, resolution):
    raw = bytearray()
    origin_x, origin_y = _preview_map_tf_pixel(width, height, origin, resolution)
    axis_length = max(4, min(width, height, 48) // 4)
    x_axis_end = min(width - 1, origin_x + axis_length)
    y_axis_end = max(0, origin_y - axis_length)

    for row in reversed(range(height)):
        raw.append(0)
        preview_y = height - 1 - row
        for column in range(width):
            index = column + row * width
            value = occupancy[index]
            if trajectory_mask[index] >= 100:
                pixel = (255, 64, 64)
            else:
                pixel = (0, 0, 0) if value >= 100 else (254, 254, 254)
            if column == origin_x and preview_y == origin_y:
                pixel = (255, 230, 96)
            elif preview_y == origin_y and origin_x <= column <= x_axis_end:
                pixel = (220, 40, 40) if trajectory_mask[index] < 100 else (255, 64, 64)
            elif column == origin_x and y_axis_end <= preview_y <= origin_y:
                pixel = (40, 180, 80)
            raw.extend(pixel)
    png = _make_png(width, height, bytes(raw))
    return base64.b64encode(png).decode("ascii")


def _preview_map_tf_pixel(width, height, origin, resolution):
    origin_x = float(origin[0])
    origin_y = float(origin[1])
    column = int(math.floor((-origin_x) / resolution + 1e-9))
    row_from_bottom = int(math.floor((-origin_y) / resolution + 1e-9))
    row = height - 1 - row_from_bottom
    return (
        max(0, min(width - 1, column)),
        max(0, min(height - 1, row)),
    )


def _render_pgm(result):
    header = f"P5\n{result.width} {result.height}\n255\n".encode("ascii")
    body = bytearray()
    for row in reversed(range(result.height)):
        for column in range(result.width):
            value = result.occupancy[column + row * result.width]
            body.append(0 if value >= 100 else 254)
    return header + bytes(body)


def _render_mask_pgm(mask_result):
    header = f"P5\n{mask_result.width} {mask_result.height}\n255\n".encode("ascii")
    body = bytearray()
    for row in reversed(range(mask_result.height)):
        for column in range(mask_result.width):
            value = mask_result.mask[column + row * mask_result.width]
            body.append(0 if value >= 100 else 254)
    return header + bytes(body)


def _result_with_trajectory_overlay(result, trajectory_mask):
    occupancy = list(result.occupancy)
    for index, value in enumerate(trajectory_mask.mask):
        if value >= 100:
            occupancy[index] = 100
    return PcdMapResult(
        width=result.width,
        height=result.height,
        resolution=result.resolution,
        origin=result.origin,
        occupancy=occupancy,
        point_count=result.point_count,
        z_min=result.z_min,
        z_max=result.z_max,
        preview_png_base64=_png_base64_from_occupancy(
            result.width,
            result.height,
            occupancy,
            origin=result.origin,
            resolution=result.resolution,
        ),
    )


def _render_map_yaml(image_name, result):
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


def _make_png(width, height, filtered_rows):
    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        return (
            struct.pack(">I", len(data))
            + chunk
            + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += make_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += make_chunk(b"IDAT", zlib.compress(filtered_rows))
    png += make_chunk(b"IEND", b"")
    return png


def _safe_map_name(map_name):
    name = str(map_name or "").strip()
    if not name:
        raise ValueError("map_name is required")
    if any(char in name for char in "/\\"):
        raise ValueError("map_name must not contain path separators")
    return Path(name).stem
