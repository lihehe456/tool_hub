from path_editor_web.task_group_builder import (
    build_subtask_pair_from_path_document,
    create_mixer_workspace,
    create_workspace,
    export_task_group_document,
    import_sidecar_workspace_into_mixer,
    load_workspace_file,
    replace_subtask_pair,
    save_workspace_file,
)


def test_build_subtask_pair_applies_default_waypoint_fields():
    path_document = {
        "path_name": "1_1",
        "map_url": "/maps/demo/map.yaml",
        "pcd_url": "/maps/demo/map.pcd",
        "change_loc": True,
        "poses": [
            {
                "waypoint_id": "1_1_0",
                "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
            }
        ],
    }

    forward_subtask, return_subtask = build_subtask_pair_from_path_document(
        path_document,
        source_path="/tmp/demo/1_1.json",
        generated_subtask_name="main_road",
    )

    assert forward_subtask["direction"] == "forward"
    assert forward_subtask["subtask_name"] == "main_road"
    assert forward_subtask["waypoints"][0]["speed_mode"] == "normal"
    assert forward_subtask["waypoints"][0]["is_single_point"] is False
    assert return_subtask["direction"] == "return"
    assert return_subtask["subtask_name"] == "main_road_r"
    assert return_subtask["waypoints"][0]["waypoint_task_id"] == ""


def test_return_subtask_reverses_waypoints_and_rotates_orientation():
    path_document = {
        "path_name": "1_1",
        "poses": [
            {
                "waypoint_id": "a",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "orientation": {"x": 0.1, "y": 0.2, "z": 0.3, "w": 0.4},
            },
            {
                "waypoint_id": "b",
                "position": {"x": 1.0, "y": 1.0, "z": 0.0},
                "orientation": {"x": 0.5, "y": 0.6, "z": 0.7, "w": 0.8},
            },
        ],
    }

    _, return_subtask = build_subtask_pair_from_path_document(
        path_document,
        source_path="/tmp/demo/1_1.json",
        generated_subtask_name="main_road",
    )

    assert [waypoint["waypoint_id"] for waypoint in return_subtask["waypoints"]] == ["b", "a"]
    assert return_subtask["waypoints"][0]["pose"]["orientation"] == {
        "x": -0.6,
        "y": 0.5,
        "z": 0.8,
        "w": -0.7,
    }


def test_workspace_round_trip_and_replace_pair(tmp_path):
    workspace_path = tmp_path / "workspace.json"
    workspace = create_workspace("demo-workspace")
    forward_subtask = {
        "id": "fwd",
        "pair_id": "pair-1",
        "source_path": "/tmp/a.json",
        "direction": "forward",
    }
    return_subtask = {
        "id": "ret",
        "pair_id": "pair-1",
        "source_path": "/tmp/a.json",
        "direction": "return",
    }

    workspace["subtasks"] = [forward_subtask, return_subtask]
    save_workspace_file(workspace_path, workspace)
    loaded = load_workspace_file(workspace_path)

    replacement_workspace = replace_subtask_pair(
        loaded,
        old_pair_id="pair-1",
        new_pair=[
            {
                "id": "fwd-2",
                "pair_id": "pair-2",
                "source_path": "/tmp/a.json",
                "direction": "forward",
            },
            {
                "id": "ret-2",
                "pair_id": "pair-2",
                "source_path": "/tmp/a.json",
                "direction": "return",
            },
        ],
    )

    assert loaded["workspace_name"] == "demo-workspace"
    assert [item["id"] for item in replacement_workspace["subtasks"]] == ["fwd-2", "ret-2"]


def test_export_task_group_document_uses_selected_ids_and_current_names():
    workspace = {
        "task_group_name": "delivery_demo",
        "subtasks": [
            {"id": "ret", "subtask_name": "main_road_r", "waypoints": []},
            {"id": "fwd", "subtask_name": "main_road_custom", "waypoints": []},
        ],
        "selected_subtask_ids": ["fwd", "ret"],
    }

    task_group = export_task_group_document(workspace)

    assert task_group["task_group_name"] == "delivery_demo"
    assert [item["subtask_name"] for item in task_group["subtasks"]] == [
        "main_road_custom",
        "main_road_r",
    ]


