import yaml

from tool_hub_web.virtual_wall_builder import (
    build_virtual_wall_document,
    load_virtual_wall_file,
    save_virtual_wall_file,
)


def test_build_virtual_wall_document_stores_segments_relative_to_map_origin():
    document = build_virtual_wall_document(
        polylines=[
            {
                "points": [
                    {"x": 11.25, "y": -2.5, "z": 0.0},
                    {"x": 12.25, "y": -2.0, "z": 0.0},
                    {"x": 12.25, "y": -1.0, "z": 0.0},
                ],
                "thickness": 0.2,
            }
        ],
        map_origin=[10.0, -3.0, 0.0],
        frame_id="map",
        default_thickness=0.1,
    )

    walls = document["virtual_walls"]

    assert walls["coordinate_mode"] == "image_relative"
    assert walls["map_origin"] == [10.0, -3.0, 0.0]
    assert walls["segments"] == [
        {"start": [1.25, 0.5, 0.0], "end": [2.25, 1.0, 0.0], "thickness": 0.2},
        {"start": [2.25, 1.0, 0.0], "end": [2.25, 2.0, 0.0], "thickness": 0.2},
    ]


def test_save_and_load_image_relative_virtual_wall_file_uses_current_map_origin(tmp_path):
    wall_path = tmp_path / "virtual_walls.yaml"
    save_virtual_wall_file(
        wall_path,
        polylines=[
            {
                "points": [
                    {"x": 2.0, "y": 3.0},
                    {"x": 4.0, "y": 3.0},
                ],
                "thickness": 0.15,
            }
        ],
        map_origin=[1.0, 1.0, 0.0],
    )

    raw = yaml.safe_load(wall_path.read_text(encoding="utf-8"))
    assert raw["virtual_walls"]["segments"][0]["start"] == [1.0, 2.0, 0.0]

    loaded = load_virtual_wall_file(wall_path, current_map_origin=[10.0, 20.0, 0.0])

    assert loaded["coordinate_mode"] == "image_relative"
    assert loaded["polylines"] == [
        {
            "points": [
                {"x": 11.0, "y": 22.0, "z": 0.0},
                {"x": 13.0, "y": 22.0, "z": 0.0},
            ],
            "thickness": 0.15,
        }
    ]


def test_load_legacy_multipoint_virtual_wall_file(tmp_path):
    wall_path = tmp_path / "legacy.yaml"
    wall_path.write_text(
        """
virtual_walls:
  frame_id: map
  thickness: 0.1
  walls:
    - points:
        - [1.0, 2.0, 0.0]
        - [3.0, 2.0, 0.0]
        - [3.0, 4.0, 0.0]
      thickness: 0.2
""".strip(),
        encoding="utf-8",
    )

    loaded = load_virtual_wall_file(wall_path, current_map_origin=[100.0, 100.0, 0.0])

    assert loaded["coordinate_mode"] == "absolute"
    assert loaded["polylines"] == [
        {
            "points": [
                {"x": 1.0, "y": 2.0, "z": 0.0},
                {"x": 3.0, "y": 2.0, "z": 0.0},
                {"x": 3.0, "y": 4.0, "z": 0.0},
            ],
            "thickness": 0.2,
        }
    ]
