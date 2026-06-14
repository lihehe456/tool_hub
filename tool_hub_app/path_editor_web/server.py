#!/usr/bin/env python3

import base64
import json
import struct
import sys
import zlib
from pathlib import Path

import yaml
from flask import Flask, jsonify, request

try:
    from runtime_paths import default_maps_root, default_paths_root
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from runtime_paths import default_maps_root, default_paths_root

try:
    from path_editor_web.task_group_builder import (
        add_subtask_pair,
        build_subtask_pair_from_path_document,
        create_workspace,
        create_mixer_workspace,
        export_task_group_document,
        import_sidecar_workspace_into_mixer,
        load_workspace_file,
        replace_subtask_pair,
        save_workspace_file,
    )
    from tool_hub_web.virtual_wall_builder import load_virtual_wall_file
except ModuleNotFoundError:
    from task_group_builder import (
        add_subtask_pair,
        build_subtask_pair_from_path_document,
        create_workspace,
        create_mixer_workspace,
        export_task_group_document,
        import_sidecar_workspace_into_mixer,
        load_workspace_file,
        replace_subtask_pair,
        save_workspace_file,
    )
    from tool_hub_web.virtual_wall_builder import load_virtual_wall_file


DEFAULT_PATHS_ROOT = default_paths_root()
DEFAULT_MAPS_ROOT = default_maps_root()


def parse_pgm(pgm_path):
    with pgm_path.open("rb") as file_obj:
        magic = file_obj.readline().strip()
        if magic != b"P5":
            raise ValueError(f"Only binary PGM (P5) supported, got {magic!r}")

        line = file_obj.readline()
        while line.startswith(b"#"):
            line = file_obj.readline()

        width, height = map(int, line.split())
        max_value = int(file_obj.readline().strip())
        if max_value > 255:
            raise ValueError("Only 8-bit PGM files are supported")

        raw = file_obj.read()

    return width, height, raw


def pgm_to_png_base64(pgm_path):
    width, height, raw = parse_pgm(pgm_path)

    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        return (
            struct.pack(">I", len(data))
            + chunk
            + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += make_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))

    rows = []
    for row_index in range(height):
        row = raw[row_index * width : (row_index + 1) * width]
        rows.append(b"\x00" + row)

    png += make_chunk(b"IDAT", zlib.compress(b"".join(rows)))
    png += make_chunk(b"IEND", b"")
    return base64.b64encode(png).decode("ascii"), width, height


VIRTUAL_WALL_FILENAMES = (
    "map_walls.yaml",
    "map_walls.yml",
    "map-walls.yaml",
    "map-walls.yml",
    "map_wall.yaml",
    "map_wall.yml",
    "map-wall.yaml",
    "map-wall.yml",
    "virtual_walls.yaml",
    "virtual_walls.yml",
    "virtual_wall.yaml",
    "virtual_wall.yml",
    "walls.yaml",
    "walls.yml",
)


def find_virtual_wall_file_for_map(yaml_path):
    map_dir = Path(yaml_path).resolve().parent
    for file_name in VIRTUAL_WALL_FILENAMES:
        candidate = map_dir / file_name
        if candidate.is_file():
            return candidate
    return None


def load_virtual_wall_overlay(yaml_path, map_origin):
    wall_path = find_virtual_wall_file_for_map(yaml_path)
    if wall_path is None:
        return None, []

    document = load_virtual_wall_file(wall_path, current_map_origin=map_origin)
    return wall_path, document.get("polylines", [])


