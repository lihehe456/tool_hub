import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from uuid import uuid4


DEFAULT_WAYPOINT_FIELDS = {
    "waypoint_task_id": "",
    "is_task_point": False,
    "speed_mode": "normal",
    "is_backward": False,
    "is_single_point": False,
}


def _timestamp():
    return datetime.now().astimezone().isoformat()


def _rotate_orientation_180(orientation):
    return {
        "x": -orientation["y"],
        "y": orientation["x"],
        "z": orientation["w"],
        "w": -orientation["z"],
    }


def _build_waypoint(pose):
    waypoint = {
        "waypoint_id": pose.get("waypoint_id", ""),
        **DEFAULT_WAYPOINT_FIELDS,
        "pose": {
            "position": deepcopy(pose["position"]),
            "orientation": deepcopy(pose["orientation"]),
        },
    }
    return waypoint


def _build_return_waypoint(waypoint):
    return {
        "waypoint_id": waypoint.get("waypoint_id", ""),
        **DEFAULT_WAYPOINT_FIELDS,
        "pose": {
            "position": deepcopy(waypoint["pose"]["position"]),
            "orientation": _rotate_orientation_180(waypoint["pose"]["orientation"]),
        },
    }


def build_subtask_pair_from_path_document(path_document, source_path, generated_subtask_name):
    pair_id = str(uuid4())
    waypoints = [_build_waypoint(pose) for pose in path_document.get("poses", [])]

    forward_subtask = {
        "id": str(uuid4()),
        "pair_id": pair_id,
        "source_path": str(source_path),
        "source_path_name": Path(source_path).name,
        "direction": "forward",
        "generated_subtask_name": generated_subtask_name,
        "subtask_name": generated_subtask_name,
        "map_url": path_document.get("map_url", ""),
        "pcd_url": path_document.get("pcd_url", ""),
        "change_loc": path_document.get("change_loc", False),
        "waypoints": waypoints,
        "generated_at": _timestamp(),
    }

    return_subtask = {
        "id": str(uuid4()),
        "pair_id": pair_id,
        "source_path": str(source_path),
        "source_path_name": Path(source_path).name,
        "direction": "return",
        "generated_subtask_name": f"{generated_subtask_name}_r",
        "subtask_name": f"{generated_subtask_name}_r",
        "map_url": path_document.get("map_url", ""),
        "pcd_url": path_document.get("pcd_url", ""),
        "change_loc": path_document.get("change_loc", False),
        "waypoints": [_build_return_waypoint(waypoint) for waypoint in reversed(waypoints)],
        "generated_at": _timestamp(),
    }

    return forward_subtask, return_subtask


def create_workspace(workspace_name):
    return {
        "version": 1,
        "workspace_name": workspace_name,
        "task_group_name": workspace_name,
        "subtasks": [],
        "selected_subtask_ids": [],
        "output_task_path": "",
        "updated_at": _timestamp(),
    }


def create_mixer_workspace(workspace_name):
    return create_workspace(workspace_name)


def load_workspace_file(path):
    workspace_path = Path(path)
    return json.loads(workspace_path.read_text(encoding="utf-8"))


