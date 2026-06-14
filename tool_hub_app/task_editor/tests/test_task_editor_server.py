import json
import sys
from pathlib import Path

import pytest

import runtime_paths
from task_editor.server import create_app


@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_load_task_bundle_reports_missing_sidecar(client, tmp_path):
    task_path = tmp_path / "delivery_demo.json"
    task_path.write_text(
        json.dumps(
            {
                "task_group_name": "delivery_demo",
                "subtasks": [{"subtask_name": "main_road", "waypoints": []}],
            }
        ),
        encoding="utf-8",
    )

    response = client.post("/api/load_task_bundle", json={"path": str(task_path)})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["task"]["task_group_name"] == "delivery_demo"
    assert payload["sidecar_exists"] is False
    assert payload["sidecar_path"].endswith("delivery_demo.workspace.json")


def test_load_task_bundle_ignores_empty_sidecar(client, tmp_path):
    task_path = tmp_path / "delivery_demo.json"
    sidecar_path = tmp_path / "delivery_demo.workspace.json"
    task_path.write_text(
        json.dumps(
            {
                "task_group_name": "delivery_demo",
                "subtasks": [{"subtask_name": "main_road", "waypoints": []}],
            }
        ),
        encoding="utf-8",
    )
    sidecar_path.write_text("", encoding="utf-8")

    response = client.post("/api/load_task_bundle", json={"path": str(task_path)})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["task"]["task_group_name"] == "delivery_demo"
    assert payload["sidecar_exists"] is False
    assert payload["workspace"] is None
    assert "sidecar_error" in payload


def test_save_task_bundle_rebuilds_invalid_sidecar(client, tmp_path):
    task_path = tmp_path / "delivery_demo.json"
    sidecar_path = tmp_path / "delivery_demo.workspace.json"
    edited_task = {
        "task_group_name": "delivery_demo",
        "subtasks": [{"subtask_name": "main_road", "waypoints": []}],
    }
    task_path.write_text(json.dumps(edited_task), encoding="utf-8")
    sidecar_path.write_text("not json", encoding="utf-8")

    response = client.post(
        "/api/save_task_bundle",
        json={"path": str(task_path), "task": edited_task},
    )
    payload = response.get_json()
    saved_sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    assert response.status_code == 200
    assert payload["workspace"]["task_group_name"] == "delivery_demo"
    assert saved_sidecar["task_group_name"] == "delivery_demo"
    assert saved_sidecar["subtasks"][0]["subtask_name"] == "main_road"


def test_build_task_workspace_sidecar_creates_adjacent_file(client, tmp_path):
    task_path = tmp_path / "delivery_demo.json"
    task_path.write_text(
        json.dumps(
            {
                "task_group_name": "delivery_demo",
                "subtasks": [
                    {"subtask_name": "main_road", "waypoints": []},
                    {"subtask_name": "main_road_r", "waypoints": []},
                ],
            }
        ),
        encoding="utf-8",
    )

    response = client.post(
        "/api/build_task_workspace_sidecar",
        json={"path": str(task_path)},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["workspace"]["task_group_name"] == "delivery_demo"
    assert payload["sidecar_path"].endswith("delivery_demo.workspace.json")
    assert tmp_path.joinpath("delivery_demo.workspace.json").is_file()


def test_save_task_bundle_updates_sidecar_snapshot(client, tmp_path):
    task_path = tmp_path / "delivery_demo.json"
    sidecar_path = tmp_path / "delivery_demo.workspace.json"
    task_document = {
        "task_group_name": "delivery_demo",
        "subtasks": [
            {"subtask_name": "main_road", "waypoints": [{"waypoint_id": "old-forward"}]},
            {"subtask_name": "main_road_r", "waypoints": [{"waypoint_id": "old-return"}]},
        ],
    }
    task_path.write_text(json.dumps(task_document), encoding="utf-8")
    sidecar_path.write_text(
        json.dumps(
            {
                "version": 1,
                "workspace_name": "delivery_demo",
                "task_group_name": "delivery_demo",
                "subtasks": [
                    {
                        "id": "fwd",
                        "pair_id": "pair-1",
                        "direction": "forward",
                        "subtask_name": "main_road",
                        "waypoints": [{"waypoint_id": "old-forward"}],
                    },
                    {
                        "id": "ret",
                        "pair_id": "pair-1",
                        "direction": "return",
                        "subtask_name": "main_road_r",
                        "waypoints": [{"waypoint_id": "old-return"}],
                    },
                ],
                "selected_subtask_ids": ["fwd", "ret"],
            }
        ),
        encoding="utf-8",
    )

    edited_task = {
        "task_group_name": "delivery_demo_v2",
        "subtasks": [
            {"subtask_name": "main_road_custom", "waypoints": [{"waypoint_id": "new-forward"}]},
            {"subtask_name": "main_road_custom_r", "waypoints": [{"waypoint_id": "new-return"}]},
        ],
    }

    response = client.post(
        "/api/save_task_bundle",
        json={"path": str(task_path), "task": edited_task},
    )
    payload = response.get_json()

    saved_task = json.loads(task_path.read_text(encoding="utf-8"))
    saved_sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    assert response.status_code == 200
    assert payload["sidecar_path"].endswith("delivery_demo.workspace.json")
    assert saved_task["task_group_name"] == "delivery_demo_v2"
    assert saved_sidecar["task_group_name"] == "delivery_demo_v2"
    assert saved_sidecar["subtasks"][0]["subtask_name"] == "main_road_custom"
    assert saved_sidecar["subtasks"][1]["waypoints"][0]["waypoint_id"] == "new-return"


def test_create_app_supports_url_prefix(tmp_path):
    app = create_app({"TESTING": True}, url_prefix="/task-editor")
    client = app.test_client()
    task_path = tmp_path / "demo.json"
    task_path.write_text('{"task_group_name":"demo","subtasks":[]}', encoding="utf-8")

    page_response = client.get("/task-editor")
    api_response = client.post(
        "/task-editor/api/load_task_bundle",
        json={"path": str(task_path)},
    )

    assert page_response.status_code == 200
    assert b"Task Editor" in page_response.data
    assert b"/task-editor/api/attributes" in page_response.data
    assert b'role="tablist"' in page_response.data
    assert b"tab-button" in page_response.data
    assert b"resolveTabButtonFromPoint" in page_response.data
    assert b"addEventListener('pointerdown'" in page_response.data
    assert b"change_loc" in page_response.data
    assert b"f-change-loc" in page_response.data
    assert b"renderSubtaskMeta" in page_response.data
    assert api_response.status_code == 200
    assert api_response.get_json()["task"]["task_group_name"] == "demo"


def test_task_editor_page_contains_defensive_task_loading_helpers(client):
    response = client.get("/")
    html = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "function normaliseTaskDocument" in html
    assert "function currentSubtask" in html
    assert "function currentWaypoints" in html
    assert "加载失败: " in html


def test_runtime_config_exposes_attrs_and_default_browse_root(tmp_path):
    attrs_dir = tmp_path / "attrs"
    attrs_dir.mkdir()
    app = create_app({"TESTING": True, "ATTRS_DIR": str(attrs_dir)})
    client = app.test_client()

    response = client.get("/api/runtime_config")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["attrs_dir"] == str(attrs_dir)
    assert payload["default_browse_root"] == str(tmp_path)
    assert payload["default_waypoint_tasks_path"] == str(attrs_dir / "waypoint_tasks")
    assert payload["default_speed_modes_path"] == str(attrs_dir / "speed_modes")


def test_source_runtime_paths_use_standalone_tool_hub_app_layout():
    tool_hub_app_dir = Path(__file__).resolve().parents[2]

    assert runtime_paths.source_repo_root() == tool_hub_app_dir
    assert runtime_paths.default_waypoint_attrs_root() == (
        tool_hub_app_dir / "task_execute_server" / "waypoints_attributes"
    )
    assert runtime_paths.default_nav2_tree_nodes_xml() == (
        tool_hub_app_dir / "nav2_behavior_tree" / "nav2_tree_nodes.xml"
    )


def test_frozen_runtime_paths_use_internal_data_dir(monkeypatch, tmp_path):
    exe_path = tmp_path / "RY-Robot-Tool-Hub"
    internal_attrs_dir = tmp_path / "_internal" / "task_execute_server" / "waypoints_attributes"
    internal_attrs_dir.mkdir(parents=True)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_path))

    assert runtime_paths.app_base_dir() == tmp_path / "_internal"
    assert runtime_paths.default_waypoint_attrs_root() == internal_attrs_dir