def test_import_sidecar_workspace_into_mixer_copies_subtasks_with_source_metadata():
    mixer_workspace = create_mixer_workspace("mix-demo")
    sidecar_workspace = {
        "workspace_name": "source-sidecar",
        "task_group_name": "delivery_demo",
        "subtasks": [
            {
                "id": "src-fwd",
                "pair_id": "src-pair",
                "direction": "forward",
                "subtask_name": "main_road",
                "waypoints": [],
            },
            {
                "id": "src-ret",
                "pair_id": "src-pair",
                "direction": "return",
                "subtask_name": "main_road_r",
                "waypoints": [],
            },
        ],
        "selected_subtask_ids": ["src-fwd", "src-ret"],
    }

    mixed = import_sidecar_workspace_into_mixer(
        mixer_workspace,
        sidecar_workspace,
        source_workspace_path="/tmp/source.workspace.json",
    )

    assert mixed["workspace_name"] == "mix-demo"
    assert mixed["selected_subtask_ids"] == []
    assert len(mixed["subtasks"]) == 2
    assert mixed["subtasks"][0]["id"] != "src-fwd"
    assert mixed["subtasks"][0]["pair_id"] != "src-pair"
    assert mixed["subtasks"][0]["source_workspace_path"] == "/tmp/source.workspace.json"
    assert mixed["subtasks"][0]["source_task_group_name"] == "delivery_demo"
    assert mixed["subtasks"][0]["source_pair_id"] == "src-pair"


def test_import_sidecar_workspace_into_mixer_replaces_existing_source_and_clears_old_selection():
    mixer_workspace = {
        "version": 1,
        "workspace_name": "mix-demo",
        "task_group_name": "mix-result",
        "subtasks": [
            {
                "id": "old-fwd",
                "pair_id": "local-old-pair",
                "direction": "forward",
                "subtask_name": "main_road",
                "source_workspace_path": "/tmp/source.workspace.json",
                "source_task_group_name": "delivery_demo",
                "source_pair_id": "src-pair",
                "waypoints": [],
            },
            {
                "id": "old-ret",
                "pair_id": "local-old-pair",
                "direction": "return",
                "subtask_name": "main_road_r",
                "source_workspace_path": "/tmp/source.workspace.json",
                "source_task_group_name": "delivery_demo",
                "source_pair_id": "src-pair",
                "waypoints": [],
            },
            {
                "id": "other-fwd",
                "pair_id": "local-other-pair",
                "direction": "forward",
                "subtask_name": "to_door",
                "source_workspace_path": "/tmp/other.workspace.json",
                "source_task_group_name": "other_demo",
                "source_pair_id": "other-pair",
                "waypoints": [],
            },
        ],
        "selected_subtask_ids": ["old-fwd", "other-fwd"],
    }
    replacement_source = {
        "workspace_name": "source-sidecar",
        "task_group_name": "delivery_demo_v2",
        "subtasks": [
            {
                "id": "new-src-fwd",
                "pair_id": "new-src-pair",
                "direction": "forward",
                "subtask_name": "main_road_v2",
                "waypoints": [],
            },
            {
                "id": "new-src-ret",
                "pair_id": "new-src-pair",
                "direction": "return",
                "subtask_name": "main_road_v2_r",
                "waypoints": [],
            },
        ],
        "selected_subtask_ids": [],
    }

    mixed = import_sidecar_workspace_into_mixer(
        mixer_workspace,
        replacement_source,
        source_workspace_path="/tmp/source.workspace.json",
    )

    assert [subtask["subtask_name"] for subtask in mixed["subtasks"]] == [
        "to_door",
        "main_road_v2",
        "main_road_v2_r",
    ]
    assert mixed["selected_subtask_ids"] == ["other-fwd"]
    assert all(subtask["id"] not in {"old-fwd", "old-ret"} for subtask in mixed["subtasks"])
