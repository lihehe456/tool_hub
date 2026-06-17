from collections import Counter
from copy import deepcopy
import json
import re
from pathlib import Path


FILENAME_RE = re.compile(r"^(?P<prefix>.+)_(?P<floor>\d+)_(?P<variant>\d+)\.json$")
TASK_PATTERNS = {
    "elevator_in_source": re.compile(r"^(?P<prefix>.+)_elevator_in_(?P<source>\d+)_x$"),
    "elevator_out_source_target": re.compile(
        r"^(?P<prefix>.+)_elevator_out_(?P<source>\d+)_(?P<target>\d+)$"
    ),
    "close_elevdoor": re.compile(r"^(?P<prefix>.+)_close_elevdoor_(?P<floor>\d+)$"),
    "elevator_in_target_source": re.compile(
        r"^(?P<prefix>.+)_elevator_in_(?P<target>\d+)_(?P<source>\d+)$"
    ),
    "elevator_out_target_source": re.compile(
        r"^(?P<prefix>.+)_elevator_out_(?P<target>\d+)_(?P<source>\d+)$"
    ),
}
SYMBOLIC_TASK_PATTERNS = {
    "elevator_in": re.compile(r"^.+_elevator_in_(?:n_x|x_n)$"),
    "elevator_out": re.compile(r"^.+_elevator_out_(?:n_x|x_n)$"),
    "close_elevdoor": re.compile(r"^.+_close_elevdoor_[nx]$"),
}


def resolve_directory(raw_path):
    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        raise ValueError("directory must be an absolute path")
    return target.resolve()


def parse_template_filename(path):
    path = Path(path)
    match = FILENAME_RE.match(path.name)
    if not match:
        raise ValueError(
            f"Template filename '{path.name}' does not match '<prefix>_<n>_<nn>.json'."
        )

    prefix = match.group("prefix")
    floor = int(match.group("floor"))
    variant = match.group("variant")
    if variant == f"{floor}01":
        suffix = "01"
    elif variant == f"{floor}03":
        suffix = "03"
    else:
        raise ValueError(
            f"Template filename '{path.name}' does not end with '{floor}01' or '{floor}03'."
        )

    return prefix, floor, suffix


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def iter_waypoint_task_ids(template_data):
    for subtask in template_data.get("subtasks", []):
        for waypoint in subtask.get("waypoints", []):
            task_id = waypoint.get("waypoint_task_id", "")
            if isinstance(task_id, str) and task_id:
                yield task_id


def uses_symbolic_floor_task_ids(template_data):
    for task_id in iter_waypoint_task_ids(template_data):
        if any(pattern.match(task_id) for pattern in SYMBOLIC_TASK_PATTERNS.values()):
            return True
    return False


def detect_task_id_mode(template_01_data, template_03_data):
    has_symbolic_01 = uses_symbolic_floor_task_ids(template_01_data)
    has_symbolic_03 = uses_symbolic_floor_task_ids(template_03_data)
    if has_symbolic_01 != has_symbolic_03:
        raise ValueError("Sample task id modes do not match.")
    return "symbolic" if has_symbolic_01 else "numeric"


def infer_source_floor(template_data, template_floor, fallback=None):
    candidates = []
    for task_id in iter_waypoint_task_ids(template_data):

        match = TASK_PATTERNS["elevator_in_source"].match(task_id)
        if match:
            candidates.append(int(match.group("source")))
            continue

        match = TASK_PATTERNS["elevator_out_source_target"].match(task_id)
        if match:
            source = int(match.group("source"))
            target = int(match.group("target"))
            if target == template_floor:
                candidates.append(source)
            elif source == template_floor:
                candidates.append(target)
            continue

        match = TASK_PATTERNS["elevator_in_target_source"].match(task_id)
        if match:
            target = int(match.group("target"))
            source = int(match.group("source"))
            if target == template_floor:
                candidates.append(source)
            elif source == template_floor:
                candidates.append(target)
            continue

        match = TASK_PATTERNS["elevator_out_target_source"].match(task_id)
        if match:
            target = int(match.group("target"))
            source = int(match.group("source"))
            if target == template_floor:
                candidates.append(source)
            elif source == template_floor:
                candidates.append(target)
            continue

        match = TASK_PATTERNS["close_elevdoor"].match(task_id)
        if match:
            floor = int(match.group("floor"))
            if floor != template_floor:
                candidates.append(floor)

    if candidates:
        return Counter(candidates).most_common(1)[0][0]
    if fallback is not None:
        return int(fallback)
    raise ValueError("Unable to infer source floor from template task ids.")