def test_attributes_can_be_loaded_from_custom_paths(client, tmp_path):
    waypoint_tasks_dir = tmp_path / "custom_waypoint_tasks"
    speed_modes_dir = tmp_path / "custom_speed_modes"
    single_point_dir = speed_modes_dir / "single_point"
    waypoint_tasks_dir.mkdir()
    speed_modes_dir.mkdir()
    single_point_dir.mkdir()

    (waypoint_tasks_dir / "door_open.xml").write_text("<root />", encoding="utf-8")
    (speed_modes_dir / "slow.xml").write_text("<root />", encoding="utf-8")
    (single_point_dir / "dock.xml").write_text("<root />", encoding="utf-8")

    response = client.get(
        "/api/attributes",
        query_string={
            "waypoint_tasks_path": str(waypoint_tasks_dir),
            "speed_modes_path": str(speed_modes_dir),
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["waypoint_tasks"] == ["door_open"]
    assert payload["speed_modes"] == ["slow"]
    assert payload["speed_modes_single"] == ["dock"]


def test_attributes_reject_invalid_custom_paths(client, tmp_path):
    missing_dir = tmp_path / "missing_waypoint_tasks"
    speed_modes_dir = tmp_path / "custom_speed_modes"
    speed_modes_dir.mkdir()

    response = client.get(
        "/api/attributes",
        query_string={
            "waypoint_tasks_path": str(missing_dir),
            "speed_modes_path": str(speed_modes_dir),
        },
    )

    assert response.status_code == 400
    assert "waypoint_tasks_path" in response.get_json()["error"]


def test_attributes_returns_empty_lists_when_default_dirs_are_missing(tmp_path):
    attrs_dir = tmp_path / "attrs"
    attrs_dir.mkdir()
    app = create_app({"TESTING": True, "ATTRS_DIR": str(attrs_dir)})
    client = app.test_client()

    response = client.get("/api/attributes")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["waypoint_tasks"] == []
    assert payload["speed_modes"] == []
    assert payload["speed_modes_single"] == []


def test_task_editor_source_page_includes_tab_hit_fix():
    tool_hub_app_dir = Path(__file__).resolve().parents[2]
    expected_markers = [
        "role=\"tablist\"",
        "tab-button",
        "resolveTabButtonFromPoint",
        "addEventListener('pointerdown'",
        "function normaliseTaskDocument",
        "function currentSubtask",
        "function currentWaypoints",
        "加载失败: ",
    ]
    html_path = tool_hub_app_dir / "task_editor" / "static" / "index.html"
    html = html_path.read_text(encoding="utf-8")

    for marker in expected_markers:
        assert marker in html, f"{html_path} is missing {marker}"
