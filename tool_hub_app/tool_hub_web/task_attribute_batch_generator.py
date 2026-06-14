from copy import deepcopy
import json
import re
from pathlib import Path


XML_FILENAME_PATTERNS = {
    "close_elevdoor": re.compile(r"^(?P<prefix>.+)_close_elevdoor_(?P<a>[A-Za-z0-9]+)\.xml$"),
    "elevator_in": re.compile(
        r"^(?P<prefix>.+)_elevator_in_(?P<a>[A-Za-z0-9]+)_(?P<b>[A-Za-z0-9]+)\.xml$"
    ),
    "elevator_out": re.compile(
        r"^(?P<prefix>.+)_elevator_out_(?P<a>[A-Za-z0-9]+)_(?P<b>[A-Za-z0-9]+)\.xml$"
    ),
}
TASK_ID_PATTERNS = {
    "close_elevdoor": re.compile(r"^(?P<prefix>.+)_close_elevdoor_(?P<floor>\d+)$"),
    "elevator_in_source": re.compile(r"^(?P<prefix>.+)_elevator_in_(?P<source>\d+)_x$"),
    "elevator_in_pair": re.compile(
        r"^(?P<prefix>.+)_elevator_in_(?P<a>\d+)_(?P<b>\d+)$"
    ),
    "elevator_out_pair": re.compile(
        r"^(?P<prefix>.+)_elevator_out_(?P<a>\d+)_(?P<b>\d+)$"
    ),
}
XML_TARGET_FLOOR_RE = re.compile(r'target_floor="([^"]+)"')
XML_COMMAND_RE = re.compile(r'command="([^"]+)"')


def resolve_directory(raw_path):
    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        raise ValueError("directory must be an absolute path")
    return target.resolve()


def resolve_file(raw_path, field_name):
    if not raw_path:
        raise ValueError(f"{field_name} is required")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{field_name} must be an absolute path")
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"{field_name} not found: {path}")
    return path


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def parse_template_xml_filename(path):
    path = Path(path)
    for attribute_type, pattern in XML_FILENAME_PATTERNS.items():
        match = pattern.match(path.name)
        if match:
            return {
                "attribute_type": attribute_type,
                "prefix": match.group("prefix"),
                "parts": tuple(
                    value for key, value in sorted(match.groupdict().items()) if key.startswith("a") or key.startswith("b")
                ),
                "path": str(path.resolve()),
                "name": path.name,
            }
    raise ValueError(f"Unsupported attribute template filename: {path.name}")


def extract_task_ids(task_data):
    task_ids = []
    for subtask in task_data.get("subtasks", []):
        for waypoint in subtask.get("waypoints", []):
            task_id = waypoint.get("waypoint_task_id", "")
            if isinstance(task_id, str) and task_id:
                task_ids.append(task_id)
    return task_ids


def infer_reference_context(reference_task_path):
    task_path = resolve_file(reference_task_path, "reference_task_path")
    data = load_json(task_path)
    task_ids = extract_task_ids(data)

    fixed_floor = None
    variable_floor = None

    for task_id in task_ids:
        match = TASK_ID_PATTERNS["elevator_in_source"].match(task_id)
        if match:
            fixed_floor = int(match.group("source"))
            break

    for task_id in task_ids:
        match = TASK_ID_PATTERNS["elevator_out_pair"].match(task_id)
        if not match:
            continue
        a = int(match.group("a"))
        b = int(match.group("b"))
        if fixed_floor is not None:
            if a == fixed_floor and b != fixed_floor:
                variable_floor = b
                break
            if b == fixed_floor and a != fixed_floor:
                variable_floor = a
                break

    if fixed_floor is None or variable_floor is None:
        raise ValueError(f"Unable to infer fixed and variable floors from reference task: {task_path}")

    return {
        "reference_task_path": str(task_path),
        "fixed_floor": fixed_floor,
        "variable_floor": variable_floor,
        "task_ids": task_ids,
    }


