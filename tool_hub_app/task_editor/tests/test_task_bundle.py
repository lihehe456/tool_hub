from path_editor_web.task_group_builder import (
    build_workspace_from_task_group_document,
    sidecar_path_for_task_group_path,
    sync_workspace_with_task_group_document,
)


def test_sidecar_path_uses_matching_basename():
    sidecar_path = sidecar_path_for_task_group_path("/tmp/tasks/delivery_demo.json")

    assert str(sidecar_path) == "/tmp/tasks/delivery_demo.workspace.json"


def test_build_workspace_from_task_group_document_preserves_runtime_order():
    task_document = {
        "task_group_name": "delivery_demo",
        "subtasks": [
            {"subtask_name": "main_road", "map_url": "/maps/a.yaml", "waypoints": [{"waypoint_id": "a"}]},
            {"subtask_name": "to_door", "map_url": "/maps/a.yaml", "waypoints": [{"waypoint_id": "b"}]},
            {"subtask_name": "to_door_r", "map_url": "/maps/a.yaml", "waypoints": [{"waypoint_id": "c"}]},
            {"subtask_name": "main_road_r", "map_url": "/maps/a.yaml", "waypoints": [{"waypoint_id": "d"}]},
        ],
    }

    workspace = build_workspace_from_task_group_document(
        task_document,
        task_group_path="/tmp/tasks/delivery_demo.json",
    )

    subtasks_by_id = {subtask["id"]: subtask for subtask in workspace["subtasks"]}

    assert workspace["workspace_name"] == "delivery_demo"
    assert workspace["task_group_name"] == "delivery_demo"
    assert [subtask["subtask_name"] for subtask in workspace["subtasks"]] == [
        "main_road",
        "main_road_r",
        "to_door",
        "to_door_r",
    ]
    assert [subtasks_by_id[subtask_id]["subtask_name"] for subtask_id in workspace["selected_subtask_ids"]] == [
        "main_road",
        "to_door",
        "to_door_r",
        "main_road_r",
    ]


def test_sync_workspace_with_task_group_document_updates_selected_snapshots():
    workspace = {
        "version": 1,
        "workspace_name": "delivery_demo",
        "task_group_name": "delivery_demo",
        "subtasks": [
            {
                "id": "fwd",
                "pair_id": "pair-1",
                "direction": "forward",
                "subtask_name": "main_road",
                "map_url": "/maps/a.yaml",
                "waypoints": [{"waypoint_id": "old-forward"}],
            },
            {
                "id": "ret",
                "pair_id": "pair-1",
                "direction": "return",
                "subtask_name": "main_road_r",
                "map_url": "/maps/a.yaml",
                "waypoints": [{"waypoint_id": "old-return"}],
            },
        ],
        "selected_subtask_ids": ["fwd", "ret"],
    }
    task_document = {
        "task_group_name": "delivery_demo_v2",
        "subtasks": [
            {
                "subtask_name": "main_road_custom",
                "map_url": "/maps/b.yaml",
                "waypoints": [{"waypoint_id": "new-forward"}],
            },
            {
                "subtask_name": "main_road_custom_r",
                "map_url": "/maps/b.yaml",
                "waypoints": [{"waypoint_id": "new-return"}],
            },
        ],
    }

    synced = sync_workspace_with_task_group_document(
        workspace,
        task_document,
        task_group_path="/tmp/tasks/delivery_demo.json",
    )

    assert synced["task_group_name"] == "delivery_demo_v2"
    assert synced["workspace_name"] == "delivery_demo"
    assert synced["subtasks"][0]["subtask_name"] == "main_road_custom"
    assert synced["subtasks"][0]["waypoints"][0]["waypoint_id"] == "new-forward"
    assert synced["subtasks"][1]["subtask_name"] == "main_road_custom_r"
    assert synced["subtasks"][1]["waypoints"][0]["waypoint_id"] == "new-return"
