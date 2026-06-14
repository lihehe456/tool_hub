import json
import subprocess
import sys
from pathlib import Path

import pytest

from path_editor_web.server import create_app


@pytest.fixture
def sample_map(tmp_path):
    map_dir = tmp_path / "maps"
    map_dir.mkdir()
    pgm_path = map_dir / "map.pgm"
    yaml_path = map_dir / "map.yaml"

    pgm_path.write_bytes(
        b"P5\n"
        b"4 3\n"
        b"255\n"
        + bytes(
            [
                0, 64, 128, 255,
                255, 128, 64, 0,
                10, 20, 30, 40,
            ]
        )
    )
    yaml_path.write_text(
        "\n".join(
            [
                "image: map.pgm",
                "resolution: 0.05",
                "origin: [1.0, 2.0, 0.0]",
            ]
        ),
        encoding="utf-8",
    )

    return {"dir": map_dir, "yaml": yaml_path, "pgm": pgm_path}


@pytest.fixture
def sample_path_dir(tmp_path):
    paths_dir = tmp_path / "paths"
    demo_dir = paths_dir / "demo"
    demo_dir.mkdir(parents=True)
    existing_path = demo_dir / "existing.json"
    existing_path.write_text(
        json.dumps(
            {
                "path_name": "existing",
                "community": "demo",
                "poses": [],
            }
        ),
        encoding="utf-8",
    )
    pair_path = demo_dir / "pair.json"
    pair_path.write_text(
        json.dumps(
            {
                "path_name": "pair",
                "community": "demo",
                "map_url": "/maps/demo/map.yaml",
                "pcd_url": "/maps/demo/map.pcd",
                "change_loc": True,
                "poses": [
                    {
                        "waypoint_id": "pair_0",
                        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    },
                    {
                        "waypoint_id": "pair_1",
                        "position": {"x": 1.0, "y": 1.0, "z": 0.0},
                        "orientation": {"x": 0.1, "y": 0.2, "z": 0.3, "w": 0.4},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return paths_dir


@pytest.fixture
def client(sample_map, sample_path_dir):
    app = create_app(
        {
            "TESTING": True,
            "MAPS_ROOT": str(sample_map["dir"].parent),
            "PATHS_ROOT": str(sample_path_dir),
        }
    )
    return app.test_client()


def test_index_serves_shell(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Path Editor Web" in response.data
    assert b"point-info" in response.data
    assert b"\xe7\x82\xb9\xe4\xbf\xa1\xe6\x81\xaf" in response.data
    assert b"/home/lmy/LMY/0_Code/FusionCloudRobot/paths" not in response.data
    assert b"/home/lmy/LMY/0_Code/FusionCloudRobot/maps" not in response.data


def test_runtime_config_exposes_current_roots(client, sample_map, sample_path_dir):
    response = client.get("/api/runtime_config")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["paths_root"] == str(sample_path_dir)
    assert payload["maps_root"] == str(sample_map["dir"].parent)


def test_runtime_config_defaults_to_opt_ry_work_root():
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.get("/api/runtime_config")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["paths_root"] == "/opt/ry"
    assert payload["maps_root"] == "/opt/ry"
    assert payload["user_root"] == "/opt/ry"


def test_browse_user_files_defaults_to_opt_ry_work_root():
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.post("/api/browse_user_files", json={})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["cwd"] == "/opt/ry"


def test_load_map_returns_png_and_metadata(client, sample_map):
    response = client.post("/api/load_map", json={"yaml_path": str(sample_map["yaml"])})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["resolution"] == 0.05
    assert payload["origin"] == [1.0, 2.0, 0.0]
    assert payload["width"] == 4
    assert payload["height"] == 3
    assert isinstance(payload["image_b64"], str)
    assert payload["image_b64"]
    assert payload["virtual_wall_path"] is None
    assert payload["virtual_walls"] == []


@pytest.mark.parametrize("wall_filename", ["map_walls.yaml", "map_wall.yaml", "map-wall.yaml", "map-walls.yaml"])
def test_load_map_includes_same_directory_virtual_wall_overlay(client, sample_map, wall_filename):
    wall_path = sample_map["dir"] / wall_filename
    wall_path.write_text(
        """
virtual_walls:
  coordinate_mode: image_relative
  frame_id: map
  map_origin: [1.0, 2.0, 0.0]
  thickness: 0.1
  segments:
    - start: [1.0, 2.0, 0.0]
      end: [3.0, 2.0, 0.0]
      thickness: 0.2
""".strip(),
        encoding="utf-8",
    )

    response = client.post("/api/load_map", json={"yaml_path": str(sample_map["yaml"])})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["virtual_wall_path"] == str(wall_path)
    assert payload["virtual_walls"] == [
        {
            "points": [
                {"x": 2.0, "y": 4.0, "z": 0.0},
                {"x": 4.0, "y": 4.0, "z": 0.0},
            ],
            "thickness": 0.2,
        }
    ]


def test_browse_paths_and_load_existing_path(client, sample_path_dir):
    browse_response = client.post(
        "/api/browse_paths",
        json={"path": str(sample_path_dir)},
    )
    browse_payload = browse_response.get_json()

    load_response = client.post(
        "/api/load_path",
        json={"path": str(sample_path_dir / "demo" / "existing.json")},
    )
    load_payload = load_response.get_json()

    assert browse_response.status_code == 200
    assert browse_payload["cwd"] == str(sample_path_dir)
    assert browse_payload["entries"][0]["name"] == "demo"
    assert load_response.status_code == 200
    assert load_payload["path_name"] == "existing"
    assert load_payload["community"] == "demo"


def test_browse_maps_lists_yaml_files(client, sample_map):
    response = client.post(
        "/api/browse_maps",
        json={"path": str(sample_map["dir"])},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["cwd"] == str(sample_map["dir"])
    assert any(entry["name"] == "map.yaml" and entry["is_yaml"] for entry in payload["entries"])


def test_browse_maps_allows_root_directory(client):
    response = client.post("/api/browse_maps", json={"path": "/"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["cwd"] == "/"


def test_load_map_allows_absolute_path_outside_configured_root(client, tmp_path):
    map_dir = tmp_path / "outside_maps"
    map_dir.mkdir()
    pgm_path = map_dir / "outside.pgm"
    yaml_path = map_dir / "outside.yaml"
    pgm_path.write_bytes(b"P5\n1 1\n255\n\x00")
    yaml_path.write_text("image: outside.pgm\nresolution: 0.05\norigin: [0.0, 0.0, 0.0]\n", encoding="utf-8")

    response = client.post("/api/load_map", json={"yaml_path": str(yaml_path)})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["origin"] == [0.0, 0.0, 0.0]


def test_save_rename_delete_path_flow(client, sample_path_dir):
    save_path = sample_path_dir / "demo" / "route.json"
    renamed_path = sample_path_dir / "demo" / "route_2.json"
    document = {"path_name": "route", "community": "demo", "poses": []}

    save_response = client.post(
        "/api/save_path_as",
        json={"path": str(save_path), "document": document},
    )
    overwrite_response = client.post(
        "/api/save_path",
        json={
            "path": str(save_path),
            "document": {"path_name": "route", "community": "demo", "poses": [{"waypoint_id": "x"}]},
        },
    )
    rename_response = client.post(
        "/api/rename_path",
        json={"src_path": str(save_path), "dst_path": str(renamed_path)},
    )
    delete_response = client.post("/api/delete_path", json={"path": str(renamed_path)})

    assert save_response.status_code == 200
    assert overwrite_response.status_code == 200
    assert rename_response.status_code == 200
    assert delete_response.status_code == 200
    assert not renamed_path.exists()


def test_load_map_outside_configured_root_reports_missing_image_file(client, tmp_path):
    outside_map = tmp_path.parent / "outside.yaml"
    outside_map.write_text("image: no.pgm\nresolution: 0.05\norigin: [0, 0, 0]\n", encoding="utf-8")

    response = client.post("/api/load_map", json={"yaml_path": str(outside_map)})

    assert response.status_code == 404
    assert "PGM not found" in response.get_json()["error"]


def test_server_module_can_be_loaded_from_package_directory(monkeypatch):
    server_path = Path(__file__).resolve().parents[1] / "server.py"
    command = [
        sys.executable,
        "-c",
        "import importlib.util, pathlib; "
        "path = pathlib.Path('server.py').resolve(); "
        "spec = importlib.util.spec_from_file_location('server_script', path); "
        "module = importlib.util.module_from_spec(spec); "
        "spec.loader.exec_module(module); "
        "print(callable(module.create_app))",
    ]

    result = subprocess.run(
        command,
        cwd=server_path.parent,
        capture_output=True,
        text=True,
        env={},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


def test_build_subtasks_from_path_returns_forward_and_return_pair(client, sample_path_dir):
    path_file = sample_path_dir / "demo" / "pair.json"

    response = client.post(
        "/api/build_subtasks_from_path",
        json={"path": str(path_file), "generated_subtask_name": "main_road"},
    )

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["forward_subtask"]["direction"] == "forward"
    assert payload["forward_subtask"]["subtask_name"] == "main_road"
    assert payload["return_subtask"]["direction"] == "return"
    assert payload["return_subtask"]["subtask_name"] == "main_road_r"


def test_workspace_round_trip_and_export(client, tmp_path):
    workspace_path = tmp_path / "task-group-workspace.json"
    export_dir = tmp_path / "exports"
    workspace = {
        "version": 1,
        "workspace_name": "demo",
        "task_group_name": "delivery_demo",
        "subtasks": [
            {"id": "fwd", "subtask_name": "main_road", "waypoints": []},
            {"id": "ret", "subtask_name": "main_road_r", "waypoints": []},
        ],
        "selected_subtask_ids": ["fwd", "ret"],
    }

    save_response = client.post(
        "/api/save_task_workspace",
        json={"workspace_path": str(workspace_path), "workspace": workspace},
    )
    load_response = client.post(
        "/api/load_task_workspace",
        json={"workspace_path": str(workspace_path)},
    )
    export_response = client.post(
        "/api/export_task_group",
        json={
            "workspace_path": str(workspace_path),
            "export_directory": str(export_dir),
        },
    )

    assert save_response.status_code == 200
    assert load_response.status_code == 200
    assert load_response.get_json()["workspace"]["workspace_name"] == "demo"
    assert export_response.status_code == 200
    export_path = export_dir / "delivery_demo.json"
    assert export_path.exists()
    assert json.loads(export_path.read_text(encoding="utf-8"))["task_group_name"] == "delivery_demo"


def test_create_task_workspace_creates_once_and_preserves_existing_content(client, tmp_path):
    workspace_path = tmp_path / "generated-workspace.json"

    create_response = client.post(
        "/api/create_task_workspace",
        json={"workspace_path": str(workspace_path)},
    )
    second_response = client.post(
        "/api/create_task_workspace",
        json={"workspace_path": str(workspace_path)},
    )

    assert create_response.status_code == 200
    assert create_response.get_json()["created"] is True
    assert workspace_path.exists()
    assert create_response.get_json()["workspace"]["workspace_name"] == "generated-workspace"
    assert create_response.get_json()["workspace"]["subtasks"] == []

    stored_workspace = json.loads(workspace_path.read_text(encoding="utf-8"))
    stored_workspace["task_group_name"] = "custom_name"
    workspace_path.write_text(json.dumps(stored_workspace, ensure_ascii=False, indent=2), encoding="utf-8")

    third_response = client.post(
        "/api/create_task_workspace",
        json={"workspace_path": str(workspace_path)},
    )

    assert second_response.status_code == 200
    assert second_response.get_json()["created"] is False
    assert third_response.status_code == 200
    assert third_response.get_json()["created"] is False
    assert third_response.get_json()["workspace"]["task_group_name"] == "custom_name"


def test_add_and_replace_subtask_pair_in_workspace(client, sample_path_dir, tmp_path):
    workspace_path = tmp_path / "task-group-workspace.json"
    initial_workspace = {
        "version": 1,
        "workspace_name": "demo",
        "task_group_name": "delivery_demo",
        "subtasks": [],
        "selected_subtask_ids": [],
    }

    save_response = client.post(
        "/api/save_task_workspace",
        json={"workspace_path": str(workspace_path), "workspace": initial_workspace},
    )
    pair_payload = {
        "forward_subtask": {
            "id": "forward-1",
            "pair_id": "pair-1",
            "source_path": str(sample_path_dir / "demo" / "pair.json"),
            "direction": "forward",
            "generated_subtask_name": "main_road",
            "subtask_name": "main_road",
            "waypoints": [],
        },
        "return_subtask": {
            "id": "return-1",
            "pair_id": "pair-1",
            "source_path": str(sample_path_dir / "demo" / "pair.json"),
            "direction": "return",
            "generated_subtask_name": "main_road_r",
            "subtask_name": "main_road_r",
            "waypoints": [],
        },
    }

    add_response = client.post(
        "/api/add_subtask_pair_to_workspace",
        json={
            "workspace_path": str(workspace_path),
            "forward_subtask": pair_payload["forward_subtask"],
            "return_subtask": pair_payload["return_subtask"],
        },
    )
    replacement_pair = {
        "forward_subtask": {
            **pair_payload["forward_subtask"],
            "id": "forward-replacement",
            "pair_id": "replacement-pair",
        },
        "return_subtask": {
            **pair_payload["return_subtask"],
            "id": "return-replacement",
            "pair_id": "replacement-pair",
        },
    }
    replace_response = client.post(
        "/api/replace_subtask_pair_in_workspace",
        json={
            "workspace_path": str(workspace_path),
            "old_pair_id": pair_payload["forward_subtask"]["pair_id"],
            **replacement_pair,
        },
    )

    assert save_response.status_code == 200
    assert add_response.status_code == 200
    assert len(add_response.get_json()["workspace"]["subtasks"]) == 2
    assert replace_response.status_code == 200
    assert [subtask["id"] for subtask in replace_response.get_json()["workspace"]["subtasks"]] == [
        "forward-replacement",
        "return-replacement",
    ]


def test_load_or_create_mixer_workspace_and_import_sidecar_source(client, tmp_path):
    mixer_workspace_path = tmp_path / "mixer.json"
    source_workspace_path = tmp_path / "source.workspace.json"
    source_workspace_path.write_text(
        json.dumps(
            {
                "version": 1,
                "workspace_name": "source",
                "task_group_name": "delivery_demo",
                "subtasks": [
                    {
                        "id": "fwd",
                        "pair_id": "pair-1",
                        "direction": "forward",
                        "subtask_name": "main_road",
                        "waypoints": [],
                    },
                    {
                        "id": "ret",
                        "pair_id": "pair-1",
                        "direction": "return",
                        "subtask_name": "main_road_r",
                        "waypoints": [],
                    },
                ],
                "selected_subtask_ids": ["fwd", "ret"],
            }
        ),
        encoding="utf-8",
    )

    create_response = client.post(
        "/api/load_or_create_mixer_workspace",
        json={"workspace_path": str(mixer_workspace_path)},
    )
    import_response = client.post(
        "/api/import_sidecar_workspace_into_mixer",
        json={
            "workspace_path": str(mixer_workspace_path),
            "source_workspace_path": str(source_workspace_path),
        },
    )

    assert create_response.status_code == 200
    assert create_response.get_json()["created"] is True
    assert create_response.get_json()["workspace"]["workspace_name"] == "mixer"
    assert import_response.status_code == 200
    assert len(import_response.get_json()["workspace"]["subtasks"]) == 2
    assert import_response.get_json()["workspace"]["subtasks"][0]["source_workspace_path"] == str(
        source_workspace_path
    )


def test_import_sidecar_workspace_into_mixer_rejects_non_sidecar_file(client, tmp_path):
    mixer_workspace_path = tmp_path / "mixer.json"
    task_group_path = tmp_path / "task-group.json"
    task_group_path.write_text(json.dumps({"task_group_name": "demo", "subtasks": []}), encoding="utf-8")

    client.post(
        "/api/load_or_create_mixer_workspace",
        json={"workspace_path": str(mixer_workspace_path)},
    )
    response = client.post(
        "/api/import_sidecar_workspace_into_mixer",
        json={
            "workspace_path": str(mixer_workspace_path),
            "source_workspace_path": str(task_group_path),
        },
    )

    assert response.status_code == 400
    assert "workspace.json" in response.get_json()["error"]


def test_browse_user_files_lists_workspace_json_entries(client, tmp_path):
    (tmp_path / "mixer.json").write_text("{}", encoding="utf-8")
    (tmp_path / "source.workspace.json").write_text("{}", encoding="utf-8")
    (tmp_path / "other.txt").write_text("x", encoding="utf-8")

    response = client.post(
        "/api/browse_user_files",
        json={
            "path": str(tmp_path),
            "file_type": "workspace_json",
        },
    )

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["cwd"] == str(tmp_path)
    assert any(entry["name"] == "source.workspace.json" and entry["is_workspace_json"] for entry in payload["entries"])
    assert any(entry["name"] == "mixer.json" and not entry["is_workspace_json"] for entry in payload["entries"])
