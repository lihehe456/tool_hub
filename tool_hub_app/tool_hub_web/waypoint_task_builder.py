from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from uuid import uuid4
import xml.etree.ElementTree as ET

from runtime_paths import default_nav2_tree_nodes_xml

REPO_SRC_DIR = Path(__file__).resolve().parents[2]
NODE_MODEL_XML_PATH = default_nav2_tree_nodes_xml()

MANUAL_NODE_SCHEMAS = {
    "Sequence": {
        "kind": "control",
        "fields": [{"name": "name", "label": "name", "default": ""}],
        "input_ports": [{"name": "name", "label": "name", "default": "", "description": "", "direction": "input"}],
        "output_ports": [],
        "min_children": 0,
    },
    "Fallback": {
        "kind": "control",
        "fields": [{"name": "name", "label": "name", "default": ""}],
        "input_ports": [{"name": "name", "label": "name", "default": "", "description": "", "direction": "input"}],
        "output_ports": [],
        "min_children": 0,
    },
    "ReactiveFallback": {
        "kind": "control",
        "fields": [{"name": "name", "label": "name", "default": ""}],
        "input_ports": [{"name": "name", "label": "name", "default": "", "description": "", "direction": "input"}],
        "output_ports": [],
        "min_children": 0,
    },
    "ReactiveSequence": {
        "kind": "control",
        "fields": [{"name": "name", "label": "name", "default": ""}],
        "input_ports": [{"name": "name", "label": "name", "default": "", "description": "", "direction": "input"}],
        "output_ports": [],
        "min_children": 0,
    },
    "PipelineSequence": {
        "kind": "control",
        "fields": [{"name": "name", "label": "name", "default": ""}],
        "input_ports": [{"name": "name", "label": "name", "default": "", "description": "", "direction": "input"}],
        "output_ports": [],
        "min_children": 0,
    },
    "RoundRobin": {
        "kind": "control",
        "fields": [{"name": "name", "label": "name", "default": ""}],
        "input_ports": [{"name": "name", "label": "name", "default": "", "description": "", "direction": "input"}],
        "output_ports": [],
        "min_children": 0,
    },
    "RecoveryNode": {
        "kind": "control",
        "fields": [
            {"name": "number_of_retries", "label": "number_of_retries", "default": "1"},
            {"name": "name", "label": "name", "default": ""},
        ],
        "input_ports": [
            {
                "name": "number_of_retries",
                "label": "number_of_retries",
                "default": "1",
                "description": "",
                "direction": "input",
            },
            {"name": "name", "label": "name", "default": "", "description": "", "direction": "input"},
        ],
        "output_ports": [],
        "min_children": 1,
        "max_children": 2,
    },
    "RetryUntilSuccessful": {
        "kind": "control",
        "fields": [{"name": "num_attempts", "label": "num_attempts", "default": "1"}],
        "input_ports": [
            {
                "name": "num_attempts",
                "label": "num_attempts",
                "default": "1",
                "description": "",
                "direction": "input",
            }
        ],
        "output_ports": [],
        "min_children": 1,
        "max_children": 1,
    },
    "DoorControl": {
        "kind": "action",
        "fields": [
            {"name": "service_name", "label": "service_name", "default": "/door_control"},
            {"name": "doorid", "label": "doorid", "default": ""},
            {"name": "executeid", "label": "executeid", "default": ""},
            {"name": "success", "label": "success", "default": "{door_success}"},
            {"name": "stateid", "label": "stateid", "default": "{door_state}"},
        ],
    },
    "EnableAmcl": {
        "kind": "action",
        "fields": [
            {"name": "service_name", "label": "service_name", "default": "/enable_amcl"},
            {"name": "data", "label": "data", "default": "true"},
        ],
    },
    "ClampWater": {
        "fields": [
            {"name": "server_name", "label": "server_name", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "OpenPlatform": {
        "fields": [
            {"name": "server_name", "label": "server_name", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "PlaceWater": {
        "fields": [
            {"name": "name", "label": "name", "default": ""},
            {"name": "server_name", "label": "server_name", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "AMCLLifecycleManager": {
        "fields": [
            {"name": "node_name", "label": "node_name", "default": "/amcl"},
            {"name": "action", "label": "action", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "ElevatorStatus": {
        "fields": [
            {"name": "enable", "label": "enable", "default": "true"},
            {"name": "car_status", "label": "car_status", "default": "in"},
            {"name": "server_name", "label": "server_name", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "GetElevatorId": {
        "fields": [
            {"name": "community", "label": "community", "default": ""},
            {"name": "building", "label": "building", "default": ""},
            {"name": "unit", "label": "unit", "default": ""},
            {"name": "floor", "label": "floor", "default": ""},
            {"name": "door", "label": "door", "default": ""},
            {"name": "elevator_id", "label": "elevator_id", "default": "{elevator_id}"},
            {"name": "success", "label": "success", "default": "{get_id_success}"},
            {"name": "service_name", "label": "service_name", "default": "get_elevator_id"},
        ],
    },
    "ElevatorCaller": {
        "fields": [
            {"name": "elevid", "label": "elevid", "default": "{elevator_id}"},
            {"name": "target_floor", "label": "target_floor", "default": ""},
            {"name": "server_name", "label": "server_name", "default": "/elevator_command"},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "ElevatorDoorKeeper": {
        "fields": [
            {"name": "command", "label": "command", "default": ""},
            {"name": "topic_name", "label": "topic_name", "default": "/elevator_open"},
        ],
    },
    "SwitchMap": {
        "fields": [
            {"name": "map_url", "label": "map_url", "default": ""},
            {"name": "service_name", "label": "service_name", "default": "/map_server/load_map"},
        ],
    },
    "SetTfBroadcast": {
        "fields": [
            {"name": "enable", "label": "enable", "default": "true"},
            {"name": "x", "label": "x", "default": "0.0"},
            {"name": "y", "label": "y", "default": "0.0"},
            {"name": "z", "label": "z", "default": "0.0"},
            {"name": "qx", "label": "qx", "default": ""},
            {"name": "qy", "label": "qy", "default": ""},
            {"name": "qz", "label": "qz", "default": ""},
            {"name": "qw", "label": "qw", "default": ""},
            {"name": "odom_topic", "label": "odom_topic", "default": "odom"},
            {"name": "service_name", "label": "service_name", "default": "set_tf_broadcast"},
        ],
    },
    "SetUseWheelOdom": {
        "fields": [
            {"name": "use_wheel_odom", "label": "use_wheel_odom", "default": "true"},
            {"name": "map_path", "label": "map_path", "default": ""},
            {"name": "service_name", "label": "service_name", "default": "/localizer/relocalize"},
        ],
    },
    "ComputePathThroughPoses": {
        "fields": [
            {"name": "goals", "label": "goals", "default": ""},
            {"name": "path", "label": "path", "default": ""},
            {"name": "planner_id", "label": "planner_id", "default": ""},
            {"name": "server_name", "label": "server_name", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "ComputePathToPose": {
        "fields": [
            {"name": "goal", "label": "goal", "default": ""},
            {"name": "path", "label": "path", "default": ""},
            {"name": "planner_id", "label": "planner_id", "default": ""},
            {"name": "server_name", "label": "server_name", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "FollowPath": {
        "fields": [
            {"name": "path", "label": "path", "default": ""},
            {"name": "controller_id", "label": "controller_id", "default": "FollowPath"},
            {"name": "goal_checker_id", "label": "goal_checker_id", "default": ""},
            {"name": "server_name", "label": "server_name", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "ClearEntireCostmap": {
        "fields": [
            {"name": "name", "label": "name", "default": ""},
            {"name": "service_name", "label": "service_name", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "RemovePassedGoals": {
        "fields": [
            {"name": "input_goals", "label": "input_goals", "default": ""},
            {"name": "output_goals", "label": "output_goals", "default": ""},
            {"name": "radius", "label": "radius", "default": ""},
        ],
    },
    "GoalUpdated": {
        "fields": [],
    },
    "RateController": {
        "kind": "control",
        "fields": [{"name": "hz", "label": "hz", "default": ""}],
        "input_ports": [{"name": "hz", "label": "hz", "default": "", "description": "", "direction": "input"}],
        "output_ports": [],
        "min_children": 1,
        "max_children": 1,
    },
    "SetPoseFromOdom": {
        "fields": [
            {"name": "server_name", "label": "server_name", "default": "set_pose_from_odom"},
            {"name": "use_custom_cov", "label": "use_custom_cov", "default": "false"},
            {"name": "cov_x", "label": "cov_x", "default": "0.5"},
            {"name": "cov_y", "label": "cov_y", "default": "0.5"},
            {"name": "cov_yaw", "label": "cov_yaw", "default": "0.26"},
        ],
        "output_ports": [
            {"name": "pose", "label": "pose", "default": "", "description": "", "direction": "output"},
            {"name": "message", "label": "message", "default": "", "description": "", "direction": "output"},
        ],
    },
    "Wait": {
        "fields": [
            {"name": "wait_duration", "label": "wait_duration", "default": ""},
            {"name": "server_name", "label": "server_name", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "StopPlayback": {
        "fields": [
            {"name": "service_name", "label": "service_name", "default": "stop_playback"},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "Spin": {
        "fields": [
            {"name": "spin_dist", "label": "spin_dist", "default": ""},
            {"name": "server_name", "label": "server_name", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "MoveForward": {
        "fields": [
            {"name": "dist", "label": "dist", "default": ""},
            {"name": "speed", "label": "speed", "default": ""},
            {"name": "forward_dist", "label": "forward_dist", "default": ""},
            {"name": "forward_speed", "label": "forward_speed", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "WaitForReturnSignal": {
        "fields": [
            {"name": "timeout_sec", "label": "timeout_sec", "default": ""},
        ],
    },
    "VirtualElevatorJudge": {
        "fields": [
            {"name": "topic_name", "label": "topic_name", "default": ""},
            {"name": "timeout", "label": "timeout", "default": ""},
            {"name": "check_rate", "label": "check_rate", "default": ""},
        ],
    },
    "RotateToGoalYawWithScan": {
        "fields": [
            {"name": "goal", "label": "goal", "default": ""},
            {"name": "scan_topic", "label": "scan_topic", "default": ""},
            {"name": "min_distance", "label": "min_distance", "default": ""},
            {"name": "server_name", "label": "server_name", "default": ""},
            {"name": "server_timeout", "label": "server_timeout", "default": ""},
        ],
    },
    "WebVoicePlayer": {
        "fields": [
            {"name": "text", "label": "text", "default": ""},
            {"name": "model", "label": "model", "default": "cosyvoice-v1"},
            {"name": "voice", "label": "voice", "default": "longxiaochun"},
            {"name": "volume", "label": "volume", "default": "50"},
            {"name": "rate", "label": "rate", "default": "1.0"},
            {"name": "pitch", "label": "pitch", "default": "1.0"},
            {"name": "sample_rate", "label": "sample_rate", "default": "22050"},
            {"name": "format", "label": "format", "default": "mp3"},
            {"name": "loop_count", "label": "loop_count", "default": "1"},
            {"name": "loop_interval", "label": "loop_interval", "default": "0.0"},
            {"name": "priority", "label": "priority", "default": "0"},
        ],
    },
    "PublishTaskStatus": {
        "fields": [{"name": "status_code", "label": "status_code", "default": "000"}],
    },
    "ChangeUssStatus": {
        "fields": [{"name": "status", "label": "status", "default": "true"}],
    },
    "AlwaysFailure": {
        "fields": [],
    },
}


def _clean_text(value):
    return " ".join((value or "").split())


def _port_to_field(port):
    return {
        "name": port["name"],
        "label": port["name"],
        "default": port.get("default", ""),
        "description": port.get("description", ""),
    }


def _normalized_port(port, direction):
    return {
        "name": port["name"],
        "label": port.get("label", port["name"]),
        "default": port.get("default", ""),
        "description": port.get("description", ""),
        "direction": direction,
    }


def _merge_named_entries(base_entries, override_entries):
    base_map = {entry["name"]: dict(entry) for entry in base_entries}
    override_map = {entry["name"]: dict(entry) for entry in override_entries}
    ordered_names = []
    for entry in override_entries:
        if entry["name"] not in ordered_names:
            ordered_names.append(entry["name"])
    for entry in base_entries:
        if entry["name"] not in ordered_names:
            ordered_names.append(entry["name"])
    return [{**base_map.get(name, {}), **override_map.get(name, {})} for name in ordered_names]


def _node_kind_from_model_tag(tag):
    if tag in {"Control", "Decorator"}:
        return "control"
    if tag in {"Action", "Condition"}:
        return "action"
    return "unknown"


def _children_limits_for_model_tag(tag):
    if tag == "Decorator":
        return {"min_children": 1, "max_children": 1}
    if tag == "Control":
        return {"min_children": 0}
    return {}


def _schema_from_model_node(element):
    input_ports = [
        _normalized_port(
            {
                "name": port.attrib["name"],
                "default": port.attrib.get("default", ""),
                "description": _clean_text(port.text),
            },
            "input",
        )
        for port in element.findall("input_port")
        if port.attrib.get("name")
    ]
    output_ports = [
        _normalized_port(
            {
                "name": port.attrib["name"],
                "default": port.attrib.get("default", ""),
                "description": _clean_text(port.text),
            },
            "output",
        )
        for port in element.findall("output_port")
        if port.attrib.get("name")
    ]
    schema = {
        "kind": _node_kind_from_model_tag(element.tag),
        "model_tag": element.tag,
        "fields": [_port_to_field(port) for port in input_ports],
        "input_ports": input_ports,
        "output_ports": output_ports,
    }
    schema.update(_children_limits_for_model_tag(element.tag))
    return schema


def _normalize_manual_schema(name, schema):
    normalized = deepcopy(schema)
    normalized.setdefault("kind", "action")
    normalized.setdefault("fields", [])
    normalized["input_ports"] = deepcopy(normalized.get("input_ports"))
    normalized["output_ports"] = deepcopy(normalized.get("output_ports", []))
    normalized["model_tag"] = normalized.get("model_tag", "Manual")
    return normalized


@lru_cache(maxsize=1)
def _load_supported_node_schemas():
    nodes = {}
    if NODE_MODEL_XML_PATH.is_file():
        try:
            root = ET.parse(NODE_MODEL_XML_PATH).getroot()
        except ET.ParseError:
            root = None
        if root is not None:
            model = root.find("TreeNodesModel")
            for element in list(model or []):
                node_id = element.attrib.get("ID")
                if not node_id:
                    continue
                nodes[node_id] = _schema_from_model_node(element)

    for name, override in MANUAL_NODE_SCHEMAS.items():
        manual_schema = _normalize_manual_schema(name, override)
        base_schema = deepcopy(nodes.get(name, {}))
        manual_input_ports = manual_schema["input_ports"]
        if manual_input_ports is None:
            manual_input_ports = (
                [_normalized_port(_port_to_field(field), "input") for field in manual_schema["fields"]]
                if not base_schema
                else []
            )
        merged = {**base_schema, **manual_schema}
        merged["fields"] = _merge_named_entries(base_schema.get("fields", []), manual_schema.get("fields", []))
        merged["input_ports"] = _merge_named_entries(
            base_schema.get("input_ports", []),
            manual_input_ports,
        )
        merged["output_ports"] = _merge_named_entries(
            base_schema.get("output_ports", []),
            manual_schema.get("output_ports", []),
        )
        nodes[name] = merged

    return nodes


def supported_waypoint_task_nodes():
    return deepcopy(_load_supported_node_schemas())


def _make_node(node_type, attrs=None, children=None):
    return {
        "id": str(uuid4()),
        "type": node_type,
        "attrs": attrs or {},
        "children": children or [],
    }


def create_default_waypoint_task_document(task_name):
    return {
        "task_name": task_name,
        "tree": _make_node("Sequence"),
    }


def _supported_node_schema(node_type):
    schema = _load_supported_node_schemas().get(node_type)
    if schema is None:
        raise ValueError(f"Unsupported node: {node_type}")
    return schema


def _parse_tree_node(element):
    _supported_node_schema(element.tag)
    children = [_parse_tree_node(child) for child in list(element)]
    return _make_node(element.tag, attrs=dict(element.attrib), children=children)


def parse_waypoint_task_xml(xml_text, task_name):
    root = ET.fromstring(xml_text)
    if root.tag != "root":
        raise ValueError("Root element must be <root>")
    if root.attrib.get("main_tree_to_execute") != "MainTree":
        raise ValueError("main_tree_to_execute must be MainTree")

    behavior_tree = root.find("BehaviorTree")
    if behavior_tree is None or behavior_tree.attrib.get("ID") != "MainTree":
        raise ValueError("BehaviorTree ID must be MainTree")

    children = list(behavior_tree)
    if len(children) != 1:
        raise ValueError("MainTree must contain exactly one top-level node")

    return {
        "task_name": task_name,
        "tree": _parse_tree_node(children[0]),
    }


def _validate_node(node):
    if node is None:
        raise ValueError("Waypoint task tree is empty")
    node_type = node.get("type", "")
    schema = _supported_node_schema(node_type)
    children = node.get("children", [])
    if schema["kind"] == "action" and children:
        raise ValueError(f"Leaf node {node_type} cannot have children")
    max_children = schema.get("max_children")
    min_children = schema.get("min_children", 0)
    if max_children is not None and len(children) > max_children:
        raise ValueError(f"Node {node_type} supports at most {max_children} children")
    if len(children) < min_children:
        raise ValueError(f"Node {node_type} requires at least {min_children} children")
    for child in children:
        _validate_node(child)


def _build_xml_node(node):
    attrs = {key: value for key, value in node.get("attrs", {}).items() if value not in ("", None)}
    element = ET.Element(node["type"], attrs)
    for child in node.get("children", []):
        element.append(_build_xml_node(child))
    return element


def serialize_waypoint_task_document(document):
    tree = document["tree"]
    if tree is None:
        raise ValueError("Waypoint task tree is empty")
    _validate_node(tree)

    root = ET.Element("root", {"main_tree_to_execute": "MainTree"})
    behavior_tree = ET.SubElement(root, "BehaviorTree", {"ID": "MainTree"})
    behavior_tree.append(_build_xml_node(tree))
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def load_waypoint_task_file(path):
    task_path = Path(path)
    xml_text = task_path.read_text(encoding="utf-8")
    return parse_waypoint_task_xml(xml_text, task_name=task_path.stem)


def save_waypoint_task_file(directory, task_name, document):
    task_dir = Path(directory)
    task_dir.mkdir(parents=True, exist_ok=True)
    task_path = task_dir / f"{task_name}.xml"
    task_document = {
        "task_name": task_name,
        "tree": document["tree"],
    }
    task_path.write_text(serialize_waypoint_task_document(task_document), encoding="utf-8")
    return task_path