def classify_attribute_template(template_xml_path, reference_context):
    info = parse_template_xml_filename(template_xml_path)
    fixed_floor = reference_context["fixed_floor"]
    variable_floor = reference_context["variable_floor"]
    parts = info["parts"]

    role = None
    if info["attribute_type"] == "close_elevdoor":
        part = parts[0]
        if part.isdigit() and int(part) == variable_floor:
            role = "variable"
        elif part.isdigit() and int(part) == fixed_floor:
            role = "fixed"
        else:
            role = "variable"
    elif info["attribute_type"] in {"elevator_in", "elevator_out"}:
        if len(parts) != 2:
            raise ValueError(f"Unsupported attribute filename format: {info['name']}")
        first, second = parts
        first_is_fixed = first.isdigit() and int(first) == fixed_floor
        second_is_fixed = second.isdigit() and int(second) == fixed_floor

        if second_is_fixed and first != "x":
            role = "variable_fixed"
        elif first_is_fixed:
            role = "fixed_variable"
        elif second == "x":
            role = "fixed_variable"
        else:
            raise ValueError(
                f"Template {info['name']} does not match reference task floors "
                f"(fixed={fixed_floor}, variable={variable_floor})."
            )

    return {
        **info,
        "variant_role": role,
        "fixed_floor": fixed_floor,
        "variable_floor": variable_floor,
    }


def build_output_xml_name(template_info, target_floor):
    prefix = template_info["prefix"]
    attribute_type = template_info["attribute_type"]
    role = template_info["variant_role"]
    fixed_floor = template_info["fixed_floor"]

    if attribute_type == "close_elevdoor":
        return f"{prefix}_close_elevdoor_{target_floor}.xml"
    if attribute_type == "elevator_in":
        if role == "variable_fixed":
            return f"{prefix}_elevator_in_{target_floor}_{fixed_floor}.xml"
        return f"{prefix}_elevator_in_{fixed_floor}_{target_floor}.xml"
    if attribute_type == "elevator_out":
        if role == "variable_fixed":
            return f"{prefix}_elevator_out_{target_floor}_{fixed_floor}.xml"
        return f"{prefix}_elevator_out_{fixed_floor}_{target_floor}.xml"
    raise ValueError(f"Unsupported attribute type: {attribute_type}")


def replace_all_matches(text, pattern, transform):
    rewrites = []

    def repl(match):
        before = match.group(0)
        after = transform(match)
        if before != after:
            rewrites.append({"before": before, "after": after})
        return after

    return pattern.sub(repl, text), rewrites


def rewrite_close_elevdoor_xml(xml_text, target_floor):
    return replace_all_matches(
        xml_text,
        XML_COMMAND_RE,
        lambda match: f'command="{target_floor}-"',
    )


def rewrite_elevator_in_xml(xml_text, template_info, target_floor):
    role = template_info["variant_role"]
    fixed_floor = template_info["fixed_floor"]
    target_value = target_floor if role == "variable_fixed" else fixed_floor
    command_floor = target_floor if role == "variable_fixed" else fixed_floor

    updated_text, tf_rewrites = replace_all_matches(
        xml_text,
        XML_TARGET_FLOOR_RE,
        lambda match: f'target_floor="{target_value}"',
    )

    def command_transform(match):
        value = match.group(1)
        suffix = value[-1] if value and value[-1] in "+-" else ""
        if not suffix:
            return match.group(0)
        return f'command="{command_floor}{suffix}"'

    updated_text, cmd_rewrites = replace_all_matches(updated_text, XML_COMMAND_RE, command_transform)
    return updated_text, tf_rewrites + cmd_rewrites


