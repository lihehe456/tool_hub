import json
import math

from tool_hub_web.subtask_composer import (
    build_return_subtask,
    create_empty_subtask,
    load_task_document_file,
    load_subtask_file,
    save_task_document_file,
    save_subtask_file,
)


def test_create_empty_subtask_uses_single_file_runtime_shape():
    subtask = create_empty_subtask(
        subtask_name="indoor",
        map_url="/opt/ry/data/maps/demo/map.yaml",
    )

    assert subtask == {
        "change_loc": False,
        "map_url": "/opt/ry/data/maps/demo/map.yaml",
        "pcd_url": "",
        "subtask_name": "indoor",
        "waypoints": [],
    }


def test_load_subtask_file_accepts_top_level_waypoints(tmp_path):
    path = tmp_path / "9_2.json"
    path.write_text(
        json.dumps(
            {
                "change_loc": False,
                "map_url": "/maps/map.yaml",
                "pcd_url": "",
                "subtask_name": "indoor",
                "waypoints": [
                    {
                        "waypoint_id": "p0",
                        "pose": {
                            "position": {"x": 1, "y": 2, "z": 0},
                            "orientation": {"x": 0, "y": 0, "z": 0, "w": 1},
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    subtask = load_subtask_file(path)

    assert subtask["subtask_name"] == "indoor"
    assert subtask["waypoints"][0]["speed_mode"] == "task_point"
    assert subtask["waypoints"][0]["waypoint_task_id"] == ""
    assert subtask["waypoints"][0]["is_single_point"] is True
    assert subtask["waypoints"][0]["is_task_point"] is False
    assert subtask["waypoints"][0]["is_backward"] is False


def test_load_task_document_file_detects_task_group_and_normalizes_subtasks(tmp_path):
    path = tmp_path / "group.json"
    path.write_text(
        json.dumps(
            {
                "task_group_name": "delivery",
                "selected_subtask_ids": ["a"],
                "subtasks": [
                    {
                        "id": "a",
                        "subtask_name": "go",
                        "map_url": "/maps/a.yaml",
                        "waypoints": [{"pose": {"position": {"x": 1}, "orientation": {"w": 1}}}],
                    },
                    {
                        "id": "b",
                        "subtask_name": "back",
                        "map_url": "/maps/b.yaml",
                        "waypoints": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = load_task_document_file(path)

    assert payload["document_type"] == "task_group"
    assert payload["task_group"]["task_group_name"] == "delivery"
    assert payload["active_subtask_index"] == 0
    assert [subtask["subtask_name"] for subtask in payload["subtasks"]] == ["go", "back"]
    assert payload["subtasks"][0]["waypoints"][0]["speed_mode"] == "task_point"


def test_save_task_document_file_preserves_task_group_fields_and_replaces_subtasks(tmp_path):
    path = tmp_path / "group.json"
    task_group = {
        "task_group_name": "delivery",
        "selected_subtask_ids": ["a"],
        "subtasks": [
            {"id": "a", "subtask_name": "old", "waypoints": []},
            {"id": "b", "subtask_name": "other", "waypoints": []},
        ],
    }
    subtasks = [
        create_empty_subtask("new_go", "/maps/new.yaml"),
        create_empty_subtask("other", "/maps/other.yaml"),
    ]

    saved_path = save_task_document_file(
        path,
        {
            "document_type": "task_group",
            "task_group": task_group,
            "subtasks": subtasks,
        },
    )
    saved = json.loads(saved_path.read_text(encoding="utf-8"))

    assert saved_path == path
    assert saved["task_group_name"] == "delivery"
    assert saved["selected_subtask_ids"] == ["a"]
    assert saved["subtasks"][0]["id"] == "a"
    assert saved["subtasks"][0]["subtask_name"] == "new_go"
    assert saved["subtasks"][0]["map_url"] == "/maps/new.yaml"


def test_save_subtask_file_preserves_single_file_runtime_shape(tmp_path):
    path = tmp_path / "outdoor.json"
    subtask = create_empty_subtask("outdoor", "/maps/outdoor.yaml")
    subtask["waypoints"].append(
        {
            "waypoint_id": "outdoor_0",
            "pose": {
                "position": {"x": 0.5, "y": -1.0, "z": 0},
                "orientation": {"x": 0, "y": 0, "z": 0, "w": 1},
            },
            "speed_mode": "task_point",
            "waypoint_task_id": "start_task_w_3D",
            "is_task_point": True,
            "is_single_point": True,
            "is_backward": False,
        }
    )

    saved_path = save_subtask_file(path, subtask)
    saved = json.loads(saved_path.read_text(encoding="utf-8"))

    assert saved_path == path
    assert list(saved.keys()) == ["change_loc", "map_url", "pcd_url", "subtask_name", "waypoints"]
    assert "task_group_name" not in saved
    assert "subtasks" not in saved
    assert saved["waypoints"][0]["waypoint_task_id"] == "start_task_w_3D"


def test_build_return_subtask_reverses_waypoints_rotates_yaw_and_clears_task_ids():
    forward = create_empty_subtask("indoor", "/maps/indoor.yaml")
    forward["waypoints"] = [
        {
            "waypoint_id": "indoor_0",
            "pose": {
                "position": {"x": 1.0, "y": 0.0, "z": 0},
                "orientation": {"x": 0, "y": 0, "z": 0, "w": 1},
            },
            "speed_mode": "task_point",
            "waypoint_task_id": "open_door_go",
            "is_task_point": True,
            "is_single_point": True,
            "is_backward": False,
        },
        {
            "waypoint_id": "indoor_1",
            "pose": {
                "position": {"x": 2.0, "y": 0.0, "z": 0},
                "orientation": {"x": 0, "y": 0, "z": 1, "w": 0},
            },
            "speed_mode": "elevator_in",
            "waypoint_task_id": "elevator_out_3_5",
            "is_task_point": True,
            "is_single_point": True,
            "is_backward": False,
        },
    ]

    returned = build_return_subtask(forward, subtask_name="indoor_r", waypoint_prefix="indoor_back")

    assert returned["subtask_name"] == "indoor_r"
    assert returned["map_url"] == "/maps/indoor.yaml"
    assert [wp["waypoint_id"] for wp in returned["waypoints"]] == ["indoor_back_0", "indoor_back_1"]
    assert [wp["pose"]["position"]["x"] for wp in returned["waypoints"]] == [2.0, 1.0]
    assert [wp["speed_mode"] for wp in returned["waypoints"]] == ["elevator_in", "task_point"]
    assert [wp["waypoint_task_id"] for wp in returned["waypoints"]] == ["", ""]
    assert [wp["is_task_point"] for wp in returned["waypoints"]] == [False, False]
    first_orientation = returned["waypoints"][0]["pose"]["orientation"]
    second_orientation = returned["waypoints"][1]["pose"]["orientation"]
    assert first_orientation == {"x": 0, "y": 0, "z": 0, "w": -1}
    assert math.isclose(second_orientation["z"], 1)
    assert math.isclose(second_orientation["w"], 0)