def validate_template_pair(template_01, template_03):
    template_01 = Path(template_01).resolve()
    template_03 = Path(template_03).resolve()
    prefix_01, floor_01, suffix_01 = parse_template_filename(template_01)
    prefix_03, floor_03, suffix_03 = parse_template_filename(template_03)

    if suffix_01 != "01":
        raise ValueError(f"Expected n01 sample, got '{template_01.name}'.")
    if suffix_03 != "03":
        raise ValueError(f"Expected n03 sample, got '{template_03.name}'.")
    if prefix_01 != prefix_03:
        raise ValueError("Sample prefixes do not match.")
    if floor_01 != floor_03:
        raise ValueError("Sample floors do not match.")

    template_01_data = load_json(template_01)
    template_03_data = load_json(template_03)
    task_id_mode = detect_task_id_mode(template_01_data, template_03_data)
    if task_id_mode == "symbolic":
        source_floor = None
    else:
        source_floor_01 = infer_source_floor(template_01_data, floor_01)
        source_floor_03 = infer_source_floor(template_03_data, floor_03)
        if source_floor_01 != source_floor_03:
            raise ValueError("Sample source floors do not match.")
        source_floor = source_floor_01

    return {
        "prefix": prefix_01,
        "template_floor": floor_01,
        "source_floor": source_floor,
        "task_id_mode": task_id_mode,
        "template_01_path": str(template_01),
        "template_03_path": str(template_03),
    }


def load_template_pair(template_01, template_03):
    return load_json(template_01), load_json(template_03)


def rewrite_waypoint_task_id(task_id, template_floor, target_floor, source_floor):
    if not isinstance(task_id, str):
        return task_id

    match = TASK_PATTERNS["elevator_in_source"].match(task_id)
    if match:
        prefix = match.group("prefix")
        return f"{prefix}_elevator_in_{source_floor}_x"

    match = TASK_PATTERNS["elevator_out_source_target"].match(task_id)
    if match:
        prefix = match.group("prefix")
        source = int(match.group("source"))
        target = int(match.group("target"))
        if target == template_floor:
            return f"{prefix}_elevator_out_{source}_{target_floor}"
        if source == template_floor:
            return f"{prefix}_elevator_out_{target_floor}_{target}"
        return task_id

    match = TASK_PATTERNS["close_elevdoor"].match(task_id)
    if match:
        prefix = match.group("prefix")
        floor = int(match.group("floor"))
        if floor == template_floor:
            return f"{prefix}_close_elevdoor_{target_floor}"
        return task_id

    match = TASK_PATTERNS["elevator_in_target_source"].match(task_id)
    if match:
        prefix = match.group("prefix")
        target = int(match.group("target"))
        source = int(match.group("source"))
        if target == template_floor:
            return f"{prefix}_elevator_in_{target_floor}_{source}"
        if source == template_floor:
            return f"{prefix}_elevator_in_{target}_{target_floor}"

    match = TASK_PATTERNS["elevator_out_target_source"].match(task_id)
    if match:
        prefix = match.group("prefix")
        target = int(match.group("target"))
        source = int(match.group("source"))
        if target == template_floor:
            return f"{prefix}_elevator_out_{target_floor}_{source}"
        if source == template_floor:
            return f"{prefix}_elevator_out_{target}_{target_floor}"

    return task_id


def build_output_data(template_data, output_name, template_floor, target_floor, source_floor, task_id_mode="numeric"):
    data = deepcopy(template_data)
    data["task_group_name"] = output_name

    rewrites = []
    if task_id_mode == "symbolic":
        return data, rewrites

    for subtask in data.get("subtasks", []):
        for waypoint in subtask.get("waypoints", []):
            if "waypoint_task_id" not in waypoint:
                continue
            before = waypoint["waypoint_task_id"]
            after = rewrite_waypoint_task_id(before, template_floor, target_floor, source_floor)
            if after != before:
                rewrites.append(
                    {
                        "subtask_name": subtask.get("subtask_name", ""),
                        "waypoint_id": waypoint.get("waypoint_id", ""),
                        "before": before,
                        "after": after,
                    }
                )
            waypoint["waypoint_task_id"] = after

    return data, rewrites


def build_output_name(prefix, target_floor, suffix):
    return f"{prefix}_{target_floor}_{target_floor}{suffix}"


def build_generated_file_records(
    template_path,
    template_data,
    prefix,
    template_floor,
    suffix,
    start,
    end,
    output_dir,
    source_floor,
    task_id_mode="numeric",
):
    output_dir = Path(output_dir).resolve()
    records = []
    for target_floor in range(start, end + 1):
        output_name = build_output_name(prefix, target_floor, suffix)
        output_path = output_dir / f"{output_name}.json"
        document, rewrites = build_output_data(
            template_data, output_name, template_floor, target_floor, source_floor, task_id_mode
        )
        records.append(
            {
                "template_path": str(Path(template_path).resolve()),
                "output_name": output_name,
                "output_path": str(output_path),
                "target_floor": target_floor,
                "suffix": suffix,
                "document": document,
                "rewrites": rewrites,
            }
        )
    return records


def sort_generated_file_records(records):
    suffix_order = {"01": 0, "03": 1}
    return sorted(
        records,
        key=lambda item: (item["target_floor"], suffix_order.get(item["suffix"], 99), item["output_name"]),
    )


def _normalize_source_floor(source_floor, template_data, template_floor):
    if source_floor is None or source_floor == "":
        return infer_source_floor(template_data, template_floor)
    return int(source_floor)


