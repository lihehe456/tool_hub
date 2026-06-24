from copy import deepcopy
import json
from pathlib import Path


DEFAULT_WAYPOINT_FIELDS = {
    "waypoint_task_id": "",
    "is_task_point": False,
    "speed_mode": "task_point",
    "is_backward": False,
    "is_single_point": True,
}


def create_empty_subtask(subtask_name, map_url="", pcd_url="", change_loc=False):
    return {
        "change_loc": bool(change_loc),
        "map_url": str(map_url or ""),
        "pcd_url": str(pcd_url or ""),
        "subtask_name": str(subtask_name or ""),
        "waypoints": [],
    }


def normalize_waypoint(waypoint, index=0):
    next_waypoint = {
        **DEFAULT_WAYPOINT_FIELDS,
        **deepcopy(waypoint or {}),
    }
    next_waypoint["waypoint_id"] = str(next_waypoint.get("waypoint_id") or f"wp_{index}")
    next_waypoint["waypoint_task_id"] = str(next_waypoint.get("waypoint_task_id") or "")
    next_waypoint["speed_mode"] = str(next_waypoint.get("speed_mode") or "task_point")
    next_waypoint["is_task_point"] = bool(next_waypoint.get("is_task_point", False))
    next_waypoint["is_single_point"] = bool(next_waypoint.get("is_single_point", True))
    next_waypoint["is_backward"] = bool(next_waypoint.get("is_backward", False))

    pose = deepcopy(next_waypoint.get("pose") or {})
    position = deepcopy(pose.get("position") or {})
    orientation = deepcopy(pose.get("orientation") or {})
    next_waypoint["pose"] = {
        "position": {
            "x": float(position.get("x", 0.0)),
            "y": float(position.get("y", 0.0)),
            "z": float(position.get("z", 0.0)),
        },
        "orientation": {
            "x": float(orientation.get("x", 0.0)),
            "y": float(orientation.get("y", 0.0)),
            "z": float(orientation.get("z", 0.0)),
            "w": float(orientation.get("w", 1.0)),
        },
    }
    return next_waypoint


def normalize_subtask(document):
    if not isinstance(document, dict):
        raise ValueError("subtask document must be an object")
    if "subtasks" in document or "task_group_name" in document:
        raise ValueError("expected a single subtask file, not a task group")
    waypoints = document.get("waypoints", [])
    if not isinstance(waypoints, list):
        raise ValueError("waypoints must be a list")
    return {
        "change_loc": bool(document.get("change_loc", False)),
        "map_url": str(document.get("map_url", "")),
        "pcd_url": str(document.get("pcd_url", "")),
        "subtask_name": str(document.get("subtask_name", "")),
        "waypoints": [
            normalize_waypoint(waypoint, index)
            for index, waypoint in enumerate(waypoints)
        ],
    }


def normalize_subtask_from_group(document, index=0):
    if not isinstance(document, dict):
        raise ValueError("subtask document must be an object")
    copy_doc = deepcopy(document)
    copy_doc.pop("subtasks", None)
    copy_doc.pop("task_group_name", None)
    return normalize_subtask(
        {
            "change_loc": copy_doc.get("change_loc", False),
            "map_url": copy_doc.get("map_url", ""),
            "pcd_url": copy_doc.get("pcd_url", ""),
            "subtask_name": copy_doc.get("subtask_name", f"subtask_{index}"),
            "waypoints": copy_doc.get("waypoints", []),
        }
    )


def normalize_task_group(document):
    if not isinstance(document, dict):
        raise ValueError("task group document must be an object")
    subtasks = document.get("subtasks", [])
    if not isinstance(subtasks, list):
        raise ValueError("subtasks must be a list")
    task_group = deepcopy(document)
    return {
        "document_type": "task_group",
        "task_group": task_group,
        "subtasks": [
            normalize_subtask_from_group(subtask, index)
            for index, subtask in enumerate(subtasks)
        ],
        "active_subtask_index": 0 if subtasks else -1,
    }


def normalize_task_document(document):
    if not isinstance(document, dict):
        raise ValueError("task document must be an object")
    if "subtasks" in document or "task_group_name" in document:
        return normalize_task_group(document)
    subtask = normalize_subtask(document)
    return {
        "document_type": "subtask",
        "task_group": None,
        "subtasks": [subtask],
        "active_subtask_index": 0,
    }


def load_subtask_file(path):
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Subtask file not found: {source}")
    return normalize_subtask(json.loads(source.read_text(encoding="utf-8")))


def load_task_document_file(path):
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Task file not found: {source}")
    return normalize_task_document(json.loads(source.read_text(encoding="utf-8")))


def save_subtask_file(path, document):
    target = Path(path).expanduser().resolve()
    if target.suffix.lower() != ".json":
        raise ValueError("path must point to a .json file")
    target.parent.mkdir(parents=True, exist_ok=True)
    subtask = normalize_subtask(document)
    target.write_text(
        json.dumps(subtask, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def save_task_document_file(path, payload):
    target = Path(path).expanduser().resolve()
    if target.suffix.lower() != ".json":
        raise ValueError("path must point to a .json file")
    target.parent.mkdir(parents=True, exist_ok=True)

    document_type = payload.get("document_type", "subtask")
    subtasks = payload.get("subtasks", [])
    if document_type == "task_group":
        task_group = deepcopy(payload.get("task_group") or {})
        original_subtasks = task_group.get("subtasks", [])
        if not isinstance(original_subtasks, list):
            original_subtasks = []
        next_subtasks = []
        for index, subtask in enumerate(subtasks):
            base = deepcopy(original_subtasks[index]) if index < len(original_subtasks) else {}
            normalized = normalize_subtask(subtask)
            base.update(normalized)
            next_subtasks.append(base)
        task_group["subtasks"] = next_subtasks
        document = task_group
    else:
        if not subtasks:
            raise ValueError("subtasks is required")
        document = normalize_subtask(subtasks[0])

    target.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def rotate_orientation_180(orientation):
    return {
        "x": -float(orientation.get("y", 0.0)),
        "y": float(orientation.get("x", 0.0)),
        "z": float(orientation.get("w", 1.0)),
        "w": -float(orientation.get("z", 0.0)),
    }


def build_return_subtask(forward_subtask, subtask_name=None, waypoint_prefix=None):
    source = normalize_subtask(forward_subtask)
    return_name = subtask_name or f"{source['subtask_name']}_r"
    prefix = waypoint_prefix or f"{source['subtask_name']}_back"
    returned = create_empty_subtask(
        return_name,
        map_url=source["map_url"],
        pcd_url=source["pcd_url"],
        change_loc=source["change_loc"],
    )
    for index, waypoint in enumerate(reversed(source["waypoints"])):
        next_waypoint = normalize_waypoint(waypoint, index)
        next_waypoint["waypoint_id"] = f"{prefix}_{index}"
        next_waypoint["waypoint_task_id"] = ""
        next_waypoint["is_task_point"] = False
        next_waypoint["pose"]["orientation"] = rotate_orientation_180(
            waypoint["pose"]["orientation"]
        )
        returned["waypoints"].append(next_waypoint)
    return returned