def is_within_root(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_target(raw_path, root):
    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        target = root / target
    target = target.resolve()

    if not is_within_root(target, root):
        raise ValueError(f"Path is outside configured root: {target}")

    return target


def json_error(message, status_code):
    return jsonify({"error": message}), status_code


def resolve_user_json_path(raw_path, field_name):
    if not raw_path:
        raise ValueError(f"{field_name} is required")

    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        raise ValueError(f"{field_name} must be an absolute path")
    if target.suffix.lower() != ".json":
        raise ValueError(f"{field_name} must point to a .json file")
    return target.resolve()


def resolve_user_directory_path(raw_path, field_name):
    if not raw_path:
        raise ValueError(f"{field_name} is required")

    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        raise ValueError(f"{field_name} must be an absolute path")
    return target.resolve()


def workspace_name_from_path(workspace_path):
    workspace_path = Path(workspace_path)
    if workspace_path.suffixes[-2:] == [".workspace", ".json"]:
        return workspace_path.name[: -len(".workspace.json")]
    if workspace_path.suffix.lower() == ".json":
        return workspace_path.stem
    return workspace_path.name


def build_entries(directory, suffix):
    entries = []
    for child in sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        entry = {
            "name": child.name,
            "path": str(child),
            "is_dir": child.is_dir(),
        }
        if suffix == ".json":
            entry["is_json"] = child.is_file() and child.suffix.lower() == ".json"
        elif suffix == ".yaml":
            entry["is_yaml"] = child.is_file() and child.suffix.lower() in {".yaml", ".yml"}
        entries.append(entry)
    return entries


def build_user_entries(directory):
    entries = []
    for child in sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        entries.append(
            {
                "name": child.name,
                "path": str(child),
                "is_dir": child.is_dir(),
                "is_json": child.is_file() and child.suffix.lower() == ".json",
                "is_workspace_json": child.is_file() and child.name.endswith(".workspace.json"),
            }
        )
    return entries


def create_app(test_config=None):
    app = Flask(__name__, static_folder="static")
    app.config.update(
        PATHS_ROOT=str(DEFAULT_PATHS_ROOT),
        MAPS_ROOT=str(DEFAULT_MAPS_ROOT),
    )

    if test_config is not None:
        app.config.update(test_config)

    def paths_root():
        return Path(app.config["PATHS_ROOT"]).resolve()

    def maps_root():
        return Path(app.config["MAPS_ROOT"]).resolve()

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/api/runtime_config")
    def runtime_config():
        return jsonify(
            {
                "paths_root": str(paths_root()),
                "maps_root": str(maps_root()),
                "user_root": str(Path.home()),
            }
        )

    @app.get("/task-groups")
    def task_groups():
        return app.send_static_file("task-group.html")

    @app.get("/task-group-mixer")
    def task_group_mixer():
        return app.send_static_file("task-group-mixer.html")

    @app.post("/api/load_map")
    def load_map():
        yaml_raw = (request.get_json(silent=True) or {}).get("yaml_path", "")
        if not yaml_raw:
            return json_error("yaml_path is required", 400)

        try:
            yaml_path = resolve_target(yaml_raw, maps_root())
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not yaml_path.is_file():
            return json_error(f"Map yaml not found: {yaml_path}", 404)

        meta = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        image_name = meta.get("image")
        if not image_name:
            return json_error(f"Map yaml missing image field: {yaml_path}", 400)

        pgm_path = (yaml_path.parent / image_name).resolve()
        if not pgm_path.is_file():
            return json_error(f"PGM not found: {pgm_path}", 404)

        image_b64, width, height = pgm_to_png_base64(pgm_path)
        wall_path, virtual_walls = load_virtual_wall_overlay(yaml_path, meta.get("origin"))
        return jsonify(
            {
                "image_b64": image_b64,
                "resolution": meta.get("resolution"),
                "origin": meta.get("origin"),
                "width": width,
                "height": height,
                "virtual_wall_path": str(wall_path) if wall_path else None,
                "virtual_walls": virtual_walls,
            }
        )

    @app.post("/api/browse_paths")
    def browse_paths():
        raw_path = (request.get_json(silent=True) or {}).get("path", str(paths_root()))

        try:
            target = resolve_target(raw_path, paths_root())
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not target.exists():
            return json_error(f"Directory not found: {target}", 404)
        if not target.is_dir():
            target = target.parent

        return jsonify(
            {
                "cwd": str(target),
                "parent": str(target.parent) if target != paths_root() else str(paths_root()),
                "entries": build_entries(target, ".json"),
            }
        )

    @app.post("/api/browse_user_files")
    def browse_user_files():
        raw_path = (request.get_json(silent=True) or {}).get("path", str(Path.home()))
        target = Path(raw_path).expanduser()
        if not target.is_absolute():
            return json_error("path must be an absolute path", 400)
        if not target.exists():
            target = target.parent
        if not target.is_dir():
            target = target.parent

        return jsonify(
            {
                "cwd": str(target.resolve()),
                "parent": str(target.resolve().parent),
                "entries": build_user_entries(target.resolve()),
            }
        )

    @app.post("/api/browse_maps")
    def browse_maps():
        raw_path = (request.get_json(silent=True) or {}).get("path", str(maps_root()))

        try:
            target = resolve_target(raw_path, maps_root())
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not target.exists():
            return json_error(f"Directory not found: {target}", 404)
        if not target.is_dir():
            target = target.parent

        return jsonify(
            {
                "cwd": str(target),
                "parent": str(target.parent) if target != maps_root() else str(maps_root()),
                "entries": build_entries(target, ".yaml"),
            }
        )

    @app.post("/api/load_path")
    def load_path():
        raw_path = (request.get_json(silent=True) or {}).get("path", "")
        if not raw_path:
            return json_error("path is required", 400)

        try:
            target = resolve_target(raw_path, paths_root())
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not target.is_file():
            return json_error(f"Path file not found: {target}", 404)

        return jsonify(json.loads(target.read_text(encoding="utf-8")))

    @app.post("/api/build_subtasks_from_path")
    def build_subtasks_from_path():
        payload = request.get_json(silent=True) or {}
        raw_path = payload.get("path", "")
        generated_subtask_name = payload.get("generated_subtask_name", "")

        if not raw_path:
            return json_error("path is required", 400)
        if not generated_subtask_name:
            return json_error("generated_subtask_name is required", 400)

        try:
            target = resolve_target(raw_path, paths_root())
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not target.is_file():
            return json_error(f"Path file not found: {target}", 404)

        path_document = json.loads(target.read_text(encoding="utf-8"))
        forward_subtask, return_subtask = build_subtask_pair_from_path_document(
            path_document,
            source_path=str(target),
            generated_subtask_name=generated_subtask_name,
        )
        return jsonify(
            {
                "forward_subtask": forward_subtask,
                "return_subtask": return_subtask,
            }
        )

    @app.post("/api/save_path")
    def save_path():
        payload = request.get_json(silent=True) or {}
        raw_path = payload.get("path", "")
        document = payload.get("document")

        if not raw_path:
            return json_error("path is required", 400)
        if document is None:
            return json_error("document is required", 400)

        try:
            target = resolve_target(raw_path, paths_root())
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not target.exists():
            return json_error(f"Path file not found: {target}", 404)

        target.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify({"ok": True, "path": str(target)})

    @app.post("/api/save_path_as")
    def save_path_as():
        payload = request.get_json(silent=True) or {}
        raw_path = payload.get("path", "")
        document = payload.get("document")

        if not raw_path:
            return json_error("path is required", 400)
        if document is None:
            return json_error("document is required", 400)

        try:
            target = resolve_target(raw_path, paths_root())
        except ValueError as exc:
            return json_error(str(exc), 400)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify({"ok": True, "path": str(target)})

    @app.post("/api/load_task_workspace")
    def load_task_workspace():
        raw_workspace_path = (request.get_json(silent=True) or {}).get("workspace_path", "")

        try:
            workspace_path = resolve_user_json_path(raw_workspace_path, "workspace_path")
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not workspace_path.is_file():
            return json_error(f"Workspace file not found: {workspace_path}", 404)

        return jsonify({"workspace": load_workspace_file(workspace_path)})

    @app.post("/api/save_task_workspace")
    def save_task_workspace():
        payload = request.get_json(silent=True) or {}
        raw_workspace_path = payload.get("workspace_path", "")
        workspace = payload.get("workspace")

        try:
            workspace_path = resolve_user_json_path(raw_workspace_path, "workspace_path")
        except ValueError as exc:
            return json_error(str(exc), 400)

        if workspace is None:
            return json_error("workspace is required", 400)

        saved_workspace = save_workspace_file(workspace_path, workspace)
        return jsonify({"ok": True, "workspace": saved_workspace})

    @app.post("/api/create_task_workspace")
    def create_task_workspace():
        raw_workspace_path = (request.get_json(silent=True) or {}).get("workspace_path", "")

        try:
            workspace_path = resolve_user_json_path(raw_workspace_path, "workspace_path")
        except ValueError as exc:
            return json_error(str(exc), 400)

        created = False
        if workspace_path.is_file():
            workspace = load_workspace_file(workspace_path)
        else:
            workspace = create_workspace(workspace_name_from_path(workspace_path))
            workspace = save_workspace_file(workspace_path, workspace)
            created = True

        return jsonify({"ok": True, "created": created, "workspace": workspace})

    @app.post("/api/load_or_create_mixer_workspace")
    def load_or_create_mixer_workspace():
        raw_workspace_path = (request.get_json(silent=True) or {}).get("workspace_path", "")

        try:
            workspace_path = resolve_user_json_path(raw_workspace_path, "workspace_path")
        except ValueError as exc:
            return json_error(str(exc), 400)

        created = False
        if workspace_path.is_file():
            workspace = load_workspace_file(workspace_path)
        else:
            workspace = create_mixer_workspace(workspace_path.stem)
            workspace = save_workspace_file(workspace_path, workspace)
            created = True

        return jsonify({"ok": True, "created": created, "workspace": workspace})

    @app.post("/api/import_sidecar_workspace_into_mixer")
    def import_sidecar_workspace_into_mixer_api():
        payload = request.get_json(silent=True) or {}
        raw_workspace_path = payload.get("workspace_path", "")
        raw_source_workspace_path = payload.get("source_workspace_path", "")

        try:
            workspace_path = resolve_user_json_path(raw_workspace_path, "workspace_path")
            source_workspace_path = resolve_user_json_path(
                raw_source_workspace_path,
                "source_workspace_path",
            )
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not workspace_path.is_file():
            return json_error(f"Workspace file not found: {workspace_path}", 404)
        if source_workspace_path.suffixes[-2:] != [".workspace", ".json"]:
            return json_error("source_workspace_path must point to a .workspace.json file", 400)
        if not source_workspace_path.is_file():
            return json_error(f"Workspace file not found: {source_workspace_path}", 404)

        mixer_workspace = load_workspace_file(workspace_path)
        sidecar_workspace = load_workspace_file(source_workspace_path)
        if not isinstance(sidecar_workspace.get("subtasks"), list):
            return json_error("source workspace missing subtasks", 400)

        mixer_workspace = import_sidecar_workspace_into_mixer(
            mixer_workspace,
            sidecar_workspace,
            source_workspace_path=str(source_workspace_path),
        )
        mixer_workspace = save_workspace_file(workspace_path, mixer_workspace)
        return jsonify({"ok": True, "workspace": mixer_workspace})

    @app.post("/api/add_subtask_pair_to_workspace")
    def add_subtask_pair_to_workspace():
        payload = request.get_json(silent=True) or {}
        raw_workspace_path = payload.get("workspace_path", "")
        forward_subtask = payload.get("forward_subtask")
        return_subtask = payload.get("return_subtask")

        try:
            workspace_path = resolve_user_json_path(raw_workspace_path, "workspace_path")
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not workspace_path.is_file():
            return json_error(f"Workspace file not found: {workspace_path}", 404)
        if forward_subtask is None or return_subtask is None:
            return json_error("forward_subtask and return_subtask are required", 400)

        workspace = load_workspace_file(workspace_path)
        workspace = add_subtask_pair(workspace, [forward_subtask, return_subtask])
        workspace = save_workspace_file(workspace_path, workspace)
        return jsonify({"ok": True, "workspace": workspace})

    @app.post("/api/replace_subtask_pair_in_workspace")
    def replace_subtask_pair_in_workspace():
        payload = request.get_json(silent=True) or {}
        raw_workspace_path = payload.get("workspace_path", "")
        old_pair_id = payload.get("old_pair_id", "")
        forward_subtask = payload.get("forward_subtask")
        return_subtask = payload.get("return_subtask")

        try:
            workspace_path = resolve_user_json_path(raw_workspace_path, "workspace_path")
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not workspace_path.is_file():
            return json_error(f"Workspace file not found: {workspace_path}", 404)
        if not old_pair_id:
            return json_error("old_pair_id is required", 400)
        if forward_subtask is None or return_subtask is None:
            return json_error("forward_subtask and return_subtask are required", 400)

        workspace = load_workspace_file(workspace_path)
        workspace = replace_subtask_pair(
            workspace,
            old_pair_id=old_pair_id,
            new_pair=[forward_subtask, return_subtask],
        )
        workspace = save_workspace_file(workspace_path, workspace)
        return jsonify({"ok": True, "workspace": workspace})

    @app.post("/api/export_task_group")
    def export_task_group():
        payload = request.get_json(silent=True) or {}
        raw_workspace_path = payload.get("workspace_path", "")
        raw_export_directory = payload.get("export_directory", "")

        try:
            workspace_path = resolve_user_json_path(raw_workspace_path, "workspace_path")
            export_directory = resolve_user_directory_path(raw_export_directory, "export_directory")
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not workspace_path.is_file():
            return json_error(f"Workspace file not found: {workspace_path}", 404)

        workspace = load_workspace_file(workspace_path)
        task_group_name = workspace.get("task_group_name", "").strip()
        if not task_group_name:
            return json_error("task_group_name is required before export", 400)

        task_group_document = export_task_group_document(workspace)
        export_directory.mkdir(parents=True, exist_ok=True)
        export_path = export_directory / f"{task_group_name}.json"
        export_path.write_text(
            json.dumps(task_group_document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return jsonify({"ok": True, "path": str(export_path), "task_group": task_group_document})

    @app.post("/api/rename_path")
    def rename_path():
        payload = request.get_json(silent=True) or {}
        raw_src_path = payload.get("src_path", "")
        raw_dst_path = payload.get("dst_path", "")

        if not raw_src_path or not raw_dst_path:
            return json_error("src_path and dst_path are required", 400)

        try:
            src_path = resolve_target(raw_src_path, paths_root())
            dst_path = resolve_target(raw_dst_path, paths_root())
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not src_path.exists():
            return json_error(f"Path file not found: {src_path}", 404)
        if dst_path.exists():
            return json_error(f"Destination already exists: {dst_path}", 400)

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.rename(dst_path)
        return jsonify({"ok": True, "path": str(dst_path)})

    @app.post("/api/delete_path")
    def delete_path():
        raw_path = (request.get_json(silent=True) or {}).get("path", "")
        if not raw_path:
            return json_error("path is required", 400)

        try:
            target = resolve_target(raw_path, paths_root())
        except ValueError as exc:
            return json_error(str(exc), 400)

        if not target.exists():
            return json_error(f"Path file not found: {target}", 404)

        target.unlink()
        return jsonify({"ok": True})

    return app


if __name__ == "__main__":
    create_app().run(port=7790, debug=False)