def preview_task_files(
    template_01,
    template_03,
    start,
    end,
    output_dir=None,
    elevator_floor=None,
):
    if start > end:
        raise ValueError("Start floor must be less than or equal to end floor.")

    pair = validate_template_pair(template_01, template_03)
    template_01_data, template_03_data = load_template_pair(template_01, template_03)
    output_dir = Path(output_dir).resolve() if output_dir else Path(template_01).resolve().parent
    if pair["task_id_mode"] == "symbolic":
        source_floor = None
    else:
        source_floor = _normalize_source_floor(elevator_floor, template_01_data, pair["template_floor"])

    generated_files = sort_generated_file_records(
        build_generated_file_records(
            template_01,
            template_01_data,
            pair["prefix"],
            pair["template_floor"],
            "01",
            start,
            end,
            output_dir,
            source_floor,
            pair["task_id_mode"],
        )
        + build_generated_file_records(
            template_03,
            template_03_data,
            pair["prefix"],
            pair["template_floor"],
            "03",
            start,
            end,
            output_dir,
            source_floor,
            pair["task_id_mode"],
        )
    )

    return {
        "pair": {
            **pair,
            "output_dir": str(output_dir),
        },
        "generated_files": [
            {
                key: value
                for key, value in record.items()
                if key not in {"document"}
            }
            for record in generated_files
        ],
    }


def write_json(path, data):
    path = Path(path)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
        file.write("\n")


def generate_task_files(
    template_01,
    template_03,
    start,
    end,
    output_dir=None,
    overwrite=False,
    elevator_floor=None,
):
    if start > end:
        raise ValueError("Start floor must be less than or equal to end floor.")

    pair = validate_template_pair(template_01, template_03)
    template_01_data, template_03_data = load_template_pair(template_01, template_03)
    output_dir = Path(output_dir).resolve() if output_dir else Path(template_01).resolve().parent
    output_dir.mkdir(parents=True, exist_ok=True)
    if pair["task_id_mode"] == "symbolic":
        source_floor = None
    else:
        source_floor = _normalize_source_floor(elevator_floor, template_01_data, pair["template_floor"])

    generated_files = sort_generated_file_records(
        build_generated_file_records(
            template_01,
            template_01_data,
            pair["prefix"],
            pair["template_floor"],
            "01",
            start,
            end,
            output_dir,
            source_floor,
            pair["task_id_mode"],
        )
        + build_generated_file_records(
            template_03,
            template_03_data,
            pair["prefix"],
            pair["template_floor"],
            "03",
            start,
            end,
            output_dir,
            source_floor,
            pair["task_id_mode"],
        )
    )

    created_files = []
    for record in generated_files:
        output_path = Path(record["output_path"])
        if output_path.exists() and not overwrite:
            raise FileExistsError(
                f"Target file already exists: {output_path}. Use overwrite to replace it."
            )
        write_json(output_path, record["document"])
        created_files.append(str(output_path))

    return {
        "pair": {
            **pair,
            "output_dir": str(output_dir),
        },
        "generated_files": [
            {
                key: value
                for key, value in record.items()
                if key not in {"document"}
            }
            for record in generated_files
        ],
        "created_files": created_files,
    }


def discover_template_pairs(directory):
    root = resolve_directory(directory)
    grouped = {}

    for path in root.rglob("*.json"):
        try:
            prefix, floor, suffix = parse_template_filename(path)
        except ValueError:
            continue

        key = (str(path.parent.resolve()), prefix, floor)
        record = grouped.setdefault(
            key,
            {
                "directory": str(path.parent.resolve()),
                "prefix": prefix,
                "template_floor": floor,
                "template_01_path": "",
                "template_03_path": "",
            },
        )
        target_field = "template_01_path" if suffix == "01" else "template_03_path"
        if record[target_field] and record[target_field] != str(path.resolve()):
            raise ValueError(f"Duplicate sample file for {prefix}_{floor}_{suffix} in {path.parent}")
        record[target_field] = str(path.resolve())

    pairs = []
    for record in grouped.values():
        if not (record["template_01_path"] and record["template_03_path"]):
            continue
        template_01_data = load_json(record["template_01_path"])
        template_03_data = load_json(record["template_03_path"])
        task_id_mode = detect_task_id_mode(template_01_data, template_03_data)
        if task_id_mode == "symbolic":
            source_floor = None
        else:
            source_floor_01 = infer_source_floor(template_01_data, record["template_floor"])
            source_floor_03 = infer_source_floor(template_03_data, record["template_floor"])
            if source_floor_01 != source_floor_03:
                raise ValueError(
                    f"Sample pair source floors do not match for {record['prefix']}_{record['template_floor']}."
                )
            source_floor = source_floor_01
        pairs.append(
            {
                **record,
                "source_floor": source_floor,
                "task_id_mode": task_id_mode,
            }
        )

    pairs.sort(key=lambda item: (item["directory"], item["prefix"], item["template_floor"]))
    return pairs