def rewrite_elevator_out_xml(xml_text, template_info, target_floor):
    role = template_info["variant_role"]
    fixed_floor = template_info["fixed_floor"]

    if role == "fixed_variable":
        target_value = target_floor

        def command_transform(match):
            value = match.group(1)
            suffix = value[-1] if value and value[-1] in "+-" else ""
            if not suffix:
                return match.group(0)
            floor = fixed_floor if suffix == "-" else target_floor
            return f'command="{floor}{suffix}"'
    else:
        target_value = fixed_floor

        def command_transform(match):
            value = match.group(1)
            suffix = value[-1] if value and value[-1] in "+-" else ""
            if not suffix:
                return match.group(0)
            floor = target_floor if suffix == "-" else fixed_floor
            return f'command="{floor}{suffix}"'

    updated_text, tf_rewrites = replace_all_matches(
        xml_text,
        XML_TARGET_FLOOR_RE,
        lambda match: f'target_floor="{target_value}"',
    )
    updated_text, cmd_rewrites = replace_all_matches(updated_text, XML_COMMAND_RE, command_transform)
    return updated_text, tf_rewrites + cmd_rewrites


def rewrite_attribute_xml(xml_text, template_info, target_floor):
    if template_info["attribute_type"] == "close_elevdoor":
        return rewrite_close_elevdoor_xml(xml_text, target_floor)
    if template_info["attribute_type"] == "elevator_in":
        return rewrite_elevator_in_xml(xml_text, template_info, target_floor)
    if template_info["attribute_type"] == "elevator_out":
        return rewrite_elevator_out_xml(xml_text, template_info, target_floor)
    raise ValueError(f"Unsupported attribute type: {template_info['attribute_type']}")


def build_generated_attribute_records(
    reference_task_path,
    template_xml_path,
    start,
    end,
    output_dir,
):
    if start > end:
        raise ValueError("Start floor must be less than or equal to end floor.")

    reference_context = infer_reference_context(reference_task_path)
    template_path = resolve_file(template_xml_path, "template_xml_path")
    template_info = classify_attribute_template(template_path, reference_context)
    template_xml_text = template_path.read_text(encoding="utf-8")
    output_dir = resolve_directory(output_dir) if output_dir else template_path.parent.resolve()

    records = []
    for target_floor in range(start, end + 1):
        output_name = build_output_xml_name(template_info, target_floor)
        output_path = output_dir / output_name
        xml_text, rewrites = rewrite_attribute_xml(template_xml_text, template_info, target_floor)
        records.append(
            {
                "reference_task_path": reference_context["reference_task_path"],
                "template_xml_path": str(template_path),
                "output_name": output_name,
                "output_path": str(output_path),
                "target_floor": target_floor,
                "attribute_type": template_info["attribute_type"],
                "variant_role": template_info["variant_role"],
                "fixed_floor": template_info["fixed_floor"],
                "variable_floor": template_info["variable_floor"],
                "xml_text": xml_text,
                "rewrites": rewrites,
            }
        )
    return {
        "reference": reference_context,
        "template": {
            key: value
            for key, value in template_info.items()
            if key not in {"parts"}
        },
        "generated_files": records,
    }


def preview_task_attribute_files(
    reference_task_path,
    template_xml_path,
    start,
    end,
    output_dir=None,
):
    result = build_generated_attribute_records(
        reference_task_path=reference_task_path,
        template_xml_path=template_xml_path,
        start=start,
        end=end,
        output_dir=output_dir,
    )
    return {
        "reference": result["reference"],
        "template": result["template"],
        "generated_files": [
            {
                key: value
                for key, value in record.items()
                if key != "xml_text"
            }
            for record in result["generated_files"]
        ],
    }


def generate_task_attribute_files(
    reference_task_path,
    template_xml_path,
    start,
    end,
    output_dir=None,
    overwrite=False,
):
    result = build_generated_attribute_records(
        reference_task_path=reference_task_path,
        template_xml_path=template_xml_path,
        start=start,
        end=end,
        output_dir=output_dir,
    )

    created_files = []
    for record in result["generated_files"]:
        output_path = Path(record["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"Target file already exists: {output_path}. Use overwrite to replace it.")
        output_path.write_text(record["xml_text"], encoding="utf-8")
        created_files.append(str(output_path))

    return {
        "reference": result["reference"],
        "template": result["template"],
        "generated_files": [
            {
                key: value
                for key, value in record.items()
                if key != "xml_text"
            }
            for record in result["generated_files"]
        ],
        "created_files": created_files,
    }