def save_workspace_file(path, workspace):
    workspace_path = Path(path)
    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    next_workspace = deepcopy(workspace)
    next_workspace["updated_at"] = _timestamp()
    workspace_path.write_text(
        json.dumps(next_workspace, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return next_workspace


def add_subtask_pair(workspace, new_pair):
    next_workspace = deepcopy(workspace)
    next_workspace["subtasks"] = next_workspace.get("subtasks", []) + list(new_pair)
    next_workspace["updated_at"] = _timestamp()
    return next_workspace


def _clone_subtask_for_mixer(subtask, local_pair_id, source_workspace_path, source_task_group_name):
    source_pair_id = subtask.get("source_pair_id") or subtask.get("pair_id") or subtask.get("id") or str(uuid4())
    return {
        **deepcopy(subtask),
        "id": str(uuid4()),
        "pair_id": local_pair_id,
        "source_workspace_path": str(source_workspace_path),
        "source_task_group_name": source_task_group_name,
        "source_pair_id": source_pair_id,
        "imported_at": _timestamp(),
    }


def import_sidecar_workspace_into_mixer(mixer_workspace, sidecar_workspace, source_workspace_path):
    next_workspace = deepcopy(mixer_workspace)
    source_workspace_path = str(source_workspace_path)
    existing_source_ids = {
        subtask["id"]
        for subtask in next_workspace.get("subtasks", [])
        if subtask.get("source_workspace_path") == source_workspace_path
    }
    next_workspace["subtasks"] = [
        subtask
        for subtask in next_workspace.get("subtasks", [])
        if subtask.get("source_workspace_path") != source_workspace_path
    ]
    next_workspace["selected_subtask_ids"] = [
        subtask_id
        for subtask_id in next_workspace.get("selected_subtask_ids", [])
        if subtask_id not in existing_source_ids
    ]

    local_pair_ids = {}
    imported_subtasks = []
    for subtask in sidecar_workspace.get("subtasks", []):
        source_pair_id = subtask.get("pair_id") or subtask.get("source_pair_id") or subtask.get("id") or str(uuid4())
        local_pair_id = local_pair_ids.setdefault(source_pair_id, str(uuid4()))
        imported_subtasks.append(
            _clone_subtask_for_mixer(
                subtask,
                local_pair_id=local_pair_id,
                source_workspace_path=source_workspace_path,
                source_task_group_name=sidecar_workspace.get("task_group_name", ""),
            )
        )

    next_workspace["subtasks"] = next_workspace.get("subtasks", []) + imported_subtasks
    next_workspace["updated_at"] = _timestamp()
    return next_workspace


def replace_subtask_pair(workspace, old_pair_id, new_pair):
    next_workspace = deepcopy(workspace)
    existing_ids = {
        subtask["id"]
        for subtask in next_workspace.get("subtasks", [])
        if subtask.get("pair_id") == old_pair_id
    }
    next_workspace["subtasks"] = [
        subtask
        for subtask in next_workspace.get("subtasks", [])
        if subtask.get("pair_id") != old_pair_id
    ] + list(new_pair)
    next_workspace["selected_subtask_ids"] = [
        subtask_id
        for subtask_id in next_workspace.get("selected_subtask_ids", [])
        if subtask_id not in existing_ids
    ]
    next_workspace["updated_at"] = _timestamp()
    return next_workspace


def export_task_group_document(workspace):
    exported_fields = {
        "subtask_name",
        "map_url",
        "pcd_url",
        "change_loc",
        "waypoints",
    }
    by_id = {
        subtask["id"]: subtask
        for subtask in workspace.get("subtasks", [])
    }
    ordered_subtasks = [
        {
            key: deepcopy(value)
            for key, value in by_id[subtask_id].items()
            if key in exported_fields
        }
        for subtask_id in workspace.get("selected_subtask_ids", [])
        if subtask_id in by_id
    ]
    return {
        "task_group_name": workspace.get("task_group_name", ""),
        "subtasks": ordered_subtasks,
    }


def sidecar_path_for_task_group_path(task_group_path):
    task_group_file = Path(task_group_path)
    if task_group_file.suffix == ".json":
        return task_group_file.with_suffix(".workspace.json")
    return task_group_file.with_name(f"{task_group_file.name}.workspace.json")


def _runtime_subtask_snapshot(task_subtask):
    return {
        "subtask_name": task_subtask.get("subtask_name", ""),
        "generated_subtask_name": task_subtask.get("subtask_name", ""),
        "map_url": task_subtask.get("map_url", ""),
        "pcd_url": task_subtask.get("pcd_url", ""),
        "change_loc": task_subtask.get("change_loc", False),
        "waypoints": deepcopy(task_subtask.get("waypoints", [])),
    }


def _subtask_base_name(subtask_name):
    if subtask_name.endswith("_r"):
        return subtask_name[:-2]
    return subtask_name


def _pair_runtime_subtasks(runtime_subtasks):
    grouped = {}
    for index, subtask in enumerate(runtime_subtasks):
        subtask_name = subtask.get("subtask_name", "")
        base_name = _subtask_base_name(subtask_name)
        direction = "return" if subtask_name.endswith("_r") else "forward"
        group = grouped.setdefault(base_name, {"forward": [], "return": []})
        group[direction].append((index, subtask))

    can_use_name_pairing = (
        runtime_subtasks
        and all(len(group["forward"]) == 1 and len(group["return"]) == 1 for group in grouped.values())
    )
    if can_use_name_pairing:
        ordered_groups = sorted(
            grouped.values(),
            key=lambda group: min(group["forward"][0][0], group["return"][0][0]),
        )
        return [
            {
                "forward": group["forward"][0],
                "return": group["return"][0],
            }
            for group in ordered_groups
        ]

    pairs = []
    index = 0
    while index < len(runtime_subtasks):
        forward_item = (index, runtime_subtasks[index])
        return_item = (index + 1, runtime_subtasks[index + 1]) if index + 1 < len(runtime_subtasks) else None
        pairs.append(
            {
                "forward": forward_item,
                "return": return_item,
            }
        )
        index += 2
    return pairs


def build_workspace_from_task_group_document(task_document, task_group_path):
    task_group_file = Path(task_group_path)
    workspace_name = task_group_file.stem
    workspace = create_workspace(workspace_name)
    workspace["task_group_name"] = task_document.get("task_group_name", workspace_name)
    workspace["output_task_path"] = str(task_group_file)

    selected_subtask_ids = []
    index_to_subtask_id = {}

    for pair in _pair_runtime_subtasks(task_document.get("subtasks", [])):
        pair_id = str(uuid4())
        for direction in ("forward", "return"):
            item = pair.get(direction)
            if item is None:
                continue
            index, runtime_subtask = item
            workspace_subtask = {
                "id": str(uuid4()),
                "pair_id": pair_id,
                "source_path": str(task_group_file),
                "source_path_name": task_group_file.name,
                "direction": direction,
                "generated_at": _timestamp(),
                **_runtime_subtask_snapshot(runtime_subtask),
            }
            workspace["subtasks"].append(workspace_subtask)
            index_to_subtask_id[index] = workspace_subtask["id"]

    for index, _runtime_subtask in enumerate(task_document.get("subtasks", [])):
        subtask_id = index_to_subtask_id.get(index)
        if subtask_id:
            selected_subtask_ids.append(subtask_id)

    workspace["selected_subtask_ids"] = selected_subtask_ids
    workspace["updated_at"] = _timestamp()
    return workspace


def sync_workspace_with_task_group_document(workspace, task_document, task_group_path):
    selected_subtask_ids = list(workspace.get("selected_subtask_ids", []))
    runtime_subtasks = list(task_document.get("subtasks", []))
    subtasks_by_id = {
        subtask.get("id"): subtask
        for subtask in workspace.get("subtasks", [])
        if subtask.get("id")
    }

    if len(selected_subtask_ids) != len(runtime_subtasks):
        rebuilt = build_workspace_from_task_group_document(task_document, task_group_path)
        rebuilt["workspace_name"] = workspace.get("workspace_name", rebuilt.get("workspace_name", ""))
        return rebuilt

    if any(subtask_id not in subtasks_by_id for subtask_id in selected_subtask_ids):
        rebuilt = build_workspace_from_task_group_document(task_document, task_group_path)
        rebuilt["workspace_name"] = workspace.get("workspace_name", rebuilt.get("workspace_name", ""))
        return rebuilt

    next_workspace = deepcopy(workspace)
    next_workspace["task_group_name"] = task_document.get(
        "task_group_name",
        next_workspace.get("task_group_name", ""),
    )
    next_workspace["output_task_path"] = str(task_group_path)

    next_subtasks = []
    runtime_by_selected_id = {
        subtask_id: runtime_subtask
        for subtask_id, runtime_subtask in zip(selected_subtask_ids, runtime_subtasks)
    }
    task_group_file = Path(task_group_path)
    for subtask in next_workspace.get("subtasks", []):
        runtime_subtask = runtime_by_selected_id.get(subtask.get("id"))
        if runtime_subtask is None:
            next_subtasks.append(subtask)
            continue
        updated_subtask = {
            **subtask,
            "source_path": str(task_group_file),
            "source_path_name": task_group_file.name,
            **_runtime_subtask_snapshot(runtime_subtask),
        }
        next_subtasks.append(updated_subtask)

    next_workspace["subtasks"] = next_subtasks
    next_workspace["updated_at"] = _timestamp()
    return next_workspace
